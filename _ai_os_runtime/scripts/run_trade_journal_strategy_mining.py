#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime_storage import artifact_reference, artifact_root

from run_strategy_backtest import run_psql_json, sql_jsonb, sql_literal


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = artifact_root("trade_journal_mining")


def sql_text_array(values: Any) -> str:
    if not values:
        return "ARRAY[]::text[]"
    if isinstance(values, str):
        values = [values]
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    if not cleaned:
        return "ARRAY[]::text[]"
    return "ARRAY[" + ",".join(sql_literal(value) for value in cleaned) + "]::text[]"


def sql_numeric(value: Any) -> str:
    if value is None:
        return "NULL"
    try:
        return str(float(value))
    except (TypeError, ValueError):
        return "NULL"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug[:64] or "pattern"


def fetch_rows() -> list[dict[str, Any]]:
    rows = run_psql_json(
        """
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT
                'journal' AS source_kind,
                id::TEXT AS source_id,
                journal_ts::TEXT AS event_ts,
                upper(nullif(symbol, '')) AS symbol,
                nullif(strategy, '') AS strategy_key,
                coalesce(nullif(setup_type, ''), nullif(strategy, ''), 'unspecified') AS setup_type,
                coalesce(nullif(timeframe, ''), 'unknown') AS timeframe,
                'journal' AS execution_mode,
                pnl::float8 AS pnl,
                r_multiple::float8 AS r_multiple,
                coalesce(nullif(entry_reason, ''), nullif(raw_text, ''), nullif(strategy, ''), 'journal note') AS entry_reason,
                nullif(exit_reason, '') AS exit_reason,
                raw_text AS notes,
                jsonb_build_object(
                    'table', 'trading.trade_journals',
                    'id', id,
                    'note_path', note_path,
                    'market_condition', market_condition,
                    'execution_quality', execution_quality,
                    'extracted_features', extracted_features
                ) AS evidence
            FROM trading.trade_journals

            UNION ALL

            SELECT
                'trade_activity_ledger' AS source_kind,
                id::TEXT AS source_id,
                trade_ts::TEXT AS event_ts,
                upper(nullif(symbol, '')) AS symbol,
                nullif(strategy_key, '') AS strategy_key,
                coalesce(nullif(setup_type, ''), nullif(strategy_key, ''), 'unspecified') AS setup_type,
                coalesce(nullif(timeframe, ''), 'unknown') AS timeframe,
                coalesce(nullif(execution_mode, ''), 'manual') AS execution_mode,
                realized_pnl::float8 AS pnl,
                NULL::float8 AS r_multiple,
                coalesce(nullif(thesis, ''), nullif(strategy_key, ''), 'trade ledger row') AS entry_reason,
                NULL::TEXT AS exit_reason,
                thesis AS notes,
                jsonb_build_object(
                    'table', 'trading.trade_activity_ledger',
                    'id', id,
                    'activity_type', activity_type,
                    'side', side,
                    'quantity', quantity,
                    'price', price,
                    'status', status,
                    'tags', tags,
                    'payload', payload
                ) AS evidence
            FROM trading.trade_activity_ledger
        ) rows
        """
    )
    return rows


def pattern_groups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row.get("setup_type") or "unspecified").strip().lower(),
            str(row.get("timeframe") or "unknown").strip().lower(),
            str(row.get("execution_mode") or "manual").strip().lower(),
        )
        grouped[key].append(row)

    patterns: list[dict[str, Any]] = []
    for (setup_type, timeframe, execution_mode), members in grouped.items():
        pnls = [float(row["pnl"]) for row in members if row.get("pnl") is not None]
        wins = [pnl for pnl in pnls if pnl > 0]
        losses = [pnl for pnl in pnls if pnl < 0]
        symbols = sorted({str(row.get("symbol") or "").upper() for row in members if row.get("symbol")})
        source_rows = [
            {
                "source_kind": row.get("source_kind"),
                "source_id": row.get("source_id"),
                "event_ts": row.get("event_ts"),
                "symbol": row.get("symbol"),
                "pnl": row.get("pnl"),
                "evidence": row.get("evidence"),
            }
            for row in members
        ]
        trade_count = len(members)
        total_pnl = sum(pnls) if pnls else None
        average_pnl = (total_pnl / len(pnls)) if pnls else None
        win_rate = (len(wins) / len(pnls)) if pnls else None
        symbol_label = symbols[0] if len(symbols) == 1 else None
        patterns.append(
            {
                "symbol": symbol_label,
                "symbols": symbols,
                "setup_type": setup_type,
                "timeframe": timeframe,
                "execution_mode": execution_mode,
                "trade_count": trade_count,
                "win_count": len(wins),
                "loss_count": len(losses),
                "total_pnl": total_pnl,
                "average_pnl": average_pnl,
                "win_rate": win_rate,
                "source_rows": source_rows,
                "entry_notes": [str(row.get("entry_reason") or row.get("notes") or "")[:240] for row in members[:5]],
            }
        )
    return sorted(patterns, key=lambda item: (item["trade_count"], item["average_pnl"] or 0), reverse=True)


