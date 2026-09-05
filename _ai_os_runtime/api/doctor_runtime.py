"""Deterministic AI OS Doctor checks and tightly allowlisted safe repair.

The runtime consumes canonical database views and injected local probes. It
never calls a model, fetches a provider, reads credential values, changes a
client record, or writes to a broker. Unknown evidence is reported as unknown,
not converted to a healthy result.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4


QueryFn = Callable[[str], list[dict[str, Any]]]
StatementFn = Callable[[str], list[dict[str, Any]]]
ProbeFn = Callable[[], dict[str, Any]]

RESULT_STATES = {"passed", "warning", "failed", "unknown", "skipped"}
SAFE_FIX_ALLOWLIST = {"release_expired_leases"}
SENSITIVE_KEY_RE = re.compile(
    r"(?:^|_)(?:api_key|access_token|refresh_token|password|secret|client_secret|private_key|auth_token)(?:$|_)",
    re.IGNORECASE,
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"(?i)(api[_ -]?key|access[_ -]?token|password|client[_ -]?secret)\s*[:=]\s*\S+"),
)


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return f"{sql_literal(encoded)}::jsonb"


def _bounded_identifier(value: object, label: str) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", text):
        raise ValueError(f"{label} must be a bounded identifier")
    return text


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _scrub_string(value: str) -> str:
    scrubbed = value
    for pattern in SECRET_VALUE_PATTERNS:
        scrubbed = pattern.sub("[REDACTED]", scrubbed)
    return scrubbed[:4000]


def redact(payload: object) -> object:
    """Return JSON-safe evidence without credential values or unbounded text."""
    if isinstance(payload, dict):
        cleaned: dict[str, object] = {}
        for raw_key, raw_value in list(payload.items())[:200]:
            key = str(raw_key)[:160]
            if SENSITIVE_KEY_RE.search(key):
                # Presence/requirement booleans are safe and required by Doctor.
                cleaned[key] = raw_value if isinstance(raw_value, bool) else "[REDACTED]"
            else:
                cleaned[key] = redact(raw_value)
        return cleaned
    if isinstance(payload, (list, tuple)):
        return [redact(value) for value in list(payload)[:200]]
    if isinstance(payload, str):
        return _scrub_string(payload)
    if payload is None or isinstance(payload, (bool, int, float)):
        return payload
    return _scrub_string(str(payload))


def evidence_digest(observed: object) -> str:
    body = json.dumps(redact(observed), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def check_result(
    status: str,
    headline: str,
    observed: dict[str, Any] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    actionable_fix: str | None = None,
) -> dict[str, Any]:
    if status not in RESULT_STATES:
        raise ValueError("invalid Doctor result state")
    return {
        "status": status,
        "headline": _scrub_string(headline),
        "observed": redact(observed or {}),
        "evidence": redact(evidence or []),
        "actionable_fix": _scrub_string(actionable_fix) if actionable_fix else None,
    }


class DoctorRuntime:
    """Run registered checks through fixed handlers and persist bounded evidence."""

    HANDLERS = {
        "postgres_migration_level": "_check_postgres_migration_level",
        "external_ssd_storage": "_check_probe",
        "api_readiness": "_check_probe",
        "redis_health": "_check_probe",
        "qdrant_health": "_check_probe",
        "obsidian_index_lag": "_check_obsidian_index_lag",
        "backup_restore_receipt": "_check_probe",
        "worker_heartbeat": "_check_worker_heartbeat",
        "expired_task_leases": "_check_expired_task_leases",
        "queue_backlog": "_check_queue_backlog",
        "routine_scheduler": "_check_routine_scheduler",
        "model_route_health": "_check_model_route_health",
        "zerodha_session_stream": "_check_zerodha_session_stream",
        "tradingview_connector": "_check_tradingview_connector",
        "pythia_optional": "_check_probe",
        "ui_asset_equality": "_check_probe",
        "launchd_services": "_check_probe",
        "configuration_drift": "_check_probe",
        "execution_safety_locks": "_check_execution_safety_locks",
        "client_scope_isolation": "_check_client_scope_isolation",
        "changed_file_secret_scan": "_check_probe",
    }

    def __init__(
        self,
        query: QueryFn,
        statement: StatementFn | None = None,
        *,
        probes: dict[str, ProbeFn] | None = None,
        actor: str = "Jarvis",
    ):
        self.query = query
        self.statement = statement
        self.probes = probes or {}
        self.actor = str(actor or "Jarvis")[:160]
        self._selected_agent: str | None = None
        self._selected_model_route: str | None = None
        self._run_mode = "scan"

    def _one(self, sql: str) -> dict[str, Any]:
        rows = self.query(sql)
        return rows[0] if rows else {}

    def registry(
        self,
        *,
        component: str | None = None,
        check_key: str | None = None,
    ) -> list[dict[str, Any]]:
        component = _bounded_identifier(component, "component")
        check_key = _bounded_identifier(check_key, "check_key")
        clauses = ["enabled=true"]
        if component:
            clauses.append(f"component={sql_literal(component)}")
        if check_key:
            clauses.append(f"check_key={sql_literal(check_key)}")
        return self.query(
            "/* doctor:registry */ SELECT check_key,component,check_name,description,"
            "runner_key,failure_severity,timeout_seconds,safe_fix_key,configuration "
            "FROM ops.doctor_check_registry WHERE "
            + " AND ".join(clauses)
            + " ORDER BY component,check_key"
        )

    def _probe_result(self, registry: dict[str, Any]) -> dict[str, Any]:
        key = str(registry["check_key"])
        probe = self.probes.get(key)
        if probe is None:
            return check_result(
                "unknown",
                f"{registry['check_name']} has no local probe evidence",
                {"probe_available": False},
                [{"source": "local_probe", "check_key": key}],
                "Run Doctor on the canonical iMac runtime where this local probe is available.",
            )
        payload = probe()
        if not isinstance(payload, dict):
            raise RuntimeError("local probe did not return an object")
        supplied_status = str(payload.get("status") or "").lower()
        if supplied_status in RESULT_STATES:
            status = supplied_status
        elif payload.get("ok") is True:
            status = "passed"
        elif payload.get("ok") is False:
            status = "failed"
        else:
            status = "unknown"
        headline = str(payload.get("headline") or f"{registry['check_name']}: {status}")
        actionable = payload.get("actionable_fix")
        observed = {key_: value for key_, value in payload.items() if key_ not in {"status", "headline", "evidence", "actionable_fix"}}
        evidence = payload.get("evidence") if isinstance(payload.get("evidence"), list) else []
        return check_result(status, headline, observed, evidence, str(actionable) if actionable else None)

    def _check_probe(self, registry: dict[str, Any]) -> dict[str, Any]:
        return self._probe_result(registry)

    def _check_postgres_migration_level(self, registry: dict[str, Any]) -> dict[str, Any]:
        row = self._one(
            """/* doctor:postgres_migration_level */
            SELECT current_database() AS database_name,
                   coalesce(max(migration_number),0)::integer AS migration_number,
                   max(applied_at) AS latest_migration_at,
                   count(*) FILTER (WHERE migration_number=260
                     AND migration_key<>'260_ai_os_doctor_and_routines_v1')::integer AS conflicting_260
            FROM core.schema_migrations"""
        )
        minimum = _as_int((registry.get("configuration") or {}).get("minimum_migration"), 260)
        level = _as_int(row.get("migration_number"))
        conflict = _as_int(row.get("conflicting_260"))
        status = "passed" if level >= minimum and conflict == 0 else "failed"
        fix = None if status == "passed" else "Apply the missing reviewed migrations in order; do not edit the ledger manually."
        return check_result(
            status,
            f"Postgres migration level is {level}; required minimum is {minimum}",
            {**row, "minimum_migration": minimum},
            [{"source": "core.schema_migrations"}],
            fix,
        )

    def _check_obsidian_index_lag(self, registry: dict[str, Any]) -> dict[str, Any]:
        row = self._one(
            """/* doctor:obsidian_index_lag */
            WITH note_state AS (
              SELECT count(*) FILTER (WHERE deleted_at IS NULL)::integer AS note_count,
                     coalesce(max(greatest(0,extract(epoch FROM
                       (coalesce(last_modified_at,indexed_at)-indexed_at)))) FILTER
                       (WHERE deleted_at IS NULL),0)::integer AS lag_seconds,
                     max(indexed_at) FILTER (WHERE deleted_at IS NULL) AS latest_indexed_at
              FROM knowledge.obsidian_notes
            ), unresolved AS (
              SELECT count(*)::integer AS unresolved_links
              FROM knowledge.note_links link
              WHERE NOT EXISTS (
                SELECT 1 FROM knowledge.obsidian_notes note
                WHERE note.deleted_at IS NULL
                  AND (note.note_path=link.to_note_path
                    OR regexp_replace(note.note_path,'\\.md$','')=regexp_replace(link.to_note_path,'\\.md$',''))
              )
            )
            SELECT note_state.*,unresolved.unresolved_links FROM note_state CROSS JOIN unresolved"""
        )
        integrity_probe = self.probes.get("obsidian_integrity")
        integrity = integrity_probe() if integrity_probe else {}
        if not isinstance(integrity, dict):
            integrity = {}
        broken = integrity.get("broken_managed_blocks")
        warn_after = _as_int((registry.get("configuration") or {}).get("warn_after_seconds"), 900)
        lag = _as_int(row.get("lag_seconds"))
        unresolved = _as_int(row.get("unresolved_links"))
        if lag > warn_after or unresolved > 0 or _as_int(broken) > 0:
            status = "failed"
            fix = "Run the existing bounded Obsidian indexer, then inspect unresolved links; preserve all human-authored text."
        elif broken is None:
            status = "warning"
            fix = "Run on the canonical vault host to verify managed-block integrity."
        else:
            status = "passed"
            fix = None
        observed = {**row, "warn_after_seconds": warn_after, "broken_managed_blocks": broken}
        return check_result(
            status,
            f"Obsidian index lag is {lag}s with {unresolved} unresolved links",
            observed,
            [{"source": "knowledge.obsidian_notes"}, {"source": "knowledge.note_links"}],
            fix,
        )

    def _check_worker_heartbeat(self, _registry: dict[str, Any]) -> dict[str, Any]:
        row = self._one(
            """/* doctor:worker_heartbeat */
            SELECT (SELECT count(*) FROM agent.workers)::integer AS worker_count,
                   (SELECT count(*) FROM agent.workers
                     WHERE status IN ('STALE','STOPPED','QUARANTINED')
                        OR last_heartbeat_at<clock_timestamp()-interval '180 seconds')::integer AS stale_workers,
                   (SELECT coalesce(max(extract(epoch FROM
                     (clock_timestamp()-last_heartbeat_at))),0)::integer FROM agent.workers) AS max_worker_age_seconds,
                   (SELECT count(*) FROM core.v_runtime_daemon_health
                     WHERE health_status<>'healthy')::integer AS unhealthy_daemons"""
        )
        workers = _as_int(row.get("worker_count"))
        unhealthy = _as_int(row.get("stale_workers")) + _as_int(row.get("unhealthy_daemons"))
        status = "failed" if unhealthy else ("warning" if workers == 0 else "passed")
        fix = None if status == "passed" else "Inspect the supervised worker/daemon and its last receipt before an allowlisted restart."
        return check_result(status, f"{workers} workers registered; {unhealthy} heartbeat failures", row,
                            [{"source": "agent.workers"}, {"source": "core.v_runtime_daemon_health"}], fix)

    def _check_expired_task_leases(self, _registry: dict[str, Any]) -> dict[str, Any]:
        row = self._one(
            """/* doctor:expired_task_leases */
            SELECT count(*)::integer AS expired_active_leases,
                   min(expires_at) AS oldest_expiry,
                   count(*) FILTER (WHERE task.recovery_policy='idempotent_read'
                     AND task.output_note_path IS NULL)::integer AS potentially_recoverable
            FROM agent.task_leases lease
            JOIN agent.tasks task ON task.id=lease.task_id
            WHERE lease.status='ACTIVE' AND lease.expires_at<=clock_timestamp()"""
        )
        expired = _as_int(row.get("expired_active_leases"))
        return check_result(
            "failed" if expired else "passed",
            f"{expired} expired active task leases detected",
            row,
            [{"source": "agent.task_leases"}, {"source": "agent.tasks"}],
            "Apply the allowlisted receipt-aware expired lease reaper." if expired else None,
        )

    def _check_queue_backlog(self, registry: dict[str, Any]) -> dict[str, Any]:
        row = self._one(
            """/* doctor:queue_backlog */
            SELECT
              (SELECT count(*) FROM agent.tasks WHERE status='failed'
                 OR runtime_state='FAILED')::integer AS failed_tasks,
              (SELECT count(*) FROM agent.tasks WHERE runtime_state='RETRYING')::integer AS retrying_tasks,
              (SELECT count(*) FROM agent.tasks WHERE status='blocked'
                 OR runtime_state='BLOCKED')::integer AS blocked_tasks,
              (SELECT count(*) FROM agent.tasks WHERE status='queued'
                 AND created_at<clock_timestamp()-interval '30 minutes')::integer AS stale_queued_tasks,
              (SELECT count(*) FROM agent.agent_messages
                 WHERE processing_status IN ('pending','failed_retry','error','blocked')
                   AND created_at<clock_timestamp()-interval '5 minutes')::integer AS message_backlog,
              (SELECT count(*) FROM agent.inbox_items
                 WHERE status IN ('new','open')
                   AND created_at<clock_timestamp()-interval '1 day')::integer AS stale_inbox_items"""
        )
        total = sum(_as_int(row.get(key)) for key in (
            "failed_tasks", "retrying_tasks", "blocked_tasks", "stale_queued_tasks",
            "message_backlog", "stale_inbox_items",
        ))
        warning_count = _as_int((registry.get("configuration") or {}).get("warning_count"), 25)
        failed = _as_int(row.get("failed_tasks")) + _as_int(row.get("message_backlog"))
        status = "failed" if failed else ("warning" if total >= warning_count else "passed")
        return check_result(
            status,
            f"Task, message and inbox backlog contains {total} attention items",
            {**row, "attention_total": total, "warning_count": warning_count},
            [{"source": "agent.tasks"}, {"source": "agent.agent_messages"}, {"source": "agent.inbox_items"}],
            "Open the canonical task/message attention queues and resolve the oldest receipt-backed failures." if status != "passed" else None,
        )

    def _check_routine_scheduler(self, _registry: dict[str, Any]) -> dict[str, Any]:
        row = self._one(
            """/* doctor:routine_scheduler */
            SELECT count(*)::integer AS routine_count,
                   count(*) FILTER (WHERE schedule.enabled)::integer AS enabled_schedule_count,
                   count(*) FILTER (WHERE version.trigger_kind='event'
                     AND definition.control_state='enabled')::integer AS enabled_event_count,
                   count(*) FILTER (WHERE
                     (version.trigger_kind='schedule'
                       AND schedule.enabled<>(definition.control_state='enabled'))
                     OR (version.trigger_kind='event' AND schedule.enabled))::integer AS state_mismatches,
                   (SELECT status FROM agent.routine_runs ORDER BY started_at DESC,id DESC LIMIT 1) AS last_run_status,
                   (SELECT started_at FROM agent.routine_runs ORDER BY started_at DESC,id DESC LIMIT 1) AS last_run_at
            FROM agent.routine_definitions definition
            JOIN agent.workflow_schedules schedule USING(schedule_key)
            JOIN agent.routine_versions version
              ON version.routine_key=definition.routine_key
             AND version.version=definition.current_version"""
        )
        count = _as_int(row.get("routine_count"))
        mismatch = _as_int(row.get("state_mismatches"))
        failed_last = str(row.get("last_run_status") or "") in {"failed", "refused"}
        status = "failed" if count != 5 or mismatch else ("warning" if failed_last else "passed")
        return check_result(
            status,
            f"{count}/5 routines registered with {mismatch} scheduler state mismatches",
            row,
            [{"source": "agent.routine_definitions"}, {"source": "agent.workflow_schedules"},
             {"source": "agent.routine_runs"}],
            "Reconcile definition control state with the existing workflow schedule; never create a second scheduler." if status != "passed" else None,
        )

    def _check_model_route_health(self, _registry: dict[str, Any]) -> dict[str, Any]:
        route_filter = ""
        if self._selected_model_route:
            route_filter = f"WHERE control.route_name={sql_literal(self._selected_model_route)}"
        agent_filter = ""
        if self._selected_agent:
            agent_filter = f"AND profile.agent_key={sql_literal(self._selected_agent)}"
        row = self._one(
            f"""/* doctor:model_route_health */
            WITH route_state AS (
              SELECT control.route_name,control.task_class,control.enabled,
                     control.default_provider,control.default_model,
                     control.runtime_status,control.endpoint_key,
                     control.health_status,control.credential_ready,
                     qualification.state AS qualification_state,
                     qualification.expires_at AS qualification_expires_at,
                     qualification.provider AS qualification_provider,
                     qualification.model_name AS qualification_model,
                     qualification.endpoint_key AS qualification_endpoint,
                     qualification.adapter_version,
                     qualification.runtime_version
              FROM agent.v_model_route_runtime_control control
              LEFT JOIN LATERAL (
                SELECT value.state,value.expires_at,value.provider,value.model_name,
                       value.endpoint_key,value.adapter_version,value.runtime_version
                FROM agent.model_route_qualifications value
                WHERE value.route_name=control.route_name
                  AND value.task_class=control.task_class
                ORDER BY value.created_at DESC,value.id DESC LIMIT 1
              ) qualification ON true
              {route_filter}
            ), agent_state AS (
              SELECT profile.agent_name,assignment.primary_route,
                     primary_route.runtime_status AS primary_runtime_status,
                     cap.agent_name AS cap_agent
              FROM agent.profiles profile
              LEFT JOIN agent.agent_model_assignments assignment USING(agent_name)
              LEFT JOIN agent.v_model_route_runtime_control primary_route
                ON primary_route.route_name=assignment.primary_route
              LEFT JOIN agent.model_cost_caps cap USING(agent_name)
              WHERE profile.status='active' {agent_filter}
            )
            SELECT count(*)::integer AS route_count,
              count(*) FILTER (WHERE enabled AND runtime_status<>'ready')::integer AS unhealthy_enabled_routes,
              count(*) FILTER (WHERE enabled AND qualification_state IS NULL)::integer AS missing_qualifications,
              count(*) FILTER (WHERE enabled AND qualification_state='failed')::integer AS failed_qualifications,
              count(*) FILTER (WHERE enabled AND qualification_expires_at<=clock_timestamp())::integer AS expired_qualifications,
              count(*) FILTER (WHERE enabled AND qualification_state IS NOT NULL AND (
                qualification_provider<>default_provider
                OR qualification_model<>default_model
                OR coalesce(qualification_endpoint,'')<>coalesce(endpoint_key,'')
              ))::integer AS qualification_identity_mismatches,
              count(*) FILTER (WHERE enabled AND qualification_state IS NOT NULL AND (
                trim(coalesce(adapter_version,''))=''
                OR trim(coalesce(runtime_version,''))=''
              ))::integer AS qualification_version_gaps,
              count(*) FILTER (WHERE enabled AND endpoint_key IS NOT NULL
                AND health_status NOT IN ('configured','healthy','ready','active'))::integer AS unhealthy_endpoints,
              (SELECT count(*) FROM agent_state)::integer AS selected_agent_count,
              (SELECT count(*) FROM agent_state WHERE primary_route IS NULL)::integer AS selected_agent_assignment_missing,
              (SELECT count(*) FROM agent_state WHERE primary_route IS NOT NULL
                AND coalesce(primary_runtime_status,'missing')<>'ready')::integer AS selected_agent_binding_unready,
              (SELECT count(*) FROM agent_state WHERE cap_agent IS NULL)::integer AS selected_agent_cost_cap_missing
            FROM route_state"""
        )
        route_count = _as_int(row.get("route_count"))
        unhealthy = sum(_as_int(row.get(key)) for key in (
            "unhealthy_enabled_routes", "missing_qualifications",
            "failed_qualifications", "expired_qualifications",
            "qualification_identity_mismatches", "qualification_version_gaps",
            "unhealthy_endpoints",
        ))
        agent_missing = sum(_as_int(row.get(key)) for key in (
            "selected_agent_assignment_missing", "selected_agent_binding_unready",
            "selected_agent_cost_cap_missing",
        ))
        selected_count = _as_int(row.get("selected_agent_count"))
        if route_count == 0 or unhealthy or agent_missing or selected_count == 0:
            status = "failed"
        else:
            status = "passed"
        return check_result(
            status,
            f"{unhealthy} route identity/qualification failures and {agent_missing} agent binding/cap failures",
            row,
            [{"source": "agent.v_model_route_runtime_control"},
             {"source": "agent.model_route_qualifications"},
             {"source": "agent.agent_model_assignments"},
             {"source": "agent.model_cost_caps"}],
            "Keep the route fail-closed; repair endpoint identity/binding and requalify it before promotion." if status != "passed" else None,
        )

    def _check_zerodha_session_stream(self, _registry: dict[str, Any]) -> dict[str, Any]:
        row = self._one(
            """/* doctor:zerodha_session_stream */
            SELECT 'Zerodha'::text AS provider,
                   stream.health_status,stream.delay_status,stream.connection_state,
                   stream.latest_quote_at,stream.latest_quote_age_seconds,
                   stream.last_heartbeat_at,stream.heartbeat_age_seconds,
                   stream.subscribed_instruments,stream.quote_count,stream.live_count,
                   coalesce(stream.broker_write_allowed,false) AS broker_write_allowed,
                   readiness.requires_api_key,
                   coalesce(readiness.has_secret_ref,false) AS api_key_present,
                   readiness.readiness_status AS connector_readiness,
                   readiness.last_checked_at AS connector_checked_at,
                   CASE
                     WHEN extract(isodow FROM now() AT TIME ZONE 'Asia/Kolkata') BETWEEN 1 AND 5
                      AND (now() AT TIME ZONE 'Asia/Kolkata')::time BETWEEN time '09:15' AND time '15:30'
                      AND NOT EXISTS (
                        SELECT 1 FROM market.exchange_holidays holiday
                        WHERE holiday.exchange='NSE'
                          AND holiday.holiday_date=(now() AT TIME ZONE 'Asia/Kolkata')::date
                          AND holiday.session_status='closed'
                      ) THEN true ELSE false
                   END AS market_open
            FROM market.v_zerodha_stream_health stream
            LEFT JOIN core.v_provider_readiness_board readiness
              ON readiness.provider_kind='source_connector'
             AND readiness.provider_key='zerodha_live_connector'
            LIMIT 1"""
        )
        broker_safe = row.get("broker_write_allowed") is False
        key_present = _as_bool(row.get("api_key_present"))
        health = str(row.get("health_status") or "not_started")
        delay = str(row.get("delay_status") or "unknown")
        market_open = _as_bool(row.get("market_open"))
        if not broker_safe or not key_present:
            status = "failed"
        elif health == "live" and delay == "healthy":
            status = "passed"
        elif market_open and delay in {"delayed_quotes", "stale_heartbeat", "disconnected"}:
            status = "failed"
        else:
            status = "warning"
        if not key_present:
            fix = "Operator must restore the existing Keychain secret reference; never provide a Zerodha credential in chat."
        elif health == "login_required":
            fix = "Complete the existing daily human Zerodha login flow; do not automate credentials."
        elif status != "passed":
            fix = "Treat the quote as stale and block valuation or show a clearly labelled fallback; inspect the existing supervised stream."
        else:
            fix = None
        return check_result(
            status,
            f"Zerodha stream is {health}; quote delay state is {delay}",
            row,
            [{"source": "market.v_zerodha_stream_health"},
             {"source": "core.v_provider_readiness_board", "provider_key": "zerodha_live_connector"}],
            fix,
        )

    def _check_tradingview_connector(self, _registry: dict[str, Any]) -> dict[str, Any]:
        row = self._one(
            """/* doctor:tradingview_connector */
            SELECT count(*)::integer AS connector_count,
                   count(*) FILTER (WHERE readiness_status='ready')::integer AS ready_count,
                   count(*) FILTER (WHERE readiness_status LIKE 'blocked%'
                     OR readiness_status='degraded')::integer AS blocked_count
            FROM core.v_provider_readiness_board
            WHERE provider_kind='source_connector'
              AND (provider_key ILIKE '%tradingview%' OR provider ILIKE '%tradingview%')"""
        )
        count = _as_int(row.get("connector_count"))
        blocked = _as_int(row.get("blocked_count"))
        status = "failed" if blocked else ("warning" if count == 0 else "passed")
        return check_result(
            status,
            f"{count} TradingView connectors found; {blocked} blocked/degraded",
            row,
            [{"source": "core.v_provider_readiness_board"}],
            "Inspect the canonical read-only TradingView connector configuration." if status != "passed" else None,
        )

    def _check_execution_safety_locks(self, _registry: dict[str, Any]) -> dict[str, Any]:
        row = self._one(
            """/* doctor:execution_safety_locks */
            SELECT state_key,global_execution_locked,broker_execution_policy,
                   paper_trading_allowed,limited_live_allowed,live_broker_writes_allowed,
                   latest_global_kill_switch_at
            FROM trading.v_execution_control_state WHERE state_key='global' LIMIT 1"""
        )
        locked = _as_bool(row.get("global_execution_locked"))
        broker_writes = _as_bool(row.get("live_broker_writes_allowed"))
        status = "passed" if row and locked and not broker_writes else "failed"
        return check_result(
            status,
            "Global execution is locked and broker writes are false" if status == "passed"
            else "Global execution safety lock is missing or broker writes are enabled",
            row,
            [{"source": "trading.v_execution_control_state"}],
            "Stop autonomous work and restore the reviewed global execution lock." if status != "passed" else None,
        )

    def _check_client_scope_isolation(self, _registry: dict[str, Any]) -> dict[str, Any]:
        row = self._one(
            """/* doctor:client_scope_isolation */
            WITH protected AS (
              SELECT DISTINCT schemaname,tablename FROM pg_policies
              WHERE policyname='rd_scope_select'
            )
            SELECT count(*)::integer AS protected_table_count,
                   count(*) FILTER (WHERE NOT class.relrowsecurity
                     OR NOT class.relforcerowsecurity)::integer AS rls_violations
            FROM protected
            JOIN pg_namespace namespace ON namespace.nspname=protected.schemaname
            JOIN pg_class class ON class.relnamespace=namespace.oid
              AND class.relname=protected.tablename"""
        )
        count = _as_int(row.get("protected_table_count"))
        violations = _as_int(row.get("rls_violations"))
        status = "passed" if count > 0 and violations == 0 else "failed"
        return check_result(
            status,
            f"{count} scoped tables checked; {violations} RLS enforcement violations",
            row,
            [{"source": "pg_policies"}, {"source": "pg_class"}],
            "Restore ENABLE and FORCE ROW LEVEL SECURITY before serving scoped data." if status != "passed" else None,
        )

    def _compare_configuration_baseline(self, result: dict[str, Any]) -> dict[str, Any]:
        """Turn a clean config probe into explicit drift evidence."""
        if self._run_mode == "baseline" or result["status"] != "passed":
            return result
        baseline = self._one(
            """/* doctor:configuration_baseline */
            SELECT observed_digest,baseline->>'configuration_digest' AS configuration_digest,
                   captured_at,captured_by
            FROM ops.doctor_baselines WHERE check_key='configuration_drift' LIMIT 1"""
        )
        expected = str(baseline.get("configuration_digest") or "")
        current = str((result.get("observed") or {}).get("configuration_digest") or "")
        if not baseline or not expected:
            return check_result(
                "warning", "Configuration is readable but no reviewed baseline exists",
                {**(result.get("observed") or {}), "baseline_present": False},
                list(result.get("evidence") or []) + [{"source": "ops.doctor_baselines"}],
                "Run Doctor with --init-baseline after reviewing the watched configuration set.",
            )
        if current != expected:
            return check_result(
                "failed", "Watched configuration differs from the reviewed baseline",
                {**(result.get("observed") or {}), "baseline_present": True,
                 "expected_configuration_digest": expected,
                 "baseline_captured_at": baseline.get("captured_at")},
                list(result.get("evidence") or []) + [{"source": "ops.doctor_baselines"}],
                "Review the exact watched-file diff; accept it with a new baseline only after approval.",
            )
        result["observed"] = {**(result.get("observed") or {}), "baseline_present": True,
                              "baseline_captured_at": baseline.get("captured_at")}
        result["evidence"] = list(result.get("evidence") or []) + [{"source": "ops.doctor_baselines"}]
        return result

    def _execute_check(self, registry: dict[str, Any]) -> dict[str, Any]:
        start = time.monotonic()
        key = str(registry.get("check_key") or "")
        handler_name = self.HANDLERS.get(key)
        if not handler_name:
            result = check_result("unknown", f"No allowlisted Doctor handler for {key}",
                                  {"handler_available": False}, [], "Add and test an explicit handler.")
        else:
            try:
                result = getattr(self, handler_name)(registry)
                if key == "configuration_drift":
                    result = self._compare_configuration_baseline(result)
            except Exception as exc:
                result = check_result(
                    "unknown",
                    f"{registry.get('check_name') or key} could not be checked",
                    {"error_type": type(exc).__name__, "error": str(exc)},
                    [{"source": "doctor_runtime", "check_key": key}],
                    "Inspect the bounded check dependency; do not treat unavailable evidence as healthy.",
                )
        result["duration_ms"] = max(0, int((time.monotonic() - start) * 1000))
        result["check_key"] = key
        result["component"] = str(registry.get("component") or "unknown")
        configured_severity = str(registry.get("failure_severity") or "high")
        result["severity"] = (
            "info" if result["status"] == "passed"
            else "medium" if result["status"] in {"warning", "unknown", "skipped"}
            else configured_severity
        )
        return result

    def _persist_start(
        self,
        *,
        mode: str,
        component: str | None,
        agent_key: str | None,
        model_route: str | None,
    ) -> dict[str, Any]:
        if self.statement is None:
            raise RuntimeError("Doctor persistence adapter is unavailable")
        run_key = "doctor-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex[:8]
        rows = self.statement(
            f"""/* doctor:persist_start */
            INSERT INTO ops.doctor_runs(
              run_key,mode,status,requested_by,selected_component,
              selected_agent_key,selected_model_route
            ) VALUES (
              {sql_literal(run_key)},{sql_literal(mode)},'running',{sql_literal(self.actor)},
              {sql_literal(component)},{sql_literal(agent_key)},{sql_literal(model_route)}
            ) RETURNING id,run_key,mode,status,started_at"""
        )
        if not rows:
            raise RuntimeError("Doctor run receipt was not persisted")
        return rows[0]

    def _persist_result(self, run_id: int, result: dict[str, Any]) -> dict[str, Any]:
        if self.statement is None:
            raise RuntimeError("Doctor persistence adapter is unavailable")
        prior = self._one(
            f"""/* doctor:last_known_good */
            SELECT max(observed_at) AS last_known_good_at
            FROM ops.doctor_check_results
            WHERE check_key={sql_literal(result['check_key'])} AND status='passed'"""
        )
        last_known_good = (
            "clock_timestamp()" if result["status"] == "passed"
            else f"{sql_literal(prior.get('last_known_good_at'))}::timestamptz"
        )
        rows = self.statement(
            f"""/* doctor:persist_result */
            INSERT INTO ops.doctor_check_results(
              doctor_run_id,check_key,component,status,severity,headline,
              observed,evidence,actionable_fix,last_known_good_at,duration_ms
            ) VALUES (
              {int(run_id)},{sql_literal(result['check_key'])},{sql_literal(result['component'])},
              {sql_literal(result['status'])},{sql_literal(result['severity'])},
              {sql_literal(result['headline'])},{sql_jsonb(result['observed'])},
              {sql_jsonb(result['evidence'])},{sql_literal(result.get('actionable_fix'))},
              {last_known_good},{int(result['duration_ms'])}
            ) RETURNING id,observed_at,last_known_good_at"""
        )
        return rows[0] if rows else {}

    def _capture_baseline(self, result_id: int, result: dict[str, Any]) -> None:
        if self.statement is None or not result_id or result["status"] != "passed":
            return
        digest = evidence_digest(result["observed"])
        self.statement(
            f"""/* doctor:capture_baseline */
            INSERT INTO ops.doctor_baselines(
              check_key,source_result_id,observed_digest,baseline,captured_by
            ) VALUES (
              {sql_literal(result['check_key'])},{int(result_id)},{sql_literal(digest)},
              {sql_jsonb(result['observed'])},{sql_literal(self.actor)}
            ) ON CONFLICT(check_key) DO UPDATE SET
              source_result_id=EXCLUDED.source_result_id,
              observed_digest=EXCLUDED.observed_digest,
              baseline=EXCLUDED.baseline,
              captured_by=EXCLUDED.captured_by,
              captured_at=clock_timestamp()"""
        )

    def run(
        self,
        *,
        component: str | None = None,
        agent_key: str | None = None,
        model_route: str | None = None,
        check_key: str | None = None,
        mode: str = "scan",
        persist: bool = True,
    ) -> dict[str, Any]:
        component = _bounded_identifier(component, "component")
        agent_key = _bounded_identifier(agent_key, "agent_key")
        model_route = _bounded_identifier(model_route, "model_route")
        check_key = _bounded_identifier(check_key, "check_key")
        if mode not in {"scan", "baseline", "safe_fix", "test"}:
            raise ValueError("invalid Doctor mode")
        self._run_mode = mode
        self._selected_agent = agent_key
        self._selected_model_route = model_route
        registry = self.registry(component=component, check_key=check_key)
        if not registry:
            raise ValueError("no enabled Doctor checks matched the selection")
        receipt = self._persist_start(
            mode=mode, component=component, agent_key=agent_key, model_route=model_route
        ) if persist else {"id": None, "run_key": None, "mode": mode, "status": "running"}
        results: list[dict[str, Any]] = []
        for row in registry:
            result = self._execute_check(row)
            if persist:
                persisted = self._persist_result(int(receipt["id"]), result)
                result["result_id"] = persisted.get("id")
                result["observed_at"] = persisted.get("observed_at")
                result["last_known_good_at"] = persisted.get("last_known_good_at")
                if mode == "baseline":
                    self._capture_baseline(_as_int(persisted.get("id")), result)
            results.append(result)
        counts = {state: sum(1 for result in results if result["status"] == state) for state in RESULT_STATES}
        overall = "failed" if counts["failed"] else (
            "degraded" if counts["warning"] or counts["unknown"] else "passed"
        )
        summary = {
            "run_key": receipt.get("run_key"),
            "mode": mode,
            "status": overall,
            "selection": {"component": component, "agent_key": agent_key, "model_route": model_route,
                          "check_key": check_key},
            "counts": counts,
            "checks": results,
            "model_calls": 0,
            "private_data_egress_allowed": False,
            "external_write_allowed": False,
            "broker_write_allowed": False,
            "credential_change_allowed": False,
        }
        if persist and self.statement is not None:
            self.statement(
                f"""/* doctor:persist_finish */
                UPDATE ops.doctor_runs SET
                  status={sql_literal(overall)},check_count={len(results)},
                  passed_count={counts['passed']},warning_count={counts['warning']},
                  failed_count={counts['failed']},unknown_count={counts['unknown']},
                  summary={sql_jsonb({'counts': counts, 'selection': summary['selection']})},
                  finished_at=clock_timestamp()
                WHERE id={int(receipt['id'])} RETURNING id"""
            )
            summary["run_id"] = receipt["id"]
        return summary

    def safe_fix(self, *, check_key: str = "expired_task_leases", confirmed: bool = False) -> dict[str, Any]:
        check_key = _bounded_identifier(check_key, "check_key") or ""
        if not confirmed:
            raise ValueError("explicit safe-fix confirmation required")
        registry = self.registry(check_key=check_key)
        if len(registry) != 1:
            raise ValueError("exactly one Doctor check must be selected")
        safe_fix_key = str(registry[0].get("safe_fix_key") or "")
        if safe_fix_key not in SAFE_FIX_ALLOWLIST:
            raise ValueError("this check has no allowlisted safe fix")
        before_run = self.run(check_key=check_key, mode="safe_fix", persist=True)
        before = before_run["checks"][0]
        if safe_fix_key == "release_expired_leases" and before["status"] != "passed":
            rows = self.statement(
                "/* doctor:safe_fix:release_expired_leases */ "
                "SELECT agent.reap_runtime_leases(100) AS result"
            ) if self.statement else []
            action = rows[0].get("result") if rows else {}
            receipt_status = "applied"
        else:
            action = {"reason": "check_already_passed"}
            receipt_status = "no_change"
        after = self._execute_check(registry[0])
        receipt_key = "doctor-fix-" + uuid4().hex
        if self.statement is None:
            raise RuntimeError("Doctor persistence adapter is unavailable")
        self.statement(
            f"""/* doctor:persist_safe_fix */
            INSERT INTO ops.doctor_safe_fix_receipts(
              receipt_key,doctor_run_id,check_key,safe_fix_key,status,requested_by,
              before_evidence,after_evidence,result_summary
            ) VALUES (
              {sql_literal(receipt_key)},{int(before_run['run_id'])},{sql_literal(check_key)},
              {sql_literal(safe_fix_key)},{sql_literal(receipt_status)},{sql_literal(self.actor)},
              {sql_jsonb(before['observed'])},{sql_jsonb(after['observed'])},
              {sql_literal('Allowlisted receipt-aware lease reconciliation completed.')}
            ) RETURNING id"""
        )
        return {
            "receipt_key": receipt_key,
            "safe_fix_key": safe_fix_key,
            "status": receipt_status,
            "before": before,
            "action": redact(action),
            "after": after,
            "model_calls": 0,
            "credential_change_allowed": False,
            "broker_write_allowed": False,
        }


__all__ = [
    "DoctorRuntime", "SAFE_FIX_ALLOWLIST", "check_result", "evidence_digest",
    "redact", "sql_jsonb", "sql_literal",
]
