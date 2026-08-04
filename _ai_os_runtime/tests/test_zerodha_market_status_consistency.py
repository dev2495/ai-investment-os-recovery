from __future__ import annotations

import unittest
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
