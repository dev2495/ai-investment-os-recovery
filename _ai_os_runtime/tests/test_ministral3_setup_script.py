import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SETUP_SCRIPT = ROOT / "scripts" / "setup_imac_ministral3_assistant.sh"
MIGRATION = ROOT / "postgres" / "init" / "174_ministral3_3b_local_assistant.sql"


class MinistralSetupScriptTests(unittest.TestCase):
    def test_probe_failures_are_persisted_before_exit(self):
        script = SETUP_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('runtime_version="$("${OLLAMA_BIN}" --version', script)
        self.assertIn('MODEL="ministral-3:3b-instruct-2512-q4_K_M"', script)
        self.assertIn('-v probe_message="${message}"', script)
        self.assertIn('-v runtime_version="${runtime_version}"', script)
        self.assertIn(
            'record_probe_state "blocked" "model_unavailable" "manifest_pull"',
            script,
        )
        self.assertIn(
            'record_probe_state "disabled" "eval_failed" "conversation_v1"',
            script,
        )

    def test_deploy_replay_preserves_confirmed_runtime_incompatibility(self):
        migration = MIGRATION.read_text(encoding="utf-8")

        self.assertIn(
            "WHEN agent.model_endpoints.health_status='model_unavailable'",
            migration,
        )
        self.assertIn(
            "config=agent.model_endpoints.config || EXCLUDED.config",
            migration,
        )


if __name__ == "__main__":
    unittest.main()
