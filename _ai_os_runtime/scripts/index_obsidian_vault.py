#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
VAULT_ROOT = RUNTIME_ROOT.parent

SKIP_DIRS = {
    ".git",
    ".obsidian",
    ".trash",
    "_ai_os_runtime",
    "node_modules",
    "__pycache__",
}

WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
TAG_RE = re.compile(r"(?<!\w)#([A-Za-z0-9_/-]+)")


def sql_quote(value: object) -> str:
    if value is None:
        return "NULL"
    text = str(value).replace("\x00", "")
    return "'" + text.replace("'", "''") + "'"


def jsonb_quote(value: object) -> str:
    return sql_quote(json.dumps(value, sort_keys=True)) + "::jsonb"


def text_array(values: list[str]) -> str:
    if not values:
        return "'{}'::text[]"
    return "ARRAY[" + ",".join(sql_quote(value) for value in values) + "]::text[]"


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    raw = text[4:end].strip()
    body = text[end + 4 :].lstrip("\n")
    parsed: dict[str, object] = {}
    current_key: str | None = None
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")) and current_key:
            value = line.strip().lstrip("-").strip()
            if value:
                existing = parsed.setdefault(current_key, [])
                if isinstance(existing, list):
                    existing.append(value)
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        current_key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            parsed[current_key] = [part.strip().strip("'\"") for part in value[1:-1].split(",") if part.strip()]
        elif value:
            parsed[current_key] = value.strip("'\"")
        else:
            parsed[current_key] = []
    return parsed, body


def extract_tags(frontmatter: dict, body: str) -> list[str]:
    tags: set[str] = set()
    frontmatter_tags = frontmatter.get("tags") or frontmatter.get("tag")
    if isinstance(frontmatter_tags, str):
        tags.add(frontmatter_tags.lstrip("#"))
    elif isinstance(frontmatter_tags, list):
        for tag in frontmatter_tags:
            tags.add(str(tag).lstrip("#"))
    for match in TAG_RE.findall(body):
        tags.add(match.strip("/"))
    return sorted(tag for tag in tags if tag)


def extract_links(body: str) -> list[dict]:
    links: list[dict] = []
    for match in WIKILINK_RE.findall(body):
        target, _, alias = match.partition("|")
        target = target.strip()
        if not target:
            continue
        links.append({"to_note_path": target, "link_text": alias.strip() or target, "link_type": "wikilink"})
    return links


def summarize_body(body: str, limit: int = 800) -> str:
    lines = [line.strip() for line in body.splitlines() if line.strip() and not line.strip().startswith("![[")]
    summary = " ".join(lines)
    if len(summary) > limit:
        return summary[:limit] + "..."
    return summary


def iter_markdown_files() -> list[Path]:
    files: list[Path] = []
    for path in VAULT_ROOT.rglob("*.md"):
        relative_parts = set(path.relative_to(VAULT_ROOT).parts)
        if relative_parts & SKIP_DIRS:
            continue
        files.append(path)
    return sorted(files)


def build_sql() -> tuple[str, dict]:
    statements = ["BEGIN;", "DELETE FROM knowledge.note_links;"]
    notes = []
    link_count = 0

    for path in iter_markdown_files():
        relative = path.relative_to(VAULT_ROOT)
        note_path = str(relative)
        text = path.read_text(encoding="utf-8", errors="replace")
        frontmatter, body = parse_frontmatter(text)
        title = str(frontmatter.get("title") or path.stem)
        note_type = str(frontmatter.get("type") or relative.parts[0] if relative.parts else "note")
        tags = extract_tags(frontmatter, body)
        links = extract_links(body)
        link_count += len(links)
        modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()

        statements.append(
            f"""
INSERT INTO knowledge.obsidian_notes (
    vault_path,
    note_path,
    title,
    note_type,
    tags,
    frontmatter,
    content_hash,
    body_summary,
    last_modified_at,
    indexed_at
)
VALUES (
    {sql_quote(str(VAULT_ROOT))},
    {sql_quote(note_path)},
    {sql_quote(title)},
    {sql_quote(note_type)},
    {text_array(tags)},
    {jsonb_quote(frontmatter)},
    {sql_quote(content_hash(text))},
    {sql_quote(summarize_body(body))},
    {sql_quote(modified_at)}::timestamptz,
    now()
)
ON CONFLICT (note_path) DO UPDATE SET
    vault_path = EXCLUDED.vault_path,
    title = EXCLUDED.title,
    note_type = EXCLUDED.note_type,
    tags = EXCLUDED.tags,
    frontmatter = EXCLUDED.frontmatter,
    content_hash = EXCLUDED.content_hash,
    body_summary = EXCLUDED.body_summary,
    last_modified_at = EXCLUDED.last_modified_at,
    indexed_at = now();
"""
        )
        for link in links:
            statements.append(
                f"""
WITH from_note AS (
    SELECT id
    FROM knowledge.obsidian_notes
    WHERE note_path = {sql_quote(note_path)}
    LIMIT 1
)
INSERT INTO knowledge.note_links (
    from_note_id,
    to_note_path,
    link_text,
    link_type
)
SELECT
    from_note.id,
    {sql_quote(link["to_note_path"])},
    {sql_quote(link["link_text"])},
    {sql_quote(link["link_type"])}
FROM from_note;
"""
            )
        notes.append(note_path)

    statements.append("COMMIT;")
    return "\n".join(statements), {"notes_indexed": len(notes), "links_indexed": link_count}


def run_psql(sql: str) -> None:
    command = ["docker", "exec", "-i", "ai_os_postgres", "psql", "-q", "-U", "ai_os", "-d", "ai_os", "-v", "ON_ERROR_STOP=1"]
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        sys.stderr.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise SystemExit(completed.returncode)


def main() -> int:
    sql, summary = build_sql()
    run_psql(sql)
    print(json.dumps({**summary, "vault_root": str(VAULT_ROOT)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
