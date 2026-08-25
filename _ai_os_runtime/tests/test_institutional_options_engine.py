from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_institutional_options_engine.py"
SPEC = importlib.util.spec_from_file_location("institutional_options_engine", SCRIPT)
assert SPEC and SPEC.loader
engine = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(engine)


def test_black_scholes_merton_known_values_and_put_call_parity() -> None:
    call = engine.black_scholes_merton("call", 100, 100, 1, 0.05, 0.20)
    put = engine.black_scholes_merton("put", 100, 100, 1, 0.05, 0.20)
    assert call["price"] == pytest.approx(10.450584, rel=1e-6)
    assert put["price"] == pytest.approx(5.573526, rel=1e-6)
    assert call["delta"] == pytest.approx(0.636831, rel=1e-6)
    assert call["gamma"] == pytest.approx(0.018762, rel=1e-5)
    assert call["vega"] == pytest.approx(37.524035, rel=1e-6)
    assert call["price"] - put["price"] == pytest.approx(100 - 100 * __import__("math").exp(-0.05), rel=1e-8)


def test_black_76_known_value_and_parity() -> None:
    call = engine.black_76("CE", 100, 100, 1, 0.05, 0.20)
    put = engine.black_76("PE", 100, 100, 1, 0.05, 0.20)
    assert call["price"] == pytest.approx(7.577082, rel=1e-6)
    assert put["price"] == pytest.approx(7.577082, rel=1e-6)
    assert call["delta"] == pytest.approx(0.513500, rel=1e-6)
    assert call["price"] - put["price"] == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize("model", ["black_scholes_merton", "black_76"])
def test_implied_volatility_round_trip_is_validated(model: str) -> None:
    if model == "black_scholes_merton":
        price = engine.black_scholes_merton("call", 100, 105, 0.5, 0.04, 0.27, 0.01)["price"]
    else:
        price = engine.black_76("call", 100, 105, 0.5, 0.04, 0.27)["price"]
    solved = engine.implied_volatility(price, model, "call", 100, 105, 0.5, 0.04, 0.01)
    assert solved["calculation_status"] == "validated"
    assert solved["converged"] is True
    assert solved["implied_volatility"] == pytest.approx(0.27, abs=1e-7)
    assert abs(solved["residual"]) <= 1e-8
    assert solved["broker_write_allowed"] is False


@pytest.mark.parametrize("bad_price", [-1.0, 101.0, 0.0])
def test_implied_volatility_failure_never_fabricates_analytics(bad_price: float) -> None:
    result = engine.implied_volatility(bad_price, "black_scholes_merton", "call", 100, 100, 1, 0.05)
    assert result["calculation_status"] != "validated"
    for field in (
        "implied_volatility", "delta", "gamma", "theta", "vega", "rho",
        "intrinsic_value", "time_value", "no_arbitrage_lower_bound",
        "no_arbitrage_upper_bound",
    ):
        assert result[field] is None
    assert result["diagnostics"] or bad_price == -1.0
    assert result["broker_write_allowed"] is False


def test_stale_liquidity_and_lookahead_filters_are_fail_closed() -> None:
    contract = {
        "quote_source_timestamp": "2026-08-04T09:00:00Z",
        "received_at": "2026-08-04T09:00:01Z",
        "bid_price": 10,
        "ask_price": 15,
        "open_interest": 0,
        "volume": 0,
    }
    result = engine.filter_contract(contract, "2026-08-04T09:05:00Z", max_age_seconds=60, max_spread_bps=100, min_open_interest=10, min_volume=1)
    assert result["eligible"] is False
    assert {"stale_quote", "spread_too_wide", "open_interest_below_minimum", "volume_below_minimum"} <= set(result["quality_flags"])
    future = dict(contract, quote_source_timestamp="2026-08-04T09:06:00Z", received_at="2026-08-04T09:06:01Z")
    assert "lookahead_quote" in engine.filter_contract(future, "2026-08-04T09:05:00Z")["quality_flags"]


def test_premium_series_buildup_and_expected_move() -> None:
    contracts = [
        {"strike": 95, "option_type": "PE", "bid_price": 1.9, "ask_price": 2.1},
        {"strike": 100, "option_type": "CE", "bid_price": 4.9, "ask_price": 5.1},
        {"strike": 100, "option_type": "PE", "bid_price": 3.9, "ask_price": 4.1},
        {"strike": 105, "option_type": "CE", "bid_price": 2.9, "ask_price": 3.1},
    ]
    series = engine.premium_series(contracts, 101, strangle_width=5)
    assert series["atm_straddle"]["call_strike"] == 100
    assert series["atm_straddle"]["combined_premium"] == pytest.approx(9.0)
    assert series["strangle"]["call_strike"] == 105
    assert series["strangle"]["put_strike"] == 95
    move = engine.expected_move(101, "atm_straddle", combined_premium=9)
    assert move["lower_band"] == 92
    assert move["upper_band"] == 110
    assert engine.classify_buildup(1, 10) == "long_buildup"
    assert engine.classify_buildup(-1, 10) == "short_buildup"
    assert engine.classify_buildup(-1, -10) == "long_unwinding"
    assert engine.classify_buildup(1, -10) == "short_covering"


