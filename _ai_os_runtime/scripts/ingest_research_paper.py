#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path


RUNTIME_ROOT = Path(os.environ.get("AI_OS_RUNTIME_ROOT") or Path(__file__).absolute().parents[1])
VAULT_ROOT = Path(os.environ.get("AI_OS_VAULT_ROOT") or RUNTIME_ROOT.parent)
ARTIFACT_ROOT = Path(os.environ.get("AI_OS_ARTIFACT_ROOT") or "/Volumes/Devarsh SSD/AI OS Data/artifacts") / "research_papers"
BUNDLED_PYTHON = Path("/Users/devarshthakkar/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3")
USER_AGENT = "AI-OS-Research/0.1 (research paper ingestion; local operator)"


def ensure_pdf_runtime() -> None:
    try:
        import pypdf  # noqa: F401
        return
    except Exception:
        pass
    if os.environ.get("AI_OS_PDF_RUNTIME_REEXEC") == "1" or not BUNDLED_PYTHON.exists():
        raise RuntimeError("pypdf is required and the bundled PDF runtime is unavailable")
    env = os.environ.copy()
    env["AI_OS_PDF_RUNTIME_REEXEC"] = "1"
    os.execve(str(BUNDLED_PYTHON), [str(BUNDLED_PYTHON), *sys.argv], env)


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return f"{sql_literal(json.dumps(value, sort_keys=True, default=str))}::jsonb"


def sql_array(values: list[str]) -> str:
    if not values:
        return "ARRAY[]::text[]"
    return "ARRAY[" + ",".join(sql_literal(value) for value in values) + "]::text[]"


def run_psql(sql: str) -> list[dict]:
    completed = subprocess.run(
        ["docker", "exec", "-i", "ai_os_postgres", "psql", "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os"],
        input=sql,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return json.loads(completed.stdout.strip() or "[]")


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:100] or "paper"


