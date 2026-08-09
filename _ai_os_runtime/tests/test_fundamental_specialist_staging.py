from datetime import datetime, timezone

from stage_fundamental_specialist_opinions import build_opinions, load_context


class CapturingGateway:
    def __init__(self) -> None:
        self.sql = ""

    def _run_json(self, sql: str) -> dict:
        self.sql = sql
        return {}


def test_context_uses_canonical_active_book_position_status() -> None:
    gateway = CapturingGateway()

    load_context(gateway, "USHAMART", "NSE", datetime(2026, 8, 8, tzinfo=timezone.utc))

    assert "position.status='active'" in gateway.sql
    assert "position.status='open'" not in gateway.sql


def test_staging_preserves_drafts_dissent_and_execution_guardrails() -> None:
    context = {
        "company": {"id": 43, "primary_symbol": "USHAMART"},
        "dossier": {"dossier_version_id": 4, "holding_thesis_id": 2},
        "evidence": [
            {"id": 21, "source_type": "corporate_filing", "source_title": "Annual Report FY 2025-26"},
            {"id": 29, "source_type": "operating_peer_primary_source", "source_title": "NSE peer filing"},
        ],
        "fact_coverage": {"revenue_from_operations": 15, "profit_after_tax": 10, "operating_cash_flow": 15, "total_assets": 13, "capital_expenditure": 9, "dividends_paid": 7},
        "operational_kpis": 5, "segments": 1, "segment_years": 5,
        "market_share_series": 0, "peers": 2, "communications": 12,
        "claims": 3, "claim_outcomes": 1, "position_rows": 2, "client_count": 2,
        "gross_exposure": 1_899_270, "valuation_complete": 0, "monte_carlo_complete": 0,
        "valuation_types": [],
        "governance_forensic": {"count": 8, "categories": 6, "active_issues": 2, "high_severity": 3, "evidence_id": 21},
        "industry_observations": {"count": 5, "categories": 5, "quantified": 1, "market_share_not_disclosed": 1, "evidence_id": 21},
        "portfolio_fit_context": {"risk_limit_clients": 2, "breaches": 1, "warnings": 0, "suitable_clients": 0},
    }
    rows = build_opinions(context, datetime(2026, 8, 8, tzinfo=timezone.utc))
    by_key = {row["specialist_key"]: row for row in rows}

    assert len(rows) == 12
    assert by_key["financial_quality"]["opinion_status"] == "evidence_complete"
    assert by_key["governance"]["opinion_status"] == "evidence_complete"
    assert by_key["forensic_accounting"]["opinion_status"] == "evidence_complete"
    assert by_key["industry"]["opinion_status"] == "evidence_complete"
    assert by_key["moat"]["opinion_status"] == "evidence_complete"
    assert by_key["portfolio_fit"]["opinion_status"] == "evidence_complete"
    assert "No add or sizing action is supportable" in by_key["portfolio_fit"]["conclusion"]
    assert "not a clean-company clearance" in by_key["governance"]["conclusion"]
    assert by_key["bear_case"]["opinion_status"] == "dissent"
    assert "numeric market share remains unavailable" in by_key["moat"]["conclusion"]
    assert all(row["disconfirming_evidence"] for row in rows)
    assert all(row["evidence_id"] in {21, 29} for row in rows)


def test_valuation_lane_completes_only_with_all_calculation_families() -> None:
    context = {
        "company": {"id": 43, "primary_symbol": "USHAMART"},
        "dossier": {"dossier_version_id": 4, "holding_thesis_id": 2},
        "evidence": [{"id": 21, "source_type": "corporate_filing", "source_title": "Annual Report FY 2025-26"}],
        "fact_coverage": {}, "valuation_complete": 3,
        "valuation_types": ["dcf", "reverse_dcf", "multiples"], "monte_carlo_complete": 1,
    }
    rows = build_opinions(context, datetime(2026, 8, 8, tzinfo=timezone.utc))
    valuation = next(row for row in rows if row["specialist_key"] == "valuation")
    assert valuation["opinion_status"] == "evidence_complete"
    assert "operator reviewed" in valuation["conclusion"]
