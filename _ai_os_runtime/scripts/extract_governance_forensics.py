#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from extract_long_term_source_document import ensure_pdf_runtime, run_psql_json, sql_jsonb, sql_literal
except ModuleNotFoundError:
    from _ai_os_runtime.scripts.extract_long_term_source_document import ensure_pdf_runtime, run_psql_json, sql_jsonb, sql_literal


RULES: tuple[dict[str, Any], ...] = (
    {
        "key": "statutory_audit_no_qualification",
        "category": "auditor",
        "status": "no_adverse_remark",
        "severity": "info",
        "patterns": (r"no qualifications?, reservations? or adverse remarks?", r"does not contain any qualification, reservation or adverse remark"),
        "conclusion": "The annual report states that the statutory audit contains no qualification, reservation or adverse remark.",
    },
    {
        "key": "statutory_audit_emphasis_of_matter",
        "category": "auditor",
        "status": "emphasis_of_matter",
        "severity": "high",
        "patterns": (r"emphasis of matter",),
        "conclusion": "The statutory auditor includes an Emphasis of Matter; this is an active review item and not a clean audit clearance.",
    },
    {
        "key": "related_party_arm_length_disclosure",
        "category": "related_party",
        "status": "no_material_issue_disclosed",
        "severity": "low",
        "patterns": (r"related party transactions?.{0,500}(ordinary course of business|arm.?s length)", r"no materially significant related party transactions"),
        "conclusion": "The company discloses related-party transactions as ordinary-course or arm's-length and reports no materially significant conflict.",
    },
    {
        "key": "cbi_proceedings_ongoing",
        "category": "legal_regulatory",
        "status": "active_issue",
        "severity": "high",
        "patterns": (r"cbi.{0,900}(proceedings?.{0,120}(ongoing|pending)|case.{0,160}(ongoing|pending))", r"central bureau of investigation.{0,900}(ongoing|pending)"),
        "conclusion": "The annual report discloses ongoing or pending CBI proceedings. This remains unresolved.",
    },
    {
        "key": "pmla_property_attachment",
        "category": "legal_regulatory",
        "status": "active_issue",
        "severity": "high",
        "patterns": (r"(?:pmla|prevention of money laundering act).{0,1200}(?:attach|attachment).{0,500}(?:190\.37|19037)", r"(?:190\.37|19037).{0,500}(?:attach|attachment).{0,500}(?:pmla|prevention of money laundering act)"),
        "conclusion": "The annual report discloses an unresolved PMLA-related property attachment of approximately INR 190.37 crore.",
        "value": 190.37,
        "unit": "INR crore",
    },
    {
        "key": "auditor_reported_fraud_none",
        "category": "fraud",
        "status": "no_material_issue_disclosed",
        "severity": "info",
        "patterns": (r"no fraud.{0,500}(reported|noticed).{0,400}(auditors?|section 143)", r"auditors?.{0,500}have not reported any instance of fraud"),
        "conclusion": "The annual report states that the auditors reported no fraud during the period.",
    },
    {
        "key": "whistleblower_complaints_none",
        "category": "whistleblower",
        "status": "no_material_issue_disclosed",
        "severity": "info",
        "patterns": (r"no (?:complaints?|instances?).{0,300}(whistle.?blower|vigil mechanism)", r"no whistle.?blower complaints?", r"whistle.?blower.{0,500}(?:nil|none|no complaints?)"),
        "conclusion": "The annual report states that no whistleblower or vigil-mechanism complaint was reported.",
    },
    {
        "key": "internal_financial_controls_adequate",
        "category": "internal_control",
        "status": "no_adverse_remark",
        "severity": "info",
        "patterns": (r"internal financial controls?.{0,500}(adequate|operating effectively|effective)",),
        "conclusion": "The annual report describes internal financial controls as adequate or operating effectively.",
    },
)


