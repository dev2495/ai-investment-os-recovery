from __future__ import annotations

import json
import unittest
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
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

    def test_parallel_batches_are_bounded_and_report_failures(self) -> None:
        gate = threading.Barrier(4)
        issues = []
        def execute(sql, *, timeout_seconds):
            self.assertEqual(timeout_seconds, 4)
            self.assertIn("1500ms", sql)
            gate.wait(timeout=2)
            if "'bad' AS key" in sql:
                raise TimeoutError("bounded failure")
            key = next(key for key in ("a", "b", "c") if f"'{key}' AS key" in sql)
            return json.dumps({key: [{"id": key}]})
        with mock.patch.object(ai_os_api_server, "run_psql_text", side_effect=execute):
            result = ai_os_api_server.run_psql_json_object({key: "SELECT 1" for key in ("a", "b", "c", "bad")},
                batch_size=1, parallel_batches=4, statement_timeout_ms=1500,
                process_timeout_seconds=4, error_collector=issues)
        self.assertEqual(result["a"], [{"id": "a"}])
        self.assertEqual(result["bad"], [])
        self.assertEqual(issues[0]["query_keys"], ["bad"])

    def test_database_fallback_shares_total_deadline(self) -> None:
        with mock.patch.object(ai_os_api_server, "psql_command_candidates", return_value=[["docker"], ["psql"]]), \
             mock.patch.object(ai_os_api_server.time, "monotonic", side_effect=[0, 0, 3]), \
             mock.patch.object(ai_os_api_server.subprocess, "run", side_effect=[SimpleNamespace(returncode=1, stderr="unavailable", stdout=""), SimpleNamespace(returncode=0, stderr="", stdout="[]")]) as run:
            self.assertEqual(ai_os_api_server.run_psql_text("SELECT 1", timeout_seconds=4), "[]")
        self.assertEqual([call.kwargs["timeout"] for call in run.call_args_list], [4, 1])

    def test_office_concurrent_reads_share_one_snapshot_and_preserve_timestamp(self) -> None:
        def build():
            time.sleep(0.05)
            return {"generated_at": "original", "agents": [{"agent_name": "Asha"}]}
        with mock.patch.object(ai_os_api_server, "_OFFICE_SNAPSHOT_CACHE", None), \
             mock.patch.object(ai_os_api_server, "build_office_snapshot", side_effect=build) as builder:
            with ThreadPoolExecutor(max_workers=8) as pool:
                snapshots = list(pool.map(lambda _: ai_os_api_server.cached_office_snapshot(), range(8)))
            self.assertEqual(builder.call_count, 1)
            snapshots[0]["agents"].clear()
            self.assertEqual(len(snapshots[1]["agents"]), 1)
            self.assertEqual(snapshots[1]["generated_at"], "original")



if __name__ == "__main__":
    unittest.main()
