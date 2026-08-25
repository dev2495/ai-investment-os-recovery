import tempfile
import unittest
from pathlib import Path

from report_delivery import select_thesis_report_delivery


class ThesisReportDeliveryTests(unittest.TestCase):
    def test_view_prefers_html_companion_for_pdf_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "thesis-v19.pdf"
            companion = report.with_suffix(".html")
            report.write_bytes(b"%PDF-1.7 binary")
            companion.write_text("<html>report</html>", encoding="utf-8")
            selected, content_type, disposition = select_thesis_report_delivery(report, "view")
            self.assertEqual(selected, companion)
            self.assertEqual(content_type, "text/html; charset=utf-8")
            self.assertEqual(disposition, "inline")

    def test_view_streams_pdf_when_html_companion_is_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "thesis-v19.pdf"
            report.write_bytes(b"%PDF-1.7 binary")
            selected, content_type, disposition = select_thesis_report_delivery(report, "view")
            self.assertEqual(selected, report)
            self.assertEqual(content_type, "application/pdf")
            self.assertEqual(disposition, "inline")

    def test_download_keeps_pdf_binary_and_attachment_disposition(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "thesis-v19.pdf"
            report.write_bytes(b"%PDF-1.7 binary")
            report.with_suffix(".html").write_text("<html>report</html>", encoding="utf-8")
            selected, content_type, disposition = select_thesis_report_delivery(report, "download")
            self.assertEqual(selected, report)
            self.assertEqual(content_type, "application/pdf")
            self.assertEqual(disposition, "attachment")


if __name__ == "__main__":
    unittest.main()
