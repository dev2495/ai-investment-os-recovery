import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SETUP_SCRIPT = ROOT / "scripts" / "setup_imac_nanbeige42_assistant.sh"
MIGRATION = ROOT / "postgres" / "init" / "175_nanbeige42_isolated_local_openai.sql"
SUPERVISOR = ROOT / "deploy" / "imac-backend" / "bin" / "supervisor.sh"


class NanbeigeSetupScriptTests(unittest.TestCase):
    def test_setup_pins_official_model_and_runtime_revisions(self):
        script = SETUP_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('MODEL_REVISION="f56ec5a9650268aa098496734743c25ea778bd2d"', script)
        self.assertIn('RUNTIME_REVISION="c6640a1c0cf7b38df342b67021a3900b04d092e7"', script)
        self.assertIn("--provider local_openai", script)
        self.assertIn("--promote", script)
        self.assertIn('shasum -a 256 "${QUANT_GGUF}"', script)
        self.assertNotIn("ollama pull", script)
        self.assertIn('EXPLICIT_REPO_ROOT="${AI_OS_REPO_ROOT:-}"', script)
        self.assertIn(
            'REPO_ROOT="${EXPLICIT_REPO_ROOT:-${AI_OS_REPO_ROOT:-${HOME}/AI_OS_NODE/current}}"',
            script,
        )
        self.assertIn(
            'RUNTIME_ROOT="${EXPLICIT_RUNTIME_ROOT:-${AI_OS_RUNTIME_ROOT:-${REPO_ROOT}/_ai_os_runtime}}"',
            script,
        )

    def test_migration_registers_isolated_loopback_endpoint(self):
        migration = MIGRATION.read_text(encoding="utf-8")

        self.assertIn("'local_openai'", migration)
        self.assertIn("'http://127.0.0.1:11436/v1'", migration)
        self.assertIn("'nanbeige42_3b_q4_local_openai_imac'", migration)
        self.assertIn("Stock Ollama does not ship", migration)
        self.assertIn('"live_execution_allowed":false', migration)

    def test_supervisor_only_starts_installed_artifacts(self):
        supervisor = SUPERVISOR.read_text(encoding="utf-8")

        self.assertIn('AI_OS_ENABLE_NANBEIGE42:-1', supervisor)
        self.assertIn('[[ -x "${NANBEIGE_SERVER}" && -f "${NANBEIGE_MODEL}" ]]', supervisor)
        self.assertIn('/v1/models" Nanbeige4.2 180', supervisor)
        self.assertIn('Nanbeige4.2 heartbeat failed', supervisor)


if __name__ == "__main__":
    unittest.main()
