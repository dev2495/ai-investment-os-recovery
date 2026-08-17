#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from run_strategy_backtest import run_psql_json, sql_jsonb, sql_literal
from run_trade_journal_strategy_mining import sql_numeric, sql_text_array


RUNTIME_ROOT = Path(os.environ.get("AI_OS_RUNTIME_ROOT") or Path(__file__).absolute().parents[1])
USER_AGENT = os.environ.get(
    "AI_OS_PUBLIC_CHECK_USER_AGENT",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 AI-OS-Research/0.1",
)
MAX_FEED_BYTES = 8_000_000

MATERIAL_KEYWORDS: list[tuple[str, float, float, str]] = [
    ("demerger", 0.82, 0.58, "special_situation"),
    ("de-merger", 0.82, 0.58, "special_situation"),
    ("merger", 0.78, 0.62, "special_situation"),
    ("amalgamation", 0.78, 0.62, "special_situation"),
    ("reverse merger", 0.86, 0.66, "special_situation"),
    ("buyback", 0.74, 0.45, "capital_return"),
    ("open offer", 0.78, 0.58, "special_situation"),
    ("delisting", 0.8, 0.68, "special_situation"),
    ("rights issue", 0.62, 0.52, "corporate_action"),
    ("preferential", 0.6, 0.56, "corporate_action"),
    ("pledge", 0.55, 0.7, "governance_risk"),
    ("insolvency", 0.58, 0.84, "distress"),
    ("nclt", 0.62, 0.74, "special_situation"),
    ("block deal", 0.58, 0.48, "market_structure"),
    ("bulk deal", 0.54, 0.48, "market_structure"),
    ("record date", 0.5, 0.35, "corporate_action"),
    ("bonus", 0.48, 0.32, "corporate_action"),
    ("split", 0.48, 0.32, "corporate_action"),
]


def strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def stable_hash(*values: object) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(str(value or "").encode("utf-8", errors="ignore"))
        digest.update(b"\x1f")
    return digest.hexdigest()[:24]


