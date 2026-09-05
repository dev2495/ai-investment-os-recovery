"""Focused disposable-PostgreSQL acceptance for migration 262.

No production connection is accepted. The harness creates and drops one
uniquely named database below the private-tmp Phase 2 test cluster.
"""
from __future__ import annotations

import os
import threading
import time
from uuid import uuid4

import pytest

from _ai_os_runtime.tests.phase2_runtime_stress import (
    SQL_ROOT,
    _assert_private_test_server,
    _bootstrap,
    _run_script,
    validate_admin_dsn,
)


EXPECTED_MIGRATIONS = {
    256: ("256_agent_runtime_leases_v1", "3aa19ffced26f4ac3709ade35ec13193a833249ac3f22ae71a2b228ba4d19cd5"),
    257: ("257_agent_runtime_policy_events_v1", "9c02ed6de61e0d9435ed5320a31a4e60eeaaad76f70d88ac38003add031999e5"),
    258: ("258_agent_conversations_handoffs_v1", "b14d772e2b8a964f40ba0fbc792454f4a0819ca1e676ff615e53925a1d55c797"),
    259: ("259_agent_model_fabric_v1", "ff523f10530ee7a58e21943bb1a16ea9dc1abfaf2dbe20a55062bf46e6b41c17"),
    260: ("260_ai_os_doctor_and_routines_v1", "881a28749e8a6e50268ab9ae5b8c69dfea7c6c3cb2b28c84b49485303b143384"),
    261: ("261_charlie_chief_of_staff_v1", "6408acc5b8b256fbd81710471aa98345f6fc685173aedd06a3e48fa5ea5ae055"),
    262: ("262_agent_os_acceptance_contracts_v1", "b83040fb45be68f0ec96f2c57360ec561ef00c35376ad6cda7401cbf41e5470c"),
}


def _install_core_ledger(connection) -> None:
    connection.execute("CREATE SCHEMA core")
    connection.execute(
        """CREATE OR REPLACE FUNCTION core.jsonb_contains_raw_secret(payload JSONB)
        RETURNS BOOLEAN LANGUAGE plpgsql IMMUTABLE AS $$
        DECLARE item RECORD; element JSONB; normalized_key TEXT;
        BEGIN
          IF payload IS NULL THEN RETURN false; END IF;
          IF jsonb_typeof(payload)='object' THEN
            FOR item IN SELECT key,value FROM jsonb_each(payload) LOOP
              normalized_key:=lower(regexp_replace(item.key,'[^a-z0-9]+','_','g'));
              IF normalized_key IN ('api_key','access_token','refresh_token','password',
                'secret','client_secret','private_key','auth_token') THEN RETURN true; END IF;
              IF core.jsonb_contains_raw_secret(item.value) THEN RETURN true; END IF;
            END LOOP;
          ELSIF jsonb_typeof(payload)='array' THEN
            FOR element IN SELECT value FROM jsonb_array_elements(payload) LOOP
              IF core.jsonb_contains_raw_secret(element) THEN RETURN true; END IF;
            END LOOP;
          END IF;
          RETURN false;
        END $$"""
    )
    connection.execute(
        """CREATE TABLE core.schema_migrations(
          migration_number integer PRIMARY KEY,
          migration_key text NOT NULL UNIQUE,
          definition_checksum_sha256 text NOT NULL,
          description text NOT NULL,
          applied_at timestamptz NOT NULL DEFAULT now(),
          applied_by text NOT NULL DEFAULT current_user,
          metadata jsonb NOT NULL DEFAULT '{}',
          CHECK(migration_number>0),
          CHECK(definition_checksum_sha256 ~ '^[0-9a-f]{64}$'),
          CHECK(NOT core.jsonb_contains_raw_secret(metadata)))"""
    )


