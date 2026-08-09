from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
SPEC = importlib.util.spec_from_file_location(
    "build_sector_membership_history_package",
    SCRIPT_DIR / "build_sector_membership_history_package.py",
)
module = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(module)


def write_snapshot(path: Path, symbols: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(module.EXPECTED_COLUMNS)
        for position, symbol in enumerate(symbols):
            writer.writerow([f"{symbol} Ltd.", "IT Services", symbol, "EQ", f"INE{position:03d}A01000"])


def write_manifest(tmp_path: Path, dates: list[str]) -> Path:
    snapshots = []
    for position, as_of in enumerate(dates):
        file_name = f"nifty-it-{as_of}.csv"
        write_snapshot(tmp_path / file_name, ["INFY", "TCS"] if position == 0 else ["INFY", "WIPRO"])
        snapshots.append({
            "as_of_date": as_of,
            "file": file_name,
            "artifact_type": "official_constituent_snapshot",
            "source_url": f"https://www.niftyindices.com/evidence/{file_name}",
            "release_reference": f"official-snapshot-{as_of}",
        })
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({
        "source_location": "https://www.niftyindices.com/",
        "observed_at": "2026-08-09T12:00:00+00:00",
        "snapshots": snapshots,
    }), encoding="utf-8")
    return path


def test_builds_non_overlapping_full_snapshot_history(tmp_path: Path) -> None:
    package = module.build_package(write_manifest(tmp_path, ["2024-07-31", "2026-07-31"]), "nifty-it")
    assert package["source"]["controls"]["replacement_notice_inference_allowed"] is False
    assert package["taxonomy"][0]["methodology"]["snapshot_count"] == 2
    assert len(package["memberships"]) == 4
    first = [row for row in package["memberships"] if row["valid_from"] == "2024-07-31"]
    latest = [row for row in package["memberships"] if row["valid_from"] == "2026-07-31"]
    assert {row["valid_to"] for row in first} == {"2026-07-30"}
    assert {row["valid_to"] for row in latest} == {None}
    assert first[0]["evidence"][0]["full_basket_row_count"] == 2
    assert package["source"]["manifest"][1]["added_symbols"] == ["WIPRO"]
    assert package["source"]["manifest"][1]["removed_symbols"] == ["TCS"]


def test_rejects_history_shorter_than_acceptance_span(tmp_path: Path) -> None:
    manifest = write_manifest(tmp_path, ["2026-01-01", "2026-07-31"])
    try:
        module.build_package(manifest, "nifty-it")
    except module.SnapshotError as exc:
        assert "365 days" in str(exc)
    else:
        raise AssertionError("short history should have been rejected")


def test_rejects_replacement_notice_as_full_snapshot(tmp_path: Path) -> None:
    manifest = write_manifest(tmp_path, ["2024-07-31", "2026-07-31"])
    value = json.loads(manifest.read_text(encoding="utf-8"))
    value["snapshots"][0]["artifact_type"] = "replacement_notice"
    manifest.write_text(json.dumps(value), encoding="utf-8")
    try:
        module.build_package(manifest, "nifty-it")
    except module.SnapshotError as exc:
        assert "official_constituent_snapshot" in str(exc)
    else:
        raise AssertionError("replacement notices must not masquerade as full snapshots")
