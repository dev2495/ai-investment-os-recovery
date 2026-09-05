"""Static and CLI contracts for migration 260 Doctor/routine delivery."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from _ai_os_runtime.api.doctor_runtime import DoctorRuntime
from _ai_os_runtime.api.routine_runtime import ROUTINE_KEYS, ROUTINE_TOOL_ALLOWLIST
from _ai_os_runtime.scripts import ai_os_doctor, run_ai_os_routine


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "postgres" / "init" / "260_ai_os_doctor_and_routines_v1.sql"


DOCTOR_CHECKS = {
    "postgres_migration_level", "external_ssd_storage", "api_readiness",
    "redis_health", "qdrant_health", "obsidian_index_lag",
    "backup_restore_receipt", "worker_heartbeat", "expired_task_leases",
    "queue_backlog", "routine_scheduler", "model_route_health",
    "zerodha_session_stream", "tradingview_connector", "pythia_optional",
    "ui_asset_equality", "launchd_services", "configuration_drift",
    "execution_safety_locks", "client_scope_isolation",
    "changed_file_secret_scan",
}


def test_migration_registry_and_runtime_handlers_are_complete():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert set(DoctorRuntime.HANDLERS) == DOCTOR_CHECKS
    assert set(ai_os_doctor.probes()) <= DOCTOR_CHECKS | {"obsidian_integrity"}
    for key in DOCTOR_CHECKS:
        assert f"('{key}'" in sql
    assert '"doctor_checks":21' in sql
    migration_key = "260_ai_os_doctor_and_routines_v1"
    checksum = hashlib.sha256(migration_key.encode("utf-8")).hexdigest()
    assert sql.count(f"'{checksum}'") == 2


def test_five_routines_are_versioned_disabled_and_reuse_schedule_authority():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert len(ROUTINE_KEYS) == 5
    assert set(ROUTINE_TOOL_ALLOWLIST) == set(ROUTINE_KEYS)
    assert "CREATE TABLE IF NOT EXISTS agent.workflow_schedules" not in sql
    assert "INSERT INTO agent.workflow_schedules" in sql
    assert "SELECT routine_key,routine_name,description,owner_agent,schedule_key,1,'disabled'" in sql
    assert "current_version=EXCLUDED.current_version" not in sql
    assert "published routine versions are immutable" in sql
    assert "event trigger requires a sha256 event hash" in sql
    assert "'Research Director','event','write_db_and_artifact'" in sql
    assert "trigger_type=EXCLUDED.trigger_type" in sql
    assert "schedule.enabled<>(definition.control_state='enabled')" in sql
    assert "version.trigger_kind='event' AND schedule.enabled" in sql
    assert "cost_budget_usd=0" in sql
    for key in ROUTINE_KEYS:
        assert f"('{key}'" in sql


def test_sql_and_runtime_encode_hard_safety_boundaries():
    sql = MIGRATION.read_text(encoding="utf-8")
    runtime_source = (ROOT / "api" / "routine_runtime.py").read_text(encoding="utf-8")
    for fragment in (
        "broker_write_allowed=false",
        "external_write_allowed=false",
        "client_write_allowed=false",
        "credential_change_allowed=false",
        "autonomous routine model budget must remain zero",
        "secret-shaped routine input refused",
    ):
        assert fragment in sql
    assert "subprocess" not in runtime_source
    assert "requests." not in runtime_source
    assert "httpx." not in runtime_source
    assert "model_calls\": 0" in runtime_source


def test_cli_exposes_scan_test_history_and_explicit_controls():
    doctor_help = ai_os_doctor.parser().format_help()
    for flag in ("--json", "--quiet", "--init-baseline", "--safe-fix",
                 "--component", "--agent", "--model-route"):
        assert flag in doctor_help
    routine_help = run_ai_os_routine.parser().format_help()
    for flag in ("--list", "--history", "--test", "--run", "--enable",
                 "--pause", "--disable", "--fixture-filing", "--confirm"):
        assert flag in routine_help


def test_optional_pythia_probe_does_not_install_or_mutate(monkeypatch):
    monkeypatch.delenv("AI_OS_PYTHIA_HEALTH_URL", raising=False)
    result = ai_os_doctor.probe_pythia()
    assert result == {
        "status": "skipped",
        "headline": "Pythia is not configured on this host",
        "installed": False,
    }


def test_routine_artifact_refuses_internal_or_unrelated_root(monkeypatch, tmp_path):
    volume = tmp_path / "external"
    outside = tmp_path / "internal"
    monkeypatch.setenv("AI_OS_SSD_ROOT", str(volume))
    monkeypatch.setenv("AI_OS_DATA_ROOT", str(outside))
    with pytest.raises(RuntimeError, match="outside the configured external SSD"):
        run_ai_os_routine.write_artifact("daily_system_health", "fixture", {})


def test_protected_zerodha_implementation_files_are_not_modified():
    protected = (
        "sync_zerodha_read_only.py", "sync_zerodha_market_data.py",
        "stream_zerodha_live.py", "configure_zerodha_imac.sh",
        "renew_zerodha_session_imac.sh", "install_zerodha_stream_imac.sh",
    )
    # This slice reads canonical views only. Its owned sources must not import or rewrite
    # any protected credential/session implementation entry point.
    owned = "\n".join((ROOT / "api" / name).read_text(encoding="utf-8")
                       for name in ("doctor_runtime.py", "routine_runtime.py"))
    for filename in protected:
        assert filename not in owned
    assert "market.v_zerodha_stream_health" in owned
    assert "core.v_provider_readiness_board" in owned
