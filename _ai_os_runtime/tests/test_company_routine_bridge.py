"""Stored-event bridge: real PostgreSQL transactions and restart publication."""
import os
from pathlib import Path
from uuid import uuid4

import pytest

from _ai_os_runtime.api.routine_runtime import RoutineRuntime
from _ai_os_runtime.tests.test_routine_runtime import FakeRoutineDatabase


def test_disabled_bridge_never_materializes():
    db = FakeRoutineDatabase(enabled=False)
    result = RoutineRuntime(db.query, db.statement).dispatch_company_events()
    assert result['status'] == 'disabled'
    assert db.statements == []


def test_publication_failure_is_restart_retryable():
    db = FakeRoutineDatabase()
    original = db.query
    pending = [{'run_key': 'stable-run', 'artifact': {'model_calls': 0}}]
    db.query = lambda sql: pending if 'company_outbox' in sql else original(sql)
    statements = []
    def statement(sql):
        statements.append(sql)
        if 'complete_company' in sql:
            pending.clear()
        return []
    def failed(*args):
        raise OSError('SSD unavailable')
    assert RoutineRuntime(db.query, statement, artifact_writer=failed).dispatch_company_events()['status'] == 'partial'
    writes = []
    def writer(key, run, artifact):
        writes.append((key, run, artifact))
        return {'path': '/Volumes/Devarsh SSD/AI OS Data/artifacts/routines/research_company_change_monitor/stable-run.json', 'sha256': 'a'*64}
    restarted = RoutineRuntime(db.query, statement, artifact_writer=writer)
    assert restarted.dispatch_company_events()['count'] == 1
    assert restarted.dispatch_company_events()['count'] == 0
    assert len(writes) == 1


def test_bridge_postgres_scope_exact_once_and_projection():
    psycopg = pytest.importorskip('psycopg')
    dsn = os.environ.get('AI_OS_TEST_PG_DSN')
    if not dsn:
        pytest.skip('disposable PostgreSQL required')
    from _ai_os_runtime.tests.phase2_runtime_stress import validate_admin_dsn, _assert_private_test_server
    from _ai_os_runtime.tests.test_agent_os_acceptance_contracts_pg import _install_core_ledger
    from psycopg.conninfo import make_conninfo
    from psycopg.rows import dict_row
    params = validate_admin_dsn(dsn)
    name = 'routine_bridge_' + uuid4().hex[:12]
    root = Path(__file__).resolve().parents[1] / 'postgres/init'
    with psycopg.connect(dsn, autocommit=True) as admin:
        _assert_private_test_server(admin, params['host'])
        admin.execute(f'CREATE DATABASE {name}')
        try:
            with psycopg.connect(make_conninfo(dsn, dbname=name), autocommit=True, row_factory=dict_row) as c:
                c.execute("SET client_encoding='UTF8'")
                _install_core_ledger(c)
                c.execute('CREATE SCHEMA agent; CREATE SCHEMA research')
                c.execute("CREATE TABLE agent.routine_definitions(routine_key text primary key,current_version int,control_state text,schedule_key text)")
                c.execute("CREATE TABLE agent.routine_versions(routine_key text,version int,trigger_kind text,cost_budget_usd numeric,PRIMARY KEY(routine_key,version))")
                c.execute('CREATE TABLE agent.workflow_schedules(schedule_key text,enabled boolean)')
                source = (root/'260_ai_os_doctor_and_routines_v1.sql').read_text()
                c.execute(source[source.index('CREATE TABLE IF NOT EXISTS agent.routine_runs'):source.index('CREATE INDEX IF NOT EXISTS idx_routine_runs_status_time')])
                c.execute(source[source.index('CREATE OR REPLACE FUNCTION agent.start_routine_run'):source.index('CREATE OR REPLACE FUNCTION agent.control_routine')])
                c.execute("CREATE TABLE research.watchlists(id bigint primary key,watchlist_key text,status text)")
                c.execute("CREATE TABLE research.watchlist_items(id bigint primary key,watchlist_id bigint,symbol text,exchange text,status text,metadata jsonb)")
                c.execute("CREATE TABLE research.company_research_updates(id bigint primary key,watchlist_item_id bigint,symbol text,exchange text,source_kind text,source_identifier text,evidence jsonb,update_key text,update_type text,source_url text,title text,summary text,effective_at timestamptz,decision_impact text)")
                migration = (root/'264_company_routine_event_bridge_v1.sql').read_text()
                c.execute(migration)
                c.execute(migration)
                c.execute("INSERT INTO agent.routine_definitions VALUES('research_company_change_monitor',1,'disabled','monitor'); INSERT INTO agent.routine_versions VALUES('research_company_change_monitor',1,'event',0); INSERT INTO agent.workflow_schedules VALUES('monitor',false)")
                c.execute("INSERT INTO research.watchlists VALUES(1,'company_research_following','active'),(2,'other','active')")
                c.execute("INSERT INTO research.watchlist_items VALUES(1,1,'WIPRO','NSE','active','{}'),(2,2,'PRIVATE','NSE','active','{}'),(3,1,'OFF','NSE','active','{\"monitoring_enabled\":false}')")
                for i, symbol in [(1,'WIPRO'),(2,'PRIVATE'),(3,'OFF')]:
                    c.execute("INSERT INTO research.company_research_updates VALUES(%s,%s,%s,'NSE','corporate_filing','research.corporate_filings:1','[{\"id\":1}]',%s,'filing','https://example.test','Filing','Stored evidence',now(),'review')",(i,i,symbol,f'filing:{i}'))
                assert c.execute('SELECT agent.materialize_company_routine_events() AS n').fetchone()['n'] == 0
                c.execute("UPDATE agent.routine_definitions SET control_state='enabled'")
                assert c.execute('SELECT agent.materialize_company_routine_events() AS n').fetchone()['n'] == 1
                assert c.execute('SELECT agent.materialize_company_routine_events() AS n').fetchone()['n'] == 0
                output = c.execute('SELECT * FROM agent.company_routine_outputs').fetchone()
                assert output['update_id'] == 1
                assert output['projection_status'] == 'pending'
                assert output['managed_note_path'].endswith(output['event_hash']+'.md')
                assert output['artifact']['model_calls'] == 0
                assert output['artifact']['broker_write_allowed'] is False
                assert c.execute('SELECT count(*) AS n FROM agent.routine_runs').fetchone()['n'] == 1
                path = '/Volumes/Devarsh SSD/AI OS Data/artifacts/routines/research_company_change_monitor/'+output['run_key']+'.json'
                c.execute('SELECT agent.complete_company_routine_artifact(%s,%s,%s)',(output['run_key'],path,'a'*64))
                assert c.execute('SELECT agent.complete_company_routine_artifact(%s,%s,%s) AS result',(output['run_key'],path,'a'*64)).fetchone()['result']['duplicate'] is True
                assert c.execute('SELECT status FROM agent.routine_runs').fetchone()['status'] == 'completed'
                assert not c.execute("SELECT has_function_privilege('public','agent.materialize_company_routine_events(integer)','EXECUTE') AS allowed").fetchone()['allowed']
        finally:
            admin.execute(f'DROP DATABASE {name} WITH (FORCE)')
