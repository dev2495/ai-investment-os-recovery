from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "postgres" / "init" / "206_sector_acceptance_v2.sql"
API = ROOT / "api" / "ai_os_api_server.py"
MCP = ROOT / "mcp_server" / "ai_os_mcp_server.py"


def test_v2_requires_real_constituent_coverage_and_history() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "run_acceptance_gates_v2" in sql
    assert "v_active_count*0.70" in sql
    assert "count(DISTINCT metric_key)=3" in sql
    assert "reported_revenue" in sql
    assert "reported_profit_after_tax" in sql
    assert "reported_basic_eps" in sql
    assert "price_to_earnings" in sql
    assert "lookback_years>=10" in sql
    assert "observation_count>=2000" in sql
    assert "backdating_allowed',false" in sql


def test_api_and_mcp_expose_publisher_without_execution_authority() -> None:
    api = API.read_text(encoding="utf-8")
    mcp = MCP.read_text(encoding="utf-8")
    assert "def sync_sector_fundamentals" in api
    assert '"/api/sector-intelligence/fundamentals/sync"' in api
    assert "run_acceptance_gates_v2" in api
    assert '"ai_os_sync_sector_fundamentals"' in mcp
    assert "broker_write_allowed" in mcp
    assert "capital_action_allowed" in mcp
