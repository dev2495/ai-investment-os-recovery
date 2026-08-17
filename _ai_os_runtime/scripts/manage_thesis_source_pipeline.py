#!/usr/bin/env python3
"""Governed thesis source matrix, reconciliation, refresh gate and cited brief."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VAULT_ROOT = Path(os.environ.get("AI_OS_VAULT_ROOT", "/Volumes/Devarsh SSD/Obsidian memory "))
OUTPUT_ROOT = VAULT_ROOT / "ai memory" / "02 Portfolio" / "Thesis Research Governance"
DOCKER = shutil.which("docker") or "/opt/homebrew/bin/docker"


def literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def jsonb(value: object) -> str:
    return literal(json.dumps(value, sort_keys=True, default=str)) + "::jsonb"


def run(sql: str, *, rows: bool = True) -> Any:
    statement = sql
    if rows:
        body = sql.rstrip().rstrip(";")
        if body.lstrip().lower().startswith(("insert ", "update ", "delete ")):
            statement = (
                "WITH q AS (" + body + ") "
                "SELECT coalesce(json_agg(row_to_json(q)), '[]'::json)::text FROM q;"
            )
        else:
            statement = (
                "SELECT coalesce(json_agg(row_to_json(q)), '[]'::json)::text FROM ("
                + body + ") q;"
            )
    completed = subprocess.run(
        [DOCKER, "exec", "-i", "ai_os_postgres", "psql", "-q", "-t", "-A",
         "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os"],
        input=statement, text=True, capture_output=True, check=False,
    )
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return json.loads(completed.stdout.strip() or "[]") if rows else completed.stdout.strip()


def get_company(symbol: str) -> dict[str, Any]:
    result = run(
        "SELECT id,primary_symbol symbol,primary_exchange exchange,"
        "coalesce(display_name,legal_name) company_name "
        "FROM research.companies WHERE upper(primary_symbol)="
        + literal(symbol.upper()) + " LIMIT 1"
    )
    if not result:
        raise ValueError("Research company not found: " + symbol)
    return result[0]


def get_matrix(symbol: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    record = get_company(symbol)
    rows = run(
        "SELECT requirement_key,section_key,section_order,data_point_key,requirement_label,"
        "acceptable_source_kinds,minimum_source_count,max_age_days,extraction_required,"
        "minimum_validation,is_material,is_required,linked_source_count,covered_source_count,"
        "pending_review_count,stale_source_count,latest_captured_at,latest_publication_date,"
        "coverage_status,coverage_debt,sources FROM research.v_thesis_source_matrix WHERE company_id="
        + str(int(record["id"])) + " ORDER BY section_order,requirement_key"
    )
    return record, rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, int]:
    result = {"total": len(rows), "covered": 0, "pending_review": 0, "stale": 0, "missing": 0, "coverage_debt": 0}
    for row in rows:
        status = str(row["coverage_status"])
        result[status] = result.get(status, 0) + 1
        result["coverage_debt"] += int(row.get("coverage_debt") or 0)
    return result


def render_matrix(record: dict[str, Any], rows: list[dict[str, Any]], generated_at: str) -> str:
    summary = summarize(rows)
    lines = [
        "# " + record["company_name"] + " (" + record["symbol"] + ") - Source-to-Section Matrix",
        "", "Generated: " + generated_at, "Exchange: " + record["exchange"],
        "Scope: personal research workspace", "",
        "A downloaded or parsed document is not automatically covered. Coverage requires source, parser",
        "(where required), validation, freshness, citation and section-link gates to pass.", "",
        "## Coverage", "",
        "- Data points: " + str(summary["total"]),
        "- Covered: " + str(summary["covered"]),
        "- Pending review: " + str(summary["pending_review"]),
        "- Stale: " + str(summary["stale"]),
        "- Missing: " + str(summary["missing"]),
        "- Source-count debt: " + str(summary["coverage_debt"]), "",
        "| Section | Data point | Sources needed | Validation | Freshness | State | Debt |",
        "|---|---|---:|---|---:|---|---:|",
    ]
    for row in rows:
        age = "event-driven" if row["max_age_days"] is None else str(row["max_age_days"]) + "d"
        lines.append(
            "| " + row["section_key"] + " | " + row["requirement_label"] + " | "
            + str(row["minimum_source_count"]) + " | " + row["minimum_validation"] + " | "
            + age + " | " + row["coverage_status"] + " | " + str(row["coverage_debt"]) + " |"
        )
    lines.extend(["", "## Data-point contracts", ""])
    for row in rows:
        lines.extend([
            "### " + row["requirement_key"], "",
            "- Section: " + row["section_key"],
            "- Acceptable source kinds: " + ", ".join(row.get("acceptable_source_kinds") or []),
            "- Extraction required: " + str(row["extraction_required"]),
            "- Minimum validation: " + row["minimum_validation"],
            "- Current state: " + row["coverage_status"],
            "- Linked sources: " + str(row["linked_source_count"]) + "; covered: " + str(row["covered_source_count"]),
            "",
        ])
    lines.extend([
        "## Safety and collection policy", "",
        "- Official or authorized HTTPS only; no cookie, paywall, access-control or robots bypass.",
        "- Public captures are rate-limited and cached on the external Devarsh SSD.",
        "- Private user artifacts remain on the external SSD and never go to cloud services.",
        "- Historical supplied research requires fresh corroboration for current facts.",
        "- This workflow permits no broker, client, alert, order, account or external write.", "",
    ])
    return "\n".join(lines)


def matrix(symbol: str) -> dict[str, Any]:
    record, rows = get_matrix(symbol)
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    directory = OUTPUT_ROOT / record["symbol"]
    directory.mkdir(parents=True, exist_ok=True)
    markdown_path = directory / ("source-to-section-matrix-" + stamp + ".md")
    json_path = directory / ("source-to-section-matrix-" + stamp + ".json")
    payload = {"company": record, "generated_at": now.isoformat(), "summary": summarize(rows), "rows": rows}
    markdown_path.write_text(render_matrix(record, rows, now.isoformat()), encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return {"company": record, "summary": payload["summary"], "markdown_path": str(markdown_path), "json_path": str(json_path)}


def classify(document_type: str) -> str:
    value = document_type.lower()
    if "annual" in value:
        return "annual_report"
    if "presentation" in value:
        return "investor_presentation"
    if "transcript" in value:
        return "transcript"
    if "result" in value:
        return "exchange_results"
    return "company_filing"


def reconcile(symbol: str, actor: str) -> dict[str, Any]:
    record = get_company(symbol)
    documents = run(
        "SELECT d.id source_document_id,d.document_key,d.holding_thesis_id,d.document_type,"
        "d.document_title,d.source_url,d.local_path,d.provenance_status,d.http_status,d.raw_artifact_id,"
        "d.updated_at,x.id source_extraction_id,x.local_pdf_path,x.local_text_path,x.parser_name,"
        "x.page_count,x.extracted_chars,x.extraction_status,x.error,x.extracted_at "
        "FROM portfolio.long_term_source_documents d LEFT JOIN LATERAL "
        "(SELECT * FROM portfolio.long_term_source_document_extractions e WHERE e.source_document_id=d.id "
        "ORDER BY e.extracted_at DESC,e.id DESC LIMIT 1) x ON true WHERE upper(d.symbol)="
        + literal(record["symbol"]) + " ORDER BY d.updated_at DESC,d.id DESC LIMIT 100"
    )
    items: list[int] = []
    proposed = 0
    for doc in documents:
        kind = classify(str(doc["document_type"]))
        pdf_path = doc.get("local_pdf_path") or doc.get("local_path")
        text_path = doc.get("local_text_path")
        governed_pdf_path = pdf_path if str(pdf_path or "").startswith("/Volumes/Devarsh SSD/") else None
        parsed = (
            doc.get("source_extraction_id") is not None and doc.get("extraction_status") == "extracted"
            and not doc.get("error") and int(doc.get("page_count") or 0) > 0
            and int(doc.get("extracted_chars") or 0) > 0
            and str(pdf_path or "").startswith("/Volumes/Devarsh SSD/")
            and str(text_path or "").startswith("/Volumes/Devarsh SSD/")
        )
        official = (
            str(doc.get("source_url") or "").startswith("https://")
            and doc.get("provenance_status") == "verified" and int(doc.get("http_status") or 0) == 200
        )
        validation = "machine_validated" if parsed and official else "pending"
        validated_at = datetime.now(timezone.utc).isoformat() if validation == "machine_validated" else None
        citation = {
            "source_document_id": doc["source_document_id"], "source_extraction_id": doc.get("source_extraction_id"),
            "page_count": doc.get("page_count"), "parser": doc.get("parser_name"), "exact_pages_pending": True,
        }
        source_key = record["symbol"].lower() + ":" + kind + ":" + doc["document_key"]
        sql = (
            "INSERT INTO research.thesis_source_items(source_key,company_id,holding_thesis_id,source_kind,"
            "source_system,source_identifier,source_url,source_title,captured_at,capture_status,parser_status,"
            "validation_status,raw_artifact_id,source_document_id,source_extraction_id,local_artifact_path,"
            "citation_locator,source_scope,authorization_basis,access_status,terms_status,robots_status,"
            "cache_status,material_change,change_kind,section_hint,validated_by,validated_at,validation_notes,metadata) VALUES("
            + literal(source_key) + "," + str(int(record["id"])) + "," + literal(doc.get("holding_thesis_id"))
            + "::bigint," + literal(kind) + ",'official_company_ir_registry'," + literal(doc["document_key"])
            + "," + literal(doc["source_url"]) + "," + literal(doc["document_title"]) + ","
            + literal(doc.get("extracted_at") or doc["updated_at"]) + "::timestamptz,'captured',"
            + literal("parsed" if parsed else "pending") + "," + literal(validation) + ","
            + literal(doc.get("raw_artifact_id")) + "::bigint," + str(int(doc["source_document_id"])) + ","
            + literal(doc.get("source_extraction_id")) + "::bigint," + literal(governed_pdf_path) + "," + jsonb(citation)
            + ",'public','operator-verified official IR registry',"
            + literal("allowed" if official else "review_required") + ","
            + literal("allowed" if official else "review_required") + ",'not_applicable','external_ssd',"
            + "false,'new','evidence_library'," + literal(actor if validation == "machine_validated" else None)
            + "," + literal(validated_at) + "::timestamptz,"
            + literal("Parser and external-SSD checks passed; exact claims/pages still need human review." if parsed else "Source or parser review required.")
            + "," + jsonb({"legacy_extraction_status": doc.get("extraction_status")}) + ") "
            + "ON CONFLICT(company_id,source_kind,source_system,source_identifier) DO UPDATE SET "
            + "source_url=EXCLUDED.source_url,source_title=EXCLUDED.source_title,captured_at=EXCLUDED.captured_at,"
            + "capture_status=EXCLUDED.capture_status,parser_status=EXCLUDED.parser_status,"
            + "validation_status=CASE WHEN research.thesis_source_items.validation_status='human_validated' "
            + "THEN research.thesis_source_items.validation_status ELSE EXCLUDED.validation_status END,"
            + "raw_artifact_id=EXCLUDED.raw_artifact_id,source_extraction_id=EXCLUDED.source_extraction_id,"
            + "local_artifact_path=EXCLUDED.local_artifact_path,citation_locator=EXCLUDED.citation_locator,"
            + "access_status=EXCLUDED.access_status,terms_status=EXCLUDED.terms_status,"
            + "validation_notes=EXCLUDED.validation_notes,metadata=research.thesis_source_items.metadata||EXCLUDED.metadata,"
            + "updated_at=now() RETURNING id"
        )
        item_id = int(run(sql)[0]["id"])
        items.append(item_id)
        links = run(
            "INSERT INTO research.thesis_source_links(source_item_id,requirement_id,link_role,link_status,"
            "citation_note,linked_by) SELECT " + str(item_id) + ",id,'supporting','proposed',"
            "'Exact claim and page review required before coverage.'," + literal(actor)
            + " FROM research.thesis_source_requirements WHERE " + literal(kind)
            + "=ANY(acceptable_source_kinds) ON CONFLICT(source_item_id,requirement_id,link_role) "
            + "DO NOTHING RETURNING id"
        )
        proposed += len(links)
        run(
            "INSERT INTO research.thesis_source_events(source_item_id,company_id,event_type,event_summary,actor,event_payload) VALUES("
            + str(item_id) + "," + str(int(record["id"])) + ",'registered',"
            + literal("Reconciled official document; section coverage remains link-review gated.") + ","
            + literal(actor) + "," + jsonb({"parser_status": "parsed" if parsed else "pending", "validation_status": validation}) + ");",
            rows=False,
        )
    return {"symbol": record["symbol"], "documents_found": len(documents), "source_items": items, "proposed_links_created": proposed}


def render_brief(record: dict[str, Any], rows: list[dict[str, Any]], generated_at: str) -> str:
    summary = summarize(rows)
    lines = [
        "# " + record["company_name"] + " (" + record["symbol"] + ") - Governed Thesis Research Brief",
        "", "Generated: " + generated_at, "Status: review required", "",
        "Coverage and evidence brief only; this is not an investment recommendation or trade authorization.", "",
        "## Coverage", "",
        "- Covered: " + str(summary["covered"]) + "/" + str(summary["total"]),
        "- Pending review: " + str(summary["pending_review"]),
        "- Missing: " + str(summary["missing"]),
        "- Stale: " + str(summary["stale"]),
        "- Source-count debt: " + str(summary["coverage_debt"]), "",
    ]
    sections: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        sections.setdefault(str(row["section_key"]), []).append(row)
    for section, section_rows in sections.items():
        lines.extend(["## " + section.replace("_", " ").title(), ""])
        for row in section_rows:
            lines.append("- " + row["requirement_label"] + ": " + row["coverage_status"])
            for source in row.get("sources") or []:
                lines.append(
                    "  - " + str(source.get("source_title")) + " | " + str(source.get("source_url"))
                    + " | captured " + str(source.get("captured_at")) + " | parser "
                    + str(source.get("parser_status")) + " | validation " + str(source.get("validation_status"))
                    + " | locator " + json.dumps(source.get("citation_locator") or {}, sort_keys=True)
                )
        lines.append("")
    lines.extend([
        "## Remaining gates", "",
        "- Review exact pages and claims before validating section links.",
        "- Freshly corroborate historical user-supplied research.",
        "- No decision, order, alert, broker, account or external write is authorized.", "",
    ])
    return "\n".join(lines)


def brief(symbol: str, actor: str) -> dict[str, Any]:
    record, rows = get_matrix(symbol)
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    directory = OUTPUT_ROOT / record["symbol"]
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ("cited-thesis-brief-" + stamp + ".md")
    content = render_brief(record, rows, now.isoformat())
    path.write_text(content, encoding="utf-8")
    digest = hashlib.sha256(content.encode()).hexdigest()
    summary = summarize(rows)
    source_count = int(run(
        "SELECT count(*)::int source_item_count FROM research.thesis_source_items WHERE company_id="
        + str(int(record["id"]))
    )[0]["source_item_count"])
    key = record["symbol"].lower() + ":" + stamp.lower()
    run(
        "INSERT INTO research.thesis_cited_briefs(brief_key,company_id,generated_by,artifact_path,artifact_hash,"
        "covered_requirement_count,total_requirement_count,pending_review_count,missing_requirement_count,"
        "stale_requirement_count,source_item_count,brief_status,notes) VALUES("
        + literal(key) + "," + str(int(record["id"])) + "," + literal(actor) + "," + literal(str(path)) + ","
        + literal(digest) + "," + str(summary["covered"]) + "," + str(summary["total"]) + ","
        + str(summary["pending_review"]) + "," + str(summary["missing"]) + "," + str(summary["stale"]) + ","
        + str(source_count) + ",'review_required','Coverage brief only; human decisions remain gated.');",
        rows=False,
    )
    return {"path": str(path), "sha256": digest, "summary": summary, "source_item_count": source_count}


def refresh_gate(source_item_id: int, actor: str) -> dict[str, Any]:
    found = run(
        "SELECT id,company_id,source_url,access_status,terms_status,robots_status,cache_status "
        "FROM research.thesis_source_items WHERE id=" + str(source_item_id)
    )
    if not found:
        raise ValueError("Source item not found")
    item = found[0]
    allowed = (
        str(item.get("source_url") or "").startswith("https://")
        and item["access_status"] == "allowed" and item["terms_status"] == "allowed"
        and item["robots_status"] not in ("review_required", "blocked")
        and item["cache_status"] == "external_ssd"
    )
    status = "ready_for_existing_official_collector" if allowed else "manual_source_review_required"
    run(
        "INSERT INTO research.thesis_source_events(source_item_id,company_id,event_type,event_summary,actor,event_payload) VALUES("
        + str(source_item_id) + "," + str(int(item["company_id"])) + ",'refresh_gated',"
        + literal(status) + "," + literal(actor)
        + "," + jsonb({"gate_status": status, "network_request_performed": False}) + ");",
        rows=False,
    )
    return {"source_item_id": source_item_id, "gate_status": status, "network_request_performed": False,
            "handoff": "Run the existing official IR collector only when this gate is ready."}


def main() -> int:
    root = argparse.ArgumentParser()
    sub = root.add_subparsers(dest="command", required=True)
    for name in ("matrix", "reconcile", "brief"):
        command = sub.add_parser(name)
        command.add_argument("--symbol", required=True)
        command.add_argument("--actor", default="AI OS Source Steward")
    gate = sub.add_parser("refresh-gate")
    gate.add_argument("--source-item-id", type=int, required=True)
    gate.add_argument("--actor", default="AI OS Source Steward")
    args = root.parse_args()
    if args.command == "matrix":
        result = matrix(args.symbol)
    elif args.command == "reconcile":
        result = reconcile(args.symbol, args.actor)
    elif args.command == "brief":
        result = brief(args.symbol, args.actor)
    else:
        result = refresh_gate(args.source_item_id, args.actor)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
