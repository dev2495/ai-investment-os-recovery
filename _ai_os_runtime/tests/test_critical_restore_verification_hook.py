from pathlib import Path
import unittest


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
RESTORE_SCRIPT = RUNTIME_ROOT / "scripts" / "verify_critical_restore.sh"
RESTORE_ROLES_SQL = RUNTIME_ROOT / "scripts" / "restore_required_roles.sql"
RESTORE_ACL_SQL = RUNTIME_ROOT / "scripts" / "restore_required_acl.sql"
MIGRATION_VERIFIER = RUNTIME_ROOT / "tests" / "verify_research_desk_migrations_rollback.sql"


class CriticalRestoreVerificationHookTests(unittest.TestCase):
    def setUp(self):
        self.script = RESTORE_SCRIPT.read_text(encoding="utf-8")

    def test_hook_is_optional_and_unreadable_input_fails_closed(self):
        self.assertIn("AI_OS_RESTORE_VERIFICATION_SQL", self.script)
        self.assertIn("restore_verification_sql=", self.script)
        self.assertIn("if [[ -n", self.script)
        self.assertIn("[[ ! -f", self.script)
        self.assertIn("|| ! -r", self.script)
        self.assertIn("must name a readable host SQL file", self.script)

    def test_sql_runs_only_inside_disposable_container_with_error_stop_and_evidence_log(self):
        command = next(
            line for line in self.script.splitlines()
            if "postgres-verification-sql.log" in line
        )
        self.assertIn("docker exec -i", command)
        self.assertIn("PG_CONTAINER", command)
        self.assertIn("-d ai_os_restore", command)
        self.assertIn("-v ON_ERROR_STOP=1", command)
        self.assertIn("-f -", command)
        self.assertIn("restore_verification_sql", command)
        self.assertIn("DRILL_ROOT", command)
        self.assertNotIn("AI_OS_POSTGRES_HOST", command)
        self.assertNotIn("AI_OS_POSTGRES_DB", command)

    def test_hook_order_is_post_restore_then_verifier_then_inventory(self):
        post_restore = self.script.index("SELECT timescaledb_post_restore(); ANALYZE;")
        hook = self.script.index("restore_verification_sql=", post_restore)
        execution = self.script.index("postgres-verification-sql.log", hook)
        inventory = self.script.index("postgres-restored-inventory.json", execution)
        self.assertLess(post_restore, hook)
        self.assertLess(hook, execution)
        self.assertLess(execution, inventory)

    def test_sanitized_non_login_role_is_bootstrapped_before_archive_restore(self):
        role_bootstrap = self.script.index("postgres-restore-roles.log")
        archive_restore = self.script.index("pg_restore -U ai_os", role_bootstrap)
        self.assertLess(role_bootstrap, archive_restore)
        self.assertIn("restore_required_roles.sql", self.script)
        self.assertNotIn("< \"${BACKUP_SET}/postgres/globals.sql\"", self.script)

        roles_sql = RESTORE_ROLES_SQL.read_text(encoding="utf-8")
        self.assertIn("CREATE ROLE ai_os_research_runtime", roles_sql)
        for attribute in (
            "NOLOGIN",
            "NOSUPERUSER",
            "NOCREATEDB",
            "NOCREATEROLE",
            "NOINHERIT",
            "NOREPLICATION",
            "NOBYPASSRLS",
        ):
            self.assertIn(attribute, roles_sql)
        self.assertNotIn("PASSWORD ", roles_sql)
        self.assertNotIn("GRANT ", roles_sql)
        self.assertNotIn("ALTER ROLE", roles_sql)

    def test_sanitized_acl_runs_after_archive_restore_and_before_verification(self):
        archive_restore = self.script.index("pg_restore -U ai_os")
        post_restore = self.script.index("SELECT timescaledb_post_restore(); ANALYZE;", archive_restore)
        acl_restore = self.script.index("postgres-restore-acl.log", post_restore)
        verifier = self.script.index("postgres-verification-sql.log", acl_restore)
        self.assertLess(archive_restore, post_restore)
        self.assertLess(post_restore, acl_restore)
        self.assertLess(acl_restore, verifier)
        self.assertIn("-v ON_ERROR_STOP=1", self.script[acl_restore - 180:acl_restore + 80])

    def test_acl_contract_is_explicit_and_preserves_research_only_boundary(self):
        acl_sql = RESTORE_ACL_SQL.read_text(encoding="utf-8")
        expected_writable_tables = (
            "knowledge.graph_nodes",
            "research.followed_sources",
            "research.followed_source_refresh_runs",
            "market.scanner_runs",
            "market.scanner_result_metric_inputs",
        )
        expected_read_only_tables = (
            "agent.approvals",
            "market.universe_memberships",
            "research.companies",
            "research.financial_ratio_results",
            "trading.symbols",
        )
        for table in expected_writable_tables + expected_read_only_tables:
            self.assertIn(table, acl_sql)
        self.assertIn("GRANT SELECT, INSERT, UPDATE ON TABLE", acl_sql)
        self.assertIn("GRANT SELECT ON TABLE", acl_sql)
        self.assertIn("GRANT USAGE, SELECT ON SEQUENCE", acl_sql)
        self.assertIn("REVOKE ALL ON SCHEMA portfolio FROM ai_os_research_runtime", acl_sql)
        self.assertIn("REVOKE ALL ON TABLE trading.order_intents FROM ai_os_research_runtime", acl_sql)
        self.assertNotIn("GRANT DELETE", acl_sql)
        self.assertNotIn("GRANT ALL", acl_sql)
        self.assertNotIn("PASSWORD ", acl_sql)

    def test_acl_contract_restores_all_27_scoped_tables(self):
        acl_sql = RESTORE_ACL_SQL.read_text(encoding="utf-8")
        verifier = MIGRATION_VERIFIER.read_text(encoding="utf-8")
        secured_block = verifier.split("WHERE (n.nspname, c.relname) IN (", 1)[1].split(
            ")\n      AND c.relrowsecurity", 1
        )[0]
        scoped_tables = []
        for schema in ("knowledge", "research", "market"):
            for line in secured_block.splitlines():
                marker = f"('{schema}','"
                if marker in line:
                    table = line.split(marker, 1)[1].split("'", 1)[0]
                    scoped_tables.append(f"{schema}.{table}")
        self.assertEqual(27, len(set(scoped_tables)))
        for table in set(scoped_tables):
            self.assertIn(table, acl_sql)

    def test_deployment_verifier_covers_migrations_244_through_249_and_rolls_back(self):
        verifier = MIGRATION_VERIFIER.read_text(encoding="utf-8")
        self.assertIn("ON_ERROR_STOP", verifier)
        for migration in range(244, 250):
            self.assertIn(str(migration), verifier)
        self.assertIn("BEGIN;", verifier)
        self.assertIn("ROLLBACK;", verifier)
        self.assertIn("verification_passed", verifier)


if __name__ == "__main__":
    unittest.main()
