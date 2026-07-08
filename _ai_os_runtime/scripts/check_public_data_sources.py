#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
POSTGRES_PASSWORD = os.environ.get("AI_OS_POSTGRES_PASSWORD", "ai_os_local_dev_change_me")
POSTGRES_PORT = os.environ.get("AI_OS_POSTGRES_PORT", "54329")
USER_AGENT = os.environ.get(
    "AI_OS_PUBLIC_CHECK_USER_AGENT",
    "AI-OS-Research/0.1 contact=local@localhost",
)

CHECKS = [
    {
        "source_key": "sec_edgar",
        "check_name": "SEC submissions API Apple sample",
        "target_url": "https://data.sec.gov/submissions/CIK0000320193.json",
        "expect_json": True,
    },
    {
        "source_key": "sec_edgar",
        "check_name": "SEC company facts API Apple sample",
        "target_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json",
        "expect_json": True,
    },
    {
        "source_key": "nse_filings",
        "check_name": "NSE corporate announcements page",
        "target_url": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
        "expect_json": False,
    },
    {
        "source_key": "bse_filings",
        "check_name": "BSE corporate announcements page",
        "target_url": "https://www.bseindia.com/corporates/ann.html",
        "expect_json": False,
    },
]


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return f"{sql_literal(json.dumps(value or {}, sort_keys=True, default=str))}::jsonb"


def psql_command_candidates() -> list[list[str]]:
    return [
        [
            "docker", "exec", "-i", "ai_os_postgres", "psql",
            "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os",
        ],
        [
            "psql", "-h", "127.0.0.1", "-p", POSTGRES_PORT,
            "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os",
        ],
    ]


def run_psql_text(sql: str) -> str:
    errors = []
    env = os.environ.copy()
    env.setdefault("PGPASSWORD", POSTGRES_PASSWORD)
    for command in psql_command_candidates():
        completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False, env=env)
        if completed.returncode == 0:
            return completed.stdout.strip()
        errors.append((command[0], (completed.stderr or completed.stdout).strip()))
    raise RuntimeError(" | ".join(f"{source}: {error}" for source, error in errors))


def fetch(check: dict[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    request = urllib.request.Request(
        check["target_url"],
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read(12_000_000 if check.get("expect_json") else 600_000)
            latency_ms = int((time.monotonic() - started) * 1000)
            sample: dict[str, Any] = {
                "bytes_sampled": len(body),
                "content_type": response.headers.get("Content-Type"),
            }
            rows_seen = None
            if check.get("expect_json"):
                parsed = json.loads(body.decode("utf-8", errors="ignore"))
                if "filings" in parsed and "recent" in parsed["filings"]:
                    recent = parsed["filings"]["recent"]
                    accession_numbers = recent.get("accessionNumber") or []
                    rows_seen = len(accession_numbers)
                    sample["entity_name"] = parsed.get("name")
                    sample["ticker_sample"] = parsed.get("tickers", [])[:5]
                    sample["recent_forms"] = (recent.get("form") or [])[:5]
                elif "facts" in parsed:
                    facts = parsed.get("facts") or {}
                    rows_seen = sum(len(tags) for tags in facts.values() if isinstance(tags, dict))
                    sample["entity_name"] = parsed.get("entityName")
                    sample["taxonomy_keys"] = list(facts.keys())[:10]
                else:
                    rows_seen = len(parsed) if isinstance(parsed, list) else 1
                    sample["json_type"] = type(parsed).__name__
            else:
                text = body.decode("utf-8", errors="ignore")
                rows_seen = 1 if text else 0
                sample["title_present"] = "<title" in text.lower()
                sample["preview"] = " ".join(text[:400].split())
            return {
                **check,
                "status": "ok",
                "http_status": response.status,
                "latency_ms": latency_ms,
                "rows_seen": rows_seen,
                "sample_payload": sample,
                "error_message": None,
            }
    except urllib.error.HTTPError as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        return {
            **check,
            "status": "http_error",
            "http_status": exc.code,
            "latency_ms": latency_ms,
            "rows_seen": None,
            "sample_payload": {"reason": exc.reason},
            "error_message": str(exc),
        }
    except Exception as exc:  # keep all checks moving
        latency_ms = int((time.monotonic() - started) * 1000)
        return {
            **check,
            "status": "failed",
            "http_status": None,
            "latency_ms": latency_ms,
            "rows_seen": None,
            "sample_payload": {},
            "error_message": f"{type(exc).__name__}: {exc}",
        }


def store_results(results: list[dict[str, Any]]) -> None:
    values = []
    for result in results:
        values.append(
            "("
            f"{sql_literal(result['source_key'])},"
            f"{sql_literal(result['check_name'])},"
            "'http',"
            f"{sql_literal(result['target_url'])},"
            f"{sql_literal(result['status'])},"
            f"{result['http_status'] if result['http_status'] is not None else 'NULL'},"
            f"{result['latency_ms'] if result['latency_ms'] is not None else 'NULL'},"
            f"{result['rows_seen'] if result['rows_seen'] is not None else 'NULL'},"
            f"{sql_jsonb(result['sample_payload'])},"
            f"{sql_literal(result['error_message'])}"
            ")"
        )
    sql = f"""
    INSERT INTO core.data_source_checks (
        source_key, check_name, check_type, target_url, status, http_status,
        latency_ms, rows_seen, sample_payload, error_message
    )
    VALUES {",".join(values)};
    """
    run_psql_text(sql)


def main() -> int:
    results = [fetch(check) for check in CHECKS]
    store_results(results)
    summary = {
        "checks": len(results),
        "ok": sum(1 for row in results if row["status"] == "ok"),
        "non_ok": sum(1 for row in results if row["status"] != "ok"),
        "results": [
            {
                "source_key": row["source_key"],
                "check_name": row["check_name"],
                "status": row["status"],
                "http_status": row["http_status"],
                "latency_ms": row["latency_ms"],
                "rows_seen": row["rows_seen"],
                "error_message": row["error_message"],
            }
            for row in results
        ],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
