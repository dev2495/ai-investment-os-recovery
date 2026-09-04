"""Bounded, metadata-only API for canonical task leases. No model or broker calls."""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
import hmac
import json
import re
import threading
import time
from uuid import UUID

try:
    from .agent_runtime import literal, token_hash
except ImportError:
    from agent_runtime import literal, token_hash


class RuntimeRequestError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def positive_id(value) -> int:
    if isinstance(value, bool) or not re.fullmatch(r"[1-9][0-9]{0,17}", str(value)):
        raise RuntimeRequestError("A positive numeric record ID is required.")
    return int(value)


def cursor_id(value) -> int:
    if not re.fullmatch(r"[0-9]{1,18}", str(value)):
        raise RuntimeRequestError("The event cursor must be a non-negative integer.")
    return int(value)


def require_worker_auth(headers, operator_token: str) -> None:
    # Heartbeats cannot use the UI's optional tokenless-loopback exception.
    supplied = headers.get("Authorization", "")
    supplied = supplied[7:].strip() if supplied.lower().startswith("bearer ") else headers.get("X-AI-OS-Operator-Token", "").strip()
    if not operator_token or not supplied or not hmac.compare_digest(supplied, operator_token):
        raise RuntimeRequestError("Worker authentication is required.", 403)


class RuntimeAPI:
    def __init__(self, execute):
        self.execute = execute
        self._replay_lock = threading.Lock()
        self._replay_cache = OrderedDict()
        self.stream_slots = threading.BoundedSemaphore(16)

    def _value(self, query: str):
        # These limits are transaction-local to the short-lived existing adapter.
        raw = self.execute("SET statement_timeout='5s'; SET lock_timeout='1s'; " + query)
        return json.loads(raw or "null")

    def rows(self, query: str) -> list[dict]:
        return self._value(f"SELECT coalesce(json_agg(row_to_json(r)),'[]'::json)::text FROM ({query}) r;") or []

    def ready(self) -> bool:
        return bool(self._value("SELECT (to_regclass('agent.v_runtime_presence') IS NOT NULL)::text;"))

    def snapshot(self) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        if not self.ready():
            return {"available": False, "generated_at": now, "reason": "lease_migration_not_installed",
                    "agents": [], "workers": [], "tasks": [], "events": [], "event_cursor": 0,
                    "broker_write_allowed": False}
        # Operational IDs/states only: no client names, task bodies, model inputs,
        # credentials, local paths, node names or lease hashes on the shared office.
        data = self._value("""
            SELECT json_build_object(
                'agents',(SELECT coalesce(json_agg(row_to_json(r)),'[]') FROM
                    (SELECT * FROM agent.v_runtime_presence ORDER BY agent_id LIMIT 500) r),
                'workers',(SELECT coalesce(json_agg(row_to_json(r)),'[]') FROM
                    (SELECT id,runtime_version,max_parallel_tasks,shutdown_requested,started_at,last_heartbeat_at,
                        CASE WHEN last_heartbeat_at<clock_timestamp()-interval '180 seconds'
                            AND status NOT IN ('STOPPED','QUARANTINED') THEN 'STALE' ELSE status END status,
                        (SELECT count(*) FROM agent.task_leases l WHERE l.worker_id=w.id AND l.status='ACTIVE'
                            AND l.expires_at>clock_timestamp()) active_leases
                     FROM agent.workers w ORDER BY last_heartbeat_at DESC LIMIT 64) r),
                'tasks',(SELECT coalesce(json_agg(row_to_json(r)),'[]') FROM
                    (SELECT t.id,t.agent_id,t.status,t.runtime_state,t.control_requested,t.recovery_policy,t.updated_at,
                        l.id lease_id,l.worker_id,l.expires_at,l.attempt,l.recovery_reason,
                        CASE WHEN l.status='ACTIVE' THEN l.status ELSE NULL END lease_status,
                        EXISTS(SELECT 1 FROM agent.task_steps s WHERE s.task_id=t.id AND s.side_effect_status<>'none') has_side_effects
                     FROM agent.tasks t LEFT JOIN LATERAL(SELECT * FROM agent.task_leases WHERE task_id=t.id ORDER BY id DESC LIMIT 1) l ON true
                     WHERE t.runtime_protocol='lease_v1' AND t.runtime_scope='internal'
                     ORDER BY t.updated_at DESC,t.id DESC LIMIT 100) r),
                'events',(SELECT coalesce(json_agg(row_to_json(r)),'[]') FROM
                    (SELECT id,task_id,agent_id,worker_id,lease_id,event_type,state,reason_code,occurred_at
                     FROM agent.task_events ORDER BY id DESC LIMIT 30) r),
                'event_cursor',(SELECT coalesce(max(id),0) FROM agent.task_events)
            )::text;
        """)
        return {"available": True, "generated_at": now, "limits": {"agents": 500, "workers": 64, "tasks": 100, "events": 30},
                "presence_contract": "unexpired_lease_and_healthy_worker", "broker_write_allowed": False, **data}

    def task(self, task_id) -> dict:
        task_id = positive_id(task_id)
        rows = self.rows(f"""SELECT id,agent_id,status,runtime_state,control_requested,recovery_policy,updated_at
            FROM agent.tasks WHERE id={task_id} AND runtime_protocol='lease_v1' AND runtime_scope='internal'""")
        if not rows:
            raise RuntimeRequestError("Managed task not found in the shared runtime scope.", 404)
        steps = self.rows(f"""SELECT id,lease_id,step_key,state,side_effect_status,started_at,finished_at,
            (receipt_ref IS NOT NULL) has_receipt FROM agent.task_steps WHERE task_id={task_id} ORDER BY id DESC LIMIT 100""")
        return {"task": rows[0], "steps": steps, "broker_write_allowed": False}

    def control(self, task_id, action: str) -> dict:
        self.task(task_id)  # Enforce the same read/control scope; no generic SQL endpoint.
        if action not in ("pause", "resume", "cancel"):
            raise RuntimeRequestError("Only pause, resume and cancel are supported.")
        try:
            return self._value(f"SELECT agent.request_runtime_control({positive_id(task_id)},{literal(action)})::text;")
        except Exception as exc:
            raise RuntimeRequestError("Task state changed or a side-effect receipt needs reconciliation. Refresh the task before trying again.", 409) from exc

    def heartbeat(self, agent_id, payload: dict) -> dict:
        allowed = {"worker_id", "lease_id", "lease_token", "request_key", "presence_state"}
        if not isinstance(payload, dict) or set(payload)-allowed:
            raise RuntimeRequestError("Heartbeat accepts only worker/lease identity, request key and presence state.")
        try:
            agent_id = positive_id(agent_id)
            worker = str(UUID(payload["worker_id"]))
            lease = positive_id(payload["lease_id"])
            request = str(UUID(payload["request_key"]))
            digest = token_hash(payload["lease_token"])
            state = payload.get("presence_state")
            if state is not None and (not isinstance(state, str) or not re.fullmatch(r"[A-Z_]{2,48}", state)):
                raise ValueError("invalid state")
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise RuntimeRequestError("Invalid worker heartbeat identity or state.") from exc
        if not self.rows(f"SELECT id FROM agent.task_leases WHERE id={lease} AND agent_id={agent_id} AND worker_id={literal(worker)}"):
            raise RuntimeRequestError("Worker does not own this agent lease.", 409)
        try:
            return self._value(f"SELECT agent.heartbeat_runtime_lease({literal(worker)},{lease},{literal(digest)},{literal(request)},{literal(state)})::text;")
        except Exception as exc:
            raise RuntimeRequestError("Lease expired, ownership changed, or presence transition is not permitted. Stop this worker task.", 409) from exc

    def replay(self, after: int) -> dict:
        after = cursor_id(after)
        # Identical connected cursors share one DB read per two seconds. No Redis
        # is required; this small cache is never the replay authority.
        with self._replay_lock:
            cached = self._replay_cache.get(after)
            if cached and time.monotonic()-cached[0] < 2:
                return cached[1]
            result = self._value(f"""SELECT json_build_object(
                'latest',(SELECT coalesce(max(id),0) FROM agent.task_events),
                'events',(SELECT coalesce(json_agg(row_to_json(r)),'[]') FROM
                    (SELECT id,task_id,agent_id,worker_id,lease_id,event_type,state,reason_code,occurred_at
                     FROM agent.task_events WHERE id>{after} ORDER BY id LIMIT 201) r)
                )::text;""")
            result["reset_required"] = len(result["events"]) > 200 or after > result["latest"]
            if result["reset_required"]:
                result["events"] = []
            self._replay_cache[after] = (time.monotonic(), result)
            self._replay_cache.move_to_end(after)
            while len(self._replay_cache) > 64:
                self._replay_cache.popitem(last=False)
            return result