def test_last_traded_premium_history_is_warning_not_executable() -> None:
    payload = {
        "as_of": "2026-08-04T09:00:01Z",
        "dry_run": True,
        "valuation": {
            "model": "black_scholes_merton",
            "valuation_timestamp": "2026-08-04T09:00:00Z",
            "spot_price": 100,
            "risk_free_rate": 0.05,
            "dividend_yield": 0,
            "time_to_expiry_years": 0.1,
        },
        "contracts": [
            {
                "trading_symbol": "CALL",
                "strike": 100,
                "option_type": "CE",
                "quote_source_timestamp": "2026-08-04T09:00:00Z",
                "received_at": "2026-08-04T09:00:01Z",
                "last_price": 5,
                "bid_price": 0,
                "ask_price": 0,
                "open_interest": 100,
                "volume": 0,
            },
            {
                "trading_symbol": "PUT",
                "strike": 100,
                "option_type": "PE",
                "quote_source_timestamp": "2026-08-04T09:00:00Z",
                "received_at": "2026-08-04T09:00:01Z",
                "last_price": 4,
                "bid_price": 0,
                "ask_price": 0,
                "open_interest": 100,
                "volume": 0,
            },
        ],
    }
    result = engine.analyze_chain(payload)
    series = result["premium_series"]["atm_straddle"]
    assert series["combined_premium"] == pytest.approx(9)
    assert series["quality_status"] == "warning"
    assert "empty_quote" in series["quality_flags"]
    assert all(row["calculation_status"] != "validated" for row in result["contracts"])
    assert result["broker_write_allowed"] is False


def test_exposures_have_explicit_assumptions_and_no_action_authority() -> None:
    metrics = engine.black_scholes_merton("call", 100, 100, 0.25, 0.05, 0.2)
    contract = {
        **metrics,
        "calculation_status": "validated",
        "option_type": "CE",
        "open_interest": 1000,
        "contract_multiplier": 50,
        "strike": 100,
        "time_to_expiry": 0.25,
        "risk_free_rate": 0.05,
        "dividend_yield": 0.0,
        "implied_volatility": 0.2,
        "model_name": "black_scholes_merton",
    }
    result = engine.exposure_estimates([contract], 100)
    assert result["quality_status"] == "passed"
    assert result["metrics"]["gex"] < 0
    assert result["assumptions"]["open_interest_sign_method"] == "calls_negative_puts_positive"
    assert "limitation" in result["assumptions"]
    assert result["paper_only"] is True
    assert result["broker_write_allowed"] is False
    assert result["capital_action_allowed"] is False


def test_replay_enforces_source_and_arrival_no_lookahead() -> None:
    batches = [
        {"batch_key": "a", "source_timestamp": "2026-08-04T09:00:00Z", "received_at": "2026-08-04T09:00:05Z", "frame_state": {"spot": 100}},
        {"batch_key": "b", "source_timestamp": "2026-08-04T09:01:00Z", "received_at": "2026-08-04T09:02:00Z", "frame_state": {"spot": 101}},
    ]
    frames = engine.replay_frames(batches, ["2026-08-04T09:00:03Z", "2026-08-04T09:00:10Z", "2026-08-04T09:01:30Z", "2026-08-04T09:02:00Z"])
    assert [frame["batch_key"] for frame in frames] == ["a", "a", "b"]
    assert all(frame["source_timestamp"] <= frame["replay_timestamp"] for frame in frames)
    assert all(frame["available_at"] <= frame["replay_timestamp"] for frame in frames)
    with pytest.raises(engine.AnalyticsError, match="source_timestamp cannot be after received_at"):
        engine.replay_frames([{"source_timestamp": "2026-08-04T09:01:00Z", "received_at": "2026-08-04T09:00:00Z"}], ["2026-08-04T09:02:00Z"])


def test_json_cli_dry_run_and_safety_contract() -> None:
    payload = {
        "operation": "implied_volatility",
        "parameters": {
            "option_price": 10.450583572185565,
            "model": "black_scholes_merton",
            "option_type": "call",
            "reference_price": 100,
            "strike": 100,
            "time_to_expiry": 1,
            "risk_free_rate": 0.05,
        },
    }
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--dry-run"],
        input=json.dumps(payload), text=True, capture_output=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    output = json.loads(completed.stdout)
    assert output["dry_run"] is True
    assert output["paper_only"] is True
    assert output["broker_write_allowed"] is False
    assert output["capital_action_allowed"] is False
    assert output["result"]["calculation_status"] == "validated"


def test_source_contains_no_database_or_broker_execution_path() -> None:
    source = SCRIPT.read_text(encoding="utf-8").lower()
    assert "psycopg" not in source
    assert "subprocess.run" not in source
    assert "place_order" not in source
    assert "broker_write_allowed\": true" not in source
