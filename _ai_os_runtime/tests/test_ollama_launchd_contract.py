from __future__ import annotations

import unittest
from pathlib import Path


class OllamaLaunchdContractTest(unittest.TestCase):
    def test_wrapper_preserves_launchd_model_path(self) -> None:
        runtime_root = Path(__file__).resolve().parents[1]
        wrapper = (
            runtime_root / "launchd" / "aios-ollama-service.sh"
        ).read_text(encoding="utf-8")

        self.assertIn(
            'export OLLAMA_MODELS="${AI_OS_OLLAMA_MODELS:-${OLLAMA_MODELS:-/Volumes/Devarsh SSD/AI OS Data/ollama/models}}"',
            wrapper,
        )
        self.assertNotIn(
            'export OLLAMA_MODELS="${AI_OS_OLLAMA_MODELS:-/Volumes/Devarsh SSD/AI OS Data/ollama/models}"',
            wrapper,
        )


if __name__ == "__main__":
    unittest.main()
