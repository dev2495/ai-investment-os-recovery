"""Durable propose/confirm/start flow for source-governed Research Cases."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone


ROLE_PLAN = [
    ("company_business", "Company Analyst", "long_term_business_model_review", "Company, business model and unit economics"),
    ("filings", "Filings and Transcript Analyst", "analyze_corporate_filing", "Official filings, annual reports and first-party evidence"),
    ("financials", "Financial Statement Analyst", "long_term_financial_quality_review", "Normalized financials and quality"),
    ("management", "Management Analyst", "long_term_management_governance_review", "Management, governance and capital allocation"),
    ("industry_moat", "Industry Analyst", "long_term_industry_review", "Industry structure, competition and moat"),
    ("valuation", "Valuation Agent", "long_term_valuation_review", "Valuation assumptions, scenarios and sensitivity"),
    ("bear_risk", "Bear Case Agent", "long_term_bear_case_review", "Bear case, red flags and permanent-loss risks"),
    ("lead_synthesis", "Long-Term Portfolio Manager", "company_research_lead_synthesis", "Integrate specialist work into a cited complete company pack"),
    ("executive_summary", "Research Analyst", "company_research_executive_summary", "Create the concise investor-facing conclusion and key changes"),
    ("independent_review", "Model Validation Agent", "company_research_independent_review", "Challenge citations, calculations, assumptions and disconfirming evidence"),
    ("committee_review", "CIO Agent", "company_research_committee_brief", "Prepare the final advisory brief and explicit human decision ask"),
]

SOURCE_PLAN = [
    {"rank": 1, "kind": "exchange_or_regulator_filing", "authorization": "official public source", "collection": "bounded cached HTTPS or existing governed registry", "requires_parse_validation": True},
    {"rank": 2, "kind": "company_annual_report_or_ir", "authorization": "official company or investor-relations source", "collection": "bounded cached HTTPS or user-approved download", "requires_parse_validation": True},
    {"rank": 3, "kind": "company_presentation_or_transcript", "authorization": "lawfully accessed official material", "collection": "bounded cached HTTPS", "requires_parse_validation": True},
    {"rank": 4, "kind": "user_supplied_first_party", "authorization": "explicit user upload", "collection": "local external-SSD intake", "requires_parse_validation": True},
    {"rank": 5, "kind": "authorized_public_news_or_research", "authorization": "approved public feed or user-provided URL", "collection": "terms and robots compliant with rate limits", "requires_parse_validation": False},
]


_RESEARCH_LAUNCH_RE = re.compile(
    r"""
    ^\s*
    (?:please\s+)?
    (?:(?:can|could|would|will)\s+you\s+)?
    (?:start|begin|launch|initiate|open|create|do)\s+
    (?:(?:a\s+new|a|new)\s+)?
    (?:(?:long[-\s]?term|fundamental|equity|investment|company|public[-\s]?company)\s+)*
    (?:research(?:\s+case)?|analysis|dossier|report)\s+
    (?:on|for|about|into)\s+
    (?P<entity>.+?)
    \s*$
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)


