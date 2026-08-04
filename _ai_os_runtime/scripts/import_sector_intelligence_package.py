#!/usr/bin/env python3
"""Validate and import an evidence-backed sector-intelligence JSON package."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from run_agent_worker_once import psql_text, sql_jsonb, sql_literal


LEVELS = {"sector": 1, "industry": 2, "sub_industry": 3}
METRIC_FAMILIES = {
    "financial", "valuation", "operating", "market_share", "capacity", "price",
    "volume", "delivery", "derivatives", "ownership", "flow", "relative_strength",
    "breadth", "macro",
}
WEIGHTING_METHODS = {"equal", "market_cap", "free_float_market_cap", "quality", "momentum", "custom"}


class PackageError(ValueError):
    pass


def nonempty(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise PackageError(f"{label} is required")
    return text


def iso_date(value: Any, label: str) -> str:
    text = nonempty(value, label)
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise PackageError(f"{label} must be YYYY-MM-DD") from exc


def iso_timestamp(value: Any, label: str) -> str:
    text = nonempty(value, label).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise PackageError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise PackageError(f"{label} must include an explicit timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def load_package(path: Path) -> dict[str, Any]:
    raw = sys.stdin.read() if str(path) == "-" else path.read_text(encoding="utf-8")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise PackageError("package root must be a JSON object")
    return value


def validate_package(package: dict[str, Any]) -> dict[str, Any]:
    source = package.get("source")
    if not isinstance(source, dict):
        raise PackageError("source object is required")
    source_name = nonempty(source.get("name"), "source.name")
    source_location = nonempty(source.get("location"), "source.location")
    artifact_ref = nonempty(source.get("artifact_ref"), "source.artifact_ref")
    observed_at = iso_timestamp(source.get("observed_at"), "source.observed_at")

    taxonomy = list(package.get("taxonomy") or [])
    if not taxonomy:
        raise PackageError("at least one taxonomy row is required")
    taxonomy_by_key: dict[str, dict[str, Any]] = {}
    for position, raw in enumerate(taxonomy):
        row = dict(raw)
        key = nonempty(row.get("taxonomy_key"), f"taxonomy[{position}].taxonomy_key")
        if key in taxonomy_by_key:
            raise PackageError(f"duplicate taxonomy_key: {key}")
        level = nonempty(row.get("node_level"), f"taxonomy[{position}].node_level")
        if level not in LEVELS:
            raise PackageError(f"unsupported taxonomy level: {level}")
        row.update({
            "taxonomy_key": key,
            "node_code": nonempty(row.get("node_code"), f"taxonomy[{position}].node_code"),
            "node_name": nonempty(row.get("node_name"), f"taxonomy[{position}].node_name"),
            "node_level": level,
            "valid_from": iso_date(row.get("valid_from"), f"taxonomy[{position}].valid_from"),
        })
        taxonomy_by_key[key] = row
    for key, row in taxonomy_by_key.items():
        parent_key = row.get("parent_key")
        if row["node_level"] == "sector" and parent_key:
            raise PackageError(f"sector {key} cannot have a parent")
        if row["node_level"] != "sector":
            if parent_key not in taxonomy_by_key:
                raise PackageError(f"taxonomy parent missing for {key}: {parent_key}")
            parent = taxonomy_by_key[str(parent_key)]
            if LEVELS[parent["node_level"]] != LEVELS[row["node_level"]] - 1:
                raise PackageError(f"taxonomy parent level is invalid for {key}")

    memberships = list(package.get("memberships") or [])
    for position, raw in enumerate(memberships):
        row = dict(raw)
        nonempty(row.get("symbol"), f"memberships[{position}].symbol")
        nonempty(row.get("exchange"), f"memberships[{position}].exchange")
        nonempty(row.get("instrument_type"), f"memberships[{position}].instrument_type")
        taxonomy_key = nonempty(row.get("taxonomy_key"), f"memberships[{position}].taxonomy_key")
        if taxonomy_key not in taxonomy_by_key:
            raise PackageError(f"membership taxonomy_key not in package: {taxonomy_key}")
        iso_date(row.get("valid_from"), f"memberships[{position}].valid_from")
        if not row.get("evidence"):
            raise PackageError(f"memberships[{position}].evidence is required")
        nonempty(row.get("source_reference") or artifact_ref, f"memberships[{position}].source_reference")

    metrics = list(package.get("metrics") or [])
    metric_keys: set[str] = set()
    for position, raw in enumerate(metrics):
        row = dict(raw)
        key = nonempty(row.get("metric_key"), f"metrics[{position}].metric_key")
        family = nonempty(row.get("metric_family"), f"metrics[{position}].metric_family")
        if family not in METRIC_FAMILIES:
            raise PackageError(f"unsupported metric family: {family}")
        if (row.get("value_numeric") is None) == (row.get("value_text") is None):
            raise PackageError(f"metrics[{position}] must provide exactly one value")
        subject = row.get("subject") or {}
        taxonomy_subject = subject.get("taxonomy_key")
        symbol_subject = subject.get("symbol")
        if bool(taxonomy_subject) == bool(symbol_subject):
            raise PackageError(f"metrics[{position}].subject must identify one taxonomy or symbol")
        if taxonomy_subject and taxonomy_subject not in taxonomy_by_key:
            raise PackageError(f"metric taxonomy_key not in package: {taxonomy_subject}")
        if symbol_subject:
            nonempty(subject.get("exchange"), f"metrics[{position}].subject.exchange")
            nonempty(subject.get("instrument_type"), f"metrics[{position}].subject.instrument_type")
        iso_timestamp(row.get("observed_at") or observed_at, f"metrics[{position}].observed_at")
        nonempty(row.get("source_reference") or artifact_ref, f"metrics[{position}].source_reference")
        metric_keys.add(key)

    indices = list(package.get("indices") or [])
    for position, raw in enumerate(indices):
        row = dict(raw)
        nonempty(row.get("index_key"), f"indices[{position}].index_key")
        method = nonempty(row.get("weighting_method"), f"indices[{position}].weighting_method")
        if method not in WEIGHTING_METHODS:
            raise PackageError(f"unsupported index weighting method: {method}")
        iso_date(row.get("base_date"), f"indices[{position}].base_date")
        if row.get("taxonomy_key") and row["taxonomy_key"] not in taxonomy_by_key:
            raise PackageError(f"index taxonomy_key not in package: {row['taxonomy_key']}")
        constituents = list(row.get("constituents") or [])
        if not constituents:
            raise PackageError(f"indices[{position}] requires constituents")
        for member_position, member in enumerate(constituents):
            nonempty(member.get("symbol"), f"indices[{position}].constituents[{member_position}].symbol")
            nonempty(member.get("exchange"), f"indices[{position}].constituents[{member_position}].exchange")
            nonempty(member.get("instrument_type"), f"indices[{position}].constituents[{member_position}].instrument_type")
            iso_date(member.get("valid_from") or row.get("base_date"), f"indices[{position}].constituents[{member_position}].valid_from")

    return {
        "source": {**source, "name": source_name, "location": source_location,
                   "artifact_ref": artifact_ref, "observed_at": observed_at},
        "taxonomy": taxonomy,
        "memberships": memberships,
        "metrics": metrics,
        "indices": indices,
        "counts": {"taxonomy": len(taxonomy), "memberships": len(memberships),
                   "metrics": len(metrics), "indices": len(indices)},
    }


def package_hash(package: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(package, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def symbol_id_sql(symbol: str, exchange: str, instrument_type: str) -> str:
    return (
        "(SELECT id FROM trading.symbols WHERE upper(symbol)=upper(" + sql_literal(symbol) + ") "
        "AND upper(exchange)=upper(" + sql_literal(exchange) + ") "
        "AND upper(instrument_type)=upper(" + sql_literal(instrument_type) + ") LIMIT 1)"
    )


def build_import_sql(validated: dict[str, Any], digest: str, actor: str, run_key: str) -> str:
    source = validated["source"]
    statements = [
        "BEGIN;",
        f"""DO $guard$ BEGIN
            IF EXISTS (SELECT 1 FROM sector_intelligence.source_import_runs WHERE package_hash={sql_literal(digest)}) THEN
                RAISE EXCEPTION 'sector package already imported: %', {sql_literal(digest)};
            END IF;
        END $guard$;""",
        f"""INSERT INTO core.source_systems (name,source_type,location,sensitivity,status,notes)
        VALUES ({sql_literal(source['name'])},{sql_literal(source.get('source_type') or 'licensed_or_primary_export')},
                {sql_literal(source['location'])},'private','connected','Sector intelligence evidence package')
        ON CONFLICT (name) DO UPDATE SET location=EXCLUDED.location,status='connected';""",
    ]
    for row in validated["taxonomy"]:
        parent = "NULL" if not row.get("parent_key") else (
            f"(SELECT id FROM sector_intelligence.taxonomy_nodes WHERE taxonomy_key={sql_literal(row['parent_key'])})"
        )
        statements.append(f"""
        INSERT INTO sector_intelligence.taxonomy_nodes
            (taxonomy_key,node_code,node_name,node_level,parent_id,country_code,description,valid_from,valid_to,
             source_system_id,source_reference,methodology)
        VALUES ({sql_literal(row['taxonomy_key'])},{sql_literal(row['node_code'])},{sql_literal(row['node_name'])},
                {sql_literal(row['node_level'])},{parent},{sql_literal(row.get('country_code') or 'IN')},
                {sql_literal(row.get('description'))},{sql_literal(row['valid_from'])}::date,
                {sql_literal(row.get('valid_to')) + '::date' if row.get('valid_to') else 'NULL'},
                (SELECT id FROM core.source_systems WHERE name={sql_literal(source['name'])}),
                {sql_literal(row.get('source_reference') or source['artifact_ref'])},{sql_jsonb(row.get('methodology') or {})})
        ON CONFLICT (taxonomy_key) DO UPDATE SET node_name=EXCLUDED.node_name,parent_id=EXCLUDED.parent_id,
            source_system_id=EXCLUDED.source_system_id,source_reference=EXCLUDED.source_reference,
            methodology=EXCLUDED.methodology,updated_at=now();""")
    for row in validated["memberships"]:
        sid = symbol_id_sql(row["symbol"], row["exchange"], row["instrument_type"])
        statements.append(f"""
        INSERT INTO sector_intelligence.instrument_membership_history
            (symbol_id,taxonomy_node_id,membership_role,valid_from,valid_to,is_primary,source_system_id,
             source_reference,evidence)
        VALUES ({sid},(SELECT id FROM sector_intelligence.taxonomy_nodes WHERE taxonomy_key={sql_literal(row['taxonomy_key'])}),
                {sql_literal(row.get('membership_role') or 'constituent')},{sql_literal(row['valid_from'])}::date,
                {sql_literal(row.get('valid_to')) + '::date' if row.get('valid_to') else 'NULL'},
                {str(row.get('is_primary', True)).lower()},
                (SELECT id FROM core.source_systems WHERE name={sql_literal(source['name'])}),
                {sql_literal(row.get('source_reference') or source['artifact_ref'])},{sql_jsonb(row['evidence'])})
        ON CONFLICT (symbol_id,taxonomy_node_id,membership_role,valid_from) DO UPDATE SET
            valid_to=EXCLUDED.valid_to,is_primary=EXCLUDED.is_primary,source_reference=EXCLUDED.source_reference,
            evidence=EXCLUDED.evidence;""")
    for row in validated["metrics"]:
        statements.append(f"""
        INSERT INTO sector_intelligence.metric_definitions
            (metric_key,metric_name,metric_family,value_type,unit,frequency,aggregation_method,higher_is_better,
             formula_expression,required_inputs,methodology_version,active)
        VALUES ({sql_literal(row['metric_key'])},{sql_literal(row.get('metric_name') or row['metric_key'])},
                {sql_literal(row['metric_family'])},{sql_literal(row.get('value_type') or 'numeric')},
                {sql_literal(row.get('unit'))},{sql_literal(row.get('frequency') or 'ad_hoc')},
                {sql_literal(row.get('aggregation_method') or 'last')},
                {str(row.get('higher_is_better')).lower() if row.get('higher_is_better') is not None else 'NULL'},
                {sql_literal(row.get('formula_expression'))},{sql_jsonb(row.get('required_inputs') or [])},
                {sql_literal(row.get('methodology_version') or 'source-v1')},true)
        ON CONFLICT (metric_key) DO UPDATE SET metric_name=EXCLUDED.metric_name,unit=EXCLUDED.unit,
            methodology_version=EXCLUDED.methodology_version,updated_at=now();""")
        subject = row["subject"]
        taxonomy_id = (
            f"(SELECT id FROM sector_intelligence.taxonomy_nodes WHERE taxonomy_key={sql_literal(subject['taxonomy_key'])})"
            if subject.get("taxonomy_key") else "NULL"
        )
        sid = symbol_id_sql(subject["symbol"], subject["exchange"], subject["instrument_type"]) if subject.get("symbol") else "NULL"
        value_numeric = str(row["value_numeric"]) if row.get("value_numeric") is not None else "NULL"
        value_text = sql_literal(row.get("value_text"))
        statements.append(f"""
        INSERT INTO sector_intelligence.metric_observations
            (metric_definition_id,taxonomy_node_id,symbol_id,observed_at,period_start,period_end,value_numeric,
             value_text,currency,source_system_id,source_reference,calculation_version,input_fingerprint,
             quality_status,metadata)
        VALUES ((SELECT id FROM sector_intelligence.metric_definitions WHERE metric_key={sql_literal(row['metric_key'])}),
                {taxonomy_id},{sid},{sql_literal(row.get('observed_at') or source['observed_at'])}::timestamptz,
                {sql_literal(row.get('period_start')) + '::date' if row.get('period_start') else 'NULL'},
                {sql_literal(row.get('period_end')) + '::date' if row.get('period_end') else 'NULL'},
                {value_numeric},{value_text},{sql_literal(row.get('currency'))},
                (SELECT id FROM core.source_systems WHERE name={sql_literal(source['name'])}),
                {sql_literal(row.get('source_reference') or source['artifact_ref'])},NULL,{sql_literal(digest)},
                'observed',{sql_jsonb(row.get('metadata') or {})});""")
    for row in validated["indices"]:
        taxonomy_id = (
            f"(SELECT id FROM sector_intelligence.taxonomy_nodes WHERE taxonomy_key={sql_literal(row['taxonomy_key'])})"
            if row.get("taxonomy_key") else "NULL"
        )
        statements.append(f"""
        INSERT INTO sector_intelligence.custom_index_definitions
            (index_key,index_name,taxonomy_node_id,base_date,base_value,currency,weighting_method,selection_rules,
             weighting_rules,rebalance_frequency,calculation_methodology,methodology_version,status,created_by)
        VALUES ({sql_literal(row['index_key'])},{sql_literal(row.get('index_name') or row['index_key'])},{taxonomy_id},
                {sql_literal(row['base_date'])}::date,{row.get('base_value') or 1000},{sql_literal(row.get('currency') or 'INR')},
                {sql_literal(row['weighting_method'])},{sql_jsonb(row.get('selection_rules') or {})},
                {sql_jsonb(row.get('weighting_rules') or {})},{sql_literal(row.get('rebalance_frequency') or 'quarterly')},
                {sql_literal(row.get('calculation_methodology') or 'point_in_time_total_return')},
                {sql_literal(row.get('methodology_version') or 'source-v1')},'validated',{sql_literal(actor)})
        ON CONFLICT (index_key) DO UPDATE SET index_name=EXCLUDED.index_name,taxonomy_node_id=EXCLUDED.taxonomy_node_id,
            selection_rules=EXCLUDED.selection_rules,weighting_rules=EXCLUDED.weighting_rules,
            methodology_version=EXCLUDED.methodology_version,updated_at=now();""")
        for member in row["constituents"]:
            sid = symbol_id_sql(member["symbol"], member["exchange"], member["instrument_type"])
            statements.append(f"""
            INSERT INTO sector_intelligence.custom_index_constituents
                (index_id,symbol_id,valid_from,valid_to,inclusion_reason,source_membership_id)
            VALUES ((SELECT id FROM sector_intelligence.custom_index_definitions WHERE index_key={sql_literal(row['index_key'])}),
                    {sid},{sql_literal(member.get('valid_from') or row['base_date'])}::date,
                    {sql_literal(member.get('valid_to')) + '::date' if member.get('valid_to') else 'NULL'},
                    {sql_literal(member.get('inclusion_reason') or 'source package')},
                    (SELECT membership.id FROM sector_intelligence.instrument_membership_history membership
                     JOIN sector_intelligence.taxonomy_nodes node ON node.id=membership.taxonomy_node_id
                     WHERE membership.symbol_id={sid} AND node.taxonomy_key={sql_literal(row.get('taxonomy_key'))}
                     ORDER BY membership.valid_from DESC LIMIT 1))
            ON CONFLICT (index_id,symbol_id,valid_from) DO UPDATE SET valid_to=EXCLUDED.valid_to,
                inclusion_reason=EXCLUDED.inclusion_reason,source_membership_id=EXCLUDED.source_membership_id;""")
    counts = validated["counts"]
    statements.append(f"""
    INSERT INTO sector_intelligence.source_import_runs
        (run_key,package_hash,source_system_id,source_artifact_ref,observed_at,status,taxonomy_rows,
         membership_rows,metric_rows,index_rows,validation_errors,imported_by,broker_write_allowed)
    VALUES ({sql_literal(run_key)},{sql_literal(digest)},
            (SELECT id FROM core.source_systems WHERE name={sql_literal(source['name'])}),
            {sql_literal(source['artifact_ref'])},{sql_literal(source['observed_at'])}::timestamptz,'imported',
            {counts['taxonomy']},{counts['memberships']},{counts['metrics']},{counts['indices']},
            '[]'::jsonb,{sql_literal(actor)},false)
    ON CONFLICT (package_hash) DO NOTHING;""")
    statements.extend(["COMMIT;", "SELECT '[]'::json::text;"])
    return "\n".join(statements)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--persist", action="store_true", help="Persist only after the complete package validates.")
    parser.add_argument("--actor", default="Sector Data Steward")
    args = parser.parse_args()
    input_path = Path("-") if args.input == "-" else Path(args.input).expanduser().resolve()
    package = load_package(input_path)
    validated = validate_package(package)
    digest = package_hash(package)
    run_key = f"sector-import-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
    if args.persist:
        psql_text(build_import_sql(validated, digest, args.actor, run_key))
    print(json.dumps({
        "run_key": run_key, "status": "imported" if args.persist else "validated",
        "package_hash": digest, "counts": validated["counts"],
        "source_artifact_ref": validated["source"]["artifact_ref"],
        "broker_write_allowed": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
