from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = RUNTIME_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_paper_monitors as paper


class PaperMonitorWorkerTests(unittest.TestCase):
    def test_momentum_transition_is_deterministic(self) -> None:
        bars = [
            paper.Bar(ts=f"2026-01-{index + 1:02d}T09:15:00+00:00", symbol="AAA", close=100.0)
            for index in range(19)
        ]
        bars.append(paper.Bar(ts="2026-01-20T09:15:00+00:00", symbol="AAA", close=110.0))

        result = paper.evaluate_symbol(bars, "momentum")

        self.assertEqual(result["status"], "evaluated")
        self.assertEqual(result["action"], "buy")
        self.assertEqual(result["previous_position"], 0)
        self.assertEqual(result["desired_position"], 1)

    def test_thin_series_is_not_evaluated(self) -> None:
        bars = [paper.Bar(ts="2026-01-01T09:15:00+00:00", symbol="AAA", close=100.0)]
        self.assertEqual(paper.evaluate_symbol(bars, "momentum"), {"status": "insufficient_bars", "bars": 1})

    def test_monitor_refuses_any_live_execution_flag(self) -> None:
        monitor = {"paper_monitor_session_id": 7, "live_execution_allowed": True}
        with self.assertRaisesRegex(RuntimeError, "not paper-only"):
            paper.evaluate_monitor(monitor, 120)

    def test_persistence_attributes_signal_position_trade_and_monitor(self) -> None:
        monitor = {
            "paper_monitor_session_id": 7,
            "strategy_id": 11,
            "instance_id": 13,
            "candidate_key": "momentum-alpha",
            "hypothesis": "Price persistence",
        }
        evaluation = {
            "action": "buy",
            "bar_ts": "2026-01-20T09:15:00+00:00",
            "price": 110.0,
            "previous_position": 0,
            "desired_position": 1,
        }
        responses = [
            [{"open_positions": 0, "latest_evaluated_bar_ts": None}],
            [{"paper_monitor_session_id": 7, "signal_id": 17, "position_opened_id": 19}],
            [{"metrics": {"positions_open": 1, "live_execution_allowed": False}}],
        ]
        with mock.patch.object(paper, "run_psql_json", side_effect=responses) as query:
            result = paper.persist_evaluation(monitor, "NSE:AAA", "1d", "momentum", evaluation)

        transaction_sql = query.call_args_list[1].args[0]
        self.assertIn("INSERT INTO trading.signals", transaction_sql)
        self.assertIn("INSERT INTO trading.paper_positions", transaction_sql)
        self.assertIn("INSERT INTO trading.trade_activity_ledger", transaction_sql)
        self.assertIn("INSERT INTO strategy.paper_monitor_events", transaction_sql)
        self.assertIn("'paper_monitor'", transaction_sql)
        self.assertIn("'paper_observed'", transaction_sql)
        self.assertIn("'live_execution_allowed', false", transaction_sql)
        self.assertEqual(result["performance"]["positions_open"], 1)

    def test_daemon_schedules_bounded_paper_monitor_worker(self) -> None:
        daemon = (SCRIPTS / "run_agent_message_daemon.py").read_text(encoding="utf-8")
        service = (RUNTIME_ROOT / "launchd" / "aios-agent-daemon-service.sh").read_text(encoding="utf-8")
        env_example = (RUNTIME_ROOT / "deploy" / "imac-backend" / "imac.env.example").read_text(encoding="utf-8")
        self.assertIn("def run_paper_monitor_evaluation", daemon)
        self.assertIn('"paper_monitor_evaluation": paper_monitor_enabled', daemon)
        self.assertIn("AI_OS_ENABLE_PAPER_MONITOR_EVALUATION", daemon)
        self.assertIn("--paper-monitor-limit", service)
        self.assertIn("AI_OS_ENABLE_PAPER_MONITOR_EVALUATION=1", env_example)

    def test_schema_keeps_paper_execution_separate_and_locked(self) -> None:
        migration = (RUNTIME_ROOT / "postgres" / "init" / "184_paper_monitor_execution_ledger_v1.sql").read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS trading.paper_positions", migration)
        self.assertIn("paper_monitor_session_id", migration)
        self.assertIn("live_execution_allowed\":false", migration)
        self.assertIn("broker_order_allowed\":false", migration)
        self.assertNotIn("portfolio.orders", migration)


if __name__ == "__main__":
    unittest.main()
