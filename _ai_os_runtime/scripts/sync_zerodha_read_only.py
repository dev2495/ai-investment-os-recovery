#!/usr/bin/env python3
"""Daily-authenticated, GET-only Zerodha account and options data connector."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


BASE_URL = os.environ.get("AI_OS_ZERODHA_BASE_URL", "https://api.kite.trade").rstrip("/")
LOGIN_URL = "https://kite.zerodha.com/connect/login?v=3&api_key={api_key}"
KEYCHAIN_SERVICE = os.environ.get("AI_OS_ZERODHA_TOKEN_SERVICE", "ai-os-zerodha-access-token")
KEYCHAIN_EXPIRY_SERVICE = os.environ.get("AI_OS_ZERODHA_TOKEN_EXPIRY_SERVICE", "ai-os-zerodha-access-token-expiry")
INDIA_TZ = ZoneInfo("Asia/Kolkata")
ENDPOINTS = {
    "holdings": "/portfolio/holdings",
    "positions": "/portfolio/positions",
    "orders": "/orders",
    "trades": "/trades",
    "funds": "/user/margins",
}


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def psql(sql: str) -> str:
    configured = os.environ.get("AI_OS_PSQL_BIN", "").strip()
    candidates = []
    if configured:
        candidates.append([configured, "-h", "127.0.0.1", "-p", os.environ.get("AI_OS_POSTGRES_PORT", "54329"), "-U", "ai_os", "-d", "ai_os", "-v", "ON_ERROR_STOP=1", "-At", "-c", sql])
    candidates.extend([
        ["psql", "-h", "127.0.0.1", "-p", os.environ.get("AI_OS_POSTGRES_PORT", "54329"), "-U", "ai_os", "-d", "ai_os", "-v", "ON_ERROR_STOP=1", "-At", "-c", sql],
        ["/opt/homebrew/bin/docker", "exec", "ai_os_postgres", "psql", "-U", "ai_os", "-d", "ai_os", "-v", "ON_ERROR_STOP=1", "-At", "-c", sql],
    ])
    errors: list[str] = []
    env = os.environ.copy()
    env.setdefault("PGPASSWORD", os.environ.get("AI_OS_POSTGRES_PASSWORD", "ai_os_local_dev_change_me"))
    for command in candidates:
        try:
            result = subprocess.run(command, text=True, capture_output=True, check=False, timeout=30, env=env)
        except OSError as exc:
            errors.append(f"{command[0]}: {exc}")
            continue
        if result.returncode == 0:
            return result.stdout.strip()
        errors.append((result.stderr or result.stdout).strip())
    raise RuntimeError("; ".join(errors))


def keychain_secret(service: str) -> str:
    try:
        result = subprocess.run(
            ["/usr/bin/security", "find-generic-password", "-s", service, "-w"],
            text=True, capture_output=True, check=False, timeout=10,
        )
    except OSError:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def store_keychain_secret(service: str, account: str, value: str) -> None:
    result = subprocess.run(
        ["/usr/bin/security", "add-generic-password", "-U", "-s", service, "-a", account, "-w", value],
        text=True, capture_output=True, check=False, timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "keychain write failed").strip())


def next_token_expiry(now: datetime | None = None) -> datetime:
    current = (now or datetime.now(INDIA_TZ)).astimezone(INDIA_TZ)
    expiry = current.replace(hour=6, minute=0, second=0, microsecond=0)
    return expiry if expiry > current else expiry + timedelta(days=1)


def parse_token_expiry(raw_value: str) -> datetime | None:
    value = raw_value.strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(INDIA_TZ)


def keychain_token() -> str:
    env_token = os.environ.get("AI_OS_ZERODHA_ACCESS_TOKEN", "").strip()
    return env_token or keychain_secret(KEYCHAIN_SERVICE)


def token_expiry() -> datetime | None:
    raw_value = os.environ.get("AI_OS_ZERODHA_ACCESS_TOKEN_EXPIRES", "").strip()
    return parse_token_expiry(raw_value or keychain_secret(KEYCHAIN_EXPIRY_SERVICE))


def token_is_current(token: str, expiry: datetime | None, now: datetime | None = None) -> bool:
    if not token or expiry is None:
        return False
    current = (now or datetime.now(INDIA_TZ)).astimezone(INDIA_TZ)
    return expiry > current


def store_keychain_token(token: str, expiry: datetime) -> None:
    store_keychain_secret(KEYCHAIN_SERVICE, "access_token", token)
    store_keychain_secret(KEYCHAIN_EXPIRY_SERVICE, "expires_at", expiry.isoformat())


def request_json(method: str, path: str, *, api_key: str, access_token: str = "", form: dict[str, str] | None = None) -> object:
    headers = {"Accept": "application/json", "X-Kite-Version": "3", "User-Agent": "AI-Investment-OS/1.0 read-only connector"}
    if access_token:
        headers["Authorization"] = f"token {api_key}:{access_token}"
    body = urllib.parse.urlencode(form).encode("utf-8") if form else None
    if body:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = urllib.request.Request(BASE_URL + path, method=method, headers=headers, data=body)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def exchange_request_token(api_key: str, api_secret: str, request_token: str) -> dict:
    checksum = hashlib.sha256(f"{api_key}{request_token}{api_secret}".encode("utf-8")).hexdigest()
    payload = request_json(
        "POST", "/session/token", api_key=api_key,
        form={"api_key": api_key, "request_token": request_token, "checksum": checksum},
    )
    data = payload.get("data") if isinstance(payload, dict) else None
    access_token = str(data.get("access_token") or "") if isinstance(data, dict) else ""
    if not access_token:
        raise RuntimeError("Zerodha token response did not include access_token")
    expiry = next_token_expiry()
    store_keychain_token(access_token, expiry)
    return {
        "status": "authenticated",
        "user_id": data.get("user_id"),
        "login_time": data.get("login_time"),
        "exchanges": data.get("exchanges") or [],
        "access_token_stored": True,
        "access_token_expires": expiry.isoformat(),
        "broker_write_allowed": False,
    }


def record_health(status: str, rows: int = 0, error: str | None = None) -> None:
    psql(
        "INSERT INTO core.connector_health_checks "
        "(target_kind,target_key,check_name,check_type,status,rows_seen,error_message,sample_payload,checked_by) VALUES ("
        "'data_source_connector','zerodha_live_connector','zerodha_read_sync','live_read',"
        f"{sql_literal(status)},{rows},{sql_literal(error)},"
        "'{\"broker_write_allowed\":false,\"manual_daily_login_required\":true}'::jsonb,'Zerodha Read-Only Connector')"
    )


def normalize_data(payload: object, dataset: str) -> object:
    if not isinstance(payload, dict):
        return payload
    data = payload.get("data")
    if dataset == "positions" and isinstance(data, dict):
        return data.get("net") or []
    return data if data is not None else payload


def sync_account(api_key: str, access_token: str, datasets: list[str]) -> dict:
    run_key = "zerodha-read-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    account_ref = hashlib.sha256(api_key.encode()).hexdigest()[:16]
    summary: dict[str, object] = {"run_key": run_key, "provider": "Zerodha", "account_ref": account_ref, "datasets": {}, "broker_write_allowed": False}
    total_rows = 0
    try:
        for dataset in datasets:
            raw = request_json("GET", ENDPOINTS[dataset], api_key=api_key, access_token=access_token)
            payload = normalize_data(raw, dataset)
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
            payload_hash = hashlib.sha256(canonical.encode()).hexdigest()
            row_count = len(payload) if isinstance(payload, list) else (len(payload) if isinstance(payload, dict) else (1 if payload else 0))
            psql(
                "INSERT INTO trading.broker_read_snapshots "
                "(run_key,provider,account_ref,dataset,source_connector_key,row_count,payload_hash,payload,created_by) VALUES ("
                f"{sql_literal(run_key)},'Zerodha',{sql_literal(account_ref)},{sql_literal(dataset)},"
                f"'zerodha_live_connector',{row_count},{sql_literal(payload_hash)},{sql_literal(canonical)}::jsonb,'Zerodha Read-Only Connector') "
                "ON CONFLICT (provider,account_ref,dataset,payload_hash) DO NOTHING"
            )
            total_rows += row_count
            summary["datasets"][dataset] = {"rows": row_count, "payload_hash": payload_hash}
        record_health("healthy", total_rows)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
        detail = exc.read().decode("utf-8", errors="replace") if isinstance(exc, urllib.error.HTTPError) else str(exc)
        error = f"{type(exc).__name__}: {detail}"[:1000]
        try:
            record_health("failed", total_rows, error)
        except RuntimeError:
            pass
        summary.update({"status": "failed", "error": error})
        return summary
    summary["status"] = "completed"
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--login-url", action="store_true")
    parser.add_argument("--exchange-request-token")
    parser.add_argument("--check-config", action="store_true")
    parser.add_argument("--datasets", nargs="*", choices=sorted(ENDPOINTS), default=list(ENDPOINTS))
    args = parser.parse_args()

    api_key = os.environ.get("AI_OS_ZERODHA_API_KEY", "").strip()
    api_secret = os.environ.get("AI_OS_ZERODHA_API_SECRET", "").strip()
    access_token = keychain_token()
    access_token_expiry = token_expiry()
    access_token_current = token_is_current(access_token, access_token_expiry)
    if args.login_url:
        print(json.dumps({"status": "ready" if api_key else "needs_credentials", "login_url": LOGIN_URL.format(api_key=urllib.parse.quote(api_key)) if api_key else None, "manual_daily_login_required": True, "broker_write_allowed": False}, indent=2))
        return 0 if api_key else 2
    if args.exchange_request_token:
        if not api_key or not api_secret:
            print(json.dumps({"status": "needs_credentials", "required_env": ["AI_OS_ZERODHA_API_KEY", "AI_OS_ZERODHA_API_SECRET"], "broker_write_allowed": False}, indent=2))
            return 2
        try:
            print(json.dumps(exchange_request_token(api_key, api_secret, args.exchange_request_token.strip()), indent=2))
            return 0
        except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError, json.JSONDecodeError) as exc:
            print(json.dumps({"status": "failed", "error": f"{type(exc).__name__}: {exc}", "broker_write_allowed": False}, indent=2))
            return 1
    status = {
        "status": "configured" if api_key and api_secret and access_token_current else "needs_credentials_or_daily_login",
        "api_key_configured": bool(api_key), "api_secret_configured": bool(api_secret),
        "daily_access_token_available": access_token_current,
        "access_token_expiry_known": access_token_expiry is not None,
        "access_token_expires_at": access_token_expiry.isoformat() if access_token_expiry else None,
        "stale_access_token_present": bool(access_token) and not access_token_current,
        "login_url": LOGIN_URL.format(api_key=urllib.parse.quote(api_key)) if api_key else None,
        "manual_daily_login_required": True, "broker_write_allowed": False,
    }
    if args.check_config or not (api_key and api_secret and access_token_current):
        print(json.dumps(status, indent=2))
        return 0 if status["status"] == "configured" else 2
    result = sync_account(api_key, access_token, args.datasets)
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
