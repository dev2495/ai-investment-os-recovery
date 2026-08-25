#!/usr/bin/env python3
"""Promote source-linked legacy annual facts through deterministic validation guardrails."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from decimal import Decimal
from itertools import combinations
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
RUNTIME_ROOT = SCRIPT_DIR.parent
for candidate in (RUNTIME_ROOT, RUNTIME_ROOT / "api"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from run_agent_worker_once import psql_json, psql_text, sql_jsonb, sql_literal

SSD_ROOT = Path("/Volumes/Devarsh SSD")
DATA_ROOT = SSD_ROOT / "AI OS Data"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def numeric_tokens(text: str) -> list[Decimal]:
    values: list[Decimal] = []
    for token in re.findall(r"\(?-?\d[\d,]*(?:\.\d+)?\)?", text or ""):
        negative = token.startswith("(") and token.endswith(")")
        cleaned = token.strip("()").replace(",", "")
        try:
            value = Decimal(cleaned)
        except Exception:
            continue
        values.append(-value if negative else value)
    return values


def line_matches(value: Decimal, line: str) -> bool:
    tokens = numeric_tokens(line)
    if any(abs(token - value) <= Decimal("0.005") for token in tokens):
        return True
    for width in (2, 3):
        if any(abs(sum(group, Decimal(0)) - value) <= Decimal("0.005") for group in combinations(tokens, width)):
            return True
    return False


def statement_unit(unit: str, value: Decimal) -> tuple[str, Decimal]:
    if unit == "INR million":
        # INR 1 million equals INR 10 lakh. Keep this as one audited boundary.
        return "lakh", value * Decimal(10)
    if unit == "INR/share":
        return "INR/share", value
    raise ValueError(f"unsupported legacy unit: {unit}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--actor", default="Financial Validation Bridge")
    args = parser.parse_args()
    ticker = args.ticker.strip().upper()
    if not SSD_ROOT.is_mount() or not DATA_ROOT.is_dir() or not os.access(DATA_ROOT, os.W_OK):
        raise RuntimeError("Devarsh SSD is not mounted and writable; no internal-disk fallback")
    rows = psql_json(f"""
      SELECT fact.id legacy_fact_id,fact.company_id,fact.fiscal_year,fact.period_end,
        fact.statement_scope,fact.value_numeric,fact.unit,fact.source_locator,
        definition.fact_key,definition.statement_type,evidence.id evidence_id,
        evidence.corporate_filing_id,filing.source_url,filing.local_path,
        filing.content_hash,filing.filed_at
      FROM research.company_statement_facts fact
      JOIN research.statement_fact_definitions definition ON definition.id=fact.fact_definition_id
      JOIN research.fundamental_evidence evidence ON evidence.id=fact.evidence_id
      JOIN research.corporate_filings filing ON filing.id=evidence.corporate_filing_id
      JOIN research.companies company ON company.id=fact.company_id
      WHERE upper(company.primary_symbol)={sql_literal(ticker)} AND fact.is_current
        AND fact.fiscal_period='FY' AND fact.statement_scope='consolidated'
        AND fact.value_numeric IS NOT NULL
      ORDER BY fact.fiscal_year,definition.fact_key
    """)
    if not rows:
        raise RuntimeError(f"no source-linked legacy annual facts found for {ticker}")
    grouped: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(int(row["corporate_filing_id"]), int(row["fiscal_year"]))].append(row)
    summary = {"ticker": ticker, "groups": 0, "facts": 0, "validated": 0, "blocked": 0, "checks_passed": 0, "checks_failed": 0}
    for (filing_id, fiscal_year), facts in grouped.items():
        first = facts[0]
        source_path = Path(str(first["local_path"]))
        if not source_path.is_absolute():
            source_path = DATA_ROOT / source_path
        if not str(source_path).startswith(str(DATA_ROOT) + os.sep) or not source_path.is_file():
            raise RuntimeError(f"source is not an SSD file: {source_path}")
        actual_sha = sha256_file(source_path)
        expected_sha = str(first.get("content_hash") or "")
        if expected_sha and actual_sha != expected_sha:
            psql_text(f"""
              INSERT INTO research.financial_history_gaps
                (company_id,section_key,metric_key,period_start,period_end,gap_status,reason,next_source)
              VALUES ({int(first['company_id'])},'financial_history',{sql_literal('source_hash_fy'+str(fiscal_year))},
                {sql_literal(str(fiscal_year-1)+'-04-01')},{sql_literal(first['period_end'])},'blocked',
                {sql_literal('Stored filing hash does not match the SSD file; facts were not promoted until lineage is repaired.')},
                {sql_literal(first['source_url'])})
              ON CONFLICT (company_id,section_key,metric_key,period_start,period_end) DO UPDATE SET
                gap_status=EXCLUDED.gap_status,reason=EXCLUDED.reason,next_source=EXCLUDED.next_source
            """)
            summary["groups"] += 1
            summary["blocked"] += len(facts)
            continue
        run_key = f"legacy-validation-{ticker.lower()}-{fiscal_year}-filing-{filing_id}-v1"
        psql_text(f"""
          INSERT INTO research.financial_production_runs
            (run_key,company_id,filing_id,parser_name,parser_version,statement_scope,currency,unit,
             source_sha256,source_url,source_path,status,completed_at,created_by,summary)
          VALUES ({sql_literal(run_key)},{int(first['company_id'])},{filing_id},'legacy_source_line_validation',1,
            'consolidated','INR','lakh',{sql_literal(actual_sha)},{sql_literal(first['source_url'])},
            {sql_literal(str(source_path))},'running',NULL,{sql_literal(args.actor)},'{{}}'::jsonb)
          ON CONFLICT (run_key) DO UPDATE SET source_sha256=EXCLUDED.source_sha256,
            source_path=EXCLUDED.source_path,status='running',completed_at=NULL,created_by=EXCLUDED.created_by
        """)
        run_id = int(psql_json(f"SELECT id FROM research.financial_production_runs WHERE run_key={sql_literal(run_key)}")[0]["id"])
        passed = 0
        values: dict[str, Decimal] = {}
        pages: dict[str, int] = {}
        for fact in facts:
            raw_value = Decimal(str(fact["value_numeric"]))
            locator = fact.get("source_locator") or {}
            line = str(locator.get("reported_line") or "")
            page = int(locator.get("page_number") or 0)
            matched = page > 0 and bool(line) and line_matches(raw_value, line)
            target_unit, normalized = statement_unit(str(fact["unit"]), raw_value)
            status = "validated" if matched else "rejected"
            if matched:
                passed += 1
                values[str(fact["fact_key"])] = normalized
                pages[str(fact["fact_key"])] = page
            psql_text(f"""
              INSERT INTO research.financial_source_facts
                (production_run_id,company_id,fact_key,fiscal_year,period_end,statement_type,
                 statement_scope,value,currency,unit,source_page,reported_line,extraction_status)
              VALUES ({run_id},{int(fact['company_id'])},{sql_literal(fact['fact_key'])},{fiscal_year},
                {sql_literal(fact['period_end'])},{sql_literal(fact['statement_type'])},'consolidated',
                {sql_literal(str(normalized))},'INR',{sql_literal(target_unit)},{max(1,page)},
                {sql_literal(line)},{sql_literal(status)})
              ON CONFLICT (production_run_id,fact_key,fiscal_year,statement_scope) DO UPDATE SET
                value=EXCLUDED.value,source_page=EXCLUDED.source_page,reported_line=EXCLUDED.reported_line,
                extraction_status=EXCLUDED.extraction_status
            """)
            psql_text(f"""
              INSERT INTO research.financial_validation_checks
                (production_run_id,check_key,period_end,check_type,status,left_value,right_value,tolerance,explanation,source_pages)
              VALUES ({run_id},{sql_literal('source_line:'+str(fact['fact_key']))},{sql_literal(fact['period_end'])},
                'source_line_match',{sql_literal('pass' if matched else 'fail')},{sql_literal(str(raw_value))},
                {sql_literal(str(raw_value)) if matched else 'NULL'},0,
                {sql_literal('Value matched the cited reported line in the official filing.' if matched else 'Value did not match the cited reported line; fact rejected.')},
                ARRAY[{max(1,page)}]::integer[])
              ON CONFLICT (production_run_id,check_key,period_end) DO UPDATE SET status=EXCLUDED.status,
                left_value=EXCLUDED.left_value,right_value=EXCLUDED.right_value,explanation=EXCLUDED.explanation,
                source_pages=EXCLUDED.source_pages
            """)
        if all(key in values for key in ("total_assets", "total_equity", "total_liabilities")):
            left = values["total_assets"]
            right = values["total_equity"] + values["total_liabilities"]
            tie = abs(left - right) <= Decimal("1")
            psql_text(f"""
              INSERT INTO research.financial_validation_checks
                (production_run_id,check_key,period_end,check_type,status,left_value,right_value,tolerance,explanation,source_pages)
              VALUES ({run_id},'balance_sheet_tie',{sql_literal(first['period_end'])},'balance_sheet_tie',
                {sql_literal('pass' if tie else 'fail')},{sql_literal(str(left))},{sql_literal(str(right))},1,
                {sql_literal('Total assets reconcile to total equity plus total liabilities.' if tie else 'Balance sheet totals do not reconcile; run blocked.')},
                ARRAY[{','.join(str(pages[key]) for key in ('total_assets','total_equity','total_liabilities'))}]::integer[])
              ON CONFLICT (production_run_id,check_key,period_end) DO UPDATE SET status=EXCLUDED.status,
                left_value=EXCLUDED.left_value,right_value=EXCLUDED.right_value,explanation=EXCLUDED.explanation,
                source_pages=EXCLUDED.source_pages
            """)
            summary["checks_passed" if tie else "checks_failed"] += 1
        all_lines = passed == len(facts)
        check_failures = int(psql_json(f"SELECT count(*) failures FROM research.financial_validation_checks WHERE production_run_id={run_id} AND status='fail'")[0]["failures"])
        run_status = "validated" if all_lines and check_failures == 0 else "blocked"
        psql_text(f"""
          UPDATE research.financial_production_runs SET status={sql_literal(run_status)},completed_at=now(),
            summary={sql_jsonb({'legacy_fact_count': len(facts), 'source_line_checks_passed': passed, 'source_line_checks_failed': len(facts)-passed, 'validation_scope': 'source transcription plus available statement tie-outs', 'human_reviewed': False})}
          WHERE id={run_id}
        """)
        summary["groups"] += 1
        summary["facts"] += len(facts)
        summary["validated"] += passed
        summary["blocked"] += len(facts) - passed
    available_years = {int(row["fiscal_year"]) for row in rows}
    for missing_year in sorted(set(range(min(available_years), max(available_years) + 1)) - available_years):
        company_id = int(rows[0]["company_id"])
        period_end = f"{missing_year}-03-31"
        psql_text(f"""
          INSERT INTO research.financial_history_gaps
            (company_id,section_key,metric_key,period_start,period_end,gap_status,reason,next_source)
          VALUES ({company_id},'financial_history',{sql_literal('missing_fy'+str(missing_year))},
            {sql_literal(str(missing_year-1)+'-04-01')},{sql_literal(period_end)},'missing',
            'No source-linked annual statement facts are present for this fiscal year.',
            'Acquire and parse the official annual report comparative statements.')
          ON CONFLICT (company_id,section_key,metric_key,period_start,period_end) DO UPDATE SET
            gap_status=EXCLUDED.gap_status,reason=EXCLUDED.reason,next_source=EXCLUDED.next_source
        """)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["blocked"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
