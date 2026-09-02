from __future__ import annotations

import sys
from pathlib import Path

import pytest

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME_ROOT))

from services.scanner_engine.service import (  # noqa: E402
    GLOBAL_SCOPE_KEY,
    FundamentalScannerService,
    ScannerValidationError,
    _evaluate,
    validate_definition,
)


def valid_definition():
    return {
        "api_version": "aios.scanner/v1",
        "universe": {"countries": ["IN"], "exchanges": ["NSE", "BSE"]},
        "requirements": {
            "required_metrics": ["roce_proxy", "debt_to_equity"],
            "minimum_data_completeness_pct": 100,
        },
        "filters": {
            "all": [
                {"metric": "roce_proxy", "operator": "gte", "value": 18},
                {"metric": "debt_to_equity", "operator": "lte", "value": 0.5},
            ]
        },
        "score": {"components": [{"metric": "roce_proxy", "weight": 1, "direction": "higher"}]},
    }


def test_valid_definition_is_canonical_and_allowlisted():
    normalized = validate_definition(valid_definition())
    assert normalized["api_version"] == "aios.scanner/v1"
    assert normalized["universe"]["exchanges"] == ["BSE", "NSE"]
    assert normalized["requirements"]["missing_data_policy"] == "exclude_and_report"


def test_arbitrary_metric_and_operator_are_rejected():
    definition = valid_definition()
    definition["filters"]["all"][0] = {"metric": "price); DROP TABLE x;--", "operator": "eval", "value": 1}
    with pytest.raises(ScannerValidationError):
        validate_definition(definition)


def test_condition_evaluation_reports_missing_instead_of_zero_fill():
    node = validate_definition(valid_definition())["filters"]
    passed, reasons = _evaluate(node, {"roce_proxy": {"value": "24.5"}})
    assert passed is False
    assert "debt_to_equity: missing" in reasons


def test_condition_evaluation_passes_real_values():
    node = validate_definition(valid_definition())["filters"]
    passed, reasons = _evaluate(node, {
        "roce_proxy": {"value": "24.5"},
        "debt_to_equity": {"value": "0.12"},
    })
    assert passed is True
    assert all("pass" in reason for reason in reasons)

def scanner_service(*, run_rows=lambda _sql: [], run_statement=lambda _sql: []):
    return FundamentalScannerService(
        run_rows=run_rows,
        run_statement=run_statement,
        sql_literal=lambda value: "'" + str(value).replace("'", "''") + "'",
        sql_jsonb=lambda _value: "'{}'::jsonb",
    )


def test_valid_global_template_clone_creates_one_workspace_draft_with_provenance():
    template = {
        "id": 41,
        "scope_key": GLOBAL_SCOPE_KEY,
        "scanner_key": "research_quality_compounders",
        "name": "Quality compounders",
        "description": "Supported deterministic template",
        "version": 1,
        "definition_hash": "a" * 64,
        "definition": valid_definition(),
    }
    responses = iter([[template], []])
    service = scanner_service(run_rows=lambda _sql: next(responses))
    captured = {}

    def create(payload):
        captured.update(payload)
        return {"created": True, "scanner": {"id": 91}}

    service.create_draft = create  # type: ignore[method-assign]
    result = service.clone_template(41, {"actor": "Test"})

    assert result["created"] is True
    assert captured["definition"]["api_version"] == "aios.scanner/v1"
    assert captured["metadata"]["cloned_from_scanner_id"] == 41
    assert captured["metadata"]["cloned_from_definition_hash"] == "a" * 64
    assert "workspace_copy" in captured["tags"]
    assert result["broker_write_allowed"] is False


def test_invalid_legacy_global_template_clone_writes_nothing():
    template = {
        "id": 42,
        "scope_key": GLOBAL_SCOPE_KEY,
        "scanner_key": "damodaran_value",
        "definition": {"state": "draft_template", "executable": False},
    }
    statements = []
    service = scanner_service(
        run_rows=lambda _sql: [template],
        run_statement=lambda sql: statements.append(sql) or [],
    )
    with pytest.raises(ScannerValidationError, match="api_version"):
        service.clone_template(42, {})
    assert statements == []


def test_workspace_scanner_cannot_be_cloned_as_template():
    service = scanner_service(run_rows=lambda _sql: [{
        "id": 9,
        "scope_key": "owner:devarsh",
        "definition": valid_definition(),
    }])
    with pytest.raises(ScannerValidationError, match="global scanner template"):
        service.clone_template(9, {})


def test_create_draft_is_idempotent_for_same_canonical_definition_hash():
    statements = []
    service = scanner_service(run_statement=lambda sql: statements.append(sql) or [{"created": False}])
    result = service.create_draft({
        "name": "Repeatable quality screen",
        "scanner_key": "repeatable_quality",
        "definition": valid_definition(),
    })
    sql = statements[0]
    assert "ON CONFLICT (scope_key,scanner_definition_id,definition_hash) DO NOTHING" in sql
    assert "'created',EXISTS(SELECT 1 FROM inserted_version)" in sql
    assert result["created"] is False


def test_natural_language_debt_score_uses_lower_direction():
    captured = {}
    service = scanner_service()
    service.create_draft = lambda payload: captured.update(payload) or {"created": True}  # type: ignore[method-assign]
    service.create_from_natural_language({
        "instruction": "Find companies with revenue growth above 12 and debt to equity below 0.5",
    })
    components = captured["definition"]["score"]["components"]
    directions = {component["metric"]: component["direction"] for component in components}
    assert directions["debt_to_equity"] == "lower"
    assert directions["revenue_cagr_5y"] == "higher"


def test_publish_request_reuses_matching_pending_or_approved_approval():
    statements = []
    service = scanner_service(
        run_statement=lambda sql: statements.append(sql) or [{"id": 77, "status": "pending"}],
    )
    service.get_scanner = lambda _scanner_id: {  # type: ignore[method-assign]
        "scope_key": "owner:devarsh",
        "version_status": "validated",
        "scanner_version_id": 55,
        "name": "Quality",
    }
    result = service.request_publish(12, {})
    assert result["approval"]["id"] == 77
    assert "WITH existing AS" in statements[0]
    assert "WHERE NOT EXISTS (SELECT 1 FROM existing)" in statements[0]


def test_durable_scanner_run_requires_explicit_operator_confirmation():
    service = scanner_service()
    service.get_scanner = lambda _scanner_id: {  # type: ignore[method-assign]
        "scope_key": "owner:devarsh",
        "version_status": "published",
        "definition": valid_definition(),
    }
    with pytest.raises(ScannerValidationError, match="operator_confirmed=true"):
        service.run_scanner(5, {})


def test_migration_adds_only_copyable_supported_templates_and_starts_no_run():
    migration = (RUNTIME_ROOT / "postgres" / "init" / "250_executable_fundamental_scanner_templates_v1.sql").read_text()
    assert "FROM seed\nJOIN definitions definition" in migration
    for scanner_key in (
        "research_quality_compounders",
        "research_cash_flow_quality",
        "research_earnings_margin_acceleration",
        "research_balance_sheet_resilience",
    ):
        assert scanner_key in migration
    assert "INSERT INTO market.scanner_runs" not in migration
    assert '"scanner_runs_started":false' in migration
    assert "version.id=alert.scanner_version_id" not in migration
    assert "run.id=alert.scanner_run_id" in migration
    assert "version.id=run.scanner_version_id" in migration
