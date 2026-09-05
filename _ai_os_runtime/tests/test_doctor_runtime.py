"""Focused negative controls for the deterministic Doctor runtime."""
from __future__ import annotations

import re

import pytest

from _ai_os_runtime.api.doctor_runtime import DoctorRuntime, redact


def registry(check_key: str, component: str, runner: str, *, severity: str = "high",
             safe_fix: str | None = None, configuration: dict | None = None) -> dict:
    return {
        "check_key": check_key,
        "component": component,
        "check_name": check_key.replace("_", " ").title(),
        "description": "synthetic evidence only",
        "runner_key": runner,
        "failure_severity": severity,
        "timeout_seconds": 5,
        "safe_fix_key": safe_fix,
        "configuration": configuration or {},
    }


REGISTRY = {
    item["check_key"]: item
    for item in (
        registry("configuration_drift", "configuration", "configuration_drift"),
        registry("pythia_optional", "services", "pythia_optional", severity="low"),
        registry("zerodha_session_stream", "zerodha", "zerodha_session_stream", severity="critical"),
        registry("model_route_health", "models", "model_route_health"),
        registry("obsidian_index_lag", "obsidian", "obsidian_index_lag",
                 configuration={"warn_after_seconds": 900}),
        registry("expired_task_leases", "agents", "expired_task_leases",
                 safe_fix="release_expired_leases"),
        registry("api_readiness", "services", "api_readiness", severity="critical"),
    )
}


class FakeDoctorDatabase:
    def __init__(self):
        self.expired = 2
        self.baseline: dict = {}
        self.model = {
            "route_count": 1,
            "unhealthy_enabled_routes": 0,
            "missing_qualifications": 0,
            "failed_qualifications": 0,
            "expired_qualifications": 0,
            "qualification_identity_mismatches": 0,
            "qualification_version_gaps": 0,
            "unhealthy_endpoints": 0,
            "selected_agent_count": 1,
            "selected_agent_assignment_missing": 0,
            "selected_agent_binding_unready": 0,
            "selected_agent_cost_cap_missing": 0,
        }
        self.zerodha = {
            "provider": "Zerodha",
            "health_status": "live",
            "delay_status": "healthy",
            "connection_state": "connected",
            "api_key_present": True,
            "broker_write_allowed": False,
            "market_open": True,
        }
        self.obsidian = {"note_count": 4, "lag_seconds": 0, "unresolved_links": 0}
        self.statements: list[str] = []
        self.next_result_id = 10

    def query(self, sql: str) -> list[dict]:
        if "doctor:registry" in sql:
            selected = list(REGISTRY.values())
            key = re.search(r"check_key='([^']+)'", sql)
            component = re.search(r"component='([^']+)'", sql)
            if key:
                selected = [value for value in selected if value["check_key"] == key.group(1)]
            if component:
                selected = [value for value in selected if value["component"] == component.group(1)]
            return selected
        if "doctor:configuration_baseline" in sql:
            return [self.baseline] if self.baseline else []
        if "doctor:zerodha_session_stream" in sql:
            return [self.zerodha]
        if "doctor:model_route_health" in sql:
            return [self.model]
        if "doctor:obsidian_index_lag" in sql:
            return [self.obsidian]
        if "doctor:expired_task_leases" in sql:
            return [{"expired_active_leases": self.expired,
                     "potentially_recoverable": self.expired,
                     "oldest_expiry": "2026-09-05T00:00:00Z" if self.expired else None}]
        if "doctor:last_known_good" in sql:
            return [{"last_known_good_at": None}]
        raise AssertionError(f"unexpected query: {sql}")

    def statement(self, sql: str) -> list[dict]:
        self.statements.append(sql)
        if "doctor:persist_start" in sql:
            return [{"id": 1, "run_key": "doctor-fixture", "mode": "safe_fix",
                     "status": "running", "started_at": "fixture"}]
        if "doctor:persist_result" in sql:
            self.next_result_id += 1
            return [{"id": self.next_result_id, "observed_at": "fixture",
                     "last_known_good_at": None}]
        if "doctor:persist_finish" in sql:
            return [{"id": 1}]
        if "doctor:safe_fix:release_expired_leases" in sql:
            before = self.expired
            self.expired = 0
            return [{"result": {"examined": before, "requeued": before, "blocked": 0}}]
        if "doctor:persist_safe_fix" in sql:
            return [{"id": 99}]
        if "doctor:capture_baseline" in sql:
            return [{"id": 1}]
        raise AssertionError(f"unexpected statement: {sql}")


