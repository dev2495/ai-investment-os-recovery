import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import unittest


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
RESTORE_ROLES_SQL = RUNTIME_ROOT / "scripts" / "restore_required_roles.sql"


def _binary(name: str) -> str | None:
    return shutil.which(name)


@unittest.skipUnless(
    os.environ.get("AI_OS_RUN_POSTGRES_RESTORE_INTEGRATION") == "1"
    and all(_binary(name) for name in ("initdb", "pg_ctl", "psql", "createdb", "dropdb", "pg_dump", "pg_restore")),
    "set AI_OS_RUN_POSTGRES_RESTORE_INTEGRATION=1 on a host that permits disposable PostgreSQL",
)
class RestoreRequiredRolesIntegrationTests(unittest.TestCase):
    def test_policy_restore_fails_without_role_then_succeeds_after_sanitized_bootstrap(self):
        root = Path(tempfile.mkdtemp(prefix="aios-restore-role-", dir="/private/tmp"))
        data = root / "data"
        socket_dir = root / "socket"
        archive = root / "policy.dump"
        socket_dir.mkdir()
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]

        admin = "restore_test_admin"
        env = os.environ.copy()
        env.update({"PGHOST": str(socket_dir), "PGPORT": str(port), "PGUSER": admin})
        started = False

        def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                args,
                check=check,
                env=env,
                text=True,
                capture_output=True,
            )

        try:
            run(_binary("initdb"), "-D", str(data), "-A", "trust", "--no-locale", "-U", admin)
            run(
                _binary("pg_ctl"),
                "-D",
                str(data),
                "-o",
                f"-F -k {socket_dir} -h '' -p {port}",
                "-w",
                "start",
            )
            started = True

            run(_binary("createdb"), "source_policy")
            source_sql = """
                CREATE ROLE ai_os_research_runtime NOLOGIN;
                CREATE TABLE public.scoped_rows (id bigint PRIMARY KEY, scope_key text NOT NULL);
                ALTER TABLE public.scoped_rows ENABLE ROW LEVEL SECURITY;
                CREATE POLICY runtime_scope_select ON public.scoped_rows
                    FOR SELECT TO ai_os_research_runtime USING (scope_key = 'public:test');
            """
            run(_binary("psql"), "-d", "source_policy", "-v", "ON_ERROR_STOP=1", "-c", source_sql)
            run(_binary("pg_dump"), "-d", "source_policy", "-Fc", "-f", str(archive))
            run(_binary("dropdb"), "source_policy")
            run(_binary("psql"), "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", "DROP ROLE ai_os_research_runtime")

            run(_binary("createdb"), "restore_without_role")
            failed_restore = run(
                _binary("pg_restore"),
                "-d",
                "restore_without_role",
                "--exit-on-error",
                "--no-owner",
                "--no-privileges",
                str(archive),
                check=False,
            )
            self.assertNotEqual(0, failed_restore.returncode)
            self.assertIn('role "ai_os_research_runtime" does not exist', failed_restore.stderr)
            run(_binary("dropdb"), "restore_without_role")

            run(_binary("createdb"), "restore_with_role")
            run(
                _binary("psql"),
                "-d",
                "restore_with_role",
                "-v",
                "ON_ERROR_STOP=1",
                "-f",
                str(RESTORE_ROLES_SQL),
            )
            run(
                _binary("pg_restore"),
                "-d",
                "restore_with_role",
                "--exit-on-error",
                "--no-owner",
                "--no-privileges",
                str(archive),
            )

            policy = run(
                _binary("psql"),
                "-d",
                "restore_with_role",
                "-tAc",
                "SELECT polname FROM pg_policy WHERE 'ai_os_research_runtime'::regrole::oid = ANY(polroles)",
            ).stdout.strip()
            self.assertEqual("runtime_scope_select", policy)
            flags = run(
                _binary("psql"),
                "-d",
                "restore_with_role",
                "-tAc",
                "SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolinherit, rolreplication, rolbypassrls FROM pg_roles WHERE rolname = 'ai_os_research_runtime'",
            ).stdout.strip()
            self.assertEqual("f|f|f|f|f|f|f", flags)
        finally:
            if started:
                subprocess.run(
                    [_binary("pg_ctl"), "-D", str(data), "-m", "fast", "-w", "stop"],
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
