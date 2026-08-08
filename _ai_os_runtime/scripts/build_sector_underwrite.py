#!/usr/bin/env python3
"""Build a source-backed sector underwrite without granting capital authority."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import subprocess
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from collect_nse_bse_filings import run_psql_json, run_psql_text, sql_jsonb, sql_literal
from runtime_storage import artifact_reference, artifact_root


SOURCE_NAME = "NSE Indices historical valuation data"
HISTORICAL_PAGE = "https://www.niftyindices.com/reports/historical-data"
ENDPOINT = "https://www.niftyindices.com/BackPage/getpepbHistoricaldataDBtoString"
CALCULATION_VERSION = "sector-underwrite-v1"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
)
DOSSIER_SECTION_KEYS = (
    "executive_conclusion", "industry_structure", "business_models",
    "constituent_fundamentals", "valuation", "market_structure",
    "ownership_and_flows", "macro_sensitivities", "portfolio_fit",
    "opportunity_cost", "bull_case", "base_case", "bear_case",
    "monitoring", "evidence_gaps",
)


def fingerprint(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def decimal_or_none(value: Any, *, allow_zero: bool = False) -> Decimal | None:
    try:
        number = Decimal(str(value)) if value not in (None, "") else None
    except (InvalidOperation, ValueError):
        return None
    if number is None or not number.is_finite():
        return None
    if number < 0 or (number == 0 and not allow_zero):
        return None
    return number


def ten_year_start(as_of_date: dt.date) -> dt.date:
    try:
        return as_of_date.replace(year=as_of_date.year - 10)
    except ValueError:
        return as_of_date.replace(year=as_of_date.year - 10, day=28)


def annual_windows(start: dt.date, end: dt.date) -> list[tuple[dt.date, dt.date]]:
    windows: list[tuple[dt.date, dt.date]] = []
    cursor = start
    while cursor <= end:
        window_end = min(end, cursor + dt.timedelta(days=364))
        windows.append((cursor, window_end))
        cursor = window_end + dt.timedelta(days=1)
    return windows


def write_artifact(path: Path, payload: Any) -> tuple[str, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True, default=str).encode()
    path.write_bytes(encoded)
    return artifact_reference(path), hashlib.sha256(encoded).hexdigest()


def fetch_history(index_name: str, start: dt.date, end: dt.date, artifact_dir: Path) -> list[dict[str, Any]]:
    observations: dict[dt.date, dict[str, Any]] = {}
    for sequence, (window_start, window_end) in enumerate(annual_windows(start, end), 1):
        request = {
            "name": index_name.upper(),
            "startDate": window_start.strftime("%m/%d/%Y"),
            "endDate": window_end.strftime("%m/%d/%Y"),
            "indexName": index_name,
        }
        body = json.dumps({"cinfo": json.dumps(request, separators=(",", ":"))})
        command = [
            "curl", "--http1.1", "--silent", "--show-error", "--fail-with-body",
            "--max-time", "60", "--retry", "2", "--retry-delay", "1",
            "--user-agent", USER_AGENT,
            "--header", "Origin: https://www.niftyindices.com",
            "--header", f"Referer: {HISTORICAL_PAGE}",
            "--header", "Content-Type: application/json; charset=UTF-8",
            "--data", body, ENDPOINT,
        ]
        completed = subprocess.run(command, capture_output=True, check=False, timeout=75)
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).decode(errors="replace")[:1200]
            raise RuntimeError(f"NSE Indices valuation request failed: {detail}")
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("NSE Indices valuation response was not JSON") from exc
        if not isinstance(payload, list):
            raise RuntimeError("NSE Indices valuation response was not a row array")
        artifact_path, artifact_sha = write_artifact(
            artifact_dir / f"{sequence:02d}-{window_start}-{window_end}.json", payload
        )
        for row in normalize_history(payload):
            row["source_artifact_path"] = artifact_path
            row["source_artifact_sha256"] = artifact_sha
            observations[row["valuation_date"]] = row
    return [observations[key] for key in sorted(observations)]


def normalize_history(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    output: dict[dt.date, dict[str, Any]] = {}
    for source_row in payload:
        if not isinstance(source_row, dict):
            continue
        try:
            valuation_date = dt.datetime.strptime(str(source_row.get("DATE") or ""), "%d %b %Y").date()
        except ValueError:
            continue
        pe = decimal_or_none(source_row.get("pe"))
        pb = decimal_or_none(source_row.get("pb"))
        dividend_yield = decimal_or_none(source_row.get("divYield"), allow_zero=True)
        if pe is None and pb is None and dividend_yield is None:
            continue
        normalized = {
            "valuation_date": valuation_date,
            "price_to_earnings": pe,
            "price_to_book": pb,
            "dividend_yield_percent": dividend_yield,
            "request_number": str(source_row.get("RequestNumber") or ""),
            "index_name": str(source_row.get("Index Name") or ""),
        }
        normalized["input_fingerprint"] = fingerprint(normalized)
        output[valuation_date] = normalized
    return [output[key] for key in sorted(output)]


def interpolated_percentile(values: list[Decimal], probability: Decimal) -> Decimal:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("percentile requires at least one value")
    if len(ordered) == 1:
        return ordered[0]
    position = probability * Decimal(len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    fraction = position - Decimal(lower)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def valuation_statistics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [row["price_to_earnings"] for row in rows if row.get("price_to_earnings") is not None]
    if not values:
        raise ValueError("no positive point-in-time P/E observations were returned")
    current = values[-1]
    less = sum(1 for value in values if value < current)
    equal = sum(1 for value in values if value == current)
    percentile_rank = (Decimal(less) + Decimal(equal) / 2) * Decimal(100) / Decimal(len(values))
    return {
        "current_value": current,
        "percentile_rank": percentile_rank,
        "minimum_value": min(values),
        "p10_value": interpolated_percentile(values, Decimal("0.10")),
        "p25_value": interpolated_percentile(values, Decimal("0.25")),
        "median_value": interpolated_percentile(values, Decimal("0.50")),
        "p75_value": interpolated_percentile(values, Decimal("0.75")),
        "p90_value": interpolated_percentile(values, Decimal("0.90")),
        "maximum_value": max(values),
        "observation_count": len(values),
        "input_fingerprint": fingerprint([
            {"date": row["valuation_date"], "pe": row.get("price_to_earnings"),
             "fingerprint": row["input_fingerprint"]}
            for row in rows if row.get("price_to_earnings") is not None
        ]),
    }


def resolve_node(taxonomy_key: str, as_of_date: dt.date) -> dict[str, Any]:
    rows = run_psql_json(f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text FROM (
            SELECT id,taxonomy_key,node_name
            FROM sector_intelligence.taxonomy_nodes
            WHERE taxonomy_key={sql_literal(taxonomy_key)}
              AND valid_from<={sql_literal(as_of_date.isoformat())}::date
              AND (valid_to IS NULL OR valid_to>={sql_literal(as_of_date.isoformat())}::date)
            ORDER BY id
        ) rows
    """)
    if len(rows) != 1:
        raise ValueError("taxonomy_key must resolve to exactly one active sector node")
    return rows[0]


