#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


POSTGRES_PASSWORD = os.environ.get("AI_OS_POSTGRES_PASSWORD", "ai_os_local_dev_change_me")
POSTGRES_PORT = os.environ.get("AI_OS_POSTGRES_PORT", "54329")
ACTOR_DEFAULT = "Fundamental Research Factory"

SECTION_SPECS: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("executive_conclusion", "Executive Investment Conclusion", ("bear_case", "risk", "portfolio_fit"), ()),
    ("industry_value_chain", "Industry Structure And Value-Chain Map", ("industry",), ("industry_report",)),
    ("business_model_unit_economics", "Business Model And Unit Economics", ("business_model", "financial_quality"), ("annual_report", "investor_presentation")),
    ("segments_geography_customers", "Products, Segments, Geography And Customers", ("business_model", "industry"), ("annual_report", "investor_presentation")),
    ("market_size_share_competition", "Market Size, Share And Competitive Position", ("industry", "moat"), ("industry_report", "investor_presentation")),
    ("moat_durability", "Moat Durability", ("moat", "bear_case"), ("annual_report", "earnings_call")),
    ("management_capital_allocation", "Management And Capital-Allocation History", ("management", "capital_allocation"), ("annual_letter", "earnings_call", "annual_report")),
    ("ten_year_financial_teardown", "Ten-Year Financial Teardown", ("financial_quality",), ("annual_report", "financial_statement")),
    ("forensic_accounting_governance", "Forensic Accounting And Governance", ("forensic_accounting", "governance"), ("annual_report", "credit_rating")),
    ("peer_benchmarking", "Peer Benchmarking", ("industry", "valuation"), ("industry_report", "financial_statement")),
    ("operating_scenarios", "Base, Bull And Bear Operating Scenarios", ("financial_quality", "bear_case", "risk"), ()),
    ("valuation", "DCF, Reverse DCF, Multiples And Monte Carlo", ("valuation",), ("valuation_work", "financial_statement")),
    ("catalysts_thesis_killers_monitoring", "Catalysts, Thesis Killers And Monitoring", ("bear_case", "risk"), ("corporate_filing", "material_news")),
    ("portfolio_fit_opportunity_cost", "Portfolio Fit, Position Sizing And Opportunity Cost", ("portfolio_fit", "risk"), ()),
    ("specialist_opinions_committee_decision", "Specialist Opinions, Dissent And Committee Decision", tuple(), tuple()),
)

REQUIRED_SPECIALISTS = {
    "business_model", "moat", "industry", "management", "governance",
    "capital_allocation", "financial_quality", "forensic_accounting",
    "valuation", "bear_case", "risk", "portfolio_fit",
}
ACCEPTED_OPINION_STATUSES = {"evidence_complete", "reviewed", "dissent"}

TRIGGER_TYPE_BY_SOURCE = {
    "results": "results",
    "quarterly_results": "results",
    "corporate_filing": "filing",
    "filing": "filing",
    "earnings_call": "earnings_call",
    "annual_report": "annual_report",
    "annual_letter": "annual_letter",
    "investor_presentation": "investor_presentation",
    "credit_rating": "credit_rating_change",
    "credit_rating_change": "credit_rating_change",
    "material_news": "material_news",
    "governance_event": "governance_event",
    "capital_allocation_event": "capital_allocation_event",
}


class FactoryGateway(Protocol):
    def load_context(self, selector: dict[str, Any], as_of: datetime) -> dict[str, Any]: ...
    def persist(self, plan: dict[str, Any]) -> dict[str, Any]: ...


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return f"{sql_literal(json.dumps(value, sort_keys=True, default=str))}::jsonb"


