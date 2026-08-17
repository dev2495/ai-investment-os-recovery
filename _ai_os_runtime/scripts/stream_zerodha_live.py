#!/usr/bin/env python3
"""Read-only Zerodha WebSocket stream with durable latest and minute state."""

from __future__ import annotations

import argparse
import json
import os
import queue
import signal
import subprocess
import threading
import time
from datetime import datetime, timezone
from typing import Any

import psycopg
from kiteconnect import KiteTicker

from sync_zerodha_read_only import keychain_token, request_json


PROVIDER = "Zerodha"
SOURCE_KEY = "zerodha_websocket"
DB_DSN = os.environ.get("AI_OS_DATABASE_DSN", "").strip()
FLUSH_SECONDS = max(0.5, float(os.environ.get("AI_OS_ZERODHA_STREAM_FLUSH_SECONDS", "2")))
HEARTBEAT_SECONDS = max(10, int(os.environ.get("AI_OS_ZERODHA_STREAM_HEARTBEAT_SECONDS", "30")))
RELOAD_SECONDS = max(60, int(os.environ.get("AI_OS_ZERODHA_STREAM_RELOAD_SECONDS", "300")))
ACCOUNT_REFRESH_SECONDS = max(120, int(os.environ.get("AI_OS_ZERODHA_ACCOUNT_REFRESH_SECONDS", "300")))
OPTIONS_REFRESH_SECONDS = max(120, int(os.environ.get("AI_OS_ZERODHA_OPTIONS_REFRESH_SECONDS", "300")))
RETENTION_DAYS = max(7, int(os.environ.get("AI_OS_ZERODHA_MINUTE_RETENTION_DAYS", "45")))

UPSERT_LIVE_SQL = """
INSERT INTO market.live_quote_state (
    provider,instrument_token,provider_symbol,symbol,exchange,instrument_type,
    last_price,last_quantity,average_price,volume,buy_quantity,sell_quantity,
    open_interest,open_interest_high,open_interest_low,bid_price,ask_price,
    day_open,day_high,day_low,previous_close,change_percent,
    exchange_timestamp,last_trade_timestamp,received_at,source_mode,raw_payload,
    broker_write_allowed
) VALUES (
    %(provider)s,%(instrument_token)s,%(provider_symbol)s,%(symbol)s,%(exchange)s,%(instrument_type)s,
    %(last_price)s,%(last_quantity)s,%(average_price)s,%(volume)s,%(buy_quantity)s,%(sell_quantity)s,
    %(open_interest)s,%(open_interest_high)s,%(open_interest_low)s,%(bid_price)s,%(ask_price)s,
    %(day_open)s,%(day_high)s,%(day_low)s,%(previous_close)s,%(change_percent)s,
    %(exchange_timestamp)s,%(last_trade_timestamp)s,%(received_at)s,'websocket_full',%(raw_payload)s::jsonb,false
) ON CONFLICT (provider,instrument_token) DO UPDATE SET
    provider_symbol=EXCLUDED.provider_symbol,symbol=EXCLUDED.symbol,exchange=EXCLUDED.exchange,
    instrument_type=EXCLUDED.instrument_type,last_price=EXCLUDED.last_price,
    last_quantity=EXCLUDED.last_quantity,average_price=EXCLUDED.average_price,
    volume=EXCLUDED.volume,buy_quantity=EXCLUDED.buy_quantity,sell_quantity=EXCLUDED.sell_quantity,
    open_interest=EXCLUDED.open_interest,open_interest_high=EXCLUDED.open_interest_high,
    open_interest_low=EXCLUDED.open_interest_low,bid_price=EXCLUDED.bid_price,
    ask_price=EXCLUDED.ask_price,day_open=EXCLUDED.day_open,day_high=EXCLUDED.day_high,
    day_low=EXCLUDED.day_low,previous_close=EXCLUDED.previous_close,
    change_percent=EXCLUDED.change_percent,exchange_timestamp=EXCLUDED.exchange_timestamp,
    last_trade_timestamp=EXCLUDED.last_trade_timestamp,received_at=EXCLUDED.received_at,
    source_mode=EXCLUDED.source_mode,raw_payload=EXCLUDED.raw_payload
WHERE market.live_quote_state.received_at <= EXCLUDED.received_at
"""

