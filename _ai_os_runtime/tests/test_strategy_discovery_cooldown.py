from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME_ROOT / "scripts"))

from run_strategy_discovery import recent_optimizer


CANDIDATE = {
    "opportunity_fingerprint": "opp_v2:abc",
    "source_fingerprint": "src_v2:def",
}


def test_completed_optimizer_is_reused() -> None:
    with patch(
        "run_strategy_discovery.fetch_json",
        return_value=[{"status": "completed", "run_key": "prior", "workflow_run_id": 7}],
    ):
        result = recent_optimizer(CANDIDATE, 168)
    assert result is not None
    assert result["status"] == "reused"
    assert result["run_key"] == "prior"


def test_unchanged_failed_optimizer_is_deferred() -> None:
    with patch(
        "run_strategy_discovery.fetch_json",
        return_value=[
            {
                "status": "failed",
                "run_key": "prior-failure",
                "workflow_run_id": 8,
                "failure_reason": "data-quality gate failed",
            }
        ],
    ):
        result = recent_optimizer(CANDIDATE, 168)
    assert result is not None
    assert result["status"] == "deferred_unchanged_failure"
    assert result["previous_status"] == "failed"
    assert "retry after source evidence changes" in result["reuse_reason"]
