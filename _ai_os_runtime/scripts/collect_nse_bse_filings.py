#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import ssl
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any


RUNTIME_ROOT = Path(os.environ.get("AI_OS_RUNTIME_ROOT") or Path(__file__).absolute().parents[1])
POSTGRES_PASSWORD = os.environ.get("AI_OS_POSTGRES_PASSWORD", "ai_os_local_dev_change_me")
POSTGRES_PORT = os.environ.get("AI_OS_POSTGRES_PORT", "54329")
USER_AGENT = os.environ.get(
    "AI_OS_PUBLIC_CHECK_USER_AGENT",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 AI-OS-Research/0.1",
)

NSE_PAGE_URL = "https://www.nseindia.com/companies-listing/corporate-filings-announcements"
BSE_PAGE_URL = "https://www.bseindia.com/corporates/ann.html"
BSE_API_URL = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
INDIA_TZ = dt.timezone(dt.timedelta(hours=5, minutes=30))

SPECIAL_EVENT_KEYWORDS = [
    ("reverse_merger", ["reverse merger", "reverse takeover"]),
    ("demerger", ["demerger", "de-merger", "resulting company pursuant to the scheme"]),
    ("merger", ["merger", "amalgamation", "merged with"]),
    ("scheme_arrangement", ["scheme of arrangement", "arrangement with creditors", "share exchange ratio"]),
    ("buyback", ["buyback", "buy-back", "tender offer for equity shares"]),
    ("open_offer", ["open offer", "public announcement under sebi takeover", "letter of offer"]),
    ("delisting", ["delisting", "de-listing", "exit offer"]),
    ("rights_issue", ["rights issue", "rights entitlement"]),
    ("preferential_allotment", ["preferential issue", "preferential allotment", "allotment of warrants", "convertible warrants", "qualified institutions placement", "qip"]),
    ("asset_sale", ["slump sale", "asset sale", "sale of undertaking", "business transfer agreement"]),
    ("pledge_change", ["pledge of shares", "release of pledge", "invocation of pledge", "encumbrance on shares"]),
    ("insolvency", ["corporate insolvency", "insolvency resolution process", "admitted under ibc", "nclt admits", "resolution plan approved"]),
    ("board_action", ["board meeting", "record date", "dividend", "bonus issue", "stock split", "sub-division of shares"]),
]


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return f"{sql_literal(json.dumps(value or {}, sort_keys=True, default=str))}::jsonb"


def psql_command_candidates() -> list[list[str]]:
    configured = os.environ.get("AI_OS_PSQL_BIN", "").strip()
    local_psql = configured if configured and Path(configured).is_file() else shutil.which("psql")
    candidates: list[list[str]] = []
    if local_psql:
        candidates.append([
            local_psql,
            "-h",
            "127.0.0.1",
            "-p",
            POSTGRES_PORT,
            "-q",
            "-t",
            "-A",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "ai_os",
            "-d",
            "ai_os",
        ])
    candidates.append([
            "docker",
            "exec",
            "-i",
            "ai_os_postgres",
            "psql",
            "-q",
            "-t",
            "-A",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "ai_os",
            "-d",
            "ai_os",
        ])
    return candidates


def run_psql_text(sql: str) -> str:
    env = os.environ.copy()
    env.setdefault("PGPASSWORD", POSTGRES_PASSWORD)
    errors: list[str] = []
    for command in psql_command_candidates():
        try:
            completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False, env=env)
        except OSError as exc:
            errors.append(f"{command[0]}: {type(exc).__name__}: {exc}")
            continue
        if completed.returncode == 0:
            return completed.stdout.strip()
        errors.append(f"{command[0]}: {(completed.stderr or completed.stdout).strip()}")
    raise RuntimeError(" | ".join(errors))


def run_psql_json(sql: str) -> list[dict[str, Any]]:
    output = run_psql_text(sql)
    return json.loads(output or "[]")


def parse_iso_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def nse_date(value: dt.date) -> str:
    return value.strftime("%d-%m-%Y")


def bse_date(value: dt.date) -> str:
    return value.strftime("%Y%m%d")


