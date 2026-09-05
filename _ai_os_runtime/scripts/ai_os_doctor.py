#!/usr/bin/env python3
"""CLI for the bounded AI OS Doctor registry."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


RUNTIME_ROOT = Path(os.environ.get("AI_OS_RUNTIME_ROOT") or Path(__file__).resolve().parents[1])
REPO_ROOT = RUNTIME_ROOT.parent
API_ROOT = RUNTIME_ROOT / "api"
SCRIPTS_ROOT = RUNTIME_ROOT / "scripts"
for import_root in (REPO_ROOT, RUNTIME_ROOT, API_ROOT, SCRIPTS_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from _ai_os_runtime.api.doctor_runtime import DoctorRuntime  # noqa: E402
from runtime_executables import docker_binary, psql_binary  # noqa: E402


class Database:
    """Bounded psql adapter; credential values stay in the subprocess env."""

    def __init__(self) -> None:
        self.statement_timeout_ms = max(500, min(30000, int(os.environ.get("AI_OS_DOCTOR_SQL_TIMEOUT_MS") or 8000)))
        self.timeout_seconds = max(2.0, min(35.0, float(os.environ.get("AI_OS_DOCTOR_PROCESS_TIMEOUT_SECONDS") or 12)))

    def _run_text(self, sql: str) -> str:
        host_psql = psql_binary()
        password = os.environ.get("AI_OS_POSTGRES_PASSWORD")
        use_host = bool(host_psql and password and (os.environ.get("AI_OS_WORKLOAD_PSQL_MODE") or "host").lower() != "docker")
        if use_host:
            connection = (
                f"host={os.environ.get('AI_OS_POSTGRES_HOST') or '127.0.0.1'} "
                f"port={os.environ.get('AI_OS_POSTGRES_PORT') or '54329'} "
                f"dbname={os.environ.get('AI_OS_POSTGRES_DB') or 'ai_os'} "
                f"user={os.environ.get('AI_OS_POSTGRES_USER') or 'ai_os'} "
                f"connect_timeout=3 options='-c statement_timeout={self.statement_timeout_ms} "
                f"-c lock_timeout={min(3000, self.statement_timeout_ms)}'"
            )
            command = [str(host_psql), connection, "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-c", sql]
            env = os.environ.copy()
            env["PGPASSWORD"] = str(password)
            completed = subprocess.run(
                command, text=True, capture_output=True, check=False,
                timeout=self.timeout_seconds, env=env,
            )
        else:
            command = [
                docker_binary(), "exec", "-i", "ai_os_postgres", "psql", "-q", "-t", "-A",
                "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os",
            ]
            completed = subprocess.run(
                command, input=sql, text=True, capture_output=True, check=False,
                timeout=self.timeout_seconds,
            )
        if completed.returncode != 0:
            message = (completed.stderr or completed.stdout or "psql failed").strip()
            raise RuntimeError(message[:1000])
        return completed.stdout.strip()

    def query(self, sql: str) -> list[dict[str, Any]]:
        clean = sql.strip().rstrip(";")
        wrapped = (
            "WITH doctor_rows AS (" + clean + ") "
            "SELECT coalesce(json_agg(row_to_json(doctor_rows)),'[]'::json)::text FROM doctor_rows;"
        )
        raw = self._run_text(wrapped)
        parsed = json.loads(raw or "[]")
        if not isinstance(parsed, list):
            raise RuntimeError("database query did not return a row list")
        return parsed

    def statement(self, sql: str) -> list[dict[str, Any]]:
        clean = sql.strip().rstrip(";")
        # The existing company monitor already emits its JSON row list.
        if "json_agg(row_to_json(mutation_rows))" in clean:
            raw = self._run_text(clean)
        else:
            wrapped = (
                "WITH mutation_rows AS (" + clean + ") "
                "SELECT coalesce(json_agg(row_to_json(mutation_rows)),'[]'::json)::text FROM mutation_rows;"
            )
            raw = self._run_text(wrapped)
        parsed = json.loads(raw or "[]")
        if not isinstance(parsed, list):
            raise RuntimeError("database statement did not return a receipt list")
        return parsed


def _http_probe(url: str, name: str, timeout: float = 3.0) -> dict[str, Any]:
    started = time.monotonic()
    try:
        request = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status_code = int(response.status)
            response.read(4096)
        latency_ms = int((time.monotonic() - started) * 1000)
        ok = 200 <= status_code < 300
        return {
            "status": "passed" if ok else "failed",
            "headline": f"{name} returned HTTP {status_code} in {latency_ms}ms",
            "status_code": status_code,
            "latency_ms": latency_ms,
            "endpoint": url,
            "actionable_fix": None if ok else f"Inspect the existing supervised {name} service.",
        }
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        return {
            "status": "failed",
            "headline": f"{name} is unreachable",
            "endpoint": url,
            "error_type": type(exc).__name__,
            "actionable_fix": f"Inspect the existing supervised {name} service and its latest logs.",
        }


def probe_api() -> dict[str, Any]:
    url = os.environ.get("AI_OS_API_HEALTH_URL") or "http://127.0.0.1:8765/api/health"
    return _http_probe(url, "AI OS API")


def probe_redis() -> dict[str, Any]:
    host = os.environ.get("AI_OS_REDIS_HOST") or "127.0.0.1"
    port = int(os.environ.get("AI_OS_REDIS_PORT") or 63799)
    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=2.0) as connection:
            connection.sendall(b"*1\r\n$4\r\nPING\r\n")
            reply = connection.recv(64)
        latency_ms = int((time.monotonic() - started) * 1000)
        ok = reply.startswith(b"+PONG")
        return {
            "status": "passed" if ok else "failed",
            "headline": f"Redis {'answered PONG' if ok else 'returned an unexpected response'} in {latency_ms}ms",
            "host": host,
            "port": port,
            "latency_ms": latency_ms,
            "actionable_fix": None if ok else "Inspect the existing local Redis service.",
        }
    except OSError as exc:
        return {
            "status": "failed",
            "headline": "Redis is unreachable",
            "host": host,
            "port": port,
            "error_type": type(exc).__name__,
            "actionable_fix": "Inspect the existing local Redis service.",
        }


def probe_qdrant() -> dict[str, Any]:
    url = os.environ.get("AI_OS_QDRANT_URL") or "http://127.0.0.1:6333/collections"
    return _http_probe(url, "Qdrant")


def probe_external_ssd() -> dict[str, Any]:
    volume = Path(os.environ.get("AI_OS_SSD_ROOT") or "/Volumes/Devarsh SSD")
    data_root = Path(os.environ.get("AI_OS_DATA_ROOT") or volume / "AI OS Data")
    exists = data_root.is_dir()
    mounted = volume.is_mount()
    writable = os.access(data_root, os.W_OK) if exists else False
    free_gb = round(os.statvfs(data_root).f_bavail * os.statvfs(data_root).f_frsize / (1024 ** 3), 2) if exists else None
    expected = ["artifacts", "backups"]
    missing = [name for name in expected if not (data_root / name).is_dir()]
    ok = mounted and exists and writable and free_gb is not None and free_gb >= 1 and not missing
    return {
        "status": "passed" if ok else "failed",
        "headline": "External SSD storage is mounted and ready" if ok else "External SSD storage contract is not satisfied",
        "volume": str(volume),
        "data_root": str(data_root),
        "mounted": mounted,
        "writable": writable,
        "free_gb": free_gb,
        "missing_expected_directories": missing,
        "internal_storage_fallback_allowed": False,
        "actionable_fix": None if ok else "Mount the configured SSD and restore its expected AI OS directories; do not fall back to internal storage.",
    }


def probe_obsidian_integrity() -> dict[str, Any]:
    vault = Path(os.environ.get("AI_OS_VAULT_ROOT") or "/Volumes/Devarsh SSD/Obsidian memory ")
    if not vault.is_dir():
        return {"status": "failed", "headline": "Obsidian vault is unavailable",
                "broken_managed_blocks": None, "files_scanned": 0}
    broken = 0
    scanned = 0
    for path in vault.rglob("*.md"):
        if scanned >= 5000:
            break
        parts = set(path.relative_to(vault).parts)
        if parts & {".git", ".obsidian", "_ai_os_runtime", "node_modules"}:
            continue
        scanned += 1
        try:
            body = path.read_text(encoding="utf-8", errors="replace")[:4_000_000]
        except OSError:
            broken += 1
            continue
        starts = body.count("<!-- AI-OS:BEGIN")
        ends = body.count("<!-- AI-OS:END")
        if starts != ends:
            broken += 1
    return {
        "status": "passed" if broken == 0 else "failed",
        "headline": f"Obsidian managed-block scan found {broken} broken notes",
        "broken_managed_blocks": broken,
        "files_scanned": scanned,
        "vault_present": True,
    }


def _newest(paths: list[Path]) -> Path | None:
    existing = [path for path in paths if path.is_file()]
    return max(existing, key=lambda path: path.stat().st_mtime) if existing else None


def probe_backup_restore() -> dict[str, Any]:
    data_root = Path(os.environ.get("AI_OS_DATA_ROOT") or "/Volumes/Devarsh SSD/AI OS Data")
    manifest = data_root / "backups" / "critical" / "current" / "manifest.txt"
    receipts = list((data_root / "artifacts" / "restore-drills").glob("restore-drill-*.json"))
    latest = _newest(receipts)
    age_hours = round((time.time() - latest.stat().st_mtime) / 3600, 2) if latest else None
    ok = manifest.is_file() and latest is not None and age_hours is not None and age_hours <= 168
    return {
        "status": "passed" if ok else "failed",
        "headline": "Backup and restore-drill receipts are current" if ok else "Backup or recent restore-drill evidence is missing",
        "backup_manifest_present": manifest.is_file(),
        "restore_receipt_present": latest is not None,
        "latest_restore_receipt": str(latest) if latest else None,
        "restore_receipt_age_hours": age_hours,
        "actionable_fix": None if ok else "Run the reviewed critical backup and disposable restore drill before promotion.",
    }


def _tree_digest(root: Path) -> tuple[str | None, int]:
    if not root.is_dir():
        return None, 0
    digest = hashlib.sha256()
    count = 0
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = str(path.relative_to(root))
        digest.update(relative.encode())
        try:
            digest.update(hashlib.sha256(path.read_bytes()).digest())
        except OSError:
            continue
        count += 1
    return digest.hexdigest(), count


def probe_ui_assets() -> dict[str, Any]:
    source = Path(os.environ.get("AI_OS_SOURCE_UI_ROOT") or RUNTIME_ROOT / "ai-office-ui" / "dist")
    deployed_raw = os.environ.get("AI_OS_DEPLOYED_UI_ROOT")
    if not deployed_raw:
        return {
            "status": "unknown",
            "headline": "Deployed UI root was not supplied for asset equality",
            "source_root": str(source),
            "deployed_root_configured": False,
            "actionable_fix": "Set AI_OS_DEPLOYED_UI_ROOT to the canonical deployed dist directory and rerun Doctor.",
        }
    deployed = Path(deployed_raw)
    source_hash, source_files = _tree_digest(source)
    deployed_hash, deployed_files = _tree_digest(deployed)
    ok = bool(source_hash and deployed_hash and source_hash == deployed_hash)
    return {
        "status": "passed" if ok else "failed",
        "headline": "Source and deployed UI assets match" if ok else "Source and deployed UI assets differ or are unavailable",
        "source_root": str(source),
        "deployed_root": str(deployed),
        "source_digest": source_hash,
        "deployed_digest": deployed_hash,
        "source_files": source_files,
        "deployed_files": deployed_files,
        "actionable_fix": None if ok else "Build and deploy the reviewed UI release, then compare asset manifests again.",
    }


def probe_launchd() -> dict[str, Any]:
    labels = (
        "com.devarsh.aios.api", "com.devarsh.aios.ui",
        "com.devarsh.aios.agent-daemon", "com.devarsh.aios.critical-backup",
        "com.devarsh.aios.zerodha-stream",
    )
    missing: list[str] = []
    for label in labels:
        completed = subprocess.run(
            ["launchctl", "print", f"gui/{os.getuid()}/{label}"],
            text=True, capture_output=True, check=False, timeout=3,
        )
        if completed.returncode != 0:
            missing.append(label)
    ok = not missing
    return {
        "status": "passed" if ok else "failed",
        "headline": f"{len(labels)-len(missing)}/{len(labels)} required LaunchAgents are loaded",
        "checked_labels": list(labels),
        "missing_labels": missing,
        "actionable_fix": None if ok else "Inspect the reviewed plist and supervisor logs before reinstalling an allowlisted LaunchAgent.",
    }


def probe_configuration() -> dict[str, Any]:
    watched = [
        RUNTIME_ROOT / "config" / "model_routes.yml",
        RUNTIME_ROOT / "docker-compose.yml",
        RUNTIME_ROOT / ".env.example",
        RUNTIME_ROOT / "launchd" / "com.devarsh.aios.api.plist",
        RUNTIME_ROOT / "launchd" / "com.devarsh.aios.agent-daemon.plist",
        RUNTIME_ROOT / "launchd" / "com.devarsh.aios.zerodha-stream.plist",
    ]
    hashes: dict[str, str] = {}
    missing: list[str] = []
    for path in watched:
        relative = str(path.relative_to(RUNTIME_ROOT))
        if not path.is_file():
            missing.append(relative)
            continue
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    return {
        "status": "passed" if not missing else "failed",
        "headline": f"Hashed {len(hashes)} watched configuration files",
        "watched_hashes": hashes,
        "configuration_digest": digest,
        "missing_watched_files": missing,
        "actionable_fix": None if not missing else "Restore missing reviewed configuration files from the canonical Git release.",
    }


SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(?:api_key|access_token|refresh_token|password|client_secret|private_key|auth_token)\b\s*[:=]\s*['\"]?[^\s'\"#]{8,}"
)


def probe_changed_file_secrets() -> dict[str, Any]:
    completed = subprocess.run(
        ["git", "status", "--porcelain=v1"], cwd=REPO_ROOT,
        text=True, capture_output=True, check=False, timeout=5,
    )
    if completed.returncode != 0:
        return {"status": "unknown", "headline": "Changed-file inventory is unavailable",
                "finding_count": None, "paths": []}
    paths: list[str] = []
    findings = 0
    for line in completed.stdout.splitlines()[:1000]:
        raw = line[3:]
        if " -> " in raw:
            raw = raw.split(" -> ", 1)[1]
        path = REPO_ROOT / raw
        if not path.is_file() or path.stat().st_size > 1_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        matches = SECRET_ASSIGNMENT.findall(text)
        if matches:
            findings += len(matches)
            paths.append(raw)
    return {
        "status": "failed" if findings else "passed",
        "headline": f"Changed-file secret scan found {findings} secret-shaped assignments",
        "finding_count": findings,
        "paths": sorted(set(paths)),
        "matched_values_returned": False,
        "actionable_fix": "Remove the value, rotate it outside chat if real, and retain only a Keychain/environment reference." if findings else None,
    }


def probe_pythia() -> dict[str, Any]:
    configured = os.environ.get("AI_OS_PYTHIA_HEALTH_URL")
    if not configured:
        return {"status": "skipped", "headline": "Pythia is not configured on this host",
                "installed": False}
    return {**_http_probe(configured, "Pythia"), "installed": True}


def probes() -> dict[str, Any]:
    return {
        "api_readiness": probe_api,
        "redis_health": probe_redis,
        "qdrant_health": probe_qdrant,
        "external_ssd_storage": probe_external_ssd,
        "obsidian_integrity": probe_obsidian_integrity,
        "backup_restore_receipt": probe_backup_restore,
        "ui_asset_equality": probe_ui_assets,
        "launchd_services": probe_launchd,
        "configuration_drift": probe_configuration,
        "changed_file_secret_scan": probe_changed_file_secrets,
        "pythia_optional": probe_pythia,
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Run deterministic AI OS health and drift checks.")
    value.add_argument("--json", action="store_true", dest="as_json", help="Print the full machine-readable result.")
    value.add_argument("--quiet", action="store_true", help="Print only degraded or failed headlines.")
    value.add_argument("--init-baseline", action="store_true", help="Capture passing checks as the reviewed drift baseline.")
    value.add_argument("--safe-fix", action="store_true", help="Apply only reviewed safe fixes and persist before/after receipts.")
    value.add_argument("--component", help="Run one Doctor component, such as zerodha or obsidian.")
    value.add_argument("--agent", help="Scope model assignment checks to one immutable agent key.")
    value.add_argument("--model-route", help="Scope model checks to one route.")
    value.add_argument("--actor", default=os.environ.get("USER") or "operator")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    database = Database()
    doctor = DoctorRuntime(database.query, database.statement, probes=probes(), actor=args.actor)
    if args.safe_fix:
        if args.component and args.component != "agents":
            raise SystemExit("--safe-fix currently supports only the agents component")
        result = doctor.safe_fix(check_key="expired_task_leases", confirmed=True)
        status = "failed" if result["after"]["status"] == "failed" else "passed"
    else:
        result = doctor.run(
            component=args.component,
            agent_key=args.agent,
            model_route=args.model_route,
            mode="baseline" if args.init_baseline else "scan",
            persist=True,
        )
        status = result["status"]
    if args.as_json:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    elif args.quiet:
        checks = result.get("checks") or [result.get("after") or {}]
        for check in checks:
            if check.get("status") != "passed":
                print(f"{check.get('status','unknown').upper()}: {check.get('headline','Doctor check unavailable')}")
    else:
        print(f"AI OS Doctor: {status.upper()}")
        checks = result.get("checks") or [result.get("after") or {}]
        for check in checks:
            print(f"[{str(check.get('status') or 'unknown').upper():7}] {check.get('headline')}")
            if check.get("actionable_fix"):
                print(f"          Next: {check['actionable_fix']}")
        print("Safety: model calls 0; credential changes false; broker writes false")
    return 2 if status == "failed" else (1 if status == "degraded" else 0)


if __name__ == "__main__":
    raise SystemExit(main())
