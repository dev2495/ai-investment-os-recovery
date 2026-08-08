from __future__ import annotations

import unittest
import tempfile
from datetime import datetime
from pathlib import Path
from unittest import mock

from _ai_os_runtime.scripts import sync_zerodha_read_only as zerodha


class ZerodhaTokenExpiryTest(unittest.TestCase):
    def test_next_expiry_before_six_is_same_day(self) -> None:
        now = datetime(2026, 8, 1, 5, 30, tzinfo=zerodha.INDIA_TZ)
        self.assertEqual(
            zerodha.next_token_expiry(now),
            datetime(2026, 8, 1, 6, 0, tzinfo=zerodha.INDIA_TZ),
        )

    def test_next_expiry_after_six_is_following_day(self) -> None:
        now = datetime(2026, 8, 1, 7, 0, tzinfo=zerodha.INDIA_TZ)
        self.assertEqual(
            zerodha.next_token_expiry(now),
            datetime(2026, 8, 2, 6, 0, tzinfo=zerodha.INDIA_TZ),
        )

    def test_token_without_expiry_metadata_is_not_current(self) -> None:
        now = datetime(2026, 8, 1, 9, 0, tzinfo=zerodha.INDIA_TZ)
        self.assertFalse(zerodha.token_is_current("old-token", None, now))
        self.assertIsNone(zerodha.parse_token_expiry("2026-08-02T06:00:00"))

    def test_current_token_requires_future_expiry(self) -> None:
        now = datetime(2026, 8, 1, 9, 0, tzinfo=zerodha.INDIA_TZ)
        future = datetime(2026, 8, 2, 6, 0, tzinfo=zerodha.INDIA_TZ)
        past = datetime(2026, 8, 1, 6, 0, tzinfo=zerodha.INDIA_TZ)
        self.assertTrue(zerodha.token_is_current("token", future, now))
        self.assertFalse(zerodha.token_is_current("token", past, now))

    def test_service_session_file_is_private_and_readable_without_keychain(self) -> None:
        expiry = datetime(2026, 8, 2, 6, 0, tzinfo=zerodha.INDIA_TZ)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "zerodha-session.json"
            with mock.patch.object(zerodha, "SESSION_FILE", path):
                zerodha.store_session_file("service-token", expiry)
                with (
                    mock.patch.dict(zerodha.os.environ, {"AI_OS_ZERODHA_ACCESS_TOKEN": ""}),
                    mock.patch.object(zerodha, "keychain_secret", return_value=""),
                ):
                    self.assertEqual(zerodha.keychain_token(), "service-token")
                    self.assertEqual(zerodha.token_expiry(), expiry)
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_exchange_stores_token_and_expiry_together(self) -> None:
        expiry = datetime(2026, 8, 2, 6, 0, tzinfo=zerodha.INDIA_TZ)
        stored = []
        with (
            mock.patch.object(
                zerodha,
                "request_json",
                return_value={"data": {"access_token": "secret", "user_id": "AB123"}},
            ),
            mock.patch.object(zerodha, "next_token_expiry", return_value=expiry),
            mock.patch.object(
                zerodha,
                "store_keychain_token",
                side_effect=lambda token, expires: stored.append((token, expires)),
            ),
            mock.patch.object(zerodha, "bound_user_id", return_value=""),
            mock.patch.object(zerodha, "store_keychain_secret"),
        ):
            result = zerodha.exchange_request_token("key", "secret", "request")

        self.assertEqual(stored, [("secret", expiry)])
        self.assertEqual(result["access_token_expires"], expiry.isoformat())
        self.assertTrue(result["profile_validated"])
        self.assertTrue(result["account_match"])
        self.assertFalse(result["broker_write_allowed"])


    def test_exchange_rejects_a_different_bound_account_before_storage(self) -> None:
        with (
            mock.patch.object(
                zerodha,
                "request_json",
                return_value={"data": {"access_token": "secret", "user_id": "WRONG"}},
            ),
            mock.patch.object(zerodha, "bound_user_id", return_value="AB123"),
            mock.patch.object(zerodha, "store_keychain_token") as store_token,
        ):
            with self.assertRaisesRegex(RuntimeError, "different account"):
                zerodha.exchange_request_token("key", "secret", "request")
        store_token.assert_not_called()


if __name__ == "__main__":
    unittest.main()
