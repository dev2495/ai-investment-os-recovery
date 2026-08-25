from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "postgres" / "init" / "202_sector_price_baseline_activation_v1.sql"


def test_activation_is_source_bounded_and_execution_locked() -> None:
    sql = MIGRATION.read_text()
    assert "CREATE OR REPLACE FUNCTION sector_intelligence.activate_price_baseline" in sql
    assert "jsonb_array_length(membership.evidence)>0" in sql
    assert "bar.source_system_id IS NOT NULL" in sql
    assert "v_effective_date-126" in sql
    assert "rank() OVER (ORDER BY momentum_return" in sql
    assert "'equal'" in sql and "'momentum'" in sql
    assert "'seed_or_fabricated_data',false" in sql
    assert "'broker_write_allowed',false" in sql
    assert "'capital_action_allowed',false" in sql
