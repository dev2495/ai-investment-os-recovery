#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
from typing import Any


def run_psql(sql: str, tuples_only: bool = False) -> str:
    command = [
        "docker",
        "exec",
        "-i",
        "ai_os_postgres",
        "psql",
        "-q",
        "-U",
        "ai_os",
        "-d",
        "ai_os",
        "-v",
        "ON_ERROR_STOP=1",
    ]
    if tuples_only:
        command.extend(["-t", "-A"])
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return completed.stdout.strip()


def fetch_json_rows(sql: str) -> list[dict[str, Any]]:
    wrapped = f"SELECT COALESCE(json_agg(row_to_json(q)), '[]'::json) FROM ({sql}) q;"
    text = run_psql(wrapped, tuples_only=True)
    return json.loads(text) if text else []


def run_psql_json_statement(sql: str) -> list[dict[str, Any]]:
    text = run_psql(sql, tuples_only=True)
    return json.loads(text) if text else []


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return f"{sql_literal(json.dumps(value, sort_keys=True, default=str))}::jsonb"


def ollama_model_names(base_url: str, timeout_seconds: float) -> set[str]:
    request = urllib.request.Request(f"{base_url.rstrip('/')}/api/tags", method="GET")
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    names: set[str] = set()
    for row in payload.get("models") or []:
        for key in ("name", "model"):
            value = str(row.get(key) or "").strip()
            if value:
                names.add(value)
    return names


def model_is_installed(model_name: str, installed_names: set[str]) -> bool:
    requested = model_name.strip()
    if not requested:
        return False
    if requested in installed_names:
        return True
    if ":" not in requested and f"{requested}:latest" in installed_names:
        return True
    return False


def check_endpoint(endpoint_key: str, actor: str = "Jarvis", timeout_seconds: float = 5.0) -> dict[str, Any]:
    rows = fetch_json_rows(
        f"""
        SELECT endpoint_key, provider, model_name, route_name, endpoint_type,
               base_url, deployment_target, status, cost_tier,
               requires_api_key, secret_ref
        FROM agent.model_endpoints
        WHERE endpoint_key = {sql_literal(endpoint_key)}
        LIMIT 1
        """
    )
    if not rows:
        raise ValueError(f"model endpoint not found: {endpoint_key}")

    endpoint = rows[0]
    provider = str(endpoint.get("provider") or "").lower()
    model_name = str(endpoint.get("model_name") or "")
    base_url = str(endpoint.get("base_url") or "").strip()
    started = time.perf_counter()
    health_status = "configured"
    error_message: str | None = None
    check_type = "configuration"
    sample: dict[str, Any] = {
        "provider": provider,
        "model_name": model_name,
        "route_name": endpoint.get("route_name"),
        "deployment_target": endpoint.get("deployment_target"),
    }

    if str(endpoint.get("status") or "") in {"disabled", "inactive", "retired"}:
        health_status = "inactive"
        error_message = "Endpoint is not enabled for runtime use."
    elif bool(endpoint.get("requires_api_key")) and not str(endpoint.get("secret_ref") or "").strip():
        health_status = "needs_secret"
        error_message = "Endpoint requires an API key; store only a secret_ref, never the key value."
    elif provider == "ollama":
        check_type = "live_model_availability"
        if not base_url:
            health_status = "needs_endpoint"
            error_message = "Ollama endpoint requires a base_url."
        else:
            try:
                installed = ollama_model_names(base_url, timeout_seconds)
                installed_match = model_is_installed(model_name, installed)
                sample.update({"server_reachable": True, "installed_model_count": len(installed), "requested_model_installed": installed_match})
                if not installed_match:
                    health_status = "model_unavailable"
                    error_message = f"Configured Ollama model is not installed: {model_name}"
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
                health_status = "endpoint_unreachable"
                error_message = f"Ollama endpoint check failed: {type(exc).__name__}: {exc}"
                sample["server_reachable"] = False
    elif provider in {"local_python", "deterministic", "local_tools"}:
        check_type = "local_runtime_configuration"
        sample["runtime_available"] = True
    elif provider in {"lm_studio", "mlx", "local_http"} and not base_url:
        health_status = "needs_endpoint"
        error_message = "Local endpoint requires a base_url or runtime socket."

    latency_ms = max(0, int((time.perf_counter() - started) * 1000))
    result_rows = run_psql_json_statement(
        f"""
        WITH check_row AS (
            INSERT INTO core.connector_health_checks (
                target_kind, target_key, check_name, check_type, status,
                latency_ms, error_message, sample_payload, checked_by
            )
            VALUES (
                'model_endpoint', {sql_literal(endpoint_key)},
                'live model endpoint health check', {sql_literal(check_type)},
                {sql_literal(health_status)}, {latency_ms}, {sql_literal(error_message)},
                {sql_jsonb(sample)}, {sql_literal(actor or 'Jarvis')}
            )
            RETURNING *
        ), endpoint_update AS (
            UPDATE agent.model_endpoints
            SET health_status = {sql_literal(health_status)},
                last_checked_at = now(),
                last_latency_ms = {latency_ms},
                last_error = {sql_literal(error_message)},
                updated_at = now()
            WHERE endpoint_key = {sql_literal(endpoint_key)}
            RETURNING endpoint_key
        )
        SELECT COALESCE(json_agg(row_to_json(check_row)), '[]'::json)::text
        FROM check_row
        """
    )
    return result_rows[0] if result_rows else {
        "target_key": endpoint_key,
        "status": health_status,
        "latency_ms": latency_ms,
        "error_message": error_message,
        "sample_payload": sample,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a live health check for one registered model endpoint.")
    parser.add_argument("--endpoint-key", required=True)
    parser.add_argument("--actor", default="Jarvis")
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    args = parser.parse_args()

    try:
        result = check_endpoint(args.endpoint_key, args.actor, max(0.5, args.timeout_seconds))
        print(json.dumps({"status": "completed", "result": result}, indent=2, sort_keys=True, default=str))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "failed", "error": f"{type(exc).__name__}: {exc}"}, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