def parse_datetime(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=INDIA_TZ)
        return parsed.astimezone(dt.timezone.utc).isoformat()
    except ValueError:
        pass
    formats = [
        "%d-%b-%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%d %b %Y %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ]
    for fmt in formats:
        try:
            return dt.datetime.strptime(text, fmt).replace(tzinfo=INDIA_TZ).astimezone(dt.timezone.utc).isoformat()
        except ValueError:
            continue
    return None


def content_hash(*values: object) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(str(value or "").encode("utf-8", errors="ignore"))
        digest.update(b"\x1f")
    return digest.hexdigest()


def classify_event(title: str, filing_type: str, body: str) -> dict[str, Any]:
    document_kind = f"{title} {filing_type}".lower()
    if "annual report" in document_kind or "annual_report" in document_kind:
        return {
            "event_type": "routine_filing",
            "urgency": "normal",
            "opportunity_score": 20,
            "risk_score": 25,
            "assigned_agent": "Filings Analyst",
        }
    text = f"{title} {filing_type} {body}".lower()
    if any(phrase in text for phrase in ["employee stock option", "stock option scheme", "esop", "exercise of stock options"]):
        return {
            "event_type": "routine_filing",
            "urgency": "normal",
            "opportunity_score": 20,
            "risk_score": 25,
            "assigned_agent": "Filings Analyst",
        }
    for event_type, keywords in SPECIAL_EVENT_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return {
                "event_type": event_type,
                "urgency": "high" if event_type not in {"board_action"} else "normal",
                "opportunity_score": 72 if event_type not in {"board_action", "pledge_change"} else 55,
                "risk_score": 68 if event_type in {"open_offer", "delisting", "insolvency", "scheme_arrangement"} else 48,
                "assigned_agent": "Special Situations Agent" if event_type not in {"board_action"} else "Filings Analyst",
            }
    return {
        "event_type": "routine_filing",
        "urgency": "normal",
        "opportunity_score": 20,
        "risk_score": 25,
        "assigned_agent": "Filings Analyst",
    }


def verified_https_context() -> ssl.SSLContext:
    ca_bundle = os.environ.get("AI_OS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
    if not ca_bundle:
        try:
            import certifi

            ca_bundle = certifi.where()
        except ImportError:
            ca_bundle = None
    return ssl.create_default_context(cafile=ca_bundle)


def curl_get(url: str, headers: dict[str, str], timeout: int = 30) -> tuple[int, bytes]:
    command = [
        os.environ.get("AI_OS_CURL_BIN", "curl"),
        "--fail-with-body",
        "--silent",
        "--show-error",
        "--location",
        "--max-time",
        str(timeout),
        "--retry",
        "2",
        "--retry-delay",
        "1",
        "--retry-all-errors",
    ]
    for name, value in headers.items():
        command.extend(["--header", f"{name}: {value}"])
    command.extend(["--write-out", "\n%{http_code}", url])
    completed = subprocess.run(
        command,
        capture_output=True,
        check=False,
        timeout=(timeout * 3) + 5,
    )
    if completed.returncode != 0:
        error = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"curl failed with exit {completed.returncode}: {error}")
    body, separator, status_text = completed.stdout.rpartition(b"\n")
    if not separator or not status_text.isdigit():
        raise RuntimeError("curl response did not include a valid HTTP status")
    return int(status_text), body


def fetch_nse(date_from: dt.date, date_to: dt.date, limit: int) -> tuple[int, str, list[dict[str, Any]]]:
    cookie_jar = CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=verified_https_context()),
        urllib.request.HTTPCookieProcessor(cookie_jar),
    )
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json,text/plain,*/*",
        "Referer": NSE_PAGE_URL,
    }
    opener.open(urllib.request.Request(NSE_PAGE_URL, headers=headers), timeout=20).read(2000)
    query = urllib.parse.urlencode(
        {
            "index": "equities",
            "from_date": nse_date(date_from),
            "to_date": nse_date(date_to),
        }
    )
    target_url = f"https://www.nseindia.com/api/corporate-announcements?{query}"
    with opener.open(urllib.request.Request(target_url, headers=headers), timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8", errors="ignore"))
        rows = payload if isinstance(payload, list) else []
        return response.status, target_url, rows[:limit]


def fetch_bse(date_from: dt.date, date_to: dt.date, limit: int) -> tuple[int, str, list[dict[str, Any]]]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json,text/plain,*/*",
        "Referer": BSE_PAGE_URL,
        "Origin": "https://www.bseindia.com",
    }
    rows: list[dict[str, Any]] = []
    http_status = 200
    target_url = BSE_API_URL
    current_date = date_to
    first_request = True
    while current_date >= date_from and len(rows) < limit:
        page = 1
        while len(rows) < limit:
            query = urllib.parse.urlencode(
                {
                    "pageno": page,
                    "strCat": "-1",
                    "strPrevDate": bse_date(current_date),
                    "strScrip": "",
                    "strSearch": "P",
                    "strToDate": bse_date(current_date),
                    "strType": "C",
                    "subcategory": "",
                }
            )
            page_url = f"{BSE_API_URL}?{query}"
            if first_request:
                target_url = page_url
                first_request = False
            http_status, raw = curl_get(page_url, headers)
            payload = json.loads(raw.decode("utf-8", errors="ignore"))
            if not isinstance(payload, dict):
                raise RuntimeError("BSE API returned a non-object payload")
            if payload.get("Status") is False:
                message = str(payload.get("Message") or "unspecified exchange error")
                raise RuntimeError(f"BSE API error: {message}")
            page_rows = payload.get("Table")
            if not isinstance(page_rows, list) or not page_rows:
                break
            normalized_page = [row for row in page_rows if isinstance(row, dict)]
            rows.extend(normalized_page)
            total_pages = int(normalized_page[0].get("TotalPageCnt") or 0) if normalized_page else 0
            if not normalized_page or (total_pages and page >= total_pages):
                break
            page += 1
            time.sleep(0.15)
        current_date -= dt.timedelta(days=1)
    return http_status, target_url, rows[:limit]


