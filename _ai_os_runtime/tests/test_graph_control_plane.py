from __future__ import annotations

import unittest
from pathlib import Path

from _ai_os_runtime.api import graph_control_plane


class GraphControlPlaneTest(unittest.TestCase):
    def test_condition_matching_is_declarative_and_bounded(self) -> None:
        run = {"working_state": {"risk": {"passed": True}, "mode": "paper"}}
        node = {"output_payload": {"decision": "approved", "score": 0.81}}

        matched, evidence = graph_control_plane.condition_matches(
            {"condition_type": "state_equals", "condition": {"path": "risk.passed", "equals": True}},
            run,
            node,
        )
        self.assertTrue(matched)
        self.assertTrue(evidence["observed"])

        matched, _ = graph_control_plane.condition_matches(
            {"condition_type": "node_output_equals", "condition": {"path": "decision", "equals": "rejected"}},
            run,
            node,
        )
        self.assertFalse(matched)

        matched, evidence = graph_control_plane.condition_matches(
            {"condition_type": "node_output_not_equals", "condition": {"path": "decision", "equals": "paper_monitor"}},
            run,
            node,
        )
        self.assertTrue(matched)
        self.assertEqual(evidence["observed"], "approved")

        matched, evidence = graph_control_plane.condition_matches(
            {"condition_type": "python_eval", "condition": {"code": "dangerous()"}},
            run,
            node,
        )
        self.assertFalse(matched)
        self.assertEqual(evidence["error"], "unsupported_condition")

    def test_start_rejects_missing_typed_inputs_before_writing(self) -> None:
        writes: list[str] = []

        def query(sql: str):
            if "v_graph_catalog" in sql:
                return [{
                    "graph_key": "strategy_research_lifecycle",
                    "status": "active",
                    "version_status": "active",
                    "validation_result": {"valid": True},
                }]
            if "input_contract" in sql:
                return [{"input_contract": {"required": ["hypothesis"]}}]
            return []

        def statement(sql: str):
            writes.append(sql)
            return []

        with self.assertRaisesRegex(ValueError, "missing required graph inputs: hypothesis"):
            graph_control_plane.start_graph_run(
                query,
                statement,
                {"graph_key": "strategy_research_lifecycle", "input_payload": {}},
            )
        self.assertEqual(writes, [])

    def test_idempotency_key_is_order_stable(self) -> None:
        first = graph_control_plane.idempotency_key("research", "ABC", {"b": 2, "a": 1})
        second = graph_control_plane.idempotency_key("research", "ABC", {"a": 1, "b": 2})
        third = graph_control_plane.idempotency_key("research", "XYZ", {"a": 1, "b": 2})
        self.assertEqual(first, second)
        self.assertNotEqual(first, third)

    def test_migration_contains_runtime_safety_contracts(self) -> None:
        migration = (
            Path(graph_control_plane.__file__).resolve().parents[1]
            / "postgres"
            / "init"
            / "170_graph_control_plane_v1.sql"
        ).read_text(encoding="utf-8")

        for table in (
            "agent.graph_definitions",
            "agent.graph_versions",
            "agent.graph_nodes",
            "agent.graph_edges",
            "agent.graph_runs",
            "agent.graph_node_runs",
            "agent.graph_edge_runs",
            "agent.graph_checkpoints",
            "agent.autonomy_policies",
            "agent.correction_ledger",
            "agent.waiting_on_principal",
        ):
            self.assertIn(table, migration)

        self.assertIn("'broker_execution_prohibited'", migration)
        self.assertIn("'strategy_research_lifecycle'", migration)
        self.assertIn("'research_to_investment_decision'", migration)
        self.assertIn("'kronos_forecast_research'", migration)
        self.assertIn("arbitrary_code_allowed", migration)
        self.assertIn("live_broker_writes_allowed", migration)

    def test_committee_bridge_routes_human_decisions_without_live_execution(self) -> None:
        migration = (
            Path(graph_control_plane.__file__).resolve().parents[1]
            / "postgres"
            / "init"
            / "171_graph_committee_bridge_v1.sql"
        ).read_text(encoding="utf-8")

        self.assertIn("agent.open_graph_committee_packet", migration)
        self.assertIn("'sealed_until_quorum',true", migration)
        self.assertIn("'model_decision','Human model feature decision'", migration)
        self.assertIn("'node_output_not_equals'", migration)
        self.assertIn('"broker_order_allowed":false', migration)


if __name__ == "__main__":
    unittest.main()