def stream_events(handler, api: RuntimeAPI, after: int) -> None:
    """Finite SSE connections bound threads/socket writes; clients resume on close."""
    if not api.stream_slots.acquire(blocking=False):
        raise RuntimeRequestError("Event stream capacity reached; use the office snapshot temporarily.", 429)
    started = False
    try:
        first = api.replay(after)  # Fail with ordinary JSON before streaming headers.
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("X-Accel-Buffering", "no")
        handler.send_header("Connection", "close")
        handler.send_header("Access-Control-Allow-Origin", handler._cors_origin())
        handler.send_header("Vary", "Origin")
        handler.end_headers()
        started = True
        handler.connection.settimeout(3)
        deadline = time.monotonic()+25
        batch = first
        while time.monotonic() < deadline:
            if batch["reset_required"]:
                handler.wfile.write(("event: reset\ndata: " + json.dumps({"cursor": batch["latest"], "reason": "snapshot_required"}) + "\n\n").encode())
                handler.wfile.flush()
                break
            for event in batch["events"]:
                after = event["id"]
                handler.wfile.write((f"id: {after}\nevent: runtime\ndata: " + json.dumps(event, separators=(",", ":")) + "\n\n").encode())
            handler.wfile.write(b": heartbeat\n\n")
            handler.wfile.flush()
            time.sleep(2)
            batch = api.replay(after)
    except (BrokenPipeError, ConnectionResetError, TimeoutError):
        pass
    except Exception:
        if not started:
            raise
        # Do not expose database errors or interleave JSON into the SSE body.
    finally:
        if started:
            handler.close_connection = True
        api.stream_slots.release()