def parse_ts(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    try:
        parsed = parsedate_to_datetime(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, IndexError):
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%d %b %Y %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            continue
    return None


def fetch_json(sql: str) -> list[dict[str, Any]]:
    return run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            {sql}
        ) rows
        """
    )


def active_feeds(limit: int, feed_keys: list[str]) -> list[dict[str, Any]]:
    key_filter = ""
    if feed_keys:
        key_filter = f"AND feed_key = ANY({sql_text_array(feed_keys)})"
    return fetch_json(
        f"""
        SELECT id, feed_key, feed_name, feed_type, provider, url, geography,
               symbols, topics, status, owner_agent, metadata
        FROM research.feed_registry
        WHERE status = 'active'
          AND feed_type IN ('news_rss', 'investor_blog_rss', 'rss', 'rss_http')
          AND url IS NOT NULL
          {key_filter}
        ORDER BY feed_name
        LIMIT {max(1, limit)}
        """
    )


def symbol_universe() -> list[str]:
    rows = fetch_json(
        """
        SELECT DISTINCT upper(symbol) AS symbol
        FROM (
            SELECT symbol FROM trading.symbols WHERE symbol IS NOT NULL
            UNION ALL
            SELECT normalized_symbol AS symbol FROM trading.instrument_watchlist WHERE normalized_symbol IS NOT NULL
            UNION ALL
            SELECT base_asset AS symbol FROM trading.instrument_watchlist WHERE base_asset IS NOT NULL
            UNION ALL
            SELECT symbol FROM research.v_watchlist_board WHERE status='active' AND symbol IS NOT NULL
            UNION ALL
            SELECT symbol FROM portfolio.positions WHERE symbol IS NOT NULL
        ) symbols
        WHERE length(symbol) BETWEEN 2 AND 20
        ORDER BY symbol
        LIMIT 1000
        """
    )
    return [str(row["symbol"]).upper() for row in rows if row.get("symbol")]


def match_symbols(text: str, universe: list[str]) -> list[str]:
    clean_text = " " + re.sub(r"[^A-Za-z0-9]+", " ", text.upper()) + " "
    matches: list[str] = []
    for symbol in universe:
        if f" {symbol} " in clean_text:
            matches.append(symbol)
    return matches[:8]


def materiality(text: str) -> tuple[float, float, list[str], str]:
    lowered = text.lower()
    best_relevance = 0.35
    best_risk = 0.35
    topics: list[str] = []
    label = "market_news"
    for keyword, relevance, risk, topic in MATERIAL_KEYWORDS:
        if keyword in lowered:
            best_relevance = max(best_relevance, relevance)
            best_risk = max(best_risk, risk)
            if topic not in topics:
                topics.append(topic)
            label = topic
    if "result" in lowered or "earnings" in lowered or "profit" in lowered:
        best_relevance = max(best_relevance, 0.56)
        if "earnings" not in topics:
            topics.append("earnings")
    if not topics:
        topics.append("market_news")
    return best_relevance, best_risk, topics, label


def read_feed(url: str, per_feed: int, timeout: int) -> tuple[int | None, list[dict[str, Any]], str | None, int]:
    started = time.monotonic()
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml, text/xml, */*"})
    status: int | None = None
    body = b""
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=max(5, timeout)) as response:
                status = int(getattr(response, "status", 200))
                body = response.read(MAX_FEED_BYTES + 1)
                if len(body) > MAX_FEED_BYTES:
                    return status, [], "FeedTooLarge: response exceeded 8 MB safety limit", int((time.monotonic() - started) * 1000)
            last_error = None
            break
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                break
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == 2:
                break
        time.sleep(2**attempt)
    if last_error is not None:
        return status, [], f"{type(last_error).__name__}: {last_error}", int((time.monotonic() - started) * 1000)
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        return status, [], f"ParseError: {exc}", int((time.monotonic() - started) * 1000)

    items: list[dict[str, Any]] = []
    rss_items = root.findall(".//item")
    atom_entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
    for item in rss_items[:per_feed]:
        title = strip_html(item.findtext("title") or "")
        link = strip_html(item.findtext("link") or "")
        published = item.findtext("pubDate") or item.findtext("published") or item.findtext("updated")
        summary = strip_html(item.findtext("description") or item.findtext("summary") or "")
        if title:
            items.append({"title": title, "link": link, "published_at": parse_ts(published), "summary": summary})
    for entry in atom_entries[:per_feed]:
        title = strip_html(entry.findtext("{http://www.w3.org/2005/Atom}title") or "")
        link = ""
        for link_el in entry.findall("{http://www.w3.org/2005/Atom}link"):
            href = link_el.attrib.get("href")
            if href:
                link = href
                break
        published = entry.findtext("{http://www.w3.org/2005/Atom}published") or entry.findtext("{http://www.w3.org/2005/Atom}updated")
        summary = strip_html(entry.findtext("{http://www.w3.org/2005/Atom}summary") or "")
        if title:
            items.append({"title": title, "link": link, "published_at": parse_ts(published), "summary": summary})
    return status, items[:per_feed], None, int((time.monotonic() - started) * 1000)


def record_feed_check(feed: dict[str, Any], http_status: int | None, items: list[dict[str, Any]], error: str | None, latency_ms: int) -> None:
    status = "ok" if not error and items else ("empty" if not error else "error")
    sample = {
        "feed_key": feed.get("feed_key"),
        "feed_type": feed.get("feed_type"),
        "provider": feed.get("provider"),
        "sample_titles": [str(item.get("title") or "")[:240] for item in items[:3]],
    }
    run_psql_json(
        f"""
        WITH inserted AS (
            INSERT INTO core.data_source_checks (
                source_key, check_name, check_type, target_url, status,
                http_status, latency_ms, rows_seen, sample_payload, error_message
            )
            VALUES (
                {sql_literal(feed.get("feed_key"))},
                {sql_literal(str(feed.get("feed_name") or feed.get("feed_key")) + " RSS ingestion")},
                'rss_http',
                {sql_literal(feed.get("url"))},
                {sql_literal(status)},
                {int(http_status) if http_status is not None else 'NULL'},
                {int(latency_ms)},
                {len(items)},
                {sql_jsonb(sample)},
                {sql_literal(error) if error else 'NULL'}
            )
            RETURNING id
        ), updated AS (
            UPDATE research.feed_registry
            SET metadata = metadata || {sql_jsonb({
                "last_check_status": status,
                "last_http_status": http_status,
                "last_rows_seen": len(items),
                "last_latency_ms": latency_ms,
                "last_error": error,
            })},
                updated_at = now()
            WHERE id = {int(feed["id"])}
            RETURNING id
        )
        SELECT jsonb_build_array(jsonb_build_object(
            'check_id', (SELECT id FROM inserted),
            'feed_id', (SELECT id FROM updated)
        ))::text
        """
    )


def start_run(run_key: str, actor: str, feed_keys: list[str]) -> dict[str, Any]:
    rows = run_psql_json(
        f"""
        WITH upserted AS (
            INSERT INTO market.news_ingestion_runs (run_key, status, feed_keys, created_by, started_at)
            VALUES ({sql_literal(run_key)}, 'running', {sql_text_array(feed_keys)}, {sql_literal(actor)}, now())
            ON CONFLICT (run_key) DO UPDATE SET
                status = 'running',
                feed_keys = EXCLUDED.feed_keys,
                created_by = EXCLUDED.created_by,
                started_at = now(),
                finished_at = NULL,
                error_message = NULL
            RETURNING *
        )
        SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
        """
    )
    return rows[0]


def upsert_news_item(feed: dict[str, Any], item: dict[str, Any], symbols: list[str], topics: list[str], relevance: float) -> dict[str, Any]:
    link = item.get("link") or f"rss://{feed['feed_key']}/{stable_hash(item.get('title'), item.get('published_at'))}"
    payload = {
        "feed_key": feed.get("feed_key"),
        "summary": item.get("summary"),
        "http_adapter": "rss_http",
        "source_url": feed.get("url"),
    }
    rows = run_psql_json(
        f"""
        WITH upserted AS (
            INSERT INTO market.news_items (
                source_name, source_url, title, publisher, published_at,
                symbols, topics, geography, relevance_score, raw_payload
            )
            VALUES (
                {sql_literal(feed.get("feed_name"))},
                {sql_literal(link)},
                {sql_literal(item.get("title"))},
                {sql_literal(feed.get("provider"))},
                {sql_literal(item.get("published_at"))}::timestamptz,
                {sql_text_array(symbols)},
                {sql_text_array(topics)},
                {sql_literal(feed.get("geography"))},
                {sql_numeric(relevance)},
                {sql_jsonb(payload)}
            )
            ON CONFLICT (source_name, source_url) DO UPDATE SET
                title = EXCLUDED.title,
                publisher = EXCLUDED.publisher,
                published_at = EXCLUDED.published_at,
                symbols = EXCLUDED.symbols,
                topics = EXCLUDED.topics,
                geography = EXCLUDED.geography,
                relevance_score = EXCLUDED.relevance_score,
                raw_payload = EXCLUDED.raw_payload,
                captured_at = now()
            RETURNING id, title, source_url, symbols, topics, relevance_score
        )
        SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
        """
    )
    return rows[0]


def create_research_idea(news_row: dict[str, Any], feed: dict[str, Any], risk_score: float, label: str) -> bool:
    if float(news_row.get("relevance_score") or 0) < 0.55:
        return False
    source_ref = str(news_row["id"])
    exists = fetch_json(
        f"""
        SELECT id
        FROM research.ideas
        WHERE source_kind = 'market.news_items'
          AND source_ref = {sql_literal(source_ref)}
        LIMIT 1
        """
    )
    if exists:
        return False
    run_psql_json(
        f"""
        WITH inserted AS (
            INSERT INTO research.ideas (
                idea_type, title, symbols, source_kind, source_ref,
                thesis, catalyst, expected_timeframe, opportunity_score,
                risk_score, status, owner_agent, evidence
            )
            VALUES (
                'news_catalyst',
                {sql_literal('News catalyst: ' + str(news_row.get('title') or '')[:180])},
                {sql_text_array(news_row.get("symbols") or [])},
                'market.news_items',
                {sql_literal(source_ref)},
                {sql_literal('News-sourced catalyst requiring source validation, price reaction check, and portfolio impact review.')},
                {sql_literal(news_row.get("title"))},
                'intraday_to_swing',
                {sql_numeric(news_row.get("relevance_score"))},
                {sql_numeric(risk_score)},
                'captured',
                'News Analyst',
                {sql_jsonb([{"table": "market.news_items", "id": news_row["id"], "source_url": news_row.get("source_url"), "feed_key": feed.get("feed_key"), "label": label}])}
            )
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text FROM inserted
        """
    )
    return True


def create_inbox_item(news_row: dict[str, Any], label: str) -> bool:
    if float(news_row.get("relevance_score") or 0) < 0.7:
        return False
    source_ref = str(news_row["id"])
    exists = fetch_json(
        f"""
        SELECT id
        FROM agent.inbox_items
        WHERE title LIKE 'News catalyst:%'
          AND evidence::text LIKE {sql_literal('%"id": ' + source_ref + '%')}
        LIMIT 1
        """
    )
    if exists:
        return False
    priority = "high" if label in {"special_situation", "distress", "governance_risk"} else "medium"
    owner = "Special Situations Agent" if label == "special_situation" else "News Analyst"
    run_psql_json(
        f"""
        WITH inserted AS (
            INSERT INTO agent.inbox_items (
                title, owner_agent, status, priority, recommended_action,
                evidence, target_workspace
            )
            VALUES (
                {sql_literal('News catalyst: ' + str(news_row.get('title') or '')[:150])},
                {sql_literal(owner)},
                'queued',
                {sql_literal(priority)},
                'Validate source, check affected holdings/watchlist, compare with exchange filings, and decide if this becomes a research or strategy task.',
                {sql_jsonb([{"table": "market.news_items", "id": news_row["id"], "source_url": news_row.get("source_url"), "label": label}])},
                'research'
            )
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text FROM inserted
        """
    )
    return True


def finish_run(run_id: int, status: str, summary: dict[str, Any], error_message: str | None, duration_ms: int) -> None:
    run_psql_json(
        f"""
        WITH updated AS (
            UPDATE market.news_ingestion_runs
            SET status = {sql_literal(status)},
                feeds_checked = {int(summary.get("feeds_checked") or 0)},
                items_seen = {int(summary.get("items_seen") or 0)},
                items_upserted = {int(summary.get("items_upserted") or 0)},
                research_ideas_created = {int(summary.get("research_ideas_created") or 0)},
                inbox_items_created = {int(summary.get("inbox_items_created") or 0)},
                sample_payload = {sql_jsonb(summary)},
                error_message = {sql_literal(error_message) if error_message else 'NULL'},
                finished_at = now(),
                duration_ms = {int(duration_ms)}
            WHERE id = {int(run_id)}
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(updated)), '[]'::json)::text FROM updated
        """
    )


def record_aggregate_news_check(status: str, summary: dict[str, Any], error_message: str | None, duration_ms: int) -> None:
    check_status = "ok" if status in {"completed", "completed_with_errors"} and int(summary.get("items_upserted") or 0) > 0 else "error"
    run_psql_json(
        f"""
        WITH inserted AS (
            INSERT INTO core.data_source_checks (
                source_key, check_name, check_type, target_url, status,
                latency_ms, rows_seen, sample_payload, error_message
            )
            VALUES (
                'global_news', 'Global market news basket ingestion',
                'news_ingestion', 'rss://global-market-news-basket',
                {sql_literal(check_status)}, {int(duration_ms)},
                {int(summary.get('items_upserted') or 0)},
                {sql_jsonb(summary)},
                {sql_literal(error_message) if error_message else 'NULL'}
            )
            RETURNING checked_at
        ), updated AS (
            UPDATE core.data_source_registry
            SET last_seen_at = CASE
                    WHEN {int(summary.get('items_upserted') or 0)} > 0 THEN (SELECT checked_at FROM inserted)
                    ELSE last_seen_at
                END,
                updated_at = now()
            WHERE source_key = 'global_news'
            RETURNING source_key
        )
        SELECT jsonb_build_array(jsonb_build_object(
            'checked_at', (SELECT checked_at FROM inserted),
            'source_key', (SELECT source_key FROM updated)
        ))::text
        """
    )


def run_ingestion(args: argparse.Namespace) -> dict[str, Any]:
    feed_keys = [item.strip() for item in str(args.feed_keys or "").split(",") if item.strip()]
    run = start_run(args.run_key, args.actor, feed_keys)
    started = time.monotonic()
    universe = symbol_universe()
    feeds = active_feeds(args.feed_limit, feed_keys)
    feed_results: list[dict[str, Any]] = []
    items_seen = 0
    items_upserted = 0
    ideas_created = 0
    inbox_created = 0
    errors: list[str] = []
    for feed in feeds:
        status, items, error, latency_ms = read_feed(str(feed.get("url")), args.per_feed, args.timeout)
        record_feed_check(feed, status, items, error, latency_ms)
        if error:
            errors.append(f"{feed.get('feed_key')}: {error}")
        feed_seen = 0
        feed_upserted = 0
        for item in items:
            text = " ".join([str(item.get("title") or ""), str(item.get("summary") or "")])
            symbols = sorted(set([*match_symbols(text, universe), *[str(s).upper() for s in (feed.get("symbols") or [])]]))
            relevance, risk, material_topics, label = materiality(text)
            topics = sorted(set([*[str(t) for t in (feed.get("topics") or [])], *material_topics]))
            news_row = upsert_news_item(feed, item, symbols, topics, relevance)
            feed_seen += 1
            feed_upserted += 1
            if create_research_idea(news_row, feed, risk, label):
                ideas_created += 1
            if create_inbox_item(news_row, label):
                inbox_created += 1
        items_seen += feed_seen
        items_upserted += feed_upserted
        feed_results.append({"feed_key": feed.get("feed_key"), "http_status": status, "latency_ms": latency_ms, "items_seen": feed_seen, "items_upserted": feed_upserted, "error": error})
    duration_ms = int((time.monotonic() - started) * 1000)
    status = "completed" if not errors else ("completed_with_errors" if items_upserted > 0 else "failed")
    summary = {
        "feeds_checked": len(feeds),
        "items_seen": items_seen,
        "items_upserted": items_upserted,
        "research_ideas_created": ideas_created,
        "inbox_items_created": inbox_created,
        "feed_results": feed_results,
        "seed_data_allowed": False,
    }
    error_message = "; ".join(errors)[:4000] if errors else None
    finish_run(int(run["id"]), status, summary, error_message, duration_ms)
    record_aggregate_news_check(status, summary, error_message, duration_ms)
    return {"run_key": args.run_key, "status": status, "summary": summary, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest active RSS/news feeds into market.news_items and catalyst ideas.")
    parser.add_argument("--run-key", default=f"market_news_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
    parser.add_argument("--actor", default="News Analyst")
    parser.add_argument("--feed-keys", default="")
    parser.add_argument("--feed-limit", type=int, default=12)
    parser.add_argument("--per-feed", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=12)
    args = parser.parse_args()
    print(json.dumps(run_ingestion(args), indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
