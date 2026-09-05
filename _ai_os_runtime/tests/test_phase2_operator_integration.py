"""Focused contracts for Phase 2 HTTP, MCP, startup and routine dispatch."""
from __future__ import annotations

from contextlib import contextmanager
from http.server import ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import threading
import urllib.error
import urllib.request
from unittest.mock import patch

import pytest

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME_ROOT / "api"))
sys.path.insert(0, str(RUNTIME_ROOT / "scripts"))

from _ai_os_runtime.api import ai_os_api_server as api_server
from _ai_os_runtime.api.agent_os_policy import Principal
from _ai_os_runtime.scripts import run_agent_message_daemon as daemon

MCP_PATH = RUNTIME_ROOT / "mcp_server" / "ai_os_mcp_server.py"
MCP_SPEC = importlib.util.spec_from_file_location("ai_os_mcp_server_phase2_contract", MCP_PATH)
assert MCP_SPEC and MCP_SPEC.loader
MCP = importlib.util.module_from_spec(MCP_SPEC)
MCP_SPEC.loader.exec_module(MCP)


@contextmanager
def live_api(monkeypatch, *, principal: Principal | None = None):
    monkeypatch.setattr(
        api_server,
        "RUNTIME_API",
        SimpleNamespace(execute=lambda _sql: "false", _value=lambda _sql: False),
    )
    monkeypatch.setattr(
        api_server, "AGENT_OS_PRINCIPAL", principal or Principal(user_id="phase2_operator")
    )
    monkeypatch.setattr(api_server, "OPERATOR_TOKEN", "synthetic-phase2-operator")
    monkeypatch.setattr(api_server, "ALLOW_TOKENLESS_LOOPBACK", False)
    http = ThreadingHTTPServer(("127.0.0.1", 0), api_server.AiOsApiHandler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{http.server_port}"
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=2)


