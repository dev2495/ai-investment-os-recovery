"""Approval-gated autonomous public-company Research Case execution.

Only explicitly approved, bounded public packets may reach OpenRouter. Private
notes, client data, portfolio state, credentials and raw prompts never leave the
machine. Full outputs are written to the external SSD; Postgres stores hashes,
summaries, citations, receipts and progress.
"""

from __future__ import annotations

import hashlib
import ast
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable


SSD_ROOT = Path("/Volumes/Devarsh SSD")
ARTIFACT_ROOT = SSD_ROOT / "AI OS Data" / "research" / "cases"
RESEARCH_MAX_COMPLETION_TOKENS = 3200
SPECIALIST_ROLES = (
    "company_business", "filings", "financials", "management",
    "industry_moat", "valuation", "bear_risk",
)
ROLE_PLAN = (
    ("company_business", "Company Analyst", "openrouter_public_lead_glm52_canary", 18000, 2600, 2),
    ("filings", "Filings and Transcript Analyst", "openrouter_public_lead_glm52_canary", 22000, 2800, 2),
    ("financials", "Financial Statement Analyst", "openrouter_public_lead_glm52_canary", 30000, 3400, 2),
    ("management", "Management Analyst", "openrouter_public_lead_glm52_canary", 18000, 2400, 2),
    ("industry_moat", "Industry Analyst", "openrouter_public_lead_glm52_canary", 18000, 2500, 2),
    ("valuation", "Valuation Agent", "openrouter_public_lead_glm52_canary", 26000, 3400, 2),
    ("bear_risk", "Bear Case Agent", "openrouter_public_lead_glm52_canary", 18000, 2400, 2),
    ("lead_synthesis", "Long-Term Portfolio Manager", "openrouter_public_lead_glm52_canary", 32000, 4000, 2),
    ("executive_summary", "Research Analyst", "openrouter_public_lead_glm52_canary", 22000, 2800, 2),
    ("independent_review", "Model Validation Agent", "openrouter_public_lead_deepseek_v4_pro_canary", 30000, 3600, 2),
    ("committee_review", "CIO Agent", "openrouter_public_lead_deepseek_v4_pro_canary", 26000, 3200, 1),
)

PACK_SECTION_PLAN = (
    ("investment_conclusion", "Investment conclusion and thesis evolution", "lead_synthesis"),
    ("business_segments", "Business, segments and unit economics", "company_business"),
    ("industry_structure", "Industry, Porter five forces and supply demand", "industry_moat"),
    ("tam_value_chain", "TAM, value chain and profit pools", "industry_moat"),
    ("moat_quality", "Moat and business quality", "industry_moat"),
    ("management_governance", "Management, governance and capital allocation", "management"),
    ("financial_history", "Financial history, ratios and numbers story", "financials"),
    ("forecasts_valuation", "Forecasts, valuation and expected return", "valuation"),
    ("catalysts_risks", "Catalysts, risks and disconfirmers", "bear_risk"),
    ("committee_decision", "Independent review and committee decision", "committee_review"),
)


ROLE_INSTRUCTIONS = {
    "company_business": "Explain the business model, segment economics, product/customer/geographic mix, moat evidence and disconfirmers.",
    "filings": "Map the primary filings, material changes, accounting scope, restatements, disclosure gaps and source chronology.",
    "financials": "Build the multi-year numbers story, margins, cash conversion, balance sheet, capital allocation, ROCE/ROIC drivers and exact gaps. Never treat missing values as zero.",
    "management": "Assess management guidance versus delivery, governance, incentives and capital allocation using exact dated claims.",
    "industry_moat": "Build an evidence-bound industry underwrite: Porter five forces, supply/demand balance, value chain and profit pools, sourced TAM/SAM breakdown, peers, customer concentration, switching costs, pricing power, competitive position, durability, Munger-style business-quality tests and evidence that falsifies each moat claim. Mark every unsupported dimension missing instead of inventing it.",
    "valuation": "Build a reproducible valuation workbench. Separate historical facts, management guidance, external estimates, model assumptions and scenarios. Where inputs exist, cover DCF, reverse DCF, multiples, peer/historical ranges and SOTP only when applicable; expose formulas, current-price/as-of, bull/base/bear, implied return, sensitivities and blocked inputs. Never invent a market price or estimate.",
    "bear_risk": "Build the strongest bear case, permanent-loss paths, forensic signals, catalysts, monitoring metrics and kill conditions.",
    "lead_synthesis": "Integrate specialist outputs into a complete company research pack. Resolve disagreement explicitly and do not upgrade machine-extracted facts to validated facts.",
    "executive_summary": "Write a concise investment-committee synopsis: conclusion state, what changed, 3-5 reasons, valuation limits, catalysts, risks and decision ask.",
    "independent_review": "Independently challenge citations, arithmetic, unsupported certainty, forecast provenance, contradictions and missing disconfirming evidence. Return review_decision passed or needs_revision.",
    "committee_review": "Prepare a decision brief with disagreements, scenario limits, catalysts, risks, kill conditions and a human_decision_ask. You cannot approve capital or trading.",
}


