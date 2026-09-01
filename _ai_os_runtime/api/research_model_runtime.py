"""Public-only model-run preflight and bounded canary controls.

This module intentionally cannot collect sources, access private case content, or
perform broker/client/external mutations. It only estimates, approves, records,
and runs a tiny fixed public validation packet after explicit approval.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

PUBLIC_CANARY_ROUTES = {
    "openrouter_public_lead_glm53_flash_canary",
    "openrouter_public_lead_glm52_canary",
    "openrouter_public_lead_deepseek_v4_pro_canary",
}
CANARY_RUBRIC = {
    "numeric_locator_accuracy_weight": 30,
    "unsupported_claim_rate_weight": 20,
    "structured_output_weight": 15,
    "investment_reasoning_weight": 15,
    "tool_reliability_weight": 10,
    "latency_weight": 5,
    "cost_weight": 5,
    "pass_rule": "Human selection only after cited-output review; no score auto-promotes a lead model.",
}


def _num(value, fallback=0):
    try:
        return Decimal(str(value if value not in (None, "") else fallback))
    except Exception:
        return Decimal(str(fallback))


def _int(value, fallback=0):
    try:
        return max(0, int(value))
    except Exception:
        return fallback


def _sha(value):
    return hashlib.sha256(str(value).encode("utf-8", errors="replace")).hexdigest()


def _case_scope(payload, run_rows, sql_literal):
    case_id = _int(payload.get("research_case_id") or payload.get("researchCaseId"))
    thesis_id = _int(payload.get("holding_thesis_id") or payload.get("holdingThesisId") or payload.get("thesis_id"))
    result = {"research_case_id": case_id or None, "holding_thesis_id": thesis_id or None, "source_count": 0, "document_count": 0, "cached_document_count": 0}
    if case_id:
        rows = run_rows(f"""
            SELECT count(*)::integer source_count,
                   count(*) FILTER (WHERE local_artifact_path IS NOT NULL)::integer document_count,
                   count(*) FILTER (WHERE local_artifact_path IS NOT NULL AND parser_status IN ('parsed','validated','human_reviewed'))::integer cached_document_count
            FROM research.research_case_evidence WHERE research_case_id={case_id}
        """)
        if rows:
            result.update(rows[0])
    elif thesis_id:
        rows = run_rows(f"""
            SELECT count(*)::integer source_count,
                   count(*) FILTER (WHERE local_artifact_path IS NOT NULL)::integer document_count,
                   count(*) FILTER (WHERE local_artifact_path IS NOT NULL AND parser_status IN ('parsed','validated','human_reviewed'))::integer cached_document_count
            FROM research.thesis_source_items WHERE holding_thesis_id={thesis_id}
        """)
        if rows:
            result.update(rows[0])
    return result


def _route_plan(payload, run_rows, sql_literal):
    requested = payload.get("runs") or []
    if not isinstance(requested, list) or not requested:
        raise ValueError("runs must contain at least one public model role with agent_name, route_name, prompt_tokens_est, completion_tokens_max and max_calls")
    plan, reasons = [], []
    for item in requested[:20]:
        if not isinstance(item, dict):
            reasons.append("run_plan_item_invalid")
            continue
        agent_name = str(item.get("agent_name") or item.get("agentName") or "").strip()
        route_name = str(item.get("route_name") or item.get("routeName") or "").strip()
        prompt_tokens = _int(item.get("prompt_tokens_est") or item.get("promptTokensEst"))
        completion_tokens = _int(item.get("completion_tokens_max") or item.get("completionTokensMax"))
        max_calls = _int(item.get("max_calls") or item.get("maxCalls") or 1, 1)
        if not agent_name or not route_name or prompt_tokens < 1 or completion_tokens < 1 or max_calls < 1:
            reasons.append(f"invalid_run:{agent_name or route_name or 'unknown'}")
            continue
        rows = run_rows(f"""
            SELECT route.route_name,route.default_provider,route.default_model,route.max_cost_tier,route.enabled,
                   cap.daily_cap_usd,cap.monthly_cap_usd,cap.max_cost_tier cap_max_cost_tier,
                   cap.cloud_requires_approval,cap.autonomous_cloud_allowed,profile.status agent_status,
                   rate.id rate_id,rate.input_usd_per_1m_tokens,rate.output_usd_per_1m_tokens,rate.rate_source,rate.effective_at
            FROM agent.model_routes route
            JOIN agent.profiles profile ON profile.agent_name={sql_literal(agent_name)}
            JOIN agent.model_cost_caps cap ON cap.agent_name=profile.agent_name
            LEFT JOIN LATERAL (
              SELECT * FROM agent.model_cost_rates
              WHERE lower(provider)='openrouter' AND model_name=route.default_model AND status='active' AND effective_at<=now()
              ORDER BY effective_at DESC LIMIT 1
            ) rate ON true
            WHERE route.route_name={sql_literal(route_name)} AND profile.status='active'
            LIMIT 1
        """)
        if not rows:
            reasons.append(f"route_or_agent_unavailable:{route_name}")
            continue
        row = rows[0]
        canary_route_override = (
            str(payload.get("request_kind") or payload.get("requestKind") or "").strip() == "canary"
            and route_name in PUBLIC_CANARY_ROUTES
        )
        if not bool(row.get("enabled")) and not canary_route_override:
            reasons.append(f"route_disabled:{route_name}")
        if row.get("default_provider") != "openrouter":
            reasons.append(f"non_openrouter_route:{route_name}")
        if row.get("rate_id") is None:
            reasons.append(f"cost_rate_missing:{route_name}")
        if bool(row.get("autonomous_cloud_allowed")) or not bool(row.get("cloud_requires_approval")):
            reasons.append(f"approval_policy_invalid:{agent_name}")
        input_rate = _num(row.get("input_usd_per_1m_tokens"))
        output_rate = _num(row.get("output_usd_per_1m_tokens"))
        estimate = (Decimal(prompt_tokens) * input_rate + Decimal(completion_tokens) * output_rate) / Decimal(1_000_000) * Decimal(max_calls)
        if estimate > _num(row.get("daily_cap_usd")):
            reasons.append(f"agent_daily_cap_would_breach:{agent_name}")
        plan.append({
            "agent_name": agent_name, "route_name": route_name, "provider": row.get("default_provider"),
            "model_name": row.get("default_model"), "cost_tier": row.get("max_cost_tier"),
            "route_enabled": bool(row.get("enabled")), "canary_route_override": canary_route_override, "prompt_tokens_est": prompt_tokens,
            "completion_tokens_max": completion_tokens, "max_calls": max_calls,
            "estimated_cost_usd": float(estimate), "hard_max_cost_usd": float(estimate * Decimal("1.20")),
            "rate_id": row.get("rate_id"), "input_usd_per_1m_tokens": float(input_rate),
            "output_usd_per_1m_tokens": float(output_rate), "rate_source": row.get("rate_source"),
            "rate_effective_at": row.get("effective_at"), "agent_daily_cap_usd": float(_num(row.get("daily_cap_usd"))),
            "agent_monthly_cap_usd": float(_num(row.get("monthly_cap_usd"))),
        })
    if len(requested) > 20:
        reasons.append("run_plan_exceeds_20_rows")
    return plan, reasons


def create_model_run_preflight(payload, *, run_rows, run_statement, sql_literal, sql_jsonb):
    actor = str(payload.get("actor") or "Devarsh").strip() or "Devarsh"
    request_kind = str(payload.get("request_kind") or payload.get("requestKind") or "research_case").strip()
    if request_kind not in {"research_case", "report", "canary"}:
        raise ValueError("request_kind must be research_case, report or canary")
    if payload.get("public_only") is not True and payload.get("publicOnly") is not True:
        raise ValueError("public_only must be true; private context is never eligible for cloud preflight")
    if bool(payload.get("contains_private_data") or payload.get("containsPrivateData")):
        raise ValueError("contains_private_data must be false for cloud preflight")
    scope = _case_scope(payload, run_rows, sql_literal)
    plan, reasons = _route_plan(payload, run_rows, sql_literal)
    exchange_rate = _num(payload.get("exchange_rate_inr_per_usd") or payload.get("exchangeRateInrPerUsd") or 87)
    estimated = sum((_num(row["estimated_cost_usd"]) for row in plan), Decimal(0))
    hard_max = sum((_num(row["hard_max_cost_usd"]) for row in plan), Decimal(0))
    storage = _int(payload.get("estimated_storage_bytes") or payload.get("estimatedStorageBytes") or 0)
    duration = _int(payload.get("estimated_duration_seconds") or payload.get("estimatedDurationSeconds") or max(30, len(plan) * 90))
    status = "blocked" if reasons else "awaiting_approval"
    preflight_key = f"preflight-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{_sha(json.dumps(plan,sort_keys=True))[:10]}"
    boundary = {"public_only": True, "private_data_egress_allowed": False, "external_write_allowed": False, "broker_write_allowed": False, "raw_prompt_stored": False, "zdr_required": True, "data_collection": "deny", "storage_root": "/Volumes/Devarsh SSD"}
    rate_snapshot = [{k: row[k] for k in ("route_name","model_name","rate_id","input_usd_per_1m_tokens","output_usd_per_1m_tokens","rate_source","rate_effective_at")} for row in plan]
    approval_payload = {"preflight_key": preflight_key, "request_kind": request_kind, "estimated_cost_usd": float(estimated), "hard_max_cost_usd": float(hard_max), "estimated_cost_inr": float(estimated * exchange_rate), "hard_max_cost_inr": float(hard_max * exchange_rate), "source_count": _int(scope.get("source_count")), "document_count": _int(scope.get("document_count")), "cached_document_count": _int(scope.get("cached_document_count")), "run_plan": plan, "data_boundary": boundary, "broker_write_allowed": False, "external_write_allowed": False}
    rows = run_statement(f"""
      WITH approval AS (
        INSERT INTO agent.approvals (approval_type,title,owner_agent,risk_level,status,requested_action,rationale)
        VALUES ('research_model_run', {sql_literal('Approve public-only model preflight: '+request_kind)}, 'AI Runtime Engineer', 'medium', {sql_literal('pending' if not reasons else 'rejected')}, {sql_jsonb(approval_payload)}, {sql_literal('Public-only, bounded model run. Approval authorizes no broker, client or external write action.')})
        RETURNING id,status
      ), inserted AS (
        INSERT INTO research.model_run_preflights (preflight_key,research_case_id,holding_thesis_id,request_kind,requested_by,status,public_only,private_data_egress_allowed,external_write_allowed,broker_write_allowed,source_count,document_count,cached_document_count,estimated_storage_bytes,estimated_duration_seconds,estimated_cost_usd,hard_max_cost_usd,exchange_rate_inr_per_usd,rate_snapshot,run_plan,data_boundary,block_reasons,approval_id,approval_expires_at)
        SELECT {sql_literal(preflight_key)}, {scope.get('research_case_id') or 'NULL'}, {scope.get('holding_thesis_id') or 'NULL'}, {sql_literal(request_kind)}, {sql_literal(actor)}, {sql_literal(status)}, true,false,false,false,{_int(scope.get('source_count'))},{_int(scope.get('document_count'))},{_int(scope.get('cached_document_count'))},{storage},{duration},{sql_literal(str(estimated))},{sql_literal(str(hard_max))},{sql_literal(str(exchange_rate))},{sql_jsonb(rate_snapshot)},{sql_jsonb(plan)},{sql_jsonb(boundary)},{sql_jsonb(reasons)},approval.id,now()+interval '24 hours'
        FROM approval RETURNING *
      ) SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text FROM inserted
    """)
    if not rows:
        raise RuntimeError("model preflight was not persisted")
    result = rows[0]
    result["estimated_cost_inr"] = float(estimated * exchange_rate)
    result["hard_max_cost_inr"] = float(hard_max * exchange_rate)
    result["no_model_invocation"] = True
    return result


def approve_model_run_preflight(payload, *, run_rows, run_statement, sql_literal):
    if payload.get("operator_confirmed") is not True and payload.get("operatorConfirmed") is not True:
        raise ValueError("operator_confirmed must be true before approving a model preflight")
    preflight_id = _int(payload.get("preflight_id") or payload.get("preflightId") or payload.get("id"))
    if not preflight_id:
        raise ValueError("preflight_id is required")
    actor = str(payload.get("actor") or "Devarsh").strip() or "Devarsh"
    rows = run_statement(f"""
      WITH selected AS (
        SELECT id,approval_id FROM research.model_run_preflights
        WHERE id={preflight_id} AND status='awaiting_approval' AND approval_expires_at>now()
        FOR UPDATE
      ), approved AS (
        UPDATE agent.approvals SET status='approved',decided_by={sql_literal(actor)},decided_at=now()
        WHERE id=(SELECT approval_id FROM selected) AND status='pending' RETURNING id
      ), updated AS (
        UPDATE research.model_run_preflights SET status='approved',approved_by={sql_literal(actor)},approved_at=now(),updated_at=now()
        WHERE id=(SELECT id FROM selected) AND EXISTS (SELECT 1 FROM approved) RETURNING *
      ) SELECT coalesce(json_agg(row_to_json(updated)), '[]'::json)::text FROM updated
    """)
    if not rows:
        raise ValueError("preflight is not pending, has expired, is blocked, or was already decided")
    result = rows[0]
    result["execution_enabled"] = result.get("request_kind") == "research_case"
    result["detail"] = (
        "Preflight approved. Start may dispatch only the bounded public Research Case packet; final investment authority remains human."
        if result["execution_enabled"]
        else "Preflight approved. Execution remains limited to the separately confirmed bounded operation."
    )
    return result


def configure_public_model_canary(payload, *, run_rows, run_statement, sql_literal, sql_jsonb):
    preflight_id = _int(payload.get("preflight_id") or payload.get("preflightId"))
    route = str(payload.get("candidate_route") or payload.get("candidateRoute") or "").strip()
    if route not in PUBLIC_CANARY_ROUTES:
        raise ValueError("candidate_route must be a configured ZDR-eligible public lead-model canary route")
    if not preflight_id:
        raise ValueError("preflight_id is required")
    actor = str(payload.get("actor") or "Devarsh").strip() or "Devarsh"
    rows = run_statement(f"""
      WITH preflight AS (
        SELECT * FROM research.model_run_preflights
        WHERE id={preflight_id} AND request_kind='canary' AND status='approved' AND public_only=true
      ), route_row AS (
        SELECT route_name,default_model FROM agent.model_routes WHERE route_name={sql_literal(route)}
      ), inserted AS (
        INSERT INTO research.public_model_canary_runs (canary_key,preflight_id,candidate_route,candidate_model,packet_key,packet_source_summary,packet_public_only,status,scoring_rubric,created_by)
        SELECT {sql_literal('canary-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+route[-12:])},preflight.id,route_row.route_name,route_row.default_model,
               'ushamart_public_packet_v1',
               {sql_jsonb([{'source':'Usha Martin official annual report and investor-relations materials','classification':'public_primary','contains_private_data':False}])},
               true,'awaiting_approval',{sql_jsonb(CANARY_RUBRIC)},{sql_literal(actor)}
        FROM preflight CROSS JOIN route_row RETURNING *
      ) SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text FROM inserted
    """)
    if not rows:
        raise ValueError("approved public-only canary preflight or candidate route was not found")
    result = rows[0]
    result["execution_enabled"] = False
    result["detail"] = "Canary is configured with a bounded public USHAMART packet. It requires the separate run endpoint and records a receipt; no research case is dispatched."
    return result


def _public_ushamart_packet():
    return """You are evaluating public-company research quality. Use only this bounded public packet; do not browse or claim information outside it.\n\nUsha Martin Limited: official historical financial/operating disclosure reports total wire-rope capacity/volume (KMT) for FY21-FY26 of 174, 189, 192, 181, 198, 207, and operational EBITDA margin of 13.5%, 14.3%, 15.7%, 18.6%, 17.2%, 19.1%. Official FY25 investor materials state value-added products were 71% and international business 55%. Official management transcript indicates approximately 104K MT wire-rope volume versus 125K MT capacity and a proposed addition of 20-25K MT.\n\nRequired JSON only: {\"facts\":[{\"claim\":string,\"value\":string,\"source\":string}],\"inferences\":[string],\"missing\":[string],\"disconfirmers\":[string]}. Cite the packet labels, distinguish fact from inference, and do not give an investment recommendation."""


def run_public_model_canary(payload, *, run_rows, run_statement, sql_literal, sql_jsonb, openrouter_chat):
    if payload.get("operator_confirmed") is not True and payload.get("operatorConfirmed") is not True:
        raise ValueError("operator_confirmed must be true before running the public model canary")
    canary_id = _int(payload.get("canary_id") or payload.get("canaryId") or payload.get("id"))
    if not canary_id:
        raise ValueError("canary_id is required")
    selected = run_rows(f"""
      SELECT canary.*,preflight.status preflight_status,preflight.public_only,preflight.approval_id,
             approval.status approval_status,route.default_provider,route.default_model
      FROM research.public_model_canary_runs canary
      JOIN research.model_run_preflights preflight ON preflight.id=canary.preflight_id
      JOIN agent.approvals approval ON approval.id=preflight.approval_id
      JOIN agent.model_routes route ON route.route_name=canary.candidate_route
      WHERE canary.id={canary_id} AND canary.status='awaiting_approval'
      LIMIT 1
    """)
    if not selected:
        raise ValueError("configured canary was not found or is not runnable")
    canary = selected[0]
    if canary.get("preflight_status") != "approved" or canary.get("approval_status") != "approved" or not bool(canary.get("public_only")) or canary.get("candidate_route") not in PUBLIC_CANARY_ROUTES:
        raise ValueError("canary fails public-only or explicit-approval gate")
    # This controlled packet has no private evidence, no user note, no portfolio
    # state, no URL fetch, and no tool/external-write capability.
    packet = _public_ushamart_packet()
    started = datetime.now(timezone.utc)
    response, status, usage = openrouter_chat(str(canary["candidate_model"]), packet, "You are a cautious public-document research evaluator. Return strict JSON only.")
    elapsed = int((datetime.now(timezone.utc)-started).total_seconds()*1000)
    prompt_tokens = _int((usage or {}).get("prompt_tokens"), max(1, len(packet)//4))
    completion_tokens = _int((usage or {}).get("completion_tokens"))
    rate_rows = run_rows(f"""SELECT input_usd_per_1m_tokens,output_usd_per_1m_tokens FROM agent.model_cost_rates WHERE provider='openrouter' AND model_name={sql_literal(canary['candidate_model'])} AND status='active' ORDER BY effective_at DESC LIMIT 1""")
    rate = rate_rows[0] if rate_rows else {}
    cost = (Decimal(prompt_tokens)*_num(rate.get("input_usd_per_1m_tokens"))+Decimal(completion_tokens)*_num(rate.get("output_usd_per_1m_tokens")))/Decimal(1_000_000)
    valid_json = False
    if response:
        try:
            candidate = response.strip()
            if candidate.startswith("```"):
                candidate = candidate.split("\n", 1)[1] if "\n" in candidate else ""
                candidate = candidate.rsplit("```", 1)[0].strip()
            decoded = json.loads(candidate)
            valid_json = isinstance(decoded, dict) and all(key in decoded for key in ("facts","inferences","missing","disconfirmers"))
        except Exception:
            pass
    outcome = "completed" if status == "called" and response else "failed"
    receipt_key = f"canary-receipt-{canary_id}-{_sha(str(started))[:12]}"
    score = {"structured_output_valid": valid_json, "latency_ms": elapsed, "actual_cost_usd": float(cost), "response_hash": _sha(response or ''), "requires_human_citation_review": True, "auto_promotion": False}
    rows = run_statement(f"""
      WITH receipt AS (
        INSERT INTO research.model_run_receipts (receipt_key,preflight_id,agent_name,route_name,provider,model_name,data_boundary,prompt_hash,prompt_tokens,completion_tokens,actual_cost_usd,latency_ms,outcome_status,source_refs,metadata)
        VALUES ({sql_literal(receipt_key)},{int(canary['preflight_id'])},'Long-Term Portfolio Manager',{sql_literal(canary['candidate_route'])},'openrouter',{sql_literal(canary['candidate_model'])},'public_only',{sql_literal(_sha(packet))},{prompt_tokens},{completion_tokens},{sql_literal(str(cost))},{elapsed},{sql_literal(outcome)},'["ushamart_public_packet_v1"]'::jsonb,{sql_jsonb({'zdr_required':True,'data_collection':'deny','response_hash':_sha(response or ''),'raw_response_stored':False})})
        RETURNING id
      ), updated AS (
        UPDATE research.public_model_canary_runs SET status={sql_literal('completed' if outcome=='completed' else 'failed')},score={sql_jsonb(score)},updated_at=now() WHERE id={canary_id} RETURNING *
      ), preflight AS (
        UPDATE research.model_run_preflights SET status='completed',completed_at=now(),updated_at=now() WHERE id={int(canary['preflight_id'])} RETURNING id
      ) SELECT coalesce(json_agg(row_to_json(updated)), '[]'::json)::text FROM updated
    """)
    if not rows:
        raise RuntimeError("canary result was not recorded")
    result = rows[0]
    result["receipt"] = {"outcome": outcome, "latency_ms": elapsed, "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "actual_cost_usd": float(cost), "response_hash": _sha(response or '')}
    # Return the fixed public response only to this confirmed caller so the
    # operator can review every citation. The wrapper must remove this field
    # before audit persistence; the durable receipt stores only its hash.
    result["response_output"] = response or ""
    result["lead_model_selected"] = False
    return result


def review_and_promote_public_model_canary(
    payload, *, run_rows, run_statement, sql_literal, sql_jsonb
):
    """Record a named human review and promote one public daily-driver candidate.

    The review is bound to the exact response hash returned by the canary. No
    model call occurs here. Promotion changes only the public Research Case
    specialist route; private data, broker writes and external writes remain
    denied and every paid Research Case still requires its own preflight.
    """
    if payload.get("operator_confirmed") is not True and payload.get("operatorConfirmed") is not True:
        raise ValueError("operator_confirmed must be true before promoting a public research model")
    if payload.get("approve_for_daily_driver") is not True and payload.get("approveForDailyDriver") is not True:
        raise ValueError("approve_for_daily_driver must be true before changing the public research daily driver")
    canary_id = _int(payload.get("canary_id") or payload.get("canaryId") or payload.get("id"))
    if not canary_id:
        raise ValueError("canary_id is required")
    reviewer = str(payload.get("reviewer") or payload.get("actor") or "").strip()
    rationale = str(payload.get("rationale") or "").strip()
    reviewed_hash = str(payload.get("reviewed_response_hash") or payload.get("reviewedResponseHash") or "").strip().lower()
    citation_score = _int(payload.get("citation_accuracy_score") or payload.get("citationAccuracyScore"))
    numeric_score = _int(payload.get("numeric_accuracy_score") or payload.get("numericAccuracyScore"))
    unsupported_claims = _int(payload.get("unsupported_claim_count") or payload.get("unsupportedClaimCount"))
    citations_checked = payload.get("source_citations_checked") is True or payload.get("sourceCitationsChecked") is True
    if not reviewer or len(rationale) < 20:
        raise ValueError("reviewer and a rationale of at least 20 characters are required")
    if len(reviewed_hash) != 64:
        raise ValueError("reviewed_response_hash must be the exact 64-character canary response hash")
    if not citations_checked:
        raise ValueError("source_citations_checked must be true")
    if citation_score < 90 or numeric_score < 95 or unsupported_claims:
        raise ValueError("promotion requires citation score >= 90, numeric score >= 95, and zero unsupported claims")

    rows = run_rows(f"""
      SELECT canary.id,canary.candidate_route,canary.candidate_model,canary.packet_public_only,
             canary.status,canary.score,route.max_cost_tier
      FROM research.public_model_canary_runs canary
      JOIN agent.model_routes route ON route.route_name=canary.candidate_route
      WHERE canary.id={canary_id}
      LIMIT 1
    """)
    if not rows:
        raise ValueError("canary was not found")
    canary = rows[0]
    score = canary.get("score") if isinstance(canary.get("score"), dict) else {}
    if (
        canary.get("status") != "completed"
        or not bool(canary.get("packet_public_only"))
        or canary.get("candidate_route") not in PUBLIC_CANARY_ROUTES
        or not bool(score.get("structured_output_valid"))
    ):
        raise ValueError("only a completed, structured-output-valid public canary can be promoted")
    if str(score.get("response_hash") or "").lower() != reviewed_hash:
        raise ValueError("reviewed_response_hash does not match the completed canary")

    reviewed_at = datetime.now(timezone.utc).isoformat()
    review = {
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "citation_accuracy_score": citation_score,
        "numeric_accuracy_score": numeric_score,
        "unsupported_claim_count": unsupported_claims,
        "source_citations_checked": True,
        "rationale": rationale,
        "selection_role": "public_research_daily_driver",
        "response_hash": reviewed_hash,
    }
    promoted_score = {
        **score,
        "human_review": review,
        "human_review_passed": True,
        "requires_human_citation_review": False,
        "auto_promotion": False,
    }
    model_name = str(canary["candidate_model"])
    max_cost_tier = str(canary.get("max_cost_tier") or "cloud_low")
    notes = (
        "Public-only Research Case specialist daily driver selected after a completed "
        "structured-output canary and named human citation/numeric review. Every paid "
        "Research Case still requires preflight approval; private data, broker writes "
        "and external writes remain denied."
    )
    alias_config = {
        "zdr_required": True,
        "data_collection": "deny",
        "public_only": True,
        "broker_write_allowed": False,
        "external_write_allowed": False,
        "private_data_egress_allowed": False,
        "selected_canary_id": canary_id,
        "reviewed_response_hash": reviewed_hash,
        "reviewed_at": reviewed_at,
        "reviewer": reviewer,
    }
    promoted = run_statement(f"""
      WITH target AS (
        SELECT id,candidate_route,candidate_model
        FROM research.public_model_canary_runs
        WHERE id={canary_id} AND status='completed' AND packet_public_only=true
        FOR UPDATE
      ), older_daily_driver AS (
        UPDATE research.public_model_canary_runs
        SET selected_for_role=false,updated_at=now()
        WHERE id<>(SELECT id FROM target)
          AND selected_for_role=true
          AND score->'human_review'->>'selection_role'='public_research_daily_driver'
        RETURNING id
      ), selected_canary AS (
        UPDATE research.public_model_canary_runs
        SET selected_for_role=true,score={sql_jsonb(promoted_score)},updated_at=now()
        WHERE id=(SELECT id FROM target)
        RETURNING id,candidate_route,candidate_model,selected_for_role,score,updated_at
      ), route_update AS (
        UPDATE agent.model_routes
        SET task_class='public_research_specialist_daily_driver',
            default_provider='openrouter',
            default_model={sql_literal(model_name)},
            escalation_provider='openrouter',
            escalation_model='deepseek/deepseek-v4-pro-0813',
            max_cost_tier={sql_literal(max_cost_tier)},
            notes={sql_literal(notes)},
            enabled=true
        WHERE route_name='openrouter_research_fast'
        RETURNING route_name,default_provider,default_model,escalation_model,max_cost_tier,enabled
      ), daily_alias AS (
        INSERT INTO agent.model_alias_registry (
          alias_key,route_name,provider_binding,model_binding,secret_ref,
          data_boundary,approval_required,fallback_alias,escalation_alias,
          status,notes,config
        ) VALUES (
          'research.public.daily_driver','openrouter_research_fast','openrouter',
          {sql_literal(model_name)},'AI_OS_OPENROUTER_API_KEY','public_only',true,
          'local.private.default','research.public.lead.deepseek_v4_pro','active',
          {sql_literal(notes)},{sql_jsonb(alias_config)}
        )
        ON CONFLICT (alias_key) DO UPDATE SET
          route_name=EXCLUDED.route_name,
          provider_binding=EXCLUDED.provider_binding,
          model_binding=EXCLUDED.model_binding,
          secret_ref=EXCLUDED.secret_ref,
          data_boundary='public_only',
          approval_required=true,
          fallback_alias=EXCLUDED.fallback_alias,
          escalation_alias=EXCLUDED.escalation_alias,
          status='active',
          notes=EXCLUDED.notes,
          config=EXCLUDED.config,
          updated_at=now()
        RETURNING alias_key,route_name,model_binding,data_boundary,approval_required,status
      )
      SELECT coalesce(json_agg(json_build_object(
        'canary_id',selected_canary.id,
        'candidate_route',selected_canary.candidate_route,
        'daily_driver_route',route_update.route_name,
        'daily_driver_model',route_update.default_model,
        'escalation_model',route_update.escalation_model,
        'selected_for_role',selected_canary.selected_for_role,
        'human_review',selected_canary.score->'human_review',
        'alias_key',daily_alias.alias_key,
        'public_only',true,
        'private_data_egress_allowed',false,
        'external_write_allowed',false,
        'broker_write_allowed',false,
        'paid_runs_still_require_preflight',true
      )), '[]'::json)::text
      FROM selected_canary CROSS JOIN route_update CROSS JOIN daily_alias
    """)
    if not promoted:
        raise RuntimeError("daily-driver promotion was not persisted")
    result = promoted[0]
    result["model_invoked"] = False
    result["detail"] = (
        f"{model_name} is selected for public Research Case specialist work. "
        "DeepSeek V4 Pro remains the lead/review escalation; every paid run remains approval-gated."
    )
    return result
