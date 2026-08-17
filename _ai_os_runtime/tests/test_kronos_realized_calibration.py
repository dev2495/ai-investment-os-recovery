from __future__ import annotations

import sys
import unittest
from subprocess import CompletedProcess
from pathlib import Path
from unittest import mock


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME_ROOT / "scripts"))

import calibrate_kronos_forecast  # noqa: E402
import run_agent_worker_once  # noqa: E402


class KronosRealizedCalibrationTests(unittest.TestCase):
    def test_empirical_crps_matches_simple_distribution(self) -> None:
        self.assertAlmostEqual(
            calibrate_kronos_forecast.empirical_crps([0.0, 2.0], 1.0),
            0.5,
        )
        self.assertAlmostEqual(
            calibrate_kronos_forecast.empirical_crps([2.0, 2.0], 1.0),
            1.0,
        )

    def test_score_steps_uses_realized_bars_without_promoting_signal(self) -> None:
        predictions = [
            {"step_index": 1, "forecast_ts": "2026-01-01T00:05:00+00:00", "close": 99},
            {"step_index": 1, "forecast_ts": "2026-01-01T00:05:00+00:00", "close": 101},
            {"step_index": 2, "forecast_ts": "2026-01-01T00:10:00+00:00", "close": 102},
            {"step_index": 2, "forecast_ts": "2026-01-01T00:10:00+00:00", "close": 104},
        ]
        actuals = [
            {
                "step_index": 1,
                "actual_ts": "2026-01-01T00:05:00+00:00",
                "actual_close": 100,
                "source_system_id": 7,
            },
            {
                "step_index": 2,
                "actual_ts": "2026-01-01T00:10:00+00:00",
                "actual_close": 103,
                "source_system_id": 7,
            },
        ]
        result = calibrate_kronos_forecast.score_steps(
            predictions=predictions,
            actuals=actuals,
            last_close=100,
            expected_horizon=2,
        )
        self.assertTrue(result["complete_horizon"])
        self.assertEqual(result["realized_points"], 2)
        self.assertEqual(result["interval_coverage"], 1.0)
        self.assertEqual(result["directional_accuracy"], 1.0)
        self.assertEqual(result["timestamp_match_rate"], 1.0)

    def test_missing_actual_bar_remains_insufficient(self) -> None:
        result = calibrate_kronos_forecast.score_steps(
            predictions=[
                {"step_index": 1, "forecast_ts": "2026-01-01T00:05:00+00:00", "close": 101},
                {"step_index": 2, "forecast_ts": "2026-01-01T00:10:00+00:00", "close": 102},
            ],
            actuals=[
                {
                    "step_index": 1,
                    "actual_ts": "2026-01-01T00:05:00+00:00",
                    "actual_close": 100,
                    "source_system_id": 7,
                }
            ],
            last_close=100,
            expected_horizon=2,
        )
        self.assertFalse(result["complete_horizon"])
        self.assertEqual(result["realized_points"], 1)

    def test_api_mcp_and_ui_expose_governed_calibration(self) -> None:
        api = (RUNTIME_ROOT / "api" / "ai_os_api_server.py").read_text(encoding="utf-8")
        mcp = (RUNTIME_ROOT / "mcp_server" / "ai_os_mcp_server.py").read_text(encoding="utf-8")
        actions = (RUNTIME_ROOT / "ai-office-ui" / "src" / "data" / "actions.ts").read_text(encoding="utf-8")
        schema = (RUNTIME_ROOT / "ai-office-ui" / "src" / "data" / "schemas.ts").read_text(encoding="utf-8")
        studio = (RUNTIME_ROOT / "ai-office-ui" / "src" / "destinations" / "firm" / "GraphStudio.tsx").read_text(encoding="utf-8")
        migration = (RUNTIME_ROOT / "postgres" / "init" / "209_kronos_realized_calibration_v1.sql").read_text(encoding="utf-8")

        self.assertIn('"/api/kronos/forecasts/calibrate"', api)
        self.assertIn('"ai_os_calibrate_kronos_forecast"', mcp)
        self.assertIn('"/api/kronos/forecasts/calibrate"', actions)
        self.assertIn("kronos_scores: z.array(liveRow).default([])", schema)
        self.assertIn("Score realized bars", studio)
        self.assertIn("automatic_strategy_promotion_allowed", migration)
        self.assertIn("broker_order_allowed", migration)

    def test_graph_data_scientist_invokes_realized_calibration(self) -> None:
        context = {
            "agent_message": {
                "metadata": {
                    "graph_key": "kronos_forecast_research",
                    "graph_run_id": 12,
                }
            }
        }
        response = {
            "forecast_run_id": 44,
            "status": "needs_review",
            "metrics": {"realized_points": 5, "expected_horizon": 5},
            "broker_order_allowed": False,
        }
        with (
            mock.patch.object(
                run_agent_worker_once,
                "psql_one",
                return_value={"id": 44, "run_key": "kronos-real", "status": "completed"},
            ),
            mock.patch.object(
                run_agent_worker_once.subprocess,
                "run",
                return_value=CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout=__import__("json").dumps(response),
                    stderr="",
                ),
            ) as runner,
        ):
            result = run_agent_worker_once.run_kronos_calibration(
                {"task_id": 98, "owner_agent": "Data Scientist"},
                context,
            )
        self.assertEqual(result["forecast_run_id"], 44)
        self.assertEqual(context["kronos_calibration"]["status"], "needs_review")
        self.assertFalse(context["execution_envelope"]["broker_order_allowed"])
        self.assertIn("calibrate_kronos_forecast.py", str(runner.call_args.args[0]))


if __name__ == "__main__":
    unittest.main()
