from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_nifty_sector_package.py"
SPEC = importlib.util.spec_from_file_location("build_nifty_sector_package", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(module)


def write_csv(path: Path, symbol: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(module.EXPECTED_COLUMNS)
        writer.writerow([f"{symbol} Ltd.", "Example Industry", symbol, "EQ", "INE000A01000"])


def test_builder_preserves_official_lineage_and_does_not_infer_history(tmp_path: Path) -> None:
    for _, _, file_name, _ in module.INDEXES:
        write_csv(tmp_path / file_name, file_name.split(".")[0].upper())
    package = module.build_package(tmp_path, "2026-07-31", "2026-08-04T12:00:00+00:00")
    assert package["source"]["source_type"] == "primary_exchange_index_download"
    assert len(package["source"]["manifest"]) == len(module.INDEXES)
    assert len(package["memberships"]) == len(module.INDEXES) * 2
    sector = package["taxonomy"][0]
    assert sector["methodology"]["historical_start_unknown"] is True
    assert "index_weights" in sector["methodology"]["not_authoritative_for"]
    membership = package["memberships"][0]
    assert membership["instrument_type"] == "equity"
    assert membership["is_primary"] is False
    assert membership["evidence"][0]["isin"] == "INE000A01000"
