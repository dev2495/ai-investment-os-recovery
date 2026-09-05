#!/usr/bin/env python3
"""Atomic, provider-free live canary for the Phase 2 lease runtime.

The canary uses only uniquely named internal/public synthetic records. It never
calls a model or provider, never enables a route or routine, never addresses a
client/book, and never grants broker or external-write authority. All lifecycle
work is one PostgreSQL transaction. The migration-262 rollout lock prevents a
production worker from observing the transaction's temporary enabled state.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Callable
from uuid import UUID, uuid4


RUNTIME_ROOT = Path(os.environ.get("AI_OS_RUNTIME_ROOT") or Path(__file__).resolve().parents[1])
SCRIPT_ROOT = RUNTIME_ROOT / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

Executor = Callable[[str], str]
RUN_KEY_RE = re.compile(r"phase2-canary-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}")
ACTOR = "Phase 2 Live Canary Operator"
CHECK_KEYS = (
    "initially_disabled",
    "temporarily_enabled",
    "first_claim",
    "heartbeat",
    "pause_at_safe_boundary",
    "safe_resume",
    "second_claim",
    "stale_old_owner_rejected",
    "fenced_old_owner_rejected",
    "receipt_recorded",
    "confirmed_cancel",
    "drained",
    "finally_disabled",
    "legacy_tasks_unchanged",
    "model_calls_unchanged",
    "routine_runs_unchanged",
)
INTEGER_IDS = (
    "agent_id", "task_id", "first_lease_id", "second_lease_id",
    "step_id", "receipt_id", "enable_rollout_id", "drain_rollout_id",
    "disable_rollout_id",
)
UUID_IDS = ("first_worker_id", "second_worker_id")


class CanaryRefusal(RuntimeError):
    """The live target or returned receipt did not satisfy the canary contract."""


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def _default_executor(sql: str) -> str:
    # Reuse the runtime's canonical local Postgres adapter. It injects the DB
    # credential only into the local process environment and never prints it.
    from run_agent_worker_once import _psql_text_unfenced

    return _psql_text_unfenced(sql)


def _new_run_key(now: datetime | None = None) -> str:
    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return f"phase2-canary-{instant.strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:12]}"


def _assert_run_key(run_key: str) -> str:
    if not isinstance(run_key, str) or not RUN_KEY_RE.fullmatch(run_key):
        raise CanaryRefusal("synthetic canary run key is invalid")
    return run_key


def _identity(run_key: str) -> dict[str, object]:
    suffix = run_key.rsplit("-", 1)[1]
    return {
        "run_key": run_key,
        "agent_key": f"phase2_synthetic_canary_{suffix}",
        "agent_name": f"Phase 2 Synthetic Canary {suffix}",
        "first_worker": str(uuid4()),
        "second_worker": str(uuid4()),
        "first_token_hash": hashlib.sha256(f"{run_key}:first-owner".encode()).hexdigest(),
        "second_token_hash": hashlib.sha256(f"{run_key}:second-owner".encode()).hexdigest(),
        "heartbeat_one": str(uuid4()),
        "heartbeat_pause": str(uuid4()),
        "heartbeat_two": str(uuid4()),
        "heartbeat_cancel": str(uuid4()),
        "receipt_hash": hashlib.sha256(f"{run_key}:public-synthetic-receipt-v1".encode()).hexdigest(),
        "artifact_ref": f"urn:aios:synthetic-canary:{run_key}:receipt",
    }


def build_canary_sql(identity: dict[str, object], process_id: int) -> str:
    """Build the one-transaction lifecycle; values are generated locally only."""
    run_key = _assert_run_key(str(identity["run_key"]))
    if not 1 <= int(process_id) <= 2_147_483_647:
        raise CanaryRefusal("canary process id is invalid")
    values = {key: sql_literal(value) for key, value in identity.items()}
    actor = sql_literal(ACTOR)
    return f"""
