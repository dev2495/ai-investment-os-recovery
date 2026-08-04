from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "postgres" / "init" / "188_institutional_data_operations_v1.sql"


class InstitutionalDataOperationsSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")

    def test_governed_expiring_valuation_policy(self) -> None:
        for contract in (
            "trading.option_valuation_policies",
            "risk_free_rate NUMERIC NOT NULL",
            "dividend_yield NUMERIC NOT NULL",
            "source_artifact_ref TEXT NOT NULL",
            "effective_from < expires_at",
            "validation_status <> 'validated' OR (validated_by IS NOT NULL AND validated_at IS NOT NULL)",
        ):
            self.assertIn(contract, self.sql)

    def test_durable_pipeline_status_and_readiness(self) -> None:
        for contract in (
            "ops.institutional_pipeline_runs",
            "calculations_blocked",
            "trading.v_option_analytics_readiness",
            "blocked_missing_valuation_policy",
            "blocked_expired_policy",
            "broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false)",
        ):
            self.assertIn(contract, self.sql)

    def test_migration_does_not_seed_market_assumptions(self) -> None:
        normalized = " ".join(self.sql.lower().split())
        self.assertNotIn("insert into trading.option_valuation_policies", normalized)
        self.assertNotIn("execution_allowed boolean not null default true", normalized)


if __name__ == "__main__":
    unittest.main()
