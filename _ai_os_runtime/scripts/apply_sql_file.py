#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]


def run_sql(sql_path: Path) -> None:
    sql = sql_path.read_text(encoding="utf-8")
    command = ["docker", "exec", "-i", "ai_os_postgres", "psql", "-U", "ai_os", "-d", "ai_os", "-v", "ON_ERROR_STOP=1"]
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        sys.stderr.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise SystemExit(completed.returncode)
    sys.stdout.write(completed.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a SQL file to the AI OS Postgres container.")
    parser.add_argument("sql_file", type=Path)
    args = parser.parse_args()

    sql_path = args.sql_file
    if not sql_path.is_absolute():
        sql_path = RUNTIME_ROOT / sql_path
    run_sql(sql_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
