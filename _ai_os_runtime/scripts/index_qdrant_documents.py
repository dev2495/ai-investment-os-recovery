#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import math
import re
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


RUNTIME_ROOT = Path(os.environ.get("AI_OS_RUNTIME_ROOT") or Path(__file__).resolve().parents[1])
DATA_ROOT = Path(os.environ.get("AI_OS_DATA_ROOT") or "/Volumes/Devarsh SSD/AI OS Data")
QDRANT_BASE_URL = "http://127.0.0.1:6333"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embed"
OLLAMA_MODEL = "qwen3-embedding:0.6b"
VECTOR_SIZE = 1024

COLLECTIONS = {
    "obsidian_notes_qwen3_embedding_0_6b": "Obsidian notes and AI OS writebacks",
    "corporate_filings_qwen3_embedding_0_6b": "Corporate filings and exchange announcements",
    "trade_journals_qwen3_embedding_0_6b": "Trade journals and post-trade notes",
    "news_social_qwen3_embedding_0_6b": "News and social feed captures",
    "research_reports_qwen3_embedding_0_6b": "AI research reports and dashboard artifacts",
    "strategy_artifacts_qwen3_embedding_0_6b": "Strategy ideas, candidates, and backtest artifacts",
}


@dataclass
class SourceDocument:
    collection_name: str
    source_table: str
    source_id: str
    title: str
    text: str
    metadata: dict[str, Any]


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


def qdrant_request(method: str, path: str, payload: dict | None = None, timeout: int = 30) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{QDRANT_BASE_URL}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def ensure_collections(recreate: bool = True) -> None:
    for collection in COLLECTIONS:
        if recreate:
            try:
                qdrant_request("DELETE", f"/collections/{collection}")
            except urllib.error.HTTPError as exc:
                if exc.code != 404:
                    raise
        try:
            qdrant_request("PUT", f"/collections/{collection}", {"vectors": {"size": VECTOR_SIZE, "distance": "Cosine"}})
        except urllib.error.HTTPError as exc:
            if exc.code != 409:
                raise


def clean_text(value: object) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\x00", " ")).strip()


def read_text_file(path: Path, max_chars: int = 120_000) -> str:
    if not path.exists() or not path.is_file():
        return ""
    if path.suffix.lower() not in {".md", ".txt", ".json", ".csv", ".sql", ".py", ".tsx", ".ts", ".js", ".html"}:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except OSError:
        return ""


def chunk_text(text: str, chunk_size: int = 1400, overlap: int = 180) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


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


