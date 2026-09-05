"""Provider-free contracts for the explicit Phase 2 live canary."""
from __future__ import annotations

import json
import os
import re
from uuid import UUID, uuid4

import pytest

from _ai_os_runtime.scripts import run_phase2_live_canary as canary


RUN_KEY = "phase2-canary-20260905T120000Z-012345abcdef"
FIRST_WORKER = "11111111-1111-4111-8111-111111111111"
SECOND_WORKER = "22222222-2222-4222-8222-222222222222"


def identity() -> dict[str, object]:
    result = canary._identity(RUN_KEY)
    result.update({
        "first_worker": FIRST_WORKER,
        "second_worker": SECOND_WORKER,
    })
    return result


def receipt(canary_identity: dict[str, object]) -> dict:
    ids = {
        key: index + 1 for index, key in enumerate(canary.INTEGER_IDS)
    }
    ids.update({
        "first_worker_id": canary_identity["first_worker"],
        "second_worker_id": canary_identity["second_worker"],
    })
    return {
        "schema_version": "phase2_live_canary.v1",
        "status": "passed",
        "run_key": canary_identity["run_key"],
        "scope": "internal",
        "data_class": "public",
        "synthetic": True,
        "initial_mode": "disabled",
        "final_mode": "disabled",
        "ids": ids,
        "timestamps": {
            "started_at": "2026-09-05T12:00:00+00:00",
            "finished_at": "2026-09-05T12:00:01+00:00",
        },
        "counts": {"task_events": 12, "active_canary_leases": 0},
        "checks": {key: True for key in canary.CHECK_KEYS},
        "terminal": {
            "task_status": "cancelled",
            "profile_status": "disabled",
            "workers_status": "STOPPED",
            "receipt_status": "recorded",
        },
        "safety": {
            "model_calls_made": False,
            "provider_calls_made": False,
            "routes_enabled": False,
            "routines_enabled": False,
            "client_writes_made": False,
            "external_writes_made": False,
            "broker_write_allowed": False,
        },
        "untrusted_secret": "must never be copied",
        "raw_private_task_body": "must never be copied",
    }


def cleanup() -> dict:
    return {
        "status": "passed",
        "claim_mode": "disabled",
        "cleanup_rollout_id": 99,
        "active_canary_leases": 0,
        "task_status": "cancelled",
        "synthetic_profile_disabled": True,
        "synthetic_workers_stopped": True,
        "broker_write_allowed": False,
    }


def test_confirmation_is_required_before_any_database_call() -> None:
    calls: list[str] = []
    result = canary.run_live_canary(
        operator_confirmed=False,
        executor=lambda sql: calls.append(sql) or "{}",
    )
    assert result == {
        "schema_version": "phase2_live_canary.v1",
        "status": "refused",
        "reason": "explicit_operator_confirmation_required",
        "database_calls_made": 0,
        "broker_write_allowed": False,
    }
    assert calls == []


def test_cli_refuses_without_confirmation_and_never_loads_executor(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        canary,
        "_default_executor",
        lambda _sql: pytest.fail("database executor must not run without confirmation"),
    )
    assert canary.main([]) == 2
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "refused"
    assert output["database_calls_made"] == 0


def test_generated_sql_is_atomic_synthetic_and_has_no_external_authority() -> None:
    canary_identity = identity()
    sql = canary.build_canary_sql(canary_identity, 321)
    lowered = sql.lower()

    assert lowered.startswith("begin;") and lowered.endswith("commit;")
    assert "set transaction isolation level repeatable read" in lowered
    assert "pg_advisory_xact_lock(262,1)" in lowered
    assert "migration_number=262" in lowered
    assert "source_kind='phase2_live_canary'" in lowered
    assert "'internal',null,null,'public'" in lowered
    assert "'public_synthetic_fixture'" in lowered
    assert "'synthetic_canary',null,'{}'::text[]" in lowered
    assert "daily_token_budget=0" in lowered
    assert "allowed_books='{}'::bigint[]" in lowered
    assert "allowed_clients='{}'::bigint[]" in lowered
    assert "broker_write_allowed',false" in lowered

    lifecycle = (
        "phase2_canary_enable",
        "agent.claim_runtime_task",
        "agent.heartbeat_runtime_lease",
        "request_runtime_control(v_task,'pause')",
        "request_runtime_control(v_task,'resume')",
        "stale owner heartbeat was accepted",
        "agent.record_runtime_step",
        "agent.record_runtime_receipt",
        "stale owner fenced write was accepted",
        "request_runtime_control(v_task,'cancel')",
        "phase2_canary_drain",
        "phase2_canary_disable",
    )
    cursor = 0
    for item in lifecycle:
        position = lowered.index(item.lower(), cursor)
        assert position >= cursor
        cursor = position + len(item)

    forbidden_mutations = re.compile(
        r"\b(?:insert\s+into|update|delete\s+from)\s+"
        r"(?:agent\.(?:model|routine)[a-z0-9_]*|research\.|market\.|trading\."
        r"|portfolio\.|client_data\.)",
        re.IGNORECASE,
    )
    assert forbidden_mutations.search(sql) is None
    for forbidden_call in (
        "control_routine(", "promote_model", "execute_model", "provider_call(",
        "broker_order(", "live_order", "sync_zerodha",
    ):
        assert forbidden_call not in lowered


