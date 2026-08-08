from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

from _ai_os_runtime.api import ai_os_api_server


class SnapshotQueryBatchingTest(unittest.TestCase):
    def test_queries_execute_in_bounded_batches(self) -> None:
        outputs = [
            json.dumps({"a": [{"id": 1}], "b": []}),
            json.dumps({"c": [{"id": 3}]}),
        ]
        with mock.patch.object(
            ai_os_api_server,
            "run_psql_text",
            side_effect=outputs,
        ) as run_psql:
            result = ai_os_api_server.run_psql_json_object(
                {
                    "a": "SELECT 1 AS id",
                    "b": "SELECT 2 AS id",
                    "c": "SELECT 3 AS id",
                },
                batch_size=2,
            )

        self.assertEqual(run_psql.call_count, 2)
        self.assertEqual(result["a"], [{"id": 1}])
        self.assertEqual(result["b"], [])
        self.assertEqual(result["c"], [{"id": 3}])
        first_sql = run_psql.call_args_list[0].args[0]
        second_sql = run_psql.call_args_list[1].args[0]
        for sql in (first_sql, second_sql):
            self.assertIn("SET statement_timeout", sql)
            self.assertIn("SET work_mem = '4MB'", sql)
            self.assertIn("SET hash_mem_multiplier = 1.0", sql)
        self.assertIn("'a' AS key", first_sql)
        self.assertIn("'b' AS key", first_sql)
        self.assertNotIn("'c' AS key", first_sql)
        self.assertIn("'c' AS key", second_sql)

    def test_failed_batch_is_isolated_and_later_batches_continue(self) -> None:
        issues: list[dict] = []
        with mock.patch.object(
            ai_os_api_server,
            "run_psql_text",
            side_effect=[
                RuntimeError("simulated database recovery"),
                json.dumps({"c": [{"id": 3}]}),
            ],
        ):
            result = ai_os_api_server.run_psql_json_object(
                {
                    "a": "SELECT 1 AS id",
                    "b": "SELECT 2 AS id",
                    "c": "SELECT 3 AS id",
                },
                batch_size=2,
                error_collector=issues,
            )

        self.assertEqual(result["a"], [])
        self.assertEqual(result["b"], [])
        self.assertEqual(result["c"], [{"id": 3}])
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["section"], "snapshot_query_batch")
        self.assertEqual(issues[0]["query_keys"], ["a", "b"])
        self.assertIn("simulated database recovery", issues[0]["error"])

    def test_research_snapshot_uses_bounded_batches_and_reports_section_errors(self) -> None:
        captured: dict[str, object] = {}

        def fake_query_object(queries, **kwargs):
            captured["query_count"] = len(queries)
            captured.update(kwargs)
            return {name: [] for name in queries}

        with mock.patch.object(
            ai_os_api_server,
            "run_psql_json_object",
            side_effect=fake_query_object,
        ):
            result = ai_os_api_server.build_research_ideas_snapshot()

        self.assertGreater(captured["query_count"], 20)
        self.assertEqual(captured["batch_size"], 8)
        self.assertEqual(captured["row_limit"], 160)
        self.assertIs(captured["error_collector"], result["issues"])

    def test_fundamental_coverage_view_aggregates_each_fact_family_before_joining(self) -> None:
        runtime_root = Path(__file__).resolve().parents[1]
        migration = (runtime_root / "postgres" / "init" / "200_fundamental_coverage_query_plan_v1.sql").read_text(encoding="utf-8")

        self.assertIn("WITH statement_coverage AS", migration)
        self.assertIn("evidence_coverage AS", migration)
        self.assertIn("peer_coverage AS", migration)
        self.assertIn("claim_coverage AS", migration)
        self.assertNotIn("LEFT JOIN research.company_statement_facts fact ON fact.company_id = company.id", migration)
        self.assertIn("false AS broker_write_allowed", migration)


if __name__ == "__main__":
    unittest.main()