class Embedder:
    def __init__(self) -> None:
        self.provider = "unknown"
        self.fallback_count = 0
        self.last_error: str | None = None
        self._ollama_available = self._preflight_ollama()

    def _ollama_request(self, text: str, timeout: int = 60) -> list[float]:
        return self._ollama_batch_request([text], timeout=timeout)[0]

    def _ollama_batch_request(self, texts: list[str], timeout: int = 180) -> list[list[float]]:
        payload = json.dumps(
            {
                "model": OLLAMA_MODEL,
                "input": [text[:4000] for text in texts],
                "truncate": True,
                "keep_alive": "10m",
            }
        ).encode("utf-8")
        request = urllib.request.Request(OLLAMA_EMBED_URL, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        embeddings = data.get("embeddings") or []
        if len(embeddings) != len(texts):
            raise ValueError(f"expected {len(texts)} embeddings, got {len(embeddings)}")
        vectors: list[list[float]] = []
        for vector in embeddings:
            if len(vector) != VECTOR_SIZE:
                raise ValueError(f"expected {VECTOR_SIZE} dimensions, got {len(vector)}")
            vectors.append([float(item) for item in vector])
        return vectors

    def _preflight_ollama(self) -> bool:
        try:
            self._ollama_request("ai os embedding preflight", timeout=90)
            self.provider = OLLAMA_MODEL
            return True
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            raise RuntimeError(f"required embedding model is unavailable: {self.last_error}") from exc

    def embed(self, text: str) -> list[float]:
        try:
            self.provider = OLLAMA_MODEL
            return self._ollama_request(text, timeout=60)
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            raise RuntimeError(f"embedding failed; refusing mixed or fake index: {self.last_error}") from exc

    def embed_many(self, texts: list[str]) -> list[tuple[list[float], str]]:
        if not texts:
            return []
        try:
            vectors = self._ollama_batch_request(texts, timeout=max(180, len(texts) * 20))
            self.provider = OLLAMA_MODEL
            return [(vector, OLLAMA_MODEL) for vector in vectors]
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            raise RuntimeError(f"embedding batch failed; refusing mixed or fake index: {self.last_error}") from exc

    def summary_provider(self) -> str:
        return OLLAMA_MODEL


def source_obsidian_notes() -> list[SourceDocument]:
    rows = fetch_json_rows(
        """
        SELECT id, vault_path, note_path, title, note_type, tags, frontmatter, body_summary, content_hash, last_modified_at
        FROM knowledge.obsidian_notes
        ORDER BY id
        """
    )
    docs: list[SourceDocument] = []
    for row in rows:
        note_path = Path(row["vault_path"]) / row["note_path"]
        body = read_text_file(note_path) or clean_text(row.get("body_summary"))
        docs.append(
            SourceDocument(
                collection_name="obsidian_notes_qwen3_embedding_0_6b",
                source_table="knowledge.obsidian_notes",
                source_id=str(row["id"]),
                title=row.get("title") or row.get("note_path") or f"note-{row['id']}",
                text=body,
                metadata={
                    "note_path": row.get("note_path"),
                    "vault_path": row.get("vault_path"),
                    "note_type": row.get("note_type"),
                    "tags": row.get("tags") or [],
                    "content_hash": row.get("content_hash"),
                    "last_modified_at": row.get("last_modified_at"),
                },
            )
        )
    return docs


def source_research_reports() -> list[SourceDocument]:
    rows = fetch_json_rows(
        """
        SELECT artifact.id, artifact.artifact_type, artifact.title, artifact.source_url,
               artifact.local_path, artifact.content_hash, artifact.mime_type,
               artifact.sensitivity, artifact.captured_at, artifact.metadata,
               ingestion.extracted_text_path, ingestion.source_path AS ingestion_source_path,
               ingestion.table_profiles, ingestion.status AS ingestion_status,
               ingestion.promotion_status
        FROM core.raw_artifacts artifact
        LEFT JOIN core.local_artifact_ingestions ingestion
          ON ingestion.raw_artifact_id = artifact.id
        WHERE artifact.artifact_type LIKE 'ai_%'
           OR artifact.artifact_type LIKE 'external_%'
           OR (
                artifact.artifact_type IN ('operator_document', 'operator_tabular_file')
                AND artifact.metadata->>'original_path' LIKE 'first_party_research:%'
              )
        ORDER BY artifact.id
        """
    )
    docs: list[SourceDocument] = []
    for row in rows:
        metadata = row.get("metadata") or {}
        extracted_path = row.get("extracted_text_path")
        local_text = read_text_file(Path(extracted_path)) if extracted_path else ""
        if not local_text and row.get("local_path"):
            local_text = read_text_file(Path(row["local_path"]))
        text_parts = [
            row.get("title") or "",
            row.get("artifact_type") or "",
            metadata.get("summary") if isinstance(metadata, dict) else "",
            local_text,
            json.dumps(metadata, sort_keys=True, default=str) if metadata else "",
            json.dumps(row.get("table_profiles") or [], sort_keys=True, default=str),
        ]
        docs.append(
            SourceDocument(
                collection_name="research_reports_qwen3_embedding_0_6b",
                source_table="core.raw_artifacts",
                source_id=str(row["id"]),
                title=row.get("title") or f"artifact-{row['id']}",
                text="\n".join(part for part in text_parts if part),
                metadata={
                    "artifact_type": row.get("artifact_type"),
                    "source_url": row.get("source_url"),
                    "local_path": row.get("local_path"),
                    "content_hash": row.get("content_hash"),
                    "mime_type": row.get("mime_type"),
                    "captured_at": row.get("captured_at"),
                    "artifact_family": metadata.get("artifact_family") if isinstance(metadata, dict) else None,
                    "provenance": "user_supplied_first_party" if str(metadata.get("original_path", "")).startswith("first_party_research:") else None,
                    "extracted_text_path": extracted_path,
                    "ingestion_status": row.get("ingestion_status"),
                    "promotion_status": row.get("promotion_status"),
                    "source_scope": "personal_research" if str(row.get("ingestion_source_path") or "").startswith("first_party_research:") else None,
                },
            )
        )
    return docs


def source_trade_journals() -> list[SourceDocument]:
    rows = fetch_json_rows(
        """
        SELECT id, journal_ts, symbol, strategy, setup_type, timeframe, market_condition,
               entry_reason, exit_reason, emotional_state, execution_quality, r_multiple,
               pnl, note_path, raw_text, extracted_features, external_ref
        FROM trading.trade_journals
        ORDER BY id
        """
    )
    docs: list[SourceDocument] = []
    for row in rows:
        text = "\n".join(
            clean_text(row.get(field))
            for field in ["symbol", "strategy", "setup_type", "market_condition", "entry_reason", "exit_reason", "emotional_state", "raw_text"]
            if clean_text(row.get(field))
        )
        docs.append(
            SourceDocument(
                collection_name="trade_journals_qwen3_embedding_0_6b",
                source_table="trading.trade_journals",
                source_id=str(row["id"]),
                title=f"{row.get('symbol') or 'Trade journal'} {row.get('journal_ts') or ''}".strip(),
                text=text,
                metadata={key: value for key, value in row.items() if key not in {"raw_text"}},
            )
        )
    return docs


def source_filings() -> list[SourceDocument]:
    rows = fetch_json_rows(
        """
        SELECT id, source_name, exchange, symbol, company_name, filing_type, event_type,
               title, filed_at, source_url, local_path, content_hash, extraction_status,
               extracted_text, payload
        FROM research.corporate_filings
        ORDER BY id
        """
    )
    docs: list[SourceDocument] = []
    for row in rows:
        docs.append(
            SourceDocument(
                collection_name="corporate_filings_qwen3_embedding_0_6b",
                source_table="research.corporate_filings",
                source_id=str(row["id"]),
                title=row.get("title") or f"filing-{row['id']}",
                text="\n".join(clean_text(row.get(field)) for field in ["company_name", "symbol", "filing_type", "event_type", "title", "extracted_text"] if clean_text(row.get(field))),
                metadata={key: value for key, value in row.items() if key not in {"extracted_text"}},
            )
        )
    return docs


def source_news_social() -> list[SourceDocument]:
    news = fetch_json_rows(
        """
        SELECT id, 'market.news_items' AS source_table, source_name, source_url, title, publisher, author,
               published_at, captured_at, symbols, topics, geography, sentiment, relevance_score,
               NULL::text AS body, raw_payload
        FROM market.news_items
        ORDER BY id
        """
    )
    social = fetch_json_rows(
        """
        SELECT id, 'market.social_items' AS source_table, source_name, source_url, title, author_handle AS author,
               posted_at AS published_at, captured_at, symbols, topics, NULL::text AS geography,
               NULL::numeric AS sentiment, relevance_score, body, raw_payload
        FROM market.social_items
        ORDER BY id
        """
    )
    docs: list[SourceDocument] = []
    for row in news + social:
        source_table = row.pop("source_table")
        docs.append(
            SourceDocument(
                collection_name="news_social_qwen3_embedding_0_6b",
                source_table=source_table,
                source_id=str(row["id"]),
                title=row.get("title") or f"feed-{row['id']}",
                text="\n".join(clean_text(row.get(field)) for field in ["title", "publisher", "author", "body", "source_name"] if clean_text(row.get(field))),
                metadata=row,
            )
        )
    return docs


def source_strategy_artifacts() -> list[SourceDocument]:
    candidates = fetch_json_rows(
        """
        SELECT id, name, candidate_key, source_kind, source_ref, hypothesis, universe, timeframe,
               entry_rules, exit_rules, risk_rules, status, owner_agent, validation_status,
               activation_gate, structured_spec, created_at, updated_at
        FROM strategy.strategy_candidates
        ORDER BY id
        """
    )
    dossiers = fetch_json_rows(
        """
        SELECT id, dossier_key, title, symbols, status, latest_triage_decision,
               recommended_next_action, discovery_count, generated_idea_count,
               optimizer_run_count, triage_decision_count, committee_review_count,
               summary, evidence_timeline, note_path, updated_at
        FROM strategy.idea_dossiers
        ORDER BY updated_at DESC, id
        """
    )
    docs: list[SourceDocument] = []
    for row in candidates:
        text = "\n".join(
            [
                clean_text(row.get("name")),
                clean_text(row.get("hypothesis")),
                json.dumps(row.get("entry_rules") or {}, sort_keys=True),
                json.dumps(row.get("exit_rules") or {}, sort_keys=True),
                json.dumps(row.get("risk_rules") or {}, sort_keys=True),
                json.dumps(row.get("structured_spec") or {}, sort_keys=True),
            ]
        )
        docs.append(
            SourceDocument(
                collection_name="strategy_artifacts_qwen3_embedding_0_6b",
                source_table="strategy.strategy_candidates",
                source_id=str(row["id"]),
                title=row.get("name") or f"strategy-{row['id']}",
                text=text,
                metadata={key: value for key, value in row.items() if key not in {"hypothesis", "entry_rules", "exit_rules", "risk_rules", "structured_spec"}},
            )
        )
    for row in dossiers:
        text = "\n".join(
            [
                clean_text(row.get("title")),
                clean_text(row.get("summary")),
                clean_text(row.get("recommended_next_action")),
                json.dumps(row.get("symbols") or [], sort_keys=True),
                json.dumps(row.get("evidence_timeline") or [], sort_keys=True, default=str),
            ]
        )
        docs.append(
            SourceDocument(
                collection_name="strategy_artifacts_qwen3_embedding_0_6b",
                source_table="strategy.idea_dossiers",
                source_id=str(row["id"]),
                title=row.get("title") or f"idea-dossier-{row['id']}",
                text=text,
                metadata={key: value for key, value in row.items() if key not in {"summary", "evidence_timeline"}},
            )
        )
    return docs


def all_source_documents() -> list[SourceDocument]:
    return [
        *source_obsidian_notes(),
        *source_research_reports(),
        *source_trade_journals(),
        *source_filings(),
        *source_news_social(),
        *source_strategy_artifacts(),
    ]


def upsert_vector_documents(rows: list[dict[str, Any]]) -> None:
    statements = ["BEGIN;"]
    statements.append(
        "DELETE FROM knowledge.vector_documents WHERE collection_name IN ("
        + ",".join(sql_literal(collection) for collection in COLLECTIONS)
        + ");"
    )
    if not rows:
        statements.append("COMMIT;")
        run_psql("\n".join(statements))
        return
    for row in rows:
        statements.append(
            f"""
INSERT INTO knowledge.vector_documents (
    collection_name, qdrant_point_id, source_table, source_id, title,
    text_hash, embedding_model, chunk_index, chunk_text_preview, metadata, indexed_at
)
VALUES (
    {sql_literal(row["collection_name"])},
    {sql_literal(row["qdrant_point_id"])},
    {sql_literal(row["source_table"])},
    {sql_literal(row["source_id"])},
    {sql_literal(row["title"])},
    {sql_literal(row["text_hash"])},
    {sql_literal(row["embedding_model"])},
    {row["chunk_index"]},
    {sql_literal(row["chunk_text_preview"])},
    {sql_jsonb(row["metadata"])},
    now()
)
ON CONFLICT (collection_name, qdrant_point_id) DO UPDATE SET
    source_table = EXCLUDED.source_table,
    source_id = EXCLUDED.source_id,
    title = EXCLUDED.title,
    text_hash = EXCLUDED.text_hash,
    embedding_model = EXCLUDED.embedding_model,
    chunk_index = EXCLUDED.chunk_index,
    chunk_text_preview = EXCLUDED.chunk_text_preview,
    metadata = EXCLUDED.metadata,
    indexed_at = now();
"""
        )
    statements.append("COMMIT;")
    run_psql("\n".join(statements))


def existing_collection_registry(collections: set[str]) -> list[dict[str, Any]]:
    if not collections:
        return []
    return fetch_json_rows(
        f"""
        SELECT collection_name,qdrant_point_id,source_table,source_id,chunk_index,text_hash
        FROM knowledge.vector_documents
        WHERE collection_name IN ({','.join(sql_literal(collection) for collection in sorted(collections))})
        ORDER BY collection_name,source_table,source_id,chunk_index
        """
    )


def existing_research_registry() -> list[dict[str, Any]]:
    """Backward-compatible bounded reader for the research-report collection."""
    return existing_collection_registry({"research_reports_qwen3_embedding_0_6b"})


def write_incremental_collection_registry(
    collection: str,
    rows: list[dict[str, Any]],
    stale_point_ids: list[str],
) -> None:
    statements = ["BEGIN;"]
    if stale_point_ids:
        statements.append(
            "DELETE FROM knowledge.vector_documents "
            f"WHERE collection_name = {sql_literal(collection)} "
            "AND qdrant_point_id IN ("
            + ",".join(sql_literal(point_id) for point_id in stale_point_ids)
            + ");"
        )
    for row in rows:
        statements.append(
            f"""
INSERT INTO knowledge.vector_documents (
    collection_name, qdrant_point_id, source_table, source_id, title,
    text_hash, embedding_model, chunk_index, chunk_text_preview, metadata, indexed_at
)
VALUES (
    {sql_literal(row["collection_name"])},
    {sql_literal(row["qdrant_point_id"])},
    {sql_literal(row["source_table"])},
    {sql_literal(row["source_id"])},
    {sql_literal(row["title"])},
    {sql_literal(row["text_hash"])},
    {sql_literal(row["embedding_model"])},
    {row["chunk_index"]},
    {sql_literal(row["chunk_text_preview"])},
    {sql_jsonb(row["metadata"])},
    now()
)
ON CONFLICT (collection_name, qdrant_point_id) DO UPDATE SET
    source_table = EXCLUDED.source_table,
    source_id = EXCLUDED.source_id,
    title = EXCLUDED.title,
    text_hash = EXCLUDED.text_hash,
    embedding_model = EXCLUDED.embedding_model,
    chunk_index = EXCLUDED.chunk_index,
    chunk_text_preview = EXCLUDED.chunk_text_preview,
    metadata = EXCLUDED.metadata,
    indexed_at = now();
"""
        )
    statements.append("COMMIT;")
    run_psql("\n".join(statements))


def write_incremental_research_registry(
    rows: list[dict[str, Any]], stale_point_ids: list[str]
) -> None:
    """Backward-compatible writer used by the Research Hub refresh contract."""
    write_incremental_collection_registry(
        "research_reports_qwen3_embedding_0_6b", rows, stale_point_ids
    )


def delete_qdrant_points(collection: str, point_ids: list[str]) -> None:
    for start in range(0, len(point_ids), 128):
        batch = point_ids[start : start + 128]
        if batch:
            qdrant_request(
                "POST",
                f"/collections/{collection}/points/delete?wait=true",
                {"points": batch},
                timeout=60,
            )


def index_collections_incremental(
    documents: list[SourceDocument],
    selected_collections: set[str],
    *,
    mode: str,
    existing_rows: list[dict[str, Any]] | None = None,
    registry_writer=None,
) -> dict[str, Any]:
    ensure_collections(recreate=False)
    selected_documents = [document for document in documents if document.collection_name in selected_collections]
    existing_rows = existing_rows if existing_rows is not None else existing_collection_registry(selected_collections)
    registry_writer = registry_writer or write_incremental_collection_registry
    existing_by_collection: dict[str, set[str]] = {collection: set() for collection in selected_collections}
    for row in existing_rows:
        if row.get("qdrant_point_id"):
            existing_by_collection.setdefault(str(row["collection_name"]), set()).add(str(row["qdrant_point_id"]))
    expected_by_collection: dict[str, list[dict[str, Any]]] = {collection: [] for collection in selected_collections}
    skipped_empty = 0
    for document in selected_documents:
        chunks = chunk_text(document.text)
        if not chunks:
            skipped_empty += 1
            continue
        for chunk_index, chunk in enumerate(chunks):
            text_hash = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
            point_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{document.collection_name}:{document.source_table}:{document.source_id}:{chunk_index}:{text_hash}",
                )
            )
            expected_by_collection[document.collection_name].append(
                {
                    "doc": document,
                    "chunk_index": chunk_index,
                    "chunk": chunk,
                    "text_hash": text_hash,
                    "point_id": point_id,
                }
            )

    indexed_count = 0
    deleted_count = 0
    unchanged_count = 0
    embedder: Embedder | None = None
    collection_summary: dict[str, dict[str, int]] = {}
    for collection in sorted(selected_collections):
        expected_records = expected_by_collection.get(collection) or []
        existing_point_ids = existing_by_collection.get(collection) or set()
        expected_point_ids = {record["point_id"] for record in expected_records}
        stale_point_ids = sorted(existing_point_ids - expected_point_ids)
        pending_records = [record for record in expected_records if record["point_id"] not in existing_point_ids]
        if pending_records and embedder is None:
            embedder = Embedder()
        for start in range(0, len(pending_records), 16):
            batch_records = pending_records[start : start + 16]
            embedded = embedder.embed_many([record["chunk"] for record in batch_records]) if embedder else []
            batch_points: list[dict[str, Any]] = []
            batch_registry: list[dict[str, Any]] = []
            for record, (vector, embedding_model) in zip(batch_records, embedded, strict=True):
                document = record["doc"]
                chunk = record["chunk"]
                payload = {
                    "title": document.title, "source_table": document.source_table,
                    "source_id": document.source_id, "chunk_index": record["chunk_index"],
                    "text_hash": record["text_hash"], "text_preview": chunk[:600],
                    "metadata": document.metadata,
                }
                batch_points.append({"id": record["point_id"], "vector": vector, "payload": payload})
                batch_registry.append({
                    "collection_name": collection, "qdrant_point_id": record["point_id"],
                    "source_table": document.source_table, "source_id": document.source_id,
                    "title": document.title, "text_hash": record["text_hash"],
                    "embedding_model": embedding_model, "chunk_index": record["chunk_index"],
                    "chunk_text_preview": chunk[:500], "metadata": document.metadata,
                })
            qdrant_request("PUT", f"/collections/{collection}/points?wait=true", {"points": batch_points}, timeout=60)
            registry_writer(collection, batch_registry, [])
            indexed_count += len(batch_registry)
        # Stale points are removed only after every expected replacement has been persisted.
        delete_qdrant_points(collection, stale_point_ids)
        registry_writer(collection, [], stale_point_ids)
        deleted_count += len(stale_point_ids)
        unchanged_count += len(expected_point_ids & existing_point_ids)
        collection_summary[collection] = {
            "existing": len(existing_point_ids), "expected": len(expected_point_ids),
            "indexed": len(pending_records), "unchanged": len(expected_point_ids & existing_point_ids),
            "deleted": len(stale_point_ids),
        }
    return {
        "mode": mode,
        "status": "success",
        "documents_seen": len(selected_documents),
        "documents_skipped_empty": skipped_empty,
        "existing_points": sum(len(value) for value in existing_by_collection.values()),
        "unchanged_points": unchanged_count,
        "points_indexed": indexed_count,
        "points_deleted": deleted_count,
        "embedding_model": OLLAMA_MODEL,
        "collections": collection_summary,
        "private_storage": "external_ssd",
    }


