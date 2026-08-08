from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = RUNTIME_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_institutional_fundamental_factory as factory


AS_OF = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)


def complete_context(*, verified: bool = True) -> dict:
    evidence = [
        {
            "id": index,
            "source_type": source_type,
            "source_name": "Primary source",
            "source_title": f"Stored source {index}",
            "published_at": f"2026-07-{index:02d}T08:00:00+00:00",
            "retrieved_at": f"2026-07-{index:02d}T09:00:00+00:00",
            "verification_status": "human_verified" if index == 1 else "machine_extracted",
        }
        for index, source_type in enumerate(
            ["annual_report", "earnings_call", "annual_letter", "industry_report", "financial_statement", "valuation_work", "material_news"],
            start=1,
        )
    ]
    opinions = [
        {
            "id": 100 + index,
            "holding_thesis_id": 41,
            "specialist_key": specialist,
            "agent_name": f"{specialist} agent",
            "opinion_status": "evidence_complete",
            "conclusion": f"Stored conclusion for {specialist}.",
            "confidence_pct": 70,
            "disconfirming_evidence": "Stored dissent record.",
            "required_followups": [],
            "evidence_id": evidence[index % len(evidence)]["id"],
            "opinion_as_of": "2026-08-03T10:00:00+00:00",
        }
        for index, specialist in enumerate(sorted(factory.REQUIRED_SPECIALISTS))
    ]
    return {
        "company": {
            "id": 9,
            "company_key": "nse-reliance",
            "legal_name": "Reliance Industries Limited",
            "primary_symbol": "RELIANCE",
            "primary_exchange": "NSE",
            "status": "active",
            "real_company_verified_at": "2026-01-01T00:00:00+00:00" if verified else None,
            "real_company_verification_evidence_id": 1 if verified else None,
        },
        "latest_dossier": {"holding_thesis_id": 41, "source_cutoff_at": "2026-07-05T00:00:00+00:00"},
        "committee": {
            "committee_review_id": 81,
            "committee_decision_id": 82,
            "recorded_decision": "hold",
            "recorded_decision_status": "final",
            "decision_notes": "Hold after independent review.",
            "decided_by": "Devarsh",
            "decision_created_at": "2026-08-03T11:00:00+00:00",
            "capital_action_allowed": False,
            "live_execution_allowed": False,
        },
        "evidence": evidence,
        "opinions": opinions,
        "coverage": {
            "annual_statement_years": 12,
            "segment_count": 3,
            "segment_fact_years": 8,
            "operational_kpi_count": 5,
            "market_share_series_count": 2,
            "peer_count": 5,
            "management_communication_count": 7,
            "management_claim_count": 8,
            "claims_with_outcomes": 4,
            "completed_valuation_types": ["dcf", "reverse_dcf", "peer_comparison"],
            "completed_monte_carlo_count": 1,
        },
    }


class FakeGateway:
    def __init__(self, context: dict) -> None:
        self.context = context
        self.persisted: list[dict] = []
        self.selectors: list[tuple[dict, datetime]] = []

    def load_context(self, selector: dict, as_of: datetime) -> dict:
        self.selectors.append((selector, as_of))
        return self.context

    def persist(self, plan: dict) -> dict:
        self.persisted.append(plan)
        return {"dossier_version_id": 501, "acceptance_run_id": 701, "capital_action_allowed": False, "broker_execution_allowed": False}


