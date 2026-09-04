import pytest
from test_agent_runtime_postgres import database, job
from _ai_os_runtime.api.agent_os_policy import Principal, evidence_refs, safe_text
from _ai_os_runtime.api.agent_runtime_api import RuntimeAPI, RuntimeRequestError


def test_shared_snapshot_replay_and_control_exclude_private_task(job):
    execute, _, name, agent, task, runtime = job
    lease = runtime.claim(task, name)
    execute(f"UPDATE agent.tasks SET client_id=901 WHERE id={task}")
    execute(f"SELECT agent.append_runtime_event({task},{agent},NULL,NULL,'state_changed','READING')")
    api = RuntimeAPI(execute)
    assert not any(row['id'] == task for row in api.snapshot()['tasks'])
    assert not any(row['task_id'] == task for row in api.replay(0)['events'])
    with pytest.raises(RuntimeRequestError, match='scope'):
        api.control(task, 'cancel')


def test_principal_never_inherits_other_book_or_client():
    principal = Principal(user_id='synthetic-a', scope='client-test', books=(7,), clients=(1,))
    principal.check_scope({'runtime_scope':'client-test','book_id':7,'client_id':1})
    for row in ({'runtime_scope':'client-test','client_id':2}, {'runtime_scope':'internal'},
                {'runtime_scope':'client-test','book_id':8}):
        with pytest.raises(RuntimeRequestError):
            principal.check_scope(row)
    with pytest.raises(RuntimeRequestError):
        principal.require('broker_order')


def test_messages_reject_credentials_and_arbitrary_evidence_content():
    assert safe_text('Show the source packet') == 'Show the source packet'
    for text in ('access_token=fixture-not-a-secret', 'Bearer synthetic-only', 'password: synthetic-only'):
        with pytest.raises(RuntimeRequestError, match='Credential'):
            safe_text(text)
    assert evidence_refs([{'table':'research.corporate_filings','id':7,'locator':'page 2'}])[0]['id'] == 7
    with pytest.raises(RuntimeRequestError):
        evidence_refs([{'table':'portfolio.clients','id':1,'body':'private'}])
