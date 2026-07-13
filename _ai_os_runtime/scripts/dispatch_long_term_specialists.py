#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUNTIME_ROOT = Path(os.environ.get("AI_OS_RUNTIME_ROOT") or Path(__file__).absolute().parents[1])
VAULT_ROOT = Path(os.environ.get("AI_OS_VAULT_ROOT") or RUNTIME_ROOT.parent)
DISPATCH_DIR = VAULT_ROOT / "ai memory" / "02 Portfolio" / "Long-Term Specialist Dispatches"


MODULES = [
    {
        "module_key": "business_model",
        "module_name": "Business Model Checklist",
        "assignment_type": "checklist",
        "agent_name": "Company Analyst",
        "skill_key": "long_term_business_model_review",
        "required_sources": ["research_packet", "company_filings", "annual_report_or_investor_presentation"],
        "output": "Source-backed business model, segment economics, pricing power, unit economics, and missing evidence.",
    },
    {
        "module_key": "moat_scorecard",
        "module_name": "Moat Scorecard",
        "assignment_type": "checklist",
        "agent_name": "Company Analyst",
        "skill_key": "long_term_business_model_review",
        "required_sources": ["research_packet", "company_filings", "competitor_or_industry_sources"],
        "output": "Moat evidence, durability, weakening signs, and source-backed score recommendation.",
    },
    {
        "module_key": "industry_structure",
        "module_name": "Industry Structure Checklist",
        "assignment_type": "checklist",
        "agent_name": "Industry Analyst",
        "skill_key": "long_term_industry_review",
        "required_sources": ["research_packet", "industry_sources", "company_filings"],
        "output": "Industry structure, growth runway, competitive intensity, customer/supplier power, disruption risk.",
    },
    {
        "module_key": "management_scorecard",
        "module_name": "Management Scorecard",
        "assignment_type": "checklist",
        "agent_name": "Management Analyst",
        "skill_key": "long_term_management_governance_review",
        "required_sources": ["annual_report", "corporate_filings", "promoter_governance_sources"],
        "output": "Promoter quality, incentives, capital allocation history, governance concerns.",
    },
    {
        "module_key": "governance_scorecard",
        "module_name": "Governance Scorecard",
        "assignment_type": "checklist",
        "agent_name": "Management Analyst",
        "skill_key": "long_term_management_governance_review",
        "required_sources": ["annual_report", "corporate_filings", "related_party_disclosures"],
        "output": "Board, auditor, related-party, remuneration, pledging, and minority treatment review.",
    },
    {
        "module_key": "capital_allocation",
        "module_name": "Capital Allocation Scorecard",
        "assignment_type": "checklist",
        "agent_name": "Management Analyst",
        "skill_key": "long_term_management_governance_review",
        "required_sources": ["financial_history", "annual_reports", "corporate_action_history"],
        "output": "Capital allocation track record, reinvestment, M&A, dividends, buybacks, debt use.",
    },
    {
        "module_key": "financial_quality",
        "module_name": "Financial Statement Quality Scorecard",
        "assignment_type": "checklist",
        "agent_name": "Financial Statement Analyst",
        "skill_key": "long_term_financial_quality_review",
        "required_sources": ["audited_financials", "cash_flow_statement", "balance_sheet_history"],
        "output": "Revenue quality, margin bridge, OCF/PAT, FCF, working capital, debt, liquidity, contingencies.",
    },
    {
        "module_key": "forensic_accounting",
        "module_name": "Forensic Accounting Checklist",
        "assignment_type": "checklist",
        "agent_name": "Forensic Accounting Agent",
        "skill_key": "long_term_forensic_accounting_review",
        "required_sources": ["audited_financials", "notes_to_accounts", "auditor_notes", "related_party_disclosures"],
        "output": "Accounting red flags, receivables/inventory spikes, related parties, auditor issues, unusual items.",
    },
    {
        "module_key": "valuation_suite",
        "module_name": "Valuation Model Suite",
        "assignment_type": "valuation",
        "agent_name": "Valuation Agent",
        "skill_key": "long_term_valuation_review",
        "required_sources": ["latest_price", "audited_financials", "growth_margin_reinvestment_assumptions"],
        "output": "DCF, reverse DCF, peer, historical, scenarios, expected CAGR, Monte Carlo source requirements.",
    },
    {
        "module_key": "bear_case",
        "module_name": "Bear Case And Thesis Killers",
        "assignment_type": "bear_case",
        "agent_name": "Bear Case Agent",
        "skill_key": "long_term_bear_case_review",
        "required_sources": ["research_packet", "checklist_findings", "valuation_findings", "risk_evidence"],
        "output": "Disconfirming evidence, thesis killers, downside path, and what would prove us wrong.",
    },
    {
        "module_key": "portfolio_fit",
        "module_name": "Portfolio Fit And Suitability",
        "assignment_type": "portfolio_fit",
        "agent_name": "Portfolio Fit Agent",
        "skill_key": "long_term_portfolio_fit_review",
        "required_sources": ["book_positions", "client_exposure", "symbol_book_exposure", "risk_limits"],
        "output": "Client suitability, concentration, liquidity, book fit, cross-book conflict, and risk follow-up.",
    },
    {
        "module_key": "risk_review",
        "module_name": "Independent Risk Review",
        "assignment_type": "risk_review",
        "agent_name": "Risk Agent",
        "skill_key": "long_term_portfolio_fit_review",
        "required_sources": ["book_positions", "source_gaps", "committee_review", "portfolio_exposure"],
        "output": "Independent risk challenge, concentration, liquidity, client suitability, and blocking conditions.",
    },
]


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


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


