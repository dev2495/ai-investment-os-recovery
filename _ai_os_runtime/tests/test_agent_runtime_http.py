"""Real HTTP + isolated PostgreSQL tests, including replay and auth boundaries."""
from __future__ import annotations

from contextlib import contextmanager
from http.server import ThreadingHTTPServer
import json
import threading
import urllib.error
import urllib.request
from uuid import uuid4

import pytest

from test_agent_runtime_postgres import database, job, expire
from _ai_os_runtime.api import ai_os_api_server as server
from _ai_os_runtime.api.agent_runtime import AgentRuntime
from _ai_os_runtime.api.agent_runtime_api import RuntimeAPI, RuntimeRequestError, overlay_office_presence


@contextmanager
def live_api(monkeypatch, execute):
    api = RuntimeAPI(execute)
    monkeypatch.setattr(server, "RUNTIME_API", api)
    monkeypatch.setattr(server, "OPERATOR_TOKEN", "synthetic-operator-only")
    monkeypatch.setattr(server, "ALLOW_TOKENLESS_LOOPBACK", False)
    http = ThreadingHTTPServer(("127.0.0.1", 0), server.AiOsApiHandler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{http.server_port}", api
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=2)


def request(base, path, payload=None, *, authorized=True):
    headers = {"Authorization": "Bearer synthetic-operator-only"} if authorized else {}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base+path, data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
    return urllib.request.urlopen(req, timeout=5)


def test_http_auth_ownership_and_no_secret_echo(job, monkeypatch):
    execute, _, name, agent, task, runtime = job
    lease = runtime.claim(task, name)
    body = {"worker_id": runtime.worker_id, "lease_id": lease.claim["lease_id"], "lease_token": lease.token,
            "request_key": str(uuid4()), "presence_state": "READING"}
    with live_api(monkeypatch, execute) as (base, _):
        with pytest.raises(urllib.error.HTTPError) as failure:
            request(base, f"/api/v1/agents/{agent}/heartbeat", body, authorized=False)
        assert failure.value.code == 403
        monkeypatch.setattr(server, "ALLOW_TOKENLESS_LOOPBACK", True)
        # Internal heartbeats still require auth even if UI loopback is allowed.
        with pytest.raises(urllib.error.HTTPError) as failure:
            request(base, f"/api/v1/agents/{agent}/heartbeat", body, authorized=False)
        assert failure.value.code == 403
        result = json.load(request(base, f"/api/v1/agents/{agent}/heartbeat", body))
        assert result["accepted"] is True
        assert lease.token not in json.dumps(result)
        with pytest.raises(urllib.error.HTTPError) as failure:
            request(base, f"/api/v1/agents/{agent+10000}/heartbeat", body)
        assert failure.value.code == 409
        assert lease.token not in failure.value.read().decode()
        with pytest.raises(urllib.error.HTTPError) as failure:
            request(base, f"/api/v1/agents/{agent}/heartbeat", {**body, "credentials": "forbidden"})
        assert failure.value.code == 400


def test_runtime_snapshot_is_metadata_only_and_reflects_expiry(job):
    execute, _, name, agent, task, runtime = job
    execute(f"UPDATE agent.tasks SET title='PRIVATE TEST PERSON',objective='PRIVATE FINANCIAL DATA' WHERE id={task}")
    lease = runtime.claim(task, name)
    api = RuntimeAPI(execute)
    snapshot = api.snapshot()
    serialized = json.dumps(snapshot)
    assert "PRIVATE" not in serialized
    assert lease.token not in serialized and "token_hash" not in serialized
    assert "node_name" not in serialized
    assert next(row for row in snapshot["agents"] if row["agent_id"] == agent)["has_live_lease"] is True
    expire(execute, lease)
    row = next(row for row in api.snapshot()["agents"] if row["agent_id"] == agent)
    assert row["state"] == "STALE" and row["has_live_lease"] is False


