from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "api" / "ai_os_api_server.py").read_text(encoding="utf-8")


def function_source(name: str, next_name: str) -> str:
    return API.split(f"def {name}(", 1)[1].split(f"def {next_name}(", 1)[0]


def test_sector_acceptance_commits_run_before_summary_read() -> None:
    source = function_source("run_sector_acceptance", "_options_engine_payload")
    assert "AS acceptance_run_id" in source
    assert "acceptance_run_id = int(run_rows[0]" in source
    assert "WHERE summary.acceptance_run_id={acceptance_run_id}" in source
    assert "WITH accepted AS" not in source


def test_options_and_office_acceptance_use_two_database_statements() -> None:
    options = function_source("run_option_acceptance", "run_office_operability_acceptance")
    office = function_source("run_office_operability_acceptance", "upsert_option_valuation_policy")
    assert "acceptance_run_id = int(run_rows[0]" in options
    assert "WHERE summary.id={acceptance_run_id}" in options
    assert "run_id = int(run_rows[0]" in office
    assert "WHERE summary.id={run_id}" in office
    assert "WITH accepted AS" not in options + office