def normalize_nse(row: dict[str, Any]) -> dict[str, Any]:
    title = str(row.get("attchmntText") or row.get("desc") or "NSE corporate announcement").strip()
    return {
        "source_name": "NSE",
        "exchange": "NSE",
        "symbol": row.get("symbol"),
        "company_name": row.get("sm_name"),
        "filing_type": row.get("desc"),
        "title": title[:900],
        "filed_at": parse_datetime(row.get("an_dt") or row.get("sort_date") or row.get("exchdisstime")),
        "source_url": row.get("attchmntFile") or NSE_PAGE_URL,
        "attachment_url": row.get("attchmntFile"),
        "text": title,
        "payload": row,
    }


def normalize_bse(row: dict[str, Any]) -> dict[str, Any]:
    attachment = row.get("ATTACHMENTNAME") or row.get("Attachment") or row.get("attachment")
    attachment_url = None
    if attachment:
        attachment_text = str(attachment)
        attachment_url = attachment_text if attachment_text.startswith("http") else f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{attachment_text}"
    title = str(row.get("NEWSSUB") or row.get("NewsSub") or row.get("HEADLINE") or row.get("SUBCATNAME") or "BSE corporate announcement").strip()
    body = " ".join(
        str(value).strip()
        for value in [row.get("HEADLINE"), row.get("MORE")]
        if value not in (None, "")
    )
    return {
        "source_name": "BSE",
        "exchange": "BSE",
        "symbol": row.get("SCRIP_CD") or row.get("SCRIPCODE") or row.get("SecurityCode"),
        "company_name": row.get("SLONGNAME") or row.get("Company") or row.get("scripname"),
        "filing_type": row.get("SUBCATNAME") or row.get("CATEGORYNAME"),
        "title": title[:900],
        "filed_at": parse_datetime(row.get("NEWS_DT") or row.get("DissemDT") or row.get("DT_TM")),
        "source_url": attachment_url or BSE_PAGE_URL,
        "attachment_url": attachment_url,
        "text": f"{title} {body}".strip(),
        "payload": row,
    }


def start_run(source_key: str, connector_key: str, exchange: str, date_from: dt.date, date_to: dt.date, actor: str, target_url: str | None = None) -> dict[str, Any]:
    run_key = f"{source_key}-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    rows = run_psql_json(
        f"""
        WITH inserted AS (
            INSERT INTO research.filing_collector_runs (
                run_key, source_key, connector_key, exchange, status,
                date_from, date_to, target_url, created_by
            )
            VALUES (
                {sql_literal(run_key)}, {sql_literal(source_key)}, {sql_literal(connector_key)},
                {sql_literal(exchange)}, 'started', {sql_literal(date_from.isoformat())}::date,
                {sql_literal(date_to.isoformat())}::date, {sql_literal(target_url)}, {sql_literal(actor)}
            )
            RETURNING *
        )
        SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text FROM inserted
        """
    )
    return rows[0]


