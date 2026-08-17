from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "api" / "ai_os_api_server.py"
SCHEMA = ROOT / "ai-office-ui" / "src" / "data" / "schemas.ts"
ACTIONS = ROOT / "ai-office-ui" / "src" / "data" / "actions.ts"
PAGE = (
    ROOT
    / "ai-office-ui"
    / "src"
    / "destinations"
    / "sector"
    / "SectorIntelligence.tsx"
)
APP = ROOT / "ai-office-ui" / "src" / "app" / "App.tsx"
DESTINATIONS = ROOT / "ai-office-ui" / "src" / "app" / "destinations.ts"


def test_sector_snapshot_exposes_named_aggregates_and_company_coverage() -> None:
    source = API.read_text(encoding="utf-8")
    assert '"fundamental_coverage": """' in source
    assert "v_fundamental_constituent_coverage" in source
    assert "definition.metric_key" in source
    assert "definition.metric_name" in source
    assert "definition.unit" in source
    assert "node.taxonomy_key" in source
    assert "node.node_name" in source


def test_sector_frontend_contract_contains_fundamental_coverage() -> None:
    source = SCHEMA.read_text(encoding="utf-8")
    sector_schema = source.split(
        "export const SectorIntelligenceSchema", 1
    )[1].split("export type SectorIntelligence", 1)[0]
    assert "fundamental_coverage: z.array(liveRow).default([])" in sector_schema


def test_sector_fundamental_refresh_is_real_and_non_executing() -> None:
    actions = ACTIONS.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    assert "useSyncSectorFundamentals" in actions
    assert '"/api/sector-intelligence/fundamentals/sync"' in actions
    assert '{ key: "fundamentals", label: "Fundamentals"' in page
    assert "SectorFundamentalSyncControl" in page
    assert "Company Fundamental Coverage" in page
    assert "Latest Source-Backed Sector Aggregates" in page
    assert "Missing history is never backfilled" not in page
    assert "missing history is never backfilled" in page
    assert '["Broker writes", 0]' in page


def test_sector_fundamentals_has_canonical_route_and_navigation() -> None:
    app = APP.read_text(encoding="utf-8")
    destinations = DESTINATIONS.read_text(encoding="utf-8")
    assert '"/sector/fundamentals": () =>' in app
    assert 'path: "/sector/fundamentals"' in destinations
    assert 'label: "Sector Fundamentals"' in destinations
