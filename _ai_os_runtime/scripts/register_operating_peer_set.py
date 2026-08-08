#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from collect_nse_bse_filings import USER_AGENT, curl_get, run_psql_json, run_psql_text, sql_jsonb, sql_literal


ALLOWED_SOURCE_HOSTS = {"nsearchives.nseindia.com", "www.nseindia.com", "bedmutha.com", "www.bedmutha.com", "www.bharatwireropes.com"}
PARSER_VERSION = "primary_source_operating_peer_registry_v1"


def visible_text(payload: bytes) -> str:
    decoded = payload.decode("utf-8", errors="ignore")
    without_scripts = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", decoded, flags=re.IGNORECASE | re.DOTALL)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", without_scripts))).strip()


def validate_peer(peer: dict[str, Any], payload: bytes) -> dict[str, Any]:
    source_url = str(peer["source_url"])
    host = (urlparse(source_url).hostname or "").lower()
    if urlparse(source_url).scheme != "https" or host not in ALLOWED_SOURCE_HOSTS:
        raise ValueError(f"Unapproved peer evidence URL: {source_url}")
    text = visible_text(payload)
    missing = [phrase for phrase in peer.get("required_phrases", []) if phrase.casefold() not in text.casefold()]
    if missing:
        raise ValueError(f"Primary evidence did not contain required phrases for {peer['symbol']}: {missing}")
    return {
        "symbol": str(peer["symbol"]).upper(),
        "source_url": source_url,
        "content_hash": hashlib.sha256(payload).hexdigest(),
        "content_bytes": len(payload),
        "matched_phrases": list(peer.get("required_phrases", [])),
    }


def load_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if len(manifest.get("peers", [])) < 2:
        raise ValueError("A peer set requires at least two independently sourced peers.")
    return manifest


