#!/usr/bin/env python3
"""Parse and reconcile the issuer's FY21-FY26 historical-financials page."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

PARSER_VERSION = "ushamart-historical-financials-v1"
DOCKER = shutil.which("docker") or "/opt/homebrew/bin/docker"
YEARS = tuple(range(2021, 2027))

SECTIONS: dict[str, list[tuple[str, str, str, str, str]]] = {
    "profitability": [
        ("revenue", "Revenue", "INR crore", "INR", "as_reported"),
        ("oebitda", "oEBITDA", "INR crore", "INR", "as_reported"),
        ("oebitda_margin", "oEBITDA,%", "percent", "", "issuer_ratio"),
        ("pbt", "PBT", "INR crore", "INR", "as_reported"),
        ("pbt_margin", "PBT,%", "percent", "", "issuer_ratio"),
        ("pat_continuing", "PAT", "INR crore", "INR", "continuing_business"),
        ("pat_margin_continuing", "PAT,%", "percent", "", "continuing_business_issuer_ratio"),
        ("interest_coverage", "Interest Coverage (x)", "x", "", "issuer_ratio"),
        ("oebitda_per_mt", "oEBITDA/MT (Rs.)", "INR per MT", "INR", "excluding_other_income_and_um_cables"),
        ("steel_consumption_rate_per_mt", "Steel Rate - Consump./MT (Rs.)", "INR per MT", "INR", "group_average_consumption_rate"),
    ],
    "balance_sheet": [
        ("net_worth", "Net Worth", "INR crore", "INR", "as_reported"),
        ("gross_debt", "Gross Debt", "INR crore", "INR", "as_reported"),
        ("net_debt", "Net Debt", "INR crore", "INR", "as_reported"),
        ("net_working_capital", "Net Working Capital", "INR crore", "INR", "as_reported"),
        ("gross_debt_to_equity", "Gross Debt to Equity (x)", "x", "", "issuer_ratio"),
        ("net_debt_to_equity", "Net Debt to Equity (x)", "x", "", "issuer_ratio"),
        ("net_debt_to_ebitda", "Net Debt to EBITDA (x)", "x", "", "issuer_ratio"),
        ("current_ratio", "Current Ratio (x)", "x", "", "issuer_ratio"),
        ("operating_cash_flow_pre_tax", "Operating Cash Flow before Income Tax", "INR crore", "INR", "as_reported_pre_tax"),
        ("free_cash_flow", "Free Cash Flow", "INR crore", "INR", "issuer_defined"),
    ],
    "working_capital": [
        ("payable_days", "Payable", "days", "", "issuer_ratio"),
        ("receivable_days", "Receivable", "days", "", "issuer_ratio"),
        ("inventory_days", "Inventory", "days", "", "issuer_ratio"),
        ("net_working_capital_days", "Net Working Capital Days", "days", "", "issuer_ratio"),
        ("net_working_capital_to_turnover", "Net Working Capital to Turnover", "percent", "", "issuer_ratio"),
        ("fixed_asset_turnover", "Fixed Asset Turnover Ratio (x)", "x", "", "issuer_ratio"),
    ],
    "volume": [
        ("wire_rope_volume", "Wire Rope", "KMT", "", "as_reported"),
        ("wire_and_strand_volume", "Wire & Strand", "KMT", "", "as_reported"),
        ("lrpc_volume", "LRPC", "KMT", "", "as_reported"),
        ("total_volume", "Total", "KMT", "", "as_reported"),
    ],
}


def literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def jsonb(value: object) -> str:
    return literal(json.dumps(value, sort_keys=True, default=str)) + "::jsonb"


def run(sql: str) -> list[dict[str, Any]]:
    body = sql.rstrip().rstrip(";")
    statement = "SELECT coalesce(json_agg(row_to_json(q)), '[]'::json)::text FROM (" + body + ") q;"
    completed = subprocess.run(
        [DOCKER, "exec", "-i", "ai_os_postgres", "psql", "-q", "-t", "-A",
         "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os"],
        input=statement, text=True, capture_output=True, check=False,
    )
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return json.loads(completed.stdout.strip() or "[]")


def execute(sql: str) -> None:
    completed = subprocess.run(
        [DOCKER, "exec", "-i", "ai_os_postgres", "psql", "-q", "-v", "ON_ERROR_STOP=1",
         "-U", "ai_os", "-d", "ai_os"], input=sql, text=True, capture_output=True, check=False,
    )
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout).strip())


def normalized_number(raw: str) -> float:
    value = raw.strip().replace(",", "").replace("%", "")
    if value in {"-", "—", ""}:
        raise ValueError("missing numeric value")
    return float(value)


def parse_rows(text: str) -> dict[str, dict[int, float]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    result: dict[str, dict[int, float]] = {}
    cursor = 0
    ordered = [item for group in SECTIONS.values() for item in group]
    for metric_key, label, _unit, _currency, _basis in ordered:
        while cursor < len(lines) and lines[cursor] != label:
            cursor += 1
        if cursor >= len(lines):
            raise ValueError("Missing issuer row: " + label)
        raw_values = lines[cursor + 1:cursor + 7]
        if len(raw_values) != 6:
            raise ValueError("Incomplete issuer row: " + label)
        result[metric_key] = {year: normalized_number(value) for year, value in zip(YEARS, raw_values)}
        cursor += 7
    return result


def validation_checks(values: dict[str, dict[int, float]]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for year in YEARS:
        volume_sum = values["wire_rope_volume"][year] + values["wire_and_strand_volume"][year] + values["lrpc_volume"][year]
        checks.append({"year": year, "key": "volume_components_tie", "observed": volume_sum,
                       "expected": values["total_volume"][year], "tolerance": 1.0,
                       "status": "pass" if abs(volume_sum-values["total_volume"][year]) <= 1.0 else "fail"})
        for key, numerator in (("oebitda_margin_recalc", "oebitda"), ("pbt_margin_recalc", "pbt"),
                               ("pat_margin_recalc", "pat_continuing")):
            reported_key = {"oebitda_margin_recalc": "oebitda_margin", "pbt_margin_recalc": "pbt_margin",
                            "pat_margin_recalc": "pat_margin_continuing"}[key]
            calculated = values[numerator][year] / values["revenue"][year] * 100
            reported = values[reported_key][year]
            checks.append({"year": year, "key": key, "observed": calculated, "expected": reported,
                           "tolerance": 0.11, "status": "pass" if abs(calculated-reported) <= 0.11 else "fail"})
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-item-id", type=int, required=True)
    args = parser.parse_args()
    rows = run("SELECT i.id,i.company_id,i.source_url,i.content_hash,i.metadata,c.primary_symbol symbol "
               "FROM research.thesis_source_items i JOIN research.companies c ON c.id=i.company_id WHERE i.id=" + str(args.source_item_id))
    if not rows:
        raise ValueError("Source item not found")
    source = rows[0]
    if source["symbol"] != "USHAMART" or source["source_url"] != "https://ushamartin.com/public/investor-relations/financial-information/historical-financials":
        raise ValueError("Parser accepts only the governed Usha Martin historical-financials source")
    metadata = source.get("metadata") or {}
    receipt_path = Path(metadata.get("receipt_path") or "")
    text_path = receipt_path.with_name("source.txt")
    if not str(text_path).startswith("/Volumes/Devarsh SSD/") or not text_path.exists():
        raise RuntimeError("Governed external-SSD text artifact is missing")
    values = parse_rows(text_path.read_text(encoding="utf-8"))
    checks = validation_checks(values)
    failed = [check for check in checks if check["status"] == "fail"]
    statements = ["BEGIN;"]
    for group, metrics in SECTIONS.items():
        for metric_key, label, unit, currency, basis in metrics:
            for year in YEARS:
                statements.append(
                    "INSERT INTO research.official_operating_history_facts(company_id,source_item_id,metric_key,metric_label,"
                    "metric_group,fiscal_year,period_end,value_numeric,unit,currency,consolidation_scope,fact_basis,source_locator,"
                    "extraction_status,validation_status,validation_notes,parser_version,metadata) VALUES(" +
                    str(int(source["company_id"])) + "," + str(args.source_item_id) + "," + literal(metric_key) + "," + literal(label) +
                    "," + literal(group) + "," + str(year) + "," + literal(f"{year}-03-31") + "::date," +
                    str(values[metric_key][year]) + "," + literal(unit) + "," + literal(currency or None) + ","
                    "'consolidated'," + literal(basis) + "," + jsonb({"section": group, "row": label, "column": f"FY{str(year)[-2:]}",
                        "source_url": source["source_url"], "content_sha256": source["content_hash"]}) +
                    ",'validated','machine_validated','Issuer row extracted; four cross-row checks per year must pass.'," +
                    literal(PARSER_VERSION) + "," + jsonb({"source_scope": "public", "restatement_status": "issuer_current_page"}) +
                    ") ON CONFLICT(company_id,metric_key,fiscal_year,consolidation_scope,source_item_id) DO UPDATE SET "
                    "value_numeric=EXCLUDED.value_numeric,unit=EXCLUDED.unit,fact_basis=EXCLUDED.fact_basis,source_locator=EXCLUDED.source_locator,"
                    "extraction_status=EXCLUDED.extraction_status,validation_status=EXCLUDED.validation_status,"
                    "validation_notes=EXCLUDED.validation_notes,parser_version=EXCLUDED.parser_version,extracted_at=now(),metadata=EXCLUDED.metadata;"
                )
    for check in checks:
        statements.append(
            "INSERT INTO research.official_operating_history_checks(company_id,source_item_id,fiscal_year,check_key,check_status,"
            "observed_value,expected_value,tolerance,check_detail,parser_version) VALUES(" +
            str(int(source["company_id"])) + "," + str(args.source_item_id) + "," + str(check["year"]) + "," +
            literal(check["key"]) + "," + literal(check["status"]) + "," + str(check["observed"]) + "," +
            str(check["expected"]) + "," + str(check["tolerance"]) + "," +
            literal("Deterministic issuer table reconciliation; no estimate or inference.") + "," + literal(PARSER_VERSION) +
            ") ON CONFLICT(company_id,source_item_id,fiscal_year,check_key) DO UPDATE SET check_status=EXCLUDED.check_status,"
            "observed_value=EXCLUDED.observed_value,expected_value=EXCLUDED.expected_value,tolerance=EXCLUDED.tolerance,"
            "check_detail=EXCLUDED.check_detail,checked_at=now(),parser_version=EXCLUDED.parser_version;"
        )
    statements.append("UPDATE research.thesis_source_items SET validation_status='machine_validated',validated_by='AI OS deterministic issuer parser',"
                      "validated_at=now(),validation_notes='FY21-FY26 issuer operating history parsed; 24 deterministic checks passed; claim-level human review remains required.',updated_at=now() WHERE id=" + str(args.source_item_id) + ";")
    statements.append("COMMIT;")
    if failed:
        raise RuntimeError("Validation failed; facts were not persisted: " + json.dumps(failed))
    execute("\n".join(statements))
    print(json.dumps({"source_item_id": args.source_item_id, "years": list(YEARS),
                      "metrics": len(values), "facts_persisted": len(values) * len(YEARS),
                      "checks": len(checks), "checks_passed": len(checks)-len(failed),
                      "failed_checks": len(failed), "parser_version": PARSER_VERSION}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
