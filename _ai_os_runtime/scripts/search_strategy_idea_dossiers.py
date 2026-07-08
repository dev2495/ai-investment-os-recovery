#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
QDRANT_BASE_URL = "http://127.0.0.1:6333"
QDRANT_COLLECTION = "strategy_artifacts_mxbai_embed_large"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embed"
OLLAMA_MODEL = "mxbai-embed-large"
VECTOR_SIZE = 1024


def run_psql(sql: str, tuples_only: bool = False) -> str:
    command = ["docker", "exec", "-i", "ai_os_postgres", "psql", "-q", "-U", "ai_os", "-d", "ai_os", "-v", "ON_ERROR_STOP=1"]
    if tuples_only:
        command.extend(["-t", "-A"])
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return completed.stdout.strip()


def fetch_json_rows(sql: str) -> list[dict[str, Any]]:
    wrapped = f"SELECT COALESCE(json_agg(row_to_json(q)), '[]'::json) FROM ({sql}) q;"
    text = run_psql(wrapped, tuples_only=True)
    return json.loads(text) if text else []


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return f"{sql_literal(json.dumps(value, sort_keys=True, default=str))}::jsonb"


def clean_text(value: object) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\x00", " ")).strip()


def local_hash_embedding(text: str) -> list[float]:
    vector = [0.0] * VECTOR_SIZE
    normalized = clean_text(text).lower()
    words = re.findall(r"[a-z0-9_.$:/-]+", normalized)
    features: list[tuple[str, float]] = []
    features.extend((word, 1.0) for word in words)
    for word in words:
        if len(word) >= 5:
            for index in range(max(1, len(word) - 3)):
                features.append((word[index : index + 4], 0.35))
    for feature, weight in features:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        index = value % VECTOR_SIZE
        sign = 1.0 if (value >> 11) & 1 else -1.0
        vector[index] += sign * weight
    norm = math.sqrt(sum(item * item for item in vector)) or 1.0
    return [item / norm for item in vector]


def qdrant_request(method: str, path: str, payload: dict | None = None, timeout: int = 20) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{QDRANT_BASE_URL}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def ollama_embedding(text: str) -> list[float]:
    payload = json.dumps({"model": OLLAMA_MODEL, "input": text[:4000], "truncate": True, "keep_alive": "10m"}).encode("utf-8")
    request = urllib.request.Request(OLLAMA_EMBED_URL, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=90) as response:
        data = json.loads(response.read().decode("utf-8"))
    embeddings = data.get("embeddings") or []
    if not embeddings:
        raise ValueError("ollama returned no embedding")
    vector = embeddings[0]
    if len(vector) != VECTOR_SIZE:
        raise ValueError(f"expected {VECTOR_SIZE} dimensions, got {len(vector)}")
    return [float(item) for item in vector]


def dominant_dossier_embedding_model() -> str:
    rows = fetch_json_rows(
        """
        SELECT embedding_model, count(*) AS chunks
        FROM knowledge.vector_documents
        WHERE source_table = 'strategy.idea_dossiers'
        GROUP BY embedding_model
        ORDER BY count(*) DESC, embedding_model
        LIMIT 1
        """
    )
    if not rows:
        return "local_hashing_1024"
    return str(rows[0].get("embedding_model") or "local_hashing_1024")


def create_run(run_key: str, query_text: str, actor: str) -> None:
    run_psql(
        f"""
        INSERT INTO strategy.idea_dossier_search_runs (run_key, query_text, status, created_by, started_at)
        VALUES ({sql_literal(run_key)}, {sql_literal(query_text)}, 'started', {sql_literal(actor)}, now())
        ON CONFLICT (run_key) DO UPDATE SET
            query_text = EXCLUDED.query_text,
            status = 'started',
            search_mode = NULL,
            embedding_model = NULL,
            qdrant_available = false,
            fallback_used = false,
            match_count = 0,
            results = '[]'::jsonb,
            error_message = NULL,
            started_at = now(),
            finished_at = NULL,
            duration_ms = NULL,
            created_by = EXCLUDED.created_by;
        """
    )


def finish_run(run_key: str, started: float, summary: dict[str, Any]) -> None:
    duration_ms = int((time.time() - started) * 1000)
    run_psql(
        f"""
        UPDATE strategy.idea_dossier_search_runs
        SET status = {sql_literal(summary["status"])},
            search_mode = {sql_literal(summary.get("search_mode"))},
            embedding_model = {sql_literal(summary.get("embedding_model"))},
            qdrant_available = {str(bool(summary.get("qdrant_available"))).lower()},
            fallback_used = {str(bool(summary.get("fallback_used"))).lower()},
            match_count = {int(summary.get("match_count") or 0)},
            results = {sql_jsonb(summary.get("results") or [])},
            error_message = {sql_literal(summary.get("error_message"))},
            finished_at = now(),
            duration_ms = {duration_ms}
        WHERE run_key = {sql_literal(run_key)};
        """
    )


def load_dossiers_by_id(ids: list[str]) -> dict[str, dict[str, Any]]:
    numeric_ids = [str(int(item)) for item in ids if str(item).isdigit()]
    if not numeric_ids:
        return {}
    rows = fetch_json_rows(
        f"""
        SELECT id, dossier_key, title, symbols, status, latest_triage_decision,
               recommended_next_action, discovery_count, generated_idea_count,
               optimizer_run_count, triage_decision_count, committee_review_count,
               priority_score, risk_score, summary, evidence_timeline, note_path,
               qdrant_index_status, updated_at
        FROM strategy.v_idea_dossiers
        WHERE id IN ({",".join(numeric_ids)})
        """
    )
    return {str(row["id"]): row for row in rows}


