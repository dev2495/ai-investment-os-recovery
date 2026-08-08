#!/usr/bin/env python3
"""Collect source-backed option valuation candidates without activating policy."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import re
import sys
import urllib.request
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

try:
    from runtime_storage import artifact_reference, artifact_root
    from sync_zerodha_market_data import query_json, quote_batches
    from sync_zerodha_read_only import keychain_token, psql, sql_literal
except ModuleNotFoundError:
    from _ai_os_runtime.scripts.runtime_storage import artifact_reference, artifact_root
    from _ai_os_runtime.scripts.sync_zerodha_market_data import query_json, quote_batches
    from _ai_os_runtime.scripts.sync_zerodha_read_only import keychain_token, psql, sql_literal


DASHBOARD_PAGE = "https://www.niftyindices.com/reports/index-dashboard"
DEFAULT_DASHBOARD = "https://www.niftyindices.com/Index_Dashboard/Index%20Dashboard_JUL2026.pdf"
ARTIFACT_ROOT = artifact_root("option_valuation_sources")
TBILL_NAME = re.compile(r"GOI\s+TBILL\s+91D-(\d{2})/(\d{2})/(\d{2})", re.IGNORECASE)


def utc(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_tbill_maturity(name: str) -> date | None:
    match = TBILL_NAME.search(name or "")
    if not match:
        return None
    day, month, year = (int(item) for item in match.groups())
    return date(2000 + year, month, day)


def continuous_zero_rate(price: float, days_to_maturity: int) -> float:
    if not 0 < price <= 100:
        raise ValueError("T-bill price must be greater than zero and no more than 100")
    if days_to_maturity <= 0:
        raise ValueError("T-bill maturity must be in the future")
    return -math.log(price / 100.0) / (days_to_maturity / 365.0)


def choose_tbill(rows: list[dict], as_of: date, minimum_days: int = 30, maximum_days: int = 100) -> dict:
    eligible: list[tuple[int, dict]] = []
    for row in rows:
        maturity = parse_tbill_maturity(str(row.get("name") or ""))
        if maturity is None:
            continue
        remaining = (maturity - as_of).days
        if minimum_days <= remaining <= maximum_days:
            eligible.append((remaining, {**row, "maturity": maturity.isoformat(), "days_to_maturity": remaining}))
    if not eligible:
        raise RuntimeError("no eligible 91-day GoI T-bill exists in the instrument cache")
    return min(eligible, key=lambda item: abs(item[0] - 60))[1]


def extract_dashboard_yields(text: str) -> dict[str, float]:
    normalized = re.sub(r"[ \t]+", " ", text.replace("\u00a0", " "))
    aliases = {"NIFTY": "Nifty 50", "BANKNIFTY": "Nifty Bank"}
    results: dict[str, float] = {}
    for underlying, label in aliases.items():
        candidates = [line.strip() for line in normalized.splitlines() if line.strip().lower().startswith(label.lower())]
        for line in candidates:
            numbers = re.findall(r"(?<![A-Za-z])(-?\d+(?:\.\d+)?)", line[len(label):])
            if numbers:
                value = float(numbers[-1])
                if 0 <= value <= 20:
                    results[underlying] = value / 100.0
                    break
    missing = sorted(set(aliases) - set(results))
    if missing:
        raise ValueError("dashboard dividend yield missing for: " + ", ".join(missing))
    return results


def fetch(url: str, accept: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "AI-Investment-OS/1.0 source collector", "Accept": accept},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def discover_dashboard_url() -> str:
    try:
        html = fetch(DASHBOARD_PAGE, "text/html,*/*").decode("utf-8", "replace")
        urls = re.findall(r'https?://[^"\']+Index(?:%20|\s)Dashboard[^"\']+\.pdf', html, re.IGNORECASE)
        if urls:
            return urls[0].replace(" ", "%20")
        paths = re.findall(r'["\']([^"\']*Index_Dashboard/[^"\']+\.pdf)["\']', html, re.IGNORECASE)
        if paths:
            return urllib.request.urljoin(DASHBOARD_PAGE, paths[0].replace(" ", "%20"))
    except Exception:
        pass
    return os.environ.get("AI_OS_NSE_INDEX_DASHBOARD_URL", DEFAULT_DASHBOARD).strip()


def pdf_text(payload: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf runtime is required for the official NSE dashboard") from exc
    return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(payload)).pages)


def insert_artifact(kind: str, title: str, source_url: str, path: Path, payload_hash: str, metadata: dict) -> int:
    raw = psql(
        "INSERT INTO core.raw_artifacts "
        "(artifact_type,title,source_url,local_path,content_hash,mime_type,sensitivity,metadata) VALUES ("
        f"{sql_literal(kind)},{sql_literal(title)},{sql_literal(source_url)},"
        f"{sql_literal(artifact_reference(path))},{sql_literal(payload_hash)},"
        f"{sql_literal('application/pdf' if path.suffix == '.pdf' else 'application/json')},'internal',"
        f"{sql_literal(json.dumps(metadata, separators=(',', ':'), default=str))}::jsonb) "
        "ON CONFLICT (source_system_id,source_url,local_path,content_hash) DO UPDATE SET metadata=EXCLUDED.metadata "
        "RETURNING id"
    )
    return int(next(line.strip() for line in raw.splitlines() if line.strip().isdigit()))


def insert_observation(row: dict) -> int:
    raw = psql(
        "INSERT INTO trading.option_valuation_source_observations "
        "(observation_key,source_kind,metric_kind,provider,exchange,underlying,instrument_identifier,"
        "value_decimal,observed_at,valid_until,source_url,raw_artifact_id,content_hash,calculation_method,"
        "calculation_inputs,quality_status,quality_checks,collected_by,broker_write_allowed) VALUES ("
        f"{sql_literal(row['observation_key'])},{sql_literal(row['source_kind'])},{sql_literal(row['metric_kind'])},"
        f"{sql_literal(row['provider'])},{sql_literal(row.get('exchange'))},{sql_literal(row.get('underlying'))},"
        f"{sql_literal(row.get('instrument_identifier'))},{row['value_decimal']},"
        f"{sql_literal(row['observed_at'])}::timestamptz,{sql_literal(row['valid_until'])}::timestamptz,"
        f"{sql_literal(row['source_url'])},{int(row['raw_artifact_id'])},{sql_literal(row['content_hash'])},"
        f"{sql_literal(row['calculation_method'])},{sql_literal(json.dumps(row['calculation_inputs'], separators=(',', ':'), default=str))}::jsonb,"
        f"{sql_literal(row['quality_status'])},{sql_literal(json.dumps(row['quality_checks'], separators=(',', ':'), default=str))}::jsonb,"
        f"{sql_literal(row['collected_by'])},false) "
        "ON CONFLICT (observation_key) DO UPDATE SET quality_status=EXCLUDED.quality_status,quality_checks=EXCLUDED.quality_checks "
        "RETURNING id"
    )
    return int(next(line.strip() for line in raw.splitlines() if line.strip().isdigit()))


def collect_rate(actor: str) -> dict:
    api_key = os.environ.get("AI_OS_ZERODHA_API_KEY", "").strip()
    token = keychain_token()
    if not api_key or not token:
        raise RuntimeError("a current read-only Zerodha session is required")
    rows = query_json(
        "SELECT trading_symbol,name,exchange FROM market.zerodha_instruments "
        "WHERE active=true AND exchange='NSE' AND name ILIKE 'GOI TBILL 91D-%' ORDER BY trading_symbol"
    )
    selected = choose_tbill(rows, datetime.now(timezone.utc).date())
    identifier = f"NSE:{selected['trading_symbol']}"
    quote = quote_batches(api_key, token, [identifier]).get(identifier)
    if not isinstance(quote, dict):
        raise RuntimeError("Zerodha returned no quote for " + identifier)
    price = float(quote.get("last_price") or 0)
    quote_at = utc(quote.get("timestamp") or datetime.now(timezone.utc).isoformat())
    age_seconds = max(0, int((datetime.now(timezone.utc) - quote_at).total_seconds()))
    if age_seconds > 4 * 24 * 3600:
        raise RuntimeError("T-bill quote is stale; source candidate was not promoted")
    rate = continuous_zero_rate(price, int(selected["days_to_maturity"]))
    if not 0 <= rate <= 0.25:
        raise RuntimeError("derived T-bill rate failed the reasonableness check")
    payload = json.dumps({"identifier": identifier, "instrument": selected, "quote": quote}, sort_keys=True, separators=(",", ":"), default=str).encode()
    digest = hashlib.sha256(payload).hexdigest()
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_ROOT / f"zerodha-tbill-{quote_at.strftime('%Y%m%dT%H%M%SZ')}-{digest[:12]}.json"
    path.write_bytes(payload)
    artifact_id = insert_artifact("option_valuation_rate_source", selected["name"], "https://kite.trade/docs/connect/v3/market-quotes/", path, digest, {"read_only": True})
    observation_id = insert_observation({
        "observation_key": f"zerodha-tbill:{identifier}:{quote_at.isoformat()}",
        "source_kind": "zerodha_tbill_zero_rate", "metric_kind": "risk_free_rate",
        "provider": "Zerodha", "exchange": "NSE", "underlying": None,
        "instrument_identifier": identifier, "value_decimal": rate,
        "observed_at": quote_at.isoformat(),
        "valid_until": min(quote_at + timedelta(days=7), datetime.combine(date.fromisoformat(selected["maturity"]), time.min, timezone.utc)).isoformat(),
        "source_url": "https://kite.trade/docs/connect/v3/market-quotes/", "raw_artifact_id": artifact_id,
        "content_hash": digest, "calculation_method": "-ln(clean_price/100)/(days_to_maturity/365)",
        "calculation_inputs": {"clean_price": price, "days_to_maturity": selected["days_to_maturity"], "maturity": selected["maturity"]},
        "quality_status": "passed" if int(quote.get("volume") or 0) > 0 else "warning",
        "quality_checks": {"freshness_age_seconds": age_seconds, "price_in_range": True, "rate_in_range": True, "volume": int(quote.get("volume") or 0)},
        "collected_by": actor,
    })
    return {"observation_id": observation_id, "identifier": identifier, "value_decimal": rate, "quality_status": "passed" if int(quote.get("volume") or 0) > 0 else "warning"}


def collect_dividends(actor: str) -> list[dict]:
    url = discover_dashboard_url()
    payload = fetch(url, "application/pdf,*/*")
    if not payload.startswith(b"%PDF"):
        raise RuntimeError("NSE index dashboard response was not a PDF")
    digest = hashlib.sha256(payload).hexdigest()
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_ROOT / f"nse-index-dashboard-{digest[:12]}.pdf"
    path.write_bytes(payload)
    yields = extract_dashboard_yields(pdf_text(payload))
    observed = datetime.now(timezone.utc)
    artifact_id = insert_artifact("option_valuation_dividend_source", "NSE Indices Index Dashboard", url, path, digest, {"official_source": True, "parsed_underlyings": sorted(yields)})
    results = []
    for underlying, value in yields.items():
        observation_id = insert_observation({
            "observation_key": f"nse-index-dashboard:{digest}:{underlying}",
            "source_kind": "nse_index_dashboard_dividend", "metric_kind": "dividend_yield",
            "provider": "NSE Indices", "exchange": "NSE", "underlying": underlying,
            "instrument_identifier": None, "value_decimal": value,
            "observed_at": observed.isoformat(), "valid_until": (observed + timedelta(days=45)).isoformat(),
            "source_url": url, "raw_artifact_id": artifact_id, "content_hash": digest,
            "calculation_method": "published index dividend yield percent / 100",
            "calculation_inputs": {"published_percent": value * 100},
            "quality_status": "passed", "quality_checks": {"official_pdf": True, "value_in_range": 0 <= value <= 0.20},
            "collected_by": actor,
        })
        results.append({"observation_id": observation_id, "underlying": underlying, "value_decimal": value, "quality_status": "passed"})
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor", default="Options Data Quality Agent")
    parser.add_argument("--sources", nargs="+", choices=["rate", "dividends"], default=["rate", "dividends"])
    args = parser.parse_args()
    result: dict[str, object] = {"status": "completed", "activated_policy": False, "broker_write_allowed": False}
    try:
        if "rate" in args.sources:
            result["rate"] = collect_rate(args.actor)
        if "dividends" in args.sources:
            result["dividends"] = collect_dividends(args.actor)
        result["candidates"] = query_json("SELECT * FROM trading.v_option_valuation_source_candidates ORDER BY underlying")
    except Exception as exc:
        result.update({"status": "failed", "error": f"{type(exc).__name__}: {exc}"[:1500]})
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
