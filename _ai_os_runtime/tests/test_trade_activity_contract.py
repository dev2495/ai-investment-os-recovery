from __future__ import annotations

import unittest
from unittest import mock

from _ai_os_runtime.api import ai_os_api_server


class TradeActivityContractTest(unittest.TestCase):
    def test_option_trade_keeps_expiry_separate_from_trade_time(self) -> None:
        recorded = {
            "id": 88,
            "symbol": "NIFTY",
            "instrument_type": "option",
            "side": "buy",
        }
        with (
            mock.patch.object(
                ai_os_api_server,
                "run_psql_json_statement",
                side_effect=[[recorded], [], []],
            ) as query,
            mock.patch.object(ai_os_api_server, "audit_api_write"),
        ):
            result = ai_os_api_server.record_trade(
                {
                    "symbol": "NIFTY",
                    "exchange": "NFO",
                    "instrument_type": "option",
                    "option_type": "CE",
                    "strike": 25000,
                    "expiry_date": "2026-08-27",
                    "strategy_name": "manual hedge",
                    "side": "buy",
                    "quantity": 75,
                    "price": 125.5,
                    "notes": "Protect tactical short",
                },
                execution_mode="manual_actual",
                source_kind="manual",
                actor_default="Devarsh",
            )

        sql = query.call_args_list[0].args[0]
        self.assertEqual(result["id"], 88)
        self.assertIn("payload, created_by", sql)
        self.assertIn('"option_type": "CE"', sql)
        self.assertIn('"expiry_date": "2026-08-27"', sql)
        self.assertIn("'Protect tactical short'", sql)
        self.assertNotIn("COALESCE('2026-08-27'::timestamptz", sql)

    def test_snapshot_projects_structured_option_fields(self) -> None:
        source = (
            ai_os_api_server.Path(ai_os_api_server.__file__)
            .read_text(encoding="utf-8")
        )
        self.assertIn("payload->>'option_type' AS option_type", source)
        self.assertIn("payload->>'expiry_date' AS expiry_date", source)


if __name__ == "__main__":
    unittest.main()
