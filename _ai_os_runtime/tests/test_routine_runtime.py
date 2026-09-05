"""Safety, control and exact-once tests for versioned routines."""
from __future__ import annotations

import json
import re

import pytest

from _ai_os_runtime.api.routine_runtime import (
    ROUTINE_KEYS,
    RoutineRuntime,
    canonical_event_hash,
)


class FakeRoutineDatabase:
    def __init__(self, *, enabled: bool = True):
        self.enabled = enabled
        self.starts: dict[str, dict] = {}
        self.statements: list[str] = []

    def _routine_from_sql(self, sql: str) -> str:
        for key in ROUTINE_KEYS:
            if f"'{key}'" in sql:
                return key
        return "daily_system_health"

    def query(self, sql: str) -> list[dict]:
        if "routine:definition" in sql:
            key = self._routine_from_sql(sql)
            trigger_kind = "event" if key == "research_company_change_monitor" else "schedule"
            return [{
                "routine_key": key,
                "current_version": 1,
                "control_state": "enabled" if self.enabled else "disabled",
                "schedule_enabled": self.enabled and trigger_kind == "schedule",
                "trigger_kind": trigger_kind,
                "allowed_tools": {
                    "daily_system_health": ["ai_os_doctor"],
                    "obsidian_incremental_index": ["index_obsidian_vault"],
                    "research_company_change_monitor": ["company_research_monitor"],
                    "stale_task_and_lease_reaper": ["release_expired_leases"],
                    "zerodha_session_and_stream_watch": ["zerodha_health_read"],
                }[key],
                "cost_budget_usd": 0,
                "broker_write_allowed": False,
            }]
        if "routine:lease_reaper:test" in sql:
            return [{"expired_active_leases": 0}]
        if "routine:obsidian:test" in sql:
            return [{"note_count": 42, "latest_indexed_at": "fixture"}]
        if "routine:list" in sql or "routine:history" in sql:
            return []
        raise AssertionError(f"unexpected query: {sql}")

    def statement(self, sql: str) -> list[dict]:
        self.statements.append(sql)
        if "routine:start" in sql:
            key = self._routine_from_sql(sql)
            match = re.search(r"'(?:[^']|'')*:(?:[0-9a-f]{64}|[^']+)'", sql)
            dedupe = match.group(0) if match else sql
            if dedupe in self.starts:
                previous = self.starts[dedupe]
                return [{"result": {**previous, "created": False, "duplicate": True}}]
            start = {
                "run_id": len(self.starts) + 1,
                "run_key": f"{key}-fixture-{len(self.starts)+1}",
                "routine_key": key,
                "routine_version": 1,
                "status": "running",
                "created": True,
                "duplicate": False,
                "test_mode": "true" in sql,
                "model_cost_usd": 0,
                "broker_write_allowed": False,
            }
            self.starts[dedupe] = start
            return [{"result": start}]
        if "routine:finish" in sql:
            return [{"result": {"status": "completed", "run_key": "fixture",
                                 "model_cost_usd": 0, "broker_write_allowed": False}}]
        if "routine:control" in sql:
            key = self._routine_from_sql(sql)
            trigger_kind = "event" if key == "research_company_change_monitor" else "schedule"
            return [{"result": {"routine_key": key,
                                 "control_state": "enabled",
                                 "schedule_enabled": trigger_kind == "schedule",
                                 "trigger_kind": trigger_kind,
                                 "broker_write_allowed": False}}]
        raise AssertionError(f"unexpected statement: {sql}")


class FakeDoctor:
    def run(self, **kwargs):
        component = kwargs.get("component")
        if component == "zerodha":
            return {
                "status": "passed", "run_key": "doctor-zerodha",
                "counts": {"passed": 1},
                "checks": [{"check_key": "zerodha_session_stream", "status": "passed",
                            "headline": "fresh", "observed": {"provider": "Zerodha",
                            "delay_status": "healthy", "broker_write_allowed": False},
                            "actionable_fix": None}],
            }
        return {
            "status": "passed", "run_key": "doctor-all", "counts": {"passed": 21},
            "checks": [{"check_key": "api_readiness", "status": "passed",
                        "headline": "ready", "actionable_fix": None}],
        }


def artifact_writer(_routine: str, run_key: str, payload: dict) -> dict[str, str]:
    assert payload["model_calls"] == 0
    assert payload["broker_write_allowed"] is False
    return {
        "path": f"/Volumes/Devarsh SSD/AI OS Data/artifacts/routines/fixture/{run_key}.json",
        "sha256": "a" * 64,
    }


def runtime(db: FakeRoutineDatabase, *, artifacts=True) -> RoutineRuntime:
    return RoutineRuntime(
        db.query,
        db.statement,
        doctor_factory=FakeDoctor,
        artifact_writer=artifact_writer if artifacts else None,
        actor="fixture-operator",
    )


def filing_payload() -> dict:
    return {
        "event_type": "filing",
        "source_identifier": "fixture:filing:26001",
        "symbol": "FIXTURE",
        "authorized_stored_source_only": True,
    }