UPSERT_MINUTE_SQL = """
INSERT INTO market.live_quote_minute_snapshots (
    provider,instrument_token,minute_ts,provider_symbol,symbol,exchange,
    open_price,high_price,low_price,close_price,volume,open_interest,tick_count,
    broker_write_allowed
) VALUES (
    %(provider)s,%(instrument_token)s,date_trunc('minute',%(received_at)s::timestamptz),
    %(provider_symbol)s,%(symbol)s,%(exchange)s,
    %(last_price)s,%(last_price)s,%(last_price)s,%(last_price)s,
    %(volume)s,%(open_interest)s,1,false
) ON CONFLICT (provider,instrument_token,minute_ts) DO UPDATE SET
    high_price=greatest(market.live_quote_minute_snapshots.high_price,EXCLUDED.high_price),
    low_price=least(market.live_quote_minute_snapshots.low_price,EXCLUDED.low_price),
    close_price=EXCLUDED.close_price,volume=EXCLUDED.volume,
    open_interest=EXCLUDED.open_interest,
    tick_count=market.live_quote_minute_snapshots.tick_count+1,updated_at=now()
"""

UPSERT_COMPATIBLE_QUOTE_SQL = """
INSERT INTO market.price_quotes (
    source_key,provider,provider_symbol,symbol,exchange,description,currency,
    price,change_percent,quote_ts,raw_payload
) VALUES (
    %(source_key)s,%(provider)s,%(provider_symbol)s,%(symbol)s,%(exchange)s,
    %(instrument_type)s,'INR',%(last_price)s,%(change_percent)s,
    date_trunc('minute',%(received_at)s::timestamptz),%(raw_payload)s::jsonb
) ON CONFLICT (source_key,provider_symbol,quote_ts) DO UPDATE SET
    price=EXCLUDED.price,change_percent=EXCLUDED.change_percent,
    raw_payload=EXCLUDED.raw_payload,created_at=now()
"""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def redact_error(value: object, *secrets: str) -> str:
    text = f"{type(value).__name__}: {value}"
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[redacted]")
    return text[:1500]


def database() -> psycopg.Connection:
    if DB_DSN:
        return psycopg.connect(DB_DSN, autocommit=False)
    return psycopg.connect(
        host=os.environ.get("AI_OS_POSTGRES_HOST", "127.0.0.1"),
        port=int(os.environ.get("AI_OS_POSTGRES_PORT", "54329")),
        user=os.environ.get("AI_OS_POSTGRES_USER", "ai_os"),
        password=os.environ.get("AI_OS_POSTGRES_PASSWORD", "ai_os_local_dev_change_me"),
        dbname=os.environ.get("AI_OS_POSTGRES_DB", "ai_os"),
        autocommit=False,
    )


def query_subscriptions(connection: psycopg.Connection) -> dict[int, dict[str, Any]]:
    query = """
    WITH desired AS (
        SELECT DISTINCT upper(symbol) AS symbol, upper(coalesce(exchange,'NSE')) AS exchange, 1 AS priority
        FROM portfolio.positions
        WHERE as_of >= (SELECT max(as_of)-interval '1 day' FROM portfolio.positions)
          AND coalesce(quantity,0)<>0
        UNION
        SELECT DISTINCT upper(symbol),upper(coalesce(exchange,'NSE')),2
        FROM research.v_watchlist_board WHERE status='active'
    ), resolved AS (
        SELECT DISTINCT ON (instrument.instrument_token)
               instrument.instrument_token,instrument.exchange,
               instrument.trading_symbol,instrument.instrument_type,desired.priority
        FROM desired
        JOIN market.zerodha_instruments instrument
          ON instrument.active
         AND upper(instrument.trading_symbol)=desired.symbol
         AND (upper(instrument.exchange)=desired.exchange
              OR (desired.exchange='NSE' AND instrument.exchange IN ('NSE','BSE')))
        ORDER BY instrument.instrument_token,desired.priority,
                 CASE WHEN upper(instrument.exchange)=desired.exchange THEN 0 ELSE 1 END
    ), indices AS (
        SELECT instrument_token,exchange,trading_symbol,instrument_type,0 AS priority
        FROM market.zerodha_instruments
        WHERE active AND exchange IN ('NSE','BSE')
          AND trading_symbol IN ('NIFTY 50','NIFTY BANK','NIFTY FIN SERVICE','SENSEX')
    ), options AS (
        SELECT instrument.instrument_token,instrument.exchange,
               instrument.trading_symbol,instrument.instrument_type,3 AS priority
        FROM trading.v_latest_option_chain chain
        JOIN market.zerodha_instruments instrument
          ON instrument.instrument_token=chain.instrument_token::bigint
        WHERE instrument.active
        ORDER BY chain.underlying,chain.expiry,abs(chain.strike-coalesce(chain.spot_price,chain.strike)),
                 chain.option_type
        LIMIT 240
    )
    SELECT DISTINCT ON (instrument_token)
           instrument_token,exchange,trading_symbol,instrument_type,priority
    FROM (
        SELECT * FROM resolved
        UNION ALL SELECT * FROM indices
        UNION ALL SELECT * FROM options
    ) subscriptions
    ORDER BY instrument_token,priority
    """
    with connection.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()
    return {
        int(row[0]): {
            "exchange": str(row[1]),
            "symbol": str(row[2]),
            "provider_symbol": f"{row[1]}:{row[2]}",
            "instrument_type": str(row[3] or ""),
        }
        for row in rows
    }