def create_run(args: argparse.Namespace, source_count: int) -> dict[str, Any]:
    evidence = [
        {"source": "trading.trade_journals"},
        {"source": "trading.trade_activity_ledger"},
        {"source_row_count": source_count},
        {"live_execution_allowed": False, "seed_data_allowed": False},
    ]
    rows = run_psql_json(
        f"""
        WITH upserted AS (
            INSERT INTO strategy.trade_journal_mining_runs (
                run_key, source_scope, min_trades, status, evidence, created_by, started_at
            )
            VALUES (
                {sql_literal(args.run_key)},
                'trade_journals_and_activity_ledger',
                {max(1, int(args.min_trades))},
                'running',
                {sql_jsonb(evidence)},
                {sql_literal(args.actor)},
                now()
            )
            ON CONFLICT (run_key) DO UPDATE SET
                source_scope = EXCLUDED.source_scope,
                min_trades = EXCLUDED.min_trades,
                status = EXCLUDED.status,
                evidence = EXCLUDED.evidence,
                created_by = EXCLUDED.created_by,
                started_at = now(),
                finished_at = NULL
            RETURNING *
        )
        SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
        """
    )
    return rows[0]


def upsert_intake(args: argparse.Namespace, patterns: list[dict[str, Any]]) -> dict[str, Any]:
    symbols = sorted({symbol for pattern in patterns for symbol in pattern.get("symbols", [])})
    intake_key = f"{args.run_key}_journal_mining_intake"
    status = "research_queue" if patterns else "insufficient_source_data"
    evidence = [
        {"source": "strategy.trade_journal_mining_runs", "run_key": args.run_key},
        {"source": "trading.trade_journals"},
        {"source": "trading.trade_activity_ledger"},
    ]
    rows = run_psql_json(
        f"""
        WITH upserted AS (
            INSERT INTO strategy.strategy_intakes (
                intake_key, created_by, intake_text, strategy_name, strategy_family,
                asset_class, symbols, universe, timeframe, intent_tags, constraints_text,
                risk_notes, requested_outputs, source_kind, source_ref, status,
                owner_agent, assigned_agents, structured_spec, evidence
            )
            VALUES (
                {sql_literal(intake_key)},
                {sql_literal(args.actor)},
                {sql_literal('Mine real trade journals and activity ledger rows into strategy hypotheses. Every output must pass DSL, data-quality, backtest, optimizer, model-validation, and committee gates before any paper or live use.')},
                {sql_literal('Trade journal mined strategy ideas')},
                'journal_mined',
                'multi_asset',
                {sql_text_array(symbols)},
                {sql_literal(', '.join(symbols) if symbols else 'journal universe')},
                'mixed',
                {sql_text_array(['trade_journal_learning', 'strategy_idea_generation', 'requires_backtest'])},
                'Use only real journal/ledger rows. Do not seed trades. Do not route to live execution.',
                'Thin samples are research hypotheses only; every idea requires cost/slippage-aware backtest and model-validation.',
                {sql_text_array(['generated_ideas', 'dsl_translation', 'backtest_plan', 'model_validation'])},
                'trade_journal_mining',
                {sql_literal(args.run_key)},
                {sql_literal(status)},
                'Strategy Generator',
                {sql_text_array(['Strategy Generator','Strategy Research Agent','Backtest Engineer','Model Validation Agent','Risk Agent'])},
                {sql_jsonb({'run_key': args.run_key, 'pattern_count': len(patterns), 'min_trades': args.min_trades})},
                {sql_jsonb(evidence)}
            )
            ON CONFLICT (intake_key) DO UPDATE SET
                symbols = EXCLUDED.symbols,
                universe = EXCLUDED.universe,
                status = EXCLUDED.status,
                structured_spec = EXCLUDED.structured_spec,
                evidence = EXCLUDED.evidence,
                updated_at = now()
            RETURNING *
        )
        SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
        """
    )
    return rows[0]


