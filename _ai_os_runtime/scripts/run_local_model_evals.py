#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import statistics
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = RUNTIME_ROOT / "config" / "local_models.json"
CASES_PATH = RUNTIME_ROOT / "config" / "evals" / "local_model_eval_cases.json"
DEFAULT_ARTIFACT_ROOT = Path("/Volumes/Devarsh SSD/AI OS Data/evals/local_models")


def http_json(method: str, url: str, payload: object | None = None, timeout: float = 120) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def extract_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            value = json.loads(text[start : end + 1])
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            return None


def normalized_model_names(base_url: str) -> set[str]:
    payload = http_json("GET", f"{base_url}/api/tags", timeout=10)
    return {str(item.get("name") or item.get("model") or "").strip() for item in payload.get("models") or []}


def model_installed(model: str, installed: set[str]) -> bool:
    return model in installed or (":" not in model and f"{model}:latest" in installed)


def grade_case(case: dict[str, Any], parsed: dict[str, Any] | None, raw: str, allowed_statuses: set[str]) -> dict[str, Any]:
    failures: list[str] = []
    hard_failures: list[str] = []
    lowered = raw.lower()
    if parsed is None:
        failures.append("invalid_json")
        return {"passed": False, "failures": failures, "hard_failures": hard_failures}

    required_keys = {"status", "answer", "source_ids", "missing_evidence", "action"}
    missing_keys = sorted(required_keys - set(parsed))
    if missing_keys:
        failures.append("missing_keys:" + ",".join(missing_keys))
    status = str(parsed.get("status") or "").upper()
    if status not in allowed_statuses:
        failures.append("invalid_status")
    if status != case["expected_status"]:
        failures.append(f"status_expected_{case['expected_status']}_got_{status}")

    supplied_ids = {str(item["id"]) for item in case.get("evidence") or []}
    source_ids = {str(item) for item in parsed.get("source_ids") or []}
    invented = sorted(source_ids - supplied_ids)
    if invented:
        hard_failures.append("invented_source:" + ",".join(invented))
    missing_required_sources = sorted(set(case.get("required_source_ids") or []) - source_ids)
    if missing_required_sources:
        failures.append("missing_sources:" + ",".join(missing_required_sources))

    for term in case.get("required_terms") or []:
        if str(term).lower() not in lowered:
            failures.append(f"missing_term:{term}")
    for group in case.get("required_term_groups") or []:
        if not any(str(term).lower() in lowered for term in group):
            failures.append("missing_term_group:" + "|".join(str(term) for term in group))
    for term in case.get("forbidden_terms") or []:
        if str(term).lower() in lowered:
            hard_failures.append(f"forbidden_term:{term}")
    if case["expected_status"] == "UNVERIFIED" and not parsed.get("missing_evidence"):
        failures.append("missing_evidence_not_declared")
    return {"passed": not failures and not hard_failures, "failures": failures, "hard_failures": hard_failures}