def clean_text(value: str) -> str:
    value = value.replace("\x00", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def split_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def validate_public_https(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("remote paper URLs must use public HTTPS")
    for result in socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM):
        address = ipaddress.ip_address(result[4][0])
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
            raise ValueError("remote paper URL resolves to a non-public address")


def allowed_local_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser().resolve()
    roots = [VAULT_ROOT.resolve(), ARTIFACT_ROOT.parent.resolve()]
    if not any(path == root or root in path.parents for root in roots):
        raise ValueError("local paper must be inside the vault or external AI OS artifact root")
    if not path.is_file():
        raise ValueError(f"local paper not found: {path}")
    return path


def acquire_pdf(pdf_url: str, local_path: str, paper_key: str) -> Path | None:
    if local_path:
        return allowed_local_path(local_path)
    if not pdf_url:
        return None
    validate_public_https(pdf_url)
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    target = ARTIFACT_ROOT / f"{slug(paper_key)}-{hashlib.sha256(pdf_url.encode()).hexdigest()[:12]}.pdf"
    request = urllib.request.Request(pdf_url, headers={"User-Agent": USER_AGENT, "Accept": "application/pdf,*/*"})
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = response.read(80 * 1024 * 1024 + 1)
    if len(payload) > 80 * 1024 * 1024:
        raise ValueError("paper PDF exceeds 80 MB limit")
    if not payload.startswith(b"%PDF"):
        raise ValueError("paper download did not return a PDF")
    target.write_bytes(payload)
    return target


def extract_pdf(path: Path) -> tuple[str, int]:
    from pypdf import PdfReader  # type: ignore

    reader = PdfReader(str(path))
    return clean_text("\n".join((page.extract_text() or "") for page in reader.pages)), len(reader.pages)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True)
    parser.add_argument("--source-key", default="local")
    parser.add_argument("--source-url", default="")
    parser.add_argument("--pdf-url", default="")
    parser.add_argument("--local-path", default="")
    parser.add_argument("--authors", default="")
    parser.add_argument("--published-date", default="")
    parser.add_argument("--doi", default="")
    parser.add_argument("--abstract", default="")
    parser.add_argument("--topics", default="")
    parser.add_argument("--asset-classes", default="")
    parser.add_argument("--markets", default="")
    parser.add_argument("--methodology-tags", default="")
    parser.add_argument("--actor", default="Research Librarian")
    args = parser.parse_args()

    if args.pdf_url:
        ensure_pdf_runtime()
    paper_key = f"paper-{slug(args.source_key)}-{hashlib.sha256((args.title + args.doi + args.source_url + args.pdf_url + args.local_path).encode()).hexdigest()[:18]}"
    pdf_path = acquire_pdf(args.pdf_url, args.local_path, paper_key)
    extracted_text = ""
    page_count = None
    text_path = None
    content_hash = hashlib.sha256((args.title + args.abstract).encode()).hexdigest()
    if pdf_path:
        ensure_pdf_runtime()
        extracted_text, page_count = extract_pdf(pdf_path)
        content_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        text_path = ARTIFACT_ROOT / f"{slug(paper_key)}-{content_hash[:12]}.txt"
        text_path.write_text(extracted_text, encoding="utf-8")

    rows = run_psql(
        f"""
        WITH paper AS (
            INSERT INTO research.research_papers (
                paper_key, source_key, title, authors, published_date, doi,
                source_url, pdf_url, local_pdf_path, local_text_path, abstract,
                extracted_text, page_count, content_hash, topics, asset_classes,
                markets, methodology_tags, extraction_status, review_status,
                owner_agent, evidence, metadata
            ) VALUES (
                {sql_literal(paper_key)}, {sql_literal(args.source_key)}, {sql_literal(args.title)},
                {sql_array(split_values(args.authors))}, {sql_literal(args.published_date or None)}::date,
                {sql_literal(args.doi or None)}, {sql_literal(args.source_url or None)}, {sql_literal(args.pdf_url or None)},
                {sql_literal(str(pdf_path) if pdf_path else None)}, {sql_literal(str(text_path) if text_path else None)},
                {sql_literal(args.abstract or None)}, {sql_literal(extracted_text or None)}, {page_count or 'NULL'},
                {sql_literal(content_hash)}, {sql_array(split_values(args.topics))}, {sql_array(split_values(args.asset_classes))},
                {sql_array(split_values(args.markets))}, {sql_array(split_values(args.methodology_tags))},
                {sql_literal('extracted' if extracted_text else 'registered')}, 'needs_review', {sql_literal(args.actor)},
                {sql_jsonb([{"source_url": args.source_url, "pdf_url": args.pdf_url, "content_hash": content_hash}])},
                {sql_jsonb({"seed_data_allowed": False, "source_backed": True})}
            )
            ON CONFLICT (paper_key) DO UPDATE SET
                authors=CASE WHEN cardinality(EXCLUDED.authors) > 0 THEN EXCLUDED.authors ELSE research.research_papers.authors END,
                published_date=coalesce(EXCLUDED.published_date,research.research_papers.published_date),
                doi=coalesce(EXCLUDED.doi,research.research_papers.doi),
                source_url=coalesce(EXCLUDED.source_url,research.research_papers.source_url),
                pdf_url=coalesce(EXCLUDED.pdf_url,research.research_papers.pdf_url),
                abstract=coalesce(EXCLUDED.abstract,research.research_papers.abstract),
                extracted_text=coalesce(EXCLUDED.extracted_text,research.research_papers.extracted_text),
                local_pdf_path=coalesce(EXCLUDED.local_pdf_path,research.research_papers.local_pdf_path),
                local_text_path=coalesce(EXCLUDED.local_text_path,research.research_papers.local_text_path),
                page_count=coalesce(EXCLUDED.page_count,research.research_papers.page_count),
                topics=CASE WHEN cardinality(EXCLUDED.topics) > 0 THEN EXCLUDED.topics ELSE research.research_papers.topics END,
                asset_classes=CASE WHEN cardinality(EXCLUDED.asset_classes) > 0 THEN EXCLUDED.asset_classes ELSE research.research_papers.asset_classes END,
                markets=CASE WHEN cardinality(EXCLUDED.markets) > 0 THEN EXCLUDED.markets ELSE research.research_papers.markets END,
                methodology_tags=CASE WHEN cardinality(EXCLUDED.methodology_tags) > 0 THEN EXCLUDED.methodology_tags ELSE research.research_papers.methodology_tags END,
                extraction_status=EXCLUDED.extraction_status, review_status='needs_review',
                evidence=EXCLUDED.evidence, updated_at=now()
            RETURNING *
        ),
        artifact AS (
            INSERT INTO core.raw_artifacts (
                source_system_id, artifact_type, title, source_url, local_path,
                content_hash, mime_type, sensitivity, metadata
            )
            SELECT NULL, 'research_paper_text', {sql_literal(args.title + ' - extracted text')},
                   {sql_literal(args.source_url or args.pdf_url or None)}, {sql_literal(str(text_path) if text_path else None)},
                   {sql_literal(content_hash)}, 'text/plain', 'public',
                   {sql_jsonb({'paper_key': paper_key, 'source_key': args.source_key, 'page_count': page_count, 'extracted_chars': len(extracted_text)})}
            FROM paper
            WHERE {sql_literal(extracted_text)} <> ''
            ON CONFLICT (source_system_id, source_url, local_path, content_hash) DO UPDATE SET
                title=EXCLUDED.title, metadata=EXCLUDED.metadata, captured_at=now()
            RETURNING id
        ),
        run AS (
            INSERT INTO research.paper_ingestion_runs (
                paper_id, status, parser_name, bytes_downloaded, page_count,
                extracted_chars, artifact_id, finished_at, created_by
            ) SELECT id, {sql_literal('completed' if extracted_text else 'registered')},
                     {sql_literal('pypdf' if extracted_text else 'metadata_only')},
                     {pdf_path.stat().st_size if pdf_path else 0}, {page_count or 'NULL'},
                     {len(extracted_text)}, (SELECT id FROM artifact), now(), {sql_literal(args.actor)} FROM paper
            RETURNING *
        )
        SELECT json_build_object(
            'paper', (SELECT json_build_object(
                'id',id,'paper_key',paper_key,'source_key',source_key,'title',title,
                'authors',authors,'published_date',published_date,'doi',doi,
                'source_url',source_url,'pdf_url',pdf_url,'local_pdf_path',local_pdf_path,
                'local_text_path',local_text_path,'page_count',page_count,
                'content_hash',content_hash,'topics',topics,'asset_classes',asset_classes,
                'markets',markets,'methodology_tags',methodology_tags,
                'extraction_status',extraction_status,'review_status',review_status,
                'owner_agent',owner_agent,'evidence',evidence,'updated_at',updated_at
            ) FROM paper),
            'run',(SELECT row_to_json(run) FROM run)
        )::text;
        """
    )
    print(json.dumps(rows if isinstance(rows, dict) else (rows[0] if rows else {}), default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
