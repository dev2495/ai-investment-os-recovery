from __future__ import annotations

import unittest
from unittest.mock import Mock

from _ai_os_runtime.api import research_model_runtime as runtime


class ResearchModelRuntimeTest(unittest.TestCase):
    def test_rejects_private_cloud_preflight(self):
        with self.assertRaises(ValueError):
            runtime.create_model_run_preflight(
                {"public_only": True, "contains_private_data": True, "runs": []},
                run_rows=Mock(return_value=[]), run_statement=Mock(), sql_literal=repr, sql_jsonb=repr
            )

    def test_qwen_is_not_a_runnable_zdr_canary(self):
        self.assertNotIn("openrouter_public_lead_qwen38_max_canary", runtime.PUBLIC_CANARY_ROUTES)

    def test_fixed_packet_has_no_private_context_or_tool_instruction(self):
        packet = runtime._public_ushamart_packet().lower()
        self.assertIn("bounded public packet", packet)
        self.assertNotIn("portfolio", packet)
        self.assertNotIn("browse", packet.replace("do not browse", ""))

    def test_disabled_route_blocks_preflight(self):
        rows = [{
            "route_name": "disabled", "default_provider": "openrouter",
            "default_model": "model", "max_cost_tier": "cloud_low", "enabled": False,
            "daily_cap_usd": 1, "monthly_cap_usd": 10,
            "cloud_requires_approval": True, "autonomous_cloud_allowed": False,
            "agent_status": "active", "rate_id": 1,
            "input_usd_per_1m_tokens": 0.1, "output_usd_per_1m_tokens": 0.2,
            "rate_source": "test", "effective_at": "2026-08-24T00:00:00Z",
        }]
        plan, reasons = runtime._route_plan(
            {"runs": [{"agent_name": "Company Analyst", "route_name": "disabled",
                        "prompt_tokens_est": 100, "completion_tokens_max": 100, "max_calls": 1}]},
            Mock(return_value=rows), repr,
        )
        self.assertEqual(len(plan), 1)
        self.assertIn("route_disabled:disabled", reasons)


    def test_glm53_canary_route_is_allowlisted_but_normal_disabled_use_stays_blocked(self):
        route = "openrouter_public_lead_glm53_flash_canary"
        self.assertIn(route, runtime.PUBLIC_CANARY_ROUTES)
        rows = [{
            "route_name": route, "default_provider": "openrouter",
            "default_model": "z-ai/glm-5.3-flash", "max_cost_tier": "cloud_low",
            "enabled": False, "daily_cap_usd": 1, "monthly_cap_usd": 10,
            "cloud_requires_approval": True, "autonomous_cloud_allowed": False,
            "agent_status": "active", "rate_id": 53,
            "input_usd_per_1m_tokens": 0.15, "output_usd_per_1m_tokens": 0.50,
            "rate_source": "openrouter_model_page_2026_09_01",
            "effective_at": "2026-09-01T00:00:00Z",
        }]
        run = {"agent_name": "Company Analyst", "route_name": route,
               "prompt_tokens_est": 100, "completion_tokens_max": 100, "max_calls": 1}
        normal_plan, normal_reasons = runtime._route_plan(
            {"request_kind": "research_case", "runs": [run]}, Mock(return_value=rows), repr,
        )
        self.assertEqual(len(normal_plan), 1)
        self.assertIn(f"route_disabled:{route}", normal_reasons)
        canary_plan, canary_reasons = runtime._route_plan(
            {"request_kind": "canary", "runs": [run]}, Mock(return_value=rows), repr,
        )
        self.assertEqual(canary_reasons, [])
        self.assertTrue(canary_plan[0]["canary_route_override"])
        self.assertFalse(canary_plan[0]["route_enabled"])


    def test_daily_driver_promotion_requires_named_human_review(self):
        with self.assertRaisesRegex(ValueError, "operator_confirmed"):
            runtime.review_and_promote_public_model_canary(
                {"canary_id": 53},
                run_rows=Mock(), run_statement=Mock(), sql_literal=repr, sql_jsonb=repr,
            )

    def test_daily_driver_promotion_rejects_weak_numeric_or_citation_review(self):
        payload = {
            "canary_id": 53,
            "operator_confirmed": True,
            "approve_for_daily_driver": True,
            "reviewer": "Test reviewer",
            "rationale": "Reviewed every cited number against the fixed packet.",
            "reviewed_response_hash": "a" * 64,
            "source_citations_checked": True,
            "citation_accuracy_score": 89,
            "numeric_accuracy_score": 95,
            "unsupported_claim_count": 0,
        }
        with self.assertRaisesRegex(ValueError, "citation score"):
            runtime.review_and_promote_public_model_canary(
                payload,
                run_rows=Mock(), run_statement=Mock(), sql_literal=repr, sql_jsonb=repr,
            )

    def test_daily_driver_promotion_binds_review_hash_and_preserves_hard_gates(self):
        response_hash = "b" * 64
        canary = {
            "id": 53,
            "candidate_route": "openrouter_public_lead_glm53_flash_canary",
            "candidate_model": "z-ai/glm-5.3-flash",
            "packet_public_only": True,
            "status": "completed",
            "max_cost_tier": "cloud_low",
            "score": {
                "structured_output_valid": True,
                "response_hash": response_hash,
                "requires_human_citation_review": True,
                "auto_promotion": False,
            },
        }
        persisted = {
            "canary_id": 53,
            "daily_driver_route": "openrouter_research_fast",
            "daily_driver_model": "z-ai/glm-5.3-flash",
            "public_only": True,
            "broker_write_allowed": False,
            "paid_runs_still_require_preflight": True,
        }
        statement = Mock(return_value=[persisted])
        result = runtime.review_and_promote_public_model_canary(
            {
                "canary_id": 53,
                "operator_confirmed": True,
                "approve_for_daily_driver": True,
                "reviewer": "Test reviewer",
                "rationale": "Every citation and numerical value matches the bounded public packet.",
                "reviewed_response_hash": response_hash,
                "source_citations_checked": True,
                "citation_accuracy_score": 100,
                "numeric_accuracy_score": 100,
                "unsupported_claim_count": 0,
            },
            run_rows=Mock(return_value=[canary]),
            run_statement=statement,
            sql_literal=repr,
            sql_jsonb=repr,
        )
        sql = statement.call_args.args[0]
        self.assertIn("route_name='openrouter_research_fast'", sql)
        self.assertIn("selection_role'='public_research_daily_driver'", sql)
        self.assertNotIn("candidate_route=(SELECT candidate_route FROM target)", sql)
        self.assertIn("'research.public.daily_driver'", sql)
        self.assertIn("approval_required=true", sql)
        self.assertIn("'public_only'", sql)
        self.assertIn("'broker_write_allowed',false", sql)
        self.assertFalse(result["model_invoked"])
        self.assertEqual(result["daily_driver_model"], "z-ai/glm-5.3-flash")

    def test_daily_driver_promotion_rejects_response_hash_mismatch(self):
        canary = {
            "id": 53,
            "candidate_route": "openrouter_public_lead_glm53_flash_canary",
            "candidate_model": "z-ai/glm-5.3-flash",
            "packet_public_only": True,
            "status": "completed",
            "max_cost_tier": "cloud_low",
            "score": {"structured_output_valid": True, "response_hash": "a" * 64},
        }
        with self.assertRaisesRegex(ValueError, "does not match"):
            runtime.review_and_promote_public_model_canary(
                {
                    "canary_id": 53,
                    "operator_confirmed": True,
                    "approve_for_daily_driver": True,
                    "reviewer": "Test reviewer",
                    "rationale": "Every citation and numerical value was checked carefully.",
                    "reviewed_response_hash": "b" * 64,
                    "source_citations_checked": True,
                    "citation_accuracy_score": 100,
                    "numeric_accuracy_score": 100,
                    "unsupported_claim_count": 0,
                },
                run_rows=Mock(return_value=[canary]),
                run_statement=Mock(),
                sql_literal=repr,
                sql_jsonb=repr,
            )


if __name__ == "__main__":
    unittest.main()
