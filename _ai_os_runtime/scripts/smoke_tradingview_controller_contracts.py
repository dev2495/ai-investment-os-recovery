#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
API_MODULE = RUNTIME_ROOT / "api" / "ai_os_api_server.py"
CONTROLLER = RUNTIME_ROOT / "scripts" / "execute_tradingview_chart_action.mjs"
ARTIFACT_ROOT = Path(os.environ.get("AI_OS_ARTIFACT_ROOT", "/Volumes/Devarsh SSD/AI OS Data/artifacts"))


def load_api_module():
    spec = importlib.util.spec_from_file_location("ai_os_api_server_contracts", API_MODULE)
    if spec is None or spec.loader is None:
        raise RuntimeError("AI OS API module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def compile_plan(module, template_key: str, action_kind: str, payload: dict) -> dict:
    template = {
        "template_key": template_key,
        "action_kind": action_kind,
        "default_exchange": "NSE",
        "default_timeframe": "D",
    }
    symbols = [str(payload.get("symbol") or payload.get("underlying") or payload.get("leg_a") or "")]
    return module.compile_tradingview_template_plan(template, payload, symbols)


def main() -> int:
    module = load_api_module()
    ratio = compile_plan(
        module,
        "relative_strength_ratio_chart",
        "formula_chart_request",
        {"symbol": "RELIANCE", "benchmark": "NSE:NIFTY", "exchange": "NSE", "timeframe": "D"},
    )
    spread = compile_plan(
        module,
        "spread_pair_formula_chart",
        "formula_chart_request",
        {"leg_a": "RELIANCE", "leg_b": "TCS", "hedge_ratio": "0.75", "exchange": "NSE", "timeframe": "D"},
    )
    straddle = compile_plan(
        module,
        "option_straddle_four_pane",
        "option_straddle_layout_request",
        {
            "underlying": "NIFTY",
            "call_symbol": "NIFTY_CALL_CONTRACT",
            "put_symbol": "NIFTY_PUT_CONTRACT",
            "expiry": "2026-07-30",
            "strike": "25000",
            "exchange": "NSE",
            "timeframe": "D",
        },
    )
    assert ratio["execution_ready"] and ratio["symbol_expression"] == "100*NSE:RELIANCE/NSE:NIFTY"
    assert spread["execution_ready"] and "0.75*NSE:TCS" in spread["symbol_expression"]
    assert straddle["execution_ready"] and straddle["fulfillment"] == "complete_four_chart_evidence_board"
    assert len(straddle["panes"]) == 4 and all(pane.get("url") for pane in straddle["panes"])

    controller_check = subprocess.run(
        ["node", "--check", str(CONTROLLER)],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if controller_check.returncode != 0:
        raise RuntimeError(controller_check.stderr or controller_check.stdout)

    evidence = sorted(
        (ARTIFACT_ROOT / "tradingview").glob("**/*-option-straddle-four-pane.png"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    artifact = None
    if evidence:
        analysis = subprocess.run(
            ["node", str(CONTROLLER), "--analyze-file", str(evidence[0])],
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        if analysis.returncode != 0:
            raise RuntimeError(analysis.stderr or analysis.stdout)
        artifact = {"path": str(evidence[0]), "analysis": json.loads(analysis.stdout)}
        if artifact["analysis"].get("status") != "passed":
            raise RuntimeError(
                f"latest four-pane TradingView artifact failed quality validation: {artifact['analysis']}"
            )

    print(json.dumps({
        "status": "passed",
        "formula_plans": 2,
        "straddle_panes": len(straddle["panes"]),
        "controller_syntax": "passed",
        "latest_four_pane_artifact": artifact,
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
