#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


RUNTIME_ROOT = Path(os.environ.get("AI_OS_RUNTIME_ROOT") or Path(__file__).absolute().parents[1])
VAULT_ROOT = Path(os.environ.get("AI_OS_VAULT_ROOT") or RUNTIME_ROOT.parent)
SCOPE_KEY = os.environ.get("AI_OS_RESEARCH_SCOPE_KEY", "owner:devarsh")

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
    run_key = "obsidian:" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    statements = [
        "BEGIN;",
        f"SET LOCAL ai_os.scope_key={sql_quote(SCOPE_KEY)};",
        "SET LOCAL ROLE ai_os_research_runtime;",
        f"""INSERT INTO knowledge.index_runs
            (scope_key,run_key,run_kind,run_mode,status,created_by,metadata)
            VALUES ({sql_quote(SCOPE_KEY)},{sql_quote(run_key)},'obsidian','incremental','running',
                    'Research Knowledge Indexer',
                    {jsonb_quote({'vault_root': str(VAULT_ROOT), 'private_storage': 'external_ssd'})});""",
        "RESET ROLE;",
    ]
    notes = []
    link_count = 0

    for path in iter_markdown_files():
        relative = path.relative_to(VAULT_ROOT)
        note_path = str(relative)
        note_key = "obsidian:" + content_hash(note_path.lower())[:40]
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
    note_key,
    scope_key,
    privacy_class,
    title,
    note_type,
    tags,
    frontmatter,
    content_hash,
    body_summary,
    last_modified_at,
    indexed_at,
    last_index_run_id,
    deleted_at
)
VALUES (
    {sql_quote(str(VAULT_ROOT))},
    {sql_quote(note_path)},
    {sql_quote(note_key)},
    {sql_quote(SCOPE_KEY)},
    'local_private',
    {sql_quote(title)},
    {sql_quote(note_type)},
    {text_array(tags)},
    {jsonb_quote(frontmatter)},
    {sql_quote(content_hash(text))},
    {sql_quote(summarize_body(body))},
    {sql_quote(modified_at)}::timestamptz,
    now(),
    (SELECT id FROM knowledge.index_runs WHERE scope_key={sql_quote(SCOPE_KEY)} AND run_key={sql_quote(run_key)}),
    NULL
)
ON CONFLICT (note_path) DO UPDATE SET
    vault_path = EXCLUDED.vault_path,
    note_key = EXCLUDED.note_key,
    scope_key = EXCLUDED.scope_key,
    privacy_class = EXCLUDED.privacy_class,
    title = EXCLUDED.title,
    note_type = EXCLUDED.note_type,
    tags = EXCLUDED.tags,
    frontmatter = EXCLUDED.frontmatter,
    content_hash = EXCLUDED.content_hash,
    body_summary = EXCLUDED.body_summary,
    last_modified_at = EXCLUDED.last_modified_at,
    indexed_at = now(),
    last_index_run_id = EXCLUDED.last_index_run_id,
    deleted_at = NULL;

DELETE FROM knowledge.note_links
WHERE from_note_id=(
    SELECT id FROM knowledge.obsidian_notes
    WHERE note_path={sql_quote(note_path)} AND scope_key={sql_quote(SCOPE_KEY)}
    LIMIT 1
);
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

    note_paths_sql = ",".join(sql_quote(path) for path in notes) or "NULL"
    statements.extend(
        [
            f"""UPDATE knowledge.obsidian_notes
                SET deleted_at=now()
                WHERE scope_key={sql_quote(SCOPE_KEY)} AND deleted_at IS NULL
                  AND note_path NOT IN ({note_paths_sql});""",
            f"SET LOCAL ai_os.scope_key={sql_quote(SCOPE_KEY)};",
            "SET LOCAL ROLE ai_os_research_runtime;",
            f"""UPDATE knowledge.index_runs
                SET status='completed',finished_at=now(),
                    counts={jsonb_quote({'notes_indexed': len(notes), 'links_indexed': link_count})}
                WHERE scope_key={sql_quote(SCOPE_KEY)} AND run_key={sql_quote(run_key)};""",
            "RESET ROLE;",
            "COMMIT;",
        ]
    )
    return "\n".join(statements), {
        "run_key": run_key,
        "scope_key": SCOPE_KEY,
        "notes_indexed": len(notes),
        "links_indexed": link_count,
    }


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
