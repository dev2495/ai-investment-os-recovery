#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import os
import subprocess
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
POSTGRES_PASSWORD = os.environ.get("AI_OS_POSTGRES_PASSWORD", "ai_os_local_dev_change_me")
POSTGRES_PORT = os.environ.get("AI_OS_POSTGRES_PORT", "54329")
USER_AGENT = os.environ.get("AI_OS_PUBLIC_CHECK_USER_AGENT", "AI-OS-Research/1.0 contact=local@localhost")


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return sql_literal(json.dumps(value, sort_keys=True, default=str)) + "::jsonb"


def run_psql(sql: str) -> str:
    commands = [
        ["docker", "exec", "-i", "ai_os_postgres", "psql", "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os"],
        ["psql", "-h", "127.0.0.1", "-p", POSTGRES_PORT, "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os"],
    ]
    errors: list[str] = []
    env = os.environ.copy()
    env.setdefault("PGPASSWORD", POSTGRES_PASSWORD)
    for command in commands:
        completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False, env=env)
        if completed.returncode == 0:
            return completed.stdout.strip()
        errors.append((completed.stderr or completed.stdout).strip())
    raise RuntimeError(" | ".join(errors))


def fetch(url: str, accept: str) -> tuple[bytes, int]:
    started = time.monotonic()
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read(15_000_000)
    return body, int((time.monotonic() - started) * 1000)


def world_bank_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indicators = {
        "NY.GDP.MKTP.CD": ("GDP current USD", "USD"),
        "NY.GDP.MKTP.KD.ZG": ("Real GDP growth", "percent"),
        "FP.CPI.TOTL.ZG": ("Consumer price inflation", "percent"),
    }
    rows: list[dict[str, Any]] = []
    total_latency = 0
    for country in ("IN", "US"):
        for series, (name, unit) in indicators.items():
            url = f"https://api.worldbank.org/v2/country/{country}/indicator/{series}?format=json&per_page=20"
            body, latency = fetch(url, "application/json")
            total_latency += latency
            payload = json.loads(body.decode("utf-8"))
            for item in (payload[1] if isinstance(payload, list) and len(payload) > 1 else []):
                if item.get("value") is None or not str(item.get("date") or "").isdigit():
                    continue
                rows.append({
                    "source_key": "world_bank_macro", "series_key": series, "series_name": name,
                    "geography": item.get("countryiso3code") or country,
                    "observation_date": f"{item['date']}-12-31", "value": item.get("value"),
                    "unit": unit, "frequency": "annual", "source_url": url,
                    "raw_payload": {"country": item.get("country"), "last_updated": payload[0].get("lastupdated")},
                })
    return rows, {"latency_ms": total_latency, "series_requests": 6}


def ecb_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    start = (date.today() - timedelta(days=120)).isoformat()
    rows: list[dict[str, Any]] = []
    total_latency = 0
    for currency in ("USD", "GBP", "JPY"):
        url = f"https://data-api.ecb.europa.eu/service/data/EXR/D.{currency}.EUR.SP00.A?startPeriod={start}&format=csvdata"
        body, latency = fetch(url, "text/csv")
        total_latency += latency
        for item in csv.DictReader(io.StringIO(body.decode("utf-8-sig"))):
            if not item.get("TIME_PERIOD") or not item.get("OBS_VALUE"):
                continue
            rows.append({
                "source_key": "ecb_data_api", "series_key": f"EXR.D.{currency}.EUR.SP00.A",
                "series_name": item.get("TITLE_COMPL") or item.get("TITLE") or f"{currency}/EUR reference rate",
                "geography": "Euro area", "observation_date": item["TIME_PERIOD"],
                "value": item["OBS_VALUE"], "unit": item.get("UNIT") or currency,
                "frequency": item.get("FREQ") or "D", "source_url": url,
                "raw_payload": {"status": item.get("OBS_STATUS"), "currency": currency, "denominator": "EUR"},
            })
    return rows, {"latency_ms": total_latency, "series_requests": 3}


def store(source_key: str, rows: list[dict[str, Any]], metadata: dict[str, Any]) -> None:
    values = []
    for row in rows:
        values.append("(" + ",".join([
            sql_literal(row["source_key"]), sql_literal(row["series_key"]), sql_literal(row["series_name"]),
            sql_literal(row["geography"]), sql_literal(row["observation_date"]) + "::date",
            str(row["value"]), sql_literal(row["unit"]), sql_literal(row["frequency"]),
            sql_literal(row["source_url"]), sql_jsonb(row["raw_payload"]),
        ]) + ")")
    if not values:
        raise RuntimeError(f"{source_key} returned no usable observations")
    connector_key = f"{source_key}_connector"
    sample = {**metadata, "rows": len(rows), "series": sorted({row["series_key"] for row in rows})}
    run_psql(f"""
        WITH upserted AS (
            INSERT INTO market.macro_observations (
                source_key,series_key,series_name,geography,observation_date,
                observation_value,unit,frequency,source_url,raw_payload
            ) VALUES {','.join(values)}
            ON CONFLICT (source_key,series_key,geography,observation_date) DO UPDATE SET
                series_name=EXCLUDED.series_name,observation_value=EXCLUDED.observation_value,
                unit=EXCLUDED.unit,frequency=EXCLUDED.frequency,source_url=EXCLUDED.source_url,
                raw_payload=EXCLUDED.raw_payload,retrieved_at=now()
            RETURNING id
        ), checked AS (
            INSERT INTO core.connector_health_checks (
                target_kind,target_key,check_name,check_type,status,latency_ms,
                rows_seen,sample_payload,checked_by
            ) VALUES ('data_source_connector',{sql_literal(connector_key)},
                {sql_literal(source_key + ' live data ingestion')},'live_http','configured',
                {int(metadata.get('latency_ms') or 0)},{len(rows)},{sql_jsonb(sample)},'Macro Researcher')
            RETURNING id
        ), source_checked AS (
            INSERT INTO core.data_source_checks (
                source_key,check_name,check_type,target_url,status,http_status,
                latency_ms,rows_seen,sample_payload,error_message
            ) VALUES ({sql_literal(source_key)},{sql_literal(source_key + ' live data ingestion')},
                'official_api_ingestion',{sql_literal(rows[0]['source_url'])},'ok',200,
                {int(metadata.get('latency_ms') or 0)},{len(rows)},{sql_jsonb(sample)},NULL)
            RETURNING id
        )
        UPDATE core.source_connector_profiles
        SET health_status='configured',last_checked_at=now(),last_latency_ms={int(metadata.get('latency_ms') or 0)},
            last_rows_seen={len(rows)},last_error=NULL,updated_at=now()
        WHERE connector_key={sql_literal(connector_key)};
        UPDATE core.data_source_registry SET last_seen_at=now(),status='active',updated_at=now()
        WHERE source_key={sql_literal(source_key)};
    """)


def main() -> int:
    result: dict[str, Any] = {"status": "completed", "sources": {}}
    for source_key, loader in (("world_bank_macro", world_bank_rows), ("ecb_data_api", ecb_rows)):
        try:
            rows, metadata = loader()
            store(source_key, rows, metadata)
            result["sources"][source_key] = {"status": "configured", "rows": len(rows), **metadata}
        except Exception as exc:  # keep independent public sources isolated
            result["status"] = "partial"
            result["sources"][source_key] = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
