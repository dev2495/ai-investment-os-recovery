import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SETUP_SCRIPTS = (
    ROOT / "scripts" / "setup_imac_basic_assistant.sh",
    ROOT / "scripts" / "setup_imac_phi_assistant.sh",
    ROOT / "scripts" / "setup_imac_qwen3_instruct_assistant.sh",
)
MIGRATIONS = (
    ROOT / "postgres" / "init" / "160_granite4_imac_basic_assistant.sql",
    ROOT / "postgres" / "init" / "161_phi4_mini_imac_basic_assistant.sql",
    ROOT / "postgres" / "init" / "163_qwen3_4b_instruct_imac_assistant.sql",
)


class LocalAssistantFailurePersistenceTests(unittest.TestCase):
    def test_setup_scripts_persist_eval_failure_before_exit(self) -> None:
        for script_path in SETUP_SCRIPTS:
            with self.subTest(script=script_path.name):
                script = script_path.read_text(encoding="utf-8")
                self.assertIn("if ! python3", script)
                self.assertIn("health_status='eval_failed'", script)
                self.assertIn("conversation_v1 did not pass", script)

    def test_deploy_replay_preserves_rejected_evaluation_evidence(self) -> None:
        for migration_path in MIGRATIONS:
            with self.subTest(migration=migration_path.name):
                migration = migration_path.read_text(encoding="utf-8")
                self.assertIn("last_eval_score IS NOT NULL", migration)
                self.assertIn("THEN 'rejected'", migration)
                self.assertIn("registry.last_eval_score < 0.8", migration)
                self.assertIn("health_status='eval_failed'", migration)


if __name__ == "__main__":
    unittest.main()
