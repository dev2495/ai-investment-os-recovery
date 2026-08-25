from __future__ import annotations

import datetime as dt
import sys
import unittest
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME_ROOT / "scripts"))

import sync_sector_ownership_flows as collector


class SectorOwnershipFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.member = {"symbol_id": 7, "symbol": "INFY", "exchange": "NSE"}
        self.artifact = {
            "source_endpoint": "https://www.nseindia.com/api/example",
            "artifact_path": "/Volumes/Devarsh SSD/evidence.json",
            "artifact_sha256": "a" * 64,
            "fetched_at": "2026-08-08T10:00:00+00:00",
        }

    def test_shareholding_cutoff_uses_filing_availability_not_only_period(self) -> None:
        payload = [
            {"date": "30-JUN-2026", "submissionDate": "15-JUL-2026", "recordId": "1"},
            {"date": "30-JUN-2026", "submissionDate": "10-AUG-2026", "recordId": "2"},
        ]
        rows = collector.eligible_shareholding_rows(payload, dt.date(2026, 8, 8))
        self.assertEqual([row["recordId"] for row in rows], ["1"])

    def test_ownership_normalization_preserves_xbrl_and_quarter_change(self) -> None:
        rows = collector.eligible_shareholding_rows([
            {
                "date": "31-MAR-2026", "submissionDate": "16-APR-2026",
                "recordId": "10", "xbrl": "https://nsearchives.nseindia.com/one.xml",
                "pr_and_prgrp": "14.38", "public_val": "85.38", "employeeTrusts": "0.23",
            },
            {
                "date": "30-JUN-2026", "submissionDate": "15-JUL-2026",
                "recordId": "11", "xbrl": "https://nsearchives.nseindia.com/two.xml",
                "pr_and_prgrp": "13.82", "public_val": "85.97", "employeeTrusts": "0.21",
            },
        ], dt.date(2026, 8, 8))
        output = collector.normalize_ownership(rows, self.member, 3, 101, self.artifact)
        latest_promoter = next(
            row for row in output
            if row["period_end"] == "2026-06-30" and row["holder_category"] == "promoter"
        )
        self.assertEqual(str(latest_promoter["holding_percent"]), "13.82")
        self.assertEqual(str(latest_promoter["change_percent_points"]), "-0.56")
        self.assertEqual(latest_promoter["source_reference"], "https://nsearchives.nseindia.com/two.xml")
        self.assertEqual(latest_promoter["evidence"][0]["record_id"], "11")

    def test_deal_normalization_preserves_side_and_does_not_guess_actor(self) -> None:
        output = collector.normalize_deals({
            "data": [
                {
                    "BD_DT_DATE": "24-JUN-2026", "BD_SYMBOL": "INFY",
                    "BD_CLIENT_NAME": "NAMED FUND", "BD_BUY_SELL": "BUY",
                    "BD_QTY_TRD": 100, "BD_TP_WATP": 1250,
                },
                {
                    "BD_DT_DATE": "24-JUN-2026", "BD_SYMBOL": "INFY",
                    "BD_CLIENT_NAME": "NAMED FUND", "BD_BUY_SELL": "SELL",
                    "BD_QTY_TRD": 40, "BD_TP_WATP": 1250,
                },
            ]
        }, self.member, 3, 102, "block_deal", self.artifact, dt.date(2026, 8, 8))
        self.assertEqual(str(output[0]["net_value"]), "125000")
        self.assertEqual(str(output[1]["net_value"]), "-50000")
        self.assertEqual(output[0]["flow_actor"], "institution")
        self.assertFalse(output[0]["evidence"][0]["actor_inference_used"])
        self.assertIsNone(output[0]["sell_value"])
        self.assertIsNone(output[1]["buy_value"])

    def test_migration_requires_both_evidence_types_and_active_membership(self) -> None:
        migration = (RUNTIME_ROOT / "postgres" / "init" / "207_sector_ownership_flow_v1.sql").read_text(encoding="utf-8")
        self.assertIn("v_flow_count>=1 AND v_ownership_count>=1", migration)
        self.assertIn("JOIN active_members", migration)
        self.assertIn("'market_wide_flow_substitution_allowed',false", migration)
        self.assertIn("jsonb_array_length(flow.evidence)>0", migration)
        self.assertIn("jsonb_array_length(ownership.evidence)>0", migration)

    def test_governance_has_no_order_or_capital_surface(self) -> None:
        source = (RUNTIME_ROOT / "scripts" / "sync_sector_ownership_flows.py").read_text(encoding="utf-8")
        self.assertIn('"broker_write_allowed": False', source)
        self.assertIn('"capital_action_allowed": False', source)
        self.assertNotIn("INSERT INTO trading.orders", source)
        self.assertNotIn("INSERT INTO portfolio.trades", source)


if __name__ == "__main__":
    unittest.main()
