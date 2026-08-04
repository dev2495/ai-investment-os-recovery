from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "postgres" / "init" / "189_sector_options_operating_team_v1.sql"
WORKER = ROOT / "scripts" / "run_agent_worker_once.py"
OFFICE_LAYOUT = ROOT / "ai-office-ui" / "src" / "office3d" / "officeLayout.ts"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_sector_and_options_control_team_is_explicitly_registered() -> None:
    sql = read(MIGRATION)
    for contract in (
        "Sector Intelligence Office",
        "Sector Portfolio Manager",
        "Sector Fundamental Analyst",
        "Sector Market Structure Analyst",
        "Sector Flow And Ownership Analyst",
        "Sector Data Steward",
        "Options Data Quality Agent",
        "sector_portfolio_management",
        "sector_fundamental_review",
        "sector_market_structure_review",
        "sector_flow_ownership_review",
        "sector_data_quality_control",
        "options_data_quality_control",
    ):
        assert contract in sql


def test_operating_team_has_hierarchy_mailboxes_personas_and_model_routes() -> None:
    sql = read(MIGRATION)
    for contract in (
        "agent.org_hierarchy",
        "agent.agent_skill_map",
        "activation_rules",
        "agent.mailboxes",
        "agent.agent_characters",
        "agent.agent_model_assignments",
        "Speak in first person. Facts and event time first.",
        "local_first_cloud_only_after_human_approval",
    ):
        assert contract in sql


def test_operating_team_cannot_seed_or_execute_trades() -> None:
    normalized = " ".join(read(MIGRATION).lower().split())
    assert '\"seed_data_allowed\":false' in normalized
    assert '\"broker_order_allowed\":false' in normalized
    assert '\"human_approval_for_capital\":true' in normalized
    assert '\"tradingview_role\":\"artifact_consumer_only\"' in normalized
    assert "insert into trading.orders" not in normalized


def test_worker_retrieves_role_scoped_institutional_evidence() -> None:
    source = read(WORKER)
    for contract in (
        'skill_key.startswith("sector_")',
        'base["sector_intelligence"]',
        "sector_intelligence.v_sector_data_freshness",
        "sector_intelligence.v_custom_index_control",
        'base["institutional_options"]',
        "trading.v_option_analytics_readiness",
        'base["fundamental_factory"]',
        "research.v_company_fundamental_coverage",
    ):
        assert contract in source


def test_live_office_has_a_sector_intelligence_room() -> None:
    source = read(OFFICE_LAYOUT)
    assert 'room("sector"' in source
    assert '"Sector Intelligence"' in source
    assert '"/sector/overview"' in source
