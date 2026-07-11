#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = RUNTIME_ROOT.parent
DEFAULT_CHECKLIST = REPO_ROOT / "ai memory/00 AI OS/Roadmap/AI Investment OS - Execution Checklist v10.0.md"
BLUEPRINT_KEY = "investment_os_v10"


@dataclass(frozen=True)
class DomainPolicy:
    domain_type: str
    owner_agent: str
    owner_department: str
    priority: str
    workspace: str


DOMAIN_POLICIES: dict[int, DomainPolicy] = {
    0: DomainPolicy("governance", "Charlie Munger", "orchestration", "critical", "system"),
    1: DomainPolicy("runtime", "Jarvis", "runtime", "critical", "system"),
    2: DomainPolicy("data", "Data Steward", "data_engineering", "critical", "system"),
    3: DomainPolicy("portfolio", "Portfolio Manager", "portfolio", "critical", "portfolio"),
    4: DomainPolicy("investment_book", "Long-Term Portfolio Manager", "portfolio", "high", "portfolio"),
    5: DomainPolicy("investment_book", "Tactical Portfolio Manager", "tactical", "high", "portfolio"),
    6: DomainPolicy("investment_book", "Head of Quant", "quant", "critical", "quant"),
    7: DomainPolicy("investment_book", "Trading Desk Agent", "trading", "critical", "trading"),
    8: DomainPolicy("research", "Research Director", "research", "critical", "research"),
    9: DomainPolicy("investment_book", "Treasury Analyst", "risk", "high", "risk"),
    10: DomainPolicy("capital", "Capital Allocation Officer", "portfolio", "critical", "portfolio"),
    11: DomainPolicy("risk", "Risk Agent", "risk", "critical", "risk"),
    12: DomainPolicy("client", "Client Manager", "client", "critical", "clients"),
    13: DomainPolicy("agent_office", "Jarvis", "orchestration", "critical", "office"),
    14: DomainPolicy("committee", "Charlie Munger", "orchestration", "critical", "office"),
    15: DomainPolicy("mcp", "Jarvis", "automation", "critical", "system"),
    16: DomainPolicy("ui", "Jarvis", "software_engineering", "critical", "command"),
    17: DomainPolicy("reporting", "Document Writer Agent", "knowledge", "high", "reports"),
    18: DomainPolicy("models", "AI Engineer", "ai_engineering", "critical", "system"),
    19: DomainPolicy("safety", "Execution Safety Agent", "risk", "critical", "risk"),
    20: DomainPolicy("roadmap", "Jarvis", "orchestration", "critical", "system"),
}


def run_psql(sql: str, tuples_only: bool = False) -> str:
    command = ["docker", "exec", "-i", "ai_os_postgres", "psql", "-q", "-U", "ai_os", "-d", "ai_os", "-v", "ON_ERROR_STOP=1"]
    if tuples_only:
        command.extend(["-t", "-A"])
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return completed.stdout.strip()


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return f"{sql_literal(json.dumps(value, sort_keys=True, default=str))}::jsonb"


def slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return result[:72] or "requirement"


def requirement_type(name: str) -> str:
    text = name.lower()
    rules = [
        (("dashboard", "widget", "ui", "office scene", "hover card"), "ui"),
        (("agent", "analyst", "manager"), "agent"),
        (("committee", "approval", "decision"), "committee"),
        (("mcp", "connector", "adapter", "bridge", "browser"), "integration"),
        (("import", "ingestion", "collector", "ohlcv", "chain", "filing", "news"), "data_pipeline"),
        (("backtest", "optimizer", "monte carlo", "var", "stress", "factor", "correlation"), "analytics"),
        (("report", "brief", "memo", "pdf"), "reporting"),
        (("policy", "safety", "kill switch", "risk limit", "audit", "backup", "restore"), "control"),
        (("schema", "table", "registry", "api", "runtime", "postgres", "redis", "qdrant"), "platform"),
    ]
    for terms, value in rules:
        if any(term in text for term in terms):
            return value
    return "capability"


