#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = RUNTIME_ROOT / "imports" / "source_components_manifest.json"
QUARANTINE_ROOT = RUNTIME_ROOT / "imports" / "quarantine"

P2_CURSOR_ZIP = Path("/Volumes/Devarsh SSD/ps 2 cursor.zip")
ALGO_ROOT = Path("/Volumes/Devarsh SSD/algo based trading software 2")

SOURCE_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".jsx",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}

SKIP_SEGMENTS = {
    "__macosx",
    ".cache",
    ".claude",
    ".git",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "cache",
    "coverage",
    "data",
    "dist",
    "logs",
    "node_modules",
    "site-packages",
    "venv",
}

SENSITIVE_PATTERNS = {
    ".env",
    "access_key",
    "apikey",
    "api_key",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
}

ALGO_REQUIRED_ROOTS = {
    "agents",
    "ai_engine",
    "alerts",
    "assistant",
    "backtesting",
    "dashboard",
    "fundamentals",
    "ideas",
    "indicators",
    "integrations",
    "live_trading",
    "market_data",
    "news",
    "options_tools",
    "portfolios",
    "quant",
    "sentiment",
    "strategies",
    "utils",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sql_quote(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def jsonb_quote(value: object) -> str:
    return sql_quote(json.dumps(value, sort_keys=True)) + "::jsonb"


def text_array(values: list[str]) -> str:
    if not values:
        return "'{}'::text[]"
    return "ARRAY[" + ",".join(sql_quote(value) for value in values) + "]::text[]"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def has_sensitive_path(name: str) -> bool:
    lower = name.lower()
    return any(pattern in lower for pattern in SENSITIVE_PATTERNS)


def path_parts_lower(name: str) -> list[str]:
    return [part.lower() for part in PurePosixPath(name).parts if part and part != "/"]


def classify_component(path: str) -> tuple[str, str]:
    lower = path.lower()
    rules = [
        ("tradingview_webhook", "TradingView webhook bridge", ["tradingview", "webhook"]),
        ("portfolio_engine", "Portfolio/account/holdings/trades engine", ["portfolio", "holdings", "accounts", "cash", "mtm"]),
        ("trade_journal", "Trading journal and post-trade learning source", ["journal", "trade_journal"]),
        ("backtesting_engine", "Backtesting and strategy validation engine", ["backtesting", "backtest"]),
        ("strategy_library", "Strategy definitions and systematic signal logic", ["strategies", "supertrend", "strategy"]),
        ("indicator_library", "Technical indicators and options Greeks", ["indicators", "greeks"]),
        ("quant_lab", "Quant, factor, regime, pairs, portfolio backtest modules", ["quant", "regime", "factor", "monte_carlo"]),
        ("market_data", "Market data, NSE/BSE, quotes, corporate source collection", ["market_data", "nse", "bse", "quotes"]),
        ("news_research", "News, sentiment, fundamentals, screeners, research inputs", ["news", "sentiment", "fundamentals", "screener"]),
        ("ideas_watchlist", "Idea generation, scanners, watchlists", ["ideas", "watchlist", "scanner"]),
        ("dashboard_ui", "Dashboard/UI component reference", ["dashboard", "frontend", "tsx", "css"]),
        ("agent_loop", "Existing assistant/agent loop reference", ["assistant", "agents", "agent"]),
        ("alerts", "Alert routing and notification reference", ["alerts", "telegram"]),
        ("runtime_config", "Runtime setup, requirements, package metadata", ["requirements", "package.json", "readme", "quickstart"]),
    ]
    for component, purpose, keywords in rules:
        if any(keyword in lower for keyword in keywords):
            return component, purpose
    return "general_app_component", "General reusable app component"


def language_for_suffix(suffix: str) -> str:
    return {
        ".css": "css",
        ".html": "html",
        ".js": "javascript",
        ".jsx": "javascript-react",
        ".json": "json",
        ".md": "markdown",
        ".py": "python",
        ".toml": "toml",
        ".ts": "typescript",
        ".tsx": "typescript-react",
        ".txt": "text",
        ".yaml": "yaml",
        ".yml": "yaml",
    }.get(suffix.lower(), "unknown")


def safe_relative_path(name: str) -> Path:
    parts = [part for part in PurePosixPath(name).parts if part not in {"", "/", ".", ".."}]
    return Path(*parts)


def should_copy_source(path: str, size_bytes: int, max_size_bytes: int = 1_000_000) -> tuple[bool, str | None]:
    parts = path_parts_lower(path)
    if not parts:
        return False, "empty_path"
    if any(part in {"..", "."} for part in parts):
        return False, "unsafe_path"
    if any(part in SKIP_SEGMENTS for part in parts):
        return False, "generated_or_data_path"
    if any(part.startswith("._") for part in parts):
        return False, "macos_resource_fork"
    if has_sensitive_path(path):
        return False, "credential_like_path"
    if PurePosixPath(path).suffix.lower() not in SOURCE_SUFFIXES:
        return False, "not_source_suffix"
    if size_bytes <= 0:
        return False, "empty"
    if size_bytes > max_size_bytes:
        return False, "over_size_limit"
    return True, None


def parse_python_requirements(text: str) -> list[dict]:
    requirements = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        line = line.split("#", 1)[0].strip()
        match = re.match(r"^([A-Za-z0-9_.-]+)(.*)$", line)
        if not match:
            continue
        requirements.append(
            {
                "package_manager": "pip",
                "package_name": match.group(1),
                "version_spec": match.group(2).strip() or None,
                "dev_dependency": False,
            }
        )
    return requirements


def parse_package_json(text: str) -> list[dict]:
    requirements = []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return requirements
    for section, is_dev in (("dependencies", False), ("devDependencies", True)):
        deps = data.get(section) or {}
        if not isinstance(deps, dict):
            continue
        for name, version in deps.items():
            requirements.append(
                {
                    "package_manager": "npm",
                    "package_name": name,
                    "version_spec": str(version) if version is not None else None,
                    "dev_dependency": is_dev,
                }
            )
    return requirements


def collect_requirements(source_path: str, content: bytes) -> list[dict]:
    name = PurePosixPath(source_path).name.lower()
    try:
        text = content.decode("utf-8", errors="replace")
    except Exception:
        return []
    if name == "requirements.txt":
        return parse_python_requirements(text)
    if name == "package.json":
        return parse_package_json(text)
    return []


def inventory_algo_components() -> tuple[list[dict], list[dict]]:
    destination_root = QUARANTINE_ROOT / "algo_components"
    if destination_root.exists():
        shutil.rmtree(destination_root)
    destination_root.mkdir(parents=True, exist_ok=True)

    files: list[dict] = []
    requirements: list[dict] = []
    if not ALGO_ROOT.exists():
        return files, requirements

    for root, dirs, file_names in os.walk(ALGO_ROOT):
        root_path = Path(root)
        dirs[:] = [directory for directory in dirs if directory.lower() not in SKIP_SEGMENTS]

        for file_name in file_names:
            source_path = root_path / file_name
            try:
                relative = source_path.relative_to(ALGO_ROOT)
            except ValueError:
                continue
            relative_text = str(relative)
            top = relative.parts[0] if relative.parts else ""
            if top not in ALGO_REQUIRED_ROOTS and file_name not in {"README.md", "requirements.txt", "run_terminal.py"}:
                continue
            ok, reason = should_copy_source(relative_text, source_path.stat().st_size)
            if not ok:
                continue

            output_path = destination_root / relative
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, output_path)
            digest = sha256_file(output_path)
            component_name, purpose = classify_component(relative_text)
            content = output_path.read_bytes()
            file_record = {
                "source_system_name": "algo trading terminal",
                "component_name": component_name,
                "source_path": str(source_path),
                "extracted_path": str(output_path.relative_to(RUNTIME_ROOT)),
                "file_type": output_path.suffix.lower(),
                "size_bytes": output_path.stat().st_size,
                "sha256": digest,
                "language": language_for_suffix(output_path.suffix),
                "purpose": purpose,
                "reuse_status": "candidate",
                "sensitivity": "private_trading",
                "metadata": {"relative_source_path": relative_text},
            }
            files.append(file_record)
            for requirement in collect_requirements(relative_text, content):
                requirements.append(
                    {
                        **requirement,
                        "source_system_name": "algo trading terminal",
                        "component_name": component_name,
                        "source_path": relative_text,
                        "metadata": {"from_file": relative_text},
                    }
                )
    return files, requirements


def inventory_p2_components() -> tuple[list[dict], list[dict]]:
    destination_root = QUARANTINE_ROOT / "p2cursor_components"
    if destination_root.exists():
        shutil.rmtree(destination_root)
    destination_root.mkdir(parents=True, exist_ok=True)

    files: list[dict] = []
    requirements: list[dict] = []
    if not P2_CURSOR_ZIP.exists():
        return files, requirements

    with zipfile.ZipFile(P2_CURSOR_ZIP) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            ok, reason = should_copy_source(info.filename, info.file_size)
            if not ok:
                continue
            lower = info.filename.lower()
            if "ps 2 cursor" not in lower:
                continue

            relative = safe_relative_path(info.filename)
            output_path = destination_root / relative
            output_path.parent.mkdir(parents=True, exist_ok=True)
            content = archive.read(info)
            output_path.write_bytes(content)
            component_name, purpose = classify_component(info.filename)
            record = {
                "source_system_name": "ps 2 cursor archive",
                "component_name": component_name,
                "source_path": info.filename,
                "extracted_path": str(output_path.relative_to(RUNTIME_ROOT)),
                "file_type": output_path.suffix.lower(),
                "size_bytes": info.file_size,
                "sha256": sha256_bytes(content),
                "language": language_for_suffix(output_path.suffix),
                "purpose": purpose,
                "reuse_status": "candidate",
                "sensitivity": "client_private",
                "metadata": {"zip_path": str(P2_CURSOR_ZIP)},
            }
            files.append(record)
            for requirement in collect_requirements(info.filename, content):
                requirements.append(
                    {
                        **requirement,
                        "source_system_name": "ps 2 cursor archive",
                        "component_name": component_name,
                        "source_path": info.filename,
                        "metadata": {"from_zip": str(P2_CURSOR_ZIP)},
                    }
                )
    return files, requirements


def inventory_sqlite_profiles() -> list[dict]:
    databases = [
        ("algo trades db", ALGO_ROOT / "data" / "trades.db", ["portfolio.trades", "trading.trade_journals"]),
        ("algo app db", ALGO_ROOT / "data" / "storage" / "app.db", ["portfolio.accounts", "portfolio.positions", "trading.signals", "research.ideas"]),
        ("algo prices db", ALGO_ROOT / "data" / "storage" / "prices.db", ["trading.ohlcv", "strategy.backtest_runs"]),
    ]
    profiles: list[dict] = []
    for source_system_name, database_path, targets in databases:
        if not database_path.exists():
            continue
        uri = f"file:{database_path}?mode=ro&immutable=1"
        with sqlite3.connect(uri, uri=True, timeout=5) as connection:
            tables = connection.execute(
                "select name from sqlite_master where type='table' and name != 'sqlite_sequence' order by name"
            ).fetchall()
            for (table_name,) in tables:
                columns = [
                    {"name": column[1], "type": column[2]}
                    for column in connection.execute(f'pragma table_info("{table_name}")').fetchall()
                ]
                row_count = connection.execute(f'select count(*) from "{table_name}"').fetchone()[0]
                profiles.append(
                    {
                        "source_system_name": source_system_name,
                        "database_path": str(database_path),
                        "table_name": table_name,
                        "row_count": row_count,
                        "columns_json": columns,
                        "target_tables": targets,
                        "import_status": "profiled",
                    }
                )
    return profiles


def register_manifest(files: list[dict], requirements: list[dict], profiles: list[dict]) -> None:
    statements = ["BEGIN;"]

    for item in files:
        statements.append(
            f"""
INSERT INTO core.source_code_files (
    source_system_id,
    component_name,
    source_path,
    extracted_path,
    file_type,
    size_bytes,
    sha256,
    language,
    purpose,
    reuse_status,
    sensitivity,
    metadata
)
SELECT
    ss.id,
    {sql_quote(item["component_name"])},
    {sql_quote(item["source_path"])},
    {sql_quote(item["extracted_path"])},
    {sql_quote(item["file_type"])},
    {item["size_bytes"]},
    {sql_quote(item["sha256"])},
    {sql_quote(item["language"])},
    {sql_quote(item["purpose"])},
    {sql_quote(item["reuse_status"])},
    {sql_quote(item["sensitivity"])},
    {jsonb_quote(item["metadata"])}
FROM core.source_systems ss
WHERE ss.name = {sql_quote(item["source_system_name"])}
ON CONFLICT (source_system_id, source_path, sha256) DO UPDATE SET
    component_name = EXCLUDED.component_name,
    extracted_path = EXCLUDED.extracted_path,
    file_type = EXCLUDED.file_type,
    size_bytes = EXCLUDED.size_bytes,
    language = EXCLUDED.language,
    purpose = EXCLUDED.purpose,
    reuse_status = EXCLUDED.reuse_status,
    sensitivity = EXCLUDED.sensitivity,
    metadata = EXCLUDED.metadata,
    registered_at = now();
"""
        )

    for item in requirements:
        statements.append(
            f"""
INSERT INTO core.source_requirements (
    source_system_id,
    component_name,
    source_path,
    package_manager,
    package_name,
    version_spec,
    dev_dependency,
    metadata
)
SELECT
    ss.id,
    {sql_quote(item["component_name"])},
    {sql_quote(item["source_path"])},
    {sql_quote(item["package_manager"])},
    {sql_quote(item["package_name"])},
    {sql_quote(item.get("version_spec"))},
    {'true' if item.get("dev_dependency") else 'false'},
    {jsonb_quote(item.get("metadata", {}))}
FROM core.source_systems ss
WHERE ss.name = {sql_quote(item["source_system_name"])}
ON CONFLICT (source_system_id, source_path, package_manager, package_name, version_spec, dev_dependency) DO UPDATE SET
    component_name = EXCLUDED.component_name,
    metadata = EXCLUDED.metadata,
    registered_at = now();
"""
        )

    for item in profiles:
        statements.append(
            f"""
INSERT INTO core.source_table_profiles (
    source_system_id,
    database_path,
    table_name,
    row_count,
    columns_json,
    target_tables,
    import_status
)
SELECT
    ss.id,
    {sql_quote(item["database_path"])},
    {sql_quote(item["table_name"])},
    {item["row_count"]},
    {jsonb_quote(item["columns_json"])},
    {text_array(item["target_tables"])},
    {sql_quote(item["import_status"])}
FROM core.source_systems ss
WHERE ss.name = {sql_quote(item["source_system_name"])}
ON CONFLICT (source_system_id, database_path, table_name) DO UPDATE SET
    row_count = EXCLUDED.row_count,
    columns_json = EXCLUDED.columns_json,
    target_tables = EXCLUDED.target_tables,
    import_status = EXCLUDED.import_status,
    profiled_at = now();
"""
        )

    statements.append("COMMIT;")
    command = ["docker", "exec", "-i", "ai_os_postgres", "psql", "-q", "-U", "ai_os", "-d", "ai_os", "-v", "ON_ERROR_STOP=1"]
    completed = subprocess.run(command, input="\n".join(statements), text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        sys.stderr.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise SystemExit(completed.returncode)


def main() -> int:
    algo_files, algo_requirements = inventory_algo_components()
    p2_files, p2_requirements = inventory_p2_components()
    profiles = inventory_sqlite_profiles()
    files = algo_files + p2_files
    requirements = algo_requirements + p2_requirements

    register_manifest(files, requirements, profiles)

    source_counts = Counter(item["source_system_name"] for item in files)
    component_counts = Counter(item["component_name"] for item in files)
    req_counts = Counter(item["package_manager"] for item in requirements)
    manifest = {
        "generated_at": utc_now(),
        "runtime_root": str(RUNTIME_ROOT),
        "quarantine_root": str(QUARANTINE_ROOT),
        "stats": {
            "files_registered": len(files),
            "requirements_registered": len(requirements),
            "sqlite_tables_profiled": len(profiles),
            "files_by_source": dict(source_counts.most_common()),
            "files_by_component": dict(component_counts.most_common()),
            "requirements_by_manager": dict(req_counts.most_common()),
        },
        "files": files,
        "requirements": requirements,
        "sqlite_profiles": profiles,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"manifest_path": str(OUTPUT_PATH), **manifest["stats"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
