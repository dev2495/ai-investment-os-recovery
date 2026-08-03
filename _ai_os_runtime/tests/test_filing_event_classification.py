from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


collector = load("collect_nse_bse_filings")
extractor = load("extract_filing_pdfs")


class FilingEventClassificationTest(unittest.TestCase):
    def classifiers(self):
        return (
            lambda title, body: collector.classify_event(title, "announcement", body),
            lambda title, body: extractor.classify_event(title, "announcement", body),
        )

    def test_generic_business_language_stays_routine(self) -> None:
        routine_cases = (
            ("Business update", "New distribution arrangement for the health insurance division."),
            ("Customer service update", "Board resolution plan for handling customer grievances."),
            ("Allotment update", "Allotment of employee stock options under the ESOP scheme."),
            ("Operational update", "Warrant officer appointed to the internal compliance team."),
        )
        for classify in self.classifiers():
            for title, body in routine_cases:
                with self.subTest(classifier=classify, title=title):
                    self.assertEqual(classify(title, body)["event_type"], "routine_filing")

    def test_specific_special_situation_phrases_are_classified(self) -> None:
        cases = (
            ("Scheme update", "Scheme of arrangement approved by the NCLT.", "scheme_arrangement"),
            ("Fund raise", "Preferential allotment of convertible warrants to promoters.", "preferential_allotment"),
            ("Creditor update", "Corporate insolvency resolution process has commenced.", "insolvency"),
            ("Transaction", "The company announced a reverse merger with the listed entity.", "reverse_merger"),
        )
        for classify in self.classifiers():
            for title, body, expected in cases:
                with self.subTest(classifier=classify, expected=expected):
                    self.assertEqual(classify(title, body)["event_type"], expected)


if __name__ == "__main__":
    unittest.main()
