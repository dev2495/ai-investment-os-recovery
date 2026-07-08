#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from itertools import zip_longest
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = RUNTIME_ROOT / "imports" / "p2cursor_profile.json"


def sql_quote(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def jsonb_quote(value: object) -> str:
    return sql_quote(json.dumps(value, sort_keys=True)) + "::jsonb"


def row_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def safe_headers(headers: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    output: list[str] = []
    for index, header in enumerate(headers, start=1):
        name = (header or "").strip() or f"column_{index}"
        count = seen.get(name, 0) + 1
        seen[name] = count
        output.append(name if count == 1 else f"{name}_{count}")
    return output


def detect_dialect(path: Path) -> csv.Dialect:
    with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as handle:
        sample = handle.read(65536)
    try:
        return csv.Sniffer().sniff(sample, delimiters=",\t;|")
    except csv.Error:
        return csv.excel


def read_csv_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    dialect = detect_dialect(path)
    with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as handle:
        reader = csv.reader(handle, dialect)
        try:
            raw_headers = next(reader)
        except StopIteration:
            return rows
        headers = safe_headers(raw_headers)
        for row_number, row in enumerate(reader, start=2):
            payload = {
                header: value
                for header, value in zip_longest(headers, row, fillvalue="")
                if header != ""
            }
            payload["__source_row_number"] = row_number
            rows.append(payload)
    return rows


def build_sql(profile_path: Path) -> tuple[str, dict]:
    data = json.loads(profile_path.read_text(encoding="utf-8"))
    statements = [
        "BEGIN;",
        """
CREATE TABLE IF NOT EXISTS client_data.p2cursor_csv_rows (
    id BIGSERIAL PRIMARY KEY,
    source_file_id BIGINT REFERENCES client_data.source_files(id),
    original_path TEXT NOT NULL,
    row_number INTEGER NOT NULL,
    row_hash TEXT NOT NULL,
    row_payload JSONB NOT NULL,
    import_status TEXT NOT NULL DEFAULT 'staged',
    staged_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE NULLS NOT DISTINCT (source_file_id, row_number, row_hash)
);
""",
        "CREATE INDEX IF NOT EXISTS idx_p2cursor_csv_rows_file ON client_data.p2cursor_csv_rows (source_file_id);",
        "CREATE INDEX IF NOT EXISTS idx_p2cursor_csv_rows_hash ON client_data.p2cursor_csv_rows (row_hash);",
    ]
    summary = {"files_seen": 0, "files_staged": 0, "rows_staged": 0, "skipped": []}

    for item in data.get("files", []):
        if item.get("profile", {}).get("kind") != "csv":
            continue
        summary["files_seen"] += 1
        path = Path(item["extracted_path"])
        rows = read_csv_rows(path)
        if not rows:
            summary["skipped"].append({"original_path": item.get("original_path"), "reason": "empty_csv"})
            continue
        summary["files_staged"] += 1
        summary["rows_staged"] += len(rows)
        for payload in rows:
            number = int(payload.get("__source_row_number") or 0)
            digest = row_hash(payload)
            statements.append(
                f"""
WITH source_file AS (
    SELECT id
    FROM client_data.source_files
    WHERE sha256 = {sql_quote(item.get("sha256"))}
    ORDER BY id
    LIMIT 1
)
INSERT INTO client_data.p2cursor_csv_rows (
    source_file_id,
    original_path,
    row_number,
    row_hash,
    row_payload,
    import_status
)
SELECT
    source_file.id,
    {sql_quote(item.get("original_path"))},
    {number},
    {sql_quote(digest)},
    {jsonb_quote(payload)},
    'staged'
FROM source_file
ON CONFLICT (source_file_id, row_number, row_hash) DO NOTHING;
"""
            )

    statements.append("COMMIT;")
    return "\n".join(statements), summary


def run_psql(sql: str) -> None:
    command = ["docker", "exec", "-i", "ai_os_postgres", "psql", "-U", "ai_os", "-d", "ai_os", "-v", "ON_ERROR_STOP=1"]
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        sys.stderr.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise SystemExit(completed.returncode)


def main() -> int:
    sql, summary = build_sql(DEFAULT_PROFILE)
    run_psql(sql)
    print(json.dumps({**summary, "target_table": "client_data.p2cursor_csv_rows"}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