def source_and_metric_ids() -> tuple[int, int]:
    rows = run_psql_json(f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text FROM (
            SELECT source.id AS source_system_id,definition.id AS metric_definition_id
            FROM core.source_systems source
            CROSS JOIN sector_intelligence.metric_definitions definition
            WHERE source.name={sql_literal(SOURCE_NAME)}
              AND definition.metric_key='price_to_earnings'
        ) rows
    """)
    if len(rows) != 1:
        raise RuntimeError("migration 208 and price_to_earnings metric must be installed")
    return int(rows[0]["source_system_id"]), int(rows[0]["metric_definition_id"])


def persist_valuation(
    node_id: int, source_system_id: int, metric_definition_id: int,
    as_of_date: dt.date, rows: list[dict[str, Any]], stats: dict[str, Any],
) -> None:
    values = []
    for row in rows:
        values.append("(" + ",".join([
            str(node_id), sql_literal(row["valuation_date"].isoformat()),
            sql_literal(str(row["price_to_earnings"])) if row["price_to_earnings"] is not None else "NULL",
            sql_literal(str(row["price_to_book"])) if row["price_to_book"] is not None else "NULL",
            sql_literal(str(row["dividend_yield_percent"])) if row["dividend_yield_percent"] is not None else "NULL",
            str(source_system_id), sql_literal(HISTORICAL_PAGE),
            sql_literal(row["source_artifact_path"]), sql_literal(row["source_artifact_sha256"]),
            sql_literal(row["request_number"]), sql_literal(row["input_fingerprint"]),
        ]) + ")")
    run_psql_text(f"""
        BEGIN;
        INSERT INTO sector_intelligence.index_valuation_history (
            taxonomy_node_id,valuation_date,price_to_earnings,price_to_book,
            dividend_yield_percent,source_system_id,source_reference,
            source_artifact_path,source_artifact_sha256,request_number,input_fingerprint
        ) VALUES {",".join(values)}
        ON CONFLICT (taxonomy_node_id,valuation_date,source_system_id) DO UPDATE SET
            price_to_earnings=EXCLUDED.price_to_earnings,
            price_to_book=EXCLUDED.price_to_book,
            dividend_yield_percent=EXCLUDED.dividend_yield_percent,
            source_reference=EXCLUDED.source_reference,
            source_artifact_path=EXCLUDED.source_artifact_path,
            source_artifact_sha256=EXCLUDED.source_artifact_sha256,
            request_number=EXCLUDED.request_number,
            input_fingerprint=EXCLUDED.input_fingerprint,
            quality_status='observed',ingested_at=now();
        INSERT INTO sector_intelligence.valuation_bands (
            taxonomy_node_id,metric_definition_id,as_of_date,lookback_years,
            current_value,percentile_rank,minimum_value,p10_value,p25_value,
            median_value,p75_value,p90_value,maximum_value,observation_count,
            calculation_version,input_fingerprint
        ) VALUES (
            {node_id},{metric_definition_id},{sql_literal(as_of_date.isoformat())}::date,10,
            {stats["current_value"]},{stats["percentile_rank"]},{stats["minimum_value"]},
            {stats["p10_value"]},{stats["p25_value"]},{stats["median_value"]},
            {stats["p75_value"]},{stats["p90_value"]},{stats["maximum_value"]},
            {stats["observation_count"]},{sql_literal(CALCULATION_VERSION)},
            {sql_literal(stats["input_fingerprint"])}
        )
        ON CONFLICT (
            taxonomy_node_id,metric_definition_id,as_of_date,lookback_years,calculation_version
        ) DO UPDATE SET
            current_value=EXCLUDED.current_value,percentile_rank=EXCLUDED.percentile_rank,
            minimum_value=EXCLUDED.minimum_value,p10_value=EXCLUDED.p10_value,
            p25_value=EXCLUDED.p25_value,median_value=EXCLUDED.median_value,
            p75_value=EXCLUDED.p75_value,p90_value=EXCLUDED.p90_value,
            maximum_value=EXCLUDED.maximum_value,observation_count=EXCLUDED.observation_count,
            input_fingerprint=EXCLUDED.input_fingerprint,calculated_at=now();
        COMMIT;
    """)


def collect_evidence(node_id: int, as_of_date: dt.date) -> dict[str, Any]:
    rows = run_psql_json(f"""
        WITH members AS (
            SELECT symbols.symbol
            FROM sector_intelligence.instrument_membership_history membership
            JOIN trading.symbols symbols ON symbols.id=membership.symbol_id
            WHERE membership.taxonomy_node_id={node_id}
              AND membership.valid_from<={sql_literal(as_of_date.isoformat())}::date
              AND (membership.valid_to IS NULL OR membership.valid_to>={sql_literal(as_of_date.isoformat())}::date)
        ), portfolio_rows AS (
            SELECT positions.symbol,positions.account_id,positions.market_value,positions.as_of
            FROM portfolio.v_latest_positions positions
            JOIN members ON upper(members.symbol)=upper(positions.symbol)
        ), all_portfolio AS (
            SELECT coalesce(sum(market_value),0) AS total_market_value,max(as_of) AS latest_as_of
            FROM portfolio.v_latest_positions
        ), fundamental AS (
            SELECT count(*) AS member_count,
                   count(*) FILTER (WHERE core_lineage_complete) AS lineage_complete_count,
                   count(*) FILTER (WHERE price_to_earnings IS NOT NULL) AS current_pe_count,
                   max(latest_fundamental_at) AS latest_fundamental_at
            FROM sector_intelligence.v_fundamental_constituent_coverage
            WHERE taxonomy_node_id={node_id}
        ), flows AS (
            SELECT count(*) AS observation_count,count(DISTINCT symbol_id) AS symbol_count,
                   max(observed_at) AS latest_at,coalesce(sum(net_value),0) AS net_value
            FROM sector_intelligence.flow_observations
            WHERE taxonomy_node_id={node_id} AND observed_at::date<={sql_literal(as_of_date.isoformat())}::date
        ), ownership AS (
            SELECT count(*) AS observation_count,count(DISTINCT symbol_id) AS symbol_count,
                   max(period_end) AS latest_period_end
            FROM sector_intelligence.ownership_observations
            WHERE taxonomy_node_id={node_id} AND period_end<={sql_literal(as_of_date.isoformat())}::date
        ), indices AS (
            SELECT count(*) AS definition_count,count(*) FILTER (WHERE status='active') AS active_count
            FROM sector_intelligence.custom_index_definitions
            WHERE taxonomy_node_id={node_id}
        )
        SELECT coalesce(json_agg(row_to_json(result)), '[]'::json)::text FROM (
            SELECT json_build_object(
                'fundamentals',(SELECT row_to_json(fundamental) FROM fundamental),
                'flows',(SELECT row_to_json(flows) FROM flows),
                'ownership',(SELECT row_to_json(ownership) FROM ownership),
                'indices',(SELECT row_to_json(indices) FROM indices),
                'portfolio',json_build_object(
                    'positions',coalesce((SELECT json_agg(row_to_json(portfolio_rows)) FROM portfolio_rows),'[]'::json),
                    'sector_market_value',coalesce((SELECT sum(market_value) FROM portfolio_rows),0),
                    'total_market_value',(SELECT total_market_value FROM all_portfolio),
                    'latest_portfolio_as_of',(SELECT latest_as_of FROM all_portfolio)
                )
            ) AS payload
        ) result
    """)
    if len(rows) != 1:
        raise RuntimeError("sector evidence query returned no result")
    payload = rows[0].get("payload")
    return payload if isinstance(payload, dict) else json.loads(payload)


def evidence_item(label: str, value: Any, source: str) -> dict[str, Any]:
    return {"label": label, "value": value, "source": source}


def build_dossier(
    node: dict[str, Any], as_of_date: dt.date, stats: dict[str, Any],
    evidence: dict[str, Any], valuation_artifacts: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], str]:
    fundamentals = evidence["fundamentals"]
    flows = evidence["flows"]
    ownership = evidence["ownership"]
    indices = evidence["indices"]
    portfolio = evidence["portfolio"]
    sector_value = Decimal(str(portfolio.get("sector_market_value") or 0))
    total_value = Decimal(str(portfolio.get("total_market_value") or 0))
    sector_weight = (sector_value * 100 / total_value) if total_value else Decimal(0)
    portfolio_positions = portfolio.get("positions") or []
    data_gaps = [
        {"gap": "sector_operating_kpi_history", "status": "missing_source_backed_history"},
        {"gap": "market_share_and_capacity_history", "status": "missing_source_backed_history"},
        {"gap": "cross_sector_opportunity_cost_comparator", "status": "not_yet_comparable"},
        {"gap": "portfolio_mark_freshness", "status": "review_required",
         "evidence": portfolio_positions},
        {"gap": "macro_and_raw_material_sensitivity", "status": "missing_validated_model"},
    ]
    common = {"as_of_date": as_of_date.isoformat(), "taxonomy_key": node["taxonomy_key"]}
    sections = {
        "executive_conclusion": {**common, "status": "monitoring",
            "conclusion": "The sector has source-backed constituents, fundamentals, valuation, ownership and flow evidence, but identified evidence gaps block an allocation recommendation.",
            "evidence": [evidence_item("current_pe", str(stats["current_value"]), HISTORICAL_PAGE),
                         evidence_item("pe_percentile", str(stats["percentile_rank"]), HISTORICAL_PAGE)]},
        "industry_structure": {**common, "status": "partial",
            "conclusion": "Point-in-time constituents are stored; value-chain and industry-structure evidence remains incomplete.",
            "evidence": [evidence_item("member_count", fundamentals["member_count"], "sector_intelligence.v_fundamental_constituent_coverage")]},
        "business_models": {**common, "status": "gap",
            "conclusion": "No sector-wide source-backed business-model and unit-economics dataset is yet available.",
            "evidence": []},
        "constituent_fundamentals": {**common, "status": "source_backed",
            "conclusion": "Constituent fundamental coverage is measured from stored source lineage.",
            "evidence": [evidence_item("lineage_complete", fundamentals["lineage_complete_count"], "sector_intelligence.v_fundamental_constituent_coverage"),
                         evidence_item("current_pe_coverage", fundamentals["current_pe_count"], "sector_intelligence.v_fundamental_constituent_coverage")]},
        "valuation": {**common, "status": "source_backed",
            "conclusion": "Official point-in-time Nifty Indices valuation history supports a ten-year P/E distribution.",
            "evidence": [evidence_item("observation_count", stats["observation_count"], HISTORICAL_PAGE),
                         evidence_item("median_pe", str(stats["median_value"]), HISTORICAL_PAGE),
                         evidence_item("current_percentile", str(stats["percentile_rank"]), HISTORICAL_PAGE)]},
        "market_structure": {**common, "status": "partial",
            "conclusion": "Custom index definitions exist, while market share and capacity evidence remains incomplete.",
            "evidence": [evidence_item("active_indices", indices["active_count"], "sector_intelligence.custom_index_definitions")]},
        "ownership_and_flows": {**common, "status": "source_backed",
            "conclusion": "Official constituent ownership filings and bulk/block deal flows are stored with artifacts.",
            "evidence": [evidence_item("ownership_rows", ownership["observation_count"], "NSE corporate shareholding filings"),
                         evidence_item("flow_rows", flows["observation_count"], "NSE bulk and block deal archives"),
                         evidence_item("net_observed_flow", flows["net_value"], "sector_intelligence.flow_observations")]},
        "macro_sensitivities": {**common, "status": "gap",
            "conclusion": "No validated macro or raw-material sensitivity model is available; no relationship is inferred.",
            "evidence": []},
        "portfolio_fit": {**common, "status": "evaluated",
            "conclusion": f"Stored positions map {sector_weight:.4f}% of total marked portfolio value to this sector; position freshness requires review.",
            "evidence": [evidence_item("sector_market_value", str(sector_value), "portfolio.v_latest_positions"),
                         evidence_item("total_market_value", str(total_value), "portfolio.v_latest_positions"),
                         evidence_item("positions", portfolio_positions, "portfolio.v_latest_positions")]},
        "opportunity_cost": {**common, "status": "incomplete_cross_sector_comparator",
            "conclusion": "No allocation recommendation is permitted until comparable point-in-time valuation and evidence coverage exist for alternative sectors.",
            "evidence": [evidence_item("current_pe_percentile", str(stats["percentile_rank"]), HISTORICAL_PAGE),
                         evidence_item("comparator_status", "not_yet_comparable", "sector_intelligence.valuation_bands")]},
        "bull_case": {**common, "status": "hypothesis_not_forecast",
            "conclusion": "Bull-case operating assumptions are not asserted until operating KPI and macro evidence is available.",
            "evidence": []},
        "base_case": {**common, "status": "monitoring",
            "conclusion": "Maintain evidence monitoring without a capital recommendation.",
            "evidence": [evidence_item("current_pe", str(stats["current_value"]), HISTORICAL_PAGE)]},
        "bear_case": {**common, "status": "risk_dissent",
            "conclusion": "Missing operating, market-share and macro evidence plus stale portfolio marks can invalidate apparent valuation comfort.",
            "evidence": data_gaps},
        "monitoring": {**common, "status": "active",
            "conclusion": "Track valuation percentile, fundamental lineage, ownership changes, observed flows and portfolio mark freshness.",
            "evidence": []},
        "evidence_gaps": {**common, "status": "open",
            "conclusion": "Open gaps are preserved as blockers rather than filled with model-generated claims.",
            "evidence": data_gaps},
    }
    assert tuple(sections) == DOSSIER_SECTION_KEYS
    evidence_references = [
        {"source": SOURCE_NAME, "url": HISTORICAL_PAGE,
         "artifacts": valuation_artifacts, "as_of": as_of_date.isoformat()},
        {"source": "NSE corporate shareholding filings", "reference": "sector_intelligence.ownership_observations"},
        {"source": "NSE bulk and block deal archives", "reference": "sector_intelligence.flow_observations"},
        {"source": "Portfolio warehouse", "reference": "portfolio.v_latest_positions"},
    ]
    monitoring = [
        {"indicator": "ten_year_pe_percentile", "value": str(stats["percentile_rank"]), "source": HISTORICAL_PAGE},
        {"indicator": "fundamental_lineage_coverage", "value": fundamentals["lineage_complete_count"], "source": "sector_intelligence.v_fundamental_constituent_coverage"},
        {"indicator": "latest_ownership_period", "value": ownership["latest_period_end"], "source": "sector_intelligence.ownership_observations"},
        {"indicator": "observed_flow_net_value", "value": flows["net_value"], "source": "sector_intelligence.flow_observations"},
        {"indicator": "portfolio_mark_freshness", "value": portfolio.get("latest_portfolio_as_of"), "source": "portfolio.v_latest_positions"},
    ]
    thesis = (
        f"{node['node_name']} has source-backed constituent fundamentals, official ten-year valuation, "
        f"ownership and observed block/bulk-deal flow evidence. Stored portfolio exposure is {sector_weight:.4f}%. "
        "Operating KPI, market-share, macro-sensitivity, cross-sector comparison and position-freshness gaps "
        "block any allocation recommendation; continue monitoring and evidence collection."
    )
    return sections, evidence_references, monitoring, thesis


def build_committee(
    sections: dict[str, Any], stats: dict[str, Any], evidence: dict[str, Any],
    evidence_references: list[dict[str, Any]], data_gaps: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], str, list[dict[str, Any]]]:
    portfolio_fit = sections["portfolio_fit"]
    opportunity_cost = sections["opportunity_cost"]
    positions = [
        {"agent": "Sector Fundamental Analyst", "position": "monitor",
         "confidence": "medium", "evidence_refs": [1], "unresolved": ["operating KPI history", "market share"]},
        {"agent": "Sector Valuation Analyst", "position": "valuation history validated; no capital conclusion",
         "confidence": "high", "evidence_refs": [0], "unresolved": ["cross-sector comparator"]},
        {"agent": "Sector Flow And Ownership Analyst", "position": "monitor official ownership and observed deal flows",
         "confidence": "medium", "evidence_refs": [1, 2], "unresolved": ["market-wide institutional flow attribution"]},
        {"agent": "Portfolio Fit Agent", "position": "exposure measured; refresh stale marks before a decision",
         "confidence": "high", "evidence_refs": [3], "unresolved": ["position mark freshness"]},
        {"agent": "Risk Agent", "position": "oppose allocation recommendation until evidence gaps close",
         "confidence": "high", "evidence_refs": [0, 1, 2, 3], "unresolved": ["macro sensitivity", "evidence completeness"]},
        {"agent": "Bear Case Agent", "position": "dissent: valuation history alone is not a complete underwrite",
         "confidence": "high", "evidence_refs": [0], "unresolved": ["operating downside scenario"]},
    ]
    dissent = (
        "Valuation and source-lineage evidence support continued monitoring, but Risk and Bear Case dissent "
        "from any allocation action because stale portfolio marks and missing operating, market-share, macro "
        "and cross-sector evidence prevent a complete underwrite."
    )
    risk_challenges = [
        {"challenge": "Portfolio marks may be stale.", "required_action": "Refresh broker positions and prices."},
        {"challenge": "Operating and market-share history is incomplete.", "required_action": "Collect primary-source KPI evidence."},
        {"challenge": "Opportunity cost is not comparable.", "required_action": "Build equivalent dossiers for alternative sectors."},
    ]
    snapshot = {
        "valuation": sections["valuation"],
        "fundamentals": sections["constituent_fundamentals"],
        "ownership_and_flows": sections["ownership_and_flows"],
        "portfolio_fit": portfolio_fit,
        "opportunity_cost": opportunity_cost,
        "data_gaps": data_gaps,
        "evidence_references": evidence_references,
        "controls": {"human_final_required": True, "capital_action_allowed": False,
                     "broker_write_allowed": False},
    }
    return snapshot, positions, dissent, risk_challenges


def persist_dossier_and_committee(
    node: dict[str, Any], as_of_date: dt.date, actor: str,
    sections: dict[str, Any], evidence_references: list[dict[str, Any]],
    monitoring: list[dict[str, Any]], thesis: str,
    snapshot: dict[str, Any], positions: list[dict[str, Any]],
    dissent: str, risk_challenges: list[dict[str, Any]],
) -> tuple[int, int]:
    node_id = int(node["id"])
    data_gaps = sections["evidence_gaps"]["evidence"]
    dossier_fingerprint = fingerprint({
        "sections": sections,
        "evidence_sources": [
            {
                "source": reference.get("source"),
                "url": reference.get("url"),
                "reference": reference.get("reference"),
            }
            for reference in evidence_references
        ],
        "monitoring": monitoring,
        "thesis": thesis,
    })
    existing = run_psql_json(f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text FROM (
            SELECT id,version,dossier_fingerprint,source_cutoff_at::date AS source_cutoff_date
            FROM sector_intelligence.research_coverage
            WHERE taxonomy_node_id={node_id}
            ORDER BY version DESC LIMIT 1
        ) rows
    """)
    same_cutoff = bool(
        existing and str(existing[0].get("source_cutoff_date") or "") == as_of_date.isoformat()
    )
    version = int(existing[0]["version"]) if same_cutoff else (
        int(existing[0]["version"]) + 1 if existing else 1
    )
    packet_key = f"sector-underwrite:{node['taxonomy_key']}:{as_of_date.isoformat()}"
    packet_fingerprint = fingerprint({
        "snapshot": snapshot, "positions": positions, "dissent": dissent, "risk": risk_challenges
    })
    rows = run_psql_json(f"""
        WITH coverage AS (
            INSERT INTO sector_intelligence.research_coverage (
                taxonomy_node_id,coverage_status,owner_agent,priority,initiated_at,
                last_reviewed_at,next_review_due_at,thesis_summary,evidence_references,
                data_gaps,monitoring_indicators,version,dossier_sections,source_cutoff_at,
                dossier_fingerprint
            ) VALUES (
                {node_id},'monitoring','Sector Fundamental Analyst','high',now(),now(),
                now()+INTERVAL '30 days',{sql_literal(thesis)},{sql_jsonb(evidence_references)},
                {sql_jsonb(data_gaps)},{sql_jsonb(monitoring)},{version},{sql_jsonb(sections)},
                {sql_literal(as_of_date.isoformat())}::date,{sql_literal(dossier_fingerprint)}
            )
            ON CONFLICT (taxonomy_node_id,version) DO UPDATE SET
                coverage_status=EXCLUDED.coverage_status,owner_agent=EXCLUDED.owner_agent,
                priority=EXCLUDED.priority,last_reviewed_at=EXCLUDED.last_reviewed_at,
                next_review_due_at=EXCLUDED.next_review_due_at,thesis_summary=EXCLUDED.thesis_summary,
                evidence_references=EXCLUDED.evidence_references,data_gaps=EXCLUDED.data_gaps,
                monitoring_indicators=EXCLUDED.monitoring_indicators,
                dossier_sections=EXCLUDED.dossier_sections,source_cutoff_at=EXCLUDED.source_cutoff_at,
                dossier_fingerprint=EXCLUDED.dossier_fingerprint,updated_at=now()
            RETURNING id
        ), packet AS (
            INSERT INTO sector_intelligence.sector_committee_packets (
                packet_key,taxonomy_node_id,packet_type,as_of_date,decision_question,
                proposed_action,evidence_snapshot,independent_positions,dissent_summary,
                risk_challenges,status,human_final_required,capital_action_allowed,
                created_by,packet_fingerprint
            ) VALUES (
                {sql_literal(packet_key)},{node_id},'institutional_sector_underwrite',
                {sql_literal(as_of_date.isoformat())}::date,
                'Is the evidence sufficient to change sector capital allocation?',
                'more_research',{sql_jsonb(snapshot)},{sql_jsonb(positions)},{sql_literal(dissent)},
                {sql_jsonb(risk_challenges)},'ready',true,false,{sql_literal(actor)},
                {sql_literal(packet_fingerprint)}
            )
            ON CONFLICT (packet_key) DO UPDATE SET
                decision_question=EXCLUDED.decision_question,proposed_action=EXCLUDED.proposed_action,
                evidence_snapshot=EXCLUDED.evidence_snapshot,
                independent_positions=EXCLUDED.independent_positions,
                dissent_summary=EXCLUDED.dissent_summary,risk_challenges=EXCLUDED.risk_challenges,
                status='ready',human_final_required=true,capital_action_allowed=false,
                packet_fingerprint=EXCLUDED.packet_fingerprint,updated_at=now()
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(result)), '[]'::json)::text FROM (
            SELECT json_build_object(
                'coverage_id',(SELECT id FROM coverage),'committee_packet_id',(SELECT id FROM packet)
            ) AS payload
        ) result
    """)
    payload = rows[0]["payload"] if rows else None
    result = payload if isinstance(payload, dict) else json.loads(payload or "{}")
    return int(result["coverage_id"]), int(result["committee_packet_id"])


