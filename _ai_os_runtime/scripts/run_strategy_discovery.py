#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from run_strategy_backtest import run_psql_json, sql_jsonb, sql_literal
from run_trade_journal_strategy_mining import sql_numeric, sql_text_array
from runtime_storage import artifact_reference, artifact_root


RUNTIME_ROOT = Path(os.environ.get("AI_OS_RUNTIME_ROOT") or Path(__file__).absolute().parents[1])
VAULT_ROOT = Path(os.environ.get("AI_OS_VAULT_ROOT") or RUNTIME_ROOT.parent)
ARTIFACT_ROOT = artifact_root("strategy_discovery")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug[:72] or "strategy"


def normalize_symbols(value: Any) -> list[str]:
    if not value:
        return []
    items = value if isinstance(value, list) else re.split(r"[,;]+", str(value))
    output: list[str] = []
    seen: set[str] = set()
    for item in items:
        symbol = str(item).strip().upper()
        if not symbol:
            continue
        symbol = symbol.split(":", 1)[-1] if symbol.startswith("NSE:") else symbol
        if symbol not in seen:
            seen.add(symbol)
            output.append(symbol)
    return output


IDENTITY_TITLE_PREFIX = re.compile(
    r"^(research-sourced strategy:|journal pattern strategy:|signal-sourced strategy:|component pattern:)\s*",
    re.IGNORECASE,
)


def normalize_identity_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def identity_parts(candidate: dict[str, Any], *, include_content: bool) -> list[str]:
    title = IDENTITY_TITLE_PREFIX.sub("", str(candidate.get("title") or "").strip())
    parts = [
        normalize_identity_text(title),
        ",".join(sorted(normalize_symbols(candidate.get("symbols")))),
        normalize_identity_text(candidate.get("universe")),
        normalize_identity_text(candidate.get("timeframe")),
        normalize_identity_text(candidate.get("template")),
    ]
    if include_content:
        parts.extend(
            [
                normalize_identity_text(candidate.get("thesis")),
                normalize_identity_text(candidate.get("catalyst")),
            ]
        )
    return parts


def opportunity_fingerprint(candidate: dict[str, Any]) -> str:
    return "opp_v2:" + hashlib.md5("|".join(identity_parts(candidate, include_content=False)).encode("utf-8")).hexdigest()  # noqa: S324


def source_fingerprint(candidate: dict[str, Any]) -> str:
    return "src_v2:" + hashlib.md5("|".join(identity_parts(candidate, include_content=True)).encode("utf-8")).hexdigest()  # noqa: S324


def infer_template(text: str) -> str:
    lowered = text.lower()
    if "mean" in lowered or "reversion" in lowered or "zscore" in lowered or "oversold" in lowered:
        return "mean_reversion"
    if "breakout" in lowered or "atr" in lowered or "range expansion" in lowered:
        return "breakout"
    if "low vol" in lowered or "low_vol" in lowered or "volatility" in lowered and "low" in lowered:
        return "low_volatility"
    return "momentum"


def normalize_timeframe(value: str | None) -> str:
    lowered = (value or "").lower()
    if "15" in lowered:
        return "15m"
    if "hour" in lowered or "1h" in lowered:
        return "1h"
    if "week" in lowered:
        return "weekly"
    if "daily" in lowered or "day" in lowered or "swing" in lowered:
        return "daily"
    return "5m"