BEGIN;
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SET LOCAL statement_timeout='45s';
SET LOCAL lock_timeout='5s';
SET LOCAL idle_in_transaction_session_timeout='60s';
SELECT pg_advisory_xact_lock(262,1);
CREATE TEMP TABLE phase2_canary_result(payload jsonb NOT NULL) ON COMMIT DROP;
DO $phase2_canary$
DECLARE
    v_run text := {values['run_key']};
    v_agent_key text := {values['agent_key']};
    v_agent_name text := {values['agent_name']};
    v_first_worker uuid := {values['first_worker']}::uuid;
    v_second_worker uuid := {values['second_worker']}::uuid;
    v_first_token text := {values['first_token_hash']};
    v_second_token text := {values['second_token_hash']};
    v_started timestamptz := clock_timestamp();
    v_initial_mode text;
    v_final_mode text;
    v_agent bigint;
    v_task bigint;
    v_first_claim jsonb;
    v_second_claim jsonb;
    v_first_lease bigint;
    v_second_lease bigint;
    v_heartbeat jsonb;
    v_control jsonb;
    v_step jsonb;
    v_step_id bigint;
    v_receipt jsonb;
    v_enable jsonb;
    v_drain jsonb;
    v_disable jsonb;
    v_stale_rejected boolean := false;
    v_fence_rejected boolean := false;
    v_legacy_count_before bigint;
    v_legacy_count_after bigint;
    v_legacy_updated_before timestamptz;
    v_legacy_updated_after timestamptz;
    v_model_id_before bigint := 0;
    v_model_id_after bigint := 0;
    v_routine_id_before bigint := 0;
    v_routine_id_after bigint := 0;
    v_events integer;
