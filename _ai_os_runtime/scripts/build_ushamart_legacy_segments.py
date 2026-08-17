#!/usr/bin/env python3
"""Parse disclosed FY17-FY19 Usha Martin segment/geography/capex tables from issuer PDFs."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

from pypdf import PdfReader

DOCKER = shutil.which("docker") or "/opt/homebrew/bin/docker"
PARSER = "ushamart_legacy_segment_parser_v1"
REPORTS = {
    2017: ("ushamart-fy2017-legacy-primary-v1", Path("/Volumes/Devarsh SSD/AI OS Data/artifacts/company_ir/ushamart/fy-2017-2018/annual-report.pdf"), 131, 132, 1),
    2018: ("ushamart-fy2018-legacy-primary-v1", Path("/Volumes/Devarsh SSD/AI OS Data/artifacts/company_ir/ushamart/fy-2017-2018/annual-report.pdf"), 131, 132, 0),
    2019: ("ushamart-fy2019-segments-primary-v1", Path("/Volumes/Devarsh SSD/AI OS Data/artifacts/company_ir/ushamart/fy-2018-2019/annual-report.pdf"), 139, 140, 0),
}


def literal(value: object) -> str:
    return "NULL" if value is None else "'" + str(value).replace("'", "''") + "'"


def psql(sql: str) -> None:
    result = subprocess.run([DOCKER, "exec", "-i", "ai_os_postgres", "psql", "-q", "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os"], input=sql, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip())


def lines(path: Path, page: int) -> list[str]:
    return [re.sub(r"\s+", " ", x).strip() for x in (PdfReader(str(path)).pages[page - 1].extract_text() or "").splitlines() if x.strip()]


def values(value: str) -> list[float]:
    result = []
    for token in re.findall(r"\(?-?\d[\d,]*(?:\.\d+)?\)?", value):
        result.append((-1 if token.startswith("(") else 1) * float(token.strip("()").replace(",", "")))
    return result


def row(page_lines: list[str], pattern: str) -> tuple[list[float], str]:
    for index, text in enumerate(page_lines):
        if re.search(pattern, text, flags=re.I):
            candidate = " ".join(page_lines[index:index + 2])
            parsed = values(candidate)
            if len(parsed) >= 2:
                return parsed, candidate
    raise ValueError("Segment row not found: " + pattern)


def facts_for_year(fiscal_year: int) -> tuple[list[dict], list[dict]]:
    run_key, path, segment_page, geo_page, value_index = REPORTS[fiscal_year]
    if not path.exists() or not str(path).startswith("/Volumes/Devarsh SSD/"):
        raise RuntimeError("Missing external-SSD issuer PDF: " + str(path))
    main = lines(path, segment_page)
    geo = lines(path, geo_page)
    external, external_line = row(main, r"^external revenue")
    result, result_line = row(main, r"^segment (?:results?|profit)")
    assets, assets_line = row(main, r"^total assets")
    liabilities, liabilities_line = row(main, r"^total liabilities")
    india, india_line = row(geo, r"^india\b")
    outside, outside_line = row(geo, r"^outside india")
    capex_india, capex_india_line = row(geo, r"^india\b")
    # The first India/Outside pair is revenue. Locate the second pair after the capex heading.
    capex_index = next(i for i, text in enumerate(geo) if re.search(r"^segment capital expenditure", text, re.I))
    capex_tail = geo[capex_index + 1:]
    capex_india, capex_india_line = row(capex_tail, r"^india\b")
    capex_outside, capex_outside_line = row(capex_tail, r"^outside india")
    names = ("steel", "wire_and_wire_ropes", "others") if fiscal_year <= 2018 else ("discontinued_steel", "wire_and_wire_ropes", "others")
    labels = ("Steel", "Wire and wire ropes", "Others") if fiscal_year <= 2018 else ("Discontinued steel", "Wire and wire ropes — continuing", "Others — continuing")
    offset = 4 * value_index
    records: list[dict] = []
    for index, (key, label) in enumerate(zip(names, labels)):
        for metric, source, source_line in (("revenue", external, external_line), ("result", result, result_line), ("assets", assets, assets_line), ("liabilities", liabilities, liabilities_line)):
            records.append({"segment_type": "business", "segment_key": key, "segment_name": label, "metric_key": metric,
                            "value": source[offset + index], "source_page": segment_page, "reported_line": source_line})
    records.extend([
        {"segment_type": "geography", "segment_key": "india", "segment_name": "India", "metric_key": "revenue", "value": india[value_index], "source_page": geo_page, "reported_line": india_line},
        {"segment_type": "geography", "segment_key": "outside_india", "segment_name": "Outside India", "metric_key": "revenue", "value": outside[value_index], "source_page": geo_page, "reported_line": outside_line},
        {"segment_type": "geography", "segment_key": "india", "segment_name": "India", "metric_key": "capex", "value": capex_india[value_index], "source_page": geo_page, "reported_line": capex_india_line},
        {"segment_type": "geography", "segment_key": "outside_india", "segment_name": "Outside India", "metric_key": "capex", "value": capex_outside[value_index], "source_page": geo_page, "reported_line": capex_outside_line},
    ])
    geography_expected = external[offset + 3] if fiscal_year <= 2018 else external[offset + 1] + external[offset + 2]
    checks = [
        {"key": "business_external_revenue_sum", "left": sum(external[offset:offset + 3]), "right": external[offset + 3], "page": segment_page},
        {"key": "geography_revenue_sum", "left": india[value_index] + outside[value_index], "right": geography_expected, "page": geo_page},
    ]
    return records, checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()
    output = []
    for year in sorted(REPORTS):
        records, checks = facts_for_year(year)
        failed = [c for c in checks if abs(c["left"] - c["right"]) > 1]
        if failed:
            raise RuntimeError("Segment reconciliation failed for FY" + str(year) + ": " + json.dumps(failed))
        output.append({"fiscal_year": year, "records": len(records), "checks": checks})
        if args.persist:
            run_key = REPORTS[year][0]
            sql = ["BEGIN;"]
            for fact in records:
                sql.append("INSERT INTO research.financial_segment_facts(production_run_id,company_id,fiscal_year,period_end,segment_type,segment_key,segment_name,metric_key,value,currency,unit,source_page,reported_line,extraction_status) SELECT id,43," + str(year) + ",DATE '" + str(year) + "-03-31'," + literal(fact["segment_type"]) + "," + literal(fact["segment_key"]) + "," + literal(fact["segment_name"]) + "," + literal(fact["metric_key"]) + "," + str(fact["value"]) + ",'INR','lakh'," + str(fact["source_page"]) + "," + literal(fact["reported_line"]) + ",'validated' FROM research.financial_production_runs WHERE run_key=" + literal(run_key) + " ON CONFLICT(production_run_id,fiscal_year,segment_type,segment_key,metric_key) DO UPDATE SET value=EXCLUDED.value,source_page=EXCLUDED.source_page,reported_line=EXCLUDED.reported_line,extraction_status='validated';")
            for check in checks:
                sql.append("INSERT INTO research.financial_validation_checks(production_run_id,check_key,period_end,check_type,status,left_value,right_value,tolerance,explanation,source_pages) SELECT id," + literal(check["key"] + "_" + str(year)) + ",DATE '" + str(year) + "-03-31','segment_reconciliation','pass'," + str(check["left"]) + "," + str(check["right"]) + ",1," + literal("Issuer segment/geography reconciliation; no estimate or inferred segment allocation.") + ",ARRAY[" + str(check["page"]) + "] FROM research.financial_production_runs WHERE run_key=" + literal(run_key) + " ON CONFLICT(production_run_id,check_key,period_end) DO UPDATE SET status='pass',left_value=EXCLUDED.left_value,right_value=EXCLUDED.right_value,source_pages=EXCLUDED.source_pages;")
            sql.append("COMMIT;")
            psql("\n".join(sql))
    print(json.dumps({"parser": PARSER, "persisted": args.persist, "years": output}, indent=2))


if __name__ == "__main__":
    main()