def test_cleanup_is_idempotent_scoped_and_refuses_shared_mode_overwrite() -> None:
    sql = canary.build_cleanup_sql(identity()).lower()
    assert sql.startswith("begin;") and sql.endswith("commit;")
    assert "pg_advisory_xact_lock(262,1)" in sql
    assert "if v_mode<>'disabled'" in sql
    assert "refuses to overwrite a non-disabled shared runtime state" in sql
    assert "source_kind='phase2_live_canary'" in sql
    assert "source_ref='" + RUN_KEY.lower() + "'" in sql
    assert "phase2_canary_cleanup" in sql
    assert "delete from" not in sql
    assert "update agent.tasks" not in sql
    assert "update agent.runtime_settings" not in sql


def test_success_is_bounded_redacted_and_cleanup_is_always_second(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canary_identity = identity()
    monkeypatch.setattr(canary, "_identity", lambda _run_key: canary_identity)
    calls: list[str] = []

    def execute(sql: str) -> str:
        calls.append(sql)
        payload = receipt(canary_identity) if len(calls) == 1 else cleanup()
        return "irrelevant psql noise\n" + json.dumps(payload)

    result = canary.run_live_canary(
        operator_confirmed=True,
        executor=execute,
        run_key=RUN_KEY,
        process_id=321,
    )
    assert result["status"] == "passed"
    assert result["run_key"] == RUN_KEY
    assert result["cleanup"]["status"] == "passed"
    assert result["safety"]["broker_write_allowed"] is False
    assert len(calls) == 2
    assert "phase2_canary_enable" in calls[0]
    assert "phase2_canary_cleanup" in calls[1]
    encoded = json.dumps(result)
    assert "untrusted_secret" not in encoded
    assert "raw_private_task_body" not in encoded
    assert len(encoded) < 32_768
    assert UUID(result["ids"]["first_worker_id"]) == UUID(FIRST_WORKER)


def test_execution_failure_is_redacted_and_still_runs_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canary_identity = identity()
    monkeypatch.setattr(canary, "_identity", lambda _run_key: canary_identity)
    calls: list[str] = []

    def execute(sql: str) -> str:
        calls.append(sql)
        if len(calls) == 1:
            raise RuntimeError("private task body and database credential")
        return json.dumps(cleanup())

    result = canary.run_live_canary(
        operator_confirmed=True, executor=execute, run_key=RUN_KEY, process_id=321
    )
    assert result["status"] == "failed"
    assert result["failure_code"] == "canary_execution_failed"
    assert result["error_type"] == "RuntimeError"
    assert result["cleanup"]["status"] == "passed"
    assert len(calls) == 2
    assert "credential" not in json.dumps(result)
    assert "private task body" not in json.dumps(result)


def test_unattested_safety_or_cleanup_failure_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canary_identity = identity()
    monkeypatch.setattr(canary, "_identity", lambda _run_key: canary_identity)
    unsafe_receipt = receipt(canary_identity)
    unsafe_receipt["safety"]["provider_calls_made"] = True
    calls = iter((json.dumps(unsafe_receipt), json.dumps(cleanup())))
    unsafe = canary.run_live_canary(
        operator_confirmed=True, executor=lambda _sql: next(calls), run_key=RUN_KEY
    )
    assert unsafe["status"] == "failed"
    assert unsafe["failure_code"] == "canary_execution_failed"

    calls = iter((json.dumps(receipt(canary_identity)), "not-json"))
    unclean = canary.run_live_canary(
        operator_confirmed=True, executor=lambda _sql: next(calls), run_key=RUN_KEY
    )
    assert unclean["status"] == "failed"
    assert unclean["failure_code"] == "canary_cleanup_failed"
    assert unclean["cleanup"]["claim_mode"] == "unverified"


def test_invalid_synthetic_identity_is_rejected_before_sql_generation() -> None:
    with pytest.raises(canary.CanaryRefusal, match="run key is invalid"):
        canary.run_live_canary(
            operator_confirmed=True,
            executor=lambda _sql: pytest.fail("invalid identity must not reach the database"),
            run_key="production-task-1",
        )
    with pytest.raises(canary.CanaryRefusal, match="process id is invalid"):
        canary.build_canary_sql(identity(), 0)


def test_live_canary_on_disposable_postgres() -> None:
    """Execute both canary transactions only on the guarded private test cluster."""
    dsn = os.environ.get("AI_OS_TEST_PG_DSN", "")
    if not dsn:
        pytest.skip("AI_OS_TEST_PG_DSN is required for isolated PostgreSQL canary acceptance")

    from psycopg import sql
    from psycopg.conninfo import make_conninfo
    import psycopg

    from _ai_os_runtime.tests.phase2_runtime_stress import (
        SQL_ROOT,
        _assert_private_test_server,
        _bootstrap,
        _run_script,
        validate_admin_dsn,
    )
    from _ai_os_runtime.tests.test_agent_os_acceptance_contracts_pg import (
        _install_acceptance_substrate,
        _install_core_ledger,
    )

    settings = validate_admin_dsn(dsn)
    database_name = "phase2_canary_" + uuid4().hex
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
        with psycopg.connect(test_dsn, autocommit=True) as connection:
            _install_core_ledger(connection)
            _bootstrap(connection)
            _install_acceptance_substrate(connection)
            # The shared stress bootstrap explicitly enables its disposable
            # queue; this canary has a stricter disabled-state precondition.
            connection.execute(
                "UPDATE agent.runtime_settings SET claim_mode='disabled' WHERE singleton"
            )
            _run_script(
                connection,
                (SQL_ROOT / "262_agent_os_acceptance_contracts_v1.sql").read_text(
                    encoding="utf-8"
                ),
            )

        def execute(statement: str) -> str:
            values: list[object] = []
            with psycopg.connect(test_dsn, autocommit=True) as connection:
                cursor = connection.execute(statement)
                while True:
                    if cursor.description:
                        row = cursor.fetchone()
                        if row:
                            values.append(row[0])
                    if not cursor.nextset():
                        break
            return str(values[-1]) if values else ""

        report = canary.run_live_canary(
            operator_confirmed=True,
            executor=execute,
            run_key=RUN_KEY,
            process_id=321,
        )
        assert report["status"] == "passed", report
        assert report["cleanup"]["claim_mode"] == "disabled"
        with psycopg.connect(test_dsn, autocommit=True) as connection:
            terminal = connection.execute(
                """SELECT task.status,profile.status,count(lease.id) FILTER(WHERE lease.status='ACTIVE'),
                   count(DISTINCT receipt.id),bool_and(worker.status='STOPPED')
                FROM agent.tasks task
                JOIN agent.profiles profile ON profile.id=task.agent_id
                JOIN agent.task_leases lease ON lease.task_id=task.id
                LEFT JOIN agent.runtime_output_receipts receipt ON receipt.task_id=task.id
                JOIN agent.workers worker ON worker.id=lease.worker_id
                WHERE task.source_kind='phase2_live_canary' AND task.source_ref=%s
                GROUP BY task.status,profile.status""",
                (RUN_KEY,),
            ).fetchone()
            assert terminal == ("cancelled", "disabled", 0, 1, True)
            assert connection.execute(
                "SELECT claim_mode FROM agent.runtime_settings WHERE singleton"
            ).fetchone()[0] == "disabled"
    finally:
        if created:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",
                (database_name,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database_name)))
        admin.close()
