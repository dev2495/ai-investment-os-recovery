from __future__ import annotations

import unittest
from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "postgres"
    / "init"
    / "187_institutional_options_analytics_v1.sql"
)


class InstitutionalOptionsSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")

    def test_foundation_relations_cover_the_institutional_options_scope(self) -> None:
        for relation in (
            "trading.option_chain_snapshot_batches",
            "trading.option_chain_contract_snapshots",
            "trading.option_valuation_inputs",
            "trading.option_iv_greeks_results",
            "trading.option_premium_series",
            "trading.option_buildup_classifications",
            "trading.option_strike_migrations",
            "trading.option_oi_heatmap_cells",
            "trading.option_volatility_metrics",
            "trading.option_expected_move_bands",
            "trading.option_exposure_estimates",
            "trading.option_participant_positions",
            "trading.option_futures_positions",
            "trading.option_analytics_alerts",
            "trading.option_paper_trade_attributions",
            "trading.option_replay_sessions",
            "trading.option_replay_frames",
            "trading.option_specialist_observations",
            "trading.option_acceptance_gate_runs",
            "trading.option_acceptance_gate_results",
            "trading.v_institutional_option_chain",
            "trading.v_option_acceptance_gate_summary",
        ):
            self.assertIn(relation, self.sql)

    def test_chain_contract_records_event_time_staleness_and_liquidity(self) -> None:
        for contract in (
            "minute_ts TIMESTAMPTZ NOT NULL",
            "source_timestamp TIMESTAMPTZ NOT NULL",
            "received_at TIMESTAMPTZ NOT NULL",
            "staleness_threshold_seconds",
            "source_age_seconds",
            "freshness_status",
            "quote_source_timestamp",
            "spread_bps",
            "liquidity_score",
            "staleness_status",
            "liquidity_status",
            "source_payload_hash",
        ):
            self.assertIn(contract, self.sql)

    def test_iv_and_greeks_require_real_inputs_convergence_and_validation(self) -> None:
        for model_input in (
            "risk_free_rate",
            "dividend_yield",
            "forward_price",
            "forward_method",
            "rate_source_timestamp",
            "input_hash",
        ):
            self.assertIn(model_input, self.sql)

        for output in (
            "implied_volatility",
            "delta",
            "gamma",
            "theta",
            "vega",
            "rho",
            "model_version",
            "solver_version",
            "iteration_count",
            "residual",
            "calculation_hash",
            "quality_flags",
        ):
            self.assertIn(output, self.sql)

        self.assertIn("option_iv_greeks_validated_only", self.sql)
        self.assertIn("calculation_status = 'validated'", self.sql)
        self.assertIn("AND converged", self.sql)
        self.assertIn("calculation_status <> 'validated'", self.sql)
        self.assertIn("AND implied_volatility IS NULL AND delta IS NULL AND gamma IS NULL", self.sql)
        self.assertIn("validated_at IS NOT NULL AND validated_by IS NOT NULL", self.sql)

    def test_derived_analytics_preserve_versions_evidence_and_assumptions(self) -> None:
        for capability in (
            "'atm_straddle','strangle'",
            "'long_buildup','short_buildup','long_unwinding','short_covering'",
            "'max_open_interest','max_oi_change','call_wall','put_wall','volume_peak'",
            "'iv_percentile','iv_rank','skew','term_structure'",
            "'atm_straddle','validated_iv_lognormal','historical_empirical'",
            "'gex','dex','vanna','charm','gamma_flip'",
            "dealer_position_assumption",
            "open_interest_sign_method",
            "source_result_ids",
            "assumptions JSONB NOT NULL",
            "calculation_version",
        ):
            self.assertIn(capability, self.sql)

    def test_replay_paper_attribution_observations_and_gates_are_fail_closed(self) -> None:
        for contract in (
            "point_in_time_enforced BOOLEAN NOT NULL DEFAULT true CHECK (point_in_time_enforced=true)",
            "option_replay_no_lookahead",
            "paper_only BOOLEAN NOT NULL DEFAULT true CHECK (paper_only=true)",
            "capital_action_allowed BOOLEAN NOT NULL DEFAULT false CHECK (capital_action_allowed=false)",
            "option_specialist_published_evidence",
            "validated_greeks_ratio",
            "liquid_contract_ratio",
            "stale_contract_ratio",
            "replay_coverage_ratio",
            "paper_attribution_coverage_ratio",
            "option_acceptance_failure_reason",
        ):
            self.assertIn(contract, self.sql)

    def test_migration_has_no_seed_contracts_or_broker_write_path(self) -> None:
        normalized = " ".join(self.sql.lower().split())
        self.assertNotIn("insert into trading.option_", normalized)
        self.assertNotIn("broker_order", normalized)
        self.assertNotIn("execution_allowed boolean not null default true", normalized)
        self.assertGreaterEqual(
            self.sql.count(
                "broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false)"
            ),
            20,
        )
        self.assertIn("false AS broker_write_allowed", self.sql)


if __name__ == "__main__":
    unittest.main()
