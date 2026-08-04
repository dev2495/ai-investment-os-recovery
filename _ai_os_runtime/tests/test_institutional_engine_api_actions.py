from __future__ import annotations

import json
import unittest
from unittest import mock

from _ai_os_runtime.api import ai_os_api_server


def completed(payload: dict) -> mock.Mock:
    return mock.Mock(returncode=0, stdout=json.dumps(payload), stderr="")


SECTOR_ROWS = [
    [{
        "index_id": 7,
        "index_key": "india-private-banks",
        "index_name": "India Private Banks",
        "weighting_method": "equal",
        "base_value": 1000,
        "effective_date": "2026-08-01",
        "methodology_version": "1",
        "weight_cap": None,
    }],
    [{
        "symbol_id": 11,
        "symbol": "HDFCBANK",
        "valid_from": "2026-08-01",
        "valid_to": None,
        "source_reference": "exchange-list",
        "evidence": [{"source": "exchange-list"}],
        "observed_at": "2026-08-01T00:00:00+00:00",
    }],
    [{
        "symbol_id": 11,
        "ts": "2026-08-01T00:00:00+00:00",
        "close": 100,
        "evidence": {"source_system_id": 1},
    }],
]

OPTIONS_ROWS = [
    [{
        "id": 19,
        "batch_key": "nifty-20260827-20260804t063000z",
        "spot_price": 25000,
        "source_timestamp": "2026-08-04T06:30:00+00:00",
        "received_at": "2026-08-04T06:30:01+00:00",
    }],
    [{
        "model": "black_scholes_merton",
        "valuation_timestamp": "2026-08-04T06:30:00+00:00",
        "spot_price": 25000,
        "futures_price": None,
        "forward_price": None,
        "risk_free_rate": 0.06,
        "dividend_yield": 0,
        "time_to_expiry_years": 0.063,
        "expiry_timestamp": "2026-08-27T10:00:00+00:00",
        "input_quality_status": "passed",
        "quality_flags": [],
    }],
    [{
        "trading_symbol": "NIFTY26AUG25000CE",
        "strike": 25000,
        "option_type": "CE",
        "contract_multiplier": 75,
        "quote_source_timestamp": "2026-08-04T06:30:00+00:00",
        "received_at": "2026-08-04T06:30:01+00:00",
        "last_price": 300,
        "bid_price": 299,
        "ask_price": 301,
        "volume": 1000,
        "open_interest": 5000,
        "previous_open_interest": 4900,
    }],
]


class InstitutionalEngineApiActionsTest(unittest.TestCase):
    def test_fundamental_factory_requires_exactly_one_selector_and_timestamp(self) -> None:
        invalid = (
            {"as_of": "2026-08-04T12:00:00+05:30"},
            {"symbol": "RELIANCE", "company_id": 1, "as_of": "2026-08-04T12:00:00+05:30"},
            {"symbol": "RELIANCE"},
            {"symbol": "RELIANCE", "as_of": "2026-08-04T12:00:00"},
        )
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                ai_os_api_server.run_institutional_fundamental_factory(payload)

    def test_fundamental_factory_defaults_to_dry_run(self) -> None:
        response = {"status": "preview", "database": {"persisted": False}}
        with (
            mock.patch.object(ai_os_api_server.subprocess, "run", return_value=completed(response)) as run,
            mock.patch.object(ai_os_api_server, "audit_api_write") as audit,
        ):
            result = ai_os_api_server.run_institutional_fundamental_factory({
                "symbol": "RELIANCE",
                "as_of": "2026-08-04T12:00:00+05:30",
            })

        self.assertEqual(result, response)
        self.assertIn("--dry-run", run.call_args.args[0])
        self.assertEqual(run.call_args.kwargs["cwd"], ai_os_api_server.RUNTIME_ROOT)
        audit.assert_called_once()

    def test_sector_engine_hydrates_warehouse_and_defaults_to_dry_run(self) -> None:
        response = {"status": "preview", "database": {"persisted": False}}
        with (
            mock.patch.object(ai_os_api_server, "run_psql_json", side_effect=SECTOR_ROWS) as database,
            mock.patch.object(ai_os_api_server.subprocess, "run", return_value=completed(response)) as run,
            mock.patch.object(ai_os_api_server, "audit_api_write") as audit,
        ):
            result = ai_os_api_server.run_sector_intelligence_engine({
                "index_key": "india-private-banks",
                "as_of_date": "2026-08-04",
            })

        self.assertEqual(result, response)
        self.assertEqual(database.call_count, 3)
        self.assertEqual(run.call_args.args[0][-2:], ["-", "--dry-run"])
        submitted = json.loads(run.call_args.kwargs["input"])
        self.assertTrue(submitted["dry_run"])
        self.assertEqual(submitted["index"]["index_id"], 7)
        self.assertEqual(submitted["memberships"][0]["symbol"], "HDFCBANK")
        audit.assert_called_once()

    def test_options_engine_hydrates_stored_batch_and_is_always_paper_only(self) -> None:
        response = {
            "status": "preview",
            "broker_write_allowed": False,
            "capital_action_allowed": False,
        }
        with (
            mock.patch.object(ai_os_api_server, "run_psql_json", side_effect=OPTIONS_ROWS) as database,
            mock.patch.object(ai_os_api_server.subprocess, "run", return_value=completed(response)) as run,
            mock.patch.object(ai_os_api_server, "audit_api_write") as audit,
        ):
            result = ai_os_api_server.run_institutional_options_engine({
                "underlying": "NIFTY",
                "exchange": "NFO",
                "expiry_date": "2026-08-27",
                "as_of": "2026-08-04T12:00:00+05:30",
                "dry_run": False,
            })

        self.assertEqual(result, response)
        self.assertEqual(database.call_count, 3)
        self.assertIn("--dry-run", run.call_args.args[0])
        submitted = json.loads(run.call_args.kwargs["input"])
        self.assertTrue(submitted["dry_run"])
        self.assertTrue(submitted["paper_only"])
        self.assertEqual(submitted["source_batch"]["id"], 19)
        self.assertEqual(len(submitted["contracts"]), 1)
        audit.assert_called_once()

    def test_options_engine_rejects_execution_and_unsafe_output(self) -> None:
        for operation in ("execute", "place_order", "broker_order", "live_trade"):
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                ai_os_api_server.run_institutional_options_engine({"operation": operation})

        unsafe = {"broker_write_allowed": True, "capital_action_allowed": False}
        with (
            mock.patch.object(ai_os_api_server, "run_psql_json", side_effect=OPTIONS_ROWS),
            mock.patch.object(ai_os_api_server.subprocess, "run", return_value=completed(unsafe)),
            mock.patch.object(ai_os_api_server, "audit_api_write") as audit,
            self.assertRaises(ValueError),
        ):
            ai_os_api_server.run_institutional_options_engine({
                "underlying": "NIFTY",
                "exchange": "NFO",
                "expiry_date": "2026-08-27",
                "as_of": "2026-08-04T12:00:00+05:30",
            })
        audit.assert_not_called()

    def test_routes_are_exposed(self) -> None:
        source = ai_os_api_server.Path(ai_os_api_server.__file__).read_text(encoding="utf-8")
        for route in (
            "/api/research/fundamental-factory/run",
            "/api/sector-intelligence/run",
            "/api/options/institutional-analytics/run",
        ):
            self.assertIn(route, source)


if __name__ == "__main__":
    unittest.main()
