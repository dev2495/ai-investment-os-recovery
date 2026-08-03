from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_strategy_backtest as backtest


class StrategyBacktestContractTest(unittest.TestCase):
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
