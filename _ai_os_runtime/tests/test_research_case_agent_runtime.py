from __future__ import annotations

import unittest
from decimal import Decimal
from unittest.mock import patch

from api.research_case_agent_runtime import (
    MAX_REVIEW_ATTEMPTS,
    ROLE_PLAN,
    PACK_SECTION_PLAN,
    SPECIALIST_ROLES,
    _validate_output,
    _role_context,
    _review_correction_envelope,
    _validate_review_correction_responses,
    _unlock_next,
    _sanitize_output_citations,
    _block_for_cost_ceiling,
    _publish_terminal_evidence_debt_report,
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
        specialist_routes = {row["route_name"] for row in plan[:7]}
        lead_routes = {row["route_name"] for row in plan[7:]}
        self.assertEqual(specialist_routes, {"openrouter_research_fast"})
        self.assertEqual(lead_routes, {"openrouter_public_lead_deepseek_v4_pro"})

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


    def test_review_corrections_are_first_class_and_not_truncated(self):
        completed = [{
            "id": 55, "iteration": 3, "attempt": 1, "role_key": "independent_review",
            "output_summary": {
                "review_decision": "needs_revision",
                "revision_requests": [
                    {"request": f"Correct mismatch {index}", "citation_ids": [f"fact:{index}"]}
                    for index in range(1, 7)
                ],
                "blocking_findings": ["Metric labels do not match their cited facts."],
            },
        }]
        envelope = _review_correction_envelope(completed)
        self.assertIsNotNone(envelope)
        self.assertEqual(len(envelope["revision_requests"]), 6)
        self.assertTrue(envelope["must_address_every_request"])
        self.assertTrue(all(row["correction_id"] for row in envelope["revision_requests"]))
        context = _role_context("lead_synthesis", {"case": {}, "boundaries": {}}, completed)
        self.assertEqual(context["required_review_corrections"], envelope)
        self.assertEqual(MAX_REVIEW_ATTEMPTS, 2)


    def test_required_reviewer_corrections_are_enforced(self):
        context = {
            "required_review_corrections": {
                "revision_requests": [
                    {"correction_id": "review-55-1-a", "request": "Fix fact mismatch"},
                    {"correction_id": "review-55-2-b", "request": "Remove unsupported ratio"},
                ],
            },
        }
        output = {
            "correction_responses": [{
                "correction_id": "review-55-1-a",
                "resolution": "Removed the mismatched fact.",
            }],
        }
        self.assertEqual(
            _validate_review_correction_responses(output, context),
            ["unaddressed_review_correction:review-55-2-b"],
        )
        output["correction_responses"].append({
            "correction_id": "review-55-2-b",
            "resolution": "Removed the unsupported ratio.",
        })
        self.assertEqual(_validate_review_correction_responses(output, context), [])

    def test_exhausted_independent_review_publishes_without_paid_call(self):
        statements = []

        def run_statement(sql):
            statements.append(sql)
            if "WITH current_review AS" in sql and "RETURNING id,event_status" in sql:
                return [{"event_status": "blocked"}]
            return []

        with patch(
            "api.research_case_agent_runtime._publish_terminal_evidence_debt_report"
        ) as publish:
            _unlock_next(
                12, 6, "independent_review",
                {
                    "review_decision": "needs_revision",
                    "revision_requests": ["Correct the metric mapping."],
                    "blocking_findings": ["A cited fact is relabelled."],
                },
                run_statement, lambda value: repr(value), lambda value: repr(value),
            )
        publish.assert_called_once()
        args = publish.call_args.args
        self.assertEqual(args[:2], (12, "independent_review_attempts_exhausted"))
        transition_sql = next(sql for sql in statements if "WITH current_review AS" in sql)
        self.assertIn("attempt FROM current_review)>=2", transition_sql)
        self.assertIn("RETURNING id,event_status", transition_sql)

    def test_financial_fact_claim_is_canonicalized_from_packet(self):
        output = {
            "summary": "draft",
            "facts": [{
                "claim": "FY2026 revenue was 1055550 lakh.",
                "value": 1055550,
                "citation_ids": ["fact:579"],
            }],
            "analysis": [], "calculations": [], "risks": [], "disconfirmers": [], "missing": [],
        }
        packet = {"financial_facts": [{
            "citation_id": "fact:579",
            "fact_key": "cash_and_cash_equivalents",
            "fiscal_year": 2026,
            "period_end": "2026-03-31",
            "value": 1055550,
            "unit": "lakh",
            "statement_scope": "consolidated",
            "extraction_status": "validated",
        }]}
        cleaned = _sanitize_output_citations(output, {"fact:579"}, packet)
        self.assertEqual(len(cleaned["facts"]), 1)
        fact = cleaned["facts"][0]
        self.assertEqual(fact["fact_key"], "cash_and_cash_equivalents")
        self.assertEqual(fact["value"], 1055550)
        self.assertEqual(fact["unit"], "lakh")
        self.assertIn("Cash And Cash Equivalents", fact["claim"])
        self.assertNotIn("revenue", fact["claim"].lower())

    def test_unvalidated_financial_fact_is_removed_as_evidence_debt(self):
        output = {
            "summary": "draft",
            "facts": [{
                "claim": "Revenue was 100 lakh.",
                "value": 100,
                "citation_ids": ["fact:1"],
            }],
            "analysis": [], "calculations": [], "risks": [], "disconfirmers": [], "missing": [],
        }
        packet = {"financial_facts": [{
            "citation_id": "fact:1",
            "fact_key": "revenue",
            "fiscal_year": 2026,
            "value": 100,
            "unit": "lakh",
            "statement_scope": "consolidated",
            "extraction_status": "machine_extracted",
        }]}
        cleaned = _sanitize_output_citations(output, {"fact:1"}, packet)
        self.assertEqual(cleaned["facts"], [])
        self.assertTrue(any(
            "not validated or human reviewed" in str(item)
            for item in cleaned["missing"]
        ))

    def test_terminal_evidence_debt_report_projects_without_model_call(self):
        statements = []
        report_calls = []

        def run_statement(sql):
            statements.append(sql)
            return [{"id": 1}]

        def report_generator(case_id, generated_by):
            report_calls.append((case_id, generated_by))
            return {
                "research_case_id": case_id,
                "holding_thesis_id": 44,
                "report_id": 81,
                "report_version": 3,
                "content_state": "evidence_debt",
                "delivery_state": "html_ready_pdf_retry",
                "freshness_state": "mixed",
                "decision_state": "research_required",
                "section_count": 8,
                "citation_count": 27,
            }

        result = _publish_terminal_evidence_debt_report(
            12, "independent_review_attempts_exhausted", run_statement,
            lambda value: repr(value), lambda value: repr(value), report_generator,
        )
        self.assertEqual(result["status"], "evidence_debt_pack_published")
        self.assertEqual(report_calls, [(12, "Research Report Builder · evidence debt")])
        self.assertTrue(any("evidence_debt_pack_published" in sql for sql in statements))
        self.assertFalse(any("openrouter" in sql.lower() for sql in statements))

    def test_cost_ceiling_terminal_marks_case_and_publishes(self):
        statements = []
        report_calls = []

        def run_statement(sql):
            statements.append(sql)
            return [{"id": 1}]

        def report_generator(case_id, generated_by):
            report_calls.append((case_id, generated_by))
            return {
                "research_case_id": case_id,
                "report_id": 91,
                "content_state": "evidence_debt",
                "delivery_state": "html_ready",
                "freshness_state": "mixed",
                "decision_state": "research_required",
            }

        result = _block_for_cost_ceiling(
            {
                "id": 158, "research_case_id": 15, "iteration": 2,
                "preflight_id": 52, "hard_max_cost_usd": "0.5497488",
            },
            spent=Decimal("0.543923"),
            projected_cost=Decimal("0.010000"),
            reason="projected_hard_cost_ceiling",
            run_statement=run_statement,
            sql_literal=lambda value: repr(value),
            sql_jsonb=lambda value: repr(value),
            report_generator=report_generator,
        )
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(
            result["report"]["status"], "evidence_debt_pack_published",
        )
        self.assertEqual(report_calls, [(15, "Research Report Builder · evidence debt")])
        combined = "\n".join(statements)
        self.assertIn("cost_ceiling", combined)
        self.assertIn("evidence_debt_pack_published", combined)
        self.assertFalse(result["capital_action_allowed"])
        self.assertFalse(result["external_write_allowed"])


if __name__ == "__main__":
    unittest.main()
