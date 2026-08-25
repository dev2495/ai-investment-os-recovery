from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "postgres" / "init" / "192_fundamental_acceptance_replay_v1.sql"
FACTORY = ROOT / "scripts" / "run_institutional_fundamental_factory.py"


def test_fundamental_acceptance_run_is_replay_safe_and_company_bound() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert "CREATE OR REPLACE FUNCTION research.open_real_company_acceptance_run" in source
    assert "ON CONFLICT (run_key) DO UPDATE" in source
    assert "v_existing_company_id<>p_company_id" in source
    assert "cannot move between companies" in source


def test_factory_replaces_gate_results_and_requires_institutional_completion() -> None:
    source = FACTORY.read_text(encoding="utf-8")
    assert "DELETE FROM research.fundamental_acceptance_gates" in source
    for gate in (
        "section_readiness",
        "management_accountability",
        "independent_challenge",
        "holding_thesis",
        "valuation_suite",
        "committee_decision",
    ):
        assert f'_gate("{gate}"' in source
    assert "completed_valuation_types" in source
    assert "completed_monte_carlo_count" in source
    assert "latest_committee AS" in source