class InstitutionalFundamentalFactoryTests(unittest.TestCase):
    def request(self, *, dry_run: bool = True) -> factory.FactoryRequest:
        return factory.FactoryRequest({"symbol": "RELIANCE", "exchange": "NSE"}, AS_OF, "Test Research Factory", "factory-test-1", dry_run)

    def test_builds_exact_fifteen_section_version_from_stored_inputs(self) -> None:
        plan = factory.build_plan(complete_context(), self.request())

        self.assertEqual(len(plan["sections"]), 15)
        self.assertEqual([row["section_key"] for row in plan["sections"]], [row[0] for row in factory.SECTION_SPECS])
        self.assertEqual(plan["acceptance_status"], "passed")
        self.assertEqual(len(plan["opinion_ids"]), 12)
        self.assertEqual(len(plan["acceptance_gates"]), 20)
        self.assertTrue(all(row["primary_evidence_id"] in range(1, 8) for row in plan["sections"]))
        self.assertIn("Stored conclusion for valuation.", next(row for row in plan["sections"] if row["section_key"] == "valuation")["content_markdown"])
        self.assertIn("Decision record: `82`", next(row for row in plan["sections"] if row["section_key"] == "specialist_opinions_committee_decision")["content_markdown"])
        self.assertNotIn("buy", plan["executive_conclusion"].lower())

    def test_missing_fact_coverage_fails_explicit_gates_without_fabricating_values(self) -> None:
        context = complete_context()
        context["coverage"]["annual_statement_years"] = 4
        context["coverage"]["market_share_series_count"] = 0

        plan = factory.build_plan(context, self.request())
        gates = {row["gate_key"]: row for row in plan["acceptance_gates"]}

        self.assertEqual(plan["acceptance_status"], "failed")
        self.assertEqual(gates["statement_history"]["gate_status"], "failed")
        self.assertEqual(gates["statement_history"]["observed_value"], {"value": 4})
        self.assertEqual(gates["market_share"]["gate_status"], "failed")
        self.assertIn("statement_history", plan["decision_summary"]["failed_gates"])

    def test_missing_committee_valuation_or_challenge_blocks_acceptance(self) -> None:
        context = complete_context()
        context["committee"] = {}
        context["coverage"]["completed_valuation_types"] = ["dcf"]
        context["coverage"]["completed_monte_carlo_count"] = 0
        challenge = next(row for row in context["opinions"] if row["specialist_key"] == "risk")
        challenge["disconfirming_evidence"] = ""

        plan = factory.build_plan(context, self.request())
        gates = {row["gate_key"]: row for row in plan["acceptance_gates"]}

        self.assertEqual(plan["acceptance_status"], "failed")
        self.assertEqual(gates["committee_decision"]["gate_status"], "failed")
        self.assertEqual(gates["valuation_suite"]["gate_status"], "failed")
        self.assertEqual(gates["independent_challenge"]["gate_status"], "failed")
        committee_section = next(row for row in plan["sections"] if row["section_key"] == "specialist_opinions_committee_decision")
        self.assertEqual(committee_section["section_status"], "draft")
        self.assertIn("No final human committee decision", committee_section["content_markdown"])

    def test_management_claims_require_observed_outcomes(self) -> None:
        context = complete_context()
        context["coverage"]["claims_with_outcomes"] = 0

        plan = factory.build_plan(context, self.request())
        gate = next(row for row in plan["acceptance_gates"] if row["gate_key"] == "management_accountability")

        self.assertEqual(gate["gate_status"], "failed")

    def test_context_query_is_point_in_time_for_valuation_and_committee(self) -> None:
        gateway = factory.PsqlGateway()
        captured: list[str] = []
        gateway._run_json = lambda sql: captured.append(sql) or {}  # type: ignore[method-assign]

        gateway.load_context({"symbol": "RELIANCE", "exchange": "NSE"}, AS_OF)
        sql = captured[0]

        self.assertIn("latest_committee AS", sql)
        self.assertIn("portfolio.long_term_committee_decisions", sql)
        self.assertIn("completed_valuation_types", sql)
        self.assertIn("portfolio.long_term_monte_carlo_runs", sql)
        self.assertIn("created_at<=", sql)

    def test_dry_run_reads_but_never_persists(self) -> None:
        gateway = FakeGateway(complete_context())

        result = factory.run_factory(self.request(dry_run=True), gateway)

        self.assertEqual(result["status"], "planned")
        self.assertEqual(gateway.persisted, [])
        self.assertFalse(result["execution_envelope"]["capital_action_allowed"])
        self.assertFalse(result["execution_envelope"]["broker_execution_allowed"])

    def test_unverified_company_is_blocked_before_any_write(self) -> None:
        gateway = FakeGateway(complete_context(verified=False))

        result = factory.run_factory(self.request(dry_run=False), gateway)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(gateway.persisted, [])
        self.assertIn("human-verified", result["reason"])

    def test_non_dry_run_persists_research_only_plan(self) -> None:
        gateway = FakeGateway(complete_context())

        result = factory.run_factory(self.request(dry_run=False), gateway)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["database"]["dossier_version_id"], 501)
        self.assertEqual(len(gateway.persisted), 1)
        persisted = gateway.persisted[0]
        self.assertFalse(persisted["decision_summary"]["capital_action_allowed"])
        self.assertFalse(persisted["decision_summary"]["broker_execution_allowed"])

    def test_refresh_triggers_only_use_recognized_evidence_after_prior_cutoff(self) -> None:
        context = complete_context()
        plan = factory.build_plan(context, self.request())

        self.assertGreater(len(plan["refresh_triggers"]), 0)
        self.assertTrue(all(row["trigger_type"] in set(factory.TRIGGER_TYPE_BY_SOURCE.values()) for row in plan["refresh_triggers"]))
        self.assertTrue(all(datetime.fromisoformat(row["event_at"]) > datetime(2026, 7, 5, tzinfo=timezone.utc) for row in plan["refresh_triggers"]))

    def test_future_input_is_rejected_by_point_in_time_gate(self) -> None:
        context = complete_context()
        context["evidence"][0]["retrieved_at"] = "2026-08-05T00:00:00+00:00"

        plan = factory.build_plan(context, self.request())
        gate = next(row for row in plan["acceptance_gates"] if row["gate_key"] == "point_in_time_inputs")

        self.assertEqual(gate["gate_status"], "failed")

    def test_cli_emits_structured_json_and_requires_timezone(self) -> None:
        gateway = FakeGateway(complete_context())
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = factory.main(
                ["--symbol", "RELIANCE", "--exchange", "NSE", "--as-of", "2026-08-04T12:00:00+00:00", "--dry-run"],
                gateway=gateway,
            )
        payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "planned")
        self.assertEqual(payload["company"]["primary_symbol"], "RELIANCE")
        with self.assertRaisesRegex(ValueError, "explicit timezone"):
            factory.parse_as_of("2026-08-04T12:00:00")

    def test_persistence_sql_is_versioned_acceptance_gated_and_has_no_execution_write(self) -> None:
        context = complete_context()
        gateway = factory.PsqlGateway()
        captured: list[str] = []
        gateway._run_json = lambda sql: captured.append(sql) or {"dossier_version_id": 1}  # type: ignore[method-assign]

        gateway.persist(factory.build_plan(context, self.request(dry_run=False)))
        sql = captured[0]

        self.assertIn("INSERT INTO research.investment_dossier_versions", sql)
        self.assertIn("INSERT INTO research.investment_dossier_sections", sql)
        self.assertIn("INSERT INTO research.fundamental_specialist_opinions", sql)
        self.assertIn("INSERT INTO research.investment_dossier_refresh_triggers", sql)
        self.assertIn("research.open_real_company_acceptance_run", sql)
        self.assertIn("INSERT INTO research.fundamental_acceptance_gates", sql)
        self.assertIn("DELETE FROM research.fundamental_acceptance_gates", sql)
        self.assertIn("context.acceptance_run_id IS NOT NULL", sql)
        self.assertIn("'acceptance_run_opened', context.acceptance_run_id IS NOT NULL", sql)
        self.assertIn("SELECT context.dossier_version_id, incoming.*", sql)
        self.assertIn("SELECT context.dossier_id, incoming.*", sql)
        self.assertIn("SELECT context.acceptance_run_id, incoming.*", sql)
        self.assertNotIn("(context.dossier_version_id", sql)
        self.assertNotIn("INSERT INTO trading.", sql)
        self.assertNotIn("INSERT INTO portfolio.orders", sql)
        self.assertNotIn("broker_order", sql)


if __name__ == "__main__":
    unittest.main()