def fetch_json(sql: str) -> list[dict[str, Any]]:
    return run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            {sql}
        ) rows
        """
    )


def research_candidates(limit: int) -> list[dict[str, Any]]:
    rows = fetch_json(
        f"""
        SELECT id, idea_type, title, symbols, source_kind, source_ref, thesis,
               catalyst, expected_timeframe, opportunity_score, risk_score,
               status, evidence, created_at
        FROM research.ideas
        WHERE status IN ('open','captured','new','active')
        ORDER BY coalesce(opportunity_score, 0) DESC, created_at DESC
        LIMIT {max(1, limit)}
        """
    )
    candidates = []
    for row in rows:
        title = str(row.get("title") or "Research idea")
        thesis = str(row.get("thesis") or title)
        candidates.append(
            {
                "source_kind": "research.ideas",
                "source_ref": str(row.get("id")),
                "title": f"Research-sourced strategy: {title}",
                "symbols": normalize_symbols(row.get("symbols")),
                "universe": "NSE",
                "timeframe": normalize_timeframe(row.get("expected_timeframe")),
                "template": infer_template(" ".join([title, thesis, str(row.get("catalyst") or "")])),
                "thesis": thesis,
                "catalyst": row.get("catalyst"),
                "priority_score": float(row.get("opportunity_score") or 0.5),
                "risk_score": float(row.get("risk_score") or 0.6),
                "evidence": [{"source": "research.ideas", "id": row.get("id"), "source_kind": row.get("source_kind"), "source_ref": row.get("source_ref")}],
                "route_to_optimizer": True,
            }
        )
    return candidates


def journal_candidates(limit: int) -> list[dict[str, Any]]:
    rows = fetch_json(
        f"""
        SELECT id, run_key, pattern_key, symbol, setup_type, timeframe,
               execution_mode, trade_count, win_rate, average_pnl, thesis,
               edge_hypothesis, evidence, status
        FROM strategy.v_trade_journal_strategy_patterns
        ORDER BY created_at DESC, trade_count DESC, average_pnl DESC NULLS LAST
        LIMIT {max(1, limit)}
        """
    )
    candidates = []
    for row in rows:
        setup = str(row.get("setup_type") or "journal pattern")
        symbol = str(row.get("symbol") or "").upper()
        title = f"Journal pattern strategy: {setup} {symbol}".strip()
        candidates.append(
            {
                "source_kind": "strategy.trade_journal_strategy_patterns",
                "source_ref": row.get("pattern_key"),
                "title": title,
                "symbols": normalize_symbols([symbol] if symbol else []),
                "universe": "NSE",
                "timeframe": normalize_timeframe(row.get("timeframe")),
                "template": infer_template(setup + " " + str(row.get("thesis") or "")),
                "thesis": str(row.get("edge_hypothesis") or row.get("thesis") or title),
                "catalyst": f"Journal pattern count {row.get('trade_count')} with win rate {row.get('win_rate')}",
                "priority_score": 0.4 if int(row.get("trade_count") or 0) < 3 else 0.65,
                "risk_score": 0.85 if int(row.get("trade_count") or 0) < 3 else 0.65,
                "evidence": [{"source": "strategy.v_trade_journal_strategy_patterns", "pattern_key": row.get("pattern_key"), "trade_count": row.get("trade_count")}],
                "route_to_optimizer": bool(symbol),
            }
        )
    return candidates


def signal_candidates(limit: int) -> list[dict[str, Any]]:
    rows = fetch_json(
        f"""
        SELECT id, ts, strategy, symbol, exchange, action, confidence,
               payload, status, external_ref
        FROM trading.signals
        ORDER BY ts DESC NULLS LAST, id DESC
        LIMIT {max(1, limit)}
        """
    )
    candidates = []
    for row in rows:
        strategy = str(row.get("strategy") or "signal")
        symbol = str(row.get("symbol") or "").upper()
        title = f"Signal-sourced strategy: {strategy} {symbol}".strip()
        candidates.append(
            {
                "source_kind": "trading.signals",
                "source_ref": str(row.get("id")),
                "title": title,
                "symbols": normalize_symbols([symbol] if symbol else []),
                "universe": row.get("exchange") or "NSE",
                "timeframe": "5m",
                "template": infer_template(strategy + " " + json.dumps(row.get("payload") or {})),
                "thesis": f"Existing signal stream observed {row.get('action')} on {symbol} from strategy {strategy}. Needs formal backtest before alert promotion.",
                "catalyst": f"Signal status {row.get('status')} from {row.get('external_ref')}",
                "priority_score": float(row.get("confidence") or 0.35),
                "risk_score": 0.75,
                "evidence": [{"source": "trading.signals", "id": row.get("id"), "external_ref": row.get("external_ref")}],
                "route_to_optimizer": bool(symbol),
            }
        )
    return candidates


def component_candidates(limit: int) -> list[dict[str, Any]]:
    rows = fetch_json(
        f"""
        SELECT ss.name AS source_system, sc.id, sc.component_name, sc.component_type,
               sc.source_path, sc.reuse_mode, sc.priority, sc.status,
               sc.description, sc.safety_notes, sc.metadata
        FROM core.source_components sc
        JOIN core.source_systems ss ON ss.id = sc.source_system_id
        WHERE lower(ss.name || ' ' || sc.component_name || ' ' || coalesce(sc.source_path,'') || ' ' || coalesce(sc.description,'')) ~
              'fincept|vibe|openalgo|trading|strategy|quant|indicator|backtest|option'
        ORDER BY
            CASE sc.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
            ss.name,
            sc.component_name
        LIMIT {max(1, limit)}
        """
    )
    candidates = []
    for row in rows:
        name = str(row.get("component_name") or "component")
        source_system = str(row.get("source_system") or "component")
        candidates.append(
            {
                "source_kind": "core.source_components",
                "source_ref": str(row.get("id")),
                "title": f"Component pattern: {source_system} - {name}",
                "symbols": [],
                "universe": "component_reference",
                "timeframe": "research",
                "template": infer_template(name + " " + str(row.get("description") or "")),
                "thesis": str(row.get("description") or f"Use {name} as a strategy/research component pattern."),
                "catalyst": f"{source_system} component is {row.get('status')} with reuse mode {row.get('reuse_mode')}",
                "priority_score": 0.7 if row.get("priority") in {"critical", "high"} else 0.45,
                "risk_score": 0.55,
                "evidence": [{"source": "core.source_components", "id": row.get("id"), "source_system": source_system, "source_path": row.get("source_path")}],
                "route_to_optimizer": False,
            }
        )
    return candidates


def create_run(args: argparse.Namespace) -> dict[str, Any]:
    rows = run_psql_json(
        f"""
        WITH upserted AS (
            INSERT INTO strategy.strategy_discovery_runs (
                run_key, status, source_scope, created_by, started_at, evidence
            )
            VALUES (
                {sql_literal(args.run_key)},
                'running',
                {sql_text_array(args.sources.split(","))},
                {sql_literal(args.actor)},
                now(),
                {sql_jsonb([{"live_execution_allowed": False, "seed_data_allowed": False}])}
            )
            ON CONFLICT (run_key) DO UPDATE SET
                status = 'running',
                source_scope = EXCLUDED.source_scope,
                created_by = EXCLUDED.created_by,
                started_at = now(),
                finished_at = NULL
            RETURNING *
        )
        SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
        """
    )
    return rows[0]


def upsert_generated_idea(run_key: str, candidate: dict[str, Any]) -> dict[str, Any]:
    fingerprint = str(candidate["opportunity_fingerprint"])
    idea_key = f"discovery_opportunity_{fingerprint.replace(':', '_')}"
    rows = run_psql_json(
        f"""
        WITH upserted AS (
            INSERT INTO strategy.generated_ideas (
                idea_key, title, idea_type, symbols, universe, timeframe,
                thesis, edge_hypothesis, entry_rules, exit_rules, risk_rules,
                data_requirements, assumptions, invalidation_tests,
                priority_score, risk_score, status, owner_agent, evidence
            )
            VALUES (
                {sql_literal(idea_key)},
                {sql_literal(candidate["title"])},
                'automatic_strategy_discovery',
                {sql_text_array(candidate.get("symbols"))},
                {sql_literal(candidate.get("universe"))},
                {sql_literal(candidate.get("timeframe"))},
                {sql_literal(candidate.get("thesis"))},
                {sql_literal("Automatically discovered hypothesis. Must pass optimizer, model validation, committee, and paper-monitor gates before any trade action.")},
                {sql_jsonb({"template": candidate.get("template"), "source": candidate.get("source_kind"), "next_step": "Translate/confirm DSL before backtest."})},
                {sql_jsonb({"required": True, "next_step": "Define stop, target, time exit, and failure conditions."})},
                {sql_jsonb({"paper_first": True, "live_execution_allowed": False, "requires_human_approval": True})},
                {sql_text_array(["trading.ohlcv", "transaction costs", "slippage", "source lineage"])},
                {sql_text_array(["Source idea is a hypothesis, not proven alpha.", "Optimizer result can reject this idea."])},
                {sql_text_array(["Reject if backtest fails after costs.", "Reject if walk-forward is unstable.", "Reject if source evidence is stale or non-repeatable."])},
                {sql_numeric(candidate.get("priority_score"))},
                {sql_numeric(candidate.get("risk_score"))},
                'research_queue',
                'Strategy Discovery Agent',
                {sql_jsonb(candidate.get("evidence") or [])}
            )
            ON CONFLICT (idea_key) DO UPDATE SET
                title = EXCLUDED.title,
                symbols = EXCLUDED.symbols,
                universe = EXCLUDED.universe,
                timeframe = EXCLUDED.timeframe,
                thesis = EXCLUDED.thesis,
                edge_hypothesis = EXCLUDED.edge_hypothesis,
                entry_rules = EXCLUDED.entry_rules,
                exit_rules = EXCLUDED.exit_rules,
                risk_rules = EXCLUDED.risk_rules,
                priority_score = EXCLUDED.priority_score,
                risk_score = EXCLUDED.risk_score,
                status = EXCLUDED.status,
                evidence = EXCLUDED.evidence,
                updated_at = now()
            RETURNING id, idea_key, title, status
        )
        SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
        """
    )
    return rows[0]


def upsert_candidate(run_id: int, run_key: str, candidate: dict[str, Any], idea: dict[str, Any], optimizer: dict[str, Any] | None) -> dict[str, Any]:
    opportunity_key = str(candidate["opportunity_fingerprint"])
    source_key = str(candidate["source_fingerprint"])
    discovery_key = f"discovery_opportunity_{opportunity_key.replace(':', '_')}"
    optimizer_run_key = optimizer.get("run_key") if optimizer else None
    optimizer_status = optimizer.get("status") if optimizer else None
    optimizer_run_id = None
    if optimizer_run_key:
        rows = fetch_json(
            f"""
            SELECT id
            FROM strategy.user_defined_optimizer_runs
            WHERE run_key = {sql_literal(optimizer_run_key)}
            LIMIT 1
            """
        )
        optimizer_run_id = rows[0]["id"] if rows else None
    if optimizer_status in {"completed", "reused"}:
        research_gate = "optimizer_completed_model_validation_required"
        next_action = "Review optimizer/backtest evidence, run model validation sweep, then committee review."
        status = "optimizer_reused" if optimizer_status == "reused" else "optimizer_routed"
    elif candidate.get("route_to_optimizer"):
        research_gate = "optimizer_route_available"
        next_action = "Run or repair optimizer workflow before promotion."
        status = "idea_created"
    else:
        research_gate = "component_or_research_reference"
        next_action = "Convert component/reference pattern into a symbol-specific strategy before optimization."
        status = "reference_only"
    rows = run_psql_json(
        f"""
        WITH upserted AS (
            INSERT INTO strategy.strategy_discovery_candidates (
                run_id, discovery_key, source_kind, source_ref, title, symbols,
                universe, timeframe, template, thesis, catalyst, priority_score,
                risk_score, route_to_optimizer, generated_idea_id,
                optimizer_run_id, optimizer_run_key, optimizer_status,
                research_gate, next_required_action, evidence, status,
                opportunity_fingerprint, source_fingerprint, is_canonical,
                first_seen_at, last_seen_at, seen_count, updated_at
            )
            VALUES (
                {run_id},
                {sql_literal(discovery_key)},
                {sql_literal(candidate["source_kind"])},
                {sql_literal(candidate.get("source_ref"))},
                {sql_literal(candidate["title"])},
                {sql_text_array(candidate.get("symbols"))},
                {sql_literal(candidate.get("universe"))},
                {sql_literal(candidate.get("timeframe"))},
                {sql_literal(candidate.get("template"))},
                {sql_literal(candidate.get("thesis"))},
                {sql_literal(candidate.get("catalyst"))},
                {sql_numeric(candidate.get("priority_score"))},
                {sql_numeric(candidate.get("risk_score"))},
                {str(bool(candidate.get("route_to_optimizer"))).lower()},
                {int(idea["id"])},
                {int(optimizer_run_id) if optimizer_run_id else 'NULL'},
                {sql_literal(optimizer_run_key)},
                {sql_literal(optimizer_status)},
                {sql_literal(research_gate)},
                {sql_literal(next_action)},
                {sql_jsonb(candidate.get("evidence") or [])},
                {sql_literal(status)},
                {sql_literal(opportunity_key)},
                {sql_literal(source_key)},
                true,
                now(),
                now(),
                1,
                now()
            )
            ON CONFLICT (opportunity_fingerprint) WHERE is_canonical DO UPDATE SET
                run_id = EXCLUDED.run_id,
                source_kind = EXCLUDED.source_kind,
                source_ref = EXCLUDED.source_ref,
                title = EXCLUDED.title,
                symbols = EXCLUDED.symbols,
                universe = EXCLUDED.universe,
                timeframe = EXCLUDED.timeframe,
                template = EXCLUDED.template,
                thesis = EXCLUDED.thesis,
                catalyst = EXCLUDED.catalyst,
                priority_score = EXCLUDED.priority_score,
                risk_score = EXCLUDED.risk_score,
                route_to_optimizer = EXCLUDED.route_to_optimizer,
                generated_idea_id = EXCLUDED.generated_idea_id,
                optimizer_run_id = EXCLUDED.optimizer_run_id,
                optimizer_run_key = EXCLUDED.optimizer_run_key,
                optimizer_status = EXCLUDED.optimizer_status,
                research_gate = EXCLUDED.research_gate,
                next_required_action = EXCLUDED.next_required_action,
                status = EXCLUDED.status,
                source_fingerprint = EXCLUDED.source_fingerprint,
                evidence = EXCLUDED.evidence,
                last_seen_at = now(),
                suppressed_reason = NULL,
                updated_at = now()
            RETURNING *
        )
        SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
        """
    )
    return rows[0]


def record_observation(run_id: int, discovery_candidate_id: int, candidate: dict[str, Any]) -> dict[str, Any]:
    rows = run_psql_json(
        f"""
        WITH observed AS (
            INSERT INTO strategy.strategy_discovery_observations (
                run_id, discovery_candidate_id, opportunity_fingerprint,
                source_fingerprint, source_refs, evidence, observed_at
            )
            VALUES (
                {int(run_id)},
                {int(discovery_candidate_id)},
                {sql_literal(candidate['opportunity_fingerprint'])},
                {sql_literal(candidate['source_fingerprint'])},
                {sql_jsonb(candidate.get('source_refs') or [])},
                {sql_jsonb(candidate.get('evidence') or [])},
                now()
            )
            ON CONFLICT (run_id, opportunity_fingerprint, source_fingerprint) DO UPDATE SET
                discovery_candidate_id = EXCLUDED.discovery_candidate_id,
                source_refs = EXCLUDED.source_refs,
                evidence = EXCLUDED.evidence
            RETURNING *
        ), observation_state AS (
            SELECT count(*)::integer AS seen_count,
                   min(observed_at) AS first_seen_at,
                   max(observed_at) AS last_seen_at
            FROM (
                SELECT run_id, source_fingerprint, observed_at
                FROM strategy.strategy_discovery_observations
                WHERE opportunity_fingerprint = {sql_literal(candidate['opportunity_fingerprint'])}
                UNION
                SELECT run_id, source_fingerprint, observed_at
                FROM observed
            ) observations
        ), refreshed AS (
            UPDATE strategy.strategy_discovery_candidates canonical
            SET seen_count = observation_state.seen_count,
                first_seen_at = observation_state.first_seen_at,
                last_seen_at = observation_state.last_seen_at,
                updated_at = now()
            FROM observation_state
            WHERE canonical.opportunity_fingerprint = {sql_literal(candidate['opportunity_fingerprint'])}
              AND canonical.is_canonical
            RETURNING canonical.id, canonical.seen_count,
                      canonical.first_seen_at, canonical.last_seen_at
        )
        SELECT coalesce(json_agg(row_to_json(refreshed)), '[]'::json)::text FROM refreshed
        """
    )
    return rows[0] if rows else {}


def recent_optimizer(candidate: dict[str, Any], cooldown_hours: int) -> dict[str, Any] | None:
    rows = fetch_json(
        f"""
        SELECT optimizer.id AS workflow_run_id, optimizer.run_key,
               optimizer.optimization_run_id, optimizer.backtest_run_id,
               optimizer.finished_at
        FROM strategy.strategy_discovery_candidates discovery
        JOIN strategy.user_defined_optimizer_runs optimizer
          ON optimizer.id = discovery.optimizer_run_id
        WHERE discovery.opportunity_fingerprint = {sql_literal(candidate.get('opportunity_fingerprint'))}
          AND discovery.source_fingerprint = {sql_literal(candidate.get('source_fingerprint'))}
          AND discovery.is_canonical
          AND optimizer.status = 'completed'
          AND optimizer.finished_at >= now() - make_interval(hours => {max(1, cooldown_hours)})
        ORDER BY optimizer.finished_at DESC
        LIMIT 1
        """
    )
    if not rows:
        return None
    return {
        "status": "reused",
        **rows[0],
        "source_fingerprint": candidate["source_fingerprint"],
        "reuse_reason": f"unchanged source was optimized within the last {max(1, cooldown_hours)} hours",
    }


def route_optimizer(args: argparse.Namespace, run_key: str, index: int, candidate: dict[str, Any]) -> dict[str, Any] | None:
    if not candidate.get("route_to_optimizer"):
        return None
    symbols = normalize_symbols(candidate.get("symbols"))
    if not symbols:
        return None
    reusable = recent_optimizer(candidate, args.optimizer_cooldown_hours)
    if reusable:
        return reusable
    optimizer_run_key = f"{run_key}_opt_{index}_{slugify(candidate['title'])}"
    command = [
        sys.executable,
        str(RUNTIME_ROOT / "scripts" / "run_user_defined_strategy_optimizer.py"),
        "--run-key",
        optimizer_run_key,
        "--actor",
        "Strategy Discovery Agent",
        "--strategy-name",
        f"{candidate['title'][:90]} [{run_key} #{index}]",
        "--intake-text",
        str(candidate.get("thesis") or candidate["title"]),
        "--symbols",
        ",".join(symbols[:3]),
        "--universe",
        str(candidate.get("universe") or "NSE"),
        "--timeframe",
        normalize_timeframe(candidate.get("timeframe")),
        "--template",
        str(candidate.get("template") or "momentum"),
        "--max-symbols",
        "3",
        "--min-rows-per-symbol",
        "50",
        "--min-total-rows",
        "50",
    ]
    completed = subprocess.run(command, cwd=VAULT_ROOT, text=True, capture_output=True, check=False, timeout=360)
    if completed.returncode != 0:
        return {"run_key": optimizer_run_key, "status": "failed", "error": (completed.stderr or completed.stdout).strip()[:1000]}
    return json.loads(completed.stdout)


def gather_candidates(args: argparse.Namespace) -> list[dict[str, Any]]:
    sources = {source.strip() for source in args.sources.split(",") if source.strip()}
    candidates: list[dict[str, Any]] = []
    if "research" in sources:
        candidates.extend(research_candidates(args.per_source_limit))
    if "journals" in sources:
        candidates.extend(journal_candidates(args.per_source_limit))
    if "signals" in sources:
        candidates.extend(signal_candidates(args.per_source_limit))
    if "components" in sources:
        candidates.extend(component_candidates(args.per_source_limit))
    deduped: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        candidate["opportunity_fingerprint"] = opportunity_fingerprint(candidate)
        candidate["source_fingerprint"] = source_fingerprint(candidate)
        candidate["evidence"] = [
            *(candidate.get("evidence") or []),
            {
                "opportunity_fingerprint": candidate["opportunity_fingerprint"],
                "source_fingerprint": candidate["source_fingerprint"],
                "fingerprint_version": "strategy_discovery_identity_v2",
            },
        ]
        key = str(candidate["opportunity_fingerprint"])
        existing = deduped.get(key)
        if existing is None:
            candidate["source_refs"] = [f"{candidate.get('source_kind')}:{candidate.get('source_ref')}"]
            candidate["_source_duplicate_count"] = 1
            deduped[key] = candidate
            continue
        existing_score = float(existing.get("priority_score") or 0)
        candidate_score = float(candidate.get("priority_score") or 0)
        selected = candidate if candidate_score > existing_score else existing
        other = existing if selected is candidate else candidate
        evidence_by_key = {
            json.dumps(item, sort_keys=True, default=str): item
            for item in [*(selected.get("evidence") or []), *(other.get("evidence") or [])]
        }
        selected["evidence"] = list(evidence_by_key.values())
        selected["priority_score"] = max(existing_score, candidate_score)
        selected["risk_score"] = max(float(existing.get("risk_score") or 0), float(candidate.get("risk_score") or 0))
        selected["route_to_optimizer"] = bool(existing.get("route_to_optimizer") or candidate.get("route_to_optimizer"))
        selected["source_refs"] = sorted(set([
            *(existing.get("source_refs") or [f"{existing.get('source_kind')}:{existing.get('source_ref')}"]),
            f"{candidate.get('source_kind')}:{candidate.get('source_ref')}",
        ]))
        selected["_source_duplicate_count"] = int(existing.get("_source_duplicate_count") or 1) + 1
        deduped[key] = selected
    return sorted(deduped.values(), key=lambda row: float(row.get("priority_score") or 0), reverse=True)[: max(1, args.max_candidates)]


def finish_run(run_id: int, status: str, summary: dict[str, Any], artifact_rel: str) -> None:
    run_psql_json(
        f"""
        WITH updated AS (
            UPDATE strategy.strategy_discovery_runs
            SET status = {sql_literal(status)},
                discovered_count = {int(summary.get("discovered_count") or 0)},
                generated_idea_count = {int(summary.get("generated_idea_count") or 0)},
                optimizer_routed_count = {int(summary.get("optimizer_routed_count") or 0)},
                summary = {sql_jsonb(summary)},
                artifact_path = {sql_literal(artifact_rel)},
                finished_at = now()
            WHERE id = {int(run_id)}
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(updated)), '[]'::json)::text FROM updated
        """
    )


def run_discovery(args: argparse.Namespace) -> dict[str, Any]:
    run = create_run(args)
    candidates = gather_candidates(args)
    output_candidates = []
    optimizer_count = 0
    optimizer_reused_count = 0
    for index, candidate in enumerate(candidates[: args.max_candidates], start=1):
        idea = upsert_generated_idea(args.run_key, candidate)
        optimizer = route_optimizer(args, args.run_key, index, candidate) if index <= args.route_top else None
        if optimizer and optimizer.get("status") == "completed":
            optimizer_count += 1
        if optimizer and optimizer.get("status") == "reused":
            optimizer_reused_count += 1
        row = upsert_candidate(int(run["id"]), args.run_key, candidate, idea, optimizer)
        observation = record_observation(int(run["id"]), int(row["id"]), candidate)
        output_candidates.append({"candidate": row, "generated_idea": idea, "optimizer": optimizer, "observation": observation})

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    summary = {
        "discovered_count": len(candidates),
        "canonical_opportunity_count": len(candidates),
        "source_duplicate_suppressed_count": sum(max(0, int(candidate.get("_source_duplicate_count") or 1) - 1) for candidate in candidates),
        "generated_idea_count": len(output_candidates),
        "optimizer_routed_count": optimizer_count,
        "optimizer_reused_count": optimizer_reused_count,
        "source_scope": [source.strip() for source in args.sources.split(",") if source.strip()],
        "live_execution_allowed": False,
        "seed_data_allowed": False,
    }
    artifact = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_key": args.run_key,
        "summary": summary,
        "candidates": output_candidates,
    }
    artifact_path = ARTIFACT_ROOT / f"{args.run_key}.json"
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True, default=str), encoding="utf-8")
    artifact_rel = artifact_reference(artifact_path)
    finish_run(int(run["id"]), "completed", summary, artifact_rel)
    artifact["artifact_path"] = artifact_rel
    artifact["run_id"] = run["id"]
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover strategy ideas from real internal sources and optionally route top ideas to the optimizer.")
    parser.add_argument("--run-key", default=f"strategy_discovery_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
    parser.add_argument("--actor", default="Strategy Discovery Agent")
    parser.add_argument("--sources", default="research,journals,signals,components")
    parser.add_argument("--per-source-limit", type=int, default=8)
    parser.add_argument("--max-candidates", type=int, default=16)
    parser.add_argument("--route-top", type=int, default=2)
    parser.add_argument("--optimizer-cooldown-hours", type=int, default=168)
    args = parser.parse_args()
    print(json.dumps(run_discovery(args), indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