def finish_run(run_id: int, status: str, http_status: int | None, rows_seen: int, rows_upserted: int, events_upserted: int, inbox_items: int, target_url: str | None, sample: object, error: str | None) -> None:
    run_psql_text(
        f"""
        UPDATE research.filing_collector_runs
        SET status = {sql_literal(status)},
            http_status = {http_status if http_status is not None else 'NULL'},
            rows_seen = {rows_seen},
            rows_upserted = {rows_upserted},
            events_upserted = {events_upserted},
            inbox_items_created = {inbox_items},
            target_url = coalesce({sql_literal(target_url)}, target_url),
            finished_at = now(),
            error_message = {sql_literal(error)},
            sample_payload = {sql_jsonb(sample)}
        WHERE id = {run_id}
        """
    )


def mark_connector_after_run(connector_key: str, status: str, http_status: int | None, rows_seen: int, target_url: str | None, sample: object, error: str | None, actor: str) -> None:
    health_status = "configured" if status == "completed" else "failed"
    health_error = None if status == "completed" else error
    check_payload = {
        "collector_status": status,
        "http_status": http_status,
        "target_url": target_url,
        "source": connector_key,
        "sample": sample,
    }
    run_psql_text(
        f"""
        INSERT INTO core.connector_health_checks (
            target_kind, target_key, check_name, check_type, status,
            rows_seen, error_message, sample_payload, checked_by
        )
        VALUES (
            'data_source_connector', {sql_literal(connector_key)},
            'filing collector run check', 'collector_run',
            {sql_literal(health_status)}, {rows_seen},
            {sql_literal(health_error)}, {sql_jsonb(check_payload)}, {sql_literal(actor)}
        );

        UPDATE core.source_connector_profiles
        SET status = CASE
                WHEN {sql_literal(status)} = 'completed'
                THEN 'configured'
                ELSE status
            END,
            health_status = {sql_literal(health_status)},
            last_checked_at = now(),
            last_rows_seen = {rows_seen},
            last_error = {sql_literal(health_error)},
            updated_at = now()
        WHERE connector_key = {sql_literal(connector_key)};
        """
    )


