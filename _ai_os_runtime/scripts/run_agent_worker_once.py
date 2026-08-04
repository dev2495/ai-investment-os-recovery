#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


RUNTIME_ROOT = Path(os.environ.get("AI_OS_RUNTIME_ROOT") or Path(__file__).resolve().parents[1])
VAULT_ROOT = Path(
    os.environ.get("AI_OS_VAULT_ROOT")
    or os.environ.get("AI_OS_VAULT_PATH")
    or RUNTIME_ROOT.parent
)
OUTPUT_DIR = VAULT_ROOT / "ai memory" / "00 AI OS" / "Agent Outputs" / "Worker Runs"
WORKER_SPOOL_ROOT = Path(
    os.environ.get("AI_OS_WORKER_SPOOL_ROOT")
    or (Path.home() / "AI_OS_NODE" / "spool" / "agent-worker")
)
WORKER_MIRROR_TIMEOUT_SECONDS = max(
    1, int(os.environ.get("AI_OS_WORKER_MIRROR_TIMEOUT_SECONDS") or 8)
)


def load_runtime_env() -> dict[str, str]:
    values: dict[str, str] = {}
    env_path = RUNTIME_ROOT / ".env"
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    values.update(os.environ)
    return values


RUNTIME_ENV = load_runtime_env()


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-").lower()
    return cleaned[:80] or "agent-run"


COMPANY_TOKEN_STOP_WORDS = {
    "AI", "ANALYST", "AND", "AVAILABLE", "CHARLIE", "COMPANY", "DECISION",
    "EVIDENCE", "FILING", "FACTS", "LATEST", "MEMO", "MISSING", "NO", "PREPARE",
    "RESEARCH", "REVIEW", "RISK", "SEPARATE", "THE", "TRADE",
}


def extract_company_query(job: dict[str, Any], message: dict[str, Any]) -> str:
    """Extract an explicit exchange-style symbol from a delegated research request."""
    text = " ".join(
        str(value or "")
        for value in (
            job.get("title"),
            job.get("objective"),
            message.get("subject"),
            message.get("body"),
        )
    )
    candidates = re.findall(r"(?<![A-Za-z0-9])[A-Z][A-Z0-9&.-]{1,19}(?![A-Za-z0-9])", text)
    return next((token for token in candidates if token not in COMPANY_TOKEN_STOP_WORDS), "")


def sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def sql_jsonb(value: Any) -> str:
    return sql_literal(json.dumps(value, default=str)) + "::jsonb"


def psql_text(sql: str) -> str:
    configured_psql = str(RUNTIME_ENV.get("AI_OS_PSQL_BIN") or "").strip()
    psql_candidates = [
        configured_psql,
        shutil.which("psql") or "",
        "/opt/homebrew/bin/psql",
        "/usr/local/bin/psql",
    ]
    psql_bin = next((candidate for candidate in psql_candidates if candidate and Path(candidate).exists()), "")
    db_host = RUNTIME_ENV.get("AI_OS_POSTGRES_HOST") or "127.0.0.1"
    db_port = RUNTIME_ENV.get("AI_OS_POSTGRES_PORT") or "54329"
    db_user = RUNTIME_ENV.get("AI_OS_POSTGRES_USER") or "ai_os"
    db_name = RUNTIME_ENV.get("AI_OS_POSTGRES_DB") or "ai_os"
    db_password = RUNTIME_ENV.get("AI_OS_POSTGRES_PASSWORD")

    if Path(psql_bin).exists() and db_password:
        command = [
            psql_bin,
            "-h",
            db_host,
            "-p",
            db_port,
            "-U",
            db_user,
            "-d",
            db_name,
            "-q",
            "-t",
            "-A",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            sql,
        ]
        env = os.environ.copy()
        env["PGPASSWORD"] = db_password
        completed = subprocess.run(command, text=True, capture_output=True, check=False, env=env, timeout=30)
    else:
        docker_bin = shutil.which("docker") or "/usr/local/bin/docker"
        if not Path(docker_bin).exists():
            raise RuntimeError("Neither psql nor docker is available for the agent worker")
        command = [
            docker_bin,
            "exec",
            "ai_os_postgres",
            "psql",
            "-U",
            "ai_os",
            "-d",
            "ai_os",
            "-q",
            "-t",
            "-A",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            sql,
        ]
        completed = subprocess.run(command, text=True, capture_output=True, check=False, timeout=30)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "psql command failed").strip()
        raise RuntimeError(detail)
    return completed.stdout.strip()


def psql_json(query: str) -> list[dict[str, Any]]:
    sql = f"SELECT coalesce(json_agg(row_to_json(result_rows)), '[]'::json)::text FROM ({query}) result_rows;"
    output = psql_text(sql)
    return json.loads(output or "[]")


def psql_one(query: str) -> dict[str, Any]:
    rows = psql_json(query)
    return rows[0] if rows else {}


def get_queue(limit: int, include_completed: bool, task_id: int | None = None) -> list[dict[str, Any]]:
    completed_filter = (
        ""
        if include_completed
        else "AND (source_kind='committee_packet_position' OR coalesce(latest_worker_status, '') <> 'completed')"
    )
    task_filter = f"AND queue.task_id = {int(task_id)}" if task_id is not None else ""
    return psql_json(
        f"""
        SELECT queue.*
        FROM agent.v_live_agent_worker_queue queue
        WHERE (
            queue.task_status IN ('queued','in_progress','needs_review')
            OR (queue.source_kind='committee_packet_position' AND queue.task_status='blocked')
        )
          {completed_filter}
          {task_filter}
        ORDER BY
            CASE WHEN EXISTS (
                SELECT 1
                FROM agent.agent_messages message
                WHERE message.generated_task_id=queue.task_id
                  AND (
                    message.metadata ? 'graph_run_id'
                    OR message.metadata ? 'graph_node_run_id'
                  )
            ) THEN 0 ELSE 1 END,
            CASE queue.task_status WHEN 'queued' THEN 1 WHEN 'in_progress' THEN 2 WHEN 'needs_review' THEN 3 ELSE 4 END,
            CASE queue.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
            queue.updated_at DESC
        LIMIT {int(limit)}
        """
    )


def profile_for(agent_name: str) -> dict[str, Any]:
    return psql_one(
        f"""
        SELECT active.agent_name, active.display_title, active.department,
               active.department_name, active.role_scope, active.persona,
               active.operating_style, active.mental_models, active.primary_skills,
               active.cost_policy, active.default_model_route, active.default_tools,
               active.permission_level, active.output_targets, active.guardrails,
               active.escalation_rules, active.daily_cadence, active.human_interface,
               assignment.primary_route, assignment.primary_model_key,
               assignment.fallback_route, assignment.escalation_route,
               assignment.context_policy, assignment.max_autonomous_cost_tier,
               assignment.escalation_triggers,
               primary_runtime.runtime_status AS primary_route_status,
               fallback_runtime.runtime_status AS fallback_route_status
        FROM agent.v_active_agents active
        LEFT JOIN agent.agent_model_assignments assignment USING(agent_name)
        LEFT JOIN agent.v_model_route_runtime_control primary_runtime
          ON primary_runtime.route_name=assignment.primary_route
        LEFT JOIN agent.v_model_route_runtime_control fallback_runtime
          ON fallback_runtime.route_name=assignment.fallback_route
        WHERE active.agent_name = {sql_literal(agent_name)}
        """
    )


def capability_for(agent_name: str) -> dict[str, Any]:
    return psql_one(
        f"""
        SELECT requested_tool_count,resolved_tool_count,ready_tool_count,
               missing_tool_count,missing_tools,tools_ready
        FROM agent.v_agent_capability_readiness
        WHERE agent_name={sql_literal(agent_name)}
        """
    )


def skill_for(skill_key: str) -> dict[str, Any]:
    return psql_one(
        f"""
        SELECT skill_key, skill_name, skill_family, execution_mode, input_sources,
               output_targets, required_tools, risk_notes, primary_agents,
               assigned_agents
        FROM agent.v_agent_skill_matrix
        WHERE skill_key = {sql_literal(skill_key)}
        """
    )


def routed_agent_for(job: dict[str, Any], skill: dict[str, Any]) -> str:
    owner = str(job.get("owner_agent") or "Jarvis")
    if job.get("source_kind") == "agent_message":
        return owner
    primary_agents = skill.get("primary_agents") or []
    assigned_agents = skill.get("assigned_agents") or []
    if owner == "Jarvis":
        for candidate in primary_agents:
            if candidate and candidate != "Jarvis":
                return str(candidate)
        if primary_agents:
            return str(primary_agents[0])
        for candidate in assigned_agents:
            if candidate and candidate != "Jarvis":
                return str(candidate)
    return owner


