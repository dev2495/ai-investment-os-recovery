from __future__ import annotations

import pathlib
import unittest
import urllib.parse
from unittest import mock

from _ai_os_runtime.api import ai_os_api_server


RUNTIME_ROOT = pathlib.Path(__file__).resolve().parents[1]


class ZerodhaAuthSecurityTests(unittest.TestCase):
    def test_begin_auth_issues_short_lived_redirect_state(self) -> None:
        with (
            mock.patch.object(
                ai_os_api_server,
                "zerodha_auth_status",
                return_value={"login_url": "https://kite.zerodha.com/connect/login?v=3&api_key=public"},
            ),
            mock.patch.object(
                ai_os_api_server,
                "run_psql_json_statement",
                return_value=[{"id": 9, "expires_at": "2026-08-03T14:10:00+00:00"}],
            ) as database,
        ):
            result = ai_os_api_server.begin_zerodha_auth({"actor": "Devarsh"})

        login_query = urllib.parse.parse_qs(urllib.parse.urlparse(result["login_url"]).query)
        redirect_params = urllib.parse.parse_qs(login_query["redirect_params"][0])
        self.assertTrue(redirect_params["state"][0])
        self.assertNotIn(redirect_params["state"][0], database.call_args.args[0])
        self.assertTrue(result["profile_validation_required"])
        self.assertFalse(result["broker_write_allowed"])

    def test_callback_state_is_single_use_and_fail_closed(self) -> None:
        with mock.patch.object(ai_os_api_server, "run_psql_json_statement", return_value=[]):
            with self.assertRaises(PermissionError):
                ai_os_api_server.consume_zerodha_auth_challenge("expired-or-used", "success")

    def test_callback_consumes_state_before_profile_bound_exchange(self) -> None:
        with (
            mock.patch.object(
                ai_os_api_server,
                "consume_zerodha_auth_challenge",
                return_value={"id": 17, "requested_by": "Devarsh"},
            ) as consume,
            mock.patch.object(
                ai_os_api_server,
                "exchange_zerodha_request_token",
                return_value={
                    "status": "authenticated",
                    "access_token_stored": True,
                    "access_token_expires": "2026-08-04T06:00:00+05:30",
                    "profile_validated": True,
                    "account_match": True,
                },
            ) as exchange,
            mock.patch.object(
                ai_os_api_server,
                "start_zerodha_post_login_sync",
                return_value={"status": "started", "jobs": {}, "broker_write_allowed": False},
            ) as refresh,
        ):
            result = ai_os_api_server.exchange_zerodha_callback({
                "status": ["success"],
                "state": ["one-time-state"],
                "request_token": ["one-time-request-token"],
            })

        consume.assert_called_once_with("one-time-state", "success")
        exchange.assert_called_once()
        refresh.assert_called_once()
        self.assertTrue(result["profile_validated"])
        self.assertTrue(result["account_match"])
        self.assertEqual(result["challenge_id"], 17)
        self.assertEqual(result["post_login_sync"]["status"], "started")
        self.assertFalse(result["broker_write_allowed"])

    def test_schema_and_ui_use_the_challenge_flow(self) -> None:
        migration = (RUNTIME_ROOT / "postgres" / "init" / "180_zerodha_auth_challenges_v1.sql").read_text(encoding="utf-8")
        frontend = (RUNTIME_ROOT / "ai-office-ui" / "src" / "app" / "GlobalTopbar.tsx").read_text(encoding="utf-8")
        self.assertIn("consumed_at IS NULL", migration)
        self.assertIn("expires_at", migration)
        self.assertIn("useBeginZerodhaAuth", frontend)
        self.assertNotIn("request_token", frontend)

    def test_pasted_callback_url_is_validated_exchanged_and_not_audited_raw(self) -> None:
        with (
            mock.patch.object(
                ai_os_api_server,
                "exchange_zerodha_request_token",
                return_value={"status": "authenticated", "account_match": True, "broker_write_allowed": False},
            ) as exchange,
            mock.patch.object(
                ai_os_api_server,
                "start_zerodha_post_login_sync",
                return_value={"status": "started", "jobs": {}, "broker_write_allowed": False},
            ) as refresh,
            mock.patch.object(ai_os_api_server, "audit_api_write") as audit,
        ):
            result = ai_os_api_server.exchange_zerodha_callback_url({
                "callback_url": "https://kite.zerodha.com/?action=login&status=success&request_token=one-time-secret",
                "actor": "Devarsh",
            })

        self.assertEqual(result["status"], "authenticated")
        self.assertEqual(result["post_login_sync"]["status"], "started")
        exchange.assert_called_once_with({"request_token": "one-time-secret", "actor": "Devarsh"})
        refresh.assert_called_once()
        self.assertNotIn("one-time-secret", repr(audit.call_args))

    def test_pasted_callback_rejects_untrusted_host(self) -> None:
        with self.assertRaises(ValueError):
            ai_os_api_server.exchange_zerodha_callback_url({
                "callback_url": "https://example.test/?action=login&status=success&request_token=secret",
            })

    def test_post_login_sync_reports_spawn_failure_without_failing_login(self) -> None:
        with mock.patch.object(
            ai_os_api_server.subprocess,
            "Popen",
            side_effect=[OSError("process limit"), mock.Mock(pid=42)],
        ):
            result = ai_os_api_server.start_zerodha_post_login_sync()

        self.assertEqual(result["status"], "started")
        self.assertEqual(result["jobs"]["account"]["status"], "start_failed")
        self.assertEqual(result["jobs"]["market"]["status"], "started")
        self.assertFalse(result["broker_write_allowed"])


if __name__ == "__main__":
    unittest.main()
