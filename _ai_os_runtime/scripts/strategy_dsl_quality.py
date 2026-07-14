#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PARSER_VERSION = "strategy_dsl_parser_v1"
ALLOWED_TEMPLATES = {"momentum", "mean_reversion", "breakout", "low_volatility"}
EXPRESSION_RE = re.compile(r"^[A-Za-z0-9_.,:%+\-*/<>=!&|()\s]+$")
RUNTIME_ROOT = Path(__file__).resolve().parents[1]


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return f"{sql_literal(json.dumps(value, sort_keys=True, default=str))}::jsonb"


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


def normalize_timeframe(value: str | None) -> str:
    value = (value or "").lower().strip()
    if value in {"5m", "5min", "5 minute", "5 minutes"} or "5" in value or "intraday" in value:
        return "5m"
    if value in {"15m", "15min", "15 minute", "15 minutes"} or "15" in value:
        return "15m"
    if value in {"1h", "60m", "hour", "hourly"} or "hour" in value:
        return "1h"
    if value in {"1d", "d", "day", "daily"} or "day" in value or "daily" in value:
        return "1d"
    return "5m"


def infer_template(text: str, override: str | None = None) -> str:
    if override and override in ALLOWED_TEMPLATES:
        return override
    lowered = text.lower()
    if "mean" in lowered or "reversion" in lowered or "zscore" in lowered or "z-score" in lowered:
        return "mean_reversion"
    if "low_vol" in lowered or "low vol" in lowered or "volatility" in lowered:
        return "low_volatility"
    if "breakout" in lowered or "atr" in lowered or "range expansion" in lowered:
        return "breakout"
    return "momentum"


