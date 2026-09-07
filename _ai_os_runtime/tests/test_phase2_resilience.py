"""Observable reconnect and database-delay behavior on disposable PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
import json
import time

import pytest

from test_agent_runtime_postgres import database, job
from test_agent_runtime_http import live_api, request
from _ai_os_runtime.api.agent_runtime import LeaseLost, fence_sql


def test_one_hundred_http_sse_clients_recover_from_future_cursor(job, monkeypatch):
    execute, _, name, _, task, runtime = job
    lease = runtime.claim(task, name)
    lease.checkpoint("read", "READING")
    with live_api(monkeypatch, execute) as (base, api):
        def reconnect(_):
            with request(base, "/api/v1/office/events/stream?after_event_id=999999999") as response:
                assert response.readline().decode().strip() == "event: reset"
                payload = json.loads(response.readline().decode()[6:])
                assert payload["reason"] == "snapshot_required"
            snapshot = api.snapshot()
            assert snapshot["available"] is True
            return payload["cursor"]
        # Respect the server's intentional 16-connection cap; 100 separate
        # clients reconnect in bounded concurrent batches.
        with ThreadPoolExecutor(max_workers=8) as pool:
            cursors = list(pool.map(reconnect, range(100)))
        assert len(cursors) == 100 and min(cursors) > 0


def test_database_lock_timeout_stops_worker_before_next_write(job):
    import psycopg
    execute, dsn, name, _, task, runtime = job
    lease = runtime.claim(task, name)
    lease.claim["heartbeat_seconds"] = 1
    original = runtime.execute
    runtime.execute = lambda sql: original("SET lock_timeout='150ms'; " + sql)
    with psycopg.connect(dsn) as blocker:
        blocker.execute("SELECT id FROM agent.task_leases WHERE id=%s FOR UPDATE", (lease.claim["lease_id"],))
        with lease:
            deadline = time.monotonic() + 4
            while not lease._lost.is_set() and time.monotonic() < deadline:
                time.sleep(0.05)
            with pytest.raises(LeaseLost):
                fence_sql(f"UPDATE agent.tasks SET title='must not write' WHERE id={task}")
        blocker.rollback()
    assert execute(f"SELECT title FROM agent.tasks WHERE id={task}") == "Synthetic task"
