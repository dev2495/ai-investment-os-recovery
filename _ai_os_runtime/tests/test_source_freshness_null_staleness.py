from pathlib import Path
import unittest


class SourceFreshnessNullStalenessTests(unittest.TestCase):
    def test_missing_observations_do_not_subtract_infinity(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "scripts" / "check_source_freshness.py").read_text(encoding="utf-8")
        self.assertIn("THEN NULL", source)
        self.assertIn("AND latest_check.checked_at IS NULL", source)
        self.assertIn("END AS staleness_minutes", source)


if __name__ == "__main__":
    unittest.main()
