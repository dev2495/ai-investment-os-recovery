from __future__ import annotations

import argparse
import unittest
from unittest import mock

from _ai_os_runtime.api import ai_os_api_server
from _ai_os_runtime.scripts import manage_long_term_research as research


class LongTermValuationGovernanceTests(unittest.TestCase):
    def complete_payload(self, **overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "status": "complete",
            "fair_value_low": 400.0,
            "fair_value_base": 500.0,
            "fair_value_high": 650.0,
            "assumptions": {"discount_rate": 0.12},
            "outputs": {"enterprise_value": 1000},
            "evidence": [{"source": "https://example.test/annual-report.pdf"}],
            "operator_confirmed": False,
        }
        payload.update(overrides)
        return payload

    def test_completion_requires_full_range_assumptions_outputs_and_sources(self) -> None:
        invalid = (
            {"fair_value_low": None},
            {"assumptions": {}},
            {"outputs": {}},
            {"evidence": []},
            {"evidence": [{}]},
        )
        for override in invalid:
            with self.subTest(override=override), self.assertRaises(ValueError):
                research.validate_valuation_update(**self.complete_payload(**override))

    def test_range_and_numbers_are_validated_authoritatively(self) -> None:
        with self.assertRaisesRegex(ValueError, "fair_value_low"):
            research.validate_valuation_update(**self.complete_payload(fair_value_low=700.0))
        with self.assertRaisesRegex(ValueError, "finite"):
            research.optional_finite_number("nan", "fair_value_base")
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            research.validate_valuation_update(**self.complete_payload(fair_value_low=-1.0))

    def test_reviewed_status_requires_explicit_operator_confirmation(self) -> None:
        with self.assertRaisesRegex(ValueError, "operator_confirmed"):
            research.validate_valuation_update(**self.complete_payload(status="reviewed"))
        research.validate_valuation_update(
            **self.complete_payload(status="reviewed", operator_confirmed=True)
        )

    def test_in_progress_update_preserves_existing_model_fields(self) -> None:
        args = argparse.Namespace(
            holding_thesis_id=2,
            model_key="dcf",
            status="in_progress",
            fair_value_low=None,
            fair_value_base=None,
            fair_value_high=None,
            expected_cagr_pct=None,
            assumptions_json=None,
            outputs_json=None,
            evidence_json=None,
            note_path=None,
            actor="Valuation Agent",
            operator_confirmed=False,
        )
        existing = {
            "fair_value_low": 400,
            "fair_value_base": 500,
            "fair_value_high": 650,
            "expected_cagr_pct": 12,
            "assumptions": {"discount_rate": 0.12},
            "outputs": {"enterprise_value": 1000},
        }
        with mock.patch.object(research, "run_psql_json", side_effect=[[existing], [{"id": 91}]]) as database:
            result = research.action_valuation(args)

        update_sql = database.call_args_list[1].args[0]
        self.assertIn("fair_value_low = '400.0'", update_sql)
        self.assertIn("fair_value_base = '500.0'", update_sql)
        self.assertIn("fair_value_high = '650.0'", update_sql)
        self.assertEqual(result["research_update_id"], 91)

    def test_api_passes_operator_confirmation_only_when_explicit(self) -> None:
        with (
            mock.patch.object(ai_os_api_server.subprocess, "run", return_value=mock.Mock(returncode=0, stdout='{"status":"reviewed"}', stderr="")) as run,
            mock.patch.object(ai_os_api_server, "audit_api_write"),
        ):
            ai_os_api_server.update_long_term_valuation_model({
                "holding_thesis_id": 2,
                "model_key": "dcf",
                "status": "reviewed",
                "operator_confirmed": True,
            })

        self.assertIn("--operator-confirmed", run.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
