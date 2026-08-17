#!/usr/bin/env python3
"""Deterministically extract FY17-FY19 Usha Martin consolidated history.

This is deliberately narrow: it accepts only the three issuer-owned annual reports
held on the external Devarsh SSD, stores their existing SHA-256 and exact PDF
locators, and makes no estimates. FY17/FY18 include the legacy steel business;
the production-run summary preserves that non-comparability for the UI/model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pypdf import PdfReader

PARSER_NAME = "ushamart_legacy_primary_statement_parser"
PARSER_VERSION = 1
DOCKER = shutil.which("docker") or "/opt/homebrew/bin/docker"


@dataclass(frozen=True)
class Report:
    fiscal_year: int
    filing_id: int
    path: Path
    source_url: str
    balance_page: int
    pnl_page: int
    cf_pages: tuple[int, ...]
    value_index: int
    scope_note: str
    issuer_restatement: bool = False


REPORTS = (
    Report(
        2017, 1956,
        Path("/Volumes/Devarsh SSD/AI OS Data/artifacts/company_ir/ushamart/fy-2017-2018/annual-report.pdf"),
        "https://ushamartin.com/public/upload/investorrelations/Annual%20Report%202017-18_20211018123932_um-ar-all-page_for-net.pdf",
        88, 89, (90, 91), 1,
        "FY2017 comparative from FY2018 consolidated annual report. Includes legacy steel operations; not comparable with post-divestment continuing-business history.",
    ),
    Report(
        2018, 1956,
        Path("/Volumes/Devarsh SSD/AI OS Data/artifacts/company_ir/ushamart/fy-2017-2018/annual-report.pdf"),
        "https://ushamartin.com/public/upload/investorrelations/Annual%20Report%202017-18_20211018123932_um-ar-all-page_for-net.pdf",
        88, 89, (90, 91), 0,
        "FY2018 consolidated annual report. Includes legacy steel operations; not comparable with post-divestment continuing-business history.",
    ),
    Report(
        2019, 1954,
        Path("/Volumes/Devarsh SSD/AI OS Data/artifacts/company_ir/ushamart/fy-2019-2020/annual-report.pdf"),
        "https://ushamartin.com/public/upload/investorrelations/Annual%20Report%202019-20_20211018122316_um-accounts_2020.pdf",
        101, 102, (103, 104), 1,
        "FY2019 comparative restated in FY2020 consolidated annual report. Continuing and discontinued operations remain separately identified.",
        True,
    ),
)


def literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def jsonb(value: object) -> str:
    return literal(json.dumps(value, sort_keys=True, default=str)) + "::jsonb"


def run(sql: str) -> list[dict[str, Any]]:
    statement = "SELECT coalesce(json_agg(row_to_json(q)), '[]'::json)::text FROM (" + sql.rstrip().rstrip(";") + ") q;"
    result = subprocess.run(
        [DOCKER, "exec", "-i", "ai_os_postgres", "psql", "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os"],
        input=statement, text=True, capture_output=True, check=False,
    )
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip())
    return json.loads(result.stdout.strip() or "[]")


def execute(sql: str) -> None:
    result = subprocess.run(
        [DOCKER, "exec", "-i", "ai_os_postgres", "psql", "-q", "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os"],
        input=sql, text=True, capture_output=True, check=False,
    )
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip())


NUMBER = re.compile(r"\(?-?\d[\d,]*(?:\.\d+)?\)?")


def numbers(value: str) -> list[float]:
    values: list[float] = []
    for token in NUMBER.findall(value):
        negative = token.startswith("(") and token.endswith(")")
        try:
            parsed = float(token.strip("()").replace(",", ""))
        except ValueError:
            continue
        values.append(-parsed if negative else parsed)
    return values


def pair(value: str) -> tuple[float, float] | None:
    values = numbers(value)
    if len(values) >= 3 and 0 <= values[0] <= 200 and abs(values[1]) >= 500:
        values = values[1:]
    if len(values) != 2:
        return None
    return values[0], values[1]


def eps_pair(value: str) -> tuple[float, float] | None:
    values = numbers(value)
    return (values[-2], values[-1]) if len(values) >= 2 else None


def lines(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]


def find_pair(raw_lines: list[str], patterns: tuple[str, ...], *, eps: bool = False) -> tuple[float, float, str] | None:
    for index, line in enumerate(raw_lines):
        normal = line.lower()
        if not any(re.search(pattern, normal) for pattern in patterns):
            continue
        for width in (1, 2, 3):
            candidate = " ".join(raw_lines[index:index + width])
            found = eps_pair(candidate) if eps else pair(candidate)
            if found is not None:
                return found[0], found[1], candidate
    return None


DEFINITIONS: dict[str, tuple[str, tuple[str, ...], str, str]] = {
    "revenue": ("income_statement", (r"^revenue from operations\b",), "lakh", "reported_revenue"),
    "other_income": ("income_statement", (r"^other income\b",), "lakh", "reported_other_income"),
    "total_income": ("income_statement", (r"^total income\b",), "lakh", "reported_total_income"),
    "material_cost": ("income_statement", (r"^cost of materials consumed\b",), "lakh", "reported_material_cost"),
    "purchases": ("income_statement", (r"^purchase of stock",), "lakh", "reported_purchases"),
    "inventory_change": ("income_statement", (r"^\(?increase\)?\s*/\s*decrease in inventories",), "lakh", "reported_inventory_change"),
    "employee_expense": ("income_statement", (r"^employee benefits? expenses?\b",), "lakh", "reported_employee_expense"),
    "finance_cost": ("income_statement", (r"^finance costs?\b",), "lakh", "reported_finance_cost"),
    "depreciation": ("income_statement", (r"^depreciation and amortisation expenses?\b",), "lakh", "reported_depreciation"),
    "other_expense": ("income_statement", (r"^other expenses?\b",), "lakh", "reported_other_expense"),
    "total_expense": ("income_statement", (r"^total expenses?\b",), "lakh", "reported_total_expense"),
    "pbt_pre_jv_exceptional": ("income_statement", (r"^profit/?\(?loss\)? before tax and share", r"^profit before tax from continuing (?:operations|business)"), "lakh", "reported_pbt_pre_jv"),
    "tax_expense": ("income_statement", (r"^total tax expense\b",), "lakh", "reported_total_tax_expense"),
    "share_of_jv_profit": ("income_statement", (r"^share of profit/?\(?loss\)? of joint",), "lakh", "reported_share_of_jv"),
    "pat_total": ("income_statement", (r"^profit/?\(?loss\)? after share of profit", r"^profit/?\(?loss\)? for the year \(from continuing", r"^profit for the year \(from continuing"), "lakh", "reported_pat_total"),
    "eps_basic_total": ("income_statement", (r"^\(?basic and diluted, computed", r"^c\) basic and diluted earnings", r"^\(c\) from continuing and discontinued"), "INR/share", "reported_eps_total"),
    "ppe": ("balance_sheet", (r"^\(?a\)? property, plant and equipment\b",), "lakh", "reported_ppe"),
    "cwip": ("balance_sheet", (r"^\(?b\)? capital work-in-progress\b",), "lakh", "reported_cwip"),
    "goodwill": ("balance_sheet", (r"^\(?d\)? goodwill on consolidation\b",), "lakh", "reported_goodwill"),
    "other_intangible_assets": ("balance_sheet", (r"^\(?e\)? (?:intangible|other intangible) assets\b",), "lakh", "reported_intangibles"),
    "inventory": ("balance_sheet", (r"^\(?a\)? inventories\b",), "lakh", "reported_inventory"),
    "trade_receivables": ("balance_sheet", (r"^\(?i\)? trade receivables\b",), "lakh", "reported_trade_receivables"),
    "cash": ("balance_sheet", (r"^\(?ii\)? cash and cash equivalents\b",), "lakh", "reported_cash"),
    "other_bank_balances": ("balance_sheet", (r"^\(?iii\)? other bank balances\b",), "lakh", "reported_other_bank_balances"),
    "total_assets": ("balance_sheet", (r"^total assets\b", r"^total\s+\d"), "lakh", "reported_total_assets"),
    "total_equity": ("balance_sheet", (r"^total equity\b",), "lakh", "reported_total_equity"),
    "non_current_borrowings": ("balance_sheet", (r"^\(?i\)? borrowings\b",), "lakh", "reported_non_current_borrowings"),
    "current_borrowings": ("balance_sheet", (r"^\(?i\)? borrowings\b",), "lakh", "reported_current_borrowings"),
    "trade_payables": ("balance_sheet", (r"^\(?ii\)? trade payables\b",), "lakh", "reported_trade_payables"),
    "total_liabilities": ("balance_sheet", (r"^total liabilities\b",), "lakh", "reported_total_liabilities"),
    "cfo": ("cash_flow", (r"^net cash flows? (?:from|generated from) operating activities\b",), "lakh", "reported_cfo"),
    "capex": ("cash_flow", (r"^purchase of property, plant and equipment\b",), "lakh", "reported_capex"),
    "cfi": ("cash_flow", (r"^net cash flows? used in investing activities\b", r"^net cash flows? from/\(used in\) investing activities\b"), "lakh", "reported_cfi"),
    "cff": ("cash_flow", (r"^net cash flows? used in financing activities\b", r"^net cash flows? from/\(used in\) financing activities\b"), "lakh", "reported_cff"),
    "fx_cash": ("cash_flow", (r"^d\. effect of foreign exchange differences",), "lakh", "reported_fx_cash"),
    "net_cash_change": ("cash_flow", (r"^net increase / \(decrease\) in cash",), "lakh", "reported_net_cash_change"),
    "opening_cash": ("cash_flow", (r"^cash and cash equivalents at the beginning",), "lakh", "reported_opening_cash"),
    "closing_cash": ("cash_flow", (r"^cash and cash equivalents at the year end",), "lakh", "reported_closing_cash"),
}


def page_text(reader: PdfReader, pages: tuple[int, ...]) -> tuple[list[str], dict[int, list[str]]]:
    by_page = {page: lines(reader.pages[page - 1].extract_text() or "") for page in pages}
    return [line for values in by_page.values() for line in values], by_page


def extract(report: Report) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if not report.path.exists() or not str(report.path).startswith("/Volumes/Devarsh SSD/"):
        raise RuntimeError("Expected issuer PDF is not on the external SSD: " + str(report.path))
    reader = PdfReader(str(report.path))
    sections = {
        "income_statement": (report.pnl_page,),
        "balance_sheet": (report.balance_page,),
        "cash_flow": report.cf_pages,
    }
    extracted: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for key, (statement_type, patterns, unit, basis) in DEFINITIONS.items():
        source_pages = sections[statement_type]
        block, by_page = page_text(reader, source_pages)
        found = find_pair(block, patterns, eps=unit == "INR/share")
        if found is None:
            missing.append({"fact_key": key, "statement_type": statement_type, "pages": source_pages})
            continue
        current, comparative, reported_line = found
        page_number = next(page for page, page_lines in by_page.items() if reported_line.split(" ")[0] in " ".join(page_lines))
        extracted.append({"fact_key": key, "statement_type": statement_type, "value": (current, comparative)[report.value_index],
                          "unit": unit, "fact_basis": basis, "source_page": page_number, "reported_line": reported_line})
    facts = {row["fact_key"]: row["value"] for row in extracted}
    checks: list[dict[str, Any]] = []
    if {"total_income", "total_expense", "pbt_pre_jv_exceptional"} <= facts.keys():
        checks.append({"key": "pnl_pre_tax_tie", "left": facts["total_income"] - facts["total_expense"],
                       "right": facts["pbt_pre_jv_exceptional"], "tolerance": 1.0, "pages": [report.pnl_page]})
    if {"total_assets", "total_equity", "total_liabilities"} <= facts.keys():
        checks.append({"key": "balance_sheet_tie", "left": facts["total_assets"],
                       "right": facts["total_equity"] + facts["total_liabilities"], "tolerance": 1.0, "pages": [report.balance_page]})
    if {"opening_cash", "cfo", "cfi", "cff", "fx_cash", "closing_cash"} <= facts.keys():
        checks.append({"key": "cash_rollforward_tie", "left": facts["opening_cash"] + facts["cfo"] + facts["cfi"] + facts["cff"] + facts["fx_cash"],
                       "right": facts["closing_cash"], "tolerance": 1.0, "pages": list(report.cf_pages)})
    for check in checks:
        check["status"] = "pass" if abs(check["left"] - check["right"]) <= check["tolerance"] else "fail"
    return extracted, checks, missing


def statement(report: Report, facts: list[dict[str, Any]], checks: list[dict[str, Any]], missing: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256(report.path.read_bytes()).hexdigest()
    db_hash = run("SELECT content_hash FROM research.corporate_filings WHERE id=" + str(report.filing_id))
    if not db_hash or db_hash[0]["content_hash"] != digest:
        raise RuntimeError("PDF SHA-256 mismatch against governed corporate filing " + str(report.filing_id))
    if any(row["status"] == "fail" for row in checks):
        raise RuntimeError("Validation failed; no facts persisted for FY" + str(report.fiscal_year) + ": " + json.dumps(checks))
    run_key = "ushamart-fy" + str(report.fiscal_year) + "-legacy-primary-v" + str(PARSER_VERSION)
    summary = {"fiscal_year": report.fiscal_year, "scope_note": report.scope_note, "comparability": "not_comparable_pre_disposal" if report.fiscal_year <= 2018 else "continuing_discontinued_split", "missing_fact_keys": [row["fact_key"] for row in missing], "checks": checks, "source_is_issuer_owned": True}
    statements = ["BEGIN;"]
    statements.append("INSERT INTO research.financial_production_runs(run_key,company_id,filing_id,parser_name,parser_version,statement_scope,currency,unit,source_sha256,source_url,source_path,status,completed_at,created_by,summary) VALUES(" +
                      literal(run_key) + ",43," + str(report.filing_id) + "," + literal(PARSER_NAME) + "," + str(PARSER_VERSION) + "," + literal("consolidated") + "," + literal("INR") + "," + literal("lakh") + "," + literal(digest) + "," + literal(report.source_url) + "," + literal(str(report.path)) + ",'validated',now(),'AI OS deterministic primary-source parser'," + jsonb(summary) + ") ON CONFLICT(run_key) DO UPDATE SET source_sha256=EXCLUDED.source_sha256,source_url=EXCLUDED.source_url,source_path=EXCLUDED.source_path,status='validated',completed_at=now(),summary=EXCLUDED.summary RETURNING id;")
    for fact in facts:
        statements.append("INSERT INTO research.financial_source_facts(production_run_id,company_id,fact_key,fiscal_year,period_end,statement_type,statement_scope,value,currency,unit,source_page,reported_line,extraction_status,issuer_restatement) SELECT id,43," + literal(fact["fact_key"]) + "," + str(report.fiscal_year) + ",DATE '" + str(report.fiscal_year) + "-03-31'," + literal(fact["statement_type"]) + ",'consolidated'," + str(fact["value"]) + ",'INR'," + literal(fact["unit"]) + "," + str(fact["source_page"]) + "," + literal(fact["reported_line"]) + ",'validated'," + ("true" if report.issuer_restatement else "false") + " FROM research.financial_production_runs WHERE run_key=" + literal(run_key) + " ON CONFLICT(production_run_id,fact_key,fiscal_year,statement_scope) DO UPDATE SET value=EXCLUDED.value,source_page=EXCLUDED.source_page,reported_line=EXCLUDED.reported_line,extraction_status='validated',issuer_restatement=EXCLUDED.issuer_restatement;")
    for check in checks:
        statements.append("INSERT INTO research.financial_validation_checks(production_run_id,check_key,period_end,check_type,status,left_value,right_value,tolerance,explanation,source_pages) SELECT id," + literal(check["key"] + "_" + str(report.fiscal_year)) + ",DATE '" + str(report.fiscal_year) + "-03-31'," + literal("statement_reconciliation") + ",'pass'," + str(check["left"]) + "," + str(check["right"]) + "," + str(check["tolerance"]) + "," + literal("Deterministic annual-report tie-out from issuer PDF; no estimates or model values.") + ",ARRAY[" + ",".join(str(page) for page in check["pages"]) + "] FROM research.financial_production_runs WHERE run_key=" + literal(run_key) + " ON CONFLICT(production_run_id,check_key,period_end) DO UPDATE SET status='pass',left_value=EXCLUDED.left_value,right_value=EXCLUDED.right_value,explanation=EXCLUDED.explanation,source_pages=EXCLUDED.source_pages;")
    for item in missing:
        statements.append("INSERT INTO research.financial_history_gaps(company_id,section_key,metric_key,period_start,period_end,gap_status,reason,next_source) VALUES(43," + literal(item["statement_type"]) + "," + literal(item["fact_key"]) + ",DATE '" + str(report.fiscal_year) + "-04-01',DATE '" + str(report.fiscal_year) + "-03-31','not_disclosed'," + literal("Issuer PDF parser did not find a reliable two-period row; value intentionally not inferred.") + "," + literal("Review exact issuer annual-report note pages.") + ") ON CONFLICT(company_id,section_key,metric_key,period_start,period_end) DO UPDATE SET reason=EXCLUDED.reason,next_source=EXCLUDED.next_source;")
    if report.fiscal_year <= 2018:
        statements.append("INSERT INTO research.financial_history_gaps(company_id,section_key,metric_key,period_start,period_end,gap_status,reason,next_source) VALUES(43,'comparability','legacy_steel_divestment',DATE '" + str(report.fiscal_year) + "-04-01',DATE '" + str(report.fiscal_year) + "-03-31','not_comparable'," + literal(report.scope_note) + "," + literal("Use continuing-operations disclosures or show a labelled break in any multi-year trend.") + ") ON CONFLICT(company_id,section_key,metric_key,period_start,period_end) DO UPDATE SET reason=EXCLUDED.reason,next_source=EXCLUDED.next_source;")
    statements.append("COMMIT;")
    return "\n".join(statements)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()
    all_output: list[dict[str, Any]] = []
    sql_blocks: list[str] = []
    for report in REPORTS:
        facts, checks, missing = extract(report)
        all_output.append({"fiscal_year": report.fiscal_year, "facts": len(facts), "checks": checks, "missing": missing, "source_path": str(report.path)})
        if args.persist:
            sql_blocks.append(statement(report, facts, checks, missing))
    if args.persist:
        for block in sql_blocks:
            execute(block)
    print(json.dumps({"parser": PARSER_NAME, "version": PARSER_VERSION, "persisted": bool(args.persist), "reports": all_output}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
