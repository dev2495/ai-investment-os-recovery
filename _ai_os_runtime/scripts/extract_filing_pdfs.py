#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any


RUNTIME_ROOT = Path(os.environ.get("AI_OS_RUNTIME_ROOT") or Path(__file__).absolute().parents[1])
POSTGRES_PASSWORD = os.environ.get("AI_OS_POSTGRES_PASSWORD", "ai_os_local_dev_change_me")
POSTGRES_PORT = os.environ.get("AI_OS_POSTGRES_PORT", "54329")
USER_AGENT = os.environ.get(
    "AI_OS_PUBLIC_CHECK_USER_AGENT",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 AI-OS-Research/0.1",
)
ARTIFACT_ROOT = Path(os.environ.get("AI_OS_ARTIFACT_ROOT") or RUNTIME_ROOT / "artifacts") / "filings"

SPECIAL_EVENT_KEYWORDS = [
    ("reverse_merger", ["reverse merger"]),
    ("demerger", ["demerger", "de-merger", "resulting company"]),
    ("merger", ["merger", "amalgamation", "merged with"]),
    ("scheme_arrangement", ["scheme of arrangement", "arrangement with creditors", "share exchange ratio"]),
    ("buyback", ["buyback", "buy-back", "tender offer"]),
    ("open_offer", ["open offer", "public announcement", "letter of offer"]),
    ("delisting", ["delisting", "de-listing", "exit offer"]),
    ("rights_issue", ["rights issue", "rights entitlement", "rights equity shares"]),
    ("preferential_allotment", ["preferential", "warrant", "allotment", "qualified institutions placement", "qip"]),
    ("asset_sale", ["slump sale", "asset sale", "sale of undertaking", "business transfer agreement"]),
    ("pledge_change", ["pledge", "encumbrance", "release of pledge"]),
    ("insolvency", ["insolvency", "ibc", "nclt", "resolution plan", "corporate insolvency"]),
    ("arbitrage_watch", ["record date", "swap ratio", "cash consideration", "court convened meeting"]),
    ("board_action", ["board meeting", "dividend", "bonus", "split", "sub-division"]),
]


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return f"{sql_literal(json.dumps(value or {}, sort_keys=True, default=str))}::jsonb"


def psql_command_candidates() -> list[list[str]]:
    return [
        [
            "/opt/homebrew/opt/postgresql@15/bin/psql",
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
        ],
        [
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
        ],
    ]


def run_psql_text(sql: str) -> str:
    env = os.environ.copy()
    env.setdefault("PGPASSWORD", POSTGRES_PASSWORD)
    errors: list[str] = []
    for command in psql_command_candidates():
        completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False, env=env)
        if completed.returncode == 0:
            return completed.stdout.strip()
        errors.append((completed.stderr or completed.stdout).strip())
    raise RuntimeError(" | ".join(errors))


def run_psql_json(sql: str) -> list[dict[str, Any]]:
    output = run_psql_text(sql)
    return json.loads(output or "[]")


def content_hash(*values: object) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(str(value or "").encode("utf-8", errors="ignore"))
        digest.update(b"\x1f")
    return digest.hexdigest()


def clean_text(value: str) -> str:
    text = value.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def storage_path(path: Path) -> str:
    try:
        return str(path.relative_to(RUNTIME_ROOT.parent))
    except ValueError:
        return str(path)


def classify_event(title: str, filing_type: str, text: str) -> dict[str, Any]:
    haystack = f"{title} {filing_type} {text[:20000]}".lower()
    if any(phrase in haystack for phrase in ["employee stock option", "stock option scheme", "esop", "exercise of stock options"]):
        return {
            "event_type": "routine_filing",
            "urgency": "normal",
            "opportunity_score": 20,
            "risk_score": 25,
            "assigned_agent": "Filings Analyst",
            "matched_keywords": [],
            "classifier": "keyword_pdf_text_v1",
        }
    matched_keywords: list[str] = []
    for event_type, keywords in SPECIAL_EVENT_KEYWORDS:
        matched_keywords = [keyword for keyword in keywords if keyword in haystack]
        if matched_keywords:
            return {
                "event_type": event_type,
                "urgency": "high" if event_type not in {"board_action"} else "normal",
                "opportunity_score": 78 if event_type not in {"board_action", "pledge_change"} else 55,
                "risk_score": 70 if event_type in {"open_offer", "delisting", "insolvency", "scheme_arrangement"} else 48,
                "assigned_agent": "Special Situations Agent" if event_type not in {"board_action"} else "Filings Analyst",
                "matched_keywords": matched_keywords,
                "classifier": "keyword_pdf_text_v1",
            }
    return {
        "event_type": "routine_filing",
        "urgency": "normal",
        "opportunity_score": 20,
        "risk_score": 25,
        "assigned_agent": "Filings Analyst",
        "matched_keywords": [],
        "classifier": "keyword_pdf_text_v1",
    }