def requirement_priority(name: str, domain_priority: str) -> str:
    text = name.lower()
    critical_terms = (
        "execution", "broker", "kill switch", "risk", "backup", "restore", "secret",
        "approval", "audit", "reconciliation", "production data", "human control",
    )
    if any(term in text for term in critical_terms):
        return "critical"
    return domain_priority


def parse_checklist(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    raw = path.read_text(encoding="utf-8")
    source_sha256 = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    lines = raw.splitlines()
    domains: list[dict[str, Any]] = []
    requirements: list[dict[str, Any]] = []
    current_domain: dict[str, Any] | None = None
    domain_items: dict[str, list[dict[str, Any]]] = {}
    item_order = 0

    heading_pattern = re.compile(r"^##\s+(\d+)\.\s+(.+?)\s*$")
    item_pattern = re.compile(r"^- \[([x~ ])\]\s+(.+?)\s*$")
    wikilink_pattern = re.compile(r"\[\[([^\]]+)\]\]")

    for line_number, line in enumerate(lines, start=1):
        heading = heading_pattern.match(line)
        if heading:
            section_number = int(heading.group(1))
            domain_name = heading.group(2).strip()
            policy = DOMAIN_POLICIES.get(section_number, DomainPolicy("capability", "Jarvis", "runtime", "high", "system"))
            domain_key = f"v10_{section_number:02d}_{slug(domain_name)}"
            current_domain = {
                "domain_key": domain_key,
                "section_number": section_number,
                "domain_name": domain_name,
                "policy": policy,
                "line_number": line_number,
            }
            domains.append(current_domain)
            domain_items[domain_key] = []
            continue

        item = item_pattern.match(line)
        if not item or current_domain is None:
            continue

        marker = item.group(1)
        raw_text = item.group(2).strip()
        name = re.split(r"\s+Evidence:\s+", raw_text, maxsplit=1)[0].strip()
        name = re.sub(r"\s+Verified\s+\d{4}-\d{2}-\d{2}.*$", "", name).strip()
        status = {"x": "done", "~": "partial", " ": "planned"}[marker]
        item_order += 1
        digest = hashlib.sha1(f"{current_domain['domain_key']}|{name}".encode("utf-8")).hexdigest()[:10]
        requirement_key = f"v10_req_{current_domain['section_number']:02d}_{slug(name)[:48]}_{digest}"
        evidence_refs = wikilink_pattern.findall(raw_text)
        policy: DomainPolicy = current_domain["policy"]
        requirement = {
            "requirement_key": requirement_key,
            "domain_key": current_domain["domain_key"],
            "requirement_name": name.rstrip("."),
            "requirement_type": requirement_type(name),
            "priority": requirement_priority(name, policy.priority),
            "current_status": status,
            "owner_agent": policy.owner_agent,
            "owner_department": policy.owner_department,
            "evidence_note_path": evidence_refs[0] if evidence_refs else None,
            "acceptance_criteria": f"{name.rstrip('.')} is implemented against production data and has linked runtime evidence; seed-only completion is not accepted.",
            "next_action": None if status == "done" else ("Close remaining hardening and attach final evidence." if status == "partial" else "Implement the requirement and attach live evidence."),
            "metadata": {
                "source": "canonical_checklist_sync",
                "source_path": str(path.relative_to(REPO_ROOT)),
                "source_sha256": source_sha256,
                "source_line": line_number,
                "section_number": current_domain["section_number"],
                "item_order": item_order,
                "status_marker": marker,
                "raw_text": raw_text,
                "evidence_refs": evidence_refs,
                "seed_data_allowed": False,
            },
        }
        requirements.append(requirement)
        domain_items[current_domain["domain_key"]].append(requirement)

    for domain in domains:
        items = domain_items[domain["domain_key"]]
        statuses = {item["current_status"] for item in items}
        if items and statuses == {"done"}:
            domain["status"] = "done"
        elif "partial" in statuses or "done" in statuses:
            domain["status"] = "partial"
        elif "blocked" in statuses:
            domain["status"] = "blocked"
        else:
            domain["status"] = "planned"
        domain["requirement_count"] = len(items)

    if not domains or not requirements:
        raise ValueError("canonical checklist parser found no domains or requirements")
    return domains, requirements, source_sha256


def upsert_registry(path: Path, actor: str, run_key: str) -> dict[str, Any]:
    started = time.time()
    domains, requirements, source_sha256 = parse_checklist(path)
    run_psql(
        f"""
        INSERT INTO core.os_blueprint_sync_runs (
            run_key, blueprint_key, status, source_path, source_sha256, created_by, started_at
        ) VALUES (
            {sql_literal(run_key)}, {sql_literal(BLUEPRINT_KEY)}, 'started',
            {sql_literal(str(path.relative_to(REPO_ROOT)))}, {sql_literal(source_sha256)},
            {sql_literal(actor)}, now()
        )
        ON CONFLICT (run_key) DO UPDATE SET
            status = 'started',
            source_path = EXCLUDED.source_path,
            source_sha256 = EXCLUDED.source_sha256,
            domain_count = 0,
            requirement_count = 0,
            done_count = 0,
            partial_count = 0,
            planned_count = 0,
            error_message = NULL,
            started_at = now(),
            finished_at = NULL,
            created_by = EXCLUDED.created_by;
        """
    )

    try:
        domain_values = []
        for domain in domains:
            policy: DomainPolicy = domain["policy"]
            domain_values.append(
                "(" + ",".join(
                    [
                        sql_literal(domain["domain_key"]),
                        sql_literal(BLUEPRINT_KEY),
                        str(domain["section_number"]),
                        sql_literal(domain["domain_name"]),
                        sql_literal(policy.domain_type),
                        sql_literal(policy.owner_agent),
                        sql_literal(policy.owner_department),
                        sql_literal(policy.priority),
                        sql_literal(domain["status"]),
                        sql_literal(f"Deliver and verify every canonical v10 requirement for {domain['domain_name']}."),
                        sql_literal(policy.workspace),
                        sql_literal("ai memory/00 AI OS/Roadmap/AI Investment OS - Execution Checklist v10.0.md"),
                        sql_jsonb({
                            "source": "canonical_checklist_sync",
                            "source_line": domain["line_number"],
                            "source_sha256": source_sha256,
                            "requirement_count": domain["requirement_count"],
                            "seed_data_allowed": False,
                        }),
                    ]
                ) + ")"
            )
        run_psql(
            """
            INSERT INTO core.os_blueprint_domains (
                domain_key, blueprint_key, section_number, domain_name, domain_type,
                owner_agent, owner_department, priority, status, objective,
                primary_workspace, canonical_note_path, metadata
            ) VALUES
            """
            + ",\n".join(domain_values)
            + """
            ON CONFLICT (domain_key) DO UPDATE SET
                blueprint_key = EXCLUDED.blueprint_key,
                section_number = EXCLUDED.section_number,
                domain_name = EXCLUDED.domain_name,
                domain_type = EXCLUDED.domain_type,
                owner_agent = EXCLUDED.owner_agent,
                owner_department = EXCLUDED.owner_department,
                priority = EXCLUDED.priority,
                status = EXCLUDED.status,
                objective = EXCLUDED.objective,
                primary_workspace = EXCLUDED.primary_workspace,
                canonical_note_path = EXCLUDED.canonical_note_path,
                metadata = EXCLUDED.metadata,
                updated_at = now();
            """
        )

        requirement_values = []
        for requirement in requirements:
            requirement_values.append(
                "(" + ",".join(
                    [
                        sql_literal(requirement["requirement_key"]),
                        sql_literal(BLUEPRINT_KEY),
                        sql_literal(requirement["domain_key"]),
                        sql_literal(requirement["requirement_name"]),
                        sql_literal(requirement["requirement_type"]),
                        sql_literal(requirement["priority"]),
                        sql_literal(requirement["current_status"]),
                        sql_literal(requirement["owner_agent"]),
                        sql_literal(requirement["owner_department"]),
                        "NULL",
                        "NULL",
                        sql_literal(requirement["evidence_note_path"]),
                        sql_literal(requirement["acceptance_criteria"]),
                        sql_literal(requirement["next_action"]),
                        sql_jsonb(requirement["metadata"]),
                    ]
                ) + ")"
            )

        for offset in range(0, len(requirement_values), 100):
            chunk = requirement_values[offset : offset + 100]
            run_psql(
                """
                INSERT INTO core.os_blueprint_requirements (
                    requirement_key, blueprint_key, domain_key, requirement_name,
                    requirement_type, priority, current_status, owner_agent,
                    owner_department, mapped_object_type, mapped_object_key,
                    evidence_note_path, acceptance_criteria, next_action, metadata
                ) VALUES
                """
                + ",\n".join(chunk)
                + """
                ON CONFLICT (requirement_key) DO UPDATE SET
                    blueprint_key = EXCLUDED.blueprint_key,
                    domain_key = EXCLUDED.domain_key,
                    requirement_name = EXCLUDED.requirement_name,
                    requirement_type = EXCLUDED.requirement_type,
                    priority = EXCLUDED.priority,
                    current_status = EXCLUDED.current_status,
                    owner_agent = EXCLUDED.owner_agent,
                    owner_department = EXCLUDED.owner_department,
                    evidence_note_path = EXCLUDED.evidence_note_path,
                    acceptance_criteria = EXCLUDED.acceptance_criteria,
                    next_action = EXCLUDED.next_action,
                    metadata = EXCLUDED.metadata,
                    updated_at = now();
                """
            )

        active_keys = ",".join(sql_literal(item["requirement_key"]) for item in requirements)
        run_psql(
            f"""
            DELETE FROM core.os_blueprint_requirements
            WHERE blueprint_key = {sql_literal(BLUEPRINT_KEY)}
              AND metadata->>'source' = 'canonical_checklist_sync'
              AND requirement_key NOT IN ({active_keys});
            """
        )

        counts = {
            "done": sum(item["current_status"] == "done" for item in requirements),
            "partial": sum(item["current_status"] == "partial" for item in requirements),
            "planned": sum(item["current_status"] == "planned" for item in requirements),
        }
        run_psql(
            f"""
            UPDATE core.os_blueprint_sync_runs
            SET status = 'completed',
                domain_count = {len(domains)},
                requirement_count = {len(requirements)},
                done_count = {counts['done']},
                partial_count = {counts['partial']},
                planned_count = {counts['planned']},
                finished_at = now()
            WHERE run_key = {sql_literal(run_key)};
            """
        )
        return {
            "run_key": run_key,
            "status": "completed",
            "blueprint_key": BLUEPRINT_KEY,
            "source_path": str(path),
            "source_sha256": source_sha256,
            "domain_count": len(domains),
            "requirement_count": len(requirements),
            "done_count": counts["done"],
            "partial_count": counts["partial"],
            "planned_count": counts["planned"],
            "duration_ms": int((time.time() - started) * 1000),
            "seed_rows_created": 0,
        }
    except Exception as exc:
        run_psql(
            f"""
            UPDATE core.os_blueprint_sync_runs
            SET status = 'failed', error_message = {sql_literal(f'{type(exc).__name__}: {exc}')}, finished_at = now()
            WHERE run_key = {sql_literal(run_key)};
            """
        )
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize the canonical v10 checklist into the AI OS operating-model registry.")
    parser.add_argument("--checklist", type=Path, default=DEFAULT_CHECKLIST)
    parser.add_argument("--actor", default="Jarvis")
    parser.add_argument("--run-key", default=f"blueprint_v10_sync_{int(time.time())}")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    checklist = args.checklist.expanduser().resolve()
    domains, requirements, source_sha256 = parse_checklist(checklist)
    if args.dry_run:
        result = {
            "status": "dry_run",
            "source_path": str(checklist),
            "source_sha256": source_sha256,
            "domain_count": len(domains),
            "requirement_count": len(requirements),
            "done_count": sum(item["current_status"] == "done" for item in requirements),
            "partial_count": sum(item["current_status"] == "partial" for item in requirements),
            "planned_count": sum(item["current_status"] == "planned" for item in requirements),
            "seed_rows_created": 0,
        }
    else:
        result = upsert_registry(checklist, args.actor.strip() or "Jarvis", args.run_key)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
