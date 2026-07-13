#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from run_strategy_backtest import run_psql_json, sql_jsonb, sql_literal
from run_trade_journal_strategy_mining import sql_numeric, sql_text_array


RUNTIME_ROOT = Path(os.environ.get("AI_OS_RUNTIME_ROOT") or Path(__file__).absolute().parents[1])
VAULT_ROOT = Path(os.environ.get("AI_OS_VAULT_ROOT") or RUNTIME_ROOT.parent)
DOSSIER_DIR = VAULT_ROOT / "ai memory" / "03 Strategies" / "Dossiers"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:90] or "strategy-idea"


def dossier_key_for(row: dict[str, Any]) -> str:
    symbols = ",".join(str(symbol).upper() for symbol in (row.get("symbols") or []))
    source_kind = str(row.get("source_kind") or "unknown")
    source_ref = str(row.get("source_ref") or "")
    title = re.sub(r"\[[^\]]+\]", "", str(row.get("title") or "")).strip().lower()
    base = "|".join([source_kind, source_ref, symbols, title])
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]
    symbol_part = slugify(symbols or source_ref or source_kind)[:32]
    title_part = slugify(title)[:42]
    return f"dossier-{symbol_part}-{title_part}-{digest}"


def fetch_json(sql: str) -> list[dict[str, Any]]:
    return run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            {sql}
        ) rows
        """
    )


def start_run(run_key: str, actor: str) -> dict[str, Any]:
    rows = run_psql_json(
        f"""
        WITH upserted AS (
            INSERT INTO strategy.idea_dossier_build_runs (run_key, status, created_by, started_at)
            VALUES ({sql_literal(run_key)}, 'running', {sql_literal(actor)}, now())
            ON CONFLICT (run_key) DO UPDATE SET
                status = 'running',
                created_by = EXCLUDED.created_by,
                started_at = now(),
                finished_at = NULL,
                error_message = NULL
            RETURNING *
        )
        SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
        """
    )
    return rows[0]


def finish_run(run_id: int, status: str, summary: dict[str, Any], error: str | None, duration_ms: int) -> None:
    run_psql_json(
        f"""
        WITH updated AS (
            UPDATE strategy.idea_dossier_build_runs
            SET status = {sql_literal(status)},
                dossiers_seen = {int(summary.get("dossiers_seen") or 0)},
                dossiers_upserted = {int(summary.get("dossiers_upserted") or 0)},
                links_upserted = {int(summary.get("links_upserted") or 0)},
                notes_written = {int(summary.get("notes_written") or 0)},
                qdrant_index_requested = {str(bool(summary.get("qdrant_index_requested"))).lower()},
                summary = {sql_jsonb(summary)},
                error_message = {sql_literal(error) if error else 'NULL'},
                finished_at = now(),
                duration_ms = {int(duration_ms)}
            WHERE id = {int(run_id)}
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(updated)), '[]'::json)::text FROM updated
        """
    )


def discovery_rows(limit: int) -> list[dict[str, Any]]:
    return fetch_json(
        f"""
        SELECT *
        FROM strategy.v_strategy_discovery_triage_queue
        ORDER BY created_at DESC, id DESC
        LIMIT {max(1, limit)}
        """
    )


def latest_decisions(candidate_ids: list[int]) -> list[dict[str, Any]]:
    if not candidate_ids:
        return []
    return fetch_json(
        f"""
        SELECT *
        FROM strategy.v_strategy_discovery_triage_decisions
        WHERE discovery_candidate_id = ANY(ARRAY[{",".join(str(int(i)) for i in candidate_ids)}]::BIGINT[])
        ORDER BY created_at ASC
        """
    )


def group_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(dossier_key_for(row), []).append(row)
    return groups


def choose_status(rows: list[dict[str, Any]], decisions: list[dict[str, Any]]) -> tuple[str, str | None, str]:
    latest_decision = decisions[-1]["decision"] if decisions else None
    if latest_decision == "reject":
        return "rejected", latest_decision, "Rejected by triage. Reopen only if new evidence appears."
    if latest_decision == "open_committee_review":
        return "committee_review", latest_decision, "Committee review opened. Generate/verify memo before final decision."
    if latest_decision == "route_special_situation":
        return "special_situation_queue", latest_decision, "Special Situations Agent must validate event terms and evidence."
    if latest_decision == "route_quant_lab":
        return "quant_lab_queue", latest_decision, "Quant Lab must repair/validate rules, backtest, and run model validation."
    if latest_decision == "request_more_evidence":
        return "needs_more_evidence", latest_decision, "Collect missing evidence and falsification tests."
    if any(row.get("optimizer_status") == "completed" for row in rows):
        return "optimizer_completed", None, "Review optimizer evidence and decide triage/committee route."
    if any(row.get("route_to_optimizer") for row in rows):
        return "optimizer_route_available", None, "Route through optimizer or request more evidence."
    return "reference_only", None, "Convert reference into a symbol-specific strategy before testing."


def timeline_for(rows: list[dict[str, Any]], decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda item: str(item.get("created_at") or "")):
        events.append(
            {
                "event_type": "discovery",
                "at": row.get("created_at"),
                "candidate_id": row.get("id"),
                "title": row.get("title"),
                "source_kind": row.get("source_kind"),
                "source_ref": row.get("source_ref"),
                "research_gate": row.get("research_gate"),
                "optimizer_status": row.get("optimizer_status"),
                "optimization_run_id": row.get("optimization_run_id"),
            }
        )
    for decision in decisions:
        events.append(
            {
                "event_type": "triage_decision",
                "at": decision.get("created_at"),
                "candidate_id": decision.get("discovery_candidate_id"),
                "decision": decision.get("decision"),
                "routed_to_agent": decision.get("routed_to_agent"),
                "inbox_item_id": decision.get("inbox_item_id"),
                "approval_id": decision.get("approval_id"),
                "committee_review_id": decision.get("committee_review_id"),
                "notes": decision.get("decision_notes"),
            }
        )
    return sorted(events, key=lambda item: str(item.get("at") or ""))


def markdown_for(dossier: dict[str, Any]) -> str:
    symbols = ", ".join(dossier["symbols"]) if dossier["symbols"] else "None"
    timeline_lines = []
    for event in dossier["evidence_timeline"][-20:]:
        if event["event_type"] == "discovery":
            timeline_lines.append(
                f"- {event.get('at')}: discovery candidate `{event.get('candidate_id')}` from `{event.get('source_kind')}`; gate `{event.get('research_gate')}`; optimizer `{event.get('optimizer_status') or 'not_routed'}`."
            )
        else:
            timeline_lines.append(
                f"- {event.get('at')}: triage `{event.get('decision')}` routed to `{event.get('routed_to_agent') or 'committee/none'}`; inbox `{event.get('inbox_item_id') or 'none'}`; approval `{event.get('approval_id') or 'none'}`."
            )
    return "\n".join(
        [
            "---",
            f"title: {dossier['title']}",
            "type: strategy_idea_dossier",
            f"dossier_key: {dossier['dossier_key']}",
            f"status: {dossier['status']}",
            f"symbols: {json.dumps(dossier['symbols'])}",
            f"updated_at: {datetime.now(timezone.utc).isoformat()}",
            "---",
            "",
            f"# {dossier['title']}",
            "",
            f"- Dossier key: `{dossier['dossier_key']}`",
            f"- Status: `{dossier['status']}`",
            f"- Symbols: {symbols}",
            f"- Source: `{dossier['source_kind']}` / `{dossier['source_ref']}`",
            f"- Discoveries: {dossier['discovery_count']}",
            f"- Generated ideas: {dossier['generated_idea_count']}",
            f"- Optimizer runs: {dossier['optimizer_run_count']}",
            f"- Triage decisions: {dossier['triage_decision_count']}",
            f"- Committee reviews: {dossier['committee_review_count']}",
            "",
            "## Current Summary",
            "",
            dossier["summary"],
            "",
            "## Next Action",
            "",
            dossier["recommended_next_action"],
            "",
            "## Evidence Timeline",
            "",
            *(timeline_lines or ["- No evidence timeline yet."]),
            "",
            "## Safety",
            "",
            "- Broker order allowed: `false`",
            "- Autonomous live execution allowed: `false`",
            "- This dossier is research memory, not trading approval.",
            "",
        ]
    )


def write_note(dossier: dict[str, Any]) -> str:
    DOSSIER_DIR.mkdir(parents=True, exist_ok=True)
    path = DOSSIER_DIR / f"{dossier['dossier_key']}.md"
    path.write_text(markdown_for(dossier), encoding="utf-8")
    return str(path.relative_to(VAULT_ROOT))


def upsert_obsidian_note(note_path: str, dossier: dict[str, Any]) -> None:
    abs_path = VAULT_ROOT / note_path
    body = abs_path.read_text(encoding="utf-8")
    content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    run_psql_json(
        f"""
        WITH upserted AS (
            INSERT INTO knowledge.obsidian_notes (
                vault_path, note_path, title, note_type, tags,
                frontmatter, content_hash, body_summary, last_modified_at, indexed_at
            )
            VALUES (
                {sql_literal(str(VAULT_ROOT))},
                {sql_literal(note_path)},
                {sql_literal(dossier["title"])},
                'strategy_idea_dossier',
                ARRAY['ai-os','strategy','dossier']::TEXT[],
                {sql_jsonb({"dossier_key": dossier["dossier_key"], "status": dossier["status"], "symbols": dossier["symbols"]})},
                {sql_literal(content_hash)},
                {sql_literal(dossier["summary"][:1000])},
                now(),
                now()
            )
            ON CONFLICT (note_path) DO UPDATE SET
                title = EXCLUDED.title,
                note_type = EXCLUDED.note_type,
                tags = EXCLUDED.tags,
                frontmatter = EXCLUDED.frontmatter,
                content_hash = EXCLUDED.content_hash,
                body_summary = EXCLUDED.body_summary,
                last_modified_at = now(),
                indexed_at = now()
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
        """
    )


def upsert_dossier(group_key: str, rows: list[dict[str, Any]], decisions: list[dict[str, Any]], write_notes: bool) -> tuple[dict[str, Any], int, bool]:
    ordered = sorted(rows, key=lambda row: str(row.get("created_at") or ""))
    latest = ordered[-1]
    status, latest_decision, next_action = choose_status(rows, decisions)
    candidate_ids = sorted({int(row["id"]) for row in rows if row.get("id")})
    generated_ids = sorted({int(row["generated_idea_id"]) for row in rows if row.get("generated_idea_id")})
    optimizer_ids = sorted({int(row["optimizer_run_id"]) for row in rows if row.get("optimizer_run_id")})
    committee_ids = sorted({int(row["committee_review_id"]) for row in rows if row.get("committee_review_id")})
    inbox_ids = sorted({int(decision["inbox_item_id"]) for decision in decisions if decision.get("inbox_item_id")})
    symbols = sorted({str(symbol).upper() for row in rows for symbol in (row.get("symbols") or []) if str(symbol).strip()})
    title = str(latest.get("title") or "Strategy idea dossier")
    timeline = timeline_for(rows, decisions)
    summary = (
        f"{title} has {len(candidate_ids)} discovery observations, {len(generated_ids)} generated idea rows, "
        f"{len(optimizer_ids)} optimizer-linked runs, and {len(decisions)} triage decisions. "
        f"Latest status is {status}. Latest recommended next action: {next_action}"
    )
    dossier_payload = {
        "dossier_key": group_key,
        "title": title,
        "canonical_title": re.sub(r"\[[^\]]+\]", "", title).strip(),
        "source_kind": latest.get("source_kind"),
        "source_ref": latest.get("source_ref"),
        "symbols": symbols,
        "universe": latest.get("universe"),
        "timeframe": latest.get("timeframe"),
        "template": latest.get("template"),
        "status": status,
        "latest_triage_decision": latest_decision,
        "recommended_next_action": next_action,
        "discovery_count": len(candidate_ids),
        "generated_idea_count": len(generated_ids),
        "optimizer_run_count": len(optimizer_ids),
        "triage_decision_count": len(decisions),
        "committee_review_count": len(committee_ids),
        "inbox_item_count": len(inbox_ids),
        "priority_score": max(float(row.get("priority_score") or 0) for row in rows),
        "risk_score": max(float(row.get("risk_score") or 0) for row in rows),
        "first_seen_at": ordered[0].get("created_at"),
        "last_seen_at": ordered[-1].get("created_at"),
        "latest_triaged_at": decisions[-1].get("created_at") if decisions else None,
        "summary": summary,
        "evidence_timeline": timeline,
        "linked_candidate_ids": candidate_ids,
        "linked_generated_idea_ids": generated_ids,
        "linked_optimizer_run_ids": optimizer_ids,
        "linked_committee_review_ids": committee_ids,
    }
    note_path = write_note(dossier_payload) if write_notes else None
    if note_path:
        dossier_payload["note_path"] = note_path
    rows_out = run_psql_json(
        f"""
        WITH upserted AS (
            INSERT INTO strategy.idea_dossiers (
                dossier_key, title, canonical_title, source_kind, source_ref,
                symbols, universe, timeframe, template, status,
                latest_triage_decision, recommended_next_action,
                discovery_count, generated_idea_count, optimizer_run_count,
                triage_decision_count, committee_review_count, inbox_item_count,
                priority_score, risk_score, first_seen_at, last_seen_at,
                latest_triaged_at, summary, evidence_timeline,
                linked_candidate_ids, linked_generated_idea_ids,
                linked_optimizer_run_ids, linked_committee_review_ids,
                note_path, qdrant_index_status, updated_at
            )
            VALUES (
                {sql_literal(group_key)},
                {sql_literal(dossier_payload["title"])},
                {sql_literal(dossier_payload["canonical_title"])},
                {sql_literal(dossier_payload["source_kind"])},
                {sql_literal(dossier_payload["source_ref"])},
                {sql_text_array(symbols)},
                {sql_literal(dossier_payload["universe"])},
                {sql_literal(dossier_payload["timeframe"])},
                {sql_literal(dossier_payload["template"])},
                {sql_literal(status)},
                {sql_literal(latest_decision)},
                {sql_literal(next_action)},
                {len(candidate_ids)},
                {len(generated_ids)},
                {len(optimizer_ids)},
                {len(decisions)},
                {len(committee_ids)},
                {len(inbox_ids)},
                {sql_numeric(dossier_payload["priority_score"])},
                {sql_numeric(dossier_payload["risk_score"])},
                {sql_literal(dossier_payload["first_seen_at"])}::timestamptz,
                {sql_literal(dossier_payload["last_seen_at"])}::timestamptz,
                {sql_literal(dossier_payload["latest_triaged_at"])}::timestamptz,
                {sql_literal(summary)},
                {sql_jsonb(timeline)},
                ARRAY[{",".join(str(i) for i in candidate_ids)}]::BIGINT[],
                ARRAY[{",".join(str(i) for i in generated_ids)}]::BIGINT[],
                ARRAY[{",".join(str(i) for i in optimizer_ids)}]::BIGINT[],
                ARRAY[{",".join(str(i) for i in committee_ids)}]::BIGINT[],
                {sql_literal(note_path)},
                'pending',
                now()
            )
            ON CONFLICT (dossier_key) DO UPDATE SET
                title = EXCLUDED.title,
                canonical_title = EXCLUDED.canonical_title,
                source_kind = EXCLUDED.source_kind,
                source_ref = EXCLUDED.source_ref,
                symbols = EXCLUDED.symbols,
                universe = EXCLUDED.universe,
                timeframe = EXCLUDED.timeframe,
                template = EXCLUDED.template,
                status = EXCLUDED.status,
                latest_triage_decision = EXCLUDED.latest_triage_decision,
                recommended_next_action = EXCLUDED.recommended_next_action,
                discovery_count = EXCLUDED.discovery_count,
                generated_idea_count = EXCLUDED.generated_idea_count,
                optimizer_run_count = EXCLUDED.optimizer_run_count,
                triage_decision_count = EXCLUDED.triage_decision_count,
                committee_review_count = EXCLUDED.committee_review_count,
                inbox_item_count = EXCLUDED.inbox_item_count,
                priority_score = EXCLUDED.priority_score,
                risk_score = EXCLUDED.risk_score,
                first_seen_at = EXCLUDED.first_seen_at,
                last_seen_at = EXCLUDED.last_seen_at,
                latest_triaged_at = EXCLUDED.latest_triaged_at,
                summary = EXCLUDED.summary,
                evidence_timeline = EXCLUDED.evidence_timeline,
                linked_candidate_ids = EXCLUDED.linked_candidate_ids,
                linked_generated_idea_ids = EXCLUDED.linked_generated_idea_ids,
                linked_optimizer_run_ids = EXCLUDED.linked_optimizer_run_ids,
                linked_committee_review_ids = EXCLUDED.linked_committee_review_ids,
                note_path = coalesce(EXCLUDED.note_path, strategy.idea_dossiers.note_path),
                qdrant_index_status = 'pending',
                updated_at = now()
            RETURNING id, dossier_key, title, status, note_path
        )
        SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
        """
    )
    dossier_row = rows_out[0]
    if note_path:
        upsert_obsidian_note(note_path, dossier_payload)
    link_count = upsert_links(int(dossier_row["id"]), rows, decisions)
    return dossier_row, link_count, bool(note_path)


def upsert_links(dossier_id: int, rows: list[dict[str, Any]], decisions: list[dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        for source_table, source_id, relation in [
            ("strategy.strategy_discovery_candidates", row.get("id"), "discovery_candidate"),
            ("strategy.generated_ideas", row.get("generated_idea_id"), "generated_idea"),
            ("strategy.user_defined_optimizer_runs", row.get("optimizer_run_id"), "optimizer_run"),
        ]:
            if not source_id:
                continue
            count += upsert_link(dossier_id, source_table, str(source_id), relation, row)
    for decision in decisions:
        count += upsert_link(dossier_id, "strategy.strategy_discovery_triage_decisions", str(decision["id"]), "triage_decision", decision)
        if decision.get("committee_review_id"):
            count += upsert_link(dossier_id, "strategy.committee_reviews", str(decision["committee_review_id"]), "committee_review", decision)
        if decision.get("approval_id"):
            count += upsert_link(dossier_id, "agent.approvals", str(decision["approval_id"]), "approval", decision)
    return count


def upsert_link(dossier_id: int, source_table: str, source_id: str, relation_type: str, evidence: dict[str, Any]) -> int:
    rows = run_psql_json(
        f"""
        WITH upserted AS (
            INSERT INTO strategy.idea_dossier_links (
                dossier_id, source_table, source_id, relation_type, evidence
            )
            VALUES (
                {int(dossier_id)}, {sql_literal(source_table)}, {sql_literal(source_id)},
                {sql_literal(relation_type)}, {sql_jsonb(evidence)}
            )
            ON CONFLICT (dossier_id, source_table, source_id, relation_type) DO UPDATE SET
                evidence = EXCLUDED.evidence
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
        """
    )
    return 1 if rows else 0


def build(args: argparse.Namespace) -> dict[str, Any]:
    run = start_run(args.run_key, args.actor)
    started = time.monotonic()
    rows = discovery_rows(args.limit)
    groups = group_rows(rows)
    dossiers: list[dict[str, Any]] = []
    total_links = 0
    notes_written = 0
    for key, group in sorted(groups.items(), key=lambda item: len(item[1]), reverse=True)[: args.max_dossiers]:
        candidate_ids = [int(row["id"]) for row in group]
        decisions = latest_decisions(candidate_ids)
        dossier, link_count, note_written = upsert_dossier(key, group, decisions, not args.no_notes)
        dossiers.append(dossier)
        total_links += link_count
        notes_written += 1 if note_written else 0
    duration_ms = int((time.monotonic() - started) * 1000)
    summary = {
        "dossiers_seen": len(groups),
        "dossiers_upserted": len(dossiers),
        "links_upserted": total_links,
        "notes_written": notes_written,
        "qdrant_index_requested": False,
        "seed_data_allowed": False,
        "live_execution_allowed": False,
        "sample_dossiers": dossiers[:5],
    }
    finish_run(int(run["id"]), "completed", summary, None, duration_ms)
    return {"run_key": args.run_key, "status": "completed", "summary": summary, "dossiers": dossiers}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build persistent strategy idea dossiers from discovered ideas and triage decisions.")
    parser.add_argument("--run-key", default=f"strategy_dossier_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
    parser.add_argument("--actor", default="Strategy Dossier Agent")
    parser.add_argument("--limit", type=int, default=250)
    parser.add_argument("--max-dossiers", type=int, default=100)
    parser.add_argument("--no-notes", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(args), indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
