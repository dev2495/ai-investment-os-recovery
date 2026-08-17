from __future__ import annotations

import importlib.util
import os
import sys
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


def load_indexer_module():
    name = "index_qdrant_documents_test"
    path = RUNTIME_ROOT / "scripts" / "index_qdrant_documents.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
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

    def test_incremental_vector_refresh_skips_unchanged_chunks(self) -> None:
        module = load_indexer_module()
        collection = "research_reports_qwen3_embedding_0_6b"
        document = module.SourceDocument(
            collection_name=collection,
            source_table="core.raw_artifacts",
            source_id="7",
            title="Research memo",
            text="alpha research evidence",
            metadata={"artifact_family": "research_report"},
        )
        chunk = module.chunk_text(document.text)[0]
        text_hash = module.hashlib.sha256(chunk.encode("utf-8")).hexdigest()
        point_id = str(
            module.uuid.uuid5(
                module.uuid.NAMESPACE_URL,
                f"{collection}:core.raw_artifacts:7:0:{text_hash}",
            )
        )
        existing = [{
            "qdrant_point_id": point_id,
            "source_table": "core.raw_artifacts",
            "source_id": "7",
            "chunk_index": 0,
            "text_hash": text_hash,
        }]

        with (
            mock.patch.object(module, "ensure_collections") as ensure_collections,
            mock.patch.object(module, "source_research_reports", return_value=[document]),
            mock.patch.object(module, "existing_research_registry", return_value=existing),
            mock.patch.object(module, "Embedder") as embedder,
            mock.patch.object(module, "qdrant_request") as qdrant_request,
            mock.patch.object(module, "delete_qdrant_points") as delete_points,
            mock.patch.object(module, "write_incremental_research_registry") as write_registry,
        ):
            summary = module.index_research_reports_incremental()

        ensure_collections.assert_called_once_with(recreate=False)
        embedder.assert_not_called()
        qdrant_request.assert_not_called()
        delete_points.assert_called_once_with(collection, [])
        write_registry.assert_called_once_with([], [])
        self.assertEqual(summary["unchanged_points"], 1)
        self.assertEqual(summary["points_indexed"], 0)
        self.assertEqual(summary["points_deleted"], 0)

    def test_research_hub_refresh_is_scheduled_and_actionable(self) -> None:
        daemon = (RUNTIME_ROOT / "scripts" / "run_agent_message_daemon.py").read_text()
        indexer = (RUNTIME_ROOT / "scripts" / "index_qdrant_documents.py").read_text()
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
        self.assertIn('"--incremental-research"', daemon)
        self.assertIn("index_research_reports_incremental", indexer)
        self.assertIn("ensure_collections(recreate=False)", indexer)
        self.assertIn('"/api/research/hub/refresh"', api)
        self.assertIn('useAction<{ actor: string }>("/api/research/hub/refresh"', ui)
        self.assertIn("await refreshHub.mutateAsync", ui)


if __name__ == "__main__":
    unittest.main()
