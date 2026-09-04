"""Fenced ownership for the existing agent.tasks queue, using the current DB adapter.

No model/provider client, filesystem task executor, credential store or broker API
is present here. Task state never implies research readiness or capital authority.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import socket
import threading
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Callable
from uuid import UUID, uuid4

RUNTIME_VERSION = "lease-v1"
_fence: ContextVar["LeaseSession | None"] = ContextVar("aios_task_fence", default=None)


def literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def token_hash(value: str) -> str:
    if not isinstance(value, str) or len(value) < 32 or len(value) > 256:
        raise ValueError("a valid worker lease token is required")
    return hashlib.sha256(value.encode()).hexdigest()


class LeaseLost(RuntimeError):
    """The caller must stop; a newer owner may hold the task."""


class TaskControl(RuntimeError):
    def __init__(self, action: str):
        self.action = action
        super().__init__(f"Task {action} at a safe boundary")


def fence_sql(sql: str) -> str:
    session = _fence.get()
    if session is None:
        return sql
    session.ensure_alive()
    # No token is persisted or put in SQL. Only its one-way hash is compared.
    return f"BEGIN; DO $fence$ BEGIN PERFORM {session.assertion}; END $fence$;\n{sql.rstrip(';')};\nCOMMIT;"


class AgentRuntime:
    def __init__(self, execute: Callable[[str], str], *, worker_id: str | None = None):
        self.execute = execute
        self.worker_id = str(UUID(worker_id)) if worker_id else str(uuid4())
        self.registered = False

    def _call(self, name: str, *args: object) -> dict:
        # Function names are internal constants, never supplied by an API caller.
        result = self.execute(f"SELECT agent.{name}({','.join(literal(arg) for arg in args)})::text;")
        value = json.loads(result or "{}")
        if not isinstance(value, dict):
            raise RuntimeError("runtime database response was not an object")
        return value

    def available(self) -> bool:
        return self.execute("SELECT (to_regprocedure('agent.claim_runtime_task(uuid,bigint,bigint,text,boolean)') IS NOT NULL)::text;").strip() == "true"

    def register(self) -> dict:
        result = self._call("register_runtime_worker", self.worker_id, socket.gethostname(), os.getpid(), RUNTIME_VERSION, 1)
        self.registered = True
        return result

    def claim(self, task_id: int, agent_name: str, *, committee_reclaim: bool = False) -> "LeaseSession | None":
        if not self.registered:
            self.register()
        # Agent lookup uses the existing profile; no unknown display name creates
        # an identity or grants any role, tool, model or client permission.
        rows = json.loads(self.execute(
            f"SELECT coalesce(json_agg(id),'[]'::json)::text FROM agent.profiles WHERE agent_name={literal(agent_name)};"
        ) or "[]")
        if len(rows) != 1:
            return None
        secret = secrets.token_hex(32)
        result = self._call("claim_runtime_task", self.worker_id, int(task_id), int(rows[0]), token_hash(secret), str(committee_reclaim).lower())
        if not result:
            return None
        return LeaseSession(self, result, secret)

    def heartbeat(self, lease_id: int, token: str, *, state: str | None = None, request_key: str | None = None) -> dict:
        return self._call("heartbeat_runtime_lease", self.worker_id, int(lease_id), token_hash(token),
                          str(UUID(request_key)) if request_key else str(uuid4()), state)

    def control(self, task_id: int, action: str) -> dict:
        return self._call("request_runtime_control", int(task_id), action)

    def reap(self, limit: int = 20) -> dict:
        return self._call("reap_runtime_leases", max(1, min(100, int(limit))))

    def idle(self) -> dict:
        """Idle cadence for the pooled daemon, without claiming an agent is working."""
        return self._call("idle_runtime_worker", self.worker_id)


@dataclass
class LeaseSession:
    runtime: AgentRuntime
    claim: dict
    token: str = field(repr=False)
    _stop: threading.Event = field(default_factory=threading.Event, repr=False)
    _lost: threading.Event = field(default_factory=threading.Event, repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)
    _context_token: object = field(default=None, repr=False)
    _released: bool = False

    @property
    def assertion(self) -> str:
        return f"agent.assert_runtime_lease({literal(self.runtime.worker_id)},{int(self.claim['lease_id'])},{literal(token_hash(self.token))})"

    def ensure_alive(self) -> None:
        if self._lost.is_set() or self._released:
            raise LeaseLost("Task lease unavailable; stop and inspect recovery state")

    def _pulse(self) -> None:
        while not self._stop.wait(max(1, int(self.claim.get("heartbeat_seconds", 15)))):
            try:
                self.runtime.heartbeat(self.claim["lease_id"], self.token)
            except Exception:
                # Uncertain ownership is never permission to continue writing.
                # Do not store the DB error, request body or token in logs.
                self._lost.set()
                return

    def __enter__(self) -> "LeaseSession":
        self._context_token = _fence.set(self)
        self._thread = threading.Thread(target=self._pulse, name="aios-lease-heartbeat", daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_exc) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        if self._context_token is not None:
            _fence.reset(self._context_token)

    def checkpoint(self, step_key: str, state: str, *, side_effect: bool = False) -> dict:
        self.ensure_alive()
        response = self.runtime.heartbeat(self.claim["lease_id"], self.token)
        control = response.get("control_requested")
        if control or response.get("shutdown_requested"):
            action = control or "pause"
            self.finish("paused" if action == "pause" else "cancelled")
            raise TaskControl(action)
        return self.runtime._call("record_runtime_step", self.runtime.worker_id, self.claim["lease_id"],
                                  token_hash(self.token), step_key, state, str(side_effect).lower())

    def finish(self, outcome: str, receipt: str | None = None) -> dict:
        self.ensure_alive()
        result = self.runtime._call("finish_runtime_lease", self.runtime.worker_id, self.claim["lease_id"],
                                    token_hash(self.token), outcome, receipt)
        self._released = True
        self._stop.set()
        return result
