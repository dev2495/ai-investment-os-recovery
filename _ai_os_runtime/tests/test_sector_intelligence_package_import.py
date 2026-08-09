from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "import_sector_intelligence_package.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("import_sector_intelligence_package", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(module)


def package() -> dict:
    return {
        "source": {
            "name": "Licensed sector export",
            "location": "operator://sector-export.json",
            "artifact_ref": "sha256://evidence-package",
            "observed_at": "2026-08-04T09:00:00+05:30",
        },
        "taxonomy": [
            {"taxonomy_key": "in-industrials", "node_code": "IND", "node_name": "Industrials",
             "node_level": "sector", "valid_from": "2020-01-01"},
            {"taxonomy_key": "in-industrials-cables", "node_code": "CABLE", "node_name": "Cables",
             "node_level": "industry", "parent_key": "in-industrials", "valid_from": "2020-01-01"},
        ],
        "memberships": [
            {"symbol": "POLYCAB", "exchange": "NSE", "instrument_type": "equity",
             "taxonomy_key": "in-industrials-cables", "valid_from": "2020-01-01",
             "source_reference": "sha256://membership-evidence",
             "evidence": [{"field": "industry", "value": "Cables"}]},
        ],
        "metrics": [
            {"metric_key": "market_cap", "metric_name": "Market capitalization",
             "metric_family": "valuation", "value_numeric": 100,
             "subject": {"symbol": "POLYCAB", "exchange": "NSE", "instrument_type": "equity"},
             "observed_at": "2026-08-04T09:00:00+05:30"},
        ],
        "indices": [
            {"index_key": "cables-equal", "index_name": "Cables Equal Weight",
             "taxonomy_key": "in-industrials-cables", "base_date": "2026-01-01",
             "weighting_method": "equal",
             "constituents": [{"symbol": "POLYCAB", "exchange": "NSE", "instrument_type": "equity"}]},
        ],
    }


class SectorIntelligencePackageImportTests(unittest.TestCase):
    def test_complete_package_validates_and_builds_transactional_sql(self) -> None:
        validated = module.validate_package(package())
        self.assertEqual(validated["counts"], {"taxonomy": 2, "memberships": 1, "metrics": 1, "indices": 1})
        digest = module.package_hash(package())
        sql = module.build_import_sql(validated, digest, "Sector Data Steward", "run-1")
        self.assertTrue(sql.startswith("BEGIN;"))
        self.assertIn("sector_intelligence.source_import_runs", sql)
        self.assertIn("INSERT INTO trading.symbols", sql)
        self.assertIn("instrument_type", sql)
        self.assertIn("sector package already imported", sql)
        self.assertIn("COMMIT;", sql)
        self.assertNotIn("broker_order", sql)

    def test_membership_without_evidence_is_rejected(self) -> None:
        value = package()
        value["memberships"][0]["evidence"] = []
        with self.assertRaisesRegex(module.PackageError, "evidence is required"):
            module.validate_package(value)

    def test_invalid_hierarchy_is_rejected(self) -> None:
        value = package()
        value["taxonomy"][1]["parent_key"] = "missing"
        with self.assertRaisesRegex(module.PackageError, "parent missing"):
            module.validate_package(value)

    def test_metric_requires_exactly_one_subject_and_value(self) -> None:
        value = package()
        value["metrics"][0]["subject"]["taxonomy_key"] = "in-industrials"
        with self.assertRaisesRegex(module.PackageError, "must identify one"):
            module.validate_package(value)

    def test_overlapping_membership_windows_are_rejected(self) -> None:
        value = package()
        value["memberships"][0]["valid_to"] = "2021-12-31"
        value["memberships"].append({
            **value["memberships"][0],
            "valid_from": "2021-01-01",
            "valid_to": None,
        })
        with self.assertRaisesRegex(module.PackageError, "overlapping membership windows"):
            module.validate_package(value)


if __name__ == "__main__":
    unittest.main()
