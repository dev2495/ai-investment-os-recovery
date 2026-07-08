#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sqlite3
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = RUNTIME_ROOT / "imports" / "source_inventory.json"

P2_CURSOR_ZIP = Path("/Volumes/Devarsh SSD/ps 2 cursor.zip")
ALGO_ROOT = Path("/Volumes/Devarsh SSD/algo based trading software 2")

SENSITIVE_PATTERNS = (
    ".env",
    "secret",
    "token",
    "credential",
    "password",
    "apikey",
    "api_key",
    "access_key",
    "private_key",
)

INTERESTING_SUFFIXES = (
    ".db",
    ".sqlite",
    ".csv",
    ".xlsx",
    ".xls",
    ".parquet",
    ".json",
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".md",
)


def is_sensitive(path: str) -> bool:
    lower = path.lower()
    return any(pattern in lower for pattern in SENSITIVE_PATTERNS)


def inventory_zip(path: Path) -> dict:
    result: dict = {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else None,
        "error": None,
        "total_entries": 0,
        "suffix_counts": {},
        "top_level_counts": {},
        "interesting_paths": [],
        "sensitive_path_flags": [],
    }

    if not path.exists():
        return result

    try:
        suffix_counts: Counter[str] = Counter()
        top_level_counts: Counter[str] = Counter()
        interesting_paths: list[str] = []
        sensitive_flags: list[str] = []

        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            result["total_entries"] = len(infos)

            for info in infos:
                name = info.filename
                parts = [part for part in name.split("/") if part]
                top_level_counts[parts[0] if parts else "(root)"] += 1
                suffix = Path(name).suffix.lower() or "(none)"
                suffix_counts[suffix] += 1

                if suffix in INTERESTING_SUFFIXES and len(interesting_paths) < 250:
                    interesting_paths.append(name)
                if is_sensitive(name) and len(sensitive_flags) < 100:
                    sensitive_flags.append(name)

        result["suffix_counts"] = dict(suffix_counts.most_common(50))
        result["top_level_counts"] = dict(top_level_counts.most_common(50))
        result["interesting_paths"] = interesting_paths
        result["sensitive_path_flags"] = sensitive_flags
    except Exception as exc:  # noqa: BLE001 - inventory should report and continue.
        result["error"] = f"{type(exc).__name__}: {exc}"

    return result


def sqlite_schema(path: Path) -> dict:
    result: dict = {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else None,
        "error": None,
        "tables": [],
    }

    if not path.exists():
        return result

    try:
        uri = f"file:{path}?mode=ro&immutable=1"
        with sqlite3.connect(uri, uri=True, timeout=2) as connection:
            cursor = connection.execute(
                "select name, type from sqlite_master where type in ('table','view') order by type, name"
            )
            for name, object_type in cursor.fetchall():
                columns = []
                try:
                    for column in connection.execute(f'pragma table_info("{name}")').fetchall():
                        columns.append({"name": column[1], "type": column[2]})
                except sqlite3.DatabaseError as exc:
                    columns.append({"error": str(exc)})
                result["tables"].append({"name": name, "type": object_type, "columns": columns})
    except Exception as exc:  # noqa: BLE001 - inventory should report and continue.
        result["error"] = f"{type(exc).__name__}: {exc}"

    return result


def inventory_directory(path: Path) -> dict:
    result: dict = {
        "path": str(path),
        "exists": path.exists(),
        "error": None,
        "total_files": 0,
        "suffix_counts": {},
        "top_level_counts": {},
        "interesting_paths": [],
        "sensitive_path_flags": [],
        "sqlite_databases": [],
    }

    if not path.exists():
        return result

    suffix_counts: Counter[str] = Counter()
    top_level_counts: Counter[str] = Counter()
    interesting_paths: list[str] = []
    sensitive_flags: list[str] = []
    sqlite_paths: list[Path] = []

    try:
        for root, dirs, files in os.walk(path):
            root_path = Path(root)
            dirs[:] = [
                directory
                for directory in dirs
                if directory not in {".git", "node_modules", "__pycache__", ".venv", "venv"}
            ]

            for file_name in files:
                file_path = root_path / file_name
                try:
                    relative = file_path.relative_to(path)
                except ValueError:
                    relative = file_path
                relative_text = str(relative)

                result["total_files"] += 1
                parts = relative.parts
                top_level_counts[parts[0] if parts else "(root)"] += 1
                suffix = file_path.suffix.lower() or "(none)"
                suffix_counts[suffix] += 1

                if suffix in INTERESTING_SUFFIXES and len(interesting_paths) < 400:
                    interesting_paths.append(relative_text)
                if is_sensitive(relative_text) and len(sensitive_flags) < 100:
                    sensitive_flags.append(relative_text)
                if suffix in {".db", ".sqlite"} and len(sqlite_paths) < 25:
                    sqlite_paths.append(file_path)

        result["suffix_counts"] = dict(suffix_counts.most_common(50))
        result["top_level_counts"] = dict(top_level_counts.most_common(50))
        result["interesting_paths"] = interesting_paths
        result["sensitive_path_flags"] = sensitive_flags
        result["sqlite_databases"] = [sqlite_schema(sqlite_path) for sqlite_path in sqlite_paths]
    except Exception as exc:  # noqa: BLE001 - inventory should report and continue.
        result["error"] = f"{type(exc).__name__}: {exc}"

    return result


def main() -> int:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    inventory = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtime_root": str(RUNTIME_ROOT),
        "sources": {
            "p2_cursor_zip": inventory_zip(P2_CURSOR_ZIP),
            "algo_trading_root": inventory_directory(ALGO_ROOT),
        },
    }
    OUTPUT_PATH.write_text(json.dumps(inventory, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"output_path": str(OUTPUT_PATH), "sources": list(inventory["sources"].keys())}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