def test_sse_resume_and_backpressure_reset(job, monkeypatch):
    execute, _, name, _, task, runtime = job
    lease = runtime.claim(task, name)
    lease.checkpoint("read", "READING")
    first = int(execute(f"SELECT min(id) FROM agent.task_events WHERE task_id={task}"))
    with live_api(monkeypatch, execute) as (base, api):
        with request(base, f"/api/v1/office/events/stream?after_event_id={first}") as response:
            assert response.headers["Content-Type"].startswith("text/event-stream")
            line = response.readline().decode().strip()
            assert line.startswith("id: ") and int(line[4:]) > first
            assert response.readline().decode().strip() == "event: runtime"
            event = json.loads(response.readline().decode()[6:])
            assert event["task_id"] == task and "lease_token" not in event
            last = event["id"]
        assert all(row["id"] > last for row in api.replay(last)["events"])
        assert api.replay(999999999)["reset_required"] is True
        execute(f"SELECT agent.append_runtime_event({task},NULL,NULL,NULL,'synthetic','READING') FROM generate_series(1,201)")
        assert api.replay(0)["reset_required"] is True
        with pytest.raises(urllib.error.HTTPError) as failure:
            request(base, "/api/v1/office/events/stream?after_event_id=0&token=never-in-url")
        assert failure.value.code == 400


def test_http_pause_resume_cancel_and_conflict(job, monkeypatch):
    execute, _, name, _, task, runtime = job
    lease = runtime.claim(task, name)
    lease.finish("paused")
    with live_api(monkeypatch, execute) as (base, _):
        result = json.load(request(base, f"/api/v1/tasks/{task}/resume", {}))
        assert result["action"] == "resume"
        task_result = json.load(request(base, f"/api/v1/tasks/{task}"))
        assert task_result["task"]["status"] == "queued"
        json.load(request(base, f"/api/v1/tasks/{task}/cancel", {}))
        assert execute(f"SELECT status FROM agent.tasks WHERE id={task}") == "cancelled"
        with pytest.raises(urllib.error.HTTPError) as failure:
            request(base, f"/api/v1/tasks/{task}/resume", {})
        assert failure.value.code == 409


def test_missing_runtime_and_historical_activity_fail_closed():
    api = RuntimeAPI(lambda _: "false")
    unavailable = api.snapshot()
    assert unavailable["available"] is False
    result = overlay_office_presence({"agents": [{"agent_name": "Researcher", "presence_state": "executing"}]}, unavailable)
    assert result["agents"][0]["presence_state"] == "UNVERIFIED"
    assert result["agents"][0]["has_live_lease"] is False


def test_null_token_fails_and_rapid_state_flood_is_bounded(job):
    execute, _, name, _, task, runtime = job
    lease = runtime.claim(task, name)
    with pytest.raises(Exception, match="ownership lost"):
        execute(f"SELECT agent.assert_runtime_lease('{runtime.worker_id}',{lease.claim['lease_id']},NULL)")
    runtime.heartbeat(lease.claim["lease_id"], lease.token, state="READING")
    for state in ["WRITING", "ANALYZING", "READING"]:
        assert runtime.heartbeat(lease.claim["lease_id"], lease.token, state=state)["accepted"] is False
    execute(f"UPDATE agent.workers SET shutdown_requested=true WHERE id='{runtime.worker_id}'")
    assert runtime.heartbeat(lease.claim["lease_id"], lease.token)["shutdown_requested"] is True


def test_idle_worker_can_return_without_identity_duplication(job):
    execute, _, _, _, _, runtime = job
    execute(f"UPDATE agent.workers SET last_heartbeat_at=now()-interval '4 minutes',status='STALE' WHERE id='{runtime.worker_id}'")
    runtime.register()
    assert execute(f"SELECT status FROM agent.workers WHERE id='{runtime.worker_id}'") == "IDLE"
    assert execute(f"SELECT count(*) FROM agent.workers WHERE id='{runtime.worker_id}'") == "1"