def clean(value: object, fallback: str = "n/a") -> str:
    if value is None:
        return fallback
    text = re.sub(r"\s+", " ", str(value).replace("\x00", " ")).strip()
    return text or fallback


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-").lower()
    return slug[:90] or "long-term-specialist-dispatch"


def fetch_context(thesis_id: int | None, review_id: int | None) -> dict[str, Any]:
    if review_id:
        rows = run_psql_json(
            f"""
            SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
            FROM (
                SELECT committee.*, committee.holding_thesis_id AS resolved_holding_thesis_id
                FROM portfolio.v_long_term_committee_queue committee
                WHERE id = {review_id}
            ) rows
            """
        )
        if not rows:
            raise ValueError(f"long-term committee review {review_id} not found")
        row = rows[0]
        thesis_id = int(row["holding_thesis_id"])
        committee = row
    else:
        committee = {}
    if not thesis_id:
        raise ValueError("holding_thesis_id or long_term_committee_review_id is required")
    thesis_rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT *
            FROM portfolio.v_long_term_thesis_control
            WHERE id = {int(thesis_id)}
        ) rows
        """
    )
    if not thesis_rows:
        raise ValueError(f"holding thesis {thesis_id} not found")
    packet_rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT id, update_kind, status, note_path, source_summary, created_at
            FROM portfolio.v_long_term_research_updates
            WHERE holding_thesis_id = {int(thesis_id)}
              AND update_kind = 'research_packet'
            ORDER BY created_at DESC
            LIMIT 3
        ) rows
        """
    )
    return {"thesis": thesis_rows[0], "committee": committee, "packets": packet_rows}


def build_note(context: dict[str, Any], assignments: list[dict[str, Any]], actor: str) -> str:
    thesis = context["thesis"]
    symbol = clean(thesis.get("symbol")).upper()
    lines = [
        f"# Long-Term Specialist Dispatch - {symbol}",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Generated by: {actor}",
        f"Thesis id: `{thesis.get('id')}`",
        f"Committee review id: `{clean(context.get('committee', {}).get('id'))}`",
        "",
        "## Dispatch Guardrail",
        "",
        "These are research assignments only. They do not authorize buy, add, trim, sell, hedge, broker order, or live strategy action.",
        "",
        "## Source Context",
        "",
        f"- Thesis status: `{clean(thesis.get('thesis_status'))}`",
        f"- Decision status: `{clean(thesis.get('decision_status'))}`",
        f"- Long-term exposure: `{clean(thesis.get('long_term_gross_exposure'))}`",
        f"- Research packet count sampled: `{len(context.get('packets') or [])}`",
        "",
        "## Assignments",
        "",
    ]
    for assignment in assignments:
        lines.append(
            f"- `{assignment['assignment_key']}` -> {assignment['agent_name']} / {assignment['module_name']} "
            f"status `{assignment['status']}`, task `{assignment.get('task_id')}`, inbox `{assignment.get('inbox_id')}`"
        )
    return "\n".join(lines) + "\n"


