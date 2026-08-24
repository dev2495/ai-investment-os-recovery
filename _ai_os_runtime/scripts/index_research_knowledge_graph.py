#!/usr/bin/env python3
"""Incrementally materialize the governed Research Desk knowledge graph.

Source reads use the local transaction database. All graph writes execute as the
RLS-constrained research runtime role with a server-owned scope. The job never
changes Obsidian content and never sends private content to a remote model.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any


SCOPE_KEY = os.environ.get("AI_OS_RESEARCH_SCOPE_KEY", "owner:devarsh")
ACTOR = "Research Knowledge Graph Indexer"


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return sql_literal(json.dumps(value, sort_keys=True, default=str)) + "::jsonb"


def run_psql(sql: str, *, tuples_only: bool = False) -> str:
    command = [
        "docker", "exec", "-i", "ai_os_postgres", "psql", "-q", "-U", "ai_os", "-d", "ai_os",
        "-v", "ON_ERROR_STOP=1",
    ]
    if tuples_only:
        command.extend(["-t", "-A"])
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return completed.stdout.strip()


def fetch_rows(sql: str) -> list[dict[str, Any]]:
    wrapped = f"SELECT coalesce(json_agg(row_to_json(q)),'[]'::json) FROM ({sql}) q;"
    raw = run_psql(wrapped, tuples_only=True)
    return json.loads(raw or "[]")


def node_key(kind: str, identity: object) -> str:
    return f"{kind}:" + hashlib.sha256(str(identity).encode("utf-8")).hexdigest()[:40]


def normalized_note_targets(note: dict[str, Any]) -> set[str]:
    note_path = str(note.get("note_path") or "").strip()
    title = str(note.get("title") or "").strip()
    stem = PurePosixPath(note_path).stem
    return {value.casefold() for value in (note_path, note_path.removesuffix(".md"), stem, title) if value}


def build_graph_sql() -> tuple[str, dict[str, int | str]]:
    companies = fetch_rows(
        "SELECT id,company_key,legal_name,display_name,primary_symbol,primary_exchange,status "
        "FROM research.companies WHERE status='active' ORDER BY id"
    )
    cases = fetch_rows(
        "SELECT id,case_key,company_id,company_name,ticker,exchange,status,decision_readiness,updated_at "
        "FROM research.research_cases WHERE status<>'cancelled' ORDER BY id"
    )
    notes = fetch_rows(
        "SELECT id,note_key,note_path,title,note_type,tags,frontmatter,content_hash,last_modified_at "
        "FROM knowledge.obsidian_notes "
        f"WHERE scope_key={sql_literal(SCOPE_KEY)} AND deleted_at IS NULL ORDER BY id"
    )
    links = fetch_rows(
        "SELECT link.id,link.from_note_id,link.to_note_path,link.link_text,link.link_type "
        "FROM knowledge.note_links link JOIN knowledge.obsidian_notes note ON note.id=link.from_note_id "
        f"WHERE note.scope_key={sql_literal(SCOPE_KEY)} AND note.deleted_at IS NULL ORDER BY link.id"
    )
    run_key = "graph:" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    statements = [
        "BEGIN;",
        f"SET LOCAL ai_os.scope_key={sql_literal(SCOPE_KEY)};",
        "SET LOCAL ROLE ai_os_research_runtime;",
        f"""INSERT INTO knowledge.index_runs
            (scope_key,run_key,run_kind,run_mode,status,input_hash,created_by,metadata)
            VALUES ({sql_literal(SCOPE_KEY)},{sql_literal(run_key)},'graph','incremental','running',
                    {sql_literal(hashlib.sha256(json.dumps({'companies': companies, 'cases': cases, 'notes': notes, 'links': links}, sort_keys=True, default=str).encode()).hexdigest())},
                    {sql_literal(ACTOR)},'{{"private_storage":"external_ssd","remote_model_used":false}}'::jsonb)
            ON CONFLICT (scope_key,run_key) DO NOTHING;""",
    ]
    node_key_by_note_id: dict[int, str] = {}
    note_lookup: dict[str, int] = {}
    company_node_by_id: dict[int, str] = {}

    for company in companies:
        key = node_key("company", company["id"])
        company_node_by_id[int(company["id"])] = key
        label = company.get("display_name") or company.get("legal_name") or company.get("primary_symbol")
        metadata = {
            "company_key": company.get("company_key"),
            "symbol": company.get("primary_symbol"),
            "exchange": company.get("primary_exchange"),
        }
        statements.append(
            f"""INSERT INTO knowledge.graph_nodes
                (scope_key,node_key,node_type,label,source_schema,source_table,source_pk,company_id,
                 privacy_class,authority,content_hash,metadata,created_by)
                VALUES ({sql_literal(SCOPE_KEY)},{sql_literal(key)},'company',{sql_literal(label)},
                        'research','companies',{sql_literal(company['id'])},{int(company['id'])},
                        'public','primary',{sql_literal(hashlib.sha256(json.dumps(metadata,sort_keys=True).encode()).hexdigest())},
                        {sql_jsonb(metadata)},{sql_literal(ACTOR)})
                ON CONFLICT (scope_key,node_key) DO UPDATE SET label=EXCLUDED.label,
                    content_hash=EXCLUDED.content_hash,metadata=EXCLUDED.metadata,deleted_at=NULL,updated_at=now();"""
        )

    for note in notes:
        key = node_key("obsidian_note", note["id"])
        node_key_by_note_id[int(note["id"])] = key
        for target in normalized_note_targets(note):
            note_lookup.setdefault(target, int(note["id"]))
        metadata = {
            "note_path": note.get("note_path"),
            "note_type": note.get("note_type"),
            "tags": note.get("tags") or [],
            "last_modified_at": note.get("last_modified_at"),
        }
        statements.append(
            f"""INSERT INTO knowledge.graph_nodes
                (scope_key,node_key,node_type,label,source_schema,source_table,source_pk,
                 privacy_class,authority,content_hash,metadata,created_by)
                VALUES ({sql_literal(SCOPE_KEY)},{sql_literal(key)},'obsidian_note',
                        {sql_literal(note.get('title') or note.get('note_path'))},'knowledge','obsidian_notes',
                        {sql_literal(note['id'])},'local_private','user_supplied',
                        {sql_literal(note.get('content_hash'))},{sql_jsonb(metadata)},{sql_literal(ACTOR)})
                ON CONFLICT (scope_key,node_key) DO UPDATE SET label=EXCLUDED.label,
                    content_hash=EXCLUDED.content_hash,metadata=EXCLUDED.metadata,deleted_at=NULL,updated_at=now();"""
        )

    for case in cases:
        key = node_key("research_case", case["id"])
        label = case.get("company_name") or case.get("ticker") or case.get("case_key")
        metadata = {
            "case_key": case.get("case_key"), "status": case.get("status"),
            "decision_readiness": case.get("decision_readiness"), "updated_at": case.get("updated_at"),
        }
        company_id = int(case["company_id"]) if case.get("company_id") is not None else None
        statements.append(
            f"""INSERT INTO knowledge.graph_nodes
                (scope_key,node_key,node_type,label,source_schema,source_table,source_pk,company_id,
                 privacy_class,authority,metadata,created_by)
                VALUES ({sql_literal(SCOPE_KEY)},{sql_literal(key)},'research_case',{sql_literal(label)},
                        'research','research_cases',{sql_literal(case['id'])},{company_id if company_id else 'NULL'},
                        'local_private','agent_interpretation',{sql_jsonb(metadata)},{sql_literal(ACTOR)})
                ON CONFLICT (scope_key,node_key) DO UPDATE SET label=EXCLUDED.label,
                    company_id=EXCLUDED.company_id,metadata=EXCLUDED.metadata,deleted_at=NULL,updated_at=now();"""
        )
        if company_id and company_id in company_node_by_id:
            edge_key = f"case-company:{case['id']}:{company_id}"
            statements.append(
                f"""INSERT INTO knowledge.graph_edges
                    (scope_key,edge_key,from_node_id,to_node_id,edge_type,source_kind,source_ref,
                     available_at,confidence,metadata,created_by)
                    SELECT {sql_literal(SCOPE_KEY)},{sql_literal(edge_key)},case_node.id,company_node.id,
                           'RESEARCHES','database_relation',{sql_literal(case.get('case_key'))},now(),1.0,
                           '{{"deterministic":true}}'::jsonb,{sql_literal(ACTOR)}
                    FROM knowledge.graph_nodes case_node,knowledge.graph_nodes company_node
                    WHERE case_node.scope_key={sql_literal(SCOPE_KEY)} AND case_node.node_key={sql_literal(key)}
                      AND company_node.scope_key={sql_literal(SCOPE_KEY)} AND company_node.node_key={sql_literal(company_node_by_id[company_id])}
                    ON CONFLICT (scope_key,edge_key) DO UPDATE SET deleted_at=NULL,available_at=now(),updated_at=now();"""
            )

    resolved_links = 0
    unresolved_links = 0
    for link in links:
        raw_target = str(link.get("to_note_path") or "").strip()
        normalized = raw_target.removesuffix(".md").casefold()
        target_note_id = note_lookup.get(normalized) or note_lookup.get(PurePosixPath(normalized).stem)
        from_key = node_key_by_note_id.get(int(link["from_note_id"]))
        if target_note_id and from_key and target_note_id != int(link["from_note_id"]):
            resolved_links += 1
            to_key = node_key_by_note_id[target_note_id]
            edge_key = f"obsidian-link:{link['id']}"
            statements.append(
                f"""INSERT INTO knowledge.graph_edges
                    (scope_key,edge_key,from_node_id,to_node_id,edge_type,source_kind,source_ref,
                     citation_locator,available_at,confidence,metadata,created_by)
                    SELECT {sql_literal(SCOPE_KEY)},{sql_literal(edge_key)},source.id,target.id,
                           'LINKS_TO','obsidian_wikilink',{sql_literal(link['id'])},
                           {sql_jsonb({'target': raw_target, 'link_text': link.get('link_text')})},now(),1.0,
                           '{{"deterministic":true}}'::jsonb,{sql_literal(ACTOR)}
                    FROM knowledge.graph_nodes source,knowledge.graph_nodes target
                    WHERE source.scope_key={sql_literal(SCOPE_KEY)} AND source.node_key={sql_literal(from_key)}
                      AND target.scope_key={sql_literal(SCOPE_KEY)} AND target.node_key={sql_literal(to_key)}
                    ON CONFLICT (scope_key,edge_key) DO UPDATE SET citation_locator=EXCLUDED.citation_locator,
                        deleted_at=NULL,available_at=now(),updated_at=now();"""
            )
        elif from_key:
            unresolved_links += 1
            link_key = f"obsidian-unresolved:{link['id']}"
            statements.append(
                f"""INSERT INTO knowledge.unresolved_links
                    (scope_key,link_key,from_note_id,raw_target,normalized_target,link_text,reason,status,
                     index_run_id,metadata)
                    VALUES ({sql_literal(SCOPE_KEY)},{sql_literal(link_key)},{int(link['from_note_id'])},
                            {sql_literal(raw_target)},{sql_literal(normalized)},{sql_literal(link.get('link_text'))},
                            'no exact scoped note target','open',
                            (SELECT id FROM knowledge.index_runs WHERE scope_key={sql_literal(SCOPE_KEY)} AND run_key={sql_literal(run_key)}),
                            '{{"deterministic":true}}'::jsonb)
                    ON CONFLICT (scope_key,link_key) DO UPDATE SET raw_target=EXCLUDED.raw_target,
                        normalized_target=EXCLUDED.normalized_target,link_text=EXCLUDED.link_text,
                        reason=EXCLUDED.reason,status='open',resolved_node_id=NULL,resolved_note_id=NULL,
                        index_run_id=EXCLUDED.index_run_id,last_seen_at=now(),
                        occurrence_count=knowledge.unresolved_links.occurrence_count+1,updated_at=now();"""
            )

    counts = {
        "companies": len(companies), "research_cases": len(cases), "notes": len(notes),
        "links": len(links), "resolved_links": resolved_links, "unresolved_links": unresolved_links,
    }
    statements.extend(
        [
            f"""UPDATE knowledge.index_runs SET status='completed',finished_at=now(),counts={sql_jsonb(counts)}
                WHERE scope_key={sql_literal(SCOPE_KEY)} AND run_key={sql_literal(run_key)};""",
            "RESET ROLE;",
            "COMMIT;",
        ]
    )
    return "\n".join(statements), {"run_key": run_key, "scope_key": SCOPE_KEY, **counts}


def main() -> int:
    sql, summary = build_graph_sql()
    run_psql(sql)
    print(json.dumps({"status": "completed", **summary, "broker_write_allowed": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
