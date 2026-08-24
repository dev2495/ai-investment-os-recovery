#!/usr/bin/env python3
"""GET-only Zerodha instruments, quotes, candles, and option-chain connector."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import subprocess
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from sync_zerodha_read_only import BASE_URL, keychain_token, psql, request_json, sql_literal


INDEX_IDENTIFIERS = {
    "NIFTY": "NSE:NIFTY 50",
    "BANKNIFTY": "NSE:NIFTY BANK",
    "FINNIFTY": "NSE:NIFTY FIN SERVICE",
    "MIDCPNIFTY": "NSE:NIFTY MID SELECT",
    "SENSEX": "BSE:SENSEX",
}
VALID_INTERVALS = {"minute", "3minute", "5minute", "10minute", "15minute", "30minute", "60minute", "day"}
ZERODHA_MARKET_TIMEZONE = ZoneInfo("Asia/Kolkata")


def canonical_instrument_type(exchange: str, broker_type: object, segment: object = None) -> str:
    """Map Zerodha instrument labels onto the warehouse security taxonomy."""
    value = str(broker_type or "").strip().upper()
    segment_value = str(segment or "").strip().upper()
    if segment_value in {"INDICES", "NSE-INDICES", "BSE-INDICES"}:
        return "index"
    if value in {"EQ", "BE", "BZ", "SM", "ST"}:
        return "equity"
    if value in {"CE", "PE"}:
        return "option"
    if value == "FUT":
        return "future"
    if value in {"INDEX", "INDICES"}:
        return "index"
    return value.lower() or ("equity" if exchange.upper() in {"NSE", "BSE"} else "unknown")


def as_number(value: object) -> str:
    if value in (None, ""):
        return ""
    try:
        return str(Decimal(str(value)))
    except InvalidOperation:
        return ""


def zerodha_timestamp_utc(value: object) -> str:
    """Treat Kite's timezone-less market timestamps as exchange-local IST."""
    parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZERODHA_MARKET_TIMEZONE)
    return parsed.astimezone(timezone.utc).isoformat()


def returned_id(raw: str, label: str) -> int:
    for line in raw.splitlines():
        candidate = line.strip()
        if candidate.isdigit():
            return int(candidate)
    raise RuntimeError(f"{label} insert did not return an id")


def query_json(query: str) -> list[dict]:
    raw = psql(
        "SELECT coalesce(json_agg(row_to_json(rows)),'[]'::json)::text "
        f"FROM ({query}) rows"
    )
    parsed = json.loads(raw or "[]")
    return parsed if isinstance(parsed, list) else []


def psql_stdin(script: str, timeout: int = 180) -> None:
    env = os.environ.copy()
    env.setdefault("PGPASSWORD", os.environ.get("AI_OS_POSTGRES_PASSWORD", "ai_os_local_dev_change_me"))
    port = os.environ.get("AI_OS_POSTGRES_PORT", "54329")
    candidates = [
        ["psql", "-h", "127.0.0.1", "-p", port, "-U", "ai_os", "-d", "ai_os", "-v", "ON_ERROR_STOP=1", "-f", "-"],
        ["/opt/homebrew/bin/docker", "exec", "-i", "ai_os_postgres", "psql", "-U", "ai_os", "-d", "ai_os", "-v", "ON_ERROR_STOP=1", "-f", "-"],
    ]
    errors: list[str] = []
    for command in candidates:
        try:
            completed = subprocess.run(
                command, input=script, text=True, capture_output=True,
                check=False, timeout=timeout, env=env,
            )
        except OSError as exc:
            errors.append(f"{command[0]}: {exc}")
            continue
        if completed.returncode == 0:
            return
        errors.append((completed.stderr or completed.stdout).strip()[-2000:])
    raise RuntimeError("; ".join(errors))


