from __future__ import annotations

import re
import unittest
from pathlib import Path


class FrontendRouteContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime_root = Path(__file__).resolve().parents[1]
        cls.destinations = (
            cls.runtime_root / "ai-office-ui" / "src" / "app" / "destinations.ts"
        ).read_text(encoding="utf-8")
        cls.app = (
            cls.runtime_root / "ai-office-ui" / "src" / "app" / "App.tsx"
        ).read_text(encoding="utf-8")

    def test_every_terminal_function_has_an_explicit_component(self) -> None:
        registered = set(re.findall(r'path: "([^"]+)"', self.destinations))
        mapped = set(
            re.findall(
                r'^\s+"([^"]+)": \(\) => import',
                self.app,
                flags=re.MULTILINE,
            )
        )

        self.assertEqual(len(registered), 65)
        self.assertEqual(mapped, registered)

    def test_shared_terminals_derive_tab_from_pathname(self) -> None:
        relative_files = (
            "destinations/options/OptionsDesk.tsx",
            "destinations/scanners/Scanners.tsx",
        )
        for relative in relative_files:
            source = (
                self.runtime_root / "ai-office-ui" / "src" / relative
            ).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIn("useLocation", source)
                self.assertIn(
                    'location.pathname.split("/").filter(Boolean).slice(-1)[0]',
                    source,
                )
                self.assertNotIn("const params = useParams()", source)
                self.assertNotIn("const tab = params.tab", source)


    def test_every_frontend_api_path_has_backend_handler(self) -> None:
        data_root = self.runtime_root / "ai-office-ui" / "src" / "data"
        frontend = "\n".join(
            (data_root / filename).read_text(encoding="utf-8")
            for filename in ("queries.ts", "actions.ts")
        )
        backend = (
            self.runtime_root / "api" / "ai_os_api_server.py"
        ).read_text(encoding="utf-8")
        paths = set(re.findall(r'"(/api/[^"?]+)', frontend))

        self.assertGreaterEqual(len(paths), 90)
        self.assertTrue({
            "/api/sector-intelligence/import",
            "/api/options/institutional-analytics/materialize",
            "/api/options/institutional-analytics/acceptance/run",
            "/api/office/operability/acceptance/run",
            "/api/options/valuation-policy/upsert",
        }.issubset(paths))
        self.assertNotIn("/api/tradingview/chart-actions", paths)
        self.assertEqual(
            sorted(path for path in paths if path not in backend),
            [],
        )

    def test_portfolio_writes_are_actionable_and_governed(self) -> None:
        actions = (
            self.runtime_root / "ai-office-ui" / "src" / "data" / "actions.ts"
        ).read_text(encoding="utf-8")
        terminal = (
            self.runtime_root
            / "ai-office-ui"
            / "src"
            / "destinations"
            / "portfolio"
            / "PortfolioTerminal.tsx"
        ).read_text(encoding="utf-8")

        self.assertIn('"/api/client-office/onboarding/stage"', actions)
        self.assertIn('"/api/portfolio/holding-updates/stage"', actions)
        self.assertIn("Stage for approval", terminal)
        self.assertIn("source_evidence", terminal)
        self.assertIn("useStageClientOnboarding", terminal)
        self.assertIn("useStageHoldingUpdate", terminal)
        self.assertNotIn(
            '<Button size="sm" variant="primary" icon={Plus}>Onboard Client</Button>',
            terminal,
        )

    def test_reconciliation_controls_are_live_and_visible(self) -> None:
        actions = (self.runtime_root / "ai-office-ui" / "src" / "data" / "actions.ts").read_text(encoding="utf-8")
        terminal = (self.runtime_root / "ai-office-ui" / "src" / "destinations" / "portfolio" / "PortfolioTerminal.tsx").read_text(encoding="utf-8")
        self.assertIn("/api/broker-reconciliation/run", actions)
        self.assertIn("/api/p2cursor-reconciliation/run", actions)
        self.assertIn("Run broker", terminal)
        self.assertIn("Run P2Cursor", terminal)
        self.assertIn("P2Cursor vs Canonical Portfolio", terminal)

    def test_domain_committee_decisions_are_live_and_human_gated(self) -> None:
        actions = (
            self.runtime_root / "ai-office-ui" / "src" / "data" / "actions.ts"
        ).read_text(encoding="utf-8")
        terminal = (
            self.runtime_root
            / "ai-office-ui"
            / "src"
            / "destinations"
            / "firm"
            / "FirmAgentViews.tsx"
        ).read_text(encoding="utf-8")

        self.assertIn("\"/api/portfolio/long-term-committee/decision\"", actions)
        self.assertIn("\"/api/strategy/committee/decision\"", actions)
        self.assertIn("\"/api/research/special-situations/decision\"", actions)
        self.assertIn("committee_item_key", terminal)
        self.assertIn("committee_review_id: sourceId", terminal)
        self.assertIn("special_memo_id: sourceId", terminal)
        self.assertIn("Record decision", terminal)
        self.assertIn("Decision rationale is required", terminal)
        self.assertNotIn("text(item, \"packet_id\"", terminal)

    def test_quant_lifecycle_actions_are_live_and_governed(self) -> None:
        actions = (
            self.runtime_root / "ai-office-ui" / "src" / "data" / "actions.ts"
        ).read_text(encoding="utf-8")
        terminal = (
            self.runtime_root
            / "ai-office-ui"
            / "src"
            / "destinations"
            / "quant"
            / "QuantStrategy.tsx"
        ).read_text(encoding="utf-8")

        for path in (
            "/api/strategy/user-defined-optimizer/run",
            "/api/strategy/quant-analytics/run",
            "/api/strategy/portfolio-allocation/run",
            "/api/strategy/retirement/run",
        ):
            self.assertIn(path, actions)
        self.assertIn("Run full research pipeline", terminal)
        self.assertIn("Allocate paper capital", terminal)
        self.assertIn("It cannot place a broker order", terminal)
        self.assertIn("Backtests Ready for Adversarial Validation", terminal)
        self.assertIn("useRunModelValidation", terminal)
        self.assertIn("/api/strategy/discovery/triage/resolve", actions)
        self.assertIn("discovery_candidate_id: candidateId", terminal)
        self.assertIn("Triage rationale is required", terminal)
        self.assertIn("Create intake", terminal)
        self.assertNotIn("paperMut.mutate({ strategy_id", terminal)
        self.assertIn("text(r, \"promotion_stage\") === \"paper_monitor_ready\"", terminal)
        self.assertIn("committee_review_id: num(r, \"committee_review_id\", 0)", terminal)
        self.assertNotIn("How to validate", terminal)




    def test_macro_quotes_use_canonical_stored_prices_not_calendar_events(self) -> None:
        terminal = (
            self.runtime_root
            / "ai-office-ui"
            / "src"
            / "destinations"
            / "macro"
            / "MacroMarkets.tsx"
        ).read_text(encoding="utf-8")
        backend = (self.runtime_root / "api" / "ai_os_api_server.py").read_text(encoding="utf-8")

        self.assertIn("research?.market_quotes", terminal)
        self.assertIn("Stored Live Quotes", terminal)
        self.assertIn("change_percent", terminal)
        self.assertNotIn("research?.market_events?.filter", terminal)
        self.assertGreaterEqual(backend.count("FROM market.v_latest_price_quotes"), 2)
        self.assertIn("lower(provider) NOT LIKE", backend)

    def test_options_surfaces_use_recorded_trades_and_live_chain_inputs(self) -> None:
        source = (
            self.runtime_root
            / "ai-office-ui"
            / "src"
            / "destinations"
            / "options"
            / "OptionsDesk.tsx"
        ).read_text(encoding="utf-8")

        self.assertIn("const optionTrades = React.useMemo", source)
        self.assertIn("tradingData?.trade_activity", source)
        self.assertIn("const activeContracts = React.useMemo", source)
        self.assertIn("premium: item.ltp", source)
        self.assertIn('instrument_type: "option"', source)
        self.assertIn("expiry_date: form.expiry_date", source)
        self.assertIn('text(row, "trade_ts"', source)
        self.assertNotIn("trade_date: form.expiry_date", source)
        self.assertIn("disabled={!liveChainReady}", source)
        self.assertNotIn("React.useState(22000)", source)
        self.assertNotRegex(source, r"premium:\s*(?:40|80|100|200)\b")

    def test_fundamental_workbenches_use_persisted_evidence_contracts(self) -> None:
        actions = (
            self.runtime_root / "ai-office-ui" / "src" / "data" / "actions.ts"
        ).read_text(encoding="utf-8")
        terminal = (
            self.runtime_root
            / "ai-office-ui"
            / "src"
            / "destinations"
            / "fundamental"
            / "FundamentalResearch.tsx"
        ).read_text(encoding="utf-8")
        backend = (
            self.runtime_root / "api" / "ai_os_api_server.py"
        ).read_text(encoding="utf-8")

        self.assertIn("holding_thesis_id: number", actions)
        self.assertIn("checklist_key: string", actions)
        self.assertIn("model_key: string", actions)
        self.assertIn("evidence?: unknown[]", actions)
        self.assertIn("Scorecard persisted", terminal)
        self.assertIn("Valuation model persisted", terminal)
        self.assertIn("Source evidence is required", terminal)
        self.assertIn('num(r, "fair_value_low", 0)', terminal)
        self.assertIn('num(r, "fair_value_base", 0)', terminal)
        self.assertIn('num(r, "fair_value_high", 0)', terminal)
        self.assertNotIn('num(r, "fair_value", 0)', terminal)
        self.assertNotIn('num(r, "upside_pct", 0)', terminal)
        self.assertIn("evidence, owner_agent, updated_at", backend)
        self.assertIn("assumptions, outputs, note_path", backend)
        self.assertIn("holding_thesis_id?: number", actions)
        self.assertIn("symbol?: string", actions)
        self.assertIn("Generate from holding", terminal)
        self.assertIn("canonical long-term book exposure", terminal)
        self.assertIn("WHERE id = {thesis_id}", backend)
        self.assertIn("symbol does not match holding_thesis_id", backend)

    def test_long_term_thesis_workspace_is_bounded_source_backed_and_locked(self) -> None:
        query_source = (
            self.runtime_root / "ai-office-ui" / "src" / "data" / "queries.ts"
        ).read_text(encoding="utf-8")
        terminal = (
            self.runtime_root / "ai-office-ui" / "src" / "destinations" /
            "fundamental" / "LongTermThesisWorkspace.tsx"
        ).read_text(encoding="utf-8")
        backend = (self.runtime_root / "api" / "ai_os_api_server.py").read_text(encoding="utf-8")
        read_model = (self.runtime_root / "api" / "long_term_thesis_workspace.py").read_text(encoding="utf-8")

        self.assertIn('"/api/research/long-term-thesis"', query_source)
        self.assertIn('request_path == "/api/research/long-term-thesis"', backend)
        self.assertIn('page_size = bounded("page_size", 12, 6, 24)', read_model)
        self.assertIn("filings_extracted", read_model)
        self.assertIn("private_data_egress_allowed", read_model)
        self.assertIn("No section-level source is linked", terminal)
        self.assertIn("Restated/superseded rows excluded", terminal)
        self.assertIn("It authorizes no broker, client, or external write", terminal)
        self.assertNotIn("mock", terminal.lower())



    def test_signal_and_paper_monitor_contracts_use_canonical_fields(self) -> None:
        actions = (self.runtime_root / "ai-office-ui" / "src" / "data" / "actions.ts").read_text(encoding="utf-8")
        quant = (self.runtime_root / "ai-office-ui" / "src" / "destinations" / "quant" / "QuantStrategy.tsx").read_text(encoding="utf-8")
        backend = (self.runtime_root / "api" / "ai_os_api_server.py").read_text(encoding="utf-8")

        self.assertIn("committee_review_id: number", actions)
        paper_interface = actions.split("export interface PaperMonitorInput", 1)[1].split("}", 1)[0]
        self.assertNotIn("strategy_id", paper_interface)
        self.assertIn("committee_review_id", quant)
        self.assertIn("promotion_stage", quant)
        self.assertIn("validation_gate_status", quant)
        self.assertIn("paper_monitor_status", quant)
        self.assertIn("next_required_action", quant)
        self.assertNotIn("days_monitored", quant)
        self.assertNotIn("drift_pct", quant)
        signal_query = backend.split("\"signals\": \"\"\"", 1)[1].split("\"\"\"", 1)[0]
        self.assertIn("AS generated_at", signal_query)
        self.assertIn("AS strategy_name", signal_query)
        self.assertIn("AS direction", signal_query)
        self.assertIn("AS signal_type", signal_query)
        self.assertIn("AS strength", signal_query)

    def test_research_daily_driver_uses_governed_public_sources(self) -> None:
        terminal = (
            self.runtime_root
            / "ai-office-ui"
            / "src"
            / "destinations"
            / "research"
            / "ResearchFilings.tsx"
        ).read_text(encoding="utf-8")
        actions = (self.runtime_root / "ai-office-ui" / "src" / "data" / "actions.ts").read_text(encoding="utf-8")
        backend = (self.runtime_root / "api" / "ai_os_api_server.py").read_text(encoding="utf-8")
        collector = (self.runtime_root / "scripts" / "ingest_market_news.py").read_text(encoding="utf-8")

        self.assertIn("Research & Market Heartbeat", terminal)
        self.assertIn("Source-backed Watchlist", terminal)
        self.assertIn("Deduplicated Intelligence Timeline", terminal)
        self.assertIn("Investor & Public Source Registry", terminal)
        self.assertIn("no automatic trading action", terminal)
        self.assertIn("Add for policy review", terminal)
        self.assertIn("useRegisterInvestorSource", actions)
        self.assertIn("/api/research/investor-sources/register", actions)
        self.assertIn("def register_investor_source", backend)
        self.assertIn("pending_source_review", backend)
        self.assertIn("approved_for_fetch", backend)
        self.assertIn("investor_blog_rss", collector)

    def test_options_reject_future_quotes_and_use_latest_qualified_batch(self) -> None:
        terminal = (
            self.runtime_root
            / "ai-office-ui"
            / "src"
            / "destinations"
            / "options"
            / "OptionsDesk.tsx"
        ).read_text(encoding="utf-8")
        backend = (self.runtime_root / "api" / "ai_os_api_server.py").read_text(encoding="utf-8")
        collector = (self.runtime_root / "scripts" / "sync_zerodha_market_data.py").read_text(encoding="utf-8")
        materializer = (self.runtime_root / "scripts" / "materialize_institutional_options.py").read_text(encoding="utf-8")

        self.assertIn('ZoneInfo("Asia/Kolkata")', collector)
        self.assertIn("def zerodha_timestamp_utc", collector)
        self.assertIn("source_observed_at = zerodha_timestamp_utc(source_timestamp)", collector)
        self.assertIn("legacy.observed_at <= now() + interval '5 minutes'", materializer)
        self.assertIn("ORDER BY source.minute_ts::timestamptz DESC", materializer)
        self.assertGreaterEqual(backend.count("<= now() + interval '5 minutes'"), 4)
        self.assertIn("dense_rank() OVER", backend)
        self.assertIn("batch_recency_rank=1", backend)
        self.assertIn("END AS current_freshness_status", backend)
        self.assertIn("interval '120 seconds'", backend)
        self.assertIn("source-qualified OI analytics", terminal)
        self.assertIn("function isFreshOptionContract", terminal)
        self.assertIn("no standalone direction claim", terminal)
        self.assertIn("No source-backed volatility conclusion", terminal)
        self.assertIn("Source status", terminal)
        self.assertIn("analysis and drafts only", terminal)
        self.assertIn("disabled={!ready}", terminal)
        self.assertIn("No order is created", terminal)
        self.assertIn("Record Trade Evidence", terminal)
        self.assertGreaterEqual(terminal.count("const symbolExpiries"), 4)
        self.assertIn("const bySeries = new Map", terminal)
        self.assertIn("const key = `${c.symbol}|${c.expiry}`", terminal)
        self.assertIn('header: "Expiry"', terminal)

if __name__ == "__main__":
    unittest.main()
