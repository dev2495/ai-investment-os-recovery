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

        self.assertEqual(len(registered), 58)
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

        self.assertEqual(len(paths), 75)
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
        self.assertNotIn("How to validate", terminal)




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



if __name__ == "__main__":
    unittest.main()