def request_bytes(path: str, api_key: str, access_token: str) -> bytes:
    request = urllib.request.Request(
        BASE_URL + path,
        headers={
            "Accept": "text/csv,application/json",
            "Accept-Encoding": "identity",
            "Authorization": f"token {api_key}:{access_token}",
            "X-Kite-Version": "3",
            "User-Agent": "AI-Investment-OS/1.0 read-only connector",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def sync_instruments(api_key: str, access_token: str, exchanges: list[str]) -> dict:
    run_key = "zerodha-instruments-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    psql(
        "INSERT INTO market.zerodha_instrument_sync_runs "
        "(run_key,status,exchange_scope,created_by) VALUES ("
        f"{sql_literal(run_key)},'started',ARRAY[{','.join(sql_literal(x) for x in exchanges)}]::text[],"
        "'Market Data Engineer')"
    )
    all_rows: list[dict] = []
    for exchange in exchanges:
        suffix = "" if exchange == "ALL" else f"/{urllib.parse.quote(exchange)}"
        body = request_bytes("/instruments" + suffix, api_key, access_token)
        text = body.decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(text)))
        all_rows.extend(row for row in rows if row.get("instrument_token") and row.get("exchange"))
    if not all_rows:
        raise RuntimeError("Zerodha instrument dump returned no rows")

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    for row in all_rows:
        writer.writerow([
            row.get("instrument_token"), row.get("exchange_token"), row.get("tradingsymbol"),
            row.get("name"), as_number(row.get("last_price")), row.get("expiry") or "",
            as_number(row.get("strike")), as_number(row.get("tick_size")), row.get("lot_size") or "",
            row.get("instrument_type"), row.get("segment"), row.get("exchange"),
        ])
    exchange_values = ",".join(sql_literal(x) for x in exchanges if x != "ALL")
    inactive_where = "true" if "ALL" in exchanges else f"exchange IN ({exchange_values})"
    script = (
        "BEGIN;\n"
        "CREATE TEMP TABLE zerodha_stage (instrument_token bigint,exchange_token bigint,trading_symbol text,name text,"
        "last_price numeric,expiry date,strike numeric,tick_size numeric,lot_size integer,instrument_type text,segment text,exchange text) ON COMMIT DROP;\n"
        "COPY zerodha_stage FROM STDIN WITH (FORMAT csv, NULL '');\n"
        + buffer.getvalue()
        + "\\.\n"
        f"UPDATE market.zerodha_instruments SET active=false WHERE {inactive_where};\n"
        "INSERT INTO market.zerodha_instruments "
        "(instrument_token,exchange_token,trading_symbol,name,last_price,expiry,strike,tick_size,lot_size,instrument_type,segment,exchange,active,source_payload) "
        "SELECT instrument_token,exchange_token,trading_symbol,name,last_price,expiry,strike,tick_size,lot_size,instrument_type,segment,exchange,true,'{}'::jsonb FROM zerodha_stage "
        "ON CONFLICT (instrument_token) DO UPDATE SET exchange_token=EXCLUDED.exchange_token,trading_symbol=EXCLUDED.trading_symbol,"
        "name=EXCLUDED.name,last_price=EXCLUDED.last_price,expiry=EXCLUDED.expiry,strike=EXCLUDED.strike,tick_size=EXCLUDED.tick_size,"
        "lot_size=EXCLUDED.lot_size,instrument_type=EXCLUDED.instrument_type,segment=EXCLUDED.segment,exchange=EXCLUDED.exchange,"
        "active=true,last_seen_at=now();\n"
        f"UPDATE market.zerodha_instrument_sync_runs SET status='completed',rows_seen={len(all_rows)},rows_upserted={len(all_rows)},finished_at=now() WHERE run_key={sql_literal(run_key)};\n"
        "COMMIT;\n"
    )
    psql_stdin(script)
    return {"status": "completed", "run_key": run_key, "rows": len(all_rows), "exchanges": exchanges}


