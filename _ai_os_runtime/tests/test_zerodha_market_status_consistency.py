from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest import mock

from _ai_os_runtime.api import ai_os_api_server


class ZerodhaMarketStatusConsistencyTest(unittest.TestCase):
    def test_stale_token_cannot_be_reported_as_available(self) -> None:
        auth = {
            "status": "needs_credentials_or_daily_login",
            "daily_access_token_available": False,
            "stale_access_token_present": True,
            "manual_daily_login_required": True,
            "login_url": "https://kite.zerodha.com/connect/login",
        }
        with (
            mock.patch.object(
                ai_os_api_server,
                "_run_zerodha_market_adapter",
                return_value={"status": "configured", "daily_access_token_available": True},
            ),
            mock.patch.object(ai_os_api_server, "zerodha_auth_status", return_value=auth),
            mock.patch.object(
                ai_os_api_server,
                "run_psql_json",
                side_effect=[
                    [{"active_instruments": 0, "latest_option_at": None}],
                    [{"health_status": "not_started", "live_count": 0}],
                ],
            ),
        ):
            result = ai_os_api_server.zerodha_market_status()

        self.assertFalse(result["daily_access_token_available"])
        self.assertEqual(result["status"], "needs_credentials_or_daily_login")
        self.assertEqual(result["stream"]["status"], "paused_for_daily_login")
        self.assertEqual(result["stream"]["health_status"], "login_required")
        self.assertFalse(result["broker_write_allowed"])
        self.assertTrue(result["auth"]["stale_access_token_present"])

    def test_company_health_is_exact_exchange_subscription_and_freshness_aware(self) -> None:
        captured = []
        candidates = [
            {
                "id": 1, "provider": "Zerodha", "source_key": "zerodha_websocket",
                "provider_symbol": "BSE:SBCL", "symbol": "SBCL", "exchange": "BSE",
                "currency": "INR", "price": 999, "quote_ts": "2026-08-24T04:59:00+00:00",
                "received_at": "2026-08-24T04:59:02+00:00", "source_priority": 1,
                "approved_for_valuation": True, "provider_entitled": True,
                "provider_entitlement_key": "zerodha_canonical", "instrument_token": 8001,
                "mapping_status": "verified_zerodha_instrument", "timestamp_basis": "exchange_timestamp",
                "broker_write_allowed": False,
            },
            {
                "id": 2, "provider": "Zerodha", "source_key": "zerodha_websocket",
                "provider_symbol": "NSE:SBCL", "symbol": "SBCL", "exchange": "NSE",
                "currency": "INR", "price": 512.25, "quote_ts": "2026-08-24T04:58:00+00:00",
                "received_at": "2026-08-24T04:58:02+00:00", "source_priority": 1,
                "approved_for_valuation": True, "provider_entitled": True,
                "provider_entitlement_key": "zerodha_canonical", "instrument_token": 9001,
                "mapping_status": "verified_zerodha_instrument", "timestamp_basis": "exchange_timestamp",
                "broker_write_allowed": False,
            },
        ]

        def fake_rows(sql):
            captured.append(sql)
            if "WITH live_quotes AS" in sql:
                return candidates
            if "FROM market.exchange_holidays" in sql:
                return []
            if "WITH mapped AS" in sql:
                return [{"instrument_token": 9001, "followed": True, "positioned": False, "live_quote_observed": True}]
            self.fail(f"unexpected query: {sql[:120]}")

        with mock.patch.object(ai_os_api_server, "run_psql_json", side_effect=fake_rows):
            result = ai_os_api_server.zerodha_company_market_health(
                "sbcl", "nse", now=datetime(2026, 8, 24, 5, 0, tzinfo=timezone.utc)
            )

        self.assertEqual(result["mapping_status"], "verified_zerodha_instrument")
        self.assertEqual(result["subscription_status"], "observed_live")
        self.assertTrue(result["decision_usable"])
        self.assertEqual(result["quote"]["value"], 512.25)
        self.assertEqual(result["quote"]["exchange"], "NSE")
        self.assertFalse(result["broker_write_allowed"])
        self.assertTrue(any("upper(live.exchange)=" in sql for sql in captured))
        self.assertTrue(any("upper(exchange)=" in sql and "upper(trading_symbol)=" in sql for sql in captured))

    def test_current_token_preserves_market_and_stream_status(self) -> None:
        auth = {
            "status": "configured",
            "daily_access_token_available": True,
            "profile_validated": True,
            "account_match": True,
        }
        with (
            mock.patch.object(
                ai_os_api_server,
                "_run_zerodha_market_adapter",
                return_value={"status": "configured", "daily_access_token_available": True},
            ),
            mock.patch.object(ai_os_api_server, "zerodha_auth_status", return_value=auth),
            mock.patch.object(
                ai_os_api_server,
                "run_psql_json",
                side_effect=[
                    [{"active_instruments": 10, "latest_option_at": "2026-08-04T10:00:00Z"}],
                    [{"health_status": "healthy", "live_count": 10}],
                ],
            ),
        ):
            result = ai_os_api_server.zerodha_market_status()

        self.assertTrue(result["daily_access_token_available"])
        self.assertEqual(result["status"], "configured")
        self.assertEqual(result["stream"]["health_status"], "healthy")
        self.assertEqual(result["warehouse"]["active_instruments"], 10)


if __name__ == "__main__":
    unittest.main()
