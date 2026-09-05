"""Fast safety-contract tests for the manual Phase 2 stress harness."""
from __future__ import annotations

import pytest

from _ai_os_runtime.tests.phase2_runtime_stress import StressRefusal, validate_admin_dsn


@pytest.mark.parametrize(
    "dsn",
    [
        "host=127.0.0.1 user=phase2_test dbname=postgres",
        "host=/private/tmp/aios-phase2-pg.guard user=postgres dbname=postgres",
        "host=/private/tmp/aios-phase2-pg.guard user=phase2_test dbname=production",
        "host=/tmp/aios-phase2-pg.guard user=phase2_test dbname=postgres",
        "host=/private/tmp/aios-phase2-pg.guard user=phase2_test dbname=postgres password=unsafe",
        "",
    ],
)
def test_refuses_every_non_synthetic_target(dsn):
    pytest.importorskip("psycopg")
    with pytest.raises(StressRefusal, match="synthetic|non-disposable"):
        validate_admin_dsn(dsn)


def test_accepts_only_private_tmp_test_conninfo_shape():
    pytest.importorskip("psycopg")
    settings = validate_admin_dsn(
        "host=/private/tmp/aios-phase2-pg.guard port=55439 user=phase2_test dbname=postgres"
    )
    assert settings["host"] == "/private/tmp/aios-phase2-pg.guard"
    assert settings["user"] == "phase2_test"
    assert settings["dbname"] == "postgres"
