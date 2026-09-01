from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from _ai_os_runtime.api import ai_os_api_server


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
                "182_model_route_reconciliation_v1.sql",
            )
        )
        cls.route_reconciliation_migrations = "\n".join(
            (cls.runtime_root / "postgres" / "init" / migration_name).read_text(encoding="utf-8")
            for migration_name in (
                "179_model_fallback_precedence_v1.sql",
                "182_model_route_reconciliation_v1.sql",
            )
        )

    def test_operator_defaults_to_private_local_route_and_uses_gemini_for_fast_public_chat(self) -> None:
        self.assertIn(
            'local: { routeName: "charlie_munger_orchestration", privateContext: true }',
            self.assistant,
        )
        self.assertIn(
            'fast: { routeName: "openrouter_gemini36_research", privateContext: false }',
            self.assistant,
        )
        self.assertIn(
            'React.useState<ReasoningRoute>("local")',
            self.assistant,
        )
        self.assertIn("Gemini Flash quick answer with verified local stack snapshot; no client data", self.assistant)
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
            "version: 9",
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
            "monthly_hard_cap: 4000",
            "daily_hard_cap: 150",
            "heavy_route_reserve_pct: 20",
            "client_private_cloud: false",
            "broker_writes: false",
            "default_model: deterministic_research_compiler_v1",
            "cloud.volume.default:",
            "default_model: deepseek/deepseek-v4-flash",
            "cloud.complex.escalation:",
            "default_model: z-ai/glm-5.2",
            "specialist.lead_engineer:",
            "public_research_daily_driver:",
            "candidate: z-ai/glm-5.3-flash",
            "promotion_endpoint: /api/research/model-runs/canary/review-promote",
            "paid_runs_after_promotion: per_run_preflight_required",
            "explicit_human_confirmation_before_live_execution: true",
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


    def test_final_migration_reconciles_route_enablement_and_activates_fleet(self) -> None:
        self.assertIn("SET enabled=nanbeige_ready", self.migration)
        self.assertIn("SET enabled=qwen2_ready", self.migration)
        self.assertIn("SET enabled=bonsai_ready", self.migration)
        self.assertIn("SELECT agent.activate_final_local_model_fleet();", self.migration)

    def test_route_reconciliation_matches_model_routes_schema(self) -> None:
        pre_function = self.route_reconciliation_migrations.split("CREATE OR REPLACE FUNCTION", 1)[0]
        self.assertNotIn("updated_at=now()", pre_function)
        self.assertNotIn("SET enabled=nanbeige_ready, updated_at=now()", self.route_reconciliation_migrations)
        self.assertNotIn("SET enabled=qwen2_ready, updated_at=now()", self.route_reconciliation_migrations)
        self.assertNotIn("SET enabled=bonsai_ready, updated_at=now()", self.route_reconciliation_migrations)

    def test_local_openai_resolution_fails_closed_without_exact_endpoint(self) -> None:
        with (
            mock.patch.object(ai_os_api_server, "run_psql_json", side_effect=RuntimeError("db unavailable")),
            mock.patch.object(ai_os_api_server, "http_json") as http_json,
        ):
            endpoint = ai_os_api_server.local_openai_endpoint("approved/model")
            available = ai_os_api_server.local_openai_model_available("approved/model")

        self.assertFalse(endpoint["resolved"])
        self.assertEqual(endpoint["base_url"], "")
        self.assertEqual(endpoint["request_model"], "")
        self.assertFalse(available)
        http_json.assert_not_called()

    def test_local_openai_requires_exact_runtime_model_alias(self) -> None:
        endpoint = {
            "resolved": True,
            "base_url": "http://127.0.0.1:11436/v1",
            "request_model": "expected-alias",
        }
        with (
            mock.patch.object(ai_os_api_server, "local_openai_endpoint", return_value=endpoint),
            mock.patch.object(ai_os_api_server, "http_json", return_value={"data": [{"id": "different-alias"}]}),
        ):
            self.assertFalse(ai_os_api_server.local_openai_model_available("approved/model"))

    def test_missing_route_is_deterministic_and_disabled(self) -> None:
        with mock.patch.object(ai_os_api_server, "run_psql_json", return_value=[]):
            route = ai_os_api_server.get_model_route("missing")
        self.assertEqual(route["default_provider"], "local_tools")
        self.assertEqual(route["default_model"], "deterministic_router_v1")
        self.assertFalse(route["enabled"])
        self.assertIsNone(route["escalation_provider"])

    def test_setup_scripts_cannot_overwrite_charlie_assignment(self) -> None:
        scripts = sorted((self.runtime_root / "scripts").glob("setup_imac_*assistant.sh"))
        self.assertGreaterEqual(len(scripts), 6)
        for script in scripts:
            source = script.read_text(encoding="utf-8")
            with self.subTest(script=script.name):
                self.assertNotIn("UPDATE agent.agent_model_assignments", source)
                self.assertIn("SELECT agent.activate_final_local_model_fleet();", source)

if __name__ == "__main__":
    unittest.main()
