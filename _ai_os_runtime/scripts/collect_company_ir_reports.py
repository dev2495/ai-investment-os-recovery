#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from collect_nse_bse_filings import curl_get, run_psql_json, run_psql_text, sql_jsonb, sql_literal
from runtime_storage import artifact_root


USER_AGENT = os.environ.get(
    "AI_OS_PUBLIC_CHECK_USER_AGENT",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 AI-OS-Research/0.1",
)
ARTIFACT_ROOT = artifact_root("company_ir")
INDIA_TZ = dt.timezone(dt.timedelta(hours=5, minutes=30))


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._text).strip()))
            self._href = None
            self._text = []


def fetch_bytes(url: str, accept: str, timeout: int = 60) -> bytes:
    status, body = curl_get(url, {"User-Agent": USER_AGENT, "Accept": accept}, timeout=timeout)
    if not 200 <= status < 300:
        raise RuntimeError(f"source returned HTTP {status}: {url}")
    return body


def fiscal_year(text: str) -> tuple[int, int] | None:
    normalized = re.sub(r"[_–—]", "-", urllib.parse.unquote(text))
    match = re.search(r"(?:20)?(\d{2})\s*-\s*(?:20)?(\d{2})", normalized)
    if not match:
        return None
    start = int(match.group(1))
    end = int(match.group(2))
    start += 2000 if start < 80 else 1900
    end += 2000 if end < 80 else 1900
    if end != start + 1 or not 2000 <= start <= 2100:
        return None
    return start, end


def discover_reports(page_url: str, include_subsidiaries: bool, limit: int) -> list[dict[str, Any]]:
    page = fetch_bytes(page_url, "text/html,application/xhtml+xml").decode("utf-8", errors="ignore")
    parser = LinkParser()
    parser.feed(page)
    page_host = urllib.parse.urlsplit(page_url).hostname or ""
    seen: set[str] = set()
    reports: list[dict[str, Any]] = []
    for href, label in parser.links:
        url = urllib.parse.urljoin(page_url, href)
        parsed = urllib.parse.urlsplit(url)
        haystack = f"{label} {parsed.path}".lower()
        if parsed.scheme != "https" or not parsed.path.lower().endswith(".pdf"):
            continue
        if not include_subsidiaries and any(word in haystack for word in ("subsidiary", "subsidiaries", "subsidairy", "subsidiairies")):
            continue
        if "annual" not in haystack or "report" not in haystack:
            continue
        if parsed.hostname not in {page_host, f"www.{page_host}", page_host.removeprefix("www.")}:
            continue
        canonical = urllib.parse.urlunsplit(parsed._replace(fragment=""))
        if canonical in seen:
            continue
        year = fiscal_year(haystack)
        if year is None:
            continue
        seen.add(canonical)
        reports.append({"url": canonical, "label": label or f"Annual Report FY {year[0]}-{year[1]}", "fiscal_year_start": year[0], "fiscal_year_end": year[1]})
    reports.sort(key=lambda row: (row["fiscal_year_end"], row["url"]), reverse=True)
    return reports[:limit]


def download_report(report: dict[str, Any], symbol: str) -> dict[str, Any]:
    target_dir = ARTIFACT_ROOT / symbol.lower() / f"fy-{report['fiscal_year_start']}-{report['fiscal_year_end']}"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "annual-report.pdf"
    data = fetch_bytes(report["url"], "application/pdf,*/*", timeout=120)
    if not data.startswith(b"%PDF"):
        raise ValueError(f"source did not return a PDF: {report['url']}")
    target.write_bytes(data)
    return {
        **report,
        "local_path": str(target),
        "content_hash": hashlib.sha256(data).hexdigest(),
        "bytes_downloaded": len(data),
        "published_at": None,
    }


