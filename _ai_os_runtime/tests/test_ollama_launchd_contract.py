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

    def test_bonsai_agent_uses_stable_internal_wrapper(self) -> None:
        runtime_root = Path(__file__).resolve().parents[1]
        plist = (
            runtime_root / "launchd" / "com.devarsh.aios.charlie-local.plist"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "/Users/devarshthakkar/Library/Application Support/AIOS/bin/start-charlie-bonsai.sh",
            plist,
        )
        self.assertNotIn("AI_OS_ACTIVE_RECOVERY", plist)

    def test_qwen_agent_uses_stable_internal_wrapper(self) -> None:
        runtime_root = Path(__file__).resolve().parents[1]
        plist = (
            runtime_root / "launchd" / "com.devarsh.aios.charlie-mlx.plist"
        ).read_text(encoding="utf-8")
        installer = (
            runtime_root / "scripts" / "install_macbook_mlx_workhorse.sh"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "/Users/devarshthakkar/Library/Application Support/AIOS/bin/start-charlie-qwen35.sh",
            plist,
        )
        self.assertNotIn("AI_OS_ACTIVE_RECOVERY", plist)
        self.assertIn("launchctl bootstrap", installer)
        self.assertIn("start_mlx_workhorse.sh", installer)
        self.assertIn("11436/v1/models", installer)


if __name__ == "__main__":
    unittest.main()
