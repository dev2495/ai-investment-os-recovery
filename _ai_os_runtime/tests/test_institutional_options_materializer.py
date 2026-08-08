from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "materialize_institutional_options.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("materialize_institutional_options", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(module)


class InstitutionalOptionsMaterializerTests(unittest.TestCase):
    @patch.object(module, "record_run")
    @patch.object(module, "pending_groups", return_value=[])
    def test_empty_source_is_blocked_not_reported_as_completed(self, pending, record) -> None:
        result = module.run(20)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["rows_read"], 0)
        self.assertEqual(result["batches_created"], 0)
        self.assertIn("no unmaterialized source", record.call_args.kwargs["error"])

    def test_contract_quality_flags_crossed_and_missing_oi(self) -> None:
        result = module.quality_for_contract({
            "quote_source_timestamp": "2026-08-04T04:00:00+00:00",
            "received_at": "2026-08-04T04:00:03+00:00",
            "bid_price": 12,
            "ask_price": 10,
            "open_interest": 0,
        })
        self.assertEqual(result["staleness_status"], "live")
        self.assertEqual(result["liquidity_status"], "illiquid")
        self.assertIn("crossed_quote", result["liquidity_flags"])
        self.assertIn("missing_open_interest", result["liquidity_flags"])

    def test_expiry_timestamp_uses_configured_timezone(self) -> None:
        value = module.expiry_timestamp(
            {"expiry": "2026-08-06"},
            {"expiry_local_time": "15:30:00", "expiry_timezone": "Asia/Kolkata"},
        )
        self.assertEqual(value, datetime(2026, 8, 6, 10, 0, tzinfo=timezone.utc))

    @patch.object(module, "record_run")
    @patch.object(module, "active_policy", return_value=None)
    @patch.object(module, "create_contracts", return_value=[{"id": 1}])
    @patch.object(module, "create_batch")
    @patch.object(module, "source_contracts", return_value=[{"legacy_snapshot_id": 1}])
    @patch.object(module, "pending_groups")
    def test_missing_policy_blocks_calculation_without_fabricating_inputs(
        self, pending, source, create_batch, create_contracts, policy, record
    ) -> None:
        pending.return_value = [{"provider": "Zerodha"}]
        create_batch.return_value = {"batch_key": "batch-1"}
        result = module.run(1)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["calculations_completed"], 0)
        self.assertEqual(result["calculations_blocked"], 1)
        self.assertEqual(result["outcomes"][0]["status"], "blocked_missing_valuation_policy")
        record.assert_called_once()

    def test_safety_contract_is_explicit_in_source(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"paper_only": True', source)
        self.assertIn('"broker_write_allowed": False', source)
        for table in (
            "trading.option_iv_greeks_results",
            "trading.option_premium_series",
            "trading.option_expected_move_bands",
            "trading.option_exposure_estimates",
        ):
            self.assertIn(table, source)
        self.assertNotIn("broker_order", source)
        self.assertNotIn("default_rate", source)


if __name__ == "__main__":
    unittest.main()
