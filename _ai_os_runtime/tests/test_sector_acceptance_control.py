from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "postgres" / "init" / "190_sector_acceptance_control_v1.sql"


def sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_real_sector_acceptance_is_durable_and_replay_safe() -> None:
    source = sql()
    assert "sector_intelligence.acceptance_runs" in source
    assert "sector_intelligence.acceptance_gate_results" in source
    assert "sector_intelligence.run_acceptance_gates" in source
    assert "ON CONFLICT (taxonomy_node_id,as_of_date,gate_version)" in source
    assert "DELETE FROM sector_intelligence.acceptance_gate_results" in source
    assert "sector_intelligence.v_acceptance_gate_summary" in source


def test_all_institutional_sector_acceptance_gates_are_explicit() -> None:
    source = sql()
    for gate_key in (
        "effective_memberships",
        "two_weighting_methods",
        "reconciled_index_history",
        "fundamental_valuation_breadth",
        "relative_strength_breadth",
        "flows_and_ownership",
        "sector_dossier",
        "committee_dissent",
        "portfolio_fit",
        "tradingview_handoff",
    ):
        assert f"('{gate_key}'" in source


def test_acceptance_rejects_lineage_free_nodes_and_never_enables_execution() -> None:
    normalized = " ".join(sql().lower().split())
    assert "lacks source lineage" in normalized
    assert "broker_write_allowed boolean not null default false check (broker_write_allowed=false)" in normalized
    assert "capital_action_allowed=false" in normalized
    assert "insert into trading.orders" not in normalized
    assert "insert into broker" not in normalized


def test_tradingview_is_only_a_native_desktop_artifact_gate() -> None:
    source = sql()
    assert "artifact.target_workspace='tradingview_desktop'" in source
    assert "artifact.source_state_fingerprint" in source
    assert "tradingview_authoritative" not in source


def test_acceptance_is_exposed_to_workers_api_and_frontend() -> None:
    api = (ROOT / "api" / "ai_os_api_server.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts" / "run_agent_worker_once.py").read_text(encoding="utf-8")
    schema = (ROOT / "ai-office-ui" / "src" / "data" / "schemas.ts").read_text(encoding="utf-8")
    page = (ROOT / "ai-office-ui" / "src" / "destinations" / "sector" / "SectorIntelligence.tsx").read_text(encoding="utf-8")
    assert '"acceptance_runs"' in api
    assert '"sector_acceptance"' in api
    assert '"acceptance"' in worker
    assert "acceptance_runs" in schema
    assert "Real-Sector Acceptance" in page
    assert "Acceptance has not been executed" in page
    assert "def run_sector_acceptance" in api
    assert '"/api/sector-intelligence/acceptance/run"' in api
    assert "useRunSectorAcceptance" in page


def test_acceptance_is_exposed_as_a_bounded_mcp_tool() -> None:
    mcp = (ROOT / "mcp_server" / "ai_os_mcp_server.py").read_text(encoding="utf-8")
    assert "def run_sector_acceptance" in mcp
    assert '"ai_os_run_sector_acceptance"' in mcp
    assert '"capital_action_allowed"] = False' in mcp
    assert '"broker_write_allowed"] = False' in mcp
