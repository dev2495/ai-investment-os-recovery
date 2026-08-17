#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


RUNTIME_ROOT = Path(os.environ.get("AI_OS_RUNTIME_ROOT") or Path(__file__).absolute().parents[1])
VAULT_ROOT = Path(os.environ.get("AI_OS_VAULT_ROOT") or RUNTIME_ROOT.parent)
POSTGRES_PASSWORD = os.environ.get("AI_OS_POSTGRES_PASSWORD", "ai_os_local_dev_change_me")
POSTGRES_PORT = os.environ.get("AI_OS_POSTGRES_PORT", "54329")
API_BASE_URL = os.environ.get("AI_OS_API_BASE_URL", "http://127.0.0.1:8765").rstrip("/")


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    payload = {} if value is None else value
    return f"{sql_literal(json.dumps(payload, sort_keys=True, default=str))}::jsonb"


def sql_text_array(values: object) -> str:
    if values is None:
        return "ARRAY[]::text[]"
    if isinstance(values, str):
        items = [item.strip() for item in values.split(",") if item.strip()]
    elif isinstance(values, list):
        items = [str(item).strip() for item in values if str(item).strip()]
    else:
        items = []
    if not items:
        return "ARRAY[]::text[]"
    return "ARRAY[" + ",".join(sql_literal(item) for item in items) + "]::text[]"


def sql_numeric(value: object, *, required: bool = False, field_name: str = "value") -> str:
    if value is None or str(value).strip() == "":
        if required:
            raise ValueError(f"{field_name} is required")
        return "NULL"
    try:
        return str(Decimal(str(value).replace(",", "").strip()))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc


def required_text(arguments: dict, field_name: str) -> str:
    value = str(arguments.get(field_name) or "").strip()
    if not value:
        raise ValueError(f"{field_name} is required")
    return value


def psql_command_candidates() -> list[list[str]]:
    return [
        [
            "docker", "exec", "-i", "ai_os_postgres", "psql",
            "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os",
        ],
        [
            "psql", "-h", "127.0.0.1", "-p", POSTGRES_PORT,
            "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os",
        ],
    ]


def run_psql_text(sql: str) -> str:
    errors = []
    env = os.environ.copy()
    env.setdefault("PGPASSWORD", POSTGRES_PASSWORD)
    for command in psql_command_candidates():
        completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False, env=env)
        if completed.returncode == 0:
            return completed.stdout.strip()
        errors.append((command[0], (completed.stderr or completed.stdout).strip()))
    joined_errors = " | ".join(f"{source}: {error}" for source, error in errors)
    raise RuntimeError(joined_errors)


def run_psql_json(query: str) -> list[dict]:
    sql = f"SELECT coalesce(json_agg(row_to_json(result_rows)), '[]'::json)::text FROM ({query}) result_rows;"
    return json.loads(run_psql_text(sql) or "[]")


def run_psql_json_statement(sql: str) -> list[dict]:
    return json.loads(run_psql_text(sql) or "[]")


def run_command(command: list[str]) -> dict:
    completed = subprocess.run(command, cwd=RUNTIME_ROOT.parent, text=True, capture_output=True, check=False)
    return {"returncode": completed.returncode, "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()}


def post_api_json(path: str, payload: dict, timeout: float = 60.0) -> dict:
    data = json.dumps(payload, default=str).encode("utf-8")
    request = urllib.request.Request(
        f"{API_BASE_URL}{path}",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API {path} failed with HTTP {exc.code}: {body}") from exc


def limit_arg(arguments: dict, default: int = 25, maximum: int = 200) -> int:
    try:
        value = int(arguments.get("limit", default))
    except (TypeError, ValueError):
        value = default
    return max(1, min(value, maximum))


def tool_result(payload: object) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, sort_keys=True, default=str)}]}


def list_active_agents(arguments: dict) -> dict:
    return tool_result(
        run_psql_json(
            """
            SELECT agent_name, department, default_model_route, permission_level, output_targets,
                   CASE
                       WHEN agent_name = 'Charlie Munger' THEN 'main_orchestrator'
                       WHEN agent_name = 'Jarvis' THEN 'runtime_layer'
                       ELSE 'specialist_agent'
                   END AS stack_role
            FROM agent.v_active_agents
            ORDER BY
                CASE
                    WHEN agent_name = 'Charlie Munger' THEN 1
                    WHEN agent_name = 'Jarvis' THEN 2
                    ELSE 3
                END,
                department,
                agent_name
            """
        )
    )


def materialize_agent_schedules(arguments: dict) -> dict:
    payload = {
        "actor": arguments.get("actor") or "Jarvis",
        "limit": limit_arg(arguments, default=10, maximum=50),
    }
    return tool_result(post_api_json("/api/agents/schedules/run", payload))


def calibrate_kronos_forecast(arguments: dict) -> dict:
    forecast_run_id = arguments.get("forecast_run_id")
    if forecast_run_id is None:
        raise ValueError("forecast_run_id is required")
    payload = {
        "forecast_run_id": int(forecast_run_id),
        "actor": str(arguments.get("actor") or "Model Validation Agent"),
    }
    return tool_result(post_api_json("/api/kronos/forecasts/calibrate", payload, timeout=180.0))


def list_open_tasks(arguments: dict) -> dict:
    limit = limit_arg(arguments)
    return tool_result(
        run_psql_json(
            f"""
            SELECT id, title, objective, owner_agent, status, priority, approval_required, source_kind, source_ref, created_at
            FROM agent.v_open_tasks
            LIMIT {limit}
            """
        )
    )


def blueprint_summary(arguments: dict) -> dict:
    return tool_result(
        {
            "summary": run_psql_json(
                """
                SELECT metric, value, interpretation
                FROM core.v_os_blueprint_summary
                ORDER BY metric
                """
            ),
            "domains": run_psql_json(
                """
                SELECT domain_key, section_number, domain_name, domain_type,
                       owner_agent, owner_department, priority, status,
                       requirement_count, done_count, partial_count,
                       planned_count, blocked_count, mapped_count,
                       progress_score, next_action
                FROM core.v_os_blueprint_domains
                ORDER BY section_number
                """
            ),
            "sync_runs": run_psql_json(
                """
                SELECT run_key, version_label, status, source_path, source_sha256,
                       domain_count, requirement_count, done_count, partial_count,
                       planned_count, error_message, started_at, finished_at, created_by
                FROM core.v_os_blueprint_sync_runs
                ORDER BY created_at DESC
                LIMIT 10
                """
            ),
        }
    )


def blueprint_requirements(arguments: dict) -> dict:
    status = str(arguments.get("status") or "").strip()
    domain_key = str(arguments.get("domain_key") or "").strip()
    priority = str(arguments.get("priority") or "").strip()
    clauses = []
    if status:
        clauses.append(f"current_status = {sql_literal(status)}")
    if domain_key:
        clauses.append(f"domain_key = {sql_literal(domain_key)}")
    if priority:
        clauses.append(f"priority = {sql_literal(priority)}")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    limit = limit_arg(arguments, default=50, maximum=200)
    return tool_result(
        run_psql_json(
            f"""
            SELECT requirement_key, requirement_name, requirement_type, priority,
                   current_status, owner_agent, owner_department, domain_key,
                   domain_name, section_number, mapped_object_type, mapped_object_key,
                   mapped_object_status, mapped_object_found, evidence_note_path,
                   acceptance_criteria, next_action, updated_at
            FROM core.v_os_blueprint_requirements
            {where}
            ORDER BY
                CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
                CASE current_status WHEN 'planned' THEN 1 WHEN 'partial' THEN 2 WHEN 'blocked' THEN 3 WHEN 'done' THEN 4 ELSE 5 END,
                section_number,
                requirement_key
            LIMIT {limit}
            """
        )
    )


def blueprint_v9_summary(arguments: dict) -> dict:
    """Compatibility alias for clients using the pre-v10 MCP tool name."""
    return blueprint_summary(arguments)


def blueprint_v9_requirements(arguments: dict) -> dict:
    """Compatibility alias for clients using the pre-v10 MCP tool name."""
    return blueprint_requirements(arguments)


def sync_position_remediation_queue(arguments: dict) -> dict:
    actor = str(arguments.get("actor") or "Portfolio Manager").strip()
    limit = limit_arg(arguments, default=200, maximum=500)
    create_tasks = bool(arguments.get("create_tasks", arguments.get("createTasks", True)))
    result_rows = run_psql_json_statement(
        f"""
        SELECT jsonb_build_array(
            books.sync_position_object_remediation_queue(
                {limit},
                {str(create_tasks).lower()},
                {sql_literal(actor)}
            )
        )::TEXT
        """
    )
    result = result_rows[0] if result_rows else {"error": "position remediation sync failed"}
    audit_mcp_call(
        tool_name="ai_os_sync_position_remediation_queue",
        action_type="sync_position_remediation_queue",
        permission_level="write_with_approval",
        actor=actor,
        target_table="books.position_object_remediation_queue",
        request_payload=arguments,
        result_payload=result,
    )
    return tool_result(result)


def position_remediation_queue(arguments: dict) -> dict:
    status = str(arguments.get("status") or "").strip()
    owner_agent = str(arguments.get("owner_agent") or arguments.get("ownerAgent") or "").strip()
    gap_type = str(arguments.get("gap_type") or arguments.get("gapType") or "").strip()
    symbol = str(arguments.get("symbol") or "").strip().upper()
    clauses = []
    if status:
        clauses.append(f"status = {sql_literal(status)}")
    if owner_agent:
        clauses.append(f"owner_agent = {sql_literal(owner_agent)}")
    if gap_type:
        clauses.append(f"gap_type = {sql_literal(gap_type)}")
    if symbol:
        clauses.append(f"upper(symbol) = {sql_literal(symbol)}")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    limit = limit_arg(arguments, default=50, maximum=200)
    return tool_result(
        run_psql_json(
            f"""
            SELECT id, remediation_key, book_position_id, client_code, client_name,
                   account_code, symbol, exchange, instrument_type, book_key,
                   book_name, purpose_key, purpose_name, gap_type, severity,
                   priority, owner_agent, skill_key, status, recommended_action,
                   task_id, task_status, inbox_id, inbox_status, v9_gap_count,
                   v9_gap_types, v9_completeness_score, v9_decision_readiness,
                   evidence, created_by, created_at, updated_at, resolved_at
            FROM books.v_position_object_remediation_queue
            {where}
            ORDER BY
                CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
                CASE status WHEN 'queued' THEN 1 WHEN 'task_created' THEN 2 WHEN 'in_progress' THEN 3 WHEN 'resolved' THEN 4 ELSE 5 END,
                updated_at DESC
            LIMIT {limit}
            """
        )
    )


def position_remediation_summary(arguments: dict) -> dict:
    return tool_result(
        run_psql_json(
            """
            SELECT metric, value, interpretation
            FROM books.v_position_object_remediation_summary
            ORDER BY metric
            """
        )
    )


def sync_long_term_coverage_queue(arguments: dict) -> dict:
    actor = str(arguments.get("actor") or "Long-Term Portfolio Manager").strip()
    limit = limit_arg(arguments, default=100, maximum=500)
    create_tasks = bool(arguments.get("create_tasks", arguments.get("createTasks", True)))
    result_rows = run_psql_json_statement(
        f"""
        SELECT jsonb_build_array(
            portfolio.sync_long_term_coverage_queue(
                {limit},
                {str(create_tasks).lower()},
                {sql_literal(actor)}
            )
        )::TEXT
        """
    )
    result = result_rows[0] if result_rows else {"error": "long-term coverage sync failed"}
    audit_mcp_call(
        tool_name="ai_os_sync_long_term_coverage_queue",
        action_type="sync_long_term_coverage_queue",
        permission_level="write_with_approval",
        actor=actor,
        target_table="portfolio.long_term_coverage_queue",
        request_payload=arguments,
        result_payload=result,
    )
    return tool_result(result)


def long_term_coverage_queue(arguments: dict) -> dict:
    status = str(arguments.get("status") or "").strip()
    owner_agent = str(arguments.get("owner_agent") or arguments.get("ownerAgent") or "").strip()
    gap_type = str(arguments.get("gap_type") or arguments.get("gapType") or "").strip()
    symbol = str(arguments.get("symbol") or "").strip().upper()
    severity = str(arguments.get("severity") or "").strip()
    clauses = []
    if status:
        clauses.append(f"status = {sql_literal(status)}")
    if owner_agent:
        clauses.append(f"owner_agent = {sql_literal(owner_agent)}")
    if gap_type:
        clauses.append(f"gap_type = {sql_literal(gap_type)}")
    if symbol:
        clauses.append(f"upper(symbol) = {sql_literal(symbol)}")
    if severity:
        clauses.append(f"severity = {sql_literal(severity)}")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    limit = limit_arg(arguments, default=50, maximum=200)
    return tool_result(
        {
            "summary": run_psql_json(
                """
                SELECT metric, value, interpretation
                FROM portfolio.v_long_term_coverage_summary
                ORDER BY metric
                """
            ),
            "queue": run_psql_json(
                f"""
                SELECT id, coverage_key, symbol, exchange, holding_thesis_id,
                       company_name, thesis_status, decision_status, gap_type,
                       severity, priority, priority_score, owner_agent, status,
                       recommended_action, task_id, task_status, inbox_id,
                       inbox_status, long_term_gross_exposure, client_count,
                       checklist_count, checklist_complete_count,
                       valuation_model_count, valuation_complete_count,
                       monte_carlo_run_count, latest_monte_carlo_at,
                       thesis_note_path, next_review_due_at, created_by,
                       created_at, updated_at
                FROM portfolio.v_long_term_coverage_queue
                {where}
                ORDER BY
                    CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
                    CASE status WHEN 'queued' THEN 1 WHEN 'task_created' THEN 2 WHEN 'in_progress' THEN 3 WHEN 'resolved' THEN 4 ELSE 5 END,
                    priority_score DESC,
                    updated_at DESC
                LIMIT {limit}
                """
            ),
        }
    )


def long_term_coverage_summary(arguments: dict) -> dict:
    return tool_result(
        run_psql_json(
            """
            SELECT metric, value, interpretation
            FROM portfolio.v_long_term_coverage_summary
            ORDER BY metric
            """
        )
    )


def p2cursor_source_summary(arguments: dict) -> dict:
    return tool_result(
        run_psql_json(
            """
            SELECT source_file_id, original_path, file_type, size_bytes, import_status, staged_row_count
            FROM client_data.v_p2cursor_source_summary
            ORDER BY file_type, original_path
            """
        )
    )


def algo_import_summary(arguments: dict) -> dict:
    return tool_result(run_psql_json("SELECT metric, value FROM core.v_algo_import_summary ORDER BY metric"))


def legacy_source_readiness(arguments: dict) -> dict:
    limit = int(arguments.get("limit") or 25)
    return tool_result(
        {
            "summary": run_psql_json(
                """
                SELECT metric, value, interpretation
                FROM core.v_legacy_source_readiness_summary
                ORDER BY metric
                """
            ),
            "p2cursor_files": run_psql_json(
                f"""
                SELECT source_file_id, original_path, file_type, profiled_row_count,
                       staged_row_count, readiness_status, recommended_action
                FROM client_data.v_p2cursor_extraction_readiness
                ORDER BY
                    CASE readiness_status
                        WHEN 'missing_staging' THEN 1
                        WHEN 'staging_count_mismatch' THEN 2
                        WHEN 'staged_needs_mapping' THEN 3
                        WHEN 'sqlite_profiled_needs_mapping' THEN 4
                        ELSE 5
                    END,
                    original_path
                LIMIT {limit}
                """
            ),
            "algo_tables": run_psql_json(
                f"""
                SELECT source_system, database_path, table_name, source_rows,
                       imported_rows, deduplicated_rows, rejected_rows,
                       resolved_rows, readiness_status, resolution_mode,
                       canonical_relation, source_value, recommended_action,
                       resolution_evidence
                FROM core.v_algo_extraction_readiness
                ORDER BY
                    CASE readiness_status
                        WHEN 'profiled_not_promoted' THEN 1
                        WHEN 'partially_promoted' THEN 2
                        WHEN 'archived_governed' THEN 3
                        WHEN 'promoted_deduplicated' THEN 4
                        WHEN 'promoted' THEN 5
                        ELSE 6
                    END,
                    CASE source_value WHEN 'high_value' THEN 1 ELSE 2 END,
                    source_rows DESC NULLS LAST,
                    table_name
                LIMIT {limit}
                """
            ),
            "issues": run_psql_json(
                f"""
                SELECT id, run_key, source_family, issue_type, severity, status,
                       source_ref, source_rows, imported_rows, owner_agent,
                       recommended_action, created_at
                FROM core.v_legacy_source_extraction_issues
                LIMIT {limit}
                """
            ),
        }
    )


def legacy_source_resolution_board(arguments: dict) -> dict:
    limit = max(1, min(int(arguments.get("limit") or 100), 250))
    return tool_result(
        run_psql_json(
            f"""
            SELECT source_system, database_path, table_name, source_rows,
                   imported_rows, deduplicated_rows, rejected_rows, resolved_rows,
                   resolution_mode, canonical_relation, readiness_status,
                   source_value, recommended_action, resolution_evidence
            FROM core.v_algo_extraction_readiness
            ORDER BY
                CASE readiness_status
                    WHEN 'profiled_not_promoted' THEN 1
                    WHEN 'partially_promoted' THEN 2
                    WHEN 'archived_governed' THEN 3
                    WHEN 'promoted_deduplicated' THEN 4
                    WHEN 'promoted' THEN 5
                    ELSE 6
                END,
                source_rows DESC NULLS LAST,
                source_system,
                table_name
            LIMIT {limit}
            """
        )
    )


def run_legacy_source_readiness(arguments: dict) -> dict:
    actor = str(arguments.get("actor") or "Jarvis").strip()
    return tool_result(post_api_json("/api/legacy-source-readiness/run", {"actor": actor}))


def component_inventory(arguments: dict) -> dict:
    source_system = arguments.get("source_system")
    where = f"WHERE source_system = {sql_literal(source_system)}" if source_system else ""
    return tool_result(
        run_psql_json(
            f"""
            SELECT source_system, component_name, file_count, total_size_bytes, languages
            FROM core.v_source_component_inventory
            {where}
            ORDER BY source_system, component_name
            """
        )
    )


def source_requirements(arguments: dict) -> dict:
    package_manager = arguments.get("package_manager")
    where = f"WHERE package_manager = {sql_literal(package_manager)}" if package_manager else ""
    return tool_result(
        run_psql_json(
            f"""
            SELECT source_system, package_manager, package_name, version_spec, appears_as_dev_dependency, references_count, components
            FROM core.v_source_requirements
            {where}
            ORDER BY source_system, package_manager, package_name
            LIMIT 300
            """
        )
    )


def source_lineage_summary(arguments: dict) -> dict:
    return tool_result(
        run_psql_json(
            """
            SELECT lineage_type, source_system, source_type, sensitivity,
                   row_count, raw_artifact_rows, source_file_rows,
                   first_seen_at, latest_seen_at, open_or_staged_rows
            FROM core.v_source_lineage_summary
            ORDER BY row_count DESC, source_system, lineage_type
            LIMIT 100
            """
        )
    )


def source_lineage(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50, maximum=200)
    lineage_type = str(arguments.get("lineage_type") or "").strip()
    client_code = str(arguments.get("client_code") or "").strip()
    symbol = str(arguments.get("symbol") or "").strip()
    source_system = str(arguments.get("source_system") or "").strip()
    clauses = []
    if lineage_type:
        clauses.append(f"lineage_type = {sql_literal(lineage_type)}")
    if client_code:
        clauses.append(f"client_code = {sql_literal(client_code)}")
    if symbol:
        clauses.append(f"symbol = {sql_literal(symbol)}")
    if source_system:
        clauses.append(f"source_system = {sql_literal(source_system)}")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result(
        run_psql_json(
            f"""
            SELECT lineage_type, row_ref, row_id, source_system, source_type,
                   artifact_type, title, source_url, local_path, content_hash,
                   event_at, source_file_id, raw_artifact_id, client_code,
                   account_code, symbol, reconciliation_status, lineage_payload
            FROM core.v_source_artifact_lineage
            {where}
            ORDER BY event_at DESC NULLS LAST, lineage_type, row_ref
            LIMIT {limit}
            """
        )
    )


def import_artifact_coverage(arguments: dict) -> dict:
    return tool_result(
        run_psql_json(
            """
            SELECT import_surface, total_rows, linked_rows, missing_rows,
                   coverage_pct, description
            FROM core.v_import_artifact_coverage
            ORDER BY import_surface
            """
        )
    )


def import_artifact_gaps(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50, maximum=200)
    return tool_result(
        run_psql_json(
            f"""
            SELECT import_surface, row_ref, title, source_path, content_hash,
                   gap_reason
            FROM core.v_import_artifact_gaps
            ORDER BY import_surface, row_ref
            LIMIT {limit}
            """
        )
    )


def portfolio_risk_limit_checks(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50, maximum=200)
    status = str(arguments.get("check_status") or "").strip()
    book_key = str(arguments.get("book_key") or "").strip()
    client_code = str(arguments.get("client_code") or "").strip()
    symbol = str(arguments.get("symbol") or "").strip()
    clauses = []
    if status:
        clauses.append(f"check_status = {sql_literal(status)}")
    if book_key:
        clauses.append(f"book_key = {sql_literal(book_key)}")
    if client_code:
        clauses.append(f"client_code = {sql_literal(client_code)}")
    if symbol:
        clauses.append(f"symbol = {sql_literal(symbol)}")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result(
        {
            "summary": run_psql_json(
                """
                SELECT metric, value, interpretation
                FROM risk.v_portfolio_risk_dashboard_summary
                ORDER BY metric
                """
            ),
            "checks": run_psql_json(
                f"""
                SELECT check_key, book_key, book_name, client_code, client_name,
                       symbol, exchange, scope_type, scope_ref, limit_key,
                       limit_name, limit_type, threshold_value, unit, severity,
                       actual_value, utilization_pct, check_status,
                       check_message, recommended_action, latest_as_of, evidence
                FROM risk.v_portfolio_risk_limit_checks
                {where}
                ORDER BY
                    CASE check_status WHEN 'breach' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END,
                    CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
                    actual_value DESC NULLS LAST,
                    book_key,
                    client_name,
                    symbol
                LIMIT {limit}
                """
            ),
        }
    )


def refresh_portfolio_risk_events(arguments: dict) -> dict:
    actor = str(arguments.get("actor") or "Risk Agent").strip()
    result_rows = run_psql_json_statement(
        f"""
        SELECT jsonb_build_array(risk.refresh_portfolio_risk_events({sql_literal(actor)}))::TEXT
        """
    )
    result = result_rows[0] if result_rows else {"error": "portfolio risk event refresh failed"}
    audit_mcp_call(
        tool_name="ai_os_refresh_portfolio_risk_events",
        action_type="refresh_portfolio_risk_events",
        permission_level="write_with_approval",
        actor=actor,
        target_table="risk.events",
        request_payload=arguments,
        result_payload=result,
    )
    return tool_result(result)


def portfolio_intelligence_v2(arguments: dict) -> dict:
    return tool_result(
        {
            "summary": run_psql_json(
                """
                SELECT section, item_key, item_name, item_value, interpretation, payload
                FROM books.v_portfolio_intelligence_v2
                ORDER BY
                    CASE section WHEN 'risk' THEN 1 WHEN 'portfolio_overview' THEN 2 WHEN 'concentration' THEN 3 ELSE 4 END,
                    item_key,
                    item_name
                LIMIT 120
                """
            ),
            "top_symbols": run_psql_json(
                """
                SELECT client_code, client_name, symbol, exchange, gross_exposure,
                       net_exposure, overall_bias, active_books, purposes,
                       conflict_count, gap_count, decision_readiness,
                       recommended_next_action
                FROM portfolio.v_symbol_intelligence
                ORDER BY gross_exposure DESC NULLS LAST, gap_count DESC, client_name, symbol
                LIMIT 25
                """
            ),
            "risk": run_psql_json(
                """
                SELECT check_status, severity, count(*) AS rows
                FROM risk.v_portfolio_risk_limit_checks
                GROUP BY check_status, severity
                ORDER BY check_status, severity
                """
            ),
        }
    )


def symbol_intelligence_v2(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=25, maximum=100)
    client_code = str(arguments.get("client_code") or "").strip()
    symbol = str(arguments.get("symbol") or "").strip().upper()
    decision_state = str(arguments.get("v2_decision_state") or arguments.get("decision_state") or "").strip()
    clauses = []
    if client_code:
        clauses.append(f"client_code = {sql_literal(client_code)}")
    if symbol:
        clauses.append(f"symbol = {sql_literal(symbol)}")
    if decision_state:
        clauses.append(f"v2_decision_state = {sql_literal(decision_state)}")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result(
        {
            "summary": run_psql_json(
                """
                SELECT metric, value, interpretation
                FROM portfolio.v_symbol_intelligence_v2_summary
                ORDER BY metric
                """
            ),
            "symbols": run_psql_json(
                f"""
                SELECT client_code, client_name, symbol, exchange,
                       gross_long, gross_short, gross_exposure, net_exposure,
                       overall_bias, active_books, purposes,
                       v2_decision_state, v2_recommended_next_action,
                       v2_decision_flags, v2_priority_rank,
                       critical_remediation_count, remediation_task_count,
                       remediation_items, risk_breach_count, risk_warning_count,
                       risk_items, coordination_question_count, coordination_items,
                       pending_committee_item_count, committee_items,
                       material_filing_count, latest_filing_title,
                       latest_filing_source_url, news_count, latest_news_title,
                       latest_news_url, symbol_strategy_candidate_count,
                       strategy_dossier_count, active_strategy_dossier_count,
                       strategy_dossiers, v2_decision_packet
                FROM portfolio.v_symbol_intelligence_v2
                {where}
                ORDER BY v2_priority_rank, gross_exposure DESC NULLS LAST,
                         critical_remediation_count DESC, client_name, symbol
                LIMIT {limit}
                """
            ),
        }
    )


def symbol_intelligence_v2_summary(arguments: dict) -> dict:
    return tool_result(
        run_psql_json(
            """
            SELECT metric, value, interpretation
            FROM portfolio.v_symbol_intelligence_v2_summary
            ORDER BY metric
            """
        )
    )


def route_symbol_intelligence_action(arguments: dict) -> dict:
    actor = str(arguments.get("actor") or "Charlie Munger").strip()
    symbol = str(arguments.get("symbol") or "").strip().upper()
    if not symbol:
        raise ValueError("symbol is required")
    client_code = str(arguments.get("client_code") or arguments.get("clientCode") or "").strip()
    exchange = str(arguments.get("exchange") or "NSE").strip().upper()
    action_type = str(arguments.get("action_type") or arguments.get("actionType") or "refresh_thesis").strip()
    notes = str(arguments.get("notes") or "").strip()
    result_rows = run_psql_json_statement(
        f"""
        SELECT jsonb_build_array(
            portfolio.route_symbol_intelligence_action(
                {sql_literal(client_code or None)},
                {sql_literal(symbol)},
                {sql_literal(exchange)},
                {sql_literal(action_type)},
                {sql_literal(actor)},
                {sql_literal(notes or None)}
            )
        )::TEXT
        """
    )
    result = result_rows[0] if result_rows else {"error": "symbol intelligence action failed"}
    audit_mcp_call(
        tool_name="ai_os_route_symbol_intelligence_action",
        action_type="route_symbol_intelligence_action",
        permission_level="write_with_approval",
        actor=actor,
        target_table="portfolio.symbol_intelligence_actions",
        target_id=result.get("action_id") if isinstance(result, dict) else None,
        request_payload=arguments,
        result_payload=result,
    )
    return tool_result(result)


def symbol_intelligence_actions(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=25, maximum=100)
    client_code = str(arguments.get("client_code") or arguments.get("clientCode") or "").strip()
    symbol = str(arguments.get("symbol") or "").strip().upper()
    action_type = str(arguments.get("action_type") or arguments.get("actionType") or "").strip()
    clauses = []
    if client_code:
        clauses.append(f"client_code = {sql_literal(client_code)}")
    if symbol:
        clauses.append(f"symbol = {sql_literal(symbol)}")
    if action_type:
        clauses.append(f"action_type = {sql_literal(action_type)}")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result(
        {
            "summary": run_psql_json(
                """
                SELECT metric, value, interpretation
                FROM portfolio.v_symbol_intelligence_action_summary
                ORDER BY metric
                """
            ),
            "actions": run_psql_json(
                f"""
                SELECT id, action_key, client_code, client_name, symbol, exchange,
                       action_type, action_status, owner_agent, target_workspace,
                       priority, task_id, task_status, inbox_id, inbox_status,
                       decision_state, recommended_action, notes, created_by,
                       created_at, updated_at
                FROM portfolio.v_symbol_intelligence_actions
                {where}
                ORDER BY created_at DESC
                LIMIT {limit}
                """
            ),
        }
    )


def position_objects_v9(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50, maximum=200)
    client_code = str(arguments.get("client_code") or "").strip()
    symbol = str(arguments.get("symbol") or "").strip()
    book_key = str(arguments.get("book_key") or "").strip()
    readiness = str(arguments.get("readiness") or "").strip()
    clauses = []
    if client_code:
        clauses.append(f"client_code = {sql_literal(client_code)}")
    if symbol:
        clauses.append(f"symbol = {sql_literal(symbol.upper())}")
    if book_key:
        clauses.append(f"book_key = {sql_literal(book_key)}")
    if readiness:
        clauses.append(f"v9_decision_readiness = {sql_literal(readiness)}")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result(
        run_psql_json(
            f"""
            SELECT book_position_id, client_code, client_name, account_code,
                   symbol, exchange, instrument_type, book_key, book_name,
                   purpose_key, purpose_name, owner_agent, strategy_key,
                   direction, market_value, gross_exposure, net_exposure,
                   time_horizon, source_kind, source_ref, source_freshness_at,
                   approval_state, risk_budget_pct, capital_budget_pct,
                   stop_price, target_price, time_exit_at, hedge_intent,
                   offset_intent, review_state, thesis_count, has_active_thesis,
                   next_review_due_at, exit_count, has_active_exit,
                   v9_gap_types, v9_gap_count, v9_completeness_score,
                   v9_decision_readiness, as_of, updated_at
            FROM books.v_position_objects_v9
            {where}
            ORDER BY v9_gap_count DESC, gross_exposure DESC NULLS LAST, client_name, symbol
            LIMIT {limit}
            """
        )
    )


def position_object_gap_summary(arguments: dict) -> dict:
    return tool_result(
        run_psql_json(
            """
            SELECT gap_type, position_count, client_count, symbol_count,
                   avg_completeness_score, severity, owner_agent
            FROM books.v_position_object_gap_summary
            ORDER BY
                CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
                position_count DESC,
                gap_type
            """
        )
    )


def cross_book_coordination_questions(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50, maximum=200)
    client_code = str(arguments.get("client_code") or "").strip()
    symbol = str(arguments.get("symbol") or "").strip()
    clauses = []
    if client_code:
        clauses.append(f"client_code = {sql_literal(client_code)}")
    if symbol:
        clauses.append(f"symbol = {sql_literal(symbol.upper())}")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result(
        run_psql_json(
            f"""
            SELECT synthetic_id, client_code, client_name, symbol, exchange,
                   gross_long, gross_short, net_exposure, offset_ratio,
                   overall_bias, active_books, purposes, offset_intents,
                   coordination_question, severity, owner_agent, latest_as_of
            FROM books.v_cross_book_coordination_questions
            {where}
            ORDER BY
                CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
                offset_ratio DESC NULLS LAST,
                gross_long DESC NULLS LAST
            LIMIT {limit}
            """
        )
    )


def live_office_rooms(arguments: dict) -> dict:
    return tool_result(
        run_psql_json(
            """
            SELECT room_key, room_name, room_rank, agent_count,
                   active_agent_count, open_task_count, blocked_task_count,
                   unread_message_count, open_inbox_count, open_risk_event_count,
                   room_workload_score, latest_activity_at, room_state, agents
            FROM agent.v_live_office_rooms
            ORDER BY room_rank, room_name
            """
        )
    )


def live_office_agent_activity(arguments: dict) -> dict:
    agent_name = str(arguments.get("agent_name") or "").strip()
    department_key = str(arguments.get("department_key") or "").strip()
    limit = int(arguments.get("limit") or 50)
    clauses = []
    if agent_name:
        clauses.append(f"agent_name = {sql_literal(agent_name)}")
    if department_key:
        clauses.append(f"department_key = {sql_literal(department_key)}")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result(
        run_psql_json(
            f"""
            SELECT agent_name, display_title, reports_to_agent, department_key,
                   department_name, role_rank, hierarchy_level, office_location,
                   animation_state, color_token, icon_hint, mailbox_address,
                   unread_message_count, open_task_count, queued_task_count,
                   in_progress_task_count, blocked_task_count, open_inbox_count,
                   urgent_inbox_count, open_risk_event_count,
                   current_task_id, current_task_title, current_task_status,
                   current_task_priority, current_work_title,
                   current_work_detail, latest_message_from_agent,
                   latest_message_subject, latest_message_priority,
                   latest_message_status, latest_worker_skill_name,
                   latest_worker_status, latest_worker_summary,
                   latest_worker_output_note_path, open_tasks,
                   workload_score, live_state, latest_activity_at
            FROM agent.v_live_office_agent_activity
            {where}
            ORDER BY role_rank, agent_name
            LIMIT {limit}
            """
        )
    )


def approval_board(arguments: dict) -> dict:
    status = str(arguments.get("approval_status") or arguments.get("status") or "").strip()
    board_lane = str(arguments.get("board_lane") or "").strip()
    risk_level = str(arguments.get("risk_level") or "").strip()
    limit = int(arguments.get("limit") or 50)
    clauses = []
    if status:
        clauses.append(f"approval_status = {sql_literal(status)}")
    if board_lane:
        clauses.append(f"board_lane = {sql_literal(board_lane)}")
    if risk_level:
        clauses.append(f"risk_level = {sql_literal(risk_level)}")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result(
        {
            "summary": run_psql_json(
                """
                SELECT metric, value, interpretation
                FROM agent.v_approval_board_summary
                ORDER BY metric
                """
            ),
            "items": run_psql_json(
                f"""
                SELECT approval_id, task_id, approval_type, board_lane, title,
                       owner_agent, risk_level, approval_status, rationale,
                       decided_by, decided_at, created_at, task_status,
                       symbol, exchange, strategy_name, client_code,
                       account_code, book_key, linked_record_id, linked_source,
                       linked_status, gate_status, broker_order_allowed,
                       live_execution_allowed, open_risk_events, gate_check_count,
                       blocked_gate_count, recommended_next_action, latest_activity_at,
                       evidence
                FROM agent.v_approval_board_items
                {where}
                ORDER BY status_rank, risk_rank, latest_activity_at DESC
                LIMIT {limit}
                """
            ),
        }
    )


def committee_room(arguments: dict) -> dict:
    committee_lane = str(arguments.get("committee_lane") or "").strip()
    room_state = str(arguments.get("room_state") or "").strip()
    limit = int(arguments.get("limit") or 50)
    clauses = []
    if committee_lane:
        clauses.append(f"committee_lane = {sql_literal(committee_lane)}")
    if room_state:
        clauses.append(f"room_state = {sql_literal(room_state)}")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result(
        {
            "summary": run_psql_json(
                """
                SELECT metric, value, interpretation
                FROM agent.v_committee_room_summary
                ORDER BY metric
                """
            ),
            "items": run_psql_json(
                f"""
                SELECT committee_item_key, committee_lane, committee_scope,
                       source_view, source_id, review_key, symbol, exchange,
                       subject_name, title, review_status, decision_status,
                       recommended_decision, final_decision, proposed_mode,
                       risk_level, memo_status, memo_note_path, approval_id,
                       approval_status, decided_by, decided_at,
                       paper_monitor_allowed, capital_action_allowed,
                       live_execution_allowed, member_count, evidence_gap_count,
                       required_followup_count, evidence, decision_pending,
                       approval_pending, memo_missing, room_state,
                       recommended_next_action, latest_activity_at
                FROM agent.v_committee_room_items
                {where}
                ORDER BY priority_rank, risk_rank, latest_activity_at DESC
                LIMIT {limit}
                """
            ),
        }
    )


def open_committee_packet_tool(arguments: dict) -> dict:
    return tool_result(post_api_json("/api/committees/packets/open", arguments, timeout=90))


def submit_committee_position_tool(arguments: dict) -> dict:
    return tool_result(post_api_json("/api/committees/positions", arguments, timeout=90))


def add_committee_discussion_tool(arguments: dict) -> dict:
    return tool_result(post_api_json("/api/committees/discussion", arguments, timeout=90))


def synthesize_committee_session_tool(arguments: dict) -> dict:
    return tool_result(post_api_json("/api/committees/synthesize", arguments, timeout=90))


def record_committee_human_decision_tool(arguments: dict) -> dict:
    return tool_result(post_api_json("/api/committees/human-decision", arguments, timeout=90))


def create_committee_followup_tool(arguments: dict) -> dict:
    return tool_result(post_api_json("/api/committees/followups", arguments, timeout=90))


def employee_profiles(arguments: dict) -> dict:
    agent_name = str(arguments.get("agent_name") or "").strip()
    department = str(arguments.get("department") or "").strip()
    limit = int(arguments.get("limit") or 50)
    clauses = []
    if agent_name:
        clauses.append(f"agent_name = {sql_literal(agent_name)}")
    if department:
        clauses.append(f"department = {sql_literal(department)}")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result(
        {
            "summary": run_psql_json(
                """
                SELECT metric, value, interpretation
                FROM agent.v_employee_profile_summary
                ORDER BY metric
                """
            ),
            "profiles": run_psql_json(
                f"""
                SELECT agent_name, display_title, department, department_name,
                       role_scope, persona, operating_style, mental_models,
                       default_model_route, permission_level, guardrails,
                       escalation_rules, daily_cadence, cost_policy,
                       human_interface, reports_to_agent, hierarchy_level,
                       authority_scope, decision_rights, character_name,
                       avatar_role, visual_traits, voice_style, office_location,
                       color_token, primary_route, route_provider,
                       route_default_model, model_key, assigned_provider,
                       assigned_model, model_family, deployment_target,
                       estimated_disk_gb, model_status, fallback_route,
                       escalation_route, context_policy, model_cost_policy,
                       max_autonomous_cost_tier, assigned_skill_count,
                       active_skill_count, enabled_tool_count,
                       read_only_tool_count, write_or_browser_tool_count,
                       open_task_count, blocked_task_count, open_inbox_count,
                       urgent_inbox_count, unread_received_count,
                       worker_run_count, output_artifact_count,
                       pending_approval_count, live_state, current_work_title,
                       current_work_detail, workload_score,
                       latest_activity_at, skills, tools, open_tasks,
                       open_inbox_items, recent_messages, recent_outputs,
                       approvals, evidence
                FROM agent.v_employee_profiles_v1
                {where}
                ORDER BY role_rank, agent_name
                LIMIT {limit}
                """
            ),
        }
    )


def output_artifact_registry(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50, maximum=200)
    artifact_family = str(arguments.get("artifact_family") or "").strip()
    owner_agent = str(arguments.get("owner_agent") or "").strip()
    symbol = str(arguments.get("symbol") or "").strip().upper()
    query = str(arguments.get("query") or "").strip()
    gaps_only = bool(arguments.get("gaps_only") or False)
    clauses = []
    if artifact_family:
        clauses.append(f"artifact_family = {sql_literal(artifact_family)}")
    if owner_agent:
        clauses.append(f"owner_agent = {sql_literal(owner_agent)}")
    if symbol:
        clauses.append(f"upper(symbol) = {sql_literal(symbol)}")
    if query:
        pattern = "%" + query + "%"
        clauses.append(
            "("
            f"title ILIKE {sql_literal(pattern)} OR "
            f"summary ILIKE {sql_literal(pattern)} OR "
            f"owner_agent ILIKE {sql_literal(pattern)} OR "
            f"company_name ILIKE {sql_literal(pattern)} OR "
            f"strategy_name ILIKE {sql_literal(pattern)} OR "
            f"artifact_location ILIKE {sql_literal(pattern)}"
            ")"
        )
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result(
        {
            "summary": run_psql_json(
                """
                SELECT metric, value, first_seen_at, latest_seen_at,
                       obsidian_note_rows, local_file_rows, source_url_rows,
                       interpretation
                FROM agent.v_output_artifact_summary
                ORDER BY
                    CASE metric WHEN 'total_artifacts' THEN 0 ELSE 1 END,
                    metric
                """
            ),
            "artifacts": [] if gaps_only else run_psql_json(
                f"""
                SELECT artifact_key, artifact_family, artifact_type, title,
                       left(summary, 700) AS summary, owner_agent, owner_title,
                       department, skill_key, skill_name, task_id, approval_id,
                       symbol, company_name, strategy_name, note_path,
                       local_path, source_url, status, capital_action_allowed,
                       live_execution_allowed, latest_activity_at,
                       artifact_location, evidence
                FROM agent.v_output_artifact_registry_v2
                {where}
                ORDER BY latest_activity_at DESC NULLS LAST, artifact_family, title
                LIMIT {limit}
                """
            ),
            "gaps": run_psql_json(
                """
                SELECT gap_type, source_view, source_id, title, owner_agent,
                       status, created_at, updated_at, gap_reason
                FROM agent.v_output_artifact_gaps
                ORDER BY
                    CASE gap_type
                        WHEN 'worker_run_missing_note' THEN 1
                        WHEN 'long_term_committee_missing_memo' THEN 2
                        WHEN 'strategy_committee_missing_memo' THEN 3
                        ELSE 4
                    END,
                    updated_at DESC NULLS LAST,
                    created_at DESC NULLS LAST
                LIMIT 100
                """
            ),
        }
    )


def agent_comments(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50, maximum=200)
    target_kind = str(arguments.get("target_kind") or "").strip()
    target_ref = str(arguments.get("target_ref") or "").strip()
    from_agent = str(arguments.get("from_agent") or "").strip()
    to_agent = str(arguments.get("to_agent") or "").strip()
    status = str(arguments.get("status") or "").strip()
    needs_attention = arguments.get("needs_attention")
    clauses = []
    if target_kind:
        clauses.append(f"target_kind = {sql_literal(target_kind)}")
    if target_ref:
        clauses.append(f"target_ref = {sql_literal(target_ref)}")
    if from_agent:
        clauses.append(f"from_agent = {sql_literal(from_agent)}")
    if to_agent:
        clauses.append(f"to_agent = {sql_literal(to_agent)}")
    if status:
        clauses.append(f"status = {sql_literal(status)}")
    if needs_attention is not None:
        clauses.append(f"needs_attention = {str(bool(needs_attention)).lower()}")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result(
        {
            "summary": run_psql_json(
                """
                SELECT metric, value, first_seen_at, latest_seen_at, interpretation
                FROM agent.v_agent_comment_summary
                ORDER BY
                    CASE metric
                        WHEN 'total_comments' THEN 1
                        WHEN 'open_comments' THEN 2
                        WHEN 'high_priority_comments' THEN 3
                        WHEN 'commented_targets' THEN 4
                        ELSE 5
                    END
                """
            ),
            "target_summary": run_psql_json(
                """
                SELECT target_kind, target_ref, target_title, target_owner_agent,
                       target_status, target_location, comment_count,
                       open_comment_count, high_priority_open_count, latest_comment_at
                FROM agent.v_agent_comment_target_summary
                ORDER BY high_priority_open_count DESC, open_comment_count DESC,
                         latest_comment_at DESC NULLS LAST
                LIMIT 100
                """
            ),
            "comments": run_psql_json(
                f"""
                SELECT id, target_kind, target_ref, target_title, target_owner_agent,
                       target_status, target_location, parent_comment_id,
                       from_agent, from_agent_title, to_agent, to_agent_title,
                       comment_type, severity, status, body, evidence, metadata,
                       created_by, created_at, updated_at, resolved_by,
                       resolved_at, needs_attention
                FROM agent.v_agent_comments
                {where}
                ORDER BY
                    CASE WHEN needs_attention THEN 0 ELSE 1 END,
                    updated_at DESC,
                    id DESC
                LIMIT {limit}
                """
            ),
        }
    )


def create_agent_comment_tool(arguments: dict) -> dict:
    payload = {
        "target_kind": arguments.get("target_kind"),
        "target_ref": arguments.get("target_ref"),
        "target_title": arguments.get("target_title"),
        "parent_comment_id": arguments.get("parent_comment_id"),
        "from_agent": arguments.get("from_agent") or arguments.get("actor") or "Charlie Munger",
        "to_agent": arguments.get("to_agent"),
        "comment_type": arguments.get("comment_type") or "review_note",
        "severity": arguments.get("severity") or "normal",
        "status": arguments.get("status") or "open",
        "body": arguments.get("body"),
        "evidence": arguments.get("evidence") or [{"source": "AI OS MCP"}],
        "metadata": arguments.get("metadata") or {"mcp_tool": "ai_os_create_agent_comment"},
        "created_by": arguments.get("created_by") or arguments.get("actor") or arguments.get("from_agent") or "Jarvis",
    }
    return tool_result(post_api_json("/api/agents/comments", payload))


def resolve_agent_comment_tool(arguments: dict) -> dict:
    payload = {
        "comment_id": arguments.get("comment_id") or arguments.get("id"),
        "status": arguments.get("status") or "resolved",
        "actor": arguments.get("actor") or arguments.get("resolved_by") or "Jarvis",
        "resolution_note": arguments.get("resolution_note") or arguments.get("note") or "",
    }
    return tool_result(post_api_json("/api/agents/comments/resolve", payload))


def model_cost_ledger(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50, maximum=200)
    agent_name = str(arguments.get("agent_name") or "").strip()
    route_name = str(arguments.get("route_name") or "").strip()
    provider = str(arguments.get("provider") or "").strip().lower()
    cost_control_status = str(arguments.get("cost_control_status") or "").strip()
    clauses = []
    if agent_name:
        clauses.append(f"agent_name = {sql_literal(agent_name)}")
    if route_name:
        clauses.append(f"route_name = {sql_literal(route_name)}")
    if provider:
        clauses.append(f"provider = {sql_literal(provider)}")
    if cost_control_status:
        clauses.append(f"cost_control_status = {sql_literal(cost_control_status)}")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result(
        {
            "summary": run_psql_json(
                """
                SELECT metric, value, first_seen_at, latest_seen_at, interpretation
                FROM agent.v_model_cost_summary
                ORDER BY
                    CASE metric
                        WHEN 'total_usage_events' THEN 1
                        WHEN 'local_usage_events' THEN 2
                        WHEN 'cloud_usage_events' THEN 3
                        WHEN 'estimated_cost_today_usd' THEN 4
                        WHEN 'estimated_cost_month_usd' THEN 5
                        WHEN 'unapproved_cloud_events' THEN 6
                        WHEN 'rate_missing_events' THEN 7
                        WHEN 'agents_with_caps' THEN 8
                        ELSE 9
                    END
                """
            ),
            "caps": run_psql_json(
                """
                SELECT agent_name, display_title, department, primary_route,
                       daily_cap_usd, monthly_cap_usd, max_cost_tier,
                       cloud_requires_approval, autonomous_cloud_allowed,
                       events_today, events_month, cost_today_usd,
                       cost_month_usd, daily_remaining_usd,
                       monthly_remaining_usd, unapproved_cloud_events_today,
                       rate_missing_events_today, cap_status
                FROM agent.v_agent_model_cost_cap_status
                ORDER BY
                    CASE cap_status
                        WHEN 'daily_cap_breach' THEN 1
                        WHEN 'approval_required' THEN 2
                        WHEN 'rate_missing' THEN 3
                        WHEN 'near_daily_cap' THEN 4
                        ELSE 5
                    END,
                    events_today DESC,
                    agent_name
                LIMIT 100
                """
            ),
            "routes": run_psql_json(
                """
                SELECT route_name, task_class, provider, model_name, cost_tier,
                       usage_events, usage_events_today, total_tokens_est,
                       cost_usd, latest_event_ts, approval_required_events,
                       rate_missing_events
                FROM agent.v_model_route_cost_summary
                ORDER BY usage_events_today DESC, usage_events DESC, route_name
                LIMIT 100
                """
            ),
            "events": run_psql_json(
                f"""
                SELECT id, event_ts, source_kind, source_ref, agent_name,
                       route_name, provider, model_name, usage_kind,
                       model_status, total_tokens_est, actual_total_tokens,
                       estimated_cost_usd, actual_cost_usd, cost_tier,
                       estimate_method, approval_id, task_id, chat_turn_id,
                       is_cloud_usage, cost_control_status
                FROM agent.v_model_cost_ledger_events
                {where}
                ORDER BY event_ts DESC, id DESC
                LIMIT {limit}
                """
            ),
        }
    )


def record_model_usage_tool(arguments: dict) -> dict:
    payload = {
        "source_kind": arguments.get("source_kind") or "mcp_manual",
        "source_ref": arguments.get("source_ref"),
        "agent_name": arguments.get("agent_name"),
        "route_name": arguments.get("route_name"),
        "provider": arguments.get("provider") or arguments.get("model_provider"),
        "model_name": arguments.get("model_name"),
        "endpoint_key": arguments.get("endpoint_key"),
        "usage_kind": arguments.get("usage_kind") or "tool_call",
        "model_status": arguments.get("model_status") or "recorded",
        "prompt_tokens_est": arguments.get("prompt_tokens_est"),
        "completion_tokens_est": arguments.get("completion_tokens_est"),
        "total_tokens_est": arguments.get("total_tokens_est"),
        "actual_prompt_tokens": arguments.get("actual_prompt_tokens"),
        "actual_completion_tokens": arguments.get("actual_completion_tokens"),
        "actual_total_tokens": arguments.get("actual_total_tokens"),
        "estimated_cost_usd": arguments.get("estimated_cost_usd"),
        "actual_cost_usd": arguments.get("actual_cost_usd"),
        "cost_tier": arguments.get("cost_tier"),
        "estimate_method": arguments.get("estimate_method") or "mcp_record",
        "approval_id": arguments.get("approval_id"),
        "task_id": arguments.get("task_id"),
        "chat_turn_id": arguments.get("chat_turn_id"),
        "evidence": arguments.get("evidence") or [{"source": "AI OS MCP"}],
        "metadata": arguments.get("metadata") or {"mcp_tool": "ai_os_record_model_usage"},
        "actor": arguments.get("actor") or "AI Engineering",
    }
    return tool_result(post_api_json("/api/models/usage", payload))


def run_provider_readiness_sweep(arguments: dict) -> dict:
    payload = {
        "run_key": arguments.get("run_key") or arguments.get("runKey") or "provider_readiness_mcp",
        "actor": arguments.get("actor") or "Jarvis",
        "model_limit": arguments.get("model_limit") or arguments.get("modelLimit") or 50,
        "source_limit": arguments.get("source_limit") or arguments.get("sourceLimit") or 80,
        "models_only": bool(arguments.get("models_only") or arguments.get("modelsOnly") or False),
        "sources_only": bool(arguments.get("sources_only") or arguments.get("sourcesOnly") or False),
    }
    return tool_result(post_api_json("/api/providers/readiness/run", payload, timeout=280))


def provider_readiness_board(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50, maximum=200)
    readiness_status = str(arguments.get("readiness_status") or arguments.get("readinessStatus") or "").strip()
    provider_kind = str(arguments.get("provider_kind") or arguments.get("providerKind") or "").strip()
    clauses = []
    if readiness_status:
        clauses.append(f"readiness_status = {sql_literal(readiness_status)}")
    if provider_kind:
        clauses.append(f"provider_kind = {sql_literal(provider_kind)}")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result(
        {
            "summary": run_psql_json("SELECT metric, value, detail FROM core.v_provider_readiness_summary ORDER BY metric"),
            "board": run_psql_json(
                f"""
                SELECT provider_kind, provider_key, provider_name, provider,
                       subject_name, route_or_source, provider_type, status,
                       health_status, readiness_status, next_action,
                       assignable, owner_agent, last_checked_at, last_error
                FROM core.v_provider_readiness_board
                {where}
                ORDER BY id
                LIMIT {limit}
                """
            ),
            "runs": run_psql_json(
                f"""
                SELECT run_key, status, model_checks_run, source_checks_run,
                       ready_count, needs_check_count, blocked_count,
                       degraded_count, error_message, started_at, finished_at,
                       duration_ms
                FROM core.v_provider_readiness_runs
                ORDER BY started_at DESC, id DESC
                LIMIT {min(limit, 25)}
                """
            ),
        }
    )


def integration_plugin_gateway(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=100, maximum=200)
    plugin_kind = str(arguments.get("plugin_kind") or arguments.get("pluginKind") or "").strip()
    gateway_status = str(arguments.get("gateway_status") or arguments.get("gatewayStatus") or "").strip()
    query = str(arguments.get("query") or "").strip()
    clauses: list[str] = []
    if plugin_kind:
        clauses.append(f"plugin_kind = {sql_literal(plugin_kind)}")
    if gateway_status:
        clauses.append(f"gateway_status = {sql_literal(gateway_status)}")
    if query:
        clauses.append(
            "(display_name ILIKE " + sql_literal(f"%{query}%")
            + " OR plugin_key ILIKE " + sql_literal(f"%{query}%")
            + " OR provider ILIKE " + sql_literal(f"%{query}%") + ")"
        )
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result({
        "summary": run_psql_json(
            "SELECT metric, value, interpretation FROM core.v_integration_plugin_summary ORDER BY metric"
        ),
        "plugins": run_psql_json(f"""
            SELECT plugin_key, plugin_kind, target_key, display_name,
                   adapter_key, lifecycle_status, access_mode, capabilities,
                   enabled, approval_required, owner_agent, provider,
                   source_key, source_type, connector_type, model_name,
                   route_name, endpoint_type, health_status, freshness_status,
                   freshness_severity, provider_readiness_status,
                   provider_assignable, mapping_count, valid_mapping_count,
                   job_count, enabled_job_count, route_count, gateway_status,
                   next_required_action, last_checked_at, last_error, updated_at
            FROM core.v_integration_plugin_gateway
            {where}
            ORDER BY plugin_kind, gateway_status, display_name
            LIMIT {limit}
        """),
        "schema_mappings": run_psql_json(f"""
            SELECT mapping_key, plugin_key, plugin_name, dataset_key,
                   target_relation, target_relation_exists, primary_key_fields,
                   timestamp_field, status, validation_status,
                   validation_errors, last_validated_at, owner_agent, updated_at
            FROM core.v_integration_schema_mapping_board
            ORDER BY updated_at DESC LIMIT {min(limit, 120)}
        """),
        "jobs": run_psql_json(f"""
            SELECT job_key, plugin_key, plugin_name, job_name, job_type,
                   executor_key, schedule_cron, enabled, run_mode,
                   approval_required, last_run_status, last_started_at,
                   last_finished_at, last_rows_written, last_error, owner_agent
            FROM core.v_integration_job_board
            ORDER BY enabled DESC, plugin_name LIMIT {min(limit, 120)}
        """),
        "execution_control": run_psql_json("""
            SELECT global_execution_locked, broker_execution_policy,
                   limited_live_allowed, live_broker_writes_allowed, lock_reason
            FROM trading.v_execution_control_state LIMIT 1
        """),
    })


def market_data_readiness(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=25, maximum=100)
    return tool_result({
        "readiness": run_psql_json("""
            SELECT dataset_scope, row_count, symbol_count, first_ts, last_ts,
                   history_days, staleness_days, source_count,
                   readiness_status, next_required_action
            FROM market.v_strategy_market_data_readiness
            ORDER BY dataset_scope
        """),
        "contracts": run_psql_json("""
            SELECT dataset_key, source_key, target_relation, grain,
                   timezone_assumption, price_adjustment_status,
                   point_in_time_status, survivorship_status,
                   execution_allowed, research_allowed, limitations, owner_agent
            FROM market.dataset_contracts ORDER BY dataset_key
        """),
        "imports": run_psql_json(f"""
            SELECT run_key, batch_key, dataset_key, status, source_hash,
                   source_rows, valid_rows, rejected_rows, corrected_rows,
                   deduplicated_rows, rows_touched, rows_inserted,
                   warehouse_rows_after, quality_status, quality_summary,
                   started_at, finished_at
            FROM market.v_market_data_import_runs
            ORDER BY started_at DESC LIMIT {limit}
        """),
        "quality_checks": run_psql_json(f"""
            SELECT run_key, dataset_key, check_key, check_name, status,
                   observed_value, threshold_value, details, checked_at
            FROM market.v_market_data_quality_checks
            ORDER BY checked_at DESC LIMIT {min(limit * 6, 300)}
        """),
        "bias_controls": run_psql_json("""
            SELECT control_key, observed_rows, mapped_rows, verified_rows,
                   applied_rows, readiness_status, next_required_action
            FROM market.v_market_bias_control_readiness
            ORDER BY control_key
        """),
    })


def run_legacy_market_data_ingestion_tool(arguments: dict) -> dict:
    return tool_result(post_api_json("/api/integrations/jobs/run", {
        "job_key": "legacy_market_data_manual_ingestion",
        "actor": arguments.get("actor") or "Jarvis",
    }))


def upsert_integration_schema_mapping_tool(arguments: dict) -> dict:
    payload = {**arguments, "actor": arguments.get("actor") or "Data Steward"}
    return tool_result(post_api_json("/api/integrations/schema-mappings/upsert", payload))


def validate_integration_schema_mapping_tool(arguments: dict) -> dict:
    payload = {
        "mapping_key": required_text(arguments, "mapping_key"),
        "actor": arguments.get("actor") or "Data Quality Agent",
    }
    return tool_result(post_api_json("/api/integrations/schema-mappings/validate", payload))


def upsert_integration_job_tool(arguments: dict) -> dict:
    payload = {**arguments, "actor": arguments.get("actor") or "Data Engineering Agent"}
    return tool_result(post_api_json("/api/integrations/jobs/upsert", payload))


def run_integration_job_tool(arguments: dict) -> dict:
    payload = {
        "job_key": required_text(arguments, "job_key"),
        "actor": arguments.get("actor") or "Jarvis",
    }
    return tool_result(post_api_json("/api/integrations/jobs/run", payload, timeout=370))


def evaluate_provider_assignment_gate(arguments: dict) -> dict:
    payload = {
        "provider_key": required_text(arguments, "provider_key"),
        "provider_kind": arguments.get("provider_kind") or arguments.get("providerKind"),
        "requesting_agent": arguments.get("requesting_agent") or arguments.get("requestingAgent") or arguments.get("agent") or "Jarvis",
        "requested_use": arguments.get("requested_use") or arguments.get("requestedUse") or arguments.get("use_case") or arguments.get("useCase") or "provider assignment",
        "source_kind": arguments.get("source_kind") or arguments.get("sourceKind"),
        "source_ref": arguments.get("source_ref") or arguments.get("sourceRef"),
        "target_workspace": arguments.get("target_workspace") or arguments.get("targetWorkspace") or "system",
        "create_inbox_on_block": arguments.get("create_inbox_on_block", arguments.get("createInboxOnBlock", True)),
        "evidence": arguments.get("evidence") or [{"source": "AI OS MCP provider assignment gate"}],
        "metadata": arguments.get("metadata") or {"mcp_tool": "ai_os_evaluate_provider_assignment_gate"},
        "actor": arguments.get("actor") or arguments.get("requested_by") or arguments.get("requestedBy") or "Jarvis",
    }
    return tool_result(post_api_json("/api/providers/assignment-gate/evaluate", payload))


def provider_assignment_gates(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50, maximum=200)
    assignment_status = str(arguments.get("assignment_status") or arguments.get("assignmentStatus") or "").strip()
    provider_kind = str(arguments.get("provider_kind") or arguments.get("providerKind") or "").strip()
    clauses = []
    if assignment_status:
        clauses.append(f"assignment_status = {sql_literal(assignment_status)}")
    if provider_kind:
        clauses.append(f"provider_kind = {sql_literal(provider_kind)}")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result(
        {
            "gates": run_psql_json(
                f"""
                SELECT id, gate_key, provider_kind, provider_key, provider_name,
                       provider, subject_name, route_or_source, department_key,
                       department_name, policy_status, policy_rule_id,
                       policy_key, policy_reason, requested_by,
                       requesting_agent, requested_use, source_kind, source_ref,
                       target_workspace, readiness_status, provider_health_status,
                       assignment_status, assignment_allowed, assignable_snapshot,
                       block_reasons, next_action, inbox_item_id, inbox_status,
                       created_at, updated_at
                FROM core.v_provider_assignment_gate_checks
                {where}
                ORDER BY created_at DESC, id DESC
                LIMIT {limit}
                """
            )
        }
    )


def department_provider_policy_board(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=80, maximum=200)
    department_key = str(arguments.get("department_key") or arguments.get("departmentKey") or "").strip()
    policy_status = str(arguments.get("policy_status") or arguments.get("policyStatus") or "").strip()
    clauses = []
    if department_key:
        clauses.append(f"department_key = {sql_literal(department_key)}")
    if policy_status:
        clauses.append(f"policy_status = {sql_literal(policy_status)}")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result(
        {
            "policies": run_psql_json(
                f"""
                SELECT id, policy_key, department_key, department_name,
                       provider_kind, provider_key_pattern,
                       route_or_source_pattern, provider_pattern,
                       policy_status, priority, reason, guardrails,
                       status, updated_at
                FROM core.v_department_provider_policy_board
                {where}
                ORDER BY
                    CASE policy_status WHEN 'blocked' THEN 1 WHEN 'approval_required' THEN 2 ELSE 3 END,
                    department_key, priority, policy_key
                LIMIT {limit}
                """
            )
        }
    )


def evaluate_task_provider_gates(arguments: dict) -> dict:
    try:
        task_id = int(arguments.get("task_id") or arguments.get("taskId"))
    except (TypeError, ValueError) as exc:
        raise ValueError("task_id is required and must be an integer") from exc
    payload = {
        "task_id": task_id,
        "actor": arguments.get("actor") or "Jarvis",
        "context": arguments.get("context") or "mcp",
    }
    return tool_result(post_api_json("/api/tasks/provider-gates/evaluate", payload))


def task_provider_gate_status(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50, maximum=200)
    status = str(arguments.get("provider_gate_status") or arguments.get("providerGateStatus") or "").strip()
    owner_agent = str(arguments.get("owner_agent") or arguments.get("ownerAgent") or "").strip()
    clauses = []
    if status:
        clauses.append(f"provider_gate_status = {sql_literal(status)}")
    if owner_agent:
        clauses.append(f"owner_agent = {sql_literal(owner_agent)}")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result(
        {
            "tasks": run_psql_json(
                f"""
                SELECT task_id, title, owner_agent, task_status,
                       provider_gate_count, passed_provider_gates,
                       approval_required_provider_gates, blocked_provider_gates,
                       provider_gate_status, latest_provider_gate_at,
                       provider_gate_evidence
                FROM agent.v_task_provider_gate_status
                {where}
                ORDER BY latest_provider_gate_at DESC NULLS LAST, task_id DESC
                LIMIT {limit}
                """
            )
        }
    )


def orchestration_stack(arguments: dict) -> dict:
    return tool_result(
        run_psql_json(
            """
            SELECT agent_name, stack_role, department, role_scope, default_model_route,
                   default_tools, permission_level, guardrails
            FROM agent.v_orchestration_stack
            """
        )
    )


def control_plane_snapshot(arguments: dict) -> dict:
    return tool_result(
        {
            "metrics": run_psql_json("SELECT metric, value FROM core.v_control_plane_snapshot ORDER BY metric"),
            "modules": run_psql_json(
                """
                SELECT module_key, module_name, category, status, priority, owner_agent,
                       ui_workspace, warehouse_objects, mcp_tools, fincept_component, next_action
                FROM core.v_control_plane_overview
                """
            ),
            "data_sources": run_psql_json(
                """
                SELECT source_key, source_name, source_type, provider, connection_mode, status,
                       freshness_target_minutes, owner_agent, sensitivity, source_location, notes
                FROM core.v_data_source_registry
                """
            ),
            "strategies": run_psql_json(
                """
                SELECT strategy_key, strategy_name, strategy_family, timeframe, universe, status,
                       live_mode, data_dependencies, owner_agent, risk_level, paper_first,
                       approval_required, fincept_component, notes
                FROM strategy.v_strategy_registry
                """
            ),
            "workflows": run_psql_json(
                """
                SELECT workflow_key, workflow_name, workflow_type, owner_agent, trigger_type,
                       status, permission_level, input_sources, output_targets, approval_required,
                       schedule_hint, notes
                FROM agent.v_workflow_registry
                """
            ),
            "clients": run_psql_json(
                """
                SELECT client_code, display_name, risk_profile, active, account_count,
                       latest_position_count, latest_market_value, latest_position_at,
                       staged_holding_updates
                FROM portfolio.v_client_control_plane
                LIMIT 100
                """
            ),
            "fincept": run_psql_json(
                """
                SELECT source_system, component_name, version, git_commit, install_status,
                       build_status, runtime_mode, install_root, app_bundle_path, binary_path,
                       features_confirmed_by_build, known_runtime_notes, updated_at
                FROM core.v_fincept_install_status
                ORDER BY updated_at DESC
                """
            ),
        }
    )


def audit_mcp_call(
    *,
    tool_name: str,
    action_type: str,
    permission_level: str,
    actor: str,
    target_table: str | None = None,
    target_id: object | None = None,
    request_payload: object | None = None,
    result_payload: object | None = None,
    status: str = "success",
    error_message: str | None = None,
) -> None:
    run_psql_json_statement(
        f"""
        WITH inserted AS (
            INSERT INTO agent.mcp_audit_log (
                tool_name, action_type, permission_level, actor, status, target_table,
                target_id, request_payload, result_payload, error_message
            )
            VALUES (
                {sql_literal(tool_name)}, {sql_literal(action_type)}, {sql_literal(permission_level)},
                {sql_literal(actor)}, {sql_literal(status)}, {sql_literal(target_table)},
                {sql_literal(target_id)}, {sql_jsonb(request_payload)}, {sql_jsonb(result_payload)},
                {sql_literal(error_message)}
            )
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text
        FROM inserted
        """
    )


def mcp_capabilities(arguments: dict) -> dict:
    return tool_result(
        {
            "tools": run_psql_json(
                """
                SELECT tool_name, tool_type, owning_agent, permission_level, enabled, description, config
                FROM agent.v_mcp_capability_matrix
                """
            ),
            "mcp_tools": run_psql_json(
                """
                SELECT tool_name, tool_type, owning_agent, permission_level, enabled, description, config
                FROM agent.v_mcp_capability_matrix
                WHERE tool_name LIKE 'ai_os_%'
                """
            ),
            "internal_capabilities": run_psql_json(
                """
                SELECT tool_name, tool_type, owning_agent, permission_level, enabled, description, config
                FROM agent.v_mcp_capability_matrix
                WHERE tool_name NOT LIKE 'ai_os_%'
                """
            ),
            "permission_summary": run_psql_json(
                """
                SELECT permission_level, count(*) AS tools
                FROM agent.v_mcp_capability_matrix
                WHERE tool_name LIKE 'ai_os_%'
                GROUP BY permission_level
                ORDER BY permission_level
                """
            ),
            "guardrails": {
                "broker_order_placement": "disabled",
                "external_posting": "disabled",
                "browser_control": "logged through browser run tools; source artifacts must be recorded",
                "obsidian_writeback": "allowed only inside structured ai memory folders",
            },
        }
    )


def mcp_audit_log(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50, maximum=200)
    tool_name = str(arguments.get("tool_name") or "").strip()
    clauses = []
    if tool_name:
        clauses.append(f"tool_name = {sql_literal(tool_name)}")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result(
        run_psql_json(
            f"""
            SELECT id, tool_name, action_type, permission_level, actor, status,
                   target_table, target_id, error_message, created_at
            FROM agent.v_recent_mcp_audit
            {where}
            LIMIT {limit}
            """
        )
    )


def list_inbox(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50, maximum=200)
    status = str(arguments.get("status") or "").strip()
    workspace = str(arguments.get("target_workspace") or "").strip()
    clauses = []
    if status:
        clauses.append(f"status = {sql_literal(status)}")
    if workspace:
        clauses.append(f"target_workspace = {sql_literal(workspace)}")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result(
        run_psql_json(
            f"""
            SELECT id, task_id, title, owner_agent, status, priority,
                   recommended_action, evidence, target_workspace, created_at, updated_at
            FROM agent.inbox_items
            {where}
            ORDER BY
                CASE priority
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    ELSE 4
                END,
                updated_at DESC
            LIMIT {limit}
            """
        )
    )


def research_factory_queue_summary(arguments: dict) -> dict:
    return tool_result(
        run_psql_json(
            """
            SELECT queue_key, queue_name, owner_agent, total_rows, open_rows,
                   blocked_or_error_rows, latest_activity_at, next_action
            FROM research.v_research_factory_queue_summary
            ORDER BY
                CASE WHEN blocked_or_error_rows > 0 THEN 1 WHEN open_rows > 0 THEN 2 ELSE 3 END,
                latest_activity_at DESC NULLS LAST,
                queue_name
            """
        )
    )


def triage_agent_message(arguments: dict) -> dict:
    try:
        message_id = int(arguments.get("message_id") or arguments.get("id"))
    except (TypeError, ValueError) as exc:
        raise ValueError("message_id is required and must be an integer") from exc
    action = str(arguments.get("action") or "acknowledge").strip().lower()
    if action not in {"mark_read", "acknowledge", "create_task"}:
        raise ValueError("action must be mark_read, acknowledge, or create_task")
    actor = str(arguments.get("actor") or "Jarvis").strip()
    target_workspace = str(arguments.get("target_workspace") or "command").strip()
    task_title = str(arguments.get("task_title") or "").strip()
    task_objective = str(arguments.get("task_objective") or "").strip()
    recommended_action = str(arguments.get("recommended_action") or "Review message and complete the handoff with evidence.").strip()
    priority = str(arguments.get("priority") or "").strip().lower()
    if priority and priority not in {"low", "normal", "medium", "high", "critical"}:
        raise ValueError("priority must be low, normal, medium, high, or critical")

    return tool_result(
        run_psql_json_statement(
            f"""
            WITH selected AS (
                SELECT *
                FROM agent.agent_messages
                WHERE id = {message_id}
                FOR UPDATE
            ),
            task_insert AS (
                INSERT INTO agent.tasks (
                    title, objective, owner_agent, status, priority, approval_required,
                    source_kind, source_ref, output_format, evidence
                )
                SELECT
                    coalesce(nullif({sql_literal(task_title)}, ''), 'Message handoff: ' || selected.subject),
                    coalesce(nullif({sql_literal(task_objective)}, ''), selected.body),
                    coalesce(selected.to_agent, {sql_literal(actor)}),
                    'queued',
                    coalesce(nullif({sql_literal(priority)}, ''), CASE selected.priority WHEN 'critical' THEN 'critical' WHEN 'high' THEN 'high' ELSE 'normal' END),
                    false,
                    'agent_message',
                    selected.id::TEXT,
                    'agent_task',
                    jsonb_build_array(jsonb_build_object(
                        'source_table', 'agent.agent_messages',
                        'message_id', selected.id,
                        'thread_key', selected.thread_key,
                        'from_agent', selected.from_agent,
                        'to_agent', selected.to_agent,
                        'subject', selected.subject
                    ))
                FROM selected
                WHERE {sql_literal(action)} = 'create_task'
                  AND selected.generated_task_id IS NULL
                RETURNING id
            ),
            task_link AS (
                SELECT
                    selected.id AS message_id,
                    coalesce(selected.generated_task_id, (SELECT id FROM task_insert LIMIT 1)) AS task_id
                FROM selected
            ),
            inbox_insert AS (
                INSERT INTO agent.inbox_items (
                    task_id, title, owner_agent, status, priority, recommended_action, evidence, target_workspace
                )
                SELECT
                    task_link.task_id,
                    coalesce(nullif({sql_literal(task_title)}, ''), 'Message handoff: ' || selected.subject),
                    coalesce(selected.to_agent, {sql_literal(actor)}),
                    'queued',
                    coalesce(nullif({sql_literal(priority)}, ''), CASE selected.priority WHEN 'critical' THEN 'critical' WHEN 'high' THEN 'high' ELSE 'normal' END),
                    {sql_literal(recommended_action)},
                    jsonb_build_array(jsonb_build_object(
                        'source_table', 'agent.agent_messages',
                        'message_id', selected.id,
                        'thread_key', selected.thread_key,
                        'from_agent', selected.from_agent,
                        'to_agent', selected.to_agent,
                        'subject', selected.subject
                    )),
                    {sql_literal(target_workspace)}
                FROM selected
                JOIN task_link ON task_link.message_id = selected.id
                WHERE {sql_literal(action)} = 'create_task'
                  AND task_link.task_id IS NOT NULL
                  AND selected.generated_inbox_id IS NULL
                RETURNING id
            ),
            updated AS (
                UPDATE agent.agent_messages msg
                SET
                    status = CASE
                        WHEN {sql_literal(action)} = 'mark_read' THEN 'read'
                        WHEN {sql_literal(action)} = 'acknowledge' THEN 'acknowledged'
                        WHEN {sql_literal(action)} = 'create_task' THEN 'routed_to_task'
                        ELSE msg.status
                    END,
                    read_at = coalesce(msg.read_at, now()),
                    processing_status = CASE
                        WHEN {sql_literal(action)} = 'mark_read' THEN 'read'
                        WHEN {sql_literal(action)} = 'acknowledge' THEN 'acknowledged'
                        WHEN {sql_literal(action)} = 'create_task' THEN 'routed_to_task'
                        ELSE msg.processing_status
                    END,
                    processed_at = CASE WHEN {sql_literal(action)} = 'create_task' THEN now() ELSE msg.processed_at END,
                    generated_task_id = coalesce(msg.generated_task_id, (SELECT task_id FROM task_link LIMIT 1)),
                    generated_inbox_id = coalesce(msg.generated_inbox_id, (SELECT id FROM inbox_insert LIMIT 1)),
                    metadata = msg.metadata || jsonb_build_object(
                        'last_triage_action', {sql_literal(action)},
                        'last_triage_actor', {sql_literal(actor)},
                        'last_triage_at', now()
                    )
                WHERE msg.id = {message_id}
                RETURNING msg.id, msg.thread_key, msg.from_agent, msg.to_agent,
                          msg.subject, msg.priority, msg.status, msg.processing_status,
                          msg.generated_task_id, msg.generated_inbox_id, msg.read_at,
                          msg.processed_at, msg.metadata
            )
            SELECT coalesce(json_agg(row_to_json(updated)), '[]'::json)::text
            FROM updated
            """
        )
    )


def create_task(arguments: dict) -> dict:
    title = required_text(arguments, "title")
    objective = required_text(arguments, "objective")
    owner_agent = str(arguments.get("owner_agent") or "Jarvis").strip()
    priority = str(arguments.get("priority") or "normal").strip()
    approval_required = bool(arguments.get("approval_required", False))
    source_kind = str(arguments.get("source_kind") or "").strip() or None
    source_ref = str(arguments.get("source_ref") or "").strip() or None
    output_format = str(arguments.get("output_format") or "").strip() or None
    evidence = arguments.get("evidence") or []
    create_inbox = bool(arguments.get("create_inbox", True))
    recommended_action = str(arguments.get("recommended_action") or "Review and execute the task with evidence.").strip()
    target_workspace = str(arguments.get("target_workspace") or "command").strip()
    actor = str(arguments.get("actor") or "Jarvis").strip()

    rows = run_psql_json_statement(
        f"""
        WITH task_insert AS (
            INSERT INTO agent.tasks (
                title, objective, owner_agent, status, priority, approval_required,
                source_kind, source_ref, output_format, evidence
            )
            VALUES (
                {sql_literal(title)}, {sql_literal(objective)}, {sql_literal(owner_agent)},
                'queued', {sql_literal(priority)}, {str(approval_required).lower()},
                {sql_literal(source_kind)}, {sql_literal(source_ref)}, {sql_literal(output_format)},
                {sql_jsonb(evidence)}
            )
            RETURNING id, title, objective, owner_agent, status, priority, approval_required
        ),
        inbox_insert AS (
            INSERT INTO agent.inbox_items (
                task_id, title, owner_agent, status, priority, recommended_action, evidence, target_workspace
            )
            SELECT id, title, owner_agent, 'queued', priority, {sql_literal(recommended_action)},
                   {sql_jsonb(evidence)}, {sql_literal(target_workspace)}
            FROM task_insert
            WHERE {str(create_inbox).lower()}
            RETURNING id
        ),
        result_rows AS (
            SELECT task_insert.*, (SELECT id FROM inbox_insert LIMIT 1) AS inbox_item_id
            FROM task_insert
        )
        SELECT coalesce(json_agg(row_to_json(result_rows)), '[]'::json)::text
        FROM result_rows
        """
    )
    result = rows[0] if rows else {"error": "task not created"}
    audit_mcp_call(
        tool_name="ai_os_create_task",
        action_type="create_task",
        permission_level="write_with_approval",
        actor=actor,
        target_table="agent.tasks",
        target_id=result.get("id") if isinstance(result, dict) else None,
        request_payload=arguments,
        result_payload=result,
    )
    return tool_result(result)


def update_task_status(arguments: dict) -> dict:
    try:
        task_id = int(arguments.get("task_id"))
    except (TypeError, ValueError) as exc:
        raise ValueError("task_id is required and must be an integer") from exc
    status = required_text(arguments, "status")
    output_note_path = str(arguments.get("output_note_path") or "").strip() or None
    evidence = arguments.get("evidence") or []
    actor = str(arguments.get("actor") or "Jarvis").strip()

    rows = run_psql_json_statement(
        f"""
        WITH updated AS (
            UPDATE agent.tasks
            SET status = {sql_literal(status)},
                output_note_path = coalesce({sql_literal(output_note_path)}, output_note_path),
                evidence = evidence || {sql_jsonb(evidence)},
                updated_at = now()
            WHERE id = {task_id}
            RETURNING id, title, owner_agent, status, priority, output_note_path, evidence, updated_at
        )
        SELECT coalesce(json_agg(row_to_json(updated)), '[]'::json)::text
        FROM updated
        """
    )
    result = rows[0] if rows else {"error": "task not found", "task_id": task_id}
    audit_mcp_call(
        tool_name="ai_os_update_task_status",
        action_type="update_task",
        permission_level="write_with_approval",
        actor=actor,
        target_table="agent.tasks",
        target_id=task_id,
        request_payload=arguments,
        result_payload=result,
        status="success" if rows else "not_found",
    )
    return tool_result(result)


def update_inbox_status(arguments: dict) -> dict:
    try:
        inbox_id = int(arguments.get("inbox_id"))
    except (TypeError, ValueError) as exc:
        raise ValueError("inbox_id is required and must be an integer") from exc
    action = str(arguments.get("action") or "").strip().lower()
    legacy_status = str(arguments.get("status") or "").strip().lower()
    if not action and legacy_status:
        action = {
            "done": "resolve", "resolved": "resolve", "completed": "resolve",
            "blocked": "block", "queued": "reopen", "new": "reopen",
            "in_progress": "claim", "running": "claim",
        }.get(legacy_status, "")
    if action not in {"claim", "reassign", "resolve", "block", "reopen"}:
        raise ValueError("action must be claim, reassign, resolve, block, or reopen")
    new_owner = str(arguments.get("owner_agent") or "").strip()
    if action == "reassign" and not new_owner:
        raise ValueError("owner_agent is required for reassign")
    if new_owner and not run_psql_json(
        f"SELECT agent_name FROM agent.profiles WHERE status='active' AND agent_name={sql_literal(new_owner)} LIMIT 1"
    ):
        raise ValueError(f"active agent not found: {new_owner}")
    note = str(arguments.get("resolution_note") or arguments.get("recommended_action") or "").strip()
    actor = str(arguments.get("actor") or "Jarvis").strip()
    status = {"claim": "in_progress", "reassign": "queued", "resolve": "done", "block": "blocked", "reopen": "queued"}[action]
    task_status = {"claim": "in_progress", "reassign": "queued", "resolve": "completed", "block": "blocked", "reopen": "queued"}[action]
    audit_evidence = [{"source": "ai_os_mcp.update_inbox_status", "action": action, "actor": actor, "owner_agent": new_owner or None, "note": note or None}]
    rows = run_psql_json_statement(
        f"""
        WITH updated AS (
            UPDATE agent.inbox_items item
            SET status = {sql_literal(status)},
                owner_agent = CASE WHEN {sql_literal(action)}='reassign' THEN {sql_literal(new_owner)} ELSE item.owner_agent END,
                claimed_by = CASE WHEN {sql_literal(action)}='claim' THEN {sql_literal(actor)} WHEN {sql_literal(action)} IN ('reassign','reopen') THEN NULL ELSE item.claimed_by END,
                claimed_at = CASE WHEN {sql_literal(action)}='claim' THEN now() WHEN {sql_literal(action)} IN ('reassign','reopen') THEN NULL ELSE item.claimed_at END,
                resolved_by = CASE WHEN {sql_literal(action)}='resolve' THEN {sql_literal(actor)} WHEN {sql_literal(action)}='reopen' THEN NULL ELSE item.resolved_by END,
                resolved_at = CASE WHEN {sql_literal(action)}='resolve' THEN now() WHEN {sql_literal(action)}='reopen' THEN NULL ELSE item.resolved_at END,
                resolution_note = CASE WHEN {sql_literal(action)} IN ('resolve','block') THEN {sql_literal(note or action)} WHEN {sql_literal(action)}='reopen' THEN NULL ELSE item.resolution_note END,
                recommended_action = CASE
                    WHEN {sql_literal(action)}='resolve' THEN 'Resolved; inspect linked evidence before reopening.'
                    WHEN {sql_literal(action)}='block' THEN 'Blocked pending evidence or dependency resolution.'
                    WHEN {sql_literal(action)}='reassign' THEN 'Reassigned to the accountable specialist.'
                    WHEN {sql_literal(action)}='claim' THEN 'Claimed for active work.'
                    ELSE 'Reopened for accountable review.' END,
                evidence = coalesce(item.evidence,'[]'::jsonb) || {sql_jsonb(audit_evidence)},
                updated_at = now()
            WHERE id = {inbox_id}
            RETURNING item.*
        ), updated_task AS (
            UPDATE agent.tasks task
            SET status={sql_literal(task_status)},
                owner_agent=CASE WHEN {sql_literal(action)}='reassign' THEN {sql_literal(new_owner)} ELSE task.owner_agent END,
                evidence=coalesce(task.evidence,'[]'::jsonb) || {sql_jsonb(audit_evidence)},
                updated_at=now()
            FROM updated item WHERE task.id=item.task_id
            RETURNING task.id,task.owner_agent,task.status,task.updated_at
        )
        SELECT coalesce(json_agg(row_to_json(result_rows)), '[]'::json)::text
        FROM (SELECT item.*,(SELECT row_to_json(task) FROM updated_task task) AS linked_task FROM updated item) result_rows
        """
    )
    result = rows[0] if rows else {"error": "inbox item not found", "inbox_id": inbox_id}
    audit_mcp_call(
        tool_name="ai_os_update_inbox_status",
        action_type=f"inbox_{action}",
        permission_level="write_with_approval",
        actor=actor,
        target_table="agent.inbox_items",
        target_id=inbox_id,
        request_payload=arguments,
        result_payload=result,
        status="success" if rows else "not_found",
    )
    return tool_result(result)


def create_approval(arguments: dict) -> dict:
    title = required_text(arguments, "title")
    approval_type = str(arguments.get("approval_type") or "system_change").strip()
    owner_agent = str(arguments.get("owner_agent") or "Risk Agent").strip()
    risk_level = str(arguments.get("risk_level") or "medium").strip()
    rationale = str(arguments.get("rationale") or "").strip() or None
    requested_action = arguments.get("requested_action") or {}
    actor = str(arguments.get("actor") or "Jarvis").strip()
    task_id_value = arguments.get("task_id")
    task_id = "NULL"
    if task_id_value not in (None, ""):
        task_id = str(int(task_id_value))
    rows = run_psql_json_statement(
        f"""
        WITH inserted AS (
            INSERT INTO agent.approvals (
                task_id, approval_type, title, owner_agent, risk_level,
                status, requested_action, rationale
            )
            VALUES (
                {task_id}, {sql_literal(approval_type)}, {sql_literal(title)},
                {sql_literal(owner_agent)}, {sql_literal(risk_level)}, 'pending',
                {sql_jsonb(requested_action)}, {sql_literal(rationale)}
            )
            RETURNING id, task_id, approval_type, title, owner_agent, risk_level, status, requested_action, rationale, created_at
        )
        SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text
        FROM inserted
        """
    )
    result = rows[0] if rows else {"error": "approval not created"}
    audit_mcp_call(
        tool_name="ai_os_create_approval",
        action_type="create_approval",
        permission_level="write_with_approval",
        actor=actor,
        target_table="agent.approvals",
        target_id=result.get("id") if isinstance(result, dict) else None,
        request_payload=arguments,
        result_payload=result,
    )
    return tool_result(result)


def decide_approval(arguments: dict) -> dict:
    try:
        approval_id = int(arguments.get("approval_id"))
    except (TypeError, ValueError) as exc:
        raise ValueError("approval_id is required and must be an integer") from exc
    decision = required_text(arguments, "decision")
    if decision not in {"approved", "rejected"}:
        raise ValueError("decision must be approved or rejected")
    decided_by = str(arguments.get("decided_by") or "Devarsh").strip()
    rationale = str(arguments.get("rationale") or "").strip() or None
    actor = str(arguments.get("actor") or decided_by).strip()
    rows = run_psql_json_statement(
        f"""
        WITH updated AS (
            UPDATE agent.approvals
            SET status = {sql_literal(decision)},
                decided_by = {sql_literal(decided_by)},
                decided_at = now(),
                rationale = coalesce({sql_literal(rationale)}, rationale)
            WHERE id = {approval_id}
              AND status = 'pending'
            RETURNING id, task_id, approval_type, title, owner_agent, risk_level, status, decided_by, decided_at, rationale
        )
        SELECT coalesce(json_agg(row_to_json(updated)), '[]'::json)::text
        FROM updated
        """
    )
    result = rows[0] if rows else {"error": "pending approval not found", "approval_id": approval_id}
    audit_mcp_call(
        tool_name="ai_os_decide_approval",
        action_type="decide_approval",
        permission_level="write_with_approval",
        actor=actor,
        target_table="agent.approvals",
        target_id=approval_id,
        request_payload=arguments,
        result_payload=result,
        status="success" if rows else "not_found",
    )
    return tool_result(result)


def create_research_idea(arguments: dict) -> dict:
    title = required_text(arguments, "title")
    idea_type = str(arguments.get("idea_type") or "research_note").strip()
    symbols = arguments.get("symbols") or []
    source_kind = str(arguments.get("source_kind") or "").strip() or None
    source_ref = str(arguments.get("source_ref") or "").strip() or None
    thesis = str(arguments.get("thesis") or "").strip() or None
    catalyst = str(arguments.get("catalyst") or "").strip() or None
    expected_timeframe = str(arguments.get("expected_timeframe") or "").strip() or None
    opportunity_score = sql_numeric(arguments.get("opportunity_score"), field_name="opportunity_score")
    risk_score = sql_numeric(arguments.get("risk_score"), field_name="risk_score")
    owner_agent = str(arguments.get("owner_agent") or "Research Lead").strip()
    evidence = arguments.get("evidence") or []
    actor = str(arguments.get("actor") or owner_agent).strip()
    rows = run_psql_json_statement(
        f"""
        WITH inserted AS (
            INSERT INTO research.ideas (
                idea_type, title, symbols, source_kind, source_ref, thesis, catalyst,
                expected_timeframe, opportunity_score, risk_score, status, owner_agent, evidence
            )
            VALUES (
                {sql_literal(idea_type)}, {sql_literal(title)}, {sql_text_array(symbols)},
                {sql_literal(source_kind)}, {sql_literal(source_ref)}, {sql_literal(thesis)},
                {sql_literal(catalyst)}, {sql_literal(expected_timeframe)}, {opportunity_score},
                {risk_score}, 'captured', {sql_literal(owner_agent)}, {sql_jsonb(evidence)}
            )
            RETURNING id, idea_type, title, symbols, source_kind, source_ref, opportunity_score, risk_score, status, owner_agent, created_at
        )
        SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text
        FROM inserted
        """
    )
    result = rows[0] if rows else {"error": "idea not created"}
    audit_mcp_call(
        tool_name="ai_os_create_research_idea",
        action_type="create_research_idea",
        permission_level="write_with_approval",
        actor=actor,
        target_table="research.ideas",
        target_id=result.get("id") if isinstance(result, dict) else None,
        request_payload=arguments,
        result_payload=result,
    )
    return tool_result(result)


def record_raw_artifact(arguments: dict) -> dict:
    artifact_type = str(arguments.get("artifact_type") or "browser_capture").strip()
    title = required_text(arguments, "title")
    source_url = str(arguments.get("source_url") or "").strip() or None
    local_path = str(arguments.get("local_path") or "").strip() or None
    mime_type = str(arguments.get("mime_type") or "text/plain").strip()
    sensitivity = str(arguments.get("sensitivity") or "private").strip()
    content_text = str(arguments.get("content_text") or "")
    content_hash = str(arguments.get("content_hash") or "").strip() or None
    if content_text and not content_hash:
        import hashlib
        content_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()
    metadata = arguments.get("metadata") or {}
    if content_text:
        metadata = {**metadata, "text_preview": content_text[:1200]}
    source_system_name = str(arguments.get("source_system_name") or "browser mcp capture").strip()
    source_type = str(arguments.get("source_type") or "mcp_artifact").strip()
    actor = str(arguments.get("actor") or "Data Steward").strip()
    rows = run_psql_json_statement(
        f"""
        WITH source_system AS (
            INSERT INTO core.source_systems (name, source_type, location, sensitivity, status, notes)
            VALUES (
                {sql_literal(source_system_name)}, {sql_literal(source_type)},
                coalesce({sql_literal(source_url)}, {sql_literal(local_path)}, 'mcp-artifact'),
                {sql_literal(sensitivity)}, 'active', 'Created or touched by MCP artifact recorder.'
            )
            ON CONFLICT (name) DO UPDATE SET
                source_type = EXCLUDED.source_type,
                location = EXCLUDED.location,
                sensitivity = EXCLUDED.sensitivity,
                status = EXCLUDED.status
            RETURNING id
        ),
        inserted AS (
            INSERT INTO core.raw_artifacts (
                source_system_id, artifact_type, title, source_url, local_path,
                content_hash, mime_type, sensitivity, metadata
            )
            SELECT id, {sql_literal(artifact_type)}, {sql_literal(title)}, {sql_literal(source_url)},
                   {sql_literal(local_path)}, {sql_literal(content_hash)}, {sql_literal(mime_type)},
                   {sql_literal(sensitivity)}, {sql_jsonb(metadata)}
            FROM source_system
            RETURNING id, artifact_type, title, source_url, local_path, content_hash, mime_type, sensitivity, captured_at
        )
        SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text
        FROM inserted
        """
    )
    result = rows[0] if rows else {"error": "artifact not recorded"}
    audit_mcp_call(
        tool_name="ai_os_record_raw_artifact",
        action_type="record_raw_artifact",
        permission_level="write_db_manual_only",
        actor=actor,
        target_table="core.raw_artifacts",
        target_id=result.get("id") if isinstance(result, dict) else None,
        request_payload={k: v for k, v in arguments.items() if k != "content_text"},
        result_payload=result,
    )
    return tool_result(result)


NOTE_FOLDERS = {
    "agent_outputs": "ai memory/00 AI OS/Agent Outputs",
    "architecture": "ai memory/00 AI OS/Architecture",
    "research": "ai memory/01 Research/MCP Outputs",
    "workflows": "ai memory/00 AI OS/Workflows",
    "reports": "ai memory/00 AI OS/Reports",
    "journal": "ai memory/09 Journal/MCP Outputs",
}


def slugify_title(title: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-").lower()
    return slug[:72] or "note"


def write_obsidian_note(arguments: dict) -> dict:
    title = required_text(arguments, "title")
    body = required_text(arguments, "body")
    folder_key = str(arguments.get("folder") or "agent_outputs").strip()
    if folder_key not in NOTE_FOLDERS:
        raise ValueError(f"folder must be one of: {', '.join(sorted(NOTE_FOLDERS))}")
    tags = arguments.get("tags") or ["ai-os", "mcp-writeback"]
    source_refs = arguments.get("source_refs") or []
    actor = str(arguments.get("actor") or "Knowledge Librarian").strip()
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    filename_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = VAULT_ROOT / NOTE_FOLDERS[folder_key]
    folder.mkdir(parents=True, exist_ok=True)
    note_path = folder / f"{filename_stamp}-{slugify_title(title)}.md"
    tag_lines = "\n".join(f"  - {str(tag)}" for tag in tags)
    source_lines = "\n".join(f"  - {str(ref)}" for ref in source_refs)
    content = (
        "---\n"
        "type: mcp_writeback\n"
        f"created: {created_at}\n"
        f"actor: {actor}\n"
        "tags:\n"
        f"{tag_lines or '  - ai-os'}\n"
        "source_refs:\n"
        f"{source_lines or '  - mcp'}\n"
        "---\n\n"
        f"# {title}\n\n"
        f"{body.rstrip()}\n"
    )
    note_path.write_text(content, encoding="utf-8")
    reindex = run_command([str(RUNTIME_ROOT / "scripts" / "index_obsidian_vault.py")])
    relative_path = str(note_path.relative_to(VAULT_ROOT))
    result = {
        "note_path": relative_path,
        "absolute_path": str(note_path),
        "bytes": note_path.stat().st_size,
        "reindex_returncode": reindex["returncode"],
        "reindex_stdout": reindex["stdout"],
        "reindex_stderr": reindex["stderr"],
    }
    audit_mcp_call(
        tool_name="ai_os_write_obsidian_note",
        action_type="write_obsidian_note",
        permission_level="write_with_approval",
        actor=actor,
        target_table="knowledge.obsidian_notes",
        target_id=relative_path,
        request_payload={k: v for k, v in arguments.items() if k != "body"},
        result_payload=result,
    )
    return tool_result(result)


def start_browser_run(arguments: dict) -> dict:
    run_type = str(arguments.get("run_type") or "browser_research").strip()
    target_url = required_text(arguments, "target_url")
    status = str(arguments.get("status") or "queued").strip()
    notes = str(arguments.get("notes") or "").strip() or None
    metadata = arguments.get("metadata") or {}
    actor = str(arguments.get("actor") or "Browser Research Runner").strip()
    source_kind = str(arguments.get("source_kind") or "").strip() or None
    source_ref = str(arguments.get("source_ref") or "").strip() or None
    task_id_value = arguments.get("task_id")
    task_id = "NULL"
    if task_id_value not in (None, ""):
        task_id = str(int(task_id_value))
    rows = run_psql_json_statement(
        f"""
        WITH inserted AS (
            INSERT INTO ops.browser_runs (
                task_id, run_type, target_url, status, actor, started_at,
                notes, metadata, source_kind, source_ref
            )
            VALUES (
                {task_id}, {sql_literal(run_type)}, {sql_literal(target_url)},
                {sql_literal(status)}, {sql_literal(actor)},
                CASE WHEN {sql_literal(status)} IN ('running','done','failed') THEN now() ELSE NULL END,
                {sql_literal(notes)}, {sql_jsonb(metadata)}, {sql_literal(source_kind)}, {sql_literal(source_ref)}
            )
            RETURNING id, task_id, run_type, target_url, status, actor, source_kind, source_ref, started_at, notes, metadata
        )
        SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text
        FROM inserted
        """
    )
    result = rows[0] if rows else {"error": "browser run not created"}
    audit_mcp_call(
        tool_name="ai_os_start_browser_run",
        action_type="start_browser_run",
        permission_level="browser_read",
        actor=actor,
        target_table="ops.browser_runs",
        target_id=result.get("id") if isinstance(result, dict) else None,
        request_payload=arguments,
        result_payload=result,
    )
    return tool_result(result)


def complete_browser_run(arguments: dict) -> dict:
    try:
        browser_run_id = int(arguments.get("browser_run_id"))
    except (TypeError, ValueError) as exc:
        raise ValueError("browser_run_id is required and must be an integer") from exc
    status = str(arguments.get("status") or "done").strip()
    actor = str(arguments.get("actor") or "Browser Research Runner").strip()
    page_title = str(arguments.get("page_title") or "").strip() or None
    extracted_text_preview = str(arguments.get("extracted_text_preview") or "").strip() or None
    screenshot_path = str(arguments.get("screenshot_path") or "").strip() or None
    notes = str(arguments.get("notes") or "").strip() or None
    metadata = arguments.get("metadata") or {}
    extracted_artifact_id = arguments.get("extracted_artifact_id")
    artifact_id = "NULL"
    if extracted_artifact_id not in (None, ""):
        artifact_id = str(int(extracted_artifact_id))
    rows = run_psql_json_statement(
        f"""
        WITH updated AS (
            UPDATE ops.browser_runs
            SET status = {sql_literal(status)},
                actor = {sql_literal(actor)},
                page_title = coalesce({sql_literal(page_title)}, page_title),
                extracted_text_preview = coalesce({sql_literal(extracted_text_preview)}, extracted_text_preview),
                screenshot_path = coalesce({sql_literal(screenshot_path)}, screenshot_path),
                extracted_artifact_id = coalesce({artifact_id}, extracted_artifact_id),
                notes = coalesce({sql_literal(notes)}, notes),
                metadata = metadata || {sql_jsonb(metadata)},
                finished_at = CASE WHEN {sql_literal(status)} IN ('done','failed','blocked') THEN now() ELSE finished_at END,
                started_at = coalesce(started_at, now())
            WHERE id = {browser_run_id}
            RETURNING id, task_id, run_type, target_url, status, actor, page_title,
                      screenshot_path, extracted_artifact_id, started_at, finished_at, notes, metadata
        )
        SELECT coalesce(json_agg(row_to_json(updated)), '[]'::json)::text
        FROM updated
        """
    )
    result = rows[0] if rows else {"error": "browser run not found", "browser_run_id": browser_run_id}
    audit_mcp_call(
        tool_name="ai_os_complete_browser_run",
        action_type="complete_browser_run",
        permission_level="browser_capture",
        actor=actor,
        target_table="ops.browser_runs",
        target_id=browser_run_id,
        request_payload=arguments,
        result_payload=result,
        status="success" if rows else "not_found",
    )
    return tool_result(result)


def browser_runs(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=30, maximum=200)
    status = str(arguments.get("status") or "").strip()
    clauses = []
    if status:
        clauses.append(f"status = {sql_literal(status)}")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result(
        run_psql_json(
            f"""
            SELECT id, task_id, run_type, target_url, status, actor, page_title,
                   screenshot_path, extracted_artifact_id, source_kind, source_ref,
                   started_at, finished_at, notes, metadata
            FROM ops.v_browser_runs
            {where}
            LIMIT {limit}
            """
        )
    )


def upsert_client(arguments: dict) -> dict:
    payload = dict(arguments)
    payload.setdefault("objectives", arguments.get("objectives") or [arguments.get("objective") or "long-term capital compounding"])
    payload.setdefault("investment_horizon", arguments.get("investment_horizon") or "needs human review")
    payload.setdefault("risk_tolerance", arguments.get("risk_tolerance") or arguments.get("risk_profile"))
    payload.setdefault("risk_capacity", arguments.get("risk_capacity") or "needs human review")
    payload.setdefault("suitability_status", arguments.get("suitability_status") or "needs_review")
    payload.setdefault("source_evidence", arguments.get("source_evidence") or [])
    if arguments.get("account_code"):
        payload["account"] = {
            "account_code": arguments.get("account_code"),
            "account_name": arguments.get("account_name"),
            "account_type": arguments.get("account_type") or "investment",
            "broker": arguments.get("broker"),
            "base_currency": arguments.get("base_currency") or "INR",
        }
    return tool_result(post_api_json("/api/client-office/onboarding/stage", payload))

    client_code = required_text(arguments, "client_code")
    display_name = str(arguments.get("display_name") or client_code).strip()
    risk_profile = str(arguments.get("risk_profile") or "").strip() or None
    broker = str(arguments.get("broker") or "").strip() or None
    account_code = str(arguments.get("account_code") or "").strip() or None
    account_name = str(arguments.get("account_name") or "").strip() or (f"{display_name} Account" if account_code else None)
    account_type = str(arguments.get("account_type") or "investment").strip()
    base_currency = str(arguments.get("base_currency") or "INR").strip()
    notes = str(arguments.get("notes") or "").strip() or None
    sensitivity = str(arguments.get("sensitivity") or "client_private").strip()
    policy = arguments.get("investment_policy") or {}

    result = run_psql_json_statement(
        f"""
        WITH upserted_client AS (
            INSERT INTO portfolio.clients (
                client_code, display_name, risk_profile, investment_policy, sensitivity, active
            )
            VALUES (
                {sql_literal(client_code)}, {sql_literal(display_name)}, {sql_literal(risk_profile)},
                {sql_jsonb(policy)}, {sql_literal(sensitivity)}, true
            )
            ON CONFLICT (client_code) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                risk_profile = coalesce(EXCLUDED.risk_profile, portfolio.clients.risk_profile),
                investment_policy = portfolio.clients.investment_policy || EXCLUDED.investment_policy,
                sensitivity = EXCLUDED.sensitivity,
                active = true
            RETURNING id, client_code, display_name, risk_profile, sensitivity
        ),
        upserted_account AS (
            INSERT INTO portfolio.accounts (
                account_code, account_name, account_type, broker, base_currency, active, client_id
            )
            SELECT
                {sql_literal(account_code)}, {sql_literal(account_name)}, {sql_literal(account_type)},
                {sql_literal(broker)}, {sql_literal(base_currency)}, true, id
            FROM upserted_client
            WHERE {sql_literal(account_code)} IS NOT NULL
              AND {sql_literal(account_code)} <> ''
            ON CONFLICT (account_code) DO UPDATE SET
                account_name = EXCLUDED.account_name,
                account_type = EXCLUDED.account_type,
                broker = EXCLUDED.broker,
                base_currency = EXCLUDED.base_currency,
                active = true,
                client_id = EXCLUDED.client_id
            RETURNING id, account_code, account_name, broker, base_currency
        ),
        intake AS (
            INSERT INTO portfolio.manual_client_intake (
                client_code, display_name, risk_profile, broker, account_code, account_name,
                account_type, base_currency, status, notes, payload, applied_at
            )
            SELECT
                c.client_code, c.display_name, c.risk_profile, {sql_literal(broker)},
                {sql_literal(account_code)}, {sql_literal(account_name)}, {sql_literal(account_type)},
                {sql_literal(base_currency)}, 'applied', {sql_literal(notes)},
                jsonb_build_object('mcp_tool', 'ai_os_upsert_client'), now()
            FROM upserted_client c
            RETURNING id, status
        ),
        inbox AS (
            INSERT INTO agent.inbox_items (
                title, owner_agent, status, priority, recommended_action, evidence, target_workspace
            )
            SELECT
                'Client intake updated: ' || c.client_code,
                'Portfolio Manager',
                'needs_review',
                'medium',
                'Review client profile, account mapping, and first holdings before client reporting.',
                jsonb_build_array(
                    jsonb_build_object('table', 'portfolio.clients', 'client_code', c.client_code),
                    jsonb_build_object('table', 'portfolio.accounts', 'account_code', {sql_literal(account_code)})
                ),
                'clients'
            FROM upserted_client c
            RETURNING id
        ),
        result_rows AS (
            SELECT
                c.id AS client_id,
                c.client_code,
                c.display_name,
                c.risk_profile,
                c.sensitivity,
                a.id AS account_id,
                a.account_code,
                a.account_name,
                a.broker,
                a.base_currency,
                (SELECT id FROM intake LIMIT 1) AS intake_id,
                (SELECT id FROM inbox LIMIT 1) AS inbox_item_id
            FROM upserted_client c
            LEFT JOIN upserted_account a ON true
        )
        SELECT coalesce(json_agg(row_to_json(result_rows)), '[]'::json)::text
        FROM result_rows
        """
    )
    payload = result[0] if result else {"error": "client upsert returned no rows"}
    audit_mcp_call(
        tool_name="ai_os_upsert_client",
        action_type="upsert_client",
        permission_level="write_db_manual_only",
        actor=str(arguments.get("actor") or "Portfolio Manager"),
        target_table="portfolio.clients",
        target_id=payload.get("client_code") if isinstance(payload, dict) else None,
        request_payload=arguments,
        result_payload=payload,
    )
    return tool_result(payload)


def stage_holding_update(arguments: dict) -> dict:
    return tool_result(post_api_json("/api/portfolio/holding-updates/stage", arguments))

    client_code = required_text(arguments, "client_code")
    account_code = required_text(arguments, "account_code")
    symbol = required_text(arguments, "symbol").upper()
    exchange = str(arguments.get("exchange") or "NSE").strip().upper()
    instrument_type = str(arguments.get("instrument_type") or "equity").strip().lower()
    quantity = sql_numeric(arguments.get("quantity"), required=True, field_name="quantity")
    average_price = sql_numeric(arguments.get("average_price"), field_name="average_price")
    market_price = sql_numeric(arguments.get("market_price"), field_name="market_price")
    market_value = sql_numeric(arguments.get("market_value"), field_name="market_value")
    as_of = str(arguments.get("as_of") or "").strip() or None
    update_reason = str(arguments.get("update_reason") or "").strip() or "manual holdings update"

    rows = run_psql_json_statement(
        f"""
        WITH resolved AS (
            SELECT c.id AS client_id, a.id AS account_id, c.client_code, a.account_code
            FROM portfolio.clients c
            JOIN portfolio.accounts a ON a.client_id = c.id
            WHERE c.client_code = {sql_literal(client_code)}
              AND a.account_code = {sql_literal(account_code)}
            LIMIT 1
        ),
        inserted AS (
            INSERT INTO portfolio.manual_holding_updates (
                client_id, account_id, client_code, account_code, symbol, exchange,
                instrument_type, quantity, average_price, market_price, market_value,
                as_of, update_reason, status, payload
            )
            SELECT
                client_id, account_id, client_code, account_code, {sql_literal(symbol)},
                {sql_literal(exchange)}, {sql_literal(instrument_type)}, {quantity},
                {average_price}, {market_price}, coalesce({market_value}, {quantity} * {market_price}),
                coalesce({sql_literal(as_of)}::timestamptz, now()), {sql_literal(update_reason)},
                'staged',
                jsonb_build_object('mcp_tool', 'ai_os_stage_holding_update')
            FROM resolved
            RETURNING id, client_code, account_code, symbol, exchange, instrument_type,
                      quantity, average_price, market_price, market_value, as_of, status
        ),
        inbox AS (
            INSERT INTO agent.inbox_items (
                title, owner_agent, status, priority, recommended_action, evidence, target_workspace
            )
            SELECT
                'Holding update staged: ' || symbol || ' for ' || client_code,
                'Portfolio Manager',
                'needs_review',
                'high',
                'Review staged holding update, then apply through ai_os_apply_holding_update if correct.',
                jsonb_build_array(
                    jsonb_build_object('table', 'portfolio.manual_holding_updates', 'id', id),
                    jsonb_build_object('client_code', client_code),
                    jsonb_build_object('symbol', symbol)
                ),
                'clients'
            FROM inserted
            RETURNING id
        ),
        result_rows AS (
            SELECT inserted.*, (SELECT id FROM inbox LIMIT 1) AS inbox_item_id
            FROM inserted
        )
        SELECT coalesce(json_agg(row_to_json(result_rows)), '[]'::json)::text
        FROM result_rows
        """
    )
    if not rows:
        payload = {
            "error": "client/account not found",
            "client_code": client_code,
            "account_code": account_code,
            "next_step": "Create or update the client/account first with ai_os_upsert_client.",
        }
        audit_mcp_call(
            tool_name="ai_os_stage_holding_update",
            action_type="stage_holding_update",
            permission_level="write_db_manual_only",
            actor=str(arguments.get("actor") or "Portfolio Manager"),
            target_table="portfolio.manual_holding_updates",
            request_payload=arguments,
            result_payload=payload,
            status="not_found",
        )
        return tool_result(payload)
    payload = rows[0]
    audit_mcp_call(
        tool_name="ai_os_stage_holding_update",
        action_type="stage_holding_update",
        permission_level="write_db_manual_only",
        actor=str(arguments.get("actor") or "Portfolio Manager"),
        target_table="portfolio.manual_holding_updates",
        target_id=payload.get("id") if isinstance(payload, dict) else None,
        request_payload=arguments,
        result_payload=payload,
    )
    return tool_result(payload)


def apply_holding_update(arguments: dict) -> dict:
    payload = {
        "update_id": arguments.get("update_id"),
        "decision": arguments.get("decision") or "approved",
        "decided_by": arguments.get("applied_by") or arguments.get("decided_by") or "Devarsh",
        "decision_notes": arguments.get("decision_notes") or "Reviewed and explicitly approved through the governed MCP holding workflow.",
        "evidence": arguments.get("evidence") or [],
    }
    return tool_result(post_api_json("/api/portfolio/holding-updates/resolve", payload))

    try:
        update_id = int(arguments.get("update_id"))
    except (TypeError, ValueError) as exc:
        raise ValueError("update_id is required and must be an integer") from exc
    applied_by = str(arguments.get("applied_by") or "Devarsh").strip()

    rows = run_psql_json_statement(
        f"""
        WITH selected_update AS (
            SELECT *
            FROM portfolio.manual_holding_updates
            WHERE id = {update_id}
              AND status = 'staged'
            LIMIT 1
        ),
        position_upsert AS (
            INSERT INTO portfolio.positions (
                account_id, symbol, exchange, instrument_type, quantity, average_price,
                market_price, market_value, unrealized_pnl, as_of, source_system_id, payload
            )
            SELECT
                account_id,
                symbol,
                exchange,
                instrument_type,
                quantity,
                average_price,
                market_price,
                coalesce(market_value, quantity * market_price),
                CASE
                    WHEN average_price IS NOT NULL AND market_price IS NOT NULL THEN (market_price - average_price) * quantity
                    ELSE NULL
                END,
                as_of,
                NULL,
                payload || jsonb_build_object(
                    'source', 'manual_holding_update',
                    'manual_update_id', id,
                    'applied_by', {sql_literal(applied_by)}
                )
            FROM selected_update
            ON CONFLICT (account_id, symbol, exchange, instrument_type, as_of) DO UPDATE SET
                quantity = EXCLUDED.quantity,
                average_price = EXCLUDED.average_price,
                market_price = EXCLUDED.market_price,
                market_value = EXCLUDED.market_value,
                unrealized_pnl = EXCLUDED.unrealized_pnl,
                payload = portfolio.positions.payload || EXCLUDED.payload
            RETURNING id, account_id, symbol, exchange, instrument_type, quantity,
                      average_price, market_price, market_value, unrealized_pnl, as_of
        ),
        marked AS (
            UPDATE portfolio.manual_holding_updates
            SET status = 'applied',
                applied_at = now(),
                payload = payload || jsonb_build_object('applied_by', {sql_literal(applied_by)})
            WHERE id = (SELECT id FROM selected_update)
            RETURNING id, client_code, account_code, status, applied_at
        ),
        inbox AS (
            INSERT INTO agent.inbox_items (
                title, owner_agent, status, priority, recommended_action, evidence, target_workspace
            )
            SELECT
                'Holding update applied: ' || p.symbol || ' for manual update ' || m.id,
                'Portfolio Manager',
                'done',
                'medium',
                'Position row updated. Include it in next client brief and thesis review if needed.',
                jsonb_build_array(
                    jsonb_build_object('table', 'portfolio.positions', 'id', p.id),
                    jsonb_build_object('table', 'portfolio.manual_holding_updates', 'id', m.id)
                ),
                'clients'
            FROM position_upsert p
            JOIN marked m ON true
            RETURNING id
        ),
        result_rows AS (
            SELECT
                m.id AS manual_update_id,
                m.client_code,
                m.account_code,
                m.status,
                m.applied_at,
                p.id AS position_id,
                p.symbol,
                p.exchange,
                p.instrument_type,
                p.quantity,
                p.average_price,
                p.market_price,
                p.market_value,
                p.unrealized_pnl,
                p.as_of,
                (SELECT id FROM inbox LIMIT 1) AS inbox_item_id
            FROM marked m
            JOIN position_upsert p ON true
        )
        SELECT coalesce(json_agg(row_to_json(result_rows)), '[]'::json)::text
        FROM result_rows
        """
    )
    if not rows:
        payload = {
            "error": "staged update not found",
            "update_id": update_id,
            "next_step": "Check portfolio.v_manual_holding_update_queue for staged updates.",
        }
        audit_mcp_call(
            tool_name="ai_os_apply_holding_update",
            action_type="apply_holding_update",
            permission_level="write_db_manual_only",
            actor=applied_by,
            target_table="portfolio.manual_holding_updates",
            target_id=update_id,
            request_payload=arguments,
            result_payload=payload,
            status="not_found",
        )
        return tool_result(payload)
    payload = rows[0]
    audit_mcp_call(
        tool_name="ai_os_apply_holding_update",
        action_type="apply_holding_update",
        permission_level="write_db_manual_only",
        actor=applied_by,
        target_table="portfolio.positions",
        target_id=payload.get("position_id") if isinstance(payload, dict) else None,
        request_payload=arguments,
        result_payload=payload,
    )
    return tool_result(payload)


def client_onboarding_control(arguments: dict) -> dict:
    action = str(arguments.get("action") or "stage").strip().lower()
    if action == "stage":
        return tool_result(post_api_json("/api/client-office/onboarding/stage", arguments))
    if action in {"approve", "reject", "resolve"}:
        payload = dict(arguments)
        if action != "resolve":
            payload["decision"] = "approved" if action == "approve" else "rejected"
        return tool_result(post_api_json("/api/client-office/onboarding/resolve", payload))
    raise ValueError("action must be stage, approve, reject, or resolve")


def client_account_change_control(arguments: dict) -> dict:
    action = str(arguments.get("action") or "stage").strip().lower()
    if action == "stage":
        return tool_result(post_api_json("/api/client-office/accounts/stage", arguments))
    if action in {"approve", "reject", "resolve"}:
        payload = dict(arguments)
        if action != "resolve":
            payload["decision"] = "approved" if action == "approve" else "rejected"
        return tool_result(post_api_json("/api/client-office/accounts/resolve", payload))
    raise ValueError("action must be stage, approve, reject, or resolve")


def holding_reconciliation_control(arguments: dict) -> dict:
    action = str(arguments.get("action") or "reconcile").strip().lower()
    if action == "observe":
        return tool_result(post_api_json("/api/client-office/holding-observations", arguments, timeout=120))
    if action == "reconcile":
        return tool_result(post_api_json("/api/client-office/reconciliation/run", arguments, timeout=120))
    raise ValueError("action must be observe or reconcile")


def client_cash_ledger_control(arguments: dict) -> dict:
    action = str(arguments.get("action") or "stage").strip().lower()
    if action == "stage":
        return tool_result(post_api_json("/api/client-office/cash/stage", arguments))
    if action in {"approve", "reject", "resolve"}:
        payload = dict(arguments)
        if action != "resolve":
            payload["decision"] = "approved" if action == "approve" else "rejected"
        return tool_result(post_api_json("/api/client-office/cash/resolve", payload))
    raise ValueError("action must be stage, approve, reject, or resolve")


def client_accounting_run(arguments: dict) -> dict:
    return tool_result(post_api_json("/api/client-office/accounting/run", arguments, timeout=300))


def client_report_delivery_control(arguments: dict) -> dict:
    action = str(arguments.get("action") or "resolve").strip().lower()
    payload = dict(arguments)
    if action in {"approve", "reject"}:
        payload["decision"] = "approved" if action == "approve" else "rejected"
    elif action != "resolve":
        raise ValueError("action must be approve, reject, or resolve")
    return tool_result(post_api_json("/api/client-office/report-delivery/resolve", payload))


def client_3081282_summary(arguments: dict) -> dict:
    return tool_result(
        {
            "client_code": "3081282",
            "summary": run_psql_json(
                """
                SELECT metric, value
                FROM client_data.v_client_3081282_dashboard_summary
                ORDER BY metric
                """
            ),
            "source_ranges": run_psql_json(
                """
                SELECT source_type, min(entry_date) AS first_entry, max(entry_date) AS last_entry, count(*) AS rows
                FROM client_data.v_attached_client_trade_ledger
                WHERE client_code = '3081282' OR source_type = 'option_log'
                GROUP BY source_type
                ORDER BY source_type
                """
            ),
            "dashboard_path": str(RUNTIME_ROOT / "dashboards" / "client_3081282_transactions" / "index.html"),
        }
    )


def client_3081282_symbol_dates(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50, maximum=300)
    clauses = []
    symbol = str(arguments.get("symbol") or "").strip()
    instrument_type = str(arguments.get("instrument_type") or "").strip()
    open_only = bool(arguments.get("open_only", False))
    if symbol:
        clauses.append(f"symbol ILIKE {sql_literal('%' + symbol + '%')}")
    if instrument_type:
        clauses.append(f"instrument_type = {sql_literal(instrument_type)}")
    if open_only:
        clauses.append("coalesce(net_quantity, 0) <> 0")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result(
        run_psql_json(
            f"""
            SELECT symbol, instrument_type, option_type, strike_price,
                   first_buy_date, last_buy_date, first_sell_date, last_sell_date,
                   bought_quantity, sold_quantity, net_quantity, trade_rows, last_trade_date
            FROM client_data.v_client_3081282_symbol_dates
            {where}
            ORDER BY last_trade_date DESC NULLS LAST, symbol
            LIMIT {limit}
            """
        )
    )


def client_3081282_trade_timeline(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50, maximum=500)
    clauses = []
    symbol = str(arguments.get("symbol") or "").strip()
    side = str(arguments.get("side") or "").strip().upper()
    instrument_type = str(arguments.get("instrument_type") or "").strip()
    if symbol:
        clauses.append(f"symbol ILIKE {sql_literal('%' + symbol + '%')}")
    if side:
        clauses.append(f"upper(side) = {sql_literal(side)}")
    if instrument_type:
        clauses.append(f"instrument_type = {sql_literal(instrument_type)}")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result(
        run_psql_json(
            f"""
            SELECT source_type, client_code, client_name, entry_date, exit_date, trade_time,
                   exchange, symbol, instrument_type, side, quantity, entry_price, exit_price,
                   net_rate, amount, expiry_date, option_type, strike_price, external_trade_ref
            FROM client_data.v_client_3081282_trade_timeline
            {where}
            ORDER BY entry_date DESC NULLS LAST, trade_time DESC NULLS LAST, symbol
            LIMIT {limit}
            """
        )
    )


def research_outputs(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50, maximum=300)
    clauses = []
    query = str(arguments.get("query") or "").strip()
    artifact_family = str(arguments.get("artifact_family") or "").strip()
    company_or_topic = str(arguments.get("company_or_topic") or "").strip()
    if query:
        pattern = "%" + query + "%"
        clauses.append(
            "("
            f"title ILIKE {sql_literal(pattern)} OR "
            f"company_or_topic ILIKE {sql_literal(pattern)} OR "
            f"summary ILIKE {sql_literal(pattern)} OR "
            f"local_path ILIKE {sql_literal(pattern)}"
            ")"
        )
    if artifact_family:
        clauses.append(f"artifact_family = {sql_literal(artifact_family)}")
    if company_or_topic:
        clauses.append(f"company_or_topic ILIKE {sql_literal('%' + company_or_topic + '%')}")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result(
        run_psql_json(
            f"""
            SELECT artifact_id, title, artifact_family, company_or_topic, root_label,
                   local_path, mime_type, size_bytes, source_last_modified_at,
                   left(summary, 700) AS summary
            FROM research.v_ai_output_inventory
            {where}
            ORDER BY captured_at DESC, title
            LIMIT {limit}
            """
        )
    )


def research_output_detail(arguments: dict) -> dict:
    artifact_id = arguments.get("artifact_id")
    if artifact_id is None:
        return tool_result({"error": "artifact_id is required"})
    try:
        artifact_id_int = int(artifact_id)
    except (TypeError, ValueError):
        return tool_result({"error": "artifact_id must be an integer"})
    return tool_result(
        run_psql_json(
            f"""
            SELECT artifact_id, source_system, artifact_type, title, artifact_family,
                   company_or_topic, local_path, source_url, mime_type, content_hash,
                   sensitivity, captured_at, source_last_modified_at, summary
            FROM research.v_ai_output_inventory
            WHERE artifact_id = {artifact_id_int}
            LIMIT 1
            """
        )
    )


def fincept_component_review(arguments: dict) -> dict:
    return tool_result(
        {
            "source_system": run_psql_json(
                """
                SELECT name, source_type, location, sensitivity, status, notes
                FROM core.source_systems
                WHERE name = 'FinceptTerminal reference repo'
                """
            ),
            "components": run_psql_json(
                """
                SELECT sc.component_name, sc.component_type, sc.reuse_mode, sc.priority, sc.status,
                       sc.description, sc.target_schema, sc.target_tables, sc.safety_notes, sc.metadata
                FROM core.source_components sc
                JOIN core.source_systems ss ON ss.id = sc.source_system_id
                WHERE ss.name = 'FinceptTerminal reference repo'
                ORDER BY sc.priority DESC, sc.component_name
                """
            ),
            "review_artifact": run_psql_json(
                """
                SELECT title, artifact_type, source_url, metadata, captured_at
                FROM core.raw_artifacts
                WHERE source_url = 'https://github.com/Fincept-Corporation/FinceptTerminal'
                ORDER BY captured_at DESC
                LIMIT 1
                """
            ),
        }
    )


def fincept_install_status(arguments: dict) -> dict:
    return tool_result(
        {
            "install": run_psql_json(
                """
                SELECT source_system, component_name, version, git_commit, install_status, build_status,
                       runtime_mode, requires_sandbox_escape, install_root, app_bundle_path, binary_path,
                       features_confirmed_by_build, known_runtime_notes, updated_at
                FROM core.v_fincept_install_status
                ORDER BY updated_at DESC
                """
            ),
            "installed_components": run_psql_json(
                """
                SELECT sc.component_name, sc.component_type, sc.reuse_mode, sc.priority, sc.status,
                       sc.description, sc.target_schema, sc.target_tables, sc.safety_notes, sc.metadata
                FROM core.source_components sc
                JOIN core.source_systems ss ON ss.id = sc.source_system_id
                WHERE ss.name = 'FinceptTerminal reference repo'
                  AND sc.status = 'installed'
                ORDER BY
                    CASE sc.priority
                        WHEN 'critical' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        ELSE 4
                    END,
                    sc.component_name
                """
            ),
        }
    )


def search_obsidian_notes(arguments: dict) -> dict:
    query = str(arguments.get("query") or "").strip()
    limit = limit_arg(arguments, default=10, maximum=50)
    if not query:
        sql = f"""
            SELECT note_path, title, note_type, tags, left(body_summary, 500) AS body_summary
            FROM knowledge.v_obsidian_note_index
            ORDER BY last_modified_at DESC NULLS LAST
            LIMIT {limit}
        """
    else:
        pattern = f"%{query}%"
        sql = f"""
            SELECT note_path, title, note_type, tags, left(body_summary, 500) AS body_summary
            FROM knowledge.v_obsidian_note_index
            WHERE note_path ILIKE {sql_literal(pattern)}
               OR title ILIKE {sql_literal(pattern)}
               OR body_summary ILIKE {sql_literal(pattern)}
            ORDER BY last_modified_at DESC NULLS LAST
            LIMIT {limit}
        """
    return tool_result(run_psql_json(sql))


def recent_trading_signals(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=25, maximum=100)
    return tool_result(
        run_psql_json(
            f"""
            SELECT ts, strategy, symbol, exchange, action, price, quantity, confidence, status
            FROM trading.v_recent_signals
            LIMIT {limit}
            """
        )
    )


def latest_positions(arguments: dict) -> dict:
    return tool_result(
        run_psql_json(
            """
            SELECT account_id, symbol, exchange, instrument_type, quantity, average_price, market_price, market_value, unrealized_pnl, as_of
            FROM portfolio.v_latest_positions
            ORDER BY market_value DESC NULLS LAST, symbol
            LIMIT 100
            """
        )
    )


def run_p2cursor_reconciliation(arguments: dict) -> dict:
    payload = {
        "actor": arguments.get("actor") or "Jarvis MCP",
        "client_code": arguments.get("client_code") or arguments.get("clientCode") or "3081832",
    }
    return tool_result(post_api_json("/api/p2cursor-reconciliation/run", payload))


def reindex_obsidian(arguments: dict) -> dict:
    return tool_result(run_command([str(RUNTIME_ROOT / "scripts" / "index_obsidian_vault.py")]))


def mcp_candidate_shortlist(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50, maximum=200)
    category = str(arguments.get("category") or "").strip()
    status = str(arguments.get("status") or "").strip()
    selected_for_phase = str(arguments.get("selected_for_phase") or "").strip()
    clauses = []
    if category:
        clauses.append(f"category = {sql_literal(category)}")
    if status:
        clauses.append(f"status = {sql_literal(status)}")
    if selected_for_phase:
        clauses.append(f"selected_for_phase = {sql_literal(selected_for_phase)}")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result(
        run_psql_json(
            f"""
            SELECT integration_key, integration_name, category, provider, repo_url, docs_url,
                   install_mode, status, priority, trust_level, permission_level,
                   requires_api_key, requires_browser_session, cost_profile, owner_agent,
                   use_case, selected_for_phase, risk_notes, evidence_refs, config, updated_at
            FROM core.v_mcp_integration_registry
            {where}
            LIMIT {limit}
            """
        )
    )


def create_tradingview_task(arguments: dict) -> dict:
    task_title = required_text(arguments, "task_title")
    instruction = required_text(arguments, "instruction")
    task_type = str(arguments.get("task_type") or "chart_review").strip()
    requested_by = str(arguments.get("requested_by") or "Devarsh").strip()
    owner_agent = str(arguments.get("owner_agent") or "Trading Desk Agent").strip()
    symbols = arguments.get("symbols") or []
    exchange = str(arguments.get("exchange") or "").strip() or None
    timeframe = str(arguments.get("timeframe") or "").strip() or None
    chart_layout = str(arguments.get("chart_layout") or "").strip() or None
    source_ref = str(arguments.get("source_ref") or "").strip() or None
    evidence = arguments.get("evidence") or []
    metadata = arguments.get("metadata") or {}
    create_inbox = bool(arguments.get("create_inbox", True))

    rows = run_psql_json_statement(
        f"""
        WITH inserted AS (
            INSERT INTO ops.tradingview_tasks (
                task_title, task_type, requested_by, owner_agent, status, symbols,
                exchange, timeframe, chart_layout, instruction, source_ref,
                evidence, metadata
            )
            VALUES (
                {sql_literal(task_title)}, {sql_literal(task_type)}, {sql_literal(requested_by)},
                {sql_literal(owner_agent)}, 'queued', {sql_text_array(symbols)},
                {sql_literal(exchange)}, {sql_literal(timeframe)}, {sql_literal(chart_layout)},
                {sql_literal(instruction)}, {sql_literal(source_ref)}, {sql_jsonb(evidence)},
                {sql_jsonb(metadata)}
            )
            RETURNING id, task_title, task_type, requested_by, owner_agent, status, symbols,
                      exchange, timeframe, chart_layout, instruction, source_ref, created_at
        ),
        inbox AS (
            INSERT INTO agent.inbox_items (
                title, owner_agent, status, priority, recommended_action, evidence, target_workspace
            )
            SELECT
                'TradingView task queued: ' || task_title,
                owner_agent,
                'queued',
                'high',
                'Open or automate TradingView, complete the chart task, then attach screenshot/artifact evidence.',
                jsonb_build_array(
                    jsonb_build_object('table', 'ops.tradingview_tasks', 'id', id),
                    jsonb_build_object('symbols', symbols),
                    jsonb_build_object('task_type', task_type)
                ) || {sql_jsonb(evidence)},
                'trading'
            FROM inserted
            WHERE {str(create_inbox).lower()}
            RETURNING id
        ),
        result_rows AS (
            SELECT inserted.*, (SELECT id FROM inbox LIMIT 1) AS inbox_item_id
            FROM inserted
        )
        SELECT coalesce(json_agg(row_to_json(result_rows)), '[]'::json)::text
        FROM result_rows
        """
    )
    result = rows[0] if rows else {"error": "TradingView task not created"}
    audit_mcp_call(
        tool_name="ai_os_create_tradingview_task",
        action_type="create_tradingview_task",
        permission_level="write_with_approval",
        actor=owner_agent,
        target_table="ops.tradingview_tasks",
        target_id=result.get("id") if isinstance(result, dict) else None,
        request_payload=arguments,
        result_payload=result,
    )
    return tool_result(result)


def execute_tradingview_chart_action(arguments: dict) -> dict:
    result = post_api_json("/api/tradingview/chart-actions", arguments, timeout=75.0)
    audit_mcp_call(
        tool_name="ai_os_execute_tradingview_chart_action",
        action_type="open_tradingview_desktop_chart",
        permission_level="native_desktop_handoff",
        actor=str(arguments.get("actor") or arguments.get("requested_by") or "Trading Desk Agent"),
        target_table="ops.tradingview_tasks",
        target_id=result.get("id") if isinstance(result, dict) else None,
        request_payload=arguments,
        result_payload=result,
    )
    return tool_result(result)


def execute_tradingview_template_action(arguments: dict) -> dict:
    result = post_api_json("/api/tradingview/template-actions", arguments, timeout=75.0)
    audit_mcp_call(
        tool_name="ai_os_execute_tradingview_template_action",
        action_type="execute_tradingview_template_action",
        permission_level="browser_capture_or_approval",
        actor=str(arguments.get("actor") or arguments.get("requested_by") or "Trading Desk Agent"),
        target_table="ops.tradingview_tasks",
        target_id=(result.get("id") or (result.get("task") or {}).get("id")) if isinstance(result, dict) else None,
        request_payload=arguments,
        result_payload=result,
    )
    return tool_result(result)


def resolve_tradingview_template_approval(arguments: dict) -> dict:
    result = post_api_json(
        "/api/tradingview/template-approvals/resolve",
        {
            "approval_id": arguments.get("approval_id") or arguments.get("approvalId") or arguments.get("id"),
            "status": arguments.get("status") or arguments.get("decision"),
            "decided_by": arguments.get("decided_by") or arguments.get("decidedBy") or arguments.get("actor") or "Devarsh",
        },
        timeout=90.0,
    )
    audit_mcp_call(
        tool_name="ai_os_resolve_tradingview_template_approval",
        action_type="resolve_tradingview_template_approval",
        permission_level="human_approval_and_browser_capture",
        actor=str(arguments.get("decided_by") or arguments.get("actor") or "Devarsh"),
        target_table="agent.approvals",
        target_id=arguments.get("approval_id") or arguments.get("approvalId") or arguments.get("id"),
        request_payload=arguments,
        result_payload=result,
    )
    return tool_result(result)


def update_tradingview_task(arguments: dict) -> dict:
    try:
        task_id = int(arguments.get("task_id"))
    except (TypeError, ValueError) as exc:
        raise ValueError("task_id is required and must be an integer") from exc
    status = str(arguments.get("status") or "").strip() or None
    result_summary = str(arguments.get("result_summary") or "").strip() or None
    output_note_path = str(arguments.get("output_note_path") or "").strip() or None
    evidence = arguments.get("evidence") or []
    metadata = arguments.get("metadata") or {}
    browser_run_id_value = arguments.get("browser_run_id")
    extracted_artifact_id_value = arguments.get("extracted_artifact_id")
    browser_run_id = "NULL"
    extracted_artifact_id = "NULL"
    if browser_run_id_value not in (None, ""):
        browser_run_id = str(int(browser_run_id_value))
    if extracted_artifact_id_value not in (None, ""):
        extracted_artifact_id = str(int(extracted_artifact_id_value))
    actor = str(arguments.get("actor") or "Trading Desk Agent").strip()

    rows = run_psql_json_statement(
        f"""
        WITH updated AS (
            UPDATE ops.tradingview_tasks
            SET status = coalesce({sql_literal(status)}, status),
                result_summary = coalesce({sql_literal(result_summary)}, result_summary),
                output_note_path = coalesce({sql_literal(output_note_path)}, output_note_path),
                browser_run_id = coalesce({browser_run_id}, browser_run_id),
                extracted_artifact_id = coalesce({extracted_artifact_id}, extracted_artifact_id),
                evidence = evidence || {sql_jsonb(evidence)},
                metadata = metadata || {sql_jsonb(metadata)},
                updated_at = now(),
                completed_at = CASE
                    WHEN coalesce({sql_literal(status)}, status) IN ('done', 'failed', 'blocked') THEN now()
                    ELSE completed_at
                END
            WHERE id = {task_id}
            RETURNING id, task_title, task_type, owner_agent, status, symbols, browser_run_id,
                      extracted_artifact_id, output_note_path, result_summary, evidence,
                      updated_at, completed_at
        )
        SELECT coalesce(json_agg(row_to_json(updated)), '[]'::json)::text
        FROM updated
        """
    )
    result = rows[0] if rows else {"error": "TradingView task not found", "task_id": task_id}
    audit_mcp_call(
        tool_name="ai_os_update_tradingview_task",
        action_type="update_tradingview_task",
        permission_level="write_with_approval",
        actor=actor,
        target_table="ops.tradingview_tasks",
        target_id=task_id,
        request_payload=arguments,
        result_payload=result,
        status="success" if rows else "not_found",
    )
    return tool_result(result)


def tradingview_tasks(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50, maximum=200)
    status = str(arguments.get("status") or "").strip()
    symbol = str(arguments.get("symbol") or "").strip()
    clauses = []
    if status:
        clauses.append(f"status = {sql_literal(status)}")
    if symbol:
        clauses.append(f"EXISTS (SELECT 1 FROM unnest(symbols) s WHERE upper(s) = {sql_literal(symbol.upper())})")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result(
        run_psql_json(
            f"""
            SELECT id, task_title, task_type, requested_by, owner_agent, status,
                   symbols, exchange, timeframe, chart_layout, instruction, source_ref,
                   browser_run_id, extracted_artifact_id, output_note_path,
                   result_summary, evidence, metadata, created_at, updated_at, completed_at
            FROM ops.v_tradingview_tasks
            {where}
            LIMIT {limit}
            """
        )
    )


def record_trade_activity(arguments: dict, *, tool_name: str, default_execution_mode: str, default_source_kind: str) -> dict:
    symbol = required_text(arguments, "symbol").upper()
    side = required_text(arguments, "side").upper()
    execution_mode = str(arguments.get("execution_mode") or default_execution_mode).strip()
    source_kind = str(arguments.get("source_kind") or default_source_kind).strip()
    source_ref = str(arguments.get("source_ref") or "").strip() or None
    client_code = str(arguments.get("client_code") or "").strip() or None
    account_code = str(arguments.get("account_code") or "").strip() or None
    strategy_key = str(arguments.get("strategy_key") or "").strip() or None
    exchange = str(arguments.get("exchange") or "NSE").strip().upper()
    instrument_type = str(arguments.get("instrument_type") or "equity").strip().lower()
    quantity = sql_numeric(arguments.get("quantity"), field_name="quantity")
    price = sql_numeric(arguments.get("price"), field_name="price")
    trade_ts = str(arguments.get("trade_ts") or "").strip() or None
    status = str(arguments.get("status") or "recorded").strip()
    thesis = str(arguments.get("thesis") or "").strip() or None
    setup_type = str(arguments.get("setup_type") or "").strip() or None
    timeframe = str(arguments.get("timeframe") or "").strip() or None
    stop_loss = sql_numeric(arguments.get("stop_loss"), field_name="stop_loss")
    target_price = sql_numeric(arguments.get("target_price"), field_name="target_price")
    realized_pnl = sql_numeric(arguments.get("realized_pnl"), field_name="realized_pnl")
    fees = sql_numeric(arguments.get("fees"), field_name="fees")
    source_signal_id_value = arguments.get("source_signal_id")
    alert_event_id_value = arguments.get("alert_event_id")
    source_signal_id = "NULL"
    alert_event_id = "NULL"
    if source_signal_id_value not in (None, ""):
        source_signal_id = str(int(source_signal_id_value))
    if alert_event_id_value not in (None, ""):
        alert_event_id = str(int(alert_event_id_value))
    tags = arguments.get("tags") or []
    evidence = arguments.get("evidence") or []
    payload = arguments.get("payload") or {}
    created_by = str(arguments.get("created_by") or "Devarsh").strip()

    rows = run_psql_json_statement(
        f"""
        WITH inserted AS (
            INSERT INTO trading.trade_activity_ledger (
                activity_type, execution_mode, source_kind, source_ref, client_code, account_code,
                strategy_key, symbol, exchange, instrument_type, side, quantity, price, trade_ts,
                status, thesis, setup_type, timeframe, stop_loss, target_price, realized_pnl,
                fees, source_signal_id, alert_event_id, tags, evidence, payload, created_by
            )
            VALUES (
                'trade', {sql_literal(execution_mode)}, {sql_literal(source_kind)}, {sql_literal(source_ref)},
                {sql_literal(client_code)}, {sql_literal(account_code)}, {sql_literal(strategy_key)},
                {sql_literal(symbol)}, {sql_literal(exchange)}, {sql_literal(instrument_type)},
                {sql_literal(side)}, {quantity}, {price}, coalesce({sql_literal(trade_ts)}::timestamptz, now()),
                {sql_literal(status)}, {sql_literal(thesis)}, {sql_literal(setup_type)}, {sql_literal(timeframe)},
                {stop_loss}, {target_price}, {realized_pnl}, {fees}, {source_signal_id}, {alert_event_id},
                {sql_text_array(tags)}, {sql_jsonb(evidence)}, {sql_jsonb(payload)}, {sql_literal(created_by)}
            )
            RETURNING id, execution_mode, source_kind, client_code, account_code, strategy_key,
                      symbol, exchange, instrument_type, side, quantity, price, trade_ts, status,
                      thesis, setup_type, timeframe, stop_loss, target_price, realized_pnl, fees,
                      tags, created_by, created_at
        ),
        inbox AS (
            INSERT INTO agent.inbox_items (
                title, owner_agent, status, priority, recommended_action, evidence, target_workspace
            )
            SELECT
                CASE
                    WHEN execution_mode IN ('paper','shadow','system_alert_paper') THEN 'Paper trade recorded: '
                    ELSE 'Manual trade recorded: '
                END || symbol || ' ' || side,
                CASE
                    WHEN execution_mode IN ('paper','shadow','system_alert_paper') THEN 'Quant Agent'
                    ELSE 'Trading Desk Agent'
                END,
                'needs_review',
                CASE
                    WHEN execution_mode IN ('paper','shadow','system_alert_paper') THEN 'medium'
                    ELSE 'high'
                END,
                'Review the trade record, attach chart/thesis evidence, and include it in next journal/strategy review.',
                jsonb_build_array(jsonb_build_object('table', 'trading.trade_activity_ledger', 'id', id)) || {sql_jsonb(evidence)},
                'trading'
            FROM inserted
            RETURNING id
        ),
        result_rows AS (
            SELECT inserted.*, (SELECT id FROM inbox LIMIT 1) AS inbox_item_id
            FROM inserted
        )
        SELECT coalesce(json_agg(row_to_json(result_rows)), '[]'::json)::text
        FROM result_rows
        """
    )
    result = rows[0] if rows else {"error": "trade activity not recorded"}
    audit_mcp_call(
        tool_name=tool_name,
        action_type="record_trade_activity",
        permission_level="write_db_manual_only",
        actor=created_by,
        target_table="trading.trade_activity_ledger",
        target_id=result.get("id") if isinstance(result, dict) else None,
        request_payload=arguments,
        result_payload=result,
    )
    return tool_result(result)


def record_manual_trade(arguments: dict) -> dict:
    return record_trade_activity(
        arguments,
        tool_name="ai_os_record_manual_trade",
        default_execution_mode="manual_actual",
        default_source_kind="manual",
    )


def record_paper_trade(arguments: dict) -> dict:
    return record_trade_activity(
        arguments,
        tool_name="ai_os_record_paper_trade",
        default_execution_mode="paper",
        default_source_kind="system_alert",
    )


def trade_activity(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50, maximum=300)
    execution_mode = str(arguments.get("execution_mode") or "").strip()
    symbol = str(arguments.get("symbol") or "").strip()
    strategy_key = str(arguments.get("strategy_key") or "").strip()
    include_summary = bool(arguments.get("include_paper_summary", True))
    clauses = []
    if execution_mode:
        clauses.append(f"execution_mode = {sql_literal(execution_mode)}")
    if symbol:
        clauses.append(f"symbol ILIKE {sql_literal('%' + symbol + '%')}")
    if strategy_key:
        clauses.append(f"strategy_key = {sql_literal(strategy_key)}")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    payload = {
        "rows": run_psql_json(
            f"""
            SELECT id, activity_type, execution_mode, source_kind, source_ref, client_code, account_code,
                   strategy_key, symbol, exchange, instrument_type, side, quantity, price, trade_ts,
                   status, thesis, setup_type, timeframe, stop_loss, target_price, realized_pnl,
                   fees, tags, created_by, created_at
            FROM trading.v_trade_activity_ledger
            {where}
            LIMIT {limit}
            """
        )
    }
    if include_summary:
        payload["paper_summary"] = run_psql_json(
            """
            SELECT strategy_key, symbol, trade_count, first_trade_ts, last_trade_ts,
                   realized_pnl, average_price, statuses
            FROM trading.v_paper_trade_summary
            LIMIT 100
            """
        )
    return tool_result(payload)


def make_strategy_key(prefix: str, value: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    base = base[:48] if base else datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{prefix}_{base}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"


def create_strategy_intake(arguments: dict) -> dict:
    intake_text = required_text(arguments, "intake_text")
    strategy_name = str(arguments.get("strategy_name") or "").strip() or "User strategy intake"
    intake_key = str(arguments.get("intake_key") or "").strip() or make_strategy_key("intake", strategy_name)
    created_by = str(arguments.get("created_by") or "Devarsh").strip()
    owner_agent = str(arguments.get("owner_agent") or "Strategy Intake Agent").strip()
    assigned_agents = arguments.get("assigned_agents") or [
        "Strategy Intake Agent",
        "Strategy Research Agent",
        "Backtest Engineer",
        "Model Validation Agent",
        "Risk Agent",
    ]
    evidence = arguments.get("evidence") or []
    structured_spec = arguments.get("structured_spec") or {}
    create_task = bool(arguments.get("create_task", True))
    rows = run_psql_json_statement(
        f"""
        WITH inserted AS (
            INSERT INTO strategy.strategy_intakes (
                intake_key, created_by, intake_text, strategy_name, strategy_family, asset_class,
                symbols, universe, timeframe, intent_tags, constraints_text, risk_notes,
                requested_outputs, source_kind, source_ref, status, owner_agent, assigned_agents,
                structured_spec, evidence
            )
            VALUES (
                {sql_literal(intake_key)}, {sql_literal(created_by)}, {sql_literal(intake_text)},
                {sql_literal(strategy_name)}, {sql_literal(arguments.get("strategy_family"))},
                {sql_literal(arguments.get("asset_class"))}, {sql_text_array(arguments.get("symbols"))},
                {sql_literal(arguments.get("universe"))}, {sql_literal(arguments.get("timeframe"))},
                {sql_text_array(arguments.get("intent_tags"))}, {sql_literal(arguments.get("constraints_text"))},
                {sql_literal(arguments.get("risk_notes"))}, {sql_text_array(arguments.get("requested_outputs"))},
                {sql_literal(arguments.get("source_kind"))}, {sql_literal(arguments.get("source_ref"))},
                {sql_literal(arguments.get("status") or "new")}, {sql_literal(owner_agent)},
                {sql_text_array(assigned_agents)}, {sql_jsonb(structured_spec)}, {sql_jsonb(evidence)}
            )
            ON CONFLICT (intake_key) DO UPDATE SET
                intake_text = EXCLUDED.intake_text,
                strategy_name = EXCLUDED.strategy_name,
                strategy_family = EXCLUDED.strategy_family,
                asset_class = EXCLUDED.asset_class,
                symbols = EXCLUDED.symbols,
                universe = EXCLUDED.universe,
                timeframe = EXCLUDED.timeframe,
                intent_tags = EXCLUDED.intent_tags,
                constraints_text = EXCLUDED.constraints_text,
                risk_notes = EXCLUDED.risk_notes,
                requested_outputs = EXCLUDED.requested_outputs,
                status = EXCLUDED.status,
                owner_agent = EXCLUDED.owner_agent,
                assigned_agents = EXCLUDED.assigned_agents,
                structured_spec = EXCLUDED.structured_spec,
                evidence = EXCLUDED.evidence,
                updated_at = now()
            RETURNING id, intake_key, strategy_name, status, owner_agent, assigned_agents, created_at, updated_at
        ),
        task_insert AS (
            INSERT INTO agent.tasks (
                title, objective, owner_agent, status, priority, approval_required,
                source_kind, source_ref, output_format, evidence
            )
            SELECT
                'Strategy intake: ' || strategy_name,
                'Convert intake into structured strategy candidate, data requirements, backtest request, and validation plan.',
                {sql_literal(owner_agent)},
                'queued',
                {sql_literal(arguments.get("priority") or "high")},
                true,
                'strategy_intake',
                intake_key,
                'strategy_spec',
                {sql_jsonb(evidence)}
            FROM inserted
            WHERE {str(create_task).lower()}
            RETURNING id
        ),
        inbox_insert AS (
            INSERT INTO agent.inbox_items (
                task_id, title, owner_agent, status, priority, recommended_action,
                evidence, target_workspace
            )
            SELECT
                task_insert.id,
                'Charlie routed strategy intake: ' || inserted.strategy_name,
                {sql_literal(owner_agent)},
                'new',
                {sql_literal(arguments.get("priority") or "high")},
                'Structure the strategy, identify required data, and queue backtest/validation work. No live execution.',
                {sql_jsonb(evidence)},
                'quant'
            FROM task_insert
            CROSS JOIN inserted
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(final_rows)), '[]'::json)::text
        FROM (
            SELECT inserted.*, task_insert.id AS task_id, inbox_insert.id AS inbox_item_id
            FROM inserted
            LEFT JOIN task_insert ON true
            LEFT JOIN inbox_insert ON true
        ) final_rows
        """
    )
    result = rows[0] if rows else {"error": "strategy intake not created"}
    audit_mcp_call(
        tool_name="ai_os_create_strategy_intake",
        action_type="create_strategy_intake",
        permission_level="write_with_approval",
        actor=created_by,
        target_table="strategy.strategy_intakes",
        target_id=result.get("id") if isinstance(result, dict) else None,
        request_payload=arguments,
        result_payload=result,
    )
    return tool_result(result)


def strategy_intakes(arguments: dict) -> dict:
    status = str(arguments.get("status") or "").strip()
    where = f"WHERE status = {sql_literal(status)}" if status else ""
    limit = limit_arg(arguments, default=50)
    return tool_result(
        run_psql_json(
            f"""
            SELECT id, intake_key, created_by, strategy_name, strategy_family, asset_class,
                   symbols, universe, timeframe, intent_tags, status, owner_agent,
                   assigned_agents, generated_ideas, strategy_candidates, source_kind,
                   source_ref, created_at, updated_at
            FROM strategy.v_strategy_intake_queue
            {where}
            ORDER BY created_at DESC
            LIMIT {limit}
            """
        )
    )


def strategy_template_library(arguments: dict) -> dict:
    family = str(arguments.get("template_family") or arguments.get("family") or "").strip()
    asset_class = str(arguments.get("asset_class") or arguments.get("assetClass") or "").strip()
    readiness = str(arguments.get("execution_readiness") or arguments.get("readiness") or "").strip()
    limit = limit_arg(arguments, default=50)
    filters: list[str] = ["status = 'active'"]
    if family:
        filters.append(f"template_family = {sql_literal(family)}")
    if asset_class:
        filters.append(f"asset_class = {sql_literal(asset_class)}")
    if readiness:
        filters.append(f"execution_readiness = {sql_literal(readiness)}")
    where = "WHERE " + " AND ".join(filters)
    return tool_result(
        {
            "summary": run_psql_json(
                """
                SELECT metric, value, interpretation
                FROM strategy.v_strategy_template_summary
                ORDER BY metric
                """
            ),
            "templates": run_psql_json(
                f"""
                SELECT id, template_key, template_name, template_family,
                       asset_class, default_timeframe, engine_template,
                       default_symbols, default_universe, description,
                       entry_rule, exit_rule, risk_rule, data_requirements,
                       required_gates, risk_controls, supported_assets,
                       source_component, execution_readiness, owner_agent,
                       application_count, applications_7d,
                       latest_application_at
                FROM strategy.v_strategy_template_library
                {where}
                ORDER BY display_rank, template_name
                LIMIT {limit}
                """
            ),
        }
    )


def create_strategy_from_template(arguments: dict) -> dict:
    template_key = required_text(arguments, "template_key")
    actor = str(arguments.get("created_by") or arguments.get("actor") or "Devarsh").strip()
    rows = run_psql_json_statement(
        f"""
        WITH created AS (
            SELECT strategy.create_strategy_from_template(
                {sql_literal(template_key)},
                {sql_literal(actor)},
                {sql_literal(arguments.get("strategy_name"))},
                {sql_text_array(arguments.get("symbols")) if arguments.get("symbols") else "NULL"},
                {sql_literal(arguments.get("universe"))},
                {sql_literal(arguments.get("timeframe"))},
                {sql_literal(arguments.get("notes"))}
            ) AS result
        )
        SELECT coalesce(json_agg(row_to_json(output_rows)), '[]'::json)::text
        FROM (
            SELECT
                (result->>'application_id')::BIGINT AS application_id,
                result->>'application_key' AS application_key,
                result->>'template_key' AS template_key,
                result->>'template_name' AS template_name,
                result->>'execution_readiness' AS execution_readiness,
                result->>'engine_template' AS engine_template,
                (result->>'intake_id')::BIGINT AS intake_id,
                result->>'intake_key' AS intake_key,
                (result->>'idea_id')::BIGINT AS idea_id,
                result->>'idea_key' AS idea_key,
                (result->>'candidate_id')::BIGINT AS candidate_id,
                result->>'candidate_key' AS candidate_key,
                (result->>'task_id')::BIGINT AS task_id,
                (result->>'inbox_id')::BIGINT AS inbox_id,
                result->>'activation_gate' AS activation_gate,
                (result->>'live_execution_allowed')::BOOLEAN AS live_execution_allowed
            FROM created
        ) output_rows
        """
    )
    result = rows[0] if rows else {"error": "strategy template application failed"}
    audit_mcp_call(
        tool_name="ai_os_create_strategy_from_template",
        action_type="create_strategy_from_template",
        permission_level="write_with_approval",
        actor=actor,
        target_table="strategy.strategy_template_applications",
        target_id=result.get("application_id") if isinstance(result, dict) else None,
        request_payload=arguments,
        result_payload=result,
    )
    return tool_result(result)


def create_generated_strategy_idea(arguments: dict) -> dict:
    title = required_text(arguments, "title")
    thesis = required_text(arguments, "thesis")
    idea_key = str(arguments.get("idea_key") or "").strip() or make_strategy_key("idea", title)
    owner_agent = str(arguments.get("owner_agent") or "Strategy Generator").strip()
    create_candidate = bool(arguments.get("create_candidate", True))
    evidence = arguments.get("evidence") or []
    rows = run_psql_json_statement(
        f"""
        WITH intake AS (
            SELECT id FROM strategy.strategy_intakes
            WHERE intake_key = {sql_literal(arguments.get("intake_key"))}
               OR id::TEXT = {sql_literal(arguments.get("intake_id"))}
            ORDER BY id DESC
            LIMIT 1
        ),
        inserted AS (
            INSERT INTO strategy.generated_ideas (
                idea_key, intake_id, title, idea_type, symbols, universe, timeframe,
                thesis, edge_hypothesis, entry_rules, exit_rules, risk_rules,
                data_requirements, assumptions, invalidation_tests, priority_score,
                risk_score, status, owner_agent, evidence
            )
            VALUES (
                {sql_literal(idea_key)}, (SELECT id FROM intake), {sql_literal(title)},
                {sql_literal(arguments.get("idea_type") or "strategy_hypothesis")},
                {sql_text_array(arguments.get("symbols"))}, {sql_literal(arguments.get("universe"))},
                {sql_literal(arguments.get("timeframe"))}, {sql_literal(thesis)},
                {sql_literal(arguments.get("edge_hypothesis"))}, {sql_jsonb(arguments.get("entry_rules"))},
                {sql_jsonb(arguments.get("exit_rules"))}, {sql_jsonb(arguments.get("risk_rules"))},
                {sql_text_array(arguments.get("data_requirements"))},
                {sql_text_array(arguments.get("assumptions"))},
                {sql_text_array(arguments.get("invalidation_tests"))},
                {sql_numeric(arguments.get("priority_score"))}, {sql_numeric(arguments.get("risk_score"))},
                {sql_literal(arguments.get("status") or "candidate")}, {sql_literal(owner_agent)},
                {sql_jsonb(evidence)}
            )
            ON CONFLICT (idea_key) DO UPDATE SET
                title = EXCLUDED.title,
                idea_type = EXCLUDED.idea_type,
                symbols = EXCLUDED.symbols,
                universe = EXCLUDED.universe,
                timeframe = EXCLUDED.timeframe,
                thesis = EXCLUDED.thesis,
                edge_hypothesis = EXCLUDED.edge_hypothesis,
                entry_rules = EXCLUDED.entry_rules,
                exit_rules = EXCLUDED.exit_rules,
                risk_rules = EXCLUDED.risk_rules,
                data_requirements = EXCLUDED.data_requirements,
                assumptions = EXCLUDED.assumptions,
                invalidation_tests = EXCLUDED.invalidation_tests,
                priority_score = EXCLUDED.priority_score,
                risk_score = EXCLUDED.risk_score,
                status = EXCLUDED.status,
                owner_agent = EXCLUDED.owner_agent,
                evidence = EXCLUDED.evidence,
                updated_at = now()
            RETURNING *
        ),
        candidate_insert AS (
            INSERT INTO strategy.strategy_candidates (
                name, source_kind, source_ref, hypothesis, universe, timeframe,
                entry_rules, exit_rules, risk_rules, status, owner_agent,
                intake_id, generated_idea_id, candidate_key, structured_spec
            )
            SELECT
                title,
                'generated_strategy_idea',
                idea_key,
                thesis,
                universe,
                timeframe,
                entry_rules,
                exit_rules,
                risk_rules,
                'idea',
                owner_agent,
                intake_id,
                id,
                {sql_literal(arguments.get("candidate_key"))},
                jsonb_build_object(
                    'data_requirements', data_requirements,
                    'assumptions', assumptions,
                    'invalidation_tests', invalidation_tests,
                    'edge_hypothesis', edge_hypothesis
                )
            FROM inserted
            WHERE {str(create_candidate).lower()}
            ON CONFLICT (name) DO UPDATE SET
                source_kind = EXCLUDED.source_kind,
                source_ref = EXCLUDED.source_ref,
                hypothesis = EXCLUDED.hypothesis,
                universe = EXCLUDED.universe,
                timeframe = EXCLUDED.timeframe,
                entry_rules = EXCLUDED.entry_rules,
                exit_rules = EXCLUDED.exit_rules,
                risk_rules = EXCLUDED.risk_rules,
                owner_agent = EXCLUDED.owner_agent,
                intake_id = EXCLUDED.intake_id,
                generated_idea_id = EXCLUDED.generated_idea_id,
                structured_spec = EXCLUDED.structured_spec,
                updated_at = now()
            RETURNING id, name, candidate_key, status
        )
        SELECT coalesce(json_agg(row_to_json(final_rows)), '[]'::json)::text
        FROM (
            SELECT inserted.id, inserted.idea_key, inserted.title, inserted.status,
                   candidate_insert.id AS strategy_id, candidate_insert.name AS strategy_name
            FROM inserted
            LEFT JOIN candidate_insert ON true
        ) final_rows
        """
    )
    result = rows[0] if rows else {"error": "generated strategy idea not created"}
    audit_mcp_call(
        tool_name="ai_os_create_generated_strategy_idea",
        action_type="create_generated_strategy_idea",
        permission_level="write_with_approval",
        actor=owner_agent,
        target_table="strategy.generated_ideas",
        target_id=result.get("id") if isinstance(result, dict) else None,
        request_payload=arguments,
        result_payload=result,
    )
    return tool_result(result)


def strategy_lab(arguments: dict) -> dict:
    status = str(arguments.get("status") or "").strip()
    where = f"WHERE status = {sql_literal(status)}" if status else ""
    limit = limit_arg(arguments, default=50)
    return tool_result(
        {
            "intakes": run_psql_json(
                f"""
                SELECT id, intake_key, strategy_name, strategy_family, symbols, universe,
                       timeframe, status, owner_agent, generated_ideas, strategy_candidates,
                       created_at, updated_at
                FROM strategy.v_strategy_intake_queue
                ORDER BY created_at DESC
                LIMIT {limit}
                """
            ),
            "generated_ideas": run_psql_json(
                f"""
                SELECT id, idea_key, title, idea_type, symbols, universe, timeframe,
                       status, priority_score, risk_score, intake_key, created_at
                FROM strategy.v_generated_ideas
                ORDER BY created_at DESC
                LIMIT {limit}
                """
            ),
            "strategy_candidates": run_psql_json(
                f"""
                SELECT strategy_id, candidate_key, name, status, validation_status,
                       activation_gate, owner_agent, timeframe, universe, intake_key,
                       idea_key, backtest_runs, optimization_runs, validation_reviews,
                       latest_backtest_finished_at, latest_optimization_finished_at,
                       latest_validation_at, created_at, updated_at
                FROM strategy.v_strategy_agent_lab
                {where}
                ORDER BY updated_at DESC
                LIMIT {limit}
                """
            ),
        }
    )


def parse_strategy_dsl(arguments: dict) -> dict:
    candidate_id = resolve_strategy_id(arguments)
    payload = {
        "candidate_id": candidate_id,
        "dsl_text": arguments.get("dsl_text") or arguments.get("dslText"),
        "actor": arguments.get("actor") or "Strategy Intake Agent",
    }
    result = post_api_json("/api/strategy/dsl/parse", payload, timeout=120)
    return tool_result(result)


def strategy_data_quality_gate(arguments: dict) -> dict:
    candidate_id = resolve_strategy_id(arguments)
    payload = {
        "candidate_id": candidate_id,
        "symbols": arguments.get("symbols"),
        "timeframe": arguments.get("timeframe"),
        "min_rows_per_symbol": arguments.get("min_rows_per_symbol") or arguments.get("minRowsPerSymbol") or 50,
        "min_total_rows": arguments.get("min_total_rows") or arguments.get("minTotalRows") or 500,
        "actor": arguments.get("actor") or "Backtest Engineer",
    }
    result = post_api_json("/api/strategy/data-quality/check", payload, timeout=120)
    return tool_result(result)


def strategy_dsl_status(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50)
    status = str(arguments.get("data_quality_status") or arguments.get("status") or "").strip()
    where = f"WHERE data_quality_status = {sql_literal(status)}" if status else ""
    return tool_result(
        {
            "readiness": run_psql_json(
                f"""
                SELECT candidate_id, candidate_key, strategy_name, candidate_status,
                       candidate_timeframe, universe, parse_status, parse_errors,
                       template, symbols, gate_key, data_quality_status,
                       data_quality_severity, data_quality_reasons, total_rows,
                       min_symbol_rows, max_symbol_rows, first_ts, last_ts, updated_at
                FROM strategy.v_strategy_dsl_readiness_summary
                {where}
                ORDER BY updated_at DESC, candidate_id DESC
                LIMIT {limit}
                """
            ),
            "latest_gates": run_psql_json(
                f"""
                SELECT id, gate_key, candidate_id, candidate_key, strategy_name,
                       timeframe, requested_symbols, matched_symbols, missing_symbols,
                       total_rows, min_symbol_rows, max_symbol_rows, status, severity,
                       reasons, created_by, created_at
                FROM strategy.v_backtest_data_quality_gates
                ORDER BY created_at DESC, id DESC
                LIMIT {limit}
                """
            ),
            "latest_specs": run_psql_json(
                f"""
                SELECT id, candidate_id, candidate_key, strategy_name, parse_status,
                       parse_errors, symbols, timeframe, template, created_by, updated_at
                FROM strategy.v_strategy_rule_specs
                ORDER BY updated_at DESC, id DESC
                LIMIT {limit}
                """
            ),
        }
    )


def run_strategy_quant_analytics(arguments: dict) -> dict:
    payload = {
        "run_key": arguments.get("run_key") or arguments.get("runKey"),
        "strategy_ids": arguments.get("strategy_ids") or arguments.get("strategyIds"),
        "timeframe": arguments.get("timeframe") or "5m",
        "limit": arguments.get("limit") or 10,
        "max_symbols": arguments.get("max_symbols") or arguments.get("maxSymbols") or 14,
        "cost_bps": arguments.get("cost_bps") or arguments.get("costBps") or 3,
        "slippage_bps": arguments.get("slippage_bps") or arguments.get("slippageBps") or 2,
        "participation_rate": arguments.get("participation_rate") or arguments.get("participationRate") or 0.05,
        "actor": arguments.get("actor") or "Quant Analytics Agent",
    }
    result = post_api_json("/api/strategy/quant-analytics/run", payload, timeout=260)
    return tool_result(result)


def run_institutional_portfolio_risk(arguments: dict) -> dict:
    payload = {
        "run_key": arguments.get("run_key") or arguments.get("runKey"),
        "lookback_days": arguments.get("lookback_days") or arguments.get("lookbackDays") or 756,
        "simulations": arguments.get("simulations") or 20_000,
        "seed": arguments.get("seed") or 20260715,
        "actor": arguments.get("actor") or "Portfolio Risk Analyst",
    }
    result = post_api_json("/api/risk/institutional/run", payload, timeout=320)
    return tool_result(result)


def sync_fundamental_company_intake(arguments: dict) -> dict:
    payload = {
        key: arguments[key]
        for key in ("symbol", "actor")
        if key in arguments
    }
    payload.update({
        "capital_action_allowed": False,
        "broker_write_allowed": False,
    })
    return tool_result(post_api_json("/api/research/fundamental-intake/sync", payload, timeout=180))


def run_institutional_fundamental_factory(arguments: dict) -> dict:
    payload = {
        key: arguments[key]
        for key in ("company_id", "company_key", "symbol", "exchange", "as_of", "actor", "run_key", "dry_run")
        if key in arguments
    }
    payload.update({
        "paper_only": True,
        "live_execution_allowed": False,
        "capital_action_allowed": False,
    })
    return tool_result(post_api_json("/api/research/fundamental-factory/run", payload, timeout=620))


def run_sector_intelligence_engine(arguments: dict) -> dict:
    payload = {
        key: arguments[key]
        for key in ("index_id", "index_key", "as_of_date", "horizon", "actor", "run_key", "dry_run")
        if key in arguments
    }
    payload.update({
        "paper_only": True,
        "live_execution_allowed": False,
        "capital_action_allowed": False,
        "tradingview_artifacts_only": True,
    })
    return tool_result(post_api_json("/api/sector-intelligence/run", payload, timeout=620))


def sync_sector_fundamentals(arguments: dict) -> dict:
    payload = {
        key: arguments[key]
        for key in ("taxonomy_key", "as_of_date", "actor", "persist")
        if key in arguments
    }
    payload.setdefault("actor", "Sector Fundamental Analyst")
    payload.setdefault("persist", True)
    payload["capital_action_allowed"] = False
    payload["broker_write_allowed"] = False
    return tool_result(post_api_json("/api/sector-intelligence/fundamentals/sync", payload, timeout=320))


def sync_sector_ownership_flows(arguments: dict) -> dict:
    payload = {
        key: arguments[key]
        for key in ("taxonomy_key", "as_of_date", "lookback_days", "actor", "persist")
        if key in arguments
    }
    payload.setdefault("actor", "Sector Flow And Ownership Analyst")
    payload.setdefault("lookback_days", 365)
    payload.setdefault("persist", True)
    payload["capital_action_allowed"] = False
    payload["broker_write_allowed"] = False
    return tool_result(post_api_json("/api/sector-intelligence/ownership-flows/sync", payload, timeout=920))


def build_sector_underwrite(arguments: dict) -> dict:
    payload = {
        key: arguments[key]
        for key in ("taxonomy_key", "as_of_date", "actor", "persist")
        if key in arguments
    }
    payload.setdefault("actor", "Sector Portfolio Manager")
    payload.setdefault("persist", True)
    payload["paper_only"] = True
    payload["live_execution_allowed"] = False
    payload["capital_action_allowed"] = False
    payload["broker_write_allowed"] = False
    return tool_result(post_api_json("/api/sector-intelligence/underwrite/build", payload, timeout=1220))


def run_sector_acceptance(arguments: dict) -> dict:
    payload = {
        key: arguments[key]
        for key in ("taxonomy_node_id", "taxonomy_key", "as_of_date", "run_key", "actor")
        if key in arguments
    }
    payload.setdefault("actor", "Sector Portfolio Manager")
    payload["paper_only"] = True
    payload["live_execution_allowed"] = False
    payload["broker_write_allowed"] = False
    payload["capital_action_allowed"] = False
    return tool_result(post_api_json("/api/sector-intelligence/acceptance/run", payload, timeout=180))


def run_institutional_options_engine(arguments: dict) -> dict:
    payload = {
        key: arguments[key]
        for key in (
            "underlying", "exchange", "expiry_date", "as_of", "model", "max_age_seconds",
            "max_spread_bps", "min_open_interest", "min_volume", "actor", "run_key",
        )
        if key in arguments
    }
    payload.update({
        "paper_only": True,
        "live_execution_allowed": False,
        "capital_action_allowed": False,
    })
    return tool_result(post_api_json("/api/options/institutional-analytics/run", payload, timeout=620))


def run_option_acceptance(arguments: dict) -> dict:
    payload = {
        key: arguments[key]
        for key in ("exchange", "underlying", "expiry_date", "window_start", "window_end", "run_key", "actor")
        if key in arguments
    }
    payload.setdefault("actor", "Options Data Quality Agent")
    payload["paper_only"] = True
    payload["live_execution_allowed"] = False
    payload["capital_action_allowed"] = False
    payload["broker_write_allowed"] = False
    return tool_result(post_api_json("/api/options/institutional-analytics/acceptance/run", payload, timeout=180))


def run_office_operability_acceptance(arguments: dict) -> dict:
    payload = {
        key: arguments[key]
        for key in ("run_key", "actor")
        if key in arguments
    }
    payload.setdefault("actor", "Jarvis")
    payload["live_execution_allowed"] = False
    payload["capital_action_allowed"] = False
    payload["broker_write_allowed"] = False
    return tool_result(post_api_json("/api/office/operability/acceptance/run", payload, timeout=180))


def materialize_institutional_options(arguments: dict) -> dict:
    payload = {
        "limit": arguments.get("limit") or 20,
        "interval_seconds": arguments.get("interval_seconds") or 300,
        "actor": arguments.get("actor") or "Options Data Quality Agent",
    }
    return tool_result(post_api_json("/api/options/institutional-analytics/materialize", payload, timeout=320))


def refresh_option_valuation_sources(arguments: dict) -> dict:
    payload = {
        "sources": arguments.get("sources") or ["rate", "dividends"],
        "actor": arguments.get("actor") or "Options Data Quality Agent",
        "broker_write_allowed": False,
        "capital_action_allowed": False,
    }
    return tool_result(post_api_json("/api/options/valuation-sources/refresh", payload, timeout=200))


def upsert_option_valuation_policy(arguments: dict) -> dict:
    payload = {
        key: arguments[key]
        for key in (
            "policy_key", "provider", "exchange", "underlying", "model_family", "risk_free_rate",
            "dividend_yield", "rate_observation_id", "dividend_observation_id",
            "effective_from", "expires_at", "operator_confirmed",
            "day_count_convention", "expiry_local_time", "expiry_timezone", "assumptions", "actor",
        )
        if key in arguments
    }
    payload.setdefault("actor", "Options Data Quality Agent")
    payload["broker_write_allowed"] = False
    payload["capital_action_allowed"] = False
    return tool_result(post_api_json("/api/options/valuation-policy/upsert", payload, timeout=120))


def import_sector_intelligence_package(arguments: dict) -> dict:
    payload = {
        "package": arguments.get("package"),
        "persist": arguments.get("persist") is True,
        "actor": arguments.get("actor") or "Sector Data Steward",
    }
    return tool_result(post_api_json("/api/sector-intelligence/import", payload, timeout=320))


def institutional_portfolio_risk(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=80)
    return tool_result(
        {
            "run": run_psql_json(
                """
                SELECT id, run_key, run_status, methodology, lookback_days,
                       simulation_count, random_seed, position_as_of,
                       market_data_as_of, source_position_count, source_symbol_count,
                       covered_symbol_count, uncovered_symbol_count, gross_exposure,
                       covered_exposure, uncovered_exposure, coverage_pct,
                       assumptions, warnings, summary, artifact_path,
                       created_by, started_at, finished_at, error_message
                FROM risk.v_latest_portfolio_risk_run
                LIMIT 1
                """
            ),
            "metrics": run_psql_json(
                f"""
                SELECT *
                FROM risk.v_latest_portfolio_risk_metrics
                ORDER BY CASE scope_type WHEN 'portfolio' THEN 1 WHEN 'book' THEN 2 ELSE 3 END,
                         scope_name
                LIMIT {limit}
                """
            ),
            "stress": run_psql_json(
                f"""
                SELECT *
                FROM risk.v_latest_portfolio_stress_results
                ORDER BY CASE scope_type WHEN 'portfolio' THEN 1 WHEN 'book' THEN 2 ELSE 3 END,
                         stressed_return_pct
                LIMIT {limit}
                """
            ),
            "liquidity": run_psql_json(
                f"""
                SELECT *
                FROM risk.v_latest_position_liquidity
                ORDER BY CASE scope_type WHEN 'portfolio' THEN 1 WHEN 'book' THEN 2 ELSE 3 END,
                         CASE liquidity_bucket WHEN 'unavailable' THEN 1 ELSE 2 END,
                         estimated_days_to_liquidate DESC NULLS FIRST,
                         gross_exposure DESC
                LIMIT {limit}
                """
            ),
            "factors": run_psql_json(
                f"""
                SELECT *
                FROM risk.v_latest_factor_risk_attribution
                ORDER BY CASE scope_type WHEN 'portfolio' THEN 1 WHEN 'book' THEN 2 ELSE 3 END,
                         contribution_pct DESC NULLS LAST, factor_name
                LIMIT {limit}
                """
            ),
            "summary": run_psql_json(
                """
                SELECT metric, value, interpretation
                FROM risk.v_institutional_risk_summary
                ORDER BY metric
                """
            ),
            "capital_action_allowed": False,
            "live_execution_allowed": False,
        }
    )


def capital_allocation_control_board(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=120)
    return tool_result(
        {
            "summary": run_psql_json(
                "SELECT metric, value, interpretation FROM books.v_capital_allocation_control_summary ORDER BY metric"
            ),
            "control_board": run_psql_json(
                f"SELECT * FROM books.v_capital_policy_control_board ORDER BY client_name, book_name LIMIT {limit}"
            ),
            "analysis": run_psql_json(
                f"SELECT * FROM books.v_capital_allocation_analysis ORDER BY run_id DESC, abs(drift_pct) DESC LIMIT {limit}"
            ),
            "committee": run_psql_json(
                f"SELECT * FROM books.v_capital_committee_queue ORDER BY updated_at DESC LIMIT {limit}"
            ),
            "capital_action_allowed": False,
            "live_execution_allowed": False,
        }
    )


def model_runtime_control(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=100)
    return tool_result(
        {
            "summary": run_psql_json(
                "SELECT metric, value, interpretation FROM agent.v_model_runtime_control_summary ORDER BY metric"
            ),
            "routes": run_psql_json(
                "SELECT * FROM agent.v_model_route_runtime_control ORDER BY runtime_status, route_name"
            ),
            "privacy_policies": run_psql_json(
                "SELECT * FROM agent.model_privacy_policies ORDER BY privacy_class"
            ),
            "agent_assignments": run_psql_json(
                f"SELECT * FROM agent.v_agent_model_matrix ORDER BY department, agent_name LIMIT {limit}"
            ),
            "cost_caps": run_psql_json(
                f"SELECT * FROM agent.v_agent_model_cost_cap_status ORDER BY department, agent_name LIMIT {limit}"
            ),
            "call_decisions": run_psql_json(
                f"SELECT * FROM agent.v_model_call_control ORDER BY created_at DESC LIMIT {limit}"
            ),
            "raw_prompt_exposed": False,
            "autonomous_cloud_allowed": False,
            "capital_action_allowed": False,
            "live_execution_allowed": False,
        }
    )


def agent_model_assignment_completeness(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=100)
    return tool_result(
        {
            "summary": run_psql_json(
                "SELECT * FROM agent.v_agent_model_assignment_completeness"
            ),
            "incomplete_assignments": run_psql_json(
                f"""
                SELECT agent_name, department, display_title, primary_route,
                       model_key, assigned_provider, assigned_model, model_status,
                       fallback_route, escalation_route, cost_policy
                FROM agent.v_agent_model_matrix
                WHERE primary_route IS NULL OR model_key IS NULL
                ORDER BY department, agent_name
                LIMIT {limit}
                """
            ),
            "raw_secrets_allowed": False,
            "autonomous_cloud_allowed": False,
            "live_execution_allowed": False,
        }
    )


def request_model_escalation(arguments: dict) -> dict:
    payload = {
        "decision_id": arguments.get("decision_id") or arguments.get("decisionId"),
        "reason": arguments.get("reason") or "Local model quality or capability was insufficient for this task.",
        "actor": arguments.get("actor") or "Devarsh",
    }
    return tool_result(post_api_json("/api/models/escalations/request", payload, timeout=90))


def propose_capital_policy(arguments: dict) -> dict:
    payload = dict(arguments)
    payload.setdefault("actor", "Capital Allocation Agent")
    return tool_result(post_api_json("/api/capital/policies/propose", payload, timeout=90))


def run_capital_allocation_analysis(arguments: dict) -> dict:
    payload = {
        "proposal_id": arguments.get("proposal_id") or arguments.get("proposalId"),
        "run_key": arguments.get("run_key") or arguments.get("runKey"),
        "minimum_coverage_pct": arguments.get("minimum_coverage_pct") or arguments.get("minimumCoveragePct") or 80,
        "actor": arguments.get("actor") or "Capital Allocation Agent",
    }
    return tool_result(post_api_json("/api/capital/analysis/run", payload, timeout=200))


def decide_capital_committee(arguments: dict) -> dict:
    payload = {
        "review_id": arguments.get("review_id") or arguments.get("reviewId"),
        "decision": arguments.get("decision"),
        "decision_notes": arguments.get("decision_notes") or arguments.get("decisionNotes"),
        "actor": arguments.get("actor") or "Charlie Munger",
    }
    return tool_result(post_api_json("/api/capital/committee/decision", payload, timeout=90))


def strategy_quant_analytics(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50)
    run_key = str(arguments.get("run_key") or arguments.get("runKey") or "").strip()
    run_where = f"WHERE run_key = {sql_literal(run_key)}" if run_key else ""
    return tool_result(
        {
            "runs": run_psql_json(
                f"""
                SELECT id, run_key, run_name, strategy_ids, timeframe, status,
                       metrics, diagnostics, quality_flags, artifact_path,
                       created_by, started_at, finished_at, regime_rows,
                       factor_rows, capacity_rows, correlation_rows, optimizer_rows
                FROM strategy.v_quant_analytics_runs
                {run_where}
                ORDER BY finished_at DESC NULLS LAST, started_at DESC
                LIMIT {limit}
                """
            ),
            "regime_performance": run_psql_json(
                f"""
                SELECT run_key, strategy_id, candidate_key, strategy_name,
                       regime_label, bars, total_return, average_return,
                       volatility, win_rate, max_drawdown
                FROM strategy.v_regime_performance_splits
                {run_where}
                ORDER BY created_at DESC, strategy_name, regime_label
                LIMIT {limit}
                """
            ),
            "factor_attribution": run_psql_json(
                f"""
                SELECT run_key, strategy_id, candidate_key, strategy_name,
                       factor_name, exposure, contribution, method, diagnostics
                FROM strategy.v_factor_attribution
                {run_where}
                ORDER BY created_at DESC, strategy_name, factor_name
                LIMIT {limit}
                """
            ),
            "capacity_liquidity": run_psql_json(
                f"""
                SELECT run_key, strategy_id, candidate_key, strategy_name,
                       symbol, timeframe, bars, average_traded_value,
                       capacity_notional, liquidity_status
                FROM strategy.v_capacity_liquidity_checks
                {run_where}
                ORDER BY created_at DESC, strategy_name, symbol
                LIMIT {limit}
                """
            ),
            "correlations": run_psql_json(
                f"""
                SELECT run_key, strategy_id_a, strategy_name_a, strategy_id_b,
                       strategy_name_b, correlation, overlap_bars
                FROM strategy.v_strategy_correlation_matrix
                {run_where}
                ORDER BY created_at DESC, strategy_name_a, strategy_name_b
                LIMIT {limit}
                """
            ),
            "optimizer": run_psql_json(
                f"""
                SELECT run_key, optimizer_method, candidate_count, weights,
                       expected_return, expected_volatility, sharpe_proxy,
                       status, diagnostics, created_at
                FROM strategy.v_strategy_portfolio_optimizer_runs
                {run_where}
                ORDER BY created_at DESC
                LIMIT {limit}
                """
            ),
        }
    )


def run_strategy_portfolio_allocation(arguments: dict) -> dict:
    payload = {
        "allocation_key": arguments.get("allocation_key") or arguments.get("allocationKey"),
        "analytics_run_key": arguments.get("analytics_run_key") or arguments.get("analyticsRunKey"),
        "timeframe": arguments.get("timeframe") or "5m",
        "capital_base": arguments.get("capital_base") or arguments.get("capitalBase") or 1_000_000,
        "max_weight": arguments.get("max_weight") or arguments.get("maxWeight") or 0.35,
        "ruin_threshold_pct": arguments.get("ruin_threshold_pct") or arguments.get("ruinThresholdPct") or 0.20,
        "horizon_bars": arguments.get("horizon_bars") or arguments.get("horizonBars") or 252,
        "simulation_count": arguments.get("simulation_count") or arguments.get("simulationCount") or 1000,
        "seed": arguments.get("seed") or 260706,
        "actor": arguments.get("actor") or "Strategy Portfolio Manager",
    }
    result = post_api_json("/api/strategy/portfolio-allocation/run", payload, timeout=260)
    return tool_result(result)


def strategy_portfolio_allocation(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50)
    allocation_key = str(arguments.get("allocation_key") or arguments.get("allocationKey") or "").strip()
    where = f"WHERE allocation_key = {sql_literal(allocation_key)}" if allocation_key else ""
    return tool_result(
        {
            "runs": run_psql_json(
                f"""
                SELECT id, allocation_key, analytics_run_id, analytics_run_key,
                       optimizer_run_id, capital_base, timeframe, status,
                       allocation_method, expected_return, expected_volatility,
                       expected_max_drawdown, quality_flags, artifact_path,
                       allocation_rows, ruin_metric_rows, constraints,
                       diagnostics, created_at
                FROM strategy.v_strategy_portfolio_allocation_runs
                {where}
                ORDER BY created_at DESC
                LIMIT {limit}
                """
            ),
            "allocations": run_psql_json(
                f"""
                SELECT allocation_key, strategy_id, candidate_key, strategy_name,
                       target_weight, target_notional, expected_return,
                       expected_volatility, risk_contribution, allocation_status,
                       diagnostics, created_at
                FROM strategy.v_strategy_portfolio_allocations
                {where}
                ORDER BY created_at DESC, target_weight DESC
                LIMIT {limit}
                """
            ),
            "probability_of_ruin": run_psql_json(
                f"""
                SELECT allocation_key, metric_scope, strategy_id, candidate_key,
                       strategy_name, horizon_bars, simulation_count,
                       starting_capital, ruin_threshold_pct, ruin_probability,
                       expected_terminal_value, terminal_p05, terminal_p50,
                       terminal_p95, max_drawdown_p95, method, quality_flags,
                       diagnostics, created_at
                FROM strategy.v_probability_of_ruin_metrics
                {where}
                ORDER BY created_at DESC, metric_scope, strategy_name
                LIMIT {limit}
                """
            ),
        }
    )


def run_strategy_retirement_review(arguments: dict) -> dict:
    payload = {
        "review_key_prefix": arguments.get("review_key_prefix") or arguments.get("reviewKeyPrefix") or "retire",
        "analytics_run_key": arguments.get("analytics_run_key") or arguments.get("analyticsRunKey"),
        "allocation_key": arguments.get("allocation_key") or arguments.get("allocationKey"),
        "actor": arguments.get("actor") or "Strategy Retirement Agent",
    }
    result = post_api_json("/api/strategy/retirement/run", payload, timeout=200)
    return tool_result(result)


def strategy_retirement_queue(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50)
    review_status = str(arguments.get("review_status") or arguments.get("reviewStatus") or "").strip()
    recommended_action = str(arguments.get("recommended_action") or arguments.get("recommendedAction") or "").strip()
    where_parts = []
    if review_status:
        where_parts.append(f"review_status = {sql_literal(review_status)}")
    if recommended_action:
        where_parts.append(f"recommended_action = {sql_literal(recommended_action)}")
    where = "WHERE " + " AND ".join(where_parts) if where_parts else ""
    return tool_result(
        {
            "retirement_queue": run_psql_json(
                f"""
                SELECT review_key, strategy_id, candidate_key, strategy_name,
                       analytics_run_key, allocation_key, review_status,
                       recommended_action, severity, trigger_reasons,
                       assigned_agents, open_assignments, total_assignments,
                       created_at, updated_at
                FROM strategy.v_strategy_retirement_queue
                {where}
                ORDER BY created_at DESC, severity DESC
                LIMIT {limit}
                """
            ),
            "specialist_assignments": run_psql_json(
                f"""
                SELECT assignment_key, review_key, candidate_key, strategy_name,
                       specialist_agent, character_name, office_location,
                       assignment_type, status, priority, findings,
                       recommended_action, created_at, updated_at
                FROM strategy.v_quant_specialist_assignments
                ORDER BY created_at DESC, priority DESC, specialist_agent
                LIMIT {limit}
                """
            ),
            "quant_lab_dashboard_v2": run_psql_json(
                f"""
                SELECT strategy_id, candidate_key, strategy_name, parse_status,
                       data_quality_status, allocation_key, target_weight,
                       target_notional, ruin_probability, review_status,
                       recommended_action, severity, trigger_reasons,
                       assigned_agents, open_assignments, total_assignments,
                       updated_at
                FROM strategy.v_quant_lab_dashboard_v2
                ORDER BY updated_at DESC
                LIMIT {limit}
                """
            ),
        }
    )


def run_model_validation_sweep(arguments: dict) -> dict:
    payload = {
        "validation_key_prefix": arguments.get("validation_key_prefix") or arguments.get("validationKeyPrefix") or "modelval",
        "actor": arguments.get("actor") or "Model Validation Agent",
        "limit": arguments.get("limit") or 25,
    }
    result = post_api_json("/api/strategy/model-validation/sweep", payload, timeout=200)
    return tool_result(result)


def model_validation_dashboard(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50)
    gate_status = str(arguments.get("validation_gate_status") or arguments.get("validationGateStatus") or "").strip()
    where = f"WHERE validation_gate_status = {sql_literal(gate_status)}" if gate_status else ""
    return tool_result(
        {
            "model_validation_dashboard": run_psql_json(
                f"""
                SELECT strategy_id, candidate_key, strategy_name, parse_status,
                       data_quality_status, latest_backtest_run_id,
                       latest_optimization_run_id, validation_review_id,
                       review_status, decision, leakage_risk, overfit_risk,
                       required_fixes, validation_gate_status,
                       validation_gate_reason, retirement_recommended_action,
                       live_execution_allowed, updated_at
                FROM strategy.v_model_validation_dashboard
                {where}
                ORDER BY updated_at DESC, strategy_id DESC
                LIMIT {limit}
                """
            ),
            "promotion_board": run_psql_json(
                f"""
                SELECT strategy_id, candidate_key, strategy_name,
                       validation_gate_status, validation_decision,
                       committee_decision_status, paper_monitor_status,
                       limited_live_request_status, promotion_stage,
                       next_required_action, broker_order_allowed,
                       autonomous_live_execution_allowed, updated_at
                FROM strategy.v_strategy_promotion_board
                ORDER BY updated_at DESC, strategy_id DESC
                LIMIT {limit}
                """
            ),
        }
    )


def strategy_promotion_board(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50)
    stage = str(arguments.get("promotion_stage") or arguments.get("promotionStage") or "").strip()
    where = f"WHERE promotion_stage = {sql_literal(stage)}" if stage else ""
    return tool_result(
        {
            "promotion_board": run_psql_json(
                f"""
                SELECT strategy_id, candidate_key, strategy_name,
                       validation_gate_status, validation_gate_reason,
                       validation_decision, committee_review_id,
                       committee_decision_status, paper_monitor_session_id,
                       paper_monitor_status, limited_live_request_id,
                       limited_live_request_status, promotion_stage,
                       next_required_action, broker_order_allowed,
                       autonomous_live_execution_allowed, updated_at
                FROM strategy.v_strategy_promotion_board
                {where}
                ORDER BY updated_at DESC, strategy_id DESC
                LIMIT {limit}
                """
            )
        }
    )


def strategy_arsenal_control_board(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=80, maximum=200)
    origin = str(arguments.get("origin_type") or arguments.get("originType") or "").strip()
    stage = str(arguments.get("promotion_stage") or arguments.get("promotionStage") or "").strip()
    query = str(arguments.get("query") or "").strip()
    clauses: list[str] = []
    if origin:
        clauses.append(f"origin_type = {sql_literal(origin)}")
    if stage:
        clauses.append(f"promotion_stage = {sql_literal(stage)}")
    if query:
        clauses.append(
            "(strategy_name ILIKE " + sql_literal(f"%{query}%")
            + " OR candidate_key ILIKE " + sql_literal(f"%{query}%")
            + " OR array_to_string(symbols, ',') ILIKE " + sql_literal(f"%{query}%") + ")"
        )
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result(
        {
            "summary": run_psql_json(
                "SELECT metric, value, interpretation FROM strategy.v_strategy_arsenal_canonical_summary ORDER BY metric"
            ),
            "control_board": run_psql_json(
                f"""
                SELECT candidate_id, candidate_key, strategy_name, candidate_status,
                       owner_agent, universe, timeframe, strategy_family,
                       asset_class, symbols, edge_hypothesis, origin_type,
                       source_kind, source_ref, discovery_candidate_id,
                       triage_decision, triage_status, parse_status,
                       data_quality_status, backtest_runs, optimization_runs,
                       validation_reviews, validation_gate_status,
                       validation_gate_reason, required_fixes,
                       committee_decision_status, paper_monitor_status,
                       limited_live_request_status, promotion_stage,
                       next_required_action, gates_passed, gates_total,
                       gate_flags, broker_order_allowed,
                       autonomous_live_execution_allowed, open_tasks,
                       evidence, updated_at, opportunity_fingerprint,
                       source_fingerprint, discovery_seen_count,
                       discovery_last_seen_at, duplicate_candidate_count
                FROM strategy.v_strategy_arsenal_canonical_control_board
                {where}
                ORDER BY updated_at DESC NULLS LAST, candidate_id DESC
                LIMIT {limit}
                """
            ),
            "execution_control": run_psql_json(
                """
                SELECT global_execution_locked, broker_execution_policy,
                       paper_trading_allowed, limited_live_allowed,
                       live_broker_writes_allowed, lock_reason, updated_at
                FROM trading.v_execution_control_state
                LIMIT 1
                """
            ),
        }
    )


def run_user_defined_strategy_optimizer(arguments: dict) -> dict:
    payload = {
        "run_key": arguments.get("run_key") or arguments.get("runKey") or "user_strategy_optimizer_mcp",
        "actor": arguments.get("actor") or "Devarsh",
        "strategy_name": arguments.get("strategy_name") or arguments.get("strategyName"),
        "intake_text": arguments.get("intake_text") or arguments.get("intakeText"),
        "dsl_text": arguments.get("dsl_text") or arguments.get("dslText"),
        "asset_class": arguments.get("asset_class") or arguments.get("assetClass") or "equity",
        "symbols": arguments.get("symbols") or [],
        "universe": arguments.get("universe") or "NSE",
        "timeframe": arguments.get("timeframe") or "5m",
        "template": arguments.get("template") or "momentum",
        "constraints_text": arguments.get("constraints_text") or arguments.get("constraintsText"),
        "risk_notes": arguments.get("risk_notes") or arguments.get("riskNotes"),
        "cost_bps": arguments.get("cost_bps") or arguments.get("costBps") or 3,
        "slippage_bps": arguments.get("slippage_bps") or arguments.get("slippageBps") or 2,
        "max_symbols": arguments.get("max_symbols") or arguments.get("maxSymbols") or 14,
        "min_rows_per_symbol": arguments.get("min_rows_per_symbol") or arguments.get("minRowsPerSymbol") or 50,
        "min_total_rows": arguments.get("min_total_rows") or arguments.get("minTotalRows"),
    }
    result = post_api_json("/api/strategy/user-defined-optimizer/run", payload, timeout=380)
    return tool_result(result)


def user_defined_strategy_optimizer_runs(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=25)
    status = str(arguments.get("status") or "").strip()
    where = f"WHERE status = {sql_literal(status)}" if status else ""
    return tool_result(
        {
            "user_defined_optimizer_runs": run_psql_json(
                f"""
                SELECT run_key, strategy_name, candidate_id, candidate_key,
                       backtest_run_id, optimization_run_id, status,
                       current_stage, requested_template, requested_timeframe,
                       requested_symbols, failure_reason, artifact_path,
                       broker_order_allowed, autonomous_live_execution_allowed,
                       created_by, started_at, finished_at, created_at
                FROM strategy.v_user_defined_optimizer_runs
                {where}
                ORDER BY created_at DESC
                LIMIT {limit}
                """
            )
        }
    )


def run_strategy_discovery(arguments: dict) -> dict:
    payload = {
        "run_key": arguments.get("run_key") or arguments.get("runKey") or "strategy_discovery_mcp",
        "actor": arguments.get("actor") or "Strategy Discovery Agent",
        "sources": arguments.get("sources") or "research,journals,signals,components",
        "per_source_limit": arguments.get("per_source_limit") or arguments.get("perSourceLimit") or 8,
        "max_candidates": arguments.get("max_candidates") or arguments.get("maxCandidates") or 16,
        "route_top": arguments.get("route_top") or arguments.get("routeTop") or 2,
    }
    result = post_api_json("/api/strategy/discovery/run", payload, timeout=620)
    return tool_result(result)


def strategy_discovery_runs(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=25)
    status = str(arguments.get("status") or "").strip()
    where = f"WHERE status = {sql_literal(status)}" if status else ""
    return tool_result(
        {
            "discovery_runs": run_psql_json(
                f"""
                SELECT run_key, status, source_scope, discovered_count,
                       generated_idea_count, optimizer_routed_count,
                       artifact_path, created_by, started_at, finished_at, created_at
                FROM strategy.v_strategy_discovery_runs
                {where}
                ORDER BY created_at DESC
                LIMIT {limit}
                """
            ),
            "discovery_candidates": run_psql_json(
                f"""
                SELECT run_key, title, source_kind, source_ref, symbols,
                       timeframe, template, priority_score, route_to_optimizer,
                       idea_key, optimizer_run_key, optimizer_status,
                       backtest_run_id, optimization_run_id, research_gate,
                       next_required_action, broker_order_allowed,
                       autonomous_live_execution_allowed, created_at
                FROM strategy.v_strategy_discovery_canonical_queue
                ORDER BY created_at DESC, priority_score DESC NULLS LAST
                LIMIT {limit}
                """
            ),
        }
    )


def resolve_strategy_discovery_triage(arguments: dict) -> dict:
    payload = {
        "discovery_candidate_id": arguments.get("discovery_candidate_id") or arguments.get("discoveryCandidateId") or arguments.get("candidate_id") or arguments.get("candidateId"),
        "decision": arguments.get("decision") or "request_more_evidence",
        "actor": arguments.get("actor") or "Charlie Munger",
        "notes": arguments.get("notes") or arguments.get("decision_notes") or arguments.get("decisionNotes") or "",
    }
    result = post_api_json("/api/strategy/discovery/triage/resolve", payload, timeout=220)
    return tool_result(result)


def strategy_discovery_triage_queue(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=25)
    decision = str(arguments.get("decision") or "").strip()
    where = f"WHERE triage_decision = {sql_literal(decision)}" if decision else ""
    return tool_result(
        {
            "triage_queue": run_psql_json(
                f"""
                SELECT id, run_key, discovery_key, source_kind, source_ref,
                       title, symbols, timeframe, template, priority_score,
                       risk_score, optimizer_status, backtest_run_id,
                       optimization_run_id, research_gate, next_required_action,
                       discovery_status, triage_decision, triage_status,
                       routed_to_agent, inbox_item_id, approval_id,
                       committee_review_id, recommended_triage_action,
                       broker_order_allowed, autonomous_live_execution_allowed,
                       created_at
                FROM strategy.v_strategy_discovery_canonical_queue
                {where}
                ORDER BY
                    CASE WHEN triage_decision = 'unreviewed' THEN 0 ELSE 1 END,
                    priority_score DESC NULLS LAST,
                    created_at DESC
                LIMIT {limit}
                """
            ),
            "recent_decisions": run_psql_json(
                f"""
                SELECT discovery_candidate_id, discovery_key, title, decision,
                       routed_to_agent, inbox_item_id, inbox_status,
                       approval_id, approval_status, committee_review_id,
                       committee_review_status, decision_notes, decided_by,
                       created_at, broker_order_allowed,
                       autonomous_live_execution_allowed
                FROM strategy.v_strategy_discovery_triage_decisions
                ORDER BY created_at DESC
                LIMIT {limit}
                """
            ),
        }
    )


def strategy_discovery_governance(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50, maximum=200)
    return tool_result(
        {
            "summary": run_psql_json(
                "SELECT metric, value, interpretation FROM strategy.v_strategy_discovery_governance_summary ORDER BY metric"
            ),
            "canonical_opportunities": run_psql_json(
                f"""
                SELECT id, opportunity_fingerprint, source_fingerprint,
                       title, symbols, universe, timeframe, template,
                       priority_score, risk_score, optimizer_status,
                       research_gate, next_required_action,
                       triage_decision, triage_status, first_seen_at,
                       last_seen_at, seen_count, suppressed_duplicate_count,
                       broker_order_allowed, autonomous_live_execution_allowed
                FROM strategy.v_strategy_discovery_canonical_queue
                ORDER BY priority_score DESC NULLS LAST, last_seen_at DESC
                LIMIT {limit}
                """
            ),
            "execution_control": run_psql_json(
                """
                SELECT global_execution_locked, broker_execution_policy,
                       paper_trading_allowed, limited_live_allowed,
                       live_broker_writes_allowed, lock_reason, updated_at
                FROM trading.v_execution_control_state
                LIMIT 1
                """
            ),
        }
    )


def build_strategy_idea_dossiers(arguments: dict) -> dict:
    payload = {
        "run_key": arguments.get("run_key") or arguments.get("runKey") or "strategy_dossiers_mcp",
        "actor": arguments.get("actor") or "Strategy Dossier Agent",
        "limit": arguments.get("limit") or 250,
        "max_dossiers": arguments.get("max_dossiers") or arguments.get("maxDossiers") or 100,
        "no_notes": bool(arguments.get("no_notes") or arguments.get("noNotes") or False),
    }
    result = post_api_json("/api/strategy/idea-dossiers/build", payload, timeout=340)
    return tool_result(result)


def search_strategy_idea_dossiers(arguments: dict) -> dict:
    payload = {
        "query": arguments.get("query") or arguments.get("query_text") or arguments.get("queryText") or "",
        "run_key": arguments.get("run_key") or arguments.get("runKey") or "strategy_dossier_search_mcp",
        "actor": arguments.get("actor") or "Strategy Dossier Search Agent",
        "limit": arguments.get("limit") or 8,
    }
    result = post_api_json("/api/strategy/idea-dossiers/search", payload, timeout=150)
    return tool_result(result)


def run_strategy_dossier_action(arguments: dict) -> dict:
    payload = {
        "dossier_id": arguments.get("dossier_id") or arguments.get("dossierId") or arguments.get("id"),
        "action": arguments.get("action") or arguments.get("action_type") or arguments.get("actionType"),
        "run_key": arguments.get("run_key") or arguments.get("runKey") or "strategy_dossier_action_mcp",
        "actor": arguments.get("actor") or "Charlie Munger",
        "notes": arguments.get("notes") or arguments.get("decision_notes") or "",
    }
    result = post_api_json("/api/strategy/idea-dossiers/action", payload, timeout=260)
    return tool_result(result)


def strategy_dossier_actions(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=25)
    return tool_result(
        {
            "actions": run_psql_json(
                f"""
                SELECT id, dossier_id, dossier_key, dossier_title,
                       action_key, action_type, status, target_agent,
                       target_table, target_id, output_payload,
                       error_message, created_by, created_at,
                       broker_order_allowed, autonomous_live_execution_allowed
                FROM strategy.v_idea_dossier_actions
                ORDER BY created_at DESC, id DESC
                LIMIT {limit}
                """
            )
        }
    )


def strategy_idea_dossiers(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=25)
    status = str(arguments.get("status") or "").strip()
    where = f"WHERE status = {sql_literal(status)}" if status else ""
    return tool_result(
        {
            "dossiers": run_psql_json(
                f"""
                SELECT id, dossier_key, title, symbols, source_kind,
                       source_ref, status, latest_triage_decision,
                       recommended_next_action, discovery_count,
                       generated_idea_count, optimizer_run_count,
                       triage_decision_count, committee_review_count,
                       inbox_item_count, priority_score, risk_score,
                       note_path, qdrant_index_status,
                       broker_order_allowed, autonomous_live_execution_allowed,
                       updated_at
                FROM strategy.v_idea_dossiers
                {where}
                ORDER BY updated_at DESC, priority_score DESC NULLS LAST
                LIMIT {limit}
                """
            ),
            "build_runs": run_psql_json(
                f"""
                SELECT run_key, status, dossiers_seen, dossiers_upserted,
                       links_upserted, notes_written, error_message,
                       started_at, finished_at, duration_ms
                FROM strategy.v_idea_dossier_build_runs
                ORDER BY started_at DESC, id DESC
                LIMIT {limit}
                """
            ),
            "search_runs": run_psql_json(
                f"""
                SELECT run_key, query_text, status, search_mode,
                       embedding_model, qdrant_available, fallback_used,
                       match_count, error_message, started_at, finished_at,
                       duration_ms
                FROM strategy.v_idea_dossier_search_runs
                ORDER BY started_at DESC, id DESC
                LIMIT {limit}
                """
            ),
        }
    )


def ingest_market_news(arguments: dict) -> dict:
    payload = {
        "run_key": arguments.get("run_key") or arguments.get("runKey") or "market_news_mcp",
        "actor": arguments.get("actor") or "News Analyst",
        "feed_limit": arguments.get("feed_limit") or arguments.get("feedLimit") or 12,
        "per_feed": arguments.get("per_feed") or arguments.get("perFeed") or 8,
        "timeout": arguments.get("timeout") or 12,
    }
    if arguments.get("feed_keys") or arguments.get("feedKeys"):
        payload["feed_keys"] = arguments.get("feed_keys") or arguments.get("feedKeys")
    result = post_api_json("/api/market/news/ingest", payload, timeout=260)
    return tool_result(result)


def run_strategy_discovery_scheduler(arguments: dict) -> dict:
    payload = {
        "run_key": arguments.get("run_key") or arguments.get("runKey") or "strategy_discovery_scheduler_mcp",
        "actor": arguments.get("actor") or "Strategy Discovery Agent",
        "interval_seconds": arguments.get("interval_seconds") or arguments.get("intervalSeconds") or 3600,
        "sources": arguments.get("sources") or "research,journals,signals,components",
        "per_source_limit": arguments.get("per_source_limit") or arguments.get("perSourceLimit") or 8,
        "max_candidates": arguments.get("max_candidates") or arguments.get("maxCandidates") or 16,
        "route_top": arguments.get("route_top") or arguments.get("routeTop") or 1,
        "news_feed_limit": arguments.get("news_feed_limit") or arguments.get("newsFeedLimit") or 12,
        "news_per_feed": arguments.get("news_per_feed") or arguments.get("newsPerFeed") or 6,
        "enable_filings": bool(arguments.get("enable_filings") or arguments.get("enableFilings") or False),
        "filing_lookback_days": arguments.get("filing_lookback_days") or arguments.get("filingLookbackDays") or 2,
        "filing_limit": arguments.get("filing_limit") or arguments.get("filingLimit") or 250,
        "filing_timeout": arguments.get("filing_timeout") or arguments.get("filingTimeout") or 300,
        "enable_filing_extraction": bool(arguments.get("enable_filing_extraction") or arguments.get("enableFilingExtraction") or False),
        "filing_extraction_limit": arguments.get("filing_extraction_limit") or arguments.get("filingExtractionLimit") or 4,
        "filing_extraction_timeout": arguments.get("filing_extraction_timeout") or arguments.get("filingExtractionTimeout") or 300,
        "disable_news": bool(arguments.get("disable_news") or arguments.get("disableNews") or False),
    }
    if arguments.get("news_feed_keys") or arguments.get("newsFeedKeys"):
        payload["news_feed_keys"] = arguments.get("news_feed_keys") or arguments.get("newsFeedKeys")
    result = post_api_json("/api/strategy/discovery/scheduler/run", payload, timeout=920)
    return tool_result(result)


def strategy_discovery_scheduler_runs(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=25)
    return tool_result(
        {
            "scheduler_runs": run_psql_json(
                f"""
                SELECT run_key, status, scheduler_interval_seconds,
                       discovery_run_key, discovery_status, discovered_count,
                       generated_idea_count, optimizer_routed_count,
                       adapter_summary, error_message, started_at, finished_at,
                       duration_ms, next_run_after
                FROM strategy.v_strategy_discovery_scheduler_runs
                ORDER BY started_at DESC, id DESC
                LIMIT {limit}
                """
            ),
            "news_ingestion_runs": run_psql_json(
                f"""
                SELECT run_key, status, feeds_checked, items_seen,
                       items_upserted, research_ideas_created,
                       inbox_items_created, error_message, started_at,
                       finished_at, duration_ms
                FROM market.v_news_ingestion_runs
                ORDER BY started_at DESC, id DESC
                LIMIT {limit}
                """
            ),
            "latest_news_items": run_psql_json(
                f"""
                SELECT source_name, title, source_url, published_at,
                       symbols, topics, relevance_score, captured_at
                FROM market.v_latest_news_items
                ORDER BY coalesce(published_at, captured_at) DESC, id DESC
                LIMIT {limit}
                """
            ),
            "filing_collector_runs": run_psql_json(
                f"""
                SELECT run_key, source_key, exchange, status, http_status,
                       rows_seen, rows_upserted, events_upserted,
                       inbox_items_created, error_message, started_at, finished_at
                FROM research.v_filing_collector_runs
                ORDER BY started_at DESC, id DESC
                LIMIT {limit}
                """
            ),
            "filing_pdf_extraction_runs": run_psql_json(
                f"""
                SELECT filing_id, source_name, exchange, symbol, status,
                       parser_name, bytes_downloaded, page_count, extracted_chars,
                       event_type_before, event_type_after, error_message,
                       started_at, finished_at
                FROM research.v_filing_pdf_extraction_runs
                ORDER BY started_at DESC, id DESC
                LIMIT {limit}
                """
            ),
            "news_source_checks": run_psql_json(
                f"""
                SELECT DISTINCT ON (source_key)
                       source_key, status, http_status, latency_ms, rows_seen,
                       error_message, checked_at
                FROM core.data_source_checks
                WHERE check_type = 'rss_http'
                ORDER BY source_key, checked_at DESC, id DESC
                LIMIT {limit}
                """
            ),
        }
    )


def runtime_daemon_health(arguments: dict) -> dict:
    return tool_result(
        {
            "runtime_daemons": run_psql_json(
                """
                SELECT daemon_key, instance_id, host_name, process_id,
                       reported_status, health_status, loop_interval_seconds,
                       enabled_workloads, last_pass_summary, last_error,
                       started_at, heartbeat_at, heartbeat_age_seconds, updated_at
                FROM core.v_runtime_daemon_health
                ORDER BY daemon_key
                """
            )
        }
    )


def agent_capability_readiness(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=120, maximum=200)
    return tool_result(
        {
            "summary": run_psql_json("SELECT * FROM agent.v_agent_operating_summary ORDER BY metric"),
            "employees": run_psql_json(
                f"""
                SELECT agent_name,display_title,department,readiness_status,operating_mode,
                       model_reasoning_ready,tools_ready,requested_tool_count,
                       resolved_tool_count,missing_tool_count,missing_tools,
                       completed_runs,operating_readiness_score
                FROM agent.v_agent_operating_readiness
                ORDER BY department,agent_name
                LIMIT {limit}
                """
            ),
            "activation": run_psql_json(
                f"""
                SELECT campaign_key,agent_name,department,status,operating_mode,
                       acceptance_checks,worker_run_id,finished_at
                FROM agent.v_employee_activation_status
                ORDER BY finished_at DESC NULLS LAST,agent_name
                LIMIT {limit}
                """
            ),
        }
    )


def fund_function_coverage(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=120, maximum=200)
    return tool_result(
        {
            "coverage": run_psql_json(
                f"""
                SELECT function_key,function_name,department_key,function_class,
                       criticality,objective,human_final_required,
                       live_execution_allowed,owner_count,reviewer_count,
                       challenger_count,assigned_agents,coverage_status
                FROM agent.v_fund_function_coverage
                ORDER BY department_key,function_name
                LIMIT {limit}
                """
            )
        }
    )


def macro_source_readiness(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=100, maximum=500)
    return tool_result(
        {
            "readiness": run_psql_json("SELECT * FROM market.v_macro_source_readiness ORDER BY source_key"),
            "observations": run_psql_json(
                f"""
                SELECT source_key,source_name,provider,series_key,series_name,
                       geography,observation_date,observation_value,unit,
                       frequency,source_url,retrieved_at
                FROM market.v_macro_observations
                ORDER BY observation_date DESC,series_key,geography
                LIMIT {limit}
                """
            ),
        }
    )


def ingest_public_macro_data(arguments: dict) -> dict:
    result = run_command([sys.executable, str(RUNTIME_ROOT / "scripts" / "ingest_public_macro_data.py")])
    payload: object = result
    if result.get("stdout"):
        try:
            payload = json.loads(str(result["stdout"]))
        except json.JSONDecodeError:
            payload = result
    if result.get("returncode") != 0:
        raise RuntimeError(result.get("stderr") or result.get("stdout") or "public macro ingestion failed")
    return tool_result(payload)


def run_trade_journal_strategy_mining(arguments: dict) -> dict:
    payload = {
        "run_key": arguments.get("run_key") or arguments.get("runKey") or "journal_mining_mcp",
        "actor": arguments.get("actor") or "Strategy Generator",
        "min_trades": arguments.get("min_trades") or arguments.get("minTrades") or 3,
        "max_patterns": arguments.get("max_patterns") or arguments.get("maxPatterns") or 10,
        "allow_thin_sample": bool(arguments.get("allow_thin_sample") or arguments.get("allowThinSample")),
    }
    result = post_api_json("/api/strategy/trade-journal-mining/run", payload, timeout=200)
    return tool_result(result)


def trade_journal_strategy_ideas(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50)
    research_gate = str(arguments.get("research_gate") or arguments.get("researchGate") or "").strip()
    where = f"WHERE research_gate = {sql_literal(research_gate)}" if research_gate else ""
    return tool_result(
        {
            "mining_runs": run_psql_json(
                f"""
                SELECT run_key, min_trades, status, generated_idea_count,
                       candidate_pattern_count, artifact_path, created_by,
                       started_at, finished_at, created_at
                FROM strategy.v_trade_journal_mining_runs
                ORDER BY created_at DESC
                LIMIT {limit}
                """
            ),
            "journal_strategy_ideas": run_psql_json(
                f"""
                SELECT run_key, pattern_key, symbol, setup_type, timeframe,
                       execution_mode, trade_count, win_rate, average_pnl,
                       status, idea_key, idea_title, idea_status, research_gate,
                       next_required_action, broker_order_allowed,
                       autonomous_live_execution_allowed, created_at
                FROM strategy.v_trade_journal_idea_generator_dashboard
                {where}
                LIMIT {limit}
                """
            ),
        }
    )


def resolve_strategy_id(arguments: dict) -> str:
    strategy_id = str(arguments.get("strategy_id") or "").strip()
    if strategy_id:
        return strategy_id
    strategy_key = str(arguments.get("candidate_key") or arguments.get("strategy_key") or "").strip()
    strategy_name = str(arguments.get("strategy_name") or "").strip()
    rows = run_psql_json(
        f"""
        SELECT id
        FROM strategy.strategy_candidates
        WHERE ({sql_literal(strategy_key)} <> '' AND candidate_key = {sql_literal(strategy_key)})
           OR ({sql_literal(strategy_name)} <> '' AND name = {sql_literal(strategy_name)})
        ORDER BY id DESC
        LIMIT 1
        """
    )
    if not rows:
        raise ValueError("strategy_id, candidate_key, or strategy_name must reference an existing strategy candidate")
    return str(rows[0]["id"])


def queue_strategy_backtest(arguments: dict) -> dict:
    strategy_id = resolve_strategy_id(arguments)
    actor = str(arguments.get("actor") or "Backtest Engineer").strip()
    rows = run_psql_json_statement(
        f"""
        WITH inserted AS (
            INSERT INTO strategy.backtest_runs (
                strategy_id, run_status, data_start, data_end, universe, timeframe,
                metrics, diagnostics, artifact_path
            )
            VALUES (
                {strategy_id},
                {sql_literal(arguments.get("run_status") or "queued")},
                {sql_literal(arguments.get("data_start"))}::date,
                {sql_literal(arguments.get("data_end"))}::date,
                {sql_literal(arguments.get("universe"))},
                {sql_literal(arguments.get("timeframe"))},
                {sql_jsonb(arguments.get("metrics"))},
                {sql_jsonb(arguments.get("diagnostics"))},
                {sql_literal(arguments.get("artifact_path"))}
            )
            RETURNING id, strategy_id, run_status, data_start, data_end, universe, timeframe, started_at, finished_at
        ),
        inbox_insert AS (
            INSERT INTO agent.inbox_items (
                title, owner_agent, status, priority, recommended_action, evidence, target_workspace
            )
            SELECT
                'Backtest queued for strategy ' || strategy_id::TEXT,
                'Backtest Engineer',
                'new',
                {sql_literal(arguments.get("priority") or "high")},
                'Run local backtest with explicit data lineage, transaction costs, and artifact output.',
                {sql_jsonb(arguments.get("evidence") or [])},
                'quant'
            FROM inserted
            WHERE {str(bool(arguments.get("create_inbox", True))).lower()}
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(final_rows)), '[]'::json)::text
        FROM (
            SELECT inserted.*, inbox_insert.id AS inbox_item_id
            FROM inserted
            LEFT JOIN inbox_insert ON true
        ) final_rows
        """
    )
    result = rows[0] if rows else {"error": "backtest not queued"}
    audit_mcp_call(
        tool_name="ai_os_queue_strategy_backtest",
        action_type="queue_strategy_backtest",
        permission_level="write_with_approval",
        actor=actor,
        target_table="strategy.backtest_runs",
        target_id=result.get("id") if isinstance(result, dict) else None,
        request_payload=arguments,
        result_payload=result,
    )
    return tool_result(result)


def record_strategy_optimization(arguments: dict) -> dict:
    strategy_id = resolve_strategy_id(arguments)
    actor = str(arguments.get("actor") or "Optimizer Agent").strip()
    rows = run_psql_json_statement(
        f"""
        WITH inserted AS (
            INSERT INTO strategy.optimization_runs (
                strategy_id, backtest_run_id, run_name, optimizer_type, status, objective,
                parameter_space, constraints, data_start, data_end, metrics, diagnostics,
                artifact_path, owner_agent, evidence, finished_at
            )
            VALUES (
                {strategy_id},
                {sql_literal(arguments.get("backtest_run_id"))}::bigint,
                {sql_literal(arguments.get("run_name") or "Optimization run")},
                {sql_literal(arguments.get("optimizer_type") or "parameter_search")},
                {sql_literal(arguments.get("status") or "queued")},
                {sql_literal(arguments.get("objective"))},
                {sql_jsonb(arguments.get("parameter_space"))},
                {sql_jsonb(arguments.get("constraints"))},
                {sql_literal(arguments.get("data_start"))}::date,
                {sql_literal(arguments.get("data_end"))}::date,
                {sql_jsonb(arguments.get("metrics"))},
                {sql_jsonb(arguments.get("diagnostics"))},
                {sql_literal(arguments.get("artifact_path"))},
                {sql_literal(actor)},
                {sql_jsonb(arguments.get("evidence") or [])},
                CASE WHEN {sql_literal(arguments.get("status") or "queued")} IN ('done','failed','cancelled') THEN now() ELSE NULL END
            )
            RETURNING id, strategy_id, backtest_run_id, run_name, optimizer_type, status, owner_agent, started_at, finished_at
        )
        SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text FROM inserted
        """
    )
    result = rows[0] if rows else {"error": "optimization not recorded"}
    audit_mcp_call(
        tool_name="ai_os_record_strategy_optimization",
        action_type="record_strategy_optimization",
        permission_level="write_with_approval",
        actor=actor,
        target_table="strategy.optimization_runs",
        target_id=result.get("id") if isinstance(result, dict) else None,
        request_payload=arguments,
        result_payload=result,
    )
    return tool_result(result)


def record_strategy_validation(arguments: dict) -> dict:
    strategy_id = resolve_strategy_id(arguments)
    actor = str(arguments.get("reviewer_agent") or "Model Validation Agent").strip()
    rows = run_psql_json_statement(
        f"""
        WITH inserted AS (
            INSERT INTO strategy.validation_reviews (
                strategy_id, backtest_run_id, optimization_run_id, reviewer_agent,
                review_status, decision, leakage_risk, overfit_risk, transaction_cost_notes,
                sample_size_notes, required_fixes, issues, evidence
            )
            VALUES (
                {strategy_id},
                {sql_literal(arguments.get("backtest_run_id"))}::bigint,
                {sql_literal(arguments.get("optimization_run_id"))}::bigint,
                {sql_literal(actor)},
                {sql_literal(arguments.get("review_status") or "draft")},
                {sql_literal(arguments.get("decision"))},
                {sql_literal(arguments.get("leakage_risk"))},
                {sql_literal(arguments.get("overfit_risk"))},
                {sql_literal(arguments.get("transaction_cost_notes"))},
                {sql_literal(arguments.get("sample_size_notes"))},
                {sql_text_array(arguments.get("required_fixes"))},
                {sql_jsonb(arguments.get("issues") or [])},
                {sql_jsonb(arguments.get("evidence") or [])}
            )
            RETURNING id, strategy_id, backtest_run_id, optimization_run_id, reviewer_agent,
                      review_status, decision, created_at, updated_at
        ),
        candidate_update AS (
            UPDATE strategy.strategy_candidates
            SET validation_status = coalesce((SELECT decision FROM inserted), (SELECT review_status FROM inserted), validation_status),
                updated_at = now()
            WHERE id = (SELECT strategy_id FROM inserted)
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text FROM inserted
        """
    )
    result = rows[0] if rows else {"error": "validation not recorded"}
    audit_mcp_call(
        tool_name="ai_os_record_strategy_validation",
        action_type="record_strategy_validation",
        permission_level="write_with_approval",
        actor=actor,
        target_table="strategy.validation_reviews",
        target_id=result.get("id") if isinstance(result, dict) else None,
        request_payload=arguments,
        result_payload=result,
    )
    return tool_result(result)


def refresh_research_hub(arguments: dict) -> dict:
    result = run_command([str(RUNTIME_ROOT / "scripts" / "inventory_ai_research_outputs.py")])
    parsed_stdout: object
    try:
        parsed_stdout = json.loads(result["stdout"] or "{}")
    except json.JSONDecodeError:
        parsed_stdout = {"raw_stdout": result["stdout"]}
    audit_mcp_call(
        tool_name="ai_os_refresh_research_hub",
        action_type="refresh_research_hub",
        permission_level="write_db_manual_only",
        actor=str(arguments.get("actor") or "Knowledge Librarian"),
        target_table="core.raw_artifacts",
        request_payload=arguments,
        result_payload={"returncode": result["returncode"], "stdout": parsed_stdout, "stderr": result["stderr"]},
        status="success" if result["returncode"] == 0 else "failed",
        error_message=result["stderr"] if result["returncode"] != 0 else None,
    )
    return tool_result({"returncode": result["returncode"], "stdout": parsed_stdout, "stderr": result["stderr"]})


def research_hub_summary(arguments: dict) -> dict:
    return tool_result(
        {
            "summary": run_psql_json(
                """
                SELECT root_label, artifact_family, artifact_count, latest_captured_at, latest_source_modified_at
                FROM research.v_research_hub_summary
                """
            ),
            "latest": run_psql_json(
                """
                SELECT artifact_id, title, artifact_family, company_or_topic, root_label,
                       local_path, mime_type, size_bytes, source_last_modified_at,
                       left(summary, 700) AS summary
                FROM research.v_ai_output_inventory
                ORDER BY captured_at DESC, source_last_modified_at DESC NULLS LAST
                LIMIT 25
                """
            ),
        }
    )


def run_public_data_source_check(arguments: dict) -> dict:
    result = run_command([str(RUNTIME_ROOT / "scripts" / "check_public_data_sources.py")])
    try:
        parsed_stdout = json.loads(result["stdout"] or "{}")
    except json.JSONDecodeError:
        parsed_stdout = {"raw_stdout": result["stdout"]}
    audit_mcp_call(
        tool_name="ai_os_run_public_data_source_check",
        action_type="run_public_data_source_check",
        permission_level="write_db_manual_only",
        actor=str(arguments.get("actor") or "Data Steward"),
        target_table="core.data_source_checks",
        request_payload=arguments,
        result_payload={"returncode": result["returncode"], "stdout": parsed_stdout, "stderr": result["stderr"]},
        status="success" if result["returncode"] == 0 else "failed",
        error_message=result["stderr"] if result["returncode"] != 0 else None,
    )
    return tool_result({"returncode": result["returncode"], "stdout": parsed_stdout, "stderr": result["stderr"]})


def data_source_checks(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50, maximum=200)
    source_key = str(arguments.get("source_key") or "").strip()
    clauses = []
    if source_key:
        clauses.append(f"source_key = {sql_literal(source_key)}")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result(
        run_psql_json(
            f"""
            SELECT source_key, check_name, check_type, target_url, status, http_status,
                   latency_ms, rows_seen, sample_payload, error_message, checked_at
            FROM core.v_recent_data_source_checks
            {where}
            ORDER BY checked_at DESC
            LIMIT {limit}
            """
        )
    )


def workspace_terminal_config(arguments: dict) -> dict:
    profile_key = str(arguments.get("profile_key") or "devarsh").strip().lower()
    return tool_result(
        {
            "config": run_psql_json(
                f"""
                SELECT profile_id, profile_key, profile_name, owner_name, is_active,
                       default_workspace, theme, density, navigation, preferences,
                       version, layout_id, workspace_key, module_order, hidden_modules,
                       column_count, settings, updated_by, updated_at
                FROM ops.v_workspace_terminal_config
                WHERE profile_key = {sql_literal(profile_key)}
                ORDER BY workspace_key NULLS LAST
                """
            ),
            "widgets": run_psql_json(
                """
                SELECT id, widget_key, widget_title, widget_type, workspace, status,
                       priority, owner_agent, query_ref, layout, data_binding,
                       last_refreshed_at, updated_at
                FROM ops.v_dashboard_widgets
                ORDER BY workspace, coalesce((layout ->> 'order')::integer, 100), updated_at DESC
                LIMIT 120
                """
            ),
        }
    )


def update_workspace_terminal(arguments: dict) -> dict:
    return tool_result(post_api_json("/api/workspaces/config/update", arguments))


def update_workspace_widget(arguments: dict) -> dict:
    return tool_result(post_api_json("/api/dashboard/widgets/update", arguments))


def governance_control_board(arguments: dict) -> dict:
    return tool_result(
        {
            "summary": run_psql_json("SELECT * FROM core.v_governance_control_summary ORDER BY metric"),
            "policies": run_psql_json(
                """
                SELECT document_key, document_type, title, policy_statement,
                       owner_agent, approval_required, status, controls,
                       evidence, version, updated_at
                FROM core.governance_documents
                ORDER BY document_type, title
                """
            ),
            "architecture_changes": run_psql_json(
                """
                SELECT * FROM core.v_architecture_change_board
                ORDER BY updated_at DESC NULLS LAST
                LIMIT 100
                """
            ),
            "architecture_decisions": run_psql_json(
                """
                SELECT id, decision_key, title, decision_status, context,
                       decision, alternatives, consequences, owner_agent,
                       approved_by, approval_id, evidence, decided_at, updated_at
                FROM core.architecture_decisions
                ORDER BY updated_at DESC
                LIMIT 100
                """
            ),
            "production_safety": run_psql_json(
                "SELECT * FROM core.v_production_safety_readiness ORDER BY check_key"
            ),
        }
    )


def request_architecture_change(arguments: dict) -> dict:
    return tool_result(post_api_json("/api/governance/architecture-changes/request", arguments))


def sync_architecture_change(arguments: dict) -> dict:
    return tool_result(post_api_json("/api/governance/architecture-changes/sync", arguments))


def ingest_research_paper(arguments: dict) -> dict:
    return tool_result(post_api_json("/api/research/papers/ingest", arguments, timeout=180.0))


def create_paper_strategy_hypotheses(arguments: dict) -> dict:
    return tool_result(post_api_json("/api/research/papers/hypotheses", arguments, timeout=120.0))


def ingest_local_artifact(arguments: dict) -> dict:
    return tool_result(post_api_json("/api/artifacts/local/ingest", arguments, timeout=180.0))


def local_artifact_ingestions(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=50, maximum=100)
    promotion_status = str(arguments.get("promotion_status") or "").strip()
    family = str(arguments.get("artifact_family") or "").strip()
    clauses = []
    if promotion_status:
        clauses.append(f"promotion_status={sql_literal(promotion_status)}")
    if family:
        clauses.append(f"artifact_family={sql_literal(family)}")
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    return tool_result({
        "summary": run_psql_json(
            "SELECT metric, value, interpretation FROM core.v_local_artifact_ingestion_summary ORDER BY metric"
        ),
        "ingestions": run_psql_json(
            f"""
            SELECT id, ingestion_key, task_id, file_name, artifact_family, content_hash,
                   parser_name, status, promotion_status, suggested_destination,
                   row_count, sheet_count, page_count, image_width, image_height,
                   extracted_chars, sensitivity, seen_count, task_status, owner_agent,
                   source_path, stored_path, extracted_text_path,
                   capital_action_allowed, live_execution_allowed, updated_at
            FROM core.v_local_artifact_ingestion_queue
            {where}
            ORDER BY updated_at DESC, id DESC
            LIMIT {limit}
            """
        ),
    })


def report_scheduler_status(arguments: dict) -> dict:
    limit = limit_arg(arguments, default=20, maximum=100)
    return tool_result({
        "health": run_psql_json("SELECT * FROM ops.v_report_scheduler_health"),
        "schedules": run_psql_json("SELECT * FROM ops.v_report_schedule_status ORDER BY cadence, report_name"),
        "invocations": run_psql_json(
            f"""
            SELECT id, invocation_key, trigger_type, report_key, status,
                   due_count, completed_count, failed_count, error_message,
                   started_at, finished_at
            FROM ops.report_scheduler_invocations
            ORDER BY started_at DESC
            LIMIT {limit}
            """
        ),
    })


def run_scheduled_reports(arguments: dict) -> dict:
    return tool_result(post_api_json("/api/reports/run", arguments, timeout=620.0))


TOOLS = {
    "ai_os_sync_fundamental_company_intake": {
        "description": "Synchronize real NSE/BSE portfolio holdings into the institutional company master and link official exchange filings as evidence. It never fabricates financial facts, scores, recommendations, capital actions, or broker orders.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "symbol": {"type": "string", "pattern": "^[A-Za-z0-9._&-]{1,40}$"},
                "actor": {"type": "string", "minLength": 1, "maxLength": 120, "default": "Fundamental Research Factory"},
            },
        },
        "handler": sync_fundamental_company_intake,
    },
    "ai_os_run_institutional_fundamental_factory": {
        "description": "Run the evidence-first institutional fundamental research factory for one real company at a point-in-time cutoff. Produces a versioned research dossier and acceptance evidence only; it is paper-only and cannot execute trades or authorize capital actions.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "company_id": {"type": "integer", "minimum": 1},
                "company_key": {"type": "string", "minLength": 1, "maxLength": 120},
                "symbol": {"type": "string", "pattern": "^[A-Za-z0-9._&-]{1,40}$"},
                "exchange": {"type": "string", "enum": ["NSE", "BSE"]},
                "as_of": {"type": "string", "format": "date-time"},
                "actor": {"type": "string", "minLength": 1, "maxLength": 120, "default": "Fundamental Research Director"},
                "run_key": {"type": "string", "pattern": "^[A-Za-z0-9._:-]{1,160}$"},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["as_of"],
            "oneOf": [
                {"required": ["company_id"]},
                {"required": ["company_key"]},
                {"required": ["symbol"]},
            ],
        },
        "handler": run_institutional_fundamental_factory,
    },
    "ai_os_run_sector_intelligence_engine": {
        "description": "Run evidence-first, point-in-time sector and custom-index calculations from governed warehouse inputs. Generates research, index history, rankings, and TradingView chart artifacts only; it is paper-only and has no broker execution or capital authority.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "index_id": {"type": "integer", "minimum": 1},
                "index_key": {"type": "string", "pattern": "^[A-Za-z0-9._:-]{1,120}$"},
                "as_of_date": {"type": "string", "format": "date"},
                "horizon": {"type": "string", "enum": ["1D", "1W", "1M", "3M", "6M", "1Y", "cycle"]},
                "actor": {"type": "string", "minLength": 1, "maxLength": 120, "default": "Sector Portfolio Manager"},
                "run_key": {"type": "string", "pattern": "^[A-Za-z0-9._:-]{1,160}$"},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["as_of_date"],
            "oneOf": [
                {"required": ["index_id"]},
                {"required": ["index_key"]},
            ],
        },
        "handler": run_sector_intelligence_engine,
    },
    "ai_os_sync_sector_fundamentals": {
        "description": "Publish latest available audited consolidated company facts into comparable sector metrics with official source lineage and point-in-time valuation. It never backdates evidence and cannot authorize capital or broker execution.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "taxonomy_key": {"type": "string", "minLength": 1, "maxLength": 160},
                "as_of_date": {"type": "string", "format": "date"},
                "actor": {"type": "string", "minLength": 1, "maxLength": 120, "default": "Sector Fundamental Analyst"},
                "persist": {"type": "boolean", "default": True},
            },
            "required": ["taxonomy_key", "as_of_date"],
        },
        "handler": sync_sector_fundamentals,
    },
    "ai_os_sync_sector_ownership_flows": {
        "description": "Collect official NSE corporate shareholding filings and constituent-level bulk/block deals for one active sector. Raw responses and hashes are retained; investor type is not guessed from names. No capital or broker execution is available.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "taxonomy_key": {"type": "string", "minLength": 1, "maxLength": 160},
                "as_of_date": {"type": "string", "format": "date"},
                "lookback_days": {"type": "integer", "minimum": 1, "maximum": 366, "default": 365},
                "actor": {"type": "string", "minLength": 1, "maxLength": 120, "default": "Sector Flow And Ownership Analyst"},
                "persist": {"type": "boolean", "default": True},
            },
            "required": ["taxonomy_key", "as_of_date"],
        },
        "handler": sync_sector_ownership_flows,
    },
    "ai_os_build_sector_underwrite": {
        "description": "Build a paper-only institutional sector underwrite from official ten-year point-in-time valuation history, stored fundamentals, ownership, flows and portfolio evidence. It records independent dissent and evidence gaps and cannot authorize capital, execution, or broker orders.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "taxonomy_key": {"type": "string", "minLength": 1, "maxLength": 160},
                "as_of_date": {"type": "string", "format": "date"},
                "actor": {"type": "string", "minLength": 1, "maxLength": 120, "default": "Sector Portfolio Manager"},
                "persist": {"type": "boolean", "default": True},
            },
            "required": ["taxonomy_key", "as_of_date"],
        },
        "handler": build_sector_underwrite,
    },
    "ai_os_calibrate_kronos_forecast": {
        "description": "Score one completed Kronos forecast against canonical realized OHLCV. The result is model-risk evidence only and cannot promote a strategy, allocate capital, or create a broker order.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "forecast_run_id": {"type": "integer", "minimum": 1},
                "actor": {"type": "string", "minLength": 1, "maxLength": 120, "default": "Model Validation Agent"},
            },
            "required": ["forecast_run_id"],
        },
        "handler": calibrate_kronos_forecast,
    },
    "ai_os_run_sector_acceptance": {
        "description": "Evaluate and persist the ten real-sector institutional acceptance gates for one active Indian sector at a point-in-time cutoff. This is paper-only and records evidence and blockers; it cannot authorize capital, execution, or a broker order.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "taxonomy_node_id": {"type": "integer", "minimum": 1},
                "taxonomy_key": {"type": "string", "minLength": 1, "maxLength": 160},
                "as_of_date": {"type": "string", "format": "date"},
                "run_key": {"type": "string", "pattern": "^[A-Za-z0-9._:-]{1,160}$"},
                "actor": {"type": "string", "minLength": 1, "maxLength": 120, "default": "Sector Portfolio Manager"},
            },
            "required": ["as_of_date"],
            "oneOf": [
                {"required": ["taxonomy_node_id"]},
                {"required": ["taxonomy_key"]},
            ],
        },
        "handler": run_sector_acceptance,
    },
    "ai_os_run_institutional_options_engine": {
        "description": "Run evidence-first institutional options analytics for one underlying and expiry using validated quotes, liquidity filters, IV, Greeks, structures, and replay controls. Analysis is paper-only with no execution; this tool cannot place, modify, or authorize any order.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "underlying": {"type": "string", "pattern": "^[A-Za-z0-9._&-]{1,40}$"},
                "exchange": {"type": "string", "enum": ["NFO", "BFO"]},
                "expiry_date": {"type": "string", "format": "date"},
                "as_of": {"type": "string", "format": "date-time"},
                "model": {"type": "string", "enum": ["black_scholes_merton", "black_76"], "default": "black_scholes_merton"},
                "max_age_seconds": {"type": "integer", "minimum": 1, "maximum": 900, "default": 120},
                "max_spread_bps": {"type": "number", "minimum": 1, "maximum": 5000, "default": 500},
                "min_open_interest": {"type": "number", "minimum": 0, "maximum": 1000000000, "default": 1},
                "min_volume": {"type": "number", "minimum": 0, "maximum": 1000000000, "default": 0},
                "actor": {"type": "string", "minLength": 1, "maxLength": 120, "default": "Options Specialist"},
                "run_key": {"type": "string", "pattern": "^[A-Za-z0-9._:-]{1,160}$"},
            },
            "required": ["underlying", "exchange", "expiry_date", "as_of"],
        },
        "handler": run_institutional_options_engine,
    },
    "ai_os_run_option_acceptance": {
        "description": "Evaluate and persist institutional options acceptance for one source-backed underlying, expiry, and multi-minute window. The tool is paper-only and cannot authorize capital, execution, or a broker order.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "exchange": {"type": "string", "enum": ["NFO", "BFO"]},
                "underlying": {"type": "string", "pattern": "^[A-Za-z0-9._&-]{1,40}$"},
                "expiry_date": {"type": "string", "format": "date"},
                "window_start": {"type": "string", "format": "date-time"},
                "window_end": {"type": "string", "format": "date-time"},
                "run_key": {"type": "string", "pattern": "^[A-Za-z0-9._:-]{1,160}$"},
                "actor": {"type": "string", "minLength": 1, "maxLength": 120, "default": "Options Data Quality Agent"},
            },
            "required": ["exchange", "underlying", "expiry_date", "window_start", "window_end"],
        },
        "handler": run_option_acceptance,
    },
    "ai_os_run_office_operability_acceptance": {
        "description": "Evaluate every active AI Office employee and department for real structure, tools, model route, bounded worker proof, evidence output, and durable handoffs. This read-and-audit tool cannot authorize capital or broker execution.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "run_key": {"type": "string", "pattern": "^[A-Za-z0-9._:-]{1,160}$"},
                "actor": {"type": "string", "minLength": 1, "maxLength": 120, "default": "Jarvis"},
            },
        },
        "handler": run_office_operability_acceptance,
    },
    "ai_os_materialize_institutional_options": {
        "description": "Materialize source-backed Zerodha option snapshots into immutable point-in-time institutional batches and calculate analytics only when a validated valuation policy exists. Paper-only; no order path.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
                "interval_seconds": {"type": "integer", "minimum": 60, "maximum": 3600, "default": 300},
                "actor": {"type": "string", "minLength": 1, "maxLength": 120},
            },
        },
        "handler": materialize_institutional_options,
    },
    "ai_os_upsert_option_valuation_policy": {
        "description": "Record a human-validated, source-evidenced and expiring rate/dividend policy for deterministic option analytics. This enables calculations only and never capital action.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "policy_key": {"type": "string", "pattern": "^[A-Za-z0-9._:-]{1,160}$"},
                "provider": {"type": "string", "minLength": 1},
                "exchange": {"type": "string", "enum": ["NFO", "BFO", "NSE", "BSE"]},
                "underlying": {"type": "string", "minLength": 1},
                "model_family": {"type": "string", "enum": ["black_scholes_merton", "black_76"]},
                "risk_free_rate": {"type": "number", "minimum": -0.2, "maximum": 1},
                "dividend_yield": {"type": "number", "minimum": -0.2, "maximum": 1},
                "rate_observation_id": {"type": "integer", "minimum": 1},
                "dividend_observation_id": {"type": "integer", "minimum": 1},
                "effective_from": {"type": "string", "format": "date-time"},
                "expires_at": {"type": "string", "format": "date-time"},
                "operator_confirmed": {"type": "boolean", "const": True},
                "day_count_convention": {"type": "string", "default": "ACT/365F"},
                "expiry_local_time": {"type": "string", "default": "15:30:00"},
                "expiry_timezone": {"type": "string", "default": "Asia/Kolkata"},
                "assumptions": {"type": "object"},
                "actor": {"type": "string", "minLength": 1, "maxLength": 120},
            },
            "required": ["policy_key", "provider", "exchange", "underlying", "risk_free_rate",
                         "dividend_yield", "rate_observation_id", "dividend_observation_id",
                         "effective_from", "expires_at", "operator_confirmed"],
        },
        "handler": upsert_option_valuation_policy,
    },
    "ai_os_refresh_option_valuation_sources": {
        "description": "Collect official read-only rate and index dividend-yield evidence as review candidates. This never activates a policy or permits execution.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "sources": {"type": "array", "items": {"type": "string", "enum": ["rate", "dividends"]}, "minItems": 1, "uniqueItems": True},
                "actor": {"type": "string", "minLength": 1, "maxLength": 120},
            },
        },
        "handler": refresh_option_valuation_sources,
    },
    "ai_os_import_sector_intelligence_package": {
        "description": "Validate or atomically import an evidence-backed licensed export or primary-source sector package containing taxonomy, memberships, metrics and custom indices.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "package": {"type": "object"},
                "persist": {"type": "boolean", "default": False},
                "actor": {"type": "string", "minLength": 1, "maxLength": 120},
            },
            "required": ["package"],
        },
        "handler": import_sector_intelligence_package,
    },
    "ai_os_report_scheduler_status": {
        "description": "Read report cadence, due state, latest launchd proof, scheduler invocation history, failures, and generated-run linkage.",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}},
        },
        "handler": report_scheduler_status,
    },
    "ai_os_run_scheduled_reports": {
        "description": "Run due source-backed reports or explicitly force one named schedule through the audited report API. This creates drafts and evidence only; it cannot send client reports or authorize capital actions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "report_key": {"type": "string"},
                "force": {"type": "boolean", "default": False},
                "actor": {"type": "string", "default": "Jarvis MCP"},
            },
        },
        "handler": run_scheduled_reports,
    },
    "ai_os_ingest_local_artifact": {
        "description": "Copy an explicitly operator-confirmed spreadsheet, document, or screenshot from the AI OS runtime, vault, or external SSD into immutable storage, profile or extract it, and create a Data Steward mapping task. Desktop, Downloads, and Documents files must use the Reports terminal file picker. Never promotes investment or trading rows automatically.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "local_path": {"type": "string"},
                "title": {"type": "string"},
                "sensitivity": {"type": "string", "enum": ["public", "internal", "private", "client_private", "restricted"], "default": "private"},
                "suggested_destination": {"type": "string"},
                "run_key": {"type": "string"},
                "actor": {"type": "string", "default": "Data Steward"},
                "operator_confirmed": {"type": "boolean", "const": True},
                "max_mb": {"type": "integer", "minimum": 1, "maximum": 200, "default": 100},
            },
            "required": ["local_path", "operator_confirmed"],
        },
        "handler": ingest_local_artifact,
    },
    "ai_os_local_artifact_ingestions": {
        "description": "Read governed local-artifact intake counts, checksums, parser status, destination mapping state, and review-task linkage without exposing raw private file contents.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "promotion_status": {"type": "string", "enum": ["needs_mapping", "needs_review", "promoted", "excluded", "blocked"]},
                "artifact_family": {"type": "string", "enum": ["tabular", "document", "image"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
            },
        },
        "handler": local_artifact_ingestions,
    },
    "ai_os_ingest_research_paper": {
        "description": "Register and extract a source-backed research paper from a public HTTPS PDF or an allowed local path. Creates a human research-review task and never promotes a strategy automatically.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "source_key": {"type": "string", "default": "local"},
                "source_url": {"type": "string"},
                "pdf_url": {"type": "string"},
                "local_path": {"type": "string"},
                "authors": {"type": "array", "items": {"type": "string"}},
                "published_date": {"type": "string"},
                "doi": {"type": "string"},
                "abstract": {"type": "string"},
                "topics": {"type": "array", "items": {"type": "string"}},
                "asset_classes": {"type": "array", "items": {"type": "string"}},
                "markets": {"type": "array", "items": {"type": "string"}},
                "methodology_tags": {"type": "array", "items": {"type": "string"}},
                "actor": {"type": "string", "default": "Research Librarian"},
            },
            "required": ["title"],
        },
        "handler": ingest_research_paper,
    },
    "ai_os_create_paper_strategy_hypotheses": {
        "description": "Persist falsifiable, source-linked strategy hypotheses from an extracted paper. Hypotheses remain in research queue until separately reviewed and promoted.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "paper_id": {"type": "integer"},
                "actor": {"type": "string", "default": "Strategy Research Agent"},
                "hypotheses": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "edge_hypothesis": {"type": "string"},
                            "market_scope": {"type": "array", "items": {"type": "string"}},
                            "asset_classes": {"type": "array", "items": {"type": "string"}},
                            "timeframe": {"type": "string"},
                            "signal_definition": {"type": "object"},
                            "data_requirements": {"type": "object"},
                            "implementation_notes": {"type": "string"},
                            "invalidation_tests": {"type": "array", "items": {"type": "object"}},
                            "limitations": {"type": "array", "items": {"type": "object"}},
                        },
                        "required": ["title", "edge_hypothesis"],
                    },
                },
            },
            "required": ["paper_id", "hypotheses"],
        },
        "handler": create_paper_strategy_hypotheses,
    },
    "ai_os_workspace_terminal_config": {
        "description": "Read the active operator workspace profile, department layouts, and live widget configuration.",
        "inputSchema": {
            "type": "object",
            "properties": {"profile_key": {"type": "string", "default": "devarsh"}},
        },
        "handler": workspace_terminal_config,
    },
    "ai_os_update_workspace_terminal": {
        "description": "Apply an audited, reversible operator workspace update for theme, density, navigation, or department layout. Does not alter market evidence or execution state.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "profile_key": {"type": "string", "default": "devarsh"},
                "actor": {"type": "string", "default": "Charlie Munger"},
                "theme": {"type": "string", "enum": ["terminal_dark", "terminal_light"]},
                "density": {"type": "string", "enum": ["compact", "standard"]},
                "default_workspace": {"type": "string"},
                "navigation": {"type": "object"},
                "preferences": {"type": "object"},
                "workspace_key": {"type": "string", "enum": ["approvals", "agents", "committees", "governance", "capital", "treasury", "models", "arsenal"]},
                "module_order": {"type": "array", "items": {"type": "string"}},
                "hidden_modules": {"type": "array", "items": {"type": "string"}},
                "column_count": {"type": "integer", "minimum": 1, "maximum": 4},
            },
        },
        "handler": update_workspace_terminal,
    },
    "ai_os_update_workspace_widget": {
        "description": "Update one dashboard widget's visibility, order, or size while preserving its live data binding and evidence lineage.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "widget_id": {"type": "integer"},
                "actor": {"type": "string", "default": "Charlie Munger"},
                "status": {"type": "string", "enum": ["active", "hidden", "archived"]},
                "size": {"type": "string", "enum": ["standard", "wide", "full"]},
                "order": {"type": "integer"},
            },
            "required": ["widget_id"],
        },
        "handler": update_workspace_widget,
    },
    "ai_os_governance_control_board": {
        "description": "Read the live governance board: policies, architecture decisions and change requests, production-safety controls, and evidence.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": governance_control_board,
    },
    "ai_os_request_architecture_change": {
        "description": "Open a material architecture change with a rollback plan, task, inbox item, and mandatory human approval. This never changes execution authority.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "change_type": {"type": "string", "default": "system_change"},
                "objective": {"type": "string"},
                "proposed_change": {"type": "string"},
                "rollback_plan": {"type": "string"},
                "actor": {"type": "string", "default": "Devarsh"},
                "owner_agent": {"type": "string", "default": "Jarvis"},
                "blast_radius": {"type": "string", "enum": ["bounded", "department", "system_wide", "execution", "client_data"]},
                "alternatives": {"type": "array", "items": {}},
                "expected_consequences": {"type": "array", "items": {}},
                "evidence": {"type": "array", "items": {}},
            },
            "required": ["title", "objective", "proposed_change", "rollback_plan"],
        },
        "handler": request_architecture_change,
    },
    "ai_os_sync_architecture_change": {
        "description": "Synchronize a decided architecture-change approval into the decision log. Pending approvals remain pending and no execution authority is granted.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "change_id": {"type": "integer"},
                "actor": {"type": "string", "default": "Jarvis"},
            },
            "required": ["change_id"],
        },
        "handler": sync_architecture_change,
    },
    "ai_os_mcp_capabilities": {
        "description": "List MCP tools registered in the warehouse with owners, permission levels, and guardrails.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": mcp_capabilities,
    },
    "ai_os_mcp_audit_log": {
        "description": "Read recent MCP audit events for write/browser tools.",
        "inputSchema": {"type": "object", "properties": {"tool_name": {"type": "string"}, "limit": {"type": "integer", "default": 50}}},
        "handler": mcp_audit_log,
    },
    "ai_os_mcp_candidate_shortlist": {
        "description": "Read approved and candidate external MCP integrations with use cases, permissions, and risk notes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string"},
                "status": {"type": "string"},
                "selected_for_phase": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": mcp_candidate_shortlist,
    },
    "ai_os_control_plane_snapshot": {
        "description": "Return the AI OS control-plane snapshot: modules, data sources, strategies, workflows, clients, and Fincept install status.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": control_plane_snapshot,
    },
    "ai_os_orchestration_stack": {
        "description": "Show the active stack roles: Charlie Munger as main orchestrator, Jarvis as runtime layer, and specialist agents.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": orchestration_stack,
    },
    "ai_os_list_active_agents": {
        "description": "List active AI OS agent profiles and routes.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": list_active_agents,
    },
    "ai_os_materialize_agent_schedules": {
        "description": "Materialize due role-scoped office schedules into durable agent tasks and inbox items. Open-task dedupe, provider gates, and all capital/execution approvals remain active.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actor": {"type": "string", "default": "Jarvis"},
                "limit": {"type": "integer", "default": 10},
            },
        },
        "handler": materialize_agent_schedules,
    },
    "ai_os_list_open_tasks": {
        "description": "List queued/in-progress/blocked AI OS tasks.",
        "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 25}}},
        "handler": list_open_tasks,
    },
    "ai_os_blueprint_summary": {
        "description": "Read canonical AI Investment OS blueprint progress, domain coverage, and registry sync evidence.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": blueprint_summary,
    },
    "ai_os_blueprint_requirements": {
        "description": "Read canonical blueprint requirements with owners, mapped runtime objects, evidence, acceptance criteria, and next actions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["planned", "partial", "done", "blocked"]},
                "domain_key": {"type": "string"},
                "priority": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": blueprint_requirements,
    },
    "ai_os_blueprint_v9_summary": {
        "description": "Compatibility alias for ai_os_blueprint_summary; returns the canonical blueprint rather than frozen v9 rows.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": blueprint_v9_summary,
    },
    "ai_os_blueprint_v9_requirements": {
        "description": "Compatibility alias for ai_os_blueprint_requirements; returns canonical requirements.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["planned", "partial", "done", "blocked"]},
                "domain_key": {"type": "string"},
                "priority": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": blueprint_v9_requirements,
    },
    "ai_os_symbol_intelligence_v2": {
        "description": "Read Symbol Intelligence v2 decision packets with book exposure, remediation, committees, risk, news, filings, and strategy links.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "client_code": {"type": "string"},
                "symbol": {"type": "string"},
                "v2_decision_state": {"type": "string"},
                "limit": {"type": "integer", "default": 25},
            },
        },
        "handler": symbol_intelligence_v2,
    },
    "ai_os_symbol_intelligence_v2_summary": {
        "description": "Read Symbol Intelligence v2 coverage and decision-state summary metrics.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": symbol_intelligence_v2_summary,
    },
    "ai_os_route_symbol_intelligence_action": {
        "description": "Route a Symbol Intelligence v2 row into the correct agent task and inbox workflow. This never approves trades or live execution.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action_type": {
                    "type": "string",
                    "enum": [
                        "refresh_thesis",
                        "review_exit_criteria",
                        "route_risk_review",
                        "route_research_update",
                        "route_quant_review",
                        "route_trading_review",
                        "request_committee_review",
                        "prepare_tradingview",
                    ],
                },
                "actor": {"type": "string", "default": "Charlie Munger"},
                "client_code": {"type": "string"},
                "exchange": {"type": "string", "default": "NSE"},
                "notes": {"type": "string"},
                "symbol": {"type": "string"},
            },
            "required": ["symbol", "action_type"],
        },
        "handler": route_symbol_intelligence_action,
    },
    "ai_os_symbol_intelligence_actions": {
        "description": "Read Symbol Intelligence actions routed into agent tasks and inboxes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action_type": {"type": "string"},
                "client_code": {"type": "string"},
                "symbol": {"type": "string"},
                "limit": {"type": "integer", "default": 25},
            },
        },
        "handler": symbol_intelligence_actions,
    },
    "ai_os_sync_position_remediation_queue": {
        "description": "Create or refresh position-object remediation queue items and optional agent tasks from readiness gaps. Local warehouse write only.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actor": {"type": "string", "default": "Portfolio Manager"},
                "limit": {"type": "integer", "default": 200},
                "create_tasks": {"type": "boolean", "default": True},
            },
        },
        "handler": sync_position_remediation_queue,
    },
    "ai_os_position_remediation_queue": {
        "description": "Read position-object remediation queue items, owner agents, linked tasks, and inbox state.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "owner_agent": {"type": "string"},
                "gap_type": {"type": "string"},
                "symbol": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": position_remediation_queue,
    },
    "ai_os_position_remediation_summary": {
        "description": "Read position-object remediation summary metrics.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": position_remediation_summary,
    },
    "ai_os_sync_long_term_coverage_queue": {
        "description": "Create or refresh Long-Term coverage queue items and optional agent tasks from live thesis, checklist, valuation, Monte Carlo, exit, and committee gaps.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "actor": {"type": "string", "default": "Long-Term Portfolio Manager"},
                "limit": {"type": "integer", "default": 100},
                "create_tasks": {"type": "boolean", "default": True},
            },
        },
        "handler": sync_long_term_coverage_queue,
    },
    "ai_os_long_term_coverage_queue": {
        "description": "Read Long-Term coverage queue items, owner agents, linked tasks, inbox state, and missing evidence by symbol.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "owner_agent": {"type": "string"},
                "gap_type": {"type": "string"},
                "severity": {"type": "string"},
                "symbol": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": long_term_coverage_queue,
    },
    "ai_os_long_term_coverage_summary": {
        "description": "Read Long-Term coverage summary metrics across missing thesis, checklist, valuation, Monte Carlo, exit, and committee readiness work.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": long_term_coverage_summary,
    },
    "ai_os_create_task": {
        "description": "Create an agent task and optional inbox item with evidence. Local warehouse write only.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "objective": {"type": "string"},
                "owner_agent": {"type": "string", "default": "Jarvis"},
                "priority": {"type": "string", "default": "normal"},
                "approval_required": {"type": "boolean", "default": False},
                "source_kind": {"type": "string"},
                "source_ref": {"type": "string"},
                "output_format": {"type": "string"},
                "evidence": {"type": "array", "items": {"type": "object"}},
                "create_inbox": {"type": "boolean", "default": True},
                "recommended_action": {"type": "string"},
                "target_workspace": {"type": "string", "default": "command"},
                "actor": {"type": "string", "default": "Jarvis"},
            },
            "required": ["title", "objective"],
        },
        "handler": create_task,
    },
    "ai_os_update_task_status": {
        "description": "Update one agent task status, evidence, and optional output note path.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer"},
                "status": {"type": "string"},
                "output_note_path": {"type": "string"},
                "evidence": {"type": "array", "items": {"type": "object"}},
                "actor": {"type": "string", "default": "Jarvis"},
            },
            "required": ["task_id", "status"],
        },
        "handler": update_task_status,
    },
    "ai_os_list_inbox": {
        "description": "List agent inbox items with optional status/workspace filters.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "target_workspace": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": list_inbox,
    },
    "ai_os_research_factory_queue_summary": {
        "description": "Summarize filings, special situations, and research-agent message queues.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": research_factory_queue_summary,
    },
    "ai_os_triage_agent_message": {
        "description": "Mark an agent message read/acknowledged or route it into a task and inbox item.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "integer"},
                "action": {"type": "string", "enum": ["mark_read", "acknowledge", "create_task"], "default": "acknowledge"},
                "task_title": {"type": "string"},
                "task_objective": {"type": "string"},
                "priority": {"type": "string"},
                "recommended_action": {"type": "string"},
                "target_workspace": {"type": "string", "default": "command"},
                "actor": {"type": "string", "default": "Jarvis"},
            },
            "required": ["message_id"],
        },
        "handler": triage_agent_message,
    },
    "ai_os_update_inbox_status": {
        "description": "Claim, reassign, resolve, block, or reopen one inbox item and synchronize its linked task.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "inbox_id": {"type": "integer"},
                "action": {"type": "string", "enum": ["claim", "reassign", "resolve", "block", "reopen"]},
                "status": {"type": "string", "description": "Legacy status input; action is preferred."},
                "owner_agent": {"type": "string"},
                "resolution_note": {"type": "string"},
                "recommended_action": {"type": "string"},
                "actor": {"type": "string", "default": "Jarvis"},
            },
            "required": ["inbox_id"],
        },
        "handler": update_inbox_status,
    },
    "ai_os_create_approval": {
        "description": "Create a human approval request for a report, trade action, data import, or system change.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer"},
                "approval_type": {"type": "string", "default": "system_change"},
                "title": {"type": "string"},
                "owner_agent": {"type": "string", "default": "Risk Agent"},
                "risk_level": {"type": "string", "default": "medium"},
                "requested_action": {"type": "object"},
                "rationale": {"type": "string"},
                "actor": {"type": "string", "default": "Jarvis"},
            },
            "required": ["title"],
        },
        "handler": create_approval,
    },
    "ai_os_decide_approval": {
        "description": "Approve or reject one pending approval with decided_by and rationale.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "approval_id": {"type": "integer"},
                "decision": {"type": "string", "enum": ["approved", "rejected"]},
                "decided_by": {"type": "string", "default": "Devarsh"},
                "rationale": {"type": "string"},
                "actor": {"type": "string"},
            },
            "required": ["approval_id", "decision"],
        },
        "handler": decide_approval,
    },
    "ai_os_p2cursor_source_summary": {
        "description": "Summarize quarantined and staged p2cursor source files.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": p2cursor_source_summary,
    },
    "ai_os_algo_import_summary": {
        "description": "Return row counts for imported algo trading data.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": algo_import_summary,
    },
    "ai_os_legacy_source_readiness": {
        "description": "Read p2cursor and old algo extraction readiness, including staged/promoted coverage and open extraction issues.",
        "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 25}}},
        "handler": legacy_source_readiness,
    },
    "ai_os_legacy_source_resolution_board": {
        "description": "Read canonical, archived, deduplicated, rejected, and unresolved row accounting for every legacy algo source table.",
        "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 100}}},
        "handler": legacy_source_resolution_board,
    },
    "ai_os_run_legacy_source_readiness": {
        "description": "Run a legacy-source extraction readiness sweep and queue Data Steward review items for gaps.",
        "inputSchema": {"type": "object", "properties": {"actor": {"type": "string", "default": "Jarvis"}}},
        "handler": run_legacy_source_readiness,
    },
    "ai_os_component_inventory": {
        "description": "List reusable components extracted from p2cursor and algo software.",
        "inputSchema": {"type": "object", "properties": {"source_system": {"type": "string"}}},
        "handler": component_inventory,
    },
    "ai_os_source_requirements": {
        "description": "List parsed pip/npm requirements from extracted source components.",
        "inputSchema": {"type": "object", "properties": {"package_manager": {"type": "string", "enum": ["pip", "npm"]}}},
        "handler": source_requirements,
    },
    "ai_os_source_lineage_summary": {
        "description": "Summarize source lineage coverage by source system, lineage type, sensitivity, and open/staged state.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": source_lineage_summary,
    },
    "ai_os_source_lineage": {
        "description": "List source lineage rows across raw artifacts, p2cursor files/rows, attached broker files, portfolio positions, and reconciliation issues.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lineage_type": {"type": "string"},
                "client_code": {"type": "string"},
                "symbol": {"type": "string"},
                "source_system": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": source_lineage,
    },
    "ai_os_import_artifact_coverage": {
        "description": "Show raw-artifact coverage across p2cursor, attached transaction, and imported file source-system surfaces.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": import_artifact_coverage,
    },
    "ai_os_import_artifact_gaps": {
        "description": "List imported files that still lack raw-artifact lineage.",
        "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 50}}},
        "handler": import_artifact_gaps,
    },
    "ai_os_portfolio_risk_limit_checks": {
        "description": "Read current portfolio risk limit checks across books, clients, symbols, and allocations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "check_status": {"type": "string", "enum": ["breach", "warning", "ok"]},
                "book_key": {"type": "string"},
                "client_code": {"type": "string"},
                "symbol": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": portfolio_risk_limit_checks,
    },
    "ai_os_refresh_portfolio_risk_events": {
        "description": "Materialize current breached portfolio risk limit checks into risk.events without duplicate open events.",
        "inputSchema": {"type": "object", "properties": {"actor": {"type": "string", "default": "Risk Agent"}}},
        "handler": refresh_portfolio_risk_events,
    },
    "ai_os_portfolio_intelligence_v2": {
        "description": "Read Portfolio Intelligence v2 summary with exposure, concentration, and risk metrics.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": portfolio_intelligence_v2,
    },
    "ai_os_position_objects_v9": {
        "description": "Read v9 institutional position objects with completeness scores and missing-field gap types.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "client_code": {"type": "string"},
                "symbol": {"type": "string"},
                "book_key": {"type": "string"},
                "readiness": {"type": "string", "enum": ["not_decision_ready", "review_required", "decision_ready"]},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": position_objects_v9,
    },
    "ai_os_position_object_gap_summary": {
        "description": "Read summary of missing v9 position-object fields by gap type.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": position_object_gap_summary,
    },
    "ai_os_cross_book_coordination_questions": {
        "description": "Read cross-book offset coordination questions for opposing exposures.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "client_code": {"type": "string"},
                "symbol": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": cross_book_coordination_questions,
    },
    "ai_os_live_office_rooms": {
        "description": "Read the Live AI Office v1 room map backed by live tasks, inboxes, messages, worker runs, and risk events.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": live_office_rooms,
    },
    "ai_os_live_office_agent_activity": {
        "description": "Read per-agent live office activity, current work, mailbox pressure, tasks, and worker state.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_name": {"type": "string"},
                "department_key": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": live_office_agent_activity,
    },
    "ai_os_approval_board": {
        "description": "Read the unified approval board across approvals, committees, TradingView, special situations, limited-live, orders, risk events, and execution gates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "approval_status": {"type": "string"},
                "board_lane": {"type": "string"},
                "risk_level": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": approval_board,
    },
    "ai_os_committee_room": {
        "description": "Read the unified committee room across Strategy Committee, Long-Term Committee, and Special Situation reviews.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "committee_lane": {"type": "string"},
                "room_state": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": committee_room,
    },
    "ai_os_open_committee_packet": {
        "description": "Open a durable committee packet from a live room item and dispatch sealed role-scoped position assignments.",
        "inputSchema": {"type": "object", "properties": {
            "committee_item_key": {"type": "string"}, "title": {"type": "string"},
            "decision_question": {"type": "string"}, "opened_by": {"type": "string", "default": "Charlie Munger"},
            "due_at": {"type": "string"}, "evidence": {"type": "array", "items": {"type": "object"}}
        }, "required": ["committee_item_key", "decision_question"]},
        "handler": open_committee_packet_tool,
    },
    "ai_os_submit_committee_position": {
        "description": "Submit one committee member's sealed independent position, evidence, confidence, and conditions.",
        "inputSchema": {"type": "object", "properties": {
            "packet_id": {"type": "integer"}, "agent_name": {"type": "string"},
            "stance": {"type": "string", "enum": ["support","oppose","conditional","abstain","request_more_evidence","block"]},
            "recommendation": {"type": "string"}, "confidence": {"type": "number", "minimum": 0, "maximum": 100},
            "thesis": {"type": "string"}, "evidence": {"type": "array", "items": {"type": "object"}},
            "conditions": {"type": "array", "items": {"type": "object"}}
        }, "required": ["packet_id","agent_name","stance","recommendation","confidence","thesis"]},
        "handler": submit_committee_position_tool,
    },
    "ai_os_add_committee_discussion": {
        "description": "Add a post-quorum committee challenge or response after the member has submitted an independent position.",
        "inputSchema": {"type": "object", "properties": {
            "packet_id": {"type": "integer"}, "from_agent": {"type": "string"},
            "message_type": {"type": "string", "enum": ["challenge","response","clarification","risk_objection","evidence_update","chair_synthesis"]},
            "body": {"type": "string"}, "reply_to_position_id": {"type": "integer"},
            "evidence": {"type": "array", "items": {"type": "object"}}
        }, "required": ["packet_id","from_agent","body"]},
        "handler": add_committee_discussion_tool,
    },
    "ai_os_synthesize_committee_session": {
        "description": "After quorum, record the registered chair's recommendation, minutes, dissent, and conditions; no capital or broker action is authorized.",
        "inputSchema": {"type": "object", "properties": {
            "packet_id": {"type": "integer"}, "chair_agent": {"type": "string"},
            "recommendation": {"type": "string"}, "minutes": {"type": "string"},
            "dissent_summary": {"type": "string"}, "conditions": {"type": "array", "items": {"type": "object"}}
        }, "required": ["packet_id","chair_agent","recommendation","minutes"]},
        "handler": synthesize_committee_session_tool,
    },
    "ai_os_record_committee_human_decision": {
        "description": "Record Devarsh's separate final decision on an awaiting-human committee packet without triggering capital or execution.",
        "inputSchema": {"type": "object", "properties": {
            "packet_id": {"type": "integer"}, "decision": {"type": "string"},
            "decided_by": {"type": "string", "default": "Devarsh"}, "rationale": {"type": "string"}
        }, "required": ["packet_id","decision","rationale"]},
        "handler": record_committee_human_decision_tool,
    },
    "ai_os_create_committee_followup": {
        "description": "Create a committee follow-up backed by an agent task and inbox assignment.",
        "inputSchema": {"type": "object", "properties": {
            "packet_id": {"type": "integer"}, "owner_agent": {"type": "string"},
            "title": {"type": "string"}, "objective": {"type": "string"}, "priority": {"type": "string"},
            "due_at": {"type": "string"}, "evidence": {"type": "array", "items": {"type": "object"}}
        }, "required": ["packet_id","owner_agent","title","objective"]},
        "handler": create_committee_followup_tool,
    },
    "ai_os_employee_profiles": {
        "description": "Read AI Office employee profiles with role, personality, model route, tools, skills, tasks, messages, outputs, and approvals.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_name": {"type": "string"},
                "department": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": employee_profiles,
    },
    "ai_os_output_artifact_registry": {
        "description": "Read the unified generated-output registry for reports, memos, worker outputs, models, indexed AI outputs, and traceability gaps.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "artifact_family": {
                    "type": "string",
                    "enum": [
                        "worker_output",
                        "committee_memo",
                        "specialist_output",
                        "research_note",
                        "risk_model",
                        "special_situation_memo",
                        "indexed_ai_output",
                    ],
                },
                "owner_agent": {"type": "string"},
                "symbol": {"type": "string"},
                "query": {"type": "string"},
                "gaps_only": {"type": "boolean", "default": False},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": output_artifact_registry,
    },
    "ai_os_agent_comments": {
        "description": "Read agent comments and review annotations across artifacts, tasks, approvals, agents, strategies, and system targets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_kind": {"type": "string"},
                "target_ref": {"type": "string"},
                "from_agent": {"type": "string"},
                "to_agent": {"type": "string"},
                "status": {"type": "string"},
                "needs_attention": {"type": "boolean"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": agent_comments,
    },
    "ai_os_create_agent_comment": {
        "description": "Create an auditable agent comment or review annotation on an AI Office target.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_kind": {
                    "type": "string",
                    "enum": [
                        "output_artifact",
                        "task",
                        "approval",
                        "agent",
                        "message_thread",
                        "symbol",
                        "strategy",
                        "client",
                        "committee_review",
                        "risk_event",
                        "system",
                    ],
                },
                "target_ref": {"type": "string"},
                "target_title": {"type": "string"},
                "parent_comment_id": {"type": "integer"},
                "from_agent": {"type": "string", "default": "Charlie Munger"},
                "to_agent": {"type": "string"},
                "comment_type": {
                    "type": "string",
                    "enum": ["review_note", "question", "objection", "risk_flag", "follow_up", "decision_note", "source_gap", "praise", "system_note"],
                    "default": "review_note",
                },
                "severity": {"type": "string", "enum": ["low", "normal", "medium", "high", "critical"], "default": "normal"},
                "status": {"type": "string", "enum": ["open", "acknowledged", "resolved", "dismissed"], "default": "open"},
                "body": {"type": "string"},
                "evidence": {"type": "array", "items": {"type": "object"}},
                "metadata": {"type": "object"},
                "actor": {"type": "string"},
            },
            "required": ["target_kind", "target_ref", "body"],
        },
        "handler": create_agent_comment_tool,
    },
    "ai_os_resolve_agent_comment": {
        "description": "Resolve, acknowledge, or dismiss an existing agent comment with audit evidence.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "comment_id": {"type": "integer"},
                "status": {"type": "string", "enum": ["acknowledged", "resolved", "dismissed"], "default": "resolved"},
                "actor": {"type": "string", "default": "Jarvis"},
                "resolution_note": {"type": "string"},
            },
            "required": ["comment_id"],
        },
        "handler": resolve_agent_comment_tool,
    },
    "ai_os_model_cost_ledger": {
        "description": "Read model usage, cost estimates, route summaries, and per-agent cost-cap status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_name": {"type": "string"},
                "route_name": {"type": "string"},
                "provider": {"type": "string"},
                "cost_control_status": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": model_cost_ledger,
    },
    "ai_os_record_model_usage": {
        "description": "Record a model usage event with estimated or actual token/cost metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_kind": {"type": "string", "default": "mcp_manual"},
                "source_ref": {"type": "string"},
                "agent_name": {"type": "string"},
                "route_name": {"type": "string"},
                "provider": {"type": "string"},
                "model_name": {"type": "string"},
                "endpoint_key": {"type": "string"},
                "usage_kind": {"type": "string", "default": "tool_call"},
                "model_status": {"type": "string", "default": "recorded"},
                "prompt_tokens_est": {"type": "number"},
                "completion_tokens_est": {"type": "number"},
                "total_tokens_est": {"type": "number"},
                "actual_prompt_tokens": {"type": "number"},
                "actual_completion_tokens": {"type": "number"},
                "actual_total_tokens": {"type": "number"},
                "estimated_cost_usd": {"type": "number"},
                "actual_cost_usd": {"type": "number"},
                "cost_tier": {"type": "string"},
                "estimate_method": {"type": "string"},
                "approval_id": {"type": "integer"},
                "task_id": {"type": "integer"},
                "chat_turn_id": {"type": "integer"},
                "evidence": {"type": "array", "items": {"type": "object"}},
                "metadata": {"type": "object"},
                "actor": {"type": "string", "default": "AI Engineering"},
            },
            "required": ["provider", "model_name"],
        },
        "handler": record_model_usage_tool,
    },
    "ai_os_run_provider_readiness_sweep": {
        "description": "Run health checks across registered model endpoints and source connectors, then persist a provider readiness summary.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_key": {"type": "string"},
                "actor": {"type": "string", "default": "Jarvis"},
                "model_limit": {"type": "integer", "default": 50},
                "source_limit": {"type": "integer", "default": 80},
                "models_only": {"type": "boolean", "default": False},
                "sources_only": {"type": "boolean", "default": False},
            },
        },
        "handler": run_provider_readiness_sweep,
    },
    "ai_os_provider_readiness_board": {
        "description": "Read the combined provider readiness board for model endpoints and source connectors.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "provider_kind": {"type": "string"},
                "readiness_status": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": provider_readiness_board,
    },
    "ai_os_integration_plugin_gateway": {
        "description": "Read the unified source/model plug-in gateway with credentials, health, freshness, schema, schedule, route, and execution-lock gates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "plugin_kind": {"type": "string", "enum": ["data_source", "model_provider"]},
                "gateway_status": {"type": "string"},
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 100},
            },
        },
        "handler": integration_plugin_gateway,
    },
    "ai_os_market_data_readiness": {
        "description": "Read real market-data coverage, immutable import lineage, quality checks, deduplication, staleness, and research-bias contracts.",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 25}},
        },
        "handler": market_data_readiness,
    },
    "ai_os_run_legacy_market_data_ingestion": {
        "description": "Run the fixed checksum-preserved legacy SQLite importer. No arbitrary path, network, broker, or execution authority is accepted.",
        "inputSchema": {
            "type": "object",
            "properties": {"actor": {"type": "string", "default": "Jarvis"}},
        },
        "handler": run_legacy_market_data_ingestion_tool,
    },
    "ai_os_upsert_integration_schema_mapping": {
        "description": "Create or update a data-source to warehouse mapping. Raw secrets are rejected.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mapping_key": {"type": "string"},
                "plugin_key": {"type": "string"},
                "dataset_key": {"type": "string"},
                "target_relation": {"type": "string"},
                "source_schema": {"type": "object"},
                "field_mappings": {"type": "object"},
                "transformations": {"type": "array"},
                "primary_key_fields": {"type": "array", "items": {"type": "string"}},
                "timestamp_field": {"type": "string"},
                "schema_version": {"type": "string", "default": "1"},
                "status": {"type": "string", "default": "configured"},
                "owner_agent": {"type": "string", "default": "Data Steward"},
                "notes": {"type": "string"},
                "actor": {"type": "string", "default": "Data Steward"},
            },
            "required": ["plugin_key", "dataset_key", "target_relation", "field_mappings", "primary_key_fields"],
        },
        "handler": upsert_integration_schema_mapping_tool,
    },
    "ai_os_validate_integration_schema_mapping": {
        "description": "Validate a plug-in mapping against the live target relation and idempotency contract.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mapping_key": {"type": "string"},
                "actor": {"type": "string", "default": "Data Quality Agent"},
            },
            "required": ["mapping_key"],
        },
        "handler": validate_integration_schema_mapping_tool,
    },
    "ai_os_upsert_integration_job": {
        "description": "Configure an allowlisted bounded ingestion or provider job. Arbitrary commands and raw secrets are rejected.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_key": {"type": "string"},
                "plugin_key": {"type": "string"},
                "job_name": {"type": "string"},
                "job_type": {"type": "string", "enum": ["poll", "import", "stream", "aggregate", "health_check", "provider_probe"]},
                "executor_key": {"type": "string", "enum": ["market_news_ingestion", "filings_collection", "tick_ohlcv_aggregation", "tradingview_quote_refresh", "public_source_check", "provider_readiness", "legacy_market_data_ingestion"]},
                "schedule_cron": {"type": "string"},
                "enabled": {"type": "boolean", "default": False},
                "run_mode": {"type": "string", "enum": ["manual", "schedule", "manual_or_schedule", "daemon"]},
                "timeout_seconds": {"type": "integer", "default": 300},
                "parameters": {"type": "object"},
                "approval_required": {"type": "boolean", "default": False},
                "owner_agent": {"type": "string", "default": "Data Engineering Agent"},
                "notes": {"type": "string"},
                "actor": {"type": "string", "default": "Data Engineering Agent"},
            },
            "required": ["plugin_key", "job_name", "job_type", "executor_key"],
        },
        "handler": upsert_integration_job_tool,
    },
    "ai_os_run_integration_job": {
        "description": "Run an enabled allowlisted integration job and persist the result. Approval-required jobs are refused.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_key": {"type": "string"},
                "actor": {"type": "string", "default": "Jarvis"},
            },
            "required": ["job_key"],
        },
        "handler": run_integration_job_tool,
    },
    "ai_os_evaluate_provider_assignment_gate": {
        "description": "Evaluate whether a model endpoint or data-source connector can be assigned to an agent task. Creates an inbox block for non-ready providers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "provider_key": {"type": "string"},
                "provider_kind": {"type": "string"},
                "requesting_agent": {"type": "string", "default": "Jarvis"},
                "requested_use": {"type": "string", "default": "provider assignment"},
                "source_kind": {"type": "string"},
                "source_ref": {"type": "string"},
                "target_workspace": {"type": "string", "default": "system"},
                "create_inbox_on_block": {"type": "boolean", "default": True},
                "evidence": {"type": "array", "items": {"type": "object"}},
                "metadata": {"type": "object"},
                "actor": {"type": "string", "default": "Jarvis"},
            },
            "required": ["provider_key"],
        },
        "handler": evaluate_provider_assignment_gate,
    },
    "ai_os_provider_assignment_gates": {
        "description": "Read recent provider assignment gate checks and resulting inbox blocks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "provider_kind": {"type": "string"},
                "assignment_status": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": provider_assignment_gates,
    },
    "ai_os_department_provider_policy_board": {
        "description": "Read department-level provider policies for model endpoints and data-source connectors.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "department_key": {"type": "string"},
                "policy_status": {"type": "string"},
                "limit": {"type": "integer", "default": 80},
            },
        },
        "handler": department_provider_policy_board,
    },
    "ai_os_evaluate_task_provider_gates": {
        "description": "Evaluate provider assignment gates for a specific agent task and update task status if blocked or approval-gated.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer"},
                "actor": {"type": "string", "default": "Jarvis"},
                "context": {"type": "string", "default": "mcp"},
            },
            "required": ["task_id"],
        },
        "handler": evaluate_task_provider_gates,
    },
    "ai_os_task_provider_gate_status": {
        "description": "Read task-level provider gate status so agent work cannot bypass model/data-source readiness controls.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "provider_gate_status": {"type": "string"},
                "owner_agent": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": task_provider_gate_status,
    },
    "ai_os_create_research_idea": {
        "description": "Create a research idea with symbols, thesis, catalyst, scores, owner, and evidence.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "idea_type": {"type": "string", "default": "research_note"},
                "title": {"type": "string"},
                "symbols": {"type": "array", "items": {"type": "string"}},
                "source_kind": {"type": "string"},
                "source_ref": {"type": "string"},
                "thesis": {"type": "string"},
                "catalyst": {"type": "string"},
                "expected_timeframe": {"type": "string"},
                "opportunity_score": {"type": "number"},
                "risk_score": {"type": "number"},
                "owner_agent": {"type": "string", "default": "Research Lead"},
                "evidence": {"type": "array", "items": {"type": "object"}},
                "actor": {"type": "string"},
            },
            "required": ["title"],
        },
        "handler": create_research_idea,
    },
    "ai_os_record_raw_artifact": {
        "description": "Register a raw artifact, browser capture, report, or public-source output in core.raw_artifacts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "artifact_type": {"type": "string", "default": "browser_capture"},
                "title": {"type": "string"},
                "source_url": {"type": "string"},
                "local_path": {"type": "string"},
                "mime_type": {"type": "string", "default": "text/plain"},
                "sensitivity": {"type": "string", "default": "private"},
                "content_text": {"type": "string"},
                "content_hash": {"type": "string"},
                "metadata": {"type": "object"},
                "source_system_name": {"type": "string", "default": "browser mcp capture"},
                "source_type": {"type": "string", "default": "mcp_artifact"},
                "actor": {"type": "string", "default": "Data Steward"},
            },
            "required": ["title"],
        },
        "handler": record_raw_artifact,
    },
    "ai_os_write_obsidian_note": {
        "description": "Write an approved markdown note into structured Obsidian AI OS folders and reindex the vault.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "body": {"type": "string"},
                "folder": {
                    "type": "string",
                    "enum": ["agent_outputs", "architecture", "research", "workflows", "reports", "journal"],
                    "default": "agent_outputs",
                },
                "tags": {"type": "array", "items": {"type": "string"}},
                "source_refs": {"type": "array", "items": {"type": "string"}},
                "actor": {"type": "string", "default": "Knowledge Librarian"},
            },
            "required": ["title", "body"],
        },
        "handler": write_obsidian_note,
    },
    "ai_os_start_browser_run": {
        "description": "Create a browser research/run log row for public-source research or UI inspection. Actual browser control is provided by the browser/Playwright MCP client.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer"},
                "run_type": {"type": "string", "default": "browser_research"},
                "target_url": {"type": "string"},
                "status": {"type": "string", "default": "queued"},
                "notes": {"type": "string"},
                "metadata": {"type": "object"},
                "actor": {"type": "string", "default": "Browser Research Runner"},
                "source_kind": {"type": "string"},
                "source_ref": {"type": "string"},
            },
            "required": ["target_url"],
        },
        "handler": start_browser_run,
    },
    "ai_os_complete_browser_run": {
        "description": "Complete a browser run with page title, text preview, screenshot path, artifact id, notes, and metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "browser_run_id": {"type": "integer"},
                "status": {"type": "string", "default": "done"},
                "actor": {"type": "string", "default": "Browser Research Runner"},
                "page_title": {"type": "string"},
                "extracted_text_preview": {"type": "string"},
                "screenshot_path": {"type": "string"},
                "extracted_artifact_id": {"type": "integer"},
                "notes": {"type": "string"},
                "metadata": {"type": "object"},
            },
            "required": ["browser_run_id"],
        },
        "handler": complete_browser_run,
    },
    "ai_os_browser_runs": {
        "description": "List browser run queue/history with optional status filter.",
        "inputSchema": {"type": "object", "properties": {"status": {"type": "string"}, "limit": {"type": "integer", "default": 30}}},
        "handler": browser_runs,
    },
    "ai_os_create_tradingview_task": {
        "description": "Queue an auditable TradingView chart/screener/browser task. This does not place trades.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_title": {"type": "string"},
                "task_type": {"type": "string", "default": "chart_review"},
                "requested_by": {"type": "string", "default": "Devarsh"},
                "owner_agent": {"type": "string", "default": "Trading Desk Agent"},
                "symbols": {"type": "array", "items": {"type": "string"}},
                "exchange": {"type": "string"},
                "timeframe": {"type": "string"},
                "chart_layout": {"type": "string"},
                "instruction": {"type": "string"},
                "source_ref": {"type": "string"},
                "evidence": {"type": "array", "items": {"type": "object"}},
                "metadata": {"type": "object"},
                "create_inbox": {"type": "boolean", "default": True},
            },
            "required": ["task_title", "instruction"],
        },
        "handler": create_tradingview_task,
    },
    "ai_os_update_tradingview_task": {
        "description": "Update a TradingView task with status, result summary, browser run, artifact, note path, and evidence.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer"},
                "status": {"type": "string"},
                "result_summary": {"type": "string"},
                "browser_run_id": {"type": "integer"},
                "extracted_artifact_id": {"type": "integer"},
                "output_note_path": {"type": "string"},
                "evidence": {"type": "array", "items": {"type": "object"}},
                "metadata": {"type": "object"},
                "actor": {"type": "string", "default": "Trading Desk Agent"},
            },
            "required": ["task_id"],
        },
        "handler": update_tradingview_task,
    },
    "ai_os_execute_tradingview_chart_action": {
        "description": "Open one or more charts in the user's logged-in TradingView Desktop app and update the governed task. This never starts a separate browser, does not claim screenshot capture, and cannot place trades.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer"},
                "task_title": {"type": "string"},
                "symbol": {"type": "string"},
                "symbols": {"type": "array", "items": {"type": "string"}},
                "exchange": {"type": "string", "default": "NSE"},
                "timeframe": {"type": "string", "default": "D"},
                "chart_layout": {"type": "string"},
                "instruction": {"type": "string"},
                "action": {"type": "string", "default": "open_chart_capture"},
                "target_url": {"type": "string"},
                "wait_ms": {"type": "integer", "default": 9000},
                "capture_screenshot": {"type": "boolean", "default": True},
                "actor": {"type": "string", "default": "Trading Desk Agent"},
                "metadata": {"type": "object"},
            },
        },
        "handler": execute_tradingview_chart_action,
    },
    "ai_os_execute_tradingview_template_action": {
        "description": "Execute a named TradingView action template, or create a human-gated approval request for unsafe templates. This does not place trades.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "template_key": {"type": "string"},
                "symbol": {"type": "string"},
                "symbols": {"type": "array", "items": {"type": "string"}},
                "exchange": {"type": "string"},
                "timeframe": {"type": "string"},
                "chart_layout": {"type": "string"},
                "instruction": {"type": "string"},
                "task_title": {"type": "string"},
                "actor": {"type": "string", "default": "Trading Desk Agent"},
                "metadata": {"type": "object"},
            },
            "required": ["template_key"],
        },
        "handler": execute_tradingview_template_action,
    },
    "ai_os_resolve_tradingview_template_approval": {
        "description": "Approve and execute or reject a compiled TradingView chart plan. Only deterministic chart/formula plans can execute; this never places a broker order.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "approval_id": {"type": "integer"},
                "status": {"type": "string", "enum": ["approved", "rejected"]},
                "decided_by": {"type": "string", "default": "Devarsh"},
            },
            "required": ["approval_id", "status"],
        },
        "handler": resolve_tradingview_template_approval,
    },
    "ai_os_tradingview_tasks": {
        "description": "List queued/completed TradingView chart, screener, options, or fundamental-ratio tasks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "symbol": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": tradingview_tasks,
    },
    "ai_os_record_manual_trade": {
        "description": "Record a manual actual trade in the local AI OS ledger. This does not touch broker accounts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "side": {"type": "string"},
                "quantity": {"type": "number"},
                "price": {"type": "number"},
                "trade_ts": {"type": "string"},
                "client_code": {"type": "string"},
                "account_code": {"type": "string"},
                "strategy_key": {"type": "string"},
                "exchange": {"type": "string", "default": "NSE"},
                "instrument_type": {"type": "string", "default": "equity"},
                "status": {"type": "string", "default": "recorded"},
                "thesis": {"type": "string"},
                "setup_type": {"type": "string"},
                "timeframe": {"type": "string"},
                "stop_loss": {"type": "number"},
                "target_price": {"type": "number"},
                "realized_pnl": {"type": "number"},
                "fees": {"type": "number"},
                "source_kind": {"type": "string"},
                "source_ref": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "evidence": {"type": "array", "items": {"type": "object"}},
                "payload": {"type": "object"},
                "created_by": {"type": "string", "default": "Devarsh"},
            },
            "required": ["symbol", "side"],
        },
        "handler": record_manual_trade,
    },
    "ai_os_record_paper_trade": {
        "description": "Record a paper/shadow trade or system-alert outcome for strategy backtracking.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "side": {"type": "string"},
                "quantity": {"type": "number"},
                "price": {"type": "number"},
                "trade_ts": {"type": "string"},
                "execution_mode": {"type": "string", "default": "paper"},
                "strategy_key": {"type": "string"},
                "exchange": {"type": "string", "default": "NSE"},
                "instrument_type": {"type": "string", "default": "equity"},
                "status": {"type": "string", "default": "recorded"},
                "thesis": {"type": "string"},
                "setup_type": {"type": "string"},
                "timeframe": {"type": "string"},
                "stop_loss": {"type": "number"},
                "target_price": {"type": "number"},
                "realized_pnl": {"type": "number"},
                "source_signal_id": {"type": "integer"},
                "alert_event_id": {"type": "integer"},
                "source_kind": {"type": "string", "default": "system_alert"},
                "source_ref": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "evidence": {"type": "array", "items": {"type": "object"}},
                "payload": {"type": "object"},
                "created_by": {"type": "string", "default": "Devarsh"},
            },
            "required": ["symbol", "side"],
        },
        "handler": record_paper_trade,
    },
    "ai_os_trade_activity": {
        "description": "Read manual, paper, shadow, and alert trade activity with optional paper summary.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "execution_mode": {"type": "string"},
                "symbol": {"type": "string"},
                "strategy_key": {"type": "string"},
                "include_paper_summary": {"type": "boolean", "default": True},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": trade_activity,
    },
    "ai_os_create_strategy_intake": {
        "description": "Create a structured strategy intake from Devarsh's natural-language instruction and queue specialist work. No trades are placed.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "intake_key": {"type": "string"},
                "created_by": {"type": "string", "default": "Devarsh"},
                "intake_text": {"type": "string"},
                "strategy_name": {"type": "string"},
                "strategy_family": {"type": "string"},
                "asset_class": {"type": "string"},
                "symbols": {"type": "array", "items": {"type": "string"}},
                "universe": {"type": "string"},
                "timeframe": {"type": "string"},
                "intent_tags": {"type": "array", "items": {"type": "string"}},
                "constraints_text": {"type": "string"},
                "risk_notes": {"type": "string"},
                "requested_outputs": {"type": "array", "items": {"type": "string"}},
                "source_kind": {"type": "string"},
                "source_ref": {"type": "string"},
                "status": {"type": "string", "default": "new"},
                "owner_agent": {"type": "string", "default": "Strategy Intake Agent"},
                "assigned_agents": {"type": "array", "items": {"type": "string"}},
                "structured_spec": {"type": "object"},
                "evidence": {"type": "array", "items": {"type": "object"}},
                "priority": {"type": "string", "default": "high"},
                "create_task": {"type": "boolean", "default": True},
            },
            "required": ["intake_text"],
        },
        "handler": create_strategy_intake,
    },
    "ai_os_strategy_intakes": {
        "description": "List strategy intakes with generated idea and candidate counts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": strategy_intakes,
    },
    "ai_os_strategy_template_library": {
        "description": "List strategy templates with data requirements, gates, readiness, and application counts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "template_family": {"type": "string"},
                "asset_class": {"type": "string"},
                "execution_readiness": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": strategy_template_library,
    },
    "ai_os_create_strategy_from_template": {
        "description": "Queue a strategy candidate from an approved template. This is paper-first and never places trades.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "template_key": {"type": "string"},
                "created_by": {"type": "string", "default": "Devarsh"},
                "actor": {"type": "string"},
                "strategy_name": {"type": "string"},
                "symbols": {"type": "array", "items": {"type": "string"}},
                "universe": {"type": "string"},
                "timeframe": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["template_key"],
        },
        "handler": create_strategy_from_template,
    },
    "ai_os_create_generated_strategy_idea": {
        "description": "Record a generated strategy hypothesis or variant with evidence and optional candidate creation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "idea_key": {"type": "string"},
                "intake_key": {"type": "string"},
                "intake_id": {"type": "integer"},
                "title": {"type": "string"},
                "idea_type": {"type": "string", "default": "strategy_hypothesis"},
                "symbols": {"type": "array", "items": {"type": "string"}},
                "universe": {"type": "string"},
                "timeframe": {"type": "string"},
                "thesis": {"type": "string"},
                "edge_hypothesis": {"type": "string"},
                "entry_rules": {"type": "object"},
                "exit_rules": {"type": "object"},
                "risk_rules": {"type": "object"},
                "data_requirements": {"type": "array", "items": {"type": "string"}},
                "assumptions": {"type": "array", "items": {"type": "string"}},
                "invalidation_tests": {"type": "array", "items": {"type": "string"}},
                "priority_score": {"type": "number"},
                "risk_score": {"type": "number"},
                "status": {"type": "string", "default": "candidate"},
                "owner_agent": {"type": "string", "default": "Strategy Generator"},
                "evidence": {"type": "array", "items": {"type": "object"}},
                "candidate_key": {"type": "string"},
                "create_candidate": {"type": "boolean", "default": True},
            },
            "required": ["title", "thesis"],
        },
        "handler": create_generated_strategy_idea,
    },
    "ai_os_strategy_lab": {
        "description": "Read strategy intakes, generated ideas, candidates, backtest counts, optimization counts, and validation counts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": strategy_lab,
    },
    "ai_os_parse_strategy_dsl": {
        "description": "Parse a candidate or user-provided strategy DSL into deterministic normalized rules. Does not execute trades.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "strategy_id": {"type": "integer"},
                "candidate_key": {"type": "string"},
                "strategy_key": {"type": "string"},
                "strategy_name": {"type": "string"},
                "dsl_text": {"type": "string"},
                "actor": {"type": "string", "default": "Strategy Intake Agent"},
            },
        },
        "handler": parse_strategy_dsl,
    },
    "ai_os_strategy_data_quality_gate": {
        "description": "Run and record the required real OHLCV data-quality preflight gate for a strategy candidate before backtesting.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "strategy_id": {"type": "integer"},
                "candidate_key": {"type": "string"},
                "strategy_key": {"type": "string"},
                "strategy_name": {"type": "string"},
                "symbols": {"type": "array", "items": {"type": "string"}},
                "timeframe": {"type": "string"},
                "min_rows_per_symbol": {"type": "integer", "default": 50},
                "min_total_rows": {"type": "integer", "default": 500},
                "actor": {"type": "string", "default": "Backtest Engineer"},
            },
        },
        "handler": strategy_data_quality_gate,
    },
    "ai_os_strategy_dsl_status": {
        "description": "Read strategy DSL parse status and latest backtest data-quality gate results.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "data_quality_status": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": strategy_dsl_status,
    },
    "ai_os_run_strategy_quant_analytics": {
        "description": "Run regime, factor, capacity, correlation, and portfolio optimizer analytics from real OHLCV/backtest data.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_key": {"type": "string"},
                "strategy_ids": {"type": "array", "items": {"type": "integer"}},
                "timeframe": {"type": "string", "default": "5m"},
                "limit": {"type": "integer", "default": 10},
                "max_symbols": {"type": "integer", "default": 14},
                "cost_bps": {"type": "number", "default": 3},
                "slippage_bps": {"type": "number", "default": 2},
                "participation_rate": {"type": "number", "default": 0.05},
                "actor": {"type": "string", "default": "Quant Analytics Agent"},
            },
        },
        "handler": run_strategy_quant_analytics,
    },
    "ai_os_strategy_quant_analytics": {
        "description": "Read latest strategy regime, factor, capacity, correlation, and portfolio optimizer analytics.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_key": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": strategy_quant_analytics,
    },
    "ai_os_run_institutional_portfolio_risk": {
        "description": "Run historical, bootstrap Monte Carlo, stress, liquidity, concentration, and market-factor risk analytics on real active book positions. Advisory only; cannot authorize capital or execution.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_key": {"type": "string"},
                "lookback_days": {"type": "integer", "default": 756},
                "simulations": {"type": "integer", "default": 20000},
                "seed": {"type": "integer", "default": 20260715},
                "actor": {"type": "string", "default": "Portfolio Risk Analyst"},
            },
        },
        "handler": run_institutional_portfolio_risk,
    },
    "ai_os_institutional_portfolio_risk": {
        "description": "Read the latest institutional portfolio VaR/ES, bootstrap paths, stress, liquidity, factor, concentration, coverage, and lineage evidence. Advisory only.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 80},
            },
        },
        "handler": institutional_portfolio_risk,
    },
    "ai_os_capital_allocation_control_board": {
        "description": "Read client/book policy readiness, real allocation, legacy-unverified defaults, drift analysis, risk budgets, committee state, and execution locks.",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 120}},
        },
        "handler": capital_allocation_control_board,
    },
    "ai_os_model_runtime_control": {
        "description": "Read local-first route readiness, all-agent assignments, privacy and cache policy, cost caps, call decisions, and escalation state without exposing raw prompts.",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 100}},
        },
        "handler": model_runtime_control,
    },
    "ai_os_agent_model_assignment_completeness": {
        "description": "Read active-agent route and explicit model-catalog assignment completeness, including any incomplete agents. Never exposes credentials or invokes a model.",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 100}},
        },
        "handler": agent_model_assignment_completeness,
    },
    "ai_os_request_model_escalation": {
        "description": "Request a privacy-checked, human-approved higher-cost model escalation for an existing model-call decision. Never invokes a cloud model or trading action.",
        "inputSchema": {
            "type": "object",
            "required": ["decision_id", "reason"],
            "properties": {
                "decision_id": {"type": "integer"},
                "reason": {"type": "string"},
                "actor": {"type": "string", "default": "Devarsh"},
            },
        },
        "handler": request_model_escalation,
    },
    "ai_os_propose_capital_policy": {
        "description": "Create an operator-supplied client capital/risk policy covering every active book and totaling 100%. Routes independent risk review; no capital or broker authority.",
        "inputSchema": {
            "type": "object",
            "required": ["client_code", "rules"],
            "properties": {
                "client_code": {"type": "string"},
                "proposal_key": {"type": "string"},
                "proposal_name": {"type": "string"},
                "capital_basis_type": {"type": "string", "enum": ["gross_exposure_only", "net_liquidation_value", "operator_supplied_total_capital"]},
                "total_capital_basis": {"type": "number"},
                "rules": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["book_key", "target_pct", "min_pct", "max_pct"],
                        "properties": {
                            "book_key": {"type": "string"},
                            "target_pct": {"type": "number"},
                            "min_pct": {"type": "number"},
                            "max_pct": {"type": "number"},
                            "risk_budget_var_99_10d_pct": {"type": "number"},
                            "max_drawdown_budget_pct": {"type": "number"},
                            "minimum_liquidity_coverage_pct": {"type": "number", "default": 80},
                            "rationale": {"type": "string"},
                        },
                    },
                },
                "actor": {"type": "string", "default": "Capital Allocation Agent"},
            },
        },
        "handler": propose_capital_policy,
    },
    "ai_os_run_capital_allocation_analysis": {
        "description": "Calculate advisory-only book drift and risk-budget gates from a client policy, real positions, and latest institutional risk evidence.",
        "inputSchema": {
            "type": "object",
            "required": ["proposal_id"],
            "properties": {
                "proposal_id": {"type": "integer"},
                "run_key": {"type": "string"},
                "minimum_coverage_pct": {"type": "number", "default": 80},
                "actor": {"type": "string", "default": "Capital Allocation Agent"},
            },
        },
        "handler": run_capital_allocation_analysis,
    },
    "ai_os_capital_committee_decision": {
        "description": "Record approve, reject, revise, or defer for a Capital Allocation Committee review. Approve only routes a separate Devarsh approval and never authorizes a trade.",
        "inputSchema": {
            "type": "object",
            "required": ["review_id", "decision"],
            "properties": {
                "review_id": {"type": "integer"},
                "decision": {"type": "string", "enum": ["approve", "reject", "revise", "defer"]},
                "decision_notes": {"type": "string"},
                "actor": {"type": "string", "default": "Charlie Munger"},
            },
        },
        "handler": decide_capital_committee,
    },
    "ai_os_run_strategy_portfolio_allocation": {
        "description": "Create a paper-only strategy portfolio allocation and probability-of-ruin metrics from a quant analytics run.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "allocation_key": {"type": "string"},
                "analytics_run_key": {"type": "string"},
                "timeframe": {"type": "string", "default": "5m"},
                "capital_base": {"type": "number", "default": 1000000},
                "max_weight": {"type": "number", "default": 0.35},
                "ruin_threshold_pct": {"type": "number", "default": 0.2},
                "horizon_bars": {"type": "integer", "default": 252},
                "simulation_count": {"type": "integer", "default": 1000},
                "seed": {"type": "integer", "default": 260706},
                "actor": {"type": "string", "default": "Strategy Portfolio Manager"},
            },
        },
        "handler": run_strategy_portfolio_allocation,
    },
    "ai_os_strategy_portfolio_allocation": {
        "description": "Read paper strategy portfolio allocation and probability-of-ruin metrics.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "allocation_key": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": strategy_portfolio_allocation,
    },
    "ai_os_run_strategy_retirement_review": {
        "description": "Create strategy retirement reviews and dispatch Quant specialist assignments from latest real analytics/allocation evidence.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "review_key_prefix": {"type": "string", "default": "retire"},
                "analytics_run_key": {"type": "string"},
                "allocation_key": {"type": "string"},
                "actor": {"type": "string", "default": "Strategy Retirement Agent"},
            },
        },
        "handler": run_strategy_retirement_review,
    },
    "ai_os_strategy_retirement_queue": {
        "description": "Read strategy retirement queue, Quant specialist assignments, and Quant Lab dashboard v2 rows.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "review_status": {"type": "string"},
                "recommended_action": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": strategy_retirement_queue,
    },
    "ai_os_run_model_validation_sweep": {
        "description": "Run deterministic model-validation reviews from latest strategy evidence. This does not approve live execution.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "validation_key_prefix": {"type": "string", "default": "modelval"},
                "actor": {"type": "string", "default": "Model Validation Agent"},
                "limit": {"type": "integer", "default": 25},
            },
        },
        "handler": run_model_validation_sweep,
    },
    "ai_os_model_validation_dashboard": {
        "description": "Read model validation dashboard rows and promotion-board gate status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "validation_gate_status": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": model_validation_dashboard,
    },
    "ai_os_strategy_promotion_board": {
        "description": "Read strategy promotion board from backtest, DSL, validation, committee, paper, and limited-live gates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "promotion_stage": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": strategy_promotion_board,
    },
    "ai_os_strategy_arsenal_control_board": {
        "description": "Read the unified Strategy Arsenal with candidate provenance, eight independent gates, next safe action, and execution-lock evidence.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "origin_type": {"type": "string", "enum": ["operator_submitted", "system_discovery", "template_library", "research_sourced", "imported_or_other"]},
                "promotion_stage": {"type": "string"},
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 80},
            },
        },
        "handler": strategy_arsenal_control_board,
    },
    "ai_os_run_user_defined_strategy_optimizer": {
        "description": "Create a strategy from user input and run parser, data gate, baseline backtest, and optimizer using real OHLCV. This never enables live execution.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_key": {"type": "string"},
                "actor": {"type": "string", "default": "Devarsh"},
                "strategy_name": {"type": "string"},
                "intake_text": {"type": "string"},
                "dsl_text": {"type": "string"},
                "asset_class": {"type": "string", "default": "equity"},
                "symbols": {"type": "array", "items": {"type": "string"}},
                "universe": {"type": "string", "default": "NSE"},
                "timeframe": {"type": "string", "default": "5m"},
                "template": {"type": "string", "enum": ["momentum", "mean_reversion", "breakout", "low_volatility"], "default": "momentum"},
                "constraints_text": {"type": "string"},
                "risk_notes": {"type": "string"},
                "cost_bps": {"type": "number", "default": 3},
                "slippage_bps": {"type": "number", "default": 2},
                "max_symbols": {"type": "integer", "default": 14},
                "min_rows_per_symbol": {"type": "integer", "default": 50},
                "min_total_rows": {"type": "integer"},
            },
            "required": ["strategy_name", "intake_text"],
        },
        "handler": run_user_defined_strategy_optimizer,
    },
    "ai_os_user_defined_strategy_optimizer_runs": {
        "description": "Read user-defined strategy optimizer workflow runs and stage results.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "limit": {"type": "integer", "default": 25},
            },
        },
        "handler": user_defined_strategy_optimizer_runs,
    },
    "ai_os_run_strategy_discovery": {
        "description": "Scan internal research, journal patterns, signals, and component patterns into strategy ideas, optionally routing top ideas through the safe optimizer pipeline.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_key": {"type": "string"},
                "actor": {"type": "string", "default": "Strategy Discovery Agent"},
                "sources": {"type": "string", "default": "research,journals,signals,components"},
                "per_source_limit": {"type": "integer", "default": 8},
                "max_candidates": {"type": "integer", "default": 16},
                "route_top": {"type": "integer", "default": 2},
            },
        },
        "handler": run_strategy_discovery,
    },
    "ai_os_strategy_discovery_runs": {
        "description": "Read automatic strategy discovery runs, generated ideas, optimizer routing, and gate status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "limit": {"type": "integer", "default": 25},
            },
        },
        "handler": strategy_discovery_runs,
    },
    "ai_os_resolve_strategy_discovery_triage": {
        "description": "Resolve a discovered strategy idea into reject, request more evidence, Quant Lab, Special Situations, or committee review. This never approves live execution.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "discovery_candidate_id": {"type": "integer"},
                "decision": {
                    "type": "string",
                    "enum": ["reject", "request_more_evidence", "route_quant_lab", "route_special_situation", "open_committee_review"],
                },
                "actor": {"type": "string", "default": "Charlie Munger"},
                "notes": {"type": "string"},
            },
            "required": ["discovery_candidate_id", "decision"],
        },
        "handler": resolve_strategy_discovery_triage,
    },
    "ai_os_strategy_discovery_triage_queue": {
        "description": "Read discovered strategy idea triage queue and recent Charlie/Jarvis decisions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "decision": {"type": "string"},
                "limit": {"type": "integer", "default": 25},
            },
        },
        "handler": strategy_discovery_triage_queue,
    },
    "ai_os_strategy_discovery_governance": {
        "description": "Read canonical strategy opportunities, duplicate suppression, cooldown reuse, provenance, and triage state.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": strategy_discovery_governance,
    },
    "ai_os_build_strategy_idea_dossiers": {
        "description": "Build persistent strategy idea dossiers from repeated discoveries and triage decisions, with Obsidian writeback. This never approves trades.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_key": {"type": "string"},
                "actor": {"type": "string", "default": "Strategy Dossier Agent"},
                "limit": {"type": "integer", "default": 250},
                "max_dossiers": {"type": "integer", "default": 100},
                "no_notes": {"type": "boolean", "default": False},
            },
        },
        "handler": build_strategy_idea_dossiers,
    },
    "ai_os_search_strategy_idea_dossiers": {
        "description": "Search persistent strategy idea dossiers through Qdrant vector retrieval with SQL lexical fallback. This reads memory and never approves trades.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "run_key": {"type": "string"},
                "actor": {"type": "string", "default": "Strategy Dossier Search Agent"},
                "limit": {"type": "integer", "default": 8},
            },
            "required": ["query"],
        },
        "handler": search_strategy_idea_dossiers,
    },
    "ai_os_run_strategy_dossier_action": {
        "description": "Run a gated action from a persistent strategy dossier: request evidence, route Quant Lab, route Special Situations, open committee review, or generate committee memo. This never approves paper/live execution.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dossier_id": {"type": "integer"},
                "action": {
                    "type": "string",
                    "enum": ["request_more_evidence", "route_quant_lab", "route_special_situation", "open_committee_review", "generate_committee_memo"],
                },
                "run_key": {"type": "string"},
                "actor": {"type": "string", "default": "Charlie Munger"},
                "notes": {"type": "string"},
            },
            "required": ["dossier_id", "action"],
        },
        "handler": run_strategy_dossier_action,
    },
    "ai_os_strategy_dossier_actions": {
        "description": "Read recent gated actions taken from persistent strategy dossiers into specialist or committee workflows.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 25},
            },
        },
        "handler": strategy_dossier_actions,
    },
    "ai_os_strategy_idea_dossiers": {
        "description": "Read persistent strategy idea dossiers with evidence timelines, linked discovery counts, triage, committee, and note paths.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "limit": {"type": "integer", "default": 25},
            },
        },
        "handler": strategy_idea_dossiers,
    },
    "ai_os_ingest_market_news": {
        "description": "Ingest active RSS/news feeds into market.news_items and create source-backed catalyst research ideas. This does not approve trading.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_key": {"type": "string"},
                "actor": {"type": "string", "default": "News Analyst"},
                "feed_keys": {"type": "string"},
                "feed_limit": {"type": "integer", "default": 12},
                "per_feed": {"type": "integer", "default": 8},
                "timeout": {"type": "integer", "default": 12},
            },
        },
        "handler": ingest_market_news,
    },
    "ai_os_run_strategy_discovery_scheduler": {
        "description": "Run news, NSE/BSE filings, bounded filing extraction, and automatic strategy discovery as one auditable scheduler job. Broker and autonomous live execution stay disabled.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_key": {"type": "string"},
                "actor": {"type": "string", "default": "Strategy Discovery Agent"},
                "interval_seconds": {"type": "integer", "default": 3600},
                "sources": {"type": "string", "default": "research,journals,signals,components"},
                "per_source_limit": {"type": "integer", "default": 8},
                "max_candidates": {"type": "integer", "default": 16},
                "route_top": {"type": "integer", "default": 1},
                "news_feed_keys": {"type": "string"},
                "news_feed_limit": {"type": "integer", "default": 12},
                "news_per_feed": {"type": "integer", "default": 6},
                "enable_filings": {"type": "boolean", "default": False},
                "filing_lookback_days": {"type": "integer", "default": 2},
                "filing_limit": {"type": "integer", "default": 250},
                "filing_timeout": {"type": "integer", "default": 300},
                "enable_filing_extraction": {"type": "boolean", "default": False},
                "filing_extraction_limit": {"type": "integer", "default": 4},
                "filing_extraction_timeout": {"type": "integer", "default": 300},
                "disable_news": {"type": "boolean", "default": False},
            },
        },
        "handler": run_strategy_discovery_scheduler,
    },
    "ai_os_strategy_discovery_scheduler_runs": {
        "description": "Read strategy discovery scheduler, news ingestion, RSS health, filing collection, extraction, and latest news evidence.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 25},
            },
        },
        "handler": strategy_discovery_scheduler_runs,
    },
    "ai_os_runtime_daemon_health": {
        "description": "Read the persisted heartbeat, cadence, enabled workloads, and latest pass status for the 24/7 AI OS daemon.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": runtime_daemon_health,
    },
    "ai_os_agent_capability_readiness": {
        "description": "Read evidence-backed employee activation, role tool entitlements, operating mode, and model-readiness separation.",
        "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 120}}},
        "handler": agent_capability_readiness,
    },
    "ai_os_fund_function_coverage": {
        "description": "Read every hedge-fund and operating-office function with its owner, independent reviewer, risk challenger, and coverage status.",
        "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 120}}},
        "handler": fund_function_coverage,
    },
    "ai_os_macro_source_readiness": {
        "description": "Read verified World Bank and ECB observations plus credential-gated FRED readiness.",
        "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 100}}},
        "handler": macro_source_readiness,
    },
    "ai_os_ingest_public_macro_data": {
        "description": "Fetch verified public World Bank and ECB observations and store source lineage and health evidence. No seed data or trading action.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": ingest_public_macro_data,
    },
    "ai_os_run_trade_journal_strategy_mining": {
        "description": "Mine real trade journals and trade activity rows into strategy hypotheses. This never approves live execution.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_key": {"type": "string", "default": "journal_mining"},
                "actor": {"type": "string", "default": "Strategy Generator"},
                "min_trades": {"type": "integer", "default": 3},
                "max_patterns": {"type": "integer", "default": 10},
                "allow_thin_sample": {"type": "boolean", "default": False},
            },
        },
        "handler": run_trade_journal_strategy_mining,
    },
    "ai_os_trade_journal_strategy_ideas": {
        "description": "Read journal-mined patterns and generated strategy ideas with sample-size gates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "research_gate": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": trade_journal_strategy_ideas,
    },
    "ai_os_queue_strategy_backtest": {
        "description": "Queue a local backtest run for an existing strategy candidate. This does not execute trades.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "strategy_id": {"type": "integer"},
                "candidate_key": {"type": "string"},
                "strategy_key": {"type": "string"},
                "strategy_name": {"type": "string"},
                "run_status": {"type": "string", "default": "queued"},
                "data_start": {"type": "string"},
                "data_end": {"type": "string"},
                "universe": {"type": "string"},
                "timeframe": {"type": "string"},
                "metrics": {"type": "object"},
                "diagnostics": {"type": "object"},
                "artifact_path": {"type": "string"},
                "priority": {"type": "string", "default": "high"},
                "evidence": {"type": "array", "items": {"type": "object"}},
                "create_inbox": {"type": "boolean", "default": True},
                "actor": {"type": "string", "default": "Backtest Engineer"},
            },
        },
        "handler": queue_strategy_backtest,
    },
    "ai_os_record_strategy_optimization": {
        "description": "Record an optimization or walk-forward run for an existing strategy candidate.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "strategy_id": {"type": "integer"},
                "candidate_key": {"type": "string"},
                "strategy_key": {"type": "string"},
                "strategy_name": {"type": "string"},
                "backtest_run_id": {"type": "integer"},
                "run_name": {"type": "string"},
                "optimizer_type": {"type": "string", "default": "parameter_search"},
                "status": {"type": "string", "default": "queued"},
                "objective": {"type": "string"},
                "parameter_space": {"type": "object"},
                "constraints": {"type": "object"},
                "data_start": {"type": "string"},
                "data_end": {"type": "string"},
                "metrics": {"type": "object"},
                "diagnostics": {"type": "object"},
                "artifact_path": {"type": "string"},
                "evidence": {"type": "array", "items": {"type": "object"}},
                "actor": {"type": "string", "default": "Optimizer Agent"},
            },
        },
        "handler": record_strategy_optimization,
    },
    "ai_os_record_strategy_validation": {
        "description": "Record a model-validation review for a strategy, backtest, or optimization run.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "strategy_id": {"type": "integer"},
                "candidate_key": {"type": "string"},
                "strategy_key": {"type": "string"},
                "strategy_name": {"type": "string"},
                "backtest_run_id": {"type": "integer"},
                "optimization_run_id": {"type": "integer"},
                "reviewer_agent": {"type": "string", "default": "Model Validation Agent"},
                "review_status": {"type": "string", "default": "draft"},
                "decision": {"type": "string"},
                "leakage_risk": {"type": "string"},
                "overfit_risk": {"type": "string"},
                "transaction_cost_notes": {"type": "string"},
                "sample_size_notes": {"type": "string"},
                "required_fixes": {"type": "array", "items": {"type": "string"}},
                "issues": {"type": "array", "items": {"type": "object"}},
                "evidence": {"type": "array", "items": {"type": "object"}},
            },
        },
        "handler": record_strategy_validation,
    },
    "ai_os_upsert_client": {
        "description": "Compatibility name for staging governed client onboarding. It creates suitability and approval records; no client/account is activated until dedicated human approval.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "client_code": {"type": "string"},
                "display_name": {"type": "string"},
                "risk_profile": {"type": "string"},
                "sensitivity": {"type": "string", "default": "client_private"},
                "investment_policy": {"type": "object"},
                "broker": {"type": "string"},
                "account_code": {"type": "string"},
                "account_name": {"type": "string"},
                "account_type": {"type": "string", "default": "investment"},
                "base_currency": {"type": "string", "default": "INR"},
                "notes": {"type": "string"},
                "objectives": {"type": "array", "items": {"type": "string"}},
                "investment_horizon": {"type": "string"},
                "risk_tolerance": {"type": "string"},
                "risk_capacity": {"type": "string"},
                "suitability_status": {"type": "string", "enum": ["needs_review", "suitable", "conditionally_suitable", "unsuitable"]},
                "source_evidence": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["client_code", "display_name", "risk_profile", "objectives", "investment_horizon", "risk_tolerance", "risk_capacity", "source_evidence"],
        },
        "handler": upsert_client,
    },
    "ai_os_stage_holding_update": {
        "description": "Stage a manual holding update for an existing client/account. Review is expected before applying it into live positions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "client_code": {"type": "string"},
                "account_code": {"type": "string"},
                "symbol": {"type": "string"},
                "exchange": {"type": "string", "default": "NSE"},
                "instrument_type": {"type": "string", "default": "equity"},
                "quantity": {"type": "number"},
                "average_price": {"type": "number"},
                "market_price": {"type": "number"},
                "market_value": {"type": "number"},
                "as_of": {"type": "string"},
                "update_reason": {"type": "string"},
            },
            "required": ["client_code", "account_code", "symbol", "quantity"],
        },
        "handler": stage_holding_update,
    },
    "ai_os_apply_holding_update": {
        "description": "Resolve and atomically apply or reject a pending holding update. Approval requires evidence and only writes the local warehouse; it never places broker orders.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "update_id": {"type": "integer"},
                "applied_by": {"type": "string", "default": "Devarsh"},
                "decision": {"type": "string", "enum": ["approved", "rejected"], "default": "approved"},
                "decision_notes": {"type": "string"},
                "evidence": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["update_id", "decision_notes", "evidence"],
        },
        "handler": apply_holding_update,
    },
    "ai_os_client_onboarding_control": {
        "description": "Stage or resolve a governed client onboarding case with objectives, suitability, account scope, source evidence, and human approval.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["stage", "approve", "reject", "resolve"]},
                "case_id": {"type": "integer"},
                "client_code": {"type": "string"},
                "display_name": {"type": "string"},
                "risk_profile": {"type": "string"},
                "objectives": {"type": "array", "items": {"type": "string"}},
                "constraints": {"type": "array", "items": {"type": "string"}},
                "investment_horizon": {"type": "string"},
                "liquidity_needs": {"type": "string"},
                "risk_tolerance": {"type": "string"},
                "risk_capacity": {"type": "string"},
                "suitability_status": {"type": "string"},
                "source_evidence": {"type": "array", "items": {"type": "object"}},
                "account": {"type": "object"},
                "decision": {"type": "string"},
                "decision_notes": {"type": "string"},
                "actor": {"type": "string"}
            }
        },
        "handler": client_onboarding_control,
    },
    "ai_os_client_account_change_control": {
        "description": "Stage or resolve approval-gated account create, update, deactivate, or reactivate requests. No broker write is possible.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["stage", "approve", "reject", "resolve"]},
                "request_id": {"type": "integer"},
                "client_code": {"type": "string"},
                "account_code": {"type": "string"},
                "change_type": {"type": "string", "enum": ["create", "update", "deactivate", "reactivate"]},
                "requested_values": {"type": "object"},
                "reason": {"type": "string"},
                "source_evidence": {"type": "array", "items": {"type": "object"}},
                "decision": {"type": "string"},
                "decision_notes": {"type": "string"},
                "actor": {"type": "string"}
            }
        },
        "handler": client_account_change_control,
    },
    "ai_os_holding_reconciliation_control": {
        "description": "Record normalized source holding observations or reconcile their latest snapshot against the warehouse position book with symbol-level breaks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["observe", "reconcile"]},
                "client_code": {"type": "string"},
                "account_code": {"type": "string"},
                "source_label": {"type": "string"},
                "as_of": {"type": "string"},
                "positions": {"type": "array", "items": {"type": "object"}},
                "evidence": {"type": "array", "items": {"type": "object"}},
                "actor": {"type": "string"}
            },
            "required": ["action", "account_code", "source_label"]
        },
        "handler": holding_reconciliation_control,
    },
    "ai_os_client_cash_ledger_control": {
        "description": "Stage or resolve an approval-gated, source-backed client cash entry. It updates only the local accounting ledger and never calls a broker.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["stage", "approve", "reject", "resolve"]},
                "entry_id": {"type": "integer"},
                "client_code": {"type": "string"},
                "account_code": {"type": "string"},
                "entry_ts": {"type": "string"},
                "entry_type": {"type": "string", "enum": ["opening_balance", "contribution", "withdrawal", "dividend", "interest", "fee", "tax", "broker_charge", "cash_adjustment", "transfer"]},
                "flow_class": {"type": "string", "enum": ["external", "income", "expense", "internal", "balance"]},
                "amount": {"type": "number"},
                "currency": {"type": "string", "default": "INR"},
                "description": {"type": "string"},
                "source_ref": {"type": "string"},
                "source_evidence": {"type": "array", "items": {"type": "object"}},
                "decision": {"type": "string", "enum": ["approved", "rejected"]},
                "decision_notes": {"type": "string"},
                "actor": {"type": "string"}
            }
        },
        "handler": client_cash_ledger_control,
    },
    "ai_os_client_accounting_run": {
        "description": "Rebuild source-backed FIFO long/short tax lots, broker/current NAV evidence, benchmark links, period performance, and attribution. Missing inputs remain explicitly incomplete.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "account_code": {"type": "string"},
                "actor": {"type": "string", "default": "Performance Attribution Agent"}
            }
        },
        "handler": client_accounting_run,
    },
    "ai_os_client_report_delivery_control": {
        "description": "Approve or reject a prepared client-report delivery queue item. This records governance only; external sending remains disabled.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["approve", "reject", "resolve"]},
                "queue_id": {"type": "integer"},
                "decision": {"type": "string", "enum": ["approved", "rejected"]},
                "decision_notes": {"type": "string"},
                "actor": {"type": "string", "default": "Devarsh"}
            },
            "required": ["queue_id"]
        },
        "handler": client_report_delivery_control,
    },
    "ai_os_client_3081282_summary": {
        "description": "Return imported client 3081282 transaction summary metrics and dashboard path.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": client_3081282_summary,
    },
    "ai_os_client_3081282_symbol_dates": {
        "description": "List symbol-level first/last buy and sell dates for client 3081282.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "instrument_type": {"type": "string", "enum": ["equity", "option"]},
                "open_only": {"type": "boolean", "default": False},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": client_3081282_symbol_dates,
    },
    "ai_os_client_3081282_trade_timeline": {
        "description": "List imported broker trade rows for client 3081282 with optional symbol, side, and instrument filters.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "side": {"type": "string", "enum": ["B", "S", "BUY", "SELL"]},
                "instrument_type": {"type": "string", "enum": ["equity", "option"]},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": client_3081282_trade_timeline,
    },
    "ai_os_research_outputs": {
        "description": "Search indexed AI-generated research reports, dashboards, models, source audits, and data packs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "artifact_family": {
                    "type": "string",
                    "enum": ["research_report", "dashboard", "financial_model", "source_audit", "executive_summary", "data_pack", "research_note"],
                },
                "company_or_topic": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": research_outputs,
    },
    "ai_os_research_output_detail": {
        "description": "Get full metadata and summary for one indexed AI-generated research artifact.",
        "inputSchema": {"type": "object", "properties": {"artifact_id": {"type": "integer"}}, "required": ["artifact_id"]},
        "handler": research_output_detail,
    },
    "ai_os_refresh_research_hub": {
        "description": "Refresh indexed Codex/Claude/cowork research reports, dashboards, models, and data packs into the research hub.",
        "inputSchema": {"type": "object", "properties": {"actor": {"type": "string", "default": "Knowledge Librarian"}}},
        "handler": refresh_research_hub,
    },
    "ai_os_research_hub_summary": {
        "description": "Read one-place research hub counts and latest research artifacts.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": research_hub_summary,
    },
    "ai_os_fincept_component_review": {
        "description": "Return FinceptTerminal source-system, component-review, and license-boundary notes.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": fincept_component_review,
    },
    "ai_os_fincept_install_status": {
        "description": "Return local FinceptTerminal install/build status, launch paths, runtime notes, and installed component map.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": fincept_install_status,
    },
    "ai_os_search_obsidian_notes": {
        "description": "Search indexed Obsidian notes by path, title, or summary.",
        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "default": 10}}},
        "handler": search_obsidian_notes,
    },
    "ai_os_recent_trading_signals": {
        "description": "List recent imported TradingView/trading signals.",
        "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 25}}},
        "handler": recent_trading_signals,
    },
    "ai_os_latest_positions": {
        "description": "List latest imported portfolio positions.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": latest_positions,
    },
    "ai_os_run_p2cursor_reconciliation": {
        "description": "Run p2cursor-vs-current statement reconciliation for a client. Defaults to Tushit client 3081832.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "client_code": {"type": "string", "default": "3081832"},
                "actor": {"type": "string", "default": "Jarvis MCP"},
            },
        },
        "handler": run_p2cursor_reconciliation,
    },
    "ai_os_run_public_data_source_check": {
        "description": "Run public SEC/NSE/BSE data-source connectivity checks and store the results.",
        "inputSchema": {"type": "object", "properties": {"actor": {"type": "string", "default": "Data Steward"}}},
        "handler": run_public_data_source_check,
    },
    "ai_os_data_source_checks": {
        "description": "Read latest public data-source connectivity check results.",
        "inputSchema": {"type": "object", "properties": {"source_key": {"type": "string"}, "limit": {"type": "integer", "default": 50}}},
        "handler": data_source_checks,
    },
    "ai_os_reindex_obsidian": {
        "description": "Reindex Obsidian note metadata into the warehouse. Writes only to Postgres knowledge tables.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": reindex_obsidian,
    },
}


def send_response(request_id: object, result: object = None, error: dict | None = None) -> None:
    response: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
    if error is not None:
        response["error"] = error
    else:
        response["result"] = result
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()


def handle_request(message: dict) -> None:
    request_id = message.get("id")
    method = message.get("method")
    params = message.get("params") or {}
    if method == "initialize":
        send_response(
            request_id,
            {
                "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "ai-os-local-mcp", "version": "0.1.0"},
            },
        )
        return
    if method == "tools/list":
        send_response(
            request_id,
            {
                "tools": [
                    {"name": name, "description": config["description"], "inputSchema": config["inputSchema"]}
                    for name, config in TOOLS.items()
                ]
            },
        )
        return
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name not in TOOLS:
            send_response(request_id, error={"code": -32602, "message": f"Unknown tool: {name}"})
            return
        try:
            send_response(request_id, TOOLS[name]["handler"](arguments))
        except Exception as exc:  # noqa: BLE001
            send_response(request_id, error={"code": -32000, "message": f"{type(exc).__name__}: {exc}"})
        return
    if method and method.startswith("notifications/"):
        return
    send_response(request_id, error={"code": -32601, "message": f"Unknown method: {method}"})


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            handle_request(json.loads(line))
        except json.JSONDecodeError as exc:
            send_response(None, error={"code": -32700, "message": str(exc)})
    return 0


if __name__ == "__main__":
    sys.exit(main())
