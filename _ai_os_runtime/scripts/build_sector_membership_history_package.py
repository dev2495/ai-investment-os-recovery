#!/usr/bin/env python3
"""Build point-in-time sector membership from dated full-basket source snapshots."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from build_nifty_sector_package import EXPECTED_COLUMNS, INDEXES


INDEX_BY_KEY = {
    index_key: (index_name, file_name, page_slug)
    for index_key, index_name, file_name, page_slug in INDEXES
}


class SnapshotError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_snapshot(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != EXPECTED_COLUMNS:
            raise SnapshotError(f"unexpected columns in {path}: {reader.fieldnames}")
        seen: set[str] = set()
        for position, raw in enumerate(reader, start=2):
            row = {key: str(raw.get(key) or "").strip() for key in EXPECTED_COLUMNS}
            if not all(row.values()):
                raise SnapshotError(f"incomplete row in {path}:{position}")
            if row["Series"] != "EQ":
                raise SnapshotError(f"unsupported series in {path}:{position}: {row['Series']}")
            symbol = row["Symbol"].upper()
            if symbol in seen:
                raise SnapshotError(f"duplicate symbol in {path}: {symbol}")
            seen.add(symbol)
            row["Symbol"] = symbol
            rows.append(row)
    if not rows:
        raise SnapshotError(f"empty constituent snapshot: {path}")
    return rows


def load_manifest(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SnapshotError("manifest root must be an object")
    return value


def build_package(manifest_path: Path, index_key: str) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    if index_key not in INDEX_BY_KEY:
        raise SnapshotError(f"unsupported index_key: {index_key}")
    index_name, default_file_name, page_slug = INDEX_BY_KEY[index_key]
    source_name = str(manifest.get("source_name") or "NSE Indices historical constituent snapshots").strip()
    source_location = str(manifest.get("source_location") or "").strip()
    if not source_location:
        raise SnapshotError("source_location is required")
    observed_at = str(manifest.get("observed_at") or datetime.now(timezone.utc).isoformat())
    observed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    if observed.tzinfo is None:
        raise SnapshotError("observed_at must include a timezone")

    raw_snapshots = list(manifest.get("snapshots") or [])
    if len(raw_snapshots) < 2:
        raise SnapshotError("at least two full-basket snapshots are required")
    parsed: list[dict[str, Any]] = []
    manifest_dir = manifest_path.parent
    seen_dates: set[date] = set()
    for position, raw in enumerate(raw_snapshots):
        if not isinstance(raw, dict):
            raise SnapshotError(f"snapshots[{position}] must be an object")
        if str(raw.get("artifact_type") or "") != "official_constituent_snapshot":
            raise SnapshotError(f"snapshots[{position}] must declare artifact_type=official_constituent_snapshot")
        as_of = date.fromisoformat(str(raw.get("as_of_date") or ""))
        if as_of in seen_dates:
            raise SnapshotError(f"duplicate snapshot date: {as_of.isoformat()}")
        seen_dates.add(as_of)
        file_path = Path(str(raw.get("file") or default_file_name)).expanduser()
        if not file_path.is_absolute():
            file_path = manifest_dir / file_path
        if not file_path.is_file():
            raise SnapshotError(f"snapshot file not found: {file_path}")
        source_url = str(raw.get("source_url") or "").strip()
        if not source_url:
            raise SnapshotError(f"snapshots[{position}].source_url is required")
        rows = parse_snapshot(file_path)
        parsed.append({
            "as_of_date": as_of,
            "file": file_path,
            "source_url": source_url,
            "release_reference": str(raw.get("release_reference") or "").strip() or None,
            "sha256": sha256_file(file_path),
            "rows": rows,
        })
    parsed.sort(key=lambda item: item["as_of_date"])
    if (parsed[-1]["as_of_date"] - parsed[0]["as_of_date"]).days < 365:
        raise SnapshotError("snapshot history must span at least 365 days")

    taxonomy_key = f"nse-index:{index_key}"
    memberships: list[dict[str, Any]] = []
    previous_symbols: set[str] = set()
    source_manifest: list[dict[str, Any]] = []
    for position, snapshot in enumerate(parsed):
        current_symbols = {row["Symbol"] for row in snapshot["rows"]}
        next_date = parsed[position + 1]["as_of_date"] if position + 1 < len(parsed) else None
        valid_to = next_date - timedelta(days=1) if next_date else None
        source_manifest.append({
            "as_of_date": snapshot["as_of_date"].isoformat(),
            "file_name": snapshot["file"].name,
            "sha256": snapshot["sha256"],
            "row_count": len(snapshot["rows"]),
            "source_url": snapshot["source_url"],
            "release_reference": snapshot["release_reference"],
            "added_symbols": sorted(current_symbols - previous_symbols) if position else [],
            "removed_symbols": sorted(previous_symbols - current_symbols) if position else [],
        })
        for row in snapshot["rows"]:
            evidence = [{
                "source": "NSE Indices Limited",
                "artifact_type": "official_constituent_snapshot",
                "source_url": snapshot["source_url"],
                "release_reference": snapshot["release_reference"],
                "artifact_sha256": snapshot["sha256"],
                "observed_at": observed.astimezone(timezone.utc).isoformat(),
                "membership_as_of": snapshot["as_of_date"].isoformat(),
                "company_name": row["Company Name"],
                "industry": row["Industry"],
                "series": row["Series"],
                "isin": row["ISIN Code"],
                "full_basket_row_count": len(snapshot["rows"]),
            }]
            memberships.append({
                "symbol": row["Symbol"],
                "exchange": "NSE",
                "instrument_type": "equity",
                "company_name": row["Company Name"],
                "currency": "INR",
                "taxonomy_key": taxonomy_key,
                "membership_role": "official_index_constituent",
                "valid_from": snapshot["as_of_date"].isoformat(),
                "valid_to": valid_to.isoformat() if valid_to else None,
                "is_primary": False,
                "source_reference": f"sha256://{snapshot['sha256']}",
                "evidence": evidence,
            })
        previous_symbols = current_symbols

    canonical = json.dumps(source_manifest, sort_keys=True, separators=(",", ":"))
    package_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "source": {
            "name": source_name,
            "source_type": "primary_exchange_index_snapshot_history",
            "location": source_location,
            "artifact_ref": f"sha256://{package_hash}",
            "observed_at": observed.astimezone(timezone.utc).isoformat(),
            "manifest": source_manifest,
            "controls": {
                "full_basket_snapshots_only": True,
                "replacement_notice_inference_allowed": False,
                "backdating_current_snapshot_allowed": False,
            },
        },
        "taxonomy": [{
            "taxonomy_key": taxonomy_key,
            "node_code": index_key.upper().replace("-", "_"),
            "node_name": index_name,
            "node_level": "sector",
            "valid_from": parsed[0]["as_of_date"].isoformat(),
            "description": "Point-in-time official Nifty sectoral-index basket history from dated full snapshots.",
            "source_reference": f"sha256://{package_hash}",
            "methodology": {
                "classification_scope": "official_index_basket_history",
                "historical_start_unknown": False,
                "history_start": parsed[0]["as_of_date"].isoformat(),
                "history_end": parsed[-1]["as_of_date"].isoformat(),
                "snapshot_count": len(parsed),
                "full_basket_snapshots_only": True,
                "page_url": f"https://www.niftyindices.com/indices/equity/sectoral-indices/{page_slug}",
            },
        }],
        "memberships": memberships,
        "metrics": [],
        "indices": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--index-key", required=True, choices=sorted(INDEX_BY_KEY))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    package = build_package(args.manifest.expanduser().resolve(), args.index_key)
    args.output.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "snapshot_count": len(package["source"]["manifest"]),
        "membership_rows": len(package["memberships"]),
        "source_artifact_ref": package["source"]["artifact_ref"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
