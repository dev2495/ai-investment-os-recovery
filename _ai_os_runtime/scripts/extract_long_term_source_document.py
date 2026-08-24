#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

try:
    from runtime_storage import artifact_reference, artifact_root
except ModuleNotFoundError:  # Imported as an _ai_os_runtime package module.
    from _ai_os_runtime.scripts.runtime_storage import artifact_reference, artifact_root
try:
    from governed_pdf_runtime import governed_pdf_python
except ModuleNotFoundError:  # Imported as an _ai_os_runtime package module.
    from _ai_os_runtime.scripts.governed_pdf_runtime import governed_pdf_python


RUNTIME_ROOT = Path(os.environ.get("AI_OS_RUNTIME_ROOT") or Path(__file__).absolute().parents[1])
VAULT_ROOT = Path(os.environ.get("AI_OS_VAULT_ROOT") or RUNTIME_ROOT.parent)
ARTIFACT_ROOT = artifact_root("source_documents") / "long_term"
USER_AGENT = "AI-OS-Research/0.1 (source document extraction; contact local user)"


def ensure_pdf_runtime() -> None:
    try:
        import pypdf  # noqa: F401
        return
    except Exception:
        pass
    if os.environ.get("AI_OS_PDF_RUNTIME_REEXEC") == "1":
        raise RuntimeError("pypdf is unavailable in the governed external-SSD PDF runtime")
    pdf_python = governed_pdf_python(verify_import=True)
    env = os.environ.copy()
    env["AI_OS_PDF_RUNTIME_REEXEC"] = "1"
    os.execve(pdf_python, [pdf_python, *sys.argv], env)


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_int(value: object) -> str:
    if value in (None, ""):
        return "NULL"
    return str(int(value))


def sql_jsonb(value: object) -> str:
    return f"{sql_literal(json.dumps(value if value is not None else {}, sort_keys=True, default=str))}::jsonb"


def run_psql_json(sql: str) -> list[dict[str, Any]]:
    command = [
        "docker",
        "exec",
        "-i",
        "ai_os_postgres",
        "psql",
        "-q",
        "-t",
        "-A",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        "ai_os",
        "-d",
        "ai_os",
    ]
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return json.loads(completed.stdout.strip() or "[]")


def clean_text(value: str) -> str:
    text = value.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean(value: object, fallback: str = "n/a") -> str:
    if value is None:
        return fallback
    return clean_text(str(value)) or fallback


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-").lower()
    return slug[:90] or "source-document"


def content_hash(*values: object) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(str(value or "").encode("utf-8", errors="ignore"))
        digest.update(b"\x1f")
    return digest.hexdigest()


