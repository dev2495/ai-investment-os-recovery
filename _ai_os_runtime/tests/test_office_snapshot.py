from __future__ import annotations

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
            error_collector: list[dict] | None = None,
        ) -> dict[str, list[dict]]:
            captured.update(queries)
            self.assertEqual(row_limit, 160)
            self.assertIsNotNone(error_collector)
            return {key: [] for key in queries}

        with mock.patch.object(ai_os_api_server, "run_psql_json_object", fake_batch):
            snapshot = ai_os_api_server.build_office_snapshot()

        self.assertEqual(snapshot["issues"], [])
        graph_query = captured["graph_node_runs"]
        self.assertIn("output_summary AS worker_summary", graph_query)
        self.assertNotIn("worker_status,worker_summary", graph_query)

    def test_live_office_state_labels_match_runtime_semantics(self) -> None:
        runtime_root = Path(__file__).resolve().parents[1]
        office_view = (runtime_root / "ai-office-ui" / "src" / "destinations" / "firm" / "OfficeView.tsx").read_text(encoding="utf-8")
        live_office = (runtime_root / "ai-office-ui" / "src" / "office3d" / "LiveOffice.tsx").read_text(encoding="utf-8")
        live_office_css = (runtime_root / "ai-office-ui" / "src" / "office3d" / "LiveOffice.css.ts").read_text(encoding="utf-8")

        for source in (office_view, live_office):
            self.assertIn("\"executing\"", source)
        self.assertIn("header: \"Active\"", office_view)
        self.assertIn("{activeCount} active", live_office)
        self.assertNotIn("{activeCount} working", live_office)
        self.assertIn("targetX * progress", live_office)
        self.assertIn("leftLegRef", live_office)
        self.assertIn('activity={data?.agent_messages ?? []}', live_office)
        self.assertIn("Latest inter-agent handoffs", live_office)
        self.assertIn("Delegate task", live_office)
        self.assertIn("Inspect task", live_office)
        self.assertIn("aios:assistant-prefill", live_office)
        self.assertIn('kind: "task"', live_office)
        self.assertIn("selectedAgent={selectedAgent}", live_office)
        self.assertIn(".office-fallback__selected", live_office_css)


if __name__ == "__main__":
    unittest.main()