def source_system_id(source_name: str) -> str:
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(result_rows)), '[]'::json)::text
        FROM (
            SELECT id
            FROM core.source_systems
            WHERE lower(name) LIKE {sql_literal('%' + source_name.lower() + '%')}
            ORDER BY id
            LIMIT 1
        ) result_rows
        """
    )
    return str(rows[0]["id"]) if rows else "NULL"


def upsert_artifact(item: dict[str, Any], source_system_sql: str, hash_value: str) -> int | None:
    rows = run_psql_json(
        f"""
        WITH inserted AS (
            INSERT INTO core.raw_artifacts (
                source_system_id, artifact_type, title, source_url,
                content_hash, mime_type, sensitivity, metadata
            )
            VALUES (
                {source_system_sql}, 'exchange_filing_announcement',
                {sql_literal(item["title"])}, {sql_literal(item["source_url"])},
                {sql_literal(hash_value)}, 'application/json', 'public',
                {sql_jsonb({"exchange": item["exchange"], "symbol": item.get("symbol"), "attachment_url": item.get("attachment_url")})}
            )
            ON CONFLICT (source_system_id, source_url, local_path, content_hash) DO UPDATE SET
                title = EXCLUDED.title,
                metadata = EXCLUDED.metadata,
                captured_at = now()
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text FROM inserted
        """
    )
    return int(rows[0]["id"]) if rows else None


def upsert_filing(run_id: int, item: dict[str, Any], source_system_sql: str, raw_artifact_id: int | None, event: dict[str, Any], hash_value: str) -> int:
    rows = run_psql_json(
        f"""
        WITH upserted AS (
            INSERT INTO research.corporate_filings (
                source_system_id, source_name, exchange, symbol, company_name,
                filing_type, event_type, title, filed_at, source_url,
                attachment_url, content_hash, extraction_status, extracted_text,
                payload, collector_run_id, raw_artifact_id
            )
            VALUES (
                {source_system_sql}, {sql_literal(item["source_name"])}, {sql_literal(item["exchange"])},
                {sql_literal(item.get("symbol"))}, {sql_literal(item.get("company_name"))},
                {sql_literal(item.get("filing_type"))}, {sql_literal(event["event_type"])},
                {sql_literal(item["title"])},
                {sql_literal(item.get("filed_at"))}::timestamptz,
                {sql_literal(item.get("source_url"))}, {sql_literal(item.get("attachment_url"))},
                {sql_literal(hash_value)}, 'captured', {sql_literal(item.get("text"))},
                {sql_jsonb(item.get("payload"))}, {run_id},
                {raw_artifact_id if raw_artifact_id is not None else 'NULL'}
            )
            ON CONFLICT (source_name, source_url, content_hash) DO UPDATE SET
                symbol = EXCLUDED.symbol,
                company_name = EXCLUDED.company_name,
                filing_type = EXCLUDED.filing_type,
                event_type = EXCLUDED.event_type,
                title = EXCLUDED.title,
                filed_at = EXCLUDED.filed_at,
                attachment_url = EXCLUDED.attachment_url,
                extraction_status = EXCLUDED.extraction_status,
                extracted_text = EXCLUDED.extracted_text,
                payload = EXCLUDED.payload,
                collector_run_id = coalesce(research.corporate_filings.collector_run_id, EXCLUDED.collector_run_id),
                raw_artifact_id = EXCLUDED.raw_artifact_id
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
        """
    )
    if not rows:
        raise RuntimeError("filing upsert returned no id")
    return int(rows[0]["id"])


def upsert_event_and_inbox(filing_id: int, item: dict[str, Any], event: dict[str, Any]) -> tuple[int, int]:
    title = item["title"]
    evidence = [
        {
            "table": "research.corporate_filings",
            "id": filing_id,
            "source_url": item.get("source_url"),
            "attachment_url": item.get("attachment_url"),
        }
    ]
    rows = run_psql_json(
        f"""
        WITH event_row AS (
            INSERT INTO research.filing_events (
                filing_id, event_type, symbol, company_name, thesis,
                opportunity_score, risk_score, urgency, status,
                evidence, assigned_agent
            )
            VALUES (
                {filing_id}, {sql_literal(event["event_type"])},
                {sql_literal(item.get("symbol"))}, {sql_literal(item.get("company_name"))},
                {sql_literal(title)}, {event["opportunity_score"]}, {event["risk_score"]},
                {sql_literal(event["urgency"])}, 'new', {sql_jsonb(evidence)},
                {sql_literal(event["assigned_agent"])}
            )
            ON CONFLICT (filing_id, event_type) DO UPDATE SET
                thesis = EXCLUDED.thesis,
                opportunity_score = EXCLUDED.opportunity_score,
                risk_score = EXCLUDED.risk_score,
                urgency = EXCLUDED.urgency,
                evidence = EXCLUDED.evidence,
                assigned_agent = EXCLUDED.assigned_agent
            RETURNING id, event_type, assigned_agent, urgency
        ), inbox_row AS (
            INSERT INTO agent.inbox_items (
                title, owner_agent, status, priority,
                recommended_action, evidence, target_workspace
            )
            SELECT
                {sql_literal("Filing event: " + title[:140])},
                assigned_agent,
                'queued',
                CASE WHEN urgency = 'high' THEN 'high' ELSE 'medium' END,
                CASE
                    WHEN event_type = 'routine_filing' THEN 'Review filing only if it affects a held or watched company.'
                    ELSE 'Analyze event terms, dates, downside, probability, and whether this is a special-situation opportunity.'
                END,
                {sql_jsonb(evidence)},
                'research'
            FROM event_row
            WHERE event_type <> 'routine_filing'
              AND NOT EXISTS (
                  SELECT 1 FROM agent.inbox_items
                  WHERE evidence::text LIKE {sql_literal('%"id": ' + str(filing_id) + '%')}
                    AND title LIKE 'Filing event:%'
              )
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(result_rows)), '[]'::json)::text
        FROM (
            SELECT
                (SELECT count(*) FROM event_row)::INT AS event_count,
                (SELECT count(*) FROM inbox_row)::INT AS inbox_count
        ) result_rows
        """
    )
    if not rows:
        return 0, 0
    return int(rows[0]["event_count"]), int(rows[0]["inbox_count"])


def collect_source(source: str, date_from: dt.date, date_to: dt.date, limit: int, actor: str, dry_run: bool) -> dict[str, Any]:
    source_key = "nse_filings" if source == "nse" else "bse_filings"
    connector_key = f"{source_key}_connector"
    exchange = source.upper()
    run = None if dry_run else start_run(source_key, connector_key, exchange, date_from, date_to, actor)
    run_id = 0 if dry_run else int(run["id"])
    target_url = None
    http_status = None
    normalized: list[dict[str, Any]] = []
    error = None
    started = time.monotonic()

    try:
        if source == "nse":
            http_status, target_url, rows = fetch_nse(date_from, date_to, limit)
            normalized = [normalize_nse(row) for row in rows]
        else:
            http_status, target_url, rows = fetch_bse(date_from, date_to, limit)
            normalized = [normalize_bse(row) for row in rows]
        status = "completed"
    except Exception as exc:  # keep all source runs auditable
        rows = []
        status = "failed"
        error = f"{type(exc).__name__}: {exc}"

    rows_upserted = 0
    events_upserted = 0
    inbox_items = 0
    event_counts: dict[str, int] = {}
    unique_filing_ids: set[int] = set()
    unique_event_keys: set[tuple[int, str]] = set()
    if not dry_run and status == "completed":
        source_system_sql = source_system_id(source)
        for item in normalized:
            event = classify_event(item["title"], str(item.get("filing_type") or ""), str(item.get("text") or ""))
            event_counts[event["event_type"]] = event_counts.get(event["event_type"], 0) + 1
            hash_value = content_hash(item["source_name"], item.get("source_url"), item["title"], item.get("filed_at"))
            raw_artifact_id = upsert_artifact(item, source_system_sql, hash_value)
            filing_id = upsert_filing(run_id, item, source_system_sql, raw_artifact_id, event, hash_value)
            event_count, inbox_count = upsert_event_and_inbox(filing_id, item, event)
            event_key = (filing_id, event["event_type"])
            if filing_id not in unique_filing_ids:
                unique_filing_ids.add(filing_id)
                rows_upserted += 1
            if event_count and event_key not in unique_event_keys:
                unique_event_keys.add(event_key)
                events_upserted += 1
            inbox_items += inbox_count

    sample = {
        "duration_ms": int((time.monotonic() - started) * 1000),
        "event_counts": event_counts,
        "sample_titles": [item["title"] for item in normalized[:5]],
    }
    if not dry_run and run_id:
        finish_run(
            run_id,
            status,
            http_status,
            len(normalized),
            rows_upserted,
            events_upserted,
            inbox_items,
            target_url,
            sample,
            error,
        )
        mark_connector_after_run(connector_key, status, http_status, len(normalized), target_url, sample, error, actor)

    return {
        "source": source,
        "run_id": run_id or None,
        "run_key": None if dry_run else run["run_key"],
        "status": status,
        "http_status": http_status,
        "target_url": target_url,
        "rows_seen": len(normalized),
        "rows_upserted": rows_upserted,
        "events_upserted": events_upserted,
        "inbox_items_created": inbox_items,
        "error_message": error,
        "sample": sample,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect NSE/BSE corporate filing announcements into AI OS.")
    parser.add_argument("--source", choices=["nse", "bse", "all"], default="all")
    parser.add_argument("--from-date", default=(dt.date.today() - dt.timedelta(days=1)).isoformat())
    parser.add_argument("--to-date", default=dt.date.today().isoformat())
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--actor", default="News Analyst")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    date_from = parse_iso_date(args.from_date)
    date_to = parse_iso_date(args.to_date)
    if date_to < date_from:
        raise SystemExit("--to-date must be >= --from-date")

    sources = ["nse", "bse"] if args.source == "all" else [args.source]
    results = [collect_source(source, date_from, date_to, max(1, args.limit), args.actor, args.dry_run) for source in sources]
    summary = {
        "ok": all(row["status"] == "completed" for row in results),
        "dry_run": args.dry_run,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "results": results,
        "totals": {
            "rows_seen": sum(int(row["rows_seen"]) for row in results),
            "rows_upserted": sum(int(row["rows_upserted"]) for row in results),
            "events_upserted": sum(int(row["events_upserted"]) for row in results),
            "inbox_items_created": sum(int(row["inbox_items_created"]) for row in results),
        },
    }
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
