"""Exchange-aware, read-only market-price resolution for valuation inputs."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterable
from zoneinfo import ZoneInfo


INDIA_TZ = ZoneInfo("Asia/Kolkata")
SESSION_OPEN = time(9, 15)
SESSION_CLOSE = time(15, 30)
QUALIFIED_TIMESTAMP_BASES = frozenset({
    "exchange_local_ist",
    "exchange_timestamp",
    "exchange_utc",
    "last_trade_local_ist",
    "provider_exchange_time",
})


def _timestamp(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _holiday_dates(rows: Iterable[dict[str, Any]], exchange: str) -> set[date]:
    output: set[date] = set()
    for row in rows:
        if str(row.get("exchange") or exchange).upper() != exchange:
            continue
        if str(row.get("session_status") or "closed").lower() not in {"closed", "holiday"}:
            continue
        try:
            output.add(date.fromisoformat(str(row.get("holiday_date"))[:10]))
        except ValueError:
            continue
    return output


def _is_session_day(day: date, holidays: set[date]) -> bool:
    return day.weekday() < 5 and day not in holidays


def expected_session_date(now_local: datetime, holidays: set[date]) -> date:
    candidate = now_local.date()
    if _is_session_day(candidate, holidays) and now_local.time() >= SESSION_OPEN:
        return candidate
    candidate -= timedelta(days=1)
    while not _is_session_day(candidate, holidays):
        candidate -= timedelta(days=1)
    return candidate


def resolve_market_price(
    rows: Iterable[dict[str, Any]],
    *,
    symbol: str,
    exchange: str,
    holidays: Iterable[dict[str, Any]] = (),
    now: datetime | None = None,
    intraday_max_age_minutes: int = 15,
    closing_quote_max_lag_minutes: int = 15,
    closing_quote_max_lead_minutes: int = 5,
) -> dict[str, Any] | None:
    """Resolve an exact exchange/symbol quote and make freshness explicit.

    The resolver never calls a broker and never mutates state. It also catches
    the historic Kite ingest bug where a timezone-less IST timestamp was stored
    as UTC and therefore appears roughly 5.5 hours after its receipt time.
    """
    wanted_symbol = symbol.strip().upper()
    wanted_exchange = exchange.strip().upper()
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    now_local = now_utc.astimezone(INDIA_TZ)
    closed_days = _holiday_dates(holidays, wanted_exchange)
    expected_day = expected_session_date(now_local, closed_days)
    candidates: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("symbol") or "").strip().upper() != wanted_symbol:
            continue
        if str(row.get("exchange") or "").strip().upper() != wanted_exchange:
            continue
        if row.get("price") in (None, ""):
            continue
        quote_ts = _timestamp(row.get("quote_ts"))
        if not quote_ts:
            continue
        received_at = _timestamp(row.get("received_at") or row.get("created_at"))
        age_minutes = (now_utc - quote_ts).total_seconds() / 60
        quote_local = quote_ts.astimezone(INDIA_TZ)
        timestamp_basis = str(row.get("timestamp_basis") or "").strip().lower()
        reason = None
        if timestamp_basis not in QUALIFIED_TIMESTAMP_BASES:
            status = "invalid_timestamp"
            reason = "quote lacks a qualified exchange or trade timestamp"
        elif quote_ts > now_utc + timedelta(minutes=5):
            status = "invalid_timestamp"
            reason = "quote timestamp is in the future"
        elif received_at and quote_ts > received_at + timedelta(minutes=5):
            status = "invalid_timestamp"
            reason = "quote timestamp is later than receipt time; exchange-time normalization failed"
        elif quote_local.date() != expected_day:
            status = "stale"
            reason = f"latest quote is not from expected exchange session {expected_day.isoformat()}"
        elif (
            _is_session_day(now_local.date(), closed_days)
            and SESSION_OPEN <= now_local.time() <= SESSION_CLOSE
            and age_minutes > max(1, int(intraday_max_age_minutes))
        ):
            status = "stale"
            reason = "latest quote exceeded the live-session freshness ceiling"
        elif not (
            _is_session_day(now_local.date(), closed_days)
            and SESSION_OPEN <= now_local.time() <= SESSION_CLOSE
        ):
            closing_floor = (
                datetime.combine(expected_day, SESSION_CLOSE, INDIA_TZ)
                - timedelta(minutes=max(1, int(closing_quote_max_lag_minutes)))
            )
            closing_ceiling = (
                datetime.combine(expected_day, SESSION_CLOSE, INDIA_TZ)
                + timedelta(minutes=max(0, int(closing_quote_max_lead_minutes)))
            )
            if not closing_floor <= quote_local <= closing_ceiling:
                status = "stale"
                reason = "latest quote is not a qualified closing-session observation"
            else:
                status = "current"
        else:
            status = "current"
        try:
            priority = max(1, int(row.get("source_priority") or 1))
        except (TypeError, ValueError):
            priority = 1
        approved = row.get("approved_for_valuation") is True
        write_locked = row.get("broker_write_allowed") is False
        provider = str(row.get("provider") or "").strip()
        is_zerodha = provider.casefold() == "zerodha"
        mapping_verified = (
            row.get("instrument_token") not in (None, "")
            and str(row.get("mapping_status") or "") == "verified_zerodha_instrument"
        )
        entitlement_key = str(row.get("provider_entitlement_key") or "").strip()
        provider_authorized = (
            mapping_verified
            if is_zerodha
            else row.get("provider_entitled") is True and bool(entitlement_key)
        )
        candidates.append({
            "row": row,
            "quote_ts": quote_ts,
            "received_at": received_at,
            "age_minutes": age_minutes,
            "freshness_status": status,
            "freshness_reason": reason,
            "source_priority": priority,
            "approved": approved,
            "provider_authorized": provider_authorized,
            "decision_usable": status == "current" and approved and provider_authorized and write_locked,
        })
    if not candidates:
        return None
    usable = [candidate for candidate in candidates if candidate["decision_usable"]]
    if usable:
        selected = min(usable, key=lambda item: (item["source_priority"], -item["quote_ts"].timestamp()))
    else:
        selected = max(candidates, key=lambda item: item["quote_ts"])
    row = selected["row"]
    quote_ts = selected["quote_ts"]
    received_at = selected["received_at"]
    age_minutes = selected["age_minutes"]
    status = selected["freshness_status"]
    reason = selected["freshness_reason"]
    priority = selected["source_priority"]
    primary = [candidate for candidate in candidates if candidate["source_priority"] == 1]
    primary_status = None
    if primary:
        primary_status = max(primary, key=lambda item: item["quote_ts"])["freshness_status"]
    fallback_used = priority > 1
    if fallback_used and not reason:
        if str(row.get("provider") or "").casefold() == "zerodha":
            reason = "stored Zerodha quote used because the primary live quote was unavailable or stale"
        else:
            reason = "entitled secondary quote used because the primary Zerodha quote was unavailable or stale"
    if status == "current" and not selected["approved"]:
        reason = "quote is not explicitly approved for valuation"
    elif status == "current" and not selected["provider_authorized"]:
        reason = "quote provider is not explicitly entitled for valuation"
    elif status == "current" and row.get("broker_write_allowed") is not False:
        reason = "quote does not carry the explicit broker-write lock required for valuation"
    return {
        "value": float(row["price"]),
        "currency": str(row.get("currency") or "INR"),
        "as_of": quote_ts.isoformat(),
        "quote_timestamp": quote_ts.isoformat(),
        "received_at": received_at.isoformat() if received_at else None,
        "age_minutes": round(age_minutes, 2),
        "age_days": max(0, int(age_minutes // 1440)),
        "provider": row.get("provider") or row.get("source_key") or "Market warehouse",
        "provider_symbol": row.get("provider_symbol") or f"{wanted_exchange}:{wanted_symbol}",
        "symbol": wanted_symbol,
        "exchange": wanted_exchange,
        "source_key": row.get("source_key"),
        "source_priority": priority,
        "fallback_used": fallback_used,
        "primary_quote_status": primary_status or "unavailable",
        "delay_status": "fallback_current" if fallback_used and status == "current" else status,
        "instrument_token": row.get("instrument_token"),
        "mapping_status": row.get("mapping_status") or "exact_exchange_symbol",
        "source": {
            "quote_id": row.get("id"),
            "source_key": row.get("source_key"),
            "provider_symbol": row.get("provider_symbol"),
            "quote_ts": quote_ts.isoformat(),
            "received_at": received_at.isoformat() if received_at else None,
            "instrument_token": row.get("instrument_token"),
            "source_mode": row.get("source_mode"),
            "mapping_status": row.get("mapping_status"),
            "timestamp_basis": row.get("timestamp_basis"),
            "provider_entitlement_key": row.get("provider_entitlement_key"),
        },
        "source_class": row.get("source_class") or "market_fact",
        "verification_status": (
            "source_linked"
            if selected["approved"] and selected["provider_authorized"]
            else "unapproved_source"
        ),
        "provider_entitled": bool(selected["provider_authorized"]),
        "freshness_status": status,
        "freshness_reason": reason,
        "expected_session_date": expected_day.isoformat(),
        "decision_usable": bool(selected["decision_usable"]),
        "broker_write_allowed": False,
    }
