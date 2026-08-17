from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

from _ai_os_runtime.api import ai_os_api_server


class OfficeSnapshotContractTest(unittest.TestCase):
    def test_graph_node_worker_summary_uses_view_output_column(self) -> None:
        captured: dict[str, str] = {}

        def fake_batch(
            queries: dict[str, str],
            *,
            row_limit: int | None = None,
            batch_size: int | None = None,
            error_collector: list[dict] | None = None,
        ) -> dict[str, list[dict]]:
            captured.update(queries)
            self.assertEqual(row_limit, 160)
            self.assertEqual(batch_size, 4)
            self.assertIsNotNone(error_collector)
            return {key: [] for key in queries}

        with mock.patch.object(ai_os_api_server, "run_psql_json_object", fake_batch):
            snapshot = ai_os_api_server.build_office_snapshot()

        self.assertEqual(snapshot["issues"], [])
        graph_query = captured["graph_node_runs"]
        self.assertIn("output_summary AS worker_summary", graph_query)
        self.assertNotIn("worker_status,worker_summary", graph_query)
        agent_query = captured["agents"]
        self.assertIn("agent.v_employee_profiles_v1", agent_query)
        self.assertIn("agent.v_agent_operating_readiness", agent_query)
        self.assertIn("output_artifact_count", agent_query)
        self.assertIn("assigned_model", agent_query)
        self.assertIn("missing_tools", agent_query)
        self.assertEqual(snapshot["projection_meta"]["privacy_mode"], "shared_safe")
        self.assertFalse(snapshot["projection_meta"]["client_detail_exposed"])
        self.assertFalse(snapshot["projection_meta"]["broker_write_allowed"])

    def test_shared_office_projection_redacts_private_work_before_response(self) -> None:
        secret = "private-client-portfolio-name"
        rows = {
            "agents": [{
                "agent_name": "Client Analyst",
                "department_name": "Client Office",
                "current_work_title": secret,
                "current_work_detail": f"Review {secret}",
            }],
            "live_office_agent_activity": [{
                "agent_name": "Portfolio Manager",
                "department_key": "portfolio",
                "current_task_id": 42,
                "current_task_title": secret,
                "current_work_title": secret,
                "current_work_detail": f"Account {secret}",
                "presence_title": secret,
                "presence_detail": secret,
                "latest_activity_at": "2026-08-10T13:00:00+00:00",
            }],
            "agent_messages": [{
                "id": 7,
                "from_agent": "Client Analyst",
                "to_agent": "Portfolio Manager",
                "subject": secret,
                "body": f"Holdings for {secret}",
                "metadata": {"privacy_scope": "client_private", "client_id": 99},
                "created_at": "2026-08-10T13:00:00+00:00",
            }],
            "graph_runs": [{
                "graph_run_id": 9,
                "subject_type": "client_portfolio",
                "subject_ref": secret,
                "run_status": "waiting_approval",
                "updated_at": "2026-08-10T13:00:00+00:00",
            }],
            "source_freshness": [{
                "source_key": "portfolio_report",
                "source_name": f"{secret} Holdings Report",
                "status": "fresh",
                "created_at": "2026-08-10T13:00:00+00:00",
            }],
            "execution_control": [{"global_execution_locked": True}],
        }

        def fake_batch(*_args, **_kwargs):
            return rows

        with mock.patch.object(ai_os_api_server, "run_psql_json_object", fake_batch):
            snapshot = ai_os_api_server.build_office_snapshot()

        serialized = json.dumps(snapshot)
        self.assertNotIn(secret, serialized)
        self.assertGreaterEqual(snapshot["projection_meta"]["redacted_record_count"], 5)
        self.assertEqual(snapshot["agent_messages"][0]["subject"], "Private scoped handoff")
        self.assertEqual(snapshot["graph_runs"][0]["subject_ref"], "private-workspace")
        self.assertEqual(snapshot["source_freshness"][0]["source_name"], "Restricted source")
        self.assertFalse(snapshot["projection_meta"]["client_detail_exposed"])

    def test_shared_office_projection_does_not_treat_disabled_client_mutation_as_private(self) -> None:
        self.assertFalse(ai_os_api_server._office_record_is_private({
            "privacy_scope": "internal",
            "client_record_mutation_allowed": False,
            "broker_write_allowed": False,
        }))

    def test_live_office_state_labels_match_runtime_semantics(self) -> None:
        runtime_root = Path(__file__).resolve().parents[1]
        office_view = (runtime_root / "ai-office-ui" / "src" / "destinations" / "firm" / "OfficeView.tsx").read_text(encoding="utf-8")
        live_office = (runtime_root / "ai-office-ui" / "src" / "office3d" / "LiveOffice.tsx").read_text(encoding="utf-8")
        live_office_css = (runtime_root / "ai-office-ui" / "src" / "office3d" / "LiveOffice.css.ts").read_text(encoding="utf-8")

        for source in (office_view, live_office):
            self.assertIn("\"executing\"", source)
        self.assertIn('Metric label="Working Now" value={working}', office_view)
        self.assertIn("{workingAgents} working", live_office)
        self.assertNotIn("{workingAgents} active", live_office)
        self.assertIn("targetX * progress", live_office)
        self.assertIn("leftLegRef", live_office)
        self.assertIn('activity={data?.agent_messages ?? []}', live_office)
        self.assertIn("Latest inter-agent handoffs", live_office)
        self.assertIn("Delegate task", live_office)
        self.assertIn("Inspect task", live_office)
        self.assertIn("aios:assistant-prefill", live_office)
        self.assertIn('kind: "task"', live_office)
        self.assertIn("selectedAgent={selectedAgent}", live_office)
        self.assertIn("function agentRoomKey", live_office)
        self.assertIn('return roomByKey(department) ? department : "lobby"', live_office)
        self.assertIn(".office-fallback__selected", live_office_css)
        self.assertIn("projection_meta", office_view)
        self.assertIn("Shared Office Contract", office_view)
        self.assertIn("Broker, capital and live writes locked", office_view)
        self.assertIn("Use static office", live_office)
        self.assertIn("Use animated office", live_office)
        self.assertIn("handleKeyboard", live_office)
        self.assertIn("prefers-reduced-motion: reduce", live_office)
        self.assertIn("Private handoff details hidden", live_office)
        self.assertIn("workspace gated", live_office)
        self.assertIn("office-spatial-toolbar", live_office_css)
        self.assertIn(".office-spatial-shell:focus-visible", live_office_css)

    def test_agent_roster_merges_live_activity_instead_of_showing_profile_idle_state(self) -> None:
        runtime_root = Path(__file__).resolve().parents[1]
        firm_views = (runtime_root / "ai-office-ui" / "src" / "destinations" / "firm" / "FirmAgentViews.tsx").read_text(encoding="utf-8")

        self.assertIn("data?.live_office_agent_activity", firm_views)
        self.assertIn('text(agent, "live_state", text(agent, "latest_worker_status", "idle"))', firm_views)
        self.assertIn("Talk or assign work", firm_views)
        self.assertIn('num(agent, "open_task_count")', firm_views)
        self.assertIn('num(agent, "open_inbox_count")', firm_views)


if __name__ == "__main__":
    unittest.main()