def call(base: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    headers = {"Authorization": "Bearer synthetic-phase2-operator"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
    request = urllib.request.Request(base + path, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


class FakeFabric:
    calls: list[tuple] = []

    def __init__(self, _execute):
        pass

    def snapshot(self):
        return {
            "available": True, "bindings": [], "history": [], "qualifications": [],
            "recent_calls": [], "audit": [], "provider_calls_made": False,
            "broker_write_allowed": False,
        }

    def propose(self, payload, actor):
        self.calls.append(("propose", payload, actor))
        return {"status": "proposed", "actor": actor, "broker_write_allowed": False}

    def qualify(self, route_name, task_class, actor):
        self.calls.append(("qualify", route_name, task_class, actor))
        return {"state": "passed", "reasoning_profiles": ["none"], "broker_write_allowed": False}

    def _version(self, version_id):
        return {
            "id": int(version_id), "binding_key": "fixture.binding",
            "primary_route": "fixture_local", "task_class": "fixture_task",
            "reasoning_profile": "none",
        }

    def compare(self, qualification_ids):
        self.calls.append(("compare", qualification_ids))
        return {
            "qualifications": [{"id": item} for item in qualification_ids],
            "provider_calls_made": False, "promotion_performed": False,
            "broker_write_allowed": False,
        }

    def promote(self, version_id, actor, approval_id=None):
        self.calls.append(("promote", version_id, actor, approval_id))
        return {"enabled": True, "actor": actor, "broker_write_allowed": False}

    def rollback(self, binding_key, version_id, actor, approval_id=None):
        self.calls.append(("rollback", binding_key, version_id, actor, approval_id))
        return {"enabled": True, "actor": actor, "broker_write_allowed": False}

    def disable(self, binding_key, actor):
        self.calls.append(("disable", binding_key, actor))
        return {"enabled": False, "actor": actor, "broker_write_allowed": False}


class FakeDoctor:
    calls: list[tuple] = []

    def run(self, **kwargs):
        self.calls.append(("run", kwargs))
        return {"status": "passed", "broker_write_allowed": False}

    def safe_fix(self, **kwargs):
        self.calls.append(("safe_fix", kwargs))
        return {"status": "completed", "broker_write_allowed": False}


class FakeRoutine:
    calls: list[tuple] = []

    def run(self, routine_key, **kwargs):
        self.calls.append(("run", routine_key, kwargs))
        return {"status": "completed", "broker_write_allowed": False}

    def control(self, routine_key, action, **kwargs):
        self.calls.append(("control", routine_key, action, kwargs))
        return {"routine_key": routine_key, "control_state": action, "broker_write_allowed": False}


def test_http_operator_routes_are_confirmed_internal_and_server_principal_scoped(monkeypatch):
    FakeFabric.calls.clear()
    FakeDoctor.calls.clear()
    FakeRoutine.calls.clear()
    monkeypatch.setattr(api_server, "ModelFabric", FakeFabric)
    monkeypatch.setattr(api_server, "_phase2_relations_ready", lambda *_names: True)
    monkeypatch.setattr(api_server, "_build_doctor_runtime", lambda _actor: FakeDoctor())
    monkeypatch.setattr(api_server, "_build_routine_runtime", lambda _actor: FakeRoutine())
    monkeypatch.setattr(api_server, "_doctor_snapshot", lambda: {
        "available": True, "status": "passed", "latest_run": {}, "checks": [],
        "registry": [], "history": [], "broker_write_allowed": False,
    })
    monkeypatch.setattr(api_server, "_routine_snapshot", lambda _actor: {
        "available": True, "routines": [], "history": [], "broker_write_allowed": False,
    })

    with live_api(monkeypatch) as base:
        for path in (
            "/api/v1/model-fabric", "/api/v1/model-bindings", "/api/v1/doctor",
            "/api/v1/system/doctor", "/api/v1/routines",
        ):
            status, body = call(base, path)
            assert status == 200
            assert body["available"] is True
            assert body["broker_write_allowed"] is False
        assert FakeFabric.calls == []

        status, body = call(base, "/api/v1/model-bindings/compare", {
            "qualification_ids": [11, 12], "confirmed": True,
        })
        assert status == 200
        assert body["provider_calls_made"] is False
        assert body["promotion_performed"] is False
        assert FakeFabric.calls[-1] == ("compare", [11, 12])

        status, body = call(base, "/api/v1/model-bindings/test", {
            "version_id": 7, "confirmed": True,
        })
        assert status == 200
        assert body["tested_version_id"] == 7
        assert body["promotion_performed"] is False
        assert FakeFabric.calls[-1][:3] == ("qualify", "fixture_local", "fixture_task")

        status, body = call(base, "/api/v1/model-bindings/promote", {
            "version_id": 7, "approval_id": 91, "confirmed": True,
        })
        assert status == 200 and body["actor"] == "phase2_operator"
        assert FakeFabric.calls[-1] == ("promote", 7, "phase2_operator", 91)

        status, body = call(base, "/api/v1/model-bindings/rollback", {
            "binding_key": "fixture.binding", "version_id": 6,
            "approval_id": 92, "confirmed": True,
        })
        assert status == 200 and body["actor"] == "phase2_operator"
        assert FakeFabric.calls[-1] == (
            "rollback", "fixture.binding", 6, "phase2_operator", 92,
        )

        status, _ = call(base, "/api/v1/model-bindings/promote", {"version_id": 7})
        assert status == 403

        status, _ = call(base, "/api/v1/model-fabric/propose", {
            "binding_key": "fixture.binding", "selector_kind": "agent",
            "selector_value": "Fixture", "task_class": "fixture_task",
            "primary_route": "fixture_local",
        })
        assert status == 403
        status, body = call(base, "/api/v1/model-fabric/propose", {
            "binding_key": "fixture.binding", "selector_kind": "agent",
            "selector_value": "Fixture", "task_class": "fixture_task",
            "primary_route": "fixture_local", "confirmed": True,
        })
        assert status == 200 and body["actor"] == "phase2_operator"
        assert FakeFabric.calls[-1][2] == "phase2_operator"

        status, _ = call(base, "/api/v1/model-fabric/propose", {
            "binding_key": "fixture.binding", "selector_kind": "agent",
            "selector_value": "Fixture", "task_class": "fixture_task",
            "primary_route": "fixture_local", "confirmed": True,
            "actor": "spoofed_reviewer",
        })
        assert status == 400

        status, body = call(base, "/api/v1/doctor/run", {
            "mode": "scan", "check_key": "queue_backlog", "confirmed": True,
        })
        assert status == 200 and body["status"] == "passed"
        assert FakeDoctor.calls[-1][1]["mode"] == "scan"
        status, _ = call(base, "/api/v1/doctor/fixes", {
            "check_key": "configuration_drift", "confirmed": True,
        })
        assert status == 403

        status, body = call(base, "/api/v1/routines/daily_system_health/enable", {
            "reason": "Reviewed fixture enablement.", "confirmed": True,
        })
        assert status == 200 and body["routine_key"] == "daily_system_health"
        call_kwargs = FakeRoutine.calls[-1][3]
        assert call_kwargs["actor"] == "phase2_operator"
        assert call_kwargs["confirmed"] is True

    with live_api(
        monkeypatch,
        principal=Principal(user_id="client_operator", scope="client_private", clients=(7,)),
    ) as base:
        status, body = call(base, "/api/v1/model-fabric")
        assert status == 403
        assert body["error"] == "agent_os_request_rejected"


def test_missing_phase2_migrations_are_truthful_read_only_unavailable(monkeypatch):
    class MissingFabric(FakeFabric):
        def snapshot(self):
            return {
                "available": False, "reason": "model_fabric_authorities_unavailable",
                "bindings": [], "history": [], "qualifications": [],
                "recent_calls": [], "audit": [], "broker_write_allowed": False,
            }

    monkeypatch.setattr(api_server, "ModelFabric", MissingFabric)
    monkeypatch.setattr(api_server, "_phase2_relations_ready", lambda *_names: False)
    with live_api(monkeypatch) as base:
        payloads = [call(base, path)[1] for path in (
            "/api/v1/model-fabric", "/api/v1/model-bindings",
            "/api/v1/doctor", "/api/v1/system/doctor", "/api/v1/routines",
        )]
    assert all(payload["available"] is False for payload in payloads)
    assert all(payload["broker_write_allowed"] is False for payload in payloads)
    assert payloads[0]["provider_calls_made"] is False


def test_sidebar_chat_routes_only_classified_phase2_commands_to_durable_charlie(monkeypatch):
    command = "Charlie, show every live agent and what each is doing."
    assert api_server.is_phase2_control_command(command) is True

    class FakeCharlie:
        calls: list[dict] = []

        def __init__(self, _execute, _principal):
            pass

        def command(self, payload):
            self.calls.append(payload)
            return {
                "current_state": "OBSERVED", "conclusion": "Agent evidence returned.",
                "next_action": "Inspect one agent if needed.", "sources": [], "tasks": [],
                "broker_write_allowed": False,
            }

    monkeypatch.setattr(api_server, "CharlieAPI", FakeCharlie)
    monkeypatch.setattr(api_server, "_phase2_relations_ready", lambda *_names: True)
    with live_api(monkeypatch) as base:
        payload = {
            "message": command, "session_key": "sidebar-fixture",
            "metadata": {"research_case_id": 12, "client_id": 99, "book_id": 88},
        }
        first_status, first = call(base, "/api/chat", payload)
        second_status, second = call(base, "/api/chat", payload)
    assert first_status == second_status == 201
    assert first["conversation_mode"] == "durable_control"
    assert first["model_runtime"]["model_calls"] == 0
    assert first["chat_turn"]["request_key"] == second["chat_turn"]["request_key"]
    assert FakeCharlie.calls[0]["context"] == {"research_case_id": 12}
    assert FakeCharlie.calls[0]["request_key"] == FakeCharlie.calls[1]["request_key"]

    class RefusingCharlie(FakeCharlie):
        def command(self, _payload):
            raise api_server.RuntimeRequestError("Bounded command refused.", 422)

    monkeypatch.setattr(api_server, "CharlieAPI", RefusingCharlie)
    monkeypatch.setattr(
        api_server, "chat_with_charlie",
        lambda _payload: (_ for _ in ()).throw(AssertionError("legacy fallback must not run")),
    )
    with live_api(monkeypatch) as base:
        status, body = call(base, "/api/chat", {"message": command})
    assert status == 422
    assert "refused" in body["message"].lower()

    legacy_command = "How are you today?"
    assert api_server.is_phase2_control_command(legacy_command) is False
    monkeypatch.setattr(api_server, "chat_with_charlie", lambda _payload: {"legacy": True})
    with live_api(monkeypatch) as base:
        status, body = call(base, "/api/chat", {"message": legacy_command})
    assert status == 201 and body == {"legacy": True}


def test_mcp_phase2_tools_are_closed_confirmed_and_route_only_to_http():
    names = {
        "ai_os_model_fabric_overview", "ai_os_model_fabric_propose",
        "ai_os_model_fabric_qualify", "ai_os_model_fabric_test",
        "ai_os_model_fabric_control", "ai_os_doctor_overview", "ai_os_doctor_run",
        "ai_os_doctor_safe_fix", "ai_os_routine_overview", "ai_os_routine_test",
        "ai_os_routine_control",
    }
    assert names <= MCP.TOOLS.keys()
    for name in names:
        schema = MCP.TOOLS[name]["inputSchema"]
        assert schema["additionalProperties"] is False
        properties = schema.get("properties", {})
        assert not {"actor", "principal", "reviewer", "client_id", "book_id", "broker"} & properties.keys()

    with pytest.raises(ValueError, match="confirmation"):
        MCP.model_fabric_test({"version_id": 7})
    with patch.object(MCP, "post_api_json", return_value={"status": "passed"}) as post:
        MCP.doctor_run({"check_key": "queue_backlog", "operator_confirmed": True})
        assert post.call_args.args[0] == "/api/v1/doctor/run"
        assert post.call_args.args[1] == {
            "check_key": "queue_backlog", "mode": "scan", "confirmed": True,
        }
    with patch.object(MCP, "post_api_json", return_value={"control_state": "enabled"}) as post:
        MCP.routine_control({
            "routine_key": "daily_system_health", "action": "enable",
            "reason": "Reviewed fixture enablement.", "operator_confirmed": True,
        })
        assert post.call_args.args[0] == "/api/v1/routines/daily_system_health/enable"
        assert post.call_args.args[1]["confirmed"] is True
        assert "operator_confirmed" not in post.call_args.args[1]
    expected = {
        "daily_system_health", "obsidian_incremental_index",
        "research_company_change_monitor", "stale_task_and_lease_reaper",
        "zerodha_session_and_stream_watch",
    }
    assert set(MCP.TOOLS["ai_os_routine_test"]["inputSchema"]["properties"]["routine_key"]["enum"]) == expected


def test_api_server_imports_in_launchd_direct_module_mode_without_external_calls(monkeypatch):
    server_path = RUNTIME_ROOT / "api" / "ai_os_api_server.py"
    spec = importlib.util.spec_from_file_location(
        "ai_os_api_server_launchd_phase2_contract", server_path
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    with patch("urllib.request.urlopen") as provider_call, patch("subprocess.run") as process_call:
        spec.loader.exec_module(module)
    provider_call.assert_not_called()
    process_call.assert_not_called()
    assert module.ModelFabric.__name__ == "ModelFabric"
    assert module.DoctorRuntime.__name__ == "DoctorRuntime"
    assert module.RoutineRuntime.__name__ == "RoutineRuntime"


def test_daemon_dispatches_only_materialized_scheduled_routines_under_a_lease(monkeypatch):
    candidate = {
        "schedule_run_id": 41, "schedule_key": "routine-daily-system-health",
        "due_at": "2026-09-05T05:30:00+05:30", "task_id": 42,
        "inbox_item_id": 43, "owner_agent": "Jarvis",
        "skill_key": "daily_system_health_routine", "routine_key": "daily_system_health",
        "trigger_kind": "schedule",
    }
    checkpoints: list[tuple] = []
    finishes: list[tuple] = []

    class Lease:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def checkpoint(self, *args, **kwargs):
            checkpoints.append((args, kwargs))

        def finish(self, *args):
            finishes.append(args)

    class LeaseRuntime:
        def claim(self, task_id, owner_agent):
            assert (task_id, owner_agent) == (42, "Jarvis")
            return Lease()

    class ScheduledRoutine:
        def run(self, routine_key, **kwargs):
            assert routine_key == "daily_system_health"
            assert kwargs["trigger_kind"] == "schedule"
            assert kwargs["payload"] == {"due_at": "2026-09-05T00:00:00.000000Z"}
            return {"run_id": 77, "run_key": "routine-fixture", "status": "completed"}

    monkeypatch.setattr(daemon, "_scheduled_routine_candidates", lambda _limit: ("ready", [candidate]))
    monkeypatch.setattr(daemon, "lease_runtime", lambda: LeaseRuntime())
    monkeypatch.setattr(daemon, "_scheduled_routine_runtime", lambda: ScheduledRoutine())
    monkeypatch.setattr(
        daemon, "_record_scheduled_routine_result",
        lambda _candidate, _result, failed: "agent.routine_runs:77",
    )
    result = daemon.dispatch_materialized_routine_tasks(10)
    assert result["status"] == "success"
    assert checkpoints == [(("routine_dispatch", "ANALYZING"), {"side_effect": True})]
    assert finishes == [("needs_review", "agent.routine_runs:77")]
    assert result["broker_write_allowed"] is False

    monkeypatch.setattr(daemon, "lease_runtime", lambda: None)
    blocked = daemon.dispatch_materialized_routine_tasks(10)
    assert blocked["status"] == "blocked"


def test_daemon_candidate_query_and_materializer_never_synthesize_event_runs(monkeypatch):
    statements: list[str] = []

    def rows(sql):
        statements.append(sql)
        return [{"ready": True}] if len(statements) == 1 else []

    monkeypatch.setattr(daemon, "psql_json", rows)
    status, candidates = daemon._scheduled_routine_candidates(10)
    assert status == "ready" and candidates == []
    query = statements[1]
    assert "version.trigger_kind='schedule'" in query
    assert "schedule.enabled=true" in query
    assert "schedule_run.status='materialized'" in query
    assert "research_company_change_monitor" not in query

    monkeypatch.setattr(
        daemon, "psql_json", lambda _sql: [{"result": {"processed": 1, "results": []}}]
    )
    monkeypatch.setattr(
        daemon, "dispatch_materialized_routine_tasks",
        lambda limit: {"status": "idle", "count": 0, "limit": limit},
    )
    materialized = daemon.run_workflow_schedule_materializer(9)
    assert materialized["status"] == "success"
    assert materialized["routine_dispatch"] == {"status": "idle", "count": 0, "limit": 9}


def test_blocked_routine_dispatch_prevents_generic_worker_claim(monkeypatch):
    monkeypatch.setattr(daemon, "process_messages", lambda _limit: [])
    monkeypatch.setattr(
        daemon, "dispatch_materialized_routine_tasks",
        lambda _limit: {"status": "blocked", "count": 0},
    )
    monkeypatch.setattr(daemon, "run_research_case_agent_once", lambda: {"status": "idle"})
    monkeypatch.setattr(daemon, "run_company_research_monitor_once", lambda **_kwargs: {"status": "idle"})
    with patch.object(daemon, "run_once") as generic_worker:
        result = daemon.daemon_pass(3, 3, graph_control_enabled=False)
    generic_worker.assert_not_called()
    assert result["worker"]["status"] == "blocked"


def test_launchd_payload_copies_phase2_runtime_dependencies():
    source = (RUNTIME_ROOT / "scripts" / "start_ai_office_live.sh").read_text()
    for name in ("agent_model_fabric.py", "doctor_runtime.py", "routine_runtime.py"):
        assert f'api/{name}" "${{AIOS_SERVICE_DIR}}/api/{name}' in source
    for name in ("ai_os_doctor.py", "run_ai_os_routine.py", "index_obsidian_vault.py", "runtime_executables.py"):
        assert f'scripts/{name}" "${{AIOS_SERVICE_DIR}}/scripts/{name}' in source
