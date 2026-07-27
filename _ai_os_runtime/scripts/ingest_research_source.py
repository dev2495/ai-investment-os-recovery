#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path


RUNTIME_ROOT = Path(os.environ.get("AI_OS_RUNTIME_ROOT") or Path(__file__).absolute().parents[1])
ARTIFACT_ROOT = Path(os.environ.get("AI_OS_ARTIFACT_ROOT") or "/Volumes/Devarsh SSD/AI OS Data/artifacts") / "research_sources"
USER_AGENT = "AI-OS-Research/1.0 (source ingestion; local operator)"
MAX_REMOTE_BYTES = 15 * 1024 * 1024
MAX_PASTED_CHARS = 1_000_000


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return f"{sql_literal(json.dumps(value, sort_keys=True, default=str))}::jsonb"


def sql_array(values: object) -> str:
    items = values if isinstance(values, list) else []
    cleaned = [str(item).strip() for item in items if str(item).strip()]
    if not cleaned:
        return "ARRAY[]::text[]"
    return "ARRAY[" + ",".join(sql_literal(item) for item in cleaned) + "]::text[]"


def run_psql(sql: str) -> dict:
    completed = subprocess.run(
        ["docker", "exec", "-i", "ai_os_postgres", "psql", "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os"],
        input=sql,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return json.loads(completed.stdout.strip() or "{}")


def clean_text(value: str) -> str:
    value = html.unescape(value).replace("\x00", " ").replace("\r", "\n")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n[ \t]+", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:90] or "research-source"


def validate_public_https(url: str) -> urllib.parse.ParseResult:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("research URLs must use public HTTPS without embedded credentials")
    for result in socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM):
        address = ipaddress.ip_address(result[4][0])
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_multicast:
            raise ValueError("research URL resolves to a non-public address")
    return parsed


class ArticleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self._ignored = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "svg", "noscript", "nav", "footer", "form"}:
            self._ignored += 1
        if tag == "title":
            self._in_title = True
        if tag in {"p", "br", "article", "section", "h1", "h2", "h3", "li", "blockquote", "tr"}:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "svg", "noscript", "nav", "footer", "form"} and self._ignored:
            self._ignored -= 1
        if tag == "title":
            self._in_title = False
        if tag in {"p", "article", "section", "h1", "h2", "h3", "li", "blockquote", "tr"}:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._ignored:
            return
        if self._in_title:
            self.title_parts.append(data)
        self.text_parts.append(data)