def idea_payload(args: argparse.Namespace, intake: dict[str, Any], pattern: dict[str, Any]) -> dict[str, Any]:
    symbol_text = pattern["symbol"] or "journal universe"
    setup = pattern["setup_type"].replace("_", " ")
    win_rate = pattern.get("win_rate")
    avg_pnl = pattern.get("average_pnl")
    evidence_level = "thin" if pattern["trade_count"] < 3 else "developing"
    title = f"Journal-mined {setup} pattern ({symbol_text}, {pattern['timeframe']})"
    thesis = (
        f"{pattern['trade_count']} real journal/ledger row(s) show a {setup} setup in "
        f"{pattern['execution_mode']} mode with average PnL "
        f"{avg_pnl:.2f}" if avg_pnl is not None else
        f"{pattern['trade_count']} real journal/ledger row(s) show a {setup} setup but outcomes are incomplete"
    )
    edge = (
        f"Historical journal evidence suggests the setup may have a repeatable context. "
        f"Evidence level is {evidence_level}; win rate is "
        f"{win_rate:.0%}" if win_rate is not None else
        f"Historical journal evidence suggests the setup may be worth formalizing. "
        f"Evidence level is {evidence_level}; win rate is unavailable."
    )
    return {
        "idea_key": f"{args.run_key}_{slugify(setup)}_{slugify(pattern['timeframe'])}_{slugify(pattern['execution_mode'])}",
        "title": title,
        "idea_type": "trade_journal_mined_strategy",
        "symbols": pattern.get("symbols", []),
        "universe": ", ".join(pattern.get("symbols", [])) or "journal universe",
        "timeframe": pattern["timeframe"],
        "thesis": thesis,
        "edge_hypothesis": edge,
        "entry_rules": {
            "source": "trade_journal_mining",
            "setup_type": pattern["setup_type"],
            "execution_mode": pattern["execution_mode"],
            "journal_entry_notes": pattern.get("entry_notes", []),
            "next_step": "Translate this into explicit DSL before backtest.",
        },
        "exit_rules": {
            "required": True,
            "next_step": "Define stop, target, time exit, and event exit before backtest.",
        },
        "risk_rules": {
            "sample_size": pattern["trade_count"],
            "evidence_level": evidence_level,
            "paper_first": True,
            "live_execution_allowed": False,
            "requires": ["data_quality_gate", "backtest", "optimizer", "model_validation", "committee_review"],
        },
        "data_requirements": [
            "trading.trade_journals",
            "trading.trade_activity_ledger",
            "trading.ohlcv",
            "instrument costs and slippage",
            "event calendar if setup is event-driven",
        ],
        "assumptions": [
            "Journal/ledger rows are accurate and not survivorship-selected.",
            "The observed context can be translated into deterministic rules.",
            "Costs, slippage, liquidity, and regime filters may erase the edge.",
        ],
        "invalidation_tests": [
            "Reject if deterministic backtest is negative after costs.",
            "Reject if walk-forward performance is unstable.",
            "Reject if sample expands and win rate/expectancy deteriorates.",
            "Reject if rules cannot be written without look-ahead or discretionary leakage.",
        ],
        "priority_score": 0.35 if pattern["trade_count"] < 3 else 0.65,
        "risk_score": 0.85 if pattern["trade_count"] < 3 else 0.65,
        "status": "research_queue",
        "owner_agent": "Strategy Generator",
        "evidence": [
            {"source": "strategy.trade_journal_mining_runs", "run_key": args.run_key},
            {"source": "strategy.strategy_intakes", "intake_key": intake["intake_key"]},
            {"source_rows": pattern["source_rows"]},
            {"live_execution_allowed": False, "seed_data_allowed": False},
        ],
    }


