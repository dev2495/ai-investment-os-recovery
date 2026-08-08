from __future__ import annotations

import os
import shutil
from pathlib import Path


def _configured_or_discovered(env_key: str, command: str, known_paths: tuple[str, ...]) -> str | None:
    configured = os.environ.get(env_key, "").strip()
    if configured and Path(configured).is_file():
        return configured
    discovered = shutil.which(command)
    if discovered:
        return discovered
    return next((path for path in known_paths if Path(path).is_file()), None)


def psql_binary() -> str | None:
    return _configured_or_discovered(
        "AI_OS_PSQL_BIN",
        "psql",
        (
            "/opt/homebrew/bin/psql",
            "/usr/local/bin/psql",
            "/opt/homebrew/opt/postgresql@17/bin/psql",
            "/opt/homebrew/opt/postgresql@16/bin/psql",
            "/opt/homebrew/opt/postgresql@15/bin/psql",
        ),
    )


def docker_binary() -> str:
    return _configured_or_discovered(
        "AI_OS_DOCKER_BIN",
        "docker",
        (
            "/opt/homebrew/bin/docker",
            "/usr/local/bin/docker",
            str(Path.home() / ".docker/bin/docker"),
            "/Applications/Docker.app/Contents/Resources/bin/docker",
        ),
    ) or "docker"