def test_event_hash_is_canonical_and_secret_values_are_not_retained():
    first = canonical_event_hash({"b": 2, "a": 1, "access_token": "never-return"})
    second = canonical_event_hash({"a": 1, "access_token": "different-secret", "b": 2})
    assert first == second
    assert re.fullmatch(r"[0-9a-f]{64}", first)
    assert "never-return" not in first


def test_real_run_refuses_disabled_definition_before_a_receipt():
    db = FakeRoutineDatabase(enabled=False)
    with pytest.raises(ValueError, match="explicitly enabled"):
        runtime(db).run("daily_system_health")
    assert db.statements == []


def test_control_requires_confirmation_and_bounded_reason():
    db = FakeRoutineDatabase()
    service = runtime(db)
    with pytest.raises(ValueError, match="confirmation"):
        service.control("daily_system_health", "enable", confirmed=False, reason="reviewed ok")
    with pytest.raises(ValueError, match="reason"):
        service.control("daily_system_health", "enable", confirmed=True, reason="short")
    receipt = service.control(
        "daily_system_health", "enable", confirmed=True,
        reason="Reviewed health routine enablement for the fixture.",
    )
    assert receipt["control_state"] == "enabled"
    assert receipt["broker_write_allowed"] is False


def test_filing_fixture_is_exact_once_and_writes_one_durable_artifact():
    db = FakeRoutineDatabase(enabled=False)
    service = runtime(db)
    payload = filing_payload()
    event_hash = canonical_event_hash(payload)
    first = service.run(
        "research_company_change_monitor", trigger_kind="event", payload=payload,
        event_hash=event_hash, test_mode=True,
    )
    second = service.run(
        "research_company_change_monitor", trigger_kind="event", payload=payload,
        event_hash=event_hash, test_mode=True,
    )
    assert first["handler_invoked"] is True
    assert first["artifact"]["path"].startswith("/Volumes/Devarsh SSD/AI OS Data/")
    assert second["duplicate_suppressed"] is True
    assert second["handler_invoked"] is False
    assert len([sql for sql in db.statements if "routine:finish" in sql]) == 1
    assert first["model_calls"] == 0
    assert first["broker_write_allowed"] is False


def test_event_trigger_requires_hash_and_company_monitor_requires_event():
    db = FakeRoutineDatabase()
    service = runtime(db)
    with pytest.raises(ValueError, match="event_hash"):
        service.run("research_company_change_monitor", trigger_kind="event", payload=filing_payload())
    with pytest.raises(ValueError, match="event trigger"):
        service.run("research_company_change_monitor", trigger_kind="manual")


def test_company_monitor_fails_closed_without_durable_artifact_writer():
    db = FakeRoutineDatabase(enabled=False)
    result = runtime(db, artifacts=False).run(
        "research_company_change_monitor", trigger_kind="event", payload=filing_payload(),
        event_hash=canonical_event_hash(filing_payload()), test_mode=True,
    )
    assert result["status"] == "failed"
    assert result["broker_write_allowed"] is False
    assert "artifact writer" in result["error"]["error"]


def test_doctor_routines_accept_minimal_run_protocol_and_remain_read_only():
    db = FakeRoutineDatabase(enabled=False)
    health = runtime(db).run("daily_system_health", test_mode=True)
    zerodha = runtime(FakeRoutineDatabase(enabled=False)).run(
        "zerodha_session_and_stream_watch", test_mode=True
    )
    assert health["result"]["doctor_run_key"] == "doctor-all"
    assert zerodha["result"]["health"]["provider"] == "Zerodha"
    assert zerodha["result"]["credential_value_read"] is False
    assert health["client_write_allowed"] is False


def test_schedule_requires_stable_due_timestamp_for_idempotency():
    db = FakeRoutineDatabase()
    service = runtime(db)
    with pytest.raises(ValueError, match="due_at"):
        service.run("daily_system_health", trigger_kind="schedule")
    result = service.run(
        "daily_system_health", trigger_kind="schedule",
        payload={"due_at": "2026-09-05T00:00:00Z"},
    )
    assert result["handler_invoked"] is True


def test_unknown_routine_and_unreviewed_tool_contract_are_refused():
    db = FakeRoutineDatabase()
    with pytest.raises(ValueError, match="allowlist"):
        runtime(db).run("arbitrary_shell")
    original = db.query

    def altered(sql: str):
        rows = original(sql)
        if "routine:definition" in sql:
            rows[0]["allowed_tools"] = ["arbitrary_shell"]
        return rows

    service = RoutineRuntime(altered, db.statement, doctor_factory=FakeDoctor)
    with pytest.raises(RuntimeError, match="allowlist"):
        service.run("daily_system_health", test_mode=True)
def test_enabled_event_routine_does_not_enable_periodic_materialization():
    db = FakeRoutineDatabase(enabled=True)
    service = runtime(db)
    service._handler = lambda _routine_key: (
        lambda **_kwargs: {"status": "completed", "source": "fixture"}
    )
    payload = filing_payload()
    result = service.run(
        "research_company_change_monitor",
        trigger_kind="event",
        payload=payload,
        event_hash=canonical_event_hash(payload),
    )
    definition = db.query(
        "/* routine:definition */ 'research_company_change_monitor'"
    )[0]
    assert result["status"] == "completed"
    assert definition["control_state"] == "enabled"
    assert definition["schedule_enabled"] is False
