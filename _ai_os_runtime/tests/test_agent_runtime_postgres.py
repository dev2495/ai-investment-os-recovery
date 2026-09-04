"""Real PostgreSQL ownership/expiry tests; never connect to production.

Run with AI_OS_TEST_PG_DSN='host=/private/tmp/... user=phase2_test dbname=postgres'.
Creates a uniquely named synthetic database; teardown drops only that exact DB.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
from pathlib import Path
import re
import threading
from uuid import uuid4

import pytest

from _ai_os_runtime.api.agent_runtime import AgentRuntime, LeaseSession, fence_sql, token_hash

SQL_ROOT = Path(__file__).resolve().parents[1] / "postgres" / "init"


@pytest.fixture(scope="module")
def database():
    dsn = os.environ.get("AI_OS_TEST_PG_DSN")
    if not dsn:
        pytest.skip("isolated PostgreSQL DSN not configured")
    psycopg = pytest.importorskip("psycopg")
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    from psycopg import sql
    settings = conninfo_to_dict(dsn)
    if not settings.get("host", "").startswith("/private/tmp/aios-phase2-pg.") or settings.get("user") != "phase2_test":
        pytest.fail("refusing non-synthetic PostgreSQL target")
    dbname = "phase2_test_" + uuid4().hex
    admin = psycopg.connect(dsn, autocommit=True)
    admin.execute(sql.SQL("CREATE DATABASE {} ENCODING 'UTF8'").format(sql.Identifier(dbname)))
    test_dsn = make_conninfo(dsn, dbname=dbname)

    def execute(statement: str):
        with psycopg.connect(test_dsn, autocommit=True) as conn:
            cursor = conn.execute(statement)
            value = None
            while True:
                if cursor.description:
                    value = cursor.fetchone()[0]
                if not cursor.nextset():
                    break
            if isinstance(value, (dict, list)):
                return json.dumps(value, default=str)
            return str(value).lower() if isinstance(value, bool) else str(value) if value is not None else ""

    execute("CREATE SCHEMA agent")
    # Use original checked-in DDL, not an invented replacement task schema.
    for filename, table in [("002_intelligence_os.sql","model_routes"), ("007_agent_profiles.sql","profiles"),
                            ("002_intelligence_os.sql","tasks"), ("002_intelligence_os.sql","approvals")]:
        source = (SQL_ROOT / filename).read_text()
        ddl = re.search(rf"CREATE TABLE IF NOT EXISTS agent\.{table} \([\s\S]*?\n\);", source)
        assert ddl
        execute(ddl.group())
    execute("ALTER TABLE agent.profiles ADD COLUMN display_title text")
    migration = (SQL_ROOT / "256_agent_runtime_leases_v1.sql").read_text()
    execute(migration)
    # Reapply proves non-destructive migration idempotence.
    execute(migration)
    for name in ("257_agent_runtime_policy_events_v1.sql",):
        extension = (SQL_ROOT / name).read_text()
        execute(extension)
        execute(extension)
    yield execute, test_dsn
    assert re.fullmatch(r"phase2_test_[a-f0-9]{32}", dbname)
    admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(dbname)))
    admin.close()


@pytest.fixture
def job(database):
    execute, dsn = database
    name = "Synthetic Analyst " + uuid4().hex
    agent_id = int(execute(f"INSERT INTO agent.profiles(agent_name,department,role_scope) VALUES ('{name}','research','Synthetic tests only') RETURNING id"))
    task_id = int(execute(f"INSERT INTO agent.tasks(title,objective,owner_agent,recovery_policy) VALUES ('Synthetic task','No real research','{name}','idempotent_read') RETURNING id"))
    runtime = AgentRuntime(execute)
    runtime.register()
    return execute, dsn, name, agent_id, task_id, runtime


def expire(execute, lease):
    execute(f"UPDATE agent.task_leases SET expires_at=clock_timestamp()-interval '1 second' WHERE id={lease.claim['lease_id']}")


def test_two_workers_one_owner(job):
    execute, _, name, _, task, runtime = job
    other = AgentRuntime(execute)
    other.register()
    barrier = threading.Barrier(2)
    def claim(worker):
        barrier.wait()
        return worker.claim(task, name)
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        results = list(pool.map(claim, [runtime, other]))
    assert sum(item is not None for item in results) == 1
    assert execute(f"SELECT count(*) FROM agent.task_leases WHERE task_id={task} AND status='ACTIVE'") == "1"


def test_expiry_requeues_read_and_fences_late_worker(job):
    execute, _, name, _, task, runtime = job
    lease = runtime.claim(task, name)
    lease.checkpoint("read", "READING")
    expire(execute, lease)
    result = runtime.reap()
    assert result["requeued"] >= 1
    other = AgentRuntime(execute)
    replacement = other.claim(task, name)
    assert replacement and replacement.claim["attempt"] == 2
    with pytest.raises(Exception, match="lease ownership lost"):
        runtime.heartbeat(lease.claim["lease_id"], lease.token, state="WRITING")
    assert execute(f"SELECT count(*) FROM agent.task_leases WHERE task_id={task} AND status='ACTIVE'") == "1"


def test_expiry_after_side_effect_never_replays(job):
    execute, _, name, _, task, runtime = job
    lease = runtime.claim(task, name)
    lease.checkpoint("write_artifact", "WRITING", side_effect=True)
    expire(execute, lease)
    runtime.reap()
    assert execute(f"SELECT status FROM agent.tasks WHERE id={task}") == "blocked"
    assert AgentRuntime(execute).claim(task, name) is None


def test_committed_output_survives_worker_loss(job):
    execute, _, name, _, task, runtime = job
    lease = runtime.claim(task, name)
    with lease:
        lease.checkpoint("output", "WRITING", side_effect=True)
        execute(fence_sql(f"UPDATE agent.tasks SET status='needs_review',output_note_path='synthetic/output.md' WHERE id={task}"))
    expire(execute, lease)
    runtime.reap()
    assert execute(f"SELECT status FROM agent.tasks WHERE id={task}") == "needs_review"
    assert execute(f"SELECT runtime_state FROM agent.tasks WHERE id={task}") == "WAITING_FOR_APPROVAL"
    assert AgentRuntime(execute).claim(task, name) is None


def test_wrong_owner_token_and_illegal_terminal_heartbeat(job):
    execute, _, name, _, task, runtime = job
    lease = runtime.claim(task, name)
    with pytest.raises(Exception, match="ownership lost"):
        runtime.heartbeat(lease.claim["lease_id"], "x"*64)
    with pytest.raises(Exception, match="terminal"):
        runtime.heartbeat(lease.claim["lease_id"], lease.token, state="COMPLETED")
    with pytest.raises(Exception, match="self-validate"):
        lease.finish("completed", "synthetic-receipt")
    assert token_hash(lease.token) in execute(f"SELECT token_hash FROM agent.task_leases WHERE task_id={task}")
    assert lease.token not in repr(lease)


def test_duplicate_heartbeat_does_not_extend_lease(job):
    execute, _, name, _, task, runtime = job
    lease = runtime.claim(task, name)
    request = str(uuid4())
    first = runtime.heartbeat(lease.claim["lease_id"], lease.token, state="READING", request_key=request)
    duplicate = runtime.heartbeat(lease.claim["lease_id"], lease.token, state="READING", request_key=request)
    assert duplicate["duplicate"] is True
    assert duplicate["expires_at"] == first["expires_at"]
    assert execute(f"SELECT count(*) FROM agent.worker_heartbeats WHERE request_key='{request}'") == "1"


def test_transaction_rollback_releases_claim(job):
    execute, dsn, name, agent, task, runtime = job
    import psycopg
    with psycopg.connect(dsn) as conn:
        conn.execute("SELECT agent.claim_runtime_task(%s,%s,%s,%s,false)", (runtime.worker_id, task, agent, "f"*64))
        conn.rollback()
    assert execute(f"SELECT status FROM agent.tasks WHERE id={task}") == "queued"
    assert AgentRuntime(execute).claim(task, name) is not None


def test_legacy_update_and_managed_write_fence(job):
    execute, _, name, _, task, runtime = job
    execute(f"UPDATE agent.tasks SET evidence='[]'::jsonb WHERE id={task}")
    lease = runtime.claim(task, name)
    with pytest.raises(Exception, match="fenced"):
        execute(f"UPDATE agent.tasks SET status='completed' WHERE id={task}")
    with lease:
        execute(fence_sql(f"UPDATE agent.tasks SET evidence='[]'::jsonb WHERE id={task}"))


def test_dependency_and_approval_gates_preserved(job):
    execute, _, name, _, task, runtime = job
    execute(f"UPDATE agent.tasks SET approval_required=true WHERE id={task}")
    assert runtime.claim(task, name) is None
    execute(f"INSERT INTO agent.approvals(task_id,approval_type,title,owner_agent,status) VALUES({task},'synthetic','Test','{name}','approved')")
    parent = execute(f"INSERT INTO agent.tasks(title,objective,owner_agent) VALUES('Parent','test','{name}') RETURNING id")
    execute(f"INSERT INTO agent.task_dependencies VALUES({task},{parent})")
    assert runtime.claim(task, name) is None
    execute(f"UPDATE agent.tasks SET status='completed' WHERE id={parent}")
    assert runtime.claim(task, name) is not None


def test_pause_at_boundary_and_resume(job):
    from _ai_os_runtime.api.agent_runtime import TaskControl
    execute, _, name, _, task, runtime = job
    lease = runtime.claim(task, name)
    runtime.control(task, "pause")
    with pytest.raises(TaskControl):
        lease.checkpoint("read", "READING")
    assert execute(f"SELECT status FROM agent.tasks WHERE id={task}") == "paused"
    runtime.control(task, "resume")
    assert execute(f"SELECT status FROM agent.tasks WHERE id={task}") == "queued"
    assert AgentRuntime(execute).claim(task, name) is not None


def test_identity_immutable_and_presence_never_faked(job):
    execute, _, name, agent, task, runtime = job
    key = execute(f"SELECT agent_key FROM agent.profiles WHERE id={agent}")
    execute(f"UPDATE agent.profiles SET display_title='Renamed title' WHERE id={agent}")
    assert execute(f"SELECT agent_key FROM agent.profiles WHERE id={agent}") == key
    with pytest.raises(Exception, match="immutable"):
        execute(f"UPDATE agent.profiles SET agent_key='different' WHERE id={agent}")
    assert execute(f"SELECT has_live_lease FROM agent.v_runtime_presence WHERE agent_id={agent}") == "false"
    lease = runtime.claim(task, name)
    assert execute(f"SELECT has_live_lease FROM agent.v_runtime_presence WHERE agent_id={agent}") == "true"
    expire(execute, lease)
    assert execute(f"SELECT state FROM agent.v_runtime_presence WHERE agent_id={agent}") == "STALE"


def test_event_immutability(job):
    execute, _, name, _, task, runtime = job
    runtime.claim(task, name)
    with pytest.raises(Exception, match="append-only"):
        execute(f"UPDATE agent.task_events SET state='COMPLETED' WHERE task_id={task}")
    assert execute(f"SELECT count(*) FROM agent.task_events WHERE task_id={task}") == "1"


def test_worker_and_agent_parallelism_caps(job):
    execute, _, name, agent, task, runtime = job
    runtime.claim(task, name)
    second_task = int(execute(f"INSERT INTO agent.tasks(title,objective,owner_agent) VALUES('Second','test','{name}') RETURNING id"))
    assert runtime.claim(second_task, name) is None
    assert AgentRuntime(execute).claim(second_task, name) is None