def quote_batches(api_key: str, access_token: str, identifiers: list[str]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    unique = list(dict.fromkeys(identifier for identifier in identifiers if ":" in identifier))
    for offset in range(0, len(unique), 200):
        query = urllib.parse.urlencode([("i", item) for item in unique[offset : offset + 200]])
        payload = request_json("GET", "/quote?" + query, api_key=api_key, access_token=access_token)
        data = payload.get("data") if isinstance(payload, dict) else {}
        if isinstance(data, dict):
            result.update({str(key): value for key, value in data.items() if isinstance(value, dict)})
    return result


def relevant_identifiers() -> list[str]:
    rows = query_json(
        """
        WITH latest_positions AS (
            SELECT DISTINCT ON (upper(symbol)) upper(symbol) symbol, coalesce(exchange,'NSE') exchange
            FROM portfolio.positions ORDER BY upper(symbol), as_of DESC
        )
        SELECT exchange||':'||symbol identifier FROM latest_positions
        UNION
        SELECT exchange||':'||upper(symbol) FROM research.v_watchlist_board WHERE status='active'
        """
    )
    identifiers = [str(row.get("identifier") or "") for row in rows]
    identifiers.extend(INDEX_IDENTIFIERS.values())
    return list(dict.fromkeys(item for item in identifiers if ":" in item))


def persist_quotes(quotes: dict[str, dict]) -> int:
    values: list[str] = []
    now_iso = datetime.now(timezone.utc).isoformat()
    for identifier, row in quotes.items():
        exchange, symbol = identifier.split(":", 1)
        price = row.get("last_price")
        if price is None:
            continue
        previous = (row.get("ohlc") or {}).get("close") if isinstance(row.get("ohlc"), dict) else None
        change = ((float(price)-float(previous))/float(previous)*100) if previous not in (None, 0) else None
        quote_ts = zerodha_timestamp_utc(row["timestamp"]) if row.get("timestamp") else now_iso
        raw_payload = dict(row)
        raw_payload["ai_os_timestamp_basis"] = "exchange_local_ist" if row.get("timestamp") else "receipt_utc"
        raw_payload["ai_os_received_at"] = now_iso
        values.append(
            "("
            f"'zerodha_live','Zerodha',{sql_literal(identifier)},{sql_literal(symbol)},"
            f"{sql_literal(exchange)},NULL,'INR',{float(price)},{'NULL' if change is None else change},"
            f"{sql_literal(quote_ts)}::timestamptz,{sql_literal(json.dumps(raw_payload,separators=(',',':'),default=str))}::jsonb"
            ")"
        )
    for offset in range(0, len(values), 100):
        psql(
            "INSERT INTO market.price_quotes "
            "(source_key,provider,provider_symbol,symbol,exchange,description,currency,price,change_percent,quote_ts,raw_payload) VALUES "
            + ",".join(values[offset : offset + 100])
            + " ON CONFLICT (source_key,provider_symbol,quote_ts) DO UPDATE SET "
              "price=EXCLUDED.price,change_percent=EXCLUDED.change_percent,raw_payload=EXCLUDED.raw_payload"
        )
    return len(values)


def sync_quotes(api_key: str, access_token: str) -> dict:
    identifiers = relevant_identifiers()
    quotes = quote_batches(api_key, access_token, identifiers)
    rows = persist_quotes(quotes)
    return {"status": "completed", "requested": len(identifiers), "rows": rows}


def resolve_instrument(exchange: str, symbol: str) -> dict:
    rows = query_json(
        "SELECT instrument_token,exchange,trading_symbol,name,instrument_type,segment "
        "FROM market.zerodha_instruments "
        f"WHERE exchange={sql_literal(exchange.upper())} AND upper(trading_symbol)={sql_literal(symbol.upper())} "
        "ORDER BY active DESC,last_seen_at DESC LIMIT 1"
    )
    if not rows:
        raise ValueError(f"instrument not cached: {exchange}:{symbol}; run instrument sync first")
    return rows[0]


def sync_historical(
    api_key: str, access_token: str, exchange: str, symbol: str,
    date_from: str, date_to: str, interval: str,
) -> dict:
    if interval not in VALID_INTERVALS:
        raise ValueError(f"unsupported interval: {interval}")
    canonical_timeframe = {"day": "1d", "60minute": "1h", "15minute": "15m", "5minute": "5m"}.get(interval, interval)
    instrument = resolve_instrument(exchange, symbol)
    token = int(instrument["instrument_token"])
    query = urllib.parse.urlencode({"from": date_from, "to": date_to, "oi": "1"})
    payload = request_json(
        "GET", f"/instruments/historical/{token}/{interval}?{query}",
        api_key=api_key, access_token=access_token,
    )
    data = payload.get("data") if isinstance(payload, dict) else {}
    candles = data.get("candles") if isinstance(data, dict) else []
    if not isinstance(candles, list):
        candles = []
    source_id = returned_id(psql(
        "INSERT INTO core.source_systems (name,source_type,location,sensitivity,status,notes) VALUES "
        "('Zerodha Kite read-only market data','broker_market_data_api','https://api.kite.trade','private','active',"
        "'GET-only instruments, quotes and historical candles; broker writes are absent.') "
        "ON CONFLICT (name) DO UPDATE SET status='active' RETURNING id"
    ), "source system")
    instrument_type = canonical_instrument_type(
        exchange, instrument.get("instrument_type"), instrument.get("segment")
    )
    symbol_id = returned_id(psql(
        "INSERT INTO trading.symbols (symbol,exchange,instrument_type,name,currency,active) VALUES ("
        f"{sql_literal(symbol.upper())},{sql_literal(exchange.upper())},{sql_literal(instrument_type)},"
        f"{sql_literal(instrument.get('name'))},'INR',true) "
        "ON CONFLICT (symbol,exchange,instrument_type) DO UPDATE SET name=EXCLUDED.name,active=true RETURNING id"
    ), "symbol")
    values: list[str] = []
    for candle in candles:
        if not isinstance(candle, list) or len(candle) < 6:
            continue
        values.append(
            f"({sql_literal(candle[0])}::timestamptz,{int(symbol_id)},{sql_literal(canonical_timeframe)},"
            f"{candle[1]},{candle[2]},{candle[3]},{candle[4]},{candle[5]},{int(source_id)})"
        )
    for offset in range(0, len(values), 200):
        psql(
            "INSERT INTO trading.ohlcv (ts,symbol_id,timeframe,open,high,low,close,volume,source_system_id) VALUES "
            + ",".join(values[offset : offset + 200])
            + " ON CONFLICT (ts,symbol_id,timeframe) DO UPDATE SET "
              "open=EXCLUDED.open,high=EXCLUDED.high,low=EXCLUDED.low,close=EXCLUDED.close,"
              "volume=EXCLUDED.volume,source_system_id=EXCLUDED.source_system_id"
        )
    committed = query_json(
        "SELECT count(*)::integer AS committed_count FROM trading.ohlcv "
        f"WHERE symbol_id={symbol_id} AND timeframe={sql_literal(canonical_timeframe)} "
        f"AND ts::date BETWEEN {sql_literal(date_from)}::date AND {sql_literal(date_to)}::date "
        f"AND source_system_id={source_id}"
    )
    committed_rows = int(committed[0]["committed_count"]) if committed else 0
    if values and committed_rows == 0:
        raise RuntimeError(f"historical candles were returned but none committed for {exchange}:{symbol}")
    return {
        "status": "completed",
        "symbol": symbol,
        "exchange": exchange,
        "interval": interval,
        "timeframe": canonical_timeframe,
        "symbol_id": symbol_id,
        "instrument_type": instrument_type,
        "api_rows": len(values),
        "rows": committed_rows,
    }


def sync_options(
    api_key: str,
    access_token: str,
    underlyings: list[str],
    strike_pairs: int,
    expiry_count: int,
) -> dict:
    collected_at = datetime.now(timezone.utc).isoformat()
    stored = 0
    summaries: list[dict] = []
    for underlying in underlyings:
        normalized = underlying.upper()
        spot_identifier = INDEX_IDENTIFIERS.get(normalized)
        if not spot_identifier:
            continue
        spot_rows = quote_batches(api_key, access_token, [spot_identifier])
        spot_payload = spot_rows.get(spot_identifier) or {}
        spot = spot_payload.get("last_price")
        if spot is None:
            summaries.append({"underlying": normalized, "status": "spot_unavailable"})
            continue
        instruments = query_json(
            "WITH selected_expiries AS (SELECT DISTINCT expiry FROM market.zerodha_instruments "
            f"WHERE active AND name={sql_literal(normalized)} AND instrument_type IN ('CE','PE') "
            f"AND expiry>=current_date ORDER BY expiry LIMIT {max(1, min(int(expiry_count), 6))}) "
            "SELECT instrument_token,trading_symbol,exchange,"
            "market.zerodha_instruments.expiry AS expiry,strike,instrument_type "
            "FROM market.zerodha_instruments JOIN selected_expiries USING (expiry) "
            f"WHERE active AND name={sql_literal(normalized)} AND instrument_type IN ('CE','PE') "
            "ORDER BY strike,instrument_type"
        )
        selected: list[dict] = []
        for expiry in sorted({str(row.get("expiry")) for row in instruments if row.get("expiry")}):
            expiry_rows = [row for row in instruments if str(row.get("expiry")) == expiry]
            strikes = sorted(
                {float(row["strike"]) for row in expiry_rows if row.get("strike") is not None},
                key=lambda value: abs(value - float(spot)),
            )
            selected_strikes = set(strikes[: max(2, strike_pairs)])
            selected.extend(
                row for row in expiry_rows
                if float(row.get("strike") or 0) in selected_strikes
            )
        identifiers = [f"{row['exchange']}:{row['trading_symbol']}" for row in selected]
        quotes = quote_batches(api_key, access_token, identifiers)
        values: list[str] = []
        missing_timestamps = 0
        for instrument in selected:
            identifier = f"{instrument['exchange']}:{instrument['trading_symbol']}"
            quote = quotes.get(identifier) or {}
            source_timestamp = quote.get("timestamp") or spot_payload.get("timestamp")
            try:
                source_observed_at = zerodha_timestamp_utc(source_timestamp)
            except (TypeError, ValueError):
                missing_timestamps += 1
                continue
            depth = quote.get("depth") if isinstance(quote.get("depth"), dict) else {}
            buy = depth.get("buy") if isinstance(depth, dict) else []
            sell = depth.get("sell") if isinstance(depth, dict) else []
            bid = buy[0].get("price") if buy and isinstance(buy[0], dict) else None
            ask = sell[0].get("price") if sell and isinstance(sell[0], dict) else None
            canonical = json.dumps(
                {"contract_quote": quote, "spot_quote": spot_payload, "collected_at": collected_at},
                sort_keys=True, separators=(",", ":"), default=str,
            )
            payload_hash = hashlib.sha256(canonical.encode()).hexdigest()
            values.append(
                "("
                f"{sql_literal(source_observed_at)}::timestamptz,'Zerodha','zerodha_live_connector',"
                f"{sql_literal(instrument['exchange'])},{sql_literal(normalized)},{sql_literal(instrument['expiry'])}::date,"
                f"{instrument['strike']},{sql_literal(instrument['instrument_type'])},{sql_literal(instrument['instrument_token'])},"
                f"{sql_literal(instrument['trading_symbol'])},{spot},{quote.get('last_price') or 'NULL'},"
                f"{bid if bid is not None else 'NULL'},{ask if ask is not None else 'NULL'},"
                f"{quote.get('volume') or 0},{quote.get('oi') or 0},NULL,NULL,NULL,NULL,NULL,"
                f"{sql_literal(canonical)}::jsonb,{sql_literal(payload_hash)},false"
                ")"
            )
        if values:
            psql(
                "INSERT INTO trading.option_chain_snapshots "
                "(observed_at,provider,source_connector_key,exchange,underlying,expiry,strike,option_type,"
                "instrument_token,trading_symbol,spot_price,last_price,bid_price,ask_price,volume,open_interest,"
                "implied_volatility,delta,gamma,theta,vega,source_payload,payload_hash,broker_write_allowed) VALUES "
                + ",".join(values)
                + " ON CONFLICT (provider,observed_at,exchange,underlying,expiry,strike,option_type) DO UPDATE SET "
                  "last_price=EXCLUDED.last_price,bid_price=EXCLUDED.bid_price,ask_price=EXCLUDED.ask_price,"
                  "volume=EXCLUDED.volume,open_interest=EXCLUDED.open_interest,source_payload=EXCLUDED.source_payload,"
                  "payload_hash=EXCLUDED.payload_hash"
            )
        stored += len(values)
        summaries.append({
            "underlying": normalized, "status": "completed", "spot": spot,
            "expiries": sorted({str(row.get("expiry")) for row in selected if row.get("expiry")}),
            "contracts": len(values),
            "missing_source_timestamps": missing_timestamps,
            "iv_and_greeks": "not_provided_by_kite",
        })
    return {"status": "completed", "collected_at": collected_at, "rows": stored, "underlyings": summaries}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--modes", nargs="+", choices=["instruments", "quotes", "options", "historical"], default=["quotes", "options"])
    parser.add_argument("--exchanges", nargs="+", default=["ALL"])
    parser.add_argument("--underlyings", nargs="+", default=["NIFTY", "BANKNIFTY"])
    parser.add_argument("--strike-pairs", type=int, default=24)
    parser.add_argument("--expiry-count", type=int, default=3)
    parser.add_argument("--historical-exchange")
    parser.add_argument("--historical-symbol")
    parser.add_argument("--from-date")
    parser.add_argument("--to-date")
    parser.add_argument("--interval", default="day")
    parser.add_argument("--check-config", action="store_true")
    args = parser.parse_args()
    api_key = os.environ.get("AI_OS_ZERODHA_API_KEY", "").strip()
    api_secret = os.environ.get("AI_OS_ZERODHA_API_SECRET", "").strip()
    access_token = keychain_token()
    status = {
        "status": "configured" if api_key and api_secret and access_token else "needs_credentials_or_daily_login",
        "api_key_configured": bool(api_key), "api_secret_configured": bool(api_secret),
        "daily_access_token_available": bool(access_token),
        "broker_write_allowed": False,
    }
    if args.check_config or status["status"] != "configured":
        print(json.dumps(status, indent=2))
        return 0 if status["status"] == "configured" else 2
    results: dict[str, object] = {"status": "completed", "broker_write_allowed": False}
    try:
        if "instruments" in args.modes:
            results["instruments"] = sync_instruments(api_key, access_token, [item.upper() for item in args.exchanges])
        if "quotes" in args.modes:
            results["quotes"] = sync_quotes(api_key, access_token)
        if "options" in args.modes:
            results["options"] = sync_options(
                api_key,
                access_token,
                args.underlyings,
                max(2, min(args.strike_pairs, 60)),
                max(1, min(args.expiry_count, 6)),
            )
        if "historical" in args.modes:
            required = [args.historical_exchange, args.historical_symbol, args.from_date, args.to_date]
            if not all(required):
                raise ValueError("historical mode requires exchange, symbol, from-date, and to-date")
            results["historical"] = sync_historical(
                api_key, access_token, args.historical_exchange, args.historical_symbol,
                args.from_date, args.to_date, args.interval,
            )
    except Exception as exc:
        results.update({"status": "failed", "error": f"{type(exc).__name__}: {exc}"[:1500]})
    print(json.dumps(results, indent=2, default=str))
    return 0 if results["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
