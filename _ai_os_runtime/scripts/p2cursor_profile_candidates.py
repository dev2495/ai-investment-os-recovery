#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sqlite3
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = RUNTIME_ROOT / "imports" / "p2cursor_extract_manifest.json"
DEFAULT_PROFILE = RUNTIME_ROOT / "imports" / "p2cursor_profile.json"
MAX_TEXT_BYTES = 50 * 1024 * 1024


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_text(value: object, limit: int = 120) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def profile_csv(path: Path) -> dict:
    result: dict = {"kind": "csv", "error": None, "delimiter": None, "columns": [], "row_count": None}
    try:
        with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as handle:
            sample = handle.read(65536)
            handle.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
            except csv.Error:
                dialect = csv.excel
            result["delimiter"] = getattr(dialect, "delimiter", ",")
            reader = csv.reader(handle, dialect)
            try:
                first_row = next(reader)
            except StopIteration:
                result["row_count"] = 0
                return result
            result["columns"] = [safe_text(column) for column in first_row]
            row_count = 1
            for row_count, _row in enumerate(reader, start=2):
                pass
            result["row_count"] = max(row_count - 1, 0)
    except Exception as exc:  # noqa: BLE001 - profiler should report and continue.
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def profile_sqlite(path: Path) -> dict:
    result: dict = {"kind": "sqlite", "error": None, "tables": []}
    try:
        uri = f"file:{path}?mode=ro&immutable=1"
        with sqlite3.connect(uri, uri=True, timeout=3) as connection:
            objects = connection.execute(
                "select name, type from sqlite_master where type in ('table','view') order by type, name"
            ).fetchall()
            for name, object_type in objects:
                table: dict = {"name": name, "type": object_type, "columns": [], "row_count": None, "error": None}
                try:
                    table["columns"] = [
                        {"name": column[1], "type": column[2], "not_null": bool(column[3]), "primary_key": bool(column[5])}
                        for column in connection.execute(f'pragma table_info("{name}")').fetchall()
                    ]
                    if object_type == "table":
                        table["row_count"] = connection.execute(f'select count(*) from "{name}"').fetchone()[0]
                except sqlite3.DatabaseError as exc:
                    table["error"] = str(exc)
                result["tables"].append(table)
    except Exception as exc:  # noqa: BLE001 - profiler should report and continue.
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def profile_xlsx(path: Path) -> dict:
    result: dict = {"kind": "xlsx", "error": None, "sheets": []}
    try:
        with zipfile.ZipFile(path) as workbook:
            workbook_xml = workbook.read("xl/workbook.xml")
        root = ElementTree.fromstring(workbook_xml)
        namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        for sheet in root.findall(".//main:sheet", namespace):
            result["sheets"].append({"name": sheet.attrib.get("name"), "sheet_id": sheet.attrib.get("sheetId")})
    except Exception as exc:  # noqa: BLE001 - profiler should report and continue.
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def profile_json(path: Path) -> dict:
    result: dict = {"kind": "json", "error": None, "top_level": None, "count": None, "keys": []}
    try:
        if path.stat().st_size > MAX_TEXT_BYTES:
            result["error"] = "skipped_profile_large_json"
            return result
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        result["top_level"] = type(data).__name__
        if isinstance(data, dict):
            result["keys"] = sorted(safe_text(key) for key in data.keys())[:250]
            result["count"] = len(data)
        elif isinstance(data, list):
            result["count"] = len(data)
            key_counts: Counter[str] = Counter()
            for item in data[:200]:
                if isinstance(item, dict):
                    key_counts.update(str(key) for key in item.keys())
            result["keys"] = sorted(key_counts.keys())[:250]
    except Exception as exc:  # noqa: BLE001 - profiler should report and continue.
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def profile_jsonl(path: Path) -> dict:
    result: dict = {"kind": "jsonl", "error": None, "row_count": 0, "keys": []}
    try:
        key_counts: Counter[str] = Counter()
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for index, line in enumerate(handle, start=1):
                if index <= 200:
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        item = None
                    if isinstance(item, dict):
                        key_counts.update(str(key) for key in item.keys())
                result["row_count"] = index
        result["keys"] = sorted(key_counts.keys())[:250]
    except Exception as exc:  # noqa: BLE001 - profiler should report and continue.
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def profile_file(path: Path) -> dict:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return profile_csv(path)
    if suffix in {".db", ".sqlite", ".sqlite3"}:
        return profile_sqlite(path)
    if suffix == ".xlsx":
        return profile_xlsx(path)
    if suffix == ".json":
        return profile_json(path)
    if suffix == ".jsonl":
        return profile_jsonl(path)
    return {"kind": suffix.lstrip(".") or "unknown", "error": "schema_profiler_not_available"}


def build_profile(manifest_path: Path, profile_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    profiles: list[dict] = []
    kind_counts: Counter[str] = Counter()
    error_counts: Counter[str] = Counter()

    for item in manifest.get("files", []):
        path = Path(item["extracted_path"])
        profile = profile_file(path)
        kind_counts[profile.get("kind", "unknown")] += 1
        if profile.get("error"):
            error_counts[profile["error"]] += 1
        profiles.append({**item, "profile": profile})

    output = {
        "generated_at": utc_now(),
        "manifest_path": str(manifest_path),
        "profile_path": str(profile_path),
        "runtime_root": str(RUNTIME_ROOT),
        "stats": {
            "profiled_files": len(profiles),
            "kind_counts": dict(kind_counts.most_common()),
            "profile_errors": dict(error_counts.most_common(25)),
        },
        "files": profiles,
    }
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")
    return output


def main() -> int:
    output = build_profile(DEFAULT_MANIFEST, DEFAULT_PROFILE)
    print(
        json.dumps(
            {
                "profile_path": str(DEFAULT_PROFILE),
                "profiled_files": output["stats"]["profiled_files"],
                "kind_counts": output["stats"]["kind_counts"],
                "profile_errors": output["stats"]["profile_errors"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
