"""Versioned, allowlisted operational routines on the existing scheduler.

No natural-language schedule is executed here. A real run requires its
definition to be explicitly enabled. Schedule-triggered routines also require
their canonical workflow schedule to be enabled; event-driven routines keep
that periodic schedule disabled. Test runs are receipt-backed but cannot call
paid models, providers, client systems, credentials or brokers.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Callable

from .doctor_runtime import DoctorRuntime, redact, sql_jsonb, sql_literal


QueryFn = Callable[[str], list[dict[str, Any]]]
StatementFn = Callable[[str], list[dict[str, Any]]]
CommandRunnerFn = Callable[[str, dict[str, Any]], dict[str, Any]]
ArtifactWriterFn = Callable[[str, str, dict[str, Any]], dict[str, str]]
DoctorFactoryFn = Callable[[], DoctorRuntime]

ROUTINE_TOOL_ALLOWLIST = {
    "daily_system_health": "ai_os_doctor",
    "obsidian_incremental_index": "index_obsidian_vault",
    "research_company_change_monitor": "company_research_monitor",
    "stale_task_and_lease_reaper": "release_expired_leases",
    "zerodha_session_and_stream_watch": "zerodha_health_read",
}
ROUTINE_KEYS = frozenset(ROUTINE_TOOL_ALLOWLIST)
TRIGGER_KINDS = {"schedule", "event", "manual"}


def _bounded_key(value: object, label: str, *, minimum: int = 1, maximum: int = 240) -> str:
    text = str(value or "").strip()
    if not minimum <= len(text) <= maximum or not re.fullmatch(r"[A-Za-z0-9_.:-]+", text):
        raise ValueError(f"{label} must be a bounded identifier")
    return text


def _json_object(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        parsed = json.loads(value or "{}")
        if isinstance(parsed, dict):
            return parsed
    raise RuntimeError("database routine response was not an object")


def _as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple):
        return [str(item) for item in value]
    if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
        return [item.strip('"') for item in value[1:-1].split(",") if item]
    return []


def canonical_event_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(redact(payload), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class RoutineRuntime:
    """Execute only the five reviewed deterministic routine implementations."""

    def __init__(
        self,
        query: QueryFn,
        statement: StatementFn,
        *,
        doctor_factory: DoctorFactoryFn | None = None,
        command_runner: CommandRunnerFn | None = None,
        artifact_writer: ArtifactWriterFn | None = None,
        actor: str = "Jarvis",
    ):
        self.query = query
        self.statement = statement
        self.doctor_factory = doctor_factory
        self.command_runner = command_runner
        self.artifact_writer = artifact_writer
        self.actor = str(actor or "Jarvis")[:160]

    def list_routines(self) -> list[dict[str, Any]]:
        return self.query(
            """/* routine:list */
            SELECT routine_key,routine_name,description,owner_agent,current_version,
                   control_state,schedule_key,schedule_enabled,next_run_at,
                   last_materialized_at,cadence_seconds,schedule_timezone,skill_key,
                   trigger_kind,permission_class,timeout_seconds,cooldown_seconds,
                   retry_policy,cost_budget_usd,stale_data_policy,approval_policy,
                   output_destinations,allowed_tools,last_run_key,last_run_status,
                   last_run_at,last_finished_at,broker_write_allowed
            FROM agent.v_routine_control ORDER BY routine_key"""
        )

    def history(self, *, routine_key: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        clauses: list[str] = []
        if routine_key is not None:
            routine_key = _bounded_key(routine_key, "routine_key")
            clauses.append(f"routine_key={sql_literal(routine_key)}")
        bounded_limit = max(1, min(500, int(limit)))
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        return self.query(
            f"""/* routine:history */
            SELECT id,run_key,routine_key,routine_name,routine_version,trigger_kind,
                   event_hash,idempotency_key,status,requested_by,result_summary,
                   evidence,output_artifact_path,output_artifact_hash,error_code,
                   started_at,finished_at,model_cost_usd,broker_write_allowed,
                   external_write_allowed,client_write_allowed
            FROM agent.v_routine_run_history{where}
            ORDER BY started_at DESC,id DESC LIMIT {bounded_limit}"""
        )

    def _definition(self, routine_key: str) -> dict[str, Any]:
        rows = self.query(
            f"""/* routine:definition */
            SELECT * FROM agent.v_routine_control
            WHERE routine_key={sql_literal(routine_key)} LIMIT 1"""
        )
        if not rows:
            raise ValueError("unknown routine")
        definition = rows[0]
        expected_tool = ROUTINE_TOOL_ALLOWLIST.get(routine_key)
        if expected_tool is None or expected_tool not in _as_list(definition.get("allowed_tools")):
            raise RuntimeError("routine tool contract does not match the reviewed allowlist")
        try:
            cost = float(definition.get("cost_budget_usd") or 0)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("routine cost budget is invalid") from exc
        if cost != 0:
            raise RuntimeError("autonomous routine model budget must remain zero")
        if definition.get("broker_write_allowed") is not False:
            raise RuntimeError("routine broker-write contract is not false")
        return definition

    def control(
        self,
        routine_key: str,
        action: str,
        *,
        confirmed: bool,
        reason: str,
        actor: str | None = None,
    ) -> dict[str, Any]:
        routine_key = _bounded_key(routine_key, "routine_key")
        if routine_key not in ROUTINE_KEYS:
            raise ValueError("routine is not in the reviewed allowlist")
        action = str(action or "").strip().lower()
        if action not in {"enable", "pause", "disable"}:
            raise ValueError("unsupported routine action")
        if not confirmed:
            raise ValueError("explicit routine control confirmation required")
        reason = str(reason or "").strip()
        if not 8 <= len(reason) <= 500:
            raise ValueError("a bounded control reason is required")
        actor_value = str(actor or self.actor)[:160]
        rows = self.statement(
            f"""/* routine:control */
            SELECT agent.control_routine(
              {sql_literal(routine_key)},{sql_literal(action)},{sql_literal(actor_value)},
              {sql_literal(reason)},true
            ) AS result"""
        )
        if not rows:
            raise RuntimeError("routine control receipt was not returned")
        return _json_object(rows[0].get("result"))

    def _start(
        self,
        routine_key: str,
        *,
        trigger_kind: str,
        event_hash: str | None,
        idempotency_key: str,
        payload: dict[str, Any],
        actor: str,
        test_mode: bool,
    ) -> dict[str, Any]:
        rows = self.statement(
            f"""/* routine:start */
            SELECT agent.start_routine_run(
              {sql_literal(routine_key)},{sql_literal(trigger_kind)},{sql_literal(event_hash)},
              {sql_literal(idempotency_key)},{sql_jsonb(payload)},{sql_literal(actor)},
              {'true' if test_mode else 'false'}
            ) AS result"""
        )
        if not rows:
            raise RuntimeError("routine start receipt was not returned")
        return _json_object(rows[0].get("result"))

    def _finish(
        self,
        run_key: str,
        *,
        status: str,
        summary: str,
        evidence: list[dict[str, Any]],
        artifact: dict[str, str] | None = None,
        error_code: str | None = None,
    ) -> dict[str, Any]:
        artifact = artifact or {}
        rows = self.statement(
            f"""/* routine:finish */
            SELECT agent.finish_routine_run(
              {sql_literal(run_key)},{sql_literal(status)},{sql_literal(summary)},
              {sql_jsonb(redact(evidence))},{sql_literal(artifact.get('path'))},
              {sql_literal(artifact.get('sha256'))},{sql_literal(error_code)}
            ) AS result"""
        )
        if not rows:
            raise RuntimeError("routine finish receipt was not returned")
        return _json_object(rows[0].get("result"))

    def _doctor(self) -> DoctorRuntime:
        if self.doctor_factory is None:
            raise RuntimeError("Doctor runtime is unavailable")
        doctor = self.doctor_factory()
        if not callable(getattr(doctor, "run", None)):
            raise RuntimeError("Doctor factory returned an invalid runtime")
        return doctor

    def _run_daily_system_health(self, *, test_mode: bool, payload: dict[str, Any]) -> dict[str, Any]:
        result = self._doctor().run(mode="test" if test_mode else "scan", persist=True)
        return {
            "status": result["status"],
            "doctor_run_key": result.get("run_key"),
            "counts": result["counts"],
            "alerts": [
                {"check_key": item["check_key"], "status": item["status"],
                 "headline": item["headline"], "actionable_fix": item.get("actionable_fix")}
                for item in result["checks"] if item["status"] in {"failed", "warning"}
            ],
        }

    def _run_obsidian_incremental_index(self, *, test_mode: bool, payload: dict[str, Any]) -> dict[str, Any]:
        if test_mode:
            rows = self.query(
                """/* routine:obsidian:test */
                SELECT count(*) FILTER (WHERE deleted_at IS NULL)::integer AS note_count,
                       max(indexed_at) FILTER (WHERE deleted_at IS NULL) AS latest_indexed_at
                FROM knowledge.obsidian_notes"""
            )
            return {"status": "fixture_checked", "index_invoked": False,
                    "observed": rows[0] if rows else {}}
        if self.command_runner is None:
            raise RuntimeError("allowlisted Obsidian command runner is unavailable")
        result = self.command_runner("obsidian_incremental_index", payload)
        return {"status": "completed", "index_invoked": True, "result": redact(result)}

    def _run_research_company_change_monitor(
        self,
        *,
        test_mode: bool,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if test_mode:
            return {
                "status": "fixture_checked",
                "monitor_invoked": False,
                "event_hash": payload.get("event_hash"),
                "event_type": str(payload.get("event_type") or "filing"),
                "symbol": str(payload.get("symbol") or "FIXTURE")[:40],
                "authorized_stored_source_only": True,
                "new_updates": 1,
            }
        from .research_monitor_runtime import run_company_research_monitor_once

        result = run_company_research_monitor_once(
            run_rows=self.query,
            run_statement=self.statement,
            sql_literal=sql_literal,
            sql_jsonb=sql_jsonb,
            limit=max(1, min(250, int(payload.get("limit") or 80))),
            min_interval_minutes=max(5, min(1440, int(payload.get("min_interval_minutes") or 15))),
            force=True,
        )
        return {"status": str(result.get("status") or "completed"),
                "monitor_invoked": True, "result": redact(result)}

    def _run_stale_task_and_lease_reaper(self, *, test_mode: bool, payload: dict[str, Any]) -> dict[str, Any]:
        if test_mode:
            rows = self.query(
                """/* routine:lease_reaper:test */
                SELECT count(*)::integer AS expired_active_leases
                FROM agent.task_leases
                WHERE status='ACTIVE' AND expires_at<=clock_timestamp()"""
            )
            return {"status": "fixture_checked", "reaper_invoked": False,
                    "observed": rows[0] if rows else {}}
        limit = max(1, min(100, int(payload.get("limit") or 20)))
        rows = self.statement(
            f"/* routine:lease_reaper */ SELECT agent.reap_runtime_leases({limit}) AS result"
        )
        result = _json_object(rows[0].get("result")) if rows else {}
        return {"status": "completed", "reaper_invoked": True, "result": redact(result)}

    def _run_zerodha_session_and_stream_watch(self, *, test_mode: bool, payload: dict[str, Any]) -> dict[str, Any]:
        result = self._doctor().run(component="zerodha", mode="test" if test_mode else "scan", persist=True)
        check = result["checks"][0]
        return {
            "status": check["status"],
            "doctor_run_key": result.get("run_key"),
            "health": check["observed"],
            "actionable_fix": check.get("actionable_fix"),
            "credential_value_read": False,
        }

    def _handler(self, routine_key: str) -> Callable[..., dict[str, Any]]:
        handlers = {
            "daily_system_health": self._run_daily_system_health,
            "obsidian_incremental_index": self._run_obsidian_incremental_index,
            "research_company_change_monitor": self._run_research_company_change_monitor,
            "stale_task_and_lease_reaper": self._run_stale_task_and_lease_reaper,
            "zerodha_session_and_stream_watch": self._run_zerodha_session_and_stream_watch,
        }
        return handlers[routine_key]

    def run(
        self,
        routine_key: str,
        *,
        trigger_kind: str = "manual",
        payload: dict[str, Any] | None = None,
        event_hash: str | None = None,
        idempotency_key: str | None = None,
        test_mode: bool = False,
        actor: str | None = None,
    ) -> dict[str, Any]:
        routine_key = _bounded_key(routine_key, "routine_key")
        if routine_key not in ROUTINE_KEYS:
            raise ValueError("routine is not in the reviewed allowlist")
        trigger_kind = str(trigger_kind or "").lower()
        if trigger_kind not in TRIGGER_KINDS:
            raise ValueError("invalid routine trigger")
        payload = dict(payload or {})
        definition = self._definition(routine_key)
        expected_trigger = str(definition.get("trigger_kind") or "")
        if expected_trigger == "event" and trigger_kind != "event":
            raise ValueError("event routine requires an event trigger")
        if expected_trigger == "schedule" and trigger_kind == "event":
            raise ValueError("scheduled routine rejects event triggers")
        if expected_trigger not in {"event", "schedule"}:
            raise RuntimeError("routine trigger contract is invalid")
        if not test_mode:
            if str(definition.get("control_state")) != "enabled":
                raise ValueError("routine is not explicitly enabled")
            if expected_trigger == "schedule" and definition.get("schedule_enabled") is not True:
                raise ValueError("scheduled routine is not enabled on the canonical scheduler")
            if expected_trigger == "event" and definition.get("schedule_enabled") is not False:
                raise RuntimeError("event routine must not enable periodic materialization")
        if trigger_kind == "event":
            event_hash = str(event_hash or payload.get("event_hash") or "").lower()
            if not re.fullmatch(r"[0-9a-f]{64}", event_hash):
                raise ValueError("event trigger requires a sha256 event_hash")
            payload["event_hash"] = event_hash
        elif event_hash is not None:
            event_hash = str(event_hash).lower()
            if not re.fullmatch(r"[0-9a-f]{64}", event_hash):
                raise ValueError("event_hash must be sha256")
        if idempotency_key is None:
            if event_hash:
                idempotency_key = f"{routine_key}:{event_hash}"
            elif trigger_kind == "schedule":
                due_at = str(payload.get("due_at") or "").strip()
                if not due_at:
                    raise ValueError("scheduled run requires due_at for idempotency")
                idempotency_key = f"{routine_key}:{due_at}"
            else:
                idempotency_key = f"{routine_key}:manual:{canonical_event_hash(payload)}"
        idempotency_key = _bounded_key(idempotency_key, "idempotency_key", minimum=8)
        actor_value = str(actor or self.actor)[:160]
        safe_payload = redact(payload)
        if not isinstance(safe_payload, dict):
            raise ValueError("routine payload must be an object")
        start = self._start(
            routine_key,
            trigger_kind=trigger_kind,
            event_hash=event_hash,
            idempotency_key=idempotency_key,
            payload=safe_payload,
            actor=actor_value,
            test_mode=test_mode,
        )
        if start.get("duplicate") is True or start.get("created") is False:
            return {
                **start,
                "duplicate_suppressed": True,
                "handler_invoked": False,
                "model_calls": 0,
                "broker_write_allowed": False,
            }
        run_key = str(start.get("run_key") or "")
        try:
            handler_result = self._handler(routine_key)(test_mode=test_mode, payload=safe_payload)
            artifact_payload = {
                "schema_version": 1,
                "routine_key": routine_key,
                "routine_version": start.get("routine_version"),
                "run_key": run_key,
                "trigger_kind": "test" if test_mode else trigger_kind,
                "event_hash": event_hash,
                "result": redact(handler_result),
                "model_calls": 0,
                "broker_write_allowed": False,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            artifact = self.artifact_writer(routine_key, run_key, artifact_payload) if self.artifact_writer else None
            if routine_key == "research_company_change_monitor" and artifact is None:
                raise RuntimeError("company monitor requires a durable external-SSD artifact writer")
            result_status = str(handler_result.get("status") or "")
            terminal = "partial" if result_status in {"failed", "warning", "partial", "degraded"} else "completed"
            finish = self._finish(
                run_key,
                status=terminal,
                summary=f"{routine_key} completed with {result_status or terminal}",
                evidence=[{"source": ROUTINE_TOOL_ALLOWLIST[routine_key],
                           "event_hash": event_hash, "test_mode": test_mode}],
                artifact=artifact,
            )
            return {
                **start,
                **finish,
                "created": True,
                "duplicate": False,
                "handler_invoked": True,
                "result": redact(handler_result),
                "artifact": artifact,
                "model_calls": 0,
                "private_data_egress_allowed": False,
                "client_write_allowed": False,
                "broker_write_allowed": False,
            }
        except Exception as exc:
            failure = {
                "error_type": type(exc).__name__,
                "error": str(redact(str(exc))),
            }
            self._finish(
                run_key,
                status="failed",
                summary=f"{routine_key} failed closed",
                evidence=[failure],
                error_code=type(exc).__name__[:120],
            )
            return {
                **start,
                "status": "failed",
                "handler_invoked": True,
                "error": failure,
                "model_calls": 0,
                "private_data_egress_allowed": False,
                "client_write_allowed": False,
                "broker_write_allowed": False,
            }


__all__ = [
    "ROUTINE_KEYS", "ROUTINE_TOOL_ALLOWLIST", "RoutineRuntime",
    "canonical_event_hash",
]