def _sha(value: str | bytes) -> str:
    raw = value if isinstance(value, bytes) else value.encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _num(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except Exception:
        return Decimal(0)


def default_run_plan() -> list[dict[str, Any]]:
    return [
        {
            "role_key": role,
            "agent_name": agent,
            "route_name": route,
            "prompt_tokens_est": prompt_tokens,
            "completion_tokens_max": completion_tokens,
            "max_calls": max_calls,
        }
        for role, agent, route, prompt_tokens, completion_tokens, max_calls in ROLE_PLAN
    ]


def ensure_research_case_preflight(
    case_id: int,
    *,
    actor: str,
    run_rows: Callable[[str], list[dict[str, Any]]],
    create_preflight: Callable[[dict[str, Any]], dict[str, Any]],
    force_new: bool = False,
) -> dict[str, Any]:
    eligible_statuses = "'awaiting_approval'" if force_new else "'awaiting_approval','approved'"
    existing = run_rows(f"""
      SELECT preflight.*,approval.status approval_status
      FROM research.model_run_preflights preflight
      LEFT JOIN agent.approvals approval ON approval.id=preflight.approval_id
      WHERE preflight.research_case_id={int(case_id)}
        AND preflight.request_kind='research_case'
        AND preflight.status IN ({eligible_statuses})
        AND coalesce(preflight.approval_expires_at,now()+interval '1 minute')>now()
      ORDER BY preflight.created_at DESC,preflight.id DESC LIMIT 1
    """)
    if existing:
        row = existing[0]
        row["estimated_cost_inr"] = float(_num(row.get("estimated_cost_usd")) * _num(row.get("exchange_rate_inr_per_usd")))
        row["hard_max_cost_inr"] = float(_num(row.get("hard_max_cost_usd")) * _num(row.get("exchange_rate_inr_per_usd")))
        return row
    return create_preflight({
        "actor": actor,
        "request_kind": "research_case",
        "research_case_id": int(case_id),
        "public_only": True,
        "contains_private_data": False,
        "estimated_storage_bytes": 12_000_000,
        "estimated_duration_seconds": 2700,
        "exchange_rate_inr_per_usd": 87,
        "runs": default_run_plan(),
    })


def _bounded(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return rows[: max(0, limit)]


def _public_packet(case: dict[str, Any], run_rows: Callable[[str], list[dict[str, Any]]], sql_literal: Callable[[Any], str]) -> dict[str, Any]:
    case_id = int(case["id"])
    company_id = int(case["company_id"])
    evidence = _bounded(run_rows(f"""
      SELECT evidence.id,('source:'||evidence.id)::text citation_id,evidence.source_kind,
             evidence.source_identifier,evidence.source_url,evidence.publication_date,
             evidence.effective_date,evidence.captured_at,evidence.parser_status,
             evidence.validation_status,evidence.citation_locator
      FROM research.research_case_evidence evidence
      WHERE evidence.research_case_id={case_id} AND evidence.source_url IS NOT NULL
        AND evidence.source_kind NOT ILIKE 'user_supplied%'
        AND evidence.source_kind NOT ILIKE '%private%'
      ORDER BY coalesce(evidence.publication_date,evidence.effective_date) DESC NULLS LAST,evidence.id DESC
      LIMIT 160
    """), 160)
    filing_documents = _bounded(run_rows(f"""
      SELECT filing.id,('filing:'||filing.id)::text citation_id,filing.source_name,
             filing.exchange,filing.symbol,filing.filing_type,filing.title,filing.filed_at,
             filing.source_url,filing.content_hash,filing.extraction_status,
             filing.pdf_page_count,left(filing.extracted_text,14000) extracted_excerpt
      FROM research.corporate_filings filing
      WHERE upper(filing.symbol)=upper({sql_literal(str(case.get('ticker') or ''))})
        AND filing.source_url IS NOT NULL AND length(coalesce(filing.extracted_text,''))>100
        AND filing.extraction_status IN ('extracted','validated','human_reviewed')
      ORDER BY CASE WHEN lower(coalesce(filing.filing_type,'')) LIKE '%annual%' THEN 0 ELSE 1 END,
        coalesce((filing.payload->>'fiscal_year_end')::integer,extract(year from filing.filed_at)::integer,0) DESC,
        coalesce(filing.filed_at,filing.created_at) DESC,filing.id DESC LIMIT 8
    """), 8)
    facts = _bounded(run_rows(f"""
      SELECT fact.id,('fact:'||fact.id)::text citation_id,fact.fact_key,fact.fiscal_year,
             fact.period_end,fact.statement_type,fact.statement_scope,fact.value,fact.currency,
             fact.unit,fact.source_page,fact.reported_line,fact.extraction_status,
             run.source_url,run.source_sha256,run.status production_status
      FROM research.financial_source_facts fact
      JOIN research.financial_production_runs run ON run.id=fact.production_run_id
      WHERE fact.company_id={company_id} AND fact.extraction_status<>'rejected'
      ORDER BY fact.fiscal_year,fact.statement_type,fact.fact_key LIMIT 650
    """), 650)
    financial_gaps = _bounded(run_rows(f"""
      SELECT id,section_key,metric_key,period_start,period_end,gap_status,reason,next_source
      FROM research.financial_history_gaps WHERE company_id={company_id}
      ORDER BY period_end,metric_key LIMIT 120
    """), 120)
    ratios = _bounded(run_rows(f"""
      SELECT ratio.id,('ratio:'||ratio.id)::text citation_id,formula.formula_key,formula.label,
             formula.version,formula.expression,formula.basis,formula.unit,ratio.period_end,
             ratio.statement_scope,ratio.value,ratio.calculation_status,ratio.not_computable_reason,
             ratio.caveats,run.source_url,run.source_sha256
      FROM research.financial_ratio_results ratio
      JOIN research.financial_formula_definitions formula ON formula.id=ratio.formula_definition_id
      JOIN research.financial_production_runs run ON run.id=ratio.production_run_id
      WHERE ratio.company_id={company_id}
      ORDER BY ratio.period_end,formula.formula_key LIMIT 300
    """), 300)
    segments = _bounded(run_rows(f"""
      SELECT segment.id,('segment:'||segment.id)::text citation_id,segment.fiscal_year,
             segment.period_end,segment.segment_type,segment.segment_key,segment.segment_name,
             segment.metric_key,segment.value,segment.currency,segment.unit,segment.source_page,
             segment.reported_line,segment.extraction_status,segment.exception_reason,
             run.source_url,run.source_sha256
      FROM research.financial_segment_facts segment
      JOIN research.financial_production_runs run ON run.id=segment.production_run_id
      WHERE segment.company_id={company_id} AND segment.extraction_status<>'blocked'
      ORDER BY segment.fiscal_year,segment.segment_type,segment.segment_key,segment.metric_key LIMIT 300
    """), 300)
    operating = _bounded(run_rows(f"""
      SELECT fact.id,('operating:'||fact.id)::text citation_id,fact.metric_key,fact.metric_label,
             fact.metric_group,fact.fiscal_year,fact.period_end,fact.value_numeric,fact.unit,
             fact.currency,fact.consolidation_scope,fact.fact_basis,fact.source_locator,
             fact.extraction_status,fact.validation_status,item.source_url,item.content_hash source_sha256
      FROM research.official_operating_history_facts fact
      JOIN research.thesis_source_items item ON item.id=fact.source_item_id
      WHERE fact.company_id={company_id} AND fact.validation_status<>'rejected'
      ORDER BY fact.fiscal_year,fact.metric_group,fact.metric_key LIMIT 300
    """), 300)
    kpis = _bounded(run_rows(f"""
      SELECT observation.id,('kpi:'||observation.id)::text citation_id,definition.kpi_key,
             definition.kpi_name,definition.description,definition.unit,definition.frequency,
             observation.period_end,observation.value_numeric,observation.value_text,
             observation.source_as_of_date,observation.source_locator,evidence.source_url,
             evidence.verification_status
      FROM research.operational_kpi_observations observation
      JOIN research.operational_kpi_definitions definition ON definition.id=observation.kpi_definition_id
      JOIN research.fundamental_evidence evidence ON evidence.id=observation.evidence_id
      WHERE observation.company_id={company_id} AND evidence.source_url IS NOT NULL
      ORDER BY observation.period_end,definition.kpi_key LIMIT 250
    """), 250)
    industry = _bounded(run_rows(f"""
      SELECT observation.id,('industry:'||observation.id)::text citation_id,
             observation.observation_key,observation.category,observation.conclusion,
             observation.value_numeric,observation.unit,observation.metric_availability,
             observation.period_end,observation.source_page,observation.source_excerpt,
             observation.verification_status,evidence.source_url
      FROM research.industry_competitive_observations observation
      JOIN research.fundamental_evidence evidence ON evidence.id=observation.evidence_id
      WHERE observation.company_id={company_id} AND evidence.source_url IS NOT NULL
        AND observation.verification_status NOT IN ('rejected','superseded')
      ORDER BY observation.period_end DESC,observation.id DESC LIMIT 120
    """), 120)
    management = _bounded(run_rows(f"""
      SELECT claim.id,('management:'||claim.id)::text citation_id,claim.claim_date,
             claim.speaker_name,claim.speaker_role,claim.claim_type,claim.claim_text,
             claim.metric_key,claim.target_operator,claim.target_value,claim.target_unit,
             claim.target_period_end,claim.claim_status,claim.source_locator,evidence.source_url,
             evidence.verification_status,outcome.outcome_date,outcome.outcome_status,
             outcome.actual_value,outcome.actual_unit,outcome.assessment
      FROM research.management_claims claim
      JOIN research.fundamental_evidence evidence ON evidence.id=claim.evidence_id
      LEFT JOIN LATERAL (
        SELECT * FROM research.management_claim_outcomes selected
        WHERE selected.claim_id=claim.id ORDER BY selected.outcome_date DESC,selected.id DESC LIMIT 1
      ) outcome ON true
      WHERE claim.company_id={company_id} AND evidence.source_url IS NOT NULL
      ORDER BY claim.claim_date DESC,claim.id DESC LIMIT 120
    """), 120)
    market_quote = _bounded(run_rows(f"""
      SELECT ('market:'||provider||':'||instrument_token)::text citation_id,provider,provider_symbol,
             symbol,exchange,instrument_type,last_price,previous_close,exchange_timestamp,received_at,source_mode
      FROM market.live_quote_state
      WHERE upper(symbol)=upper({sql_literal(str(case.get('ticker') or ''))})
        AND broker_write_allowed=false
      ORDER BY received_at DESC LIMIT 1
    """), 1)
    packet = {
        "case": {
            "id": case_id, "case_key": case.get("case_key"), "company_id": company_id,
            "company_name": case.get("company_name"), "ticker": case.get("ticker"),
            "exchange": case.get("exchange"), "mandate": case.get("mandate"),
            "horizon": case.get("horizon"), "as_of": datetime.now(timezone.utc).date().isoformat(),
        },
        "evidence": evidence, "filing_documents": filing_documents,
        "financial_facts": facts, "financial_gaps": financial_gaps, "ratios": ratios,
        "segments": segments, "operating_history": operating, "operating_kpis": kpis,
        "industry": industry, "management_guidance": management, "market_quote": market_quote,
        "boundaries": {
            "public_only": True, "private_data_egress_allowed": False,
            "external_write_allowed": False, "broker_write_allowed": False,
            "raw_prompt_stored": False, "accepted_financial_numeric_requires_status": "validated_or_human_reviewed",
            "qualitative_official_filing_rule": "extracted narrative may support qualitative claims when its extracted status is explicit",
        },
    }
    return packet


def prepare_research_case_runtime(
    case_id: int,
    preflight_id: int,
    *,
    actor: str,
    run_rows: Callable[[str], list[dict[str, Any]]],
    run_statement: Callable[[str], list[dict[str, Any]]],
    sql_literal: Callable[[Any], str],
    sql_jsonb: Callable[[Any], str],
    force_new_iteration: bool = False,
) -> dict[str, Any]:
    gate = run_rows(f"""
      SELECT case_row.*,preflight.id preflight_id,preflight.status preflight_status,
             preflight.public_only,preflight.private_data_egress_allowed,
             preflight.external_write_allowed,preflight.broker_write_allowed,
             preflight.approval_id,approval.status approval_status
      FROM research.research_cases case_row
      JOIN research.model_run_preflights preflight ON preflight.research_case_id=case_row.id
      JOIN agent.approvals approval ON approval.id=preflight.approval_id
      WHERE case_row.id={int(case_id)} AND preflight.id={int(preflight_id)} LIMIT 1
    """)
    if not gate:
        raise ValueError("approved Research Case model preflight was not found")
    case = gate[0]
    if case.get("preflight_status") != "approved" or case.get("approval_status") != "approved":
        raise ValueError("Research Case cost and public-data boundary must be explicitly approved before Start")
    if not bool(case.get("public_only")) or bool(case.get("private_data_egress_allowed")) or bool(case.get("external_write_allowed")) or bool(case.get("broker_write_allowed")):
        raise ValueError("Research Case preflight violates the public-only, no-write boundary")
    section_values = ",".join(
        f"({int(case_id)},{sql_literal(section_key)},{sql_literal(title)},{sql_literal(owner_role)},1)"
        for section_key, title, owner_role in PACK_SECTION_PLAN
    )
    run_statement(f"""
      WITH inserted AS (
        INSERT INTO research.research_pack_sections (
          research_case_id,section_key,title,owner_role,version
        ) VALUES {section_values}
        ON CONFLICT (research_case_id,section_key,version) DO NOTHING
        RETURNING id
      )
      SELECT coalesce(json_agg(row_to_json(inserted)),json_build_array())::text
      FROM inserted
    """)
    existing_runs = run_rows(f"""
      SELECT count(*)::integer model_run_count,
             count(*) FILTER (WHERE status='queued')::integer queued_count,
             min(public_packet_id)::bigint public_packet_id
      FROM research.research_case_model_runs
      WHERE research_case_id={int(case_id)} AND preflight_id={int(preflight_id)}
    """)
    if existing_runs and _int(existing_runs[0].get("model_run_count")) and not force_new_iteration:
        return {
            "public_packet_id": _int(existing_runs[0].get("public_packet_id")),
            "model_run_count": _int(existing_runs[0].get("model_run_count")),
            "queued_count": _int(existing_runs[0].get("queued_count")),
            "preflight_id": int(preflight_id), "idempotent_reuse": True,
            "private_data_egress_allowed": False, "capital_action_allowed": False,
        }
    iteration_rows = run_rows(f"SELECT coalesce(max(iteration),0)+1 next_iteration FROM research.research_case_model_runs WHERE research_case_id={int(case_id)}")
    iteration = _int((iteration_rows or [{"next_iteration": 1}])[0].get("next_iteration"), 1) if force_new_iteration else 1
    packet = _public_packet(case, run_rows, sql_literal)
    encoded = json.dumps(packet, sort_keys=True, separators=(",", ":"), default=str)
    packet_hash = _sha(encoded)
    source_ids = sorted({
        str(row.get("citation_id"))
        for key in ("evidence", "filing_documents", "financial_facts", "ratios", "segments", "operating_history", "operating_kpis", "industry", "management_guidance", "market_quote")
        for row in packet.get(key, []) if row.get("citation_id")
    })
    packet_key = f"case-{int(case_id)}-{packet_hash[:16]}"
    packet_rows = run_statement(f"""
      WITH version_row AS (
        SELECT coalesce(max(packet_version),0)+1 next_version
        FROM research.research_case_public_packets WHERE research_case_id={int(case_id)}
      ), inserted AS (
        INSERT INTO research.research_case_public_packets (
          research_case_id,preflight_id,packet_key,packet_version,source_count,source_ids,
          public_context,packet_hash,contains_private_data,contains_client_data,
          approved_for_cloud_at,approved_for_cloud_by,created_by
        ) SELECT {int(case_id)},{int(preflight_id)},{sql_literal(packet_key)},next_version,
          {len(source_ids)},{sql_jsonb(source_ids)},{sql_jsonb(packet)},{sql_literal(packet_hash)},
          false,false,now(),{sql_literal(actor)},{sql_literal(actor)} FROM version_row
        ON CONFLICT (packet_key) DO UPDATE SET preflight_id=EXCLUDED.preflight_id
        RETURNING *
      ) SELECT coalesce(json_agg(row_to_json(inserted)),'[]'::json)::text FROM inserted
    """)
    if not packet_rows:
        raise RuntimeError("public Research Case packet was not persisted")
    public_packet = packet_rows[0]
    packet_id = int(public_packet["id"])
    model_rows = []
    for role, agent, route, _, _, _ in ROLE_PLAN:
        route_rows = run_rows(f"SELECT default_model FROM agent.model_routes WHERE route_name={sql_literal(route)} LIMIT 1")
        if not route_rows:
            raise ValueError(f"model route is unavailable: {route}")
        initial_status = "queued" if role in SPECIALIST_ROLES else "awaiting_dependencies"
        run_key = f"case-{case_id}-i{iteration}-{role}-a1-{packet_hash[:12]}"
        output_contract = {"strict_json": True, "citation_ids_must_match_packet": True, "human_final_authority": True}
        inserted = run_statement(f"""
          WITH inserted AS (
            INSERT INTO research.research_case_model_runs (
              research_case_id,public_packet_id,preflight_id,role_key,agent_name,run_key,
              iteration,attempt,status,route_name,provider,model_name,output_contract
            ) VALUES ({int(case_id)},{packet_id},{int(preflight_id)},{sql_literal(role)},
              {sql_literal(agent)},{sql_literal(run_key)},{iteration},1,{sql_literal(initial_status)},
              {sql_literal(route)},'openrouter',{sql_literal(route_rows[0]['default_model'])},{sql_jsonb(output_contract)})
            ON CONFLICT (research_case_id,role_key,iteration,attempt) DO UPDATE SET
              public_packet_id=EXCLUDED.public_packet_id,preflight_id=EXCLUDED.preflight_id,
              route_name=EXCLUDED.route_name,model_name=EXCLUDED.model_name,
              status=CASE WHEN research.research_case_model_runs.status IN ('completed','running')
                          THEN research.research_case_model_runs.status ELSE EXCLUDED.status END,
              updated_at=now() RETURNING *
          ) SELECT coalesce(json_agg(row_to_json(inserted)),'[]'::json)::text FROM inserted
        """)
        if inserted:
            model_rows.append(inserted[0])
    run_statement(f"""
      WITH superseded AS (
        UPDATE research.research_case_model_runs SET status='needs_revision',
          exception_detail=concat_ws('; ',NULLIF(exception_detail,''),
            {sql_literal('superseded_by_iteration_'+str(iteration))}),
          finished_at=coalesce(finished_at,now()),updated_at=now()
        WHERE research_case_id={int(case_id)} AND iteration<{iteration}
          AND status IN ('awaiting_dependencies','queued','blocked','failed') RETURNING id
      ), updated AS (
        UPDATE research.research_case_agent_runs agent_run SET
          status=CASE WHEN agent_run.role_key IN ({','.join(sql_literal(role) for role in SPECIALIST_ROLES)}) THEN 'queued' ELSE 'awaiting_dependencies' END,
          updated_at=now()
        WHERE agent_run.research_case_id={int(case_id)} RETURNING id
      ), case_iteration AS (
        UPDATE research.research_cases SET iteration_count=GREATEST(iteration_count,{iteration}),
          status='active',lead_status='specialists_running',
          current_goal='Run approved specialist analysis through independent review and committee gating',
          decision_readiness='needs_research',last_progress_at=now(),updated_at=now()
        WHERE id={int(case_id)} RETURNING id
      ), event AS (
        INSERT INTO research.research_case_events (research_case_id,event_type,event_status,event_summary,actor,event_payload)
        VALUES ({int(case_id)},'model_runtime_authorized','recorded',
          'Public-only autonomous research authorized within the approved cost ceiling; final investment decision remains human.',
          {sql_literal(actor)},{sql_jsonb({'preflight_id': int(preflight_id), 'public_packet_id': packet_id, 'source_count': len(source_ids), 'model_run_count': len(model_rows), 'iteration': iteration, 'private_data_egress_allowed': False, 'capital_action_allowed': False})})
        RETURNING id
      ) SELECT coalesce(json_agg(json_build_object('updated_agent_runs',(SELECT count(*) FROM updated),'event_id',event.id)),'[]'::json)::text FROM event
    """)
    return {
        "public_packet_id": packet_id, "packet_hash": packet_hash,
        "source_count": len(source_ids), "model_run_count": len(model_rows), "iteration": iteration,
        "queued_roles": list(SPECIALIST_ROLES), "preflight_id": int(preflight_id),
        "private_data_egress_allowed": False, "capital_action_allowed": False,
    }


def _strip_json_fence(value: str) -> str:
    candidate = (value or "").strip()
    if candidate.startswith("```"):
        candidate = candidate.split("\n", 1)[1] if "\n" in candidate else ""
        candidate = candidate.rsplit("```", 1)[0].strip()
    return candidate


def _parse_structured_output(value: str) -> dict[str, Any]:
    """Parse JSON or a safe literal object, then apply the strict contract validator."""
    candidate = _strip_json_fence(value)
    if not candidate:
        raise ValueError("empty_model_output")
    attempts = [candidate]
    first = candidate.find("{")
    last = candidate.rfind("}")
    if first >= 0 and last > first and candidate[first:last + 1] != candidate:
        attempts.append(candidate[first:last + 1])
    errors: list[str] = []
    for payload in attempts:
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            errors.append(f"json:{exc.msg}")
        else:
            if isinstance(parsed, dict):
                return parsed
        try:
            parsed = ast.literal_eval(payload)
        except (SyntaxError, ValueError) as exc:
            errors.append(f"literal:{type(exc).__name__}")
        else:
            if isinstance(parsed, dict):
                return parsed
    raise ValueError("structured_output_parse_failed:" + ",".join(errors[:4]))


def _sanitize_output_citations(output: dict[str, Any], allowed_ids: set[str]) -> dict[str, Any]:
    """Remove unsupported draft claims without weakening the citation gate.

    Packet labels and case identifiers are not evidence. Unsupported fact rows
    are dropped and recorded as evidence debt; non-factual narrative keeps only
    approved citations. This never manufactures or remaps a source.
    """
    dropped: list[str] = []
    for section in ("facts", "analysis", "calculations", "risks", "disconfirmers"):
        values = output.get(section)
        if not isinstance(values, list):
            continue
        cleaned: list[dict[str, Any]] = []
        for index, item in enumerate(values):
            if not isinstance(item, dict):
                if section == "facts":
                    dropped.append(f"Unsupported {section} item {index} was removed because it was not structured or source-linked.")
                    continue
                item = {"finding": str(item), "citation_ids": []}
            ids = item.get("citation_ids") or []
            if not isinstance(ids, list):
                ids = []
            item["citation_ids"] = [str(value) for value in ids if str(value) in allowed_ids]
            if section == "facts" and not item["citation_ids"]:
                dropped.append(f"Unsupported draft fact {index} was removed because it had no approved source citation.")
                continue
            cleaned.append(item)
        output[section] = cleaned
    for section in ("missing", "source_requests"):
        values = output.get(section)
        if not isinstance(values, list):
            continue
        for item in values:
            if isinstance(item, dict) and "citation_ids" in item:
                ids = item.get("citation_ids") or []
                item["citation_ids"] = [str(value) for value in ids if str(value) in allowed_ids] if isinstance(ids, list) else []
    if dropped:
        missing = output.setdefault("missing", [])
        if isinstance(missing, list):
            missing.extend({"item": detail, "citation_ids": []} for detail in dropped)
    return output


def _validate_output(role: str, output: Any, allowed_ids: set[str]) -> tuple[bool, list[str], list[str]]:
    errors: list[str] = []
    cited: set[str] = set()
    if not isinstance(output, dict):
        return False, ["output_not_object"], []
    # Normalising an omitted optional collection to [] adds no factual claim and
    # avoids wasting a paid retry on formatting alone.
    collection_keys = (
        "facts", "analysis", "calculations", "assumptions", "risks",
        "disconfirmers", "missing", "source_requests",
    )
    for key in collection_keys:
        output.setdefault(key, [])

    # Canonicalise a namespace slip only when the numeric suffix maps to exactly
    # one approved packet citation (for example source:6990 -> filing:6990).
    suffix_index: dict[str, list[str]] = {}
    for allowed_id in allowed_ids:
        prefix, separator, suffix = allowed_id.partition(":")
        if prefix and separator and suffix.isdigit():
            suffix_index.setdefault(suffix, []).append(allowed_id)
    for key in ("summary", "facts", "analysis", "calculations", "assumptions", "risks", "disconfirmers", "missing", "source_requests"):
        if key not in output:
            errors.append(f"missing_key:{key}")
    for section in ("facts", "analysis", "calculations", "risks", "disconfirmers"):
        values = output.get(section) or []
        if not isinstance(values, list):
            errors.append(f"not_list:{section}")
            continue
        for index, item in enumerate(values):
            if not isinstance(item, dict):
                errors.append(f"not_object:{section}:{index}")
                continue
            ids = item.get("citation_ids") or []
            if section == "facts" and not ids:
                errors.append(f"uncited_fact:{index}")
            if not isinstance(ids, list):
                errors.append(f"citation_ids_not_list:{section}:{index}")
                continue
            for citation_index, citation_id in enumerate(ids):
                citation = str(citation_id)
                if citation not in allowed_ids:
                    _, separator, suffix = citation.partition(":")
                    candidates = suffix_index.get(suffix, []) if separator and suffix.isdigit() else []
                    if len(candidates) == 1:
                        citation = candidates[0]
                        ids[citation_index] = citation
                cited.add(citation)
                if citation not in allowed_ids:
                    errors.append(f"unknown_citation:{citation}")
    if role == "independent_review" and str(output.get("review_decision") or "") not in {"passed", "needs_revision"}:
        errors.append("invalid_review_decision")
    if role == "committee_review" and not str(output.get("human_decision_ask") or "").strip():
        errors.append("missing_human_decision_ask")
    return not errors, errors, sorted(cited)


def _role_context(role: str, packet: dict[str, Any], completed: list[dict[str, Any]]) -> dict[str, Any]:
    base = {"case": packet.get("case"), "boundaries": packet.get("boundaries")}
    keys_by_role = {
        "company_business": ("evidence", "filing_documents", "segments", "operating_history", "operating_kpis", "industry"),
        "filings": ("evidence", "filing_documents", "financial_facts", "segments", "management_guidance"),
        "financials": ("financial_facts", "financial_gaps", "ratios", "segments", "operating_history"),
        "management": ("management_guidance", "evidence", "filing_documents", "financial_facts"),
        "industry_moat": ("industry", "operating_kpis", "segments", "evidence", "filing_documents"),
        "valuation": ("financial_facts", "financial_gaps", "ratios", "operating_history", "industry", "market_quote"),
        "bear_risk": ("financial_facts", "financial_gaps", "ratios", "management_guidance", "industry", "evidence", "filing_documents"),
    }
    if role in keys_by_role:
        for key in keys_by_role[role]:
            base[key] = packet.get(key) or []
    else:
        base["specialist_outputs"] = [
            {
                "role_key": row.get("role_key"),
                "summary": str((row.get("output_summary") or {}).get("summary") or "")[:1800],
                "facts": ((row.get("output_summary") or {}).get("facts") or [])[:4],
                "analysis": ((row.get("output_summary") or {}).get("analysis") or [])[:4],
                "calculations": ((row.get("output_summary") or {}).get("calculations") or [])[:3],
                "risks": ((row.get("output_summary") or {}).get("risks") or [])[:3],
                "missing": ((row.get("output_summary") or {}).get("missing") or [])[:4],
                "review_decision": (row.get("output_summary") or {}).get("review_decision"),
                "revision_requests": ((row.get("output_summary") or {}).get("revision_requests") or [])[:4],
            }
            for row in completed
        ]
        if role in {"lead_synthesis", "executive_summary", "independent_review", "committee_review"}:
            base["validated_financial_facts"] = [
                {
                    "citation_id": row.get("citation_id"), "fact_key": row.get("fact_key"),
                    "fiscal_year": row.get("fiscal_year"), "value": row.get("value"),
                    "unit": row.get("unit"),
                    "display_value_crore": (float(row.get("value")) / 100.0)
                        if row.get("unit") == "lakh" and row.get("value") is not None else None,
                    "display_unit": "INR crore" if row.get("unit") == "lakh" else row.get("unit"), "statement_scope": row.get("statement_scope"),
                    "status": row.get("extraction_status"),
                }
                for row in packet.get("financial_facts", [])
                if row.get("citation_id") and row.get("extraction_status") in {"validated", "human_reviewed"}
            ][:400]
            base["financial_gaps"] = packet.get("financial_gaps") or []
            base["market_quote"] = packet.get("market_quote") or []
        if role in {"independent_review", "committee_review"}:
            base["source_index"] = [
                {"citation_id": row.get("citation_id"), "source_url": row.get("source_url"), "status": row.get("validation_status") or row.get("extraction_status") or row.get("verification_status")}
                for key in ("evidence", "filing_documents", "financial_facts", "ratios", "segments", "operating_history", "operating_kpis", "industry", "management_guidance", "market_quote")
                for row in packet.get(key, []) if row.get("citation_id")
            ][:900]
    return base


def _prompt(role: str, context: dict[str, Any]) -> tuple[str, str]:
    contract = {
        "role_key": role, "summary": "string", "facts": [{"claim": "string", "value": "string or number", "citation_ids": ["allowed id"]}],
        "analysis": [{"point": "string", "citation_ids": ["allowed id"]}],
        "calculations": [{"label": "string", "formula": "string", "inputs": {}, "result": "string or number", "citation_ids": ["allowed id"]}],
        "assumptions": [], "risks": [{"risk": "string", "monitor": "string", "citation_ids": []}],
        "disconfirmers": [{"condition": "string", "citation_ids": []}], "missing": [], "source_requests": [],
    }
    if role == "independent_review":
        contract.update({"review_decision": "passed or needs_revision", "blocking_findings": [], "revision_requests": []})
    if role == "committee_review":
        contract.update({"human_decision_ask": "string"})
    system = (
        "You are an institutional public-company research agent. Work only from the supplied approved public packet and completed role outputs. "
        "Never browse, call tools, infer an absent number, treat missing as zero, expose private data, or authorize a trade. "
        "Every factual or numeric claim must cite packet citation_ids. Financial numerics accepted as facts require validated or human-reviewed fact citations; do not use a machine-extracted evidence summary as numeric truth. Values whose unit is INR lakh must be used exactly as supplied. When display_value_crore is provided, use that value only with the label INR crore; never label a crore conversion as lakh. Never divide or multiply values merely for display. Official filing excerpts marked extracted may support qualitative business, management and industry claims when that status is explicit. Cash-flow outflows retain their negative accounting sign; use absolute value only inside a formula that says so. Never derive share count from PAT divided by EPS unless explicitly labeled an estimate. Clearly separate facts, management guidance, model assumptions, inference and missing evidence.  Return one complete strict JSON object only, under 800 words. Keep facts and analysis to at most 6 items each, calculations to 4, and every other array to 5, using empty arrays when unavailable."
    )
    bounded_context = dict(context)
    while len(json.dumps(bounded_context, separators=(",", ":"), default=str)) > 110_000:
        list_keys = [key for key, value in bounded_context.items() if isinstance(value, list) and len(value) > 8]
        if not list_keys:
            break
        largest = max(list_keys, key=lambda key: len(json.dumps(bounded_context[key], default=str)))
        bounded_context[largest] = bounded_context[largest][: max(8, len(bounded_context[largest]) // 2)]
    prompt = json.dumps({
        "instruction": ROLE_INSTRUCTIONS[role], "required_contract": contract,
        "review_rule": "For independent review, disclosed evidence gaps alone are not a rejection reason. Pass an evidence-debt pack when every presented claim is supported, calculations are reproducible, and missing inputs are explicit; reject only unsupported or internally inconsistent claims.",
        "context": bounded_context,
    }, separators=(",", ":"), default=str)
    return system, prompt


def _write_artifact(case_key: str, run_key: str, payload: dict[str, Any]) -> tuple[str, str]:
    durable_parent = SSD_ROOT / "AI OS Data"
    if not SSD_ROOT.is_mount() or not durable_parent.is_dir() or not os.access(str(durable_parent), os.W_OK):
        raise RuntimeError("external SSD is not mounted and writable; no internal-disk fallback is allowed")
    target_dir = ARTIFACT_ROOT / re.sub(r"[^a-zA-Z0-9._-]+", "-", case_key)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "agent-runs" / f"{re.sub(r'[^a-zA-Z0-9._-]+', '-', run_key)}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n").encode("utf-8")
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".agent-run-", suffix=".tmp", delete=False) as handle:
        handle.write(encoded)
        temporary = Path(handle.name)
    os.replace(temporary, target)
    return str(target), _sha(encoded)


def _unlock_next(case_id: int, iteration: int, role: str, output: dict[str, Any], run_statement, sql_literal, sql_jsonb) -> None:
    if role in SPECIALIST_ROLES:
        next_role = "lead_synthesis"
        condition = f"(SELECT count(*) FROM research.research_case_model_runs WHERE research_case_id={case_id} AND iteration={iteration} AND role_key IN ({','.join(sql_literal(item) for item in SPECIALIST_ROLES)}) AND status='completed')={len(SPECIALIST_ROLES)}"
    elif role == "lead_synthesis":
        next_role, condition = "executive_summary", "true"
    elif role == "executive_summary":
        next_role, condition = "independent_review", "true"
    elif role == "independent_review":
        if output.get("review_decision") == "needs_revision":
            run_statement(f"""
              WITH current_review AS (
                SELECT max(attempt)::integer attempt FROM research.research_case_model_runs
                WHERE research_case_id={case_id} AND iteration={iteration} AND role_key='independent_review'
              ), blocked AS (
                UPDATE research.research_cases SET status='blocked',lead_status='independent_review_blocked',
                  decision_readiness='needs_research',exception_count=exception_count+1,
                  last_progress_at=now(),updated_at=now()
                WHERE id={case_id} AND (SELECT attempt FROM current_review)>=4 RETURNING id
              ), preflight_complete AS (
                UPDATE research.model_run_preflights SET status='completed',completed_at=now(),updated_at=now()
                WHERE id=(SELECT preflight_id FROM research.research_case_model_runs
                  WHERE research_case_id={case_id} AND iteration={iteration} AND role_key='independent_review'
                  ORDER BY attempt DESC,id DESC LIMIT 1)
                  AND status='approved' AND EXISTS (SELECT 1 FROM blocked) RETURNING id
              ), blocker_updated AS (
                UPDATE research.research_case_blockers SET status='open',
                  system_action='All approved in-ceiling reconciliation attempts are exhausted; completed evidence and drafts are preserved.',
                  user_action='Prepare a fresh cost plan for additional research, or keep the case blocked as an evidence-debt record.',
                  updated_at=now() WHERE research_case_id={case_id} AND blocker_key='independent_review'
                    AND EXISTS (SELECT 1 FROM blocked) RETURNING id
              ), marked AS (
                UPDATE research.research_case_model_runs SET status='needs_revision',updated_at=now()
                WHERE research_case_id={case_id} AND iteration={iteration}
                  AND role_key IN ('lead_synthesis','executive_summary','independent_review')
                  AND attempt=(SELECT attempt FROM current_review)
                  AND status='completed' RETURNING id
              ), revision_runs AS (
                INSERT INTO research.research_case_model_runs (
                  research_case_id,public_packet_id,preflight_id,role_key,agent_name,run_key,
                  iteration,attempt,status,route_name,provider,model_name,output_contract
                )
                SELECT prior.research_case_id,prior.public_packet_id,prior.preflight_id,prior.role_key,
                  prior.agent_name,prior.run_key||'-revision-'||((SELECT attempt FROM current_review)+1),
                  prior.iteration,(SELECT attempt FROM current_review)+1,
                  CASE WHEN prior.role_key='lead_synthesis' THEN 'queued' ELSE 'awaiting_dependencies' END,
                  prior.route_name,prior.provider,prior.model_name,prior.output_contract
                FROM research.research_case_model_runs prior
                WHERE prior.research_case_id={case_id} AND prior.iteration={iteration}
                  AND prior.role_key IN ('lead_synthesis','executive_summary','independent_review')
                  AND prior.attempt=(SELECT attempt FROM current_review)
                  AND NOT EXISTS (SELECT 1 FROM blocked)
                ON CONFLICT (research_case_id,role_key,iteration,attempt) DO NOTHING RETURNING role_key
              ), agent_updated AS (
                UPDATE research.research_case_agent_runs SET
                  status=CASE WHEN role_key='lead_synthesis' THEN 'queued' ELSE 'awaiting_dependencies' END,
                  exceptions=coalesce(exceptions,'[]'::jsonb)||{sql_jsonb([{'kind': 'independent_review_revision', 'detail': item} for item in (output.get('revision_requests') or [])])},
                  updated_at=now()
                WHERE research_case_id={case_id}
                  AND role_key IN ('lead_synthesis','executive_summary','independent_review')
                  AND NOT EXISTS (SELECT 1 FROM blocked) RETURNING id
              ), event AS (
                INSERT INTO research.research_case_events (research_case_id,event_type,event_status,event_summary,actor,event_payload)
                VALUES ({case_id},'independent_review',
                  CASE WHEN EXISTS (SELECT 1 FROM blocked) THEN 'blocked' ELSE 'needs_revision' END,
                  CASE WHEN EXISTS (SELECT 1 FROM blocked)
                    THEN 'Independent review still found blocking issues after the bounded revision; human input is required.'
                    ELSE 'Independent reviewer returned the pack for one bounded revision.' END,
                  'Model Validation Agent',{sql_jsonb({'revision_requests': output.get('revision_requests') or [], 'blocking_findings': output.get('blocking_findings') or [], 'max_review_attempts': 4})}) RETURNING id
              ) SELECT coalesce(json_agg(row_to_json(event)),'[]'::json)::text FROM event
            """)
            return
        run_statement(f"""
          WITH resolved AS (
            UPDATE research.research_case_blockers SET status='resolved',resolved_at=now(),
              resolution='Independent review passed the reconciled pack; committee review is queued.',
              user_action=NULL,updated_at=now()
            WHERE research_case_id={case_id} AND blocker_key='independent_review'
              AND status IN ('open','retrying') RETURNING id
          ) SELECT coalesce(json_agg(row_to_json(resolved)),'[]'::json)::text FROM resolved
        """)
        next_role, condition = "committee_review", "true"
    else:
        run_statement(f"""
          WITH preflight_complete AS (
            UPDATE research.model_run_preflights SET status='completed',completed_at=now(),updated_at=now()
            WHERE id=(SELECT preflight_id FROM research.research_case_model_runs
                      WHERE research_case_id={case_id} AND role_key='committee_review'
                      ORDER BY iteration DESC,attempt DESC LIMIT 1) AND status='approved' RETURNING id
          ), approval AS (
            INSERT INTO agent.approvals (approval_type,title,owner_agent,risk_level,status,requested_action,rationale)
            VALUES ('research_case_review',{sql_literal('Review complete company research pack for case '+str(case_id))},'Long-Term Portfolio Manager','medium','pending',
              {sql_jsonb({'research_case_id': case_id, 'decision_options': ['research_more','monitor','approve_watchlist','approve_hold','reject'], 'capital_action_allowed': False, 'live_execution_allowed': False})},
              'Committee brief is advisory. Human review cannot place an order or mutate broker/client systems.') RETURNING id
          ), updated AS (
            UPDATE research.research_cases SET status='review',lead_status='committee_brief_ready',
              decision_readiness='awaiting_human_review',last_progress_at=now(),updated_at=now()
            WHERE id={case_id} RETURNING id
          ), event AS (
            INSERT INTO research.research_case_events (research_case_id,event_type,event_status,event_summary,actor,event_payload)
            SELECT {case_id},'committee_brief_ready','awaiting_human_review','Autonomous research and independent review finished; the decision remains with the user.','CIO Agent',
              jsonb_build_object('approval_id',approval.id,'capital_action_allowed',false,'live_execution_allowed',false) FROM approval RETURNING id
          ) SELECT coalesce(json_agg(json_build_object('approval_id',approval.id,'case_id',updated.id)),'[]'::json)::text FROM approval CROSS JOIN updated
        """)
        return
    run_statement(f"""
      WITH updated AS (
        UPDATE research.research_case_model_runs SET status='queued',updated_at=now()
        WHERE research_case_id={case_id} AND iteration={iteration} AND role_key={sql_literal(next_role)}
          AND status='awaiting_dependencies' AND ({condition}) RETURNING id
      ) SELECT coalesce(json_agg(row_to_json(updated)),'[]'::json)::text FROM updated
    """)


def _retry_or_block(run: dict[str, Any], errors: list[str], run_statement, sql_literal, sql_jsonb) -> str:
    case_id = int(run["research_case_id"])
    attempt = int(run.get("attempt") or 1)
    iteration = int(run.get("iteration") or 1)
    role = str(run["role_key"])
    current_iteration = run_statement(f"""
      WITH current_case AS (
        SELECT iteration_count FROM research.research_cases WHERE id={case_id}
      )
      SELECT coalesce(json_agg(row_to_json(current_case)),'[]'::json)::text
      FROM current_case
    """)
    if current_iteration and int(current_iteration[0].get("iteration_count") or 0) != iteration:
        run_statement(f"""
          WITH updated AS (
            UPDATE research.research_case_model_runs SET status='needs_revision',
              exception_detail=concat_ws('; ',NULLIF(exception_detail,''),
                {sql_literal('superseded_by_iteration_'+str(current_iteration[0].get('iteration_count')))}),
              finished_at=coalesce(finished_at,now()),updated_at=now()
            WHERE id={int(run['id'])} RETURNING id
          ) SELECT coalesce(json_agg(row_to_json(updated)),'[]'::json)::text FROM updated
        """)
        return "superseded"
    retrying = attempt < 2
    next_key = f"{run['run_key']}-retry-{attempt + 1}"
    run_statement(f"""
      WITH retry AS (
        INSERT INTO research.research_case_model_runs (
          research_case_id,public_packet_id,preflight_id,role_key,agent_name,run_key,
          iteration,attempt,status,route_name,provider,model_name,output_contract
        ) SELECT research_case_id,public_packet_id,preflight_id,role_key,agent_name,
          {sql_literal(next_key)},iteration,{attempt + 1},'queued',route_name,provider,model_name,output_contract
        FROM research.research_case_model_runs WHERE id={int(run['id'])} AND {str(retrying).lower()}
        ON CONFLICT (research_case_id,role_key,iteration,attempt) DO NOTHING RETURNING id
      ), agent_updated AS (
        UPDATE research.research_case_agent_runs SET
          status=CASE WHEN {str(retrying).lower()} THEN 'queued' ELSE 'needs_validation' END,
          exceptions=coalesce(exceptions,'[]'::jsonb)||{sql_jsonb([{'kind': 'model_run_failure', 'attempt': attempt, 'detail': item} for item in errors])},
          updated_at=now()
        WHERE research_case_id={case_id} AND role_key={sql_literal(role)}
        RETURNING graph_node_run_id,task_id
      ), node_updated AS (
        UPDATE agent.graph_node_runs SET
          status=CASE WHEN {str(retrying).lower()} THEN 'queued' ELSE 'failed' END,
          error={sql_jsonb({'model_run_id': int(run['id']), 'errors': errors, 'retry_scheduled': retrying})},
          finished_at=CASE WHEN {str(retrying).lower()} THEN NULL ELSE now() END,updated_at=now()
        WHERE id=(SELECT graph_node_run_id FROM agent_updated LIMIT 1) RETURNING task_id
      ), task_updated AS (
        UPDATE agent.tasks SET status=CASE WHEN {str(retrying).lower()} THEN 'queued' ELSE 'blocked' END,
          updated_at=now() WHERE id=(SELECT task_id FROM node_updated LIMIT 1) RETURNING id
      ), case_updated AS (
        UPDATE research.research_cases SET
          status=CASE WHEN {str(retrying).lower()} THEN status ELSE 'blocked' END,
          lead_status=CASE WHEN {str(retrying).lower()} THEN 'bounded_retry' ELSE 'agent_run_blocked' END,
          decision_readiness=CASE WHEN {str(retrying).lower()} THEN decision_readiness ELSE 'needs_research' END,
          exception_count=exception_count+1,last_progress_at=now(),updated_at=now()
        WHERE id={case_id} RETURNING id
      ), event AS (
        INSERT INTO research.research_case_events (research_case_id,event_type,event_status,event_summary,actor,event_payload)
        VALUES ({case_id},'model_run',
          CASE WHEN {str(retrying).lower()} THEN 'retry_scheduled' ELSE 'blocked' END,
          CASE WHEN {str(retrying).lower()}
            THEN {sql_literal('A bounded retry was scheduled for '+role+'.')}
            ELSE {sql_literal('The '+role.replace('_',' ')+' role is genuinely blocked after two failed attempts.')} END,
          {sql_literal(str(run['agent_name']))},{sql_jsonb({'role_key': role, 'attempt': attempt, 'errors': errors, 'retry_scheduled': retrying})})
        RETURNING id
      ) SELECT coalesce(json_agg(row_to_json(event)),'[]'::json)::text FROM event
    """)
    return "retry_scheduled" if retrying else "blocked"


def run_next_research_case_model(
    *,
    run_rows: Callable[[str], list[dict[str, Any]]],
    run_statement: Callable[[str], list[dict[str, Any]]],
    sql_literal: Callable[[Any], str],
    sql_jsonb: Callable[[Any], str],
    openrouter_chat: Callable[[str, str, str | None], tuple[str | None, str, dict[str, Any]]],
) -> dict[str, Any]:
    candidates = run_rows("""
      SELECT model_run.*,packet.packet_key,packet.packet_hash,packet.public_context,packet.source_ids,
             packet.contains_private_data,packet.contains_client_data,packet.approved_for_cloud_at,
             case_row.case_key,case_row.status case_status,preflight.status preflight_status,
             preflight.hard_max_cost_usd,preflight.approval_id,approval.status approval_status
      FROM research.research_case_model_runs model_run
      JOIN research.research_case_public_packets packet ON packet.id=model_run.public_packet_id
      JOIN research.research_cases case_row ON case_row.id=model_run.research_case_id
      JOIN research.model_run_preflights preflight ON preflight.id=model_run.preflight_id
      JOIN agent.approvals approval ON approval.id=preflight.approval_id
      WHERE model_run.status='queued' AND case_row.status IN ('active','review')
        AND model_run.iteration=case_row.iteration_count
      ORDER BY model_run.created_at,model_run.id LIMIT 1
    """)
    if not candidates:
        return {"status": "idle", "count": 0}
    run = candidates[0]
    run_id = int(run["id"])
    if run.get("preflight_status") != "approved" or run.get("approval_status") != "approved" or bool(run.get("contains_private_data")) or bool(run.get("contains_client_data")):
        raise RuntimeError("queued Research Case run fails explicit approval or public-only packet gate")
    spend_rows = run_rows(f"SELECT coalesce(sum(actual_cost_usd),0) spent FROM research.model_run_receipts WHERE preflight_id={int(run['preflight_id'])}")
    spent = _num((spend_rows or [{}])[0].get("spent"))
    if spent >= _num(run.get("hard_max_cost_usd")):
        run_statement(f"""
          WITH updated AS (UPDATE research.research_case_model_runs SET status='blocked',exception_detail='approved hard cost ceiling reached',updated_at=now() WHERE id={run_id} RETURNING id)
          SELECT coalesce(json_agg(row_to_json(updated)),'[]'::json)::text FROM updated
        """)
        return {"status": "blocked", "reason": "hard_cost_ceiling_reached", "model_run_id": run_id}
    claimed = run_statement(f"""
      WITH updated AS (
        UPDATE research.research_case_model_runs SET status='running',started_at=now(),updated_at=now()
        WHERE id={run_id} AND status='queued' RETURNING *
      ) SELECT coalesce(json_agg(row_to_json(updated)),'[]'::json)::text FROM updated
    """)
    if not claimed:
        return {"status": "lost_claim", "count": 0}
    role = str(run["role_key"])
    packet = run.get("public_context") or {}
    completed = run_rows(f"""
      SELECT DISTINCT ON (role_key) role_key,output_summary,artifact_path,validation_result
      FROM research.research_case_model_runs
      WHERE research_case_id={int(run['research_case_id'])} AND iteration={int(run.get('iteration') or 1)}
        AND role_key<>{sql_literal(role)}
        AND status IN ('completed','needs_revision')
      ORDER BY role_key,attempt DESC,finished_at DESC,id DESC LIMIT 20
    """)
    context = _role_context(role, packet, completed)
    system_prompt, prompt = _prompt(role, context)
    prompt_hash = _sha(prompt)
    rate_rows = run_rows(f"""
      SELECT input_usd_per_1m_tokens,output_usd_per_1m_tokens FROM agent.model_cost_rates
      WHERE provider='openrouter' AND model_name={sql_literal(run['model_name'])} AND status='active'
      ORDER BY effective_at DESC LIMIT 1
    """)
    rates = rate_rows[0] if rate_rows else {}
    projected_prompt_tokens = max(1, len(prompt) / 4)
    projected_cost = (Decimal(projected_prompt_tokens) * _num(rates.get("input_usd_per_1m_tokens")) + Decimal(RESEARCH_MAX_COMPLETION_TOKENS) * _num(rates.get("output_usd_per_1m_tokens"))) / Decimal(1_000_000)
    if spent + projected_cost > _num(run.get("hard_max_cost_usd")):
        run_statement(f"""
          WITH model_updated AS (UPDATE research.research_case_model_runs SET status='blocked',
            exception_detail='Projected call cost would exceed the approved hard ceiling.',finished_at=now(),updated_at=now()
            WHERE id={run_id} RETURNING id),
          case_updated AS (UPDATE research.research_cases SET status='blocked',lead_status='cost_ceiling_blocked',
            current_goal='Review a new cost preflight before additional model work',updated_at=now()
            WHERE id={int(run['research_case_id'])} RETURNING id),
          event AS (INSERT INTO research.research_case_events
            (research_case_id,event_type,event_status,event_summary,actor,event_payload)
            VALUES ({int(run['research_case_id'])},'cost_ceiling','blocked',
              'The next model call was blocked before dispatch because its maximum projected cost could exceed the approved ceiling.',
              'Model Cost Guard',{sql_jsonb({'spent_usd': float(spent), 'projected_call_usd': float(projected_cost), 'hard_max_usd': float(_num(run.get('hard_max_cost_usd')))})}) RETURNING id)
          SELECT coalesce(json_agg(row_to_json(event)),'[]'::json)::text FROM event
        """)
        return {"status": "blocked", "reason": "projected_hard_cost_ceiling", "model_run_id": run_id}
    started = datetime.now(timezone.utc)
    response, call_status, usage = openrouter_chat(str(run["model_name"]), prompt, system_prompt)
    latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    prompt_tokens = _int((usage or {}).get("prompt_tokens"), max(1, len(prompt) // 4))
    completion_tokens = _int((usage or {}).get("completion_tokens"))
    rate_rows = run_rows(f"""
      SELECT input_usd_per_1m_tokens,output_usd_per_1m_tokens FROM agent.model_cost_rates
      WHERE provider='openrouter' AND model_name={sql_literal(run['model_name'])} AND status='active'
      ORDER BY effective_at DESC LIMIT 1
    """)
    rates = rate_rows[0] if rate_rows else {}
    cost = (Decimal(prompt_tokens) * _num(rates.get("input_usd_per_1m_tokens")) + Decimal(completion_tokens) * _num(rates.get("output_usd_per_1m_tokens"))) / Decimal(1_000_000)
    if call_status != "called":
        cost = Decimal(0)
    if call_status != "called" or not response:
        error = f"model_call_failed:{call_status}"
        run_statement(f"""
          WITH receipt AS (
            INSERT INTO research.model_run_receipts (receipt_key,preflight_id,agent_name,route_name,provider,model_name,data_boundary,prompt_hash,prompt_tokens,completion_tokens,actual_cost_usd,latency_ms,outcome_status,source_refs,metadata)
            VALUES ({sql_literal('case-receipt-'+str(run_id)+'-'+_sha(str(started))[:12])},{int(run['preflight_id'])},{sql_literal(run['agent_name'])},{sql_literal(run['route_name'])},'openrouter',{sql_literal(run['model_name'])},'public_only',{sql_literal(prompt_hash)},{prompt_tokens},{completion_tokens},{sql_literal(str(cost))},{latency_ms},'failed','[]'::jsonb,{sql_jsonb({'zdr_required': True, 'data_collection': 'deny', 'raw_prompt_stored': False, 'call_status': call_status})}) RETURNING id
          ), updated AS (
            UPDATE research.research_case_model_runs SET status='failed',prompt_hash={sql_literal(prompt_hash)},actual_cost_usd={sql_literal(str(cost))},latency_ms={latency_ms},exception_detail={sql_literal(error)},finished_at=now(),updated_at=now() WHERE id={run_id} RETURNING id
          ) SELECT coalesce(json_agg(json_build_object('receipt_id',receipt.id,'model_run_id',updated.id)),'[]'::json)::text FROM receipt CROSS JOIN updated
        """)
        retry_status = _retry_or_block(run, [error], run_statement, sql_literal, sql_jsonb)
        return {"status": retry_status, "model_run_id": run_id, "role_key": role, "error": error}
    try:
        output = _parse_structured_output(response)
    except Exception as exc:
        output = {}
        parse_error = f"invalid_json:{type(exc).__name__}"
    else:
        parse_error = ""
    allowed_source_ids = set(str(item) for item in (run.get("source_ids") or []))
    output = _sanitize_output_citations(output, allowed_source_ids)
    valid, errors, cited = _validate_output(role, output, allowed_source_ids)
    if parse_error:
        errors.insert(0, parse_error)
        valid = False
    artifact_payload = {
        "research_case_id": int(run["research_case_id"]), "model_run_id": run_id,
        "role_key": role, "agent_name": run["agent_name"], "model_name": run["model_name"],
        "packet_key": run["packet_key"], "packet_hash": run["packet_hash"],
        "generated_at": datetime.now(timezone.utc).isoformat(), "output": output,
        "validation": {"valid": valid, "errors": errors, "cited_source_ids": cited},
        "receipt": {"prompt_hash": prompt_hash, "response_hash": _sha(response), "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "actual_cost_usd": float(cost), "latency_ms": latency_ms},
    }
    artifact_path, artifact_hash = _write_artifact(str(run["case_key"]), str(run["run_key"]), artifact_payload)
    final_status = "completed" if valid else "failed"
    summary = output if valid else {"role_key": role, "summary": "Output failed the citation/structure contract.", "missing": errors}
    receipt_key = f"case-receipt-{run_id}-{_sha(str(started))[:12]}"
    persisted = run_statement(f"""
      WITH receipt AS (
        INSERT INTO research.model_run_receipts (receipt_key,preflight_id,agent_name,route_name,provider,model_name,data_boundary,prompt_hash,prompt_tokens,completion_tokens,actual_cost_usd,latency_ms,outcome_status,source_refs,metadata)
        VALUES ({sql_literal(receipt_key)},{int(run['preflight_id'])},{sql_literal(run['agent_name'])},{sql_literal(run['route_name'])},'openrouter',{sql_literal(run['model_name'])},'public_only',{sql_literal(prompt_hash)},{prompt_tokens},{completion_tokens},{sql_literal(str(cost))},{latency_ms},{sql_literal('completed' if valid else 'failed')},{sql_jsonb(cited)},{sql_jsonb({'zdr_required': True, 'data_collection': 'deny', 'raw_prompt_stored': False, 'raw_response_stored_in_db': False, 'response_hash': _sha(response), 'artifact_hash': artifact_hash})}) RETURNING id
      ), model_updated AS (
        UPDATE research.research_case_model_runs SET status={sql_literal(final_status)},prompt_hash={sql_literal(prompt_hash)},response_hash={sql_literal(_sha(response))},artifact_path={sql_literal(artifact_path)},artifact_hash={sql_literal(artifact_hash)},output_summary={sql_jsonb(summary)},validation_result={sql_jsonb({'valid': valid, 'errors': errors})},cited_source_ids={sql_jsonb(cited)},actual_cost_usd={sql_literal(str(cost))},latency_ms={latency_ms},exception_detail={sql_literal('; '.join(errors)) if errors else 'NULL'},finished_at=now(),updated_at=now() WHERE id={run_id} RETURNING id
      ), agent_updated AS (
        UPDATE research.research_case_agent_runs SET status={sql_literal('completed' if valid else 'needs_validation')},evidence={sql_jsonb([{'citation_id': item} for item in cited])},artifacts={sql_jsonb([{'path': artifact_path, 'sha256': artifact_hash, 'model_run_id': run_id}])},exceptions={sql_jsonb(errors)},updated_at=now() WHERE research_case_id={int(run['research_case_id'])} AND role_key={sql_literal(role)} RETURNING graph_node_run_id,task_id
      ), node_updated AS (
        UPDATE agent.graph_node_runs SET status={sql_literal('completed' if valid else 'failed')},output_payload={sql_jsonb({'model_run_id': run_id, 'summary': str(output.get('summary') or '')[:1000]})},evidence={sql_jsonb([{'citation_id': item} for item in cited])},error={sql_jsonb({'errors': errors})},finished_at=now(),updated_at=now() WHERE id=(SELECT graph_node_run_id FROM agent_updated LIMIT 1) RETURNING task_id
      ), task_updated AS (
        UPDATE agent.tasks SET status={sql_literal('completed' if valid else 'blocked')},output_note_path={sql_literal(artifact_path)},evidence={sql_jsonb([{'citation_id': item} for item in cited])},updated_at=now() WHERE id=(SELECT task_id FROM node_updated LIMIT 1) RETURNING id
      ) SELECT coalesce(json_agg(json_build_object('receipt_id',receipt.id,'model_run_id',model_updated.id)),'[]'::json)::text FROM receipt CROSS JOIN model_updated
    """)
    if not persisted:
        raise RuntimeError("Research Case model receipt was not persisted")
    if valid:
        section_keys = {
            "company_business": ["business_segments"],
            "financials": ["financial_history"],
            "management": ["management_governance"],
            "industry_moat": ["industry_structure", "tam_value_chain", "moat_quality"],
            "valuation": ["forecasts_valuation"],
            "bear_risk": ["catalysts_risks"],
            "lead_synthesis": ["investment_conclusion"],
            "committee_review": ["committee_decision"],
        }.get(role, [])
        if section_keys:
            run_statement(f"""
              WITH updated AS (
                UPDATE research.research_pack_sections SET
                  status={sql_literal('reviewed' if role in {'independent_review','committee_review'} else 'draft')},
                  summary={sql_literal(str(output.get('summary') or '')[:4000])},content={sql_jsonb(output)},
                  citation_ids={sql_jsonb(cited)},coverage_gaps={sql_jsonb(output.get('missing') or [])},
                  artifact_path={sql_literal(artifact_path)},artifact_hash={sql_literal(artifact_hash)},updated_at=now()
                WHERE research_case_id={int(run['research_case_id'])}
                  AND section_key IN ({','.join(sql_literal(key) for key in section_keys)})
                  AND version=1 RETURNING id
              ) SELECT coalesce(json_agg(row_to_json(updated)),'[]'::json)::text FROM updated
            """)
        _unlock_next(int(run["research_case_id"]), int(run.get("iteration") or 1), role, output, run_statement, sql_literal, sql_jsonb)
        if role == "committee_review":
            try:
                from research_case_report import generate_research_case_report
                report = generate_research_case_report(int(run["research_case_id"]), "Research Report Builder")
                run_statement(f"""
                  WITH resolved AS (
                    UPDATE research.research_case_blockers SET
                      status='resolved',resolution='A cited HTML and PDF report was generated on the external SSD.',resolved_at=now(),updated_at=now()
                    WHERE research_case_id={int(run['research_case_id'])}
                      AND blocker_key='research_pack_generation' AND status IN ('open','retrying') RETURNING id
                  ), event AS (INSERT INTO research.research_case_events
                    (research_case_id,event_type,event_status,event_summary,actor,event_payload)
                    VALUES ({int(run['research_case_id'])},'research_pack','generated',
                      {sql_literal('The cited HTML and PDF company research pack was generated on Devarsh SSD.' if report.get('pdf_path') else 'The cited HTML research pack was published on Devarsh SSD; PDF rendering remains a bounded local retry.')},
                      'Research Report Builder',{sql_jsonb(report)}) RETURNING id)
                  SELECT coalesce(json_agg(row_to_json(event)),'[]'::json)::text FROM event
                """)
            except Exception as exc:
                run_statement(f"""
                  WITH blocker AS (INSERT INTO research.research_case_blockers
                    (research_case_id,blocker_key,stage_key,title,detail,system_action,user_action,status,severity,metadata)
                    VALUES ({int(run['research_case_id'])},'research_pack_generation','report','Research pack generation failed',
                      {sql_literal(type(exc).__name__+': '+str(exc))},'The stack will preserve completed analysis and retry report rendering.',NULL,'open','high','{{}}'::jsonb)
                    ON CONFLICT (research_case_id,blocker_key) DO UPDATE SET detail=EXCLUDED.detail,status='open',updated_at=now() RETURNING id)
                  SELECT coalesce(json_agg(row_to_json(blocker)),'[]'::json)::text FROM blocker
                """)
    else:
        final_status = _retry_or_block(run, errors, run_statement, sql_literal, sql_jsonb)
    return {
        "status": final_status, "count": 1, "model_run_id": run_id,
        "research_case_id": int(run["research_case_id"]), "role_key": role,
        "agent_name": run["agent_name"], "model_name": run["model_name"],
        "artifact_path": artifact_path, "artifact_hash": artifact_hash,
        "actual_cost_usd": float(cost), "latency_ms": latency_ms,
        "citation_count": len(cited), "validation_errors": errors,
        "capital_action_allowed": False, "external_write_allowed": False,
    }
