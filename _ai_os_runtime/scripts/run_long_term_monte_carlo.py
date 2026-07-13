#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import math
import random
import re
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUNTIME_ROOT = Path(os.environ.get("AI_OS_RUNTIME_ROOT") or Path(__file__).absolute().parents[1])
VAULT_ROOT = Path(os.environ.get("AI_OS_VAULT_ROOT") or RUNTIME_ROOT.parent)
NOTE_DIR = VAULT_ROOT / "ai memory" / "02 Portfolio" / "Long-Term Monte Carlo"


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return f"{sql_literal(json.dumps(value if value is not None else {}, sort_keys=True, default=str))}::jsonb"


def run_psql_json(sql: str) -> list[dict[str, Any]]:
    command = [
        "docker",
        "exec",
        "-i",
        "ai_os_postgres",
        "psql",
        "-q",
        "-t",
        "-A",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        "ai_os",
        "-d",
        "ai_os",
    ]
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return json.loads(completed.stdout.strip() or "[]")


def clean(value: object, fallback: str = "n/a") -> str:
    if value is None:
        return fallback
    text = re.sub(r"\s+", " ", str(value).replace("\x00", " ")).strip()
    return text or fallback


def safe_slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-").lower()[:90] or "monte-carlo"


def to_float(value: object, fallback: float | None = None) -> float | None:
    if value is None or value == "":
        return fallback
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return fallback


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * pct
    lower = math.floor(pos)
    upper = math.ceil(pos)
    if lower == upper:
        return ordered[int(pos)]
    weight = pos - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def pct_summary(values: list[float]) -> dict[str, float | None]:
    return {
        "p01": round(percentile(values, 0.01), 4) if values else None,
        "p05": round(percentile(values, 0.05), 4) if values else None,
        "p10": round(percentile(values, 0.10), 4) if values else None,
        "p25": round(percentile(values, 0.25), 4) if values else None,
        "p50": round(percentile(values, 0.50), 4) if values else None,
        "p75": round(percentile(values, 0.75), 4) if values else None,
        "p90": round(percentile(values, 0.90), 4) if values else None,
        "p95": round(percentile(values, 0.95), 4) if values else None,
        "p99": round(percentile(values, 0.99), 4) if values else None,
    }


def triangular(rng: random.Random, low: float, mode: float, high: float) -> float:
    low, high = min(low, high), max(low, high)
    mode = min(max(mode, low), high)
    return rng.triangular(low, high, mode)


def fetch_context(holding_thesis_id: int) -> dict[str, Any]:
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT *
            FROM portfolio.v_long_term_thesis_control
            WHERE id = {int(holding_thesis_id)}
            LIMIT 1
        ) rows
        """
    )
    if not rows:
        raise ValueError(f"No long-term thesis found for id {holding_thesis_id}")
    thesis = rows[0]
    valuation_rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT *
            FROM portfolio.v_long_term_valuation_models
            WHERE holding_thesis_id = {int(holding_thesis_id)}
            ORDER BY model_key
        ) rows
        """
    )
    source_extractions = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT id, source_document_id, document_title, document_type,
                   page_count, extracted_chars, extraction_status, local_text_path,
                   extracted_at
            FROM portfolio.v_long_term_source_document_extractions
            WHERE symbol = {sql_literal(clean(thesis.get("symbol")).upper())}
              AND exchange IS NOT DISTINCT FROM {sql_literal(thesis.get("exchange"))}
            ORDER BY extracted_at DESC
            LIMIT 10
        ) rows
        """
    )
    quotes = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT source_key, provider, provider_symbol, symbol, exchange,
                   price, change_percent, quote_ts, created_at
            FROM market.v_latest_price_quotes
            WHERE upper(symbol) = {sql_literal(clean(thesis.get("symbol")).upper())}
              AND exchange IS NOT DISTINCT FROM {sql_literal(thesis.get("exchange"))}
            ORDER BY quote_ts DESC NULLS LAST, created_at DESC
            LIMIT 5
        ) rows
        """
    )
    positions = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT client_name, account_code, broker, symbol, exchange,
                   quantity, average_price, market_price, market_value,
                   gross_exposure, net_exposure, purpose_key, as_of
            FROM books.v_book_positions
            WHERE book_key = 'long_term'
              AND status = 'active'
              AND upper(symbol) = {sql_literal(clean(thesis.get("symbol")).upper())}
              AND exchange IS NOT DISTINCT FROM {sql_literal(thesis.get("exchange"))}
            ORDER BY gross_exposure DESC NULLS LAST
            LIMIT 50
        ) rows
        """
    )
    checklists = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT checklist_key, status, score
            FROM portfolio.v_long_term_thesis_checklists
            WHERE holding_thesis_id = {int(holding_thesis_id)}
            ORDER BY checklist_key
        ) rows
        """
    )
    return {
        "thesis": thesis,
        "valuation_rows": valuation_rows,
        "source_extractions": source_extractions,
        "quotes": quotes,
        "positions": positions,
        "checklists": checklists,
    }


