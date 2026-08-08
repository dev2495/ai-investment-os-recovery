from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _ai_os_runtime.scripts import extract_long_term_source_document as extractor


class LongTermSourceDocumentStorageTests(unittest.TestCase):
    def test_external_text_artifact_uses_absolute_storage_reference(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            text_path = Path(directory) / "source.txt"
            text_path.write_text("source backed text", encoding="utf-8")
            document = {
                "id": 3,
                "source_request_id": 2,
                "symbol": "USHAMART",
                "document_type": "annual_report",
                "document_title": "Annual Report",
                "source_url": "https://example.test/annual-report.pdf",
            }
            with mock.patch.object(
                extractor,
                "run_psql_json",
                return_value=[{"id": 99}],
            ) as database:
                artifact_id = extractor.insert_raw_text_artifact(
                    document,
                    text_path,
                    "source backed text",
                    10,
                    "pypdf",
                )

        self.assertEqual(artifact_id, 99)
        self.assertIn(str(text_path.resolve()), database.call_args.args[0])

    def test_external_pdf_and_text_paths_persist_without_vault_relative_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pdf_path = Path(directory) / "source.pdf"
            text_path = Path(directory) / "source.txt"
            document = {
                "id": 3,
                "source_request_id": 2,
                "symbol": "USHAMART",
                "document_type": "annual_report",
                "document_title": "Annual Report",
                "source_url": "https://example.test/annual-report.pdf",
            }
            with mock.patch.object(
                extractor,
                "run_psql_json",
                return_value=[{"id": 7, "key_snippets": []}],
            ) as database:
                extractor.persist_extraction(
                    document,
                    pdf_path,
                    text_path,
                    "source backed text",
                    10,
                    "pypdf",
                    99,
                    "Fundamental Data Engineer",
                )

        sql = database.call_args.args[0]
        self.assertIn(str(pdf_path.resolve()), sql)
        self.assertIn(str(text_path.resolve()), sql)


if __name__ == "__main__":
    unittest.main()
