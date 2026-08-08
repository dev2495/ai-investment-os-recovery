import importlib.util
import sys
import tempfile
from pathlib import Path
from unittest import TestCase, mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("extract_filing_pdfs", SCRIPTS / "extract_filing_pdfs.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class FilingPdfDownloadTransportTests(TestCase):
    def test_uses_verified_curl_transport_and_rejects_non_pdf(self):
        filing = {
            "id": 7,
            "source_name": "NSE",
            "attachment_url": "https://nsearchives.nseindia.com/corporate/example.pdf",
        }
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(MODULE, "ARTIFACT_ROOT", Path(directory)):
            with mock.patch.object(MODULE, "curl_get", return_value=(200, b"%PDF-1.7\ncontent")) as transport:
                path = MODULE.download_pdf(filing)
                self.assertTrue(path.is_file())
                self.assertEqual(path.read_bytes()[:4], b"%PDF")
                transport.assert_called_once()
            with mock.patch.object(MODULE, "curl_get", return_value=(200, b"<html>blocked</html>")):
                with self.assertRaises(ValueError):
                    MODULE.download_pdf({**filing, "id": 8})
