from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "collect_nse_bse_filings.py"
SPEC = importlib.util.spec_from_file_location("collect_nse_bse_filings", MODULE_PATH)
assert SPEC and SPEC.loader
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


def test_fetch_bse_uses_bounded_curl_transport() -> None:
    with patch.object(
        collector,
        "curl_get",
        return_value=(200, b'{"Table": []}'),
    ) as curl_get:
        status, target_url, rows = collector.fetch_bse(
            collector.dt.date(2026, 8, 4), collector.dt.date(2026, 8, 4), 100
        )

    assert status == 200
    assert target_url.startswith(collector.BSE_API_URL)
    assert rows == []
    curl_get.assert_called_once()
    request_url, headers = curl_get.call_args.args
    assert request_url.startswith(collector.BSE_API_URL)
    assert headers["Referer"] == collector.BSE_PAGE_URL
    assert headers["Origin"] == "https://www.bseindia.com"


def test_collection_reports_unique_durable_filings_and_events() -> None:
    normalized = {
        "source_name": "BSE",
        "exchange": "BSE",
        "symbol": "500000",
        "company_name": "Example Ltd",
        "filing_type": "Company Update",
        "title": "Repeated exchange announcement",
        "filed_at": "2026-08-04T10:00:00+00:00",
        "source_url": "https://example.invalid/filing.pdf",
        "attachment_url": "https://example.invalid/filing.pdf",
        "text": "Repeated exchange announcement",
        "payload": {},
    }
    date = collector.dt.date(2026, 8, 4)

    with (
        patch.object(collector, "start_run", return_value={"id": 12, "run_key": "run-12"}),
        patch.object(collector, "fetch_bse", return_value=(200, collector.BSE_API_URL, [{}, {}])),
        patch.object(collector, "normalize_bse", side_effect=[normalized, normalized]),
        patch.object(collector, "source_system_id", return_value="1"),
        patch.object(collector, "upsert_artifact", return_value=7),
        patch.object(collector, "upsert_filing", return_value=42),
        patch.object(collector, "upsert_event_and_inbox", side_effect=[(1, 1), (1, 0)]),
        patch.object(collector, "finish_run") as finish_run,
        patch.object(collector, "mark_connector_after_run"),
    ):
        result = collector.collect_source("bse", date, date, 100, "test", False)

    assert result["rows_seen"] == 2
    assert result["rows_upserted"] == 1
    assert result["events_upserted"] == 1
    assert result["inbox_items_created"] == 1
    assert finish_run.call_args.args[3:7] == (2, 1, 1, 1)


def test_fetch_bse_rejects_exchange_error_payload() -> None:
    with patch.object(
        collector,
        "curl_get",
        return_value=(200, b'{"Status": false, "Message": "Please try again"}'),
    ):
        try:
            collector.fetch_bse(
                collector.dt.date(2026, 8, 4), collector.dt.date(2026, 8, 4), 100
            )
        except RuntimeError as exc:
            assert str(exc) == "BSE API error: Please try again"
        else:
            raise AssertionError("exchange error payload must fail the collector")