def first_match(text: str, patterns: list[str], flags: int = re.IGNORECASE | re.DOTALL) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return clean_text(match.group(1) if match.groups() else match.group(0))[:500]
    return None


def all_matches(text: str, pattern: str, flags: int = re.IGNORECASE | re.DOTALL, limit: int = 10) -> list[str]:
    values: list[str] = []
    for match in re.finditer(pattern, text, flags):
        value = clean_text(match.group(1) if match.groups() else match.group(0))
        if value and value not in values:
            values.append(value[:500])
        if len(values) >= limit:
            break
    return values


def extract_special_terms(event: dict[str, Any], text: str) -> dict[str, Any]:
    event_type = str(event.get("event_type") or "routine_filing")
    date_pattern = r"([0-9]{1,2}[-/ ][A-Za-z]{3,9}[-/ ,]+[0-9]{4}|[A-Za-z]{3,9}\s+[0-9]{1,2},\s+[0-9]{4}|[0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{4})"
    money_pattern = r"((?:Rs\.?|INR|₹)\s*[0-9][0-9,]*(?:\.\d+)?(?:\s*(?:crore|crores|lakh|lakhs|million|billion))?)"
    compact_text = clean_text(text)
    terms = {
        "record_date": first_match(compact_text, [rf"record date(?:[^\n.]{{0,140}}?){date_pattern}", rf"record date[^\n.]*?is\s+{date_pattern}"]),
        "ex_date": first_match(compact_text, [rf"ex[-\s]?date(?:[^\n.]{{0,140}}?){date_pattern}"]),
        "meeting_date": first_match(compact_text, [rf"(?:meeting|board meeting|court convened meeting)(?:[^\n.]{{0,140}}?){date_pattern}"]),
        "opening_date": first_match(compact_text, [rf"(?:opening date|offer opens|issue opens)(?:[^\n.]{{0,140}}?){date_pattern}"]),
        "closing_date": first_match(compact_text, [rf"(?:closing date|offer closes|issue closes)(?:[^\n.]{{0,140}}?){date_pattern}"]),
        "offer_price": first_match(compact_text, [rf"(?:offer price|buyback price|exit price|price of|at a price of)(?:[^\n.]{{0,180}}?){money_pattern}"]),
        "issue_price": first_match(compact_text, [rf"(?:issue price|subscription price|exercise price|warrant price)(?:[^\n.]{{0,180}}?){money_pattern}"]),
        "cash_consideration": first_match(compact_text, [rf"(?:cash consideration|consideration payable|cash payment)(?:[^\n.]{{0,180}}?){money_pattern}"]),
        "swap_ratio": first_match(compact_text, [
            r"([0-9]+(?:\.[0-9]+)?\s*(?:equity\s+)?shares?[^\n.]{0,80}?for\s+every\s+[0-9]+(?:\.[0-9]+)?[^\n.]{0,80}?shares?)",
            r"((?:swap ratio|share exchange ratio|in the ratio of)[^\n.]{0,120}?[0-9]+(?:\.[0-9]+)?\s*:\s*[0-9]+(?:\.[0-9]+)?)",
        ]),
        "entitlement_ratio": first_match(compact_text, [
            r"([0-9]+\s*(?:rights|right|bonus)?\s*(?:equity\s+)?shares?[^\n.]{0,80}?for\s+every\s+[0-9]+[^\n.]{0,80}?shares?)",
            r"((?:entitlement ratio|rights ratio|bonus ratio|in the ratio of)[^\n.]{0,120}?[0-9]+\s*:\s*[0-9]+)",
        ]),
        "buyback_size": first_match(compact_text, [rf"(?:buyback size|maximum buyback size|aggregate amount of the buyback|buyback offer size)(?:[^\n.]{{0,200}}?){money_pattern}"]),
        "aggregate_amount": first_match(compact_text, [rf"(?:aggregate amount|maximum amount|issue size|offer size)(?:[^\n.]{{0,200}}?){money_pattern}"]),
        "dates_found": all_matches(compact_text, date_pattern, limit=12),
        "money_values_found": all_matches(compact_text, money_pattern, limit=12),
        "matched_keywords": event.get("matched_keywords", []),
        "classifier": event.get("classifier", "keyword_pdf_text_v1"),
    }
    if event_type not in {"merger", "demerger", "scheme_arrangement", "reverse_merger"}:
        terms["swap_ratio"] = None
    timeline_snippets = all_matches(
        compact_text,
        r"((?:record date|opening date|closing date|board meeting|shareholder meeting|court convened meeting|nclt|effective date|last date)[^\n]{0,220})",
        limit=8,
    )
    condition_snippets = all_matches(
        compact_text,
        r"((?:subject to|conditional upon|approval of|sanction of|no adverse observation|nclt|sebi|stock exchange)[^\n]{0,240})",
        limit=8,
    )
    terms["timeline_text"] = " | ".join(timeline_snippets)[:1500] if timeline_snippets else None
    terms["conditions_text"] = " | ".join(condition_snippets)[:1500] if condition_snippets else None
    useful_keys = [
        "record_date",
        "ex_date",
        "meeting_date",
        "opening_date",
        "closing_date",
        "offer_price",
        "issue_price",
        "cash_consideration",
        "swap_ratio",
        "entitlement_ratio",
        "buyback_size",
        "aggregate_amount",
        "timeline_text",
        "conditions_text",
    ]
    hit_count = sum(1 for key in useful_keys if terms.get(key))
    base = 0.2 if event_type == "routine_filing" else 0.45
    terms["confidence"] = min(0.95, base + hit_count * 0.08)
    terms["status"] = "needs_review" if event_type != "routine_filing" else "reference_only"
    return terms


