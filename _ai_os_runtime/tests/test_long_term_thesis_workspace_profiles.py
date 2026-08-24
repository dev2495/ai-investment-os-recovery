import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from long_term_thesis_workspace import build_long_term_thesis_workspace


class LongTermThesisWorkspaceProfileTests(unittest.TestCase):
    def build(self, query):
        selector_sql = []
        query_batches = []

        def run_rows(sql):
            selector_sql.append(sql)
            return [{
                "id": 7,
                "symbol": "ACME",
                "exchange": "NSE",
                "company_name": "Acme Limited",
                "legal_name": "Acme Limited",
                "research_company_id": 11,
                "dossier_version_id": 13,
                "research_pack": {
                    "investment_conclusion": {
                        "title": "Investment conclusion",
                        "summary": "Current source-backed conclusion.",
                        "status": "reviewed",
                        "content": {"decision": "monitor"},
                        "citation_ids": [101, 102],
                        "coverage_gaps": ["current market price"],
                    },
                },
            }]

        def run_map(queries, **_kwargs):
            query_batches.append(dict(queries))
            result = {key: [] for key in queries}
            if "coverage" in queries:
                result["coverage"] = [{
                    "selected_company_facts": 31,
                    "selected_company_evidence": 17,
                    "selected_company_filings": 5,
                }]
            return result

        response = build_long_term_thesis_workspace(
            query,
            run_rows=run_rows,
            run_map=run_map,
            sql_literal=lambda value: "'" + str(value).replace("'", "''") + "'",
            runtime_root=ROOT,
            vault_root=Path("/Volumes/Devarsh SSD/Obsidian memory"),
        )
        self.assertEqual(len(selector_sql), 1)
        self.assertEqual(len(query_batches), 1)
        return response, selector_sql[0], query_batches[0]

    def test_default_dashboard_omits_research_operations_and_keeps_investor_data(self):
        response, selector_sql, queries = self.build({})

        self.assertEqual(response["workspace_profile"], "long_term_thesis_dashboard_v1")
        self.assertIn("FROM research.research_cases latest_case", selector_sql)
        self.assertIn("FROM research.research_pack_sections section", selector_sql)
        self.assertIn("'content',latest_section.content", selector_sql)
        self.assertIn(
            "ORDER BY latest_case.updated_at DESC,latest_case.id DESC\n      LIMIT 1",
            selector_sql,
        )
        self.assertIn(
            "section.updated_at DESC,section.id DESC\n                 LIMIT 20",
            selector_sql,
        )
        self.assertNotIn("FROM research.fundamental_evidence e", selector_sql)
        self.assertNotIn("research.research_case_work_items", selector_sql)
        self.assertNotIn("research.research_case_model_runs", selector_sql)

        heavy_keys = {
            "fundamental_evidence",
            "source_matrix",
            "source_pipeline",
            "cited_briefs",
            "research_cases",
            "research_case_work_items",
            "research_case_agents",
            "research_case_evidence",
            "research_case_events",
            "model_run_preflights",
            "research_case_model_runs",
            "financial_production_runs",
        }
        self.assertTrue(heavy_keys.isdisjoint(queries))
        self.assertTrue(heavy_keys.isdisjoint(response))
        dashboard_sql = "\n".join(queries.values())
        self.assertNotIn("research.research_cases", dashboard_sql)
        self.assertNotIn("research.research_case_", dashboard_sql)
        self.assertNotIn("research.model_run_preflights", dashboard_sql)
        self.assertLessEqual(len(queries), 22)

        investor_keys = {
            "dossier_sections",
            "financial_facts",
            "financial_history",
            "financial_production_ratios",
            "valuation_models",
            "filings",
            "news",
        }
        self.assertTrue(investor_keys.issubset(queries))
        self.assertTrue(investor_keys.issubset(response))
        self.assertNotIn("fundamental_evidence", queries["coverage"])
        self.assertIsNone(response["pagination"]["evidence_total"])
        pack = response["selected_thesis"]["research_pack"]["investment_conclusion"]
        self.assertEqual(pack["content"], {"decision": "monitor"})
        self.assertEqual(pack["citation_ids"], [101, 102])
        self.assertEqual(pack["coverage_gaps"], ["current market price"])

    def test_explicit_dashboard_profile_remains_lightweight(self):
        response, selector_sql, queries = self.build({"profile": ["dashboard"]})

        self.assertEqual(response["workspace_profile"], "long_term_thesis_dashboard_v1")
        self.assertIn("FROM research.research_cases latest_case", selector_sql)
        self.assertIn("FROM research.research_pack_sections section", selector_sql)
        self.assertNotIn("research_cases", queries)
        self.assertNotIn("research_case_model_runs", queries)
        self.assertLessEqual(len(queries), 22)

    def test_selection_prefers_id_then_exact_symbol_exchange_then_fallback(self):
        selector_rows = [
            {
                "id": 7, "symbol": "ACME", "exchange": "NSE",
                "company_name": "Acme Limited", "legal_name": "Acme Limited",
                "research_company_id": 11, "dossier_version_id": 13,
            },
            {
                "id": 12, "symbol": "WIPRO", "exchange": "NSE",
                "company_name": "Wipro Limited", "legal_name": "Wipro Limited",
                "research_company_id": 21, "dossier_version_id": 23,
            },
        ]

        def run_rows(_sql):
            return selector_rows

        def run_map(queries, **_kwargs):
            result = {key: [] for key in queries}
            if "coverage" in queries:
                result["coverage"] = [{}]
            return result

        def build_for(query):
            return build_long_term_thesis_workspace(
                query, run_rows=run_rows, run_map=run_map,
                sql_literal=lambda value: "'" + str(value).replace("'", "''") + "'",
                runtime_root=ROOT,
                vault_root=Path("/Volumes/Devarsh SSD/Obsidian memory"),
            )

        selected_by_symbol = build_for({"symbol": ["wipro"], "exchange": ["nse"]})
        self.assertEqual(selected_by_symbol["selected_thesis"]["id"], 12)
        self.assertEqual(selected_by_symbol["selected_thesis"]["symbol"], "WIPRO")

        selected_by_id = build_for({
            "thesis_id": ["7"], "symbol": ["WIPRO"], "exchange": ["NSE"],
        })
        self.assertEqual(selected_by_id["selected_thesis"]["id"], 7)

        fallback = build_for({"symbol": ["MISSING"], "exchange": ["BSE"]})
        self.assertEqual(fallback["selected_thesis"]["id"], 7)

    def test_operations_profile_explicitly_hydrates_control_plane(self):
        response, selector_sql, queries = self.build({"profile": ["operations"]})

        self.assertEqual(response["workspace_profile"], "long_term_thesis_operations_v1")
        self.assertIn("research.research_cases", selector_sql)
        self.assertIn("research.research_pack_sections", selector_sql)
        required_operations = {
            "fundamental_evidence",
            "research_cases",
            "research_case_work_items",
            "research_case_agents",
            "research_case_evidence",
            "research_case_events",
            "model_run_preflights",
            "research_case_model_runs",
        }
        self.assertTrue(required_operations.issubset(queries))
        self.assertTrue(required_operations.issubset(response))
        self.assertEqual(response["pagination"]["evidence_total"], 17)
        self.assertEqual(
            response["selected_thesis"]["research_pack"]["investment_conclusion"]["content"],
            {"decision": "monitor"},
        )


if __name__ == "__main__":
    unittest.main()
