from __future__ import annotations

import re
import unittest
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    RUNTIME_ROOT
    / "postgres"
    / "init"
    / "185_institutional_fundamental_research_v1.sql"
)


class InstitutionalFundamentalSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.migration = MIGRATION_PATH.read_text(encoding="utf-8")

    def test_migration_defines_complete_normalized_foundation(self) -> None:
        required_tables = (
            "research.companies",
            "research.fundamental_evidence",
            "research.statement_fact_definitions",
            "research.company_statement_facts",
            "research.company_segments",
            "research.company_segment_facts",
            "research.operational_kpi_definitions",
            "research.operational_kpi_observations",
            "research.market_share_observations",
            "research.peer_sets",
            "research.peer_set_memberships",
            "research.management_communications",
            "research.management_claims",
            "research.management_claim_outcomes",
            "research.investment_dossiers",
            "research.investment_dossier_versions",
            "research.investment_dossier_sections",
            "research.investment_dossier_section_evidence",
            "research.investment_dossier_refresh_triggers",
            "research.fundamental_specialist_opinions",
            "research.fundamental_acceptance_runs",
            "research.fundamental_acceptance_gates",
        )
        for table in required_tables:
            with self.subTest(table=table):
                self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", self.migration)

    def test_statement_facts_are_point_in_time_and_restatement_aware(self) -> None:
        for contract in (
            "source_as_of_date DATE NOT NULL",
            "available_at TIMESTAMPTZ NOT NULL",
            "recorded_at TIMESTAMPTZ NOT NULL",
            "restatement_version INTEGER NOT NULL",
            "restatement_status TEXT NOT NULL",
            "supersedes_fact_id BIGINT",
            "WHERE is_current",
            "research.record_company_statement_fact",
            "research.company_statement_series_as_of",
            "p_years INTEGER DEFAULT 15",
            "fact.available_at <= p_as_of",
            "fact.recorded_at <= p_as_of",
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, self.migration)

    def test_observations_require_normalized_evidence(self) -> None:
        evidence_bound_tables = (
            "company_statement_facts",
            "company_segments",
            "company_segment_facts",
            "operational_kpi_definitions",
            "operational_kpi_observations",
            "market_share_observations",
            "peer_sets",
            "peer_set_memberships",
            "management_communications",
            "management_claims",
            "management_claim_outcomes",
            "investment_dossier_sections",
            "investment_dossier_refresh_triggers",
            "fundamental_specialist_opinions",
            "fundamental_acceptance_runs",
            "fundamental_acceptance_gates",
        )
        for table in evidence_bound_tables:
            with self.subTest(table=table):
                match = re.search(
                    rf"CREATE TABLE IF NOT EXISTS research\.{table}\s*\((.*?)\n\);",
                    self.migration,
                    flags=re.DOTALL,
                )
                self.assertIsNotNone(match)
                self.assertRegex(
                    match.group(1),
                    r"(?:evidence_id|verification_evidence_id) BIGINT NOT NULL REFERENCES research\.fundamental_evidence\(id\)",
                )

        self.assertIn("chk_fundamental_evidence_locator", self.migration)
        self.assertIn(
            "num_nonnulls(source_document_id, corporate_filing_id, raw_artifact_id, nullif(source_url, '')) > 0",
            self.migration,
        )
        self.assertIn("verification_status = 'human_verified'", self.migration)

    def test_company_verification_fk_is_idempotently_guarded(self) -> None:
        self.assertRegex(
            self.migration,
            re.compile(
                r"DO \$\$.*IF NOT EXISTS \(.*FROM pg_constraint.*"
                r"conname = 'fk_research_company_verification_evidence'.*"
                r"conrelid = 'research\.companies'::regclass.*"
                r"ADD CONSTRAINT fk_research_company_verification_evidence.*END IF;.*\$\$;",
                flags=re.DOTALL,
            ),
        )
        self.assertEqual(self.migration.count("ADD CONSTRAINT fk_research_company_verification_evidence"), 1)

    def test_dossier_contract_covers_all_fifteen_sections_and_portfolio_fit(self) -> None:
        required_sections = (
            "executive_conclusion",
            "industry_value_chain",
            "business_model_unit_economics",
            "segments_geography_customers",
            "market_size_share_competition",
            "moat_durability",
            "management_capital_allocation",
            "ten_year_financial_teardown",
            "forensic_accounting_governance",
            "peer_benchmarking",
            "operating_scenarios",
            "valuation",
            "catalysts_thesis_killers_monitoring",
            "portfolio_fit_opportunity_cost",
            "specialist_opinions_committee_decision",
        )
        for section in required_sections:
            with self.subTest(section=section):
                self.assertIn(f"'{section}'", self.migration)

        specialist_keys = re.search(
            r"CONSTRAINT chk_fundamental_specialist_key CHECK \(specialist_key IN \((.*?)\)\)",
            self.migration,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(specialist_keys)
        self.assertEqual(specialist_keys.group(1).count("'financial_quality'"), 1)
        self.assertIn("'portfolio_fit'", specialist_keys.group(1))

    def test_refresh_and_real_company_acceptance_are_first_class(self) -> None:
        for trigger_type in (
            "results",
            "filing",
            "earnings_call",
            "annual_report",
            "annual_letter",
            "credit_rating_change",
            "material_news",
        ):
            self.assertIn(f"'{trigger_type}'", self.migration)

        self.assertIn("research.open_real_company_acceptance_run", self.migration)
        self.assertIn("chk_fundamental_acceptance_real_company CHECK (real_company_verified)", self.migration)
        self.assertIn("real_company_verified_at IS NOT NULL", self.migration)
        self.assertIn("research.v_real_company_acceptance_status", self.migration)

    def test_api_read_models_are_present(self) -> None:
        for read_model in (
            "research.v_company_statement_facts_current",
            "research.v_management_claim_scorecard",
            "research.v_latest_investment_dossiers",
            "research.v_dossier_refresh_queue",
            "research.v_company_fundamental_coverage",
            "research.v_real_company_acceptance_status",
        ):
            with self.subTest(read_model=read_model):
                self.assertIn(f"CREATE OR REPLACE VIEW {read_model}", self.migration)

    def test_migration_contains_no_seed_or_example_company_rows(self) -> None:
        self.assertIsNone(
            re.search(
                r"INSERT\s+INTO\s+research\.companies",
                self.migration,
                flags=re.IGNORECASE,
            )
        )
        self.assertNotRegex(self.migration, r"(?i)\b(seed|example|demo|sample)_company\b")


if __name__ == "__main__":
    unittest.main()
