from __future__ import annotations

import unittest
from unittest import mock

from _ai_os_runtime.api import ai_os_api_server


class LunaModelRoutePolicyTest(unittest.TestCase):
    @staticmethod
    def fake_psql(query: str):
        if "FROM agent.profiles profile" in query:
            return [{
                "agent_name": "Charlie Munger",
                "department": "executive",
                "primary_route": "charlie_munger_orchestration",
                "fallback_route": None,
                "escalation_route": "openrouter_luna_volume",
                "max_autonomous_cost_tier": "cloud_low",
                "cloud_requires_approval": True,
                "autonomous_cloud_allowed": False,
                "cap_max_cost_tier": "frontier",
                "hard_stop_on_breach": True,
                "daily_cap_usd": 1.666667,
                "monthly_cap_usd": 50,
                "cost_today_usd": 0,
                "cost_month_usd": 0,
                "daily_remaining_usd": 1.666667,
                "monthly_remaining_usd": 50,
                "cap_status": "ok",
            }]
        if "FROM agent.model_routes" in query:
            if "openrouter_luna_volume" not in query:
                return []
            return [{
                "route_name": "openrouter_luna_volume",
                "task_class": "public_internal_routine_conversation_and_drafts",
                "default_provider": "openrouter",
                "default_model": "openai/gpt-5.6-luna",
                "escalation_provider": "openai",
                "escalation_model": "gpt-5.6-terra",
                "max_cost_tier": "cloud_low",
                "notes": "Capped public/internal volume route.",
                "enabled": True,
            }]
        if "FROM agent.model_cost_rates" in query:
            return [{
                "id": 1,
                "cost_tier": "cloud_low",
                "input_usd_per_1m_tokens": 0.50,
                "output_usd_per_1m_tokens": 3.00,
                "rate_source": "test_rate",
                "effective_at": "2026-08-01T00:00:00Z",
            }]
        if "FROM agent.v_system_model_budget_status" in query:
            return [{
                "policy_key": "ai_os_cloud",
                "daily_remaining_usd": 1.5,
                "monthly_remaining_usd": 45,
                "budget_status": "ok",
            }]
        if "FROM agent.model_privacy_policies" in query:
            return [{
                "privacy_class": "internal",
                "cloud_model_allowed": True,
                "cache_allowed": False,
                "retention_days": 0,
                "max_context_chars": 100000,
            }]
        raise AssertionError(f"Unexpected SQL: {query}")

    @staticmethod
    def fake_statement(query: str):
        if "INSERT INTO agent.model_call_decisions" in query:
            allowed = "'allowed'" in query
            privacy_class = "client_private" if "'client_private'" in query else "internal"
            return [{
                "id": 9001,
                "decision_key": "test-luna-decision",
                "requested_route": "openrouter_luna_volume",
                "selected_route": "openrouter_luna_volume" if allowed else None,
                "selected_provider": "openrouter" if allowed else None,
                "selected_model": "openai/gpt-5.6-luna" if allowed else None,
                "privacy_class": privacy_class,
                "contains_client_data": not allowed,
                "decision_status": "allowed" if allowed else "blocked",
                "cache_status": "bypassed",
                "block_reasons": [] if allowed else [
                    "cloud_route_blocks_client_private_context"
                ],
                "route_candidates": [{
                    "route_name": "openrouter_luna_volume",
                    "provider": "openrouter",
                    "model_name": "openai/gpt-5.6-luna",
                    "available_for_chat": allowed,
                    "reason": (
                        "available_explicit_approval"
                        if allowed
                        else "cloud_route_blocks_client_private_context"
                    ),
                }],
            }]
        raise AssertionError(f"Unexpected statement SQL: {query}")

    def choose(self, *, privacy_class: str, contains_client_data: bool):
        with (
            mock.patch.object(ai_os_api_server, "OPENROUTER_API_KEY", "test-key"),
            mock.patch.object(ai_os_api_server, "run_psql_json", self.fake_psql),
            mock.patch.object(
                ai_os_api_server,
                "run_psql_json_statement",
                self.fake_statement,
            ),
        ):
            return ai_os_api_server.choose_chat_model_call(
                {
                    "assistant_name": "Charlie Munger",
                    "route_name": "openrouter_luna_volume",
                    "privacy_class": privacy_class,
                    "contains_client_data": contains_client_data,
                    "cloud_approved": True,
                    "session_key": "test-luna",
                },
                "Summarize public market developments without client data.",
            )

    def test_explicit_internal_luna_route_is_allowed_under_budget(self) -> None:
        decision = self.choose(privacy_class="internal", contains_client_data=False)

        self.assertEqual(decision["decision_status"], "allowed")
        self.assertEqual(decision["selected_route"], "openrouter_luna_volume")
        self.assertEqual(decision["selected_provider"], "openrouter")
        self.assertEqual(decision["selected_model"], "openai/gpt-5.6-luna")
        self.assertEqual(decision["block_reasons"], [])

    def test_luna_route_rejects_client_private_context(self) -> None:
        decision = self.choose(
            privacy_class="client_private",
            contains_client_data=True,
        )

        self.assertEqual(decision["decision_status"], "blocked")
        self.assertIsNone(decision["selected_route"])
        candidates = decision["route_candidates"]
        self.assertEqual(candidates[0]["reason"], "cloud_route_blocks_client_private_context")


if __name__ == "__main__":
    unittest.main()