def upsert_report(run_id: int, report: dict[str, Any], symbol: str, exchange: str, company_name: str, page_url: str) -> int:
    fiscal_label = f"FY {report['fiscal_year_start']}-{str(report['fiscal_year_end'])[-2:]}"
    title = f"{company_name} Annual Report {fiscal_label}"
    payload = {
        "source_type": "official_company_ir",
        "investor_relations_page": page_url,
        "fiscal_year_start": report["fiscal_year_start"],
        "fiscal_year_end": report["fiscal_year_end"],
        "document_sha256": report["content_hash"],
        "collector_run_id": run_id,
        "financial_facts_extracted": False,
    }
    rows = run_psql_json(
        f"""
        WITH artifact AS (
            INSERT INTO core.raw_artifacts (
                artifact_type, title, source_url, local_path, content_hash,
                mime_type, sensitivity, metadata
            ) VALUES (
                'company_annual_report', {sql_literal(title)}, {sql_literal(report['url'])},
                {sql_literal(report['local_path'])}, {sql_literal(report['content_hash'])},
                'application/pdf', 'public', {sql_jsonb(payload)}
            )
            ON CONFLICT (source_system_id, source_url, local_path, content_hash) DO UPDATE SET
                title=EXCLUDED.title, metadata=EXCLUDED.metadata, captured_at=now()
            RETURNING id
        ), filing AS (
            INSERT INTO research.corporate_filings (
                source_name, exchange, symbol, company_name, filing_type, event_type,
                title, filed_at, source_url, attachment_url, local_path, content_hash,
                extraction_status, payload, raw_artifact_id
            ) VALUES (
                'Company IR', {sql_literal(exchange)}, {sql_literal(symbol)}, {sql_literal(company_name)},
                'annual_report', 'routine_filing', {sql_literal(title)},
                {sql_literal(report.get('published_at'))}::timestamptz,
                {sql_literal(report['url'])}, {sql_literal(report['url'])},
                {sql_literal(report['local_path'])}, {sql_literal(report['content_hash'])},
                'captured', {sql_jsonb(payload)}, (SELECT id FROM artifact)
            )
            ON CONFLICT (source_name, source_url, content_hash) DO UPDATE SET
                exchange=EXCLUDED.exchange, symbol=EXCLUDED.symbol, company_name=EXCLUDED.company_name,
                title=EXCLUDED.title, filed_at=EXCLUDED.filed_at, attachment_url=EXCLUDED.attachment_url,
                local_path=EXCLUDED.local_path, payload=EXCLUDED.payload,
                raw_artifact_id=EXCLUDED.raw_artifact_id
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(filing)), '[]'::json)::text FROM filing
        """
    )
    return int(rows[0]["id"])


def collect(args: argparse.Namespace) -> dict[str, Any]:
    symbol = args.symbol.strip().upper()
    exchange = args.exchange.strip().upper()
    company_name = args.company_name.strip()
    page_url = args.url.strip()
    if not re.fullmatch(r"[A-Z0-9._&-]{1,40}", symbol):
        raise ValueError("unsupported symbol format")
    if exchange not in {"NSE", "BSE"}:
        raise ValueError("exchange must be NSE or BSE")
    if urllib.parse.urlsplit(page_url).scheme != "https":
        raise ValueError("investor-relations URL must use HTTPS")
    run_key = f"company-ir-{exchange.lower()}-{symbol.lower()}-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"
    rows = run_psql_json(
        f"""
        WITH inserted AS (
          INSERT INTO research.company_ir_collection_runs (
            run_key,symbol,exchange,company_name,investor_relations_url,status,started_by
          ) VALUES (
            {sql_literal(run_key)},{sql_literal(symbol)},{sql_literal(exchange)},
            {sql_literal(company_name)},{sql_literal(page_url)},'started',{sql_literal(args.actor)}
          ) RETURNING id
        ) SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text FROM inserted
        """
    )
    run_id = int(rows[0]["id"])
    try:
        discovered = discover_reports(page_url, args.include_subsidiaries, max(1, args.limit))
        downloaded: list[dict[str, Any]] = []
        filing_ids: list[int] = []
        if not args.dry_run:
            for report in discovered:
                item = download_report(report, symbol)
                downloaded.append(item)
                filing_ids.append(upsert_report(run_id, item, symbol, exchange, company_name, page_url))
        total_bytes = sum(int(row["bytes_downloaded"]) for row in downloaded)
        summary = {
            "ok": True,
            "run_id": run_id,
            "run_key": run_key,
            "status": "dry_run" if args.dry_run else "completed",
            "symbol": symbol,
            "exchange": exchange,
            "investor_relations_url": page_url,
            "reports_discovered": len(discovered),
            "reports_upserted": len(filing_ids),
            "bytes_downloaded": total_bytes,
            "filing_ids": filing_ids,
            "fiscal_years": [row["fiscal_year_end"] for row in discovered],
            "financial_facts_extracted": False,
            "broker_write_allowed": False,
        }
        run_psql_text(
            f"UPDATE research.company_ir_collection_runs SET status={sql_literal(summary['status'])}, "
            f"rows_seen={len(discovered)}, reports_upserted={len(filing_ids)}, bytes_downloaded={total_bytes}, "
            f"finished_at=now(), summary={sql_jsonb(summary)} WHERE id={run_id}"
        )
        return summary
    except Exception as exc:
        run_psql_text(
            f"UPDATE research.company_ir_collection_runs SET status='failed',finished_at=now(),"
            f"error_message={sql_literal(type(exc).__name__ + ': ' + str(exc))} WHERE id={run_id}"
        )
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect official company investor-relations annual reports as evidence.")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--exchange", required=True, choices=["NSE", "BSE"])
    parser.add_argument("--company-name", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument("--actor", default="Fundamental Data Steward")
    parser.add_argument("--include-subsidiaries", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(collect(args), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