def normalized_page(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def source_excerpt(text: str, match: re.Match[str], radius: int = 600) -> str:
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    return text[start:end].strip()[:1800]


def extract_observations_from_pages(pages: list[str], period_end: str) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rule in RULES:
        for page_number, raw_text in enumerate(pages, start=1):
            text = normalized_page(raw_text)
            for pattern in rule["patterns"]:
                match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
                if not match:
                    continue
                observations.append({
                    "observation_key": rule["key"],
                    "category": rule["category"],
                    "observation_status": rule["status"],
                    "severity": rule["severity"],
                    "conclusion": rule["conclusion"],
                    "disclosed_value": rule.get("value"),
                    "disclosed_unit": rule.get("unit"),
                    "period_end": period_end,
                    "source_page": page_number,
                    "source_excerpt": source_excerpt(text, match),
                    "extraction_method": "deterministic_pattern",
                    "verification_status": "machine_extracted",
                    "metadata": {"pattern": pattern},
                })
                seen.add(rule["key"])
                break
            if rule["key"] in seen:
                break
    return observations


def load_source(source_document_id: int, evidence_id: int) -> dict[str, Any]:
    rows = run_psql_json(f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text FROM (
          SELECT extraction.local_pdf_path, extraction.symbol, company.id AS company_id,
                 evidence.id AS evidence_id,
                 coalesce(evidence.published_at,evidence.retrieved_at) AS available_at
          FROM portfolio.long_term_source_document_extractions extraction
          JOIN portfolio.long_term_source_documents document ON document.id=extraction.source_document_id
          JOIN research.companies company
            ON upper(company.primary_symbol)=upper(document.symbol)
           AND upper(company.primary_exchange)=upper(document.exchange)
          JOIN research.fundamental_evidence evidence ON evidence.id={int(evidence_id)}
             AND evidence.company_id=company.id
          WHERE extraction.source_document_id={int(source_document_id)}
            AND extraction.extraction_status IN ('extracted','completed')
          ORDER BY extraction.extracted_at DESC LIMIT 1
        ) rows
    """)
    if not rows:
        raise ValueError("completed source extraction and matching company evidence are required")
    return rows[0]


def persist(source: dict[str, Any], observations: list[dict[str, Any]]) -> dict[str, Any]:
    if not observations:
        raise ValueError("no governed observations matched; inspect the source before changing extraction rules")
    values = []
    for row in observations:
        values.append("(" + ",".join((
            str(int(source["company_id"])), str(int(source["evidence_id"])), sql_literal(row["observation_key"]),
            sql_literal(row["category"]), sql_literal(row["observation_status"]), sql_literal(row["severity"]),
            sql_literal(row["conclusion"]), str(row["disclosed_value"]) if row["disclosed_value"] is not None else "NULL",
            sql_literal(row["disclosed_unit"]), sql_literal(row["period_end"]) + "::date", str(row["source_page"]),
            sql_literal(row["source_excerpt"]), sql_literal(row["extraction_method"]),
            sql_literal(row["verification_status"]), sql_literal(source["available_at"]) + "::timestamptz",
            sql_jsonb(row["metadata"]),
        )) + ")")
    result = run_psql_json(f"""
      WITH incoming(company_id,evidence_id,observation_key,category,observation_status,severity,
        conclusion,disclosed_value,disclosed_unit,period_end,source_page,source_excerpt,
        extraction_method,verification_status,available_at,metadata) AS (VALUES {','.join(values)}),
      upserted AS (
        INSERT INTO research.governance_forensic_observations (
          company_id,evidence_id,observation_key,category,observation_status,severity,
          conclusion,disclosed_value,disclosed_unit,period_end,source_page,source_excerpt,
          extraction_method,verification_status,available_at,metadata
        ) SELECT * FROM incoming
        ON CONFLICT (company_id,evidence_id,observation_key,period_end) DO UPDATE SET
          category=EXCLUDED.category,observation_status=EXCLUDED.observation_status,
          severity=EXCLUDED.severity,conclusion=EXCLUDED.conclusion,
          disclosed_value=EXCLUDED.disclosed_value,disclosed_unit=EXCLUDED.disclosed_unit,
          source_page=EXCLUDED.source_page,source_excerpt=EXCLUDED.source_excerpt,
          extraction_method=EXCLUDED.extraction_method,verification_status=EXCLUDED.verification_status,
          available_at=EXCLUDED.available_at,metadata=EXCLUDED.metadata,updated_at=now()
        RETURNING observation_key,category,observation_status,severity,source_page
      ) SELECT json_build_object('written',count(*),'observations',json_agg(row_to_json(upserted) ORDER BY category,observation_key))::text FROM upserted
    """)
    if not isinstance(result, dict):
        raise RuntimeError("governance observation persistence returned an invalid result")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract page-cited governance and forensic disclosures from a retained annual report.")
    parser.add_argument("--source-document-id", type=int, required=True)
    parser.add_argument("--evidence-id", type=int, required=True)
    parser.add_argument("--period-end", required=True)
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()
    datetime.fromisoformat(args.period_end)
    ensure_pdf_runtime()
    from pypdf import PdfReader  # type: ignore

    source = load_source(args.source_document_id, args.evidence_id)
    pdf_path = Path(source["local_pdf_path"])
    if not pdf_path.is_absolute():
        pdf_path = Path(os.environ.get("AI_OS_VAULT_ROOT", Path(__file__).absolute().parents[2])) / pdf_path
    reader = PdfReader(str(pdf_path))
    observations = extract_observations_from_pages([page.extract_text() or "" for page in reader.pages], args.period_end)
    database = persist(source, observations) if args.persist else {"written": 0}
    print(json.dumps({
        "ok": True, "symbol": source["symbol"], "source_document_id": args.source_document_id,
        "evidence_id": args.evidence_id, "observation_count": len(observations),
        "observations": observations, "database": database,
        "capital_action_allowed": False, "broker_write_allowed": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
