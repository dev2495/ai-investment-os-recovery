#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ZIP_PATH = Path("/Volumes/Devarsh SSD/ps 2 cursor.zip")
DEFAULT_DEST = RUNTIME_ROOT / "imports" / "quarantine" / "p2cursor_selected"
DEFAULT_MANIFEST = RUNTIME_ROOT / "imports" / "p2cursor_extract_manifest.json"

DATA_SUFFIXES = {
    ".csv",
    ".db",
    ".feather",
    ".parquet",
    ".sqlite",
    ".sqlite3",
    ".xls",
    ".xlsx",
    ".jsonl",
}

CONDITIONAL_JSON_SUFFIXES = {".json"}

DATA_KEYWORDS = {
    "account",
    "backtest",
    "client",
    "data",
    "equity",
    "export",
    "folio",
    "holding",
    "history",
    "import",
    "journal",
    "kite",
    "ledger",
    "order",
    "pnl",
    "portfolio",
    "position",
    "price",
    "report",
    "signal",
    "stock",
    "strategy",
    "trade",
    "transaction",
    "watchlist",
    "zerodha",
}

SKIP_SEGMENTS = {
    "__macosx",
    ".cache",
    ".git",
    ".next",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "build",
    "cache",
    "coverage",
    "dist",
    "node_modules",
    "site-packages",
    "vendor",
    "venv",
}

SENSITIVE_PATTERNS = {
    ".env",
    "access_key",
    "apikey",
    "api_key",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
}

SKIP_FILENAMES = {
    "package-lock.json",
    "package.json",
    "pnpm-lock.yaml",
    "tsconfig.json",
    "vite.config.json",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def lower_parts(name: str) -> list[str]:
    return [part.lower() for part in PurePosixPath(name).parts if part and part != "/"]


def is_symlink(info: zipfile.ZipInfo) -> bool:
    file_type = (info.external_attr >> 16) & 0o170000
    return file_type == 0o120000


def has_sensitive_path(name: str) -> bool:
    lower = name.lower()
    return any(pattern in lower for pattern in SENSITIVE_PATTERNS)


def should_skip_path(info: zipfile.ZipInfo) -> tuple[bool, str | None]:
    if info.is_dir():
        return True, "directory"
    if is_symlink(info):
        return True, "symlink"
    if info.file_size <= 0:
        return True, "empty"

    parts = lower_parts(info.filename)
    if not parts:
        return True, "empty_path"
    if any(part in {"..", "."} for part in parts):
        return True, "unsafe_path"
    if any(part in SKIP_SEGMENTS for part in parts):
        return True, "generated_or_dependency_path"
    if parts[-1].startswith("._"):
        return True, "macos_resource_fork"
    if parts[-1] in SKIP_FILENAMES:
        return True, "app_config_json"
    if has_sensitive_path(info.filename):
        return True, "credential_like_path"
    return False, None


def is_candidate(info: zipfile.ZipInfo) -> tuple[bool, str | None]:
    skipped, reason = should_skip_path(info)
    if skipped:
        return False, reason

    suffix = PurePosixPath(info.filename).suffix.lower()
    if suffix in DATA_SUFFIXES:
        return True, None
    if suffix in CONDITIONAL_JSON_SUFFIXES:
        lower = info.filename.lower()
        if any(keyword in lower for keyword in DATA_KEYWORDS):
            return True, None
        return False, "json_without_data_keyword"
    return False, "not_data_suffix"


def safe_relative_path(name: str) -> Path:
    parts = [part for part in PurePosixPath(name).parts if part not in {"", "/", ".", ".."}]
    return Path(*parts)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_candidates(
    zip_path: Path,
    destination: Path,
    manifest_path: Path,
    max_file_size_mb: int,
    max_total_size_mb: int,
) -> dict:
    if not zip_path.exists():
        raise FileNotFoundError(f"p2cursor archive not found: {zip_path}")

    max_file_size = max_file_size_mb * 1024 * 1024
    max_total_size = max_total_size_mb * 1024 * 1024

    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    skipped: Counter[str] = Counter()
    extracted: list[dict] = []
    total_candidate_bytes = 0
    extracted_bytes = 0

    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            candidate, reason = is_candidate(info)
            if not candidate:
                skipped[reason or "not_candidate"] += 1
                continue

            total_candidate_bytes += info.file_size
            if info.file_size > max_file_size:
                skipped["over_file_size_limit"] += 1
                continue
            if extracted_bytes + info.file_size > max_total_size:
                skipped["over_total_size_limit"] += 1
                continue

            relative = safe_relative_path(info.filename)
            output_path = destination / relative
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with archive.open(info, "r") as source, output_path.open("wb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)

            digest = sha256_file(output_path)
            extracted_bytes += info.file_size
            extracted.append(
                {
                    "original_path": info.filename,
                    "extracted_path": str(output_path),
                    "relative_extracted_path": str(output_path.relative_to(RUNTIME_ROOT)),
                    "suffix": output_path.suffix.lower(),
                    "size_bytes": info.file_size,
                    "sha256": digest,
                    "modified_at_zip": datetime(*info.date_time, tzinfo=timezone.utc).isoformat(),
                }
            )

    suffix_counts = Counter(item["suffix"] or "(none)" for item in extracted)
    manifest = {
        "generated_at": utc_now(),
        "zip_path": str(zip_path),
        "destination": str(destination),
        "runtime_root": str(RUNTIME_ROOT),
        "policy": {
            "mode": "selective_quarantine_extraction",
            "max_file_size_mb": max_file_size_mb,
            "max_total_size_mb": max_total_size_mb,
            "extracted_suffixes": sorted(DATA_SUFFIXES | CONDITIONAL_JSON_SUFFIXES),
            "skip_segments": sorted(SKIP_SEGMENTS),
            "sensitive_path_patterns_skipped": sorted(SENSITIVE_PATTERNS),
        },
        "stats": {
            "extracted_files": len(extracted),
            "extracted_bytes": extracted_bytes,
            "total_candidate_bytes_before_limits": total_candidate_bytes,
            "suffix_counts": dict(suffix_counts.most_common()),
            "skipped_reasons": dict(skipped.most_common()),
        },
        "files": extracted,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely extract p2cursor data candidates into quarantine.")
    parser.add_argument("--zip-path", type=Path, default=DEFAULT_ZIP_PATH)
    parser.add_argument("--destination", type=Path, default=DEFAULT_DEST)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--max-file-size-mb", type=int, default=250)
    parser.add_argument("--max-total-size-mb", type=int, default=2048)
    args = parser.parse_args()

    manifest = extract_candidates(
        zip_path=args.zip_path,
        destination=args.destination,
        manifest_path=args.manifest,
        max_file_size_mb=args.max_file_size_mb,
        max_total_size_mb=args.max_total_size_mb,
    )
    print(
        json.dumps(
            {
                "manifest_path": str(args.manifest),
                "destination": str(args.destination),
                "extracted_files": manifest["stats"]["extracted_files"],
                "extracted_bytes": manifest["stats"]["extracted_bytes"],
                "suffix_counts": manifest["stats"]["suffix_counts"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
