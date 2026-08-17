from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Callable


QueryFn = Callable[[str], list[dict[str, Any]]]

STOP_WORDS = {
    "about", "after", "before", "brief", "build", "company", "decision",
    "evidence", "full", "india", "indian", "investment", "latest", "market",
    "prepare", "research", "review", "start", "the", "this", "today", "workflow",
}

MATERIAL_PATTERNS: tuple[tuple[str, int, str], ...] = (
    (r"\b(results?|earnings?|revenue|profit|loss|guidance)\b", 3, "financial_result"),
    (r"\b(merger|demerger|acquisition|takeover|open offer|buyback|delisting)\b", 5, "corporate_action"),
    (r"\b(default|insolvency|bankruptcy|fraud|investigation|penalty|ban)\b", 5, "adverse_event"),
    (r"\b(order|contract|approval|licen[cs]e|launch|capacity|capex)\b", 2, "operating_event"),
    (r"\b(rating|downgrade|upgrade|stake|promoter|pledge|dividend)\b", 3, "capital_or_rating_event"),
    (r"\b(rbi|sebi|nse|bse|regulator|policy|rate decision|inflation)\b", 2, "regulatory_or_macro_event"),
)


def sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def topic_tokens(subject: str) -> list[str]:
    tokens = [
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9&.-]{2,39}", subject)
        if token.lower() not in STOP_WORDS
    ]
    return list(dict.fromkeys(tokens))[:6]


def materiality_for_news(item: dict[str, Any]) -> dict[str, Any]:
    title = str(item.get("title") or "").strip()
    score = 0
    reasons: list[str] = []
    for pattern, weight, reason in MATERIAL_PATTERNS:
        if re.search(pattern, title, flags=re.IGNORECASE):
            score += weight
            reasons.append(reason)
    relevance = item.get("relevance_score")
    try:
        numeric_relevance = float(relevance) if relevance is not None else 0.0
    except (TypeError, ValueError):
        numeric_relevance = 0.0
    if numeric_relevance >= 0.8:
        score += 2
        reasons.append("high_source_relevance")
    elif numeric_relevance >= 0.6:
        score += 1
        reasons.append("moderate_source_relevance")
    return {
        "score": score,
        "reasons": list(dict.fromkeys(reasons)),
        "material": score >= 3,
    }


def _news_query(subject: str, symbol: str, lookback_hours: int, *, matched: bool) -> str:
    filters: list[str] = []
    if symbol:
        filters.extend(
            [
                f"{sql_literal(symbol.upper())}=ANY(coalesce(symbols,ARRAY[]::TEXT[]))",
                f"upper(title) LIKE {sql_literal('%' + symbol.upper() + '%')}",
            ]
        )
    for token in topic_tokens(subject):
        filters.extend(
            [
                f"lower(title) LIKE {sql_literal('%' + token + '%')}",
                f"{sql_literal(token)}=ANY(coalesce(topics,ARRAY[]::TEXT[]))",
            ]
        )
    match_clause = " AND (" + " OR ".join(filters) + ")" if matched and filters else ""
    return f"""
        SELECT id,source_name,source_url,title,publisher,author,
               published_at,captured_at,symbols,topics,geography,relevance_score
        FROM market.news_items
        WHERE captured_at >= now() - make_interval(hours => {lookback_hours})
          AND source_url IS NOT NULL AND btrim(source_url) <> ''
          {match_clause}
        ORDER BY coalesce(published_at,captured_at) DESC,id DESC
        LIMIT 8
    """


