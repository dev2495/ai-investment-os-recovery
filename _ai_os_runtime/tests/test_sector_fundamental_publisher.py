from __future__ import annotations

import datetime as dt
import sys
from decimal import Decimal
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import sync_sector_fundamentals as publisher


def fact(key: str, value: str, unit: str, symbol_id: int = 1) -> dict:
    return {
        "symbol_id": symbol_id,
        "primary_symbol": "TEST",
        "primary_exchange": "NSE",
        "fact_key": key,
        "fiscal_year": 2026,
        "period_start": "2025-04-01",
        "period_end": "2026-03-31",
        "statement_scope": "consolidated",
        "value_numeric": value,
        "currency": "INR",
        "unit": unit,
        "available_at": "2026-07-01T10:00:00+00:00",
        "evidence_id": 99,
        "source_url": "https://company.example/annual-report.pdf",
        "verification_status": "machine_extracted",
        "source_locator": {"page": 100},
    }


def test_monetary_units_are_converted_only_at_sector_boundary() -> None:
    crore = publisher.normalize_fact(fact("revenue_from_operations", "12.5", "INR crore"))
    lakh = publisher.normalize_fact(fact("profit_after_tax", "25", "INR lakh"))
    million = publisher.normalize_fact(fact("total_assets", "40", "INR million"))
    assert crore["normalized_value"] == Decimal("125.0")
    assert lakh["normalized_value"] == Decimal("2.5")
    assert million["normalized_value"] == Decimal("40")
    assert crore["lineage"]["original_unit"] == "INR crore"
    assert crore["normalized_unit"] == "INR million"


def test_unresolved_or_non_inr_units_are_rejected_not_guessed() -> None:
    with pytest.raises(ValueError, match="unresolved source unit"):
        publisher.normalize_fact(fact("revenue_from_operations", "10", "lakh"))
    row = fact("revenue_from_operations", "10", "INR crore")
    row["currency"] = "USD"
    with pytest.raises(ValueError, match="INR-denominated"):
        publisher.normalize_fact(row)


def test_unresolved_optional_fact_is_quarantined_without_losing_valid_facts() -> None:
    valid = fact("revenue_from_operations", "10", "INR crore")
    unresolved = fact("total_equity", "5", "source_unit_unresolved")
    rejections = []
    observations = publisher.build_observations(
        [valid, unresolved], [], 3000, dt.date(2026, 7, 2), rejections
    )
    assert [row["metric_key"] for row in observations] == ["reported_revenue"]
    assert rejections == [{
        "symbol": "TEST",
        "fact_key": "total_equity",
        "evidence_id": 99,
        "reason": "total_equity has unresolved source unit: source_unit_unresolved",
    }]


def test_eps_is_per_share_and_pe_uses_point_in_time_price() -> None:
    eps = fact("basic_eps", "20", "INR/share")
    observations = publisher.build_observations(
        [eps],
        [{"symbol_id": 1, "latest_close": "500", "price_ts": "2026-07-02T10:00:00+00:00", "price_source_system_id": 2054}],
        3000,
        dt.date(2026, 7, 2),
    )
    pe = next(row for row in observations if row["metric_key"] == "price_to_earnings")
    assert pe["value"] == Decimal("25")
    assert pe["period_start"] == "2026-07-02"
    assert pe["period_end"] == "2026-07-02"
    assert pe["metadata"]["eps_available_at"] == "2026-07-01T10:00:00+00:00"
    assert pe["metadata"]["price_source_system_id"] == 2054
    assert pe["metadata"]["point_in_time"] is True


def test_nonpositive_eps_never_creates_pe() -> None:
    eps = fact("basic_eps", "-5", "INR/share")
    observations = publisher.build_observations(
        [eps],
        [{"symbol_id": 1, "latest_close": "500", "price_ts": "2026-07-02T10:00:00+00:00", "price_source_system_id": 2054}],
        3000,
        dt.date(2026, 7, 2),
    )
    assert all(row["metric_key"] != "price_to_earnings" for row in observations)


def test_sector_ratios_use_ratio_of_sums_not_average_of_company_ratios() -> None:
    observations = []
    for symbol_id, revenue, profit, equity in ((1, "100", "10", "50"), (2, "300", "60", "150")):
        for metric, value in (
            ("reported_revenue", revenue),
            ("reported_profit_after_tax", profit),
            ("reported_total_equity", equity),
        ):
            observations.append({
                "metric_key": metric,
                "symbol_id": symbol_id,
                "value": Decimal(value),
                "input_fingerprint": f"{symbol_id}-{metric}",
            })
    aggregates = publisher.compute_aggregates(observations, 10)
    margin = next(row for row in aggregates if row["metric_key"] == "net_profit_margin")
    roe = next(row for row in aggregates if row["metric_key"] == "return_on_equity")
    assert margin["value"] == Decimal("17.5")
    assert roe["value"] == Decimal("35")
    assert margin["covered_count"] == 2
    assert margin["constituent_count"] == 10


def test_governance_contract_has_no_broker_execution_surface() -> None:
    source = (SCRIPTS / "sync_sector_fundamentals.py").read_text(encoding="utf-8")
    assert "broker_write_allowed" in source
    assert "capital_action_allowed" in source
    assert "INSERT INTO trading.orders" not in source
    assert "INSERT INTO portfolio.trades" not in source
    assert "No backdating" in source
    assert "metric_keys == required_core_metrics" in source
