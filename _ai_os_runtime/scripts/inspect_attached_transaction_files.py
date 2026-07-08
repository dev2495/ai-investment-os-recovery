#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


FILES = [
    Path("/Users/devarshthakkar/Downloads/3081282_Transactions (1).xls"),
    Path("/Users/devarshthakkar/Downloads/3081282_Transactions.xls"),
    Path("/Users/devarshthakkar/Desktop/option log.xlsx"),
]


def profile_frame(df: pd.DataFrame) -> dict:
    columns = [str(column).strip() for column in df.columns]
    date_like = []
    for column in columns:
        lower = column.lower()
        if "date" in lower or "time" in lower:
            series = pd.to_datetime(df[column], errors="coerce")
            if series.notna().any():
                date_like.append(
                    {
                        "column": column,
                        "min": series.min().isoformat(),
                        "max": series.max().isoformat(),
                        "non_null": int(series.notna().sum()),
                    }
                )
    return {
        "rows": int(len(df)),
        "columns": columns,
        "date_like": date_like,
        "non_null_counts": {column: int(df[column].notna().sum()) for column in df.columns[:40]},
    }


def read_file(path: Path) -> list[dict]:
    if path.suffix.lower() == ".xlsx":
        sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
        return [{"sheet": sheet_name, **profile_frame(frame)} for sheet_name, frame in sheets.items()]
    tables = pd.read_html(path)
    return [{"sheet": f"html_table_{index + 1}", **profile_frame(frame)} for index, frame in enumerate(tables)]


def main() -> int:
    output = []
    for path in FILES:
        output.append({"path": str(path), "exists": path.exists(), "tables": read_file(path) if path.exists() else []})
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