def upsert_pattern_and_idea(run: dict[str, Any], intake: dict[str, Any], args: argparse.Namespace, pattern: dict[str, Any]) -> dict[str, Any]:
    payload = idea_payload(args, intake, pattern)
    pattern_key = f"{payload['idea_key']}_pattern"
    candidate_key = f"candidate_{payload['idea_key']}"
    rows = run_psql_json(
        f"""
        WITH idea AS (
            INSERT INTO strategy.generated_ideas (
                idea_key, intake_id, title, idea_type, symbols, universe, timeframe,
                thesis, edge_hypothesis, entry_rules, exit_rules, risk_rules,
                data_requirements, assumptions, invalidation_tests, priority_score,
                risk_score, status, owner_agent, evidence
            )
            VALUES (
                {sql_literal(payload["idea_key"])},
                {int(intake["id"])},
                {sql_literal(payload["title"])},
                {sql_literal(payload["idea_type"])},
                {sql_text_array(payload["symbols"])},
                {sql_literal(payload["universe"])},
                {sql_literal(payload["timeframe"])},
                {sql_literal(payload["thesis"])},
                {sql_literal(payload["edge_hypothesis"])},
                {sql_jsonb(payload["entry_rules"])},
                {sql_jsonb(payload["exit_rules"])},
                {sql_jsonb(payload["risk_rules"])},
                {sql_text_array(payload["data_requirements"])},
                {sql_text_array(payload["assumptions"])},
                {sql_text_array(payload["invalidation_tests"])},
                {sql_numeric(payload["priority_score"])},
                {sql_numeric(payload["risk_score"])},
                {sql_literal(payload["status"])},
                {sql_literal(payload["owner_agent"])},
                {sql_jsonb(payload["evidence"])}
            )
            ON CONFLICT (idea_key) DO UPDATE SET
                intake_id = EXCLUDED.intake_id,
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
        pattern AS (
            INSERT INTO strategy.trade_journal_strategy_patterns (
                run_id, pattern_key, pattern_type, symbol, setup_type, timeframe,
                execution_mode, trade_count, win_count, loss_count, total_pnl,
                average_pnl, win_rate, idea_id, candidate_key, thesis,
                edge_hypothesis, entry_rules, exit_rules, risk_rules, evidence, status
            )
            SELECT
                {int(run["id"])},
                {sql_literal(pattern_key)},
                'journal_performance_cluster',
                {sql_literal(pattern["symbol"])},
                {sql_literal(pattern["setup_type"])},
                {sql_literal(pattern["timeframe"])},
                {sql_literal(pattern["execution_mode"])},
                {int(pattern["trade_count"])},
                {int(pattern["win_count"])},
                {int(pattern["loss_count"])},
                {sql_numeric(pattern["total_pnl"])},
                {sql_numeric(pattern["average_pnl"])},
                {sql_numeric(pattern["win_rate"])},
                idea.id,
                {sql_literal(candidate_key)},
                {sql_literal(payload["thesis"])},
                {sql_literal(payload["edge_hypothesis"])},
                {sql_jsonb(payload["entry_rules"])},
                {sql_jsonb(payload["exit_rules"])},
                {sql_jsonb(payload["risk_rules"])},
                {sql_jsonb(payload["evidence"])},
                CASE WHEN {int(pattern["trade_count"])} < {max(1, int(args.min_trades))} THEN 'thin_sample_research' ELSE 'research_queue' END
            FROM idea
            ON CONFLICT (pattern_key) DO UPDATE SET
                run_id = EXCLUDED.run_id,
                symbol = EXCLUDED.symbol,
                setup_type = EXCLUDED.setup_type,
                timeframe = EXCLUDED.timeframe,
                execution_mode = EXCLUDED.execution_mode,
                trade_count = EXCLUDED.trade_count,
                win_count = EXCLUDED.win_count,
                loss_count = EXCLUDED.loss_count,
                total_pnl = EXCLUDED.total_pnl,
                average_pnl = EXCLUDED.average_pnl,
                win_rate = EXCLUDED.win_rate,
                idea_id = EXCLUDED.idea_id,
                candidate_key = EXCLUDED.candidate_key,
                thesis = EXCLUDED.thesis,
                edge_hypothesis = EXCLUDED.edge_hypothesis,
                entry_rules = EXCLUDED.entry_rules,
                exit_rules = EXCLUDED.exit_rules,
                risk_rules = EXCLUDED.risk_rules,
                evidence = EXCLUDED.evidence,
                status = EXCLUDED.status
            RETURNING *
        )
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT
                pattern.id AS pattern_id,
                pattern.pattern_key,
                pattern.status AS pattern_status,
                idea.id AS idea_id,
                idea.idea_key,
                idea.title,
                idea.status AS idea_status,
                pattern.trade_count,
                pattern.win_rate,
                pattern.average_pnl
            FROM pattern
            CROSS JOIN idea
        ) rows
        """
    )
    return rows[0]


