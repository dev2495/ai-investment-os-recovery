"""Company-agnostic, conservative valuation read model.

Only persisted calculations and validated statement inputs are projected. This
module never creates a forecast, multiple, probability, fair value, or review.
"""
from __future__ import annotations

from datetime import datetime, timezone

from market_price_resolver import resolve_market_price

CALCULATED = {"complete", "validated", "human_reviewed", "approved"}
REVIEWED = {"human_reviewed", "approved"}


def _num(value):
    try:
        value = float(value)
        return value if value == value else None
    except (TypeError, ValueError):
        return None


def _age(raw):
    try:
        stamp = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(timezone.utc) - stamp).days)
    except (TypeError, ValueError):
        return None


def _latest_facts(history):
    if not history:
        return {}, None
    row = max(history, key=lambda item: int(item.get("fiscal_year") or 0))
    return {str(f.get("fact_key") or ""): f for f in row.get("facts") or []}, row.get("fiscal_year")


def _fact(facts, *keys):
    return next((facts[key] for key in keys if key in facts and _num(facts[key].get("value")) is not None), None)


def _price(models, selected, data):
    warehouse = resolve_market_price(
        data.get("market_price_anchor") or [],
        symbol=str(selected.get("symbol") or ""),
        exchange=str(selected.get("exchange") or "NSE"),
        holidays=data.get("market_holidays") or [],
    )
    if warehouse:
        return warehouse
    anchors = []
    for model in models:
        assumptions = model.get("assumptions") if isinstance(model.get("assumptions"), dict) else {}
        source = assumptions.get("current_price_source") if isinstance(assumptions.get("current_price_source"), dict) else {}
        value = _num(assumptions.get("current_price")) or _num(source.get("price"))
        if value is None:
            continue
        as_of = source.get("quote_ts") or source.get("as_of") or source.get("captured_at")
        anchors.append({"value": value, "currency": "INR", "as_of": as_of,
                        "age_days": _age(as_of), "provider": source.get("provider") or source.get("source_key") or "Persisted model input",
                        "provider_symbol": source.get("provider_symbol") or source.get("symbol"), "source": source,
                        "source_class": "persisted_model_input", "verification_status": "source_linked" if as_of and source else "captured_unverified",
                        "freshness_status": "stale", "decision_usable": False, "broker_write_allowed": False,
                        "freshness_reason": "persisted model input is retained for lineage only; refresh the canonical read-only quote"})
    if anchors:
        anchors.sort(key=lambda row: str(row.get("as_of") or ""), reverse=True)
        return anchors[0]
    return None