def _install_acceptance_substrate(connection) -> None:
    connection.execute(
        """CREATE TABLE agent.department_registry(
          department_key text PRIMARY KEY, department_name text NOT NULL,
          status text NOT NULL DEFAULT 'active')"""
    )
    connection.execute(
        """INSERT INTO agent.department_registry(department_key,department_name)
        VALUES('research','Research')"""
    )
    connection.execute(
        """CREATE VIEW agent.v_agent_capability_readiness AS
        SELECT profile.agent_name,true AS tools_ready,'{}'::text[] AS missing_tools
        FROM agent.profiles profile"""
    )
    connection.execute(
        "CREATE TABLE agent.routine_definitions(routine_key text PRIMARY KEY)"
    )
    number = 260
    key, checksum = EXPECTED_MIGRATIONS[number]
    connection.execute(
        """INSERT INTO core.schema_migrations(
          migration_number,migration_key,definition_checksum_sha256,description)
        VALUES(%s,%s,%s,'covered by the dedicated migration-260 acceptance harness')""",
        (number, key, checksum),
    )


def _seed_agent(connection):
    connection.execute(
        """INSERT INTO agent.model_routes(
          route_name,task_class,default_provider,default_model,max_cost_tier,enabled)
        VALUES('acceptance_route','general','local','deterministic','local',true)"""
    )
    agent_id = connection.execute(
        """INSERT INTO agent.profiles(
          agent_name,department,role_scope,default_model_route,max_parallel_tasks)
        VALUES('Acceptance Agent','research','analyst','acceptance_route',1)
        RETURNING id"""
    ).fetchone()[0]
    connection.execute(
        """UPDATE agent.agent_workspaces SET capability_status='READY',
          allowed_task_classes=ARRAY['general'],allowed_scopes=ARRAY['internal'],
          allowed_data_classes=ARRAY['internal'] WHERE agent_id=%s""",
        (agent_id,),
    )
    version_id = connection.execute(
        """INSERT INTO agent.model_binding_versions(
          binding_key,version,selector_kind,selector_value,task_class,primary_route,
          context_budget,max_output_tokens,temperature,route_snapshot,created_by)
        VALUES('acceptance.binding',1,'agent','Acceptance Agent','general',
          'acceptance_route',4096,512,0,'{}','acceptance') RETURNING id"""
    ).fetchone()[0]
    connection.execute(
        """INSERT INTO agent.model_binding_heads(binding_key,version_id,enabled,updated_by)
        VALUES('acceptance.binding',%s,true,'acceptance')""",
        (version_id,),
    )
    worker_id = uuid4()
    connection.execute(
        "SELECT agent.register_runtime_worker(%s,'acceptance-node',1,'acceptance-v1',1)",
        (worker_id,),
    )
    task_id = connection.execute(
        """INSERT INTO agent.tasks(
          title,objective,owner_agent,status,priority,source_kind,source_ref,agent_id,
          runtime_protocol,runtime_state,task_class,recovery_policy,runtime_scope,
          data_class,runtime_context)
        VALUES('Acceptance task','Validate rollout serialization','Acceptance Agent',
          'queued','normal','acceptance','acceptance',%s,'lease_v1',NULL,'general',
          'idempotent_read','internal','internal','{}') RETURNING id""",
        (agent_id,),
    ).fetchone()[0]
    return agent_id, worker_id, task_id, version_id


def _assert_existing_role_version_snapshot(connection) -> None:
    profile_id = connection.execute(
        """INSERT INTO agent.profiles(agent_name,department,role_scope,role_version)
        VALUES('Existing Versioned Agent','research','analyst',7) RETURNING id"""
    ).fetchone()[0]
    connection.execute(
        "DELETE FROM agent.agent_workspaces WHERE agent_id=%s", (profile_id,)
    )
    _run_script(
        connection,
        (SQL_ROOT / "257_agent_runtime_policy_events_v1.sql").read_text(encoding="utf-8"),
    )
    assert connection.execute(
        "SELECT role_version FROM agent.agent_workspaces WHERE agent_id=%s", (profile_id,)
    ).fetchone()[0] == 7
    connection.execute(
        "DELETE FROM agent.agent_workspaces WHERE agent_id=%s", (profile_id,)
    )
    connection.execute("DELETE FROM agent.profiles WHERE id=%s", (profile_id,))


