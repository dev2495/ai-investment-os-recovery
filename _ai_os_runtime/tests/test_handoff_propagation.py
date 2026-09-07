"""Durable, independently validated research handoffs on disposable PostgreSQL."""
import json
from pathlib import Path
from uuid import uuid4

import pytest

from test_agent_runtime_postgres import database, job, test_handoff_requires_live_owner_cited_receipt_and_independent_validation as run_chain
from _ai_os_runtime.api.agent_collaboration import CollaborationAPI
from _ai_os_runtime.api.agent_charlie import CharlieAPI
from _ai_os_runtime.api.agent_os_policy import Principal
from _ai_os_runtime.api.agent_runtime_api import RuntimeRequestError


def install(execute):
    source = (Path(__file__).parents[1] / 'postgres/init/263_handoff_parent_propagation_v1.sql').read_text()
    execute(source)
    execute(source)


def test_wipro_validated_chain_projects_without_accepting_research(job):
    execute, _, _, sender, parent, _ = job
    install(execute)
    case = int(execute("INSERT INTO research.research_cases(case_key,company_name,ticker,status) VALUES('wipro-handoff','Wipro','WIPRO','review') RETURNING id"))
    execute("INSERT INTO agent.committee_registry VALUES('handoff-review','Research Director review')")
    packet = int(execute("INSERT INTO agent.committee_packets(packet_key,committee_key,title,decision_question,opened_by) VALUES('wipro-handoff','handoff-review','Wipro','Review cited evidence','test') RETURNING id"))
    execute(f"UPDATE agent.tasks SET runtime_context='{{\"research_case_id\":{case},\"committee_packet_id\":{packet}}}' WHERE id={parent}")
    run_chain(job)
    handoff = CollaborationAPI(execute, Principal()).handoffs()[0]
    assert handoff['state'] == 'VALIDATED'
    assert handoff['recovery_action'] is None
    assert len(json.loads(execute(f"SELECT validated_handoffs FROM research.research_cases WHERE id={case}"))) == 1
    assert execute(f"SELECT status FROM research.research_cases WHERE id={case}") == 'review'
    assert execute(f"SELECT packet_status FROM agent.committee_packets WHERE id={packet}") == 'collecting_positions'
    assert execute(f"SELECT metadata->'validated_handoffs' IS NOT NULL FROM agent.committee_packets WHERE id={packet}") == 'true'
    assert execute(f"SELECT runtime_context->'validated_handoffs' IS NOT NULL FROM agent.tasks WHERE id={parent}") == 'true'


def test_redirect_and_exact_blocker_command(job):
    execute, _, name, _, task, runtime = job
    assert runtime.claim(task, name)
    api = CollaborationAPI(execute, Principal())
    result = api.redirect_task(task, {'objective': 'Use primary sources only.', 'source_policy': 'primary_only'})
    assert result['waiting_for_safe_boundary'] is True
    with pytest.raises(RuntimeRequestError):
        api.redirect_task(task, {'objective': 'Change scope', 'source_policy': 'anything'})
    response = CharlieAPI(execute, Principal()).command({
        'request_key': 'blocked:' + uuid4().hex,
        'command': 'Charlie, explain why this task is blocked.', 'context': {'task_id': task},
    })
    assert response['broker_write_allowed'] is False
    assert response['context']['task_id'] == task


def test_restart_recovers_pending_handoff_without_invented_progress(job):
    execute, _, name, sender, parent, runtime = job
    install(execute)
    assert runtime.claim(parent, name)
    recipient = int(execute("INSERT INTO agent.profiles(agent_name,department,role_scope) VALUES('Recovery recipient','research','Synthetic') RETURNING id"))
    api = CollaborationAPI(execute, Principal(agent_id=sender))
    api.create_thread({'thread_key': 'recovery:handoff', 'room_type': 'direct', 'title': 'Recovery'})
    result = api.create_handoff({'request_key': 'recovery:handoff', 'thread_key': 'recovery:handoff',
        'to_agent_id': recipient, 'parent_task_id': parent, 'question': 'Check stored citations.'})
    # A fresh API object/connection reconstructs the same durable child after restart.
    rows = CollaborationAPI(execute, Principal()).handoffs()
    recovered = next(row for row in rows if row['id'] == result['handoff_id'])
    assert recovered['state'] == 'REQUESTED'
    assert recovered['recovery_action'] == 'acknowledge'
    assert recovered['child_task_id'] == result['child_task_id']
    execute(f"UPDATE agent.task_handoffs SET client_id=91 WHERE id={result['handoff_id']}")
    assert all(row['id'] != result['handoff_id'] for row in CollaborationAPI(execute, Principal()).handoffs())
    assert any(row['id'] == result['handoff_id'] for row in CollaborationAPI(execute, Principal(clients=(91,))).handoffs())
