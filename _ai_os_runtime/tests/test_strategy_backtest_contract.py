from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_strategy_backtest as backtest
from strategy_rule_engine import compile_rule_set, positions_for_rule_set


class StrategyBacktestContractTest(unittest.TestCase):
    @staticmethod
    def bars(closes: list[float]) -> list[backtest.Bar]:
        return [
            backtest.Bar(
                ts=f"2026-01-{index + 1:02d}T09:15:00+00:00",
                symbol="AAA",
                open=close,
                high=close + 1,
                low=close - 1,
                close=close,
                volume=1000 + index,
            )
            for index, close in enumerate(closes)
        ]

    def test_compiled_rules_drive_positions_instead_of_hidden_template(self) -> None:
        bars = self.bars([10, 10, 10, 12, 13, 11, 9, 12])
        fast = compile_rule_set("close > sma(close, 3)", "close < sma(close, 3)")
        impossible = compile_rule_set("close > sma(close, 3) * 10", "holding_bars >= 1")
        fast_positions = positions_for_rule_set(bars, fast)
        impossible_positions = positions_for_rule_set(bars, impossible)
        self.assertNotEqual(fast_positions, impossible_positions)
        self.assertGreater(sum(fast_positions), 0)
        self.assertEqual(sum(impossible_positions), 0)
        self.assertNotEqual(fast.rule_hash, impossible.rule_hash)

    def test_compiler_rejects_arbitrary_python(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported"):
            compile_rule_set("__import__(1)", "close < sma(close, 3)")

    def test_fetch_bars_applies_requested_date_window(self) -> None:
        with mock.patch.object(backtest, "run_psql_json", return_value=[]) as query:
            backtest.fetch_bars(["AAA"], "1d", 1, "2025-01-01", "2025-12-31")
        sql = query.call_args.args[0]
        self.assertIn("o.ts >= '2025-01-01'::date", sql)
        self.assertIn("o.ts < ('2025-12-31'::date + interval '1 day')", sql)

    def test_equity_curve_uses_real_timestamp_aligned_returns(self) -> None:
        bars = []
        for symbol, multiplier in (("AAA", 1.0), ("BBB", 1.5)):
            for index in range(30):
                bars.append(backtest.Bar(
                    ts=f"2026-01-{index + 1:02d}T09:15:00+00:00",
                    symbol=symbol,
                    close=(100.0 + index) * multiplier,
                ))
        candidate = {
            "id": 1,
            "candidate_key": "truth-contract",
            "name": "Timestamp-aligned momentum",
            "activation_gate": "paper_first",
        }

        with mock.patch.object(backtest, "fetch_bars", return_value=bars):
            result = backtest.run_backtest(
                candidate,
                ["AAA", "BBB"],
                "1d",
                "momentum",
                cost_bps=0.0,
                slippage_bps=0.0,
                max_symbols=2,
            )

        curve = result["diagnostics"]["equity_curve"]
        self.assertTrue(curve)
        self.assertEqual(len(curve), 29)
        self.assertEqual(curve[-1]["equity"] - 1.0, result["metrics"]["total_return"])
        self.assertEqual(
            result["diagnostics"]["equity_curve_method"],
            "equal_weight_mean_of_available_symbol_returns_by_timestamp",
        )
        self.assertEqual(result["diagnostics"]["equity_curve_source"], "trading.ohlcv")
        self.assertEqual(result["data_start"], "2026-01-01")
        self.assertEqual(result["data_end"], "2026-01-30")

    def test_psql_retries_transient_connection_timeout(self) -> None:
        timeout = mock.Mock(returncode=2, stderr="psql: connection timeout expired", stdout="")
        success = mock.Mock(returncode=0, stderr="", stdout="[]\n")
        with (
            mock.patch.dict(backtest.os.environ, {"AI_OS_PSQL_BIN": "/usr/bin/true", "AI_OS_POSTGRES_PASSWORD": "test"}),
            mock.patch.object(backtest.subprocess, "run", side_effect=[timeout, success]) as run,
            mock.patch.object(backtest.time, "sleep") as sleep,
        ):
            self.assertEqual(backtest.run_psql_json("SELECT 1"), [])
        self.assertEqual(run.call_count, 2)
        sleep.assert_called_once_with(0.5)

    def test_background_workload_can_bypass_host_port_forwarder(self) -> None:
        success = mock.Mock(returncode=0, stderr="", stdout="[]\n")
        with (
            mock.patch.dict(backtest.os.environ, {"AI_OS_WORKLOAD_PSQL_MODE": "docker", "AI_OS_PSQL_BIN": "/usr/bin/true", "AI_OS_POSTGRES_PASSWORD": "test"}),
            mock.patch.object(backtest.subprocess, "run", return_value=success) as run,
        ):
            self.assertEqual(backtest.run_psql_json("SELECT 1"), [])
        command = run.call_args.args[0]
        self.assertEqual(command[:3], ["docker", "exec", "-i"])
        self.assertEqual(run.call_args.kwargs["input"], "SELECT 1")

    def test_psql_does_not_retry_sql_errors(self) -> None:
        failure = mock.Mock(returncode=2, stderr="ERROR: column does not exist", stdout="")
        with (
            mock.patch.dict(backtest.os.environ, {"AI_OS_PSQL_BIN": "/usr/bin/true", "AI_OS_POSTGRES_PASSWORD": "test"}),
            mock.patch.object(backtest.subprocess, "run", return_value=failure) as run,
            mock.patch.object(backtest.time, "sleep") as sleep,
        ):
            with self.assertRaisesRegex(RuntimeError, "column does not exist"):
                backtest.run_psql_json("SELECT missing")
        run.assert_called_once()
        sleep.assert_not_called()

    def test_frontend_does_not_synthesize_backtest_curves(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "ai-office-ui/src/destinations/quant/QuantStrategy.tsx"
        ).read_text(encoding="utf-8")
        self.assertIn("No persisted equity curve", source)
        self.assertNotIn("Synthesize an equity curve", source)
        self.assertNotIn("Math.sin(i * 0.7)", source)


if __name__ == "__main__":
    unittest.main()
