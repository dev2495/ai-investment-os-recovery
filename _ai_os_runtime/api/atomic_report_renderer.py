"""Bounded, atomic local-Chrome report rendering shared by report builders."""
from __future__ import annotations

import hashlib
import os
import re
import signal
import subprocess
import tempfile
import time
import urllib.parse
import zlib
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4


DEFAULT_BROWSERS = (
    Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
)


def find_chrome_browser(candidates: Iterable[Path] = DEFAULT_BROWSERS) -> Path | None:
    return next((Path(path) for path in candidates if Path(path).is_file()), None)


def _valid_pdf(path: Path, minimum_size: int) -> bool:
    if not path.is_file() or path.stat().st_size < minimum_size:
        return False
    with path.open("rb") as handle:
        return handle.read(5) == b"%PDF-"


def _pdf_privacy_issue(path: Path) -> str | None:
    """Reject browser chrome or links that expose local report locations.

    Chrome may encode printed headers in a Flate-compressed content stream or
    as UTF-16-ish text. Inspect the raw file plus bounded decompressed streams
    before the atomic publish step so a prior good PDF is never replaced by an
    artifact that leaks an SSD path.
    """
    try:
        data = path.read_bytes()
    except OSError as exc:
        return f"PDF privacy validation could not read the artifact: {type(exc).__name__}: {exc}"
    payloads = [data]
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
        compressed = match.group(1)
        if len(compressed) > 16 * 1024 * 1024:
            continue
        try:
            decompressor = zlib.decompressobj()
            payloads.append(decompressor.decompress(compressed, 16 * 1024 * 1024))
        except zlib.error:
            continue
    markers = (
        (b"file://", "local file URI"),
        (b"/volumes/", "private volume path"),
        (b"file%3a%2f%2f", "encoded local file URI"),
        (b"%2fvolumes%2f", "encoded private volume path"),
    )
    for payload in payloads:
        normalized = payload.lower().replace(b"\x00", b"")
        try:
            decoded = urllib.parse.unquote_to_bytes(normalized.decode("latin-1", errors="ignore"))
        except (UnicodeError, ValueError):
            decoded = normalized
        for candidate in (normalized, decoded.lower()):
            for marker, label in markers:
                if marker in candidate:
                    return f"PDF privacy validation failed: {label} detected"
    return None


def render_html_pdf(
    browser: Path,
    html_path: Path,
    pdf_path: Path,
    *,
    profile_root: Path | None = None,
    timeout_seconds: float = 60,
    stable_checks: int = 4,
    poll_interval: float = 0.25,
    minimum_size: int = 1024,
) -> dict[str, Any]:
    """Render into a unique sibling file and atomically publish once valid."""
    started = time.monotonic()
    browser = Path(browser)
    html_path = Path(html_path)
    pdf_path = Path(pdf_path)
    if not browser.is_file() or not os.access(browser, os.X_OK):
        return {"ok": False, "error": "local Chrome renderer is unavailable"}
    if not html_path.is_file():
        return {"ok": False, "error": "HTML report is unavailable"}
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    profile_parent = Path(profile_root or pdf_path.parent)
    profile_parent.mkdir(parents=True, exist_ok=True)
    render_path = pdf_path.with_name(f".{pdf_path.name}.rendering-{uuid4().hex}.pdf")
    process: subprocess.Popen | None = None
    profile_directory: tempfile.TemporaryDirectory | None = None
    error: str | None = None
    try:
        profile_directory = tempfile.TemporaryDirectory(prefix=".chrome-report-", dir=str(profile_parent))
        command = [
            str(browser), "--headless=new", "--no-sandbox", "--disable-gpu",
            "--disable-extensions", "--disable-background-networking", "--no-first-run",
            "--disable-dev-shm-usage", "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=5000", "--no-pdf-header-footer", "--print-to-pdf-no-header",
            f"--user-data-dir={profile_directory.name}", f"--print-to-pdf={render_path}", html_path.as_uri(),
        ]
        process = subprocess.Popen(
            command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        deadline = time.monotonic() + max(0.1, float(timeout_seconds))
        previous_size = -1
        stable = 0
        while time.monotonic() < deadline:
            if render_path.is_file():
                size = render_path.stat().st_size
                stable = stable + 1 if size >= minimum_size and size == previous_size else 0
                previous_size = size
                if stable >= max(1, int(stable_checks)) and _valid_pdf(render_path, minimum_size):
                    break
            if process.poll() is not None and not render_path.exists():
                error = f"Chrome exited {process.returncode} before producing a PDF"
                break
            time.sleep(max(0.01, float(poll_interval)))
        else:
            error = f"PDF render did not produce a stable file within {timeout_seconds:g} seconds"
    except OSError as exc:
        error = f"PDF renderer could not start: {type(exc).__name__}: {exc}"
    finally:
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    error = error or "Chrome did not terminate after its bounded render attempt"
        if profile_directory is not None:
            try:
                profile_directory.cleanup()
            except OSError as exc:
                error = error or f"Chrome profile cleanup failed: {type(exc).__name__}: {exc}"
    if not error and _valid_pdf(render_path, minimum_size):
        error = _pdf_privacy_issue(render_path)
    if not error and _valid_pdf(render_path, minimum_size):
        os.replace(render_path, pdf_path)
        digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        return {
            "ok": True, "pdf_path": str(pdf_path), "pdf_hash": digest,
            "size_bytes": pdf_path.stat().st_size,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
    render_path.unlink(missing_ok=True)
    return {
        "ok": False, "error": error or "PDF renderer did not create a valid artifact",
        "duration_ms": int((time.monotonic() - started) * 1000),
    }
