import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
from valuation_workbench import build_valuation_workbench


def _history():
    return [{"fiscal_year": 2026, "facts": [
        {"fact_key": "profit_after_tax", "value": 1000, "unit": "lakh", "extraction_status": "validated", "source_url": "https://issuer.example/ar.pdf", "source_page": 80},
        {"fact_key": "basic_eps", "value": 10, "unit": "INR/share", "extraction_status": "validated", "source_url": "https://issuer.example/ar.pdf", "source_page": 81},
        {"fact_key": "cash_and_cash_equivalents", "value": 200, "unit": "lakh"},
        {"fact_key": "current_borrowings", "value": 500, "unit": "lakh"},
    ]}]


def test_missing_models_never_create_fair_value():
    selected = {"symbol": "TEST", "exchange": "NSE", "legal_name": "Test Limited", "research_pack": {}}
    result = build_valuation_workbench(selected, {"financial_history": _history(), "financial_validation_checks": []})
    assert all(method["status"] == "blocked" for method in result["methods"])
    assert all(method["bear"] is None and method["base"] is None and method["bull"] is None for method in result["methods"])
    assert result["review"]["capital_action_allowed"] is False
    assert result["share_basis"]["shares_crore"] == 1.0


def test_calculated_model_remains_unreviewed_and_stale_price_blocks_decision():
    selected = {"symbol": "TEST", "exchange": "NSE", "legal_name": "Test Limited", "research_pack": {}}
    model = {"id": 1, "model_type": "dcf", "status": "complete", "fair_value_low": 80, "fair_value_base": 100, "fair_value_high": 130,
             "assumptions": {"current_price": 90, "current_price_source": {"price": 90, "provider": "Read-only feed", "quote_ts": "2020-01-01T00:00:00+00:00"},
                             "fcf_history": [{"fiscal_year": 2024}, {"fiscal_year": 2025}, {"fiscal_year": 2026}],
                             "scenarios": {"base": {"discount": .12, "terminal_growth": .04}}},
             "outputs": {}, "updated_at": "2026-08-17T00:00:00+00:00"}
    result = build_valuation_workbench(selected, {"financial_history": _history(), "valuation_models": [model], "financial_validation_checks": []})
    dcf = next(method for method in result["methods"] if method["key"] == "dcf")
    assert dcf["status"] == "calculated_unreviewed"
    assert dcf["decision_usable"] is False
    assert any(blocker["key"] == "market_price" for blocker in result["blockers"])
    assert any(blocker["key"] == "human_review" for blocker in result["blockers"])


def test_agent_draft_price_is_visible_but_unverified():
    selected = {"symbol": "TEST", "exchange": "NSE", "legal_name": "Test Limited", "research_pack": {"forecasts_valuation": {"summary": "Current market price is available at INR 1,027.75.", "citation_ids": ["market:x"]}}}
    result = build_valuation_workbench(selected, {"financial_history": _history(), "financial_validation_checks": []})
    assert result["current_price"]["value"] == 1027.75
    assert result["current_price"]["verification_status"] == "captured_unverified"
    assert any(blocker["key"] == "market_price" for blocker in result["blockers"])
