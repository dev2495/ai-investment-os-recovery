#!/usr/bin/env python3
"""Bounded, explicit-URL public research capture with SSD lineage and corroboration gates."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

COLLECTOR_VERSION = "governed-source-v1"
USER_AGENT = "AIOSResearchCollector/1.0 (+local personal research; bounded explicit URLs)"
SSD_ROOT = Path(os.environ.get("AI_OS_DATA_ROOT", "/Volumes/Devarsh SSD/AI OS Data"))
CACHE_ROOT = SSD_ROOT / "research" / "source_cache"
DOCKER = shutil.which("docker") or "/opt/homebrew/bin/docker"
TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source"}
ALLOWED_MIME = {"text/html", "application/xhtml+xml", "application/pdf", "text/plain"}
PRIMARY_KINDS = {
    "official_company_page", "official_ir_page", "annual_report", "company_filing",
    "exchange_filing", "exchange_results", "exchange_announcement", "investor_presentation",
    "transcript", "regulatory_source",
}


def literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def jsonb(value: object) -> str:
    return literal(json.dumps(value, sort_keys=True, default=str)) + "::jsonb"


def run(sql: str) -> list[dict[str, Any]]:
    body = sql.rstrip().rstrip(";")
    if body.lstrip().lower().startswith(("insert ", "update ", "delete ")):
        statement = "WITH q AS (" + body + ") SELECT coalesce(json_agg(row_to_json(q)), '[]'::json)::text FROM q;"
    else:
        statement = "SELECT coalesce(json_agg(row_to_json(q)), '[]'::json)::text FROM (" + body + ") q;"
    completed = subprocess.run(
        [DOCKER, "exec", "-i", "ai_os_postgres", "psql", "-q", "-t", "-A",
         "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os"],
        input=statement, text=True, capture_output=True, check=False,
    )
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return json.loads(completed.stdout.strip() or "[]")


def execute(sql: str) -> None:
    completed = subprocess.run(
        [DOCKER, "exec", "-i", "ai_os_postgres", "psql", "-q", "-v", "ON_ERROR_STOP=1",
         "-U", "ai_os", "-d", "ai_os"], input=sql, text=True, capture_output=True, check=False,
    )
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout).strip())


def canonicalize_url(raw: str) -> str:
    parsed = urllib.parse.urlsplit(raw.strip())
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError("Only explicit HTTPS URLs are allowed")
    host = parsed.hostname.lower().rstrip(".")
    port = "" if parsed.port in (None, 443) else f":{parsed.port}"
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query = sorted((k, v) for k, v in query if k.lower() not in TRACKING_KEYS and not k.lower().startswith("utm_"))
    return urllib.parse.urlunsplit(("https", host + port, path, urllib.parse.urlencode(query), ""))


def hostname_allowed(hostname: str, pattern: str) -> bool:
    return re.search(pattern, hostname.lower(), flags=re.IGNORECASE) is not None


class ArticleHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.meta: dict[str, str] = {}
        self._title = False
        self._blocked = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k.lower(): (v or "") for k, v in attrs}
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._blocked += 1
        if tag.lower() == "title":
            self._title = True
        if tag.lower() == "meta":
            key = (attrs_dict.get("property") or attrs_dict.get("name") or "").lower()
            value = attrs_dict.get("content", "").strip()
            if key and value:
                self.meta[key] = value

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self._blocked:
            self._blocked -= 1
        if tag.lower() == "title":
            self._title = False

    def handle_data(self, data: str) -> None:
        value = " ".join(html.unescape(data).split())
        if not value or self._blocked:
            return
        if self._title:
            self.title_parts.append(value)
        self.text_parts.append(value)


def parse_html_document(data: bytes, charset: str = "utf-8") -> dict[str, str]:
    parser = ArticleHTMLParser()
    parser.feed(data.decode(charset, errors="replace"))
    title = parser.meta.get("og:title") or parser.meta.get("twitter:title") or " ".join(parser.title_parts)
    author = parser.meta.get("author") or parser.meta.get("article:author") or ""
    published = parser.meta.get("article:published_time") or parser.meta.get("date") or ""
    text = "\n".join(parser.text_parts)
    return {"title": title.strip(), "author": author.strip(), "published_at": published.strip(), "text": text.strip()}


def get_company(symbol: str) -> dict[str, Any]:
    rows = run("SELECT id,primary_symbol symbol,coalesce(display_name,legal_name) company_name "
               "FROM research.companies WHERE upper(primary_symbol)=" + literal(symbol.upper()) + " LIMIT 1")
    if not rows:
        raise ValueError("Unknown research company: " + symbol)
    return rows[0]


def get_policy(provider: str) -> dict[str, Any]:
    rows = run("SELECT * FROM research.source_provider_policies WHERE provider_key=" + literal(provider) + " AND is_active")
    if not rows:
        raise ValueError("Provider is not in the active governed allowlist: " + provider)
    return rows[0]


def register(args: argparse.Namespace) -> dict[str, Any]:
    company = get_company(args.symbol)
    policy = get_policy(args.provider)
    canonical = canonicalize_url(args.url)
    if not hostname_allowed(urllib.parse.urlsplit(canonical).hostname or "", policy["hostname_pattern"]):
        raise ValueError("URL hostname is outside the selected provider policy")
    key_seed = f"{company['id']}|{policy['provider_key']}|{canonical}"
    key = "candidate:" + hashlib.sha256(key_seed.encode()).hexdigest()
    rows = run(
        "INSERT INTO research.source_collection_candidates(candidate_key,company_id,provider_key,requested_url,"
        "canonical_url,source_title,author_name,publication_date,discovered_by,discovery_method,"
        "explicit_collection_scope,candidate_status,review_notes,metadata) VALUES(" + literal(key) + "," +
        str(int(company["id"])) + "," + literal(policy["provider_key"]) + "," + literal(args.url) + "," +
        literal(canonical) + "," + literal(args.title) + "," + literal(args.author) + "," +
        literal(args.publication_date) + "::date," + literal(args.actor) + "," + literal(args.discovery_method) +
        ",true,'ready','Explicit public URL authorized for bounded read-only capture.'," +
        jsonb({"registered_from": "single_url", "no_broad_crawl": True}) + ") ON CONFLICT(company_id,provider_key,canonical_url) "
        "DO UPDATE SET source_title=coalesce(EXCLUDED.source_title,research.source_collection_candidates.source_title),"
        "author_name=coalesce(EXCLUDED.author_name,research.source_collection_candidates.author_name),"
        "publication_date=coalesce(EXCLUDED.publication_date,research.source_collection_candidates.publication_date),"
        "explicit_collection_scope=true,candidate_status=CASE WHEN research.source_collection_candidates.candidate_status='captured' "
        "THEN 'captured' ELSE 'ready' END,updated_at=now() RETURNING id,candidate_key,canonical_url,candidate_status"
    )
    return rows[0]


def record_exception(candidate_id: int, capture_id: int | None, code: str, summary: str,
                     remediation: str, *, retryable: bool = False, retry_after: datetime | None = None) -> None:
    execute(
        "INSERT INTO research.source_collection_exceptions(candidate_id,capture_id,exception_code,severity,"
        "exception_summary,remediation,retryable,retry_after) VALUES(" + str(candidate_id) + "," +
        (str(capture_id) if capture_id else "NULL") + "," + literal(code) + ",'high'," + literal(summary) + "," +
        literal(remediation) + "," + ("true" if retryable else "false") + "," +
        literal(retry_after.isoformat() if retry_after else None) + "::timestamptz);"
    )


def check_robots(url: str) -> tuple[bool, str, str]:
    parsed = urllib.parse.urlsplit(url)
    robots_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "/robots.txt", "", ""))
    request = urllib.request.Request(robots_url, headers={"User-Agent": USER_AGENT, "Accept": "text/plain"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status != 200:
                return False, robots_url, "unavailable"
            text = response.read(1024 * 1024).decode("utf-8", errors="replace")
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(text.splitlines())
        return parser.can_fetch(USER_AGENT, url), robots_url, "allowed" if parser.can_fetch(USER_AGENT, url) else "blocked"
    except (urllib.error.URLError, TimeoutError, OSError):
        return False, robots_url, "unavailable"


def collect(args: argparse.Namespace) -> dict[str, Any]:
    rows = run(
        "SELECT c.*,p.provider_name,p.provider_class,p.hostname_pattern,p.source_system,p.default_source_kind,"
        "p.robots_check_required,p.terms_basis,p.minimum_interval_seconds,p.maximum_bytes,p.cache_ttl_hours,"
        "p.primary_corroboration_required,co.primary_symbol symbol FROM research.source_collection_candidates c "
        "JOIN research.source_provider_policies p ON p.provider_key=c.provider_key "
        "JOIN research.companies co ON co.id=c.company_id WHERE c.id=" + str(args.candidate_id)
    )
    if not rows:
        raise ValueError("Collection candidate not found")
    item = rows[0]
    now = datetime.now(timezone.utc)
    if not item["explicit_collection_scope"]:
        raise ValueError("Candidate lacks explicit single-URL collection scope")
    if item.get("next_allowed_at") and datetime.fromisoformat(str(item["next_allowed_at"]).replace("Z", "+00:00")) > now:
        raise ValueError("Provider cooldown is active; retry after " + str(item["next_allowed_at"]))
    url = canonicalize_url(item["canonical_url"])
    host = urllib.parse.urlsplit(url).hostname or ""
    if not hostname_allowed(host, item["hostname_pattern"]):
        raise ValueError("Candidate URL no longer matches provider policy")
    capture_id = int(run(
        "INSERT INTO research.source_collection_captures(candidate_id,capture_status,requested_url,robots_status,collector_version) VALUES(" +
        str(args.candidate_id) + ",'started'," + literal(url) + ",'not_checked'," + literal(COLLECTOR_VERSION) + ") RETURNING id"
    )[0]["id"])
    allowed, robots_url, robots_status = check_robots(url) if item["robots_check_required"] else (True, "", "not_checked")
    if not allowed:
        execute("UPDATE research.source_collection_captures SET capture_status='blocked',completed_at=now(),robots_url=" +
                literal(robots_url) + ",robots_status=" + literal(robots_status) + ",error_code='robots_not_allowed',"
                "error_detail='Robots permission was not affirmatively available.' WHERE id=" + str(capture_id) + ";"
                "UPDATE research.source_collection_candidates SET candidate_status='blocked',last_attempt_at=now(),updated_at=now() WHERE id=" + str(args.candidate_id) + ";")
        record_exception(args.candidate_id, capture_id, "robots_not_allowed",
                         "Capture stopped because robots permission was blocked or unavailable.",
                         "Review the source manually or use an official alternative; do not bypass robots.")
        return {"candidate_id": args.candidate_id, "capture_id": capture_id, "status": "blocked", "robots_status": robots_status}
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf,text/plain;q=0.8"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            final_url = canonicalize_url(response.geturl())
            final_host = urllib.parse.urlsplit(final_url).hostname or ""
            if not hostname_allowed(final_host, item["hostname_pattern"]):
                raise ValueError("Redirect crossed the governed provider hostname boundary")
            content_type_header = response.headers.get_content_type().lower()
            if content_type_header not in ALLOWED_MIME:
                raise ValueError("Unsupported response content type: " + content_type_header)
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > int(item["maximum_bytes"]):
                raise ValueError("Response exceeds provider maximum bytes")
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(min(65536, int(item["maximum_bytes"]) + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > int(item["maximum_bytes"]):
                    raise ValueError("Response exceeded provider maximum bytes during streaming")
            data = b"".join(chunks)
            http_status = int(response.status)
            charset = response.headers.get_content_charset() or "utf-8"
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        execute("UPDATE research.source_collection_captures SET capture_status='failed',completed_at=now(),robots_url=" +
                literal(robots_url) + ",robots_status='allowed',error_code='bounded_fetch_failed',error_detail=" +
                literal(str(exc)[:1000]) + " WHERE id=" + str(capture_id) + "; UPDATE research.source_collection_candidates "
                "SET candidate_status='failed',last_attempt_at=now(),next_allowed_at=now()+interval '15 minutes',updated_at=now() WHERE id=" + str(args.candidate_id) + ";")
        record_exception(args.candidate_id, capture_id, "bounded_fetch_failed", str(exc)[:500],
                         "Retry after cooldown or replace with an official accessible URL; do not bypass access controls.",
                         retryable=True, retry_after=now + timedelta(minutes=15))
        return {"candidate_id": args.candidate_id, "capture_id": capture_id, "status": "failed", "error": str(exc)}

    digest = hashlib.sha256(data).hexdigest()
    existing = run("SELECT id,raw_artifact_path FROM research.source_collection_captures WHERE content_sha256=" +
                   literal(digest) + " AND capture_status='captured' AND id<>" + str(capture_id) + " ORDER BY id LIMIT 1")
    directory = CACHE_ROOT / str(item["symbol"]).upper() / str(item["provider_key"]) / digest[:16]
    directory.mkdir(parents=True, exist_ok=True)
    if not str(directory).startswith("/Volumes/Devarsh SSD/"):
        raise RuntimeError("Refusing internal-disk source cache fallback")
    suffix = ".pdf" if content_type_header == "application/pdf" else ".html" if "html" in content_type_header else ".txt"
    raw_path = directory / ("source" + suffix)
    raw_path.write_bytes(data)
    extracted: dict[str, str] = {"title": "", "author": "", "published_at": "", "text": ""}
    text_path: Path | None = None
    parser_status = "pending"
    if "html" in content_type_header:
        extracted = parse_html_document(data, charset)
        text_path = directory / "source.txt"
        text_path.write_text(extracted["text"], encoding="utf-8")
        parser_status = "parsed" if len(extracted["text"]) >= 200 else "failed"
    elif content_type_header == "text/plain":
        text_path = directory / "source.txt"
        text_path.write_bytes(data)
        parser_status = "parsed"
    receipt_path = directory / "receipt.json"
    receipt = {
        "candidate_id": args.candidate_id, "capture_id": capture_id, "collector_version": COLLECTOR_VERSION,
        "requested_url": url, "final_url": final_url, "captured_at": now.isoformat(), "http_status": http_status,
        "content_type": content_type_header, "bytes": len(data), "sha256": digest,
        "robots_url": robots_url, "robots_status": "allowed", "terms_basis": item["terms_basis"],
        "cache_root": str(directory), "source_scope": "public", "cookies_or_credentials_used": False,
        "primary_corroboration_required": bool(item["primary_corroboration_required"]),
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    duplicate_id = int(existing[0]["id"]) if existing else None
    capture_status = "duplicate" if duplicate_id else "captured"
    execute("UPDATE research.source_collection_captures SET capture_status=" + literal(capture_status) +
            ",completed_at=now(),final_url=" + literal(final_url) + ",http_status=" + str(http_status) +
            ",content_type=" + literal(content_type_header) + ",response_bytes=" + str(len(data)) +
            ",content_sha256=" + literal(digest) + ",raw_artifact_path=" + literal(str(raw_path)) +
            ",text_artifact_path=" + literal(str(text_path) if text_path else None) + ",receipt_path=" +
            literal(str(receipt_path)) + ",robots_url=" + literal(robots_url) + ",robots_status='allowed',parser_status=" +
            literal(parser_status) + ",duplicate_of_capture_id=" + (str(duplicate_id) if duplicate_id else "NULL") +
            " WHERE id=" + str(capture_id) + ";")
    source_key = str(item["symbol"]).lower() + ":" + str(item["source_system"]) + ":" + digest
    title = item.get("source_title") or extracted.get("title") or final_url
    author = item.get("author_name") or extracted.get("author") or None
    publication_date = item.get("publication_date")
    if not publication_date and extracted.get("published_at"):
        publication_date = extracted["published_at"][:10]
    source_item = run(
        "INSERT INTO research.thesis_source_items(source_key,company_id,source_kind,source_system,source_identifier,"
        "source_url,source_title,publication_date,captured_at,capture_status,parser_status,validation_status,"
        "local_artifact_path,content_hash,citation_locator,freshness_expires_at,source_scope,authorization_basis,"
        "access_status,terms_status,robots_status,cache_status,rate_limit_seconds,section_hint,validation_notes,metadata) VALUES(" +
        literal(source_key) + "," + str(int(item["company_id"])) + "," + literal(item["default_source_kind"]) + "," +
        literal(item["source_system"]) + "," + literal(digest) + "," + literal(final_url) + "," + literal(title) + "," +
        literal(publication_date) + "::date,now(),'captured'," + literal(parser_status) + ",'pending'," + literal(str(raw_path)) +
        "," + literal(digest) + "," + jsonb({"capture_id": capture_id, "sha256": digest, "exact_claim_locator_pending": True}) +
        ",now()+make_interval(hours=>" + str(int(item["cache_ttl_hours"])) + "),'public'," +
        literal(item["terms_basis"]) + ",'allowed','allowed','allowed','external_ssd'," +
        str(int(item["minimum_interval_seconds"])) + ",'evidence_library','Captured public source; claims remain review and corroboration gated.'," +
        jsonb({"author": author, "provider_key": item["provider_key"], "receipt_path": str(receipt_path),
               "primary_corroboration_required": bool(item["primary_corroboration_required"])}) +
        ") ON CONFLICT(source_key) DO UPDATE SET captured_at=now(),local_artifact_path=EXCLUDED.local_artifact_path,"
        "content_hash=EXCLUDED.content_hash,citation_locator=EXCLUDED.citation_locator,metadata=research.thesis_source_items.metadata||EXCLUDED.metadata,"
        "updated_at=now() RETURNING id"
    )[0]
    execute("UPDATE research.source_collection_candidates SET candidate_status=" + literal(capture_status) +
            ",captured_source_item_id=" + str(int(source_item["id"])) + ",source_title=coalesce(source_title," + literal(title) +
            "),author_name=coalesce(author_name," + literal(author) + "),publication_date=coalesce(publication_date," +
            literal(publication_date) + "::date),last_attempt_at=now(),next_allowed_at=now()+make_interval(secs=>" +
            str(int(item["minimum_interval_seconds"])) + "),updated_at=now() WHERE id=" + str(args.candidate_id) + ";")
    return {"candidate_id": args.candidate_id, "capture_id": capture_id, "source_item_id": int(source_item["id"]),
            "status": capture_status, "provider": item["provider_name"], "title": title, "author": author,
            "publication_date": publication_date, "sha256": digest, "bytes": len(data), "parser_status": parser_status,
            "raw_path": str(raw_path), "text_path": str(text_path) if text_path else None,
            "receipt_path": str(receipt_path), "primary_corroboration_required": bool(item["primary_corroboration_required"])}


def map_section(args: argparse.Namespace) -> dict[str, Any]:
    rows = run("SELECT captured_source_item_id FROM research.source_collection_candidates WHERE id=" + str(args.candidate_id))
    if not rows or not rows[0]["captured_source_item_id"]:
        raise ValueError("Candidate must be captured before section mapping")
    source_item_id = int(rows[0]["captured_source_item_id"])
    result = run(
        "INSERT INTO research.thesis_source_links(source_item_id,requirement_id,link_role,link_status,citation_note,linked_by) "
        "SELECT " + str(source_item_id) + ",id,'supporting','proposed'," + literal(args.citation_note) + "," + literal(args.actor) +
        " FROM research.thesis_source_requirements WHERE requirement_key=" + literal(args.requirement_key) +
        " ON CONFLICT(source_item_id,requirement_id,link_role) DO UPDATE SET citation_note=EXCLUDED.citation_note,linked_at=now() RETURNING id"
    )
    if not result:
        raise ValueError("Unknown thesis requirement key")
    return {"source_item_id": source_item_id, "requirement_key": args.requirement_key,
            "link_status": "proposed", "coverage_changed": False}


def claim(args: argparse.Namespace) -> dict[str, Any]:
    rows = run("SELECT c.company_id,c.captured_source_item_id,p.primary_corroboration_required FROM research.source_collection_candidates c "
               "JOIN research.source_provider_policies p ON p.provider_key=c.provider_key WHERE c.id=" + str(args.candidate_id))
    if not rows or not rows[0]["captured_source_item_id"]:
        raise ValueError("Captured source required before creating a claim draft")
    item = rows[0]
    requirement = "NULL"
    if args.requirement_key:
        found = run("SELECT id FROM research.thesis_source_requirements WHERE requirement_key=" + literal(args.requirement_key))
        if not found:
            raise ValueError("Unknown thesis requirement key")
        requirement = str(int(found[0]["id"]))
    needs_primary = bool(item["primary_corroboration_required"])
    result = run(
        "INSERT INTO research.source_claim_candidates(company_id,source_item_id,requirement_id,claim_text,claim_kind,"
        "citation_locator,primary_corroboration_required,acceptance_status,created_by) VALUES(" +
        str(int(item["company_id"])) + "," + str(int(item["captured_source_item_id"])) + "," + requirement + "," +
        literal(args.claim_text) + "," + literal(args.claim_kind) + "," + jsonb({"locator": args.locator}) + "," +
        ("true" if needs_primary else "false") + "," + literal("needs_primary" if needs_primary else "draft") + "," +
        literal(args.actor) + ") RETURNING id,acceptance_status,primary_corroboration_required"
    )[0]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    reg = sub.add_parser("register")
    reg.add_argument("--symbol", required=True); reg.add_argument("--provider", required=True); reg.add_argument("--url", required=True)
    reg.add_argument("--title"); reg.add_argument("--author"); reg.add_argument("--publication-date")
    reg.add_argument("--actor", default="AI OS Research Lead")
    reg.add_argument("--discovery-method", choices=("operator","agent_search","official_registry","user_supplied"), default="agent_search")
    cap = sub.add_parser("collect"); cap.add_argument("--candidate-id", required=True, type=int)
    link = sub.add_parser("map-section"); link.add_argument("--candidate-id", required=True, type=int)
    link.add_argument("--requirement-key", required=True); link.add_argument("--citation-note", required=True)
    link.add_argument("--actor", default="AI OS Research Lead")
    cl = sub.add_parser("claim"); cl.add_argument("--candidate-id", required=True, type=int)
    cl.add_argument("--claim-text", required=True); cl.add_argument("--claim-kind", required=True,
        choices=("historical_fact","current_fact","management_guidance","estimate","opinion","hypothesis"))
    cl.add_argument("--requirement-key"); cl.add_argument("--locator", required=True)
    cl.add_argument("--actor", default="AI OS Research Lead")
    args = parser.parse_args()
    if args.command == "register": result = register(args)
    elif args.command == "collect": result = collect(args)
    elif args.command == "map-section": result = map_section(args)
    else: result = claim(args)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