def insert_note(note_path: Path, title: str, summary: str) -> None:
    rel_path = str(note_path.relative_to(VAULT_ROOT))
    run_psql_json(
        f"""
        WITH upserted AS (
            INSERT INTO knowledge.obsidian_notes (
                vault_path, note_path, title, note_type, tags, frontmatter,
                content_hash, body_summary, last_modified_at, indexed_at
            )
            VALUES (
                {sql_literal(str(VAULT_ROOT))},
                {sql_literal(rel_path)},
                {sql_literal(title)},
                'long_term_specialist_dispatch',
                ARRAY['ai-os','long-term','specialist-dispatch']::text[],
                {sql_jsonb({'source': 'dispatch_long_term_specialists.py'})},
                md5({sql_literal(note_path.read_text())}),
                {sql_literal(summary)},
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
                last_modified_at = EXCLUDED.last_modified_at,
                indexed_at = now()
            RETURNING *
        )
        SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
        """
    )


def dispatch(context: dict[str, Any], actor: str) -> list[dict[str, Any]]:
    thesis = context["thesis"]
    thesis_id = int(thesis["id"])
    symbol = clean(thesis.get("symbol")).upper()
    review_id = context.get("committee", {}).get("id")
    latest_packet = (context.get("packets") or [{}])[0] if context.get("packets") else {}
    evidence = [
        {"table": "portfolio.holding_theses", "id": thesis_id},
        {"view": "portfolio.v_long_term_thesis_control", "id": thesis_id},
        {"latest_research_packet": latest_packet.get("note_path")},
        {"committee_review_id": review_id},
        {"capital_action_allowed": False},
        {"live_execution_allowed": False},
    ]
    assignments: list[dict[str, Any]] = []
    for module in MODULES:
        assignment_key = f"lt-{thesis_id}-{module['module_key']}-{safe_slug(module['agent_name'])}"
        objective = (
            f"Complete {module['module_name']} for {symbol} with source-backed evidence. "
            "If sources are missing, keep status source_required and list exact required sources. "
            "Do not recommend buy/sell/add/trim/hedge action."
        )
        assignment_rows = run_psql_json(
            f"""
            WITH rows AS (
                INSERT INTO portfolio.long_term_specialist_assignments (
                    assignment_key, holding_thesis_id, committee_review_id,
                    module_key, module_name, assignment_type, agent_name, skill_key,
                    status, source_status, required_sources, evidence,
                    output_requirements, created_by, updated_at
                )
                VALUES (
                    {sql_literal(assignment_key)},
                    {thesis_id},
                    {sql_literal(review_id)},
                    {sql_literal(module['module_key'])},
                    {sql_literal(module['module_name'])},
                    {sql_literal(module['assignment_type'])},
                    {sql_literal(module['agent_name'])},
                    {sql_literal(module['skill_key'])},
                    'queued',
                    'source_required',
                    {sql_jsonb(module['required_sources'])},
                    {sql_jsonb(evidence)},
                    {sql_jsonb({'expected_output': module['output'], 'capital_action_allowed': False, 'live_execution_allowed': False})},
                    {sql_literal(actor)},
                    now()
                )
                ON CONFLICT (holding_thesis_id, module_key, agent_name) DO UPDATE SET
                    committee_review_id = EXCLUDED.committee_review_id,
                    status = CASE
                        WHEN portfolio.long_term_specialist_assignments.status IN ('completed','needs_review') THEN portfolio.long_term_specialist_assignments.status
                        ELSE 'queued'
                    END,
                    source_status = EXCLUDED.source_status,
                    required_sources = EXCLUDED.required_sources,
                    evidence = EXCLUDED.evidence,
                    output_requirements = EXCLUDED.output_requirements,
                    updated_at = now()
                RETURNING *
            )
            SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text FROM rows
            """
        )
        if not assignment_rows:
            continue
        row = assignment_rows[0]
        task_rows = run_psql_json(
            f"""
            WITH rows AS (
                INSERT INTO agent.tasks (
                    title, objective, owner_agent, status, priority, approval_required,
                    source_kind, source_ref, output_format, evidence
                )
                VALUES (
                    {sql_literal(f'{symbol}: {module["module_name"]}')},
                    {sql_literal(objective)},
                    {sql_literal(module['agent_name'])},
                    'queued',
                    'high',
                    false,
                    'portfolio.long_term_specialist_assignments',
                    {sql_literal(assignment_key)},
                    {sql_literal(module['assignment_type'])},
                    {sql_jsonb(evidence)}
                )
                ON CONFLICT (title, owner_agent, source_kind, source_ref)
                WHERE status = ANY (ARRAY['queued'::text, 'in_progress'::text, 'blocked'::text])
                  AND source_kind IS NOT NULL
                  AND source_ref IS NOT NULL
                DO UPDATE SET
                    objective = EXCLUDED.objective,
                    evidence = EXCLUDED.evidence,
                    updated_at = now()
                RETURNING id
            )
            SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text FROM rows
            """
        )
        if not task_rows:
            continue
        task_id = task_rows[0]["id"]
        inbox_rows = run_psql_json(
            f"""
            WITH rows AS (
                INSERT INTO agent.inbox_items (
                    task_id, title, owner_agent, status, priority,
                    recommended_action, evidence, target_workspace
                )
                VALUES (
                    {task_id},
                    {sql_literal(f'{symbol}: specialist module assigned - {module["module_name"]}')},
                    {sql_literal(module['agent_name'])},
                    'new',
                    'high',
                    {sql_literal(module['output'])},
                    {sql_jsonb(evidence)},
                    'Long-Term Office'
                )
                RETURNING id
            )
            SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text FROM rows
            """
        )
        inbox_id = inbox_rows[0]["id"] if inbox_rows else None
        message_rows = run_psql_json(
            f"""
            WITH rows AS (
                INSERT INTO agent.agent_messages (
                    thread_key, from_agent, to_agent, subject, body, priority,
                    related_task_id, related_skill_key, metadata, generated_task_id, generated_inbox_id
                )
                VALUES (
                    {sql_literal(f'long-term-thesis-{thesis_id}')},
                    'Long-Term Portfolio Manager',
                    {sql_literal(module['agent_name'])},
                    {sql_literal(f'{symbol}: complete {module["module_name"]}')},
                    {sql_literal(objective)},
                    'high',
                    {task_id},
                    {sql_literal(module['skill_key'])},
                    {sql_jsonb({'assignment_key': assignment_key, 'module_key': module['module_key'], 'guardrail': 'research_only'})},
                    {task_id},
                    {sql_literal(inbox_id)}
                )
                RETURNING id
            )
            SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text FROM rows
            """
        )
        message_id = message_rows[0]["id"] if message_rows else None
        linked_rows = run_psql_json(
            f"""
            WITH updated AS (
                UPDATE portfolio.long_term_specialist_assignments
                SET task_id = {task_id},
                    inbox_id = {sql_literal(inbox_id)},
                    message_id = {sql_literal(message_id)},
                    updated_at = now()
                WHERE assignment_key = {sql_literal(assignment_key)}
                RETURNING *
            )
            SELECT coalesce(json_agg(row_to_json(updated)), '[]'::json)::text FROM updated
            """
        )
        if linked_rows:
            row = linked_rows[0]
            assignments.append(
                {
                    "assignment_key": row["assignment_key"],
                    "agent_name": row["agent_name"],
                    "module_name": row["module_name"],
                    "status": row["status"],
                    "task_id": task_id,
                    "inbox_id": inbox_id,
                    "message_id": message_id,
                }
            )
    return assignments