BEGIN
    IF to_regprocedure('agent.set_runtime_claim_mode(text,text,text,text,text)') IS NULL
       OR to_regprocedure('agent.runtime_cutover_status()') IS NULL
       OR to_regprocedure('agent.record_runtime_receipt(uuid,bigint,text,bigint,text,text,text,jsonb)') IS NULL
       OR NOT EXISTS (
           SELECT 1 FROM core.schema_migrations
           WHERE migration_number=262
             AND migration_key='262_agent_os_acceptance_contracts_v1'
       ) THEN
        RAISE EXCEPTION 'phase2 acceptance contracts are unavailable';
    END IF;

    SELECT claim_mode INTO v_initial_mode
    FROM agent.runtime_settings WHERE singleton FOR UPDATE;
    IF v_initial_mode IS DISTINCT FROM 'disabled' THEN
        RAISE EXCEPTION 'phase2 canary requires an initially disabled lease runtime';
    END IF;
    IF EXISTS (SELECT 1 FROM agent.task_leases WHERE status='ACTIVE') THEN
        RAISE EXCEPTION 'phase2 canary requires zero active or unreaped leases';
    END IF;
    IF EXISTS (
        SELECT 1 FROM agent.tasks
        WHERE source_kind='phase2_live_canary' AND source_ref=v_run
    ) THEN
        RAISE EXCEPTION 'phase2 canary run key already exists';
    END IF;

    SELECT count(*),max(updated_at) INTO v_legacy_count_before,v_legacy_updated_before
    FROM agent.tasks WHERE runtime_protocol='legacy';
    IF to_regclass('agent.model_call_decisions') IS NOT NULL THEN
        EXECUTE 'SELECT coalesce(max(id),0) FROM agent.model_call_decisions'
        INTO v_model_id_before;
    END IF;
    IF to_regclass('agent.routine_runs') IS NOT NULL THEN
        EXECUTE 'SELECT coalesce(max(id),0) FROM agent.routine_runs'
        INTO v_routine_id_before;
    END IF;

    INSERT INTO agent.profiles(
        agent_name,agent_key,department,role_scope,default_model_route,default_tools,
        permission_level,status,guardrails,output_targets,role_version,max_parallel_tasks
    ) VALUES (
        v_agent_name,v_agent_key,'runtime','synthetic_canary',NULL,'{{}}'::text[],
        'read_only','active',
        '{{"synthetic":true,"public_fixture_only":true,"model_calls":false,"provider_calls":false,"external_writes":false,"broker_write_allowed":false}}'::jsonb,
        '{{}}'::text[],1,1
    ) RETURNING id INTO v_agent;
    UPDATE agent.agent_workspaces
    SET room_key='runtime',allowed_task_classes=ARRAY['phase2_canary'],
        allowed_scopes=ARRAY['internal'],allowed_books='{{}}'::bigint[],
        allowed_clients='{{}}'::bigint[],allowed_data_classes=ARRAY['public'],
        denied_capabilities=ARRAY[
            'broker.*','credential.*','client.*','model.*','provider.*',
            'research.*','routine.*','external.*','shell.production'
        ],daily_token_budget=0,capability_status='READY',updated_at=clock_timestamp()
    WHERE agent_id=v_agent;

    PERFORM agent.register_runtime_worker(
        v_first_worker,'phase2-live-canary',{int(process_id)},'phase2-live-canary-v1',1
    );
    PERFORM agent.register_runtime_worker(
        v_second_worker,'phase2-live-canary',{int(process_id)},'phase2-live-canary-v1',1
    );
    PERFORM agent.configure_runtime_worker(v_first_worker,ARRAY['phase2_canary'],'{{}}'::text[]);
    PERFORM agent.configure_runtime_worker(v_second_worker,ARRAY['phase2_canary'],'{{}}'::text[]);

    INSERT INTO agent.tasks(
        title,objective,owner_agent,status,priority,approval_required,source_kind,
        source_ref,output_format,evidence,agent_id,runtime_protocol,runtime_state,
        task_class,recovery_policy,recovery_limit,runtime_scope,book_id,client_id,
        data_class,runtime_context
    ) VALUES (
        'Phase 2 synthetic lifecycle canary',
        'Public synthetic lease, control, fencing and receipt acceptance only.',
        v_agent_name,'queued','normal',false,'phase2_live_canary',v_run,'json',
        jsonb_build_array(jsonb_build_object('kind','public_synthetic_fixture','run_key',v_run)),
        v_agent,'lease_v1',NULL,'phase2_canary','idempotent_read',1,
        'internal',NULL,NULL,'public',jsonb_build_object(
            'synthetic',true,'public_fixture_only',true,'run_key',v_run,
            'model_calls_allowed',false,'provider_calls_allowed',false,
            'client_writes_allowed',false,'external_writes_allowed',false,
            'broker_write_allowed',false
        )
    ) RETURNING id INTO v_task;

    v_enable := agent.set_runtime_claim_mode(
        v_run||'.enable','disabled','enabled',{actor},'phase2_canary_enable'
    );
    IF v_enable->>'claim_mode'<>'enabled' THEN
        RAISE EXCEPTION 'canary enable transition failed';
    END IF;

    v_first_claim := agent.claim_runtime_task(
        v_first_worker,v_task,v_agent,v_first_token,false
    );
    IF v_first_claim='{{}}'::jsonb THEN RAISE EXCEPTION 'first canary claim failed'; END IF;
    v_first_lease := (v_first_claim->>'lease_id')::bigint;
    v_heartbeat := agent.heartbeat_runtime_lease(
        v_first_worker,v_first_lease,v_first_token,{values['heartbeat_one']}::uuid,'READING'
    );
    IF coalesce((v_heartbeat->>'accepted')::boolean,false) IS NOT true THEN
        RAISE EXCEPTION 'first canary heartbeat failed';
    END IF;

    v_control := agent.request_runtime_control(v_task,'pause');
    v_heartbeat := agent.heartbeat_runtime_lease(
        v_first_worker,v_first_lease,v_first_token,{values['heartbeat_pause']}::uuid,NULL
    );
    IF v_heartbeat->>'control_requested'<>'pause' THEN
        RAISE EXCEPTION 'pause was not visible at the safe boundary';
    END IF;
    PERFORM agent.finish_runtime_lease(
        v_first_worker,v_first_lease,v_first_token,'paused',NULL
    );
    v_control := agent.request_runtime_control(v_task,'resume');
    IF v_control->>'action'<>'resume' THEN RAISE EXCEPTION 'safe resume failed'; END IF;

    v_second_claim := agent.claim_runtime_task(
        v_second_worker,v_task,v_agent,v_second_token,false
    );
    IF v_second_claim='{{}}'::jsonb THEN RAISE EXCEPTION 'second canary claim failed'; END IF;
    v_second_lease := (v_second_claim->>'lease_id')::bigint;

    BEGIN
        PERFORM agent.heartbeat_runtime_lease(
            v_first_worker,v_first_lease,v_first_token,{values['heartbeat_two']}::uuid,'READING'
        );
    EXCEPTION WHEN OTHERS THEN
        IF SQLSTATE='P0001' AND SQLERRM='lease ownership lost' THEN
            v_stale_rejected := true;
        ELSE
            RAISE;
        END IF;
    END;
    IF NOT v_stale_rejected THEN RAISE EXCEPTION 'stale owner heartbeat was accepted'; END IF;

    v_heartbeat := agent.heartbeat_runtime_lease(
        v_second_worker,v_second_lease,v_second_token,{values['heartbeat_two']}::uuid,'WRITING'
    );
    IF coalesce((v_heartbeat->>'accepted')::boolean,false) IS NOT true THEN
        RAISE EXCEPTION 'second canary heartbeat failed';
    END IF;
    v_step := agent.record_runtime_step(
        v_second_worker,v_second_lease,v_second_token,'synthetic_receipt','WRITING',true
    );
    v_step_id := (v_step->>'step_id')::bigint;
    v_receipt := agent.record_runtime_receipt(
        v_second_worker,v_second_lease,v_second_token,v_step_id,
        'phase2_synthetic_receipt',{values['artifact_ref']},{values['receipt_hash']},
        jsonb_build_array(jsonb_build_object(
            'kind','public_synthetic_fixture','run_key',v_run,'external_write',false
        ))
    );
    IF (v_receipt->>'receipt_id')::bigint IS NULL THEN
        RAISE EXCEPTION 'synthetic receipt was not recorded';
    END IF;

    BEGIN
        PERFORM agent.record_runtime_step(
            v_first_worker,v_first_lease,v_first_token,'stale_fence_probe','WRITING',false
        );
    EXCEPTION WHEN OTHERS THEN
        IF SQLSTATE='P0001' AND SQLERRM='lease ownership lost' THEN
            v_fence_rejected := true;
        ELSE
            RAISE;
        END IF;
    END;
    IF NOT v_fence_rejected THEN RAISE EXCEPTION 'stale owner fenced write was accepted'; END IF;

    v_control := agent.request_runtime_control(v_task,'cancel');
    IF v_control->>'action'<>'cancel' THEN RAISE EXCEPTION 'confirmed cancel was rejected'; END IF;
    v_heartbeat := agent.heartbeat_runtime_lease(
        v_second_worker,v_second_lease,v_second_token,{values['heartbeat_cancel']}::uuid,NULL
    );
    IF v_heartbeat->>'control_requested'<>'cancel' THEN
        RAISE EXCEPTION 'cancel was not visible at the safe boundary';
    END IF;
    PERFORM agent.finish_runtime_lease(
        v_second_worker,v_second_lease,v_second_token,'cancelled',NULL
    );

    v_drain := agent.set_runtime_claim_mode(
        v_run||'.drain','enabled','draining',{actor},'phase2_canary_drain'
    );
    v_disable := agent.set_runtime_claim_mode(
        v_run||'.disable','draining','disabled',{actor},'phase2_canary_disable'
    );
    PERFORM agent.idle_runtime_worker(v_first_worker);
    PERFORM agent.idle_runtime_worker(v_second_worker);
    UPDATE agent.agent_workspaces
    SET capability_status='UNAVAILABLE',updated_at=clock_timestamp()
    WHERE agent_id=v_agent;
    UPDATE agent.profiles SET status='disabled',updated_at=clock_timestamp()
    WHERE id=v_agent;

    SELECT claim_mode INTO v_final_mode
    FROM agent.runtime_settings WHERE singleton;
    SELECT count(*),max(updated_at) INTO v_legacy_count_after,v_legacy_updated_after
    FROM agent.tasks WHERE runtime_protocol='legacy';
    IF to_regclass('agent.model_call_decisions') IS NOT NULL THEN
        EXECUTE 'SELECT coalesce(max(id),0) FROM agent.model_call_decisions'
        INTO v_model_id_after;
    END IF;
    IF to_regclass('agent.routine_runs') IS NOT NULL THEN
        EXECUTE 'SELECT coalesce(max(id),0) FROM agent.routine_runs'
        INTO v_routine_id_after;
    END IF;
    SELECT count(*) INTO v_events FROM agent.task_events WHERE task_id=v_task;

    IF v_final_mode<>'disabled'
       OR EXISTS(SELECT 1 FROM agent.task_leases WHERE task_id=v_task AND status='ACTIVE')
       OR NOT EXISTS(SELECT 1 FROM agent.tasks WHERE id=v_task AND status='cancelled'
                     AND runtime_scope='internal' AND data_class='public'
                     AND book_id IS NULL AND client_id IS NULL)
       OR NOT EXISTS(SELECT 1 FROM agent.task_steps WHERE id=v_step_id
                     AND side_effect_status='recorded'
                     AND receipt_ref='runtime_receipt:'||(v_receipt->>'receipt_id'))
       OR v_legacy_count_before<>v_legacy_count_after
       OR v_legacy_updated_before IS DISTINCT FROM v_legacy_updated_after
       OR v_model_id_before<>v_model_id_after
       OR v_routine_id_before<>v_routine_id_after THEN
        RAISE EXCEPTION 'phase2 canary terminal safety assertion failed';
    END IF;

    INSERT INTO phase2_canary_result(payload) VALUES (jsonb_build_object(
        'schema_version','phase2_live_canary.v1','status','passed','run_key',v_run,
        'scope','internal','data_class','public','synthetic',true,
        'initial_mode',v_initial_mode,'final_mode',v_final_mode,
        'ids',jsonb_build_object(
            'agent_id',v_agent,'task_id',v_task,
            'first_worker_id',v_first_worker,'second_worker_id',v_second_worker,
            'first_lease_id',v_first_lease,'second_lease_id',v_second_lease,
            'step_id',v_step_id,'receipt_id',(v_receipt->>'receipt_id')::bigint,
            'enable_rollout_id',(v_enable->>'rollout_id')::bigint,
            'drain_rollout_id',(v_drain->>'rollout_id')::bigint,
            'disable_rollout_id',(v_disable->>'rollout_id')::bigint
        ),
        'timestamps',jsonb_build_object(
            'started_at',v_started,'finished_at',clock_timestamp()
        ),
        'counts',jsonb_build_object('task_events',v_events,'active_canary_leases',0),
        'checks',jsonb_build_object(
            'initially_disabled',v_initial_mode='disabled',
            'temporarily_enabled',v_enable->>'claim_mode'='enabled',
            'first_claim',v_first_lease IS NOT NULL,'heartbeat',true,
            'pause_at_safe_boundary',true,'safe_resume',true,
            'second_claim',v_second_lease IS NOT NULL,
            'stale_old_owner_rejected',v_stale_rejected,
            'fenced_old_owner_rejected',v_fence_rejected,
            'receipt_recorded',(v_receipt->>'receipt_id') IS NOT NULL,
            'confirmed_cancel',true,'drained',v_drain->>'claim_mode'='draining',
            'finally_disabled',v_final_mode='disabled',
            'legacy_tasks_unchanged',v_legacy_count_before=v_legacy_count_after
                AND v_legacy_updated_before IS NOT DISTINCT FROM v_legacy_updated_after,
            'model_calls_unchanged',v_model_id_before=v_model_id_after,
            'routine_runs_unchanged',v_routine_id_before=v_routine_id_after
        ),
        'terminal',jsonb_build_object(
            'task_status','cancelled','profile_status','disabled',
            'workers_status','STOPPED','receipt_status','recorded'
        ),
        'safety',jsonb_build_object(
            'model_calls_made',false,'provider_calls_made',false,
            'routes_enabled',false,'routines_enabled',false,
            'client_writes_made',false,'external_writes_made',false,
            'broker_write_allowed',false
        )
    ));
