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
            mock.patch.object(ai_os_api_server, "governed_pdf_python", return_value="/governed/pdf/python"),
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

        with (
            mock.patch.object(ai_os_api_server, "ingest_research_source", fake_ingest),
            mock.patch.object(ai_os_api_server, "create_agent_message") as generic_delegation,
        ):
            operations = ai_os_api_server.execute_charlie_safe_tools(
                "Read and analyze https://example.com/strategy-note as a research source with testable hypotheses, "
                "then delegate the evidence review to the research team"
            )

        self.assertEqual(len(operations), 1)
        self.assertEqual(operations[0]["tool"], "ingest_research_source")
        self.assertEqual(captured["source_url"], "https://example.com/strategy-note")
        self.assertIn("backtest_spec", captured["desired_outputs"])
        self.assertFalse(operations[0]["result"]["live_execution_allowed"])
        generic_delegation.assert_not_called()

    def test_multiple_article_urls_are_deduplicated_and_ingested(self) -> None:
        captured: list[dict] = []

        def fake_ingest(payload: dict) -> dict:
            captured.append(payload)
            return {"status": "assigned", "live_execution_allowed": False, "paper": {"id": len(captured)}}

        with mock.patch.object(ai_os_api_server, "ingest_research_source", fake_ingest):
            operations = ai_os_api_server.execute_charlie_safe_tools(
                "Read and analyze https://example.com/a https://example.com/b https://example.com/a"
            )

        self.assertEqual([item["tool"] for item in operations], [
            "ingest_research_source", "ingest_research_source",
        ])
        self.assertEqual(
            [item["source_url"] for item in captured],
            ["https://example.com/a", "https://example.com/b"],
        )
        self.assertTrue(all(item["desired_outputs"][-1] == "backtest_spec" for item in captured))

    def test_explicit_article_hypothesis_is_queued_once_for_a_source_batch(self) -> None:
        captured: list[dict] = []

        def fake_ingest(payload: dict) -> dict:
            captured.append(payload)
            return {"status": "assigned", "live_execution_allowed": False, "paper": {"id": len(captured)}}

        with mock.patch.object(ai_os_api_server, "ingest_research_source", fake_ingest):
            ai_os_api_server.execute_charlie_safe_tools(
                "Read https://example.com/a and https://example.com/b and test hypothesis that "
                "post-earnings gap downs mean revert within five sessions, then delegate evidence review"
            )

        self.assertEqual(
            captured[0]["hypothesis"],
            "post-earnings gap downs mean revert within five sessions",
        )
        self.assertNotIn("hypothesis", captured[1])

    def test_generic_testable_hypotheses_request_does_not_invent_one(self) -> None:
        captured = {}

        def fake_ingest(payload: dict) -> dict:
            captured.update(payload)
            return {"status": "assigned", "live_execution_allowed": False, "paper": {"id": 1}}

        with mock.patch.object(ai_os_api_server, "ingest_research_source", fake_ingest):
            ai_os_api_server.execute_charlie_safe_tools(
                "Analyze https://example.com/a and produce testable hypotheses"
            )

        self.assertNotIn("hypothesis", captured)

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

    def test_open_ended_work_request_is_durably_queued(self) -> None:
        captured = {}

        def fake_message(payload: dict) -> dict:
            captured.update(payload)
            return {
                "id": 44,
                "to_agent": payload["to_agent"],
                "subject": payload["subject"],
                "processing_status": "pending",
            }

        with (
            mock.patch.object(
                ai_os_api_server,
                "run_psql_json",
                return_value=[
                    {"agent_name": "Charlie Munger"},
                    {"agent_name": "Jarvis"},
                ],
            ),
            mock.patch.object(ai_os_api_server, "create_agent_message", fake_message),
        ):
            operations = ai_os_api_server.execute_charlie_safe_tools(
                "Please investigate how promoter pledging changed across my watchlist and prepare an evidence pack"
            )

        self.assertEqual(operations[0]["tool"], "queue_open_ended_work")
        self.assertEqual(captured["from_agent"], "Charlie Munger")
        self.assertEqual(captured["to_agent"], "Jarvis")
        self.assertEqual(captured["related_skill_key"], "route_user_request")
        self.assertTrue(captured["metadata"]["open_ended_intake"])

    def test_ordinary_question_does_not_create_background_work(self) -> None:
        with mock.patch.object(ai_os_api_server, "create_agent_message") as create_message:
            operations = ai_os_api_server.execute_charlie_safe_tools(
                "How does the research department work?"
            )

        self.assertEqual(operations, [])
        create_message.assert_not_called()

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

    def test_sector_team_delegation_routes_to_sector_portfolio_manager(self) -> None:
        captured = {}
        profiles = [{
            "agent_name": "Sector Portfolio Manager",
            "display_title": "Head Of Sector Intelligence",
            "department": "sector",
            "department_name": "Sector Intelligence Office",
        }]

        def fake_message(payload: dict) -> dict:
            captured.update(payload)
            return {"status": "created", "id": 21}

        with (
            mock.patch.object(ai_os_api_server, "run_psql_json", return_value=profiles),
            mock.patch.object(ai_os_api_server, "create_agent_message", fake_message),
        ):
            operations = ai_os_api_server.execute_charlie_safe_tools(
                "Have the sector team review banking breadth and prepare a source-linked committee packet"
            )

        self.assertEqual(operations[0]["tool"], "delegate_agent_work")
        self.assertEqual(captured["to_agent"], "Sector Portfolio Manager")
        self.assertEqual(captured["related_skill_key"], "sector_portfolio_management")

    def test_sector_acceptance_command_runs_canonical_gate_action(self) -> None:
        captured = {}

        def fake_run(payload: dict) -> dict:
            captured.update(payload)
            return {"status": "blocked", "gate_count": 10, "passed_count": 6, "broker_write_allowed": False}

        with mock.patch.object(ai_os_api_server, "run_sector_acceptance", fake_run):
            operations = ai_os_api_server.execute_charlie_safe_tools(
                "Run sector acceptance for taxonomy node 12 as of 2026-08-04"
            )

        self.assertEqual(operations[0]["tool"], "run_sector_acceptance")
        self.assertEqual(captured["taxonomy_node_id"], 12)
        self.assertEqual(captured["as_of_date"], "2026-08-04")
        self.assertEqual(captured["actor"], "Devarsh via Charlie Munger")

    def test_sector_acceptance_command_requires_bounded_subject_and_date(self) -> None:
        with mock.patch.object(ai_os_api_server, "run_sector_acceptance") as run:
            operations = ai_os_api_server.execute_charlie_safe_tools("Check sector acceptance")

        self.assertEqual(operations[0]["status"], "needs_input")
        run.assert_not_called()

    def test_option_acceptance_command_runs_bounded_live_window_gates(self) -> None:
        captured = {}

        def fake_run(payload: dict) -> dict:
            captured.update(payload)
            return {"status": "blocked", "gate_count": 11, "passed_count": 7, "broker_write_allowed": False}

        with mock.patch.object(ai_os_api_server, "run_option_acceptance", fake_run):
            operations = ai_os_api_server.execute_charlie_safe_tools(
                "Run options acceptance NFO NIFTY expiry 2026-08-27 "
                "from 2026-08-04T09:20:00+05:30 to 2026-08-04T09:50:00+05:30"
            )

        self.assertEqual(operations[0]["tool"], "run_option_acceptance")
        self.assertEqual(captured["underlying"], "NIFTY")
        self.assertEqual(captured["exchange"], "NFO")
        self.assertEqual(captured["expiry_date"], "2026-08-27")
        self.assertEqual(captured["window_start"], "2026-08-04T09:20:00+05:30")

    def test_fundamental_factory_command_can_validate_or_explicitly_persist(self) -> None:
        captured = []

        def fake_run(payload: dict) -> dict:
            captured.append(payload)
            return {"status": "completed", "acceptance_status": "failed"}

        with mock.patch.object(ai_os_api_server, "run_institutional_fundamental_factory", fake_run):
            validate = ai_os_api_server.execute_charlie_safe_tools(
                "Run fundamental research factory RELIANCE NSE as of 2026-08-04T12:00:00+05:30"
            )
            persist = ai_os_api_server.execute_charlie_safe_tools(
                "Refresh institutional fundamental factory RELIANCE NSE 2026-08-04T12:00:00+05:30 and persist"
            )

        self.assertEqual(validate[0]["tool"], "run_institutional_fundamental_factory")
        self.assertTrue(captured[0]["dry_run"])
        self.assertFalse(captured[1]["dry_run"])
        self.assertEqual(captured[1]["symbol"], "RELIANCE")
        self.assertEqual(persist[0]["status"], "completed")

    def test_fundamental_factory_command_never_guesses_company_or_cutoff(self) -> None:
        with mock.patch.object(ai_os_api_server, "run_institutional_fundamental_factory") as run:
            operations = ai_os_api_server.execute_charlie_safe_tools("Run fundamental factory")

        self.assertEqual(operations[0]["status"], "needs_input")
        run.assert_not_called()

    def test_office_operability_command_runs_durable_acceptance(self) -> None:
        with mock.patch.object(
            ai_os_api_server,
            "run_office_operability_acceptance",
            return_value={"status": "blocked", "gate_count": 11, "passed_count": 8},
        ) as run:
            operations = ai_os_api_server.execute_charlie_safe_tools("Run AI office operability acceptance")

        self.assertEqual(operations[0]["tool"], "run_office_operability_acceptance")
        self.assertEqual(operations[0]["status"], "blocked")
        run.assert_called_once()

    def test_option_acceptance_command_never_guesses_missing_window(self) -> None:
        with mock.patch.object(ai_os_api_server, "run_option_acceptance") as run:
            operations = ai_os_api_server.execute_charlie_safe_tools(
                "Check options acceptance for NIFTY NFO"
            )

        self.assertEqual(operations[0]["status"], "needs_input")
        run.assert_not_called()

    def test_options_data_quality_agent_has_safe_fallback_skill(self) -> None:
        with mock.patch.object(ai_os_api_server, "run_psql_json", side_effect=RuntimeError("view unavailable")):
            skill = ai_os_api_server.resolve_delegation_skill({
                "agent_name": "Options Data Quality Agent",
            })

        self.assertEqual(skill, "options_data_quality_control")

    def test_explicit_candidate_backtest_runs_deterministic_engine(self) -> None:
        captured = {}

        def fake_backtest(payload: dict) -> dict:
            captured.update(payload)
            return {"status": "completed", "backtest_run_id": 17, "live_execution_allowed": False}

        with mock.patch.object(ai_os_api_server, "run_strategy_backtest", fake_backtest):
            operations = ai_os_api_server.execute_charlie_safe_tools(
                "Run a backtest for candidate 42"
            )

        self.assertEqual(operations[0]["tool"], "run_strategy_backtest")
        self.assertEqual(captured["candidate_id"], 42)
        self.assertEqual(captured["actor"], "Devarsh via Charlie")
        self.assertFalse(operations[0]["result"]["live_execution_allowed"])

    def test_named_candidate_backtest_requires_one_unique_match(self) -> None:
        captured = {}

        def fake_backtest(payload: dict) -> dict:
            captured.update(payload)
            return {"status": "completed", "backtest_run_id": 18}

        with (
            mock.patch.object(
                ai_os_api_server,
                "run_psql_json",
                return_value=[
                    {"id": 7, "candidate_key": "nifty-rsi-reversal", "name": "NIFTY RSI reversal"},
                    {"id": 9, "candidate_key": "banknifty-breakout", "name": "BANKNIFTY breakout"},
                ],
            ),
            mock.patch.object(ai_os_api_server, "run_strategy_backtest", fake_backtest),
        ):
            operations = ai_os_api_server.execute_charlie_safe_tools(
                "Backtest strategy NIFTY RSI reversal"
            )

        self.assertEqual(operations[0]["status"], "completed")
        self.assertEqual(captured["candidate_id"], 7)

    def test_ambiguous_backtest_request_does_not_guess(self) -> None:
        with (
            mock.patch.object(
                ai_os_api_server,
                "run_psql_json",
                return_value=[
                    {"id": 7, "candidate_key": "rsi-one", "name": "RSI reversal"},
                    {"id": 8, "candidate_key": "rsi-two", "name": "RSI reversal intraday"},
                ],
            ),
            mock.patch.object(ai_os_api_server, "run_strategy_backtest") as backtest,
        ):
            operations = ai_os_api_server.execute_charlie_safe_tools(
                "Run a backtest on RSI reversal intraday"
            )

        self.assertEqual(operations[0]["status"], "needs_candidate")
        self.assertEqual(len(operations[0]["matches"]), 2)
        backtest.assert_not_called()

    def test_explicit_candidate_optimization_runs_deterministic_engine(self) -> None:
        with mock.patch.object(
            ai_os_api_server,
            "run_strategy_optimization",
            return_value={"status": "completed", "optimization_run_id": 4},
        ) as optimize:
            operations = ai_os_api_server.execute_charlie_safe_tools(
                "Optimize candidate 42"
            )

        self.assertEqual(operations[0]["tool"], "run_strategy_optimization")
        self.assertEqual(optimize.call_args.args[0]["candidate_id"], 42)

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

    def test_embedding_does_not_depend_on_transient_ollama_tags(self) -> None:
        with (
            mock.patch.object(ai_os_api_server, "local_model_governance", return_value={"assignable": True}),
            mock.patch.object(ai_os_api_server, "http_json", return_value={"embeddings": [[0.1, 0.2]]}),
            mock.patch.object(ai_os_api_server, "ollama_model_available") as tags_probe,
        ):
            vector = ai_os_api_server.ollama_embed("execution safety rule")

        self.assertEqual(vector, [0.1, 0.2])
        tags_probe.assert_not_called()

    def test_stored_memory_title_request_requires_semantic_retrieval(self) -> None:
        message = (
            "Use our stored AI OS memory to tell me the execution-safety rule "
            "and name the relevant memory titles."
        )
        self.assertTrue(ai_os_api_server.is_auto_factual_retrieval_request(message))
        reply = ai_os_api_server.deterministic_chat_reply(
            message,
            {"context_errors": []},
            [],
            [],
            {"default_model": "test"},
            "embedding_model_unavailable",
        )
        self.assertIn("cannot name or cite stored notes", reply)
        self.assertIn("embedding_model_unavailable", reply)

    def test_latest_report_uses_structured_ledger_without_semantic_retrieval(self) -> None:
        message = (
            "Find the latest Provider Readiness Report in our knowledge library. "
            "Tell me who produced it, when it was updated, and cite the exact stored artifact."
        )
        context = {
            "latest_reports": [{
                "report_name": "Provider Readiness Report",
                "owner_agent": "Model Governance Agent",
                "updated_at": "2026-07-31T02:15:00+00:00",
                "output_note_path": "ai memory/00 AI OS/Reports/Scheduled/provider-readiness.md",
            }],
            "context_errors": [],
        }
        self.assertEqual(
            ai_os_api_server.structured_evidence_sections_for_request(message, context),
            ["latest_reports"],
        )
        reply = ai_os_api_server.deterministic_chat_reply(
            message,
            context,
            [],
            [],
            {"default_model": "test"},
            "disabled_for_nonprivate_context",
        )
        self.assertIn("produced by Model Governance Agent", reply)
        self.assertIn("2026-07-31T02:15:00+00:00", reply)
        self.assertIn("ai memory/00 AI OS/Reports/Scheduled/provider-readiness.md", reply)
        self.assertNotIn("cannot name or cite stored notes", reply)

    def test_structured_report_evidence_does_not_weaken_memory_title_gate(self) -> None:
        report_request = "Find the latest report and cite the exact artifact"
        memory_request = "Use our stored memory and name the relevant stored note"
        context = {"latest_reports": [{"report_name": "Daily Brief"}]}
        self.assertEqual(
            ai_os_api_server.structured_evidence_sections_for_request(report_request, context),
            ["latest_reports"],
        )
        self.assertEqual(
            ai_os_api_server.structured_evidence_sections_for_request(memory_request, context),
            [],
        )

    def test_retrieval_gate_precedes_model_call_for_factual_memory_requests(self) -> None:
        source = Path(ai_os_api_server.__file__).read_text(encoding="utf-8")
        gate = source.index("elif retrieval_gate_blocked:")
        provider_call = source.index("elif model_decision.get(\"decision_status\") == \"allowed\":", gate)
        self.assertLess(gate, provider_call)
        self.assertIn("existing_missing_evidence = list", source)
        self.assertIn("semantic_retrieval_passed", source)

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

    def test_institutional_program_status_uses_verified_read_models(self) -> None:
        context = {
            "option_analytics_readiness": [{
                "underlying": "NIFTY", "expiry": "2026-08-27",
                "analytics_readiness": "ready", "validated_greeks_count": 42,
                "contract_count": 48, "model_family": "black_scholes_merton",
            }],
            "institutional_option_pipeline_runs": [{
                "run_key": "options-1", "status": "completed", "batches_created": 1,
                "calculations_completed": 42, "calculations_blocked": 6,
            }],
            "sector_data_freshness": [{
                "node_name": "Banks", "freshness_state": "stale",
                "latest_metric_at": "2026-08-01T10:00:00Z",
                "latest_market_monitor_at": None, "latest_flow_at": None,
            }],
            "sector_custom_indices": [{"index_key": "banks_quality"}],
            "sector_import_runs": [{
                "run_key": "sector-1", "status": "imported",
                "source_name": "Licensed sector export", "imported_at": "2026-08-04T10:00:00Z",
            }],
            "fundamental_coverage": [{
                "primary_symbol": "RELIANCE", "annual_statement_years": 12,
                "operational_kpi_count": 8, "peer_count": 6,
                "real_company_verified": True,
            }],
            "investment_dossiers": [{
                "primary_symbol": "RELIANCE", "dossier_status": "in_review",
                "reviewed_section_count": 12, "section_count": 15,
                "specialist_count": 10, "has_portfolio_fit": True,
            }],
            "fundamental_acceptance": [{"run_key": "reliance-acceptance"}],
        }

        options_reply = ai_os_api_server.deterministic_chat_reply(
            "Is NIFTY options analytics ready?", context, [], [], {"default_model": "test"}, "not_requested"
        )
        sector_reply = ai_os_api_server.deterministic_chat_reply(
            "What sector data is stale?", context, [], [], {"default_model": "test"}, "not_requested"
        )
        fundamental_reply = ai_os_api_server.deterministic_chat_reply(
            "Which fundamental dossier is ready?", context, [], [], {"default_model": "test"}, "not_requested"
        )

        self.assertIn("42/48 validated Greeks", options_reply)
        self.assertIn("6 blocked", options_reply)
        self.assertIn("Banks: stale", sector_reply)
        self.assertIn("Latest source package sector-1 is imported", sector_reply)
        self.assertIn("12 annual statement years", fundamental_reply)
        self.assertIn("portfolio-fit present", fundamental_reply)

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

    def test_capability_question_gets_direct_deterministic_answer(self) -> None:
        reply = ai_os_api_server.deterministic_chat_reply(
            "Can you explain what you can do for me without changing anything?",
            {},
            [],
            [],
            {"default_model": "test"},
            "not_requested",
        )

        self.assertIn("delegate named work", reply)
        self.assertIn("place broker orders", reply)
        self.assertNotIn("Largest visible holding", reply)

    def test_attention_question_returns_current_work_and_decision_queue(self) -> None:
        reply = ai_os_api_server.deterministic_chat_reply(
            "Good morning Charlie. What are you working on and what needs my attention today?",
            {
                "scoped_employee": [{
                    "agent_name": "Charlie Munger",
                    "live_state": "available",
                    "current_work_title": "Daily Office Brief",
                    "current_work_detail": "The evidence-backed letter is complete.",
                }],
                "approval_summary": [
                    {"metric": "pending", "value": "2"},
                    {"metric": "high_or_critical_pending", "value": "1"},
                ],
                "pending_approvals": [{"title": "Approve research escalation"}],
                "graph_attention": [{
                    "graph_run_id": 9,
                    "title": "Review risk objection",
                    "priority": "high",
                }],
            },
            [],
            [],
            {"default_model": "test"},
            "not_requested",
        )

        self.assertIn("current assignment is Daily Office Brief", reply)
        self.assertIn("2 pending approvals", reply)
        self.assertIn("run 9 Review risk objection", reply)
        self.assertIn("Broker execution remains locked", reply)

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

    def test_direct_office_delegation_creates_message_and_linked_task(self) -> None:
        with (
            mock.patch.object(ai_os_api_server, "create_agent_message", return_value={"id": 41}) as create_message,
            mock.patch.object(
                ai_os_api_server,
                "triage_agent_message",
                return_value={"generated_task_id": 73, "generated_inbox_id": 88},
            ) as triage,
            mock.patch.object(ai_os_api_server, "audit_api_write"),
        ):
            result = ai_os_api_server.delegate_agent_task({
                "to_agent": "Research Analyst",
                "objective": "Review the latest filing with cited evidence.",
                "actor": "Devarsh",
            })
        self.assertEqual(result["status"], "queued")
        self.assertEqual(result["task_id"], 73)
        self.assertFalse(result["broker_write_allowed"])
        self.assertEqual(create_message.call_args.args[0]["to_agent"], "Research Analyst")
        self.assertEqual(triage.call_args.args[0]["action"], "create_task")


if __name__ == "__main__":
    unittest.main()