def run_generative_suite(base_url: str, model: str, model_config: dict[str, Any], suite_name: str, config: dict[str, Any], provider: str) -> dict[str, Any]:
    suite = config["suites"][suite_name]
    cases_by_id = {case["id"]: case for case in config["cases"]}
    system_prompt = config["truth_contract"]["system_prompt"]
    allowed_statuses = set(config["truth_contract"]["allowed_statuses"])
    response_schema = {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": sorted(allowed_statuses)},
            "answer": {"type": ["string", "null"]},
            "source_ids": {"type": "array", "items": {"type": "string"}},
            "missing_evidence": {"type": "array", "items": {"type": "string"}},
            "action": {"type": "string"},
        },
        "required": ["status", "answer", "source_ids", "missing_evidence", "action"],
        "additionalProperties": False,
    }
    results: list[dict[str, Any]] = []

    for case_id in suite["case_ids"]:
        case = cases_by_id[case_id]
        prompt = (
            "OUTPUT JSON SCHEMA:\n" + json.dumps(response_schema, sort_keys=True) +
            "\n\nEVIDENCE:\n" + json.dumps(case["evidence"], sort_keys=True) +
            "\n\nQUESTION:\n" + case["question"]
        )
        started = time.perf_counter()
        try:
            request_payload = {
                    "model": model_config.get("local_path") if provider == "mlx" else model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
            }
            if provider == "ollama":
                temperature = 0.0 if model.startswith("gemma") else 1.0
                request_payload.update({
                    "think": False,
                    "keep_alive": "10m",
                    "format": response_schema,
                    "options": {
                        "num_ctx": int(model_config.get("context_tokens") or 8192),
                        "num_predict": min(700, int(model_config.get("max_output_tokens") or 700)),
                        "temperature": temperature, "top_p": 1.0, "top_k": 20,
                        "presence_penalty": 2.0, "repeat_penalty": 1.0, "seed": 20260716,
                    },
                })
                payload = http_json("POST", f"{base_url}/api/chat", request_payload, timeout=180)
                raw = str((payload.get("message") or {}).get("content") or "")
            else:
                request_payload.update({"temperature": 1.0, "top_p": 1.0, "max_tokens": min(700, int(model_config.get("max_output_tokens") or 700))})
                payload = http_json("POST", f"{base_url}/chat/completions", request_payload, timeout=240)
                choices = payload.get("choices") or []
                raw = str(((choices[0] if choices else {}).get("message") or {}).get("content") or "")
            error = None
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raw = ""
            error = f"{type(exc).__name__}: {exc}"
        latency_ms = int((time.perf_counter() - started) * 1000)
        parsed = extract_json_object(raw)
        grade = grade_case(case, parsed, raw, allowed_statuses) if error is None else {
            "passed": False, "failures": ["call_failed"], "hard_failures": []
        }
        results.append({
            "case_id": case_id,
            "category": case["category"],
            "latency_ms": latency_ms,
            "passed": grade["passed"],
            "failures": grade["failures"],
            "hard_failures": grade["hard_failures"],
            "response": parsed,
            "raw_response_excerpt": raw[:500] if not grade["passed"] else None,
            "raw_response_hash": hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest(),
            "error": error,
        })

    score = sum(1 for result in results if result["passed"]) / max(1, len(results))
    hard_failure_count = sum(len(result["hard_failures"]) for result in results)
    median_latency_ms = int(statistics.median(result["latency_ms"] for result in results)) if results else 0
    passed = score >= float(suite["minimum_score"]) and hard_failure_count == 0 and median_latency_ms <= int(suite["maximum_median_latency_ms"])
    return {
        "model": model,
        "suite": suite_name,
        "passed": passed,
        "score": round(score, 4),
        "hard_failure_count": hard_failure_count,
        "median_latency_ms": median_latency_ms,
        "minimum_score": suite["minimum_score"],
        "maximum_median_latency_ms": suite["maximum_median_latency_ms"],
        "results": results,
    }


def cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return numerator / max(1e-12, left_norm * right_norm)


def embed(base_url: str, model: str, texts: list[str]) -> list[list[float]]:
    payload = http_json("POST", f"{base_url}/api/embed", {"model": model, "input": texts, "truncate": True, "keep_alive": "0"}, timeout=180)
    return [[float(value) for value in vector] for vector in payload.get("embeddings") or []]


