import importlib.util
import pathlib
import unittest


RUNTIME_ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_aggregator():
    path = RUNTIME_ROOT / "scripts" / "aggregate_ticks_to_ohlcv.py"
    spec = importlib.util.spec_from_file_location("aggregate_ticks_to_ohlcv_contract", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LiveMarketPipelineContractTests(unittest.TestCase):
    def test_canonical_ohlcv_combines_live_zerodha_minutes_with_legacy_ticks(self) -> None:
        module = load_aggregator()
        sql = module.build_aggregation_sql("5m", module.TIMEFRAMES[-1][2])

        self.assertIn("FROM market.live_quote_minute_snapshots snapshot", sql)
        self.assertIn("snapshot.provider = 'Zerodha'", sql)
        self.assertIn("FROM trading.ticks t", sql)
        self.assertIn("source_priority DESC", sql)
        self.assertIn("INSERT INTO trading.ohlcv", sql)
        self.assertNotIn("date_bin(INTERVAL '5 minutes', t.ts", sql)
        self.assertIn("snapshot.minute_ts::date", sql)
        self.assertIn("IS NULL THEN COALESCE(snapshot.volume, 0)", sql)

    def test_websocket_writer_preserves_every_tick_before_minute_upsert(self) -> None:
        source = (RUNTIME_ROOT / "scripts" / "stream_zerodha_live.py").read_text(encoding="utf-8")

        self.assertIn("pending: list[dict[str, Any]] = []", source)
        self.assertIn("pending.append(normalized)", source)
        self.assertIn("rows = list(pending)", source)
        self.assertNotIn("pending[token] = normalized", source)
        self.assertIn("tick_queue.put(ticks, timeout=max(1.0, FLUSH_SECONDS))", source)
        self.assertNotIn("tick_queue.get_nowait()", source)
        self.assertIn("stop_event.set()", source)
        self.assertIn("high_price=greatest", source)
        self.assertIn("low_price=least", source)

    def test_tradingview_web_quote_scanner_is_off_by_default(self) -> None:
        daemon = (RUNTIME_ROOT / "scripts" / "run_agent_message_daemon.py").read_text(encoding="utf-8")
        service = (RUNTIME_ROOT / "launchd" / "aios-agent-daemon-service.sh").read_text(encoding="utf-8")
        env_example = (RUNTIME_ROOT / "deploy" / "imac-backend" / "imac.env.example").read_text(encoding="utf-8")

        self.assertIn('os.environ.get("AI_OS_ENABLE_TRADINGVIEW_QUOTE_REFRESH", "0")', daemon)
        self.assertIn('AI_OS_ENABLE_TRADINGVIEW_QUOTE_REFRESH:-0', service)
        self.assertIn("AI_OS_ENABLE_TRADINGVIEW_QUOTE_REFRESH=0", env_example)
        self.assertNotIn("AI_OS_ENABLE_TRADINGVIEW_BROWSER", env_example)
        self.assertNotIn("TRADINGVIEW_CDP_PORT", env_example)

    def test_market_calendar_is_an_always_on_bounded_workload(self) -> None:
        daemon = (RUNTIME_ROOT / "scripts" / "run_agent_message_daemon.py").read_text(encoding="utf-8")
        service = (RUNTIME_ROOT / "launchd" / "aios-agent-daemon-service.sh").read_text(encoding="utf-8")

        self.assertIn("def run_market_calendar_refresh", daemon)
        self.assertIn("AI_OS_ENABLE_MARKET_CALENDAR_SCHEDULER", daemon)
        self.assertIn("market_calendar_refresh", daemon)
        self.assertIn("AI_OS_MARKET_CALENDAR_INTERVAL_SECONDS", service)
        self.assertIn("--market-calendar-timeout", service)

    def test_options_routes_and_missing_analytics_are_explicit(self) -> None:
        app = (RUNTIME_ROOT / "ai-office-ui" / "src" / "app" / "App.tsx").read_text(encoding="utf-8")
        registry = (RUNTIME_ROOT / "ai-office-ui" / "src" / "app" / "destinations.ts").read_text(encoding="utf-8")
        options = (RUNTIME_ROOT / "ai-office-ui" / "src" / "destinations" / "options" / "OptionsDesk.tsx").read_text(encoding="utf-8")

        for route in ("/options/oi-analysis", "/options/strategies"):
            self.assertIn(route, app)
            self.assertIn(route, registry)
        self.assertIn("data?.option_oi_change", options)
        self.assertIn("Kite quotes do not supply IV", options)
        self.assertIn('optionalNum(r, "delta")', options)
        self.assertNotIn('iv: num(r, "implied_volatility"', options)


if __name__ == "__main__":
    unittest.main()
