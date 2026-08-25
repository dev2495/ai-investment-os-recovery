import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import governed_pdf_runtime as runtime


class GovernedPdfRuntimeTests(unittest.TestCase):
    def test_runtime_is_external_root_scoped_and_preflighted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "pdf-extraction"
            binary = root / "bin" / "python"
            binary.parent.mkdir(parents=True)
            binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
            with mock.patch.object(runtime, "GOVERNED_RUNTIME_ROOT", root), mock.patch.object(
                runtime, "DEFAULT_SSD_PDF_PYTHON", binary
            ):
                self.assertEqual(runtime.governed_pdf_python(environment={}, verify_import=True), str(binary))

    def test_never_falls_back_outside_governed_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "pdf-extraction"
            with mock.patch.object(runtime, "GOVERNED_RUNTIME_ROOT", root):
                with self.assertRaisesRegex(RuntimeError, "inside the external-SSD"):
                    runtime.governed_pdf_python(environment={"AI_OS_PDF_PYTHON": sys.executable})

    def test_missing_runtime_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "pdf-extraction"
            missing = root / "bin" / "python"
            with mock.patch.object(runtime, "GOVERNED_RUNTIME_ROOT", root), mock.patch.object(
                runtime, "DEFAULT_SSD_PDF_PYTHON", missing
            ):
                with self.assertRaisesRegex(RuntimeError, "no internal-disk fallback"):
                    runtime.governed_pdf_python(environment={})


if __name__ == "__main__":
    unittest.main()
