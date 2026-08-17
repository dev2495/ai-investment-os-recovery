from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from _ai_os_runtime.api import ai_os_api_server


class BlueprintEvidenceReconciliationTest(unittest.TestCase):
    def test_schema_keeps_agent_output_candidate_and_human_reviewed(self) -> None:
        runtime_root = Path(__file__).resolve().parents[1]
        migration = (runtime_root / "postgres" / "init" / "199_blueprint_evidence_reconciliation_v1.sql").read_text(encoding="utf-8")

        self.assertIn("core.os_blueprint_evidence_links", migration)
        self.assertIn("'candidate', 'verified', 'rejected'", migration)
        self.assertIn("agent output never verifies itself", migration.lower())
        self.assertIn("broker_write_allowed BOOLEAN NOT NULL DEFAULT false", migration)
        self.assertIn("delivery_review_state", migration)

    def test_reconcile_links_worker_evidence_without_verifying_it(self) -> None:
        result_row = {
            "run_key": "blueprint-evidence-test",
            "status": "completed",
            "candidate_count": 1,
            "broker_write_allowed": False,
            "evidence_links": [{"evidence_status": "candidate"}],
        }
        with mock.patch.object(ai_os_api_server, "run_psql_json_statement", return_value=[result_row]) as execute, mock.patch.object(ai_os_api_server, "audit_api_write"):
            result = ai_os_api_server.reconcile_blueprint_evidence({"actor": "Jarvis", "run_key": "blueprint-evidence-test"})

        sql = execute.call_args.args[0]
        self.assertEqual(result, result_row)
        self.assertIn("'candidate'", sql)
        self.assertIn("self_verification_allowed", sql)
        self.assertIn("false", sql)
        self.assertNotIn("live_broker", sql)

    def test_review_requires_named_rationale_and_explicit_delivery_state(self) -> None:
        with self.assertRaisesRegex(ValueError, "rationale is required"):
            ai_os_api_server.review_blueprint_evidence({
                "evidence_link_id": 1,
                "decision": "verified",
                "delivery_status": "done",
            })
        with self.assertRaisesRegex(ValueError, "partial or done"):
            ai_os_api_server.review_blueprint_evidence({
                "evidence_link_id": 1,
                "decision": "verified",
                "delivery_status": "planned",
                "rationale": "Checked live evidence.",
            })

    def test_frontend_exposes_scan_and_review_not_automatic_completion(self) -> None:
        runtime_root = Path(__file__).resolve().parents[1]
        actions = (runtime_root / "ai-office-ui" / "src" / "data" / "actions.ts").read_text(encoding="utf-8")
        governance = (runtime_root / "ai-office-ui" / "src" / "destinations" / "firm" / "FirmAgentViews.tsx").read_text(encoding="utf-8")

        self.assertIn('/api/blueprint/evidence/reconcile', actions)
        self.assertIn('/api/blueprint/evidence/review', actions)
        self.assertIn("Scan evidence", governance)
        self.assertIn("Verify evidence", governance)
        self.assertIn("Agent output is candidate evidence only", governance)


if __name__ == "__main__":
    unittest.main()
