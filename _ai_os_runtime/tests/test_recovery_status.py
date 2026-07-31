import os
import pathlib
import tempfile
import unittest
from unittest import mock

from _ai_os_runtime.api import ai_os_api_server


class RecoveryStatusTests(unittest.TestCase):
    def test_offsite_backup_root_is_used_when_legacy_root_is_unset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            backup_root = pathlib.Path(directory) / "critical"
            current = backup_root / "current"
            (current / "postgres").mkdir(parents=True)
            (current / "integrity").mkdir()
            (current / "vault").mkdir()
            (current / "postgres" / "ai_os.dump").write_bytes(b"pgdump")
            (current / "integrity" / "checksums.sha256").write_text(
                "checksum  postgres/ai_os.dump\n",
                encoding="utf-8",
            )
            (current / "vault" / "note.md").write_text("# recovered\n", encoding="utf-8")
            (current / "manifest.txt").write_text(
                "format_version=2\n"
                "created_at=2026-07-31T00:00:00Z\n"
                "source_commit=abc1234\n"
                "postgres_archive=postgres/ai_os.dump\n"
                "checksums=integrity/checksums.sha256\n"
                "vault_root=vault\n"
                "qdrant_rebuildable=true\n",
                encoding="utf-8",
            )

            with mock.patch.dict(
                os.environ,
                {
                    "AI_OS_CRITICAL_BACKUP_ROOT": "",
                    "AI_OS_OFFSITE_BACKUP_ROOT": str(backup_root),
                    "AI_OS_RESTORE_DRILL_ROOT": str(pathlib.Path(directory) / "drills"),
                },
                clear=False,
            ):
                status = ai_os_api_server.build_recovery_status()

        self.assertEqual(status["backup_root"], str(backup_root))
        self.assertEqual(status["repo_commit"], "abc1234")
        self.assertTrue(status["postgres_dump_exists"])
        self.assertTrue(status["checksums_exist"])
        self.assertTrue(status["vault_copy_exists"])
        self.assertEqual(status["vault_file_count"], 1)
        self.assertTrue(status["qdrant_rebuildable"])

    def test_imac_backup_manifest_is_self_describing(self) -> None:
        script = (
            pathlib.Path(__file__).parents[1]
            / "deploy"
            / "imac-backend"
            / "bin"
            / "aios-imac"
        ).read_text(encoding="utf-8")

        for field in (
            "format_version=2",
            "backup_profile=imac_compact_rebuildable",
            "repo_commit=%s",
            "postgres_archive=postgres/ai_os.dump",
            "postgres_inventory=postgres/inventory.json",
            "postgres_image=%s",
            "timescaledb_extension_version=%s",
            "timescaledb_catalog_version=%s",
            "checksums=integrity/checksums.sha256",
            "vault_root=vault",
            "qdrant_rebuildable=true",
        ):
            self.assertIn(field, script)


    def test_compact_restore_drill_is_version_aligned_and_image_pinned(self) -> None:
        runtime_root = pathlib.Path(__file__).parents[1]
        restore_script = (
            runtime_root / "scripts" / "verify_imac_compact_restore.sh"
        ).read_text(encoding="utf-8")
        env_example = (
            runtime_root / "deploy" / "imac-backend" / "imac.env.example"
        ).read_text(encoding="utf-8")
        compose = (
            runtime_root / "deploy" / "imac-backend" / "docker-compose.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("CREATE EXTENSION timescaledb VERSION", restore_script)
        self.assertIn("timescaledb_pre_restore()", restore_script)
        self.assertIn("ALTER EXTENSION timescaledb UPDATE TO", restore_script)
        self.assertIn("timescaledb_post_restore()", restore_script)
        self.assertIn("postgres-inventory.diff", restore_script)
        self.assertNotIn("timescale/timescaledb:latest-pg16", env_example)
        self.assertNotIn("redis:7-alpine", env_example)
        self.assertIn("timescale/timescaledb@sha256:", compose)
        self.assertIn("qdrant/qdrant@sha256:", compose)
        self.assertIn("redis@sha256:", compose)


if __name__ == "__main__":
    unittest.main()
