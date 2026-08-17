import importlib.util
import sys
import unittest
from decimal import Decimal
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "promote_legacy_financial_history.py"
sys.path.insert(0, str(MODULE_PATH.parent))
spec = importlib.util.spec_from_file_location("promote_legacy_financial_history", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class LegacyFinancialValidationTests(unittest.TestCase):
    def test_inr_million_converts_to_ten_lakh(self):
        self.assertEqual(module.statement_unit("INR million", Decimal("12.5")), ("lakh", Decimal("125.0")))

    def test_direct_reported_value(self):
        self.assertTrue(module.line_matches(Decimal("131354"), "Profit attributable 131,354 110,452"))

    def test_parenthesized_negative(self):
        self.assertTrue(module.line_matches(Decimal("-62750"), "Payment of dividend (62,750) (5,218)"))

    def test_disclosed_component_sum(self):
        self.assertTrue(module.line_matches(Decimal("182025"), "Trade receivables 11 117,745 115,477 | Unbilled receivables 64,280 58,345"))

    def test_rejects_unmatched_value(self):
        self.assertFalse(module.line_matches(Decimal("999"), "Revenue 1,234 1,100"))


if __name__ == "__main__":
    unittest.main()