def start_run(connection: psycopg.Connection, subscription_count: int) -> tuple[int, str]:
    run_key = "zerodha-stream-" + utc_now().strftime("%Y%m%dT%H%M%SZ")
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO market.zerodha_stream_runs (
                run_key,status,connection_state,subscribed_instruments,metadata
            ) VALUES (%s,'starting','connecting',%s,%s::jsonb)
            RETURNING id
            """,
            (run_key, subscription_count, json.dumps({"source_mode": "websocket_full", "broker_write_allowed": False})),
        )
        run_id = int(cursor.fetchone()[0])
    connection.commit()
    return run_id, run_key


def update_run(connection: psycopg.Connection, run_id: int, **values: object) -> None:
    allowed = {
        "status", "connection_state", "subscribed_instruments", "ticks_received",
        "rows_upserted", "snapshots_written", "reconnect_count", "connected_at",
        "last_tick_at", "last_heartbeat_at", "finished_at", "error_message", "metadata",
    }
    updates = [(key, value) for key, value in values.items() if key in allowed]
    if not updates:
        return
    clause = ",".join(f"{key}=%s" for key, _ in updates)
    with connection.cursor() as cursor:
        cursor.execute(
            f"UPDATE market.zerodha_stream_runs SET {clause} WHERE id=%s",
            [value for _, value in updates] + [run_id],
        )
    connection.commit()


def notify_login_required(connection: psycopg.Connection, reason: str) -> None:
    today = utc_now().astimezone().date().isoformat()
    title = f"Zerodha daily login required: {today}"
    evidence = json.dumps([
        {"source": "market.v_zerodha_stream_health", "reason": reason},
        {"source": "https://kite.trade/docs/connect/v3/user/", "expiry": "06:00 Asia/Kolkata next day"},
    ])
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO agent.inbox_items (
                title,owner_agent,status,priority,recommended_action,evidence,target_workspace
            )
            SELECT %s,'Jarvis','queued','high',
                   'Open the Zerodha connection action, complete the required human login, and let the stream reconnect automatically.',
                   %s::jsonb,'system'
            WHERE NOT EXISTS (
                SELECT 1 FROM agent.inbox_items
                WHERE title=%s AND created_at>=current_date
            )
            """,
            (title, evidence, title),
        )
    connection.commit()
    subprocess.run(
        ["/usr/bin/osascript", "-e", 'display notification "Open AI Office to reconnect live prices." with title "Zerodha login required"'],
        check=False, capture_output=True, text=True, timeout=10,
    )


