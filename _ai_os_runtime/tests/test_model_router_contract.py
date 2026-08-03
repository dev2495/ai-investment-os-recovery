from __future__ import annotations

import unittest
from pathlib import Path


class ModelRouterContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime_root = Path(__file__).resolve().parents[1]
        cls.assistant = (
            cls.runtime_root / "ai-office-ui" / "src" / "assistant" / "AssistantRail.tsx"
        ).read_text(encoding="utf-8")
        cls.registry = (
            cls.runtime_root / "config" / "model_routes.yml"
        ).read_text(encoding="utf-8")
        cls.migration = "\n".join(
            (cls.runtime_root / "postgres" / "init" / migration_name).read_text(encoding="utf-8")
            for migration_name in (
                "176_hybrid_luna_model_router_v1.sql",
                "177_final_hybrid_model_fleet_v1.sql",
                "178_hybrid_model_router_v2.sql",
                "179_model_fallback_precedence_v1.sql",
            )
        )

    def test_operator_defaults_to_private_local_route_and_uses_luna_for_volume(self) -> None:
        self.assertIn(
            'local: { routeName: "charlie_munger_orchestration", privateContext: true }',
            self.assistant,
        )
        self.assertIn(
            'fast: { routeName: "openrouter_luna_volume", privateContext: false }',
            self.assistant,
        )
        self.assertIn(
            'React.useState<ReasoningRoute>("local")',
            self.assistant,
        )
        self.assertIn("Capped Luna volume model; no client data", self.assistant)
        self.assertIn(
            'research: { routeName: "openrouter_gemini36_research", privateContext: false }',
            self.assistant,
        )
        self.assertIn(
            'deep: { routeName: "openrouter_terra_research", privateContext: false }',
            self.assistant,
        )
        self.assertIn(
            'review: { routeName: "openrouter_sol_review", privateContext: false }',
            self.assistant,
        )

    def test_registry_matches_hybrid_cost_and_privacy_policy(self) -> None:
        required_registry_fragments = (
            "version: 5",
            "model: mlx-community/Qwen3.5-9B-4bit",
            "production_fallback_model: prism-ml/Bonsai-27B-Q1_0",
            "status: production_conversation_only",
            "model: nanbeige/nanbeige4.2:3b-Q4_K_M",
            "fallback_route: nanbeige42_local_assistant",
            "openrouter_luna_volume:",
            "openrouter_gemini36_research:",
            "default_model: google/gemini-3.6-flash",
            "always_on_daily_driver:",
            "local_workhorse_synthesis:",
            "multimodal_document_analysis:",
            "default_model: openai/gpt-5.6-luna",
            "openrouter_terra_research:",
            "default_model: openai/gpt-5.6-terra",
            "openrouter_sol_review:",
            "default_model: openai/gpt-5.6-sol",
            "monthly_soft_cap: 3000",
            "monthly_hard_cap: 4500",
            "daily_hard_cap: 150",
            "heavy_route_reserve_pct: 20",
            "client_private_cloud: false",
            "broker_writes: false",
            "default_model: deterministic_research_compiler_v1",
        )
        for fragment in required_registry_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.registry)

    def test_database_policy_enforces_same_global_budget(self) -> None:
        self.assertIn(
            "'ai_os_cloud', 'INR', 3000, 4500, 150, 90, 20, true, 'active'",
            self.migration,
        )
        self.assertIn("'openrouter_terra_research'", self.migration)
        self.assertIn("'openrouter_sol_review'", self.migration)
        self.assertIn("'openrouter_gemini36_research'", self.migration)
        self.assertIn("'google/gemini-3.6-flash'", self.migration)
        self.assertIn("CREATE OR REPLACE FUNCTION agent.activate_final_local_model_fleet()", self.migration)
        self.assertIn("registry.promotion_status='approved'", self.migration)
        self.assertIn("registry.eval_suite='conversation_v1'", self.migration)
        self.assertIn('"kv_cache_quantization":false', self.migration)
        self.assertIn("broker_writes_allowed',false", self.migration)
        self.assertIn("WHEN nanbeige_ready THEN 'nanbeige42_local_assistant'", self.migration)
        self.assertIn("WHEN qwen2_ready THEN 'imac_qwen35_2b_private'", self.migration)
        self.assertIn("'fallback_precedence'", self.migration)


if __name__ == "__main__":
    unittest.main()
