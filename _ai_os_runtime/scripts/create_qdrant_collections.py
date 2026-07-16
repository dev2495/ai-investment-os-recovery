#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request


QDRANT_BASE_URL = "http://127.0.0.1:6333"
VECTOR_SIZE = 1024
DISTANCE = "Cosine"

COLLECTIONS = [
    "obsidian_notes_qwen3_embedding_0_6b",
    "corporate_filings_qwen3_embedding_0_6b",
    "trade_journals_qwen3_embedding_0_6b",
    "news_social_qwen3_embedding_0_6b",
    "research_reports_qwen3_embedding_0_6b",
    "strategy_artifacts_qwen3_embedding_0_6b",
]


def request(method: str, path: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{QDRANT_BASE_URL}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    created_or_existing: list[str] = []
    for collection in COLLECTIONS:
        payload = {"vectors": {"size": VECTOR_SIZE, "distance": DISTANCE}}
        try:
            response = request("PUT", f"/collections/{collection}", payload)
            status = response.get("status")
            if status != "ok":
                print(json.dumps({"collection": collection, "response": response}, indent=2))
                return 1
            created_or_existing.append(collection)
        except urllib.error.HTTPError as exc:
            print(f"ERROR creating {collection}: HTTP {exc.code} {exc.read().decode('utf-8')}", file=sys.stderr)
            return 1
    print(json.dumps({"collections": created_or_existing, "vector_size": VECTOR_SIZE, "distance": DISTANCE}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