def build_valuation_workbench(selected, data):
    models = data.get("valuation_models") or []
    history = data.get("financial_history") or []
    checks = data.get("financial_validation_checks") or []
    peers = data.get("operating_peers") or []
    segments = data.get("financial_segment_history") or data.get("segment_facts") or []
    facts, fiscal_year = _latest_facts(history)
    price = _price(models, selected, data)

    pat = _fact(facts, "profit_after_tax", "pat_continuing", "pat_total")
    eps = _fact(facts, "basic_eps", "eps_basic_continuing", "eps_basic_total")
    shares = _fact(facts, "shares_outstanding", "diluted_shares", "basic_shares")
    share_basis = None
    if shares:
        raw = _num(shares.get("value"))
        share_basis = {"shares": raw, "shares_crore": raw / 10_000_000 if raw and raw > 1_000_000 else raw,
                       "method": "issuer-reported shares outstanding", "status": str(shares.get("extraction_status") or "validated"),
                       "source_url": shares.get("source_url"), "source_page": shares.get("source_page"), "period": fiscal_year}
    elif pat and eps and _num(eps.get("value")):
        share_basis = {"shares": None, "shares_crore": _num(pat.get("value")) / _num(eps.get("value")) / 100,
                       "method": "validated PAT (INR lakh) / issuer-reported basic EPS / 100", "status": "derived_reproducible",
                       "source_url": pat.get("source_url") or eps.get("source_url"),
                       "source_page": [pat.get("source_page"), eps.get("source_page")], "period": fiscal_year}

    cash_fact = _fact(facts, "cash", "cash_and_cash_equivalents")
    other_bank_fact = _fact(facts, "other_bank_balances")
    total_debt_fact = _fact(facts, "total_borrowings", "total_debt")
    current_debt_fact = _fact(facts, "current_borrowings")
    non_current_debt_fact = _fact(facts, "non_current_borrowings")
    cash_value = _num((cash_fact or {}).get("value"))
    other_bank_value = _num((other_bank_fact or {}).get("value"))
    if total_debt_fact:
        debt_value = _num(total_debt_fact.get("value"))
        debt_basis = "issuer_reported_total"
    elif current_debt_fact and non_current_debt_fact:
        debt_value = _num(current_debt_fact.get("value")) + _num(non_current_debt_fact.get("value"))
        debt_basis = "current_plus_non_current"
    else:
        debt_value = None
        debt_basis = "incomplete"
    missing_components = []
    if cash_value is None:
        missing_components.append("cash_and_cash_equivalents")
    if other_bank_value is None:
        missing_components.append("other_bank_balances")
    if debt_value is None:
        if current_debt_fact is None:
            missing_components.append("current_borrowings")
        if non_current_debt_fact is None:
            missing_components.append("non_current_borrowings")
    complete_cash = cash_value is not None and other_bank_value is not None
    net_debt = debt_value - cash_value - other_bank_value if debt_value is not None and complete_cash else None
    equity_bridge = {
        "cash_crore": cash_value / 100 if cash_value is not None else None,
        "other_bank_balances_crore": other_bank_value / 100 if other_bank_value is not None else None,
        "debt_crore": debt_value / 100 if debt_value is not None else None,
        "net_debt_crore": net_debt / 100 if net_debt is not None else None,
        "period": fiscal_year, "debt_basis": debt_basis,
        "missing_components": missing_components,
        "status": "validated_actual" if net_debt is not None else "partial" if any((cash_fact, other_bank_fact, total_debt_fact, current_debt_fact, non_current_debt_fact)) else "missing",
    }

    by_type = {}
    for model in models:
        by_type.setdefault(str(model.get("model_type") or "unknown").lower(), model)
    specs = [
        ("dcf", "DCF", "What normalized free cash flow is worth under explicit forecast, WACC and terminal assumptions."),
        ("reverse_dcf", "Reverse DCF", "What operating growth the current price requires; not a target price."),
        ("multiples", "Earnings multiple", "Subject-company earnings sensitivity unless compatible peer metrics are linked."),
        ("historical_multiple", "Historical range", "Where the security trades versus its own comparable history."),
        ("relative_valuation", "Peer comparison", "Premium or discount to compatible peers on aligned periods and definitions."),
        ("sotp", "SOTP", "Segment valuation only when segment profit, capital and a valid method are disclosed."),
    ]
    methods = []
    for key, label, meaning in specs:
        model = by_type.get(key)
        state = str((model or {}).get("status") or "missing").lower()
        calculated = bool(model and state in CALCULATED and any(_num(model.get(field)) is not None for field in ("fair_value_low", "fair_value_base", "fair_value_high")))
        reviewed = state in REVIEWED
        methods.append({"key": key, "label": label, "meaning": meaning,
                        "status": "human_reviewed" if reviewed else "calculated_unreviewed" if calculated else "blocked",
                        "model_id": model.get("id") if model else None, "as_of": model.get("updated_at") if model else None,
                        "bear": _num(model.get("fair_value_low")) if calculated else None,
                        "base": _num(model.get("fair_value_base")) if calculated else None,
                        "bull": _num(model.get("fair_value_high")) if calculated else None,
                        "expected_cagr_pct": _num(model.get("expected_cagr_pct")) if calculated else None,
                        "assumptions": model.get("assumptions") if model else {}, "outputs": model.get("outputs") if model else {},
                        "owner": model.get("owner_agent") if model else "Valuation Agent",
                        "decision_usable": reviewed and bool(price) and price.get("decision_usable") is True})

    dcf = by_type.get("dcf") or {}
    assumptions = dcf.get("assumptions") if isinstance(dcf.get("assumptions"), dict) else {}
    fcf_history = assumptions.get("fcf_history") if isinstance(assumptions.get("fcf_history"), list) else []
    scenarios = assumptions.get("scenarios") if isinstance(assumptions.get("scenarios"), dict) else {}
    wacc = any(_num(assumptions.get(key)) is not None for key in ("wacc", "discount_rate")) or any(isinstance(case, dict) and _num(case.get("discount")) is not None for case in scenarios.values())
    terminal = _num(assumptions.get("terminal_growth")) is not None or any(isinstance(case, dict) and _num(case.get("terminal_growth")) is not None for case in scenarios.values())
    dcf_state = next(method for method in methods if method["key"] == "dcf")
    blockers = []
    def block(key, title, reason, repair, priority="required"):
        blockers.append({"key": key, "title": title, "reason": reason, "repair": repair, "priority": priority})
    if not price:
        block("market_price", "Current market price missing", "No source-linked market price and timestamp is persisted.", "Refresh the read-only quote, then rerun valuation preflight.")
    elif price.get("decision_usable") is not True or price.get("freshness_status") != "current" or price.get("verification_status") != "source_linked":
        block("market_price", "Market price is stale or unverified", f"The only anchor is {price.get('provider')} as of {price.get('as_of') or 'an unknown time'}.", "Refresh the read-only quote and preserve provider, symbol and timestamp.")
    if not share_basis:
        block("share_basis", "Per-share basis missing", "Neither validated shares nor a reproducible PAT/EPS bridge is available.", "Validate share count, dilution and split/restatement history.")
    if len(fcf_history) < 3:
        block("cash_flow_base", "Normalized cash-flow base missing", "Fewer than three source-linked FCF observations are stored in the DCF snapshot.", "Build and validate CFO minus capex history; explain normalization and one-offs.")
    if not wacc:
        block("discount_rate", "Discount rate/WACC missing", "No explicit discount-rate input exists in the persisted DCF.", "Persist risk-free rate, ERP, beta, cost of debt, tax rate and capital weights for review.")
    if not terminal:
        block("terminal_value", "Terminal assumptions missing", "No explicit terminal-growth or exit-multiple assumption exists.", "Persist a terminal method and sensitivity with economic rationale.")
    if dcf_state["status"] != "human_reviewed":
        block("human_review", "DCF is not human-reviewed", "Calculated values remain analyst scenarios and cannot support a capital decision.", "Review cash-flow base, forecast path, equity bridge and sensitivity; approve or return with rationale.")
    if not peers:
        block("peer_universe", "Compatible peer universe missing", "No source-linked operating-peer set is available.", "Define core, secondary and excluded peers with inclusion rationale.", "enrichment")
    block("peer_metrics", "Comparable peer metrics not validated", "Operating-peer names alone are not valuation comparables; aligned prices, periods and definitions are absent.", "Normalize peer growth, margin, return and valuation metrics before showing a premium/discount.", "enrichment")
    if not segments:
        block("sotp", "SOTP inputs unavailable", "No segment profit/capital schedule supports independent segment valuation.", "Validate segment revenue, profit, capital employed and reconciliation before enabling SOTP.", "optional")

    monte = (data.get("monte_carlo_runs") or [None])[0]
    valid_checks = sum(1 for row in checks if str(row.get("check_status") or row.get("status") or "").lower() in {"pass", "passed", "validated"})
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "company": {"symbol": selected.get("symbol"), "exchange": selected.get("exchange"), "name": selected.get("legal_name") or selected.get("company_name")},
        "classification": {"historical": "validated_actual", "guidance": "management_guidance", "external_estimates": "not_available", "model_outputs": "scenario_not_fact"},
        "current_price": price, "share_basis": share_basis, "equity_bridge": equity_bridge,
        "actuals": {"fiscal_year_start": min((int(row.get("fiscal_year") or 0) for row in history), default=None), "fiscal_year_end": fiscal_year,
                    "years": len(history), "validation_checks_passed": valid_checks, "validation_checks_total": len(checks)},
        "guidance_count": len(data.get("management_guidance") or []), "external_estimate_count": 0,
        "peer_universe_count": len(peers), "methods": methods,
        "scenario_count": sum(1 for method in methods if method["status"] != "blocked"),
        "monte_carlo": {"status": "withheld", "reason": "A legacy distribution exists, but its method is not aligned to the DCF and has not passed human replay review." if monte else "No replayable DCF-basis distribution is stored.",
                        "legacy_run_id": monte.get("id") if monte else None, "simulation_count": monte.get("simulation_count") if monte else None},
        "blockers": blockers,
        "review": {"status": "review_required", "capital_action_allowed": False, "broker_write_allowed": False,
                   "next_action": blockers[0]["repair"] if blockers else "Record an explicit human valuation review."},
    }