def main() -> int:
    parser = argparse.ArgumentParser(description="Dispatch Long-Term specialist research assignments.")
    parser.add_argument("--holding-thesis-id", type=int)
    parser.add_argument("--long-term-committee-review-id", type=int)
    parser.add_argument("--actor", default="Long-Term Portfolio Manager")
    args = parser.parse_args()
    try:
        context = fetch_context(args.holding_thesis_id, args.long_term_committee_review_id)
        assignments = dispatch(context, args.actor)
        thesis = context["thesis"]
        symbol = clean(thesis.get("symbol")).upper()
        DISPATCH_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        note_path = DISPATCH_DIR / f"{stamp}-{safe_slug(symbol)}-specialist-dispatch.md"
        note_path.write_text(build_note(context, assignments, args.actor))
        rel_path = str(note_path.relative_to(VAULT_ROOT))
        insert_note(note_path, f"Long-Term Specialist Dispatch - {symbol}", f"Dispatched {len(assignments)} specialist assignments for {symbol}.")
        if assignments:
            keys = ",".join(sql_literal(item["assignment_key"]) for item in assignments)
            run_psql_json(
                f"""
                WITH updated AS (
                    UPDATE portfolio.long_term_specialist_assignments
                    SET note_path = {sql_literal(rel_path)}, updated_at = now()
                    WHERE assignment_key IN ({keys})
                    RETURNING id
                )
                SELECT coalesce(json_agg(row_to_json(updated)), '[]'::json)::text FROM updated
                """
            )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "holding_thesis_id": context["thesis"]["id"],
                "symbol": clean(context["thesis"].get("symbol")).upper(),
                "committee_review_id": context.get("committee", {}).get("id"),
                "assignment_count": len(assignments),
                "note_path": rel_path,
                "assignments": assignments,
                "capital_action_allowed": False,
                "live_execution_allowed": False,
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
