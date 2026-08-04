from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "api" / "ai_os_api_server.py"
UI = ROOT / "ai-office-ui" / "src"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_api_exposes_all_three_institutional_programs() -> None:
    source = read(API)
    assert '"fundamental_coverage"' in source
    assert '"investment_dossiers"' in source
    assert '"fundamental_acceptance"' in source
    assert '"/api/sector-intelligence/snapshot"' in source
    assert '"institutional_option_chain"' in source
    assert '"option_acceptance"' in source


def test_api_queries_match_new_view_contracts() -> None:
    source = read(API)
    assert "acceptance_run_id AS run_id" in source
    assert "ranking_universe" in source
    assert "calculation_version" in source
    assert "index_id AS custom_index_id" in source
    assert "source_state_fingerprint" in source
    assert "spot_price, batch_freshness_status" in source
    assert "pending_gate_count" not in source
    assert "ranking_key, taxonomy_node_id" not in source


def test_frontend_routes_and_schemas_are_reachable() -> None:
    app = read(UI / "app" / "App.tsx")
    destinations = read(UI / "app" / "destinations.ts")
    schemas = read(UI / "data" / "schemas.ts")
    for route in (
        "/fundamental/dossiers",
        "/sector/overview",
        "/sector/indices",
        "/sector/flows",
        "/sector/committee",
    ):
        assert route in app
        assert route in destinations
    for key in (
        "fundamental_acceptance",
        "institutional_option_chain",
        "option_analytics_alerts",
        "option_specialist_observations",
    ):
        assert key in schemas


def test_options_ui_never_claims_unvalidated_analytics() -> None:
    source = read(UI / "destinations" / "options" / "OptionsDesk.tsx")
    assert "greeks_validated" in source
    assert "Institutional Analytics Readiness" in source
    assert "No broker write is permitted" in source
    assert "oipulse-class and beyond" not in source.lower()


def test_sector_ui_keeps_tradingview_as_artifact_consumer() -> None:
    source = read(UI / "destinations" / "sector" / "SectorIntelligence.tsx")
    assert "TradingView" in source
    assert "artifact" in source.lower()
    assert "Broker writes" in source