def finish_run(run: dict[str, Any], args: argparse.Namespace, status: str, created: list[dict[str, Any]], patterns: list[dict[str, Any]], artifact_path: Path | None) -> dict[str, Any]:
    summary = {
        "source_rows": sum(pattern["trade_count"] for pattern in patterns),
        "pattern_count": len(patterns),
        "generated_idea_count": len(created),
        "min_trades": args.min_trades,
        "live_execution_allowed": False,
        "seed_data_allowed": False,
    }
    artifact_rel = artifact_reference(artifact_path) if artifact_path else None
    rows = run_psql_json(
        f"""
        WITH updated AS (
            UPDATE strategy.trade_journal_mining_runs
            SET
                status = {sql_literal(status)},
                generated_idea_count = {len(created)},
                candidate_pattern_count = {len(patterns)},
                summary = {sql_jsonb(summary)},
                artifact_path = {sql_literal(artifact_rel)},
                finished_at = now()
            WHERE id = {int(run["id"])}
            RETURNING *
        )
        SELECT coalesce(json_agg(row_to_json(updated)), '[]'::json)::text FROM updated
        """
    )
    return rows[0]


def run_mining(args: argparse.Namespace) -> dict[str, Any]:
    source_rows = fetch_rows()
    run = create_run(args, len(source_rows))
    patterns = pattern_groups(source_rows)
    eligible = [pattern for pattern in patterns if pattern["trade_count"] >= max(1, int(args.min_trades))]
    if not eligible and patterns and args.allow_thin_sample:
        eligible = patterns[: max(1, int(args.max_patterns))]
    eligible = eligible[: max(1, int(args.max_patterns))]
    intake = upsert_intake(args, eligible or patterns)

    created = [upsert_pattern_and_idea(run, intake, args, pattern) for pattern in eligible]
    status = "completed" if created else ("insufficient_source_data" if source_rows else "no_source_rows")

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    artifact = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_key": args.run_key,
        "status": status,
        "source_row_count": len(source_rows),
        "pattern_count": len(patterns),
        "eligible_pattern_count": len(eligible),
        "created": created,
        "patterns": patterns,
        "live_execution_allowed": False,
        "seed_data_allowed": False,
    }
    artifact_path = ARTIFACT_ROOT / f"{args.run_key}.json"
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True, default=str), encoding="utf-8")
    finished = finish_run(run, args, status, created, patterns, artifact_path)
    artifact["artifact_path"] = artifact_reference(artifact_path)
    artifact["run_id"] = finished["id"]
    artifact["intake_key"] = intake.get("intake_key")
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser(description="Mine real trade journals and trade activity rows into strategy hypotheses.")
    parser.add_argument("--run-key", default=f"journal_mining_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
    parser.add_argument("--actor", default="Strategy Generator")
    parser.add_argument("--min-trades", type=int, default=3)
    parser.add_argument("--max-patterns", type=int, default=10)
    parser.add_argument("--allow-thin-sample", action="store_true", help="Generate low-evidence hypotheses when real source rows exist but the sample is below min-trades.")
    args = parser.parse_args()
    print(json.dumps(run_mining(args), indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