_RESEARCH_ENTITY_FIRST_RE = re.compile(
    r"""
    ^\s*
    (?P<entity>[A-Za-z0-9&().,'/:+\-\s]{2,120}?)
    \s+(?:too|also|with|for|covering|including)\s+
    (?P<scope>.+?)
    \s*$
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)
_RESEARCH_SCOPE_RE = re.compile(
    r"\b(?:latest|filings?|annual\s+reports?|news|results?|earnings|financials?|"
    r"moat|valuation|reverse\s+dcf|dcf|peers?|risk|catalysts?|research)\b",
    flags=re.IGNORECASE,
)


def _clean_entity_candidate(value):
    candidate = re.sub(r"\s+", " ", str(value or "")).strip()
    candidate = candidate.strip(" \t\r\n.,:;-–—!?")
    if len(candidate) >= 2 and candidate[0] == candidate[-1] and candidate[0] in {"'", '\"'}:
        candidate = candidate[1:-1].strip()
    return candidate


def extract_research_entity(command):
    """Return the entity only for an explicit research-launch command.

    The bounded grammar requires an action verb, a research noun and a
    preposition. Repeated unwrapping also handles a full command accidentally
    nested inside a client's ``entity`` field.
    """
    candidate = _clean_entity_candidate(command)
    matched = False
    for _ in range(3):
        match = _RESEARCH_LAUNCH_RE.match(candidate)
        if not match:
            break
        matched = True
        nested = _clean_entity_candidate(match.group("entity"))
        if not nested or nested == candidate:
            break
        candidate = nested
    if matched and candidate:
        return candidate
    entity_first = _RESEARCH_ENTITY_FIRST_RE.match(candidate)
    if entity_first and _RESEARCH_SCOPE_RE.search(entity_first.group("scope")):
        entity = _clean_entity_candidate(entity_first.group("entity"))
        # A URL-led article command can otherwise resemble entity-first intake.
        # URLs are governed evidence inputs, never company identities.
        if re.search(r"https?://", entity, flags=re.IGNORECASE):
            return None
        return entity or None
    return None


def _slug(value):
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")[:80] or "research"


def _entity_matches(query, run_rows, sql_literal):
    needle = str(query or "").strip()
    if not needle:
        return []
    normalized = re.sub(r"\s+", " ", needle).strip()
    exchange_hint = ""
    symbol_hint = normalized
    exchange_match = re.match(r"^(NSE|BSE)\s*:\s*([A-Za-z0-9&._-]+)$", normalized, re.IGNORECASE)
    if exchange_match:
        exchange_hint = exchange_match.group(1).upper()
        symbol_hint = exchange_match.group(2).upper()
    rows = run_rows(f"""
      SELECT company.id company_id,company.company_key,company.legal_name,
             company.display_name,company.primary_symbol ticker,company.primary_exchange exchange,
             thesis.id holding_thesis_id,thesis.thesis_title,thesis.thesis_status,
             (company.real_company_verified_at IS NOT NULL) identity_verified,
             CASE WHEN company.real_company_verified_at IS NOT NULL THEN 'verified_company_registry'
                  WHEN symbol.active IS true THEN 'authorized_market_symbol_registry'
                  ELSE 'unverified_company_registry' END identity_source
      FROM research.companies company
      LEFT JOIN trading.symbols symbol
        ON upper(symbol.symbol)=upper(company.primary_symbol)
       AND upper(symbol.exchange)=upper(company.primary_exchange)
       AND symbol.active IS true AND symbol.instrument_type='equity'
      LEFT JOIN LATERAL (
        SELECT id,thesis_title,thesis_status FROM portfolio.holding_theses
        WHERE upper(symbol)=upper(company.primary_symbol)
          AND upper(exchange)=upper(company.primary_exchange)
        ORDER BY updated_at DESC,id DESC LIMIT 1
      ) thesis ON true
      WHERE (company.real_company_verified_at IS NOT NULL OR symbol.active IS true)
        AND ({sql_literal(exchange_hint)}='' OR upper(company.primary_exchange)={sql_literal(exchange_hint)})
        AND (
          upper(company.primary_symbol)=upper({sql_literal(symbol_hint)})
          OR lower(company.legal_name)=lower({sql_literal(normalized)})
          OR lower(coalesce(company.display_name,''))=lower({sql_literal(normalized)})
          OR lower(company.legal_name) LIKE '%'||lower({sql_literal(normalized)})||'%'
          OR lower({sql_literal(normalized)}) LIKE '%'||lower(company.legal_name)||'%'
          OR lower({sql_literal(normalized)}) LIKE '%'||lower(coalesce(company.display_name,''))||'%'
        )
      ORDER BY CASE WHEN upper(company.primary_symbol)=upper({sql_literal(symbol_hint)}) THEN 0
                    WHEN lower(company.legal_name)=lower({sql_literal(normalized)}) THEN 1 ELSE 2 END,
               company.id LIMIT 8
    """)
    return rows


def _resolve_entity_prefix(query, run_rows, sql_literal):
    """Resolve a verified company at the start of a natural-language scope.

    The launch grammar captures everything after ``on`` so legitimate company
    names containing connector words remain possible.  When the complete text
    is not a registry match, trim only from the right and select the longest
    prefix which maps to one verified listing.  No company is guessed or
    created by this fallback.
    """
    normalized = _clean_entity_candidate(query)
    matches = _entity_matches(normalized, run_rows, sql_literal)
    if matches:
        return normalized, matches
    tokens = normalized.split()
    for end in range(len(tokens) - 1, 0, -1):
        candidate = _clean_entity_candidate(" ".join(tokens[:end]))
        if not candidate:
            continue
        candidate_matches = _entity_matches(candidate, run_rows, sql_literal)
        if candidate_matches:
            return candidate, candidate_matches
    return normalized, []


def _confirm_market_reference_company(company_id, actor, *, run_statement, sql_literal):
    """Confirm listing identity from an active local symbol reference plus operator choice.

    This never validates financial claims. Official filings remain a separate
    collection, extraction and validation gate after Start.
    """
    run_statement(f"""
      WITH candidate AS (
        SELECT company.id,company.primary_exchange,company.primary_symbol,symbol.name symbol_name
        FROM research.companies company
        JOIN trading.symbols symbol
          ON upper(symbol.symbol)=upper(company.primary_symbol)
         AND upper(symbol.exchange)=upper(company.primary_exchange)
         AND symbol.active IS true AND symbol.instrument_type='equity'
        WHERE company.id={int(company_id)}
      ), evidence AS (
        INSERT INTO research.fundamental_evidence (
          company_id,source_type,source_name,source_url,source_title,retrieved_at,
          extraction_method,verification_status,verified_by,verified_at,source_locator,metadata
        ) SELECT id,'authorized_market_reference','Local authorized market symbol registry',
          CASE WHEN primary_exchange='NSE' THEN 'https://www.nseindia.com/get-quotes/equity?symbol='||primary_symbol
               WHEN primary_exchange='BSE' THEN 'https://www.bseindia.com/stock-share-price/'||lower(primary_symbol) ELSE NULL END,
          primary_exchange||':'||primary_symbol||' identity reference',now(),
          'active_symbol_registry_plus_operator_confirmation','human_verified',
          {sql_literal(actor)},now(),jsonb_build_object('exchange',primary_exchange,'symbol',primary_symbol),
          jsonb_build_object('identity_only',true,'financial_facts_validated',false,
            'operator_confirmed',true,'reference_name',symbol_name)
        FROM candidate
        WHERE NOT EXISTS (
          SELECT 1 FROM research.fundamental_evidence existing
          WHERE existing.company_id=candidate.id
            AND existing.source_type='authorized_market_reference'
            AND existing.source_locator->>'symbol'=candidate.primary_symbol
        ) RETURNING id,company_id
      ), evidence_id AS (
        SELECT id,company_id FROM evidence UNION ALL
        SELECT existing.id,existing.company_id FROM research.fundamental_evidence existing
        JOIN candidate ON candidate.id=existing.company_id
        WHERE existing.source_type='authorized_market_reference'
          AND existing.source_locator->>'symbol'=candidate.primary_symbol
        ORDER BY id DESC LIMIT 1
      ) UPDATE research.companies company SET
          real_company_verified_at=coalesce(company.real_company_verified_at,now()),
          real_company_verification_evidence_id=coalesce(company.real_company_verification_evidence_id,evidence_id.id),
          metadata=coalesce(company.metadata,'{{}}'::jsonb)||jsonb_build_object(
            'identity_verified',true,'identity_verification_scope','listing_identity_only',
            'identity_verified_by',{sql_literal(actor)},'financial_coverage_inferred',false),
          updated_at=now()
        FROM evidence_id WHERE company.id=evidence_id.company_id
    """)


def propose_research_case(payload, *, run_rows, run_statement, sql_literal, sql_jsonb):
    request_text = str(payload.get("request_text") or payload.get("requestText") or payload.get("entity") or "").strip()
    supplied_entity = str(payload.get("entity") or payload.get("ticker") or payload.get("idea") or "").strip()
    entity_query = (
        extract_research_entity(request_text)
        or extract_research_entity(supplied_entity)
        or _clean_entity_candidate(supplied_entity)
        or _clean_entity_candidate(request_text)
    )
    owner = str(payload.get("owner_agent") or "Long-Term Portfolio Manager").strip()
    priority = str(payload.get("priority") or "medium").lower()
    if priority not in {"low", "normal", "medium", "high", "critical"}:
        raise ValueError("priority must be low, normal, medium, high, or critical")
    horizon = str(payload.get("horizon") or "3-5 years").strip()
    requested_entity_scope = entity_query
    entity_query, matches = _resolve_entity_prefix(entity_query, run_rows, sql_literal)
    scope_suffix = requested_entity_scope[len(entity_query):].strip(" ,.:;-–—")
    if scope_suffix.lower().startswith("for "):
        scope_suffix = scope_suffix[4:].strip()
    default_mandate = f"Build a source-backed long-term investment decision brief for {entity_query}."
    if scope_suffix:
        default_mandate += f" Focus on {scope_suffix.rstrip('.')}."
    mandate = str(payload.get("mandate") or default_mandate).strip()
    explicit_company_id = payload.get("company_id") or payload.get("companyId")
    if explicit_company_id:
        scoped_matches = [row for row in matches if int(row.get("company_id") or 0) == int(explicit_company_id)]
        if scoped_matches:
            matches = scoped_matches
    if len(matches) == 1 and matches[0].get("identity_source") == "authorized_market_symbol_registry" and not bool(matches[0].get("identity_verified")):
        if explicit_company_id and int(matches[0].get("company_id") or 0) == int(explicit_company_id):
            _confirm_market_reference_company(
                int(explicit_company_id), str(payload.get("actor") or "Devarsh"),
                run_statement=run_statement, sql_literal=sql_literal,
            )
            matches = _entity_matches(entity_query, run_rows, sql_literal)
        else:
            return {
                "status": "needs_confirmation", "resolution_status": "needs_confirmation",
                "query": entity_query, "matches": matches,
                "detail": "One active listed-company reference matched. Confirm the exact exchange and company below. This confirms identity only; filings and financial facts still require official-source collection and validation.",
            }
    if len(matches) != 1:
        if not matches:
            detail = (
                f'No verified listed company matched "{entity_query}". Try its exact exchange ticker, '
                "or add and verify the company in the Research registry. No case or agent work was created."
            )
        else:
            detail = (
                f'More than one verified company matched "{entity_query}". Choose the exact exchange listing below. '
                "No case or agent work was created."
            )
        return {"status": "needs_input", "resolution_status": "needs_input", "query": entity_query, "matches": matches, "detail": detail}
    match = matches[0]
    company_id = int(match["company_id"])
    thesis_id = int(match.get("holding_thesis_id") or 0)
    entity_key = str(match.get("company_key") or f"{match.get('exchange')}:{match.get('ticker')}")
    identity = hashlib.sha256(f"{entity_key}|{horizon}|{mandate.lower()}".encode("utf-8")).hexdigest()
    case_key = f"research-{_slug(match.get('ticker'))}-{identity[:12]}"
    create_distinct = payload.get("create_distinct_confirmed") is True or payload.get("createDistinctConfirmed") is True
    exact = run_rows(f"""
      SELECT * FROM research.research_cases
      WHERE company_id={company_id} AND idempotency_key={sql_literal(identity)}
        AND status IN ('proposed','active','collecting','review','blocked')
      ORDER BY updated_at DESC,id DESC LIMIT 1
    """)
    if exact:
        current = exact[0]
        if str(current.get("status")) == "blocked":
            return {
                "status": "blocked_conflict", "research_case": current, "matches": matches,
                "requires_action": True, "idempotent_reuse": True,
                "action_choices": ["view_or_repair_existing", "create_distinct_mandate"],
                "detail": "This exact mandate already exists but its research lanes are waiting for qualified sources. Open it to repair the cited inputs, or change the mandate and confirm a distinct case.",
            }
        return {
            "status": str(current.get("status") or "proposed"), "research_case": current,
            "matches": matches, "requires_explicit_start": str(current.get("status")) == "proposed",
            "idempotent_reuse": True,
            "detail": "This exact mandate already exists; it was reused without creating duplicate work.",
        }
    existing = run_rows(f"""
      SELECT * FROM research.research_cases
      WHERE company_id={company_id}
        AND status IN ('proposed','active','collecting','review','blocked')
      ORDER BY updated_at DESC,id DESC LIMIT 1
    """)
    if existing and not create_distinct:
        current = existing[0]
        return {
            "status": "blocked_conflict" if str(current.get("status")) == "blocked" else "open_case_conflict",
            "research_case": current, "matches": matches, "requires_action": True,
            "action_choices": ["view_or_repair_existing", "create_distinct_mandate"],
            "detail": "A different open mandate exists for this company. Review it, or confirm creation of this distinct mandate; the existing case does not prevent new research.",
        }
    work_plan = [
        {"role_key": role, "agent_name": agent, "skill_key": skill, "objective": objective, "status": "proposed"}
        for role, agent, skill, objective in ROLE_PLAN
    ]
    data_boundary = {
        "privacy_scope": "local_private",
        "private_data_egress_allowed": False,
        "external_write_allowed": False,
        "broker_write_allowed": False,
        "client_write_allowed": False,
        "authorized_sources_only": True,
        "user_uploads_allowed": True,
        "storage_root": "/Volumes/Devarsh SSD",
    }
    budget = {
        "max_roles": len(ROLE_PLAN), "max_source_urls_per_role": 12,
        "max_retries_per_role": 2, "cooldown_minutes": 30,
        "paid_calls_allowed": True, "paid_calls_require_explicit_preflight_approval": True,
        "public_cloud_only": True, "private_data_egress_allowed": False,
    }
    result = run_statement(f"""
      WITH upserted AS (
        INSERT INTO research.research_cases (
          case_key,request_text,entity_type,entity_key,resolution_status,company_id,
          holding_thesis_id,ticker,exchange,company_name,owner_agent,priority,horizon,
          mandate,status,work_plan,source_plan,budget,data_boundary,coverage_snapshot,
          idempotency_key,proposed_by,cooldown_until
        ) VALUES (
          {sql_literal(case_key)},{sql_literal(request_text or f'Start research on {entity_query}')},
          'company',{sql_literal(entity_key)},'confirmed',{company_id},{thesis_id or 'NULL'},
          {sql_literal(match.get('ticker'))},{sql_literal(match.get('exchange'))},
          {sql_literal(match.get('legal_name') or match.get('display_name'))},{sql_literal(owner)},
          {sql_literal(priority)},{sql_literal(horizon)},{sql_literal(mandate)},'proposed',
          {sql_jsonb(work_plan)},{sql_jsonb(SOURCE_PLAN)},{sql_jsonb(budget)},
          {sql_jsonb(data_boundary)},'{{}}'::jsonb,{sql_literal(identity)},
          {sql_literal(str(payload.get('actor') or 'Devarsh'))},now()+interval '30 minutes'
        ) ON CONFLICT (case_key) DO UPDATE SET
          request_text=EXCLUDED.request_text,priority=EXCLUDED.priority,horizon=EXCLUDED.horizon,
          mandate=EXCLUDED.mandate,work_plan=EXCLUDED.work_plan,source_plan=EXCLUDED.source_plan,
          budget=EXCLUDED.budget,data_boundary=EXCLUDED.data_boundary,updated_at=now()
        RETURNING *
      ), event AS (
        INSERT INTO research.research_case_events (
          research_case_id,event_type,event_status,event_summary,actor,event_payload
        ) SELECT id,'proposed','recorded','Entity resolved; work and source plan await explicit Start.',
          {sql_literal(str(payload.get('actor') or 'Devarsh'))},
          jsonb_build_object('company_id',company_id,'ticker',ticker,'source_plan',source_plan)
        FROM upserted
        WHERE NOT EXISTS (
          SELECT 1 FROM research.research_case_events existing
          WHERE existing.research_case_id=upserted.id AND existing.event_type='proposed'
        ) RETURNING id
      ) SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
    """)
    return {"status": "proposed", "research_case": result[0], "matches": matches, "requires_explicit_start": True} if result else {"status": "failed"}


def start_research_case(payload, *, run_rows, run_statement, sql_literal, sql_jsonb, start_graph):
    if payload.get("operator_confirmed") is not True and payload.get("operatorConfirmed") is not True:
        raise ValueError("operator_confirmed must be true before dispatching research agents")
    case_id = int(payload.get("research_case_id") or payload.get("researchCaseId") or payload.get("id") or 0)
    if not case_id:
        raise ValueError("research_case_id is required")
    preflight_id = int(payload.get("model_preflight_id") or payload.get("modelPreflightId") or 0)
    if not preflight_id:
        raise ValueError("model_preflight_id is required; review and approve the bounded public-research cost estimate before Start")
    preflight_rows = run_rows(f"""
      SELECT preflight.id,preflight.status,preflight.public_only,
             preflight.private_data_egress_allowed,preflight.external_write_allowed,
             preflight.broker_write_allowed,preflight.source_count,preflight.document_count,approval.status approval_status
      FROM research.model_run_preflights preflight
      JOIN agent.approvals approval ON approval.id=preflight.approval_id
      WHERE preflight.id={preflight_id} AND preflight.research_case_id={case_id}
        AND preflight.request_kind='research_case' LIMIT 1
    """)
    if not preflight_rows:
        raise ValueError("model preflight does not belong to this Research Case")
    preflight = preflight_rows[0]
    if preflight.get("status") != "approved" or preflight.get("approval_status") != "approved":
        raise ValueError("Research Case model preflight must be explicitly approved before Start")
    if not bool(preflight.get("public_only")) or bool(preflight.get("private_data_egress_allowed")) or bool(preflight.get("external_write_allowed")) or bool(preflight.get("broker_write_allowed")):
        raise ValueError("Research Case preflight violates the public-only, no-write safety boundary")
    qualified_source_count = int(preflight.get("source_count") or 0)
    model_dispatch_allowed = qualified_source_count > 0
    case_rows = run_rows(f"SELECT * FROM research.research_cases WHERE id={case_id} LIMIT 1")
    if not case_rows:
        raise ValueError("research case was not found")
    case = case_rows[0]
    if case.get("resolution_status") != "confirmed":
        raise ValueError("research case entity must be confirmed before start")
    existing_run_id = int(case.get("graph_run_id") or 0)
    if existing_run_id and case.get("status") in {"active", "collecting", "review", "blocked"}:
        lane_rows = run_rows(f"SELECT count(*)::integer lane_count FROM research.research_case_agent_runs WHERE research_case_id={case_id}")
        lane_count = int((lane_rows or [{}])[0].get("lane_count") or 0)
        if lane_count == len(ROLE_PLAN):
            return {
                "status": str(case.get("status")),
                "research_case": case,
                "graph": {"graph_run_id": existing_run_id, "created": False, "idempotent_reuse": True},
                "agent_count": lane_count,
                "idempotent_reuse": True,
                "capital_action_allowed": False,
                "external_write_allowed": False,
            }
    actor = str(payload.get("actor") or "Devarsh").strip()
    graph_input = {
        "research_case_id": case_id,
        "entity_key": case.get("entity_key"),
        "ticker": case.get("ticker"),
        "exchange": case.get("exchange"),
        "company_name": case.get("company_name"),
        "holding_thesis_id": case.get("holding_thesis_id"),
        "company_id": case.get("company_id"),
        "mandate": case.get("mandate"),
        "horizon": case.get("horizon"),
        "source_plan": case.get("source_plan") or [],
        "budget": case.get("budget") or {},
        "data_boundary": case.get("data_boundary") or {},
        "model_preflight_id": preflight_id,
    }
    graph_result = start_graph({
        "graph_key": "company_research_case",
        "actor": actor,
        "trigger_type": "user_command",
        "subject_type": "research_case",
        "subject_ref": str(case_id),
        "correlation_key": str(case.get("case_key")),
        "idempotency_key": f"research-case:{case_id}:v3",
        "input_payload": graph_input,
        "max_steps": 20,
    })
    graph_run_id = int(graph_result.get("graph_run_id") or 0)
    if not graph_run_id:
        raise RuntimeError("research case graph did not return a run id")
    rows = run_statement(f"""
      WITH updated_case AS (
        UPDATE research.research_cases SET status={sql_literal('active' if model_dispatch_allowed else 'collecting')},graph_run_id={graph_run_id},
          confirmed_by={sql_literal(actor)},started_at=coalesce(started_at,now()),updated_at=now()
        WHERE id={case_id} RETURNING *
      ), agent_rows AS (
        INSERT INTO research.research_case_agent_runs (
          research_case_id,role_key,agent_name,skill_key,status,graph_node_run_id,task_id,inbox_id
        ) SELECT {case_id},node.node_key,node.owner_agent,node.skill_key,
          CASE WHEN {sql_literal('ready' if model_dispatch_allowed else 'awaiting_sources')}='awaiting_sources' THEN 'awaiting_sources' WHEN node.configuration->>'source_qualified_worker_required'='true' THEN 'awaiting_source_worker' ELSE node_run.status END,
          node_run.id,node_run.task_id,inbox.id
        FROM agent.graph_node_runs node_run
        JOIN agent.graph_nodes node ON node.id=node_run.graph_node_id
        LEFT JOIN agent.inbox_items inbox ON inbox.task_id=node_run.task_id
        WHERE node_run.graph_run_id={graph_run_id}
          AND node.node_key IN ('company_business','filings','financials','management','industry_moat','valuation','bear_risk','lead_synthesis','executive_summary','independent_review','committee_review')
        ON CONFLICT (research_case_id,role_key) DO UPDATE SET
          status=EXCLUDED.status,graph_node_run_id=EXCLUDED.graph_node_run_id,
          task_id=EXCLUDED.task_id,inbox_id=EXCLUDED.inbox_id,updated_at=now()
        RETURNING id
      ), official_evidence AS (
        INSERT INTO research.research_case_evidence (
          research_case_id,evidence_id,source_item_id,source_kind,source_identifier,
          source_url,local_artifact_path,publication_date,effective_date,captured_at,
          parser_status,validation_status,citation_locator,dedupe_key,created_by
        ) SELECT {case_id},item.fundamental_evidence_id,item.id,item.source_kind,
          item.source_identifier,item.source_url,item.local_artifact_path,
          item.publication_date,item.effective_date,item.captured_at,item.parser_status,
          item.validation_status,item.citation_locator,
          coalesce(item.content_hash,item.source_key),{sql_literal(actor)}
        FROM research.thesis_source_items item
        WHERE item.company_id={int(case.get('company_id') or -1)}
          AND item.source_kind IN ('annual_report','exchange_filing','company_announcement','investor_presentation','company_ir','user_supplied_research')
        ON CONFLICT (research_case_id,dedupe_key) DO UPDATE SET
          parser_status=EXCLUDED.parser_status,validation_status=EXCLUDED.validation_status,
          citation_locator=EXCLUDED.citation_locator,updated_at=now()
        RETURNING id
      ), monitor_list AS (
        INSERT INTO research.watchlists (watchlist_key,watchlist_name,purpose,status,owner_agent,created_by,metadata)
        VALUES ('company_research_following','Followed company research',
          'Official filings, authorized news, catalysts, thesis changes and review dates for approved Research Cases',
          'active','Research Director',{sql_literal(actor)},
          jsonb_build_object('automatic_collection',true,'broker_write_allowed',false,'private_data_egress_allowed',false))
        ON CONFLICT (watchlist_key) DO UPDATE SET status='active',updated_at=now()
        RETURNING id
      ), monitored_company AS (
        INSERT INTO research.watchlist_items (
          watchlist_id,symbol,exchange,company_name,item_type,status,priority,thesis,
          review_on,owner_agent,source_kind,source_ref,created_by,evidence,metadata
        ) SELECT id,{sql_literal(case.get('ticker'))},{sql_literal(case.get('exchange'))},
          {sql_literal(case.get('company_name'))},'research_case','active',{sql_literal(str(case.get('priority') or 'medium'))},
          {sql_literal(case.get('mandate'))},current_date+7,'Company Analyst','research_case',
          {sql_literal('research_case:'+str(case_id))},{sql_literal(actor)},'[]'::jsonb,
          jsonb_build_object('research_case_id',{case_id},'automatic_collection',true,
            'filings_cadence_hours',24,'news_cadence_hours',6,'decision_change_requires_human_review',true,
            'broker_write_allowed',false,'external_write_allowed',false)
        FROM monitor_list
        ON CONFLICT (watchlist_id,exchange,symbol,item_type) DO UPDATE SET
          company_name=EXCLUDED.company_name,status='active',priority=EXCLUDED.priority,
          thesis=EXCLUDED.thesis,review_on=EXCLUDED.review_on,source_ref=EXCLUDED.source_ref,
          metadata=EXCLUDED.metadata,updated_at=now()
        RETURNING id
      ), event AS (
        INSERT INTO research.research_case_events (
          research_case_id,event_type,event_status,event_summary,actor,event_payload
        ) SELECT {case_id},'started','recorded',{sql_literal('Explicit Start dispatched bounded public-research specialists, lead synthesis, independent review and committee brief.' if model_dispatch_allowed else 'Explicit Start created the durable source-collection workstream; paid model roles are waiting for qualified public evidence.')},
          {sql_literal(actor)},jsonb_build_object('graph_run_id',{graph_run_id},'model_preflight_id',{preflight_id},'company_monitoring_active',true,'capital_action_allowed',false,'external_write_allowed',false)
        WHERE NOT EXISTS (
          SELECT 1 FROM research.research_case_events existing
          WHERE existing.research_case_id={case_id} AND existing.event_type='started'
        ) RETURNING id
      )
      SELECT coalesce(json_agg(row_to_json(result_rows)), '[]'::json)::text
      FROM (
        SELECT updated_case.*, (SELECT count(*) FROM agent_rows)::integer agent_count,
          (SELECT count(*) FROM official_evidence)::integer linked_evidence_count
        FROM updated_case
      ) result_rows
    """)
    return {"status": "active" if model_dispatch_allowed else "collecting", "research_case": rows[0] if rows else case, "graph": graph_result, "source_count": qualified_source_count, "model_dispatch_allowed": model_dispatch_allowed, "model_gate": None if model_dispatch_allowed else "waiting_for_qualified_public_sources", "capital_action_allowed": False, "external_write_allowed": False}
