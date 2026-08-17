from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "postgres" / "init" / "224_options_acceptance_qualified_gamma_flip_v2.sql"


def sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_gamma_flip_no_crossing_is_qualified_not_fabricated() -> None:
    source = sql()
    assert "institutional-options-acceptance-v2" in source
    assert "estimate.assumptions->>'crossing_found'='false'" in source
    assert "estimate.assumptions->>'result_interpretation'='no_crossing_within_tested_grid'" in source
    assert "estimate.quality_status='not_computable'" in source
    assert "estimate.metric_value IS NULL" in source
    assert "jsonb_array_length(estimate.spot_grid)>1" in source
    assert "black_box_signal_allowed',false" in source


def test_gamma_flip_crossing_still_requires_a_numeric_value() -> None:
    source = sql()
    assert "estimate.metric_value IS NOT NULL" in source
    assert "estimate.metric_name='gamma_flip'" in source
    assert "count(DISTINCT estimate.metric_name)" in source