def valuation_row(context: dict[str, Any], model_key: str) -> dict[str, Any]:
    for row in context["valuation_rows"]:
        if row.get("model_key") == model_key:
            return row
    return {}


def financial_snapshot(context: dict[str, Any]) -> dict[str, Any]:
    for row in context["valuation_rows"]:
        assumptions = row.get("assumptions") or {}
        snap = assumptions.get("financial_snapshot")
        if isinstance(snap, dict) and snap:
            return snap
    return {}


def latest_price(context: dict[str, Any], fallback: float | None = None) -> float | None:
    for quote in context["quotes"]:
        price = to_float(quote.get("price"))
        if price is not None and price > 0:
            return price
    for row in context["valuation_rows"]:
        price = to_float((row.get("assumptions") or {}).get("current_price"))
        if price is not None and price > 0:
            return price
    return fallback


def build_assumptions(args: argparse.Namespace, context: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    snap = financial_snapshot(context)
    warnings: list[str] = []
    revenue = to_float(snap.get("revenue_crore"))
    pat = to_float(snap.get("pat_crore"))
    current_pat_margin = (pat / revenue) if revenue and pat and revenue > 0 else None
    volume_growth = to_float(snap.get("volume_growth_pct"))
    base_growth = args.revenue_growth_base
    if base_growth is None:
        base_growth = (volume_growth / 100.0) if volume_growth is not None else 0.08
    start_price = args.start_price if args.start_price is not None else latest_price(context)
    if start_price is None or start_price <= 0:
        warnings.append("No current price found; Monte Carlo cannot be treated as valuation-ready.")
        start_price = 100.0
    starting_multiple = args.starting_multiple
    if starting_multiple is None:
        starting_multiple = 35.0
        warnings.append("Starting valuation multiple is a provisional operator default because share-count/current multiple is not yet sourced.")
    elif not args.starting_multiple_source:
        warnings.append("Starting valuation multiple was provided without a source reference; committee review must validate it before treating the run as complete.")
    if current_pat_margin is None:
        current_pat_margin = 0.08
        warnings.append("PAT margin is missing; using provisional 8 percent margin for engine run.")
    source_quality_haircut = args.source_quality_haircut
    if context["source_extractions"]:
        source_quality_haircut = min(source_quality_haircut, 0.98)
    else:
        source_quality_haircut = min(source_quality_haircut, 0.85)
        warnings.append("No extracted source document found; applying stronger source-quality haircut.")
    assumptions = {
        "method": "fundamental_driver_monte_carlo_v1",
        "horizon_years": args.horizon_years,
        "simulation_count": args.simulations,
        "seed": args.seed,
        "start_price": start_price,
        "starting_multiple": starting_multiple,
        "starting_multiple_source": args.starting_multiple_source or "operator_input_without_source_reference",
        "starting_metric": "pat_proxy",
        "revenue_growth_distribution": {
            "low": args.revenue_growth_low if args.revenue_growth_low is not None else max(base_growth - 0.10, -0.05),
            "base": base_growth,
            "high": args.revenue_growth_high if args.revenue_growth_high is not None else base_growth + 0.10,
        },
        "terminal_pat_margin_distribution": {
            "low": args.margin_low if args.margin_low is not None else max(current_pat_margin * 0.65, 0.01),
            "base": args.margin_base if args.margin_base is not None else current_pat_margin,
            "high": args.margin_high if args.margin_high is not None else min(current_pat_margin * 1.45, 0.30),
        },
        "terminal_multiple_distribution": {
            "low": args.terminal_multiple_low,
            "base": args.terminal_multiple_base,
            "high": args.terminal_multiple_high,
        },
        "annual_dilution_distribution": {
            "low": args.dilution_low,
            "base": args.dilution_base,
            "high": args.dilution_high,
        },
        "annual_volatility": args.annual_volatility,
        "source_quality_haircut": source_quality_haircut,
        "capital_action_allowed": False,
        "live_execution_allowed": False,
    }
    return assumptions, warnings


def run_simulation(assumptions: dict[str, Any]) -> dict[str, Any]:
    rng = random.Random(int(assumptions["seed"]))
    years = int(assumptions["horizon_years"])
    start_price = float(assumptions["start_price"])
    starting_multiple = float(assumptions["starting_multiple"])
    growth = assumptions["revenue_growth_distribution"]
    margin = assumptions["terminal_pat_margin_distribution"]
    multiple = assumptions["terminal_multiple_distribution"]
    dilution = assumptions["annual_dilution_distribution"]
    volatility = float(assumptions["annual_volatility"])
    haircut = float(assumptions["source_quality_haircut"])
    terminal_prices: list[float] = []
    cagrs: list[float] = []
    drawdowns: list[float] = []
    final_value_indexes: list[float] = []
    sample_paths: list[dict[str, Any]] = []
    for idx in range(int(assumptions["simulation_count"])):
        annual_growth = triangular(rng, float(growth["low"]), float(growth["base"]), float(growth["high"]))
        terminal_margin = triangular(rng, float(margin["low"]), float(margin["base"]), float(margin["high"]))
        base_margin = max(float(margin["base"]), 0.0001)
        terminal_multiple = triangular(rng, float(multiple["low"]), float(multiple["base"]), float(multiple["high"]))
        annual_dilution = triangular(rng, float(dilution["low"]), float(dilution["base"]), float(dilution["high"]))
        fundamental_return = ((1 + annual_growth) ** years) * (terminal_margin / base_margin) * (terminal_multiple / starting_multiple)
        dilution_factor = max((1 - annual_dilution) ** years, 0.01)
        terminal_price = max(start_price * fundamental_return * dilution_factor * haircut, 0.01)
        cagr = (terminal_price / start_price) ** (1 / years) - 1
        path = [start_price]
        running_peak = start_price
        max_drawdown = 0.0
        for _year in range(years):
            yearly_return = rng.gauss(cagr, volatility)
            next_value = max(path[-1] * (1 + yearly_return), 0.01)
            path.append(next_value)
            running_peak = max(running_peak, next_value)
            if running_peak > 0:
                max_drawdown = min(max_drawdown, next_value / running_peak - 1)
        terminal_prices.append(terminal_price)
        cagrs.append(cagr)
        drawdowns.append(max_drawdown)
        final_value_indexes.append(terminal_price / start_price)
        if idx < 20:
            sample_paths.append(
                {
                    "path_id": idx + 1,
                    "annual_growth": round(annual_growth, 4),
                    "terminal_margin": round(terminal_margin, 4),
                    "terminal_multiple": round(terminal_multiple, 2),
                    "annual_dilution": round(annual_dilution, 4),
                    "terminal_price": round(terminal_price, 2),
                    "cagr": round(cagr, 4),
                    "max_drawdown": round(max_drawdown, 4),
                    "path": [round(item, 2) for item in path],
                }
            )
    probability_summary = {
        "negative_cagr_probability": round(sum(1 for item in cagrs if item < 0) / len(cagrs), 4),
        "permanent_loss_30pct_probability": round(sum(1 for item in final_value_indexes if item < 0.70) / len(final_value_indexes), 4),
        "double_or_better_probability": round(sum(1 for item in final_value_indexes if item >= 2.0) / len(final_value_indexes), 4),
        "drawdown_30pct_probability": round(sum(1 for item in drawdowns if item <= -0.30) / len(drawdowns), 4),
    }
    percentile_summary = {
        "terminal_price": pct_summary(terminal_prices),
        "cagr": pct_summary(cagrs),
        "max_drawdown": pct_summary(drawdowns),
        "final_value_index": pct_summary(final_value_indexes),
    }
    outputs = {
        "mean_terminal_price": round(statistics.fmean(terminal_prices), 4),
        "median_terminal_price": round(percentile(terminal_prices, 0.50) or 0, 4),
        "mean_cagr": round(statistics.fmean(cagrs), 4),
        "median_cagr": round(percentile(cagrs, 0.50) or 0, 4),
        "mean_max_drawdown": round(statistics.fmean(drawdowns), 4),
        "sample_paths": sample_paths,
    }
    return {
        "outputs": outputs,
        "percentile_summary": percentile_summary,
        "probability_summary": probability_summary,
    }


def run_status(warnings: list[str], context: dict[str, Any]) -> str:
    if warnings:
        return "needs_review"
    checklist_scores = [to_float(row.get("score")) for row in context["checklists"] if to_float(row.get("score")) is not None]
    if len(checklist_scores) < 6:
        return "needs_review"
    return "complete"


def build_note(context: dict[str, Any], assumptions: dict[str, Any], result: dict[str, Any], warnings: list[str], actor: str) -> Path:
    thesis = context["thesis"]
    symbol = clean(thesis.get("symbol")).upper()
    generated_at = datetime.now(timezone.utc)
    NOTE_DIR.mkdir(parents=True, exist_ok=True)
    note_path = NOTE_DIR / f"{generated_at.strftime('%Y%m%dT%H%M%SZ')}-{safe_slug(symbol)}-monte-carlo.md"
    probs = result["probability_summary"]
    cagr = result["percentile_summary"]["cagr"]
    terminal = result["percentile_summary"]["terminal_price"]
    lines = [
        f"# Long-Term Monte Carlo - {symbol}",
        "",
        f"Generated: {generated_at.isoformat()}",
        f"Generated by: {actor}",
        f"Thesis id: `{thesis.get('id')}`",
        f"Company: {clean(thesis.get('company_name'))}",
        f"Exchange: `{clean(thesis.get('exchange'))}`",
        "",
        "## Decision Guardrail",
        "",
        "This is a simulation and risk-distribution artifact only. It does not approve buy, add, trim, sell, hedge, or live execution.",
        "",
        "## Setup",
        "",
        f"- Method: `{assumptions['method']}`",
        f"- Start price: `{assumptions['start_price']}`",
        f"- Starting multiple: `{assumptions['starting_multiple']}` on `{assumptions['starting_metric']}`",
        f"- Horizon: `{assumptions['horizon_years']}` years",
        f"- Simulations: `{assumptions['simulation_count']}`",
        f"- Seed: `{assumptions['seed']}`",
        f"- Source quality haircut: `{assumptions['source_quality_haircut']}`",
        "",
        "## Distributions",
        "",
        f"- Revenue growth: `{assumptions['revenue_growth_distribution']}`",
        f"- Terminal PAT margin: `{assumptions['terminal_pat_margin_distribution']}`",
        f"- Terminal multiple: `{assumptions['terminal_multiple_distribution']}`",
        f"- Annual dilution: `{assumptions['annual_dilution_distribution']}`",
        f"- Annual volatility: `{assumptions['annual_volatility']}`",
        "",
        "## Results",
        "",
        f"- Median terminal price: `{terminal.get('p50')}`",
        f"- Downside p10 terminal price: `{terminal.get('p10')}`",
        f"- Upside p90 terminal price: `{terminal.get('p90')}`",
        f"- Median CAGR: `{cagr.get('p50')}`",
        f"- Downside p10 CAGR: `{cagr.get('p10')}`",
        f"- Upside p90 CAGR: `{cagr.get('p90')}`",
        f"- Negative CAGR probability: `{probs['negative_cagr_probability']}`",
        f"- Permanent loss over 30 percent probability: `{probs['permanent_loss_30pct_probability']}`",
        f"- Double-or-better probability: `{probs['double_or_better_probability']}`",
        f"- 30 percent drawdown probability: `{probs['drawdown_30pct_probability']}`",
        "",
        "## Warnings",
        "",
    ]
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- No engine warnings.")
    lines.extend(
        [
            "",
            "## Evidence",
            "",
            f"- Source extractions: `{len(context['source_extractions'])}`",
            f"- Quote rows: `{len(context['quotes'])}`",
            f"- Position rows: `{len(context['positions'])}`",
            f"- Checklist rows: `{len(context['checklists'])}`",
            "",
            "## Next Review",
            "",
            "- Valuation Agent: replace provisional starting multiple with sourced current market-cap/share-count multiple.",
            "- Financial Statement Analyst: normalize PAT/FCF before committee use.",
            "- Risk Agent: compare drawdown and loss probabilities with book/client risk limits.",
            "- Charlie: use this as one input in committee, not as a standalone decision.",
        ]
    )
    note_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return note_path


def insert_obsidian_note(note_path: Path, title: str, summary: str) -> None:
    rel_path = str(note_path.relative_to(VAULT_ROOT))
    run_psql_json(
        f"""
        WITH upserted AS (
            INSERT INTO knowledge.obsidian_notes (
                vault_path, note_path, title, note_type, tags, frontmatter,
                content_hash, body_summary, last_modified_at, indexed_at
            )
            VALUES (
                {sql_literal(str(VAULT_ROOT))},
                {sql_literal(rel_path)},
                {sql_literal(title)},
                'long_term_monte_carlo',
                ARRAY['ai-os','long-term','monte-carlo']::text[],
                {sql_jsonb({'source': 'run_long_term_monte_carlo.py'})},
                md5({sql_literal(note_path.read_text(encoding='utf-8'))}),
                {sql_literal(summary)},
                now(),
                now()
            )
            ON CONFLICT (note_path) DO UPDATE SET
                title = EXCLUDED.title,
                note_type = EXCLUDED.note_type,
                tags = EXCLUDED.tags,
                frontmatter = EXCLUDED.frontmatter,
                content_hash = EXCLUDED.content_hash,
                body_summary = EXCLUDED.body_summary,
                last_modified_at = EXCLUDED.last_modified_at,
                indexed_at = now()
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
        """
    )


def persist_run(context: dict[str, Any], assumptions: dict[str, Any], result: dict[str, Any], warnings: list[str], note_path: Path, actor: str) -> dict[str, Any]:
    thesis = context["thesis"]
    mc_model = valuation_row(context, "long_term_monte_carlo")
    status = run_status(warnings, context)
    rel_path = str(note_path.relative_to(VAULT_ROOT))
    run_key = f"ltmc-{thesis['id']}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{assumptions['seed']}"
    input_snapshot = {
        "financial_snapshot": financial_snapshot(context),
        "quote_count": len(context["quotes"]),
        "source_extraction_count": len(context["source_extractions"]),
        "position_count": len(context["positions"]),
        "checklists": context["checklists"],
    }
    evidence = [
        {"view": "portfolio.v_long_term_thesis_control", "id": thesis.get("id")},
        {"view": "portfolio.v_long_term_valuation_models", "model_key": "long_term_monte_carlo", "id": mc_model.get("id")},
        {"view": "portfolio.v_long_term_source_document_extractions", "rows": len(context["source_extractions"])},
        {"view": "market.v_latest_price_quotes", "rows": len(context["quotes"])},
        {"view": "books.v_book_positions", "rows": len(context["positions"])},
        {"note_path": rel_path},
    ]
    rows = run_psql_json(
        f"""
        WITH inserted AS (
            INSERT INTO portfolio.long_term_monte_carlo_runs (
                run_key, holding_thesis_id, valuation_model_id, symbol, exchange,
                company_name, run_status, horizon_years, simulation_count, seed,
                start_price, starting_multiple, starting_metric, assumptions,
                input_snapshot, outputs, percentile_summary, probability_summary,
                warnings, evidence, note_path, created_by
            )
            VALUES (
                {sql_literal(run_key)},
                {int(thesis['id'])},
                {mc_model.get('id') if mc_model.get('id') is not None else 'NULL'},
                {sql_literal(clean(thesis.get('symbol')).upper())},
                {sql_literal(thesis.get('exchange'))},
                {sql_literal(thesis.get('company_name'))},
                {sql_literal(status)},
                {int(assumptions['horizon_years'])},
                {int(assumptions['simulation_count'])},
                {int(assumptions['seed'])},
                {float(assumptions['start_price'])},
                {float(assumptions['starting_multiple'])},
                {sql_literal(assumptions['starting_metric'])},
                {sql_jsonb(assumptions)},
                {sql_jsonb(input_snapshot)},
                {sql_jsonb(result['outputs'])},
                {sql_jsonb(result['percentile_summary'])},
                {sql_jsonb(result['probability_summary'])},
                {sql_jsonb(warnings)},
                {sql_jsonb(evidence)},
                {sql_literal(rel_path)},
                {sql_literal(actor)}
            )
            RETURNING *
        ),
        valuation_update AS (
            UPDATE portfolio.holding_valuation_models vm
            SET status = (SELECT run_status FROM inserted),
                assumptions = (SELECT assumptions FROM inserted),
                outputs = jsonb_build_object(
                    'method', 'fundamental_driver_monte_carlo_v1',
                    'latest_run_id', (SELECT id FROM inserted),
                    'percentile_summary', (SELECT percentile_summary FROM inserted),
                    'probability_summary', (SELECT probability_summary FROM inserted),
                    'outputs', (SELECT outputs FROM inserted),
                    'warnings', (SELECT warnings FROM inserted),
                    'capital_action_allowed', false,
                    'live_execution_allowed', false
                ),
                note_path = (SELECT note_path FROM inserted),
                owner_agent = {sql_literal(actor)},
                updated_at = now()
            WHERE vm.holding_thesis_id = {int(thesis['id'])}
              AND vm.model_key = 'long_term_monte_carlo'
            RETURNING vm.*
        ),
        thesis_update AS (
            UPDATE portfolio.holding_theses ht
            SET monte_carlo_payload = jsonb_build_object(
                    'latest_run_id', (SELECT id FROM inserted),
                    'run_status', (SELECT run_status FROM inserted),
                    'percentile_summary', (SELECT percentile_summary FROM inserted),
                    'probability_summary', (SELECT probability_summary FROM inserted),
                    'note_path', (SELECT note_path FROM inserted),
                    'updated_at', now()
                ),
                valuation_status = 'in_progress',
                updated_by = {sql_literal(actor)},
                updated_at = now()
            WHERE ht.id = {int(thesis['id'])}
            RETURNING ht.id
        ),
        research_update AS (
            INSERT INTO portfolio.holding_thesis_research_updates (
                holding_thesis_id, update_kind, model_key, status, assumptions,
                outputs, evidence, note_path, source_summary, created_by
            )
            SELECT
                holding_thesis_id,
                'monte_carlo_run',
                'long_term_monte_carlo',
                run_status,
                assumptions,
                jsonb_build_object(
                    'percentile_summary', percentile_summary,
                    'probability_summary', probability_summary,
                    'outputs', outputs,
                    'warnings', warnings
                ),
                evidence,
                note_path,
                jsonb_build_object('source', 'run_long_term_monte_carlo.py'),
                {sql_literal(actor)}
            FROM inserted
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text FROM inserted
        """
    )
    if not rows:
        raise RuntimeError("Monte Carlo run insert failed")
    insert_obsidian_note(
        note_path,
        f"Long-Term Monte Carlo - {clean(thesis.get('symbol')).upper()}",
        f"Long-term Monte Carlo run for {clean(thesis.get('symbol')).upper()}; status {status}; median CAGR {result['percentile_summary']['cagr'].get('p50')}.",
    )
    return rows[0]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a deterministic long-term Monte Carlo simulation.")
    parser.add_argument("--holding-thesis-id", type=int, required=True)
    parser.add_argument("--actor", default="Quant Risk Analyst")
    parser.add_argument("--horizon-years", type=int, default=5)
    parser.add_argument("--simulations", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--start-price", type=float)
    parser.add_argument("--starting-multiple", type=float)
    parser.add_argument("--starting-multiple-source")
    parser.add_argument("--revenue-growth-low", type=float)
    parser.add_argument("--revenue-growth-base", type=float)
    parser.add_argument("--revenue-growth-high", type=float)
    parser.add_argument("--margin-low", type=float)
    parser.add_argument("--margin-base", type=float)
    parser.add_argument("--margin-high", type=float)
    parser.add_argument("--terminal-multiple-low", type=float, default=12.0)
    parser.add_argument("--terminal-multiple-base", type=float, default=18.0)
    parser.add_argument("--terminal-multiple-high", type=float, default=28.0)
    parser.add_argument("--dilution-low", type=float, default=0.0)
    parser.add_argument("--dilution-base", type=float, default=0.0)
    parser.add_argument("--dilution-high", type=float, default=0.01)
    parser.add_argument("--annual-volatility", type=float, default=0.32)
    parser.add_argument("--source-quality-haircut", type=float, default=0.95)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.horizon_years < 1:
        raise ValueError("horizon-years must be at least 1")
    if args.simulations < 100:
        raise ValueError("simulations must be at least 100")
    context = fetch_context(args.holding_thesis_id)
    assumptions, warnings = build_assumptions(args, context)
    result = run_simulation(assumptions)
    note_path = build_note(context, assumptions, result, warnings, args.actor)
    row = persist_run(context, assumptions, result, warnings, note_path, args.actor)
    print(
        json.dumps(
            {
                "action": "long_term_monte_carlo",
                "run_id": row["id"],
                "run_key": row["run_key"],
                "holding_thesis_id": row["holding_thesis_id"],
                "symbol": row["symbol"],
                "run_status": row["run_status"],
                "note_path": row["note_path"],
                "median_cagr": result["percentile_summary"]["cagr"].get("p50"),
                "negative_cagr_probability": result["probability_summary"]["negative_cagr_probability"],
                "warnings": warnings,
            },
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
