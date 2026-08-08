#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

from collect_nse_bse_filings import run_psql_json, run_psql_text, sql_jsonb, sql_literal


PARSER_VERSION = "annual_report_consolidated_rows_v2"
FACTS = {
    "revenue_from_operations": {
        "canonical_name": "Revenue from operations",
        "statement_type": "income_statement",
        "labels": (r"^revenue from operations\b", r"^total revenue from operations\b"),
    },
    "profit_after_tax": {
        "canonical_name": "Profit after tax",
        "statement_type": "income_statement",
        "labels": (
            r"^profit for the year after tax\b",
            r"^profit after tax for the year\b",
            r"^profit for the (?:year|period) \(from continuing and discontinued operations\)",
            r"^profit for the (?:year|period)\b",
        ),
    },
    "total_assets": {
        "canonical_name": "Total assets",
        "statement_type": "balance_sheet",
        "labels": (r"^total assets\b",),
    },
    "total_equity": {
        "canonical_name": "Total equity",
        "statement_type": "balance_sheet",
        "labels": (r"^total equity\b",),
    },
}
AMOUNT = re.compile(r"(?<![A-Za-z])\(?-?\d[\d,]*(?:\.\d+)?\)?")


def parse_amounts(line: str) -> list[float]:
    values: list[float] = []
    for token in AMOUNT.findall(line):
        negative = token.startswith("(") and token.endswith(")")
        normalized = token.strip("()").replace(",", "")
        try:
            value = float(normalized)
        except ValueError:
            continue
        values.append(-value if negative else value)
    return values


def reported_pair(line: str) -> tuple[float, float] | None:
    if len(re.findall(r"(?:^|\s)-(?:\s|$)", line)) >= 2:
        return None
    values = parse_amounts(line)
    if len(values) < 2:
        return None
    if len(values) >= 3 and 0 <= values[0] <= 200 and abs(values[1]) >= 500:
        values = values[1:]
    if len(values) != 2:
        return None
    return values[0], values[1]


def normalized_lines(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]


def page_kind(text: str) -> str | None:
    normalized = re.sub(r"\s+", " ", text).lower()
    if re.search(r"consolidated (?:statement of )?profit and loss", normalized):
        return "income_statement"
    if re.search(r"consolidated (?:balance sheet|statement of financial position)", normalized):
        return "balance_sheet"
    return None


def extract_annual_report(path: Path, fiscal_year: int) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    from pypdf import PdfReader  # type: ignore

    segment_pattern = re.compile(
        r"single\s+operating\s+segment\s*,?\s*i\.?e\.?\s*,?\s*[\"\u201c]?([^\"\u201d\n.]+)",
        re.IGNORECASE,
    )
    found: dict[str, dict[str, Any]] = {}
    segment: dict[str, Any] | None = None
    for page_number, page in enumerate(PdfReader(str(path)).pages, start=1):
        text = page.extract_text() or ""
        if segment is None:
            normalized_page = re.sub(r"\s+", " ", text)
            match = segment_pattern.search(normalized_page)
            if match:
                segment_name = re.sub(r"\s+", " ", match.group(1)).strip(" \"\u201c\u201d")
                if segment_name and len(segment_name) <= 120:
                    segment = {
                        "segment_key": re.sub(r"[^a-z0-9]+", "_", segment_name.lower()).strip("_"),
                        "segment_name": segment_name,
                        "reported_text": re.sub(r"\s+", " ", match.group(0)).strip(),
                        "page_number": page_number,
                    }
        kind = page_kind(text)
        if kind is None:
            continue
        for line in normalized_lines(text):
            lower = line.lower()
            for fact_key, definition in FACTS.items():
                if fact_key in found or definition["statement_type"] != kind:
                    continue
                if not any(re.search(pattern, lower) for pattern in definition["labels"]):
                    continue
                pair = reported_pair(line)
                if pair is None:
                    continue
                current, comparative = pair
                found[fact_key] = {
                    "fact_key": fact_key,
                    "fiscal_year": fiscal_year,
                    "current_value": current,
                    "comparative_value": comparative,
                    "reported_line": line,
                    "page_number": page_number,
                    "statement_type": kind,
                }
    return list(found.values()), segment


def extract_single_segment_declaration(path: Path) -> dict[str, Any] | None:
    return extract_annual_report(path, 0)[1]


def extract_pdf(path: Path, fiscal_year: int) -> list[dict[str, Any]]:
    return extract_annual_report(path, fiscal_year)[0]


