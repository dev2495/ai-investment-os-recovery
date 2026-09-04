"""Process-loss and actual existing worker boundary tests on synthetic PostgreSQL."""
from __future__ import annotations

import json
import multiprocessing
from pathlib import Path
from unittest import mock

import pytest

from test_agent_runtime_postgres import database, job
from _ai_os_runtime.api.agent_runtime import AgentRuntime
from _ai_os_runtime.scripts import run_agent_worker_once as worker
from _ai_os_runtime.mcp_server import ai_os_mcp_server as mcp

def _claim_in_child(dsn, name, task, sender):
    import psycopg
    import threading
    def execute(statement):
        with psycopg.connect(dsn, autocommit=True) as connection:
            return str(connection.execute(statement).fetchone()[0])
    runtime = AgentRuntime(execute)
    lease = runtime.claim(task, name)
    lease.checkpoint("synthetic_read", "READING")
    sender.send((runtime.worker_id, lease.claim["lease_id"]))
    threading.Event().wait(15)


def test_killed_worker_goes_stale_and_only_read_is_reclaimed(job):
    execute, dsn, name, agent, task, _ = job
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_claim_in_child, args=(dsn, name, task, sender))
    process.start()
    try:
        assert receiver.poll(5)
        worker_id, lease_id = receiver.recv()
        process.terminate()
        process.join(timeout=3)
        assert not process.is_alive()
        # Accelerated clock: no 45-second wall sleep or production mutation.
        execute(f"UPDATE agent.task_leases SET expires_at=now()-interval '1 second' WHERE id={lease_id}")
        execute(f"UPDATE agent.workers SET last_heartbeat_at=now()-interval '1 minute' WHERE id='{worker_id}'")
        assert execute(f"SELECT state FROM agent.v_runtime_presence WHERE agent_id={agent}") == "STALE"
        replacement = AgentRuntime(execute)
        replacement.reap()
        claimed = replacement.claim(task, name)
        assert claimed.claim["attempt"] == 2
        assert execute(f"SELECT status FROM agent.workers WHERE id='{worker_id}'") == "STALE"
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=3)
        receiver.close()
        sender.close()


def test_existing_worker_commits_under_real_fence(job):
    # Import the exact module used by the existing worker so its ContextVar is
    # shared; only the expensive/public-provider adapters are synthetic stubs.
    execute, _, name, _, task, _ = job
    runtime = worker.AgentRuntime(execute)
    job_row = {"task_id": task, "title": "Synthetic", "owner_agent": name,
               "source_kind": "employee_activation", "suggested_skill_key": "refresh_dashboard_widget"}
    def completed(*_args):
        worker.psql_text(f"UPDATE agent.tasks SET status='needs_review',output_note_path='synthetic/test.md' WHERE id={task}")
        return {"worker_run": {"id": 1}, "task": {"status": "needs_review"}}
    with (
        mock.patch.object(worker, "lease_runtime", return_value=runtime),
        mock.patch.object(worker, "_psql_text_unfenced", side_effect=execute),
        mock.patch.object(worker, "get_queue", return_value=[job_row]),
        mock.patch.object(worker, "skill_for", return_value={"skill_key": "refresh_dashboard_widget"}),
        mock.patch.object(worker, "routed_agent_for", return_value=name),
        mock.patch.object(worker, "profile_for", return_value={"agent_name": name}),
        mock.patch.object(worker, "context_for", return_value={}),
        mock.patch.object(worker, "execution_envelope_for", return_value={}),
        mock.patch.object(worker, "summary_for", return_value=("Synthetic test only", [])),
        mock.patch.object(worker, "write_note", return_value=Path("synthetic/test.md")),
        mock.patch.object(worker, "complete_job", side_effect=completed),
    ):
        result = worker.run_once(1, False, task)
    assert result["ownership_protocol"] == "lease_v1"
    assert execute(f"SELECT status FROM agent.tasks WHERE id={task}") == "needs_review"
    assert execute(f"SELECT count(*) FROM agent.task_steps WHERE task_id={task} AND side_effect_status='recorded'") == "2"
    assert execute(f"SELECT count(*) FROM agent.task_leases WHERE task_id={task} AND status='ACTIVE'") == "0"


def test_opt_in_is_fail_closed_without_migration(monkeypatch):
    monkeypatch.setattr(worker, "_LEASE_RUNTIME", None)
    monkeypatch.setattr(worker, "RUNTIME_ENV", {"AI_OS_AGENT_LEASE_RUNTIME_ENABLED": "false"})
    with mock.patch.object(worker, "_psql_text_unfenced") as sql:
        assert worker.lease_runtime() is None
        sql.assert_not_called()
    monkeypatch.setattr(worker, "RUNTIME_ENV", {"AI_OS_AGENT_LEASE_RUNTIME_ENABLED": "true"})
    with mock.patch.object(worker, "_psql_text_unfenced", return_value="false"):
        with pytest.raises(RuntimeError, match="migration 256"):
            worker.lease_runtime()


def test_mcp_reuses_authenticated_api_and_requires_operator_instruction(monkeypatch):
    with mock.patch.object(mcp, "post_api_json", return_value={"action": "pause"}) as post:
        with pytest.raises(ValueError, match="Explicit operator"):
            mcp.runtime_task_control({"task_id": 7, "action": "pause"})
        post.assert_not_called()
        result = mcp.runtime_task_control({"task_id": 7, "action": "pause", "operator_confirmed": True})
        post.assert_called_once_with("/api/v1/tasks/7/pause", {}, timeout=15)
        assert json.loads(result["content"][0]["text"])["action"] == "pause"
    monkeypatch.setenv("AI_OS_OPERATOR_TOKEN", "synthetic-not-a-secret")
    assert mcp.api_auth_headers() == {"Authorization": "Bearer synthetic-not-a-secret"}