def vector_search(query: str, limit: int) -> tuple[list[dict[str, Any]], str, bool]:
    index_model = dominant_dossier_embedding_model()
    fallback_used = False
    if index_model.startswith("mxbai") or index_model == OLLAMA_MODEL:
        try:
            vector = ollama_embedding(query)
            embedding_model = OLLAMA_MODEL
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
            vector = local_hash_embedding(query)
            embedding_model = "local_hashing_1024"
            fallback_used = True
    else:
        vector = local_hash_embedding(query)
        embedding_model = "local_hashing_1024"

    payload = qdrant_request(
        "POST",
        f"/collections/{QDRANT_COLLECTION}/points/search",
        {
            "vector": vector,
            "limit": max(1, min(limit * 3, 30)),
            "with_payload": True,
            "filter": {"must": [{"key": "source_table", "match": {"value": "strategy.idea_dossiers"}}]},
        },
    )
    best_hits: dict[str, dict[str, Any]] = {}
    for item in payload.get("result", []):
        point_payload = item.get("payload") or {}
        source_id = str(point_payload.get("source_id") or "")
        if not source_id:
            continue
        score = float(item.get("score") or 0)
        current = best_hits.get(source_id)
        if current is None or score > float(current.get("score") or 0):
            best_hits[source_id] = {
                "dossier_id": source_id,
                "vector_score": score,
                "matched_title": point_payload.get("title"),
                "matched_preview": point_payload.get("text_preview"),
                "qdrant_point_id": item.get("id"),
            }
    hits = sorted(best_hits.values(), key=lambda row: float(row.get("vector_score") or 0), reverse=True)[:limit]
    dossiers = load_dossiers_by_id([str(row["dossier_id"]) for row in hits])
    results: list[dict[str, Any]] = []
    for hit in hits:
        dossier = dossiers.get(str(hit["dossier_id"]), {})
        results.append({**dossier, **hit, "match_source": "qdrant_vector"})
    return results, embedding_model, fallback_used


def lexical_search(query: str, limit: int) -> list[dict[str, Any]]:
    terms = [term for term in re.findall(r"[a-z0-9]+", query.lower()) if len(term) >= 3][:8]
    if not terms:
        return []
    score_terms = []
    where_terms = []
    for term in terms:
        pattern = f"%{term}%"
        fields = "lower(coalesce(title,'') || ' ' || coalesce(summary,'') || ' ' || coalesce(recommended_next_action,''))"
        score_terms.append(f"CASE WHEN {fields} LIKE {sql_literal(pattern)} THEN 1 ELSE 0 END")
        where_terms.append(f"{fields} LIKE {sql_literal(pattern)}")
    rows = fetch_json_rows(
        f"""
        SELECT id, dossier_key, title, symbols, status, latest_triage_decision,
               recommended_next_action, discovery_count, generated_idea_count,
               optimizer_run_count, triage_decision_count, committee_review_count,
               priority_score, risk_score, summary, evidence_timeline, note_path,
               qdrant_index_status, updated_at,
               ({' + '.join(score_terms)}) AS lexical_score
        FROM strategy.v_idea_dossiers
        WHERE {' OR '.join(where_terms)}
        ORDER BY ({' + '.join(score_terms)}) DESC,
                 priority_score DESC NULLS LAST,
                 updated_at DESC
        LIMIT {max(1, min(limit, 25))}
        """
    )
    return [{**row, "match_source": "sql_lexical"} for row in rows]


def search_dossiers(args: argparse.Namespace) -> dict[str, Any]:
    run_started = time.time()
    create_run(args.run_key, args.query, args.actor)
    qdrant_error = None
    try:
        results, embedding_model, fallback_used = vector_search(args.query, args.limit)
        summary = {
            "run_key": args.run_key,
            "status": "completed",
            "query": args.query,
            "search_mode": "qdrant_vector",
            "embedding_model": embedding_model,
            "qdrant_available": True,
            "fallback_used": fallback_used,
            "match_count": len(results),
            "results": results,
        }
        if not results:
            lexical = lexical_search(args.query, args.limit)
            summary.update(
                {
                    "search_mode": "qdrant_vector_empty_sql_lexical",
                    "fallback_used": True,
                    "match_count": len(lexical),
                    "results": lexical,
                }
            )
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        qdrant_error = f"{type(exc).__name__}: {exc}"
        lexical = lexical_search(args.query, args.limit)
        summary = {
            "run_key": args.run_key,
            "status": "completed" if lexical else "no_matches",
            "query": args.query,
            "search_mode": "sql_lexical",
            "embedding_model": dominant_dossier_embedding_model(),
            "qdrant_available": False,
            "fallback_used": True,
            "match_count": len(lexical),
            "results": lexical,
            "error_message": qdrant_error,
        }
    finish_run(args.run_key, run_started, summary)
    if qdrant_error and summary["results"]:
        summary["qdrant_error"] = qdrant_error
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Search strategy idea dossiers through Qdrant with SQL fallback.")
    parser.add_argument("--query", required=True)
    parser.add_argument("--run-key", default="strategy_dossier_search_cli")
    parser.add_argument("--actor", default="Strategy Dossier Search Agent")
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()
    try:
        result = search_dossiers(args)
    except Exception as exc:
        print(json.dumps({"run_key": args.run_key, "status": "failed", "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
