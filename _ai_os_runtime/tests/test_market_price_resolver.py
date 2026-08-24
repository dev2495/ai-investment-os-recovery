import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from market_price_resolver import resolve_market_price
from sync_zerodha_market_data import zerodha_timestamp_utc


class MarketPriceResolverTests(unittest.TestCase):
    @staticmethod
    def zerodha_row(**overrides):
        row = {
            "provider": "Zerodha",
            "source_priority": 1,
            "approved_for_valuation": True,
            "broker_write_allowed": False,
            "instrument_token": 42,
            "mapping_status": "verified_zerodha_instrument",
            "timestamp_basis": "exchange_timestamp",
        }
        row.update(overrides)
        return row

    @staticmethod
    def entitled_secondary_row(**overrides):
        row = {
            "provider": "TradingView",
            "source_priority": 3,
            "approved_for_valuation": True,
            "broker_write_allowed": False,
            "provider_entitled": True,
            "provider_entitlement_key": "tradingview_scanner_quotes",
            "mapping_status": "exact_exchange_symbol",
            "timestamp_basis": "provider_exchange_time",
        }
        row.update(overrides)
        return row

    def test_exact_exchange_wins_and_live_quote_is_current(self):
        now = datetime(2026, 8, 24, 5, 0, tzinfo=timezone.utc)
        rows = [
            self.zerodha_row(id=1, symbol="TEST", exchange="BSE", price=999,
                              quote_ts="2026-08-24T04:59:00+00:00",
                              received_at="2026-08-24T05:00:00+00:00", instrument_token=41),
            self.zerodha_row(id=2, symbol="TEST", exchange="NSE", price=101,
                              quote_ts="2026-08-24T04:55:00+00:00",
                              received_at="2026-08-24T04:56:00+00:00"),
        ]
        result = resolve_market_price(rows, symbol="test", exchange="NSE", now=now)
        self.assertEqual(result["value"], 101)
        self.assertEqual(result["exchange"], "NSE")
        self.assertEqual(result["freshness_status"], "current")
        self.assertTrue(result["decision_usable"])

    def test_legacy_ist_as_utc_skew_is_rejected(self):
        now = datetime(2026, 8, 24, 5, 2, tzinfo=timezone.utc)
        result = resolve_market_price([self.zerodha_row(
            symbol="TEST", exchange="NSE", price=101,
            quote_ts="2026-08-24T10:30:00+00:00", received_at="2026-08-24T05:00:00+00:00",
        )], symbol="TEST", exchange="NSE", now=now)
        self.assertEqual(result["freshness_status"], "invalid_timestamp")
        self.assertFalse(result["decision_usable"])

    def test_last_session_closing_quote_is_current_on_weekend_and_holiday(self):
        friday_quote = [self.zerodha_row(
            symbol="TEST", exchange="NSE", price=101,
            quote_ts="2026-08-21T10:00:00+00:00", received_at="2026-08-21T10:01:00+00:00",
        )]
        weekend = resolve_market_price(
            friday_quote, symbol="TEST", exchange="NSE",
            now=datetime(2026, 8, 23, 6, 0, tzinfo=timezone.utc),
        )
        holiday = resolve_market_price(
            friday_quote, symbol="TEST", exchange="NSE",
            holidays=[{"exchange": "NSE", "holiday_date": "2026-08-24", "session_status": "closed"}],
            now=datetime(2026, 8, 24, 6, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(weekend["freshness_status"], "current")
        self.assertTrue(weekend["decision_usable"])
        self.assertEqual(holiday["freshness_status"], "current")
        self.assertTrue(holiday["decision_usable"])

    def test_live_session_age_ceiling_is_enforced(self):
        result = resolve_market_price([self.zerodha_row(
            symbol="TEST", exchange="NSE", price=101,
            quote_ts="2026-08-24T04:00:00+00:00", received_at="2026-08-24T04:01:00+00:00",
        )], symbol="TEST", exchange="NSE", now=datetime(2026, 8, 24, 5, 0, tzinfo=timezone.utc))
        self.assertEqual(result["freshness_status"], "stale")
        self.assertFalse(result["decision_usable"])

    def test_after_hours_requires_a_closing_session_observation(self):
        now = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
        morning = resolve_market_price([self.zerodha_row(
            symbol="TEST", exchange="NSE", price=98,
            quote_ts="2026-08-24T04:30:00+00:00", received_at="2026-08-24T04:30:02+00:00",
        )], symbol="TEST", exchange="NSE", now=now)
        closing = resolve_market_price([self.zerodha_row(
            symbol="TEST", exchange="NSE", price=101,
            quote_ts="2026-08-24T10:00:00+00:00", received_at="2026-08-24T10:00:02+00:00",
        )], symbol="TEST", exchange="NSE", now=now)
        self.assertEqual(morning["freshness_status"], "stale")
        self.assertFalse(morning["decision_usable"])
        self.assertEqual(closing["freshness_status"], "current")
        self.assertTrue(closing["decision_usable"])

    def test_current_zerodha_live_quote_wins_over_secondary(self):
        now = datetime(2026, 8, 24, 5, 0, tzinfo=timezone.utc)
        result = resolve_market_price([
            self.entitled_secondary_row(symbol="TEST", exchange="NSE", price=102,
                quote_ts="2026-08-24T04:59:00+00:00", received_at="2026-08-24T04:59:05+00:00"),
            self.zerodha_row(symbol="TEST", exchange="NSE", price=101,
                quote_ts="2026-08-24T04:58:00+00:00", received_at="2026-08-24T04:58:02+00:00"),
        ], symbol="TEST", exchange="NSE", now=now)
        self.assertEqual(result["provider"], "Zerodha")
        self.assertEqual(result["value"], 101)
        self.assertFalse(result["fallback_used"])
        self.assertFalse(result["broker_write_allowed"])

    def test_entitled_fallback_is_explicit_when_primary_is_stale(self):
        now = datetime(2026, 8, 24, 5, 0, tzinfo=timezone.utc)
        result = resolve_market_price([
            self.zerodha_row(symbol="TEST", exchange="NSE", price=100,
                quote_ts="2026-08-21T10:00:00+00:00", received_at="2026-08-21T10:00:02+00:00"),
            self.entitled_secondary_row(symbol="TEST", exchange="NSE", price=103,
                quote_ts="2026-08-24T04:59:00+00:00", received_at="2026-08-24T04:59:03+00:00"),
        ], symbol="TEST", exchange="NSE", now=now)
        self.assertEqual(result["value"], 103)
        self.assertTrue(result["fallback_used"])
        self.assertEqual(result["delay_status"], "fallback_current")
        self.assertEqual(result["primary_quote_status"], "stale")
        self.assertTrue(result["decision_usable"])

    def test_secondary_without_explicit_entitlement_fails_closed(self):
        result = resolve_market_price([self.entitled_secondary_row(
            symbol="TEST", exchange="NSE", price=101,
            quote_ts="2026-08-24T04:59:00+00:00", received_at="2026-08-24T04:59:02+00:00",
            provider_entitled=False, provider_entitlement_key="",
        )], symbol="TEST", exchange="NSE", now=datetime(2026, 8, 24, 5, 0, tzinfo=timezone.utc))
        self.assertFalse(result["decision_usable"])
        self.assertFalse(result["provider_entitled"])
        self.assertIn("not explicitly entitled", result["freshness_reason"])

    def test_unapproved_current_quote_is_not_decision_usable(self):
        result = resolve_market_price([self.zerodha_row(
            symbol="TEST", exchange="NSE", price=101,
            quote_ts="2026-08-24T04:59:00+00:00", received_at="2026-08-24T04:59:02+00:00",
            approved_for_valuation=False,
        )], symbol="TEST", exchange="NSE", now=datetime(2026, 8, 24, 5, 0, tzinfo=timezone.utc))
        self.assertFalse(result["decision_usable"])
        self.assertEqual(result["verification_status"], "unapproved_source")
        self.assertIn("not explicitly approved", result["freshness_reason"])

    def test_missing_explicit_write_lock_fails_closed(self):
        result = resolve_market_price([self.zerodha_row(
            symbol="TEST", exchange="NSE", price=101,
            quote_ts="2026-08-24T04:59:00+00:00", received_at="2026-08-24T04:59:02+00:00",
            broker_write_allowed=None,
        )], symbol="TEST", exchange="NSE", now=datetime(2026, 8, 24, 5, 0, tzinfo=timezone.utc))
        self.assertFalse(result["decision_usable"])
        self.assertIn("broker-write lock", result["freshness_reason"])

    def test_unqualified_timestamp_basis_fails_closed(self):
        result = resolve_market_price([self.zerodha_row(
            symbol="TEST", exchange="NSE", price=101,
            quote_ts="2026-08-24T04:59:00+00:00", received_at="2026-08-24T04:59:02+00:00",
            timestamp_basis="receipt_utc",
        )], symbol="TEST", exchange="NSE", now=datetime(2026, 8, 24, 5, 0, tzinfo=timezone.utc))
        self.assertEqual(result["freshness_status"], "invalid_timestamp")
        self.assertFalse(result["decision_usable"])

    def test_zerodha_naive_timestamp_is_normalized_from_ist(self):
        self.assertEqual(zerodha_timestamp_utc("2026-08-17 15:30:00"), "2026-08-17T10:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