def load_reports(symbol: str, exchange: str, limit: int) -> list[dict[str, Any]]:
    return run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(report_rows)), '[]'::json)::text
        FROM (
          SELECT filing.id AS filing_id, filing.local_path,
                 (filing.payload->>'fiscal_year_end')::int AS fiscal_year,
                 evidence.id AS evidence_id, evidence.retrieved_at,
                 filing.content_hash
          FROM research.corporate_filings filing
          JOIN research.fundamental_evidence evidence ON evidence.corporate_filing_id=filing.id
          WHERE filing.source_name='Company IR'
            AND upper(filing.symbol)={sql_literal(symbol)}
            AND upper(filing.exchange)={sql_literal(exchange)}
            AND filing.extraction_status='extracted'
            AND filing.local_path IS NOT NULL
            AND filing.payload->>'fiscal_year_end' IS NOT NULL
          ORDER BY (filing.payload->>'fiscal_year_end')::int DESC
          LIMIT {limit}
        ) report_rows
        """
    )


def persist(
    company_id: int,
    reports: list[dict[str, Any]],
    extracted: list[dict[str, Any]],
    segments: list[dict[str, Any]],
    actor: str,
) -> dict[str, int]:
    definitions = []
    for fact_key, definition in FACTS.items():
        definitions.append(
            "(" + ",".join((
                sql_literal(fact_key), sql_literal(definition["canonical_name"]),
                sql_literal(definition["statement_type"]), "'monetary'", "'INR lakh'", "'flow'" if definition["statement_type"] == "income_statement" else "'instant'",
                sql_literal(f"Machine-readable consolidated annual report row; review required before investment use."),
            )) + ")"
        )
    run_psql_text(
        "INSERT INTO research.statement_fact_definitions "
        "(fact_key,canonical_name,statement_type,value_type,default_unit,balance_type,description) VALUES "
        + ",".join(definitions)
        + " ON CONFLICT (fact_key) DO UPDATE SET canonical_name=EXCLUDED.canonical_name,description=EXCLUDED.description;"
    )
    report_by_id = {int(row["filing_id"]): row for row in reports}
    count = 0
    for row in extracted:
        report = report_by_id[int(row["filing_id"])]
        fy = int(row["fiscal_year"])
        period_end = dt.date(fy, 3, 31)
        period_start = dt.date(fy - 1, 4, 1)
        available_at = str(report["retrieved_at"])
        metadata = {
            "parser_version": PARSER_VERSION,
            "review_status": "machine_extracted_unreviewed",
            "source_document_sha256": report["content_hash"],
            "actor": actor,
            "broker_write_allowed": False,
        }
        run_psql_text(
            f"""
            INSERT INTO research.company_statement_facts (
              company_id,fact_definition_id,fiscal_year,fiscal_period,period_start,period_end,
              statement_scope,value_numeric,currency,unit,scale_power,reported_value_text,
              source_as_of_date,available_at,restatement_version,restatement_status,is_current,
              evidence_id,source_locator,metadata
            ) SELECT
              {company_id},definition.id,{fy},'FY',{sql_literal(period_start.isoformat())}::date,
              {sql_literal(period_end.isoformat())}::date,'consolidated',{row['current_value']},
              'INR','lakh',0,{sql_literal(row['reported_line'])},{sql_literal(period_end.isoformat())}::date,
              {sql_literal(available_at)}::timestamptz,1,'reported',true,{int(report['evidence_id'])},
              {sql_jsonb({'filing_id': row['filing_id'], 'page_number': row['page_number'], 'reported_line': row['reported_line']})},
              {sql_jsonb(metadata)}
            FROM research.statement_fact_definitions definition
            WHERE definition.fact_key={sql_literal(row['fact_key'])}
            ON CONFLICT (company_id,fact_definition_id,fiscal_year,fiscal_period,period_end,statement_scope,restatement_version)
            DO UPDATE SET value_numeric=EXCLUDED.value_numeric,reported_value_text=EXCLUDED.reported_value_text,
              available_at=EXCLUDED.available_at,evidence_id=EXCLUDED.evidence_id,
              source_locator=EXCLUDED.source_locator,metadata=EXCLUDED.metadata,recorded_at=now();
            """
        )
        count += 1
    segment_count = 0
    segment_fact_count = 0
    revenue_by_filing = {
        int(row["filing_id"]): row
        for row in extracted
        if row["fact_key"] == "revenue_from_operations"
    }
    for segment in segments:
        report = report_by_id[int(segment["filing_id"])]
        fy = int(segment["fiscal_year"])
        valid_from = dt.date(fy - 1, 4, 1)
        metadata = {
            "parser_version": PARSER_VERSION,
            "review_status": "machine_extracted_unreviewed",
            "single_operating_segment": True,
            "source_document_sha256": report["content_hash"],
            "reported_text": segment["reported_text"],
            "page_number": segment["page_number"],
            "actor": actor,
            "broker_write_allowed": False,
        }
        segment_rows = run_psql_json(
            f"""
            WITH existing AS (
              SELECT id FROM research.company_segments
              WHERE company_id={company_id} AND segment_key={sql_literal(segment['segment_key'])}
              ORDER BY valid_from LIMIT 1
            ), updated AS (
              UPDATE research.company_segments target
              SET valid_from=least(target.valid_from,{sql_literal(valid_from.isoformat())}::date),
                  segment_name={sql_literal(segment['segment_name'])},updated_at=now()
              FROM existing
              WHERE target.id=existing.id
              RETURNING target.id
            ), inserted AS (
              INSERT INTO research.company_segments (
                company_id,segment_key,segment_name,segment_type,valid_from,evidence_id,metadata
              )
              SELECT {company_id},{sql_literal(segment['segment_key'])},{sql_literal(segment['segment_name'])},
                     'operating',{sql_literal(valid_from.isoformat())}::date,{int(report['evidence_id'])},{sql_jsonb(metadata)}
              WHERE NOT EXISTS (SELECT 1 FROM updated)
              RETURNING id
            ), segment_row AS (
              SELECT coalesce((SELECT id FROM inserted),(SELECT id FROM updated)) AS id
            )
            SELECT coalesce(json_agg(row_to_json(segment_row)), '[]'::json)::text
            FROM segment_row
            """
        )
        if not segment_rows:
            continue
        segment_count += 1
        revenue = revenue_by_filing.get(int(segment["filing_id"]))
        if not revenue:
            continue
        period_end = dt.date(fy, 3, 31)
        period_start = dt.date(fy - 1, 4, 1)
        locator = {
            "derivation": "single_operating_segment_consolidated_revenue",
            "segment_declaration_page": segment["page_number"],
            "segment_declaration": segment["reported_text"],
            "financial_statement_page": revenue["page_number"],
            "reported_financial_line": revenue["reported_line"],
            "filing_id": segment["filing_id"],
        }
        run_psql_text(
            f"""
            INSERT INTO research.company_segment_facts (
              company_id,segment_id,fact_definition_id,fiscal_year,fiscal_period,
              period_start,period_end,value_numeric,currency,unit,scale_power,
              source_as_of_date,available_at,evidence_id,source_locator
            )
            SELECT {company_id},{int(segment_rows[0]['id'])},definition.id,{fy},'FY',
                   {sql_literal(period_start.isoformat())}::date,{sql_literal(period_end.isoformat())}::date,
                   {revenue['current_value']},'INR','lakh',0,{sql_literal(period_end.isoformat())}::date,
                   {sql_literal(str(report['retrieved_at']))}::timestamptz,{int(report['evidence_id'])},
                   {sql_jsonb(locator)}
            FROM research.statement_fact_definitions definition
            WHERE definition.fact_key='revenue_from_operations'
            ON CONFLICT (segment_id,fact_definition_id,fiscal_year,fiscal_period,period_end,evidence_id)
            DO UPDATE SET value_numeric=EXCLUDED.value_numeric,source_locator=EXCLUDED.source_locator;
            """
        )
        segment_fact_count += 1
    return {
        "statement_facts": count,
        "segment_declarations": segment_count,
        "segment_facts": segment_fact_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize audited consolidated annual-report rows without LLM inference.")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--exchange", required=True, choices=["NSE", "BSE"])
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument("--actor", default="Fundamental Data Steward")
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()
    symbol = args.symbol.strip().upper()
    exchange = args.exchange.strip().upper()
    reports = load_reports(symbol, exchange, max(1, min(args.limit, 25)))
    company_rows = run_psql_json(
        f"SELECT coalesce(json_agg(row_to_json(c)), '[]'::json)::text FROM (SELECT id FROM research.companies WHERE primary_symbol={sql_literal(symbol)} AND primary_exchange={sql_literal(exchange)} LIMIT 1) c"
    )
    if not company_rows:
        raise SystemExit("company is not registered")
    extracted: list[dict[str, Any]] = []
    segments: list[dict[str, Any]] = []
    for report in reports:
        path = Path(str(report["local_path"]))
        report_facts, segment = extract_annual_report(path, int(report["fiscal_year"]))
        for fact in report_facts:
            extracted.append({**fact, "filing_id": int(report["filing_id"]), "evidence_id": int(report["evidence_id"])})
        if segment:
            segments.append({
                **segment,
                "fiscal_year": int(report["fiscal_year"]),
                "filing_id": int(report["filing_id"]),
                "evidence_id": int(report["evidence_id"]),
            })
    rows_written = (
        persist(int(company_rows[0]["id"]), reports, extracted, segments, args.actor)
        if args.persist
        else {"statement_facts": 0, "segment_declarations": 0, "segment_facts": 0}
    )
    coverage = {key: sum(1 for row in extracted if row["fact_key"] == key) for key in FACTS}
    output = {
        "ok": True,
        "symbol": symbol,
        "exchange": exchange,
        "parser_version": PARSER_VERSION,
        "reports_seen": len(reports),
        "facts_extracted": len(extracted),
        "rows_written": rows_written,
        "single_segment_declarations": len(segments),
        "segments": segments,
        "coverage": coverage,
        "fiscal_years": sorted({int(row["fiscal_year"]) for row in extracted}),
        "review_status": "machine_extracted_unreviewed",
        "capital_action_allowed": False,
        "broker_write_allowed": False,
        "sample": extracted[:8],
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
