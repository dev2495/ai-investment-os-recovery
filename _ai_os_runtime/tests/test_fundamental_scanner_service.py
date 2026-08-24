from __future__ import annotations

import sys
from pathlib import Path

import pytest

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME_ROOT))

from services.scanner_engine.service import (  # noqa: E402
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
