from __future__ import annotations

import unittest
from unittest import mock

from _ai_os_runtime.api import ai_os_api_server


class OfficeSnapshotContractTest(unittest.TestCase):
    def test_graph_node_worker_summary_uses_view_output_column(self) -> None:
        captured: dict[str, str] = {}

        def fake_batch(queries: dict[str, str], *, row_limit: int | None = None) -> dict[str, list[dict]]:
            captured.update(queries)
            self.assertEqual(row_limit, 160)
            return {key: [] for key in queries}

        with mock.patch.object(ai_os_api_server, "run_psql_json_object", fake_batch):
            snapshot = ai_os_api_server.build_office_snapshot()

        self.assertEqual(snapshot["issues"], [])
        graph_query = captured["graph_node_runs"]
        self.assertIn("output_summary AS worker_summary", graph_query)
        self.assertNotIn("worker_status,worker_summary", graph_query)


if __name__ == "__main__":
    unittest.main()
