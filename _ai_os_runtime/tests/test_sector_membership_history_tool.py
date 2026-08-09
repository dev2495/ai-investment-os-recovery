from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_history_builder_is_registered_with_no_inference_or_capital_authority() -> None:
    migration = (ROOT / "postgres" / "init" / "215_sector_membership_history_tool_v1.sql").read_text(
        encoding="utf-8"
    )
    assert "ai_os_build_sector_membership_history" in migration
    assert '"replacement_notice_inference_allowed":false' in migration
    assert '"backdating_current_snapshot_allowed":false' in migration
    assert '"seed_data_allowed":false' in migration
    assert '"broker_order_allowed":false' in migration
    assert '"capital_action_allowed":false' in migration
