from __future__ import annotations

import unittest
import json
from pathlib import Path
from unittest import mock

from _ai_os_runtime.api import ai_os_api_server


class CharlieOperatorActionsTest(unittest.TestCase):
    def test_research_intake_assigns_specialist_skills(self) -> None:
        messages: list[dict] = []

        def fake_message(payload: dict) -> dict:
            messages.append(payload)
            return {"id": len(messages), "to_agent": payload["to_agent"]}

        completed = mock.Mock(
            returncode=0,
            stdout=json.dumps({
                "paper": {
                    "id": 91,
                    "paper_key": "paper-91",
                    "title": "Point-in-time alpha architecture",
                    "source_url": "https://example.com/research",
                    "content_hash": "abc123",
                }
            }),
            stderr="",
        )
        with (
            mock.patch.object(ai_os_api_server.subprocess, "run", return_value=completed),
            mock.patch.object(
                ai_os_api_server,
                "run_psql_json",
                return_value=[
                    {"agent_name": "Research Analyst"},
                    {"agent_name": "Strategy Research Agent"},
                ],
            ),
            mock.patch.object(ai_os_api_server, "create_agent_message", fake_message),
            mock.patch.object(ai_os_api_server, "triage_agent_message", return_value={"status": "queued"}),
            mock.patch.object(ai_os_api_server, "run_psql_json_statement", return_value=[{"id": 7}]),
            mock.patch.object(ai_os_api_server, "run_psql_text"),
            mock.patch.object(ai_os_api_server, "audit_api_write"),
        ):
            result = ai_os_api_server.ingest_research_source({
                "source_url": "https://example.com/research",
                "research_objective": "Test the architecture without leakage.",
            })

        self.assertEqual(
            [(item["to_agent"], item["related_skill_key"]) for item in messages],
            [
                ("Research Analyst", "company_research_note"),
                ("Strategy Research Agent", "generate_strategy_hypothesis"),
            ],
        )
        self.assertFalse(result["live_execution_allowed"])

    def test_article_url_creates_governed_research_intake(self) -> None:
        captured = {}

        def fake_ingest(payload: dict) -> dict:
            captured.update(payload)
            return {"status": "assigned", "live_execution_allowed": False, "paper": {"id": 91}}

        with mock.patch.object(ai_os_api_server, "ingest_research_source", fake_ingest):
            operations = ai_os_api_server.execute_charlie_safe_tools(
                "Read and analyze this article https://example.com/strategy-note as a possible hypothesis source"
            )

        self.assertEqual(operations[0]["tool"], "ingest_research_source")
        self.assertEqual(captured["source_url"], "https://example.com/strategy-note")
        self.assertIn("backtest_spec", captured["desired_outputs"])
        self.assertFalse(operations[0]["result"]["live_execution_allowed"])

    def test_scoped_identity_is_first_person_and_role_specific(self) -> None:
        profile = {
            "agent_name": "Research Analyst",
            "display_title": "Senior Fundamental Research Analyst",
            "department_name": "Research Factory",
            "role_scope": "Verify primary evidence and build company research.",
            "persona": "Skeptical evidence auditor.",
            "operating_style": "Primary sources first.",
            "mental_models": ["base_rates"],
            "primary_route": "research_company_analysis",
            "permission_level": "read_only",
        }
        with mock.patch.object(ai_os_api_server, "run_psql_json", return_value=[profile]):
            identity = ai_os_api_server.resolve_conversation_identity({
                "metadata": {"assistant_scope": "Research Analyst"}
            })

        self.assertEqual(identity["agent_name"], "Research Analyst")
        self.assertIn("I am Research Analyst", identity["first_person_identity"])
        self.assertEqual(identity["primary_route"], "research_company_analysis")

    def test_explicit_strategy_command_creates_real_intake(self) -> None:
        captured = {}

        def fake_create(payload: dict) -> dict:
            captured.update(payload)
            return {"status": "created", "candidate_key": "candidate-42"}

        with mock.patch.object(ai_os_api_server, "create_strategy_intake", fake_create):
            operations = ai_os_api_server.execute_charlie_safe_tools(
                "Create a strategy called NIFTY RSI reversal that buys after RSI recovery and exits at ATR stop"
            )

        self.assertEqual(operations[0]["tool"], "create_strategy_intake")
        self.assertEqual(operations[0]["status"], "created")
        self.assertEqual(captured["strategy_name"], "NIFTY RSI reversal")
        self.assertIn("structured_spec", captured["requested_outputs"])
        self.assertNotIn("live_execution", captured["requested_outputs"])

    def test_explicit_delegation_creates_medium_priority_message(self) -> None:
        captured = {}
        profiles = [{
            "agent_name": "Research Analyst",
            "display_title": "Research Analyst",
            "department": "research",
            "department_name": "Research Division",
        }]

        def fake_message(payload: dict) -> dict:
            captured.update(payload)
            return {"status": "created", "id": 17}

        with (
            mock.patch.object(ai_os_api_server, "run_psql_json", return_value=profiles),
            mock.patch.object(ai_os_api_server, "create_agent_message", fake_message),
        ):
            operations = ai_os_api_server.execute_charlie_safe_tools(
                "Ask the research department to review the latest RELIANCE filing"
            )

        self.assertEqual(operations[0]["tool"], "delegate_agent_work")
        self.assertEqual(captured["to_agent"], "Research Analyst")
        self.assertEqual(captured["priority"], "medium")
        self.assertTrue(captured["metadata"]["operator_requested"])

    def test_natural_department_delegation_is_actionable(self) -> None:
        captured = {}
        profiles = [{
            "agent_name": "Head of Quant",
            "display_title": "Head of Quant",
            "department": "quant",
            "department_name": "Quantitative Strategies Office",
        }]

        def fake_message(payload: dict) -> dict:
            captured.update(payload)
            return {"status": "created", "id": 18}

        with (
            mock.patch.object(ai_os_api_server, "run_psql_json", return_value=profiles),
            mock.patch.object(ai_os_api_server, "create_agent_message", fake_message),
        ):
            operations = ai_os_api_server.execute_charlie_safe_tools(
                "Have the quant team test this factor hypothesis and prepare a validation report"
            )

        self.assertEqual(operations[0]["tool"], "delegate_agent_work")
        self.assertEqual(captured["to_agent"], "Head of Quant")

    def test_explicit_quant_team_outranks_research_subject_words(self) -> None:
        captured = {}
        profiles = [
            {
                "agent_name": "Research Analyst",
                "display_title": "Research Analyst",
                "department": "research",
                "department_name": "Research Factory",
            },
            {
                "agent_name": "Head of Quant",
                "display_title": "Head of Quant",
                "department": "quant",
                "department_name": "Quantitative Strategies Office",
            },
        ]

        def fake_message(payload: dict) -> dict:
            captured.update(payload)
            return {"status": "created", "id": 19}

        with (
            mock.patch.object(ai_os_api_server, "run_psql_json", return_value=profiles),
            mock.patch.object(ai_os_api_server, "create_agent_message", fake_message),
        ):
            ai_os_api_server.execute_charlie_safe_tools(
                "Have the quant team review research source 1 and prepare a validation plan"
            )

        self.assertEqual(captured["to_agent"], "Head of Quant")

    def test_non_action_conversation_does_not_write(self) -> None:
        with (
            mock.patch.object(ai_os_api_server, "create_strategy_intake") as strategy,
            mock.patch.object(ai_os_api_server, "create_agent_message") as message,
        ):
            operations = ai_os_api_server.execute_charlie_safe_tools(
                "What is going on in the office today?"
            )
        self.assertEqual(operations, [])
        strategy.assert_not_called()
        message.assert_not_called()

    def test_research_status_language_requests_verified_context(self) -> None:
        self.assertTrue(
            ai_os_api_server.is_auto_factual_retrieval_request(
                "What changed in the research office tonight, and what is actually completed?"
            )
        )

    def test_research_status_reply_names_completed_specialist_outputs(self) -> None:
        reply = ai_os_api_server.deterministic_chat_reply(
            "What changed in research tonight?",
            {
                "research_intakes": [{
                    "title": "Options source",
                    "hypothesis_count": 1,
                    "intake_status": "hypothesis_queued",
                    "extraction_word_count": 400,
                    "source_url": "https://example.com/options",
                }],
                "research_cycles": [{"id": 3}],
                "research_worker_outputs": [{
                    "worker_run_id": 321,
                    "agent_name": "Strategy Research Agent",
                    "skill_key": "generate_strategy_hypothesis",
                    "paper_title": "Options source",
                    "output_note_path": "ai memory/output.md",
                }],
            },
            [],
            [],
            {"default_model": "test"},
            "not_requested",
        )

        self.assertIn("1 immutable cycles (research ledger entries, not completed backtests)", reply)
        self.assertIn("run 321 by Strategy Research Agent", reply)
        self.assertIn("live execution are disabled", reply)

    def test_response_ledger_accepts_warehouse_truth_states(self) -> None:
        migration = (
            Path(ai_os_api_server.__file__).resolve().parents[1]
            / "postgres"
            / "init"
            / "167_response_evidence_warehouse_states_v1.sql"
        ).read_text(encoding="utf-8")

        self.assertIn("'warehouse_verified'", migration)
        self.assertIn("'warehouse_partial'", migration)

    def test_capability_question_is_not_misread_as_delegation(self) -> None:
        with mock.patch.object(
            ai_os_api_server,
            "create_agent_message",
        ) as create_message:
            operations = ai_os_api_server.execute_charlie_safe_tools(
                "What can I ask you to do, and how will you keep me in control?"
            )

        self.assertEqual(operations, [])
        create_message.assert_not_called()

    def test_zerodha_exchange_restarts_read_only_stream(self) -> None:
        with (
            mock.patch.object(
                ai_os_api_server,
                "_run_zerodha_adapter",
                return_value={"status": "connected", "broker_write_allowed": False},
            ) as adapter,
            mock.patch.object(
                ai_os_api_server,
                "restart_zerodha_stream_async",
                return_value={"status": "restart_requested"},
            ),
            mock.patch.object(ai_os_api_server, "audit_api_write"),
        ):
            result = ai_os_api_server.exchange_zerodha_request_token({"request_token": "one-time-token"})
        adapter.assert_called_once_with(["--exchange-request-token", "one-time-token"], 60)
        self.assertEqual(result["stream_restart"]["status"], "restart_requested")
        self.assertFalse(result["broker_write_allowed"])


if __name__ == "__main__":
    unittest.main()
