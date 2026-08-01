from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = RUNTIME_ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_agent_worker_once


class ResearchEvidenceWorkerTest(unittest.TestCase):
    def test_coverage_gap_skill_writes_substantive_source_backed_review(self) -> None:
        job = {
            "task_id": 500,
            "owner_agent": "Research Librarian",
            "suggested_skill_key": "research_evidence_curation",
            "source_kind": "agent_message",
            "source_ref": "133",
        }
        profile = {
            "agent_name": "Research Librarian",
            "display_title": "Research Evidence Librarian",
            "cost_policy": "local_first_cloud_only_after_approval",
        }
        skill = {
            "skill_key": "research_evidence_curation",
            "skill_name": "Research Evidence Curation",
        }
        context = {
            "artifact_gaps": [
                {
                    "gap_type": "worker_run_missing_note",
                    "source_view": "agent.v_recent_worker_runs",
                    "source_id": "17",
                    "title": "Research worker run",
                    "owner_agent": "Research Analyst",
                    "status": "completed",
                    "updated_at": "2026-07-31T10:00:00+00:00",
                    "gap_reason": "Completed worker run has no output_note_path.",
                },
                {
                    "gap_type": "strategy_committee_missing_memo",
                    "source_view": "strategy.v_strategy_committee_queue",
                    "source_id": "9",
                    "title": "Mean reversion review",
                    "owner_agent": "Strategy Review Committee",
                    "status": "needs_review",
                    "updated_at": "2026-07-31T09:00:00+00:00",
                    "gap_reason": "Committee review has no generated memo_note_path.",
                },
            ],
            "execution_envelope": {
                "capital_action_allowed": False,
                "live_execution_allowed": False,
            },
        }

        summary, next_actions = run_agent_worker_once.summary_for(
            job, profile, skill, context
        )

        self.assertIn("Reviewed 2 current gap rows", summary)
        self.assertIn("agent.v_recent_worker_runs:17", summary)
        self.assertIn("strategy.v_strategy_committee_queue:9", summary)
        self.assertIn("Re-materialize the worker output into Obsidian", summary)
        self.assertIn("Generate the committee memo", summary)
        self.assertIn("no source records were altered", summary)
        self.assertIn("Broker orders allowed: false", summary)
        self.assertNotIn("Processed internal message", summary)
        self.assertTrue(any("rerun this skill" in action for action in next_actions))


    def test_company_research_request_extracts_symbol(self) -> None:
        query = run_agent_worker_once.extract_company_query(
            {"objective": "Review latest available RELIANCE filing and prepare a decision memo."},
            {"subject": "Company research", "body": "Separate facts from inference. No trade."},
        )
        self.assertEqual(query, "RELIANCE")

    def test_company_research_missing_filing_is_explicit_and_non_actionable(self) -> None:
        summary, next_actions = run_agent_worker_once.summary_for(
            {
                "task_id": 503,
                "owner_agent": "Research Analyst",
                "suggested_skill_key": "company_research_note",
                "source_kind": "agent_message",
            },
            {
                "agent_name": "Research Analyst",
                "display_title": "Company Research Analyst",
                "cost_policy": "local_first_cloud_only_after_approval",
            },
            {"skill_key": "company_research_note", "skill_name": "Company Research Note"},
            {
                "company_research": {
                    "query": "RELIANCE",
                    "filing_inventory": {
                        "total_filings": 1365,
                        "latest_filed_at": "2026-07-31T10:20:42+00:00",
                    },
                    "filings": [],
                    "holding_theses": [{"id": 9, "thesis_status": "needs_review"}],
                    "ideas": [],
                    "notes": [],
                }
            },
        )

        self.assertIn("Company Research Decision Memo", summary)
        self.assertIn("No official filing row matched `RELIANCE`", summary)
        self.assertIn("missing-evidence result", summary)
        self.assertIn("Insufficient evidence for a trade", summary)
        self.assertIn("Broker write allowed: false", summary)
        self.assertNotIn("Processed internal message", summary)
        self.assertTrue(any("entity-resolution" in action for action in next_actions))

    def test_complete_job_marks_originating_message_processed(self) -> None:
        captured: dict[str, str] = {}

        def fake_psql(sql: str) -> str:
            captured["sql"] = sql
            return '{"worker_run":{"id":408},"message":{"id":136,"status":"read","processing_status":"processed"}}'

        with (
            tempfile.TemporaryDirectory() as directory,
            mock.patch.object(run_agent_worker_once, "VAULT_ROOT", Path(directory)),
            mock.patch.object(run_agent_worker_once, "psql_text", side_effect=fake_psql),
        ):
            note_path = Path(directory) / "ai memory" / "output.md"
            result = run_agent_worker_once.complete_job(
                {
                    "task_id": 503,
                    "owner_agent": "Research Analyst",
                    "suggested_skill_key": "company_research_note",
                },
                {"agent_name": "Research Analyst"},
                {"skill_key": "company_research_note"},
                {"note_persistence": {"status": "deferred_error", "spool_path": "/tmp/output.md"}},
                "Evidence-backed output.",
                note_path,
            )

        self.assertEqual(result["message"]["processing_status"], "processed")
        self.assertIn("UPDATE agent.agent_messages", captured["sql"])
        self.assertIn("processing_status = 'processed'", captured["sql"])
        self.assertIn("WHERE generated_task_id = 503", captured["sql"])

    def test_worker_note_uses_internal_spool_before_vault_mirror(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            output = vault / "ai memory" / "00 AI OS" / "Agent Outputs" / "Worker Runs"
            spool = root / "spool"
            context: dict = {}
            with (
                mock.patch.object(run_agent_worker_once, "VAULT_ROOT", vault),
                mock.patch.object(run_agent_worker_once, "OUTPUT_DIR", output),
                mock.patch.object(run_agent_worker_once, "WORKER_SPOOL_ROOT", spool),
            ):
                path = run_agent_worker_once.write_note(
                    {"task_id": 501, "task_status": "queued", "suggested_skill_key": "company_research_note"},
                    {"agent_name": "Research Analyst", "display_title": "Company Research Analyst"},
                    {"skill_name": "Company Research Note"},
                    context,
                    "Verified output.",
                    ["Review the evidence."],
                )

            relative = path.relative_to(vault)
            self.assertTrue((spool / relative).exists())
            self.assertTrue(path.exists())
            self.assertEqual(context["note_persistence"]["status"], "mirrored")

    def test_worker_note_defers_unhealthy_vault_without_losing_spool(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            output = vault / "ai memory" / "00 AI OS" / "Agent Outputs" / "Worker Runs"
            spool = root / "spool"
            context: dict = {}
            with (
                mock.patch.object(run_agent_worker_once, "VAULT_ROOT", vault),
                mock.patch.object(run_agent_worker_once, "OUTPUT_DIR", output),
                mock.patch.object(run_agent_worker_once, "WORKER_SPOOL_ROOT", spool),
                mock.patch.object(
                    run_agent_worker_once.subprocess,
                    "run",
                    side_effect=subprocess.TimeoutExpired(["/bin/mkdir"], 8),
                ),
            ):
                path = run_agent_worker_once.write_note(
                    {"task_id": 502, "task_status": "queued", "suggested_skill_key": "company_research_note"},
                    {"agent_name": "Research Analyst", "display_title": "Company Research Analyst"},
                    {"skill_name": "Company Research Note"},
                    context,
                    "Verified output.",
                    ["Review the evidence."],
                )

            relative = path.relative_to(vault)
            self.assertTrue((spool / relative).exists())
            self.assertFalse(path.exists())
            self.assertEqual(context["note_persistence"]["status"], "deferred_timeout")


if __name__ == "__main__":
    unittest.main()
