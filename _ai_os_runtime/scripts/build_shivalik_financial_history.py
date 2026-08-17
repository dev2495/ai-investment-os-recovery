#!/usr/bin/env python3
"""Build a reconciled Shivalik consolidated history from official annual reports.

The script is intentionally issuer-specific at the page/label adapter layer and
generic at the governed persistence layer. It never infers a missing reported
line, never writes outside the external SSD, and advances rows to validated
only when the source hash and statement tie-outs pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
RUNTIME_ROOT = SCRIPT_DIR.parent
for candidate in (RUNTIME_ROOT, RUNTIME_ROOT / "api"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from collect_nse_bse_filings import (
    run_psql_json as _run_psql_json,
    run_psql_text as psql_text,
    sql_jsonb,
    sql_literal,
)

SSD_ROOT = Path("/Volumes/Devarsh SSD")
DATA_ROOT = SSD_ROOT / "AI OS Data"
COMPANY_ID = 35
TICKER = "SBCL"
PARSER_NAME = "shivalik_consolidated_statement_reconciler"
PARSER_VERSION = 1


def psql_json(query: str) -> list[dict[str, Any]]:
    """Return rows through the runtime's docker-backed JSON SQL boundary."""
    normalized = query.strip().rstrip(";")
    if normalized.upper().startswith(("INSERT", "UPDATE", "DELETE")):
        wrapped = (
            "WITH changed AS (" + normalized + ") "
            "SELECT coalesce(json_agg(row_to_json(changed)), '[]'::json)::text FROM changed"
        )
    else:
        wrapped = (
            "SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text "
            "FROM (" + normalized + ") rows"
        )
    return _run_psql_json(wrapped)

FACT_PATTERNS: dict[str, tuple[str, tuple[str, ...]]] = {
    "property_plant_equipment": ("balance_sheet", (r"property,? plant (?:&|and) equipment",)),
    "capital_work_in_progress": ("balance_sheet", (r"capital work-in-progress", r"capital work in progress")),
    "total_non_current_assets": ("balance_sheet", (r"^total non[- ]?current assets",)),
    "inventories": ("balance_sheet", (r"\binventories\b",)),
    "trade_receivables": ("balance_sheet", (r"trade receivables",)),
    "cash_and_cash_equivalents": ("balance_sheet", (r"cash and cash equivalents", r"cash and cash equivalents")),
    "other_bank_balances": ("balance_sheet", (r"bank balances other than", r"other bank balances")),
    "total_current_assets": ("balance_sheet", (r"^total current assets",)),
    "total_assets": ("balance_sheet", (r"^total assets",)),
    "equity_share_capital": ("balance_sheet", (r"equity share capital", r"equity share capital")),
    "total_equity": ("balance_sheet", (r"^total equity",)),
    "non_current_borrowings": ("balance_sheet", (r"borrowings",)),
    "current_borrowings": ("balance_sheet", (r"borrowings",)),
    "total_non_current_liabilities": ("balance_sheet", (r"^total non[- ]?current liabilities",)),
    "total_current_liabilities": ("balance_sheet", (r"^total current liabilities",)),
    "revenue_from_operations": ("income_statement", (r"revenue from operations",)),
    "other_income": ("income_statement", (r"^(?:ii\s+)?other income",)),
    "total_income": ("income_statement", (r"^(?:iii\s+)?total (?:income|revenue)",)),
    "cost_of_materials_consumed": ("income_statement", (r"cost of materials consumed",)),
    "inventory_change": ("income_statement", (r"changes in inventories",)),
    "employee_benefit_expense": ("income_statement", (r"employee benefits? expense",)),
    "finance_cost": ("income_statement", (r"finance costs?",)),
    "depreciation_amortisation": ("income_statement", (r"depreciation (?:&|and) amortisation",)),
    "manufacturing_other_expenses": ("income_statement", (r"manufacturing (?:&|and) other expenses",)),
    "total_expenses": ("income_statement", (r"^total expenses",)),
    "profit_before_joint_venture": ("income_statement", (r"profit before share of", r"profit\s*/?\s*\(loss\) before tax\s*\(iii-iv\)", r"profit before exceptional items and tax\s*\(iii-iv\)")),
    "share_of_joint_venture_profit": ("income_statement", (r"^vi share of profit",)),
    "exceptional_items": ("income_statement", (r"^viii exceptional items",)),
    "profit_before_tax": ("income_statement", (r"profit before tax \(vii-viii\)", r"profit/?\(loss\) before tax \(vii-viii\)")),
    "tax_expense": ("income_statement", (r"^total tax expense", r"^total\s+\d")),
    "profit_after_tax": ("income_statement", (r"profit for the years? \(ix-x\)", r"profit/?\(loss\) for the years? \(ix-x\)")),
    "basic_eps": ("income_statement", (r"basic (?:&|and) diluted", r"\(a\) basic")),
    "operating_cash_flow": ("cash_flow", (r"net cash generated from operating activities", r"net cash generated from operating activities")),
    "capital_expenditure": ("cash_flow", (r"payment for (?:purchase of )?property plant", r"payment for purchase of property plant")),
    "investing_cash_flow": ("cash_flow", (r"net cash \(used in\)/ from investing activities",)),
    "financing_cash_flow": ("cash_flow", (r"net cash generated from financing activities",)),
    "net_cash_change": ("cash_flow", (r"net increase in cash and cash equivalents",)),
    "opening_cash": ("cash_flow", (r"cash and cash equivalents (?:at the beginning of the year|\(opening balance\))",)),
    "cash_acquired": ("cash_flow", (r"cash and cash equivalents acquired in business combination",)),
    "exchange_effect_cash": ("cash_flow", (r"unrealised exchange .*translation of foreign currency cash",)),
    "closing_cash": ("cash_flow", (r"cash and cash equivalents? (?:at the closing of year|\(closing balance\))",)),
    "dividends_paid": ("cash_flow", (r"^dividend paid",)),
}

