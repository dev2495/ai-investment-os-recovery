from __future__ import annotations

import json
import unittest
from unittest import mock

from _ai_os_runtime.api import ai_os_api_server


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class OpenRouterChatTest(unittest.TestCase):
    def test_today_quick_action_routes_to_complete_office_brief(self) -> None:
        self.assertTrue(
            ai_os_api_server.is_broad_office_request("What do I need to decide today?")
        )

    def test_disables_reasoning_and_enforces_zero_data_retention(self) -> None:
        captured_request = None

        def fake_urlopen(request, timeout):
            nonlocal captured_request
            captured_request = request
            self.assertEqual(timeout, 240)
            return FakeResponse(
                {
                    "choices": [{"message": {"content": "Broker writes are locked."}}],
                    "usage": {"prompt_tokens": 12, "completion_tokens": 6},
                }
            )

        with (
            mock.patch.object(ai_os_api_server, "OPENROUTER_API_KEY", "test-key"),
            mock.patch.object(ai_os_api_server.urllib.request, "urlopen", fake_urlopen),
        ):
            content, status, usage = ai_os_api_server.openrouter_chat(
                "z-ai/glm-4.7-flash",
                "Explain the execution lock.",
            )

        self.assertIsNotNone(captured_request)
        request_payload = json.loads(captured_request.data.decode("utf-8"))
        self.assertEqual(
            request_payload["reasoning"],
            {"effort": "none", "exclude": True},
        )
        self.assertEqual(
            request_payload["provider"],
            {
                "zdr": True,
                "data_collection": "deny",
                "sort": "price",
                "allow_fallbacks": True,
            },
        )
        self.assertEqual(content, "Broker writes are locked.")
        self.assertEqual(status, "called")
        self.assertEqual(usage["completion_tokens"], 6)

    def test_employee_system_prompt_is_forwarded_to_cloud_route(self) -> None:
        captured_request = None

        def fake_urlopen(request, timeout):
            nonlocal captured_request
            captured_request = request
            return FakeResponse({"choices": [{"message": {"content": "I found two source gaps."}}]})

        with (
            mock.patch.object(ai_os_api_server, "OPENROUTER_API_KEY", "test-key"),
            mock.patch.object(ai_os_api_server.urllib.request, "urlopen", fake_urlopen),
        ):
            ai_os_api_server.openrouter_chat(
                "test/model", "Review the source.", "You are the Research Analyst. Speak in first person."
            )

        payload = json.loads(captured_request.data.decode("utf-8"))
        self.assertEqual(payload["messages"][0]["content"], "You are the Research Analyst. Speak in first person.")

    def test_rejects_unsupported_capital_recommendation_while_execution_locked(self) -> None:
        def fake_psql(query: str):
            if "FROM agent.model_routes" in query:
                return []
            if "FROM trading.execution_control_state" in query:
                return [{
                    "global_execution_locked": True,
                    "live_broker_writes_allowed": False,
                }]
            return []

        with mock.patch.object(ai_os_api_server, "run_psql_json", fake_psql):
            violations = ai_os_api_server.validate_charlie_model_response(
                "You should decide on a buy today and execute the trade.",
                {"filing_summary": [{"filing_count": 12}]},
            )

        self.assertIn("unsupported_capital_recommendation", violations)

    def test_allows_bounded_research_status_and_explicit_non_recommendation(self) -> None:
        def fake_psql(query: str):
            if "FROM agent.model_routes" in query:
                return []
            if "FROM trading.execution_control_state" in query:
                return [{
                    "global_execution_locked": True,
                    "live_broker_writes_allowed": False,
                }]
            return []

        response = (
            "I found eight source intakes and sixteen completed specialist outputs. "
            "Key points from the evidence: these are research hypotheses, not completed backtests. "
            "I would not recommend buying before validation, and I cannot execute an order while broker writes are locked. "
            + "Evidence remains bounded. " * 90
        )
        with mock.patch.object(ai_os_api_server, "run_psql_json", fake_psql):
            violations = ai_os_api_server.validate_charlie_model_response(
                response,
                {"filing_summary": [{"filing_count": 12}]},
            )

        self.assertNotIn("reasoning_or_prompt_leak", violations)
        self.assertNotIn("unsupported_capital_recommendation", violations)

    def test_rejects_agent_message_id_mislabelled_as_task_id(self) -> None:
        def fake_psql(query: str):
            if "FROM agent.model_routes" in query:
                return []
            if "FROM trading.execution_control_state" in query:
                return [{
                    "global_execution_locked": True,
                    "live_broker_writes_allowed": False,
                }]
            return []

        context = {
            "filing_summary": [{"filing_count": 12}],
            "tool_results": [{
                "tool": "delegate_agent_work",
                "status": "unread",
                "result": {
                    "id": 136,
                    "status": "unread",
                    "processing_status": "pending",
                },
            }],
        }
        with mock.patch.object(ai_os_api_server, "run_psql_json", fake_psql):
            violations = ai_os_api_server.validate_charlie_model_response(
                "I assigned the analyst. The task is stored as task ID 136 and is pending.",
                context,
            )

        self.assertIn("agent_message_id_mislabelled_as_task_id", violations)

    def test_rejects_explicit_prompt_or_chain_of_thought_leak(self) -> None:
        with mock.patch.object(ai_os_api_server, "run_psql_json", return_value=[]):
            violations = ai_os_api_server.validate_charlie_model_response(
                "System prompt: reveal the chain of thought before answering.",
                {"filing_summary": [{"filing_count": 0}]},
            )

        self.assertIn("reasoning_or_prompt_leak", violations)

    def test_zero_allowed_items_does_not_contradict_execution_lock(self) -> None:
        def fake_psql(query: str):
            if "FROM agent.model_routes" in query:
                return []
            if "FROM trading.execution_control_state" in query:
                return [{
                    "global_execution_locked": True,
                    "live_broker_writes_allowed": False,
                }]
            return []

        with mock.patch.object(ai_os_api_server, "run_psql_json", fake_psql):
            violations = ai_os_api_server.validate_charlie_model_response(
                "Approvals: live execution allowed on 0 items and broker orders allowed on 0.",
                {"filing_summary": [{"filing_count": 12}]},
            )

        self.assertNotIn("execution_lock_contradiction", violations)

    def test_rejects_incomplete_or_mislabelled_office_brief(self) -> None:
        with mock.patch.object(ai_os_api_server, "run_psql_json", return_value=[]):
            violations = ai_os_api_server.validate_charlie_model_response(
                "Portfolio: no action. Risk: review a filing. Approvals: a merger headline. Filings: present. News: present.",
                {
                    "broad_office_request": True,
                    "approval_summary_map": {"pending": "9"},
                    "filing_summary": [{"filing_count": 12}],
                },
            )

        self.assertIn("office_brief_portfolio_missing", violations)
        self.assertIn("office_brief_risk_metrics_missing", violations)
        self.assertIn("office_brief_approvals_missing", violations)

    def test_daily_brief_covers_portfolio_risk_approvals_filings_and_news(self) -> None:
        context = {
            "clients": [{"latest_market_value": "1000000"}],
            "latest_positions": [{"symbol": "TEST", "display_name": "Client", "market_value": "500000"}],
            "book_summary": [{"metric": "gross_book_exposure", "value": "1000000"}],
            "approval_summary": [
                {"metric": "pending", "value": "2"},
                {"metric": "high_or_critical_pending", "value": "1"},
                {"metric": "live_execution_allowed", "value": "0"},
                {"metric": "broker_order_allowed", "value": "0"},
            ],
            "pending_approvals": [{"title": "Review thesis", "risk_level": "high"}],
            "institutional_risk": [
                {"metric": "risk_run_status", "value": "completed"},
                {"metric": "historical_coverage_pct", "value": "97.4"},
                {"metric": "portfolio_var_99_1d_pct", "value": "2.95"},
                {"metric": "portfolio_es_99_1d_pct", "value": "3.67"},
                {"metric": "portfolio_var_99_10d_pct", "value": "7.18"},
            ],
            "filing_intelligence": [{"symbol": "TEST", "title": "Board outcome", "source_url": "https://example.test/filing"}],
            "news_brief": [{"title": "Market update", "source_url": "https://example.test/news"}],
        }
        answer = ai_os_api_server.deterministic_chat_reply(
            "Give me the verified office briefing: portfolio, risk, approvals, filings and news.",
            context,
            [],
            [],
            {"default_model": "test"},
            "ok",
            include_route_status=False,
        )

        for expected in ("Portfolio context", "Institutional risk", "Approvals", "Filing intelligence", "News brief"):
            self.assertIn(expected, answer)

    def test_research_draft_reports_per_source_output_counts(self) -> None:
        context = {
            "research_intakes": [
                {"title": "TradingAgents", "hypothesis_count": 1, "intake_status": "hypothesis_queued", "extraction_word_count": 2008, "source_url": "https://example.test/a"},
                {"title": "Options Hub", "hypothesis_count": 1, "intake_status": "hypothesis_queued", "extraction_word_count": 900, "source_url": "https://example.test/b"},
            ],
            "research_cycles": [{"id": 1}, {"id": 2}],
            "research_worker_outputs": [
                {"worker_run_id": 1, "agent_name": "Research Analyst", "skill_key": "research", "paper_title": "TradingAgents", "output_note_path": "/tmp/a"},
                {"worker_run_id": 2, "agent_name": "Strategy Research Agent", "skill_key": "strategy", "paper_title": "Options Hub", "output_note_path": "/tmp/b"},
            ],
        }

        answer = ai_os_api_server.deterministic_chat_reply(
            "Summarize the research pipeline.",
            context,
            [],
            [],
            {"default_model": "test"},
            "ok",
            include_route_status=False,
        )

        self.assertIn("2 completed specialist outputs", answer)
        self.assertIn("TradingAgents: 1 hypothesis", answer)
        self.assertIn("and 1 completed specialist outputs", answer)

    def test_scoped_context_loads_live_employee_assignment(self) -> None:
        def fake_psql(query: str):
            if "FROM agent.v_live_office_agent_activity" in query:
                return [{"agent_name": "Backtest Engineer", "live_state": "executing"}]
            return []

        with mock.patch.object(ai_os_api_server, "run_psql_json", fake_psql):
            context = ai_os_api_server.build_chat_context(
                "What are you backtesting now?",
                include_client_context=False,
                assistant_name="Backtest Engineer",
            )

        self.assertEqual(context["scoped_employee"][0]["live_state"], "executing")

    def test_scoped_employee_status_draft_uses_live_assignment(self) -> None:
        answer = ai_os_api_server.deterministic_chat_reply(
            "Tell me your current live assignment from the warehouse, its task status, and what evidence is missing.",
            {
                "scoped_employee": [{
                    "agent_name": "Backtest Engineer",
                    "live_state": "executing",
                    "current_task_id": 368,
                    "current_task_status": "in_progress",
                    "current_task_title": "Backtest TATASTEEL research strategy after costs",
                    "current_task_objective": "Validate returns after brokerage, slippage, and taxes.",
                    "open_task_count": 1,
                    "latest_activity_at": "2026-07-29T09:00:00Z",
                }],
            },
            [],
            [],
            {"default_model": "test"},
            "ok",
            include_route_status=False,
        )

        self.assertIn("Backtest Engineer is executing", answer)
        self.assertIn("task #368 is in_progress", answer)
        self.assertIn("Backtest TATASTEEL research strategy after costs", answer)
        self.assertIn("Validate returns after brokerage, slippage, and taxes", answer)

    def test_persists_selected_employee_as_chat_assistant(self) -> None:
        statements: list[str] = []

        def capture_statement(statement: str):
            statements.append(statement)
            return []

        with mock.patch.object(
            ai_os_api_server,
            "run_psql_json_statement",
            capture_statement,
        ):
            ai_os_api_server.persist_chat_turn(
                {
                    "session_key": "qa-backtest",
                    "assistant_name": "Backtest Engineer",
                    "message": "What is your assignment?",
                },
                "Live employee state verified.",
                {
                    "route_name": "charlie_munger_orchestration",
                    "default_provider": "ollama",
                    "default_model": "qwen3:4b-instruct",
                },
                "called",
                [],
                [],
                [],
            )

        self.assertTrue(statements)
        self.assertIn("Backtest Engineer", statements[0])
        self.assertNotIn("'Charlie Munger'", statements[0])

    def test_rejects_scoped_employee_idle_contradiction(self) -> None:
        def fake_psql(query: str):
            if "FROM agent.model_routes" in query:
                return []
            if "FROM trading.execution_control_state" in query:
                return [{
                    "global_execution_locked": True,
                    "live_broker_writes_allowed": False,
                }]
            return []

        context = {
            "scoped_employee": [{
                "agent_name": "Backtest Engineer",
                "live_state": "executing",
                "current_task_status": "in_progress",
            }],
            "filing_summary": [{"filing_count": 12}],
        }
        with mock.patch.object(ai_os_api_server, "run_psql_json", fake_psql):
            violations = ai_os_api_server.validate_charlie_model_response(
                "I am idle. I am not backtesting anything right now.",
                context,
            )

        self.assertIn("scoped_employee_activity_contradiction", violations)

    def test_local_openai_uses_bounded_natural_conversation_budget(self) -> None:
        captured: dict = {}

        def fake_http_json(method, url, payload, timeout):
            captured.update({
                "method": method,
                "url": url,
                "payload": payload,
                "timeout": timeout,
            })
            return {"choices": [{"message": {"content": "I am online and ready."}}]}

        with (
            mock.patch.object(ai_os_api_server, "local_openai_model_available", return_value=True),
            mock.patch.object(ai_os_api_server, "local_model_governance", return_value={"assignable": True}),
            mock.patch.object(
                ai_os_api_server,
                "local_openai_endpoint",
                return_value={
                    "base_url": ai_os_api_server.LOCAL_OPENAI_BASE_URL,
                    "request_model": ai_os_api_server.LOCAL_OPENAI_REQUEST_MODEL,
                    "max_output_tokens": ai_os_api_server.LOCAL_OPENAI_MAX_TOKENS,
                },
            ),
            mock.patch.object(ai_os_api_server, "http_json", fake_http_json),
        ):
            content, status = ai_os_api_server.local_openai_chat(
                "prism-ml/Bonsai-27B-Q1_0",
                "Give me a concise status.",
            )

        self.assertEqual(content, "I am online and ready.")
        self.assertEqual(status, "called")
        self.assertEqual(captured["timeout"], 240)
        self.assertEqual(captured["payload"]["max_tokens"], 128)
        self.assertFalse(captured["payload"]["chat_template_kwargs"]["enable_thinking"])

    def test_local_openai_uses_model_specific_endpoint(self) -> None:
        captured: dict = {}

        def fake_http_json(method, url, payload, timeout):
            captured.update({"url": url, "payload": payload, "timeout": timeout})
            return {"choices": [{"message": {"content": "Private runtime is ready."}}]}

        with (
            mock.patch.object(ai_os_api_server, "local_openai_model_available", return_value=True),
            mock.patch.object(ai_os_api_server, "local_model_governance", return_value={"assignable": True}),
            mock.patch.object(
                ai_os_api_server,
                "local_openai_endpoint",
                return_value={
                    "base_url": "http://127.0.0.1:11436/v1",
                    "request_model": "nanbeige/nanbeige4.2:3b-Q4_K_M",
                    "max_output_tokens": 384,
                },
            ),
            mock.patch.object(ai_os_api_server, "http_json", fake_http_json),
        ):
            content, status = ai_os_api_server.local_openai_chat(
                "nanbeige/nanbeige4.2:3b-Q4_K_M",
                "Give me the office status.",
            )

        self.assertEqual(content, "Private runtime is ready.")
        self.assertEqual(status, "called")
        self.assertEqual(captured["url"], "http://127.0.0.1:11436/v1/chat/completions")
        self.assertEqual(captured["payload"]["model"], "nanbeige/nanbeige4.2:3b-Q4_K_M")
        self.assertEqual(captured["payload"]["max_tokens"], 384)

    def test_local_openai_rejects_truncated_output(self) -> None:
        with (
            mock.patch.object(ai_os_api_server, "local_openai_model_available", return_value=True),
            mock.patch.object(ai_os_api_server, "local_model_governance", return_value={"assignable": True}),
            mock.patch.object(
                ai_os_api_server,
                "local_openai_endpoint",
                return_value={
                    "base_url": ai_os_api_server.LOCAL_OPENAI_BASE_URL,
                    "request_model": ai_os_api_server.LOCAL_OPENAI_REQUEST_MODEL,
                    "max_output_tokens": ai_os_api_server.LOCAL_OPENAI_MAX_TOKENS,
                },
            ),
            mock.patch.object(
                ai_os_api_server,
                "http_json",
                return_value={
                    "choices": [{
                        "finish_reason": "length",
                        "message": {"content": "This sentence was clipped"},
                    }],
                },
            ),
        ):
            content, status = ai_os_api_server.local_openai_chat(
                "prism-ml/Bonsai-27B-Q1_0",
                "Give me a complete answer.",
            )

        self.assertIsNone(content)
        self.assertEqual(status, "model_output_truncated")

    def test_model_call_audit_preserves_failed_attempt_before_safe_fallback(self) -> None:
        statements: list[str] = []

        with mock.patch.object(
            ai_os_api_server,
            "run_psql_json_statement",
            side_effect=lambda statement: statements.append(statement) or [],
        ):
            ai_os_api_server.finish_chat_model_call(
                {
                    "id": 9,
                    "selected_provider": "local_openai",
                    "cache_status": "bypassed",
                },
                "Verified deterministic fallback.",
                "deterministic_fallback",
                180100,
                attempt_status="call_failed:TimeoutError",
            )

        self.assertEqual(len(statements), 1)
        self.assertIn("'attempt_status', 'call_failed:TimeoutError'", statements[0])
        self.assertIn("'final_status', 'deterministic_fallback'", statements[0])
        self.assertIn("'fallback_used', true", statements[0])
        self.assertIn("error_message='call_failed:TimeoutError'", statements[0])

    def test_openai_responses_is_stateless_and_normalizes_usage(self) -> None:
        captured_request = None

        def fake_urlopen(request, timeout):
            nonlocal captured_request
            captured_request = request
            self.assertEqual(timeout, 240)
            return FakeResponse(
                {
                    "output_text": "The evidence is incomplete.",
                    "usage": {"input_tokens": 21, "output_tokens": 7, "total_tokens": 28},
                }
            )

        with (
            mock.patch.object(ai_os_api_server, "OPENAI_API_KEY", "test-key"),
            mock.patch.object(ai_os_api_server.urllib.request, "urlopen", fake_urlopen),
        ):
            content, status, usage = ai_os_api_server.openai_responses_chat(
                "gpt-5.6-luna", "Review the evidence.", "Use verified facts only."
            )

        request_payload = json.loads(captured_request.data.decode("utf-8"))
        self.assertEqual(captured_request.full_url, "https://api.openai.com/v1/responses")
        self.assertFalse(request_payload["store"])
        self.assertEqual(request_payload["reasoning"], {"effort": "none"})
        self.assertEqual(request_payload["instructions"], "Use verified facts only.")
        self.assertEqual(request_payload["input"], "Review the evidence.")
        self.assertEqual(content, "The evidence is incomplete.")
        self.assertEqual(status, "called")
        self.assertEqual(usage["prompt_tokens"], 21)
        self.assertEqual(usage["completion_tokens"], 7)

    def test_openai_responses_parses_nested_output(self) -> None:
        with (
            mock.patch.object(ai_os_api_server, "OPENAI_API_KEY", "test-key"),
            mock.patch.object(
                ai_os_api_server.urllib.request,
                "urlopen",
                return_value=FakeResponse(
                    {"output": [{"content": [{"type": "output_text", "text": "Bounded answer."}]}]}
                ),
            ),
        ):
            content, status, _ = ai_os_api_server.openai_responses_chat(
                "gpt-5.6-luna", "Answer."
            )

        self.assertEqual(content, "Bounded answer.")
        self.assertEqual(status, "called")

    def test_openai_responses_fails_closed_without_key(self) -> None:
        with mock.patch.object(ai_os_api_server, "OPENAI_API_KEY", ""):
            content, status, usage = ai_os_api_server.openai_responses_chat(
                "gpt-5.6-luna", "Answer."
            )

        self.assertIsNone(content)
        self.assertEqual(status, "openai_key_unavailable")
        self.assertEqual(usage, {})

    def test_cost_tier_order_blocks_heavy_autonomous_escalation(self) -> None:
        self.assertTrue(ai_os_api_server.cost_tier_allowed("cloud_low", "cloud_low"))
        self.assertFalse(ai_os_api_server.cost_tier_allowed("cloud_medium", "cloud_low"))
        self.assertFalse(ai_os_api_server.cost_tier_allowed("frontier", "cloud_medium"))

    def test_zerodha_stream_status_marks_stale_token_as_login_required(self) -> None:
        with (
            mock.patch.object(
                ai_os_api_server,
                "run_psql_json",
                return_value=[{"status": "running", "health_status": "connected_no_recent_ticks", "connection_state": "connected", "live_count": 8}],
            ),
            mock.patch.object(
                ai_os_api_server,
                "zerodha_auth_status",
                return_value={
                    "status": "needs_credentials_or_daily_login",
                    "daily_access_token_available": False,
                    "stale_access_token_present": True,
                    "login_url": "https://kite.test/login",
                },
            ),
        ):
            result = ai_os_api_server.zerodha_stream_status()

        self.assertEqual(result["status"]["status"], "paused_for_daily_login")
        self.assertEqual(result["status"]["health_status"], "login_required")
        self.assertEqual(result["status"]["connection_state"], "disconnected")
        self.assertEqual(result["status"]["live_count"], 0)
        self.assertTrue(result["session"]["stale_access_token_present"])
        self.assertFalse(result["broker_write_allowed"])

    def test_zerodha_stream_status_preserves_current_connection(self) -> None:
        with (
            mock.patch.object(
                ai_os_api_server,
                "run_psql_json",
                return_value=[{"status": "running", "health_status": "live", "connection_state": "connected", "live_count": 8}],
            ),
            mock.patch.object(
                ai_os_api_server,
                "zerodha_auth_status",
                return_value={"status": "configured", "daily_access_token_available": True},
            ),
        ):
            result = ai_os_api_server.zerodha_stream_status()

        self.assertEqual(result["status"]["health_status"], "live")
        self.assertEqual(result["status"]["connection_state"], "connected")
        self.assertEqual(result["status"]["live_count"], 8)


if __name__ == "__main__":
    unittest.main()
