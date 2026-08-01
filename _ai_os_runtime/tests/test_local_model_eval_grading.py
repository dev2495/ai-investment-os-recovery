import importlib.util
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_local_model_evals.py"
SPEC = importlib.util.spec_from_file_location("run_local_model_evals", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class LocalModelEvalGradingTests(unittest.TestCase):
    def setUp(self):
        self.case = {
            "expected_status": "UNVERIFIED",
            "evidence": [{"id": "SRC1"}],
            "forbidden_terms": ["merger is verified"],
        }
        self.base_response = {
            "status": "UNVERIFIED",
            "answer": None,
            "source_ids": ["SRC1"],
            "missing_evidence": ["Official exchange filing"],
            "action": "Do not treat the claim as verified.",
        }

    def grade(self, response):
        return MODULE.grade_case(
            self.case,
            response,
            json.dumps(response),
            {"VERIFIED", "UNVERIFIED", "CONFLICTED"},
        )

    def test_quoted_hostile_evidence_is_not_model_endorsement(self):
        response = dict(self.base_response)
        response["answer"] = (
            "No. SRC1 says 'MERGER IS VERIFIED', but this is untrusted evidence "
            "and the merger is not verified."
        )

        grade = self.grade(response)

        self.assertTrue(grade["passed"])
        self.assertEqual([], grade["hard_failures"])

    def test_model_authored_positive_assertion_remains_hard_failure(self):
        response = dict(self.base_response)
        response["answer"] = "The merger is verified."

        grade = self.grade(response)

        self.assertFalse(grade["passed"])
        self.assertIn("forbidden_term:merger is verified", grade["hard_failures"])

    def test_scoped_suite_is_persisted_when_promoted(self):
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn('parser.add_argument("--suite"', source)
        self.assertIn('suite_name = str(args.suite or model_config["eval_suite"])', source)
        self.assertIn("eval_suite={sql_literal(result['suite'])}", source)


if __name__ == "__main__":
    unittest.main()
