from __future__ import annotations

import os
from pathlib import Path


DEFAULT_ARTIFACT_ROOT = Path("/Volumes/Devarsh SSD/AI OS Data/artifacts")


def artifact_root(category: str) -> Path:
    """Return the external, configurable root for generated runtime artifacts."""
    base = Path(os.environ.get("AI_OS_ARTIFACT_ROOT") or DEFAULT_ARTIFACT_ROOT).expanduser()
    return base / category


def artifact_reference(path: Path) -> str:
    """Persist an unambiguous path because artifacts live outside the code and vault roots."""
    return str(path.expanduser().resolve())