def _assert_ledger_guard(connection, number: int, filename: str) -> None:
    key, checksum = EXPECTED_MIGRATIONS[number]
    connection.execute(
        "UPDATE core.schema_migrations SET definition_checksum_sha256=%s WHERE migration_number=%s",
        ("0" * 64, number),
    )
    statement = (SQL_ROOT / filename).read_text(encoding="utf-8")
    with pytest.raises(Exception, match=f"migration {number} ledger mismatch"):
        _run_script(connection, statement)
    connection.rollback()
    connection.execute(
        """UPDATE core.schema_migrations
        SET migration_key=%s,definition_checksum_sha256=%s WHERE migration_number=%s""",
        (key, checksum, number),
    )


def _assert_raises(connection, statement: str, params=()) -> None:
    with pytest.raises(Exception):
        connection.execute(statement, params)


def _exercise(connection, connect_test) -> None:
    migration = (SQL_ROOT / "262_agent_os_acceptance_contracts_v1.sql").read_text(encoding="utf-8")
    _run_script(connection, migration)
    _run_script(connection, migration)

    rows = connection.execute(
        """SELECT migration_number,migration_key,definition_checksum_sha256
        FROM core.schema_migrations WHERE migration_number BETWEEN 256 AND 262
        ORDER BY migration_number"""
    ).fetchall()
    assert rows == [(number, *EXPECTED_MIGRATIONS[number]) for number in range(256, 263)]
    assert connection.execute(
        "SELECT claim_mode FROM agent.runtime_settings WHERE singleton"
    ).fetchone()[0] == "disabled"

    agent_id, worker_id, task_id, version_id = _seed_agent(connection)
    assert connection.execute(
        "SELECT agent.claim_runtime_task(%s,%s,%s,%s,false)",
        (worker_id, task_id, agent_id, "d" * 64),
    ).fetchone()[0] == {}
    connection.execute(
        """SELECT agent.set_runtime_claim_mode(
          'acceptance-canary-01','disabled','enabled','acceptance','read_only_canary')"""
    )
    snapshot = connection.execute(
        "SELECT agent.runtime_policy_snapshot(%s)", (agent_id,)
    ).fetchone()[0]
    assert snapshot["model_fabric_bindings"][0]["version_id"] == version_id

    event_id = connection.execute(
        """SELECT agent.append_scoped_runtime_event_v2(
          'task_created','queued',%s,%s,'runtime','acceptance','accepted',
          NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'{}','internal_read',
          '{"task_id":1}','{"producer":"acceptance"}',%s,NULL,NULL)""",
        (task_id, agent_id, worker_id),
    ).fetchone()[0]
    projected = connection.execute(
        "SELECT worker_id,entity_ids,metadata FROM agent.v_runtime_events_v1 WHERE event_id=%s",
        (event_id,),
    ).fetchone()
    assert projected == (worker_id, {"task_id": 1}, {"producer": "acceptance"})
    legacy_event_id = connection.execute(
        """SELECT agent.append_scoped_runtime_event(
          'task_created','queued',%s,%s,'runtime','legacy-producer','accepted')""",
        (task_id, agent_id),
    ).fetchone()[0]
    assert connection.execute(
        "SELECT event_id FROM agent.v_runtime_events_v1 WHERE event_id=%s", (legacy_event_id,)
    ).fetchone()[0] == legacy_event_id
    _assert_raises(
        connection,
        """SELECT agent.append_scoped_runtime_event_v2(
          'task_created',NULL,%s,%s,'runtime',NULL,NULL,NULL,NULL,NULL,NULL,NULL,
          NULL,NULL,NULL,'{}','internal_read','{}','{"password":"nope"}')""",
        (task_id, agent_id),
    )

    connection.execute(
        "UPDATE agent.profiles SET role_version=role_version+1 WHERE id=%s", (agent_id,)
    )
    status = connection.execute(
        "SELECT operating_status FROM agent.v_desk_operating_status_v1 WHERE department_key='research'"
    ).fetchone()[0]
    assert status == "PARTIAL"
    claim = connection.execute(
        "SELECT agent.claim_runtime_task(%s,%s,%s,%s,false)",
        (worker_id, task_id, agent_id, "a" * 64),
    ).fetchone()[0]
    assert claim == {}
    connection.execute(
        "UPDATE agent.agent_workspaces SET role_version=(SELECT role_version FROM agent.profiles WHERE id=%s) WHERE agent_id=%s",
        (agent_id, agent_id),
    )
    token_hash = "c" * 64
    lease_claim = connection.execute(
        "SELECT agent.claim_runtime_task(%s,%s,%s,%s,false)",
        (worker_id, task_id, agent_id, token_hash),
    ).fetchone()[0]
    assert lease_claim["model_fabric_bindings"][0]["version_id"] == version_id
    lease_id = lease_claim["lease_id"]
    lease_policy = connection.execute(
        "SELECT policy_snapshot FROM agent.task_leases WHERE id=%s", (lease_id,)
    ).fetchone()[0]
    assert lease_policy["model_fabric_bindings"][0]["version_id"] == version_id
    next_version_id = connection.execute(
        """INSERT INTO agent.model_binding_versions(
          binding_key,version,selector_kind,selector_value,task_class,primary_route,
          context_budget,max_output_tokens,temperature,route_snapshot,created_by)
        VALUES('acceptance.binding',2,'agent','Acceptance Agent','general',
          'acceptance_route',4096,512,0,'{}','acceptance') RETURNING id"""
    ).fetchone()[0]
    connection.execute(
        """UPDATE agent.model_binding_heads SET version_id=%s,updated_by='acceptance'
        WHERE binding_key='acceptance.binding'""",
        (next_version_id,),
    )
    unchanged_lease_policy = connection.execute(
        "SELECT policy_snapshot FROM agent.task_leases WHERE id=%s", (lease_id,)
    ).fetchone()[0]
    assert unchanged_lease_policy["model_fabric_bindings"][0]["version_id"] == version_id
    connection.execute(
        "SELECT agent.finish_runtime_lease(%s,%s,%s,'needs_review','acceptance:receipt')",
        (worker_id, lease_id, token_hash),
    )
    task_id = connection.execute(
        """INSERT INTO agent.tasks(
          title,objective,owner_agent,status,priority,source_kind,source_ref,agent_id,
          runtime_protocol,runtime_state,task_class,recovery_policy,runtime_scope,
          data_class,runtime_context)
        VALUES('Acceptance race task','Validate rollout serialization','Acceptance Agent',
          'queued','normal','acceptance','acceptance-race',%s,'lease_v1',NULL,'general',
          'idempotent_read','internal','internal','{}') RETURNING id""",
        (agent_id,),
    ).fetchone()[0]

    first = connection.execute(
        "SELECT agent.set_runtime_claim_mode('acceptance-drain-001','enabled','draining','acceptance','test_drain')"
    ).fetchone()[0]
    duplicate = connection.execute(
        "SELECT agent.set_runtime_claim_mode('acceptance-drain-001','enabled','draining','acceptance','test_drain')"
    ).fetchone()[0]
    assert first["duplicate"] is False and duplicate["duplicate"] is True
    _assert_raises(
        connection,
        "SELECT agent.set_runtime_claim_mode('acceptance-drain-001','enabled','draining','different','test_drain')",
    )
    connection.execute(
        "SELECT agent.set_runtime_claim_mode('acceptance-enable-01','draining','enabled','acceptance','test_enable')"
    )
    no_change = connection.execute(
        "SELECT agent.set_runtime_claim_mode('acceptance-noop-001','enabled','enabled','acceptance','test_noop')"
    ).fetchone()[0]
    no_change_replay = connection.execute(
        "SELECT agent.set_runtime_claim_mode('acceptance-noop-001','enabled','enabled','acceptance','test_noop')"
    ).fetchone()[0]
    assert no_change["no_change"] is True
    assert no_change_replay["duplicate"] is True
    assert no_change_replay["no_change"] is True
    assert no_change_replay["rollout_id"] == no_change["rollout_id"]
    _assert_raises(
        connection,
        """SELECT agent.set_runtime_claim_mode(
          'acceptance-noop-001','enabled','draining','acceptance','test_noop')""",
    )
    _assert_raises(
        connection,
        "SELECT agent.set_runtime_claim_mode('acceptance-illegal1','enabled','disabled','acceptance','test_illegal')",
    )
    _assert_raises(
        connection,
        "UPDATE agent.event_retention_policies SET hot_days=3650 WHERE policy_key='runtime_events_v1'",
    )
    public_execute = connection.execute(
        """SELECT EXISTS(SELECT 1 FROM pg_proc proc,
          LATERAL aclexplode(coalesce(proc.proacl,acldefault('f',proc.proowner))) acl
          WHERE proc.oid='agent.set_runtime_claim_mode(text,text,text,text,text)'::regprocedure
            AND acl.grantee=0 AND acl.privilege_type='EXECUTE')"""
    ).fetchone()[0]
    assert public_execute is False

    blocker = connect_test()
    claimant = connect_test()
    claim_result = []
    try:
        blocker.autocommit = False
        blocker.execute("SELECT pg_advisory_xact_lock(262,1)")

        def claim_while_locked():
            claim_result.append(
                claimant.execute(
                    "SELECT agent.claim_runtime_task(%s,%s,%s,%s,false)",
                    (worker_id, task_id, agent_id, "b" * 64),
                ).fetchone()[0]
            )

        thread = threading.Thread(target=claim_while_locked, daemon=True)
        thread.start()
        time.sleep(0.2)
        assert thread.is_alive()
        blocker.execute(
            "SELECT agent.set_runtime_claim_mode('acceptance-drain-002','enabled','draining','acceptance','race_drain')"
        )
        blocker.commit()
        thread.join(timeout=5)
        assert not thread.is_alive() and claim_result == [{}]
    finally:
        blocker.close()
        claimant.close()

    connection.execute(
        "UPDATE core.schema_migrations SET definition_checksum_sha256=%s WHERE migration_number=260",
        ("0" * 64,),
    )
    with pytest.raises(Exception, match="prerequisite migration ledger mismatch"):
        _run_script(connection, migration)

    connection.rollback()
    connection.execute(
        "UPDATE core.schema_migrations SET definition_checksum_sha256=%s WHERE migration_number=260",
        (EXPECTED_MIGRATIONS[260][1],),
    )
    connection.execute(
        "UPDATE core.schema_migrations SET definition_checksum_sha256=%s WHERE migration_number=262",
        ("0" * 64,),
    )
    with pytest.raises(Exception, match="migration 262 ledger mismatch"):
        _run_script(connection, migration)


