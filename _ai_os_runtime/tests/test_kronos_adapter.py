
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = RUNTIME_ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import kronos_inference_worker
import run_agent_worker_once
import run_kronos_forecast


class KronosAdapterTest(unittest.TestCase):
    def test_pinned_revisions_and_safetensor_hashes_are_immutable(self) -> None:
        self.assertEqual(
            kronos_inference_worker.KRONOS_CODE_REVISION,
            "67b630e67f6a18c9e9be918d9b4337c960db1e9a",
        )
        self.assertEqual(
            kronos_inference_worker.KRONOS_MODEL_REVISION,
            "f4e68697d9d5aed55cef5c96aabc3376bcad9f81",
        )
        self.assertEqual(
            kronos_inference_worker.KRONOS_TOKENIZER_REVISION,
            "26966d0035065a0cae0ebad7af8ece35bc1fb51c",
        )
        self.assertEqual(len(kronos_inference_worker.KRONOS_MODEL_SHA256), 64)
        self.assertEqual(len(kronos_inference_worker.KRONOS_TOKENIZER_SHA256), 64)

    def test_graph_studio_uses_model_revision_not_source_revision(self) -> None:
        source = (
            RUNTIME_ROOT
            / "ai-office-ui"
            / "src"
            / "destinations"
            / "firm"
            / "GraphStudio.tsx"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'model_revision: "f4e68697d9d5aed55cef5c96aabc3376bcad9f81"',
            source,
        )
        self.assertNotIn(
            'model_revision: "67b630e67f6a18c9e9be918d9b4337c960db1e9a"',
            source,
        )
        self.assertIn('horizon: "5"', source)
        self.assertIn('path_count: "20"', source)
        self.assertIn('className="graph-studio__run-panel"', source)
        styles = (
            RUNTIME_ROOT
            / "ai-office-ui"
            / "src"
            / "destinations"
            / "firm"
            / "GraphStudio.css.ts"
        ).read_text(encoding="utf-8")
        self.assertIn(
            ".graph-studio__run-panel > .aios-panel__header",
            styles,
        )

    def test_daily_forecast_timestamps_skip_weekend_and_exchange_holiday(self) -> None:
        timestamps = run_kronos_forecast.future_timestamps(
            "2026-01-23T10:00:00+00:00",
            "1d",
            "NSE",
            2,
            ["2026-01-26"],
        )
        local_dates = [
            datetime.fromisoformat(value).astimezone(run_kronos_forecast.IST).date().isoformat()
            for value in timestamps
        ]
        self.assertEqual(local_dates, ["2026-01-27", "2026-01-28"])

    def test_intraday_timestamps_restart_at_market_open(self) -> None:
        timestamps = run_kronos_forecast.future_timestamps(
            "2026-01-23T10:00:00+00:00",
            "5m",
            "NSE",
            1,
            ["2026-01-26"],
        )
        local = datetime.fromisoformat(timestamps[0]).astimezone(run_kronos_forecast.IST)
        self.assertEqual(local.date().isoformat(), "2026-01-27")
        self.assertEqual(local.strftime("%H:%M"), "09:15")

    def test_create_run_uses_top_level_data_modifying_cte(self) -> None:
        returned = json.dumps(
            {
                "id": 12,
                "run_key": "kronos-test",
                "source_hash": "abc",
                "source_start_ts": "2026-07-17T18:30:00+00:00",
                "source_end_ts": "2026-07-20T18:30:00+00:00",
            }
        )
        with mock.patch.object(
            run_kronos_forecast,
            "psql_text",
            return_value=returned,
        ) as query:
            result = run_kronos_forecast.create_run(
                task_id=None,
                graph_run_id=None,
                graph_node_run_id=None,
                candidate={"symbol_id": 1},
                rows=[
                    {"ts": "2026-07-17T18:30:00+00:00"},
                    {"ts": "2026-07-20T18:30:00+00:00"},
                ],
                symbol="TATASTEEL",
                exchange="NSE",
                timeframe="1d",
                as_of=datetime(2026, 7, 20, 18, 30, tzinfo=timezone.utc),
                lookback=2,
                horizon=2,
                path_count=20,
                model_revision=kronos_inference_worker.KRONOS_MODEL_REVISION,
                seed_base=20260729,
                temperature=1.0,
                top_p=0.9,
            )
        sql = query.call_args.args[0]
        self.assertIn("WITH inserted AS (", sql)
        self.assertIn("INSERT INTO strategy.kronos_forecast_runs", sql)
        self.assertIn("SELECT row_to_json(inserted)::text FROM inserted", sql)
        self.assertEqual(result["id"], 12)

    def test_distribution_contract_requires_real_twenty_path_output(self) -> None:
        paths = []
        for path_index in range(1, 21):
            points = []
            for step_index in range(1, 3):
                close = 100.0 + path_index / 10 + step_index
                points.append(
                    {
                        "step_index": step_index,
                        "forecast_ts": f"2026-01-{27 + step_index:02d}T10:00:00+00:00",
                        "open": close - 0.2,
                        "high": close + 0.4,
                        "low": close - 0.5,
                        "close": close,
                        "volume": 1000.0 + path_index,
                        "amount": 100000.0,
                        "ohlc_valid": True,
                        "volume_valid": True,
                    }
                )
            paths.append({"path_index": path_index, "points": points})
        features, validation, flattened = run_kronos_forecast.distribution_features(
            {"paths": paths, "path_count": 20, "horizon": 2},
            100.0,
        )
        self.assertEqual(len(flattened), 40)
        self.assertTrue(validation["path_contract_satisfied"])
        self.assertEqual(validation["ohlc_validity"], 1.0)
        self.assertFalse(features["direct_signal"])
        self.assertFalse(features["broker_order_allowed"])
        self.assertEqual(features["feature_kind"], "forecast_distribution")

    def test_incomplete_path_set_is_rejected_instead_of_fabricated(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "path count"):
            run_kronos_forecast.distribution_features(
                {"paths": [], "path_count": 20, "horizon": 2},
                100.0,
            )

    def test_graph_managed_tasks_are_prioritized_ahead_of_stale_queue(self) -> None:
        with mock.patch.object(
            run_agent_worker_once,
            "psql_json",
            return_value=[],
        ) as query:
            run_agent_worker_once.get_queue(5, include_completed=False)
        sql = query.call_args.args[0]
        graph_priority = sql.index("message.generated_task_id=queue.task_id")
        task_state_priority = sql.index("CASE queue.task_status")
        ordinary_priority = sql.index("CASE queue.priority")
        self.assertLess(graph_priority, task_state_priority)
        self.assertLess(task_state_priority, ordinary_priority)

    def test_graph_managed_worker_completes_for_control_plane_review(self) -> None:
        job = {
            "task_id": 44,
            "widget_id": None,
            "inbox_item_id": 7,
            "owner_agent": "Feature Engineer",
            "suggested_skill_key": "kronos_forecast_feature_generation",
        }
        context = {
            "agent_message": {
                "metadata": {"graph_run_id": 3, "graph_node_run_id": 9}
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            note = vault / "worker.md"
            note.write_text("evidence", encoding="utf-8")
            response = json.dumps(
                {
                    "worker_run": {"id": 1},
                    "task": {"id": 44, "status": "completed"},
                    "widget": None,
                    "inbox": {"id": 7, "status": "completed"},
                }
            )
            with (
                mock.patch.object(run_agent_worker_once, "VAULT_ROOT", vault),
                mock.patch.object(
                    run_agent_worker_once,
                    "psql_text",
                    return_value=response,
                ) as query,
            ):
                result = run_agent_worker_once.complete_job(
                    job,
                    {"agent_name": "Feature Engineer"},
                    {"skill_key": "kronos_forecast_feature_generation"},
                    context,
                    "completed",
                    note,
                )
        sql = query.call_args.args[0]
        self.assertIn("SET status = 'completed'", sql)
        self.assertEqual(result["task"]["status"], "completed")

    def test_graph_managed_failure_is_visible_to_graph_runner(self) -> None:
        job = {
            "task_id": 45,
            "widget_id": None,
            "inbox_item_id": 8,
            "owner_agent": "Feature Engineer",
            "suggested_skill_key": "kronos_forecast_feature_generation",
        }
        with mock.patch.object(
            run_agent_worker_once,
            "psql_one",
            side_effect=[
                {"metadata": {"graph_run_id": 3, "graph_node_run_id": 9}},
                {"id": 2, "task_status": "failed"},
            ],
        ) as query:
            result = run_agent_worker_once.record_worker_failure(
                job,
                {"agent_name": "Feature Engineer"},
                {"skill_key": "kronos_forecast_feature_generation"},
                RuntimeError("model unavailable"),
            )
        sql = query.call_args_list[1].args[0]
        self.assertIn("SET status='failed'", sql)
        self.assertIn("SET status='blocked'", sql)
        self.assertEqual(result["task_status"], "failed")

    def test_migration_prohibits_direct_signal_and_broker_orders(self) -> None:
        migration = (
            RUNTIME_ROOT / "postgres" / "init" / "172_kronos_research_adapter_v1.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("CHECK (NOT direct_signal)", migration)
        self.assertIn("CHECK (NOT broker_order_allowed)", migration)
        self.assertIn("'synthetic_fallback_allowed':false".replace("'", '"'), migration)
        self.assertIn("strategy.v_kronos_research_runs", migration)


if __name__ == "__main__":
    unittest.main()