def build_public_market_evidence_packet(query: QueryFn, payload: dict[str, Any]) -> dict[str, Any]:
    subject = re.sub(r"\s+", " ", str(payload.get("subject") or payload.get("objective") or "").strip())[:500]
    symbol = re.sub(r"[^A-Za-z0-9&.-]", "", str(payload.get("symbol") or "").upper())[:30]
    lookback_hours = bounded_int(payload.get("lookback_hours"), 72, 6, 168)
    raw_source_ids = payload.get("source_ids") or payload.get("sourceIds") or []
    if isinstance(raw_source_ids, str):
        raw_source_ids = [part.strip() for part in raw_source_ids.split(",") if part.strip()]
    source_ids = []
    for value in raw_source_ids if isinstance(raw_source_ids, list) else []:
        try:
            source_ids.append(int(value))
        except (TypeError, ValueError):
            continue
    source_ids = list(dict.fromkeys(source_ids))[:50]

    first_party_evidence: list[dict[str, Any]] = []
    if source_ids:
        first_party_evidence = query(
            f"""
            SELECT artifact.id AS raw_artifact_id,artifact.title,artifact.content_hash,
                   artifact.mime_type,artifact.captured_at,ingestion.id AS ingestion_id,
                   ingestion.status AS ingestion_status,ingestion.promotion_status,
                   ingestion.updated_at,ingestion.task_id,
                   count(vector.qdrant_point_id) AS indexed_chunk_count,
                   'user_supplied_first_party'::text AS provenance,
                   'personal_research'::text AS scope,
                   false AS current_market_fact_eligible
            FROM core.raw_artifacts artifact
            JOIN core.local_artifact_ingestions ingestion ON ingestion.raw_artifact_id=artifact.id
            LEFT JOIN knowledge.vector_documents vector
              ON vector.collection_name='research_reports_qwen3_embedding_0_6b'
             AND vector.source_table='core.raw_artifacts'
             AND vector.source_id=artifact.id::text
            WHERE artifact.id IN ({','.join(str(value) for value in source_ids)})
              AND ingestion.source_path LIKE 'first_party_research:%'
            GROUP BY artifact.id,artifact.title,artifact.content_hash,artifact.mime_type,
                     artifact.captured_at,ingestion.id,ingestion.status,
                     ingestion.promotion_status,ingestion.updated_at,ingestion.task_id
            ORDER BY artifact.id
            """
        )

    news = query(_news_query(subject, symbol, lookback_hours, matched=True))
    selection_mode = "subject_match"
    if not news:
        news = query(_news_query(subject, symbol, lookback_hours, matched=False))
        selection_mode = "latest_public_fallback"

    for item in news:
        item["materiality"] = materiality_for_news(item)

    quotes: list[dict[str, Any]] = []
    if symbol:
        quotes = query(
            f"""
            SELECT provider,provider_symbol,symbol,exchange,instrument_type,last_price,
                   volume,open_interest,bid_price,ask_price,day_open,day_high,day_low,
                   previous_close,change_percent,exchange_timestamp,last_trade_timestamp,
                   received_at,source_mode,broker_write_allowed
            FROM market.live_quote_state
            WHERE upper(symbol)={sql_literal(symbol)}
               OR upper(provider_symbol)={sql_literal(symbol)}
               OR upper(symbol) LIKE {sql_literal('%' + symbol + '%')}
            ORDER BY received_at DESC
            LIMIT 3
            """
        )

    events: list[dict[str, Any]] = []
    if symbol:
        events = query(
            f"""
            SELECT id,source_key,exchange,symbol,company_name,event_date,event_type,
                   purpose,description,source_url,captured_at
            FROM market.corporate_event_calendar
            WHERE event_date BETWEEN current_date - 7 AND current_date + 45
              AND (upper(symbol)={sql_literal(symbol)}
                   OR upper(company_name) LIKE {sql_literal('%' + symbol + '%')})
            ORDER BY event_date,id
            LIMIT 5
            """
        )

    freshness_source_keys = (
        "'global_news','zerodha_live','tick_ohlcv_aggregation'"
        if symbol
        else "'global_news'"
    )
    freshness = query(
        f"""
        SELECT DISTINCT ON (source_key)
               source_key,source_name,freshness_target_minutes,latest_check_at,
               latest_ok_at,latest_quote_at,staleness_minutes,status,severity,rows_seen
        FROM core.data_source_freshness_checks
        WHERE source_key IN ({freshness_source_keys})
        ORDER BY source_key,latest_check_at DESC NULLS LAST,created_at DESC
        """
    )
    freshness_by_key = {str(row.get("source_key")): row for row in freshness}
    missing_evidence: list[str] = []
    warnings: list[str] = []
    global_news = freshness_by_key.get("global_news") or {}
    if not news:
        missing_evidence.append("No cited public news row was available inside the bounded lookback.")
    if str(global_news.get("status") or "").lower() not in {"fresh", "ok", "current"}:
        missing_evidence.append("The curated public-news source did not pass its current freshness gate.")
    if symbol and not quotes:
        warnings.append(f"No read-only live quote matched {symbol}; price-dependent conclusions are unavailable.")
    if not events:
        warnings.append("No matching stored corporate event was found; this is a bounded evidence gap.")
    if source_ids and len(first_party_evidence) != len(source_ids):
        missing_evidence.append("One or more requested first-party source IDs were absent or outside the authorized personal-research scope.")
    if first_party_evidence:
        warnings.append("User-supplied evidence is historical context only; every current claim requires fresh public or official corroboration.")
    warnings.append("Official filing, transcript, company-fundamental, valuation, and portfolio-fit evidence are not included unless a downstream node finds accepted source rows.")

    quality_status = "blocked" if missing_evidence else ("warning" if warnings else "passed")
    canonical = {
        "subject": subject,
        "symbol": symbol,
        "lookback_hours": lookback_hours,
        "news": [
            {
                "id": row.get("id"),
                "url": row.get("source_url"),
                "published_at": row.get("published_at"),
                "captured_at": row.get("captured_at"),
            }
            for row in news
        ],
        "quotes": [
            {
                "provider": row.get("provider"),
                "symbol": row.get("symbol"),
                "received_at": row.get("received_at"),
            }
            for row in quotes
        ],
        "events": [{"id": row.get("id"), "captured_at": row.get("captured_at")} for row in events],
        "freshness": [
            {
                "source_key": row.get("source_key"),
                "latest_check_at": row.get("latest_check_at"),
                "status": row.get("status"),
            }
            for row in freshness
        ],
        "first_party_evidence": [
            {
                "raw_artifact_id": row.get("raw_artifact_id"),
                "content_hash": row.get("content_hash"),
                "updated_at": row.get("updated_at"),
                "indexed_chunk_count": row.get("indexed_chunk_count"),
            }
            for row in first_party_evidence
        ],
    }
    source_fingerprint = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()

    return {
        "packet_version": "public_market_evidence_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "subject": subject,
        "symbol": symbol or None,
        "lookback_hours": lookback_hours,
        "selection_mode": selection_mode,
        "source_fingerprint": source_fingerprint,
        "quality": {
            "status": quality_status,
            "news_count": len(news),
            "quote_count": len(quotes),
            "event_count": len(events),
            "freshness_count": len(freshness),
            "first_party_evidence_count": len(first_party_evidence),
            "missing_evidence": missing_evidence,
            "warnings": warnings,
            "capital_action_allowed": False,
            "live_execution_allowed": False,
            "broker_write_allowed": False,
        },
        "news": news,
        "quotes": quotes,
        "events": events,
        "freshness": freshness,
        "first_party_evidence": first_party_evidence,
        "evidence_boundary": {
            "user_supplied_evidence_is_current_fact": False,
            "fresh_external_corroboration_required": True,
            "capital_action_allowed": False,
            "live_execution_allowed": False,
        },
    }

