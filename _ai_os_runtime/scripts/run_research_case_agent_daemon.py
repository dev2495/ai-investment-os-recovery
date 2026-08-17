#!/usr/bin/env python3
"""Continuously advance explicitly approved public-company Research Cases."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
RUNTIME_ROOT = SCRIPT_DIR.parent
for candidate in (RUNTIME_ROOT, RUNTIME_ROOT / "api"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from run_research_case_agent_once import run_once  # noqa: E402


_STOP = False


def _stop(_signum, _frame):
    global _STOP
    _STOP = True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--idle-seconds", type=float, default=15.0)
    parser.add_argument("--step-seconds", type=float, default=2.0)
    parser.add_argument("--error-seconds", type=float, default=30.0)
    args = parser.parse_args()
    if min(args.idle_seconds, args.step_seconds, args.error_seconds) <= 0:
        parser.error("all intervals must be positive")

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    print(json.dumps({"event": "research_case_agent_daemon_started"}), flush=True)
    while not _STOP:
        try:
            result = run_once()
            print(json.dumps(result, sort_keys=True, default=str), flush=True)
            delay = args.idle_seconds if result.get("status") == "idle" else args.step_seconds
        except Exception as exc:
            print(json.dumps({"status": "error", "error": f"{type(exc).__name__}: {exc}"}), file=sys.stderr, flush=True)
            delay = args.error_seconds
        deadline = time.monotonic() + delay
        while not _STOP and time.monotonic() < deadline:
            time.sleep(min(0.5, deadline - time.monotonic()))
    print(json.dumps({"event": "research_case_agent_daemon_stopped"}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
