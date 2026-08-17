from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "postgres" / "init" / "196_office_capability_closure_v1.sql"


def test_new_sector_and_options_capabilities_resolve_to_real_tools() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    for alias in (
        "sector_warehouse",
        "sector_intelligence_engine",
        "sector_importer",
        "filing_evidence_reader",
        "zerodha_read_only",
        "institutional_options_materializer",
        "options_math_engine",
    ):
        assert f"('{alias}'" in source
    assert "ai_os_sector_intelligence_snapshot" in source
    assert "ai_os_sector_intelligence_engine" in source


def test_tradingview_permission_boundary_is_not_bypassed() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert "tradingview_task_queue" in source
    assert "Accessibility permission" in source
    assert "broker_order_allowed\":false" in source
    assert "UPDATE agent.tool_registry" not in source


def test_all_active_assignments_receive_deterministic_fallback() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert "fallback_route='agent_worker_deterministic'" in source
    assert "intended primary route is preserved" in source
    assert "profile.status='active'" in source
