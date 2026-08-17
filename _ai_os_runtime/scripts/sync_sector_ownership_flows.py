#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import tempfile
import time
import urllib.parse
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from collect_nse_bse_filings import run_psql_json, run_psql_text, sql_jsonb, sql_literal
from runtime_storage import artifact_reference, artifact_root


NSE_ROOT = "https://www.nseindia.com"
SHAREHOLDING_PAGE = NSE_ROOT + "/companies-listing/corporate-filings-shareholding-pattern"
DEALS_PAGE = NSE_ROOT + "/report-detail/display-bulk-and-block-deals"
SHAREHOLDING_SOURCE = "NSE corporate shareholding filings"
DEALS_SOURCE = "NSE bulk and block deal archives"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
)
OWNERSHIP_FIELDS = (
    ("promoter", "Promoter and promoter group", "pr_and_prgrp"),
    ("public", "Public shareholders", "public_val"),
    ("other", "Employee trusts", "employeeTrusts"),
)


def parse_nse_date(value: Any) -> dt.date | None:
    text = str(value or "").strip()
    if not text:
        return None
    for pattern in ("%d-%b-%Y", "%d-%B-%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def decimal_or_none(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value)) if value not in (None, "") else None
    except (InvalidOperation, ValueError):
        return None


def fingerprint(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def write_artifact(path: Path, payload: Any) -> tuple[str, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True, default=str).encode("utf-8")
    path.write_bytes(encoded)
    return artifact_reference(path), hashlib.sha256(encoded).hexdigest()


class NSESession:
    def __init__(self, artifact_dir: Path, delay_seconds: float = 0.35) -> None:
        self.artifact_dir = artifact_dir
        self.delay_seconds = delay_seconds
        descriptor, cookie_path = tempfile.mkstemp(prefix="aios-nse-", suffix=".cookies")
        os.close(descriptor)
        self.cookie_file = Path(cookie_path)
        self._primed: set[str] = set()

    def close(self) -> None:
        self.cookie_file.unlink(missing_ok=True)

    def _curl(self, url: str, referer: str, accept: str) -> bytes:
        command = [
            "curl", "--http1.1", "--fail-with-body", "--silent", "--show-error",
            "--max-time", "45", "--retry", "2", "--retry-delay", "1",
            "--cookie", str(self.cookie_file), "--cookie-jar", str(self.cookie_file),
            "--user-agent", USER_AGENT, "--header", f"Accept: {accept}",
            "--header", f"Referer: {referer}", url,
        ]
        completed = subprocess.run(command, capture_output=True, check=False, timeout=55)
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).decode("utf-8", errors="replace")[:1000]
            raise RuntimeError(f"NSE request failed: {detail}")
        return completed.stdout

    def prime(self, page: str) -> None:
        if page in self._primed:
            return
        self._curl(page, NSE_ROOT + "/", "text/html,application/xhtml+xml")
        self._primed.add(page)
        time.sleep(self.delay_seconds)

    def json(self, endpoint: str, page: str, artifact_name: str) -> tuple[Any, dict[str, Any]]:
        self.prime(page)
        raw = self._curl(endpoint, page, "application/json,text/plain,*/*")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"NSE returned invalid JSON for {endpoint}") from exc
        artifact_path, sha256 = write_artifact(self.artifact_dir / artifact_name, payload)
        time.sleep(self.delay_seconds)
        return payload, {
            "source_endpoint": endpoint,
            "artifact_path": artifact_path,
            "artifact_sha256": sha256,
            "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }


def active_members(taxonomy_key: str, as_of_date: dt.date) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT node.id AS taxonomy_node_id,node.taxonomy_key,node.node_name,
                   symbol.id AS symbol_id,upper(symbol.symbol) AS symbol,
                   upper(symbol.exchange) AS exchange
            FROM sector_intelligence.taxonomy_nodes node
            JOIN sector_intelligence.instrument_membership_history membership
              ON membership.taxonomy_node_id=node.id
             AND membership.valid_from<={sql_literal(as_of_date.isoformat())}::date
             AND (membership.valid_to IS NULL OR membership.valid_to>={sql_literal(as_of_date.isoformat())}::date)
            JOIN trading.symbols symbol ON symbol.id=membership.symbol_id
            WHERE node.taxonomy_key={sql_literal(taxonomy_key)}
              AND node.valid_from<={sql_literal(as_of_date.isoformat())}::date
              AND (node.valid_to IS NULL OR node.valid_to>={sql_literal(as_of_date.isoformat())}::date)
            ORDER BY symbol.symbol
        ) rows
        """
    )
    if not rows:
        raise ValueError("taxonomy_key has no active point-in-time constituents")
    node_ids = {int(row["taxonomy_node_id"]) for row in rows}
    if len(node_ids) != 1:
        raise ValueError("taxonomy_key must resolve to exactly one active node")
    return {
        "taxonomy_node_id": next(iter(node_ids)),
        "taxonomy_key": taxonomy_key,
        "node_name": str(rows[0]["node_name"]),
    }, rows


def source_system_ids() -> dict[str, int]:
    names = [SHAREHOLDING_SOURCE, DEALS_SOURCE]
    rows = run_psql_json(
        "SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text FROM ("
        "SELECT id,name FROM core.source_systems WHERE name IN ("
        + ",".join(sql_literal(name) for name in names)
        + ")) rows"
    )
    result = {str(row["name"]): int(row["id"]) for row in rows}
    if set(result) != set(names):
        raise RuntimeError("migration 207 source systems are not installed")
    return result


def eligible_shareholding_rows(payload: Any, as_of_date: dt.date) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    eligible = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        period_end = parse_nse_date(row.get("date"))
        available_at = parse_nse_date(row.get("submissionDate") or row.get("broadcastDate"))
        if period_end and available_at and period_end <= as_of_date and available_at <= as_of_date:
            eligible.append({**row, "_period_end": period_end, "_available_at": available_at})
    eligible.sort(key=lambda row: (row["_period_end"], row["_available_at"], str(row.get("recordId") or "")))
    return eligible


def normalize_ownership(
    rows: list[dict[str, Any]],
    member: dict[str, Any],
    node_id: int,
    source_system_id: int,
    artifact_evidence: dict[str, Any],
) -> list[dict[str, Any]]:
    previous: dict[str, Decimal] = {}
    output: list[dict[str, Any]] = []
    for row in rows:
        source_reference = str(row.get("xbrl") or artifact_evidence["source_endpoint"])
        for category, holder_name, field in OWNERSHIP_FIELDS:
            value = decimal_or_none(row.get(field))
            if value is None:
                continue
            change = value - previous[category] if category in previous else None
            previous[category] = value
            evidence = [{
                **artifact_evidence,
                "record_id": str(row.get("recordId") or ""),
                "submission_date": row["_available_at"].isoformat(),
                "period_end": row["_period_end"].isoformat(),
                "xbrl_url": str(row.get("xbrl") or ""),
                "source_field": field,
                "symbol": member["symbol"],
                "exchange": member["exchange"],
            }]
            output.append({
                "symbol_id": int(member["symbol_id"]),
                "taxonomy_node_id": node_id,
                "period_end": row["_period_end"].isoformat(),
                "holder_category": category,
                "holder_name": holder_name,
                "holding_percent": value,
                "shares_held": None,
                "pledged_percent": None,
                "change_percent_points": change,
                "observation_type": "shareholding_pattern",
                "source_system_id": source_system_id,
                "source_reference": source_reference,
                "evidence": evidence,
            })
    return output


def normalize_deals(
    payload: Any,
    member: dict[str, Any],
    node_id: int,
    source_system_id: int,
    flow_type: str,
    artifact_evidence: dict[str, Any],
    as_of_date: dt.date,
) -> list[dict[str, Any]]:
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []
    output = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        trade_date = parse_nse_date(row.get("BD_DT_DATE"))
        quantity = decimal_or_none(row.get("BD_QTY_TRD"))
        price = decimal_or_none(row.get("BD_TP_WATP"))
        side = str(row.get("BD_BUY_SELL") or "").strip().upper()
        if not trade_date or trade_date > as_of_date or not quantity or not price or side not in {"BUY", "SELL"}:
            continue
        traded_value = quantity * price
        row_fingerprint = fingerprint({
            "flow_type": flow_type,
            "date": trade_date.isoformat(),
            "symbol": str(row.get("BD_SYMBOL") or member["symbol"]),
            "client": str(row.get("BD_CLIENT_NAME") or ""),
            "side": side,
            "quantity": str(quantity),
            "price": str(price),
        })
        evidence = [{
            **artifact_evidence,
            "row_fingerprint": row_fingerprint,
            "client_name": str(row.get("BD_CLIENT_NAME") or ""),
            "side": side,
            "quantity": str(quantity),
            "price": str(price),
            "symbol": member["symbol"],
            "exchange": member["exchange"],
            "actor_classification": "institution",
            "actor_inference_used": False,
        }]
        output.append({
            "taxonomy_node_id": node_id,
            "symbol_id": int(member["symbol_id"]),
            "observed_at": trade_date.isoformat() + "T15:30:00+05:30",
            "flow_actor": "institution",
            "flow_type": flow_type,
            "buy_value": traded_value if side == "BUY" else None,
            "sell_value": traded_value if side == "SELL" else None,
            "net_value": traded_value if side == "BUY" else -traded_value,
            "currency": "INR",
            "source_system_id": source_system_id,
            "source_reference": DEALS_PAGE + "#" + row_fingerprint,
            "evidence": evidence,
        })
    return output


def persist_rows(ownership: list[dict[str, Any]], flows: list[dict[str, Any]]) -> dict[str, int]:
    ownership_values = []
    for row in ownership:
        ownership_values.append("(" + ",".join([
            str(row["symbol_id"]), str(row["taxonomy_node_id"]), sql_literal(row["period_end"]) + "::date",
            sql_literal(row["holder_category"]), sql_literal(row["holder_name"]),
            str(row["holding_percent"]), "NULL", "NULL",
            str(row["change_percent_points"]) if row["change_percent_points"] is not None else "NULL",
            sql_literal(row["observation_type"]), str(row["source_system_id"]),
            sql_literal(row["source_reference"]), sql_jsonb(row["evidence"]),
        ]) + ")")
    flow_values = []
    for row in flows:
        flow_values.append("(" + ",".join([
            str(row["taxonomy_node_id"]), str(row["symbol_id"]), sql_literal(row["observed_at"]) + "::timestamptz",
            sql_literal(row["flow_actor"]), sql_literal(row["flow_type"]),
            str(row["buy_value"]) if row["buy_value"] is not None else "NULL",
            str(row["sell_value"]) if row["sell_value"] is not None else "NULL",
            str(row["net_value"]), sql_literal(row["currency"]), str(row["source_system_id"]),
            sql_literal(row["source_reference"]), sql_jsonb(row["evidence"]),
        ]) + ")")
    statements = ["BEGIN;"]
    if ownership_values:
        statements.append(
            "INSERT INTO sector_intelligence.ownership_observations "
            "(symbol_id,taxonomy_node_id,period_end,holder_category,holder_name,holding_percent,"
            "shares_held,pledged_percent,change_percent_points,observation_type,source_system_id,source_reference,evidence) VALUES "
            + ",".join(ownership_values)
            + " ON CONFLICT (symbol_id,period_end,holder_category,holder_name,observation_type,source_reference) DO UPDATE SET "
            "holding_percent=EXCLUDED.holding_percent,change_percent_points=EXCLUDED.change_percent_points,"
            "source_system_id=EXCLUDED.source_system_id,evidence=EXCLUDED.evidence"
        )
    if flow_values:
        statements.append(
            "INSERT INTO sector_intelligence.flow_observations "
            "(taxonomy_node_id,symbol_id,observed_at,flow_actor,flow_type,buy_value,sell_value,net_value,currency,"
            "source_system_id,source_reference,evidence) VALUES "
            + ",".join(flow_values) + " ON CONFLICT DO NOTHING"
        )
    statements.append("COMMIT;")
    run_psql_text(";".join(statements))
    return {"ownership_rows_submitted": len(ownership), "flow_rows_submitted": len(flows)}


def collect(
    taxonomy_key: str,
    as_of_date: dt.date,
    lookback_days: int,
    persist: bool,
    actor: str,
) -> dict[str, Any]:
    node, members = active_members(taxonomy_key, as_of_date)
    systems = source_system_ids()
    safe_key = taxonomy_key.replace(":", "_").replace("/", "_")
    artifact_dir = artifact_root("sector_ownership_flows") / safe_key / as_of_date.isoformat()
    session = NSESession(artifact_dir)
    ownership: list[dict[str, Any]] = []
    flows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    from_date = as_of_date - dt.timedelta(days=lookback_days)
    try:
        for member in members:
            symbol = str(member["symbol"])
            try:
                share_endpoint = NSE_ROOT + "/api/corporate-share-holdings-master?" + urllib.parse.urlencode({
                    "index": "equities", "symbol": symbol,
                })
                share_payload, share_evidence = session.json(
                    share_endpoint, SHAREHOLDING_PAGE, f"{symbol}-shareholding.json"
                )
                ownership.extend(normalize_ownership(
                    eligible_shareholding_rows(share_payload, as_of_date),
                    member,
                    int(node["taxonomy_node_id"]),
                    systems[SHAREHOLDING_SOURCE],
                    share_evidence,
                ))
                for option_type, flow_type in (("bulk_deals", "bulk_deal"), ("block_deals", "block_deal")):
                    deal_endpoint = NSE_ROOT + "/api/historicalOR/bulk-block-short-deals?" + urllib.parse.urlencode({
                        "optionType": option_type,
                        "symbol": symbol,
                        "from": from_date.strftime("%d-%m-%Y"),
                        "to": as_of_date.strftime("%d-%m-%Y"),
                    })
                    deal_payload, deal_evidence = session.json(
                        deal_endpoint, DEALS_PAGE, f"{symbol}-{option_type}.json"
                    )
                    flows.extend(normalize_deals(
                        deal_payload,
                        member,
                        int(node["taxonomy_node_id"]),
                        systems[DEALS_SOURCE],
                        flow_type,
                        deal_evidence,
                        as_of_date,
                    ))
            except (RuntimeError, subprocess.SubprocessError) as exc:
                errors.append({"symbol": symbol, "error": f"{type(exc).__name__}: {exc}"[:1000]})
    finally:
        session.close()
    result: dict[str, Any] = {
        "status": "completed" if not errors else ("partial" if ownership or flows else "failed"),
        **node,
        "as_of_date": as_of_date.isoformat(),
        "lookback_days": lookback_days,
        "constituent_count": len(members),
        "ownership_observation_count": len(ownership),
        "ownership_symbol_count": len({row["symbol_id"] for row in ownership}),
        "flow_observation_count": len(flows),
        "flow_symbol_count": len({row["symbol_id"] for row in flows}),
        "artifact_root": artifact_reference(artifact_dir),
        "errors": errors,
        "persisted": persist,
        "actor": actor,
        "seed_data_allowed": False,
        "broker_write_allowed": False,
        "capital_action_allowed": False,
    }
    if persist:
        result["database"] = persist_rows(ownership, flows)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect official NSE sector ownership and constituent deal flows.")
    parser.add_argument("--taxonomy-key", required=True)
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--lookback-days", type=int, default=365)
    parser.add_argument("--actor", default="Sector Flow And Ownership Analyst")
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()
    as_of_date = dt.date.fromisoformat(args.as_of_date)
    if args.lookback_days < 1 or args.lookback_days > 366:
        raise ValueError("lookback_days must be between 1 and 366")
    result = collect(args.taxonomy_key.strip(), as_of_date, args.lookback_days, args.persist, args.actor.strip())
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result["status"] in {"completed", "partial"} else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": f"{type(exc).__name__}: {exc}", "broker_write_allowed": False}, indent=2))
        raise SystemExit(1)