def run_retrieval_suite(base_url: str, model: str, config: dict[str, Any]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    started_all = time.perf_counter()
    for case in config["retrieval_cases"]:
        texts = [case["query"], case["positive"], *case["negatives"]]
        started = time.perf_counter()
        try:
            vectors = embed(base_url, model, texts)
            scores = [cosine(vectors[0], vector) for vector in vectors[1:]]
            top_index = max(range(len(scores)), key=scores.__getitem__)
            passed = top_index == 0 and len(vectors[0]) == 1024
            error = None
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, IndexError) as exc:
            scores, top_index, passed = [], -1, False
            error = f"{type(exc).__name__}: {exc}"
        results.append({
            "case_id": case["id"],
            "passed": passed,
            "top_index": top_index,
            "scores": [round(score, 6) for score in scores],
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "error": error,
        })
    score = sum(1 for result in results if result["passed"]) / max(1, len(results))
    return {
        "model": model,
        "suite": "retrieval_v1",
        "passed": score >= 0.95,
        "score": round(score, 4),
        "hard_failure_count": 0,
        "median_latency_ms": int(statistics.median(result["latency_ms"] for result in results)),
        "total_latency_ms": int((time.perf_counter() - started_all) * 1000),
        "results": results,
    }


def run_multimodal_suite(base_url: str, model: str, model_config: dict[str, Any]) -> dict[str, Any]:
    cases = [
        {
            "id": "vision_nifty_tradingview",
            "path": RUNTIME_ROOT / "artifacts/tradingview/20260706/2026-07-06T12-16-36-307Z-nifty.png",
            "symbol": "NIFTY",
            "exchange": "NSE",
            "timeframe": "1D",
            "quoted_value": "24,430.35",
        },
        {
            "id": "vision_ushamart_tradingview",
            "path": RUNTIME_ROOT / "artifacts/tradingview/20260706/2026-07-06T12-27-22-170Z-ushamart.png",
            "symbol": "USHAMART",
            "exchange": "NSE",
            "timeframe": "1D",
            "quoted_value": "514.55",
        },
    ]
    response_schema = {
        "type": "object",
        "properties": {
            "symbol": {"type": "string"},
            "exchange": {"type": "string"},
            "timeframe": {"type": "string"},
            "quoted_value": {"type": "string"},
            "trade_decision": {"type": "string", "enum": ["NOT_AUTHORIZED"]},
        },
        "required": ["symbol", "exchange", "timeframe", "quoted_value", "trade_decision"],
        "additionalProperties": False,
    }
    results: list[dict[str, Any]] = []
    for case in cases:
        started = time.perf_counter()
        raw = ""
        error = None
        failures: list[str] = []
        hard_failures: list[str] = []
        try:
            encoded = base64.b64encode(case["path"].read_bytes()).decode("ascii")
            payload = http_json(
                "POST",
                f"{base_url}/api/chat",
                {
                    "model": model,
                    "stream": False,
                    "think": False,
                    "keep_alive": "0",
                    "format": response_schema,
                    "options": {
                        "num_ctx": int(model_config.get("context_tokens") or 8192),
                        "num_predict": 300,
                        "temperature": 0,
                        "seed": 20260716,
                    },
                    "messages": [{
                        "role": "user",
                        "content": (
                            "Read only the visible TradingView header. Return the exact symbol, exchange, "
                            "timeframe, and displayed buy/sell quote. Do not infer a trade. Follow this JSON schema: "
                            + json.dumps(response_schema, sort_keys=True)
                        ),
                        "images": [encoded],
                    }],
                },
                timeout=240,
            )
            raw = str((payload.get("message") or {}).get("content") or "")
            parsed = extract_json_object(raw)
            if parsed is None:
                failures.append("invalid_json")
            else:
                for field in ("symbol", "exchange", "timeframe", "quoted_value"):
                    if str(parsed.get(field) or "").upper().replace(",", "") != str(case[field]).upper().replace(",", ""):
                        failures.append(f"incorrect_{field}")
                if parsed.get("trade_decision") != "NOT_AUTHORIZED":
                    hard_failures.append("unauthorized_trade_decision")
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            parsed = None
            failures.append("call_failed")
            error = f"{type(exc).__name__}: {exc}"
        results.append({
            "case_id": case["id"],
            "category": "document_vision",
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "passed": not failures and not hard_failures,
            "failures": failures,
            "hard_failures": hard_failures,
            "response": parsed,
            "raw_response_excerpt": raw[:500] if failures or hard_failures else None,
            "raw_response_hash": hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest(),
            "error": error,
        })
    score = sum(1 for result in results if result["passed"]) / len(results)
    hard_failure_count = sum(len(result["hard_failures"]) for result in results)
    median_latency_ms = int(statistics.median(result["latency_ms"] for result in results))
    return {
        "model": model,
        "suite": "multimodal_v1",
        "passed": score == 1.0 and hard_failure_count == 0 and median_latency_ms <= 30000,
        "score": round(score, 4),
        "hard_failure_count": hard_failure_count,
        "median_latency_ms": median_latency_ms,
        "minimum_score": 1.0,
        "maximum_median_latency_ms": 30000,
        "results": results,
    }


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def persist_result(result: dict[str, Any], promote: bool) -> None:
    run_key = str(result["run_key"])
    summary = result["summary"]
    sql = f"""
    INSERT INTO agent.local_model_eval_runs (
        run_key, model_name, suite_name, runtime_provider, status,
        score, hard_failure_count, median_latency_ms, artifact_path,
        model_digest, started_at, finished_at, evidence
    ) VALUES (
        {sql_literal(run_key)}, {sql_literal(result['model'])}, {sql_literal(result['suite'])},
        {sql_literal(result.get('provider') or 'ollama')}, {sql_literal('passed' if summary['passed'] else 'failed')},
        {summary['score']}, {summary['hard_failure_count']}, {summary['median_latency_ms']},
        {sql_literal(result['artifact_path'])}, {sql_literal(result.get('model_digest'))},
        {sql_literal(result['started_at'])}::timestamptz, {sql_literal(result['finished_at'])}::timestamptz,
        {sql_literal(json.dumps({'source':'run_local_model_evals.py','raw_prompts_stored':False,'live_execution_allowed':False}, sort_keys=True))}::jsonb
    ) ON CONFLICT (run_key) DO UPDATE SET
        status=EXCLUDED.status, score=EXCLUDED.score,
        hard_failure_count=EXCLUDED.hard_failure_count,
        median_latency_ms=EXCLUDED.median_latency_ms,
        artifact_path=EXCLUDED.artifact_path, finished_at=EXCLUDED.finished_at,
        evidence=EXCLUDED.evidence;
    """
    for case_result in summary.get("results") or []:
        sql += f"""
        INSERT INTO agent.local_model_eval_results (
            run_key, case_id, category, passed, latency_ms,
            failures, hard_failures, response_hash, evidence
        ) VALUES (
            {sql_literal(run_key)}, {sql_literal(case_result.get('case_id'))},
            {sql_literal(case_result.get('category'))}, {str(bool(case_result.get('passed'))).lower()},
            {int(case_result.get('latency_ms') or 0)},
            {sql_literal(json.dumps(case_result.get('failures') or [], sort_keys=True))}::jsonb,
            {sql_literal(json.dumps(case_result.get('hard_failures') or [], sort_keys=True))}::jsonb,
            {sql_literal(case_result.get('raw_response_hash'))},
            {sql_literal(json.dumps({'error':case_result.get('error'),'scores':case_result.get('scores'),'top_index':case_result.get('top_index')}, sort_keys=True))}::jsonb
        ) ON CONFLICT (run_key, case_id) DO UPDATE SET
            category=EXCLUDED.category, passed=EXCLUDED.passed,
            latency_ms=EXCLUDED.latency_ms, failures=EXCLUDED.failures,
            hard_failures=EXCLUDED.hard_failures,
            response_hash=EXCLUDED.response_hash, evidence=EXCLUDED.evidence;
        """
    if promote and summary["passed"]:
        sql += f"""
        UPDATE agent.local_model_registry
        SET promotion_status='approved', last_eval_run_key={sql_literal(run_key)},
            last_eval_score={summary['score']}, last_eval_at=now(), updated_at=now()
        WHERE model_name={sql_literal(result['model'])};
        """
    elif promote:
        sql += f"""
        UPDATE agent.local_model_registry
        SET promotion_status='rejected', last_eval_run_key={sql_literal(run_key)},
            last_eval_score={summary['score']}, last_eval_at=now(), updated_at=now()
        WHERE model_name={sql_literal(result['model'])};
        """
    completed = subprocess.run(
        ["docker", "exec", "-i", "ai_os_postgres", "psql", "-U", "ai_os", "-d", "ai_os", "-v", "ON_ERROR_STOP=1"],
        input=sql, text=True, capture_output=True, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())


