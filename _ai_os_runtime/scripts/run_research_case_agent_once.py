#!/usr/bin/env python3
"""Run at most one approved public-company Research Case model step."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
RUNTIME_ROOT = SCRIPT_DIR.parent
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))
if str(RUNTIME_ROOT / "api") not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT / "api"))

from api.ai_os_api_server import openrouter_chat  # noqa: E402
from api.research_case_agent_runtime import run_next_research_case_model  # noqa: E402
from api.research_case_source_runtime import run_source_once  # noqa: E402
from api.research_case_report import retry_pending_research_case_report  # noqa: E402
from run_agent_worker_once import psql_json, psql_text, sql_jsonb, sql_literal  # noqa: E402


def research_openrouter_chat(model_name: str, prompt: str, system_prompt: str | None = None):
    """Use a bounded structured response large enough for the governed research contract."""
    return openrouter_chat(
        model_name,
        prompt,
        system_prompt,
        max_completion_tokens=3200,
        json_object=True,
    )


def psql_json_statement(sql: str):
    value = json.loads(psql_text(sql) or "[]")
    if not isinstance(value, list):
        raise RuntimeError("Research Case statement did not return a JSON array")
    return value


def run_once():
    source_result = run_source_once(
        run_statement=psql_json_statement,
        sql_literal=sql_literal,
        sql_jsonb=sql_jsonb,
    )
    if source_result.get("status") != "idle":
        return source_result
    model_result = run_next_research_case_model(
        run_rows=psql_json,
        run_statement=psql_json_statement,
        sql_literal=sql_literal,
        sql_jsonb=sql_jsonb,
        openrouter_chat=research_openrouter_chat,
    )
    if model_result.get("status") != "idle":
        return model_result
    return retry_pending_research_case_report()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = run_once()
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True, default=str))
    return 0 if result.get("status") not in {"failed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