def normalize_tick(tick: dict[str, Any], instrument: dict[str, Any]) -> dict[str, Any] | None:
    price = tick.get("last_price")
    if price is None:
        return None
    depth = tick.get("depth") if isinstance(tick.get("depth"), dict) else {}
    buys = depth.get("buy") if isinstance(depth, dict) and isinstance(depth.get("buy"), list) else []
    sells = depth.get("sell") if isinstance(depth, dict) and isinstance(depth.get("sell"), list) else []
    ohlc = tick.get("ohlc") if isinstance(tick.get("ohlc"), dict) else {}
    close = ohlc.get("close")
    change = tick.get("change")
    if change is None and close not in (None, 0):
        change = (float(price)-float(close))/float(close)*100
    received_at = utc_now()
    payload = json.dumps(tick, default=json_default, separators=(",", ":"), sort_keys=True)
    return {
        "source_key": SOURCE_KEY,
        "provider": PROVIDER,
        "instrument_token": int(tick["instrument_token"]),
        "provider_symbol": instrument["provider_symbol"],
        "symbol": instrument["symbol"],
        "exchange": instrument["exchange"],
        "instrument_type": instrument["instrument_type"],
        "last_price": price,
        "last_quantity": tick.get("last_traded_quantity"),
        "average_price": tick.get("average_traded_price"),
        "volume": tick.get("volume_traded"),
        "buy_quantity": tick.get("total_buy_quantity"),
        "sell_quantity": tick.get("total_sell_quantity"),
        "open_interest": tick.get("oi"),
        "open_interest_high": tick.get("oi_day_high"),
        "open_interest_low": tick.get("oi_day_low"),
        "bid_price": buys[0].get("price") if buys and isinstance(buys[0], dict) else None,
        "ask_price": sells[0].get("price") if sells and isinstance(sells[0], dict) else None,
        "day_open": ohlc.get("open"),
        "day_high": ohlc.get("high"),
        "day_low": ohlc.get("low"),
        "previous_close": close,
        "change_percent": change,
        "exchange_timestamp": tick.get("exchange_timestamp"),
        "last_trade_timestamp": tick.get("last_trade_time"),
        "received_at": received_at,
        "raw_payload": payload,
    }


class TickWriter(threading.Thread):
    def __init__(
        self,
        tick_queue: queue.Queue[list[dict[str, Any]]],
        instruments: dict[int, dict[str, Any]],
        run_id: int,
        stop_event: threading.Event,
    ) -> None:
        super().__init__(name="zerodha-tick-writer", daemon=True)
        self.tick_queue = tick_queue
        self.instruments = instruments
        self.run_id = run_id
        self.stop_event = stop_event
        self.ticks_received = 0
        self.rows_upserted = 0
        self.snapshots_written = 0
        self.last_tick_at: datetime | None = None

    def run(self) -> None:
        connection = database()
        pending: list[dict[str, Any]] = []
        last_flush = time.monotonic()
        last_heartbeat = 0.0
        last_retention = 0.0
        try:
            while not self.stop_event.is_set() or not self.tick_queue.empty() or pending:
                timeout = max(0.1, FLUSH_SECONDS-(time.monotonic()-last_flush))
                try:
                    batch = self.tick_queue.get(timeout=min(timeout, 1.0))
                    self.ticks_received += len(batch)
                    for tick in batch:
                        token = int(tick.get("instrument_token") or 0)
                        instrument = self.instruments.get(token)
                        if not instrument:
                            continue
                        normalized = normalize_tick(tick, instrument)
                        if normalized:
                            pending.append(normalized)
                            self.last_tick_at = normalized["received_at"]
                except queue.Empty:
                    pass
                now_monotonic = time.monotonic()
                if pending and (now_monotonic-last_flush >= FLUSH_SECONDS or self.stop_event.is_set()):
                    rows = list(pending)
                    with connection.cursor() as cursor:
                        cursor.executemany(UPSERT_LIVE_SQL, rows)
                        cursor.executemany(UPSERT_MINUTE_SQL, rows)
                        cursor.executemany(UPSERT_COMPATIBLE_QUOTE_SQL, rows)
                    connection.commit()
                    self.rows_upserted += len(rows)
                    self.snapshots_written += len(rows)
                    pending.clear()
                    last_flush = now_monotonic
                if now_monotonic-last_heartbeat >= HEARTBEAT_SECONDS:
                    update_run(
                        connection,self.run_id,status="running",connection_state="connected",
                        ticks_received=self.ticks_received,rows_upserted=self.rows_upserted,
                        snapshots_written=self.snapshots_written,last_tick_at=self.last_tick_at,
                        last_heartbeat_at=utc_now(),
                    )
                    last_heartbeat = now_monotonic
                if now_monotonic-last_retention >= 21600:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "DELETE FROM market.live_quote_minute_snapshots WHERE minute_ts<now()-(%s||' days')::interval",
                            (RETENTION_DAYS,),
                        )
                        cursor.execute(
                            "DELETE FROM market.price_quotes WHERE source_key=%s AND quote_ts<now()-(%s||' days')::interval",
                            (SOURCE_KEY, RETENTION_DAYS),
                        )
                    connection.commit()
                    last_retention = now_monotonic
        finally:
            connection.close()


