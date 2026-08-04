from __future__ import annotations

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class FundamentalRealCompanyIntakeTests(unittest.TestCase):
    def test_migration_is_real_source_only_and_execution_locked(self) -> None:
        source = (ROOT / "postgres" / "init" / "194_fundamental_real_company_intake_v1.sql").read_text()
        self.assertIn("portfolio.positions", source)
        self.assertIn("research.corporate_filings", source)
        self.assertIn("official_exchange_filing", source)
        self.assertIn("financial_coverage_inferred', false", source)
        self.assertIn("capital_action_allowed BOOLEAN NOT NULL DEFAULT false", source)
        self.assertIn("broker_write_allowed BOOLEAN NOT NULL DEFAULT false", source)
        self.assertNotIn("INSERT INTO research.company_statement_facts", source)
        self.assertNotIn("INSERT INTO trading.order", source)

    def test_api_exposes_durable_intake_and_snapshot(self) -> None:
        source = (ROOT / "api" / "ai_os_api_server.py").read_text()
        self.assertIn("def sync_fundamental_company_intake(payload: dict) -> dict:", source)
        self.assertIn('"/api/research/fundamental-intake/sync"', source)
        self.assertIn('"fundamental_intake":', source)
        self.assertIn("research.v_company_intake_status", source)
        self.assertIn("fundamental intake violated its no-execution contract", source)

    def test_mcp_and_frontend_expose_operator_action(self) -> None:
        mcp = (ROOT / "mcp_server" / "ai_os_mcp_server.py").read_text()
        actions = (ROOT / "ai-office-ui" / "src" / "data" / "actions.ts").read_text()
        ui = (
            ROOT
            / "ai-office-ui"
            / "src"
            / "destinations"
            / "fundamental"
            / "FundamentalResearch.tsx"
        ).read_text()
        self.assertIn('"ai_os_sync_fundamental_company_intake"', mcp)
        self.assertIn("sync_fundamental_company_intake", mcp)
        self.assertIn("useSyncFundamentalCompanyIntake", actions)
        self.assertIn("Sync holdings & filings", ui)
        self.assertIn("next_required_action", ui)


if __name__ == "__main__":
    unittest.main()