def run_acceptance(node_id: int, as_of_date: dt.date, actor: str) -> dict[str, Any]:
    run_key = f"sector-underwrite-v4-{node_id}-{as_of_date.isoformat()}"
    run_rows = run_psql_json(f"""
        SELECT coalesce(json_agg(row_to_json(result)), '[]'::json)::text FROM (
            SELECT sector_intelligence.run_acceptance_gates_v4(
                {sql_literal(run_key)},{node_id},{sql_literal(as_of_date.isoformat())}::date,
                {sql_literal(actor)}
            ) AS acceptance_run_id
        ) result
    """)
    if len(run_rows) != 1 or not run_rows[0].get("acceptance_run_id"):
        raise RuntimeError("v4 sector acceptance returned no durable run id")
    acceptance_run_id = int(run_rows[0]["acceptance_run_id"])
    rows = run_psql_json(f"""
        SELECT coalesce(json_agg(row_to_json(summary)), '[]'::json)::text
        FROM sector_intelligence.v_acceptance_gate_summary summary
        WHERE summary.acceptance_run_id={acceptance_run_id}
    """)
    if len(rows) != 1:
        raise RuntimeError("v4 sector acceptance returned no summary")
    return rows[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--taxonomy-key", required=True)
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--actor", default="Sector Portfolio Manager")
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()
    as_of_date = dt.date.fromisoformat(args.as_of_date)
    node = resolve_node(args.taxonomy_key.strip(), as_of_date)
    start = ten_year_start(as_of_date) - dt.timedelta(days=14)
    artifact_dir = artifact_root("sector_underwrites") / args.taxonomy_key / as_of_date.isoformat() / "valuation"
    rows = fetch_history(str(node["node_name"]), start, as_of_date, artifact_dir)
    exact_rows = [row for row in rows if ten_year_start(as_of_date) <= row["valuation_date"] <= as_of_date]
    stats = valuation_statistics(exact_rows)
    evidence = collect_evidence(int(node["id"]), as_of_date)
    artifacts = sorted({
        (row["source_artifact_path"], row["source_artifact_sha256"])
        for row in exact_rows
    })
    artifact_evidence = [{"path": path, "sha256": sha} for path, sha in artifacts]
    sections, references, monitoring, thesis = build_dossier(
        node, as_of_date, stats, evidence, artifact_evidence
    )
    data_gaps = sections["evidence_gaps"]["evidence"]
    snapshot, positions, dissent, risk_challenges = build_committee(
        sections, stats, evidence, references, data_gaps
    )
    result: dict[str, Any] = {
        "status": "validated",
        "taxonomy_key": node["taxonomy_key"],
        "taxonomy_node_id": int(node["id"]),
        "as_of_date": as_of_date.isoformat(),
        "valuation_observation_count": stats["observation_count"],
        "valuation_start": exact_rows[0]["valuation_date"].isoformat(),
        "valuation_end": exact_rows[-1]["valuation_date"].isoformat(),
        "current_pe": str(stats["current_value"]),
        "current_pe_percentile": str(stats["percentile_rank"]),
        "dossier_section_count": len(sections),
        "independent_position_count": len(positions),
        "open_data_gap_count": len(data_gaps),
        "artifact_count": len(artifacts),
        "persisted": False,
        "broker_write_allowed": False,
        "capital_action_allowed": False,
    }
    if args.persist:
        source_system_id, metric_definition_id = source_and_metric_ids()
        persist_valuation(
            int(node["id"]), source_system_id, metric_definition_id, as_of_date, exact_rows, stats
        )
        coverage_id, packet_id = persist_dossier_and_committee(
            node, as_of_date, args.actor, sections, references, monitoring, thesis,
            snapshot, positions, dissent, risk_challenges,
        )
        result.update({
            "status": "completed", "persisted": True,
            "coverage_id": coverage_id, "committee_packet_id": packet_id,
            "acceptance": run_acceptance(int(node["id"]), as_of_date, args.actor),
        })
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
