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


if __name__ == "__main__":
    unittest.main()
