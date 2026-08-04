#!/usr/bin/env python3
"""Deterministic, paper-only institutional options analytics.

The module deliberately has no database or broker dependency.  It accepts a
point-in-time JSON payload, performs validated calculations, and emits JSON
records shaped for migration 187.  Units are explicit:

* volatility and rates are decimals (0.20 means 20%);
* theta and charm are annual derivatives (divide by 365 for calendar-day use);
* vega and rho are changes for a 1.00 absolute change (multiply by 0.01 for one
  volatility/rate point);
* GEX is currency delta change for a 1% underlying move;
* DEX is signed currency delta notional;
* vanna exposure is currency delta-notional change for one volatility point;
* charm exposure is currency delta-notional change for one calendar day.

No result produced by this process authorizes capital action or broker writes.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


MODEL_VERSION = "institutional-options-1.0"
SOLVER_VERSION = "bounded-bisection-1.0"
SAFETY = {
    "paper_only": True,
    "broker_write_allowed": False,
    "capital_action_allowed": False,
}
EXPOSURE_ASSUMPTIONS = {
    "dealer_position_assumption": "dealers_short_customer_open_interest",
    "open_interest_sign_method": "calls_negative_puts_positive",
    "gex_unit": "currency_delta_change_per_1pct_underlying_move",
    "dex_unit": "currency_delta_notional",
    "vanna_unit": "currency_delta_notional_change_per_1_vol_point",
    "charm_unit": "currency_delta_notional_change_per_calendar_day",
    "gamma_flip_method": "linear_interpolation_of_aggregate_gex_over_spot_grid",
    "limitation": "open_interest has no observed owner or trade direction; exposures are scenario estimates",
}


class AnalyticsError(ValueError):
    """A deterministic input or validation failure."""


def _finite(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise AnalyticsError(f"{name} must be numeric") from exc
    if not math.isfinite(result):
        raise AnalyticsError(f"{name} must be finite")
    return result


def _positive(value: Any, name: str) -> float:
    result = _finite(value, name)
    if result <= 0:
        raise AnalyticsError(f"{name} must be positive")
    return result


def _option_type(value: str) -> str:
    normalized = str(value).upper()
    if normalized in {"CE", "CALL", "C"}:
        return "call"
    if normalized in {"PE", "PUT", "P"}:
        return "put"
    raise AnalyticsError("option_type must be call/put or CE/PE")


def _normal_pdf(value: float) -> float:
    return math.exp(-0.5 * value * value) / math.sqrt(2.0 * math.pi)


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def _core_terms(reference: float, strike: float, time_to_expiry: float, rate_carry: float, volatility: float) -> tuple[float, float]:
    root_time = math.sqrt(time_to_expiry)
    d1 = (math.log(reference / strike) + (rate_carry + 0.5 * volatility * volatility) * time_to_expiry) / (volatility * root_time)
    return d1, d1 - volatility * root_time


def black_scholes_merton(
    option_type: str,
    spot: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    volatility: float,
    dividend_yield: float = 0.0,
) -> dict[str, float]:
    """Return Black-Scholes-Merton price and analytical Greeks."""
    kind = _option_type(option_type)
    spot = _positive(spot, "spot")
    strike = _positive(strike, "strike")
    time_to_expiry = _positive(time_to_expiry, "time_to_expiry")
    volatility = _positive(volatility, "volatility")
    risk_free_rate = _finite(risk_free_rate, "risk_free_rate")
    dividend_yield = _finite(dividend_yield, "dividend_yield")
    d1, d2 = _core_terms(spot, strike, time_to_expiry, risk_free_rate - dividend_yield, volatility)
    discount_r = math.exp(-risk_free_rate * time_to_expiry)
    discount_q = math.exp(-dividend_yield * time_to_expiry)
    density = _normal_pdf(d1)
    root_time = math.sqrt(time_to_expiry)
    if kind == "call":
        price = spot * discount_q * _normal_cdf(d1) - strike * discount_r * _normal_cdf(d2)
        delta = discount_q * _normal_cdf(d1)
        theta = (
            -(spot * discount_q * density * volatility) / (2.0 * root_time)
            - risk_free_rate * strike * discount_r * _normal_cdf(d2)
            + dividend_yield * spot * discount_q * _normal_cdf(d1)
        )
        rho = strike * time_to_expiry * discount_r * _normal_cdf(d2)
        charm = dividend_yield * discount_q * _normal_cdf(d1)
    else:
        price = strike * discount_r * _normal_cdf(-d2) - spot * discount_q * _normal_cdf(-d1)
        delta = discount_q * (_normal_cdf(d1) - 1.0)
        theta = (
            -(spot * discount_q * density * volatility) / (2.0 * root_time)
            + risk_free_rate * strike * discount_r * _normal_cdf(-d2)
            - dividend_yield * spot * discount_q * _normal_cdf(-d1)
        )
        rho = -strike * time_to_expiry * discount_r * _normal_cdf(-d2)
        charm = -dividend_yield * discount_q * _normal_cdf(-d1)
    gamma = discount_q * density / (spot * volatility * root_time)
    vega = spot * discount_q * density * root_time
    vanna = -discount_q * density * d2 / volatility
    common_charm = discount_q * density * (
        2.0 * (risk_free_rate - dividend_yield) * time_to_expiry - d2 * volatility * root_time
    ) / (2.0 * time_to_expiry * volatility * root_time)
    charm -= common_charm
    return {
        "price": price,
        "delta": delta,
        "gamma": gamma,
        "theta": theta,
        "vega": vega,
        "rho": rho,
        "vanna": vanna,
        "charm": charm,
        "d1": d1,
        "d2": d2,
    }


def black_76(
    option_type: str,
    forward: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    volatility: float,
) -> dict[str, float]:
    """Return Black-76 price and forward Greeks.

    Delta, gamma, vanna and charm are derivatives with respect to the supplied
    forward, not spot.  Theta holds the quoted forward constant.
    """
    kind = _option_type(option_type)
    forward = _positive(forward, "forward")
    strike = _positive(strike, "strike")
    time_to_expiry = _positive(time_to_expiry, "time_to_expiry")
    volatility = _positive(volatility, "volatility")
    risk_free_rate = _finite(risk_free_rate, "risk_free_rate")
    d1, d2 = _core_terms(forward, strike, time_to_expiry, 0.0, volatility)
    discount = math.exp(-risk_free_rate * time_to_expiry)
    density = _normal_pdf(d1)
    root_time = math.sqrt(time_to_expiry)
    if kind == "call":
        undiscounted = forward * _normal_cdf(d1) - strike * _normal_cdf(d2)
        delta = discount * _normal_cdf(d1)
        rho = -time_to_expiry * discount * undiscounted
    else:
        undiscounted = strike * _normal_cdf(-d2) - forward * _normal_cdf(-d1)
        delta = -discount * _normal_cdf(-d1)
        rho = -time_to_expiry * discount * undiscounted
    price = discount * undiscounted
    gamma = discount * density / (forward * volatility * root_time)
    vega = discount * forward * density * root_time
    theta = risk_free_rate * price - discount * forward * density * volatility / (2.0 * root_time)
    vanna = -discount * density * d2 / volatility
    charm = (
        risk_free_rate * delta
        - discount * density * (-d2 * volatility * root_time) / (2.0 * time_to_expiry * volatility * root_time)
    )
    return {
        "price": price,
        "delta": delta,
        "gamma": gamma,
        "theta": theta,
        "vega": vega,
        "rho": rho,
        "vanna": vanna,
        "charm": charm,
        "d1": d1,
        "d2": d2,
    }


def no_arbitrage_bounds(
    model: str,
    option_type: str,
    reference_price: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    dividend_yield: float = 0.0,
) -> tuple[float, float]:
    kind = _option_type(option_type)
    reference_price = _positive(reference_price, "reference_price")
    strike = _positive(strike, "strike")
    time_to_expiry = _positive(time_to_expiry, "time_to_expiry")
    risk_free_rate = _finite(risk_free_rate, "risk_free_rate")
    discount_r = math.exp(-risk_free_rate * time_to_expiry)
    normalized = model.lower()
    if normalized == "black_scholes_merton":
        discount_q = math.exp(-_finite(dividend_yield, "dividend_yield") * time_to_expiry)
        asset = reference_price * discount_q
    elif normalized == "black_76":
        asset = reference_price * discount_r
    else:
        raise AnalyticsError("model must be black_scholes_merton or black_76")
    discounted_strike = strike * discount_r
    if kind == "call":
        return max(0.0, asset - discounted_strike), asset
    return max(0.0, discounted_strike - asset), discounted_strike


def implied_volatility(
    option_price: float,
    model: str,
    option_type: str,
    reference_price: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    dividend_yield: float = 0.0,
    tolerance: float = 1e-8,
    max_iterations: int = 200,
    min_volatility: float = 1e-8,
    max_volatility: float = 8.0,
) -> dict[str, Any]:
    """Solve IV by bounded bisection and validate price residual.

    Any failure returns null IV/Greeks/bounds to satisfy migration 187's
    validated-only invariant.  Diagnostic bounds stay in ``diagnostics``.
    """
    empty = {
        "calculation_status": "not_computable",
        "converged": False,
        "iteration_count": None,
        "residual": None,
        "implied_volatility": None,
        "delta": None,
        "gamma": None,
        "theta": None,
        "vega": None,
        "rho": None,
        "intrinsic_value": None,
        "time_value": None,
        "no_arbitrage_lower_bound": None,
        "no_arbitrage_upper_bound": None,
        "quality_status": "rejected",
        "quality_flags": [],
        "diagnostics": {},
        **SAFETY,
    }
    try:
        price = _finite(option_price, "option_price")
        if price < 0:
            raise AnalyticsError("option_price must be nonnegative")
        lower, upper = no_arbitrage_bounds(
            model, option_type, reference_price, strike, time_to_expiry,
            risk_free_rate, dividend_yield,
        )
        empty["diagnostics"] = {"no_arbitrage_lower_bound": lower, "no_arbitrage_upper_bound": upper}
        bound_epsilon = max(tolerance, 1e-12 * max(1.0, upper))
        if price < lower - bound_epsilon or price > upper + bound_epsilon:
            raise AnalyticsError("market price violates no-arbitrage bounds")
        if price <= lower + bound_epsilon or price >= upper - bound_epsilon:
            raise AnalyticsError("market price is on a bound; positive finite IV is not identifiable")
        if max_iterations <= 0 or tolerance <= 0 or min_volatility <= 0 or max_volatility <= min_volatility:
            raise AnalyticsError("invalid solver configuration")

        normalized = model.lower()

        def evaluate(volatility: float) -> dict[str, float]:
            if normalized == "black_scholes_merton":
                return black_scholes_merton(
                    option_type, reference_price, strike, time_to_expiry,
                    risk_free_rate, volatility, dividend_yield,
                )
            if normalized == "black_76":
                return black_76(
                    option_type, reference_price, strike, time_to_expiry,
                    risk_free_rate, volatility,
                )
            raise AnalyticsError("model must be black_scholes_merton or black_76")

        low = min_volatility
        high = max_volatility
        low_price = evaluate(low)["price"]
        high_price = evaluate(high)["price"]
        if price < low_price - tolerance or price > high_price + tolerance:
            raise AnalyticsError("solver volatility bracket does not contain market price")
        solved: dict[str, float] | None = None
        solved_vol = None
        residual = None
        iteration = 0
        for iteration in range(1, max_iterations + 1):
            mid = 0.5 * (low + high)
            candidate = evaluate(mid)
            candidate_residual = candidate["price"] - price
            if abs(candidate_residual) <= tolerance:
                solved = candidate
                solved_vol = mid
                residual = candidate_residual
                break
            if candidate_residual < 0:
                low = mid
            else:
                high = mid
        if solved is None or solved_vol is None or residual is None:
            empty["calculation_status"] = "failed"
            raise AnalyticsError("implied-volatility solver did not converge")
        if solved_vol <= 0 or not all(math.isfinite(solved[key]) for key in ("price", "delta", "gamma", "theta", "vega", "rho")):
            raise AnalyticsError("solver produced non-finite analytics")
        intrinsic = lower
        return {
            "calculation_status": "validated",
            "converged": True,
            "iteration_count": iteration,
            "residual": residual,
            "implied_volatility": solved_vol,
            "delta": solved["delta"],
            "gamma": solved["gamma"],
            "theta": solved["theta"],
            "vega": solved["vega"],
            "rho": solved["rho"],
            "vanna": solved["vanna"],
            "charm": solved["charm"],
            "intrinsic_value": intrinsic,
            "time_value": price - intrinsic,
            "no_arbitrage_lower_bound": lower,
            "no_arbitrage_upper_bound": upper,
            "quality_status": "passed",
            "quality_flags": [],
            "diagnostics": {},
            "model_name": normalized,
            "model_version": MODEL_VERSION,
            "solver_name": "bounded_bisection",
            "solver_version": SOLVER_VERSION,
            **SAFETY,
        }
    except AnalyticsError as exc:
        empty["quality_flags"].append(str(exc))
        return empty


def _timestamp(value: Any, name: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise AnalyticsError(f"{name} must be ISO-8601") from exc
    else:
        raise AnalyticsError(f"{name} must be a datetime or ISO-8601 string")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def filter_contract(
    contract: dict[str, Any],
    as_of: datetime | str,
    max_age_seconds: int = 120,
    max_spread_bps: float = 500.0,
    min_open_interest: float = 1.0,
    min_volume: float = 0.0,
) -> dict[str, Any]:
    """Apply point-in-time freshness and executable-liquidity filters."""
    flags: list[str] = []
    now = _timestamp(as_of, "as_of")
    try:
        quote_time = _timestamp(contract.get("quote_source_timestamp"), "quote_source_timestamp")
        received_at = _timestamp(contract.get("received_at", contract.get("quote_source_timestamp")), "received_at")
        if quote_time > now or received_at > now:
            flags.append("lookahead_quote")
        age = (now - quote_time).total_seconds()
        if age < 0 or age > max_age_seconds:
            flags.append("stale_quote")
    except AnalyticsError as exc:
        age = None
        flags.append(str(exc))
    bid = contract.get("bid_price")
    ask = contract.get("ask_price")
    spread_bps = None
    try:
        bid_value = _finite(bid, "bid_price")
        ask_value = _finite(ask, "ask_price")
        if bid_value < 0 or ask_value < 0:
            flags.append("negative_quote")
        elif bid_value > ask_value:
            flags.append("crossed_quote")
        elif bid_value == 0 and ask_value == 0:
            flags.append("empty_quote")
        else:
            midpoint = 0.5 * (bid_value + ask_value)
            spread_bps = (ask_value - bid_value) / midpoint * 10000.0 if midpoint > 0 else math.inf
            if spread_bps > max_spread_bps:
                flags.append("spread_too_wide")
    except AnalyticsError:
        flags.append("missing_two_sided_quote")
    open_interest = contract.get("open_interest")
    volume = contract.get("volume")
    try:
        if _finite(open_interest, "open_interest") < min_open_interest:
            flags.append("open_interest_below_minimum")
    except AnalyticsError:
        flags.append("missing_open_interest")
    try:
        if _finite(volume, "volume") < min_volume:
            flags.append("volume_below_minimum")
    except AnalyticsError:
        flags.append("missing_volume")
    return {
        "eligible": not flags,
        "staleness_status": "live" if "stale_quote" not in flags and "lookahead_quote" not in flags else "stale",
        "liquidity_status": "liquid" if not flags else "illiquid",
        "source_age_seconds": age,
        "spread_bps": spread_bps,
        "quality_flags": flags,
        **SAFETY,
    }


def select_market_price(contract: dict[str, Any]) -> tuple[str, float] | None:
    try:
        bid = _finite(contract.get("bid_price"), "bid_price")
        ask = _finite(contract.get("ask_price"), "ask_price")
        if 0 <= bid <= ask and ask > 0:
            return "mid", 0.5 * (bid + ask)
    except AnalyticsError:
        pass
    try:
        last = _finite(contract.get("last_price"), "last_price")
        if last >= 0:
            return "last", last
    except AnalyticsError:
        pass
    return None


def premium_series(contracts: Iterable[dict[str, Any]], spot: float, strangle_width: float | None = None) -> dict[str, Any]:
    """Select nearest ATM straddle and symmetric-width strangle from valid prices."""
    spot = _positive(spot, "spot")
    priced: dict[tuple[float, str], tuple[dict[str, Any], float]] = {}
    for contract in contracts:
        selected = select_market_price(contract)
        if selected is None:
            continue
        strike = _positive(contract.get("strike"), "strike")
        priced[(strike, _option_type(str(contract.get("option_type"))))] = (contract, selected[1])
    common = sorted({strike for strike, kind in priced if kind == "call"} & {strike for strike, kind in priced if kind == "put"})
    result: dict[str, Any] = {"atm_straddle": None, "strangle": None, **SAFETY}
    if common:
        strike = min(common, key=lambda item: (abs(item - spot), item))
        call_price = priced[(strike, "call")][1]
        put_price = priced[(strike, "put")][1]
        result["atm_straddle"] = {
            "series_type": "atm_straddle", "reference_spot": spot,
            "call_strike": strike, "put_strike": strike,
            "call_premium": call_price, "put_premium": put_price,
            "combined_premium": call_price + put_price,
            "selection_method": "nearest_common_strike_to_spot",
            "quality_status": "passed", "assumptions": {}, **SAFETY,
        }
    width = _positive(strangle_width, "strangle_width") if strangle_width is not None else None
    call_strikes = sorted(strike for strike, kind in priced if kind == "call" and strike > spot)
    put_strikes = sorted((strike for strike, kind in priced if kind == "put" and strike < spot), reverse=True)
    if call_strikes and put_strikes:
        call_target = spot + (width or 0.0)
        put_target = spot - (width or 0.0)
        call_strike = min(call_strikes, key=lambda item: (abs(item - call_target), item))
        put_strike = min(put_strikes, key=lambda item: (abs(item - put_target), -item))
        call_price = priced[(call_strike, "call")][1]
        put_price = priced[(put_strike, "put")][1]
        result["strangle"] = {
            "series_type": "strangle", "reference_spot": spot,
            "call_strike": call_strike, "put_strike": put_strike,
            "call_premium": call_price, "put_premium": put_price,
            "combined_premium": call_price + put_price,
            "selection_method": "nearest_otm_strikes_to_symmetric_target",
            "quality_status": "passed",
            "assumptions": {"requested_width": width}, **SAFETY,
        }
    return result


def classify_buildup(price_change: float, open_interest_change: float, tolerance: float = 1e-12) -> str:
    price_change = _finite(price_change, "price_change")
    open_interest_change = _finite(open_interest_change, "open_interest_change")
    if abs(price_change) <= tolerance or abs(open_interest_change) <= tolerance:
        return "neutral"
    if price_change > 0 and open_interest_change > 0:
        return "long_buildup"
    if price_change < 0 and open_interest_change > 0:
        return "short_buildup"
    if price_change < 0 and open_interest_change < 0:
        return "long_unwinding"
    return "short_covering"


def expected_move(
    reference_price: float,
    method: str,
    confidence_level: float = 0.682689492,
    combined_premium: float | None = None,
    implied_volatility_value: float | None = None,
    horizon_years: float | None = None,
) -> dict[str, Any]:
    reference_price = _positive(reference_price, "reference_price")
    confidence_level = _finite(confidence_level, "confidence_level")
    if not 0 < confidence_level < 1:
        raise AnalyticsError("confidence_level must be between zero and one")
    normalized = method.lower()
    if normalized == "atm_straddle":
        move = _finite(combined_premium, "combined_premium")
        if move < 0:
            raise AnalyticsError("combined_premium must be nonnegative")
        assumptions = {"band_definition": "reference_price plus_or_minus combined_atm_premium"}
    elif normalized == "validated_iv_lognormal":
        volatility = _positive(implied_volatility_value, "implied_volatility")
        horizon = _positive(horizon_years, "horizon_years")
        # One standard-deviation move.  Non-default confidence levels are labels,
        # not silently transformed without a standard-library inverse CDF.
        if abs(confidence_level - 0.682689492) > 1e-6:
            raise AnalyticsError("validated_iv_lognormal currently supports one-standard-deviation confidence only")
        move = reference_price * volatility * math.sqrt(horizon)
        assumptions = {"formula": "spot * validated_iv * sqrt(year_fraction)", "distribution": "lognormal_small_move_approximation"}
    else:
        raise AnalyticsError("method must be atm_straddle or validated_iv_lognormal")
    return {
        "method": normalized,
        "confidence_level": confidence_level,
        "reference_price": reference_price,
        "expected_move_absolute": move,
        "expected_move_percent": move / reference_price * 100.0,
        "lower_band": max(0.0, reference_price - move),
        "upper_band": reference_price + move,
        "probability_method": assumptions.get("distribution", "premium_implied_not_a_calibrated_probability"),
        "assumptions": assumptions,
        "quality_status": "passed",
        **SAFETY,
    }


def exposure_estimates(
    validated_contracts: Iterable[dict[str, Any]],
    spot: float,
    spot_grid_percent: Iterable[float] = (-0.10, -0.05, 0.0, 0.05, 0.10),
) -> dict[str, Any]:
    """Calculate assumption-bound GEX/DEX/vanna/charm and a gamma-flip grid."""
    spot = _positive(spot, "spot")
    rows = list(validated_contracts)
    totals = {"gex": 0.0, "dex": 0.0, "vanna": 0.0, "charm": 0.0}
    used = 0
    for row in rows:
        if row.get("calculation_status") != "validated":
            continue
        try:
            kind = _option_type(str(row.get("option_type")))
            sign = -1.0 if kind == "call" else 1.0
            open_interest = _finite(row.get("open_interest"), "open_interest")
            multiplier = _positive(row.get("contract_multiplier", 1.0), "contract_multiplier")
            delta = _finite(row.get("delta"), "delta")
            gamma = _finite(row.get("gamma"), "gamma")
            vanna = _finite(row.get("vanna"), "vanna")
            charm = _finite(row.get("charm"), "charm")
        except AnalyticsError:
            continue
        totals["gex"] += sign * gamma * open_interest * multiplier * spot * spot * 0.01
        totals["dex"] += sign * delta * open_interest * multiplier * spot
        totals["vanna"] += sign * vanna * open_interest * multiplier * spot * 0.01
        totals["charm"] += sign * charm * open_interest * multiplier * spot / 365.0
        used += 1

    grid: list[dict[str, float]] = []
    for shock in sorted({_finite(item, "spot_grid_percent") for item in spot_grid_percent}):
        shocked_spot = spot * (1.0 + shock)
        if shocked_spot <= 0:
            continue
        aggregate = 0.0
        for row in rows:
            if row.get("calculation_status") != "validated":
                continue
            try:
                kind = _option_type(str(row.get("option_type")))
                sign = -1.0 if kind == "call" else 1.0
                model = str(row.get("model_name", "black_scholes_merton"))
                strike = _positive(row.get("strike"), "strike")
                time_to_expiry = _positive(row.get("time_to_expiry"), "time_to_expiry")
                rate = _finite(row.get("risk_free_rate", 0.0), "risk_free_rate")
                volatility = _positive(row.get("implied_volatility"), "implied_volatility")
                if model == "black_76":
                    metrics = black_76(kind, shocked_spot, strike, time_to_expiry, rate, volatility)
                else:
                    metrics = black_scholes_merton(kind, shocked_spot, strike, time_to_expiry, rate, volatility, _finite(row.get("dividend_yield", 0.0), "dividend_yield"))
                aggregate += sign * metrics["gamma"] * _finite(row.get("open_interest"), "open_interest") * _positive(row.get("contract_multiplier", 1.0), "contract_multiplier") * shocked_spot * shocked_spot * 0.01
            except AnalyticsError:
                continue
        grid.append({"spot": shocked_spot, "shock_percent": shock, "aggregate_gex": aggregate})
    gamma_flip = None
    for left, right in zip(grid, grid[1:]):
        if left["aggregate_gex"] == 0:
            gamma_flip = left["spot"]
            break
        if left["aggregate_gex"] * right["aggregate_gex"] < 0:
            weight = -left["aggregate_gex"] / (right["aggregate_gex"] - left["aggregate_gex"])
            gamma_flip = left["spot"] + weight * (right["spot"] - left["spot"])
            break
    quality = "passed" if used else "not_computable"
    return {
        "metrics": totals if used else {key: None for key in totals},
        "gamma_flip": gamma_flip,
        "spot_grid": grid,
        "contracts_used": used,
        "contracts_supplied": len(rows),
        "coverage_ratio": used / len(rows) if rows else 0.0,
        "quality_status": quality,
        "assumptions": dict(EXPOSURE_ASSUMPTIONS),
        **SAFETY,
    }


def replay_frames(batches: Iterable[dict[str, Any]], replay_clocks: Iterable[datetime | str]) -> list[dict[str, Any]]:
    """Build point-in-time replay frames using only evidence available by each clock."""
    parsed: list[tuple[datetime, datetime, dict[str, Any]]] = []
    for batch in batches:
        source = _timestamp(batch.get("source_timestamp"), "source_timestamp")
        available = _timestamp(batch.get("received_at", batch.get("available_at")), "received_at")
        if source > available:
            raise AnalyticsError("source_timestamp cannot be after received_at")
        parsed.append((source, available, batch))
    frames: list[dict[str, Any]] = []
    for frame_number, clock_value in enumerate(sorted(_timestamp(item, "replay_clock") for item in replay_clocks)):
        eligible = [item for item in parsed if item[0] <= clock_value and item[1] <= clock_value]
        if not eligible:
            continue
        source, available, batch = max(eligible, key=lambda item: (item[0], item[1]))
        frames.append({
            "frame_number": frame_number,
            "replay_timestamp": clock_value.isoformat(),
            "source_timestamp": source.isoformat(),
            "available_at": available.isoformat(),
            "batch_key": batch.get("batch_key"),
            "frame_state": batch.get("frame_state", {}),
            "point_in_time_enforced": True,
            **SAFETY,
        })
    return frames


def analyze_chain(payload: dict[str, Any]) -> dict[str, Any]:
    valuation = payload.get("valuation") or {}
    contracts = list(payload.get("contracts") or [])
    as_of = payload.get("as_of") or valuation.get("valuation_timestamp")
    model = str(valuation.get("model", "black_scholes_merton"))
    reference = valuation.get("spot_price") if model == "black_scholes_merton" else valuation.get("forward_price", valuation.get("futures_price"))
    filters = payload.get("filters") or {}
    results: list[dict[str, Any]] = []
    validated_for_exposure: list[dict[str, Any]] = []
    eligible_for_premium: list[dict[str, Any]] = []
    for contract in contracts:
        check = filter_contract(
            contract, as_of,
            max_age_seconds=int(filters.get("max_age_seconds", 120)),
            max_spread_bps=float(filters.get("max_spread_bps", 500.0)),
            min_open_interest=float(filters.get("min_open_interest", 1.0)),
            min_volume=float(filters.get("min_volume", 0.0)),
        )
        base = {"trading_symbol": contract.get("trading_symbol"), "strike": contract.get("strike"), "option_type": contract.get("option_type"), "filter": check}
        if not check["eligible"]:
            results.append({**base, **implied_volatility(0.0, model, str(contract.get("option_type")), reference, contract.get("strike"), valuation.get("time_to_expiry_years"), valuation.get("risk_free_rate"), valuation.get("dividend_yield", 0.0))})
            results[-1]["quality_flags"] = list(dict.fromkeys(check["quality_flags"] + results[-1]["quality_flags"]))
            continue
        selected = select_market_price(contract)
        if selected is None:
            failed = implied_volatility(-1.0, model, str(contract.get("option_type")), reference, contract.get("strike"), valuation.get("time_to_expiry_years"), valuation.get("risk_free_rate"), valuation.get("dividend_yield", 0.0))
            failed["quality_flags"] = ["no_valid_market_price"]
            results.append({**base, **failed})
            continue
        solved = implied_volatility(
            selected[1], model, str(contract.get("option_type")), reference,
            contract.get("strike"), valuation.get("time_to_expiry_years"),
            valuation.get("risk_free_rate"), valuation.get("dividend_yield", 0.0),
        )
        row = {**base, "price_field_used": selected[0], "option_price_used": selected[1], **solved}
        results.append(row)
        eligible_for_premium.append(contract)
        if solved["calculation_status"] == "validated":
            validated_for_exposure.append({
                **contract, **solved, "model_name": model,
                "time_to_expiry": valuation.get("time_to_expiry_years"),
                "risk_free_rate": valuation.get("risk_free_rate"),
                "dividend_yield": valuation.get("dividend_yield", 0.0),
            })
    spot = valuation.get("spot_price", reference)
    premiums = premium_series(eligible_for_premium, spot, payload.get("strangle_width"))
    moves: list[dict[str, Any]] = []
    if premiums["atm_straddle"]:
        moves.append(expected_move(spot, "atm_straddle", combined_premium=premiums["atm_straddle"]["combined_premium"]))
    exposures = exposure_estimates(validated_for_exposure, spot)
    return {
        "engine": MODEL_VERSION,
        "as_of": _timestamp(as_of, "as_of").isoformat(),
        "contracts": results,
        "premium_series": premiums,
        "expected_moves": moves,
        "exposure_estimates": exposures,
        "assumptions": {"exposures": EXPOSURE_ASSUMPTIONS},
        "dry_run": bool(payload.get("dry_run", False)),
        **SAFETY,
    }


def execute(payload: dict[str, Any]) -> dict[str, Any]:
    operation = str(payload.get("operation", "analyze_chain"))
    if operation == "price":
        params = payload.get("parameters") or {}
        model = str(params.pop("model", "black_scholes_merton"))
        result = black_scholes_merton(**params) if model == "black_scholes_merton" else black_76(**params)
        return {"operation": operation, "model": model, "result": result, **SAFETY}
    if operation == "implied_volatility":
        return {"operation": operation, "result": implied_volatility(**(payload.get("parameters") or {})), **SAFETY}
    if operation == "replay":
        return {"operation": operation, "frames": replay_frames(payload.get("batches") or [], payload.get("replay_clocks") or []), **SAFETY}
    if operation == "analyze_chain":
        return analyze_chain(payload)
    raise AnalyticsError(f"unsupported operation: {operation}")


def _read_json(path: str) -> dict[str, Any]:
    raw = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise AnalyticsError("input JSON must be an object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="-", help="JSON input path, or - for stdin")
    parser.add_argument("--output", default="-", help="JSON output path, or - for stdout")
    parser.add_argument("--dry-run", action="store_true", help="record dry-run intent; calculations are always paper-only")
    args = parser.parse_args(argv)
    try:
        payload = _read_json(args.input)
        payload["dry_run"] = bool(args.dry_run or payload.get("dry_run"))
        result = execute(payload)
        result["dry_run"] = payload["dry_run"]
        serialized = json.dumps(result, indent=2, sort_keys=True, allow_nan=False)
        if args.output == "-":
            print(serialized)
        else:
            Path(args.output).write_text(serialized + "\n", encoding="utf-8")
        return 0
    except (AnalyticsError, json.JSONDecodeError, OSError, TypeError) as exc:
        error = {"status": "failed", "error": str(exc), "dry_run": bool(args.dry_run), **SAFETY}
        print(json.dumps(error, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