def fetch_document(source_document_id: int | None, symbol: str | None) -> dict[str, Any]:
    where = []
    if source_document_id:
        where.append(f"id = {int(source_document_id)}")
    if symbol:
        where.append(f"upper(symbol) = {sql_literal(symbol.upper())}")
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT *
            FROM portfolio.v_long_term_source_documents
            {where_sql}
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
        ) rows
        """
    )
    if not rows:
        raise ValueError("No matching Long-Term source document found")
    return rows[0]


def download_pdf(document: dict[str, Any]) -> Path:
    source_url = clean(document.get("source_url"), "")
    if not source_url:
        local_path = document.get("local_path")
        if local_path:
            path = VAULT_ROOT / str(local_path)
            if path.exists():
                return path
        raise ValueError("source_url or existing local_path is required for extraction")
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    digest = content_hash(source_url)[:12]
    target = ARTIFACT_ROOT / f"source-document-{document['id']}-{safe_slug(clean(document.get('symbol')))}-{digest}.pdf"
    request = urllib.request.Request(
        source_url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/pdf,*/*"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = response.read()
    target.write_bytes(payload)
    return target


def extract_pdf_text(path: Path) -> tuple[str, int, str]:
    from pypdf import PdfReader  # type: ignore

    reader = PdfReader(str(path))
    chunks: list[str] = []
    for page in reader.pages:
        chunks.append(page.extract_text() or "")
    return clean_text("\n".join(chunks)), len(reader.pages), "pypdf"


def key_snippets(text: str) -> list[dict[str, str]]:
    compact = clean_text(text)
    lowered = compact.lower()
    terms = [
        "business",
        "wire rope",
        "steel",
        "lrdpc",
        "mining",
        "infrastructure",
        "international",
        "customer",
        "margin",
        "risk",
        "competition",
        "capital expenditure",
    ]
    snippets: list[dict[str, str]] = []
    for term in terms:
        index = lowered.find(term)
        if index < 0:
            continue
        start = max(0, index - 260)
        end = min(len(compact), index + 520)
        snippets.append({"term": term, "snippet": compact[start:end]})
        if len(snippets) >= 8:
            break
    return snippets


def insert_raw_text_artifact(document: dict[str, Any], text_path: Path, extracted_text: str, page_count: int, parser_name: str) -> int:
    hash_value = content_hash(document.get("id"), document.get("source_url"), extracted_text[:200000])
    metadata = {
        "source_document_id": document.get("id"),
        "source_request_id": document.get("source_request_id"),
        "symbol": document.get("symbol"),
        "document_type": document.get("document_type"),
        "parser": parser_name,
        "page_count": page_count,
        "extracted_chars": len(extracted_text),
    }
    rows = run_psql_json(
        f"""
        WITH rows AS (
            INSERT INTO core.raw_artifacts (
                source_system_id, artifact_type, title, source_url, local_path,
                content_hash, mime_type, sensitivity, metadata
            )
            VALUES (
                NULL,
                'long_term_source_document_text',
                {sql_literal(clean(document.get('document_title')) + ' - extracted text')},
                {sql_literal(document.get('source_url'))},
                {sql_literal(artifact_reference(text_path))},
                {sql_literal(hash_value)},
                'text/plain',
                'public',
                {sql_jsonb(metadata)}
            )
            ON CONFLICT (source_system_id, source_url, local_path, content_hash) DO UPDATE SET
                title = EXCLUDED.title,
                metadata = EXCLUDED.metadata,
                captured_at = now()
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text FROM rows
        """
    )
    if not rows:
        raise ValueError("raw text artifact insert returned no row")
    return int(rows[0]["id"])


def persist_extraction(
    document: dict[str, Any],
    pdf_path: Path,
    text_path: Path,
    extracted_text: str,
    page_count: int,
    parser_name: str,
    raw_artifact_id: int,
    actor: str,
) -> dict[str, Any]:
    snippets = key_snippets(extracted_text)
    rows = run_psql_json(
        f"""
        WITH rows AS (
            INSERT INTO portfolio.long_term_source_document_extractions (
                source_document_id, source_request_id, raw_artifact_id,
                symbol, document_type, document_title, source_url,
                local_pdf_path, local_text_path, parser_name, page_count,
                extracted_chars, text_excerpt, key_snippets,
                extraction_status, error, extracted_by, updated_at
            )
            VALUES (
                {int(document['id'])},
                {sql_int(document.get('source_request_id'))},
                {raw_artifact_id},
                {sql_literal(document.get('symbol'))},
                {sql_literal(document.get('document_type'))},
                {sql_literal(document.get('document_title'))},
                {sql_literal(document.get('source_url'))},
                {sql_literal(artifact_reference(pdf_path))},
                {sql_literal(artifact_reference(text_path))},
                {sql_literal(parser_name)},
                {page_count},
                {len(extracted_text)},
                {sql_literal(extracted_text[:4000])},
                {sql_jsonb(snippets)},
                'extracted',
                NULL,
                {sql_literal(actor)},
                now()
            )
            ON CONFLICT (source_document_id, parser_name) DO UPDATE SET
                source_request_id = EXCLUDED.source_request_id,
                raw_artifact_id = EXCLUDED.raw_artifact_id,
                source_url = EXCLUDED.source_url,
                local_pdf_path = EXCLUDED.local_pdf_path,
                local_text_path = EXCLUDED.local_text_path,
                page_count = EXCLUDED.page_count,
                extracted_chars = EXCLUDED.extracted_chars,
                text_excerpt = EXCLUDED.text_excerpt,
                key_snippets = EXCLUDED.key_snippets,
                extraction_status = EXCLUDED.extraction_status,
                error = NULL,
                extracted_by = EXCLUDED.extracted_by,
                updated_at = now()
            RETURNING *
        )
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text FROM rows
        """
    )
    if not rows:
        raise ValueError("source document extraction insert returned no row")
    return rows[0]


def extract_document(args: argparse.Namespace) -> dict[str, Any]:
    ensure_pdf_runtime()
    document = fetch_document(args.source_document_id, args.symbol)
    pdf_path = download_pdf(document)
    extracted_text, page_count, parser_name = extract_pdf_text(pdf_path)
    if not extracted_text:
        raise ValueError("PDF extraction produced no text")
    text_path = pdf_path.with_suffix(".txt")
    text_path.write_text(extracted_text)
    raw_artifact_id = insert_raw_text_artifact(document, text_path, extracted_text, page_count, parser_name)
    extraction = persist_extraction(document, pdf_path, text_path, extracted_text, page_count, parser_name, raw_artifact_id, args.actor)
    return {
        "extraction_id": extraction["id"],
        "source_document_id": document["id"],
        "source_request_id": document.get("source_request_id"),
        "symbol": document.get("symbol"),
        "document_type": document.get("document_type"),
        "page_count": page_count,
        "extracted_chars": len(extracted_text),
        "raw_artifact_id": raw_artifact_id,
        "local_pdf_path": artifact_reference(pdf_path),
        "local_text_path": artifact_reference(text_path),
        "snippet_count": len(extraction.get("key_snippets") or []),
        "capital_action_allowed": False,
        "live_execution_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract text from a registered Long-Term source document.")
    parser.add_argument("--source-document-id", type=int)
    parser.add_argument("--symbol")
    parser.add_argument("--actor", default="Filings and Transcript Analyst")
    args = parser.parse_args()
    try:
        result = extract_document(args)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
