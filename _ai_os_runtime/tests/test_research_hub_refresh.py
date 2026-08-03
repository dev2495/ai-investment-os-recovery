from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


RUNTIME_ROOT = Path(__file__).resolve().parents[1]


def load_inventory_module():
    path = RUNTIME_ROOT / "scripts" / "inventory_ai_research_outputs.py"
    spec = importlib.util.spec_from_file_location("inventory_ai_research_outputs", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ResearchHubRefreshContractTest(unittest.TestCase):
    def test_research_source_roots_include_shared_inboxes(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            vault = root / "vault"
            data = root / "data"
            extra = root / "extra"
            with mock.patch.dict(
                os.environ,
                {
                    "AI_OS_VAULT_ROOT": str(vault),
                    "AI_OS_DATA_ROOT": str(data),
                    "AI_OS_RESEARCH_EXTRA_ROOTS": str(extra),
                },
            ):
                module = load_inventory_module()
                roots = dict(module.configured_source_roots())

        self.assertEqual(roots["vault_agent_outputs"], vault / "ai memory" / "00 AI OS" / "Agent Outputs")
        self.assertEqual(roots["vault_research_outputs"], vault / "ai memory" / "01 Research" / "AI Outputs")
        self.assertEqual(roots["shared_research_inbox"], data / "research-inbox")
        self.assertEqual(roots["configured_root_1"], extra)

    def test_research_hub_refresh_is_scheduled_and_actionable(self) -> None:
        daemon = (RUNTIME_ROOT / "scripts" / "run_agent_message_daemon.py").read_text()
        api = (RUNTIME_ROOT / "api" / "ai_os_api_server.py").read_text()
        ui = (
            RUNTIME_ROOT
            / "ai-office-ui"
            / "src"
            / "destinations"
            / "firm"
            / "FirmAgentViews.tsx"
        ).read_text()

        self.assertIn("run_research_hub_refresh", daemon)
        self.assertIn('"research_hub_refresh": research_hub_refresh_enabled', daemon)
        self.assertIn('"/api/research/hub/refresh"', api)
        self.assertIn('useAction<{ actor: string }>("/api/research/hub/refresh"', ui)
        self.assertIn("await refreshHub.mutateAsync", ui)


if __name__ == "__main__":
    unittest.main()