MANDATORY = {
    "balance_sheet": {"total_assets", "total_equity", "total_non_current_liabilities", "total_current_liabilities"},
    "income_statement": {"total_income", "total_expenses", "profit_before_joint_venture", "profit_before_tax", "tax_expense", "profit_after_tax", "revenue_from_operations"},
    "cash_flow": {"operating_cash_flow", "investing_cash_flow", "financing_cash_flow", "net_cash_change", "opening_cash", "closing_cash"},
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_lines(text: str) -> list[str]:
    text = re.sub(r"(?<=\d)\s+\.(?=\d)", ".", text)
    for broken, fixed in {
        "ma terials": "materials", "c hanges": "changes", "e mployee": "employee",
        "f inance": "finance", "depr eciation": "depreciation",
        "manufact uring": "manufacturing", "ba sic": "basic",
    }.items():
        text = re.sub(re.escape(broken), fixed, text, flags=re.IGNORECASE)
    return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]


def number_tokens(text: str) -> list[Decimal]:
    values: list[Decimal] = []
    for token in re.findall(r"\(?-?\d[\d,]*(?:\.\d+)?\)?", text):
        negative = token.startswith("(") and token.endswith(")")
        try:
            value = Decimal(token.strip("()").replace(",", ""))
        except Exception:
            continue
        values.append(-value if negative else value)
    return values


def pair_from(lines: list[str], index: int) -> tuple[Decimal, Decimal, str] | None:
    for width in (1, 2, 3):
        candidate = " ".join(lines[index:index + width])
        values = number_tokens(candidate)
        if len(values) >= 2:
            return values[-2], values[-1], candidate
    return None


def page_kinds(text: str) -> list[str]:
    compact = re.sub(r"\s+", " ", text).lower()
    kinds: list[str] = []
    if "consolidated balance sheet" in compact and "total assets" in compact and "total equity" in compact:
        kinds.append("balance_sheet")
    if "consolidated statement of profit" in compact and "revenue from operations" in compact and "total expenses" in compact:
        kinds.append("income_statement")
    if "consolidated cash flow statement" in compact and any(
        marker in compact for marker in ("cash flow from operating activities", "cash flow from financing activities", "net increase in cash")
    ):
        kinds.append("cash_flow")
    return kinds


