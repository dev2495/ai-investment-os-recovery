#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import statistics
from decimal import Decimal
from typing import Any

from collect_nse_bse_filings import run_psql_json, run_psql_text, sql_jsonb, sql_literal


CALCULATION_VERSION = "sector-fundamentals-v1"
SOURCE_SYSTEM_NAME = "Official company investor relations reports"
FACT_METRICS = {
    "revenue_from_operations": "reported_revenue",
    "profit_after_tax": "reported_profit_after_tax",
    "basic_eps": "reported_basic_eps",
    "total_assets": "reported_total_assets",
    "total_equity": "reported_total_equity",
    "operating_cash_flow": "reported_operating_cash_flow",
    "trade_receivables": "reported_trade_receivables",
}
MONETARY_FACTS = set(FACT_METRICS) - {"basic_eps"}
UNIT_MULTIPLIERS = {
    "INR million": Decimal("1"),
    "INR crore": Decimal("10"),
    "INR lakh": Decimal("0.1"),
}


def fingerprint(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def decimal_value(value: Any) -> Decimal:
    return Decimal(str(value))


def normalize_fact(row: dict[str, Any]) -> dict[str, Any]:
    fact_key = str(row["fact_key"])
    if fact_key not in FACT_METRICS:
        raise ValueError(f"unsupported fact_key: {fact_key}")
    value = decimal_value(row["value_numeric"])
    original_unit = str(row.get("unit") or "")
    if fact_key in MONETARY_FACTS:
        if str(row.get("currency") or "").upper() != "INR":
            raise ValueError(f"{fact_key} must be INR-denominated")
        multiplier = UNIT_MULTIPLIERS.get(original_unit)
        if multiplier is None:
            raise ValueError(f"{fact_key} has unresolved source unit: {original_unit or 'missing'}")
        normalized_value = value * multiplier
        normalized_unit = "INR million"
    else:
        if original_unit != "INR/share":
            raise ValueError(f"basic_eps must use INR/share, received {original_unit or 'missing'}")
        normalized_value = value
        normalized_unit = "INR/share"
    lineage = {
        "evidence_id": int(row["evidence_id"]),
        "source_url": str(row["source_url"]),
        "source_locator": row.get("source_locator") or {},
        "verification_status": str(row.get("verification_status") or "unverified"),
        "fact_key": fact_key,
        "fiscal_year": int(row["fiscal_year"]),
        "period_end": str(row["period_end"]),
        "available_at": str(row["available_at"]),
        "original_value": str(value),
        "original_unit": original_unit,
        "normalized_value": str(normalized_value),
        "normalized_unit": normalized_unit,
    }
    return {
        **row,
        "metric_key": FACT_METRICS[fact_key],
        "normalized_value": normalized_value,
        "normalized_unit": normalized_unit,
        "input_fingerprint": fingerprint(lineage),
        "lineage": lineage,
    }


def latest_prices(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    prices: dict[int, dict[str, Any]] = {}
    for row in rows:
        if row.get("latest_close") is None or row.get("price_ts") is None:
            continue
        prices[int(row["symbol_id"])] = {
            "close": decimal_value(row["latest_close"]),
            "ts": str(row["price_ts"]),
            "source_system_id": int(row["price_source_system_id"]),
        }
    return prices


def build_observations(
    facts: list[dict[str, Any]],
    price_rows: list[dict[str, Any]],
    official_source_system_id: int,
    as_of_date: dt.date,
    rejections: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in facts:
        try:
            normalized.append(normalize_fact(row))
        except ValueError as exc:
            if rejections is not None:
                rejections.append({
                    "symbol": row.get("primary_symbol"),
                    "fact_key": row.get("fact_key"),
                    "evidence_id": row.get("evidence_id"),
                    "reason": str(exc),
                })
    observations: list[dict[str, Any]] = []
    eps_by_symbol: dict[int, dict[str, Any]] = {}
    for row in normalized:
        symbol_id = int(row["symbol_id"])
        if row["metric_key"] == "reported_basic_eps":
            eps_by_symbol[symbol_id] = row
        observations.append({
            "metric_key": row["metric_key"],
            "symbol_id": symbol_id,
            "observed_at": str(row["available_at"]),
            "period_start": row.get("period_start"),
            "period_end": row.get("period_end"),
            "value": row["normalized_value"],
            "currency": "INR" if row["metric_key"] != "reported_basic_eps" else None,
            "source_system_id": official_source_system_id,
            "source_reference": str(row["source_url"]),
            "input_fingerprint": row["input_fingerprint"],
            "quality_status": "validated" if row.get("verification_status") == "verified" else "observed",
            "metadata": {
                **row["lineage"],
                "symbol": row["primary_symbol"],
                "exchange": row["primary_exchange"],
                "statement_scope": row.get("statement_scope"),
                "publisher": CALCULATION_VERSION,
                "broker_write_allowed": False,
            },
        })
    prices = latest_prices(price_rows)
    for symbol_id, eps in eps_by_symbol.items():
        price = prices.get(symbol_id)
        if not price or decimal_value(eps["normalized_value"]) <= 0 or price["close"] <= 0:
            continue
        pe = price["close"] / decimal_value(eps["normalized_value"])
        pe_lineage = {
            "as_of_date": as_of_date.isoformat(),
            "symbol_id": symbol_id,
            "eps_fingerprint": eps["input_fingerprint"],
            "eps_available_at": str(eps["available_at"]),
            "price": str(price["close"]),
            "price_ts": price["ts"],
            "price_source_system_id": price["source_system_id"],
        }
        observations.append({
            "metric_key": "price_to_earnings",
            "symbol_id": symbol_id,
            "observed_at": max(str(eps["available_at"]), price["ts"]),
            "period_start": as_of_date.isoformat(),
            "period_end": as_of_date.isoformat(),
            "value": pe,
            "currency": None,
            "source_system_id": official_source_system_id,
            "source_reference": f"{eps['source_url']} | market-source:{price['source_system_id']}",
            "input_fingerprint": fingerprint(pe_lineage),
            "quality_status": "observed",
            "metadata": {
                **pe_lineage,
                "metric": "price_to_earnings",
                "unit": "multiple",
                "point_in_time": True,
                "broker_write_allowed": False,
            },
        })
    return observations


def compute_aggregates(observations: list[dict[str, Any]], constituent_count: int) -> list[dict[str, Any]]:
    by_metric: dict[str, list[dict[str, Any]]] = {}
    for row in observations:
        by_metric.setdefault(str(row["metric_key"]), []).append(row)
    aggregates: list[dict[str, Any]] = []
    for metric_key in (
        "reported_revenue",
        "reported_profit_after_tax",
        "reported_total_assets",
        "reported_total_equity",
        "reported_operating_cash_flow",
        "reported_trade_receivables",
    ):
        rows = by_metric.get(metric_key, [])
        if rows:
            aggregates.append({
                "metric_key": metric_key,
                "value": sum((decimal_value(row["value"]) for row in rows), Decimal("0")),
                "covered_count": len({int(row["symbol_id"]) for row in rows}),
                "constituent_count": constituent_count,
                "method": "sum",
                "source_fingerprints": sorted(str(row["input_fingerprint"]) for row in rows),
            })
    pe_rows = [row for row in by_metric.get("price_to_earnings", []) if decimal_value(row["value"]) > 0]
    if pe_rows:
        aggregates.append({
            "metric_key": "price_to_earnings",
            "value": Decimal(str(statistics.median([float(row["value"]) for row in pe_rows]))),
            "covered_count": len({int(row["symbol_id"]) for row in pe_rows}),
            "constituent_count": constituent_count,
            "method": "median",
            "source_fingerprints": sorted(str(row["input_fingerprint"]) for row in pe_rows),
        })
    revenue = by_metric.get("reported_revenue", [])
    profit = by_metric.get("reported_profit_after_tax", [])
    revenue_by_symbol = {int(row["symbol_id"]): decimal_value(row["value"]) for row in revenue}
    profit_by_symbol = {int(row["symbol_id"]): decimal_value(row["value"]) for row in profit}
    common = sorted(set(revenue_by_symbol) & set(profit_by_symbol))
    total_revenue = sum((revenue_by_symbol[symbol] for symbol in common), Decimal("0"))
    total_profit = sum((profit_by_symbol[symbol] for symbol in common), Decimal("0"))
    if common and total_revenue != 0:
        aggregates.append({
            "metric_key": "net_profit_margin",
            "value": Decimal("100") * total_profit / total_revenue,
            "covered_count": len(common),
            "constituent_count": constituent_count,
            "method": "ratio_of_sums",
            "source_fingerprints": sorted(
                [row["input_fingerprint"] for row in revenue if int(row["symbol_id"]) in common]
                + [row["input_fingerprint"] for row in profit if int(row["symbol_id"]) in common]
            ),
        })
    equity = by_metric.get("reported_total_equity", [])
    equity_by_symbol = {int(row["symbol_id"]): decimal_value(row["value"]) for row in equity}
    roe_common = sorted(set(profit_by_symbol) & set(equity_by_symbol))
    total_equity = sum((equity_by_symbol[symbol] for symbol in roe_common), Decimal("0"))
    roe_profit = sum((profit_by_symbol[symbol] for symbol in roe_common), Decimal("0"))
    if roe_common and total_equity != 0:
        aggregates.append({
            "metric_key": "return_on_equity",
            "value": Decimal("100") * roe_profit / total_equity,
            "covered_count": len(roe_common),
            "constituent_count": constituent_count,
            "method": "ratio_of_sums_period_end_equity_snapshot",
            "source_fingerprints": sorted(
                [row["input_fingerprint"] for row in equity if int(row["symbol_id"]) in roe_common]
                + [row["input_fingerprint"] for row in profit if int(row["symbol_id"]) in roe_common]
            ),
        })
    for aggregate in aggregates:
        aggregate["input_fingerprint"] = fingerprint({
            "metric_key": aggregate["metric_key"],
            "method": aggregate["method"],
            "sources": aggregate["source_fingerprints"],
        })
    return aggregates


def load_inputs(taxonomy_key: str, as_of_date: dt.date) -> dict[str, Any]:
    nodes = run_psql_json(
        "SELECT coalesce(json_agg(row_to_json(x)),'[]'::json)::text FROM ("
        "SELECT id,taxonomy_key,node_name FROM sector_intelligence.taxonomy_nodes "
        f"WHERE taxonomy_key={sql_literal(taxonomy_key)} AND valid_from<={sql_literal(as_of_date)}::date "
        f"AND (valid_to IS NULL OR valid_to>={sql_literal(as_of_date)}::date)) x"
    )
    if len(nodes) != 1:
        raise ValueError("taxonomy_key must resolve to exactly one active node")
    node = nodes[0]
    rows = run_psql_json(
        "SELECT coalesce(json_agg(row_to_json(x)),'[]'::json)::text FROM ("
        "WITH members AS ("
        "SELECT membership.symbol_id,symbol.symbol,symbol.exchange "
        "FROM sector_intelligence.instrument_membership_history membership "
        "JOIN trading.symbols symbol ON symbol.id=membership.symbol_id "
        f"WHERE membership.taxonomy_node_id={int(node['id'])} "
        f"AND membership.valid_from<={sql_literal(as_of_date)}::date "
        f"AND (membership.valid_to IS NULL OR membership.valid_to>={sql_literal(as_of_date)}::date)"
        "), ranked AS ("
        "SELECT member.symbol_id,fact.*,row_number() OVER ("
        "PARTITION BY member.symbol_id,fact.fact_key "
        "ORDER BY fact.period_end DESC NULLS LAST,fact.available_at DESC,fact.evidence_id DESC) AS rank "
        "FROM members member JOIN research.v_company_statement_facts_current fact "
        "ON upper(fact.primary_symbol)=upper(member.symbol) AND upper(fact.primary_exchange)=upper(member.exchange) "
        f"WHERE fact.fact_key IN ({','.join(sql_literal(key) for key in FACT_METRICS)}) "
        f"AND fact.available_at::date<={sql_literal(as_of_date)}::date "
        "AND fact.statement_scope='consolidated' AND fact.value_numeric IS NOT NULL"
        ") SELECT * FROM ranked WHERE rank=1 ORDER BY symbol_id,fact_key) x"
    )
    price_rows = run_psql_json(
        "SELECT coalesce(json_agg(row_to_json(x)),'[]'::json)::text FROM ("
        "WITH members AS ("
        "SELECT membership.symbol_id FROM sector_intelligence.instrument_membership_history membership "
        f"WHERE membership.taxonomy_node_id={int(node['id'])} "
        f"AND membership.valid_from<={sql_literal(as_of_date)}::date "
        f"AND (membership.valid_to IS NULL OR membership.valid_to>={sql_literal(as_of_date)}::date)"
        ") SELECT member.symbol_id,price.close AS latest_close,price.ts AS price_ts,"
        "price.source_system_id AS price_source_system_id FROM members member "
        "LEFT JOIN LATERAL (SELECT close,ts,source_system_id FROM trading.ohlcv "
        "WHERE symbol_id=member.symbol_id AND timeframe='1d' "
        f"AND ts::date<={sql_literal(as_of_date)}::date AND close>0 AND source_system_id IS NOT NULL "
        "ORDER BY ts DESC LIMIT 1) price ON true ORDER BY member.symbol_id) x"
    )
    source_rows = run_psql_json(
        "SELECT coalesce(json_agg(row_to_json(x)),'[]'::json)::text FROM ("
        f"SELECT id FROM core.source_systems WHERE name={sql_literal(SOURCE_SYSTEM_NAME)}) x"
    )
    if len(source_rows) != 1:
        raise ValueError("official company IR source system is not registered; apply migration 205")
    member_count_rows = run_psql_json(
        "SELECT coalesce(json_agg(row_to_json(x)),'[]'::json)::text FROM ("
        "SELECT count(*)::int AS constituent_count FROM sector_intelligence.instrument_membership_history "
        f"WHERE taxonomy_node_id={int(node['id'])} AND valid_from<={sql_literal(as_of_date)}::date "
        f"AND (valid_to IS NULL OR valid_to>={sql_literal(as_of_date)}::date)) x"
    )
    return {
        "node": node,
        "facts": rows,
        "prices": price_rows,
        "official_source_system_id": int(source_rows[0]["id"]),
        "constituent_count": int(member_count_rows[0]["constituent_count"]),
    }


def persist(
    node_id: int,
    as_of_date: dt.date,
    observations: list[dict[str, Any]],
    aggregates: list[dict[str, Any]],
    actor: str,
) -> dict[str, Any]:
    if not observations:
        raise ValueError("no source-backed observations are available to persist")
    values = []
    for row in observations:
        values.append(
            "("
            f"(SELECT id FROM sector_intelligence.metric_definitions WHERE metric_key={sql_literal(row['metric_key'])}),"
            f"NULL,{int(row['symbol_id'])},{sql_literal(row['observed_at'])}::timestamptz,"
            f"{sql_literal(row.get('period_start'))}::date,{sql_literal(row.get('period_end'))}::date,"
            f"{row['value']},{sql_literal(row.get('currency'))},{int(row['source_system_id'])},"
            f"{sql_literal(row['source_reference'])},{sql_literal(CALCULATION_VERSION)},"
            f"{sql_literal(row['input_fingerprint'])},{sql_literal(row['quality_status'])},{sql_jsonb(row['metadata'])}"
            ")"
        )
    run_psql_text(
        "INSERT INTO sector_intelligence.metric_observations ("
        "metric_definition_id,taxonomy_node_id,symbol_id,observed_at,period_start,period_end,"
        "value_numeric,currency,source_system_id,source_reference,calculation_version,"
        "input_fingerprint,quality_status,metadata) VALUES "
        + ",".join(values)
        + " ON CONFLICT DO NOTHING;"
    )
    aggregate_rows = []
    for row in aggregates:
        fingerprint_list = ",".join(sql_literal(item) for item in row["source_fingerprints"])
        ids = run_psql_json(
            "SELECT coalesce(json_agg(row_to_json(x)),'[]'::json)::text FROM ("
            "SELECT id FROM sector_intelligence.metric_observations "
            f"WHERE input_fingerprint IN ({fingerprint_list}) ORDER BY id) x"
        ) if fingerprint_list else []
        observation_ids = "ARRAY[" + ",".join(str(int(item["id"])) for item in ids) + "]::bigint[]"
        aggregate_rows.append(
            "("
            f"{node_id},(SELECT id FROM sector_intelligence.metric_definitions WHERE metric_key={sql_literal(row['metric_key'])}),"
            f"{sql_literal(as_of_date)}::date,'FY_LATEST',{row['value']},{row['constituent_count']},"
            f"{row['covered_count']},'equal',{sql_literal(CALCULATION_VERSION)},"
            f"{sql_literal(row['input_fingerprint'])},{observation_ids},'calculated'"
            ")"
        )
    if aggregate_rows:
        run_psql_text(
            "INSERT INTO sector_intelligence.sector_aggregates ("
            "taxonomy_node_id,metric_definition_id,as_of_date,horizon,value,constituent_count,"
            "covered_count,weighting_method,calculation_version,input_fingerprint,"
            "source_observation_ids,quality_status) VALUES "
            + ",".join(aggregate_rows)
            + " ON CONFLICT (taxonomy_node_id,metric_definition_id,as_of_date,horizon,weighting_method,calculation_version) "
            "DO UPDATE SET value=EXCLUDED.value,constituent_count=EXCLUDED.constituent_count,"
            "covered_count=EXCLUDED.covered_count,input_fingerprint=EXCLUDED.input_fingerprint,"
            "source_observation_ids=EXCLUDED.source_observation_ids,quality_status=EXCLUDED.quality_status,"
            "calculated_at=now();"
        )
    return {
        "observations": len(observations),
        "aggregates": len(aggregates),
        "actor": actor,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish source-backed company facts into Sector Intelligence.")
    parser.add_argument("--taxonomy-key", required=True)
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--actor", default="Sector Fundamental Analyst")
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()
    as_of_date = dt.date.fromisoformat(args.as_of_date)
    inputs = load_inputs(args.taxonomy_key.strip(), as_of_date)
    rejected_facts: list[dict[str, Any]] = []
    observations = build_observations(
        inputs["facts"],
        inputs["prices"],
        inputs["official_source_system_id"],
        as_of_date,
        rejected_facts,
    )
    aggregates = compute_aggregates(observations, inputs["constituent_count"])
    database = (
        persist(int(inputs["node"]["id"]), as_of_date, observations, aggregates, args.actor)
        if args.persist
        else {"observations": 0, "aggregates": 0, "dry_run": True}
    )
    core_metrics_by_symbol: dict[int, set[str]] = {}
    for row in observations:
        if row["metric_key"] in {"reported_revenue", "reported_profit_after_tax", "reported_basic_eps"}:
            core_metrics_by_symbol.setdefault(int(row["symbol_id"]), set()).add(str(row["metric_key"]))
    required_core_metrics = {"reported_revenue", "reported_profit_after_tax", "reported_basic_eps"}
    core_symbols = {
        symbol_id
        for symbol_id, metric_keys in core_metrics_by_symbol.items()
        if metric_keys == required_core_metrics
    }
    output = {
        "ok": True,
        "status": "completed" if args.persist else "dry_run",
        "taxonomy_node": inputs["node"],
        "as_of_date": as_of_date.isoformat(),
        "constituent_count": inputs["constituent_count"],
        "source_fact_count": len(inputs["facts"]),
        "published_observation_count": len(observations),
        "rejected_fact_count": len(rejected_facts),
        "rejected_facts": rejected_facts,
        "aggregate_count": len(aggregates),
        "core_symbol_count": len(core_symbols),
        "valuation_symbol_count": sum(1 for row in observations if row["metric_key"] == "price_to_earnings"),
        "database": database,
        "calculation_version": CALCULATION_VERSION,
        "historical_valuation_band_created": False,
        "historical_valuation_band_reason": "No backdating: valuation history begins only after audited facts become available.",
        "broker_write_allowed": False,
        "capital_action_allowed": False,
    }
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
