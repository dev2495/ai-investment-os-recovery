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

    def test_black_76_reference_is_a_derived_forward_not_spot(self) -> None:
        result = module.valuation_reference(
            {"spot_price": 25000},
            {"model_family": "black_76", "risk_free_rate": 0.053542, "dividend_yield": 0.0129},
            30 / 365,
        )
        self.assertEqual(result["reference_kind"], "derived_forward")
        self.assertEqual(result["forward_method"], "spot_rate_dividend_carry")
        self.assertGreater(result["forward_price"], result["spot_price"])
        self.assertAlmostEqual(result["reference_price"], result["forward_price"])

    def test_bsm_reference_remains_spot(self) -> None:
        result = module.valuation_reference(
            {"spot_price": 25000},
            {"model_family": "black_scholes_merton", "risk_free_rate": 0.05, "dividend_yield": 0.01},
            30 / 365,
        )
        self.assertEqual(result["reference_kind"], "spot")
        self.assertIsNone(result["forward_price"])
        self.assertEqual(result["reference_price"], 25000)

    @patch.object(module, "record_run")
    @patch.object(module, "rebuild_point_in_time_replay", return_value=2)
    @patch.object(module, "persist_specialist_observation", return_value=1)
    @patch.object(module, "persist_source_premium_series", return_value=2)
    @patch.object(module, "persist_market_structure", return_value={"heatmap": 1, "buildup": 0, "migrations": 0})
    @patch.object(module, "active_policy", return_value=None)
    @patch.object(module, "create_contracts", return_value=[{"id": 1}])
    @patch.object(module, "create_batch")
    @patch.object(module, "source_contracts", return_value=[{"legacy_snapshot_id": 1}])
    @patch.object(module, "pending_groups")
    def test_missing_policy_blocks_calculation_without_fabricating_inputs(
        self, pending, source, create_batch, create_contracts, policy,
        market_structure, premium, specialist, replay, record
    ) -> None:
        pending.return_value = [{"provider": "Zerodha"}]
        create_batch.return_value = {
            "id": 1, "batch_key": "batch-1", "provider": "Zerodha",
            "exchange": "NFO", "underlying": "NIFTY", "expiry": "2026-08-11",
        }
        result = module.run(1)
        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["calculations_completed"], 6)
        self.assertEqual(result["calculations_blocked"], 1)
        self.assertEqual(result["outcomes"][0]["status"], "market_structure_completed_valuation_blocked")
        self.assertEqual(result["replay_frames_written"], 2)
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
            "trading.option_oi_heatmap_cells",
            "trading.option_buildup_classifications",
            "trading.option_strike_migrations",
            "trading.option_replay_sessions",
            "trading.option_replay_frames",
            "trading.option_specialist_observations",
            "trading.option_volatility_metrics",
        ):
            self.assertIn(table, source)
        self.assertNotIn("broker_order", source)
        self.assertNotIn("default_rate", source)
        self.assertIn('"forward_price": float(valuation["forward_price"])', source)

    def test_source_minutes_are_refreshed_across_expiries(self) -> None:
        touched = [{
            "id": 1, "provider": "Zerodha", "exchange": "NFO", "underlying": "NIFTY",
            "expiry": "2026-08-11", "minute_ts": "2026-08-10T04:00:00+00:00",
            "source_timestamp": "2026-08-10T04:00:01+00:00",
            "received_at": "2026-08-10T04:00:02+00:00", "spot_price": 25000,
        }]
        with patch.object(module, "rows", return_value=[{
            "id": 2, "batch_key": "later", "provider": "Zerodha", "exchange": "NFO",
            "underlying": "NIFTY", "expiry": "2026-08-18",
            "minute_ts": "2026-08-10T04:00:00+00:00",
            "source_timestamp": "2026-08-10T04:00:03+00:00",
            "received_at": "2026-08-10T04:00:04+00:00", "spot_price": 25000,
        }]) as query:
            refreshed = module.volatility_refresh_batches(touched)
        self.assertEqual([row["id"] for row in refreshed], [1, 2])
        self.assertIn("batch.minute_ts IN", query.call_args.args[0])
        self.assertIn("result.calculation_status='validated'", query.call_args.args[0])

    def test_replay_uses_parsed_timestamp_maximum(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('max(parse_timestamp(row["source_timestamp"]) for row in scope).isoformat()', source)
        self.assertIn("prior_oi_changes", source)


if __name__ == "__main__":
    unittest.main()
