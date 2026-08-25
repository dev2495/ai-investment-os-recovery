from __future__ import annotations

import re
import unittest
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
MIGRATION = RUNTIME_ROOT / "postgres" / "init" / "186_sector_intelligence_v1.sql"


class SectorIntelligenceSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")

    def test_migration_is_transactional_and_does_not_seed_market_data(self) -> None:
        self.assertTrue(self.sql.startswith("BEGIN;"))
        self.assertTrue(self.sql.rstrip().endswith("COMMIT;"))
        self.assertNotRegex(self.sql, re.compile(r"\bINSERT\s+INTO\b", re.IGNORECASE))
        self.assertNotIn("seed", self.sql.lower())
        self.assertNotIn("fake", self.sql.lower())

    def test_taxonomy_and_temporal_membership_are_normalized(self) -> None:
        for contract in (
            "CREATE SCHEMA IF NOT EXISTS sector_intelligence",
            "sector_intelligence.taxonomy_nodes",
            "node_level IN ('sector', 'industry', 'sub_industry')",
            "parent_id BIGINT REFERENCES sector_intelligence.taxonomy_nodes",
            "sector_intelligence.instrument_membership_history",
            "symbol_id BIGINT NOT NULL REFERENCES trading.symbols(id)",
            "valid_from DATE NOT NULL",
            "valid_to DATE",
            "chk_sector_membership_validity",
            "v_sector_hierarchy",
        ):
            self.assertIn(contract, self.sql)

    def test_metrics_aggregates_valuation_market_share_and_capacity_have_lineage(self) -> None:
        for table in (
            "metric_definitions",
            "metric_observations",
            "sector_aggregates",
            "valuation_bands",
            "market_share_observations",
            "capacity_observations",
        ):
            self.assertIn(f"sector_intelligence.{table}", self.sql)

        for lineage_field in (
            "source_system_id",
            "source_reference",
            "calculation_version",
            "methodology_version",
            "input_fingerprint",
            "quality_status",
        ):
            self.assertIn(lineage_field, self.sql)

        self.assertIn("'financial', 'valuation', 'operating', 'market_share', 'capacity'", self.sql)
        self.assertIn("ratio_of_sums", self.sql)
        self.assertIn("percentile_rank BETWEEN 0 AND 100", self.sql)

    def test_custom_indices_own_constituents_weights_rebalances_and_history(self) -> None:
        for table in (
            "custom_index_definitions",
            "custom_index_constituents",
            "custom_index_rebalances",
            "custom_index_weights",
            "custom_index_history",
        ):
            self.assertIn(f"sector_intelligence.{table}", self.sql)

        self.assertIn("selection_rules JSONB NOT NULL", self.sql)
        self.assertIn("weighting_rules JSONB NOT NULL", self.sql)
        self.assertIn("target_weight BETWEEN 0 AND 1", self.sql)
        self.assertIn("input_fingerprint TEXT NOT NULL", self.sql)
        self.assertIn("v_custom_index_control", self.sql)

    def test_relative_strength_breadth_and_market_monitors_cover_required_horizons(self) -> None:
        self.assertIn("sector_intelligence.relative_strength_observations", self.sql)
        self.assertIn("sector_intelligence.breadth_observations", self.sql)
        self.assertGreaterEqual(
            self.sql.count("horizon IN ('1D', '1W', '1M', '3M', '6M', '1Y', 'cycle')"),
            2,
        )
        self.assertIn("sector_intelligence.market_monitor_observations", self.sql)
        self.assertIn("market_segment IN ('cash', 'futures', 'options')", self.sql)
        self.assertIn("contract_expiry", self.sql)
        self.assertIn("option_type", self.sql)
        self.assertIn("strike", self.sql)

    def test_flow_and_ownership_contracts_cover_institutional_disclosures(self) -> None:
        self.assertIn("sector_intelligence.flow_observations", self.sql)
        self.assertIn("sector_intelligence.ownership_observations", self.sql)
        for category in (
            "'FII'",
            "'DII'",
            "'mutual_fund'",
            "'promoter'",
            "'insider'",
            "'bulk_deal'",
            "'block_deal'",
            "'shareholding_pattern'",
            "'pledge'",
        ):
            self.assertIn(category, self.sql)

    def test_sensitivities_classification_ranking_and_research_controls_exist(self) -> None:
        for table in (
            "raw_material_sensitivities",
            "macro_sensitivities",
            "sector_classifications",
            "sector_rankings",
            "research_coverage",
            "sector_committee_packets",
            "portfolio_manager_mandates",
        ):
            self.assertIn(f"sector_intelligence.{table}", self.sql)

        for view in (
            "v_sector_committee_control",
            "v_sector_portfolio_manager_control",
            "v_sector_data_freshness",
        ):
            self.assertIn(f"sector_intelligence.{view}", self.sql)

        self.assertIn("human_final_required BOOLEAN NOT NULL DEFAULT true", self.sql)
        self.assertIn("capital_action_allowed BOOLEAN NOT NULL DEFAULT false", self.sql)
        self.assertIn("broker_order_allowed BOOLEAN NOT NULL DEFAULT false", self.sql)
        self.assertIn("chk_sector_pm_broker_guard CHECK (broker_order_allowed = false)", self.sql)

    def test_tradingview_is_artifact_consumer_not_authoritative_warehouse(self) -> None:
        self.assertIn("sector_intelligence.generated_chart_artifacts", self.sql)
        self.assertIn("target_workspace TEXT NOT NULL DEFAULT 'tradingview_desktop'", self.sql)
        self.assertIn("chk_sector_chart_target CHECK (target_workspace = 'tradingview_desktop')", self.sql)
        self.assertIn("generated_expression", self.sql)
        self.assertIn("pine_source", self.sql)
        self.assertIn("chart_layout", self.sql)
        self.assertIn("TradingView Desktop is an artifact consumer only", self.sql)
        self.assertNotIn("tradingview_web", self.sql.lower())
        artifact_table = self.sql.split(
            "CREATE TABLE IF NOT EXISTS sector_intelligence.generated_chart_artifacts",
            1,
        )[1].split("CREATE OR REPLACE VIEW", 1)[0]
        self.assertNotIn("broker_order", artifact_table)


if __name__ == "__main__":
    unittest.main()
