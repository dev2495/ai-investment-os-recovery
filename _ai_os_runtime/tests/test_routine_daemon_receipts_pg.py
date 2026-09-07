"""Regression for committed projection UPDATE being parsed as raw JSON."""
import os
import pytest
from _ai_os_runtime.tests.test_phase2_operator_integration import daemon


def test_daemon_routine_statement_encodes_committed_receipts(monkeypatch):
    psycopg = pytest.importorskip('psycopg')
    from _ai_os_runtime.tests.phase2_runtime_stress import validate_admin_dsn, _assert_private_test_server
    dsn = os.environ.get('AI_OS_TEST_PG_DSN')
    if not dsn:
        pytest.skip('disposable PostgreSQL required')
    params = validate_admin_dsn(dsn)
    with psycopg.connect(dsn, autocommit=True) as connection:
        _assert_private_test_server(connection, params['host'])
        connection.execute("SET client_encoding='UTF8'")
        connection.execute('CREATE TEMP TABLE routine_projection_receipt(run_key text, status text)')
        monkeypatch.setattr(daemon, 'psql_text', lambda sql: connection.execute(sql).fetchone()[0])
        service = daemon._scheduled_routine_runtime()
        assert service.statement("INSERT INTO routine_projection_receipt VALUES('research-company-1','pending')") == []
        result = service.statement("UPDATE routine_projection_receipt SET status='projected' WHERE run_key='research-company-1' RETURNING run_key")
        assert result == [{'run_key':'research-company-1'}]
        assert connection.execute('SELECT status FROM routine_projection_receipt').fetchone()[0] == 'projected'
        assert service.statement("SELECT jsonb_build_object('status','completed') AS result") == [{'result':{'status':'completed'}}]
        assert service.statement("UPDATE routine_projection_receipt SET status='projected' WHERE false RETURNING run_key") == []
        doctor = service.doctor_factory()
        assert doctor.statement("SELECT 12 AS id") == [{'id':12}]
