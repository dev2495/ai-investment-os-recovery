from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_source_freshness import classify


class SourceFreshnessNullStalenessTests(unittest.TestCase):
    def test_quote_sources_use_quote_time_not_connector_check_time(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "scripts" / "check_source_freshness.py").read_text(encoding="utf-8")
        self.assertIn("THEN 'quote'", source)
        self.assertIn("now()-latest_quote.latest_quote_at", source)
        self.assertIn('return "missing_quote", "high"', source)
        self.assertNotIn("now() - GREATEST(\n                            coalesce(latest_quote", source)
        self.assertIn("END AS staleness_minutes", source)

    def test_fresh_quote_does_not_require_a_connector_check(self) -> None:
        self.assertEqual(classify({
            "freshness_basis": "quote", "latest_quote_at": "2026-08-24T10:00:00Z",
            "latest_check_at": None, "staleness_minutes": 2, "freshness_target_minutes": 15,
        }, None), ("fresh", "low"))

    def test_missing_quote_cannot_be_masked_by_a_fresh_connector_check(self) -> None:
        self.assertEqual(classify({
            "freshness_basis": "quote", "latest_quote_at": None,
            "latest_check_at": "2026-08-24T10:00:00Z", "latest_check_status": "ok",
            "staleness_minutes": None, "freshness_target_minutes": 15,
        }, None), ("missing_quote", "high"))


if __name__ == "__main__":
    unittest.main()