def select_filings(limit: int, filing_id: int | None, force: bool) -> list[dict[str, Any]]:
    where = [
        "coalesce(cf.attachment_url, cf.source_url) IS NOT NULL",
        "lower(coalesce(cf.attachment_url, cf.source_url)) LIKE '%.pdf%'",
    ]
    if filing_id is not None:
        where.append(f"cf.id = {filing_id}")
    elif not force:
        where.append(
            """(
                cf.extraction_status = 'captured'
                OR (
                    cf.extraction_status = 'extraction_failed'
                    AND (
                        SELECT count(*)
                        FROM research.filing_pdf_extraction_runs attempts
                        WHERE attempts.filing_id = cf.id
                    ) < 3
                    AND coalesce((
                        SELECT max(attempts.started_at)
                        FROM research.filing_pdf_extraction_runs attempts
                        WHERE attempts.filing_id = cf.id
                    ), '-infinity'::timestamptz) < now() - interval '6 hours'
                )
            )"""
        )
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(result_rows)), '[]'::json)::text
        FROM (
            SELECT cf.id, cf.source_system_id, cf.source_name, cf.exchange, cf.symbol, cf.company_name,
                   cf.filing_type, cf.event_type, cf.title, cf.source_url, cf.attachment_url,
                   cf.local_path, cf.extraction_status,
                   EXISTS (
                       SELECT 1
                       FROM portfolio.positions p
                       WHERE upper(p.symbol) = upper(cf.symbol)
                         AND coalesce(p.quantity, 0) <> 0
                   ) AS is_held,
                   EXISTS (
                       SELECT 1
                       FROM trading.instrument_watchlist w
                       WHERE upper(coalesce(w.normalized_symbol, w.base_asset, '')) = upper(cf.symbol)
                   ) AS is_watched,
                   (
                       SELECT count(*)
                       FROM research.filing_pdf_extraction_runs attempts
                       WHERE attempts.filing_id = cf.id
                   ) AS extraction_attempt_count
            FROM research.corporate_filings cf
            WHERE {' AND '.join(where)}
            ORDER BY
                CASE
                    WHEN coalesce(cf.event_type, 'routine_filing') <> 'routine_filing' THEN 0
                    WHEN EXISTS (
                        SELECT 1 FROM portfolio.positions p
                        WHERE upper(p.symbol) = upper(cf.symbol)
                          AND coalesce(p.quantity, 0) <> 0
                    ) THEN 1
                    WHEN EXISTS (
                        SELECT 1 FROM trading.instrument_watchlist w
                        WHERE upper(coalesce(w.normalized_symbol, w.base_asset, '')) = upper(cf.symbol)
                    ) THEN 2
                    ELSE 3
                END,
                coalesce(cf.filed_at, cf.created_at) DESC,
                cf.id DESC
            LIMIT {max(1, limit)}
        ) result_rows
        """
    )
    return rows


def start_run(filing: dict[str, Any], actor: str) -> dict[str, Any]:
    source_url = filing.get("attachment_url") or filing.get("source_url")
    rows = run_psql_json(
        f"""
        WITH inserted AS (
            INSERT INTO research.filing_pdf_extraction_runs (
                filing_id, status, source_url, event_type_before, created_by
            )
            VALUES (
                {int(filing["id"])}, 'started', {sql_literal(source_url)},
                {sql_literal(filing.get("event_type"))}, {sql_literal(actor)}
            )
            RETURNING *
        )
        SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text FROM inserted
        """
    )
    return rows[0]


def finish_run(run_id: int, status: str, local_pdf_path: str | None, parser_name: str | None, bytes_downloaded: int, page_count: int | None, extracted_chars: int, event_type_after: str | None, classifier_payload: object, error: str | None) -> None:
    run_psql_text(
        f"""
        UPDATE research.filing_pdf_extraction_runs
        SET status = {sql_literal(status)},
            local_pdf_path = {sql_literal(local_pdf_path)},
            parser_name = {sql_literal(parser_name)},
            bytes_downloaded = {bytes_downloaded},
            page_count = {page_count if page_count is not None else 'NULL'},
            extracted_chars = {extracted_chars},
            event_type_after = {sql_literal(event_type_after)},
            classifier_payload = {sql_jsonb(classifier_payload)},
            finished_at = now(),
            error_message = {sql_literal(error)}
        WHERE id = {run_id}
        """
    )


def download_pdf(filing: dict[str, Any]) -> Path:
    source_url = str(filing.get("attachment_url") or filing.get("source_url") or "")
    if not source_url:
        raise ValueError("filing has no PDF URL")
    source_name = re.sub(r"[^A-Za-z0-9]+", "_", str(filing.get("source_name") or "source")).strip("_").lower() or "source"
    target_dir = ARTIFACT_ROOT / source_name / dt.date.today().isoformat()
    target_dir.mkdir(parents=True, exist_ok=True)
    hash_part = content_hash(filing.get("id"), source_url)[:12]
    target = target_dir / f"filing-{filing['id']}-{hash_part}.pdf"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/pdf,*/*",
        "Referer": "https://www.nseindia.com/",
    }
    request = urllib.request.Request(source_url, headers=headers)
    with urllib.request.urlopen(request, timeout=45) as response:
        data = response.read()
    if not data.startswith(b"%PDF"):
        raise ValueError(f"downloaded content is not a PDF: {source_url}")
    target.write_bytes(data)
    return target


def extract_pdf_text(path: Path) -> tuple[str, int, str]:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("pypdf is required; run with the bundled Codex Python runtime") from exc

    reader = PdfReader(str(path))
    chunks: list[str] = []
    for index, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001
            page_text = f"\n[page {index + 1} extraction error: {type(exc).__name__}: {exc}]\n"
        if page_text.strip():
            chunks.append(f"\n--- page {index + 1} ---\n{page_text}")
    return clean_text("\n".join(chunks)), len(reader.pages), "pypdf"


def upsert_text_artifact(filing: dict[str, Any], local_pdf_path: Path, extracted_text: str, event: dict[str, Any]) -> int | None:
    hash_value = content_hash(local_pdf_path, extracted_text[:200000])
    rows = run_psql_json(
        f"""
        WITH inserted AS (
            INSERT INTO core.raw_artifacts (
                source_system_id, artifact_type, title, source_url, local_path,
                content_hash, mime_type, sensitivity, metadata
            )
            VALUES (
                {int(filing["source_system_id"]) if filing.get("source_system_id") is not None else 'NULL'},
                'filing_pdf_text', {sql_literal(filing.get("title"))},
                {sql_literal(filing.get("attachment_url") or filing.get("source_url"))},
                {sql_literal(storage_path(local_pdf_path))},
                {sql_literal(hash_value)}, 'text/plain', 'public',
                {sql_jsonb({"filing_id": filing.get("id"), "event_type": event.get("event_type"), "parser": "pypdf"})}
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


def upsert_event_and_inbox(filing: dict[str, Any], event: dict[str, Any]) -> tuple[int, int]:
    filing_id = int(filing["id"])
    evidence = [
        {
            "table": "research.corporate_filings",
            "id": filing_id,
            "source_url": filing.get("source_url"),
            "attachment_url": filing.get("attachment_url"),
            "extraction": "pdf_text",
            "matched_keywords": event.get("matched_keywords", []),
        }
    ]
    rows = run_psql_json(
        f"""
        WITH demote_routine AS (
            UPDATE research.filing_events
            SET status = 'superseded'
            WHERE filing_id = {filing_id}
              AND event_type = 'routine_filing'
              AND {sql_literal(event["event_type"])} <> 'routine_filing'
        ), event_row AS (
            INSERT INTO research.filing_events (
                filing_id, event_type, symbol, company_name, thesis,
                opportunity_score, risk_score, urgency, status,
                evidence, assigned_agent
            )
            VALUES (
                {filing_id}, {sql_literal(event["event_type"])},
                {sql_literal(filing.get("symbol"))}, {sql_literal(filing.get("company_name"))},
                {sql_literal(filing.get("title"))}, {event["opportunity_score"]}, {event["risk_score"]},
                {sql_literal(event["urgency"])}, 'new', {sql_jsonb(evidence)},
                {sql_literal(event["assigned_agent"])}
            )
            ON CONFLICT (filing_id, event_type) DO UPDATE SET
                thesis = EXCLUDED.thesis,
                opportunity_score = EXCLUDED.opportunity_score,
                risk_score = EXCLUDED.risk_score,
                urgency = EXCLUDED.urgency,
                evidence = EXCLUDED.evidence,
                assigned_agent = EXCLUDED.assigned_agent,
                status = CASE WHEN research.filing_events.status = 'superseded' THEN 'new' ELSE research.filing_events.status END
            RETURNING id, event_type, assigned_agent, urgency
        ), inbox_row AS (
            INSERT INTO agent.inbox_items (
                title, owner_agent, status, priority,
                recommended_action, evidence, target_workspace
            )
            SELECT
                {sql_literal("PDF filing event: " + str(filing.get("title") or "Filing")[:140])},
                assigned_agent,
                'queued',
                CASE WHEN urgency = 'high' THEN 'high' ELSE 'medium' END,
                'Analyze parsed filing text, event terms, timeline, downside, probability, and whether this is actionable.',
                {sql_jsonb(evidence)},
                'research'
            FROM event_row
            WHERE event_type <> 'routine_filing'
              AND NOT EXISTS (
                  SELECT 1 FROM agent.inbox_items
                  WHERE evidence::text LIKE {sql_literal('%"id": ' + str(filing_id) + '%')}
                    AND title LIKE 'PDF filing event:%'
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


def upsert_special_terms(filing: dict[str, Any], run_id: int, event: dict[str, Any], terms: dict[str, Any]) -> int | None:
    event_type = str(event.get("event_type") or "routine_filing")
    has_terms = any(
        terms.get(key)
        for key in [
            "record_date",
            "ex_date",
            "meeting_date",
            "opening_date",
            "closing_date",
            "offer_price",
            "issue_price",
            "cash_consideration",
            "swap_ratio",
            "entitlement_ratio",
            "buyback_size",
            "aggregate_amount",
            "timeline_text",
            "conditions_text",
        ]
    )
    if event_type == "routine_filing" and not has_terms:
        return None
    rows = run_psql_json(
        f"""
        WITH event_ref AS (
            SELECT id
            FROM research.filing_events
            WHERE filing_id = {int(filing["id"])}
              AND event_type = {sql_literal(event_type)}
            ORDER BY id DESC
            LIMIT 1
        ), upserted AS (
            INSERT INTO research.special_situation_terms (
                filing_id, filing_event_id, extraction_run_id, event_type,
                symbol, company_name, record_date, ex_date, meeting_date,
                opening_date, closing_date, offer_price, issue_price,
                cash_consideration, swap_ratio, entitlement_ratio, buyback_size,
                aggregate_amount, timeline_text, conditions_text, raw_terms,
                confidence, status, updated_at
            )
            VALUES (
                {int(filing["id"])}, (SELECT id FROM event_ref), {run_id}, {sql_literal(event_type)},
                {sql_literal(filing.get("symbol"))}, {sql_literal(filing.get("company_name"))},
                {sql_literal(terms.get("record_date"))}, {sql_literal(terms.get("ex_date"))},
                {sql_literal(terms.get("meeting_date"))}, {sql_literal(terms.get("opening_date"))},
                {sql_literal(terms.get("closing_date"))}, {sql_literal(terms.get("offer_price"))},
                {sql_literal(terms.get("issue_price"))}, {sql_literal(terms.get("cash_consideration"))},
                {sql_literal(terms.get("swap_ratio"))}, {sql_literal(terms.get("entitlement_ratio"))},
                {sql_literal(terms.get("buyback_size"))}, {sql_literal(terms.get("aggregate_amount"))},
                {sql_literal(terms.get("timeline_text"))}, {sql_literal(terms.get("conditions_text"))},
                {sql_jsonb(terms)}, {terms.get("confidence", 0)}, {sql_literal(terms.get("status", "needs_review"))}, now()
            )
            ON CONFLICT (filing_id, event_type) DO UPDATE SET
                filing_event_id = EXCLUDED.filing_event_id,
                extraction_run_id = EXCLUDED.extraction_run_id,
                symbol = EXCLUDED.symbol,
                company_name = EXCLUDED.company_name,
                record_date = EXCLUDED.record_date,
                ex_date = EXCLUDED.ex_date,
                meeting_date = EXCLUDED.meeting_date,
                opening_date = EXCLUDED.opening_date,
                closing_date = EXCLUDED.closing_date,
                offer_price = EXCLUDED.offer_price,
                issue_price = EXCLUDED.issue_price,
                cash_consideration = EXCLUDED.cash_consideration,
                swap_ratio = EXCLUDED.swap_ratio,
                entitlement_ratio = EXCLUDED.entitlement_ratio,
                buyback_size = EXCLUDED.buyback_size,
                aggregate_amount = EXCLUDED.aggregate_amount,
                timeline_text = EXCLUDED.timeline_text,
                conditions_text = EXCLUDED.conditions_text,
                raw_terms = EXCLUDED.raw_terms,
                confidence = EXCLUDED.confidence,
                status = EXCLUDED.status,
                updated_at = now()
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
        """
    )
    return int(rows[0]["id"]) if rows else None


def update_filing(filing: dict[str, Any], run_id: int, local_pdf_path: Path, extracted_text: str, page_count: int, text_artifact_id: int | None, event: dict[str, Any]) -> None:
    relative_path = storage_path(local_pdf_path)
    run_psql_text(
        f"""
        UPDATE research.corporate_filings
        SET extraction_status = 'extracted',
            extracted_text = {sql_literal(extracted_text[:500000])},
            local_path = {sql_literal(relative_path)},
            event_type = {sql_literal(event["event_type"])},
            raw_artifact_id = coalesce({text_artifact_id if text_artifact_id is not None else 'NULL'}, raw_artifact_id),
            pdf_page_count = {page_count},
            pdf_extracted_at = now(),
            pdf_extraction_run_id = {run_id},
            classification_payload = {sql_jsonb(event)}
        WHERE id = {int(filing["id"])}
        """
    )


def extract_one(filing: dict[str, Any], actor: str, dry_run: bool) -> dict[str, Any]:
    run = None if dry_run else start_run(filing, actor)
    run_id = 0 if dry_run else int(run["id"])
    started = time.monotonic()
    local_pdf_path: Path | None = None
    parser_name = None
    page_count = None
    extracted_text = ""
    error = None
    status = "completed"
    event = {"event_type": filing.get("event_type") or "unknown"}
    event_count = 0
    inbox_count = 0
    text_artifact_id = None
    terms: dict[str, Any] = {}
    special_terms_id = None

    try:
        local_pdf_path = download_pdf(filing)
        extracted_text, page_count, parser_name = extract_pdf_text(local_pdf_path)
        if len(extracted_text) < 50:
            raise ValueError("PDF text extraction returned less than 50 characters")
        event = classify_event(str(filing.get("title") or ""), str(filing.get("filing_type") or ""), extracted_text)
        terms = extract_special_terms(event, extracted_text)
        event["terms"] = terms
        if not dry_run:
            text_artifact_id = upsert_text_artifact(filing, local_pdf_path, extracted_text, event)
            update_filing(filing, run_id, local_pdf_path, extracted_text, page_count, text_artifact_id, event)
            event_count, inbox_count = upsert_event_and_inbox(filing, event)
            special_terms_id = upsert_special_terms(filing, run_id, event, terms)
    except Exception as exc:  # noqa: BLE001
        status = "failed"
        error = f"{type(exc).__name__}: {exc}"
        if not dry_run:
            run_psql_text(
                f"""
                UPDATE research.corporate_filings
                SET extraction_status = 'extraction_failed',
                    classification_payload = classification_payload || {sql_jsonb({"last_error": error})}
                WHERE id = {int(filing["id"])}
                """
            )

    classifier_payload = {
        "duration_ms": int((time.monotonic() - started) * 1000),
        "event": event,
        "text_preview": extracted_text[:700],
        "text_artifact_id": text_artifact_id,
        "special_terms_id": special_terms_id,
        "terms": terms,
    }
    if not dry_run and run_id:
        finish_run(
            run_id,
            status,
            storage_path(local_pdf_path) if local_pdf_path else None,
            parser_name,
            local_pdf_path.stat().st_size if local_pdf_path and local_pdf_path.exists() else 0,
            page_count,
            len(extracted_text),
            str(event.get("event_type")) if event else None,
            classifier_payload,
            error,
        )

    return {
        "filing_id": filing["id"],
        "run_id": run_id or None,
        "status": status,
        "source_url": filing.get("attachment_url") or filing.get("source_url"),
        "local_pdf_path": storage_path(local_pdf_path) if local_pdf_path else None,
        "parser_name": parser_name,
        "page_count": page_count,
        "extracted_chars": len(extracted_text),
        "event_type_before": filing.get("event_type"),
        "event_type_after": event.get("event_type") if event else None,
        "events_upserted": event_count,
        "inbox_items_created": inbox_count,
        "special_terms_id": special_terms_id,
        "terms": terms,
        "error_message": error,
        "sample": classifier_payload,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Download filing PDFs, extract text, and classify filing events.")
    parser.add_argument("--filing-id", type=int)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--actor", default="Filings Analyst")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    filings = select_filings(max(1, args.limit), args.filing_id, args.force)
    results = [extract_one(filing, args.actor, args.dry_run) for filing in filings]
    summary = {
        "ok": all(row["status"] == "completed" for row in results),
        "dry_run": args.dry_run,
        "selected": len(filings),
        "results": results,
        "totals": {
            "extracted_chars": sum(int(row["extracted_chars"]) for row in results),
            "events_upserted": sum(int(row["events_upserted"]) for row in results),
            "inbox_items_created": sum(int(row["inbox_items_created"]) for row in results),
            "special_terms_upserted": sum(1 for row in results if row.get("special_terms_id")),
        },
    }
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