def evaluate_task_provider_gates(task_id: object, actor: str = "Jarvis", context: str = "agent_worker_preflight") -> dict[str, Any]:
    try:
        numeric_task_id = int(task_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("task_id is required for provider gate preflight") from exc
    return psql_one(
        f"""
        SELECT core.evaluate_task_provider_assignment_gates(
            {numeric_task_id},
            {sql_literal(actor)},
            {sql_literal(context)}
        ) AS result
        """
    ).get("result") or {}


def claim_task(task_id: object, actor: str = "Jarvis", allow_committee_reclaim: bool = False) -> dict[str, Any]:
    try:
        numeric_task_id = int(task_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("task_id is required for worker claim") from exc
    sql = f"""
    WITH claimed AS (
        UPDATE agent.tasks
        SET status = 'in_progress',
            evidence = coalesce(evidence, '[]'::jsonb) || jsonb_build_array(jsonb_build_object(
                'source', 'run_agent_worker_once.claim_task',
                'claimed_by', {sql_literal(actor)},
                'claimed_at', now()
            )),
            updated_at = now()
        WHERE id = {numeric_task_id}
          AND (
              status = 'queued'
              OR (
                  {str(bool(allow_committee_reclaim)).lower()}
                  AND source_kind='committee_packet_position'
                  AND status IN ('needs_review','blocked')
              )
          )
        RETURNING id, status, updated_at
    )
    SELECT coalesce((SELECT row_to_json(claimed) FROM claimed), '{{}}'::json)::text;
    """
    return json.loads(psql_text(sql) or "{}")


def context_for(skill_key: str, widget_key: str | None, job: dict[str, Any] | None = None) -> dict[str, Any]:
    base = {
        "clients": psql_one("SELECT count(*)::INT AS count FROM portfolio.clients WHERE active = true"),
        "inbox": psql_one("SELECT count(*)::INT AS open_items FROM agent.inbox_items WHERE status IN ('new','queued','open','needs_review')"),
        "widgets": psql_one("SELECT count(*)::INT AS active_widgets FROM ops.dashboard_widgets WHERE status = 'active'"),
    }
    if job and job.get("source_kind") == "agent_message":
        source_ref = str(job.get("source_ref") or "")
        base["agent_message"] = psql_one(
            f"""
            SELECT id, thread_key, from_agent, to_agent, subject, body,
                   priority, status, processing_status, related_skill_key,
                   metadata, created_at
            FROM agent.agent_messages
            WHERE generated_task_id = {int(job.get("task_id"))}
            ORDER BY created_at DESC,id DESC
            LIMIT 1
            """
        )
        if not base["agent_message"] and source_ref.isdigit():
            base["agent_message"] = psql_one(
                f"""
                SELECT id, thread_key, from_agent, to_agent, subject, body,
                       priority, status, processing_status, related_skill_key,
                       metadata, created_at
                FROM agent.agent_messages
                WHERE id = {int(source_ref)}
                LIMIT 1
                """
            )
        base["office"] = {
            "mailboxes": psql_one("SELECT count(*)::INT AS count FROM agent.mailboxes WHERE status = 'active'"),
            "unread_messages": psql_one("SELECT count(*)::INT AS count FROM agent.agent_messages WHERE status = 'unread'"),
            "pending_messages": psql_one("SELECT count(*)::INT AS count FROM agent.agent_messages WHERE processing_status IN ('pending','failed_retry')"),
        }
        message = base.get("agent_message") or {}
        message_metadata = message.get("metadata") or {}
        message_text = f"{message.get('subject') or ''} {message.get('body') or ''}".lower()
        paper_id = message_metadata.get("paper_id")
        if not str(paper_id or "").isdigit():
            source_aliases = (
                ("tradingagents", "tradingagents"),
                ("ai hedge fund", "ai hedge fund"),
                ("newsdesk", "newsdesk"),
                ("commodity landed", "commodity landed"),
                ("tradingview screener", "tradingview screener"),
                ("fii dii", "fii dii"),
                ("options hub", "options hub"),
                ("fundamental scanner", "fundamental scanner"),
            )
            source_term = next((query for alias, query in source_aliases if alias in message_text), None)
            if source_term:
                matched_source = psql_one(
                    "SELECT id FROM research.research_papers "
                    f"WHERE lower(title) LIKE {sql_literal('%' + source_term + '%')} "
                    "ORDER BY updated_at DESC,id DESC LIMIT 1"
                )
                paper_id = matched_source.get("id")
        if (
            skill_key == "research_evidence_curation"
            and any(
                term in message_text
                for term in ("coverage gap", "artifact gap", "knowledge gap", "missing note")
            )
        ):
            base["artifact_gaps"] = psql_json(
                """
                SELECT gap_type,source_view,source_id,title,owner_agent,status,
                       created_at,updated_at,gap_reason
                FROM agent.v_output_artifact_gaps
                ORDER BY updated_at DESC NULLS LAST,created_at DESC NULLS LAST
                LIMIT 20
                """
            )
            base["artifact_gap_summary"] = psql_json(
                """
                SELECT gap_type,count(*)::int AS gap_count,
                       max(updated_at) AS latest_updated_at
                FROM agent.v_output_artifact_gaps
                GROUP BY gap_type
                ORDER BY gap_count DESC,gap_type
                """
            )
        if skill_key in {
            "company_research_note",
            "research_evidence_curation",
            "generate_strategy_hypothesis",
            "head_quant_governance",
            "validate_strategy_model",
        } and str(paper_id or "").isdigit():
            numeric_paper_id = int(paper_id)
            base["research_source"] = psql_one(
                f"""
                SELECT id,paper_key,title,source_url,source_kind,research_objective,
                       target_universe,desired_outputs,extraction_word_count,
                       extraction_status,review_status,intake_status,content_hash,
                       metadata,evidence,left(extracted_text,12000) AS extracted_text
                FROM research.research_papers
                WHERE id={numeric_paper_id}
                """
            )
            base["research_hypotheses"] = psql_json(
                f"""
                SELECT id,title,edge_hypothesis,market_scope,asset_classes,timeframe,
                       signal_definition,data_requirements,invalidation_tests,
                       limitations,status,owner_agent
                FROM research.paper_strategy_hypotheses
                WHERE paper_id={numeric_paper_id}
                ORDER BY created_at,id
                """
            )
            base["research_cycle"] = psql_one(
                f"""
                SELECT id,cycle_key,objective,as_of,universe,strategy_spec,status,
                       owner_agent,evidence,broker_write_allowed,live_execution_allowed
                FROM strategy.research_cycles
                WHERE source_kind='research_source' AND source_ref={sql_literal(str(numeric_paper_id))}
                ORDER BY created_at DESC,id DESC
                LIMIT 1
                """
            )
        if skill_key == "company_research_note" and not base.get("research_source"):
            company_query = extract_company_query(job, message)
            base["company_research"] = {
                "query": company_query,
                "filing_inventory": psql_one(
                    """
                    SELECT count(*)::INT AS total_filings,
                           max(filed_at) AS latest_filed_at
                    FROM research.v_corporate_filing_inbox
                    """
                ),
                "filings": [],
                "holding_theses": [],
                "ideas": [],
                "notes": [],
            }
            if company_query:
                match = "%" + company_query.lower() + "%"
                base["company_research"]["filings"] = psql_json(
                    f"""
                    SELECT filing_id,source_name,exchange,symbol,company_name,title,
                           filing_type,event_type,filed_at,source_url,attachment_url,
                           extraction_status,opportunity_score,risk_score,event_status
                    FROM research.v_corporate_filing_inbox
                    WHERE upper(coalesce(symbol,''))={sql_literal(company_query.upper())}
                       OR lower(coalesce(company_name,'')) LIKE {sql_literal(match)}
                       OR lower(coalesce(title,'')) LIKE {sql_literal(match)}
                    ORDER BY filed_at DESC NULLS LAST,filing_id DESC
                    LIMIT 10
                    """
                )
                base["company_research"]["holding_theses"] = psql_json(
                    f"""
                    SELECT id,symbol,exchange,thesis_status,thesis_note_path,
                           valuation_note_path,risk_note_path,last_reviewed_at,
                           next_review_due_at,conviction_score,valuation_range,risks
                    FROM portfolio.holding_theses
                    WHERE upper(symbol)={sql_literal(company_query.upper())}
                    ORDER BY last_reviewed_at DESC NULLS LAST,id DESC
                    LIMIT 10
                    """
                )
                base["company_research"]["ideas"] = psql_json(
                    f"""
                    SELECT id,idea_type,title,symbols,thesis,catalyst,expected_timeframe,
                           opportunity_score,risk_score,status,owner_agent,evidence,
                           output_note_path,updated_at
                    FROM research.ideas
                    WHERE {sql_literal(company_query.upper())}=ANY(symbols)
                       OR lower(title) LIKE {sql_literal(match)}
                    ORDER BY updated_at DESC,id DESC
                    LIMIT 10
                    """
                )
                base["company_research"]["notes"] = psql_json(
                    f"""
                    SELECT id,note_path,title,note_type,tags,body_summary,last_modified_at,indexed_at
                    FROM knowledge.obsidian_notes
                    WHERE lower(title) LIKE {sql_literal(match)}
                       OR lower(coalesce(body_summary,'')) LIKE {sql_literal(match)}
                       OR {sql_literal(company_query.lower())}=ANY(
                           SELECT lower(tag) FROM unnest(tags) AS tag
                       )
                    ORDER BY coalesce(last_modified_at,indexed_at) DESC,id DESC
                    LIMIT 10
                    """
                )
                base["selected_filing_evidence"] = base["company_research"]["filings"]
        if skill_key in {"head_quant_governance", "validate_strategy_model", "generate_strategy_hypothesis"}:
            base["workflow_contracts"] = psql_json(
                """
                SELECT workflow_key,workflow_name,workflow_type,owner_agent,status,
                       permission_level,approval_required,notes,metadata
                FROM agent.workflow_registry
                WHERE workflow_key IN (
                    'checkpointed_research_committee',
                    'outcome_grounded_decision_review',
                    'mrchartist_multi_source_intelligence'
                )
                ORDER BY workflow_key
                """
            )
    if job and job.get("source_kind") == "committee_packet_position":
        source_ref = str(job.get("source_ref") or "")
        packet_id = source_ref.split(":", 1)[0]
        if packet_id.isdigit():
            base["committee_packet"] = psql_one(
                f"""
                SELECT id,packet_key,committee_key,committee_name,chair_agent,mandate,
                       quorum,decision_options,human_final_required,committee_item_key,
                       source_view,source_id,title,decision_question,packet_status,
                       evidence,metadata,due_at,opened_by,opened_at,counted_positions
                FROM agent.v_committee_packet_control
                WHERE id={int(packet_id)}
                """
            )
            base["committee_mandate"] = psql_one(
                f"""
                SELECT membership.committee_role,membership.vote_type,
                       membership.challenge_mandate,membership.required
                FROM agent.committee_memberships membership
                JOIN agent.committee_packets packet USING(committee_key)
                WHERE packet.id={int(packet_id)}
                  AND membership.agent_name={sql_literal(str(job.get('owner_agent') or ''))}
                """
            )
    if skill_key.startswith("sector_"):
        base["sector_intelligence"] = {
            "freshness": psql_json(
                """
                SELECT taxonomy_node_id,taxonomy_key,node_name,latest_metric_at,
                       latest_market_monitor_at,latest_flow_at,
                       latest_ownership_period_end,latest_research_review_at
                FROM sector_intelligence.v_sector_data_freshness
                ORDER BY node_name
                LIMIT 40
                """
            ),
            "custom_indices": psql_json(
                """
                SELECT index_id,index_key,index_name,status,weighting_method,
                       rebalance_frequency,latest_rebalance_date,
                       current_constituent_count,latest_calculated_at,latest_index_value
                FROM sector_intelligence.v_custom_index_control
                ORDER BY status,index_name
                LIMIT 30
                """
            ),
            "rankings": psql_json(
                """
                SELECT taxonomy_node_id,as_of_date,ranking_universe,ranking_type,
                       horizon,score,rank_value,universe_size,calculation_version,
                       input_fingerprint,calculated_at
                FROM sector_intelligence.sector_rankings
                ORDER BY as_of_date DESC,ranking_type,rank_value
                LIMIT 60
                """
            ),
            "source_imports": psql_json(
                """
                SELECT run.run_key,source.name AS source_name,run.source_artifact_ref,
                       run.observed_at,run.status,run.taxonomy_rows,
                       run.membership_rows,run.metric_rows,run.index_rows,
                       run.validation_errors,run.imported_at
                FROM sector_intelligence.source_import_runs run
                JOIN core.source_systems source ON source.id=run.source_system_id
                ORDER BY run.imported_at DESC
                LIMIT 10
                """
            ),
            "acceptance": psql_json(
                """
                SELECT acceptance_run_id,run_key,taxonomy_key,node_name,as_of_date,
                       status,gate_count,passed_count,failed_count,blocked_count,
                       gates,started_at,finished_at,broker_write_allowed
                FROM sector_intelligence.v_acceptance_gate_summary
                ORDER BY started_at DESC
                LIMIT 10
                """
            ),
        }
    if skill_key in {"options_data_quality_control", "options_iv_greeks_review", "options_overlay_review"}:
        base["institutional_options"] = {
            "readiness": psql_json(
                """
                SELECT provider,exchange,underlying,expiry,minute_ts,
                       freshness_status,batch_quality_status,contract_count,
                       policy_key,model_family,policy_expires_at,
                       analytics_readiness,broker_write_allowed
                FROM trading.v_option_analytics_readiness
                ORDER BY minute_ts DESC,underlying
                LIMIT 30
                """
            ),
            "pipeline_runs": psql_json(
                """
                SELECT run_key,status,rows_read,rows_written,batches_created,
                       calculations_completed,calculations_blocked,
                       quality_summary,error_message,started_at,finished_at
                FROM ops.institutional_pipeline_runs
                WHERE workload_key='institutional_options_materializer'
                ORDER BY started_at DESC
                LIMIT 10
                """
            ),
            "acceptance": psql_json(
                """
                SELECT run_key,exchange,underlying,expiry,status,gate_count,
                       passed_count,failed_count,blocked_count,
                       validated_greeks_ratio,liquid_contract_ratio,
                       stale_contract_ratio,replay_coverage_ratio,
                       paper_attribution_coverage_ratio,started_at,finished_at
                FROM trading.v_option_acceptance_gate_summary
                ORDER BY started_at DESC
                LIMIT 10
                """
            ),
        }
    if skill_key == "company_research_note" or skill_key.startswith("long_term_"):
        base["fundamental_factory"] = {
            "coverage": psql_json(
                """
                SELECT company_key,legal_name,primary_symbol,primary_exchange,
                       real_company_verified,annual_statement_years,segment_count,
                       operational_kpi_count,market_share_series_count,peer_count,
                       management_communication_count,management_claim_count,
                       claims_with_outcomes,latest_statement_available_at,
                       latest_evidence_retrieved_at
                FROM research.v_company_fundamental_coverage
                ORDER BY real_company_verified DESC,annual_statement_years DESC,legal_name
                LIMIT 20
                """
            ),
            "dossiers": psql_json(
                """
                SELECT dossier_key,legal_name,primary_symbol,dossier_status,
                       version_number,version_status,research_as_of,evidence_coverage,
                       section_count,reviewed_section_count,specialist_count,
                       has_portfolio_fit,updated_at
                FROM research.v_latest_investment_dossiers
                ORDER BY updated_at DESC
                LIMIT 20
                """
            ),
            "acceptance": psql_json(
                """
                SELECT run_key,legal_name,primary_symbol,run_status,
                       real_company_verified,data_as_of,gate_count,passed_gate_count,
                       failed_gate_count,blocked_gate_count,started_at,completed_at
                FROM research.v_real_company_acceptance_status
                ORDER BY started_at DESC
                LIMIT 20
                """
            ),
        }
    if skill_key == "portfolio_snapshot_review" or widget_key == "portfolio_latest_positions":
        base["portfolio"] = psql_one(
            """
            SELECT count(*)::INT AS latest_positions,
                   coalesce(round(sum(market_value), 2), 0) AS market_value,
                   count(*) FILTER (WHERE market_price IS NULL)::INT AS missing_market_prices
            FROM portfolio.v_latest_positions
            """
        )
        base["top_positions"] = psql_json(
            """
            SELECT c.display_name, a.account_code, p.symbol, p.exchange,
                   p.quantity, p.market_value, p.unrealized_pnl
            FROM portfolio.v_latest_positions p
            JOIN portfolio.accounts a ON a.id = p.account_id
            LEFT JOIN portfolio.clients c ON c.id = a.client_id
            ORDER BY p.market_value DESC NULLS LAST
            LIMIT 5
            """
        )
    elif skill_key == "monitor_strategy_alerts" or widget_key == "market_signal_monitor":
        base["trading"] = {
            "signals": psql_one("SELECT count(*)::INT AS count FROM trading.signals"),
            "open_alerts": psql_one("SELECT count(*)::INT AS count FROM strategy.v_open_alerts"),
            "tradingview_tasks": psql_one("SELECT count(*)::INT AS queued FROM ops.tradingview_tasks WHERE status IN ('queued','open','in_progress')"),
        }
        base["recent_signals"] = psql_json(
            """
            SELECT ts, strategy, symbol, exchange, action, confidence, status
            FROM trading.v_recent_signals
            ORDER BY ts DESC
            LIMIT 5
            """
        )
    elif skill_key == "strategy_lab_review" or widget_key == "strategy_lab_queue":
        base["strategy"] = {
            "registry": psql_one("SELECT count(*)::INT AS count FROM strategy.strategy_registry"),
            "intakes": psql_one("SELECT count(*)::INT AS count FROM strategy.strategy_intakes"),
            "generated_ideas": psql_one("SELECT count(*)::INT AS count FROM strategy.generated_ideas"),
            "backtests": psql_one("SELECT count(*)::INT AS count FROM strategy.backtest_runs"),
            "optimizations": psql_one("SELECT count(*)::INT AS count FROM strategy.optimization_runs"),
            "validations": psql_one("SELECT count(*)::INT AS count FROM strategy.validation_reviews"),
        }
    elif skill_key in {"analyze_corporate_filing", "news_to_dashboard_alert"} or widget_key == "research_filings_inbox":
        base["research"] = {
            "feed_registry": psql_one("SELECT count(*)::INT AS count FROM research.feed_registry"),
            "corporate_filings": psql_one("SELECT count(*)::INT AS count FROM research.corporate_filings"),
            "filing_events": psql_one("SELECT count(*)::INT AS count FROM research.filing_events"),
            "news_items": psql_one("SELECT count(*)::INT AS count FROM market.news_items"),
            "social_items": psql_one("SELECT count(*)::INT AS count FROM market.social_items"),
        }
        base["research_hub"] = psql_json(
            """
            SELECT root_label, artifact_family, artifact_count
            FROM research.v_research_hub_summary
            ORDER BY artifact_count DESC
            LIMIT 6
            """
        )
        base["recent_filings"] = psql_json(
            """
            SELECT filing_id,source_name,exchange,symbol,company_name,title,
                   filing_type,event_type,filed_at,source_url,attachment_url,
                   extraction_status,opportunity_score,risk_score,event_status,
                   assigned_agent,event_created_at
            FROM research.v_corporate_filing_inbox
            WHERE filed_at >= current_date - interval '2 days'
            ORDER BY filed_at DESC NULLS LAST,event_created_at DESC NULLS LAST,filing_id DESC
            LIMIT 20
            """
        )
        base["special_situation_filings"] = psql_json(
            """
            SELECT filing_id,source_name,exchange,symbol,company_name,title,
                   filing_type,event_type,filed_at,source_url,attachment_url,
                   extraction_status,opportunity_score,risk_score,event_status,
                   assigned_agent,event_created_at
            FROM research.v_corporate_filing_inbox
            WHERE filed_at >= current_date - interval '14 days'
              AND event_type IN (
                  'merger','demerger','reverse_merger','open_offer','buyback',
                  'delisting','scheme_of_arrangement','preferential_allotment'
              )
            ORDER BY filed_at DESC NULLS LAST,event_created_at DESC NULLS LAST,filing_id DESC
            LIMIT 20
            """
        )
    elif skill_key == "model_runtime_check" or widget_key == "model_runtime_status":
        base["runtime"] = {
            "enabled_model_routes": psql_one("SELECT count(*)::INT AS count FROM agent.model_routes WHERE enabled = true"),
            "enabled_tools": psql_one("SELECT count(*)::INT AS count FROM agent.tool_registry WHERE enabled = true"),
            "active_agents": psql_one("SELECT count(*)::INT AS count FROM agent.v_active_agents"),
            "active_skills": psql_one("SELECT count(*)::INT AS count FROM agent.skills WHERE status = 'active'"),
        }
    return base


def execution_envelope_for(profile: dict[str, Any], skill: dict[str, Any]) -> dict[str, Any]:
    capability = capability_for(str(profile.get("agent_name") or ""))
    return {
        "mode": "deterministic_evidence_worker",
        "model_invocation": "deferred_until_model_stack",
        "primary_route": profile.get("primary_route") or profile.get("default_model_route"),
        "primary_route_status": profile.get("primary_route_status"),
        "fallback_route": profile.get("fallback_route"),
        "fallback_route_status": profile.get("fallback_route_status"),
        "escalation_route": profile.get("escalation_route"),
        "permission_level": profile.get("permission_level"),
        "tools": profile.get("default_tools") or [],
        "skills": profile.get("primary_skills") or [],
        "required_tools": skill.get("required_tools") or [],
        "capability_readiness": capability,
        "guardrails": profile.get("guardrails") or {},
        "human_interface": profile.get("human_interface"),
        "evidence_policy": "warehouse_and_source_references_only",
        "capital_action_allowed": False,
        "live_execution_allowed": False,
    }


def committee_position_for(
    job: dict[str, Any], profile: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    packet = context.get("committee_packet") or {}
    mandate = context.get("committee_mandate") or {}
    options = [str(option) for option in (packet.get("decision_options") or [])]
    if not packet or not options:
        raise ValueError("committee packet context or decision options are missing")

    role_text = " ".join(
        str(value or "")
        for value in (
            profile.get("agent_name"),
            profile.get("display_title"),
            mandate.get("committee_role"),
            mandate.get("vote_type"),
            mandate.get("challenge_mandate"),
        )
    ).lower()
    defensive_role = any(
        token in role_text
        for token in ("risk", "bear", "compliance", "validation", "quality", "kill switch", "forensic", "veto")
    )
    preferred = (
        ["request_evidence", "more_research", "revise", "paper_only", "paper_monitor", "paper_trade", "watchlist", "defer", "reject", "block"]
        if defensive_role
        else ["paper_monitor", "more_research", "watchlist", "conditional", "revise", "paper_trade", "defer"]
    )
    recommendation = next((option for option in preferred if option in options), options[0])
    evidence = packet.get("evidence") if isinstance(packet.get("evidence"), list) else []
    stance = "request_more_evidence" if defensive_role else "conditional"
    confidence = 82 if defensive_role else 72
    challenge = str(mandate.get("challenge_mandate") or "independent evidence and opportunity cost")
    thesis = (
        f"{profile.get('agent_name')} independently reviewed '{packet.get('title')}' under the "
        f"{mandate.get('committee_role', 'member')} mandate. The current bounded packet supports "
        f"a {recommendation} recommendation, conditional on resolving {challenge.lower()}. "
        f"This is a deterministic evidence-stage position; no model-generated facts or capital action were used."
    )
    conditions = [
        {"condition": "Verify every material claim against the packet source and current warehouse data."},
        {"condition": f"Resolve role challenge mandate: {challenge}."},
        {"condition": "Keep broker execution and capital allocation blocked until the human-final decision."},
    ]
    return {
        "packet_id": int(packet["id"]),
        "agent_name": str(profile.get("agent_name") or job.get("owner_agent")),
        "stance": stance,
        "recommendation": recommendation,
        "confidence": confidence,
        "thesis": thesis,
        "evidence": evidence + [
            {
                "source": "agent.committee_memberships",
                "agent_name": profile.get("agent_name"),
                "challenge_mandate": challenge,
            },
            {"source": "agent.worker_runs", "mode": "deterministic_evidence_worker"},
        ],
        "conditions": conditions,
    }


def submit_committee_position(position: dict[str, Any]) -> dict[str, Any]:
    return psql_one(
        f"""
        SELECT agent.submit_committee_position(
            {int(position['packet_id'])},
            {sql_literal(position['agent_name'])},
            {sql_literal(position['stance'])},
            {sql_literal(position['recommendation'])},
            {float(position['confidence'])},
            {sql_literal(position['thesis'])},
            {sql_jsonb(position['evidence'])},
            {sql_jsonb(position['conditions'])}
        ) AS result
        """
    ).get("result") or {}


def advance_committee_after_all_positions(packet_id: int) -> dict[str, Any]:
    packet = psql_one(
        f"SELECT * FROM agent.v_committee_packet_control WHERE id={int(packet_id)}"
    )
    if packet.get("packet_status") != "deliberating":
        return {"status": packet.get("packet_status"), "advanced": False}
    required = psql_one(
        f"""
        SELECT count(*)::int AS required_count,
               count(position.id)::int AS submitted_count
        FROM agent.committee_packets packet
        JOIN agent.committee_memberships membership
          ON membership.committee_key=packet.committee_key AND membership.required
        LEFT JOIN agent.committee_positions position
          ON position.packet_id=packet.id AND position.agent_name=membership.agent_name
        WHERE packet.id={int(packet_id)}
        """
    )
    if int(required.get("submitted_count") or 0) < int(required.get("required_count") or 0):
        return {"status": "deliberating", "advanced": False, **required}

    positions = psql_json(
        f"""
        SELECT position.id,position.agent_name,position.stance,position.recommendation,
               position.confidence,position.thesis,position.conditions,
               membership.vote_type,membership.challenge_mandate
        FROM agent.committee_positions position
        JOIN agent.committee_packets packet ON packet.id=position.packet_id
        JOIN agent.committee_memberships membership
          ON membership.committee_key=packet.committee_key AND membership.agent_name=position.agent_name
        WHERE position.packet_id={int(packet_id)}
        ORDER BY position.submitted_at,position.id
        """
    )
    for position in positions:
        existing = psql_one(
            f"""
            SELECT id FROM agent.committee_discussion_messages
            WHERE packet_id={int(packet_id)} AND from_agent={sql_literal(position['agent_name'])}
            LIMIT 1
            """
        )
        if existing:
            continue
        message_type = "risk_objection" if position.get("stance") in {"block", "request_more_evidence", "oppose"} else "challenge"
        body = (
            f"Post-quorum challenge from {position['agent_name']}: test the recommendation "
            f"'{position['recommendation']}' against {str(position.get('challenge_mandate') or 'the strongest disconfirming evidence').lower()}. "
            "No peer position changes the original sealed stance without new cited evidence."
        )
        psql_one(
            f"""
            SELECT agent.add_committee_discussion(
                {int(packet_id)},{sql_literal(position['agent_name'])},{sql_literal(message_type)},
                {sql_literal(body)},{int(position['id'])},
                {sql_jsonb([{'source': 'agent.committee_positions', 'position_id': position['id']}])}
            ) AS result
            """
        )

    voting = [position for position in positions if position.get("vote_type") != "non_voting"]
    counts: dict[str, int] = {}
    for position in voting:
        recommendation = str(position.get("recommendation") or "")
        counts[recommendation] = counts.get(recommendation, 0) + 1
    recommendation = sorted(counts, key=lambda value: (-counts[value], value))[0]
    dissent = [
        f"{position['agent_name']}: {position['recommendation']} ({position['stance']})"
        for position in voting
        if position.get("recommendation") != recommendation
    ]
    minutes = "\n".join(
        [
            f"Committee packet {packet.get('packet_key')} completed sealed independent collection and post-quorum challenge.",
            f"Recommendation tally: {json.dumps(counts, sort_keys=True)}.",
            f"Synthesized recommendation: {recommendation}.",
            "All capital, client-facing, and broker actions remain blocked pending Devarsh's human-final decision.",
        ]
    )
    result = psql_one(
        f"""
        SELECT agent.synthesize_committee_session(
            {int(packet_id)},{sql_literal(packet['chair_agent'])},{sql_literal(recommendation)},
            {sql_literal(minutes)},{sql_literal('; '.join(dissent) if dissent else 'No recommendation dissent recorded.')},
            {sql_jsonb([{'condition': 'Human-final decision by Devarsh is required before any external or capital action.'}])}
        ) AS result
        """
    ).get("result") or {}
    return {"status": result.get("packet_status"), "advanced": True, "packet": result}



def run_kronos_adapter(job: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    tool = psql_one(
        """
        SELECT enabled,config
        FROM agent.tool_registry
        WHERE tool_name='kronos_inference_adapter'
        LIMIT 1
        """
    )
    if not tool.get("enabled"):
        raise RuntimeError(
            "Kronos inference adapter is not ready. Run setup_kronos_runtime.sh and activate its verified registry entry."
        )
    message = context.get("agent_message") or {}
    metadata = message.get("metadata") if isinstance(message.get("metadata"), dict) else {}
    payload = metadata.get("input_payload") if isinstance(metadata.get("input_payload"), dict) else {}
    if not payload:
        raise ValueError("The Kronos graph node is missing its typed input_payload.")
    script = RUNTIME_ROOT / "scripts" / "run_kronos_forecast.py"
    command = [
        sys.executable,
        str(script),
        "--task-id",
        str(int(job["task_id"])),
        "--payload-json",
        json.dumps(payload, sort_keys=True),
    ]
    graph_run_id = metadata.get("graph_run_id")
    graph_node_run_id = metadata.get("graph_node_run_id")
    if str(graph_run_id or "").isdigit():
        command.extend(["--graph-run-id", str(int(graph_run_id))])
    if str(graph_node_run_id or "").isdigit():
        command.extend(["--graph-node-run-id", str(int(graph_node_run_id))])
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        timeout=int(os.environ.get("AI_OS_KRONOS_TASK_TIMEOUT_SECONDS") or 7200),
        env={**os.environ, "AI_OS_RUNTIME_ROOT": str(RUNTIME_ROOT)},
    )
    result: dict[str, Any] = {}
    for raw_line in reversed(completed.stdout.splitlines()):
        try:
            candidate = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            result = candidate
            break
    if completed.returncode != 0 or result.get("status") != "completed":
        detail = result.get("error") or completed.stderr.strip() or "Kronos adapter failed."
        raise RuntimeError(str(detail))
    context["kronos_forecast"] = result
    context["execution_envelope"] = {
        **(context.get("execution_envelope") or {}),
        "mode": "pinned_local_model_adapter",
        "model_invocation": "Kronos-mini",
        "capital_action_allowed": False,
        "live_execution_allowed": False,
        "broker_order_allowed": False,
    }
    return result

def summary_for(job: dict[str, Any], profile: dict[str, Any], skill: dict[str, Any], context: dict[str, Any]) -> tuple[str, list[str]]:
    skill_key = str(skill.get("skill_key") or job.get("suggested_skill_key") or "refresh_dashboard_widget")
    lines: list[str] = []
    next_actions: list[str] = []

    if skill_key == "kronos_forecast_feature_generation" and context.get("kronos_forecast"):
        forecast = context["kronos_forecast"]
        validation = forecast.get("validation") or {}
        terminal = ((forecast.get("features") or {}).get("terminal_return") or {})
        lines.append(
            f"Generated {forecast.get('path_count')} pinned Kronos mini research paths over "
            f"{forecast.get('horizon')} bars on {forecast.get('device')} and persisted "
            f"{forecast.get('stored_points')} forecast points as run {forecast.get('forecast_run_id')}."
        )
        lines.append(
            "This is a forecast distribution feature, not a trade signal. "
            f"Terminal median return={terminal.get('median')}; "
            f"10th-90th percentile={terminal.get('p10')} to {terminal.get('p90')}; "
            f"OHLC validity={validation.get('ohlc_validity')}; "
            f"volume validity={validation.get('volume_validity')}."
        )
        lines.append(
            f"Point-in-time source hash: {forecast.get('source_hash')}; output hash: {forecast.get('output_hash')}."
        )
        next_actions.append("Run realized calibration, walk-forward cost-aware backtesting, and independent Model Risk review.")
        next_actions.append("Keep every forecast-derived feature out of signals, paper orders, and live orders until the graph's human decision gate.")
    elif job.get("source_kind") == "committee_packet_position":
        position = committee_position_for(job, profile, context)
        packet = context.get("committee_packet") or {}
        lines.append(
            f"Prepared a sealed independent {position['stance']} position for {packet.get('committee_name')} "
            f"with recommendation {position['recommendation']} and confidence {position['confidence']}%."
        )
        lines.append(position["thesis"])
        next_actions.append("Submit the position, wait for every required member, then open post-quorum challenge and chair synthesis.")
        next_actions.append("Require Devarsh's human-final decision before capital, client-facing, or broker action.")
    elif skill_key == "research_evidence_curation" and "artifact_gaps" in context:
        gaps = context.get("artifact_gaps") or []
        remediation_by_type = {
            "worker_run_missing_note": (
                "Re-materialize the worker output into Obsidian, persist output_note_path, "
                "and verify the note exists before closing the run."
            ),
            "long_term_research_update_missing_note": (
                "Create a company research note linked to the update, symbol, thesis, source lineage, "
                "and review date; then reconcile note_path."
            ),
            "strategy_committee_missing_memo": (
                "Generate the committee memo from the sealed review packet, attach evidence and dissent, "
                "and keep the decision pending human approval."
            ),
        }
        gap_lines: list[str] = []
        for index, gap in enumerate(gaps, start=1):
            gap_type = str(gap.get("gap_type") or "unclassified_gap")
            remediation = remediation_by_type.get(
                gap_type,
                "Route the source row to its owner, materialize the missing durable artifact, "
                "and reconcile the registry before closure.",
            )
            gap_lines.extend([
                f"### Gap {index}: {gap.get('title') or gap_type}",
                f"- Type: {gap_type}; status: {gap.get('status') or 'unknown'}; owner: {gap.get('owner_agent') or 'unassigned'}.",
                f"- Evidence row: {gap.get('source_view') or 'unknown'}:{gap.get('source_id') or 'unknown'}; updated: {gap.get('updated_at') or gap.get('created_at') or 'unknown'}.",
                f"- Verified reason: {gap.get('gap_reason') or 'No reason was supplied by the gap registry.'}",
                f"- Remediation contract: {remediation}",
                "",
            ])
        lines.append("\n".join([
            "## Knowledge Coverage Gap Review",
            f"Reviewed {len(gaps)} current gap rows from authoritative view agent.v_output_artifact_gaps.",
            "This run is a read-only evidence review: no source records were altered and no trading action was requested or allowed.",
            "",
            *(
                gap_lines
                if gap_lines
                else [
                    "No open output-artifact gaps were returned by the warehouse at execution time.",
                    "The empty result is bounded to the current view and timestamp; it is not evidence that every research domain is complete.",
                ]
            ),
            "## Control Conclusion",
            "- Each gap remains open until its owning source row has a verified Obsidian artifact and the registry no longer returns it.",
            "- Capital action allowed: false. Live execution allowed: false. Broker orders allowed: false.",
        ]))
        next_actions.extend([
            "Assign each remediation contract to the listed owner and retain the source-view/source-ID pair in the task evidence.",
            "After remediation, rerun this skill and close only the gaps that disappear from agent.v_output_artifact_gaps.",
        ])
    elif context.get("research_source") and skill_key in {"company_research_note", "research_evidence_curation"}:
        source = context.get("research_source") or {}
        source_text = str(source.get("extracted_text") or "")
        headings = [
            line.lstrip("# ").strip()
            for line in source_text.splitlines()
            if line.strip().startswith("#") and line.lstrip("# ").strip()
        ][:8]
        evidence_lines = []
        for line in source_text.splitlines():
            candidate = line.strip().lstrip("-*> ").strip()
            if len(candidate) < 45:
                continue
            lowered = candidate.lower()
            if any(token in lowered for token in ("proof of concept", "educational", "agent", "risk", "backtest", "portfolio", "signal", "valuation")):
                evidence_lines.append(candidate[:320])
            if len(evidence_lines) >= 6:
                break
        summary = "\n".join([
            "### Verified source facts",
            f"- Source: [{source.get('title')}]({source.get('source_url')})",
            f"- Content hash: `{source.get('content_hash')}`; extracted words: {source.get('extraction_word_count')}; extraction status: `{source.get('extraction_status')}`.",
            f"- Operator objective: {source.get('research_objective')}",
            f"- Source sections detected: {', '.join(headings) if headings else 'No explicit headings detected.'}",
            "",
            "### Source-backed claims",
            *([f"- {line}" for line in evidence_lines] or ["- No claim is promoted until a human reviewer opens the stored source artifact."]),
            "",
            "### Fact, inference, and unknown",
            "- Fact: the stored artifact and hash above are the evidence boundary for this review.",
            "- Inference: the architecture can inform employee roles and research sequencing, but it does not establish investable alpha.",
            "- Unknown: empirical edge, capacity, slippage, market-regime stability, and India-specific data availability remain unverified.",
            "- Constraint: source claims marked as educational or proof-of-concept must not be represented as production evidence.",
        ])
        lines.append(summary)
        next_actions.extend([
            "Open the stored source artifact and approve or reject each extracted claim before durable thesis use.",
            "Send only approved, falsifiable claims to Head of Quant for point-in-time testing.",
        ])
    elif skill_key == "company_research_note":
        research = context.get("company_research") or {}
        query = str(research.get("query") or "").strip()
        inventory = research.get("filing_inventory") or {}
        filings = list(research.get("filings") or [])
        theses = list(research.get("holding_theses") or [])
        ideas = list(research.get("ideas") or [])
        notes = list(research.get("notes") or [])
        as_of = inventory.get("latest_filed_at") or "unavailable"
        filing_lines = [
            f"- Filing `{row.get('filing_id')}`: {row.get('source_name')} "
            f"{row.get('exchange') or ''}:{row.get('symbol') or ''}, "
            f"filed `{row.get('filed_at') or 'unknown'}`; "
            f"[{row.get('title') or 'Untitled filing'}]"
            f"({row.get('attachment_url') or row.get('source_url') or ''}); "
            f"extraction=`{row.get('extraction_status') or 'unknown'}`."
            for row in filings
        ]
        thesis_lines = [
            f"- Holding thesis `{row.get('id')}`: status=`{row.get('thesis_status')}`, "
            f"last_reviewed=`{row.get('last_reviewed_at') or 'never'}`, "
            f"conviction=`{row.get('conviction_score')}`."
            for row in theses
        ]
        idea_lines = [
            f"- Idea `{row.get('id')}`: {row.get('title')} status=`{row.get('status')}`, "
            f"owner=`{row.get('owner_agent') or 'unassigned'}`, updated=`{row.get('updated_at')}`."
            for row in ideas
        ]
        note_lines = [
            f"- Note `{row.get('note_path')}`: {row.get('title')}, "
            f"indexed=`{row.get('indexed_at')}`."
            for row in notes
        ]
        lines.append("\n".join([
            "## Company Research Decision Memo",
            f"- Requested company/symbol: `{query or 'not identified'}`.",
            f"- Filing warehouse boundary: {inventory.get('total_filings', 0)} rows; latest filed_at `{as_of}`.",
            "",
            "### Verified facts",
            *(filing_lines or [f"- No official filing row matched `{query}` in the current warehouse. This is a missing-evidence result, not evidence that no filing exists."]),
            *(thesis_lines or [f"- No holding-thesis row matched `{query}`."]),
            *(idea_lines or [f"- No research-idea row matched `{query}`."]),
            *(note_lines or [f"- No indexed Obsidian note matched `{query}`."]),
            "",
            "### Inference",
            "- No investment inference is promoted unless it is traceable to the matched source rows above.",
            "- Existing triage scores, thesis status, and idea status are workflow metadata, not a buy or sell conclusion.",
            "",
            "### Missing evidence",
            *(
                ["- The matched filing attachments still require document-level extraction and term verification."]
                if filings
                else ["- The requested official filing is absent from the current matched warehouse set; collector coverage or entity mapping must be checked."]
            ),
            "- Current market context, management commentary, valuation, disconfirming evidence, and portfolio fit were not supplied by this bounded request.",
            "",
            "### Decision status",
            "- Insufficient evidence for a trade, price target, sizing, or client action.",
            "- Broker write allowed: false. Live execution allowed: false. Human review required: true.",
        ]))
        if not query:
            next_actions.append("Ask the operator for an exact exchange symbol or company name, then rerun the evidence lookup.")
        elif not filings:
            next_actions.append(
                f"Run the official NSE/BSE collector and entity-resolution check for `{query}`, "
                "then repeat this memo with the matched filing ID."
            )
        else:
            next_actions.append("Extract and verify every matched official attachment before updating the durable company thesis.")
        next_actions.append("Route any verified material finding to independent Risk and human review; do not place an order.")
    elif context.get("research_source") and skill_key in {"generate_strategy_hypothesis", "head_quant_governance", "validate_strategy_model"}:
        source = context.get("research_source") or {}
        hypotheses = context.get("research_hypotheses") or []
        cycle = context.get("research_cycle") or {}
        requested = str((source.get("metadata") or {}).get("requested_hypothesis") or "").strip()
        if not requested and hypotheses:
            requested = str(hypotheses[0].get("edge_hypothesis") or "").strip()
        if not requested:
            requested = "No trade signal is emitted unless a source-supported alpha rule has point-in-time inputs and can abstain when evidence is insufficient."
        universe = source.get("target_universe") or cycle.get("universe") or "operator-defined liquid instruments"
        workflow_contracts = context.get("workflow_contracts") or []
        workflow_lines = [
            "### Current registered workflow controls",
            *(
                [
                    f"- `{row.get('workflow_key')}`: {row.get('workflow_name')} is `{row.get('status')}`, "
                    f"permission `{row.get('permission_level')}`, human approval required={bool(row.get('approval_required'))}."
                    for row in workflow_contracts
                ]
                or ["- No matching workflow contract is registered; comparison remains blocked until the control plane is defined."]
            ),
            "- TradingAgents patterns are adopted as typed, checkpointed research handoffs only; the internal workflow registry and human approval boundary remain controlling.",
            "",
        ]
        summary = "\n".join([
            "### Falsifiable hypothesis",
            f"- {requested}",
            "- Null: the rule has no positive net out-of-sample expectancy after costs and produces no improvement over the declared benchmark.",
            "",
            "### Point-in-time test specification",
            f"1. Freeze cycle `{cycle.get('cycle_key') or 'new-cycle-required'}` at `{cycle.get('as_of') or 'explicit as_of required'}` for universe `{universe}`.",
            "2. Version every source record by event time and ingestion time; use only values observable before each decision timestamp.",
            "3. Convert the narrative into one deterministic signal contract: inputs, transforms, lookback, direction, conviction, confidence, and explicit abstain conditions.",
            "4. Use anchored walk-forward splits with a final untouched holdout; purge overlapping labels and embargo adjacent observations.",
            "5. Compare against buy-and-hold, cash, and a simple non-LLM rule using identical universe, rebalance times, and costs.",
            "6. Apply fees, bid-ask spread, impact, borrow/funding, turnover, liquidity, and capacity assumptions before scoring.",
            "7. Report CAGR, volatility, Sharpe/Sortino, max drawdown, hit rate, turnover, exposure, tail loss, stability by regime, and abstention rate.",
            "8. Run survivorship, delisting, corporate-action, timestamp, restatement, duplicate-row, and data-gap checks before any result is reviewable.",
            "",
            *workflow_lines,
            "### Invalidation and promotion gates",
            "- Reject if the effect disappears after costs, depends on leaked/restated data, fails the untouched holdout, or is concentrated in too few names/dates.",
            "- Reject if parameter neighborhoods are unstable, regime performance is contradictory without a declared filter, or capacity is below the intended book size.",
            "- Abstain when required inputs are stale, contradictory, outside the tested universe, or below the confidence floor.",
            "- Promotion path: research -> independent model validation -> risk review -> paper monitor -> paper trade. No automatic live promotion.",
            f"- Current execution flags: broker_write_allowed={bool(cycle.get('broker_write_allowed'))}; live_execution_allowed={bool(cycle.get('live_execution_allowed'))}.",
        ])
        lines.append(summary)
        next_actions.extend([
            "Specify the exact alpha formula, rebalance timestamp, benchmark, cost schedule, and data tables before queueing a backtest.",
            "Create a new immutable research cycle for every changed hypothesis or data cut; never overwrite this cycle.",
            "Require independent Model Validation and Risk approval before paper monitoring or trading.",
        ])
    elif skill_key == "analyze_corporate_filing":
        message = context.get("agent_message") or {}
        objective = " ".join(
            str(value or "")
            for value in (job.get("objective"), message.get("subject"), message.get("body"))
        ).lower()
        special_terms = (
            "merger", "demerger", "reverse merger", "open offer", "buyback",
            "delisting", "scheme of arrangement", "preferential allotment",
            "special situation",
        )
        special_requested = any(term in objective for term in special_terms)
        evidence_rows = list(
            (context.get("special_situation_filings") if special_requested else context.get("recent_filings"))
            or []
        )
        requested_event_types: set[str] = set()
        event_phrases = (
            ("reverse merger", "reverse_merger"),
            ("demerger", "demerger"),
            ("open offer", "open_offer"),
            ("buyback", "buyback"),
            ("delisting", "delisting"),
            ("scheme of arrangement", "scheme_of_arrangement"),
            ("preferential allotment", "preferential_allotment"),
        )
        for phrase, event_type in event_phrases:
            if phrase in objective:
                requested_event_types.add(event_type)
        if "merger" in objective and not {"reverse_merger", "demerger"}.intersection(requested_event_types):
            requested_event_types.add("merger")
        if requested_event_types:
            evidence_rows = [
                row for row in evidence_rows
                if str(row.get("event_type") or "") in requested_event_types
            ]
        context["selected_filing_evidence"] = evidence_rows
        filing_lines: list[str] = []
        unparsed_count = 0
        for row in evidence_rows:
            source_url = str(row.get("attachment_url") or row.get("source_url") or "").strip()
            extraction_status = str(row.get("extraction_status") or "unknown")
            if extraction_status not in {"extracted", "completed", "parsed"}:
                unparsed_count += 1
            company = str(row.get("company_name") or row.get("symbol") or "Unknown company")
            exchange_symbol = ":".join(
                value for value in (str(row.get("exchange") or ""), str(row.get("symbol") or "")) if value
            ) or "symbol unavailable"
            title = str(row.get("title") or "Untitled filing").replace("\n", " ").strip()
            filing_lines.append(
                f"- **{company}** (`{exchange_symbol}`), stored event `{row.get('event_type') or 'unclassified'}`, "
                f"filed `{row.get('filed_at') or 'time unavailable'}`; filing id `{row.get('filing_id')}`."
            )
            filing_lines.append(
                f"  Source: [{title}]({source_url})" if source_url else f"  Source URL missing for: {title}"
            )
            filing_lines.append(
                "  Triage state: "
                f"extraction=`{extraction_status}`, event_status=`{row.get('event_status') or 'unknown'}`, "
                f"opportunity_score=`{row.get('opportunity_score')}`, risk_score=`{row.get('risk_score')}`."
            )
        if requested_event_types:
            scope_label = (
                "event types " + ", ".join(sorted(requested_event_types)) + " from the last 14 days"
            )
        else:
            scope_label = "special-situation filings from the last 14 days" if special_requested else "filings from the last 2 days"
        summary = "\n".join([
            "### Evidence-reviewed filing set",
            f"- Scope: {scope_label}; bounded rows returned: {len(evidence_rows)}.",
            *(filing_lines or ["- No matching stored filing rows were found. This is an evidence gap, not a negative finding."]),
            "",
            "### Facts, inferences, and unknowns",
            "- Fact: every item above is a stored NSE/BSE collector row and carries its source or attachment URL when supplied by the exchange.",
            "- Inference boundary: the stored event label and opportunity/risk scores are triage metadata, not verified transaction terms or an investment conclusion.",
            f"- Document gap: {unparsed_count} of {len(evidence_rows)} rows do not have a completed parsed-document status; terms inside those attachments remain unverified.",
            "- Unknowns until document review: consideration, swap ratio, record date, approvals, conditions precedent, timeline, tax treatment, liquidity, and break risk.",
            "- Decision boundary: this memo makes no buy, sell, sizing, capital-allocation, or execution recommendation.",
        ])
        lines.append(summary)
        if evidence_rows:
            next_actions.append("Parse the linked exchange attachments and extract the exact transaction terms before forming a thesis.")
            next_actions.append("Route verified terms to Special Situations, independent Risk, and then human committee review; keep broker writes locked.")
        else:
            next_actions.append("Refine the company, symbol, event type, or date window and rerun the official filing collector.")
    elif job.get("source_kind") == "agent_message":
        message = context.get("agent_message", {})
        lines.append(
            f"Processed internal message '{message.get('subject', job.get('title'))}' "
            f"from {message.get('from_agent', 'unknown')} to {message.get('to_agent', profile.get('agent_name'))}."
        )
        lines.append(
            f"Routed work to {profile.get('agent_name', job.get('owner_agent'))} using "
            f"{skill.get('skill_name', skill_key)} with priority {job.get('priority', 'medium')}."
        )
        if message.get("body"):
            lines.append(f"Message objective: {str(message.get('body'))[:280]}")
        next_actions.append("Reply to the sending agent if more evidence, approval, or a specialist handoff is required.")
        next_actions.append("Escalate to Charlie Munger before any capital allocation, client-facing, or broker-execution action.")
    elif skill_key == "portfolio_snapshot_review":
        portfolio = context.get("portfolio", {})
        lines.append(
            f"Portfolio snapshot sees {portfolio.get('latest_positions', 0)} latest positions across {context.get('clients', {}).get('count', 0)} active clients."
        )
        lines.append(f"Visible latest market value totals about INR {portfolio.get('market_value', 0)}.")
        if portfolio.get("missing_market_prices"):
            next_actions.append(f"Resolve {portfolio.get('missing_market_prices')} missing market prices before client-facing output.")
        next_actions.append("Review top exposures and stale holding theses with Charlie before any rebalance action.")
    elif skill_key == "monitor_strategy_alerts":
        trading = context.get("trading", {})
        lines.append(
            f"Trading monitor sees {trading.get('signals', {}).get('count', 0)} stored signals and {trading.get('open_alerts', {}).get('count', 0)} open alerts."
        )
        lines.append(f"TradingView queued/open tasks: {trading.get('tradingview_tasks', {}).get('queued', 0)}.")
        next_actions.append("Keep this as paper/review mode until Risk approves any live execution path.")
    elif skill_key == "strategy_lab_review":
        strategy = context.get("strategy", {})
        lines.append(
            "Strategy lab has "
            f"{strategy.get('registry', {}).get('count', 0)} registered strategies, "
            f"{strategy.get('generated_ideas', {}).get('count', 0)} generated ideas, "
            f"{strategy.get('backtests', {}).get('count', 0)} backtests, and "
            f"{strategy.get('validations', {}).get('count', 0)} validation reviews."
        )
        next_actions.append("Prioritize candidates that have data lineage, transaction costs, and validation coverage.")
    elif skill_key == "model_runtime_check":
        runtime = context.get("runtime", {})
        lines.append(
            "Runtime registry has "
            f"{runtime.get('active_agents', {}).get('count', 0)} active agents, "
            f"{runtime.get('active_skills', {}).get('count', 0)} active skills, "
            f"{runtime.get('enabled_model_routes', {}).get('count', 0)} enabled model routes, and "
            f"{runtime.get('enabled_tools', {}).get('count', 0)} enabled tools."
        )
        next_actions.append("Run the worker on a schedule after manual run outputs are reviewed.")
    else:
        department = str(profile.get("department_name") or profile.get("department") or "operations").lower()
        objective = str(job.get("objective") or job.get("title") or "governed work")[:320]
        source = f"{job.get('source_kind') or 'task'}:{job.get('source_ref') or job.get('task_id')}"
        family_guidance = {
            "research": "separated sourced evidence, interpretation, disconfirming evidence, and unresolved questions",
            "quant": "framed a falsifiable hypothesis with data lineage, costs, leakage controls, and out-of-sample validation",
            "portfolio": "checked book purpose, horizon, gross/net exposure, concentration, liquidity, and client mandate",
            "risk": "tested limits, tail scenarios, data quality, model risk, and kill-switch implications",
            "trading": "kept order intent, execution evidence, costs, and post-trade attribution separate from investment thesis",
            "data": "checked provenance, schema, freshness, reconciliation, licensing, and quarantine boundaries",
            "engineering": "bounded the change, verification evidence, rollback path, and production safety controls",
            "knowledge": "preserved citations, entity links, provenance, and the durable Obsidian output path",
            "client": "checked account scope, suitability, privacy, reconciliation, approval, and communication controls",
            "treasury": "checked cash, collateral, liquidity, counterparty, currency, and funding constraints",
            "executive": "framed opportunity cost, decision owner, dissent, approval boundary, and next accountable action",
        }
        guidance = next((value for key, value in family_guidance.items() if key in department), None)
        if guidance is None:
            guidance = "checked source evidence, ownership, dependencies, approval boundaries, and next accountable action"
        lines.append(
            f"{profile.get('agent_name', job.get('owner_agent'))} triaged '{objective}' using "
            f"{skill.get('skill_name', skill_key)} and {guidance}."
        )
        lines.append(f"Bounded source: {source}. Model invocation is deferred; this run records deterministic operating evidence only.")
        next_actions.append("Review unresolved evidence gaps and route any specialized analysis through the assigned department skill.")

    lines.append(f"Agent stance: {profile.get('display_title') or profile.get('agent_name')} uses {profile.get('cost_policy', 'local_first')} routing.")
    return " ".join(lines), next_actions


def write_note(job: dict[str, Any], profile: dict[str, Any], skill: dict[str, Any], context: dict[str, Any], summary: str, next_actions: list[str]) -> Path:
    today = datetime.now().strftime("%Y-%m-%d")
    filename = (
        f"{today} task-{job.get('task_id')} "
        f"{slugify(str(profile.get('agent_name') or job.get('owner_agent') or 'agent'))} "
        f"{slugify(str(job.get('suggested_skill_key') or 'skill'))}.md"
    )
    path = OUTPUT_DIR / filename
    relative_path = path.relative_to(VAULT_ROOT)
    spool_path = WORKER_SPOOL_ROOT / relative_path
    evidence = [
        "agent.v_live_agent_worker_queue",
        "agent.v_active_agents",
        "agent.v_agent_skill_matrix",
        str(job.get("source_kind") or ""),
        str(job.get("source_ref") or ""),
    ]
    for filing in (context.get("selected_filing_evidence") or context.get("special_situation_filings") or context.get("recent_filings") or []):
        evidence.append(
            "research.v_corporate_filing_inbox "
            f"filing_id={filing.get('filing_id')} "
            f"source={filing.get('attachment_url') or filing.get('source_url') or 'missing'}"
        )
    for gap in context.get("artifact_gaps") or []:
        evidence.append(
            "agent.v_output_artifact_gaps "
            f"gap_type={gap.get('gap_type')} "
            f"source={gap.get('source_view')}:{gap.get('source_id')}"
        )
    body = [
        f"# Agent Worker Run - Task {job.get('task_id')}",
        "",
        f"Date: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"Agent: {profile.get('agent_name', job.get('owner_agent'))}",
        f"Role: {profile.get('display_title') or profile.get('role_scope') or 'Agent'}",
        f"Skill: {skill.get('skill_name', job.get('suggested_skill_key'))}",
        f"Widget: {job.get('widget_key')} - {job.get('widget_title')}",
        f"Task status before run: {job.get('task_status')}",
        f"Execution mode: {(context.get('execution_envelope') or {}).get('mode', 'deterministic_evidence_worker')}",
        f"Model invocation: {(context.get('execution_envelope') or {}).get('model_invocation', 'deferred_until_model_stack')}",
        "",
        "## Output",
        "",
        summary,
        "",
        "## Next Actions",
        "",
    ]
    body.extend([f"- {action}" for action in next_actions])
    body.extend(
        [
            "",
            "## Evidence",
            "",
        ]
    )
    body.extend([f"- {item}" for item in evidence if item])
    body.extend(
        [
            "",
            "## Bounded Context Snapshot",
            "",
            "```json",
            json.dumps(context, indent=2, default=str),
            "```",
            "",
        ]
    )
    note_text = "\n".join(body)
    spool_path.parent.mkdir(parents=True, exist_ok=True)
    spool_tmp = spool_path.with_suffix(spool_path.suffix + ".tmp")
    spool_tmp.write_text(note_text, encoding="utf-8")
    spool_tmp.replace(spool_path)

    mirror = {
        "status": "pending",
        "vault_path": str(path),
        "spool_path": str(spool_path),
    }
    try:
        subprocess.run(
            ["/bin/mkdir", "-p", str(path.parent)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=WORKER_MIRROR_TIMEOUT_SECONDS,
        )
        subprocess.run(
            ["/bin/cp", "-f", str(spool_path), str(path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=WORKER_MIRROR_TIMEOUT_SECONDS,
        )
        mirror["status"] = "mirrored"
    except subprocess.TimeoutExpired as exc:
        mirror.update({"status": "deferred_timeout", "error": f"{type(exc).__name__}: {exc}"[:500]})
    except (OSError, subprocess.CalledProcessError) as exc:
        mirror.update({"status": "deferred_error", "error": f"{type(exc).__name__}: {exc}"[:500]})
    context["note_persistence"] = mirror
    return path


def complete_job(job: dict[str, Any], profile: dict[str, Any], skill: dict[str, Any], context: dict[str, Any], summary: str, note_path: Path) -> dict[str, Any]:
    relative_note = str(note_path.relative_to(VAULT_ROOT))
    evidence = [
        {"source": "agent.v_live_agent_worker_queue", "task_id": job.get("task_id")},
        {"source": "agent.v_agent_skill_matrix", "skill_key": skill.get("skill_key")},
        {
            "source": "obsidian_note" if (context.get("note_persistence") or {}).get("status") == "mirrored" else "obsidian_mirror_pending",
            "path": relative_note,
            "mirror_status": (context.get("note_persistence") or {}).get("status"),
        },
        {
            "source": "durable_internal_spool",
            "path": (context.get("note_persistence") or {}).get("spool_path"),
        },
    ]
    for filing in (context.get("selected_filing_evidence") or context.get("special_situation_filings") or context.get("recent_filings") or []):
        evidence.append({
            "source": "research.v_corporate_filing_inbox",
            "filing_id": filing.get("filing_id"),
            "source_url": filing.get("attachment_url") or filing.get("source_url"),
            "event_type": filing.get("event_type"),
            "extraction_status": filing.get("extraction_status"),
        })
    for gap in context.get("artifact_gaps") or []:
        evidence.append({
            "source": "agent.v_output_artifact_gaps",
            "gap_type": gap.get("gap_type"),
            "source_view": gap.get("source_view"),
            "source_id": gap.get("source_id"),
            "owner_agent": gap.get("owner_agent"),
        })
    kronos_forecast = context.get("kronos_forecast")
    if isinstance(kronos_forecast, dict):
        evidence.extend(kronos_forecast.get("evidence") or [])
        evidence.append(
            {
                "source": "strategy.kronos_forecast_runs",
                "forecast_run_id": kronos_forecast.get("forecast_run_id"),
                "source_hash": kronos_forecast.get("source_hash"),
                "output_hash": kronos_forecast.get("output_hash"),
            }
        )
    input_snapshot = {
        "job": job,
        "agent": profile,
        "skill": skill,
        "context_counts": context,
    }
    message = context.get("agent_message") if isinstance(context.get("agent_message"), dict) else {}
    message_metadata = message.get("metadata") if isinstance(message.get("metadata"), dict) else {}
    graph_managed = str(message_metadata.get("graph_node_run_id") or "").isdigit()
    task_completion_status = "completed" if graph_managed else "needs_review"
    inbox_completion_status = "completed" if graph_managed else "needs_review"
    inbox_recommendation = (
        "Graph node evidence captured; Graph Control Plane owns downstream review and approval."
        if graph_managed
        else "Review the completed agent worker output note, then decide whether to close, rerun, or escalate."
    )
    sql = f"""
    WITH inserted_run AS (
        INSERT INTO agent.worker_runs (
            task_id, widget_id, agent_name, skill_key, run_mode, status,
            input_snapshot, output_summary, output_note_path, evidence,
            started_at, finished_at
        )
        VALUES (
            {int(job.get('task_id'))},
            {int(job.get('widget_id')) if job.get('widget_id') is not None else 'NULL'},
            {sql_literal(profile.get('agent_name') or job.get('owner_agent') or 'Jarvis')},
            {sql_literal(skill.get('skill_key') or job.get('suggested_skill_key'))},
            'manual_once',
            'completed',
            {sql_jsonb(input_snapshot)},
            {sql_literal(summary)},
            {sql_literal(relative_note)},
            {sql_jsonb(evidence)},
            now(),
            now()
        )
        RETURNING id, task_id, widget_id, agent_name, skill_key, status,
                  output_summary, output_note_path, evidence, started_at, finished_at
    ),
    updated_task AS (
        UPDATE agent.tasks
        SET status = {sql_literal(task_completion_status)},
            output_note_path = {sql_literal(relative_note)},
            evidence = coalesce(evidence, '[]'::jsonb) || {sql_jsonb(evidence)},
            updated_at = now()
        WHERE id = {int(job.get('task_id'))}
        RETURNING id, status, output_note_path, updated_at
    ),
    updated_widget AS (
        UPDATE ops.dashboard_widgets
        SET last_refreshed_at = now(),
            evidence = coalesce(evidence, '[]'::jsonb) || {sql_jsonb(evidence)},
            updated_at = now()
        WHERE id = {int(job.get('widget_id')) if job.get('widget_id') is not None else -1}
        RETURNING id, widget_key, last_refreshed_at
    ),
    updated_inbox AS (
        UPDATE agent.inbox_items
        SET status = {sql_literal(inbox_completion_status)},
            recommended_action = {sql_literal(inbox_recommendation)},
            evidence = coalesce(evidence, '[]'::jsonb) || {sql_jsonb(evidence)},
            updated_at = now()
        WHERE id = {int(job.get('inbox_item_id')) if job.get('inbox_item_id') is not None else -1}
        RETURNING id, status, updated_at
    ),
    updated_message AS (
        UPDATE agent.agent_messages
        SET status = 'read',
            read_at = coalesce(read_at, now()),
            processing_status = 'processed',
            processed_at = now(),
            error_message = NULL,
            metadata = coalesce(metadata, '{{}}'::jsonb) || jsonb_build_object(
                'completed_worker_run_id', (SELECT id FROM inserted_run),
                'completed_output_note_path', {sql_literal(relative_note)},
                'completed_at', now()
            )
        WHERE generated_task_id = {int(job.get('task_id'))}
        RETURNING id,status,processing_status,processed_at
    )
    SELECT json_build_object(
        'worker_run', (SELECT row_to_json(inserted_run) FROM inserted_run),
        'task', (SELECT row_to_json(updated_task) FROM updated_task),
        'widget', (SELECT row_to_json(updated_widget) FROM updated_widget),
        'inbox', (SELECT row_to_json(updated_inbox) FROM updated_inbox),
        'message', (SELECT row_to_json(updated_message) FROM updated_message)
    )::text;
    """
    return json.loads(psql_text(sql))


def record_worker_failure(job: dict[str, Any], profile: dict[str, Any], skill: dict[str, Any], error: Exception) -> dict[str, Any]:
    message = str(error)[:1200]
    task_id = int(job.get("task_id"))
    inbox_id = int(job.get("inbox_item_id")) if job.get("inbox_item_id") is not None else -1
    graph_message = psql_one(
        f"""
        SELECT metadata
        FROM agent.agent_messages
        WHERE generated_task_id={task_id}
        ORDER BY created_at DESC,id DESC
        LIMIT 1
        """
    )
    graph_metadata = graph_message.get("metadata") if isinstance(graph_message.get("metadata"), dict) else {}
    graph_managed = str(graph_metadata.get("graph_node_run_id") or "").isdigit()
    failure_status = "failed" if graph_managed else "needs_review"
    inbox_failure_status = "blocked" if graph_managed else "needs_review"
    evidence = [
        {"source": "run_agent_worker_once", "task_id": task_id, "status": "failed"},
        {"error": message},
    ]
    return psql_one(
        f"""
        WITH inserted_run AS (
            INSERT INTO agent.worker_runs (
                task_id, widget_id, agent_name, skill_key, run_mode, status,
                input_snapshot, output_summary, evidence, started_at, finished_at
            ) VALUES (
                {task_id},
                {int(job.get('widget_id')) if job.get('widget_id') is not None else 'NULL'},
                {sql_literal(profile.get('agent_name') or job.get('owner_agent') or 'Jarvis')},
                {sql_literal(skill.get('skill_key') or job.get('suggested_skill_key'))},
                'manual_once', 'failed', {sql_jsonb({'job': job})},
                {sql_literal('Worker failure: ' + message)}, {sql_jsonb(evidence)}, now(), now()
            )
            RETURNING id,task_id,agent_name,skill_key,status,output_summary,finished_at
        ),
        updated_task AS (
            UPDATE agent.tasks
            SET status={sql_literal(failure_status)},
                evidence=coalesce(evidence,'[]'::jsonb) || {sql_jsonb(evidence)},
                updated_at=now()
            WHERE id={task_id}
            RETURNING id,status
        ),
        updated_inbox AS (
            UPDATE agent.inbox_items
            SET status={sql_literal(inbox_failure_status)},
                recommended_action='Worker failed. Review the recorded error, fix the bounded cause, then requeue.',
                evidence=coalesce(evidence,'[]'::jsonb) || {sql_jsonb(evidence)},
                updated_at=now()
            WHERE id={inbox_id}
            RETURNING id
        )
        SELECT inserted_run.*,updated_task.status AS task_status
        FROM inserted_run CROSS JOIN updated_task
        """
    )


def run_once(limit: int, include_completed: bool, task_id: int | None = None) -> dict[str, Any]:
    jobs = get_queue(limit, include_completed, task_id)
    results: list[dict[str, Any]] = []
    for job in jobs:
        skill_key = str(job.get("suggested_skill_key") or "refresh_dashboard_widget")
        skill = skill_for(skill_key)
        if not skill:
            skill = skill_for("refresh_dashboard_widget")
        routed_agent = routed_agent_for(job, skill)
        profile = profile_for(routed_agent)
        if not profile:
            profile = profile_for(str(job.get("owner_agent") or "Jarvis"))
        if not profile:
            profile = profile_for("Jarvis")
        claim = claim_task(
            job.get("task_id"),
            str(profile.get("agent_name") or "Jarvis"),
            job.get("source_kind") == "committee_packet_position",
        )
        if not claim:
            results.append(
                {
                    "task_id": job.get("task_id"),
                    "widget_key": job.get("widget_key"),
                    "agent_name": profile.get("agent_name"),
                    "skill_key": skill.get("skill_key"),
                    "output_note_path": None,
                    "worker_run_id": None,
                    "task_status": job.get("task_status"),
                    "skipped": "not_queued_or_already_claimed",
                }
            )
            continue
        try:
            if job.get("source_kind") == "committee_packet_position":
                gate_result = {
                    "overall_status": "passed",
                    "next_task_status": "in_progress",
                    "gate_ids": [],
                    "reason": "deterministic sealed position; no model or external provider invocation",
                }
            elif skill_key == "kronos_forecast_feature_generation":
                gate_result = {
                    "overall_status": "passed",
                    "next_task_status": "in_progress",
                    "gate_ids": [],
                    "reason": "pinned local model adapter with independent tool readiness and no provider spend",
                }
            else:
                gate_result = evaluate_task_provider_gates(job.get("task_id"), str(profile.get("agent_name") or "Jarvis"))
            if gate_result.get("overall_status") != "passed":
                results.append(
                    {
                        "task_id": job.get("task_id"),
                        "widget_key": job.get("widget_key"),
                        "agent_name": profile.get("agent_name"),
                        "skill_key": skill.get("skill_key"),
                        "output_note_path": None,
                        "worker_run_id": None,
                        "task_status": gate_result.get("next_task_status"),
                        "provider_gate_status": gate_result.get("overall_status"),
                        "provider_gate_ids": gate_result.get("gate_ids"),
                    }
                )
                continue
            context = context_for(skill_key, job.get("widget_key"), job)
            context["execution_envelope"] = execution_envelope_for(profile, skill)
            if skill_key == "kronos_forecast_feature_generation":
                run_kronos_adapter(job, context)
            summary, next_actions = summary_for(job, profile, skill, context)
            note_path = write_note(job, profile, skill, context, summary, next_actions)
            completed = complete_job(job, profile, skill, context, summary, note_path)
            committee_result: dict[str, Any] | None = None
            if job.get("source_kind") == "committee_packet_position":
                position = committee_position_for(job, profile, context)
                submitted = submit_committee_position(position)
                committee_result = {
                    "position": submitted,
                    "deliberation": advance_committee_after_all_positions(int(position["packet_id"])),
                }
                current_task = psql_one(
                    f"SELECT id,status,output_note_path,updated_at FROM agent.tasks WHERE id={int(job.get('task_id'))}"
                )
                completed["task"] = current_task
            results.append(
                {
                    "task_id": job.get("task_id"),
                    "widget_key": job.get("widget_key"),
                    "agent_name": profile.get("agent_name"),
                    "skill_key": skill.get("skill_key"),
                    "output_note_path": completed.get("worker_run", {}).get("output_note_path"),
                    "worker_run_id": completed.get("worker_run", {}).get("id"),
                    "task_status": completed.get("task", {}).get("status"),
                    "committee": committee_result,
                }
            )
        except Exception as exc:
            failed = record_worker_failure(job, profile, skill, exc)
            results.append(
                {
                    "task_id": job.get("task_id"),
                    "widget_key": job.get("widget_key"),
                    "agent_name": profile.get("agent_name"),
                    "skill_key": skill.get("skill_key"),
                    "output_note_path": None,
                    "worker_run_id": failed.get("id"),
                    "task_status": failed.get("task_status", "needs_review"),
                    "error": str(exc),
                }
            )
    return {
        "count": len(results),
        "results": results,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one bounded AI OS agent worker pass.")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--include-completed", action="store_true")
    parser.add_argument("--task-id", type=int)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = run_once(max(1, args.limit), args.include_completed, args.task_id)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"processed={result['count']}")
        for row in result["results"]:
            if row.get("skipped"):
                print(f"- task {row['task_id']} skipped: {row['skipped']}")
            elif row.get("provider_gate_status") and row.get("provider_gate_status") != "passed":
                print(f"- task {row['task_id']} {row['agent_name']} {row['skill_key']} blocked by provider gate {row['provider_gate_status']}")
            else:
                print(f"- task {row['task_id']} {row['agent_name']} {row['skill_key']} -> {row['output_note_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
