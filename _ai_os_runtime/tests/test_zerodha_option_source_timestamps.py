from pathlib import Path
import unittest


class ZerodhaOptionSourceTimestampContractTests(unittest.TestCase):
    def test_option_snapshots_use_broker_timestamp_and_retain_collection_time(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "scripts" / "sync_zerodha_market_data.py").read_text(encoding="utf-8")
        self.assertIn('source_timestamp = quote.get("timestamp") or spot_payload.get("timestamp")', source)
        self.assertIn("source_observed_at", source)
        self.assertIn('"collected_at": collected_at', source)
        self.assertNotIn("f\"{sql_literal(observed_at)}::timestamptz,'Zerodha'", source)


if __name__ == "__main__":
    unittest.main()
