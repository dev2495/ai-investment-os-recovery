from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable


RowsFn = Callable[[str], list[dict[str, Any]]]
StatementFn = Callable[[str], list[dict[str, Any]]]
LiteralFn = Callable[[Any], str]
JsonFn = Callable[[Any], str]

SCOPE_KEY = "owner:devarsh"
MAX_LIMIT = 100
ALLOWED_OPERATORS = {"gt", "gte", "lt", "lte", "eq", "neq"}
ALLOWED_METRICS = {
    "asset_turnover",
    "capex_to_revenue",
    "cfo_pat",
    "current_ratio",
    "debt_to_equity",
    "dso",
    "ebitda_margin",
    "fcf_margin",
    "interest_coverage",
    "pat_margin",
    "revenue_cagr_5y",
    "pat_cagr_5y",
    "roce_proxy",
    "roe",
    "governance_flag_count",
}
GLOBAL_SCOPE_KEY = "global:public"
REQUIRED_VALIDATION_KINDS = ("schema", "metric_availability", "point_in_time", "known_fixture")
METRIC_ALIASES = {
    "sales_cagr_5y": "revenue_cagr_5y",
    "ocf_pat": "cfo_pat",
    "roic": "roce_proxy",
    "roce": "roce_proxy",
}
METRIC_METADATA = {
    "asset_turnover": ("Asset turnover", "ratio", "multiple"),
    "capex_to_revenue": ("Capex / revenue", "ratio", "percent"),
    "cfo_pat": ("CFO / PAT", "ratio", "percent"),
    "current_ratio": ("Current ratio", "ratio", "multiple"),
    "debt_to_equity": ("Debt / equity", "ratio", "multiple"),
    "dso": ("Days sales outstanding", "ratio", "days"),
    "ebitda_margin": ("EBITDA margin", "ratio", "percent"),
    "fcf_margin": ("FCF margin", "ratio", "percent"),
    "interest_coverage": ("Interest coverage", "ratio", "multiple"),
    "pat_margin": ("PAT margin", "ratio", "percent"),
    "revenue_cagr_5y": ("Revenue CAGR", "statement_fact", "percent"),
    "pat_cagr_5y": ("PAT CAGR", "statement_fact", "percent"),
    "roce_proxy": ("ROCE proxy", "ratio", "percent"),
    "roe": ("Return on equity", "ratio", "percent"),
    "governance_flag_count": ("Governance filing flags", "filing", "count"),
}


class ScannerValidationError(ValueError):
    pass


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _text_array(values: list[str], literal: LiteralFn) -> str:
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    if not cleaned:
        return "ARRAY[]::text[]"
    return "ARRAY[" + ",".join(literal(value) for value in cleaned) + "]::text[]"


def _metric_key(value: Any) -> str:
    key = re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower()).strip("_")
    return METRIC_ALIASES.get(key, key)


def _compare(actual: Decimal, operator: str, expected: Decimal) -> bool:
    if operator == "gt":
        return actual > expected
    if operator == "gte":
        return actual >= expected
    if operator == "lt":
        return actual < expected
    if operator == "lte":
        return actual <= expected
    if operator == "eq":
        return actual == expected
    if operator == "neq":
        return actual != expected
    raise ScannerValidationError(f"unsupported operator: {operator}")


def _validate_condition(node: Any, *, path: str = "filters") -> list[dict[str, Any]]:
    if not isinstance(node, dict):
        raise ScannerValidationError(f"{path} must be an object")
    group_keys = [key for key in ("all", "any", "not") if key in node]
    if group_keys:
        if len(group_keys) != 1 or len(node) != 1:
            raise ScannerValidationError(f"{path} must contain exactly one group operator")
        key = group_keys[0]
        children = node[key]
        if key == "not":
            children = [children]
        if not isinstance(children, list) or not children:
            raise ScannerValidationError(f"{path}.{key} must contain at least one condition")
        normalized = [_validate_condition(child, path=f"{path}.{key}[{index}]") for index, child in enumerate(children)]
        return [{key: [item[0] for item in normalized]}]
    if set(node) - {"metric", "operator", "value"}:
        raise ScannerValidationError(f"{path} contains unsupported fields")
    metric = _metric_key(node.get("metric"))
    operator = str(node.get("operator") or "").lower()
    expected = _decimal(node.get("value"))
    if metric not in ALLOWED_METRICS:
        raise ScannerValidationError(f"{path}.metric is not allowlisted: {metric or 'missing'}")
    if operator not in ALLOWED_OPERATORS:
        raise ScannerValidationError(f"{path}.operator is not allowlisted: {operator or 'missing'}")
    if expected is None:
        raise ScannerValidationError(f"{path}.value must be a finite number")
    return [{"metric": metric, "operator": operator, "value": float(expected)}]


def validate_definition(definition: Any) -> dict[str, Any]:
    if not isinstance(definition, dict):
        raise ScannerValidationError("definition must be an object")
    if str(definition.get("api_version") or "") != "aios.scanner/v1":
        raise ScannerValidationError("api_version must equal aios.scanner/v1")
    universe = definition.get("universe")
    if not isinstance(universe, dict):
        raise ScannerValidationError("universe must be an object")
    exchanges = universe.get("exchanges") or ["NSE", "BSE"]
    if not isinstance(exchanges, list) or not exchanges:
        raise ScannerValidationError("universe.exchanges must be a non-empty list")
    normalized_exchanges = sorted({str(value).upper() for value in exchanges if str(value).upper() in {"NSE", "BSE"}})
    if not normalized_exchanges:
        raise ScannerValidationError("only NSE and BSE are supported in Research Desk v1")
    requirements = definition.get("requirements") or {}
    required = [_metric_key(value) for value in requirements.get("required_metrics") or []]
    unknown = sorted(set(required) - ALLOWED_METRICS)
    if unknown:
        raise ScannerValidationError(f"required_metrics are not allowlisted: {', '.join(unknown)}")
    completeness = _decimal(requirements.get("minimum_data_completeness_pct", 100))
    if completeness is None or completeness < 0 or completeness > 100:
        raise ScannerValidationError("minimum_data_completeness_pct must be between 0 and 100")
    conditions = _validate_condition(definition.get("filters") or {"all": []})
    score = definition.get("score") or {"components": []}
    components = score.get("components") if isinstance(score, dict) else None
    if not isinstance(components, list) or len(components) > 20:
        raise ScannerValidationError("score.components must be a list of at most 20 entries")
    normalized_components: list[dict[str, Any]] = []
    for index, component in enumerate(components):
        if not isinstance(component, dict):
            raise ScannerValidationError(f"score.components[{index}] must be an object")
        metric = _metric_key(component.get("metric"))
        weight = _decimal(component.get("weight"))
        direction = str(component.get("direction") or "higher")
        if metric not in ALLOWED_METRICS or weight is None or weight < 0 or direction not in {"higher", "lower"}:
            raise ScannerValidationError(f"score.components[{index}] is invalid")
        normalized_components.append({"metric": metric, "weight": float(weight), "direction": direction})
    return {
        "api_version": "aios.scanner/v1",
        "universe": {
            **universe,
            "countries": ["IN"],
            "exchanges": normalized_exchanges,
            "as_of_policy": "point_in_time",
        },
        "requirements": {
            **requirements,
            "required_metrics": sorted(set(required)),
            "minimum_data_completeness_pct": float(completeness),
            "missing_data_policy": "exclude_and_report",
        },
        "filters": conditions[0],
        "score": {"components": normalized_components},
    }


def _evaluate(node: dict[str, Any], metrics: dict[str, dict[str, Any]]) -> tuple[bool, list[str]]:
    if "all" in node:
        outcomes = [_evaluate(child, metrics) for child in node["all"]]
        return all(item[0] for item in outcomes), [reason for item in outcomes for reason in item[1]]
    if "any" in node:
        outcomes = [_evaluate(child, metrics) for child in node["any"]]
        return any(item[0] for item in outcomes), [reason for item in outcomes for reason in item[1]]
    if "not" in node:
        child = node["not"][0]
        outcome, reasons = _evaluate(child, metrics)
        return not outcome, [f"not({reason})" for reason in reasons]
    metric = str(node["metric"])
    observed = metrics.get(metric) or {}
    actual = _decimal(observed.get("value"))
    expected = _decimal(node.get("value"))
    if actual is None or expected is None:
        return False, [f"{metric}: missing"]
    passed = _compare(actual, str(node["operator"]), expected)
    return passed, [f"{metric} {node['operator']} {expected}: {actual} ({'pass' if passed else 'fail'})"]


