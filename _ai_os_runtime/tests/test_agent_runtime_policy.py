"""Observable policy, clock, dependency and receipt behavior on isolated Postgres."""
import json
from uuid import uuid4

import pytest

from test_agent_runtime_postgres import database, job, expire
from _ai_os_runtime.api.agent_runtime import AgentRuntime, literal, token_hash


def test_snapshot_is_complete_immutable_and_uses_canonical_profile(job):
    execute, _, name, agent, task, runtime = job
    lease = runtime.claim(task, name)
    snapshot = json.loads(execute(f"SELECT policy_snapshot FROM agent.task_leases WHERE id={lease.claim['lease_id']}"))
    assert snapshot['agent_id'] == agent
    assert snapshot['agent_name'] == name
    assert snapshot['permission_level'] == 'read_only'
    assert snapshot['allowed_clients'] == []
    assert snapshot['broker_write_allowed'] is False
    assert {'role_version', 'policy_version', 'workspace_key', 'cost_policy', 'model_assignment'} <= snapshot.keys()
    execute(f"UPDATE agent.profiles SET role_version=2 WHERE id={agent}")
    assert json.loads(execute(f"SELECT policy_snapshot FROM agent.task_leases WHERE id={lease.claim['lease_id']}")) == snapshot
    with pytest.raises(Exception, match='immutable'):
        execute(f"UPDATE agent.task_leases SET policy_snapshot='{{}}' WHERE id={lease.claim['lease_id']}")


def test_dependency_cycle_and_scope_rejected(job):
    execute, _, name, _, task, _ = job
    second = execute(f"INSERT INTO agent.tasks(title,objective,owner_agent) VALUES('second','synthetic',{literal(name)}) RETURNING id")
    third = execute(f"INSERT INTO agent.tasks(title,objective,owner_agent) VALUES('third','synthetic',{literal(name)}) RETURNING id")
    execute(f"INSERT INTO agent.task_dependencies VALUES({task},{second}),({second},{third})")
    with pytest.raises(Exception, match='cycle'):
        execute(f"INSERT INTO agent.task_dependencies VALUES({third},{task})")
    execute(f"UPDATE agent.tasks SET client_id=123 WHERE id={third}")
    with pytest.raises(Exception, match='cross-scope'):
        execute(f"INSERT INTO agent.task_dependencies VALUES({task},{third})")


def test_owner_class_and_client_scope_fail_closed(job):
    execute, _, name, agent, task, runtime = job
    execute(f"UPDATE agent.tasks SET task_class='arbitrary_shell' WHERE id={task}")
    assert runtime.claim(task, name) is None
    execute(f"UPDATE agent.tasks SET task_class='general',client_id=123 WHERE id={task}")
    assert runtime.claim(task, name) is None
    execute(f"UPDATE agent.tasks SET client_id=NULL,owner_agent='Unmapped specialist' WHERE id={task}")
    assert runtime.claim(task, name) is None
    execute(f"UPDATE agent.tasks SET owner_agent={literal(name)} WHERE id={task}")
    assert runtime.claim(task, name)


def test_configurable_clock_idle_cadence_and_drain(job):
    execute, _, name, _, task, runtime = job
    try:
        execute("UPDATE agent.runtime_settings SET active_heartbeat_seconds=1,idle_heartbeat_seconds=2,lease_seconds=3")
        idle = runtime.idle()
        assert idle['next_heartbeat_seconds'] == 2
        lease = runtime.claim(task, name)
        assert lease.claim['heartbeat_seconds'] == 1
        age = float(execute(f"SELECT extract(epoch FROM expires_at-heartbeat_at) FROM agent.task_leases WHERE id={lease.claim['lease_id']}"))
        assert age == 3
        with pytest.raises(Exception, match='active workers'):
            runtime.idle()
        execute("UPDATE agent.runtime_settings SET claim_mode='draining'")
        lease.finish('paused')
        runtime.control(task, 'resume')
        assert AgentRuntime(execute).claim(task, name) is None
        assert runtime.idle()['shutdown_requested'] is True
    finally:
        execute("UPDATE agent.runtime_settings SET active_heartbeat_seconds=15,idle_heartbeat_seconds=60,lease_seconds=45,claim_mode='enabled'")


def test_recorded_output_reconciles_without_replaying(job):
    execute, _, name, _, task, runtime = job
    lease = runtime.claim(task, name)
    step = lease.checkpoint('artifact', 'WRITING', side_effect=True)
    receipt = runtime._call('record_runtime_receipt', runtime.worker_id, lease.claim['lease_id'], token_hash(lease.token),
                            step['step_id'], 'final', 'artifact:synthetic', 'a'*64, '[]')
    assert receipt['content_hash'] == 'a'*64
    with pytest.raises(Exception, match='conflict'):
        runtime._call('record_runtime_receipt', runtime.worker_id, lease.claim['lease_id'], token_hash(lease.token),
                     step['step_id'], 'final', 'artifact:synthetic', 'b'*64, '[]')
    expire(execute, lease)
    runtime.reap()
    result = json.loads(execute(f"SELECT agent.reconcile_runtime_receipts({task})"))
    assert result['replayed_work'] is False and result['status'] == 'needs_review'
    assert AgentRuntime(execute).claim(task, name) is None


def test_unknown_events_and_illegal_reactivation_rejected(job):
    execute, _, name, _, task, runtime = job
    with pytest.raises(Exception, match='unknown runtime event'):
        execute("SELECT agent.append_runtime_event(NULL,NULL,NULL,NULL,'anything','READING')")
    lease = runtime.claim(task, name)
    lease.finish('cancelled')
    with pytest.raises(Exception, match='illegal task state'):
        execute(f"BEGIN; SELECT set_config('aios.runtime_task','{task}',true); UPDATE agent.tasks SET status='in_progress' WHERE id={task}; COMMIT")
    with pytest.raises(Exception, match='illegal lease state'):
        execute(f"UPDATE agent.task_leases SET status='ACTIVE' WHERE id={lease.claim['lease_id']}")
    assert execute("SELECT agent.runtime_transition_allowed('execution','POLICY_CHECKED','ROUTED')") == 'false'
