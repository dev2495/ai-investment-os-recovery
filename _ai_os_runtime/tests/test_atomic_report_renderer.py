import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
from atomic_report_renderer import render_html_pdf
import research_case_report


class AtomicReportRendererTests(unittest.TestCase):
    def _browser(self, root: Path, body: str) -> Path:
        path = root / "fake-browser"
        path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

    def test_valid_pdf_atomically_replaces_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            html = root / "report.html"
            pdf = root / "report.pdf"
            html.write_text("<html>report</html>", encoding="utf-8")
            pdf.write_bytes(b"old")
            browser = self._browser(root, "for a in \"$@\"; do case \"$a\" in --print-to-pdf=*) p=${a#*=};; esac; done\nprintf '%s' '%PDF-1.7 valid report bytes' > \"$p\"\n")
            result = render_html_pdf(browser, html, pdf, timeout_seconds=1, stable_checks=1,
                                     poll_interval=0.01, minimum_size=8)
            self.assertTrue(result["ok"])
            self.assertTrue(pdf.read_bytes().startswith(b"%PDF-"))
            self.assertFalse(list(root.glob("*.rendering-*.pdf")))

    def test_timeout_preserves_existing_destination_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            html = root / "report.html"
            pdf = root / "report.pdf"
            html.write_text("<html>report</html>", encoding="utf-8")
            pdf.write_bytes(b"existing")
            browser = self._browser(root, "sleep 5\n")
            result = render_html_pdf(browser, html, pdf, timeout_seconds=0.1, stable_checks=1,
                                     poll_interval=0.01, minimum_size=8)
            self.assertFalse(result["ok"])
            self.assertEqual(pdf.read_bytes(), b"existing")
            self.assertFalse(list(root.glob("*.rendering-*.pdf")))

    def test_renderer_requires_both_header_suppression_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            html = root / "report.html"
            pdf = root / "report.pdf"
            html.write_text("<html>report</html>", encoding="utf-8")
            browser = self._browser(
                root,
                "new=0; legacy=0\n"
                "for a in \"$@\"; do case \"$a\" in "
                "--no-pdf-header-footer) new=1;; "
                "--print-to-pdf-no-header) legacy=1;; "
                "--print-to-pdf=*) p=${a#*=};; esac; done\n"
                "if [ \"$new\" = 1 ] && [ \"$legacy\" = 1 ]; then "
                "printf '%s' '%PDF-1.7 headerless report bytes' > \"$p\"; fi\n",
            )
            result = render_html_pdf(browser, html, pdf, timeout_seconds=1, stable_checks=1,
                                     poll_interval=0.01, minimum_size=8)
            self.assertTrue(result["ok"])

    def test_private_path_pdf_is_rejected_without_replacing_prior_pdf(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            html = root / "report.html"
            pdf = root / "report.pdf"
            html.write_text("<html>report</html>", encoding="utf-8")
            pdf.write_bytes(b"%PDF-1.7 prior-safe-report")
            browser = self._browser(
                root,
                "for a in \"$@\"; do case \"$a\" in --print-to-pdf=*) p=${a#*=};; esac; done\n"
                "printf '%s' '%PDF-1.7 file:///Volumes/Devarsh SSD/private/report.html' > \"$p\"\n",
            )
            result = render_html_pdf(browser, html, pdf, timeout_seconds=1, stable_checks=1,
                                     poll_interval=0.01, minimum_size=8)
            self.assertFalse(result["ok"])
            self.assertIn("privacy validation failed", result["error"])
            self.assertEqual(pdf.read_bytes(), b"%PDF-1.7 prior-safe-report")

    def test_report_links_only_render_public_http_sources(self):
        public = research_case_report._source_link("https://issuer.example/report.pdf", 9)
        private = research_case_report._source_link("file:///Volumes/Devarsh SSD/private/report.pdf", 9)
        self.assertIn("https://issuer.example/report.pdf", public)
        self.assertNotIn("file://", private)
        self.assertIn("public URL unavailable", private)

    def test_draft_or_evidence_debt_never_assesses_as_accepted(self):
        common = {
            "case": {},
            "evidence": [{"validation_status": "validated"}],
            "preflight": {"status": "completed"},
            "review": {"status": "completed", "output_summary": {"review_decision": "passed"},
                       "validation_result": {"valid": True}},
            "facts": [{"extraction_status": "validated"}],
            "ratios": [{"calculation_status": "validated", "value": "12.5"}],
        }
        draft = research_case_report.assess_prepublication(
            common["case"], [{"section_key": "summary", "status": "draft", "coverage_gaps": []}],
            common["evidence"], common["preflight"], common["review"], [], common["facts"], common["ratios"])
        self.assertEqual(draft["content_state"], "draft")
        self.assertNotIn("Complete", draft["content_label"])
        debt = research_case_report.assess_prepublication(
            common["case"], [{"section_key": "summary", "status": "reviewed", "coverage_gaps": ["FY2023 cash flow"]}],
            common["evidence"], common["preflight"], common["review"],
            [{"status": "open", "severity": "high"}], common["facts"], common["ratios"])
        self.assertEqual(debt["content_state"], "evidence_debt")
        self.assertEqual(debt["decision_state"], "research_required")

    def test_acceptance_requires_preflight_review_sections_sources_facts_and_ratios(self):
        result = research_case_report.assess_prepublication(
            {}, [{"section_key": "summary", "status": "reviewed", "coverage_gaps": []}],
            [{"validation_status": "human_reviewed"}], {"status": "completed"},
            {"status": "completed", "output_summary": {"review_decision": "passed"},
             "validation_result": {"valid": True}},
            [{"status": "open", "severity": "high", "blocker_key": "report_pdf_render"}],
            [{"extraction_status": "validated"}],
            [{"calculation_status": "human_reviewed", "value": "8.2"}],
        )
        self.assertEqual(result["content_state"], "accepted")
        self.assertEqual(result["decision_state"], "awaiting_human_review")
        self.assertFalse(result["capital_action_allowed"])
        self.assertEqual(result["open_delivery_blocker_count"], 1)
        self.assertEqual(result["open_high_blocker_count"], 0)

    def test_financial_exhibits_preserve_conversion_formula_citations_and_gaps(self):
        facts = [
            {"fact_key": "revenue", "fiscal_year": 2024, "period_end": "2024-03-31",
             "statement_type": "income_statement", "statement_scope": "consolidated",
             "value": "12345", "unit": "lakh", "source_page": 81,
             "source_url": "https://issuer.example/ar-2024.pdf", "extraction_status": "validated"},
            {"fact_key": "revenue", "fiscal_year": 2026, "period_end": "2026-03-31",
             "statement_type": "income_statement", "statement_scope": "consolidated",
             "value": "15000", "unit": "lakh", "source_page": 90,
             "source_url": "https://issuer.example/ar-2026.pdf", "extraction_status": "human_reviewed"},
        ]
        ratios = [{"formula_key": "roce", "formula_version": 1, "label": "ROCE",
                   "expression": "EBIT / average capital employed × 100", "unit": "percent",
                   "period_end": "2026-03-31", "statement_scope": "consolidated", "value": "18.25",
                   "calculation_status": "validated", "caveats": ["Average capital basis"],
                   "inputs": [{"input_role": "ebit", "value": "2500", "unit": "lakh",
                               "source_page": 92, "source_url": "https://issuer.example/ar-2026.pdf"}]}]
        rendered, snapshot = research_case_report.render_financial_exhibits(facts, ratios)
        self.assertIn("₹123.45 crore", rendered)
        self.assertIn("12,345 INR lakh ÷ 100", rendered)
        self.assertIn("EBIT / average capital employed", rendered)
        self.assertIn("https://issuer.example/ar-2026.pdf", rendered)
        self.assertEqual(snapshot["missing_financial_years"], [2025])

    def test_pdf_failure_preserves_honestly_labelled_html_and_delivery_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AI OS Data").mkdir()
            statements = []

            def fake_rows(sql):
                if "FROM research.research_cases" in sql:
                    return [{"id": 22, "company_id": 9, "company_name": "Example Limited",
                             "ticker": "EXAMPLE", "exchange": "NSE", "mandate": "Research Example",
                             "decision_readiness": "evidence_debt", "owner_agent": "Lead"}]
                if "FROM research.research_pack_sections" in sql:
                    return [{"section_key": "investment_conclusion", "title": "Investment conclusion",
                             "status": "draft", "content": {"summary": "Draft conclusion"},
                             "coverage_gaps": ["Valuation inputs missing"]}]
                if "FROM research.research_case_evidence" in sql:
                    return []
                if "FROM research.model_run_preflights" in sql:
                    return [{"status": "completed"}]
                if "FROM research.research_case_model_runs" in sql:
                    return [{"status": "completed", "output_summary": {"review_decision": "passed"},
                             "validation_result": {"valid": True}}]
                if "FROM research.research_case_blockers" in sql:
                    return []
                if "FROM research.financial_source_facts" in sql:
                    return []
                if "FROM research.financial_ratio_results" in sql:
                    return []
                if "coalesce(max(report_version),0)+1" in sql:
                    return [{"version": 1}]
                if "SELECT id,report_version,report_status" in sql:
                    return [{"id": 88, "report_version": 1, "report_status": "generated",
                             "html_path": "unused", "html_hash": "abc", "pdf_path": None, "pdf_hash": None}]
                if "FROM portfolio.holding_theses" in sql:
                    return [{"id": 31, "thesis_version": 1, "thesis_status": "under_research",
                             "decision_status": "research_required"}]
                raise AssertionError(sql)

            with mock.patch.object(research_case_report, "SSD", root),                  mock.patch.object(research_case_report, "ROOT", root / "reports"),                  mock.patch.object(research_case_report.Path, "is_mount", return_value=True),                  mock.patch.object(research_case_report.os, "access", return_value=True),                  mock.patch.object(research_case_report, "rows", side_effect=fake_rows),                  mock.patch.object(research_case_report, "statement", side_effect=statements.append),                  mock.patch.object(research_case_report, "chrome", return_value=None):
                result = research_case_report.generate_research_case_report(22)
            html_text = Path(result["html_path"]).read_text(encoding="utf-8")
            self.assertEqual(result["report_status"], "generated")
            self.assertEqual(result["delivery_state"], "html_ready_pdf_retry")
            self.assertEqual(result["content_state"], "evidence_debt")
            self.assertIsNone(result["pdf_path"])
            self.assertIn("Evidence-Debt Research Pack", html_text)
            self.assertNotIn("Complete Company Research Pack", html_text)
            self.assertIn("page-break-after:avoid", html_text)
            self.assertIn("section h2,section h3,thead{break-after:avoid;page-break-after:avoid}", html_text)
            self.assertIn("break-inside:avoid;page-break-inside:avoid", html_text)
            self.assertTrue(any("html_ready_pdf_retry" in sql for sql in statements))

    def test_case_retry_updates_same_report_id_and_version(self):
        with tempfile.TemporaryDirectory() as directory:
            html = Path(directory) / "case-v3.html"
            html.write_text("<html>report</html>", encoding="utf-8")
            statements = []
            report_row = [{"id": 71, "research_case_id": 12, "report_version": 3,
                           "html_path": str(html), "html_hash": "abc", "coverage_snapshot": {}}]
            rendered = {"ok": True, "pdf_path": str(html.with_suffix(".pdf")), "pdf_hash": "def",
                        "size_bytes": 1234, "duration_ms": 10}
            with mock.patch.object(research_case_report, "rows", return_value=report_row), \
                 mock.patch.object(research_case_report, "statement", side_effect=statements.append), \
                 mock.patch.object(research_case_report, "chrome", return_value=Path("/fake/chrome")), \
                 mock.patch.object(research_case_report, "render_html_pdf", return_value=rendered):
                result = research_case_report.retry_research_case_report_pdf(71)
            self.assertEqual(result["report_id"], 71)
            self.assertEqual(result["report_version"], 3)
            self.assertIn("WHERE id=71", statements[0])
            self.assertIn("without rerunning paid research", statements[0])
            self.assertIn('"delivery_state": "pdf_ready"', statements[0])


if __name__ == "__main__":
    unittest.main()