def test_redaction_never_returns_credential_values():
    payload = redact({
        "access_token": "token-should-never-return",
        "requires_api_key": True,
        "error": "request failed: Bearer abcdefghijklmnop",
        "nested": [{"password": "also-secret"}],
    })
    encoded = repr(payload)
    assert "token-should-never-return" not in encoded
    assert "also-secret" not in encoded
    assert "abcdefghijklmnop" not in encoded
    assert payload["requires_api_key"] is True


def test_unknown_probe_is_not_reported_healthy():
    db = FakeDoctorDatabase()
    result = DoctorRuntime(db.query, probes={}).run(
        check_key="api_readiness", persist=False
    )
    assert result["status"] == "degraded"
    assert result["checks"][0]["status"] == "unknown"


def test_configuration_drift_requires_and_compares_reviewed_baseline():
    db = FakeDoctorDatabase()
    probe = lambda: {"status": "passed", "headline": "config readable",
                     "configuration_digest": "b" * 64, "watched_hashes": {"a": "b"}}
    doctor = DoctorRuntime(db.query, probes={"configuration_drift": probe})
    assert doctor.run(check_key="configuration_drift", persist=False)["checks"][0]["status"] == "warning"
    db.baseline = {"observed_digest": "c" * 64, "configuration_digest": "a" * 64,
                   "captured_at": "fixture", "captured_by": "reviewer"}
    drift = doctor.run(check_key="configuration_drift", persist=False)["checks"][0]
    assert drift["status"] == "failed"
    assert drift["observed"]["expected_configuration_digest"] == "a" * 64
    # Baseline creation intentionally bypasses comparison so a reviewed baseline can be initialized.
    assert doctor.run(check_key="configuration_drift", mode="baseline", persist=False)["checks"][0]["status"] == "passed"


def test_optional_pythia_absence_is_explicitly_skipped():
    db = FakeDoctorDatabase()
    doctor = DoctorRuntime(db.query, probes={
        "pythia_optional": lambda: {"status": "skipped", "headline": "Pythia is not installed",
                                    "installed": False}
    })
    check = doctor.run(check_key="pythia_optional", persist=False)["checks"][0]
    assert check["status"] == "skipped"
    assert check["observed"]["installed"] is False


def test_market_open_stale_zerodha_quote_fails_closed_without_secret():
    db = FakeDoctorDatabase()
    db.zerodha.update({"delay_status": "delayed_quotes", "latest_quote_age_seconds": 180})
    check = DoctorRuntime(db.query).run(
        check_key="zerodha_session_stream", persist=False
    )["checks"][0]
    assert check["status"] == "failed"
    assert check["observed"]["provider"] == "Zerodha"
    assert check["observed"]["broker_write_allowed"] is False
    assert "credential" not in repr(check).lower()


def test_dead_model_route_and_obsidian_lag_are_actionable_failures():
    db = FakeDoctorDatabase()
    db.model["unhealthy_enabled_routes"] = 1
    model = DoctorRuntime(db.query).run(check_key="model_route_health", persist=False)["checks"][0]
    assert model["status"] == "failed"
    db.obsidian.update({"lag_seconds": 1200, "unresolved_links": 2})
    obsidian = DoctorRuntime(
        db.query, probes={"obsidian_integrity": lambda: {"broken_managed_blocks": 0}}
    ).run(check_key="obsidian_index_lag", persist=False)["checks"][0]
    assert obsidian["status"] == "failed"
    assert obsidian["actionable_fix"]


def test_missing_or_identity_drifted_model_qualification_fails_closed():
    db = FakeDoctorDatabase()
    db.model["missing_qualifications"] = 1
    missing = DoctorRuntime(db.query).run(
        check_key="model_route_health", persist=False
    )["checks"][0]
    assert missing["status"] == "failed"
    db.model["missing_qualifications"] = 0
    db.model["qualification_identity_mismatches"] = 1
    drifted = DoctorRuntime(db.query).run(
        check_key="model_route_health", persist=False
    )["checks"][0]
    assert drifted["status"] == "failed"


def test_only_allowlisted_safe_fix_runs_with_before_after_receipt():
    db = FakeDoctorDatabase()
    doctor = DoctorRuntime(db.query, db.statement)
    with pytest.raises(ValueError, match="confirmation"):
        doctor.safe_fix(confirmed=False)
    result = doctor.safe_fix(confirmed=True)
    assert result["status"] == "applied"
    assert result["before"]["status"] == "failed"
    assert result["after"]["status"] == "passed"
    assert result["broker_write_allowed"] is False
    assert any("agent.reap_runtime_leases(100)" in sql for sql in db.statements)
    assert not any("zerodha" in sql.lower() for sql in db.statements)
