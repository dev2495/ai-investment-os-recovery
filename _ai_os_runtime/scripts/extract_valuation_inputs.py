#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from extract_governance_forensics import load_source, normalized_page
from extract_long_term_source_document import ensure_pdf_runtime, run_psql_json, sql_jsonb, sql_literal


def parse_indian_number(value: str) -> float:
    return float(value.replace(",", ""))


def extract_valuation_inputs_from_pages(pages: list[str], fiscal_year: int) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for page_number, raw in enumerate(pages, start=1):
        text = normalized_page(raw)
        if not re.search(r"diluted EPS", text, re.IGNORECASE) or not re.search(r"weighted average number of equity shares", text, re.IGNORECASE):
            continue
        eps_matches = re.findall(r"Diluted EPS\s*\(in Rs\.\).*?(-?[0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
        diluted_matches = re.findall(r"adjusted for the effect of dilution.*?([0-9]{1,2}(?:,[0-9]{2}){2},[0-9]{3}|[0-9]{8,10})", text, re.IGNORECASE)
        basic_matches = re.findall(r"purpose of basic EPS.*?([0-9]{1,2}(?:,[0-9]{2}){2},[0-9]{3}|[0-9]{8,10})", text, re.IGNORECASE)
        if not eps_matches or not diluted_matches:
            continue
        positive_eps = [parse_indian_number(value) for value in eps_matches if parse_indian_number(value) > 0]
        if not positive_eps:
            continue
        diluted = max(parse_indian_number(value) for value in diluted_matches)
        basic = max((parse_indian_number(value) for value in basic_matches), default=diluted)
        eps = max(positive_eps)
        excerpt_start = max(0, text.lower().find("the following reflects") - 80)
        excerpt = text[excerpt_start:excerpt_start + 1800]
        candidates.append({"page": page_number, "eps": eps, "diluted": diluted, "basic": basic, "excerpt": excerpt})
    if not candidates:
        return []
    selected = max(candidates, key=lambda row: (row["eps"], row["page"]))
    common = {
        "fiscal_year": fiscal_year,
        "statement_scope": "consolidated",
        "source_page": selected["page"],
        "source_excerpt": selected["excerpt"],
        "extraction_method": "deterministic_pattern",
        "verification_status": "machine_extracted",
    }
    return [
        {**common, "input_key": "diluted_weighted_average_shares", "value_numeric": selected["diluted"], "unit": "shares"},
        {**common, "input_key": "basic_weighted_average_shares", "value_numeric": selected["basic"], "unit": "shares"},
        {**common, "input_key": "diluted_eps_continuing", "value_numeric": selected["eps"], "unit": "INR/share"},
    ]


def persist(source: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("no consolidated valuation inputs matched")
    values = []
    for row in rows:
        values.append("(" + ",".join((
            str(int(source["company_id"])), str(int(source["evidence_id"])), str(row["fiscal_year"]),
            sql_literal(row["input_key"]), str(row["value_numeric"]), sql_literal(row["unit"]),
            sql_literal(row["statement_scope"]), str(row["source_page"]), sql_literal(row["source_excerpt"]),
            sql_literal(row["extraction_method"]), sql_literal(row["verification_status"]),
            sql_literal(source["available_at"]) + "::timestamptz", sql_jsonb({"source_document_id": source.get("source_document_id")}),
        )) + ")")
    result = run_psql_json(f"""
      WITH incoming(company_id,evidence_id,fiscal_year,input_key,value_numeric,unit,statement_scope,
        source_page,source_excerpt,extraction_method,verification_status,available_at,metadata) AS (VALUES {','.join(values)}),
      upserted AS (
        INSERT INTO research.company_valuation_inputs (company_id,evidence_id,fiscal_year,input_key,
          value_numeric,unit,statement_scope,source_page,source_excerpt,extraction_method,
          verification_status,available_at,metadata)
        SELECT * FROM incoming
        ON CONFLICT (company_id,evidence_id,fiscal_year,input_key,statement_scope) DO UPDATE SET
          value_numeric=EXCLUDED.value_numeric,unit=EXCLUDED.unit,source_page=EXCLUDED.source_page,
          source_excerpt=EXCLUDED.source_excerpt,extraction_method=EXCLUDED.extraction_method,
          verification_status=EXCLUDED.verification_status,available_at=EXCLUDED.available_at,
          metadata=EXCLUDED.metadata,updated_at=now()
        RETURNING input_key,value_numeric,unit,source_page,verification_status
      ) SELECT json_build_object('written',count(*),'inputs',json_agg(row_to_json(upserted) ORDER BY input_key))::text FROM upserted
    """)
    if not isinstance(result, dict):
        raise RuntimeError("valuation input persistence returned an invalid result")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract consolidated, page-cited valuation inputs from a retained annual report.")
    parser.add_argument("--source-document-id", type=int, required=True)
    parser.add_argument("--evidence-id", type=int, required=True)
    parser.add_argument("--fiscal-year", type=int, required=True)
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()
    ensure_pdf_runtime()
    from pypdf import PdfReader  # type: ignore

    source = load_source(args.source_document_id, args.evidence_id)
    source["source_document_id"] = args.source_document_id
    reader = PdfReader(str(Path(source["local_pdf_path"])))
    rows = extract_valuation_inputs_from_pages([page.extract_text() or "" for page in reader.pages], args.fiscal_year)
    database = persist(source, rows) if args.persist else {"written": 0}
    print(json.dumps({"ok": True, "symbol": source["symbol"], "inputs": rows, "database": database,
                      "capital_action_allowed": False, "broker_write_allowed": False}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
