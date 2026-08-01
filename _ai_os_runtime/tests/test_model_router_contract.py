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
        cls.migration = (
            cls.runtime_root / "postgres" / "init" / "176_hybrid_luna_model_router_v1.sql"
        ).read_text(encoding="utf-8")

    def test_operator_defaults_to_private_bonsai_and_uses_luna_for_volume(self) -> None:
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
        self.assertNotIn(
            'fast: { routeName: "openrouter_research_fast"',
            self.assistant,
        )

    def test_registry_matches_hybrid_cost_and_privacy_policy(self) -> None:
        required_registry_fragments = (
            "version: 3",
            "model: prism-ml/Bonsai-27B-Q1_0",
            "fallback_model: nanbeige/nanbeige4.2:3b-Q4_K_M",
            "openrouter_luna_volume:",
            "always_on_daily_driver:",
            "local_workhorse_synthesis:",
            "multimodal_document_analysis:",
            "default_model: openai/gpt-5.6-luna",
            "default_model: minimax/minimax-m3",
            "default_model: z-ai/glm-5.2",
            "monthly_soft_cap: 3000",
            "monthly_hard_cap: 4500",
            "daily_hard_cap: 150",
            "heavy_route_reserve_pct: 20",
            "client_private_cloud: false",
            "broker_writes: false",
        )
        for fragment in required_registry_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.registry)

    def test_database_policy_enforces_same_global_budget(self) -> None:
        self.assertIn(
            "'ai_os_cloud', 'INR', 3000, 4500, 150, 90, 20, true, 'active'",
            self.migration,
        )
        self.assertIn(
            "('openrouter_luna_volume','public_internal_routine_conversation_and_drafts'",
            self.migration,
        )
        self.assertIn(
            "SET escalation_route='openrouter_luna_volume'",
            self.migration,
        )


if __name__ == "__main__":
    unittest.main()
