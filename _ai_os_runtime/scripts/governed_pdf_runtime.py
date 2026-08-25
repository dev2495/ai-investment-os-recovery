"""Resolve the only production Python runtime permitted to parse PDFs.

PDF parsing is intentionally fail-closed.  A LaunchAgent or API process must not
silently fall back to its own interpreter because that makes dependency and data
residency behaviour depend on how the process happened to be started.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Mapping


GOVERNED_RUNTIME_ROOT = Path("/Volumes/Devarsh SSD/AI OS Data/runtime/pdf-extraction")
DEFAULT_SSD_PDF_PYTHON = GOVERNED_RUNTIME_ROOT / "bin" / "python"


def _is_within(path: Path, root: Path) -> bool:
    """Use lexical containment so an interpreter symlink may target system Python."""
    try:
        path.absolute().relative_to(root.absolute())
        return True
    except ValueError:
        return False


def governed_pdf_python(
    *,
    environment: Mapping[str, str] | None = None,
    verify_import: bool = False,
    import_timeout_seconds: float = 15,
) -> str:
    """Return the governed SSD interpreter or raise without a fallback.

    ``AI_OS_PDF_PYTHON`` remains configurable for deployment, but production
    paths must stay inside the governed external-SSD runtime directory.
    Constants are deliberately module-level so tests can replace them without
    weakening the production containment rule.
    """
    env = environment if environment is not None else os.environ
    configured = str(env.get("AI_OS_PDF_PYTHON") or DEFAULT_SSD_PDF_PYTHON).strip()
    candidate = Path(configured)
    if not candidate.is_absolute() or not _is_within(candidate, GOVERNED_RUNTIME_ROOT):
        raise RuntimeError(
            "governed PDF runtime must be an absolute path inside the external-SSD PDF runtime"
        )
    if not candidate.is_file() or not os.access(candidate, os.X_OK):
        raise RuntimeError(
            "governed external-SSD PDF runtime is unavailable; no internal-disk fallback"
        )
    if verify_import:
        try:
            completed = subprocess.run(
                [str(candidate), "-c", "import pypdf"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=max(1.0, float(import_timeout_seconds)),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(
                "governed external-SSD PDF runtime failed its bounded dependency preflight"
            ) from exc
        if completed.returncode != 0:
            raise RuntimeError(
                "governed external-SSD PDF runtime does not provide pypdf; no fallback"
            )
    return str(candidate)
