#!/usr/bin/env python3
"""Bounded, restartable Phase 2 observation soak; no models or broker writes.

Uses the canonical loopback API and records only counts, states and timing.
It does not claim that observing idle workers proves active-workload endurance.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import urllib.request


def assess(samples: list[dict], required_seconds: int = 86400) -> dict:
    elapsed = samples[-1]["epoch"] - samples[0]["epoch"] if len(samples) > 1 else 0
    gaps = [b["epoch"] - a["epoch"] for a, b in zip(samples, samples[1:])]
    failures = sum(not row.get("ok", False) for row in samples)
    complete = elapsed >= required_seconds and failures == 0 and max(gaps, default=0) <= 180
    return {"status": "passed" if complete else "pending" if elapsed < required_seconds else "failed",
            "elapsed_seconds": elapsed, "required_seconds": required_seconds,
            "samples": len(samples), "failed_samples": failures, "maximum_gap_seconds": max(gaps, default=0),
            "active_worker_samples": sum(row.get("active_leases", 0) > 0 for row in samples),
            "scope": "runtime_observation_only", "active_workload_endurance_accepted": False,
            "broker_write_allowed": False}


def get_json(path: str) -> dict:
    with urllib.request.urlopen("http://127.0.0.1:8765" + path, timeout=10) as response:
        return json.load(response)


def sample() -> dict:
    row = {"epoch": time.time(), "checked_at": datetime.now(timezone.utc).isoformat(), "ok": False}
    try:
        health = get_json("/api/health")
        runtime = get_json("/api/v1/office/snapshot").get("runtime", {})
        row.update(ok=health.get("ok") is True and runtime.get("available") is True
                   and runtime.get("broker_write_allowed") is False,
                   agents=len(runtime.get("agents", [])), workers=len(runtime.get("workers", [])),
                   active_leases=sum(int(w.get("active_leases", 0)) for w in runtime.get("workers", [])),
                   event_cursor=runtime.get("event_cursor", 0))
    except Exception as error:
        row["error_type"] = type(error).__name__
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-key", required=True)
    args = parser.parse_args()
    if not args.run_key.startswith("phase2-") or not args.run_key.replace("-", "").isalnum() or len(args.run_key) > 80:
        parser.error("run key must be a bounded phase2 identifier")
    root = Path(os.environ["AI_OS_DATA_ROOT"]).resolve() / "artifacts" / "phase2-soak"
    root.mkdir(parents=True, exist_ok=True)
    target = root / (args.run_key + ".json")
    samples = json.loads(target.read_text())["observations"] if target.exists() else []
    while True:
        samples.append(sample())
        result = assess(samples)
        payload = {"run_key": args.run_key, "assessment": result, "observations": samples}
        temp = target.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, indent=2) + "\n")
        temp.replace(target)
        if result["elapsed_seconds"] >= 86400:
            print(json.dumps(result), flush=True)
            return 0 if result["status"] == "passed" else 1
        time.sleep(60)


if __name__ == "__main__":
    raise SystemExit(main())