def overlay_office_presence(snapshot: dict, runtime: dict) -> dict:
    """Do not convert historical activity/role configuration into a live worker."""
    by_name = {row["agent_name"]: row for row in runtime.get("agents", [])}
    for collection in ("agents", "live_office_agent_activity"):
        snapshot[collection] = [
            {**row, "historical_presence_state": row.get("presence_state", row.get("live_state")),
             "presence_state": by_name.get(row.get("agent_name"), {}).get("state", "UNVERIFIED"),
             "has_live_lease": by_name.get(row.get("agent_name"), {}).get("has_live_lease", False),
             "lease_expires_at": by_name.get(row.get("agent_name"), {}).get("expires_at")}
            for row in snapshot.get(collection, [])
        ]
    snapshot["runtime"] = runtime
    # Room activity counts follow the same lease evidence as individual agents.
    for room in snapshot.get("live_office_rooms", []):
        room_key = str(room.get("room_key", "")).lower().replace(" ", "_")
        candidates = {
            row.get("agent_name") for row in snapshot.get("agents", []) + snapshot.get("live_office_agent_activity", [])
            if str(row.get("department_key", row.get("department", ""))).lower().replace(" ", "_") == room_key
        }
        room["historical_executing_agent_count"] = room.get("executing_agent_count")
        room["executing_agent_count"] = sum(bool(by_name.get(name, {}).get("has_live_lease")) for name in candidates)
        if room.get("room_state") in ("working", "executing", "active") and not room["executing_agent_count"]:
            room["room_state"] = "unverified"
    return snapshot