def fetch_and_validate(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    for peer in manifest["peers"]:
        status, payload = curl_get(
            peer["source_url"],
            {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*"},
            timeout=45,
        )
        if status != 200:
            raise RuntimeError(f"Primary peer evidence returned HTTP {status}: {peer['source_url']}")
        validated.append({**peer, **validate_peer(peer, payload)})
    return validated


def subject_company_id(manifest: dict[str, Any]) -> int:
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(company)), '[]'::json)::text
        FROM (
          SELECT id FROM research.companies
          WHERE primary_exchange={sql_literal(str(manifest['subject_exchange']).upper())}
            AND primary_symbol={sql_literal(str(manifest['subject_symbol']).upper())}
          ORDER BY id LIMIT 1
        ) company
        """
    )
    if not rows:
        raise ValueError("Subject company is not registered in the real-company research warehouse.")
    return int(rows[0]["id"])


def persist(manifest: dict[str, Any], peers: list[dict[str, Any]], actor: str) -> dict[str, int]:
    company_id = subject_company_id(manifest)
    evidence_ids: dict[str, int] = {}
    peer_company_ids: dict[str, int] = {}
    now = dt.datetime.now(dt.timezone.utc)
    as_of_date = dt.date.fromisoformat(manifest["valid_from"])

    for peer in peers:
        evidence_rows = run_psql_json(
            f"""
            WITH existing AS (
              SELECT id FROM research.fundamental_evidence
              WHERE company_id={company_id} AND source_url={sql_literal(peer['source_url'])}
                AND content_hash={sql_literal(peer['content_hash'])}
              ORDER BY id LIMIT 1
            ), inserted AS (
              INSERT INTO research.fundamental_evidence (
                company_id,source_type,source_name,source_url,source_title,retrieved_at,
                source_as_of_date,content_hash,extraction_method,verification_status,source_locator,metadata
              ) SELECT
                {company_id},'operating_peer_primary_source','Primary company or exchange source',
                {sql_literal(peer['source_url'])},{sql_literal(peer['source_title'])},{sql_literal(now.isoformat())}::timestamptz,
                {sql_literal(as_of_date.isoformat())}::date,{sql_literal(peer['content_hash'])},
                'required_phrase_match','machine_extracted',
                {sql_jsonb({'matched_phrases': peer['matched_phrases'], 'parser_version': PARSER_VERSION})},
                {sql_jsonb({'peer_symbol': peer['symbol'], 'identity_source_url': peer.get('identity_source_url'), 'content_bytes': peer['content_bytes'], 'review_status': 'machine_extracted_unreviewed', 'actor': actor, 'broker_write_allowed': False})}
              WHERE NOT EXISTS (SELECT 1 FROM existing)
              RETURNING id
            ), selected AS (
              SELECT id FROM inserted UNION ALL SELECT id FROM existing
            ) SELECT coalesce(json_agg(row_to_json(selected)), '[]'::json)::text FROM selected
            """
        )
        evidence_id = int(evidence_rows[0]["id"])
        evidence_ids[peer["symbol"]] = evidence_id
        company_rows = run_psql_json(
            f"""
            WITH upserted AS (
              INSERT INTO research.companies (
                company_key,legal_name,display_name,primary_symbol,primary_exchange,isin,identifiers,metadata
              ) VALUES (
                {sql_literal('nse:' + peer['symbol'].lower())},{sql_literal(peer['legal_name'])},{sql_literal(peer['legal_name'])},
                {sql_literal(peer['symbol'])},{sql_literal(peer['exchange'])},{sql_literal(peer['isin'])},
                {sql_jsonb({'isin': peer['isin'], 'nse_symbol': peer['symbol']})},
                {sql_jsonb({'registered_from': 'operating_peer_primary_source', 'human_review_required': True})}
              ) ON CONFLICT (primary_exchange,primary_symbol) DO UPDATE SET
                legal_name=EXCLUDED.legal_name,display_name=EXCLUDED.display_name,isin=EXCLUDED.isin,
                identifiers=research.companies.identifiers || EXCLUDED.identifiers,updated_at=now()
              RETURNING id
            ) SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
            """
        )
        peer_company_ids[peer["symbol"]] = int(company_rows[0]["id"])

    set_evidence_id = evidence_ids[peers[0]["symbol"]]
    set_rows = run_psql_json(
        f"""
        WITH upserted AS (
          INSERT INTO research.peer_sets (
            peer_set_key,subject_company_id,peer_set_name,methodology,valid_from,evidence_id,created_by
          ) VALUES (
            {sql_literal(manifest['peer_set_key'])},{company_id},{sql_literal(manifest['peer_set_name'])},
            {sql_literal(manifest['methodology'])},{sql_literal(manifest['valid_from'])}::date,{set_evidence_id},{sql_literal(actor)}
          ) ON CONFLICT (peer_set_key) DO UPDATE SET
            peer_set_name=EXCLUDED.peer_set_name,methodology=EXCLUDED.methodology,evidence_id=EXCLUDED.evidence_id,
            updated_at=now()
          RETURNING id
        ) SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
        """
    )
    peer_set_id = int(set_rows[0]["id"])
    for peer in peers:
        run_psql_text(
            f"""
            INSERT INTO research.peer_set_memberships (
              peer_set_id,peer_company_id,membership_role,inclusion_reason,valid_from,evidence_id
            ) VALUES (
              {peer_set_id},{peer_company_ids[peer['symbol']]},{sql_literal(peer['membership_role'])},
              {sql_literal(peer['inclusion_reason'])},{sql_literal(manifest['valid_from'])}::date,
              {evidence_ids[peer['symbol']]}
            ) ON CONFLICT (peer_set_id,peer_company_id,valid_from) DO UPDATE SET
              membership_role=EXCLUDED.membership_role,inclusion_reason=EXCLUDED.inclusion_reason,
              evidence_id=EXCLUDED.evidence_id;
            """
        )
    return {"subject_company_id": company_id, "peer_set_id": peer_set_id, "peer_count": len(peers), "evidence_count": len(evidence_ids)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Register a primary-source-validated operating peer set.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--persist", action="store_true")
    parser.add_argument("--actor", default="Fundamental Data Engineer")
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    peers = fetch_and_validate(manifest)
    result: dict[str, Any] = {
        "status": "validated",
        "peer_set_key": manifest["peer_set_key"],
        "peer_count": len(peers),
        "peers": [{key: row[key] for key in ("symbol", "source_url", "content_hash", "content_bytes", "matched_phrases")} for row in peers],
        "persisted": False,
        "broker_write_allowed": False,
    }
    if args.persist:
        result["database"] = persist(manifest, peers, args.actor)
        result["persisted"] = True
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
