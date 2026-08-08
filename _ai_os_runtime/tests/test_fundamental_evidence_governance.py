from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from _ai_os_runtime.api import ai_os_api_server


class FundamentalEvidenceGovernanceTests(unittest.TestCase):
    def test_review_requires_explicit_operator_confirmation_and_rationale(self) -> None:
        with self.assertRaisesRegex(ValueError, "operator_confirmed"):
            ai_os_api_server.review_fundamental_evidence({
                "evidence_id": 19,
                "decision": "human_verified",
                "rationale": "Reviewed official filing pages.",
            })
        with self.assertRaisesRegex(ValueError, "at least 12"):
            ai_os_api_server.review_fundamental_evidence({
                "evidence_id": 19,
                "decision": "human_verified",
                "rationale": "too short",
                "operator_confirmed": True,
            })

    def test_review_updates_only_selected_evidence_and_keeps_execution_locked(self) -> None:
        reviewed = {
            "evidence_id": 19,
            "verification_status": "human_verified",
            "verified_by": "Devarsh",
            "capital_action_allowed": False,
            "broker_write_allowed": False,
        }
        with (
            mock.patch.object(ai_os_api_server, "run_psql_json_statement", return_value=[reviewed]) as execute,
            mock.patch.object(ai_os_api_server, "audit_api_write") as audit,
        ):
            result = ai_os_api_server.review_fundamental_evidence({
                "evidence_id": 19,
                "decision": "human_verified",
                "rationale": "Reviewed official annual report source and locator.",
                "operator_confirmed": True,
                "actor": "Devarsh",
            })

        sql = execute.call_args.args[0]
        self.assertIn("WHERE evidence.id = 19", sql)
        self.assertIn("'human_verified'", sql)
        self.assertIn("operator_confirmed", sql)
        self.assertFalse(result["broker_write_allowed"])
        self.assertNotIn("request_token", repr(audit.call_args))

    def test_frontend_exposes_gate_details_and_human_review(self) -> None:
        runtime_root = Path(__file__).resolve().parents[1]
        actions = (runtime_root / "ai-office-ui" / "src" / "data" / "actions.ts").read_text(encoding="utf-8")
        terminal = (runtime_root / "ai-office-ui" / "src" / "destinations" / "fundamental" / "FundamentalResearch.tsx").read_text(encoding="utf-8")

        self.assertIn('/api/research/fundamental-evidence/review', actions)
        self.assertIn("Human Evidence Review", terminal)
        self.assertIn("Acceptance Gate Detail", terminal)
        self.assertIn("operator_confirmed: true", terminal)


if __name__ == "__main__":
    unittest.main()
