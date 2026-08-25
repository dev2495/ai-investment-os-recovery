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
    def test_current_selector_is_provider_bounded_and_row_bounded(self) -> None:
        with patch.object(module, "rows", return_value=[]) as query:
            module.current_pending_groups(6, provider="Zerodha", source_row_limit=768)
        sql = query.call_args.args[0]
        self.assertIn("WITH candidate_source AS MATERIALIZED", sql)
        self.assertIn("FROM candidate_source legacy", sql)
        self.assertIn("legacy.provider='Zerodha'", sql)
        self.assertIn("ORDER BY legacy.observed_at DESC", sql)
        self.assertIn("LIMIT 8192", sql)
        self.assertIn("LIMIT 768", sql)
        self.assertIn("FROM recent_source legacy", sql)
        self.assertIn("source_payload->>'collected_at'", sql)
        self.assertIn("legacy.created_at", sql)
        self.assertIn("array_agg(legacy.id", sql)
        self.assertIn("batch.contract_count IS DISTINCT FROM source.contract_count", sql)

    def test_source_contracts_use_capture_minute_but_preserve_quote_timestamp(self) -> None:
        group = {
            "provider": "Zerodha", "exchange": "NFO", "underlying": "NIFTY",
            "expiry": "2026-08-18", "minute_ts": "2026-08-11T07:15:00+00:00",
            "source_snapshot_ids": [101, 102],
        }
        with patch.object(module, "rows", return_value=[]) as query:
            module.source_contracts(group)
        sql = query.call_args.args[0]
        self.assertIn("legacy.id=ANY(ARRAY[101,102]::bigint[])", sql)
        self.assertIn("legacy.observed_at::text AS quote_source_timestamp", sql)

    @patch.object(module, "historical_pending_groups", return_value=[{"mode": "maintenance"}])
    @patch.object(module, "current_pending_groups", return_value=[{"mode": "current"}])
    def test_historical_selector_requires_explicit_mode(self, current, historical) -> None:
        self.assertEqual(module.pending_groups(2), [{"mode": "current"}])
        historical.assert_not_called()
        self.assertEqual(
            module.pending_groups(2, maintenance_backfill=True),
            [{"mode": "maintenance"}],
        )
        historical.assert_called_once_with(2)

    def test_materializer_db_calls_use_sub_five_second_cancellation(self) -> None:
        with patch.object(module, "run_psql_json", return_value=[]) as execute:
            module.materializer_psql_json("SELECT '[]'::json::text")
        self.assertEqual(execute.call_args.kwargs["statement_timeout_ms"], 3500)
        self.assertEqual(execute.call_args.kwargs["timeout_seconds"], 4.0)

    def test_contracts_batch_prior_oi_and_upsert_in_one_write(self) -> None:
        batch = {
            "id": 9, "provider": "Zerodha", "exchange": "NFO", "underlying": "NIFTY",
            "expiry": "2026-08-18", "minute_ts": "2026-08-11T06:49:00+00:00",
        }
        contracts = [{
            "legacy_snapshot_id": index,
            "instrument_token": str(index),
            "trading_symbol": f"NIFTY-{index}",
            "strike": 24000 + index * 50,
            "option_type": "CE",
            "contract_multiplier": 75,
            "quote_source_timestamp": "2026-08-11T06:49:01+00:00",
            "received_at": "2026-08-11T06:49:02+00:00",
            "last_price": 100 - index,
            "bid_price": 99 - index,
            "ask_price": 101 - index,
            "volume": 1000 + index,
            "open_interest": 5000 + index,
            "source_payload_hash": f"hash-{index}",
            "source_payload": {"source": "test"},
        } for index in (1, 2)]
        with patch.object(module, "write_returning", return_value=[{"id": 1}, {"id": 2}]) as write:
            result = module.create_contracts(batch, contracts)
        self.assertEqual(len(result), 2)
        write.assert_called_once()
        sql = write.call_args.args[0]
        self.assertIn("LEFT JOIN LATERAL", sql)
        self.assertIn("previous_open_interest", sql)
        self.assertEqual(sql.count("NIFTY-"), 2)

    def test_heatmap_and_buildup_are_each_batch_upserts(self) -> None:
        batch = {
            "id": 10, "provider": "Zerodha", "exchange": "NFO", "underlying": "NIFTY",
            "expiry": "2026-08-18", "minute_ts": "2026-08-11T06:49:00+00:00",
        }
        contracts = [{
            "id": 101 + index, "strike": 24000 + index * 50, "option_type": "XX",
            "last_price": 100 + index, "open_interest": 5000 + index,
            "previous_open_interest": 4900 + index, "volume": 1000 + index,
        } for index in (1, 2)]
        prior_contracts = [{
            "id": 201 + index, "strike": 24000 + index * 50, "option_type": "XX",
            "last_price": 99 + index, "open_interest": 4900 + index,
            "volume": 900 + index,
        } for index in (1, 2)]
        with patch.object(
            module,
            "rows",
            side_effect=[[{"id": 8, "minute_ts": "2026-08-11T06:48:00+00:00"}], prior_contracts, []],
        ), patch.object(module, "write_returning", return_value=[{"id": 1}, {"id": 2}]) as write:
            result = module.persist_market_structure(batch, contracts)
        statements = [call.args[0] for call in write.call_args_list]
        self.assertEqual(sum("INSERT INTO trading.option_oi_heatmap_cells" in sql for sql in statements), 1)
        self.assertEqual(sum("INSERT INTO trading.option_buildup_classifications" in sql for sql in statements), 1)
        self.assertEqual(result["heatmap"], 2)
        self.assertEqual(result["buildup"], 2)

    @patch.object(module, "recent_valued_batches", return_value=[])
    @patch.object(module, "record_run")
    @patch.object(module, "pending_groups", return_value=[])
    def test_empty_source_is_blocked_not_reported_as_completed(self, pending, record, recent) -> None:
        result = module.run(20)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["rows_read"], 0)
        self.assertEqual(result["batches_created"], 0)
        self.assertIn("no unmaterialized or refreshable valued option snapshots", record.call_args.kwargs["error"])

    def test_postgres_timestamp_text_is_normalized(self) -> None:
        self.assertEqual(
            module.parse_timestamp("2026-08-08 09:39:20.54936+00:00").isoformat(),
            "2026-08-08T09:39:20.549360+00:00",
        )
        self.assertEqual(
            module.parse_timestamp("2026-08-10 15:17:00+00").isoformat(),
            "2026-08-10T15:17:00+00:00",
        )

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

    def test_analysis_clock_waits_for_complete_contract_batch(self) -> None:
        value = module.analysis_as_of(
            {"received_at": "2026-08-11T08:21:14.040732+00:00"},
            [
                {"received_at": "2026-08-11T08:21:14.879499+00:00"},
                {"received_at": "2026-08-11T08:21:14.500000+00:00"},
            ],
        )
        self.assertEqual(value.isoformat(), "2026-08-11T08:21:14.879499+00:00")

    def test_greek_conflict_refreshes_result_not_only_hash(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        analytics = source[source.index("def persist_analytics"):]
        conflict = analytics[
            analytics.index("ON CONFLICT (contract_snapshot_id"):
            analytics.index("by_strike_type =")
        ]
        self.assertIn("calculation_status=EXCLUDED.calculation_status", conflict)
        self.assertIn("implied_volatility=EXCLUDED.implied_volatility", conflict)
        self.assertIn("quality_flags=EXCLUDED.quality_flags", conflict)

    def test_gamma_flip_records_a_qualified_no_crossing_result(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"no_crossing_within_tested_grid"', source)
        self.assertIn('"crossing_found": metric_value is not None', source)

    def test_batch_repair_is_explicit_and_preserves_safety(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("def repair_batch_analytics", source)
        self.assertIn("--repair-batch-id", source)
        self.assertIn("AI_OS_OPTIONS_MAINTENANCE_REPAIR", source)
        self.assertIn('"broker_write_allowed": False', source)

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
        self.assertIn('replay_frames([event], [event["received_at"]])', source)
        self.assertNotIn('replay_frames(payload, [row["received_at"] for row in scope])', source)


if __name__ == "__main__":
    unittest.main()
