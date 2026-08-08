from datetime import date
import math
from pathlib import Path
import unittest

from _ai_os_runtime.scripts.collect_option_valuation_sources import (
    choose_tbill,
    continuous_zero_rate,
    extract_dashboard_yields,
    parse_tbill_maturity,
)


class OptionValuationSourceCollectorTests(unittest.TestCase):
    def test_parses_and_selects_a_middle_maturity_tbill(self) -> None:
        rows = [
            {"trading_symbol": "NEAR", "name": "GOI TBILL 91D-20/08/26", "exchange": "NSE"},
            {"trading_symbol": "MID", "name": "GOI TBILL 91D-24/09/26", "exchange": "NSE"},
            {"trading_symbol": "FAR", "name": "GOI TBILL 91D-29/10/26", "exchange": "NSE"},
        ]
        self.assertEqual(parse_tbill_maturity(rows[1]["name"]), date(2026, 9, 24))
        self.assertEqual(choose_tbill(rows, date(2026, 8, 9))["trading_symbol"], "MID")

    def test_zero_rate_uses_continuous_discounting(self) -> None:
        actual = continuous_zero_rate(99.0, 60)
        self.assertAlmostEqual(actual, -math.log(0.99) / (60 / 365), places=12)
        with self.assertRaises(ValueError):
            continuous_zero_rate(0, 60)

    def test_extracts_published_dividend_yields(self) -> None:
        text = "Nifty 50 25,000 22.1 3.6 1.22\nNifty Bank 55,000 16.8 2.5 0.66\n"
        result = extract_dashboard_yields(text)
        self.assertAlmostEqual(result["NIFTY"], 0.0122)
        self.assertAlmostEqual(result["BANKNIFTY"], 0.0066)

    def test_daemon_refreshes_candidates_without_activating_policy(self) -> None:
        daemon = (Path(__file__).resolve().parents[1] / "scripts" / "run_agent_message_daemon.py").read_text(encoding="utf-8")
        self.assertIn("run_option_valuation_source_refresh", daemon)
        self.assertIn("AI_OS_OPTION_VALUATION_SOURCE_INTERVAL_SECONDS", daemon)
        self.assertIn("payload.get(\"activated_policy\") is not False", daemon)


if __name__ == "__main__":
    unittest.main()