def parse_symbols(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        raw_items = value
    else:
        text = str(value).strip()
        raw_items = re.split(r"[,;]+", text) if re.search(r"[,;]", text) else [text]
    output: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        symbol = str(item).strip().upper()
        if not symbol or symbol in {"AND", "OR", "NSE", "BSE"}:
            continue
        if re.fullmatch(r"[A-Z0-9:._ -]{2,40}", symbol) and symbol not in seen:
            seen.add(symbol)
            output.append(symbol)
    return output


def fetch_candidate(candidate_id: int) -> dict[str, Any]:
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT candidate.id, coalesce(candidate.candidate_key, 'candidate_' || candidate.id::TEXT) AS candidate_key,
                   candidate.name, candidate.hypothesis, candidate.universe, candidate.timeframe,
                   candidate.entry_rules, candidate.exit_rules, candidate.risk_rules,
                   candidate.structured_spec, candidate.owner_agent,
                   coalesce(intake.symbols, ARRAY[]::TEXT[]) AS intake_symbols,
                   intake.intake_text
            FROM strategy.strategy_candidates candidate
            LEFT JOIN strategy.strategy_intakes intake ON intake.id = candidate.intake_id
            WHERE candidate.id = {int(candidate_id)}
            LIMIT 1
        ) rows
        """
    )
    if not rows:
        raise ValueError(f"strategy candidate {candidate_id} was not found")
    return rows[0]


def split_dsl_sections(dsl_text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    freeform: list[str] = []
    for raw_line in dsl_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z][A-Za-z0-9 _-]{1,40})\s*:\s*(.+)$", line)
        if match:
            key = re.sub(r"[^a-z0-9]+", "_", match.group(1).lower()).strip("_")
            sections[key] = match.group(2).strip()
        else:
            freeform.append(line)
    if freeform:
        sections["notes"] = " ".join(freeform)
    return sections


def validate_expression(label: str, value: str, errors: list[str]) -> list[str]:
    if not value:
        return []
    if not EXPRESSION_RE.fullmatch(value):
        errors.append(f"{label} contains unsupported characters")
    tokens = sorted(set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", value.lower())))
    unsupported = [
        token
        for token in tokens
        if token
        not in {
            "and",
            "or",
            "not",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "sma",
            "ema",
            "rsi",
            "atr",
            "vwap",
            "crosses_above",
            "crosses_below",
            "holding_days",
            "stop_loss_pct",
            "target_pct",
            "zscore",
        }
    ]
    if unsupported:
        errors.append(f"{label} has unsupported tokens: {', '.join(unsupported[:8])}")
    return tokens


def parse_strategy_dsl(candidate_id: int, dsl_text: str | None = None, *, created_by: str = "Strategy Intake Agent") -> dict[str, Any]:
    candidate = fetch_candidate(candidate_id)
    if not dsl_text:
        existing_rows = run_psql_json(
            f"""
            SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
            FROM (
                SELECT id, candidate_id, parser_version, parse_status, parse_errors,
                       symbols, timeframe, template, normalized_rules, updated_at
                FROM strategy.strategy_rule_specs
                WHERE candidate_id = {candidate_id}
                  AND parser_version = {sql_literal(PARSER_VERSION)}
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
            ) rows
            """
        )
        if existing_rows:
            return existing_rows[0]
    fallback_text = "\n".join(
        str(candidate.get(key) or "")
        for key in ["name", "hypothesis", "universe", "timeframe", "entry_rules", "exit_rules", "risk_rules", "structured_spec", "intake_text"]
    ).strip()
    source_text = (dsl_text or fallback_text).strip()
    sections = split_dsl_sections(source_text)
    errors: list[str] = []

    entry = sections.get("entry") or sections.get("entry_rules") or json.dumps(candidate.get("entry_rules") or {}, sort_keys=True)
    exit_rule = sections.get("exit") or sections.get("exit_rules") or json.dumps(candidate.get("exit_rules") or {}, sort_keys=True)
    risk = sections.get("risk") or sections.get("risk_rules") or json.dumps(candidate.get("risk_rules") or {}, sort_keys=True)
    symbols = parse_symbols(sections.get("symbols") or sections.get("symbol") or candidate.get("intake_symbols"))
    timeframe = normalize_timeframe(sections.get("timeframe") or candidate.get("timeframe"))
    template = infer_template(" ".join([source_text, entry, exit_rule]), sections.get("template"))

    entry_tokens = validate_expression("entry", entry, errors) if entry not in {"{}", "[]"} else []
    exit_tokens = validate_expression("exit", exit_rule, errors) if exit_rule not in {"{}", "[]"} else []
    validate_expression("risk", risk, errors) if risk not in {"{}", "[]"} else []
    if not source_text:
        errors.append("strategy DSL text is empty")
    if not entry_tokens and entry in {"{}", "[]"}:
        errors.append("entry rule is missing")
    if not exit_tokens and exit_rule in {"{}", "[]"}:
        errors.append("exit rule is missing")

    status = "passed" if not errors else "needs_review"
    parsed_spec = {
        "candidate_id": candidate_id,
        "candidate_key": candidate.get("candidate_key"),
        "strategy_name": candidate.get("name"),
        "sections": sections,
        "symbols": symbols,
        "timeframe": timeframe,
        "template": template,
    }
    normalized_rules = {
        "entry": {"expression": entry, "tokens": entry_tokens},
        "exit": {"expression": exit_rule, "tokens": exit_tokens},
        "risk": {"expression": risk},
        "engine_template": template,
        "paper_first": True,
        "arbitrary_code_allowed": False,
    }
    rows = run_psql_json(
        f"""
        WITH upserted AS (
            INSERT INTO strategy.strategy_rule_specs (
                candidate_id, spec_source, parser_version, dsl_text, parsed_spec,
                normalized_rules, parse_status, parse_errors, symbols, timeframe,
                template, created_by, updated_at
            )
            VALUES (
                {candidate_id}, 'candidate_or_user_dsl', {sql_literal(PARSER_VERSION)},
                {sql_literal(source_text)}, {sql_jsonb(parsed_spec)}, {sql_jsonb(normalized_rules)},
                {sql_literal(status)}, {sql_text_array(errors)}, {sql_text_array(symbols)},
                {sql_literal(timeframe)}, {sql_literal(template)}, {sql_literal(created_by)}, now()
            )
            ON CONFLICT (candidate_id, parser_version) DO UPDATE SET
                dsl_text = EXCLUDED.dsl_text,
                parsed_spec = EXCLUDED.parsed_spec,
                normalized_rules = EXCLUDED.normalized_rules,
                parse_status = EXCLUDED.parse_status,
                parse_errors = EXCLUDED.parse_errors,
                symbols = EXCLUDED.symbols,
                timeframe = EXCLUDED.timeframe,
                template = EXCLUDED.template,
                created_by = EXCLUDED.created_by,
                updated_at = now()
            RETURNING id, candidate_id, parser_version, parse_status, parse_errors,
                      symbols, timeframe, template, normalized_rules, updated_at
        )
        SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
        """
    )
    return rows[0] if rows else {}


def symbol_variants(symbols: list[str]) -> list[str]:
    variants: set[str] = set()
    for symbol in symbols:
        cleaned = symbol.strip().upper()
        if not cleaned:
            continue
        variants.add(cleaned)
        if ":" not in cleaned:
            variants.add(f"NSE:{cleaned}")
    return sorted(variants)


def run_data_quality_gate(
    candidate_id: int,
    symbols: list[str] | None = None,
    timeframe: str | None = None,
    *,
    min_rows_per_symbol: int = 50,
    min_total_rows: int = 500,
    created_by: str = "Backtest Engineer",
) -> dict[str, Any]:
    candidate = fetch_candidate(candidate_id)
    spec_rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT symbols, timeframe, template, parse_status, parse_errors
            FROM strategy.strategy_rule_specs
            WHERE candidate_id = {candidate_id}
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
        ) rows
        """
    )
    spec = spec_rows[0] if spec_rows else {}
    requested_symbols = symbols or parse_symbols(spec.get("symbols")) or parse_symbols(candidate.get("intake_symbols"))
    normalized_timeframe = normalize_timeframe(timeframe or spec.get("timeframe") or candidate.get("timeframe"))
    variants = symbol_variants(requested_symbols)
    symbol_filter = ""
    if variants:
        symbol_filter = f"AND upper(symbol.symbol) = ANY(ARRAY[{','.join(sql_literal(item) for item in variants)}]::TEXT[])"

    coverage_rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT CASE
                       WHEN position(':' IN upper(symbol.symbol)) > 0
                           THEN split_part(upper(symbol.symbol), ':', 2)
                       ELSE upper(symbol.symbol)
                   END AS symbol,
                   count(*)::BIGINT AS rows_seen,
                   min(ohlcv.ts) AS first_ts,
                   max(ohlcv.ts) AS last_ts
            FROM trading.ohlcv ohlcv
            JOIN trading.symbols symbol ON symbol.id = ohlcv.symbol_id
            WHERE ohlcv.timeframe = {sql_literal(normalized_timeframe)}
              AND ohlcv.close IS NOT NULL
              {symbol_filter}
            GROUP BY 1
            ORDER BY rows_seen DESC, 1
        ) rows
        """
    )
    matched_symbols = [str(row["symbol"]) for row in coverage_rows]
    matched_normalized = {symbol.split(":", 1)[-1].upper() for symbol in matched_symbols} | {symbol.upper() for symbol in matched_symbols}
    missing_symbols = [symbol for symbol in requested_symbols if symbol.upper().split(":", 1)[-1] not in matched_normalized] if requested_symbols else []
    row_counts = [int(row["rows_seen"]) for row in coverage_rows]
    total_rows = sum(row_counts)
    min_symbol_rows = min(row_counts) if row_counts else 0
    max_symbol_rows = max(row_counts) if row_counts else 0
    first_values = [str(row["first_ts"]) for row in coverage_rows if row.get("first_ts")]
    last_values = [str(row["last_ts"]) for row in coverage_rows if row.get("last_ts")]
    reasons: list[str] = []
    if not coverage_rows:
        reasons.append("No matching OHLCV rows found in trading.ohlcv")
    if requested_symbols and missing_symbols:
        reasons.append("Requested symbols missing from OHLCV: " + ", ".join(missing_symbols[:10]))
    if total_rows < min_total_rows:
        reasons.append(f"Total rows {total_rows} below minimum {min_total_rows}")
    if coverage_rows and min_symbol_rows < min_rows_per_symbol:
        reasons.append(f"Minimum per-symbol rows {min_symbol_rows} below minimum {min_rows_per_symbol}")
    if spec and spec.get("parse_status") not in {None, "passed"}:
        reasons.append("Strategy DSL parse status is " + str(spec.get("parse_status")))

    status = "passed" if not reasons else "failed"
    severity = "info" if status == "passed" else "high"
    gate_key = "dq_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f") + f"_{candidate_id}"
    payload = {
        "candidate_id": candidate_id,
        "candidate_key": candidate.get("candidate_key"),
        "coverage": coverage_rows,
        "min_rows_per_symbol": min_rows_per_symbol,
        "min_total_rows": min_total_rows,
        "seed_data_allowed": False,
        "source_table": "trading.ohlcv",
        "parser_version": PARSER_VERSION,
    }
    rows = run_psql_json(
        f"""
        WITH inserted AS (
            INSERT INTO strategy.backtest_data_quality_gates (
                candidate_id, gate_key, timeframe, requested_symbols, matched_symbols,
                missing_symbols, min_rows_per_symbol, min_total_rows, total_rows,
                min_symbol_rows, max_symbol_rows, first_ts, last_ts, status,
                severity, reasons, gate_payload, created_by
            )
            VALUES (
                {candidate_id}, {sql_literal(gate_key)}, {sql_literal(normalized_timeframe)},
                {sql_text_array(requested_symbols)}, {sql_text_array(matched_symbols)},
                {sql_text_array(missing_symbols)}, {int(min_rows_per_symbol)}, {int(min_total_rows)},
                {int(total_rows)}, {int(min_symbol_rows)}, {int(max_symbol_rows)},
                {sql_literal(min(first_values) if first_values else None)}::timestamptz,
                {sql_literal(max(last_values) if last_values else None)}::timestamptz,
                {sql_literal(status)}, {sql_literal(severity)}, {sql_text_array(reasons)},
                {sql_jsonb(payload)}, {sql_literal(created_by)}
            )
            RETURNING *
        )
        SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text FROM inserted
        """
    )
    return rows[0] if rows else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse strategy DSL and run OHLCV data-quality preflight gates.")
    parser.add_argument("--candidate-id", type=int, required=True)
    parser.add_argument("--dsl-text", default="")
    parser.add_argument("--symbols", default="")
    parser.add_argument("--timeframe", default="")
    parser.add_argument("--min-rows-per-symbol", type=int, default=50)
    parser.add_argument("--min-total-rows", type=int, default=500)
    parser.add_argument("--actor", default="Strategy Intake Agent")
    parser.add_argument("--parse", action="store_true")
    parser.add_argument("--gate", action="store_true")
    args = parser.parse_args()

    output: dict[str, Any] = {}
    if args.parse or not args.gate:
        output["parse"] = parse_strategy_dsl(args.candidate_id, args.dsl_text or None, created_by=args.actor)
    if args.gate:
        symbols = parse_symbols(args.symbols)
        output["gate"] = run_data_quality_gate(
            args.candidate_id,
            symbols=symbols,
            timeframe=args.timeframe or None,
            min_rows_per_symbol=args.min_rows_per_symbol,
            min_total_rows=args.min_total_rows,
            created_by=args.actor,
        )
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), flush=True)
        raise SystemExit(1)
