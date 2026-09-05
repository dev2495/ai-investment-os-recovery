#!/usr/bin/env python3
"""Operator CLI for the five disabled-by-default AI OS routines."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUNTIME_ROOT = Path(os.environ.get("AI_OS_RUNTIME_ROOT") or Path(__file__).resolve().parents[1])
REPO_ROOT = RUNTIME_ROOT.parent
for import_root in (REPO_ROOT, RUNTIME_ROOT, RUNTIME_ROOT / "api", RUNTIME_ROOT / "scripts"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from _ai_os_runtime.api.doctor_runtime import DoctorRuntime  # noqa: E402
from _ai_os_runtime.api.routine_runtime import (  # noqa: E402
    ROUTINE_KEYS,
    RoutineRuntime,
    canonical_event_hash,
)
from ai_os_doctor import Database, probes  # noqa: E402


def write_artifact(routine_key: str, run_key: str, payload: dict[str, Any]) -> dict[str, str]:
    volume = Path(os.environ.get("AI_OS_SSD_ROOT") or "/Volumes/Devarsh SSD")
    data_root = Path(os.environ.get("AI_OS_DATA_ROOT") or volume / "AI OS Data")
    try:
        data_root.relative_to(volume)
    except ValueError as exc:
        raise RuntimeError("routine artifact root is outside the configured external SSD") from exc
    if not volume.is_mount():
        raise RuntimeError("configured external SSD is not mounted")
    destination = data_root / "artifacts" / "routines" / routine_key
    destination.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, indent=2, sort_keys=True, default=str).encode("utf-8")
    digest = hashlib.sha256(body).hexdigest()
    final_path = destination / f"{run_key}.json"
    temporary = destination / f".{run_key}.{os.getpid()}.tmp"
    temporary.write_bytes(body)
    os.replace(temporary, final_path)
    return {"path": str(final_path), "sha256": digest}


def run_allowlisted_command(command_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    if command_key != "obsidian_incremental_index":
        raise ValueError("command is not in the routine command allowlist")
    command = [sys.executable, str(RUNTIME_ROOT / "scripts" / "index_obsidian_vault.py")]
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        timeout=650,
        env=os.environ.copy(),
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "Obsidian index failed")[:1000])
    try:
        result = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError("Obsidian index did not return JSON evidence") from exc
    if not isinstance(result, dict):
        raise RuntimeError("Obsidian index response was not an object")
    return result


def load_payload(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    source = Path(path)
    if not source.is_file() or source.stat().st_size > 1_000_000:
        raise ValueError("payload file must be a bounded local JSON file")
    value = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("payload JSON must be an object")
    return value


def fixture_filing() -> dict[str, Any]:
    return {
        "event_type": "filing",
        "source_kind": "fixture_safe_official_filing",
        "source_identifier": "fixture:research.corporate_filings:26001",
        "exchange": "NSE",
        "symbol": "FIXTURE",
        "title": "Fixture-safe quarterly filing event",
        "effective_at": "2026-09-05T00:00:00Z",
        "authorized_stored_source_only": True,
    }


def build_runtime(database: Database, actor: str) -> RoutineRuntime:
    return RoutineRuntime(
        database.query,
        database.statement,
        doctor_factory=lambda: DoctorRuntime(
            database.query, database.statement, probes=probes(), actor=actor
        ),
        command_runner=run_allowlisted_command,
        artifact_writer=write_artifact,
        actor=actor,
    )


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="List, test, run or explicitly control AI OS routines.")
    action = value.add_mutually_exclusive_group(required=True)
    action.add_argument("--list", action="store_true", help="List routine definitions and control state.")
    action.add_argument("--history", action="store_true", help="Show durable routine receipts.")
    action.add_argument("--test", action="store_true", help="Run a receipt-backed no-provider test.")
    action.add_argument("--run", action="store_true", help="Run an already-enabled routine.")
    action.add_argument("--enable", action="store_true", help="Explicitly enable a routine and its existing schedule.")
    action.add_argument("--pause", action="store_true", help="Pause a routine and its existing schedule.")
    action.add_argument("--disable", action="store_true", help="Disable a routine and its existing schedule.")
    action.add_argument("--fixture-filing", action="store_true", help="Run the stable M7 filing fixture once.")
    value.add_argument("--routine", choices=sorted(ROUTINE_KEYS))
    value.add_argument("--trigger", choices=("manual", "schedule", "event"), default="manual")
    value.add_argument("--event-hash", help="SHA-256 event identity for exact-once event routines.")
    value.add_argument("--payload-file", help="Bounded local JSON object; never use for credentials.")
    value.add_argument("--due-at", help="Stable schedule due timestamp used for idempotency.")
    value.add_argument("--idempotency-key")
    value.add_argument("--reason", default="")
    value.add_argument("--confirm", action="store_true", help="Confirm a routine control change.")
    value.add_argument("--limit", type=int, default=100)
    value.add_argument("--actor", default=os.environ.get("USER") or "operator")
    value.add_argument("--json", action="store_true", dest="as_json")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    database = Database()
    runtime = build_runtime(database, args.actor)
    if args.list:
        result: object = runtime.list_routines()
    elif args.history:
        result = runtime.history(routine_key=args.routine, limit=args.limit)
    elif args.enable or args.pause or args.disable:
        if not args.routine:
            raise SystemExit("--routine is required for control changes")
        action = "enable" if args.enable else ("pause" if args.pause else "disable")
        result = runtime.control(
            args.routine, action, confirmed=args.confirm, reason=args.reason, actor=args.actor
        )
    else:
        payload = fixture_filing() if args.fixture_filing else load_payload(args.payload_file)
        routine_key = "research_company_change_monitor" if args.fixture_filing else args.routine
        if not routine_key:
            raise SystemExit("--routine is required for a run or test")
        trigger = "event" if args.fixture_filing else args.trigger
        if args.due_at:
            payload["due_at"] = args.due_at
        event_hash = args.event_hash
        if trigger == "event" and not event_hash:
            event_hash = canonical_event_hash(payload)
        result = runtime.run(
            routine_key,
            trigger_kind=trigger,
            payload=payload,
            event_hash=event_hash,
            idempotency_key=args.idempotency_key,
            test_mode=bool(args.test or args.fixture_filing),
            actor=args.actor,
        )
    if args.as_json:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    elif isinstance(result, list):
        for row in result:
            print(
                f"{row.get('routine_key','?')}: "
                f"{row.get('control_state') or row.get('status') or 'unknown'}"
            )
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    if isinstance(result, dict) and result.get("status") == "failed":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