def validate_session(api_key: str, access_token: str) -> tuple[bool, str | None]:
    try:
        payload = request_json("GET", "/user/profile", api_key=api_key, access_token=access_token)
        return isinstance(payload, dict) and payload.get("status") == "success", None
    except Exception as exc:  # noqa: BLE001
        return False, redact_error(exc, access_token, api_key)


def run_read_only_refresh(script: str, arguments: list[str], timeout: int) -> tuple[bool, str | None]:
    try:
        completed = subprocess.run(
            [os.sys.executable, os.path.join(os.path.dirname(__file__), script), *arguments],
            cwd=os.path.dirname(__file__), text=True, capture_output=True, check=False, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, redact_error(exc)
    if completed.returncode == 0:
        return True, None
    detail = (completed.stderr or completed.stdout or f"{script} failed")[-1500:]
    return False, redact_error(detail)


def run_stream(api_key: str, access_token: str, run_seconds: int | None) -> dict[str, Any]:
    connection = database()
    instruments = query_subscriptions(connection)
    run_id, run_key = start_run(connection, len(instruments))
    if not instruments:
        update_run(connection,run_id,status="failed",connection_state="disconnected",
                   finished_at=utc_now(),error_message="No instruments resolved for streaming.")
        connection.close()
        return {"status": "failed", "run_key": run_key, "error": "no subscriptions"}

    tick_queue: queue.Queue[list[dict[str, Any]]] = queue.Queue(maxsize=2000)
    stop_event = threading.Event()
    connected_event = threading.Event()
    writer = TickWriter(tick_queue,instruments,run_id,stop_event)
    writer.start()
    ticker = KiteTicker(api_key,access_token,reconnect=True,reconnect_max_tries=50,reconnect_max_delay=60)
    reconnects = 0
    connection_lock = threading.Lock()

    def on_ticks(ws: KiteTicker, ticks: list[dict[str, Any]]) -> None:
        try:
            tick_queue.put(ticks, timeout=max(1.0, FLUSH_SECONDS))
        except queue.Full:
            stop_event.set()
            ws.stop()

    def on_connect(ws: KiteTicker, _response: object) -> None:
        nonlocal instruments
        with connection_lock:
            tokens = list(instruments)
            ws.subscribe(tokens)
            ws.set_mode(ws.MODE_FULL,tokens)
        connected_event.set()
        status_connection = database()
        try:
            update_run(
                status_connection,run_id,status="running",connection_state="connected",
                subscribed_instruments=len(tokens),connected_at=utc_now(),
                last_heartbeat_at=utc_now(),error_message=None,
            )
        finally:
            status_connection.close()

    def on_reconnect(_ws: KiteTicker, attempts_count: int) -> None:
        nonlocal reconnects
        reconnects = attempts_count

    def on_noreconnect(ws: KiteTicker) -> None:
        stop_event.set()
        ws.stop()

    def on_error(_ws: KiteTicker, _code: object, reason: object) -> None:
        status_connection = database()
        try:
            update_run(
                status_connection,run_id,status="degraded",connection_state="reconnecting",
                reconnect_count=reconnects,error_message=redact_error(reason,access_token,api_key),
                last_heartbeat_at=utc_now(),
            )
        finally:
            status_connection.close()

    ticker.on_ticks=on_ticks
    ticker.on_connect=on_connect
    ticker.on_reconnect=on_reconnect
    ticker.on_noreconnect=on_noreconnect
    ticker.on_error=on_error

    def supervisor() -> None:
        nonlocal instruments
        started = time.monotonic()
        last_reload = started
        last_account_refresh = 0.0
        last_options_refresh = 0.0
        while not stop_event.wait(5):
            if run_seconds and time.monotonic()-started>=run_seconds:
                stop_event.set()
                ticker.stop()
                return
            current_token = keychain_token()
            if current_token and current_token != access_token:
                stop_event.set()
                ticker.stop()
                return
            now_monotonic = time.monotonic()
            if connected_event.is_set() and now_monotonic-last_account_refresh>=ACCOUNT_REFRESH_SECONDS:
                run_read_only_refresh(
                    "sync_zerodha_read_only.py",
                    ["--datasets","holdings","positions","orders","trades","funds"],
                    180,
                )
                last_account_refresh = time.monotonic()
            if connected_event.is_set() and now_monotonic-last_options_refresh>=OPTIONS_REFRESH_SECONDS:
                run_read_only_refresh(
                    "sync_zerodha_market_data.py",
                    ["--modes","quotes","options","--underlyings","NIFTY","BANKNIFTY"],
                    240,
                )
                last_options_refresh = time.monotonic()
            if time.monotonic()-last_reload>=RELOAD_SECONDS and connected_event.is_set():
                refresh_connection = database()
                try:
                    refreshed = query_subscriptions(refresh_connection)
                finally:
                    refresh_connection.close()
                old_tokens=set(instruments)
                new_tokens=set(refreshed)
                with connection_lock:
                    if new_tokens-old_tokens:
                        ticker.subscribe(list(new_tokens-old_tokens))
                        ticker.set_mode(ticker.MODE_FULL,list(new_tokens-old_tokens))
                    if old_tokens-new_tokens:
                        ticker.unsubscribe(list(old_tokens-new_tokens))
                    instruments.clear()
                    instruments.update(refreshed)
                last_reload=time.monotonic()

    supervisor_thread=threading.Thread(target=supervisor,name="zerodha-stream-supervisor",daemon=True)
    supervisor_thread.start()

    def shutdown(_signum: int, _frame: object) -> None:
        stop_event.set()
        ticker.stop()

    signal.signal(signal.SIGTERM,shutdown)
    signal.signal(signal.SIGINT,shutdown)
    final_status="stopped"
    final_error=None
    try:
        ticker.connect(threaded=False,disable_ssl_verification=False)
    except Exception as exc:  # noqa: BLE001
        final_status="failed"
        final_error=redact_error(exc,access_token,api_key)
    finally:
        stop_event.set()
        writer.join(timeout=15)
        update_run(
            connection,run_id,status=final_status,connection_state="disconnected",
            ticks_received=writer.ticks_received,rows_upserted=writer.rows_upserted,
            snapshots_written=writer.snapshots_written,reconnect_count=reconnects,
            last_tick_at=writer.last_tick_at,last_heartbeat_at=utc_now(),
            finished_at=utc_now(),error_message=final_error,
        )
        connection.close()
    return {
        "status": final_status,"run_key": run_key,"subscriptions": len(instruments),
        "ticks_received": writer.ticks_received,"rows_upserted": writer.rows_upserted,
        "snapshots_written": writer.snapshots_written,"error": final_error,
        "broker_write_allowed": False,
    }


def main() -> int:
    parser=argparse.ArgumentParser(description="Run the read-only Zerodha WebSocket price stream.")
    parser.add_argument("--run-seconds",type=int)
    parser.add_argument("--check",action="store_true")
    args=parser.parse_args()
    api_key=os.environ.get("AI_OS_ZERODHA_API_KEY","").strip()
    access_token=keychain_token()
    connection=database()
    try:
        if not api_key or not access_token:
            notify_login_required(connection,"missing daily access token")
            print(json.dumps({"status":"waiting_for_daily_login","api_key_configured":bool(api_key),
                              "access_token_available":bool(access_token),"broker_write_allowed":False}))
            return 2
        valid,error=validate_session(api_key,access_token)
        if not valid:
            notify_login_required(connection,error or "daily access token rejected")
            print(json.dumps({"status":"token_expired","error":error,"broker_write_allowed":False}))
            return 2
        if args.check:
            subscriptions=query_subscriptions(connection)
            print(json.dumps({"status":"ready","subscriptions":len(subscriptions),
                              "broker_write_allowed":False}))
            return 0
    finally:
        connection.close()
    result=run_stream(api_key,access_token,args.run_seconds)
    print(json.dumps(result,default=json_default))
    return 0 if result["status"] in {"stopped","running"} else 1


if __name__=="__main__":
    raise SystemExit(main())
