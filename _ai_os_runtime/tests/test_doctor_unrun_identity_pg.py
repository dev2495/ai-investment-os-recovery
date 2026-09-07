import os
from pathlib import Path
from uuid import uuid4
import pytest


def test_twenty_one_unrun_checks_retain_identity_without_health_claim():
    psycopg = pytest.importorskip('psycopg')
    from psycopg.conninfo import make_conninfo
    from _ai_os_runtime.tests.phase2_runtime_stress import validate_admin_dsn, _assert_private_test_server
    from _ai_os_runtime.tests.test_agent_os_acceptance_contracts_pg import _install_core_ledger
    dsn = os.environ.get('AI_OS_TEST_PG_DSN')
    if not dsn:
        pytest.skip('disposable PostgreSQL required')
    params = validate_admin_dsn(dsn)
    name = 'doctor_unrun_' + uuid4().hex[:12]
    sql_root = Path(__file__).resolve().parents[1] / 'postgres/init'
    with psycopg.connect(dsn, autocommit=True) as admin:
        _assert_private_test_server(admin, params['host'])
        admin.execute(f'CREATE DATABASE {name}')
        try:
            with psycopg.connect(make_conninfo(dsn,dbname=name),autocommit=True) as c:
                c.execute("SET client_encoding='UTF8'")
                _install_core_ledger(c)
                c.execute('CREATE SCHEMA ops')
                source = (sql_root/'260_ai_os_doctor_and_routines_v1.sql').read_text()
                c.execute(source[source.index('CREATE TABLE IF NOT EXISTS ops.doctor_check_registry'):source.index('-- Versioned routines.')])
                # The real migration seeds all 21 registry entries.
                assert c.execute('SELECT count(*) FROM ops.doctor_check_registry').fetchone()[0] == 21
                fix = (sql_root/'266_doctor_unrun_identity_v1.sql').read_text()
                c.execute(fix)
                c.execute(fix)
                assert c.execute("SELECT count(*) FROM ops.v_doctor_latest WHERE check_key IS NOT NULL AND component IS NOT NULL AND status='not_run' AND observed_at IS NULL").fetchone()[0] == 21
                assert c.execute("SELECT count(*) FROM ops.v_doctor_latest WHERE status='passed'").fetchone()[0] == 0
        finally:
            admin.execute(f'DROP DATABASE {name} WITH (FORCE)')
