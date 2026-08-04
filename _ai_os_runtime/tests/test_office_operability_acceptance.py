from pathlib import Path
from unittest import mock

import pytest

from _ai_os_runtime.api import ai_os_api_server


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "postgres" / "init" / "193_live_office_operability_acceptance_v1.sql"


def test_office_operability_has_complete_real_team_gates() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    for gate in (
        "roster_structure",
        "persona_identity",
        "skills_tools",
        "model_routes",
        "department_staffing",
        "fund_function_coverage",
        "bounded_worker_proof",
        "department_evidence",
        "inter_agent_handoffs",
        "processed_delegation",
        "zero_broker_writes",
    ):
        assert f"('{gate}'" in source
    assert "synthetic_worker_runs_allowed',false" in source
    assert "broker_write_allowed BOOLEAN NOT NULL DEFAULT false" in source


def test_office_operability_is_replay_safe_and_durable() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert "ON CONFLICT (run_key) DO UPDATE" in source
    assert "DELETE FROM agent.office_operability_gate_results" in source
    assert "agent.v_office_operability_acceptance" in source


def test_office_operability_api_runs_canonical_function() -> None:
    response = {
        "id": 3,
        "run_key": "office-operability-20260804T120000Z",
        "status": "blocked",
        "gate_count": 11,
        "passed_count": 8,
        "blocked_count": 3,
        "broker_write_allowed": False,
    }
    with (
        mock.patch.object(ai_os_api_server, "run_psql_json", return_value=[response]) as database,
        mock.patch.object(ai_os_api_server, "audit_api_write") as audit,
    ):
        result = ai_os_api_server.run_office_operability_acceptance({"run_key": response["run_key"], "actor": "Devarsh"})

    assert result == response
    query = database.call_args.args[0]
    assert "agent.run_office_operability_acceptance" in query
    assert "agent.v_office_operability_acceptance" in query
    audit.assert_called_once()


def test_office_operability_api_rejects_unsafe_run_key() -> None:
    with pytest.raises(ValueError):
        ai_os_api_server.run_office_operability_acceptance({"run_key": "bad key; drop"})


def test_office_frontend_exposes_operator_acceptance_and_full_profiles() -> None:
    actions = (ROOT / "ai-office-ui" / "src" / "data" / "actions.ts").read_text(encoding="utf-8")
    office = (ROOT / "ai-office-ui" / "src" / "destinations" / "firm" / "OfficeView.tsx").read_text(encoding="utf-8")
    schema = (ROOT / "ai-office-ui" / "src" / "data" / "schemas.ts").read_text(encoding="utf-8")
    assert "useRunOfficeOperabilityAcceptance" in actions
    assert '"/api/office/operability/acceptance/run"' in actions
    assert "AI Office Operability" in office
    assert "Run acceptance" in office
    assert "office_operability_acceptance" in schema