END
$phase2_canary$;
SELECT payload::text FROM phase2_canary_result;
COMMIT;
""".strip()


def build_cleanup_sql(identity: dict[str, object]) -> str:
    """Build idempotent synthetic-only cleanup and terminal rollout audit."""
    _assert_run_key(str(identity["run_key"]))
    values = {key: sql_literal(value) for key, value in identity.items()}
    actor = sql_literal(ACTOR)
    return f"""
BEGIN;
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SET LOCAL statement_timeout='20s';
SET LOCAL lock_timeout='5s';
SELECT pg_advisory_xact_lock(262,1);
CREATE TEMP TABLE phase2_canary_cleanup(payload jsonb NOT NULL) ON COMMIT DROP;
DO $phase2_cleanup$
DECLARE v_mode text; v_rollout jsonb; v_active integer; v_task_status text;
BEGIN
    IF to_regprocedure('agent.set_runtime_claim_mode(text,text,text,text,text)') IS NULL THEN
        RAISE EXCEPTION 'phase2 rollout authority is unavailable';
    END IF;
    SELECT claim_mode INTO v_mode FROM agent.runtime_settings WHERE singleton FOR UPDATE;
    IF v_mode<>'disabled' THEN
        RAISE EXCEPTION 'fail-safe refuses to overwrite a non-disabled shared runtime state';
    END IF;
    SELECT count(*) INTO v_active
    FROM agent.task_leases lease
    JOIN agent.tasks task ON task.id=lease.task_id
    WHERE task.source_kind='phase2_live_canary'
      AND task.source_ref={values['run_key']} AND lease.status='ACTIVE';
    IF v_active<>0 THEN RAISE EXCEPTION 'synthetic canary still has an active lease'; END IF;

    UPDATE agent.workers SET status='STOPPED',shutdown_requested=true,
        last_heartbeat_at=clock_timestamp()
    WHERE id IN ({values['first_worker']}::uuid,{values['second_worker']}::uuid)
      AND NOT EXISTS(
          SELECT 1 FROM agent.task_leases lease
          WHERE lease.worker_id=agent.workers.id AND lease.status='ACTIVE'
      );
    UPDATE agent.agent_workspaces SET capability_status='UNAVAILABLE',updated_at=clock_timestamp()
    WHERE workspace_key={values['agent_key']};
    UPDATE agent.profiles SET status='disabled',updated_at=clock_timestamp()
    WHERE agent_key={values['agent_key']} AND agent_name={values['agent_name']};

    v_rollout := agent.set_runtime_claim_mode(
        {values['run_key']}||'.cleanup','disabled','disabled',{actor},'phase2_canary_cleanup'
    );
    SELECT status INTO v_task_status FROM agent.tasks
    WHERE source_kind='phase2_live_canary' AND source_ref={values['run_key']};
    INSERT INTO phase2_canary_cleanup(payload) VALUES (jsonb_build_object(
        'status','passed','claim_mode',v_mode,
        'cleanup_rollout_id',(v_rollout->>'rollout_id')::bigint,
        'active_canary_leases',v_active,
        'task_status',coalesce(v_task_status,'not_created'),
        'synthetic_profile_disabled',NOT EXISTS(
            SELECT 1 FROM agent.profiles WHERE agent_key={values['agent_key']} AND status='active'
        ),
        'synthetic_workers_stopped',NOT EXISTS(
            SELECT 1 FROM agent.workers
            WHERE id IN ({values['first_worker']}::uuid,{values['second_worker']}::uuid)
              AND status<>'STOPPED'
        ),
        'broker_write_allowed',false
    ));