def test_acceptance_contracts_on_disposable_postgres() -> None:
    dsn = os.environ.get("AI_OS_TEST_PG_DSN", "")
    if not dsn:
        pytest.skip("AI_OS_TEST_PG_DSN is required for the isolated PostgreSQL acceptance test")
    settings = validate_admin_dsn(dsn)
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo

    database_name = "phase2_acceptance_" + uuid4().hex
    admin = psycopg.connect(dsn, autocommit=True)
    created = False
    try:
        _assert_private_test_server(admin, settings["host"])
        admin.execute(
            sql.SQL("CREATE DATABASE {} ENCODING 'UTF8' TEMPLATE template0").format(
                sql.Identifier(database_name)
            )
        )
        created = True
        test_dsn = make_conninfo(dsn, dbname=database_name)

        def connect_test():
            return psycopg.connect(test_dsn, autocommit=True)

        with connect_test() as connection:
            _install_core_ledger(connection)
            _bootstrap(connection)
            for number, filename in (
                (256, "256_agent_runtime_leases_v1.sql"),
                (257, "257_agent_runtime_policy_events_v1.sql"),
                (258, "258_agent_conversations_handoffs_v1.sql"),
                (259, "259_agent_model_fabric_v1.sql"),
                (261, "261_charlie_chief_of_staff_v1.sql"),
            ):
                _assert_ledger_guard(connection, number, filename)
            _assert_existing_role_version_snapshot(connection)
            _install_acceptance_substrate(connection)
            _exercise(connection, connect_test)
    finally:
        if created:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",
                (database_name,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database_name)))
        admin.close()
