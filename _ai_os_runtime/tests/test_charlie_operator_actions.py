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
                "Read and analyze https://example.com/strategy-note as a research source with testable hypotheses"
            )

        self.assertEqual(operations[0]["tool"], "ingest_research_source")
        self.assertEqual(captured["source_url"], "https://example.com/strategy-note")
        self.assertIn("backtest_spec", captured["desired_outputs"])
        self.assertFalse(operations[0]["result"]["live_execution_allowed"])

    def test_negated_source_command_does_not_ingest(self) -> None:
        with mock.patch.object(ai_os_api_server, "ingest_research_source") as ingest:
            operations = ai_os_api_server.execute_charlie_safe_tools(
                "Do not ingest or read https://example.com/strategy-note"
            )

        self.assertEqual(operations, [])
        ingest.assert_not_called()

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
        self.assertEqual(captured["related_skill_key"], "company_research_note")
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
        self.assertEqual(captured["related_skill_key"], "head_quant_governance")

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

    def test_status_question_does_not_start_graph(self) -> None:
        with mock.patch.object(ai_os_api_server, "start_graph_control_run") as start_graph:
            operations = ai_os_api_server.execute_charlie_safe_tools(
                "What is the status of the research workflow?"
            )
        self.assertEqual(operations, [])
        start_graph.assert_not_called()

    def test_explicit_research_lifecycle_starts_governed_graph(self) -> None:
        captured = {}

        def fake_start(payload: dict) -> dict:
            captured.update(payload)
            return {"graph_run_id": 42, "run_status": "running", "created": True}

        with mock.patch.object(ai_os_api_server, "start_graph_control_run", fake_start):
            operations = ai_os_api_server.execute_charlie_safe_tools(
                "Start the full research cycle on RELIANCE capital allocation and governance"
            )

        self.assertEqual(operations[0]["tool"], "start_graph_run")
        self.assertEqual(operations[0]["detail"], "42")
        self.assertEqual(captured["graph_key"], "research_to_investment_decision")
        self.assertIn("RELIANCE", captured["input_payload"]["subject"])
        self.assertEqual(captured["input_payload"]["symbol"], "RELIANCE")
        self.assertEqual(captured["trigger_type"], "charlie_chat")
        self.assertTrue(captured["idempotency_key"])

    def test_explicit_strategy_lifecycle_does_not_create_parallel_intake(self) -> None:
        captured = {}

        def fake_start(payload: dict) -> dict:
            captured.update(payload)
            return {"graph_run_id": 43, "run_status": "running", "created": True}

        with (
            mock.patch.object(ai_os_api_server, "start_graph_control_run", fake_start),
            mock.patch.object(ai_os_api_server, "create_strategy_intake") as create_intake,
            mock.patch.object(ai_os_api_server, "create_agent_message") as create_message,
        ):
            operations = ai_os_api_server.execute_charlie_safe_tools(
                "Run the strategy research lifecycle for NIFTY 15m opening range mean reversion"
            )

        self.assertEqual(operations[0]["tool"], "start_graph_run")
        self.assertEqual(captured["graph_key"], "strategy_research_lifecycle")
        self.assertEqual(captured["input_payload"]["timeframe"], "15m")
        create_intake.assert_not_called()
        create_message.assert_not_called()

    def test_graph_run_control_is_explicit_and_bounded(self) -> None:
        with mock.patch.object(
            ai_os_api_server,
            "pause_graph_control_run",
            return_value={"graph_run_id": 77, "run_status": "paused"},
        ) as pause:
            operations = ai_os_api_server.execute_charlie_safe_tools("Pause workflow run 77")

        self.assertEqual(operations[0]["tool"], "pause_graph_run")
        self.assertEqual(operations[0]["detail"], "77")
        pause.assert_called_once()
        self.assertEqual(pause.call_args.args[0]["graph_run_id"], 77)

    def test_kronos_requires_symbol_before_any_write(self) -> None:
        with mock.patch.object(ai_os_api_server, "start_graph_control_run") as start_graph:
            operations = ai_os_api_server.execute_charlie_safe_tools(
                "Start a Kronos forecast research run"
            )
        self.assertEqual(operations[0]["status"], "needs_input")
        start_graph.assert_not_called()

    def test_kronos_requires_validated_adapter_before_start(self) -> None:
        with (
            mock.patch.object(ai_os_api_server, "run_psql_json", return_value=[]),
            mock.patch.object(ai_os_api_server, "start_graph_control_run") as start_graph,
        ):
            operations = ai_os_api_server.execute_charlie_safe_tools(
                "Run Kronos forecast research for RELIANCE 1d NSE"
            )
        self.assertEqual(operations[0]["status"], "dependency_required")
        start_graph.assert_not_called()

    def test_graph_status_reply_uses_verified_run_state(self) -> None:
        reply = ai_os_api_server.deterministic_chat_reply(
            "Show the graph run status",
            {
                "graph_catalog": [{"graph_key": "daily_office_intelligence"}],
                "graph_runs": [{
                    "graph_run_id": 9,
                    "graph_name": "Daily Office Intelligence Loop",
                    "run_status": "running",
                    "current_node_name": "Review portfolios and books",
                    "current_owner_agent": "Portfolio Manager",
                    "completed_nodes": 2,
                    "total_nodes": 9,
                }],
                "graph_attention": [],
            },
            [],
            [],
            {"default_model": "test"},
            "not_requested",
        )
        self.assertIn("run 9 Daily Office Intelligence Loop", reply)
        self.assertIn("2/9 nodes complete", reply)
        self.assertIn("broker writes are disabled", reply)

    def test_research_status_language_requests_verified_context(self) -> None:
        self.assertTrue(
            ai_os_api_server.is_auto_factual_retrieval_request(
                "What changed in the research office tonight, and what is actually completed?"
            )
        )

    def test_research_status_can_use_internal_cloud_boundary(self) -> None:
        self.assertFalse(
            ai_os_api_server.message_requires_client_private_context(
                "Which research sources and specialist outputs were completed tonight?"
            )
        )

    def test_portfolio_and_broad_office_requests_stay_client_private(self) -> None:
        self.assertTrue(
            ai_os_api_server.message_requires_client_private_context(
                "Summarize my client portfolio positions and exposure"
            )
        )

    def test_fast_route_selection_is_explicit_one_call_cloud_approval(self) -> None:
        self.assertTrue(
            ai_os_api_server.is_explicit_cloud_route_selection(
                {"route_name": "openrouter_research_fast"},
                {"default_provider": "openrouter"},
            )
        )
        self.assertFalse(
            ai_os_api_server.is_explicit_cloud_route_selection(
                {}, {"default_provider": "openrouter"}
            )
        )
        self.assertTrue(
            ai_os_api_server.message_requires_client_private_context(
                "Brief me on what is going on in the office today"
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

    def test_active_graph_progression_is_bounded_and_audited(self) -> None:
        with (
            mock.patch.object(
                ai_os_api_server,
                "run_psql_json",
                return_value=[
                    {"graph_run_id": 41, "graph_key": "daily_office_intelligence"},
                    {"graph_run_id": 42, "graph_key": "strategy_research_lifecycle"},
                ],
            ) as query,
            mock.patch.object(
                ai_os_api_server.graph_control_plane,
                "advance_graph_run",
                side_effect=[
                    {"graph_key": "daily_office_intelligence", "run_status": "running", "processed_steps": 3, "attention": []},
                    {"graph_key": "strategy_research_lifecycle", "run_status": "waiting_approval", "processed_steps": 2, "attention": [{"id": 9}]},
                ],
            ) as advance,
            mock.patch.object(ai_os_api_server, "audit_api_write") as audit,
        ):
            result = ai_os_api_server.advance_active_graph_control_runs({
                "actor": "Jarvis test",
                "limit": 999,
                "max_steps": 999,
            })

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["runs"][1]["waiting"], 1)
        self.assertEqual(advance.call_args_list[0].args[2]["max_steps"], 100)
        self.assertIn("LIMIT 50", query.call_args.args[0])
        audit.assert_called_once()

    def test_manual_worker_immediately_advances_graph_control(self) -> None:
        completed = mock.Mock(returncode=0, stdout='{"count":1,"results":[]}', stderr="")
        with (
            mock.patch.object(ai_os_api_server.subprocess, "run", return_value=completed),
            mock.patch.object(
                ai_os_api_server,
                "advance_active_graph_control_runs",
                return_value={"status": "success", "active_runs_seen": 1, "count": 1, "runs": [], "errors": []},
            ) as advance,
            mock.patch.object(ai_os_api_server, "audit_api_write"),
        ):
            result = ai_os_api_server.run_agent_worker({"actor": "Devarsh", "limit": 1})

        self.assertEqual(result["graph_control_plane"]["status"], "success")
        advance.assert_called_once()
        self.assertEqual(advance.call_args.args[0]["actor"], "Devarsh")

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
