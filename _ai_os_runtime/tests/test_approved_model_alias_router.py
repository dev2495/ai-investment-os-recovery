import pathlib
import unittest


class ApprovedModelAliasRouterContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime_root = pathlib.Path(__file__).resolve().parents[1]
        cls.config = (cls.runtime_root / "config" / "model_routes.yml").read_text()
        cls.migration = (
            cls.runtime_root
            / "postgres"
            / "init"
            / "218_approved_model_alias_router_v1.sql"
        ).read_text()

    def test_cloud_alias_chain_is_centralized(self):
        for value in (
            "cloud.volume.default",
            "deepseek/deepseek-v4-flash",
            "cloud.complex.escalation",
            "z-ai/glm-5.2",
            "AI_OS_OPENROUTER_API_KEY",
        ):
            self.assertIn(value, self.config)
            self.assertIn(value, self.migration)

    def test_heavy_models_are_named_and_not_routine(self):
        for alias in (
            "specialist.lead_engineer",
            "specialist.senior_investment_reviewer",
            "specialist.final_strategy_writer",
        ):
            self.assertIn(alias, self.config)
            self.assertIn(alias, self.migration)
        self.assertIn("committee_duplication", self.config)
        self.assertIn("approval_only_unbound", self.migration)

    def test_budget_and_trading_gates_are_explicit(self):
        for value in (
            "monthly_soft_cap: 3000",
            "monthly_hard_cap: 4000",
            "client_or_restricted_data: local_only_no_cloud_fallback",
            "explicit_human_confirmation_before_live_execution: true",
        ):
            self.assertIn(value, self.config)
        self.assertIn("monthly_hard_cap_inr = 4000", self.migration)
        self.assertIn("live_trade_execution", self.migration)
        self.assertIn("blocked_by_default", self.migration)

    def test_task_declaration_and_trace_contract(self):
        for value in (
            "task_type",
            "risk",
            "tools",
            "context_need",
            "latency",
            "cost_ceiling_inr",
            "data_boundary",
            "approval_required",
            "trace_id",
            "decision_reason",
            "usage_event_id",
        ):
            self.assertIn(value, self.config)
        self.assertIn("agent.v_model_router_registry", self.migration)


if __name__ == "__main__":
    unittest.main()
