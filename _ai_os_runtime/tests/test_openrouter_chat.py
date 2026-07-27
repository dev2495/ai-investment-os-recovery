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


if __name__ == "__main__":
    unittest.main()
