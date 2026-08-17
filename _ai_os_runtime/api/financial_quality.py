"""Comparable, source-linked financial quality and capital-efficiency calculations."""

from __future__ import annotations


def canonical_evidence_status(raw):
    value = str(raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    if value in {"human_reviewed", "human_validated", "reviewed", "approved"}:
        return "Human-reviewed"
    if value in {"validated", "machine_validated", "verified"}:
        return "Validated"
    if value in {"machine_extracted", "extracted"}:
        return "Machine-extracted"
    if value in {"parsed", "parse_complete"}:
        return "Parsed"
    if value in {"source_captured", "captured", "registered", "active"}:
        return "Source captured"
    if value in {"stale", "expired"}:
        return "Stale"
    return "Missing"


def build_financial_quality(facts):
    """Build investor metrics without manufacturing unsupported ratios."""
    supported = {
        "revenue_from_operations": "Revenue",
        "ebitda": "EBITDA",
        "earnings_before_interest_and_tax": "EBIT",
        "profit_after_tax": "PAT",
        "operating_cash_flow": "CFO",
        "capital_expenditure": "Capital expenditure",
        "cash_and_cash_equivalents": "Cash and equivalents",
        "current_borrowings": "Current borrowings",
        "non_current_borrowings": "Non-current borrowings",
        "total_equity": "Total equity",
        "inventories": "Inventories",
        "trade_receivables": "Trade receivables",
        "trade_payables": "Trade payables",
        "total_assets": "Total assets",
        "total_liabilities": "Total liabilities",
        "property_plant_and_equipment": "Net PP&E",
        "intangible_assets": "Intangible assets",
        "current_assets": "Current assets",
        "current_liabilities": "Current liabilities",
        "cost_of_goods_sold": "Cost of goods sold",
        "depreciation_and_amortization": "Depreciation and amortization",
        "finance_costs": "Finance costs",
        "tax_expense": "Tax expense",
        "dividends_paid": "Dividends paid",
        "share_buyback": "Share buyback",
    }
    cleaned = [
        row for row in facts
        if row.get("fact_key") in supported
        and row.get("value_numeric") not in (None, "")
        and str(row.get("fiscal_period") or "FY").upper() == "FY"
    ]
    grouped = {}
    for fact in cleaned:
        basis = (
            str(fact.get("statement_scope") or "unknown").lower(),
            str(fact.get("currency") or "unknown").upper(),
            str(fact.get("unit") or "reported").lower(),
        )
        grouped.setdefault(basis, []).append(fact)

    def fact_payload(row):
        if not row:
            return None
        locator = row.get("source_locator") if isinstance(row.get("source_locator"), dict) else {}
        return {
            "kind": "historical_fact",
            "fact_key": row.get("fact_key"),
            "label": supported.get(row.get("fact_key"), row.get("canonical_name")),
            "value": float(row.get("value_numeric")),
            "currency": row.get("currency"),
            "unit": row.get("unit"),
            "fiscal_year": row.get("fiscal_year"),
            "period_start": row.get("period_start"),
            "period_end": row.get("period_end"),
            "statement_scope": row.get("statement_scope"),
            "source_as_of_date": row.get("source_as_of_date"),
            "available_at": row.get("available_at"),
            "verification_status": canonical_evidence_status(row.get("verification_status")),
            "source_name": row.get("source_name"),
            "source_url": row.get("source_url"),
            "evidence_id": row.get("evidence_id"),
            "page_number": locator.get("page_number"),
            "reported_line": locator.get("reported_line"),
            "source_locator": locator,
        }

    def derived(label, formula, inputs, calculation):
        missing = [name for name, payload in inputs.items() if payload is None]
        if missing:
            return {
                "kind": "not_computable", "label": label, "value": None,
                "formula": formula, "missing_inputs": missing, "status": "Not computable",
            }
        try:
            value = calculation({name: payload["value"] for name, payload in inputs.items()})
        except (ArithmeticError, TypeError, ValueError, ZeroDivisionError):
            value = None
        if value is None:
            return {
                "kind": "not_computable", "label": label, "value": None,
                "formula": formula, "missing_inputs": ["consistent non-zero inputs"],
                "status": "Not computable",
            }
        return {
            "kind": "derived_calculation", "label": label, "value": float(value),
            "formula": formula, "inputs": [payload for payload in inputs.values() if payload],
            "status": "Derived",
        }

    basis_groups = []
    for (scope, currency, unit), basis_facts in sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True):
        year_map = {}
        for row in basis_facts:
            year = int(row.get("fiscal_year") or 0)
            if year:
                year_map.setdefault(year, {})[str(row.get("fact_key"))] = fact_payload(row)
        years = sorted(year_map)
        series = []
        for year in years:
            metrics = year_map[year]
            revenue = metrics.get("revenue_from_operations")
            ebitda = metrics.get("ebitda")
            ebit = metrics.get("earnings_before_interest_and_tax")
            pat = metrics.get("profit_after_tax")
            cfo = metrics.get("operating_cash_flow")
            capex = metrics.get("capital_expenditure")
            cash = metrics.get("cash_and_cash_equivalents")
            current_debt = metrics.get("current_borrowings")
            non_current_debt = metrics.get("non_current_borrowings")
            equity = metrics.get("total_equity")
            total_assets = metrics.get("total_assets")
            inventory = metrics.get("inventories")
            receivables = metrics.get("trade_receivables")
            payables = metrics.get("trade_payables")
            current_assets = metrics.get("current_assets")
            current_liabilities = metrics.get("current_liabilities")
            cogs = metrics.get("cost_of_goods_sold")
            depreciation = metrics.get("depreciation_and_amortization")
            finance_costs = metrics.get("finance_costs")
            dividend = metrics.get("dividends_paid")
            buyback = metrics.get("share_buyback")
            prior_equity = year_map.get(year - 1, {}).get("total_equity")
            prior_assets = year_map.get(year - 1, {}).get("total_assets")
            prior_inventory = year_map.get(year - 1, {}).get("inventories")
            prior_receivables = year_map.get(year - 1, {}).get("trade_receivables")
            prior_payables = year_map.get(year - 1, {}).get("trade_payables")
            prior_cash = year_map.get(year - 1, {}).get("cash_and_cash_equivalents")
            prior_current_debt = year_map.get(year - 1, {}).get("current_borrowings")
            prior_non_current_debt = year_map.get(year - 1, {}).get("non_current_borrowings")
            closing_invested_capital = derived(
                "Closing invested capital (financing approach)",
                "equity + current borrowings + non-current borrowings − cash",
                {"equity": equity, "current borrowings": current_debt, "non-current borrowings": non_current_debt, "cash": cash},
                lambda v: v["equity"] + v["current borrowings"] + v["non-current borrowings"] - v["cash"],
            )
            opening_invested_capital = derived(
                "Opening invested capital (financing approach)",
                "opening equity + opening current borrowings + opening non-current borrowings − opening cash",
                {"opening equity": prior_equity, "opening current borrowings": prior_current_debt, "opening non-current borrowings": prior_non_current_debt, "opening cash": prior_cash},
                lambda v: v["opening equity"] + v["opening current borrowings"] + v["opening non-current borrowings"] - v["opening cash"],
            )
            average_invested_capital = derived(
                "Average invested capital", "(opening invested capital + closing invested capital) / 2",
                {"opening invested capital": opening_invested_capital if opening_invested_capital.get("value") is not None else None,
                 "closing invested capital": closing_invested_capital if closing_invested_capital.get("value") is not None else None},
                lambda v: (v["opening invested capital"] + v["closing invested capital"]) / 2,
            )
            net_operating_working_capital = derived(
                "Net operating working capital", "trade receivables + inventories − trade payables",
                {"trade receivables": receivables, "inventories": inventory, "trade payables": payables},
                lambda v: v["trade receivables"] + v["inventories"] - v["trade payables"],
            )
            derived_metrics = {
                "ebitda_margin_pct": derived("EBITDA margin", "EBITDA / revenue × 100", {"ebitda": ebitda, "revenue": revenue}, lambda v: v["ebitda"] / v["revenue"] * 100 if v["revenue"] else None),
                "ebit_margin_pct": derived("EBIT margin", "EBIT / revenue × 100", {"ebit": ebit, "revenue": revenue}, lambda v: v["ebit"] / v["revenue"] * 100 if v["revenue"] else None),
                "pat_margin_pct": derived("PAT margin", "PAT / revenue × 100", {"pat": pat, "revenue": revenue}, lambda v: v["pat"] / v["revenue"] * 100 if v["revenue"] else None),
                "fcf": derived("Free cash flow", "CFO + capital expenditure (capex stored as cash outflow)", {"cfo": cfo, "capex": capex}, lambda v: v["cfo"] + v["capex"]),
                "cfo_pat_conversion_pct": derived("CFO / PAT conversion", "CFO / PAT × 100", {"cfo": cfo, "pat": pat}, lambda v: v["cfo"] / v["pat"] * 100 if v["pat"] else None),
                "net_debt": derived("Net debt / (cash)", "current borrowings + non-current borrowings − cash", {"current borrowings": current_debt, "non-current borrowings": non_current_debt, "cash": cash}, lambda v: v["current borrowings"] + v["non-current borrowings"] - v["cash"]),
                "roe_pct": derived("ROE", "PAT / average opening and closing equity × 100", {"pat": pat, "closing equity": equity, "opening equity": prior_equity}, lambda v: v["pat"] / ((v["closing equity"] + v["opening equity"]) / 2) * 100 if (v["closing equity"] + v["opening equity"]) else None),
                "asset_turnover": derived("Asset turnover", "revenue / average opening and closing total assets", {"revenue": revenue, "closing total assets": total_assets, "opening total assets": prior_assets}, lambda v: v["revenue"] / ((v["closing total assets"] + v["opening total assets"]) / 2) if (v["closing total assets"] + v["opening total assets"]) else None),
                "financial_leverage": derived("Financial leverage", "average total assets / average equity", {"closing total assets": total_assets, "opening total assets": prior_assets, "closing equity": equity, "opening equity": prior_equity}, lambda v: ((v["closing total assets"] + v["opening total assets"]) / 2) / ((v["closing equity"] + v["opening equity"]) / 2) if (v["closing equity"] + v["opening equity"]) else None),
                "dupont_roe_pct": derived("DuPont ROE", "PAT margin × asset turnover × financial leverage", {"PAT": pat, "revenue": revenue, "closing total assets": total_assets, "opening total assets": prior_assets, "closing equity": equity, "opening equity": prior_equity}, lambda v: (v["PAT"] / v["revenue"]) * (v["revenue"] / ((v["closing total assets"] + v["opening total assets"]) / 2)) * (((v["closing total assets"] + v["opening total assets"]) / 2) / ((v["closing equity"] + v["opening equity"]) / 2)) * 100 if v["revenue"] and (v["closing total assets"] + v["opening total assets"]) and (v["closing equity"] + v["opening equity"]) else None),
                "closing_invested_capital": closing_invested_capital,
                "opening_invested_capital": opening_invested_capital,
                "average_invested_capital": average_invested_capital,
                "capital_turnover": derived("Capital turnover", "revenue / average invested capital", {"revenue": revenue, "average invested capital": average_invested_capital if average_invested_capital.get("value") is not None else None}, lambda v: v["revenue"] / v["average invested capital"] if v["average invested capital"] else None),
                "nopat": derived("NOPAT", "EBIT × (1 − normalized operating tax rate)", {"EBIT": ebit, "normalized operating tax rate": None}, lambda _v: None),
                "roce_pct": derived("ROCE", "EBIT / average invested capital × 100", {"EBIT": ebit, "average invested capital": average_invested_capital if average_invested_capital.get("value") is not None else None}, lambda v: v["EBIT"] / v["average invested capital"] * 100 if v["average invested capital"] else None),
                "roic_pct": derived("ROIC", "NOPAT / average invested capital × 100", {"NOPAT": None, "average invested capital": average_invested_capital if average_invested_capital.get("value") is not None else None}, lambda _v: None),
                "net_operating_working_capital": net_operating_working_capital,
                "working_capital_days": derived("Working-capital days", "Average operating working capital / comparable annual revenue × 365", {"comparable working capital": None, "revenue": revenue}, lambda _v: None),
                "dso_days": derived("Days sales outstanding", "average trade receivables / revenue × 365", {"closing receivables": receivables, "opening receivables": prior_receivables, "revenue": revenue}, lambda v: ((v["closing receivables"] + v["opening receivables"]) / 2) / v["revenue"] * 365 if v["revenue"] else None),
                "dio_days": derived("Days inventory outstanding", "average inventory / cost of goods sold × 365", {"closing inventory": inventory, "opening inventory": prior_inventory, "cost of goods sold": cogs}, lambda v: ((v["closing inventory"] + v["opening inventory"]) / 2) / v["cost of goods sold"] * 365 if v["cost of goods sold"] else None),
                "dpo_days": derived("Days payable outstanding", "average trade payables / cost of goods sold × 365", {"closing payables": payables, "opening payables": prior_payables, "cost of goods sold": cogs}, lambda v: ((v["closing payables"] + v["opening payables"]) / 2) / v["cost of goods sold"] * 365 if v["cost of goods sold"] else None),
                "capex_reinvestment_pct": derived("Capex / revenue", "absolute capital expenditure / revenue × 100", {"capex": capex, "revenue": revenue}, lambda v: abs(v["capex"]) / v["revenue"] * 100 if v["revenue"] else None),
                "capex_depreciation": derived("Capex / depreciation", "absolute capital expenditure / depreciation and amortization", {"capex": capex, "depreciation and amortization": depreciation}, lambda v: abs(v["capex"]) / v["depreciation and amortization"] if v["depreciation and amortization"] else None),
                "reinvestment_rate": derived("Reinvestment rate", "(net capex + change in operating working capital) / NOPAT", {"net capex": None, "change in operating working capital": None, "NOPAT": None}, lambda _v: None),
                "interest_coverage": derived("Interest coverage", "EBIT / finance costs", {"EBIT": ebit, "finance costs": finance_costs}, lambda v: v["EBIT"] / abs(v["finance costs"]) if v["finance costs"] else None),
                "current_ratio": derived("Current ratio", "current assets / current liabilities", {"current assets": current_assets, "current liabilities": current_liabilities}, lambda v: v["current assets"] / v["current liabilities"] if v["current liabilities"] else None),
                "dividend_payout_pct": derived("Dividend / PAT", "absolute dividends paid / PAT × 100", {"dividend": dividend, "pat": pat}, lambda v: abs(v["dividend"]) / v["pat"] * 100 if v["pat"] else None),
                "buyback": buyback or {"kind": "not_computable", "label": "Share buyback", "value": None, "formula": "As reported", "missing_inputs": ["share buyback disclosure"], "status": "Not available"},
            }
            series.append({
                "fiscal_year": year,
                "period_start": next((item.get("period_start") for item in metrics.values() if item.get("period_start")), None),
                "period_end": next((item.get("period_end") for item in metrics.values() if item.get("period_end")), None),
                "source_as_of_date": max((str(item.get("source_as_of_date")) for item in metrics.values() if item.get("source_as_of_date")), default=None),
                "verification_status": min((item.get("verification_status") for item in metrics.values()), default="Missing"),
                "metrics": metrics,
                "derived": derived_metrics,
            })

        latest_year = years[-1] if years else None
        latest = year_map.get(latest_year, {}) if latest_year else {}
        cagr = {}
        for key, label in (("revenue_from_operations", "Revenue CAGR"), ("profit_after_tax", "PAT CAGR")):
            available = [(year, year_map[year].get(key)) for year in years if year_map[year].get(key)]
            window = available[-6:]
            if len(window) >= 2 and window[0][1]["value"] > 0 and window[-1][1]["value"] > 0:
                periods = window[-1][0] - window[0][0]
                cagr[key] = derived(
                    label,
                    f"(FY{window[-1][0]} / FY{window[0][0]}) ^ (1 / {periods}) − 1",
                    {f"FY{window[0][0]}": window[0][1], f"FY{window[-1][0]}": window[-1][1]},
                    lambda v, p=periods: ((list(v.values())[-1] / list(v.values())[0]) ** (1 / p) - 1) * 100 if p > 0 else None,
                )
            else:
                cagr[key] = {"kind": "not_computable", "label": label, "value": None, "formula": "Comparable positive endpoints required", "missing_inputs": ["comparable endpoint history"], "status": "Not computable"}
        basis_groups.append({
            "basis_key": f"{scope}:{currency}:{unit}:FY",
            "basis_label": f"As reported · {scope.title()} · {currency} {unit} · annual",
            "statement_scope": scope,
            "currency": currency,
            "unit": unit,
            "fiscal_period": "FY",
            "years": years,
            "latest_fiscal_year": latest_year,
            "latest_source_as_of_date": max((str(item.get("source_as_of_date")) for item in latest.values() if item.get("source_as_of_date")), default=None),
            "verification_status": canonical_evidence_status(next((item.get("verification_status") for item in latest.values() if item.get("verification_status")), None)),
            "series": series,
            "cagr": cagr,
            "incremental_returns": [
                {
                    "label": f"Incremental ROCE ({window}y)",
                    "window_years": window,
                    "start_year": (latest_year - window) if latest_year else None,
                    "end_year": latest_year,
                    "kind": "not_computable",
                    "value": None,
                    "status": "Not computable",
                    "formula": "change in EBIT / change in invested capital × 100 over a consistent scope and basis",
                    "missing_inputs": ["comparable EBIT endpoints", "comparable invested-capital endpoints"],
                }
                for window in (3, 5, 10)
            ],
            "capital_efficiency_policy": {
                "roce_definition": "EBIT / average invested capital",
                "roic_definition": "NOPAT / average invested capital",
                "invested_capital_definition": "equity + interest-bearing borrowings − cash (financing approach)",
                "operating_reconciliation": "Net working capital + net PP&E + intangibles + other net operating assets; unavailable until every disclosed component is captured.",
                "capital_basis": "Average opening and closing capital; closing capital is shown separately.",
                "maintenance_growth_capex": "Not classified unless company disclosure explicitly separates maintenance and growth capex.",
                "wacc_comparison": "Withheld until an explicit WACC or hurdle is user-reviewed.",
            },
        })

    return {
        "status": "available" if basis_groups else "missing",
        "basis_mode": "as_reported_with_explicit_derived_metrics",
        "basis_groups": basis_groups,
        "available_scopes": sorted({group["statement_scope"] for group in basis_groups}),
        "available_units": sorted({group["unit"] for group in basis_groups}),
        "available_currencies": sorted({group["currency"] for group in basis_groups}),
        "coverage_note": "Historical facts retain their reported basis. Derived metrics are calculated only within one comparable scope, currency, unit and annual period.",
        "missing_value_policy": "Missing or inconsistent inputs render as Not computable; zero is never substituted.",
    }