def fetch_public_source(url: str) -> tuple[bytes, str, str | None]:
    validate_public_https(url)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf,text/plain;q=0.9,*/*;q=0.1"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        final_url = response.geturl()
        validate_public_https(final_url)
        content_type = str(response.headers.get_content_type() or "application/octet-stream").lower()
        payload = response.read(MAX_REMOTE_BYTES + 1)
    if len(payload) > MAX_REMOTE_BYTES:
        raise ValueError("research source exceeds the 15 MB ingestion limit")
    return payload, content_type, final_url


def extract_payload(payload: bytes, content_type: str) -> tuple[str, str | None, str, int | None]:
    if content_type == "application/pdf" or payload.startswith(b"%PDF"):
        try:
            from pypdf import PdfReader  # type: ignore
        except ImportError as exc:
            raise RuntimeError("pypdf is required for PDF source ingestion") from exc
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        temp_pdf = ARTIFACT_ROOT / ("source-" + hashlib.sha256(payload).hexdigest()[:16] + ".pdf")
        temp_pdf.write_bytes(payload)
        reader = PdfReader(str(temp_pdf))
        extracted = clean_text("\n".join((page.extract_text() or "") for page in reader.pages))
        return extracted, None, "pypdf", len(reader.pages)
    decoded = payload.decode("utf-8", errors="replace")
    if "html" in content_type or "<html" in decoded[:1000].lower():
        parser = ArticleParser()
        parser.feed(decoded)
        return clean_text(" ".join(parser.text_parts)), clean_text(" ".join(parser.title_parts)) or None, "html.parser", None
    return clean_text(decoded), None, "plain_text", None


def infer_source_key(source_url: str, requested: str) -> str:
    if requested in {"web", "blog", "github", "manual", "arxiv", "ssrn", "nber", "local"}:
        return requested
    hostname = (urllib.parse.urlparse(source_url).hostname or "").lower()
    return "github" if hostname == "github.com" or hostname.endswith(".github.com") else "web"


def main() -> int:
    raw = sys.stdin.read(MAX_PASTED_CHARS + 100_000)
    request = json.loads(raw or "{}")
    source_url = str(request.get("source_url") or "").strip()
    pasted_text = str(request.get("pasted_text") or "").strip()
    if not source_url and not pasted_text:
        raise ValueError("source_url or pasted_text is required")
    if len(pasted_text) > MAX_PASTED_CHARS:
        raise ValueError("pasted research text exceeds 1,000,000 characters")

    final_url = source_url or None
    page_title = None
    parser_name = "operator_text"
    page_count = None
    local_binary_path = None
    if source_url:
        payload, content_type, final_url = fetch_public_source(source_url)
        extracted_text, page_title, parser_name, page_count = extract_payload(payload, content_type)
        if content_type == "application/pdf" or payload.startswith(b"%PDF"):
            local_binary_path = ARTIFACT_ROOT / ("source-" + hashlib.sha256(payload).hexdigest()[:16] + ".pdf")
    else:
        extracted_text = clean_text(pasted_text)

    if pasted_text and source_url:
        extracted_text = clean_text(extracted_text + "\n\nOperator notes:\n" + pasted_text)
    if len(extracted_text) < 80:
        raise ValueError("source extraction returned too little text to create a research record")

    title = clean_text(str(request.get("title") or page_title or ""))
    if not title:
        path_label = urllib.parse.unquote(urllib.parse.urlparse(source_url).path).strip("/") if source_url else ""
        title = path_label.replace("-", " ").replace("_", " ")[:160] or "Operator research note"
    objective = clean_text(str(request.get("research_objective") or request.get("objective") or "Extract claims, evidence, risks, and falsifiable investment or strategy hypotheses."))
    target_universe = clean_text(str(request.get("target_universe") or request.get("universe") or "")) or None
    desired_outputs = request.get("desired_outputs") if isinstance(request.get("desired_outputs"), list) else ["research_note", "hypothesis_review", "backtest_spec"]
    source_kind = str(request.get("source_kind") or ("pasted_text" if not source_url else "web_article")).strip()
    source_key = infer_source_key(source_url, str(request.get("source_key") or ""))
    actor = str(request.get("actor") or "Devarsh via Charlie").strip()
    word_count = len(extracted_text.split())
    content_hash = hashlib.sha256(extracted_text.encode("utf-8")).hexdigest()
    paper_key = "source-" + slug(source_key) + "-" + content_hash[:20]

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    text_path = ARTIFACT_ROOT / f"{slug(title)}-{content_hash[:12]}.txt"
    text_path.write_text(extracted_text, encoding="utf-8")
    evidence = [{
        "source_url": final_url,
        "content_hash": content_hash,
        "parser": parser_name,
        "operator_supplied_text": bool(pasted_text),
        "captured_by": actor,
    }]
    metadata = {
        "seed_data_allowed": False,
        "source_backed": True,
        "operator_objective": objective,
        "requested_hypothesis": str(request.get("hypothesis") or "").strip() or None,
        "broker_write_allowed": False,
        "live_execution_allowed": False,
    }

    result = run_psql(
        f"""
        WITH paper AS (
            INSERT INTO research.research_papers (
                paper_key,source_key,title,source_url,local_pdf_path,local_text_path,
                extracted_text,page_count,content_hash,topics,asset_classes,markets,
                extraction_status,review_status,owner_agent,evidence,metadata,
                source_kind,research_objective,target_universe,desired_outputs,
                extraction_word_count,intake_status
            ) VALUES (
                {sql_literal(paper_key)},{sql_literal(source_key)},{sql_literal(title)},
                {sql_literal(final_url)},{sql_literal(str(local_binary_path) if local_binary_path else None)},
                {sql_literal(str(text_path))},{sql_literal(extracted_text)},{page_count or 'NULL'},
                {sql_literal(content_hash)},{sql_array(request.get('topics'))},
                {sql_array(request.get('asset_classes'))},{sql_array(request.get('markets'))},
                'extracted','needs_review','Research Librarian',{sql_jsonb(evidence)},{sql_jsonb(metadata)},
                {sql_literal(source_kind)},{sql_literal(objective)},{sql_literal(target_universe)},
                {sql_array(desired_outputs)},{word_count},'assigned'
            )
            ON CONFLICT (paper_key) DO UPDATE SET
                title=EXCLUDED.title,
                source_url=coalesce(EXCLUDED.source_url,research.research_papers.source_url),
                local_text_path=EXCLUDED.local_text_path,
                extracted_text=EXCLUDED.extracted_text,
                content_hash=EXCLUDED.content_hash,
                extraction_status='extracted',review_status='needs_review',
                source_kind=EXCLUDED.source_kind,
                research_objective=EXCLUDED.research_objective,
                target_universe=EXCLUDED.target_universe,
                desired_outputs=EXCLUDED.desired_outputs,
                extraction_word_count=EXCLUDED.extraction_word_count,
                intake_status='assigned',evidence=EXCLUDED.evidence,
                metadata=research.research_papers.metadata || EXCLUDED.metadata,updated_at=now()
            RETURNING *
        ), artifact AS (
            INSERT INTO core.raw_artifacts (
                source_system_id,artifact_type,title,source_url,local_path,
                content_hash,mime_type,sensitivity,metadata
            ) SELECT NULL,'research_source_text',{sql_literal(title)},{sql_literal(final_url)},
                     {sql_literal(str(text_path))},{sql_literal(content_hash)},'text/plain',
                     {sql_literal('internal' if pasted_text and not source_url else 'public')},
                     {sql_jsonb({'paper_key': paper_key, 'word_count': word_count, 'parser': parser_name})}
              FROM paper
            ON CONFLICT (source_system_id,source_url,local_path,content_hash) DO UPDATE SET
                title=EXCLUDED.title,metadata=EXCLUDED.metadata,captured_at=now()
            RETURNING id
        ), run AS (
            INSERT INTO research.paper_ingestion_runs (
                paper_id,status,parser_name,bytes_downloaded,page_count,
                extracted_chars,artifact_id,finished_at,created_by
            ) SELECT id,'completed',{sql_literal(parser_name)},0,{page_count or 'NULL'},
                     {len(extracted_text)},(SELECT id FROM artifact),now(),{sql_literal(actor)}
              FROM paper
            RETURNING *
        )
        SELECT json_build_object(
            'paper',(SELECT json_build_object(
                'id',id,'paper_key',paper_key,'title',title,'source_key',source_key,
                'source_url',source_url,'source_kind',source_kind,'content_hash',content_hash,
                'local_text_path',local_text_path,'extraction_status',extraction_status,
                'review_status',review_status,'intake_status',intake_status,
                'extraction_word_count',extraction_word_count,'research_objective',research_objective,
                'target_universe',target_universe,'desired_outputs',desired_outputs,'evidence',evidence
            ) FROM paper),
            'run',(SELECT row_to_json(run) FROM run),
            'extraction',json_build_object('parser',{sql_literal(parser_name)},'word_count',{word_count},'page_count',{page_count or 'NULL'})
        )::text;
        """
    )
    print(json.dumps(result, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}), file=sys.stderr)
        raise SystemExit(1)
