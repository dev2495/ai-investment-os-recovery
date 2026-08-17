from __future__ import annotations

import unittest
from pathlib import Path


class InstitutionalEngineFrontendActionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        runtime_root = Path(__file__).resolve().parents[1]
        frontend = runtime_root / "ai-office-ui" / "src"
        cls.actions = (frontend / "data" / "actions.ts").read_text(encoding="utf-8")
        cls.fundamental = (
            frontend / "destinations" / "fundamental" / "FundamentalResearch.tsx"
        ).read_text(encoding="utf-8")
        cls.sector = (
            frontend / "destinations" / "sector" / "SectorIntelligence.tsx"
        ).read_text(encoding="utf-8")
        cls.options = (
            frontend / "destinations" / "options" / "OptionsDesk.tsx"
        ).read_text(encoding="utf-8")

    def test_typed_engine_actions_use_the_required_endpoints(self) -> None:
        expected = {
            "useRunInstitutionalFundamentalFactory": "/api/research/fundamental-factory/run",
            "useRunSectorIntelligence": "/api/sector-intelligence/run",
            "useRunInstitutionalOptionsAnalytics": "/api/options/institutional-analytics/run",
        }
        for hook, endpoint in expected.items():
            with self.subTest(hook=hook):
                self.assertIn("export function " + hook, self.actions)
                self.assertIn('"' + endpoint + '"', self.actions)

    def test_each_action_invalidates_its_authoritative_read_models(self) -> None:
        self.assertIn(
            "[Q.researchIdeas, Q.portfolioOffice, Q.office, Q.reports]",
            self.actions,
        )
        self.assertIn("[Q.sectorIntelligence, Q.office]", self.actions)
        self.assertIn("[Q.tradingQuantRisk, Q.office]", self.actions)
        self.assertIn('sectorIntelligence: ["sector-intelligence"]', self.actions)

    def test_operator_forms_have_required_inputs_and_default_to_dry_run(self) -> None:
        for source in (self.fundamental, self.sector, self.options):
            with self.subTest(source=source[:40]):
                self.assertIn("mutation.isPending", source)
                self.assertIn("mutation.isError", source)
                self.assertIn("mutation.isSuccess", source)
                self.assertIn('role="alert"', source)
                self.assertIn('role="status"', source)

        for source in (self.fundamental, self.sector):
            self.assertIn('mode: "dry_run"', source)
            self.assertIn('value="dry_run"', source)
        self.assertIn("dry_run: true", self.options)
        self.assertNotIn('value="persist"', self.options)

        for label in ("Company symbol", "Exchange", "Research cutoff", "Run mode"):
            self.assertIn('label="' + label + '"', self.fundamental)
        for label in ("Custom index", "As-of date", "Strength horizon", "Run mode"):
            self.assertIn('label="' + label + '"', self.sector)
        for label in (
            "Underlying",
            "Expiry",
            "Valuation cutoff",
            "Pricing model",
            "Max quote age (sec)",
            "Max spread (bps)",
            "Minimum OI",
            "Minimum volume",
        ):
            self.assertIn('label="' + label + '"', self.options)

    def test_submissions_send_safe_mode_and_never_claim_execution(self) -> None:
        for source in (self.fundamental, self.sector):
            self.assertIn('dry_run: form.mode === "dry_run"', source)
        self.assertIn("dry_run: true", self.options)

        self.assertIn("cannot place or propose a broker order", self.fundamental)
        self.assertIn("no broker execution is available", self.sector)
        self.assertIn("It never submits a broker order", self.options)
        self.assertNotIn("/api/orders", self.fundamental + self.sector + self.options)
        self.assertNotIn("/api/execution", self.fundamental + self.sector + self.options)


if __name__ == "__main__":
    unittest.main()
