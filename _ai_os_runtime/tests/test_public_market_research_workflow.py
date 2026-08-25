from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
for candidate in (RUNTIME_ROOT, RUNTIME_ROOT / "scripts", RUNTIME_ROOT / "api"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from api import ai_os_api_server
from api.market_research_workflow import (
    build_public_market_evidence_packet,
    materiality_for_news,
)
import run_agent_worker_once


class PublicMarketEvidencePacketTest(unittest.TestCase):
    def fake_query(self, sql: str) -> list[dict]:
        if "FROM market.news_items" in sql:
            return [{
                "id": 7,
                "source_name": "official-feed",
                "source_url": "https://example.test/item-7",
                "title": "Company reports quarterly results and guidance",
                "publisher": "Example Exchange",
                "author": None,
                "published_at": "2026-08-10T10:00:00+00:00",
                "captured_at": "2026-08-10T10:01:00+00:00",
                "symbols": ["EXAMPLE"],
                "topics": ["results"],
                "geography": "IN",
                "relevance_score": 0.9,
            }]
        if "FROM market.live_quote_state" in sql:
            return [{
                "provider": "read-only-broker",
                "provider_symbol": "EXAMPLE",
                "symbol": "EXAMPLE",
                "exchange": "NSE",
                "last_price": 100,
                "change_percent": 1,
                "received_at": "2026-08-10T10:02:00+00:00",
                "broker_write_allowed": False,
            }]
        if "FROM market.corporate_event_calendar" in sql:
            return []
        if "FROM core.data_source_freshness_checks" in sql:
            return [{
                "source_key": "global_news",
                "source_name": "Public news",
                "freshness_target_minutes": 15,
                "latest_check_at": "2026-08-10T10:02:00+00:00",
                "status": "fresh",
                "severity": "low",
                "staleness_minutes": 2,
                "rows_seen": 1,
            }]
        raise AssertionError(sql)

    def test_packet_is_cited_stable_and_fail_closed_for_capital(self) -> None:
        payload = {"subject": "Review EXAMPLE quarterly results", "symbol": "EXAMPLE"}
        first = build_public_market_evidence_packet(self.fake_query, payload)
        second = build_public_market_evidence_packet(self.fake_query, payload)
        self.assertEqual(first["source_fingerprint"], second["source_fingerprint"])
        self.assertEqual(first["quality"]["status"], "warning")
        self.assertFalse(first["quality"]["capital_action_allowed"])
        self.assertFalse(first["quality"]["live_execution_allowed"])
        self.assertFalse(first["quality"]["broker_write_allowed"])
        self.assertEqual(first["news"][0]["source_url"], "https://example.test/item-7")

    def test_materiality_is_deterministic_and_not_a_trade_signal(self) -> None:
        result = materiality_for_news({"title": "Board approves buyback after results", "relevance_score": 0.9})
        self.assertTrue(result["material"])
        self.assertGreaterEqual(result["score"], 3)
        self.assertIn("corporate_action", result["reasons"])


class PublicMarketResearchGraphTest(unittest.TestCase):
    def test_api_freezes_packet_and_keeps_user_command_idempotency_stable(self) -> None:
        packet = {
            "packet_version": "public_market_evidence_v1",
            "source_fingerprint": "a" * 64,
            "subject": "Example results",
            "symbol": "EXAMPLE",
            "quality": {"status": "passed", "capital_action_allowed": False},
        }
        captured: dict = {}

        def fake_start(query, statement, payload):
            captured.update(payload)
            return {"graph_run_id": 41, "created": True}

        with (
            mock.patch.object(ai_os_api_server, "build_public_market_evidence_packet", return_value=packet),
            mock.patch.object(ai_os_api_server.graph_control_plane, "start_graph_run", side_effect=fake_start),
            mock.patch.object(ai_os_api_server.graph_control_plane, "advance_graph_run", return_value={"graph_run_id": 41, "run_status": "running"}),
            mock.patch.object(ai_os_api_server, "audit_api_write"),
        ):
            result = ai_os_api_server.start_graph_control_run({
                "graph_key": "research_to_investment_decision",
                "trigger_type": "charlie_chat",
                "subject_ref": "example-results",
                "input_payload": {"subject": "Example results", "symbol": "EXAMPLE"},
            })

        self.assertTrue(result["created"])
        self.assertEqual(result["evidence_gate"]["source_fingerprint"], "a" * 64)
        self.assertEqual(captured["input_payload"]["evidence_packet"], packet)
        expected_key = ai_os_api_server.graph_control_plane.idempotency_key(
            "research_to_investment_decision",
            "example-results",
            {
                "subject": "Example results",
                "symbol": "EXAMPLE",
                "decision_question": None,
                "objective": None,
            },
        )
        self.assertEqual(captured["idempotency_key"], expected_key)
        self.assertNotIn(packet["source_fingerprint"], captured["idempotency_key"])

    def test_worker_outputs_citations_and_explicit_missing_evidence(self) -> None:
        packet = build_public_market_evidence_packet(PublicMarketEvidencePacketTest().fake_query, {
            "subject": "Review EXAMPLE quarterly results", "symbol": "EXAMPLE"
        })
        context = {"market_research_packet": packet, "recent_filings": []}
        summary, actions = run_agent_worker_once.market_research_summary_for("analyze_corporate_filing", context)
        self.assertIn("https://example.test/item-7", summary)
        self.assertIn("No accepted official filing row", summary)
        self.assertIn("Broker write allowed: false", summary)
        self.assertTrue(actions)

    def test_migration_and_daemon_contract_are_fail_closed(self) -> None:
        migration = (RUNTIME_ROOT / "postgres" / "init" / "221_public_market_research_workflow_v1.sql").read_text()
        daemon = (RUNTIME_ROOT / "scripts" / "run_agent_message_daemon.py").read_text()
        for value in (
            "market_research_heartbeat_runs",
            "cooldown_until",
            "broker_write_allowed BOOLEAN NOT NULL DEFAULT false",
            "live_execution_allowed BOOLEAN NOT NULL DEFAULT false",
            "capital_action_allowed BOOLEAN NOT NULL DEFAULT false",
        ):
            self.assertIn(value, migration)
        self.assertIn("run_market_research_heartbeat", daemon)
        self.assertIn("source_blocked", daemon)
        self.assertIn("idempotency_key", daemon)


if __name__ == "__main__":
    unittest.main()
