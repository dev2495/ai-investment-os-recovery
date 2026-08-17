from __future__ import annotations

import unittest

from api.research_case_agent_runtime import (
    ROLE_PLAN,
    PACK_SECTION_PLAN,
    SPECIALIST_ROLES,
    _validate_output,
    _role_context,
    _sanitize_output_citations,
    default_run_plan,
)


class ResearchCaseAgentRuntimeTests(unittest.TestCase):
    def test_plan_has_specialists_synthesis_review_and_committee(self):
        plan = default_run_plan()
        self.assertEqual(len(plan), 11)
        self.assertEqual({row["role_key"] for row in plan}, {row[0] for row in ROLE_PLAN})
        self.assertEqual(len(SPECIALIST_ROLES), 7)
        self.assertEqual(len(PACK_SECTION_PLAN), 10)
        self.assertEqual(len({row[0] for row in PACK_SECTION_PLAN}), 10)
        self.assertEqual(plan[-2]["agent_name"], "Model Validation Agent")
        self.assertEqual(plan[-1]["agent_name"], "CIO Agent")

    def test_uncited_fact_is_rejected(self):
        output = {
            "summary": "draft", "facts": [{"claim": "Revenue grew", "value": "10", "citation_ids": []}],
            "analysis": [], "calculations": [], "assumptions": [], "risks": [],
            "disconfirmers": [], "missing": [], "source_requests": [],
        }
        valid, errors, _ = _validate_output("financials", output, {"fact:1"})
        self.assertFalse(valid)
        self.assertIn("uncited_fact:0", errors)

    def test_unknown_citation_is_rejected(self):
        output = {
            "summary": "draft", "facts": [{"claim": "Revenue", "value": "10", "citation_ids": ["fact:9"]}],
            "analysis": [], "calculations": [], "assumptions": [], "risks": [],
            "disconfirmers": [], "missing": [], "source_requests": [],
        }
        valid, errors, _ = _validate_output("financials", output, {"fact:1"})
        self.assertFalse(valid)
        self.assertIn("unknown_citation:fact:9", errors)

    def test_independent_review_and_committee_contracts(self):
        base = {
            "summary": "review", "facts": [], "analysis": [], "calculations": [],
            "assumptions": [], "risks": [], "disconfirmers": [], "missing": [],
            "source_requests": [],
        }
        valid, errors, _ = _validate_output("independent_review", {**base, "review_decision": "passed"}, set())
        self.assertTrue(valid, errors)
        valid, errors, _ = _validate_output("committee_review", {**base, "human_decision_ask": ""}, set())
        self.assertFalse(valid)
        self.assertIn("missing_human_decision_ask", errors)


    def test_optional_empty_collections_are_normalised(self):
        output = {"summary": "draft", "facts": []}
        valid, errors, _ = _validate_output("financials", output, set())
        self.assertTrue(valid, errors)
        self.assertEqual(output["source_requests"], [])

    def test_unique_numeric_citation_namespace_is_canonicalised(self):
        output = {
            "summary": "draft",
            "facts": [{"claim": "Official filing claim", "value": "n/a", "citation_ids": ["source:6990"]}],
        }
        valid, errors, cited = _validate_output("industry_moat", output, {"filing:6990"})
        self.assertTrue(valid, errors)
        self.assertEqual(cited, ["filing:6990"])
        self.assertEqual(output["facts"][0]["citation_ids"], ["filing:6990"])

    def test_synthesis_receives_exact_validated_financial_values(self):
        packet = {
            "case": {"ticker": "WIPRO"}, "boundaries": {},
            "financial_facts": [
                {"citation_id": "fact:582", "fact_key": "profit_after_tax", "fiscal_year": 2026,
                 "value": 1319740, "unit": "lakh", "statement_scope": "consolidated",
                 "extraction_status": "validated"},
                {"citation_id": "fact:1", "value": 99, "unit": "lakh", "extraction_status": "machine_extracted"},
            ],
        }
        context = _role_context("lead_synthesis", packet, [])
        self.assertEqual(context["validated_financial_facts"][0]["value"], 1319740)
        self.assertEqual(context["validated_financial_facts"][0]["display_value_crore"], 13197.4)
        self.assertEqual(context["validated_financial_facts"][0]["display_unit"], "INR crore")
        self.assertEqual(len(context["validated_financial_facts"]), 1)

    def test_ambiguous_numeric_citation_namespace_is_rejected(self):
        output = {
            "summary": "draft",
            "facts": [{"claim": "Ambiguous claim", "value": "n/a", "citation_ids": ["document:5"]}],
        }
        valid, errors, _ = _validate_output("industry_moat", output, {"source:5", "filing:5"})
        self.assertFalse(valid)
        self.assertIn("unknown_citation:document:5", errors)


    def test_sanitizer_removes_pseudo_citations_without_inventing_sources(self):
        output = {
            "summary": "Evidence debt",
            "facts": [
                {"claim": "Unsupported identity", "citation_ids": ["case:15"]},
                {"claim": "Market price", "citation_ids": ["case:15", "market:Zerodha:1"]},
            ],
            "analysis": ["No validated history", {"finding": "Blocked", "citation_ids": ["packet:financial_facts"]}],
            "missing": [{"item": "Financial history", "citation_ids": ["packet:financial_facts"]}],
        }
        cleaned = _sanitize_output_citations(output, {"market:Zerodha:1"})
        self.assertEqual(len(cleaned["facts"]), 1)
        self.assertEqual(cleaned["facts"][0]["citation_ids"], ["market:Zerodha:1"])
        self.assertEqual(cleaned["analysis"][0]["citation_ids"], [])
        self.assertEqual(cleaned["analysis"][1]["citation_ids"], [])
        self.assertEqual(cleaned["missing"][0]["citation_ids"], [])
        self.assertTrue(any("Unsupported draft fact" in str(item) for item in cleaned["missing"]))


if __name__ == "__main__":
    unittest.main()
