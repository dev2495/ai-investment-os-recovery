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


if __name__ == "__main__":
    unittest.main()
