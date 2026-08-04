from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "postgres" / "init" / "191_options_acceptance_evaluator_v1.sql"


def sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_options_acceptance_evaluator_is_replay_safe_and_durable() -> None:
    source = sql()
    assert "trading.run_option_acceptance_gates" in source
    assert "ON CONFLICT (run_key) DO UPDATE" in source
    assert "DELETE FROM trading.option_acceptance_gate_results" in source
    assert "trading.option_acceptance_gate_runs" in source
    assert "trading.option_acceptance_gate_results" in source


def test_options_acceptance_covers_full_institutional_contract() -> None:
    source = sql()
    for gate in (
        "multi_minute_capture",
        "contract_coverage",
        "validated_iv_greeks",
        "liquidity_staleness",
        "straddle_oi_history",
        "volatility_surface",
        "exposure_estimates",
        "point_in_time_replay",
        "specialist_brief",
        "paper_attribution",
        "zero_broker_writes",
    ):
        assert f"('{gate}'" in source


def test_options_acceptance_is_read_only_over_market_evidence() -> None:
    normalized = " ".join(sql().lower().split())
    assert "insert into trading.option_chain_snapshot_batches" not in normalized
    assert "insert into trading.option_chain_contract_snapshots" not in normalized
    assert "insert into trading.orders" not in normalized
    assert "insert into broker" not in normalized
    assert "broker_write_allowed',false" in normalized
    assert "capital_action_allowed',false" in normalized


def test_options_acceptance_has_api_mcp_and_frontend_actions() -> None:
    api = (ROOT / "api" / "ai_os_api_server.py").read_text(encoding="utf-8")
    mcp = (ROOT / "mcp_server" / "ai_os_mcp_server.py").read_text(encoding="utf-8")
    actions = (ROOT / "ai-office-ui" / "src" / "data" / "actions.ts").read_text(encoding="utf-8")
    assert "def run_option_acceptance" in api
    assert '"/api/options/institutional-analytics/acceptance/run"' in api
    assert "def run_option_acceptance" in mcp
    assert '"ai_os_run_option_acceptance"' in mcp
    assert "useRunOptionAcceptance" in actions
    page = (ROOT / "ai-office-ui" / "src" / "destinations" / "options" / "OptionsDesk.tsx").read_text(encoding="utf-8")
    assert "OptionsAcceptanceControl" in page
    assert "Run Live-Window Acceptance" in page
    assert "Materialize real Zerodha option snapshots" in page