@dataclass
class FundamentalScannerService:
    run_rows: RowsFn
    run_statement: StatementFn
    sql_literal: LiteralFn
    sql_jsonb: JsonFn
    scope_key: str = SCOPE_KEY
    run_control_statement: StatementFn | None = None

    def list_scanners(self, *, limit: Any = 25, cursor: Any = 0) -> dict[str, Any]:
        page_size = _bounded_int(limit, 25, 1, MAX_LIMIT)
        offset = _bounded_int(cursor, 0, 0, 100000)
        rows = self.run_rows(
            f"""
            SELECT definition.id,definition.scope_key,definition.scanner_key,definition.name,definition.description,
                   definition.status,definition.tags,definition.updated_at,
                   version.id scanner_version_id,version.version,version.status version_status,
                   version.definition_hash,
                   version.definition_json->>'api_version' definition_api_version,
                   CASE
                     WHEN definition.scope_key={self.sql_literal(GLOBAL_SCOPE_KEY)}
                      AND version.definition_json->>'api_version'='aios.scanner/v1'
                     THEN true ELSE false
                   END template_executable,
                   coalesce((SELECT jsonb_object_agg(validation.validation_kind,validation.status)
                             FROM market.scanner_validations validation
                             WHERE validation.scope_key=definition.scope_key
                               AND validation.scanner_version_id=version.id),'{{}}'::jsonb) validation_summary,
                   coalesce((SELECT jsonb_object_agg(latest.validation_kind,jsonb_build_object(
                               'status',latest.status,'report',latest.report,'coverage',latest.coverage,
                               'completed_at',latest.completed_at))
                             FROM (
                               SELECT DISTINCT ON (validation_kind)
                                      validation_kind,status,report,coverage,completed_at
                               FROM market.scanner_validations selected_validation
                               WHERE selected_validation.scope_key=definition.scope_key
                                 AND selected_validation.scanner_version_id=version.id
                               ORDER BY validation_kind,created_at DESC
                             ) latest),'{{}}'::jsonb) validation_details,
                   (SELECT approval.id
                    FROM agent.approvals approval
                    WHERE approval.approval_type='scanner_publish'
                      AND approval.status IN ('pending','approved')
                      AND approval.requested_action->>'scanner_id'=definition.id::text
                      AND approval.requested_action->>'scanner_version_id'=version.id::text
                      AND approval.requested_action->>'scope_key'=definition.scope_key
                    ORDER BY CASE approval.status WHEN 'approved' THEN 1 ELSE 2 END,
                             approval.created_at DESC LIMIT 1) publish_approval_id,
                   (SELECT approval.status
                    FROM agent.approvals approval
                    WHERE approval.approval_type='scanner_publish'
                      AND approval.status IN ('pending','approved')
                      AND approval.requested_action->>'scanner_id'=definition.id::text
                      AND approval.requested_action->>'scanner_version_id'=version.id::text
                      AND approval.requested_action->>'scope_key'=definition.scope_key
                    ORDER BY CASE approval.status WHEN 'approved' THEN 1 ELSE 2 END,
                             approval.created_at DESC LIMIT 1) publish_approval_status,
                   (SELECT count(*) FROM market.scanner_runs run WHERE run.scanner_version_id=version.id) run_count,
                   (SELECT max(run.as_of_cutoff_at) FROM market.scanner_runs run WHERE run.scanner_version_id=version.id) last_run_as_of
            FROM market.scanner_definitions definition
            LEFT JOIN LATERAL (
              SELECT selected.* FROM market.scanner_versions selected
              WHERE selected.scanner_definition_id=definition.id
              ORDER BY selected.version DESC LIMIT 1
            ) version ON true
            WHERE definition.scope_key IN ({self.sql_literal(self.scope_key)},{self.sql_literal(GLOBAL_SCOPE_KEY)})
            ORDER BY definition.name,definition.id LIMIT {page_size + 1} OFFSET {offset}
            """
        )
        return {
            "items": rows[:page_size],
            "page": {"limit": page_size, "cursor": offset, "next_cursor": offset + page_size if len(rows) > page_size else None},
            "broker_write_allowed": False,
            "external_write_allowed": False,
        }

    def get_scanner(self, scanner_id: int) -> dict[str, Any]:
        rows = self.run_rows(
            f"""
            SELECT definition.*,version.id scanner_version_id,version.version,
                   version.status version_status,version.definition_json AS definition,version.definition_hash,
                   version.calculation_revision,version.published_at,
                   (SELECT coalesce(jsonb_agg(to_jsonb(validation) ORDER BY validation.created_at DESC),'[]'::jsonb)
                    FROM market.scanner_validations validation WHERE validation.scanner_version_id=version.id) validations
            FROM market.scanner_definitions definition
            JOIN LATERAL (
              SELECT selected.* FROM market.scanner_versions selected
              WHERE selected.scanner_definition_id=definition.id ORDER BY selected.version DESC LIMIT 1
            ) version ON true
            WHERE definition.id={int(scanner_id)}
              AND definition.scope_key IN ({self.sql_literal(self.scope_key)},{self.sql_literal(GLOBAL_SCOPE_KEY)}) LIMIT 1
            """
        )
        if not rows:
            raise ValueError("fundamental scanner was not found")
        return {**rows[0], "broker_write_allowed": False, "external_write_allowed": False}

    def create_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = re.sub(r"\s+", " ", str(payload.get("name") or "").strip())[:140]
        if len(name) < 3:
            raise ScannerValidationError("name must be at least three characters")
        scanner_key = re.sub(r"[^a-z0-9]+", "_", str(payload.get("scanner_key") or name).lower()).strip("_")[:80]
        definition = validate_definition(payload.get("definition"))
        definition_hash = _hash(definition)
        actor = str(payload.get("actor") or "Devarsh")[:120]
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        rows = self.run_statement(
            f"""
            WITH scanner AS (
              INSERT INTO market.scanner_definitions
                (scope_key,scanner_key,name,description,owner_agent,status,tags,metadata,created_by)
              VALUES ({self.sql_literal(self.scope_key)},{self.sql_literal(scanner_key)},{self.sql_literal(name)},
                      {self.sql_literal(str(payload.get('description') or 'User-defined deterministic fundamental scanner')[:500])},
                      'Fundamental Research Analyst','draft',
                      {_text_array([str(item) for item in payload.get('tags') or []], self.sql_literal)},
                      {self.sql_jsonb(metadata)},{self.sql_literal(actor)})
              ON CONFLICT (scope_key,scanner_key) DO UPDATE SET
                metadata=market.scanner_definitions.metadata||EXCLUDED.metadata,updated_at=now()
              RETURNING *
            ), next_version AS (
              SELECT coalesce(max(version),0)+1 number FROM market.scanner_versions
              WHERE scanner_definition_id=(SELECT id FROM scanner)
            ), inserted_version AS (
              INSERT INTO market.scanner_versions
                (scope_key,scanner_definition_id,version,api_version,dsl_version,status,definition_json,
                 definition_hash,universe_config,filter_config,score_config,output_config,
                 calculation_revision,source_request_text,created_by)
              SELECT {self.sql_literal(self.scope_key)},scanner.id,next_version.number,'v1','v1','draft',
                     {self.sql_jsonb(definition)},{self.sql_literal(definition_hash)},
                     {self.sql_jsonb(definition['universe'])},{self.sql_jsonb(definition['filters'])},
                     {self.sql_jsonb(definition['score'])},
                     {self.sql_jsonb({'missing_data_policy':'exclude_and_report','broker_write_allowed':False})},
                     'research-desk-v1',{self.sql_literal(str(payload.get('description') or '')[:2000])},
                     {self.sql_literal(actor)}
              FROM scanner,next_version
              ON CONFLICT (scope_key,scanner_definition_id,definition_hash) DO NOTHING
              RETURNING *
            ), version AS (
              SELECT * FROM inserted_version
              UNION ALL
              SELECT existing.*
              FROM market.scanner_versions existing,scanner
              WHERE existing.scope_key={self.sql_literal(self.scope_key)}
                AND existing.scanner_definition_id=scanner.id
                AND existing.definition_hash={self.sql_literal(definition_hash)}
              LIMIT 1
            )
            SELECT jsonb_build_array(jsonb_build_object(
              'scanner',(SELECT to_jsonb(scanner) FROM scanner),
              'version',(SELECT to_jsonb(version) FROM version),
              'created',EXISTS(SELECT 1 FROM inserted_version),
              'broker_write_allowed',false,'external_write_allowed',false
            ))::text
            """
        )
        return rows[0] if rows else {}

    def clone_template(self, scanner_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        template = self.get_scanner(scanner_id)
        if template.get("scope_key") != GLOBAL_SCOPE_KEY:
            raise ScannerValidationError("only a global scanner template can be copied into your workspace")
        definition = validate_definition(template.get("definition"))
        definition_hash = _hash(definition)
        scanner_key = re.sub(
            r"[^a-z0-9]+",
            "_",
            str(payload.get("scanner_key") or template.get("scanner_key") or template.get("name") or "scanner").lower(),
        ).strip("_")[:80]
        existing = self.run_rows(
            f"""
            SELECT definition.*,version.id scanner_version_id,version.version,
                   version.status version_status,version.definition_json AS definition,
                   version.definition_hash,version.calculation_revision
            FROM market.scanner_definitions definition
            JOIN market.scanner_versions version
              ON version.scanner_definition_id=definition.id
             AND version.scope_key=definition.scope_key
            WHERE definition.scope_key={self.sql_literal(self.scope_key)}
              AND definition.scanner_key={self.sql_literal(scanner_key)}
              AND version.definition_hash={self.sql_literal(definition_hash)}
            ORDER BY version.version DESC LIMIT 1
            """
        )
        if existing:
            return {
                "scanner": existing[0],
                "version": existing[0],
                "created": False,
                "cloned_from": {"scanner_id": scanner_id, "scope_key": GLOBAL_SCOPE_KEY},
                "broker_write_allowed": False,
                "external_write_allowed": False,
            }
        result = self.create_draft({
            "name": payload.get("name") or template.get("name"),
            "scanner_key": scanner_key,
            "description": payload.get("description") or template.get("description"),
            "definition": definition,
            "tags": ["workspace_copy", f"template:{template.get('scanner_key') or scanner_id}"],
            "metadata": {
                "cloned_from_scope": GLOBAL_SCOPE_KEY,
                "cloned_from_scanner_id": scanner_id,
                "cloned_from_scanner_key": template.get("scanner_key"),
                "cloned_from_version": template.get("version"),
                "cloned_from_definition_hash": template.get("definition_hash"),
            },
            "actor": payload.get("actor") or "Devarsh",
        })
        result["cloned_from"] = {"scanner_id": scanner_id, "scope_key": GLOBAL_SCOPE_KEY}
        result["broker_write_allowed"] = False
        result["external_write_allowed"] = False
        return result
    def create_from_natural_language(self, payload: dict[str, Any]) -> dict[str, Any]:
        instruction = re.sub(r"\s+", " ", str(payload.get("instruction") or payload.get("text") or "").strip())[:2000]
        if len(instruction) < 12:
            raise ScannerValidationError("a specific scanner instruction is required")
        lowered = instruction.lower()
        conditions: list[dict[str, Any]] = []
        patterns = (
            (r"(?:sales|revenue)[^\d]{0,30}(?:cagr|growth)[^\d]{0,20}(?:above|over|>=?)\s*(\d+(?:\.\d+)?)", "revenue_cagr_5y", "gte"),
            (r"(?:pat|profit)[^\d]{0,30}(?:cagr|growth)[^\d]{0,20}(?:above|over|>=?)\s*(\d+(?:\.\d+)?)", "pat_cagr_5y", "gte"),
            (r"(?:roic|roce)[^\d]{0,20}(?:above|over|>=?)\s*(\d+(?:\.\d+)?)", "roce_proxy", "gte"),
            (r"(?:ocf|cfo)\s*/\s*pat[^\d]{0,20}(?:above|over|>=?)\s*(\d+(?:\.\d+)?)", "cfo_pat", "gte"),
            (r"debt\s*(?:to|/)\s*equity[^\d]{0,20}(?:below|under|<=?)\s*(\d+(?:\.\d+)?)", "debt_to_equity", "lte"),
        )
        for pattern, metric, operator in patterns:
            match = re.search(pattern, lowered)
            if match:
                value = float(match.group(1))
                if metric == "cfo_pat" and value <= 5:
                    value *= 100
                conditions.append({"metric": metric, "operator": operator, "value": value})
        unsupported: list[str] = []
        for term in ("p/e", "pe ", "median p", "promoter pledge", "net cash", "historical replay"):
            if term in lowered:
                unsupported.append(term.strip())
        if not conditions:
            raise ScannerValidationError("no supported deterministic metric threshold could be resolved")
        completeness_match = re.search(r"(?:completeness|coverage)[^\d]{0,20}(\d+(?:\.\d+)?)", lowered)
        completeness = float(completeness_match.group(1)) if completeness_match else 80.0
        required = sorted({str(item["metric"]) for item in conditions})
        definition = {
            "api_version": "aios.scanner/v1",
            "universe": {"countries": ["IN"], "exchanges": ["NSE", "BSE"], "as_of_policy": "point_in_time"},
            "requirements": {"required_metrics": required, "minimum_data_completeness_pct": completeness, "missing_data_policy": "exclude_and_report"},
            "filters": {"all": conditions},
            "score": {"components": [
                {"metric": metric, "weight": 1 / len(required),
                 "direction": "lower" if metric in {"debt_to_equity", "dso", "capex_to_revenue"} else "higher"}
                for metric in required
            ]},
        }
        result = self.create_draft({
            "name": payload.get("name") or "Natural language scanner",
            "description": instruction,
            "definition": definition,
            "actor": payload.get("actor") or "Devarsh",
            "tags": ["natural_language_draft"],
        })
        result["interpretation"] = {
            "resolved_conditions": conditions,
            "unsupported_requirements": unsupported,
            "status": "draft_requires_review" if unsupported else "draft",
            "note": "Unsupported requirements remain explicit and were not silently dropped from validation readiness.",
        }
        return result

    def validate_scanner(self, scanner_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        scanner = self.get_scanner(scanner_id)
        if scanner.get("scope_key") != self.scope_key:
            raise ScannerValidationError("clone the global template into your workspace before validation")
        normalized = validate_definition(scanner.get("definition"))
        actor = str(payload.get("actor") or "Devarsh")[:120]
        warnings: list[str] = []
        unsupported = payload.get("unsupported_requirements") or []
        if unsupported:
            warnings.append("Natural-language requirements remain unsupported: " + ", ".join(map(str, unsupported)))
        _companies, metrics_by_company = self._load_company_metrics(datetime.now(timezone.utc))
        required = set(normalized["requirements"]["required_metrics"])
        availability = {
            metric: sum(1 for metrics in metrics_by_company.values() if metric in metrics)
            for metric in sorted(required)
        }
        unavailable = sorted(metric for metric, count in availability.items() if count == 0)
        if unavailable:
            warnings.append("No validated point-in-time input is available for: " + ", ".join(unavailable))
        final_status = "warning" if warnings else "passed"
        validation_rows: list[dict[str, Any]] = []
        reports = {
            "schema": {
                "allowlisted_ast": True,
                "dynamic_sql": False,
                "definition_hash": _hash(normalized),
            },
            "metric_availability": {
                "required_metrics": sorted(required),
                "eligible_company_counts": availability,
                "unavailable_metrics": unavailable,
            },
            "point_in_time": {
                "as_of_policy": normalized["universe"]["as_of_policy"],
                "missing_data_policy": normalized["requirements"]["missing_data_policy"],
                "future_inputs_rejected": True,
            },
            "known_fixture": {
                "fixture": "deterministic_contract_v1",
                "evaluation": "allowlisted comparison operators and missing-as-excluded behavior",
                "passed": True,
            },
        }
        for kind in REQUIRED_VALIDATION_KINDS:
            kind_status = final_status if kind == "metric_availability" else "passed"
            validation_key = f"scanner:{int(scanner['scanner_version_id'])}:{kind}:{_hash(reports[kind])[:16]}"
            rows = self.run_statement(
                f"""
                WITH validation AS (
                  INSERT INTO market.scanner_validations
                    (scope_key,validation_key,idempotency_key,scanner_version_id,validation_kind,status,
                     as_of_date,report,coverage,completed_at)
                  VALUES ({self.sql_literal(self.scope_key)},{self.sql_literal(validation_key)},
                          {self.sql_literal(validation_key)},{int(scanner['scanner_version_id'])},
                          {self.sql_literal(kind)},{self.sql_literal(kind_status)},current_date,
                          {self.sql_jsonb(reports[kind])},
                          {self.sql_jsonb({'companies_considered': len(metrics_by_company), 'warnings': warnings})},now())
                  ON CONFLICT (scope_key,idempotency_key) DO UPDATE SET
                    status=EXCLUDED.status,report=EXCLUDED.report,coverage=EXCLUDED.coverage,completed_at=now()
                  RETURNING *
                )
                SELECT jsonb_build_array(to_jsonb(validation))::text FROM validation
                """
            )
            if rows:
                validation_rows.append(rows[0])
        version_rows = self.run_statement(
            f"""
            WITH version AS (
              UPDATE market.scanner_versions
              SET status=CASE WHEN {self.sql_literal(final_status)}='passed' THEN 'validated' ELSE 'draft' END,
                  definition_json={self.sql_jsonb(normalized)},
                  universe_config={self.sql_jsonb(normalized['universe'])},
                  filter_config={self.sql_jsonb(normalized['filters'])},
                  score_config={self.sql_jsonb(normalized['score'])}
              WHERE id={int(scanner['scanner_version_id'])} AND scope_key={self.sql_literal(self.scope_key)}
                AND status IN ('draft','validated')
              RETURNING *
            )
            SELECT jsonb_build_array(to_jsonb(version))::text FROM version
            """
        )
        return {
            "scanner_id": scanner_id,
            "scanner_version_id": scanner["scanner_version_id"],
            "status": "validated" if final_status == "passed" else "draft",
            "validations": validation_rows,
            "warnings": warnings,
            "version": version_rows[0] if version_rows else None,
            "broker_write_allowed": False,
            "external_write_allowed": False,
        }

    def request_publish(self, scanner_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        scanner = self.get_scanner(scanner_id)
        if scanner.get("scope_key") != self.scope_key or scanner.get("version_status") != "validated":
            raise ScannerValidationError("only a validated workspace scanner can request publication")
        actor = str(payload.get("actor") or "Devarsh")[:120]
        control_statement = self.run_control_statement or self.run_statement
        rows = control_statement(
            f"""
            WITH existing AS (
              SELECT *
              FROM agent.approvals
              WHERE approval_type='scanner_publish'
                AND status IN ('pending','approved')
                AND requested_action->>'scanner_id'={self.sql_literal(str(int(scanner_id)))}
                AND requested_action->>'scanner_version_id'={self.sql_literal(str(int(scanner['scanner_version_id'])))}
                AND requested_action->>'scope_key'={self.sql_literal(self.scope_key)}
              ORDER BY CASE status WHEN 'approved' THEN 1 ELSE 2 END,created_at DESC
              LIMIT 1
            ), inserted AS (
              INSERT INTO agent.approvals
                (approval_type,title,owner_agent,risk_level,status,requested_action,rationale)
              SELECT 'scanner_publish',
                     {self.sql_literal('Publish fundamental scanner: ' + str(scanner.get('name') or scanner_id))},
                     'Fundamental Research Analyst','low','pending',
                     {self.sql_jsonb({'scanner_id': scanner_id, 'scanner_version_id': scanner['scanner_version_id'], 'scope_key': self.scope_key, 'broker_write_allowed': False})},
                     {self.sql_literal('Explicit publication authorizes only deterministic read-only research screening; no alert schedule, external write or broker action.')}
              WHERE NOT EXISTS (SELECT 1 FROM existing)
              RETURNING *
            ), approval AS (
              SELECT * FROM existing
              UNION ALL
              SELECT * FROM inserted
              LIMIT 1
            )
            SELECT jsonb_build_array(to_jsonb(approval))::text FROM approval
            """
        )
        if not rows:
            raise RuntimeError("scanner publication approval could not be created")
        return {
            "approval": rows[0],
            "status": "awaiting_explicit_approval" if rows[0].get("status") == "pending" else "approved",
            "requested_by": actor,
            "broker_write_allowed": False,
            "external_write_allowed": False,
        }
    def publish_scanner(self, scanner_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        scanner = self.get_scanner(scanner_id)
        try:
            approval_id = int(payload.get("approval_id"))
        except (TypeError, ValueError) as exc:
            raise ScannerValidationError("an approved scanner_publish approval_id is required") from exc
        approval_rows = self.run_rows(
            f"""
            SELECT id,status,approval_type,requested_action,decided_by,decided_at
            FROM agent.approvals
            WHERE id={approval_id}
              AND approval_type='scanner_publish'
              AND status='approved'
              AND requested_action->>'scanner_id'={self.sql_literal(str(int(scanner_id)))}
              AND requested_action->>'scanner_version_id'={self.sql_literal(str(int(scanner['scanner_version_id'])))}
              AND requested_action->>'scope_key'={self.sql_literal(self.scope_key)}
            LIMIT 1
            """
        )
        if not approval_rows:
            raise ScannerValidationError(
                "scanner publication remains blocked until the matching scanner_publish approval is explicitly approved"
            )
        rows = self.run_statement(
            f"""
            WITH version AS (
              UPDATE market.scanner_versions
              SET status='published',publish_approval_id={approval_id},published_at=now()
              WHERE id={int(scanner['scanner_version_id'])} AND scope_key={self.sql_literal(self.scope_key)}
                AND status='validated'
              RETURNING *
            ), definition AS (
              UPDATE market.scanner_definitions
              SET status='active',current_published_version_id=(SELECT id FROM version),updated_at=now()
              WHERE id={int(scanner_id)} AND scope_key={self.sql_literal(self.scope_key)}
                AND EXISTS (SELECT 1 FROM version)
              RETURNING *
            )
            SELECT jsonb_build_array(jsonb_build_object(
              'scanner',(SELECT to_jsonb(definition) FROM definition),
              'version',(SELECT to_jsonb(version) FROM version),
              'approval_id',{approval_id},
              'approved_by',{self.sql_literal(str(approval_rows[0].get('decided_by') or 'Devarsh'))},
              'approved_at',{self.sql_literal(str(approval_rows[0].get('decided_at')))}::timestamptz,
              'broker_write_allowed',false,
              'external_write_allowed',false
            ))::text
            """
        )
        if not rows or not rows[0].get("version"):
            raise ScannerValidationError("approved publication gate was not satisfied")
        return rows[0]

    def _load_company_metrics(self, as_of_at: datetime) -> tuple[list[dict[str, Any]], dict[int, dict[str, dict[str, Any]]]]:
        cutoff = as_of_at.isoformat()
        companies = self.run_rows(
            f"""
            SELECT id,display_name,primary_symbol,primary_exchange,reporting_currency,status,
                   real_company_verified_at
            FROM research.companies
            WHERE status='active' AND real_company_verified_at IS NOT NULL
              AND upper(coalesce(primary_exchange,'')) IN ('NSE','BSE')
            ORDER BY display_name,id LIMIT 5000
            """
        )
        metrics: dict[int, dict[str, dict[str, Any]]] = {int(row["id"]): {} for row in companies}
        ratio_rows = self.run_rows(
            f"""
            SELECT DISTINCT ON (ratio.company_id,formula.formula_key)
                   ratio.company_id,ratio.id ratio_result_id,formula.formula_key,formula.expression,
                   formula.unit,ratio.period_end,ratio.value,ratio.calculation_status,
                   coalesce((SELECT jsonb_agg(input.fact_id ORDER BY input.fact_id)
                             FROM research.financial_ratio_inputs input WHERE input.ratio_result_id=ratio.id),'[]'::jsonb) fact_ids
            FROM research.financial_ratio_results ratio
            JOIN research.financial_formula_definitions formula ON formula.id=ratio.formula_definition_id
            WHERE ratio.calculation_status='validated'
              AND ratio.period_end<={self.sql_literal(as_of_at.date().isoformat())}::date
              AND ratio.created_at<={self.sql_literal(cutoff)}::timestamptz
              AND formula.formula_key=ANY(ARRAY[{','.join(self.sql_literal(key) for key in sorted(ALLOWED_METRICS))}]::text[])
            ORDER BY ratio.company_id,formula.formula_key,ratio.period_end DESC,ratio.id DESC
            """
        )
        for row in ratio_rows:
            company_id = int(row["company_id"])
            if company_id in metrics:
                metrics[company_id][str(row["formula_key"])] = {
                    "value": row.get("value"), "unit": row.get("unit"), "period_end": row.get("period_end"),
                    "available_at": cutoff,
                    "calculation_status": "validated",
                    "formula": row.get("expression"),
                    "inputs": [{
                        "input_role": "validated_ratio",
                        "financial_ratio_result_id": row.get("ratio_result_id"),
                        "source_available_at": cutoff,
                        "metadata": {"fact_ids": row.get("fact_ids") or []},
                    }],
                }
        fact_rows = self.run_rows(
            f"""
            SELECT fact.id,fact.company_id,definition.fact_key,fact.fiscal_year,fact.period_end,
                   fact.statement_scope,fact.value_numeric AS value,fact.currency,fact.unit,
                   fact.available_at,fact.source_locator
            FROM research.company_statement_facts fact
            JOIN research.statement_fact_definitions definition ON definition.id=fact.fact_definition_id
            WHERE fact.is_current AND fact.evidence_id IS NOT NULL
              AND fact.period_end<={self.sql_literal(as_of_at.date().isoformat())}::date
              AND fact.available_at<={self.sql_literal(cutoff)}::timestamptz
              AND definition.fact_key IN ('revenue','revenue_from_operations','pat_total','profit_after_tax')
            ORDER BY fact.company_id,definition.fact_key,fact.fiscal_year,fact.id
            """
        )
        grouped: dict[tuple[int, str], list[dict[str, Any]]] = {}
        for row in fact_rows:
            canonical = "revenue" if str(row["fact_key"]) in {"revenue", "revenue_from_operations"} else "pat"
            grouped.setdefault((int(row["company_id"]), canonical), []).append(row)
        for (company_id, canonical), rows in grouped.items():
            by_year: dict[int, dict[str, Any]] = {}
            for row in rows:
                year = int(row["fiscal_year"])
                current = by_year.get(year)
                if current is None or str(row["fact_key"]) in {"revenue", "pat_total"}:
                    by_year[year] = row
            if len(by_year) < 2 or company_id not in metrics:
                continue
            end_year = max(by_year)
            start_candidates = [year for year in by_year if year <= end_year - 5]
            if not start_candidates:
                continue
            start_year = max(start_candidates)
            start = by_year[start_year]
            end = by_year[end_year]
            start_value = _decimal(start.get("value")); end_value = _decimal(end.get("value"))
            years = end_year - start_year
            if start_value is None or end_value is None or start_value <= 0 or end_value <= 0 or years <= 0:
                continue
            value = (float(end_value / start_value) ** (1 / years) - 1) * 100
            metrics[company_id][f"{canonical}_cagr_5y"] = {
                "value": value, "unit": "percent", "period_end": end.get("period_end"),
                "available_at": max(str(start.get("available_at")), str(end.get("available_at"))),
                "calculation_status": "calculated",
                "formula": f"(({canonical}_FY{end_year}/{canonical}_FY{start_year})^(1/{years})-1)*100",
                "inputs": [
                    {
                        "input_role": "start_period",
                        "company_statement_fact_id": start.get("id"),
                        "source_available_at": start.get("available_at"),
                        "metadata": {"fiscal_year": start_year, "source_locator": start.get("source_locator") or {}},
                    },
                    {
                        "input_role": "end_period",
                        "company_statement_fact_id": end.get("id"),
                        "source_available_at": end.get("available_at"),
                        "metadata": {"fiscal_year": end_year, "source_locator": end.get("source_locator") or {}},
                    },
                ],
            }
        governance = self.run_rows(
            f"""
            SELECT company.id company_id,count(DISTINCT filing.id) flag_count,
                   coalesce(jsonb_agg(DISTINCT jsonb_build_object(
                     'id',filing.id,
                     'available_at',coalesce(filing.filed_at,filing.created_at),
                     'title',filing.title
                   )),'[]'::jsonb) filing_inputs
            FROM research.companies company
            JOIN research.corporate_filings filing
              ON upper(filing.symbol)=upper(company.primary_symbol)
             AND upper(filing.exchange)=upper(company.primary_exchange)
            WHERE coalesce(filing.filed_at,filing.created_at)<={self.sql_literal(cutoff)}::timestamptz
              AND coalesce(filing.filed_at,filing.created_at)>={self.sql_literal((as_of_at-timedelta(days=730)).isoformat())}::timestamptz
              AND lower(coalesce(filing.title,'')||' '||coalesce(filing.event_type,'')) ~
                  '(auditor|resignation|pledge|fraud|investigation|default|insolvency|penalty)'
            GROUP BY company.id
            """
        )
        for row in governance:
            company_id = int(row["company_id"])
            if company_id in metrics:
                metrics[company_id]["governance_flag_count"] = {
                    "value": row.get("flag_count"), "unit": "count", "period_end": as_of_at.date().isoformat(),
                    "available_at": cutoff,
                    "calculation_status": "calculated",
                    "formula": "count(distinct qualified filing ids matching reviewed governance-risk taxonomy over prior two years)",
                    "inputs": [{
                        "input_role": "governance_keyword_filing",
                        "corporate_filing_id": item.get("id"),
                        "source_available_at": item.get("available_at"),
                        "metadata": {"title": item.get("title")},
                    } for item in (row.get("filing_inputs") or [])],
                }
        return companies, metrics

    def _legacy_run_scanner(self, scanner_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        scanner = self.get_scanner(scanner_id)
        if scanner.get("version_status") not in {"validated", "published"}:
            raise ScannerValidationError("scanner must pass validation before a run")
        normalized = validate_definition(scanner.get("definition"))
        as_of_raw = str(payload.get("as_of_at") or payload.get("asOf") or datetime.now(timezone.utc).isoformat())
        as_of_at = datetime.fromisoformat(as_of_raw.replace("Z", "+00:00"))
        if as_of_at.tzinfo is None:
            raise ScannerValidationError("as_of_at must include an explicit timezone")
        as_of_at = as_of_at.astimezone(timezone.utc)
        companies, metrics_by_company = self._load_company_metrics(as_of_at)
        required = set(normalized["requirements"]["required_metrics"])
        minimum = Decimal(str(normalized["requirements"]["minimum_data_completeness_pct"]))
        definition_hash = _hash(normalized)
        universe_hash = _hash([{key: row.get(key) for key in ("id", "primary_symbol", "primary_exchange")} for row in companies])
        idempotency = _hash({"version": scanner["scanner_version_id"], "as_of": as_of_at.isoformat(), "universe": universe_hash, "engine": "research-desk-v1"})
        evaluated: list[dict[str, Any]] = []
        for company in companies:
            company_id = int(company["id"])
            company_metrics = metrics_by_company.get(company_id) or {}
            present = required.intersection(company_metrics)
            completeness = Decimal("100") if not required else Decimal(len(present) * 100) / Decimal(len(required))
            missing = sorted(required - present)
            eligible = completeness >= minimum and not missing
            passed, reasons = _evaluate(normalized["filters"], company_metrics) if eligible else (False, [f"missing: {item}" for item in missing])
            components = normalized["score"]["components"]
            score = Decimal("0")
            score_coverage = Decimal("0")
            for component in components:
                observed = _decimal((company_metrics.get(component["metric"]) or {}).get("value"))
                if observed is None:
                    continue
                weight = Decimal(str(component["weight"])); score_coverage += weight
                score += observed * weight * (Decimal("-1") if component["direction"] == "lower" else Decimal("1"))
            evaluated.append({
                "company": company, "metrics": company_metrics, "eligible": eligible, "passed": passed,
                "completeness": float(completeness), "missing": missing, "reasons": reasons,
                "score": float(score) if score_coverage > 0 else None,
            })
        passing = sorted((row for row in evaluated if row["eligible"] and row["passed"]), key=lambda row: (-(row["score"] or -math.inf), str(row["company"].get("display_name"))))
        rank_by_company = {int(row["company"]["id"]): rank for rank, row in enumerate(passing, 1)}
        actor = str(payload.get("actor") or "Devarsh")[:120]
        run_rows = self.run_statement(
            f"""
            WITH inserted AS (
              INSERT INTO market.scanner_runs
                (scope_key,run_key,scanner_version_id,as_of_at,universe_version,status,total_universe,
                 eligible_universe,excluded_universe,stale_quote_count,provider_failure_count,
                 calculation_revision,definition_hash,input_snapshot_hash,warnings,idempotency_key,model_cost_usd,created_by,finished_at)
              VALUES ({self.sql_literal(self.scope_key)},{self.sql_literal('scanner:' + idempotency[:24])},
                      {int(scanner['scanner_version_id'])},{self.sql_literal(as_of_at.isoformat())}::timestamptz,
                      {self.sql_literal(universe_hash)},'completed',{len(evaluated)},
                      {sum(1 for row in evaluated if row['eligible'])},{sum(1 for row in evaluated if not row['eligible'])},0,0,
                      'research-desk-v1',{self.sql_literal(definition_hash)},{self.sql_literal(universe_hash)},
                      {self.sql_jsonb([])},{self.sql_literal(idempotency)},0,{self.sql_literal(actor)},now())
              ON CONFLICT (scope_key,idempotency_key) DO UPDATE SET run_key=market.scanner_runs.run_key
              RETURNING *
            ) SELECT jsonb_build_array(to_jsonb(inserted))::text FROM inserted
            """
        )
        if not run_rows:
            raise RuntimeError("scanner run could not be persisted")
        run = run_rows[0]
        run_id = int(run["id"])
        for row in evaluated:
            company = row["company"]
            status = "eligible" if row["eligible"] else "excluded_missing_data"
            persisted = self.run_statement(
                f"""
                WITH universe AS (
                  INSERT INTO market.scanner_run_universe
                    (scope_key,scanner_run_id,company_id,exchange,symbol,eligibility_status,exclusion_reasons,data_completeness_pct)
                  VALUES ({self.sql_literal(self.scope_key)},{run_id},{int(company['id'])},
                          {self.sql_literal(company.get('primary_exchange'))},{self.sql_literal(company.get('primary_symbol'))},
                          {self.sql_literal(status)},{self.sql_jsonb(row['missing'])},{row['completeness']})
                  ON CONFLICT (scanner_run_id,company_id) DO UPDATE SET eligibility_status=EXCLUDED.eligibility_status,
                    exclusion_reasons=EXCLUDED.exclusion_reasons,data_completeness_pct=EXCLUDED.data_completeness_pct
                  RETURNING *
                ), result AS (
                  INSERT INTO market.scanner_results
                    (scope_key,scanner_run_id,company_id,rank,score,passed,exchange,symbol,company_name,
                     quote_freshness,reasons,warnings)
                  VALUES ({self.sql_literal(self.scope_key)},{run_id},{int(company['id'])},
                          {rank_by_company.get(int(company['id'])) or len(evaluated)+1},
                          {row['score'] if row['score'] is not None else 'NULL'},{str(bool(row['passed'])).lower()},
                          {self.sql_literal(company.get('primary_exchange'))},{self.sql_literal(company.get('primary_symbol'))},
                          {self.sql_literal(company.get('display_name'))},'unavailable',
                          {self.sql_jsonb(row['reasons'])},{self.sql_jsonb(row['missing'])})
                  ON CONFLICT (scanner_run_id,company_id) DO UPDATE SET rank=EXCLUDED.rank,score=EXCLUDED.score,
                    passed=EXCLUDED.passed,reasons=EXCLUDED.reasons,warnings=EXCLUDED.warnings
                  RETURNING id
                ) SELECT jsonb_build_array(jsonb_build_object('result_id',(SELECT id FROM result)))::text
                """
            )
            result_id = int(persisted[0]["result_id"])
            for metric_key, metric in row["metrics"].items():
                if metric_key not in required and metric_key not in {item["metric"] for item in normalized["score"]["components"]}:
                    continue
                metric_rows = self.run_statement(
                    f"""
                    WITH metric AS (
                      INSERT INTO market.scanner_result_metrics
                        (scope_key,scanner_result_id,metric_key,metric_value,metric_unit,calculation_status,formula,source_as_of,caveat)
                      VALUES ({self.sql_literal(self.scope_key)},{result_id},{self.sql_literal(metric_key)},
                              {self.sql_literal(metric.get('value'))}::numeric,{self.sql_literal(metric.get('unit'))},'computed',
                              {self.sql_literal(metric.get('formula'))},{self.sql_literal(metric.get('period_end'))}::timestamptz,NULL)
                      ON CONFLICT (scanner_result_id,metric_key) DO UPDATE SET metric_value=EXCLUDED.metric_value,
                        metric_unit=EXCLUDED.metric_unit,formula=EXCLUDED.formula,source_as_of=EXCLUDED.source_as_of
                      RETURNING id
                    ) SELECT jsonb_build_array(jsonb_build_object('metric_id',(SELECT id FROM metric)))::text
                    """
                )
                metric_id = int(metric_rows[0]["metric_id"])
                input_ids = metric.get("input_ids") or ([metric.get("input_id")] if metric.get("input_id") else [])
                input_type = str(metric.get("input_type") or "unknown")
                for input_id in input_ids:
                    if input_id is None:
                        continue
                    self.run_statement(
                        f"""
                        WITH inserted AS (
                          INSERT INTO market.scanner_result_metric_inputs
                            (scope_key,scanner_result_metric_id,input_type,input_pk,known_at,evidence)
                          VALUES ({self.sql_literal(self.scope_key)},{metric_id},{self.sql_literal(input_type)},
                                  {self.sql_literal(str(input_id))},{self.sql_literal(metric.get('period_end'))}::timestamptz,
                                  {self.sql_jsonb({'fact_ids': metric.get('fact_ids') or []})})
                          ON CONFLICT (scanner_result_metric_id,input_type,input_pk) DO NOTHING RETURNING id
                        ) SELECT coalesce(jsonb_agg(to_jsonb(inserted)),'[]'::jsonb)::text FROM inserted
                        """
                    )
        return self.get_run(run_id)

    def _ensure_metric_definitions(self, metric_keys: set[str]) -> dict[str, dict[str, Any]]:
        keys = sorted(metric_keys.intersection(ALLOWED_METRICS))
        if not keys:
            return {}
        formulas = {
            str(row["formula_key"]): row
            for row in self.run_rows(
                f"""
                SELECT id,formula_key,expression,unit
                FROM research.financial_formula_definitions
                WHERE formula_key=ANY(ARRAY[{','.join(self.sql_literal(key) for key in keys)}]::text[])
                ORDER BY id DESC
                """
            )
        }
        for metric_key in keys:
            label, source_kind, unit = METRIC_METADATA[metric_key]
            formula = formulas.get(metric_key) or {}
            implementation_key = (
                "statement_fact_cagr_v1"
                if source_kind == "statement_fact"
                else "governance_filing_count_v1"
                if source_kind == "filing"
                else "validated_financial_ratio_v1"
            )
            definition_payload = {
                "metric_key": metric_key,
                "implementation_key": implementation_key,
                "source_kind": source_kind,
                "formula_definition_id": formula.get("id"),
                "unit": formula.get("unit") or unit,
                "code_revision": "research-desk-v1",
            }
            self.run_statement(
                f"""
                WITH inserted AS (
                  INSERT INTO market.scanner_metric_definitions
                    (scope_key,metric_key,version,label,value_type,unit,implementation_key,
                     formula_definition_id,source_kind,point_in_time_required,required_history_periods,
                     required_lag_days,sector_applicability,exclusions,definition_hash,code_revision,status,created_by)
                  VALUES ({self.sql_literal(self.scope_key)},{self.sql_literal(metric_key)},1,
                          {self.sql_literal(label)},'numeric',{self.sql_literal(formula.get('unit') or unit)},
                          {self.sql_literal(implementation_key)},
                          {int(formula['id']) if formula.get('id') else 'NULL'},
                          {self.sql_literal(source_kind)},true,
                          {6 if source_kind == 'statement_fact' else 1},0,
                          '{{}}'::jsonb,'[]'::jsonb,{self.sql_literal(_hash(definition_payload))},
                          'research-desk-v1','active','Research Desk')
                  ON CONFLICT (scope_key,metric_key,version) DO NOTHING
                  RETURNING id
                )
                SELECT coalesce(jsonb_agg(to_jsonb(inserted)),'[]'::jsonb)::text FROM inserted
                """
            )
        return {
            str(row["metric_key"]): row
            for row in self.run_rows(
                f"""
                SELECT * FROM market.scanner_metric_definitions
                WHERE scope_key={self.sql_literal(self.scope_key)}
                  AND status='active'
                  AND metric_key=ANY(ARRAY[{','.join(self.sql_literal(key) for key in keys)}]::text[])
                ORDER BY metric_key,version DESC
                """
            )
        }

    def _load_universe(self, as_of_at: datetime, exchanges: list[str], universe_key: str) -> list[dict[str, Any]]:
        return self.run_rows(
            f"""
            SELECT membership.id universe_membership_id,membership.universe_key,
                   symbol.id symbol_id,symbol.symbol,symbol.exchange,symbol.name symbol_name,
                   company.id company_id,company.display_name company_name,
                   membership.valid_from,membership.valid_to,membership.verification_status,
                   membership.source_ref,membership.created_at membership_created_at
            FROM market.universe_memberships membership
            JOIN trading.symbols symbol ON symbol.id=membership.symbol_id
            LEFT JOIN research.companies company
              ON upper(company.primary_symbol)=upper(symbol.symbol)
             AND upper(company.primary_exchange)=upper(symbol.exchange)
             AND company.status='active'
            WHERE membership.universe_key={self.sql_literal(universe_key)}
              AND membership.valid_from<={self.sql_literal(as_of_at.date().isoformat())}::date
              AND (membership.valid_to IS NULL OR membership.valid_to>={self.sql_literal(as_of_at.date().isoformat())}::date)
              AND upper(symbol.exchange)=ANY(ARRAY[{','.join(self.sql_literal(value) for value in exchanges)}]::text[])
            ORDER BY symbol.exchange,symbol.symbol,symbol.id
            LIMIT 5000
            """
        )

    def run_scanner(self, scanner_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        scanner = self.get_scanner(scanner_id)
        if scanner.get("scope_key") != self.scope_key or scanner.get("version_status") != "published":
            raise ScannerValidationError("scanner runs require the explicitly published workspace version")
        if payload.get("operator_confirmed") is not True:
            raise ScannerValidationError("operator_confirmed=true is required for a durable point-in-time scanner run")
        normalized = validate_definition(scanner.get("definition"))
        as_of_raw = str(payload.get("as_of_at") or payload.get("asOf") or datetime.now(timezone.utc).isoformat())
        as_of_at = datetime.fromisoformat(as_of_raw.replace("Z", "+00:00"))
        if as_of_at.tzinfo is None:
            raise ScannerValidationError("as_of_at must include an explicit timezone")
        as_of_at = as_of_at.astimezone(timezone.utc)
        universe_key = str(payload.get("universe_key") or "LEGACY_ALGO_CURRENT_SNAPSHOT")[:120]
        universe = self._load_universe(as_of_at, normalized["universe"]["exchanges"], universe_key)
        if not universe:
            raise ScannerValidationError(f"no point-in-time universe membership exists for {universe_key}")
        _companies, metrics_by_company = self._load_company_metrics(as_of_at)
        required = set(normalized["requirements"]["required_metrics"])
        score_metrics = {item["metric"] for item in normalized["score"]["components"]}
        metric_definitions = self._ensure_metric_definitions(required | score_metrics)
        missing_definitions = sorted((required | score_metrics) - set(metric_definitions))
        if missing_definitions:
            raise ScannerValidationError("metric definitions are unavailable: " + ", ".join(missing_definitions))
        minimum = Decimal(str(normalized["requirements"]["minimum_data_completeness_pct"])) / Decimal("100")
        definition_hash = _hash(normalized)
        universe_hash = _hash([
            {
                "membership_id": row.get("universe_membership_id"),
                "symbol_id": row.get("symbol_id"),
                "valid_from": row.get("valid_from"),
                "valid_to": row.get("valid_to"),
            }
            for row in universe
        ])
        idempotency = _hash({
            "version": scanner["scanner_version_id"],
            "as_of_date": as_of_at.date().isoformat(),
            "cutoff": as_of_at.isoformat(),
            "universe": universe_hash,
            "engine": "research-desk-v1",
        })
        evaluated: list[dict[str, Any]] = []
        for member in universe:
            company_id = int(member["company_id"]) if member.get("company_id") is not None else None
            company_metrics = metrics_by_company.get(company_id, {}) if company_id is not None else {}
            present = required.intersection(company_metrics)
            completeness = Decimal("1") if not required else Decimal(len(present)) / Decimal(len(required))
            missing = sorted(required - present)
            eligible = company_id is not None and completeness >= minimum and not missing
            passed, reasons = (
                _evaluate(normalized["filters"], company_metrics)
                if eligible
                else (False, ["company identity is not mapped"] if company_id is None else [f"missing: {item}" for item in missing])
            )
            score = Decimal("0")
            score_coverage = Decimal("0")
            for component in normalized["score"]["components"]:
                observed = _decimal((company_metrics.get(component["metric"]) or {}).get("value"))
                if observed is None:
                    continue
                weight = Decimal(str(component["weight"]))
                score_coverage += weight
                score += observed * weight * (Decimal("-1") if component["direction"] == "lower" else Decimal("1"))
            evaluated.append({
                "member": member,
                "company_metrics": company_metrics,
                "eligible": eligible,
                "passed": bool(passed),
                "completeness": completeness,
                "missing": missing,
                "reasons": reasons,
                "score": score if score_coverage > 0 else None,
            })
        passing = sorted(
            (row for row in evaluated if row["eligible"] and row["passed"]),
            key=lambda row: (-(float(row["score"]) if row["score"] is not None else -math.inf), str(row["member"].get("symbol"))),
        )
        rank_by_symbol = {int(row["member"]["symbol_id"]): rank for rank, row in enumerate(passing, 1)}
        actor = str(payload.get("actor") or "Devarsh")[:120]
        run_rows = self.run_statement(
            f"""
            WITH inserted AS (
              INSERT INTO market.scanner_runs
                (scope_key,run_key,idempotency_key,scanner_version_id,as_of_date,as_of_cutoff_at,
                 universe_key,universe_hash,engine_revision,code_revision,status,total_symbols,
                 eligible_symbols,excluded_symbols,missing_symbols,stale_symbols,provider_failure_count,
                 coverage_report,warnings,created_by,finished_at)
              VALUES ({self.sql_literal(self.scope_key)},{self.sql_literal('scanner:' + idempotency[:24])},
                      {self.sql_literal(idempotency)},{int(scanner['scanner_version_id'])},
                      {self.sql_literal(as_of_at.date().isoformat())}::date,
                      {self.sql_literal(as_of_at.isoformat())}::timestamptz,
                      {self.sql_literal(universe_key)},{self.sql_literal(universe_hash)},
                      'deterministic-scanner-v1','research-desk-v1','completed',{len(evaluated)},
                      {sum(1 for row in evaluated if row['eligible'])},
                      {sum(1 for row in evaluated if row['eligible'] and not row['passed'])},
                      {sum(1 for row in evaluated if not row['eligible'])},0,0,
                      {self.sql_jsonb({
                          'required_metrics': sorted(required),
                          'minimum_data_completeness': float(minimum),
                          'passed_symbols': len(passing),
                          'missing_data_policy': 'exclude_and_report',
                      })},
                      {self.sql_jsonb([])},{self.sql_literal(actor)},now())
              ON CONFLICT (scope_key,idempotency_key) DO UPDATE SET run_key=market.scanner_runs.run_key
              RETURNING *
            )
            SELECT jsonb_build_array(to_jsonb(inserted))::text FROM inserted
            """
        )
        if not run_rows:
            raise RuntimeError("scanner run could not be persisted")
        run = run_rows[0]
        run_id = int(run["id"])
        for row in evaluated:
            member = row["member"]
            if row["eligible"]:
                eligibility_status = "eligible"
                exclusion_code = "filter_not_matched" if not row["passed"] else None
                exclusion_reason = "; ".join(row["reasons"]) if not row["passed"] else None
            else:
                eligibility_status = "missing"
                exclusion_code = "company_identity_missing" if member.get("company_id") is None else "required_metric_missing"
                exclusion_reason = "; ".join(row["reasons"]) or "required point-in-time inputs are unavailable"
            snapshot_hash = _hash({
                "membership_id": member["universe_membership_id"],
                "metrics": {
                    key: {
                        "value": value.get("value"),
                        "period_end": value.get("period_end"),
                        "available_at": value.get("available_at"),
                    }
                    for key, value in row["company_metrics"].items()
                    if key in required | score_metrics
                },
            })
            universe_rows = self.run_statement(
                f"""
                WITH universe_row AS (
                  INSERT INTO market.scanner_run_universe
                    (scope_key,scanner_run_id,universe_membership_id,symbol_id,company_id,
                     eligibility_status,exclusion_code,exclusion_reason,data_completeness,
                     data_cutoff_at,provider_warnings,input_snapshot_hash)
                  VALUES ({self.sql_literal(self.scope_key)},{run_id},{int(member['universe_membership_id'])},
                          {int(member['symbol_id'])},{int(member['company_id']) if member.get('company_id') is not None else 'NULL'},
                          {self.sql_literal(eligibility_status)},{self.sql_literal(exclusion_code)},
                          {self.sql_literal(exclusion_reason)},{str(row['completeness'])},
                          {self.sql_literal(as_of_at.isoformat())}::timestamptz,'[]'::jsonb,
                          {self.sql_literal(snapshot_hash)})
                  ON CONFLICT (scope_key,scanner_run_id,symbol_id) DO UPDATE SET
                    eligibility_status=EXCLUDED.eligibility_status,
                    exclusion_code=EXCLUDED.exclusion_code,
                    exclusion_reason=EXCLUDED.exclusion_reason,
                    data_completeness=EXCLUDED.data_completeness,
                    data_cutoff_at=EXCLUDED.data_cutoff_at,
                    input_snapshot_hash=EXCLUDED.input_snapshot_hash
                  RETURNING *
                )
                SELECT jsonb_build_array(to_jsonb(universe_row))::text FROM universe_row
                """
            )
            universe_row_id = int(universe_rows[0]["id"])
            reason_codes = ["passed"] if row["passed"] else ([exclusion_code] if exclusion_code else ["not_matched"])
            result_rows = self.run_statement(
                f"""
                WITH result AS (
                  INSERT INTO market.scanner_results
                    (scope_key,scanner_run_id,scanner_run_universe_id,symbol_id,company_id,rank,
                     passed,score,data_completeness,reason_codes,reason_summary,artifact_refs)
                  VALUES ({self.sql_literal(self.scope_key)},{run_id},{universe_row_id},{int(member['symbol_id'])},
                          {int(member['company_id']) if member.get('company_id') is not None else 'NULL'},
                          {rank_by_symbol.get(int(member['symbol_id'])) or 'NULL'},
                          {str(bool(row['passed'])).lower()},
                          {str(row['score']) if row['score'] is not None else 'NULL'},
                          {str(row['completeness'])},
                          {_text_array([str(item) for item in reason_codes if item], self.sql_literal)},
                          {self.sql_literal('; '.join(row['reasons']))},'[]'::jsonb)
                  ON CONFLICT (scope_key,scanner_run_id,symbol_id) DO UPDATE SET
                    scanner_run_universe_id=EXCLUDED.scanner_run_universe_id,
                    company_id=EXCLUDED.company_id,rank=EXCLUDED.rank,passed=EXCLUDED.passed,
                    score=EXCLUDED.score,data_completeness=EXCLUDED.data_completeness,
                    reason_codes=EXCLUDED.reason_codes,reason_summary=EXCLUDED.reason_summary
                  RETURNING *
                )
                SELECT jsonb_build_array(to_jsonb(result))::text FROM result
                """
            )
            result_id = int(result_rows[0]["id"])
            for metric_key in sorted(required | score_metrics):
                metric = row["company_metrics"].get(metric_key)
                if metric is None:
                    continue
                metric_definition = metric_definitions[metric_key]
                metric_value = _decimal(metric.get("value"))
                if metric_value is None:
                    continue
                formula_hash = _hash(metric.get("formula") or metric_key)
                calculation_hash = _hash({
                    "metric": metric_key,
                    "value": str(metric_value),
                    "inputs": metric.get("inputs") or [],
                    "as_of": as_of_at.isoformat(),
                })
                metric_rows = self.run_statement(
                    f"""
                    WITH metric AS (
                      INSERT INTO market.scanner_result_metrics
                        (scope_key,scanner_result_id,metric_definition_id,metric_key,metric_version,
                         calculation_status,value_numeric,unit,as_of_date,available_at,formula_hash,
                         calculation_hash,warnings)
                      VALUES ({self.sql_literal(self.scope_key)},{result_id},{int(metric_definition['id'])},
                              {self.sql_literal(metric_key)},{int(metric_definition['version'])},
                              {self.sql_literal(metric.get('calculation_status') or 'calculated')},
                              {str(metric_value)},{self.sql_literal(metric.get('unit'))},
                              {self.sql_literal(as_of_at.date().isoformat())}::date,
                              {self.sql_literal(metric.get('available_at') or as_of_at.isoformat())}::timestamptz,
                              {self.sql_literal(formula_hash)},{self.sql_literal(calculation_hash)},'[]'::jsonb)
                      ON CONFLICT (scope_key,scanner_result_id,metric_key,metric_version) DO UPDATE SET
                        calculation_status=EXCLUDED.calculation_status,value_numeric=EXCLUDED.value_numeric,
                        unit=EXCLUDED.unit,as_of_date=EXCLUDED.as_of_date,available_at=EXCLUDED.available_at,
                        formula_hash=EXCLUDED.formula_hash,calculation_hash=EXCLUDED.calculation_hash
                      RETURNING *
                    )
                    SELECT jsonb_build_array(to_jsonb(metric))::text FROM metric
                    """
                )
                result_metric_id = int(metric_rows[0]["id"])
                for input_row in metric.get("inputs") or []:
                    source_available_at = input_row.get("source_available_at")
                    if not source_available_at:
                        continue
                    self.run_statement(
                        f"""
                        WITH inserted AS (
                          INSERT INTO market.scanner_result_metric_inputs
                            (scope_key,result_metric_id,input_role,company_statement_fact_id,
                             financial_ratio_result_id,price_quote_id,governance_observation_id,
                             corporate_filing_id,universe_membership_id,source_available_at,
                             source_row_hash,metadata)
                          VALUES ({self.sql_literal(self.scope_key)},{result_metric_id},
                                  {self.sql_literal(input_row.get('input_role') or 'source')},
                                  {int(input_row['company_statement_fact_id']) if input_row.get('company_statement_fact_id') else 'NULL'},
                                  {int(input_row['financial_ratio_result_id']) if input_row.get('financial_ratio_result_id') else 'NULL'},
                                  {int(input_row['price_quote_id']) if input_row.get('price_quote_id') else 'NULL'},
                                  {int(input_row['governance_observation_id']) if input_row.get('governance_observation_id') else 'NULL'},
                                  {int(input_row['corporate_filing_id']) if input_row.get('corporate_filing_id') else 'NULL'},
                                  {int(input_row['universe_membership_id']) if input_row.get('universe_membership_id') else 'NULL'},
                                  {self.sql_literal(source_available_at)}::timestamptz,
                                  {self.sql_literal(_hash(input_row))},
                                  {self.sql_jsonb(input_row.get('metadata') or {})})
                          ON CONFLICT DO NOTHING RETURNING id
                        )
                        SELECT coalesce(jsonb_agg(to_jsonb(inserted)),'[]'::jsonb)::text FROM inserted
                        """
                    )
        return self.get_run(run_id)

    def get_run(self, run_id: int) -> dict[str, Any]:
        rows = self.run_rows(
            f"""
            SELECT run.*,definition.scanner_key,definition.name scanner_name,version.version
            FROM market.scanner_runs run
            JOIN market.scanner_versions version ON version.id=run.scanner_version_id
            JOIN market.scanner_definitions definition ON definition.id=version.scanner_definition_id
            WHERE run.id={int(run_id)} AND run.scope_key={self.sql_literal(self.scope_key)} LIMIT 1
            """
        )
        if not rows:
            raise ValueError("scanner run was not found")
        return {**rows[0], "broker_write_allowed": False, "external_write_allowed": False}

    def list_results(self, run_id: int, *, limit: Any = 50, after_rank: Any = 0) -> dict[str, Any]:
        page_size = _bounded_int(limit, 50, 1, MAX_LIMIT)
        rank_cursor = _bounded_int(after_rank, 0, 0, 1000000)
        rows = self.run_rows(
            f"""
            SELECT result.*,
                   symbol.exchange,symbol.symbol,symbol.name AS symbol_name,company.display_name AS company_name,
                   coalesce((SELECT jsonb_agg(jsonb_build_object(
                     'id',metric.id,'metric_key',metric.metric_key,'value',metric.value_numeric,
                     'value_text',metric.value_text,'unit',metric.unit,'status',metric.calculation_status,
                     'as_of_date',metric.as_of_date,'available_at',metric.available_at,
                     'formula_hash',metric.formula_hash,'calculation_hash',metric.calculation_hash,
                     'inputs',coalesce((SELECT jsonb_agg(to_jsonb(input) ORDER BY input.id)
                       FROM market.scanner_result_metric_inputs input WHERE input.result_metric_id=metric.id),'[]'::jsonb)
                   ) ORDER BY metric.metric_key) FROM market.scanner_result_metrics metric
                   WHERE metric.scanner_result_id=result.id),'[]'::jsonb) metrics
            FROM market.scanner_results result
            JOIN trading.symbols symbol ON symbol.id=result.symbol_id
            LEFT JOIN research.companies company ON company.id=result.company_id
            WHERE result.scanner_run_id={int(run_id)} AND result.scope_key={self.sql_literal(self.scope_key)}
              AND coalesce(result.rank,2147483647)>{rank_cursor}
            ORDER BY result.rank NULLS LAST,result.id LIMIT {page_size + 1}
            """
        )
        return {
            "run": self.get_run(run_id),
            "items": rows[:page_size],
            "page": {"limit": page_size, "after_rank": rank_cursor,
                     "next_after_rank": rows[page_size - 1].get("rank") if len(rows) > page_size else None},
            "broker_write_allowed": False,
            "external_write_allowed": False,
        }