def stable_fingerprint(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def parse_as_of(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    fraction = re.search(r"\.(\d+)([+-]\d{2}:\d{2})$", normalized)
    if fraction:
        digits = fraction.group(1)[:6].ljust(6, "0")
        normalized = normalized[:fraction.start()] + "." + digits + fraction.group(2)
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("--as-of must include an explicit timezone")
    return parsed.astimezone(timezone.utc)


def parse_timestamp(value: object) -> datetime | None:
    if not value:
        return None
    return parse_as_of(str(value))


def slug(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")[:96] or "company"


class PsqlGateway:
    @staticmethod
    def _commands() -> list[list[str]]:
        configured_psql = os.environ.get("AI_OS_PSQL_BIN", "").strip()
        local_psql = configured_psql if configured_psql and Path(configured_psql).is_file() else shutil.which("psql")
        commands: list[list[str]] = []
        if local_psql:
            commands.append([
                local_psql, "-h", "127.0.0.1",
                "-p", POSTGRES_PORT, "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1",
                "-U", "ai_os", "-d", "ai_os",
            ])
        docker = shutil.which("docker") or next(
            (path for path in ("/opt/homebrew/bin/docker", "/usr/local/bin/docker") if Path(path).is_file()),
            "docker",
        )
        commands.append([
                docker, "exec", "-i", "ai_os_postgres", "psql", "-q", "-t",
                "-A", "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os",
            ])
        return commands

    def _run_json(self, sql: str) -> Any:
        env = os.environ.copy()
        env.setdefault("PGPASSWORD", POSTGRES_PASSWORD)
        errors: list[str] = []
        for command in self._commands():
            try:
                completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False, env=env)
            except OSError as exc:
                errors.append(f"{command[0]}: {type(exc).__name__}: {exc}")
                continue
            if completed.returncode == 0:
                return json.loads(completed.stdout.strip() or "null")
            errors.append(f"{command[0]}: {(completed.stderr or completed.stdout).strip()}")
        raise RuntimeError(" | ".join(errors))

    def load_context(self, selector: dict[str, Any], as_of: datetime) -> dict[str, Any]:
        if selector.get("company_id") is not None:
            company_filter = f"company.id = {int(selector['company_id'])}"
        elif selector.get("company_key"):
            company_filter = f"company.company_key = {sql_literal(selector['company_key'])}"
        else:
            exchange_filter = (
                f" AND company.primary_exchange = {sql_literal(str(selector['exchange']).upper())}"
                if selector.get("exchange") else ""
            )
            company_filter = f"upper(company.primary_symbol) = {sql_literal(str(selector['symbol']).upper())}{exchange_filter}"
        cutoff = sql_literal(as_of.isoformat())
        sql = f"""
        WITH target AS (
            SELECT company.*
            FROM research.companies company
            WHERE {company_filter}
            ORDER BY company.id
            LIMIT 1
        ), target_thesis AS (
            SELECT thesis.id
            FROM portfolio.holding_theses thesis
            JOIN target
              ON upper(thesis.symbol) = upper(target.primary_symbol)
             AND (
                  thesis.exchange IS NULL
                  OR target.primary_exchange IS NULL
                  OR upper(thesis.exchange) = upper(target.primary_exchange)
             )
            ORDER BY
                CASE WHEN upper(thesis.exchange) = upper(target.primary_exchange) THEN 0 ELSE 1 END,
                thesis.id
            LIMIT 1
        ), eligible_evidence AS (
            SELECT evidence.*
            FROM research.fundamental_evidence evidence
            JOIN target ON target.id = evidence.company_id
            WHERE evidence.retrieved_at <= {cutoff}::timestamptz
              AND coalesce(evidence.published_at, evidence.retrieved_at) <= {cutoff}::timestamptz
              AND evidence.verification_status NOT IN ('rejected', 'superseded')
        ), latest_dossier AS (
            SELECT dossier.id AS dossier_id, dossier.dossier_key,
                   coalesce(dossier.holding_thesis_id, (SELECT id FROM target_thesis)) AS holding_thesis_id,
                   version.id AS version_id, version.version_number, version.source_cutoff_at
            FROM research.investment_dossiers dossier
            JOIN target ON target.id = dossier.company_id
            LEFT JOIN LATERAL (
                SELECT candidate.* FROM research.investment_dossier_versions candidate
                WHERE candidate.dossier_id = dossier.id
                  AND candidate.source_cutoff_at <= {cutoff}::timestamptz
                ORDER BY candidate.version_number DESC LIMIT 1
            ) version ON true
            ORDER BY dossier.updated_at DESC LIMIT 1
        ), latest_opinions AS (
            SELECT opinion.*
            FROM (
                SELECT opinion.*, row_number() OVER (
                    PARTITION BY opinion.specialist_key, opinion.agent_name
                    ORDER BY opinion.opinion_as_of DESC, opinion.id DESC
                ) AS rank
                FROM research.fundamental_specialist_opinions opinion
                JOIN target ON target.id = opinion.company_id
                JOIN eligible_evidence evidence ON evidence.id = opinion.evidence_id
                WHERE opinion.opinion_as_of <= {cutoff}::timestamptz
                  AND opinion.opinion_status NOT IN ('rejected', 'stale')
            ) opinion WHERE opinion.rank = 1
        ), latest_committee AS (
            SELECT review.id AS committee_review_id, review.review_status,
                   review.recommended_decision, review.decision_status,
                   review.memo_status, review.committee_members,
                   review.evidence_summary, review.source_gaps,
                   review.required_followups, review.final_decision,
                   review.decision_notes, review.decided_by, review.decided_at,
                   decision.id AS committee_decision_id,
                   decision.decision AS recorded_decision,
                   decision.decision_status AS recorded_decision_status,
                   decision.evidence AS decision_evidence,
                   decision.created_at AS decision_created_at,
                   review.live_execution_allowed,
                   review.capital_action_allowed
            FROM portfolio.long_term_committee_reviews review
            JOIN target_thesis ON target_thesis.id=review.holding_thesis_id
            LEFT JOIN LATERAL (
                SELECT item.* FROM portfolio.long_term_committee_decisions item
                WHERE item.committee_review_id=review.id
                  AND item.created_at<={cutoff}::timestamptz
                ORDER BY item.created_at DESC,item.id DESC LIMIT 1
            ) decision ON true
            WHERE review.created_at<={cutoff}::timestamptz
            ORDER BY coalesce(decision.created_at,review.decided_at,review.created_at) DESC,review.id DESC
            LIMIT 1
        ), point_in_time_facts AS (
            SELECT fact.*, row_number() OVER (
                PARTITION BY fact.fact_definition_id, fact.fiscal_year, fact.fiscal_period,
                             fact.period_end, fact.statement_scope
                ORDER BY fact.restatement_version DESC, fact.recorded_at DESC
            ) AS rank
            FROM research.company_statement_facts fact
            JOIN target ON target.id = fact.company_id
            JOIN eligible_evidence evidence ON evidence.id = fact.evidence_id
            WHERE fact.available_at <= {cutoff}::timestamptz
              AND fact.recorded_at <= {cutoff}::timestamptz
        )
        SELECT json_build_object(
            'company', (SELECT row_to_json(row) FROM (
                SELECT id, company_key, legal_name, display_name, primary_symbol,
                       primary_exchange, status, real_company_verified_at,
                       real_company_verification_evidence_id
                FROM target
            ) row),
            'target_thesis_id', (SELECT id FROM target_thesis),
            'latest_dossier', (SELECT row_to_json(latest_dossier) FROM latest_dossier),
            'committee', (SELECT row_to_json(latest_committee) FROM latest_committee),
            'evidence', coalesce((SELECT json_agg(row_to_json(row) ORDER BY row.retrieved_at, row.id) FROM (
                SELECT id, source_type, source_name, source_url, source_title, published_at,
                       retrieved_at, source_as_of_date, verification_status, source_locator
                FROM eligible_evidence
            ) row), '[]'::json),
            'opinions', coalesce((SELECT json_agg(row_to_json(row) ORDER BY row.specialist_key, row.id) FROM (
                SELECT id, holding_thesis_id, specialist_key, agent_name, opinion_status,
                       conclusion, score_low, score_base, score_high, confidence_pct,
                       disconfirming_evidence, required_followups, evidence_id, opinion_as_of
                FROM latest_opinions
            ) row), '[]'::json),
            'coverage', json_build_object(
                'annual_statement_years', (SELECT count(DISTINCT fiscal_year) FROM point_in_time_facts WHERE rank = 1 AND fiscal_period = 'FY'),
                'segment_count', (SELECT count(*) FROM research.company_segments segment JOIN target ON target.id = segment.company_id JOIN eligible_evidence evidence ON evidence.id = segment.evidence_id WHERE segment.valid_from <= {cutoff}::date AND (segment.valid_to IS NULL OR segment.valid_to >= {cutoff}::date)),
                'segment_fact_years', (SELECT count(DISTINCT fact.fiscal_year) FROM research.company_segment_facts fact JOIN target ON target.id = fact.company_id JOIN eligible_evidence evidence ON evidence.id = fact.evidence_id WHERE fact.available_at <= {cutoff}::timestamptz),
                'operational_kpi_count', (SELECT count(DISTINCT observation.kpi_definition_id) FROM research.operational_kpi_observations observation JOIN target ON target.id = observation.company_id JOIN eligible_evidence evidence ON evidence.id = observation.evidence_id WHERE observation.available_at <= {cutoff}::timestamptz),
                'market_share_series_count', (SELECT count(DISTINCT observation.market_key) FROM research.market_share_observations observation JOIN target ON target.id = observation.company_id JOIN eligible_evidence evidence ON evidence.id = observation.evidence_id WHERE observation.available_at <= {cutoff}::timestamptz),
                'peer_count', (SELECT count(DISTINCT membership.peer_company_id) FROM research.peer_sets peer_set JOIN target ON target.id = peer_set.subject_company_id JOIN eligible_evidence set_evidence ON set_evidence.id = peer_set.evidence_id JOIN research.peer_set_memberships membership ON membership.peer_set_id = peer_set.id JOIN eligible_evidence member_evidence ON member_evidence.id = membership.evidence_id WHERE peer_set.valid_from <= {cutoff}::date AND (peer_set.valid_to IS NULL OR peer_set.valid_to >= {cutoff}::date) AND membership.valid_from <= {cutoff}::date AND (membership.valid_to IS NULL OR membership.valid_to >= {cutoff}::date)),
                'management_communication_count', (SELECT count(*) FROM research.management_communications communication JOIN target ON target.id = communication.company_id JOIN eligible_evidence evidence ON evidence.id = communication.evidence_id WHERE communication.communication_date <= {cutoff}::date AND communication.transcript_status NOT IN ('rejected', 'superseded')),
                'management_claim_count', (SELECT count(*) FROM research.management_claims claim JOIN target ON target.id = claim.company_id JOIN eligible_evidence evidence ON evidence.id = claim.evidence_id WHERE claim.claim_date <= {cutoff}::date),
                'claims_with_outcomes', (SELECT count(DISTINCT outcome.claim_id) FROM research.management_claim_outcomes outcome JOIN research.management_claims claim ON claim.id = outcome.claim_id JOIN target ON target.id = claim.company_id JOIN eligible_evidence evidence ON evidence.id = outcome.evidence_id WHERE outcome.outcome_date <= {cutoff}::date),
                'completed_valuation_types', coalesce((SELECT json_agg(DISTINCT lower(replace(replace(model.model_type,'-','_'),' ','_')) ORDER BY lower(replace(replace(model.model_type,'-','_'),' ','_')))
                    FROM portfolio.holding_valuation_models model JOIN target_thesis ON target_thesis.id=model.holding_thesis_id
                    WHERE model.status IN ('complete','reviewed') AND model.updated_at<={cutoff}::timestamptz), '[]'::json),
                'completed_monte_carlo_count', (SELECT count(*) FROM portfolio.long_term_monte_carlo_runs run JOIN target_thesis ON target_thesis.id=run.holding_thesis_id
                    WHERE run.run_status='complete' AND run.created_at<={cutoff}::timestamptz)
            )
        )::text;
        """
        result = self._run_json(sql)
        return result or {}

    def persist(self, plan: dict[str, Any]) -> dict[str, Any]:
        sections = plan["sections"]
        section_values = ",\n".join(
            "(" + ",".join(
                (
                    sql_literal(section["section_key"]),
                    str(section["section_order"]),
                    sql_literal(section["section_title"]),
                    sql_literal(section["section_status"]),
                    sql_literal(section["content_markdown"]),
                    str(section["primary_evidence_id"]),
                    sql_literal(section["evidence_as_of"]) + "::timestamptz",
                    sql_literal(plan["actor"]),
                )
            ) + ")"
            for section in sections
        )
        evidence_values = ",\n".join(
            f"({sql_literal(section['section_key'])},{evidence_id},'supporting',{sql_literal('Factory-selected point-in-time evidence')})"
            for section in sections for evidence_id in section["evidence_ids"]
        )
        opinion_ids = ",".join(str(int(value)) for value in plan["opinion_ids"]) or "NULL"
        trigger_values = ",\n".join(
            "(" + ",".join(
                (
                    sql_literal(trigger["trigger_type"]),
                    "'research.fundamental_evidence'", sql_literal(str(trigger["evidence_id"])),
                    sql_literal(trigger["materiality"]), sql_literal(trigger["event_at"]) + "::timestamptz",
                    str(trigger["evidence_id"]), sql_jsonb(trigger["metadata"]),
                )
            ) + ")"
            for trigger in plan["refresh_triggers"]
        )
        gate_values = ",\n".join(
            "(" + ",".join(
                (
                    sql_literal(gate["gate_key"]),
                    sql_literal(gate["gate_name"]), sql_literal(gate["gate_status"]),
                    sql_jsonb(gate["observed_value"]), sql_jsonb(gate["required_value"]),
                    sql_literal(gate.get("failure_reason")), str(plan["verification_evidence_id"]),
                    sql_literal(plan["actor"]),
                )
            ) + ")"
            for gate in plan["acceptance_gates"]
        )
        refresh_sql = ""
        if trigger_values:
            refresh_sql = f"""
            INSERT INTO research.investment_dossier_refresh_triggers (
                dossier_id, trigger_type, trigger_source_table, trigger_source_id,
                materiality, event_at, evidence_id, metadata
            ) SELECT context.dossier_id, incoming.*
              FROM (VALUES {trigger_values}) AS incoming(
                trigger_type, trigger_source_table, trigger_source_id,
                materiality, event_at, evidence_id, metadata
              ) JOIN institutional_factory_context context ON true
            ON CONFLICT (dossier_id, trigger_source_table, trigger_source_id, trigger_type)
              DO UPDATE SET materiality = EXCLUDED.materiality, event_at = EXCLUDED.event_at,
                            evidence_id = EXCLUDED.evidence_id, metadata = EXCLUDED.metadata;
            """
        sql = f"""
        BEGIN;
        CREATE TEMP TABLE institutional_factory_context ON COMMIT DROP AS
        WITH dossier AS (
            INSERT INTO research.investment_dossiers (
                company_id, holding_thesis_id, dossier_key, dossier_status, owner_agent
            ) VALUES (
                {int(plan['company_id'])}, {str(plan['holding_thesis_id']) if plan.get('holding_thesis_id') is not None else 'NULL'},
                {sql_literal(plan['dossier_key'])}, 'in_review', {sql_literal(plan['actor'])}
            ) ON CONFLICT (dossier_key) DO UPDATE SET
                holding_thesis_id = coalesce(EXCLUDED.holding_thesis_id, research.investment_dossiers.holding_thesis_id),
                dossier_status = 'in_review', owner_agent = EXCLUDED.owner_agent, updated_at = now()
            RETURNING id, holding_thesis_id
        ), matching_version AS (
            SELECT existing.id, existing.dossier_id, existing.version_number
            FROM dossier
            JOIN research.investment_dossier_versions existing
              ON existing.dossier_id = dossier.id
             AND existing.source_cutoff_at = {sql_literal(plan['as_of'])}::timestamptz
             AND existing.decision_summary ->> 'input_fingerprint' = {sql_literal(plan['input_fingerprint'])}
            ORDER BY existing.id DESC
            LIMIT 1
        ), next_version AS (
            SELECT dossier.id AS dossier_id, dossier.holding_thesis_id,
                   coalesce(max(existing.version_number), 0) + 1 AS version_number,
                   max(existing.id) FILTER (WHERE existing.version_number = current.current_version) AS supersedes_version_id
            FROM dossier
            LEFT JOIN research.investment_dossier_versions existing ON existing.dossier_id = dossier.id
            LEFT JOIN LATERAL (
                SELECT max(version_number) AS current_version
                FROM research.investment_dossier_versions item WHERE item.dossier_id = dossier.id
            ) current ON true
            GROUP BY dossier.id, dossier.holding_thesis_id
        ), inserted_version AS (
            INSERT INTO research.investment_dossier_versions (
                dossier_id, version_number, version_status, research_as_of, source_cutoff_at,
                executive_conclusion, decision_summary, evidence_coverage, generated_by,
                supersedes_version_id
            ) SELECT dossier_id, version_number, 'specialist_review',
                     {sql_literal(plan['as_of'])}::timestamptz, {sql_literal(plan['as_of'])}::timestamptz,
                     {sql_literal(plan['executive_conclusion'])}, {sql_jsonb(plan['decision_summary'])},
                     {sql_jsonb(plan['evidence_coverage'])}, {sql_literal(plan['actor'])}, supersedes_version_id
              FROM next_version
             WHERE NOT EXISTS (SELECT 1 FROM matching_version)
             RETURNING id, dossier_id, version_number
        ), version AS (
            SELECT id, dossier_id, version_number, true AS version_reused
            FROM matching_version
            UNION ALL
            SELECT id, dossier_id, version_number, false AS version_reused
            FROM inserted_version
        ), updated AS (
            UPDATE research.investment_dossiers dossier
            SET current_version_number = version.version_number, updated_at = now()
            FROM version WHERE dossier.id = version.dossier_id RETURNING dossier.id
        )
        SELECT version.dossier_id, version.id AS dossier_version_id, version.version_number,
               version.version_reused,
               next_version.holding_thesis_id, NULL::bigint AS acceptance_run_id
        FROM version JOIN next_version ON next_version.dossier_id = version.dossier_id;

        INSERT INTO research.investment_dossier_sections (
            dossier_version_id, section_key, section_order, section_title, section_status,
            content_markdown, primary_evidence_id, evidence_as_of, generated_by
        ) SELECT context.dossier_version_id, incoming.*
          FROM (VALUES {section_values}) AS incoming(
            section_key, section_order, section_title, section_status,
            content_markdown, primary_evidence_id, evidence_as_of, generated_by
          ) JOIN institutional_factory_context context ON true
        ON CONFLICT (dossier_version_id, section_key) DO NOTHING;

        INSERT INTO research.investment_dossier_section_evidence (
            dossier_section_id, evidence_id, evidence_role, citation_note
        ) SELECT section.id, incoming.evidence_id, incoming.evidence_role, incoming.citation_note
          FROM (VALUES {evidence_values}) AS incoming(section_key, evidence_id, evidence_role, citation_note)
          JOIN institutional_factory_context context ON true
          JOIN research.investment_dossier_sections section
            ON section.dossier_version_id = context.dossier_version_id
           AND section.section_key = incoming.section_key
        ON CONFLICT DO NOTHING;

        INSERT INTO research.fundamental_specialist_opinions (
            company_id, dossier_version_id, holding_thesis_id, specialist_key, agent_name,
            opinion_status, conclusion, score_low, score_base, score_high, confidence_pct,
            disconfirming_evidence, required_followups, evidence_id, opinion_as_of
        ) SELECT opinion.company_id, context.dossier_version_id,
                 coalesce(context.holding_thesis_id, opinion.holding_thesis_id), opinion.specialist_key,
                 opinion.agent_name, opinion.opinion_status, opinion.conclusion, opinion.score_low,
                 opinion.score_base, opinion.score_high, opinion.confidence_pct,
                 opinion.disconfirming_evidence, opinion.required_followups, opinion.evidence_id,
                 opinion.opinion_as_of
          FROM research.fundamental_specialist_opinions opinion
          JOIN institutional_factory_context context ON true
         WHERE opinion.id IN ({opinion_ids})
        ON CONFLICT (dossier_version_id, specialist_key, agent_name) DO NOTHING;

        {refresh_sql}

        UPDATE institutional_factory_context context
        SET acceptance_run_id = CASE
            WHEN {str(bool(plan['acceptance_eligible'])).lower()}
            THEN research.open_real_company_acceptance_run(
                {sql_literal(plan['run_key'])}, {int(plan['company_id'])},
                {str(plan['holding_thesis_id']) if plan.get('holding_thesis_id') is not None else 'NULL'},
                context.dossier_version_id, {sql_literal(plan['as_of'])}::timestamptz, {sql_literal(plan['actor'])}
            )
            ELSE NULL
        END;

        DELETE FROM research.fundamental_acceptance_gates gate
        USING institutional_factory_context context
        WHERE context.acceptance_run_id IS NOT NULL
          AND gate.acceptance_run_id = context.acceptance_run_id;

        INSERT INTO research.fundamental_acceptance_gates (
            acceptance_run_id, gate_key, gate_name, gate_status, observed_value,
            required_value, failure_reason, evidence_id, evaluated_by
        ) SELECT context.acceptance_run_id, incoming.*
          FROM (VALUES {gate_values}) AS incoming(
            gate_key, gate_name, gate_status, observed_value,
            required_value, failure_reason, evidence_id, evaluated_by
          ) JOIN institutional_factory_context context ON context.acceptance_run_id IS NOT NULL;

        UPDATE research.fundamental_acceptance_runs run
        SET run_status = {sql_literal(plan['acceptance_status'])}, completed_at = now(),
            notes = {sql_literal(plan['acceptance_note'])}
        FROM institutional_factory_context context
        WHERE context.acceptance_run_id IS NOT NULL
          AND run.id = context.acceptance_run_id;

        SELECT json_build_object(
            'dossier_id', context.dossier_id, 'dossier_version_id', context.dossier_version_id,
            'version_number', context.version_number, 'acceptance_run_id', context.acceptance_run_id,
            'input_fingerprint', {sql_literal(plan['input_fingerprint'])},
            'version_reused', context.version_reused,
            'acceptance_run_opened', context.acceptance_run_id IS NOT NULL,
            'acceptance_status', {sql_literal(plan['acceptance_status'])},
            'sections_written', {len(sections)}, 'specialist_opinions_cloned',
            (SELECT count(*) FROM research.fundamental_specialist_opinions opinion
              WHERE opinion.dossier_version_id = context.dossier_version_id),
            'refresh_triggers_enqueued', {len(plan['refresh_triggers'])},
            'capital_action_allowed', false, 'broker_execution_allowed', false
        )::text FROM institutional_factory_context context;
        COMMIT;
        """
        return self._run_json(sql) or {}


def _evidence_for_section(
    evidence: list[dict[str, Any]],
    opinions: list[dict[str, Any]],
    specialist_keys: tuple[str, ...],
    source_types: tuple[str, ...],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    matching_opinions = [row for row in opinions if not specialist_keys or row.get("specialist_key") in specialist_keys]
    opinion_evidence = {int(row["evidence_id"]) for row in matching_opinions if row.get("evidence_id") is not None}
    normalized_sources = {value.lower() for value in source_types}
    topical = [
        row for row in evidence
        if int(row["id"]) in opinion_evidence or str(row.get("source_type") or "").lower() in normalized_sources
    ]
    selected = topical or evidence[:8]
    deduplicated = list({int(row["id"]): row for row in selected}.values())[:12]
    return deduplicated, matching_opinions, bool(topical)


def _section_markdown(
    title: str,
    section_key: str,
    as_of: str,
    evidence: list[dict[str, Any]],
    opinions: list[dict[str, Any]],
    topical: bool,
    committee: dict[str, Any] | None = None,
) -> str:
    lines = [f"# {title}", "", f"- Research cutoff: `{as_of}`", "- Source mode: stored point-in-time evidence only", ""]
    lines.append("## Stored Specialist Opinions")
    lines.append("")
    if opinions:
        for opinion in opinions:
            lines.extend([
                f"### {opinion.get('specialist_key')} - {opinion.get('agent_name')}",
                f"- Status: `{opinion.get('opinion_status')}`",
                f"- Opinion as of: `{opinion.get('opinion_as_of')}`",
                f"- Confidence: `{opinion.get('confidence_pct')}`",
                "",
                str(opinion.get("conclusion") or "No stored conclusion."),
                "",
                f"Disconfirming evidence: {opinion.get('disconfirming_evidence') or 'None stored.'}",
                "",
            ])
    else:
        lines.extend(["No eligible stored specialist opinion exists for this section.", ""])
    lines.extend(["## Evidence Inventory", ""])
    for item in evidence:
        lines.append(
            f"- Evidence `{item.get('id')}`: {item.get('source_title')} "
            f"({item.get('source_type')}; retrieved `{item.get('retrieved_at')}`; verification `{item.get('verification_status')}`)"
        )
    if not topical:
        lines.extend(["", "## Evidence Gap", "", f"No section-specific evidence mapping was available for `{section_key}` at the cutoff."])
    if section_key == "specialist_opinions_committee_decision":
        lines.extend(["", "## Durable Committee Record", ""])
        if committee and committee.get("committee_decision_id"):
            lines.extend([
                f"- Review: `{committee.get('committee_review_id')}`",
                f"- Decision record: `{committee.get('committee_decision_id')}`",
                f"- Final decision: `{committee.get('recorded_decision') or committee.get('final_decision')}`",
                f"- Decided by: `{committee.get('decided_by')}`",
                f"- Decided at: `{committee.get('decision_created_at') or committee.get('decided_at')}`",
                f"- Capital action allowed: `{bool(committee.get('capital_action_allowed'))}`",
                f"- Live execution allowed: `{bool(committee.get('live_execution_allowed'))}`",
                "",
                str(committee.get("decision_notes") or "No additional committee note stored."),
            ])
        else:
            lines.append("No final human committee decision exists at the research cutoff.")
    return "\n".join(lines).strip() + "\n"


def _gate(key: str, name: str, passed: bool, observed: Any, required: Any, reason: str) -> dict[str, Any]:
    return {
        "gate_key": key,
        "gate_name": name,
        "gate_status": "passed" if passed else "failed",
        "observed_value": observed if isinstance(observed, dict) else {"value": observed},
        "required_value": required if isinstance(required, dict) else {"value": required},
        "failure_reason": None if passed else reason,
    }


def evaluate_acceptance(
    company: dict[str, Any],
    evidence: list[dict[str, Any]],
    opinions: list[dict[str, Any]],
    sections: list[dict[str, Any]],
    coverage: dict[str, Any],
    latest_dossier: dict[str, Any],
    committee: dict[str, Any],
    as_of: datetime,
) -> list[dict[str, Any]]:
    qualified_opinions = [
        row for row in opinions
        if str(row.get("opinion_status") or "").lower() in ACCEPTED_OPINION_STATUSES
    ]
    specialists = {str(row.get("specialist_key")) for row in qualified_opinions}
    specialist_rows = {str(row.get("specialist_key")): row for row in qualified_opinions}
    human_verified = sum(1 for row in evidence if row.get("verification_status") == "human_verified")
    valuation_types = {str(value).lower().replace("-", "_").replace(" ", "_") for value in coverage.get("completed_valuation_types") or []}
    valuation_families = {
        "dcf": bool(valuation_types & {"dcf", "discounted_cash_flow"}),
        "reverse_dcf": bool(valuation_types & {"reverse_dcf", "reverse_discounted_cash_flow"}),
        "multiples": bool(valuation_types & {"multiples", "relative_valuation", "peer_comparison", "comparable_companies"}),
        "monte_carlo": int(coverage.get("completed_monte_carlo_count") or 0) > 0,
    }
    challenge_keys = ("bear_case", "risk", "forensic_accounting")
    challenge_rows = [specialist_rows.get(key) for key in challenge_keys]
    independent_challenge = all(
        row and str(row.get("disconfirming_evidence") or "").strip()
        for row in challenge_rows
    ) and len({str(row.get("agent_name")) for row in challenge_rows if row}) == len(challenge_keys)
    committee_complete = bool(
        committee.get("committee_decision_id")
        and committee.get("recorded_decision_status") == "final"
        and committee.get("recorded_decision")
        and committee.get("capital_action_allowed") is False
        and committee.get("live_execution_allowed") is False
    )
    point_in_time = all(
        (parse_timestamp(row.get("retrieved_at")) or as_of) <= as_of
        and (parse_timestamp(row.get("published_at")) or parse_timestamp(row.get("retrieved_at")) or as_of) <= as_of
        for row in evidence
    ) and all((parse_timestamp(row.get("opinion_as_of")) or as_of) <= as_of for row in opinions)
    gates = [
        _gate("real_company_verified", "Company identity is matched to retained primary evidence", bool(company.get("real_company_verified_at") and company.get("real_company_verification_evidence_id")), {"identity_matched_at": company.get("real_company_verified_at"), "evidence_id": company.get("real_company_verification_evidence_id")}, {"primary_source_identity_match": True}, "Company identity lacks retained primary-source evidence."),
        _gate("point_in_time_inputs", "All inputs respect the research cutoff", point_in_time, {"as_of": as_of.isoformat()}, {"future_inputs": 0}, "At least one evidence item or opinion is newer than the cutoff."),
        _gate("fifteen_sections", "All fifteen dossier sections assembled", len(sections) == 15, len(sections), 15, "The dossier does not contain all required sections."),
        _gate("section_evidence", "Every section has stored evidence", all(row.get("evidence_ids") for row in sections), sum(1 for row in sections if row.get("evidence_ids")), 15, "At least one section has no eligible stored evidence."),
        _gate("section_readiness", "All dossier sections are evidence complete", all(row.get("section_status") == "evidence_complete" for row in sections), sum(1 for row in sections if row.get("section_status") == "evidence_complete"), 15, "At least one dossier section remains a draft or lacks section-specific evidence."),
        _gate("statement_history", "Ten-year annual statement history", int(coverage.get("annual_statement_years") or 0) >= 10, int(coverage.get("annual_statement_years") or 0), 10, "Fewer than ten annual statement years are available at the cutoff."),
        _gate("segment_history", "Segment history is populated", int(coverage.get("segment_count") or 0) > 0 and int(coverage.get("segment_fact_years") or 0) >= 3, {"segments": int(coverage.get("segment_count") or 0), "years": int(coverage.get("segment_fact_years") or 0)}, {"segments_min": 1, "years_min": 3}, "Segment definitions or history are incomplete."),
        _gate("operational_kpis", "Operational KPI history is populated", int(coverage.get("operational_kpi_count") or 0) > 0, int(coverage.get("operational_kpi_count") or 0), 1, "No operational KPI series is available."),
        _gate("market_share", "Market-share history is populated", int(coverage.get("market_share_series_count") or 0) > 0, int(coverage.get("market_share_series_count") or 0), 1, "No market-share series is available."),
        _gate("peer_set", "Point-in-time peer set is populated", int(coverage.get("peer_count") or 0) >= 2, int(coverage.get("peer_count") or 0), 2, "Fewer than two eligible peers are available."),
        _gate("management_intelligence", "Management communications and claims are tracked", int(coverage.get("management_communication_count") or 0) > 0 and int(coverage.get("management_claim_count") or 0) > 0, {"communications": int(coverage.get("management_communication_count") or 0), "claims": int(coverage.get("management_claim_count") or 0), "claims_with_outcomes": int(coverage.get("claims_with_outcomes") or 0)}, {"communications_min": 1, "claims_min": 1}, "Management communication or claim history is absent."),
        _gate("management_accountability", "Management claims have observed outcomes", int(coverage.get("claims_with_outcomes") or 0) > 0, int(coverage.get("claims_with_outcomes") or 0), 1, "No management claim has a point-in-time observed outcome."),
        _gate("specialist_coverage", "All required specialists submitted evidence-backed opinions", REQUIRED_SPECIALISTS <= specialists, {"present": sorted(specialists), "missing": sorted(REQUIRED_SPECIALISTS - specialists)}, {"required": sorted(REQUIRED_SPECIALISTS)}, "One or more required specialist opinions are missing."),
        _gate("independent_challenge", "Bear, risk, and forensic specialists preserve disconfirming evidence", independent_challenge, {"specialists": list(challenge_keys), "independent_agents": len({str(row.get('agent_name')) for row in challenge_rows if row})}, {"documented_challenges": 3, "independent_agents": 3}, "Independent bear, risk, or forensic challenge is incomplete."),
        _gate("portfolio_fit", "Portfolio-fit opinion is present", "portfolio_fit" in specialists, {"present": "portfolio_fit" in specialists}, {"present": True}, "The mandatory portfolio-fit opinion is missing."),
        _gate("holding_thesis", "Dossier is linked to a durable holding thesis", latest_dossier.get("holding_thesis_id") is not None, {"holding_thesis_id": latest_dossier.get("holding_thesis_id")}, {"linked": True}, "No durable holding thesis is linked to the company dossier."),
        _gate("valuation_suite", "DCF, reverse DCF, multiples, and Monte Carlo are complete", all(valuation_families.values()), valuation_families, {key: True for key in valuation_families}, "One or more required valuation families are incomplete."),
        _gate("committee_decision", "Final human committee decision is durably recorded", committee_complete, {"committee_review_id": committee.get("committee_review_id"), "committee_decision_id": committee.get("committee_decision_id"), "decision": committee.get("recorded_decision"), "decision_status": committee.get("recorded_decision_status")}, {"final_human_decision": True, "capital_action_allowed": False, "live_execution_allowed": False}, "No final research-only human committee decision exists at the cutoff."),
        _gate("evidence_quality", "Human-verified evidence is present", human_verified > 0, human_verified, 1, "No human-verified evidence is available at the cutoff."),
        _gate("execution_lock", "Research cannot take capital or broker action", True, {"capital_action_allowed": False, "broker_execution_allowed": False}, {"capital_action_allowed": False, "broker_execution_allowed": False}, "Execution lock was not enforced."),
    ]
    return gates


def build_refresh_triggers(evidence: list[dict[str, Any]], latest_cutoff: datetime | None) -> list[dict[str, Any]]:
    if latest_cutoff is None:
        return []
    triggers: list[dict[str, Any]] = []
    for row in evidence:
        event_at = parse_timestamp(row.get("published_at")) or parse_timestamp(row.get("retrieved_at"))
        trigger_type = TRIGGER_TYPE_BY_SOURCE.get(str(row.get("source_type") or "").lower())
        if not trigger_type or not event_at or event_at <= latest_cutoff:
            continue
        triggers.append({
            "trigger_type": trigger_type,
            "evidence_id": int(row["id"]),
            "event_at": event_at.isoformat(),
            "materiality": "review",
            "metadata": {"source_title": row.get("source_title"), "source_type": row.get("source_type"), "point_in_time": True},
        })
    return triggers


@dataclass(frozen=True)
class FactoryRequest:
    selector: dict[str, Any]
    as_of: datetime
    actor: str
    run_key: str
    dry_run: bool


def build_plan(context: dict[str, Any], request: FactoryRequest) -> dict[str, Any]:
    company = context.get("company") or {}
    if not company:
        raise ValueError("No company matched the requested selector.")
    evidence = list(context.get("evidence") or [])
    opinions = list(context.get("opinions") or [])
    coverage = dict(context.get("coverage") or {})
    latest_dossier = context.get("latest_dossier") or {}
    committee = context.get("committee") or {}
    if not evidence:
        raise ValueError("No eligible stored evidence exists at the requested point in time.")
    sections: list[dict[str, Any]] = []
    for order, (key, title, specialist_keys, source_types) in enumerate(SECTION_SPECS, start=1):
        selected, section_opinions, topical = _evidence_for_section(evidence, opinions, specialist_keys, source_types)
        section_complete = bool(
            topical
            and section_opinions
            and all(
                str(row.get("opinion_status") or "").lower() in ACCEPTED_OPINION_STATUSES
                for row in section_opinions
            )
        )
        if key == "specialist_opinions_committee_decision":
            section_complete = section_complete and bool(committee.get("committee_decision_id"))
        sections.append({
            "section_key": key,
            "section_order": order,
            "section_title": title,
            "section_status": "evidence_complete" if section_complete else "draft",
            "content_markdown": _section_markdown(title, key, request.as_of.isoformat(), selected, section_opinions, topical, committee),
            "primary_evidence_id": int(selected[0]["id"]),
            "evidence_ids": [int(row["id"]) for row in selected],
            "evidence_as_of": request.as_of.isoformat(),
        })
    gates = evaluate_acceptance(company, evidence, opinions, sections, coverage, latest_dossier, committee, request.as_of)
    failed = [gate["gate_key"] for gate in gates if gate["gate_status"] != "passed"]
    specialists = sorted({str(row.get("specialist_key")) for row in opinions})
    human_verified = any(row.get("verification_status") == "human_verified" for row in evidence)
    thesis_id = latest_dossier.get("holding_thesis_id") or context.get("target_thesis_id")
    company_key = company.get("company_key") or company.get("primary_symbol") or company["id"]
    latest_cutoff = parse_timestamp(latest_dossier.get("source_cutoff_at"))
    plan = {
        "status": "planned" if request.dry_run else "ready_to_persist",
        "dry_run": request.dry_run,
        "run_key": request.run_key,
        "actor": request.actor,
        "as_of": request.as_of.isoformat(),
        "company_id": int(company["id"]),
        "company": company,
        "holding_thesis_id": int(thesis_id) if thesis_id is not None else None,
        "dossier_key": latest_dossier.get("dossier_key") or f"institutional-fundamental-{slug(company_key)}-{thesis_id or 'company'}",
        "sections": sections,
        "opinion_ids": [int(row["id"]) for row in opinions],
        "verification_evidence_id": int(company.get("real_company_verification_evidence_id") or evidence[0]["id"]),
        "acceptance_eligible": human_verified > 0,
        "executive_conclusion": "No capital action is authorized. Review the source-backed dossier sections, failed gates, specialist dissent, and committee record.",
        "decision_summary": {"acceptance_status": "passed" if not failed else "failed", "failed_gates": failed, "capital_action_allowed": False, "broker_execution_allowed": False},
        "evidence_coverage": {**coverage, "evidence_count": len(evidence), "specialists_present": specialists, "section_count": len(sections), "point_in_time_cutoff": request.as_of.isoformat()},
        "refresh_triggers": build_refresh_triggers(evidence, latest_cutoff),
        "acceptance_gates": gates,
        "acceptance_status": "passed" if not failed else "failed",
        "acceptance_note": "Acceptance passed." if not failed else "Acceptance failed: " + ", ".join(failed),
        "execution_envelope": {"capital_action_allowed": False, "broker_execution_allowed": False, "research_only": True},
    }
    plan["input_fingerprint"] = stable_fingerprint({
        "company_id": plan["company_id"],
        "holding_thesis_id": plan["holding_thesis_id"],
        "as_of": plan["as_of"],
        "sections": plan["sections"],
        "decision_summary": plan["decision_summary"],
        "evidence_coverage": plan["evidence_coverage"],
        "refresh_triggers": plan["refresh_triggers"],
        "acceptance_gates": plan["acceptance_gates"],
    })
    plan["decision_summary"]["input_fingerprint"] = plan["input_fingerprint"]
    return plan


def run_factory(request: FactoryRequest, gateway: FactoryGateway) -> dict[str, Any]:
    context = gateway.load_context(request.selector, request.as_of)
    plan = build_plan(context, request)
    company = plan["company"]
    real_company_verified = bool(company.get("real_company_verified_at") and company.get("real_company_verification_evidence_id"))
    if not real_company_verified:
        return {
            "status": "blocked",
            "dry_run": request.dry_run,
            "reason": "Company identity is not matched to retained primary-source evidence.",
            "company": company,
            "acceptance_gates": plan["acceptance_gates"],
            "execution_envelope": plan["execution_envelope"],
        }
    if request.dry_run:
        return plan
    database = gateway.persist(plan)
    return {
        "status": "completed",
        "dry_run": False,
        "run_key": request.run_key,
        "company": company,
        "as_of": plan["as_of"],
        "acceptance_status": plan["acceptance_status"],
        "failed_gates": plan["decision_summary"]["failed_gates"],
        "section_count": len(plan["sections"]),
        "refresh_trigger_count": len(plan["refresh_triggers"]),
        "execution_envelope": plan["execution_envelope"],
        "database": database,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Assemble and accept a point-in-time institutional company dossier from migration 185 data.")
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--company-id", type=int)
    selector.add_argument("--company-key")
    selector.add_argument("--symbol")
    parser.add_argument("--exchange", help="Optional exchange qualifier when --symbol is used.")
    parser.add_argument("--as-of", required=True, help="ISO-8601 cutoff with timezone, for example 2026-08-04T12:00:00+05:30.")
    parser.add_argument("--actor", default=ACTOR_DEFAULT)
    parser.add_argument("--run-key")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None, gateway: FactoryGateway | None = None) -> int:
    args = build_parser().parse_args(argv)
    as_of = parse_as_of(args.as_of)
    if args.exchange and not args.symbol:
        raise ValueError("--exchange is valid only with --symbol")
    selector = {"company_id": args.company_id, "company_key": args.company_key, "symbol": args.symbol, "exchange": args.exchange}
    run_key = args.run_key or f"fundamental_factory_{slug(args.company_id or args.company_key or args.symbol)}_{as_of.strftime('%Y%m%dT%H%M%SZ')}"
    result = run_factory(FactoryRequest(selector, as_of, args.actor, run_key, args.dry_run), gateway or PsqlGateway())
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result["status"] in {"planned", "completed"} else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "error", "error": type(exc).__name__, "message": str(exc)}, sort_keys=True), file=sys.stderr)
        raise SystemExit(1)
