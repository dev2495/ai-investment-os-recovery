"""Real legacy INSERT trigger and evaluator under the managed task fence."""
from pathlib import Path
import pytest
from test_agent_runtime_postgres import database
from _ai_os_runtime.api.agent_runtime import AgentRuntime

ROOT = Path(__file__).parents[1] / 'postgres/init'


def test_legacy_provider_gate_keeps_real_tasks_blocked_and_allows_no_provider_fixture(database):
    execute, _ = database
    execute('CREATE SCHEMA IF NOT EXISTS core')
    execute("CREATE TABLE core.v_provider_readiness_board(provider_kind text,provider_key text,route_or_source text)")
    # Model provider decisions remain blocked; use the actual checked-in
    # task evaluator and INSERT trigger, not a replacement gate implementation.
    execute("CREATE FUNCTION core.evaluate_provider_assignment_gate(jsonb) RETURNS jsonb LANGUAGE sql AS $$ SELECT '{\"id\":1,\"assignment_status\":\"blocked\",\"assignment_allowed\":false}'::jsonb $$")
    legacy = next(ROOT.glob('100_*.sql')).read_text()
    execute(legacy.split('CREATE OR REPLACE VIEW agent.v_task_provider_gate_status')[0])
    migration = (ROOT / '265_managed_task_provider_insert_gate_v1.sql').read_text()
    execute(migration)
    execute(migration)
    agent = int(execute("INSERT INTO agent.profiles(agent_name,department,role_scope,permission_level,default_model_route,default_tools) VALUES('Provider test','runtime','synthetic_canary','read_only',NULL,'{}') RETURNING id"))
    execute(f"UPDATE agent.agent_workspaces SET daily_token_budget=0,allowed_task_classes=ARRAY['phase2_canary'],denied_capabilities=ARRAY['model.*','provider.*','broker.*','external.*','client.*','credential.*'] WHERE agent_id={agent}")
    task = int(execute(f"INSERT INTO agent.tasks(title,objective,owner_agent,agent_id,runtime_protocol) VALUES('Real research','Needs a model','Provider test',{agent},'lease_v1') RETURNING id"))
    assert execute(f'SELECT status FROM agent.tasks WHERE id={task}') == 'blocked'
    assert execute(f"SELECT evidence::text LIKE '%overall_status%' FROM agent.tasks WHERE id={task}") == 'true'
    with pytest.raises(Exception, match='fenced runtime operation'):
        execute(f"UPDATE agent.tasks SET evidence='[]' WHERE id={task}")
    context = '{"synthetic":true,"public_fixture_only":true,"model_calls_allowed":false,"provider_calls_allowed":false,"client_writes_allowed":false,"external_writes_allowed":false,"broker_write_allowed":false}'
    fixture = int(execute(f"INSERT INTO agent.tasks(title,objective,owner_agent,agent_id,runtime_protocol,task_class,source_kind,runtime_scope,data_class,approval_required,recovery_policy,runtime_context) VALUES('Canary','Public fixture','Provider test',{agent},'lease_v1','phase2_canary','phase2_live_canary','internal','public',false,'idempotent_read','{context}') RETURNING id"))
    assert execute(f'SELECT status FROM agent.tasks WHERE id={fixture}') == 'queued'
    assert execute(f"SELECT evidence::text LIKE '%governed_provider_free_synthetic_fixture%' FROM agent.tasks WHERE id={fixture}") == 'true'
    # Merely claiming the class must never exempt a model-capable profile.
    execute(f"UPDATE agent.agent_workspaces SET daily_token_budget=100 WHERE agent_id={agent}")
    denied = int(execute(f"INSERT INTO agent.tasks(title,objective,owner_agent,agent_id,runtime_protocol,task_class,source_kind,runtime_scope,data_class,approval_required,recovery_policy,runtime_context) VALUES('Spoof','Model capable','Provider test',{agent},'lease_v1','phase2_canary','phase2_live_canary','internal','public',false,'idempotent_read','{context}') RETURNING id"))
    assert execute(f'SELECT status FROM agent.tasks WHERE id={denied}') == 'blocked'
    execute("CREATE OR REPLACE FUNCTION core.evaluate_provider_assignment_gate(jsonb) RETURNS jsonb LANGUAGE sql AS $$ SELECT '{\"id\":2,\"assignment_status\":\"approval_required\",\"assignment_allowed\":false}'::jsonb $$")
    pending = int(execute(f"INSERT INTO agent.tasks(title,objective,owner_agent,agent_id,runtime_protocol,status) VALUES('Pending','Needs approval','Provider test',{agent},'lease_v1','handoff_pending') RETURNING id"))
    assert execute(f'SELECT status FROM agent.tasks WHERE id={pending}') == 'needs_review'
    worker = AgentRuntime(execute)
    assert worker.claim(task, 'Provider test') is None
    assert worker.claim(pending, 'Provider test') is None
    execute("CREATE OR REPLACE FUNCTION core.evaluate_provider_assignment_gate(jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'provider unavailable'; END $$")
    failure = int(execute(f"INSERT INTO agent.tasks(title,objective,owner_agent,agent_id,runtime_protocol,status) VALUES('Failure','Gate unavailable','Provider test',{agent},'lease_v1','handoff_pending') RETURNING id"))
    assert execute(f'SELECT status FROM agent.tasks WHERE id={failure}') == 'blocked'
    assert execute(f"SELECT evidence::text LIKE '%provider_gate_evaluation_failed%' FROM agent.tasks WHERE id={failure}") == 'true'