def index_research_reports_incremental() -> dict[str, Any]:
    collection = "research_reports_qwen3_embedding_0_6b"
    existing_rows = existing_research_registry()
    for row in existing_rows:
        row.setdefault("collection_name", collection)
    return index_collections_incremental(
        source_research_reports(), {collection}, mode="incremental_research_reports",
        existing_rows=existing_rows,
        registry_writer=lambda _collection, rows, stale: write_incremental_research_registry(rows, stale),
    )


def index_all_collections_incremental() -> dict[str, Any]:
    return index_collections_incremental(
        all_source_documents(), set(COLLECTIONS), mode="incremental_all_collections"
    )


def index_documents() -> dict[str, Any]:
    embedder = Embedder()
    ensure_collections()
    docs = all_source_documents()
    points_by_collection: dict[str, list[dict[str, Any]]] = {collection: [] for collection in COLLECTIONS}
    registry_rows: list[dict[str, Any]] = []
    chunk_records: list[dict[str, Any]] = []
    skipped = 0

    for doc in docs:
        chunks = chunk_text(doc.text)
        if not chunks:
            skipped += 1
            continue
        for index, chunk in enumerate(chunks):
            text_hash = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc.collection_name}:{doc.source_table}:{doc.source_id}:{index}:{text_hash}"))
            chunk_records.append(
                {
                    "doc": doc,
                    "chunk_index": index,
                    "chunk": chunk,
                    "text_hash": text_hash,
                    "point_id": point_id,
                }
            )

    for start in range(0, len(chunk_records), 16):
        batch_records = chunk_records[start : start + 16]
        embedded = embedder.embed_many([record["chunk"] for record in batch_records])
        for record, (vector, embedding_model) in zip(batch_records, embedded, strict=True):
            doc = record["doc"]
            chunk = record["chunk"]
            payload = {
                "title": doc.title,
                "source_table": doc.source_table,
                "source_id": doc.source_id,
                "chunk_index": record["chunk_index"],
                "text_hash": record["text_hash"],
                "text_preview": chunk[:600],
                "metadata": doc.metadata,
            }
            points_by_collection[doc.collection_name].append({"id": record["point_id"], "vector": vector, "payload": payload})
            registry_rows.append(
                {
                    "collection_name": doc.collection_name,
                    "qdrant_point_id": record["point_id"],
                    "source_table": doc.source_table,
                    "source_id": doc.source_id,
                    "title": doc.title,
                    "text_hash": record["text_hash"],
                    "embedding_model": embedding_model,
                    "chunk_index": record["chunk_index"],
                    "chunk_text_preview": chunk[:500],
                    "metadata": doc.metadata,
                }
            )

    for collection, points in points_by_collection.items():
        for start in range(0, len(points), 64):
            batch = points[start : start + 64]
            if batch:
                qdrant_request("PUT", f"/collections/{collection}/points?wait=true", {"points": batch}, timeout=60)

    upsert_vector_documents(registry_rows)
    if any(row["source_table"] == "strategy.idea_dossiers" for row in registry_rows):
        run_psql("UPDATE strategy.idea_dossiers SET qdrant_index_status = 'indexed', updated_at = now() WHERE id IN (SELECT source_id::BIGINT FROM knowledge.vector_documents WHERE source_table = 'strategy.idea_dossiers');")
    return {
        "documents_seen": len(docs),
        "documents_skipped_empty": skipped,
        "points_indexed": len(registry_rows),
        "embedding_model": embedder.summary_provider(),
        "fallback_chunks": embedder.fallback_count,
        "last_embedding_error": embedder.last_error,
        "collections": {collection: len(points) for collection, points in points_by_collection.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build governed Qdrant indexes.")
    parser.add_argument(
        "--incremental-research",
        action="store_true",
        help="Update only changed research-report chunks without recreating collections.",
    )
    parser.add_argument(
        "--rebuild-all",
        action="store_true",
        help="Explicit maintenance-only full collection rebuild. Normal runs are incremental.",
    )
    args = parser.parse_args()
    if not DATA_ROOT.exists() or not str(DATA_ROOT.resolve()).startswith("/Volumes/Devarsh SSD/"):
        print("Qdrant index failed: external Devarsh SSD data root is unavailable; no internal-disk fallback", file=sys.stderr)
        return 1
    try:
        if args.rebuild_all and args.incremental_research:
            raise RuntimeError("choose either --rebuild-all or --incremental-research")
        summary = index_documents() if args.rebuild_all else (
            index_research_reports_incremental() if args.incremental_research else index_all_collections_incremental()
        )
    except (RuntimeError, urllib.error.URLError) as exc:
        print(f"Qdrant index failed: {exc}", file=sys.stderr)
        return 1
    output_path = DATA_ROOT / "artifacts" / "indexes" / "qdrant_index_summary.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