END
$phase2_cleanup$;
SELECT payload::text FROM phase2_canary_cleanup;
COMMIT;
""".strip()


def _parse_object(raw: str) -> dict:
    if not isinstance(raw, str) or not raw.strip() or len(raw) > 131_072:
        raise CanaryRefusal("canary database receipt was missing or unbounded")
    for line in reversed(raw.splitlines()):
        try:
            payload = json.loads(line.strip())
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(payload, dict):
            return payload
    raise CanaryRefusal("canary database receipt was not a JSON object")


def _bounded_int(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise CanaryRefusal(f"{name} was not a positive record id")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise CanaryRefusal(f"{name} was not a positive record id") from exc
    if not 1 <= result <= 9_223_372_036_854_775_807:
        raise CanaryRefusal(f"{name} was not a positive record id")
    return result


def _normalize_receipt(payload: dict, expected_identity: dict[str, object]) -> dict:
    expected_run_key = str(expected_identity["run_key"])
    if payload.get("status") != "passed" or payload.get("run_key") != expected_run_key:
        raise CanaryRefusal("canary database receipt did not attest the expected run")
    if (
        payload.get("schema_version") != "phase2_live_canary.v1"
        or payload.get("scope") != "internal"
        or payload.get("data_class") != "public"
        or payload.get("synthetic") is not True
        or payload.get("initial_mode") != "disabled"
        or payload.get("final_mode") != "disabled"
    ):
        raise CanaryRefusal("canary database receipt did not attest its safety boundary")
    ids = payload.get("ids") if isinstance(payload.get("ids"), dict) else {}
    checks = payload.get("checks") if isinstance(payload.get("checks"), dict) else {}
    timestamps = payload.get("timestamps") if isinstance(payload.get("timestamps"), dict) else {}
    counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
    if any(checks.get(key) is not True for key in CHECK_KEYS):
        raise CanaryRefusal("one or more canary safety checks did not pass")
    normalized_ids = {key: _bounded_int(ids.get(key), key) for key in INTEGER_IDS}
    for key in UUID_IDS:
        normalized_ids[key] = str(UUID(str(ids.get(key))))
        identity_key = key.removesuffix("_id")
        if normalized_ids[key] != str(expected_identity[identity_key]):
            raise CanaryRefusal(f"{key} did not match the synthetic canary identity")
    normalized_times: dict[str, str] = {}
    parsed_times: dict[str, datetime] = {}
    for key in ("started_at", "finished_at"):
        value = str(timestamps.get(key) or "")
        if not 1 <= len(value) <= 64:
            raise CanaryRefusal(f"{key} was missing from the canary receipt")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() is None:
            raise CanaryRefusal(f"{key} was not timezone-aware")
        parsed_times[key] = parsed
        normalized_times[key] = value
    if parsed_times["finished_at"] < parsed_times["started_at"]:
        raise CanaryRefusal("canary receipt timestamps were out of order")
    terminal = payload.get("terminal") if isinstance(payload.get("terminal"), dict) else {}
    if terminal != {
        "task_status": "cancelled", "profile_status": "disabled",
        "workers_status": "STOPPED", "receipt_status": "recorded",
    }:
        raise CanaryRefusal("canary records were not terminal and inert")
    if counts.get("active_canary_leases") != 0:
        raise CanaryRefusal("canary receipt retained an active synthetic lease")
    expected_safety = {
        "model_calls_made": False,
        "provider_calls_made": False,
        "routes_enabled": False,
        "routines_enabled": False,
        "client_writes_made": False,
        "external_writes_made": False,
        "broker_write_allowed": False,
    }
    if payload.get("safety") != expected_safety:
        raise CanaryRefusal("canary database receipt did not attest zero external authority")
    return {
        "schema_version": "phase2_live_canary.v1",
        "status": "passed",
        "run_key": expected_run_key,
        "scope": "internal",
        "data_class": "public",
        "synthetic": True,
        "initial_mode": "disabled",
        "final_mode": "disabled",
        "ids": normalized_ids,
        "timestamps": normalized_times,
        "counts": {
            "task_events": max(0, min(10_000, int(counts.get("task_events") or 0))),
            "active_canary_leases": 0,
        },
        "checks": {key: True for key in CHECK_KEYS},
        "terminal": terminal,
        "safety": expected_safety,
    }


def _normalize_cleanup(payload: dict) -> dict:
    if payload.get("status") != "passed" or payload.get("claim_mode") != "disabled":
        raise CanaryRefusal("fail-safe cleanup did not confirm disabled state")
    task_status = str(payload.get("task_status") or "")
    if task_status not in {"cancelled", "not_created"}:
        raise CanaryRefusal("fail-safe cleanup found a non-terminal synthetic task")
    if payload.get("synthetic_profile_disabled") is not True:
        raise CanaryRefusal("synthetic profile was not disabled")
    if payload.get("active_canary_leases") != 0:
        raise CanaryRefusal("fail-safe cleanup found an active synthetic lease")
    if payload.get("broker_write_allowed") is not False:
        raise CanaryRefusal("fail-safe cleanup returned broker authority")
    if payload.get("synthetic_workers_stopped") is not True:
        raise CanaryRefusal("synthetic workers were not stopped")
    return {
        "status": "passed",
        "claim_mode": "disabled",
        "cleanup_rollout_id": _bounded_int(
            payload.get("cleanup_rollout_id"), "cleanup_rollout_id"
        ),
        "active_canary_leases": 0,
        "task_status": task_status,
        "synthetic_profile_disabled": True,
        "synthetic_workers_stopped": True,
        "broker_write_allowed": False,
    }


def run_live_canary(
    *,
    operator_confirmed: bool,
    executor: Executor | None = None,
    run_key: str | None = None,
    process_id: int | None = None,
) -> dict:
    """Run the canary and always attempt an idempotent terminal cleanup audit."""
    if operator_confirmed is not True:
        return {
            "schema_version": "phase2_live_canary.v1",
            "status": "refused",
            "reason": "explicit_operator_confirmation_required",
            "database_calls_made": 0,
            "broker_write_allowed": False,
        }
    selected_run_key = _assert_run_key(run_key or _new_run_key())
    identity = _identity(selected_run_key)
    execute = executor or _default_executor
    result: dict | None = None
    execution_error: Exception | None = None
    cleanup: dict | None = None
    cleanup_error: Exception | None = None
    try:
        result = _normalize_receipt(
            _parse_object(execute(build_canary_sql(
                identity, os.getpid() if process_id is None else process_id))), identity,
        )
    except Exception as exc:  # raw DB/provider text is intentionally never returned
        execution_error = exc
    finally:
        try:
            cleanup = _normalize_cleanup(
                _parse_object(execute(build_cleanup_sql(identity)))
            )
        except Exception as exc:  # report only a bounded error class
            cleanup_error = exc

    if execution_error is None and cleanup_error is None and result is not None:
        result["cleanup"] = cleanup
        return result
    return {
        "schema_version": "phase2_live_canary.v1",
        "status": "failed",
        "run_key": selected_run_key,
        "failure_code": (
            "canary_execution_failed" if execution_error is not None
            else "canary_cleanup_failed"
        ),
        "error_type": type(execution_error or cleanup_error).__name__[:80],
        "cleanup": cleanup or {
            "status": "failed", "claim_mode": "unverified",
            "broker_write_allowed": False,
        },
        "safety": {
            "model_calls_made": False, "provider_calls_made": False,
            "routes_enabled": False, "routines_enabled": False,
            "client_writes_made": False, "external_writes_made": False,
            "broker_write_allowed": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the atomic synthetic-only Phase 2 live lease canary."
    )
    parser.add_argument(
        "--operator-confirmed", action="store_true",
        help="Confirm the temporary synthetic disabled-to-enabled canary and terminal cancel.",
    )
    args = parser.parse_args(argv)
    report = run_live_canary(operator_confirmed=args.operator_confirmed)
    encoded = json.dumps(report, sort_keys=True, separators=(",", ":"), default=str)
    if len(encoded) > 32_768:
        encoded = json.dumps({
            "schema_version": "phase2_live_canary.v1", "status": "failed",
            "failure_code": "bounded_output_exceeded", "broker_write_allowed": False,
        }, sort_keys=True, separators=(",", ":"))
    print(encoded)
    return 0 if report.get("status") == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