def extract_report(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    from pypdf import PdfReader  # type: ignore

    pages: dict[str, int] = {}
    facts: dict[str, dict[str, Any]] = {}
    for page_number, page in enumerate(PdfReader(str(path)).pages, start=1):
        text = page.extract_text() or ""
        kinds = page_kinds(text)
        if not kinds:
            continue
        lines = normalized_lines(text)
        for kind in kinds:
            if kind in pages and kind != "cash_flow":
                continue
            pages.setdefault(kind, page_number)
            current_liability_section = False
            non_current_liability_section = False
            for index, line in enumerate(lines):
                lower = line.lower()
                if kind == "balance_sheet":
                    if lower.startswith("non-current liabilities"):
                        non_current_liability_section, current_liability_section = True, False
                    elif lower.startswith("current liabilities"):
                        current_liability_section, non_current_liability_section = True, False
                for key, (statement_type, patterns) in FACT_PATTERNS.items():
                    if key in facts or statement_type != kind:
                        continue
                    if key == "non_current_borrowings" and not non_current_liability_section:
                        continue
                    if key == "current_borrowings" and not current_liability_section:
                        continue
                    if not any(re.search(pattern, lower) for pattern in patterns):
                        continue
                    if key in {"exceptional_items", "cash_acquired"}:
                        special_values = number_tokens(line)
                        if len(special_values) <= 1 and "-" in line:
                            value = special_values[0] if special_values else Decimal(0)
                            token_match = re.search(r"\(?-?\d[\d,]*(?:\.\d+)?\)?", line)
                            dash_position = line.find("-")
                            token_position = token_match.start() if token_match else -1
                            dash_is_current = token_position >= 0 and dash_position < token_position
                            facts[key] = {
                                "fact_key": key,
                                "statement_type": kind,
                                "page": page_number,
                                "reported_line": line,
                                "current": Decimal(0) if dash_is_current else value,
                                "comparative": value if dash_is_current else Decimal(0),
                            }
                            continue
                    pair = pair_from(lines, index)
                    if not pair:
                        continue
                    current, comparative, reported_line = pair
                    facts[key] = {
                        "fact_key": key,
                        "statement_type": kind,
                        "page": page_number,
                        "reported_line": reported_line,
                        "current": current,
                        "comparative": comparative,
                    }
    return facts, pages


def source_reports(limit: int) -> list[dict[str, Any]]:
    return psql_json(f"""
      SELECT filing.id filing_id,(filing.payload->>'fiscal_year_end')::int fiscal_year,
        filing.source_url,filing.local_path,filing.content_hash,evidence.id evidence_id
      FROM research.corporate_filings filing
      JOIN research.fundamental_evidence evidence ON evidence.corporate_filing_id=filing.id
      WHERE evidence.company_id={COMPANY_ID} AND filing.source_name='Company IR'
        AND filing.filing_type='annual_report' AND filing.payload->>'fiscal_year_end' IS NOT NULL
      ORDER BY (filing.payload->>'fiscal_year_end')::int DESC,filing.id DESC LIMIT {limit}
    """)


def selected_years(reports: list[dict[str, Any]]) -> dict[int, tuple[dict[str, Any], str]]:
    selected: dict[int, tuple[dict[str, Any], str]] = {}
    for report in reports:
        fy = int(report["fiscal_year"])
        selected.setdefault(fy, (report, "current"))
        selected.setdefault(fy - 1, (report, "comparative"))
    return {year: value for year, value in selected.items() if 2020 <= year <= 2026}


def upsert_fact(run_id: int, year: int, row: dict[str, Any], side: str) -> int:
    value = row[side]
    unit = "INR/share" if row["fact_key"] == "basic_eps" else "lakh"
    result = psql_json(f"""
      INSERT INTO research.financial_source_facts
        (production_run_id,company_id,fact_key,fiscal_year,period_end,statement_type,
         statement_scope,value,currency,unit,source_page,reported_line,extraction_status)
      VALUES ({run_id},{COMPANY_ID},{sql_literal(row['fact_key'])},{year},DATE '{year}-03-31',
        {sql_literal(row['statement_type'])},'consolidated',{sql_literal(str(value))},'INR',
        {sql_literal(unit)},{int(row['page'])},{sql_literal(row['reported_line'])},'validated')
      ON CONFLICT (production_run_id,fact_key,fiscal_year,statement_scope) DO UPDATE SET
        value=EXCLUDED.value,source_page=EXCLUDED.source_page,reported_line=EXCLUDED.reported_line,
        extraction_status='validated'
      RETURNING id
    """)
    return int(result[0]["id"])


def check(run_id: int, year: int, key: str, check_type: str, left: Decimal, right: Decimal, pages: list[int], tolerance: Decimal = Decimal("1")) -> bool:
    passed = abs(left - right) <= tolerance
    psql_text(f"""
      INSERT INTO research.financial_validation_checks
        (production_run_id,check_key,period_end,check_type,status,left_value,right_value,tolerance,explanation,source_pages)
      VALUES ({run_id},{sql_literal(key)},DATE '{year}-03-31',{sql_literal(check_type)},
        {sql_literal('pass' if passed else 'fail')},{sql_literal(str(left))},{sql_literal(str(right))},
        {sql_literal(str(tolerance))},{sql_literal('Official annual-report statement tie-out.' if passed else 'Official statement did not tie; facts remain blocked.')},
        ARRAY[{','.join(str(page) for page in sorted(set(pages)))}]::integer[])
      ON CONFLICT (production_run_id,check_key,period_end) DO UPDATE SET status=EXCLUDED.status,
        left_value=EXCLUDED.left_value,right_value=EXCLUDED.right_value,tolerance=EXCLUDED.tolerance,
        explanation=EXCLUDED.explanation,source_pages=EXCLUDED.source_pages
    """)
    return passed


def persist_ratio(run_id: int, year: int, key: str, label: str, expression: str, unit: str, value: Decimal | None, inputs: dict[str, int], reason: str | None = None, caveats: list[str] | None = None) -> None:
    basis = {"scope": "consolidated", "period": "annual", "source": "validated official annual reports"}
    definition = psql_json(f"""
      INSERT INTO research.financial_formula_definitions(formula_key,version,label,expression,basis,unit,created_by)
      VALUES ({sql_literal(key)},2,{sql_literal(label)},{sql_literal(expression)},{sql_jsonb(basis)},
        {sql_literal(unit)},'AI OS deterministic formula registry')
      ON CONFLICT(formula_key,version) DO UPDATE SET label=EXCLUDED.label,expression=EXCLUDED.expression,
        basis=EXCLUDED.basis,unit=EXCLUDED.unit RETURNING id
    """)
    result = psql_json(f"""
      INSERT INTO research.financial_ratio_results
        (production_run_id,company_id,formula_definition_id,period_end,statement_scope,value,
         calculation_status,not_computable_reason,caveats)
      VALUES ({run_id},{COMPANY_ID},{int(definition[0]['id'])},DATE '{year}-03-31','consolidated',
        {sql_literal(str(value)) if value is not None else 'NULL'},
        {sql_literal('validated' if value is not None else 'not_computable')},
        {sql_literal(reason) if reason else 'NULL'},{sql_jsonb(caveats or [])})
      ON CONFLICT(production_run_id,formula_definition_id,period_end,statement_scope) DO UPDATE SET
        value=EXCLUDED.value,calculation_status=EXCLUDED.calculation_status,
        not_computable_reason=EXCLUDED.not_computable_reason,caveats=EXCLUDED.caveats RETURNING id
    """)
    ratio_id = int(result[0]["id"])
    psql_text(f"DELETE FROM research.financial_ratio_inputs WHERE ratio_result_id={ratio_id}")
    for role, fact_id in inputs.items():
        psql_text(f"INSERT INTO research.financial_ratio_inputs(ratio_result_id,input_role,fact_id) VALUES({ratio_id},{sql_literal(role)},{fact_id})")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--persist", action="store_true")
    parser.add_argument("--actor", default="AI OS Financial Validation Agent")
    args = parser.parse_args()
    if not SSD_ROOT.is_mount() or not DATA_ROOT.is_dir() or not os.access(DATA_ROOT, os.W_OK):
        raise RuntimeError("Devarsh SSD is not mounted and writable; no internal-disk fallback")
    reports = source_reports(12)
    parsed: dict[int, tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, int]]] = {}
    for report in reports:
        fy = int(report["fiscal_year"])
        if fy in parsed:
            continue
        path = Path(str(report["local_path"])).resolve()
        if not str(path).startswith(str(DATA_ROOT) + os.sep) or not path.is_file():
            continue
        if path.parent.name != f"fy-{fy - 1}-{fy}":
            # Preserve earlier collector mistakes for audit, but never parse a
            # report whose governed fiscal-year folder disagrees with metadata.
            continue
        actual_hash = sha256_file(path)
        if actual_hash != str(report["content_hash"]):
            raise RuntimeError(f"source hash mismatch for FY{fy}: {path}")
        facts, pages = extract_report(path)
        parsed[fy] = (report, facts, pages)
    chosen = selected_years([row[0] for row in parsed.values()])
    preview: dict[int, dict[str, Any]] = {}
    for year, (report, side) in chosen.items():
        facts = parsed[int(report["fiscal_year"])][1]
        preview[year] = {key: str(row[side]) for key, row in facts.items()}
    if not args.persist:
        print(json.dumps({"ok": True, "years": sorted(preview), "facts_per_year": {str(y): len(v) for y, v in preview.items()}, "preview": preview}, indent=2, sort_keys=True))
        return 0

    year_fact_ids: dict[int, dict[str, int]] = defaultdict(dict)
    year_values: dict[int, dict[str, Decimal]] = defaultdict(dict)
    year_runs: dict[int, int] = {}
    failures: list[str] = []
    for year in sorted(chosen):
        report, side = chosen[year]
        report_fy = int(report["fiscal_year"])
        facts, pages = parsed[report_fy][1], parsed[report_fy][2]
        available = {key: row for key, row in facts.items() if row[side] is not None}
        missing = sorted(set().union(*MANDATORY.values()) - set(available))
        run_key = f"shivalik-official-history-fy{year}-source-fy{report_fy}-v1"
        run = psql_json(f"""
          INSERT INTO research.financial_production_runs
            (run_key,company_id,filing_id,parser_name,parser_version,statement_scope,currency,unit,
             source_sha256,source_url,source_path,status,created_by,summary)
          VALUES ({sql_literal(run_key)},{COMPANY_ID},{int(report['filing_id'])},{sql_literal(PARSER_NAME)},
            {PARSER_VERSION},'consolidated','INR','lakh',{sql_literal(report['content_hash'])},
            {sql_literal(report['source_url'])},{sql_literal(report['local_path'])},'running',
            {sql_literal(args.actor)},{sql_jsonb({'source_fiscal_year': report_fy, 'selected_side': side})})
          ON CONFLICT(run_key) DO UPDATE SET status='running',completed_at=NULL,summary=EXCLUDED.summary RETURNING id
        """)
        run_id = int(run[0]["id"]); year_runs[year] = run_id
        for key, row in available.items():
            fact_id = upsert_fact(run_id, year, row, side)
            year_fact_ids[year][key] = fact_id
            year_values[year][key] = row[side]
        values = year_values[year]
        checks: list[bool] = []
        if all(k in values for k in ("total_assets", "total_equity", "total_non_current_liabilities", "total_current_liabilities")):
            checks.append(check(run_id, year, "balance_sheet_tie", "balance_sheet", values["total_assets"], values["total_equity"] + values["total_non_current_liabilities"] + values["total_current_liabilities"], [pages["balance_sheet"]]))
        if all(k in values for k in ("total_income", "total_expenses", "profit_before_joint_venture")):
            checks.append(check(run_id, year, "profit_loss_operating_tie", "profit_and_loss", values["total_income"] - values["total_expenses"], values["profit_before_joint_venture"], [pages["income_statement"]]))
        if all(k in values for k in ("profit_before_joint_venture", "share_of_joint_venture_profit", "profit_before_tax")):
            exceptional = values.get("exceptional_items", Decimal(0))
            checks.append(check(run_id, year, "profit_before_tax_tie", "profit_and_loss", values["profit_before_joint_venture"] + values["share_of_joint_venture_profit"] - exceptional, values["profit_before_tax"], [pages["income_statement"]]))
        if all(k in values for k in ("profit_before_tax", "tax_expense", "profit_after_tax")):
            checks.append(check(run_id, year, "profit_after_tax_tie", "profit_and_loss", values["profit_before_tax"] - values["tax_expense"], values["profit_after_tax"], [pages["income_statement"]]))
        if all(k in values for k in ("operating_cash_flow", "investing_cash_flow", "financing_cash_flow", "net_cash_change")):
            checks.append(check(run_id, year, "cash_flow_tie", "cash_flow", values["operating_cash_flow"] + values["investing_cash_flow"] + values["financing_cash_flow"], values["net_cash_change"], [pages["cash_flow"]]))
        if all(k in values for k in ("opening_cash", "net_cash_change", "closing_cash")):
            checks.append(check(run_id, year, "cash_rollforward_tie", "cash_flow", values["opening_cash"] + values["net_cash_change"] + values.get("cash_acquired", Decimal(0)) + values.get("exchange_effect_cash", Decimal(0)), values["closing_cash"], [pages["cash_flow"]]))
        complete = not missing and checks and all(checks)
        status = "validated" if complete else "blocked"
        if not complete:
            failures.append(f"FY{year}: missing={missing}, checks={checks}")
        psql_text(f"UPDATE research.financial_production_runs SET status={sql_literal(status)},completed_at=now(),summary={sql_jsonb({'source_fiscal_year': report_fy, 'selected_side': side, 'facts': len(available), 'missing_mandatory': missing, 'checks_passed': sum(1 for x in checks if x), 'checks_total': len(checks), 'human_reviewed': False})} WHERE id={run_id}")
    # Ratios are created only from years whose source run validated.
    for year in sorted(year_runs):
        run_id = year_runs[year]; values = year_values[year]; ids = year_fact_ids[year]
        status = psql_json(f"SELECT status FROM research.financial_production_runs WHERE id={run_id}")[0]["status"]
        if status != "validated":
            continue
        revenue = values["revenue_from_operations"]; pat = values["profit_after_tax"]
        ebit = values["profit_before_joint_venture"] + values["finance_cost"]
        ebitda = ebit + values["depreciation_amortisation"]
        capex = abs(values.get("capital_expenditure", Decimal(0)))
        fcf = values["operating_cash_flow"] - capex
        persist_ratio(run_id, year, "ebitda_margin", "EBITDA margin", "(profit before JV + finance cost + D&A) / revenue", "percent", ebitda / revenue * 100, {k: ids[k] for k in ("profit_before_joint_venture", "finance_cost", "depreciation_amortisation", "revenue_from_operations")})
        persist_ratio(run_id, year, "pat_margin", "PAT margin", "profit after tax / revenue", "percent", pat / revenue * 100, {k: ids[k] for k in ("profit_after_tax", "revenue_from_operations")})
        persist_ratio(run_id, year, "cfo_pat", "Cash conversion", "operating cash flow / profit after tax", "percent", values["operating_cash_flow"] / pat * 100, {k: ids[k] for k in ("operating_cash_flow", "profit_after_tax")})
        persist_ratio(run_id, year, "fcf_margin", "FCF margin", "(operating cash flow - capex) / revenue", "percent", fcf / revenue * 100, {k: ids[k] for k in ("operating_cash_flow", "capital_expenditure", "revenue_from_operations")})
        persist_ratio(run_id, year, "current_ratio", "Current ratio", "current assets / current liabilities", "ratio", values["total_current_assets"] / values["total_current_liabilities"], {k: ids[k] for k in ("total_current_assets", "total_current_liabilities")})
        debt = values.get("non_current_borrowings", Decimal(0)) + values.get("current_borrowings", Decimal(0))
        persist_ratio(run_id, year, "debt_to_equity", "Debt to equity", "(current + non-current borrowings) / equity", "ratio", debt / values["total_equity"], {k: ids[k] for k in ("non_current_borrowings", "current_borrowings", "total_equity") if k in ids})
        persist_ratio(run_id, year, "interest_coverage", "Interest coverage", "EBIT before JV / finance cost", "ratio", ebit / values["finance_cost"], {k: ids[k] for k in ("profit_before_joint_venture", "finance_cost")})
        persist_ratio(run_id, year, "capex_to_revenue", "Capex / revenue", "absolute capex / revenue", "percent", capex / revenue * 100, {k: ids[k] for k in ("capital_expenditure", "revenue_from_operations")})
        if year - 1 in year_values and "trade_receivables" in year_values[year - 1]:
            persist_ratio(run_id, year, "dso", "Receivable days", "average receivables / revenue * 365", "days", ((values["trade_receivables"] + year_values[year - 1]["trade_receivables"]) / 2) / revenue * 365, {"closing_receivables": ids["trade_receivables"], "opening_receivables": year_fact_ids[year - 1]["trade_receivables"], "revenue": ids["revenue_from_operations"]}, caveats=["Uses current and prior year-end receivables from validated consolidated statements."])
        else:
            persist_ratio(run_id, year, "dso", "Receivable days", "average receivables / revenue * 365", "days", None, {"closing_receivables": ids["trade_receivables"], "revenue": ids["revenue_from_operations"]}, reason="Prior-year receivables are not available in the validated history; average DSO is not computable.")
        if year - 1 in year_values:
            avg_equity = (values["total_equity"] + year_values[year - 1]["total_equity"]) / 2
            persist_ratio(run_id, year, "roe", "Return on equity", "PAT / average equity", "percent", pat / avg_equity * 100, {"pat": ids["profit_after_tax"], "closing_equity": ids["total_equity"], "opening_equity": year_fact_ids[year - 1]["total_equity"]})
            avg_assets = (values["total_assets"] + year_values[year - 1]["total_assets"]) / 2
            persist_ratio(run_id, year, "asset_turnover", "Asset turnover", "revenue / average total assets", "ratio", revenue / avg_assets, {"revenue": ids["revenue_from_operations"], "closing_assets": ids["total_assets"], "opening_assets": year_fact_ids[year - 1]["total_assets"]})
            net_capital = values["total_equity"] + debt - values["cash_and_cash_equivalents"] - values.get("other_bank_balances", Decimal(0))
            prior = year_values[year - 1]
            prior_debt = prior.get("non_current_borrowings", Decimal(0)) + prior.get("current_borrowings", Decimal(0))
            prior_capital = prior["total_equity"] + prior_debt - prior["cash_and_cash_equivalents"] - prior.get("other_bank_balances", Decimal(0))
            persist_ratio(run_id, year, "roce_proxy", "ROCE proxy", "EBIT / average (equity + borrowings - cash - bank balances)", "percent", ebit / ((net_capital + prior_capital) / 2) * 100, {"profit_before_jv": ids["profit_before_joint_venture"], "finance_cost": ids["finance_cost"], "closing_equity": ids["total_equity"], "opening_equity": year_fact_ids[year - 1]["total_equity"]}, caveats=["Transparent capital-employed proxy; not labelled canonical ROIC because full operating invested-capital components are not yet validated."])
    print(json.dumps({"ok": not failures, "years": sorted(year_runs), "validated_years": [y for y,r in year_runs.items() if psql_json(f'SELECT status FROM research.financial_production_runs WHERE id={r}')[0]['status']=='validated'], "facts": sum(len(v) for v in year_fact_ids.values()), "failures": failures}, indent=2, sort_keys=True))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