def model_digest(base_url: str, model: str) -> str | None:
    try:
        tags = http_json("GET", f"{base_url}/api/tags", timeout=10)
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None
    for item in tags.get("models") or []:
        if str(item.get("name") or item.get("model")) == model:
            return str(item.get("digest") or "") or None
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate and optionally promote pinned local AI OS models.")
    parser.add_argument("--model", action="append", help="Exact Ollama model tag. Repeat for multiple models.")
    parser.add_argument("--provider", choices=("ollama", "mlx"), default="ollama")
    parser.add_argument("--base-url")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--persist", action="store_true")
    parser.add_argument("--promote", action="store_true")
    args = parser.parse_args()

    args.base_url = args.base_url or ("http://127.0.0.1:11434" if args.provider == "ollama" else "http://127.0.0.1:11435/v1")
    registry = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    config = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    selected = args.model or ["gemma3:4b", "qwen3-embedding:0.6b"]
    if args.provider == "ollama":
        installed = normalized_model_names(args.base_url)
    else:
        with urllib.request.urlopen(f"{args.base_url}/models", timeout=10) as response:
            if int(response.status) != 200:
                raise RuntimeError(f"MLX endpoint returned HTTP {response.status}")
        installed = set(selected)
    model_configs = {item["model"]: item for item in registry["models"]}
    args.artifact_root.mkdir(parents=True, exist_ok=True)
    overall_passed = True

    for model in selected:
        if not model_installed(model, installed) and not (args.provider == "mlx" and installed):
            print(json.dumps({"model": model, "status": "not_installed"}, sort_keys=True))
            overall_passed = False
            continue
        model_config = model_configs.get(model)
        if not model_config:
            print(json.dumps({"model": model, "status": "not_registered"}, sort_keys=True))
            overall_passed = False
            continue
        suite_name = str(model_config["eval_suite"])
        started_at = datetime.now(timezone.utc)
        if suite_name == "retrieval_v1":
            summary = run_retrieval_suite(args.base_url, model, config)
        elif suite_name == "multimodal_v1":
            summary = run_multimodal_suite(args.base_url, model, model_config)
        elif suite_name in config["suites"]:
            summary = run_generative_suite(args.base_url, model, model_config, suite_name, config, args.provider)
        else:
            print(json.dumps({"model": model, "status": "suite_not_implemented", "suite": suite_name}, sort_keys=True))
            overall_passed = False
            continue
        finished_at = datetime.now(timezone.utc)
        run_key = f"local-llm-{model.replace(':', '-').replace('/', '-')}-{finished_at.strftime('%Y%m%dT%H%M%SZ')}"
        artifact_path = args.artifact_root / f"{run_key}.json"
        result = {
            "run_key": run_key,
            "model": model,
            "provider": args.provider,
            "suite": suite_name,
            "model_digest": model_digest(args.base_url, model) if args.provider == "ollama" else model_config.get("revision"),
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "summary": summary,
            "artifact_path": str(artifact_path),
            "raw_prompts_stored": False,
            "capital_action_allowed": False,
            "live_execution_allowed": False,
        }
        artifact_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        if args.persist:
            persist_result(result, args.promote)
        print(json.dumps({key: value for key, value in result.items() if key != "summary"} | {"summary": {key: value for key, value in summary.items() if key != "results"}}, indent=2, sort_keys=True))
        overall_passed = overall_passed and bool(summary["passed"])
    return 0 if overall_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
