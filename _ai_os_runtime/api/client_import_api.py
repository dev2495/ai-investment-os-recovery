from __future__ import annotations

import hashlib
import html
import io
import json
import os
import re
import secrets
import subprocess
import time
from datetime import datetime
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

import ai_os_api_server as core


CLIENT_IMPORT_ROOT = Path(
    os.environ.get("AI_OS_CLIENT_IMPORT_ROOT", "/Volumes/Devarsh SSD/AI OS Data/client_imports")
)


def _access(actor: str, client_code: str, account_code: str, required_scope: str) -> dict[str, Any]:
    rows = core.run_psql_json(
        f"""
        SELECT client.id AS client_id,account.id AS account_id,account.broker
        FROM portfolio.clients client
        JOIN portfolio.accounts account ON account.client_id=client.id
        JOIN client_data.client_access_grants access_grant ON access_grant.client_id=client.id
        WHERE lower(access_grant.actor)=lower({core.sql_literal(actor)})
          AND access_grant.active
          AND (access_grant.expires_at IS NULL OR access_grant.expires_at > now())
          AND {core.sql_literal(required_scope)}=ANY(access_grant.scopes)
          AND client.client_code={core.sql_literal(client_code)}
          AND account.account_code={core.sql_literal(account_code)}
          AND client.active AND account.active
        LIMIT 1
        """
    )
    if not rows:
        raise PermissionError("the operator does not have the required client-scoped access grant")
    return rows[0]


def _access_by_key(actor: str, import_key: str, required_scope: str) -> dict[str, Any]:
    rows = core.run_psql_json(
        f"""
        SELECT import.id,import.import_key,import.client_id,import.account_id,
               import.broker,import.status,import.identity_status,import.source_identity_hash
        FROM client_data.secure_client_imports import
        JOIN client_data.client_access_grants access_grant ON access_grant.client_id=import.client_id
        WHERE import.import_key={core.sql_literal(import_key)}
          AND lower(access_grant.actor)=lower({core.sql_literal(actor)})
          AND access_grant.active
          AND (access_grant.expires_at IS NULL OR access_grant.expires_at > now())
          AND {core.sql_literal(required_scope)}=ANY(access_grant.scopes)
        LIMIT 1
        """
    )
    if not rows:
        raise PermissionError("the operator does not have access to this client import")
    return rows[0]


def run_import(import_key: str, actor: str) -> dict[str, Any]:
    _access_by_key(actor, import_key, "portfolio_import")
    script_path = core.RUNTIME_ROOT / "scripts" / "ingest_secure_client_report.py"
    completed = subprocess.run(
        [core.governed_pdf_python(verify_import=True), str(script_path), "--import-key", import_key, "--actor", actor],
        cwd=str(core.RUNTIME_ROOT),
        text=True,
        capture_output=True,
        check=False,
        timeout=240,
    )
    if completed.returncode != 0:
        try:
            failure = json.loads(completed.stdout or "{}")
            message = str(failure.get("message") or failure.get("error") or "secure client import failed")
        except json.JSONDecodeError:
            message = "secure client import failed"
        raise RuntimeError(message)
    result = json.loads(completed.stdout or "{}")
    result["broker_write_allowed"] = False
    return result


def receive_upload(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    file_name = Path(handler.headers.get("X-AI-OS-File-Name", "").strip()).name
    client_code = handler.headers.get("X-AI-OS-Client-Code", "").strip()
    account_code = handler.headers.get("X-AI-OS-Account-Code", "").strip()
    report_kind = handler.headers.get("X-AI-OS-Report-Kind", "").strip().lower()
    actor = handler.headers.get("X-AI-OS-Actor", "Devarsh").strip() or "Devarsh"
    if not file_name or not client_code or not account_code:
        raise ValueError("file, client, and account are required")
    allowed_report_kinds = {
        "aditya_birla_money_capital_gains", "broker_transactions", "holdings_statement",
        "broker_ledger", "contract_note", "portfolio_snapshot", "tax_report", "browser_visible_capture", "other",
    }
    if report_kind not in allowed_report_kinds:
        raise ValueError("report_kind is not supported")
    suffix = Path(file_name).suffix.lower()
    if suffix not in {".csv", ".tsv", ".xls", ".xlsx", ".pdf", ".html"}:
        raise ValueError("client reports must be CSV, TSV, XLS, XLSX, PDF, or sanitized HTML")
    try:
        content_length = int(handler.headers.get("Content-Length", "0") or "0")
    except ValueError as exc:
        raise ValueError("Content-Length must be an integer") from exc
    if content_length <= 0 or content_length > 25 * 1024 * 1024:
        raise ValueError("client report must be between 1 byte and 25 MB")

    access = _access(actor, client_code, account_code, "portfolio_import")
    client_scope = hashlib.sha256(f"{access['client_id']}:{access['account_id']}".encode("utf-8")).hexdigest()[:20]
    CLIENT_IMPORT_ROOT.mkdir(parents=True, exist_ok=True)
    incoming_root = CLIENT_IMPORT_ROOT / "incoming"
    raw_base = CLIENT_IMPORT_ROOT / "raw"
    raw_root = raw_base / client_scope
    incoming_root.mkdir(parents=True, exist_ok=True)
    raw_root.mkdir(parents=True, exist_ok=True)
    os.chmod(CLIENT_IMPORT_ROOT, 0o700)
    os.chmod(raw_base, 0o700)
    os.chmod(incoming_root, 0o700)
    os.chmod(raw_root, 0o700)
    staging_path = incoming_root / f"{time.time_ns()}-{os.getpid()}{suffix}"
    digest = hashlib.sha256()
    remaining = content_length
    try:
        with staging_path.open("xb") as handle:
            os.chmod(staging_path, 0o600)
            while remaining:
                chunk = handler.rfile.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise ValueError("uploaded file ended before Content-Length bytes were received")
                handle.write(chunk)
                digest.update(chunk)
                remaining -= len(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        checksum = digest.hexdigest()
        final_path = raw_root / f"{checksum}{suffix}"
        if final_path.exists():
            if core.sha256_file(final_path) != checksum:
                raise RuntimeError("checksum-addressed client import path is inconsistent")
            staging_path.unlink(missing_ok=True)
        else:
            os.replace(staging_path, final_path)
            os.chmod(final_path, 0o600)
        import_key = "client-import-" + secrets.token_hex(9)
        mime_type = handler.headers.get("Content-Type", "application/octet-stream").split(";", 1)[0].strip()
        inserted = core.run_psql_json_statement(
            f"""
            WITH intake AS (
                INSERT INTO client_data.secure_client_imports (
                    import_key,client_id,account_id,broker,report_kind,original_file_name,
                    storage_path,sha256,file_bytes,mime_type,received_by
                ) VALUES (
                    {core.sql_literal(import_key)},{int(access['client_id'])},{int(access['account_id'])},
                    {core.sql_literal(access.get('broker') or 'Unknown')},{core.sql_literal(report_kind)},
                    {core.sql_literal(file_name)},{core.sql_literal(str(final_path))},{core.sql_literal(checksum)},
                    {content_length},{core.sql_literal(mime_type)},{core.sql_literal(actor)}
                )
                ON CONFLICT (client_id,account_id,sha256,report_kind) DO UPDATE SET updated_at=now()
                RETURNING import_key,left(sha256,12) checksum_prefix
            )
            SELECT coalesce(json_agg(row_to_json(intake)), '[]'::json)::text FROM intake
            """
        )
        if not inserted:
            raise RuntimeError("secure client intake did not return a durable record")
        durable_key = str(inserted[0]["import_key"])
        core.run_psql_text(
            f"""
            INSERT INTO client_data.client_import_audit (import_id,event_type,actor,event_status,metadata)
            SELECT id,'file_received',{core.sql_literal(actor)},'success',
                   jsonb_build_object('checksum_prefix',{core.sql_literal(checksum[:12])},
                                      'file_bytes',{content_length},'report_kind',{core.sql_literal(report_kind)},
                                      'immutable',true,'broker_write_allowed',false)
            FROM client_data.secure_client_imports WHERE import_key={core.sql_literal(durable_key)};
            """
        )
        result = run_import(durable_key, actor)
        core.audit_api_write(
            "ai_os_secure_client_report_upload", "secure_client_report_upload", actor,
            "client_data.secure_client_imports",
            {key: result.get(key) for key in (
                "import_key", "status", "identity_status", "checksum_prefix",
                "normalized_rows", "exception_count", "reconciliation_status", "broker_write_allowed",
            )},
            {"report_kind": report_kind, "file_bytes": content_length, "operator_confirmed": True},
        )
        return result
    finally:
        staging_path.unlink(missing_ok=True)


class _VisibleTableSanitizer(HTMLParser):
    _allowed = {"table", "caption", "thead", "tbody", "tfoot", "tr", "th", "td"}
    _blocked = {"script", "style", "form", "input", "button", "select", "option", "textarea", "iframe", "object", "embed", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.output: list[str] = []
        self.table_depth = 0
        self.blocked_depth = 0
        self.hidden_depth = 0
        self.table_count = 0
        self.cell_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attr_map = {str(key).lower(): str(value or "").lower() for key, value in attrs}
        hidden = "hidden" in attr_map or attr_map.get("aria-hidden") == "true" or any(
            token in attr_map.get("style", "") for token in ("display:none", "display: none", "visibility:hidden", "visibility: hidden")
        )
        if tag in self._blocked:
            self.blocked_depth += 1
            return
        if self.hidden_depth:
            self.hidden_depth += 1
            return
        if hidden:
            self.hidden_depth = 1
            return
        if self.blocked_depth or self.hidden_depth or tag not in self._allowed:
            return
        if tag == "table":
            self.table_depth += 1
            self.table_count += 1
        if self.table_depth:
            self.output.append(f"<{tag}>")
            if tag in {"th", "td"}:
                self.cell_count += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self._blocked and self.blocked_depth:
            self.blocked_depth -= 1
            return
        if self.hidden_depth:
            self.hidden_depth -= 1
            return
        if self.blocked_depth or tag not in self._allowed or not self.table_depth:
            return
        self.output.append(f"</{tag}>")
        if tag == "table":
            self.table_depth = max(0, self.table_depth - 1)

    def handle_data(self, data: str) -> None:
        if self.table_depth and not self.blocked_depth and not self.hidden_depth:
            compact = re.sub(r"\s+", " ", data).strip()
            if compact:
                self.output.append(html.escape(compact))


def sanitize_visible_browser_content(content: str, content_type: str) -> tuple[bytes, dict[str, int]]:
    if not content or len(content.encode("utf-8")) > 2 * 1024 * 1024:
        raise ValueError("selected visible content must be between 1 byte and 2 MB")
    if re.search(r"authorization\s*:\s*bearer|cookie\s*:|access[_ -]?token|refresh[_ -]?token|<input[^>]+type=[\"']?password", content, re.IGNORECASE):
        raise ValueError("the capture appears to contain credentials or session material; copy only the visible portfolio table")
    if content_type == "text/html":
        sanitizer = _VisibleTableSanitizer()
        sanitizer.feed(content)
        sanitizer.close()
        if sanitizer.table_count == 0 or sanitizer.cell_count < 2:
            raise ValueError("no visible table cells were found in the copied content")
        clean = "<!doctype html><meta charset=\"utf-8\"><body>" + "".join(sanitizer.output) + "</body>"
        return clean.encode("utf-8"), {"tables": sanitizer.table_count, "cells": sanitizer.cell_count}
    if content_type != "text/plain":
        raise ValueError("content_type must be text/html or text/plain")
    rows = []
    for line in content.splitlines():
        cells = [cell.strip() for cell in line.split("\t")]
        if len(cells) > 1 and any(cells):
            rows.append(cells[:40])
    if not rows:
        raise ValueError("plain-text capture must contain tab-separated visible table rows")
    rendered = ["<!doctype html><meta charset=\"utf-8\"><body><table>"]
    for row in rows[:5000]:
        rendered.append("<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>")
    rendered.append("</table></body>")
    return "".join(rendered).encode("utf-8"), {"tables": 1, "cells": sum(len(row) for row in rows[:5000])}


class _CaptureUpload:
    def __init__(self, content: bytes, headers: dict[str, str]) -> None:
        self.rfile = io.BytesIO(content)
        self.headers = headers


def receive_browser_capture(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("operator_confirmed") is not True:
        raise ValueError("operator_confirmed must be true")
    client_code = str(payload.get("client_code") or "").strip()
    account_code = str(payload.get("account_code") or "").strip()
    source_key = str(payload.get("source_key") or "").strip()
    page_title = str(payload.get("page_title") or "").strip()[:160]
    if re.search(r"https?://|[?&](?:token|session|auth)=", page_title, re.IGNORECASE):
        raise ValueError("page_title must be a short label, not a URL or session reference")
    captured_at_raw = str(payload.get("captured_at") or "").strip()
    actor = str(payload.get("actor") or "Devarsh").strip() or "Devarsh"
    content_type = str(payload.get("content_type") or "text/plain").split(";", 1)[0].strip().lower()
    content = str(payload.get("content") or "")
    allowed_sources = {
        "aditya_birla_money_authenticated_portfolio", "zerodha_authenticated_portfolio",
        "authorized_broker_portfolio", "authorized_portfolio_tracker",
    }
    if source_key not in allowed_sources:
        raise ValueError("source_key is not an approved authenticated portfolio source")
    try:
        captured_at = datetime.fromisoformat(captured_at_raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("captured_at must be an ISO-8601 timestamp") from exc
    if captured_at.tzinfo is None:
        raise ValueError("captured_at must include a timezone")
    access = _access(actor, client_code, account_code, "portfolio_import")
    sanitized, mapping = sanitize_visible_browser_content(content, content_type)
    safe_name = "visible-browser-capture-" + captured_at.strftime("%Y%m%dT%H%M%S") + ".html"
    upload = _CaptureUpload(sanitized, {
        "X-AI-OS-File-Name": safe_name,
        "X-AI-OS-Client-Code": client_code,
        "X-AI-OS-Account-Code": account_code,
        "X-AI-OS-Report-Kind": "browser_visible_capture",
        "X-AI-OS-Actor": actor,
        "Content-Length": str(len(sanitized)),
        "Content-Type": "text/html",
    })
    result = receive_upload(upload)  # type: ignore[arg-type]
    capture_key = "browser-capture-" + secrets.token_hex(9)
    core.run_psql_text(f"""
        UPDATE client_data.secure_client_imports
        SET identity_status='resolved',
            status=CASE WHEN status='needs_identity_review' THEN 'parsed' ELSE status END,
            source_as_of={core.sql_literal(captured_at)}::timestamptz,
            updated_at=now()
        WHERE import_key={core.sql_literal(result['import_key'])};
        INSERT INTO client_data.client_browser_capture_sessions (
            capture_key,import_id,client_id,account_id,source_key,page_title,captured_at,
            consent_actor,content_type,status,field_mapping,preview_summary
        )
        SELECT {core.sql_literal(capture_key)},id,{int(access['client_id'])},{int(access['account_id'])},
               {core.sql_literal(source_key)},{core.sql_literal(page_title)},{core.sql_literal(captured_at)}::timestamptz,
               {core.sql_literal(actor)},{core.sql_literal(content_type)},
               CASE WHEN status IN ('failed','stored_unparsed','blocked_identity_mismatch') THEN 'needs_review' ELSE 'parsed' END,
               {core.sql_literal(json.dumps(mapping))}::jsonb,
               jsonb_build_object('normalized_rows',{int(result.get('normalized_rows') or 0)},
                                  'exception_count',{int(result.get('exception_count') or 0)},
                                  'identity_status',{core.sql_literal(result.get('identity_status'))},
                                  'reconciliation_status',{core.sql_literal(result.get('reconciliation_status'))},
                                  'broker_write_allowed',false)
        FROM client_data.secure_client_imports WHERE import_key={core.sql_literal(result['import_key'])};
        INSERT INTO client_data.client_import_audit (import_id,event_type,actor,event_status,metadata)
        SELECT id,'browser_visible_capture',{core.sql_literal(actor)},'success',
               jsonb_build_object('capture_key',{core.sql_literal(capture_key)},'source_key',{core.sql_literal(source_key)},
                                  'capture_scope','user_selected_visible_content','sanitized',true,
                                  'credentials_captured',false,'browser_write_allowed',false)
        FROM client_data.secure_client_imports WHERE import_key={core.sql_literal(result['import_key'])};
    """)
    response = {**result, "capture_key": capture_key, "captured_at": captured_at.isoformat(),
                "capture_scope": "user_selected_visible_content", "sanitized": True,
                "credentials_captured": False, "browser_write_allowed": False}
    core.audit_api_write(
        "ai_os_browser_visible_capture", "browser_visible_capture", actor,
        "client_data.client_browser_capture_sessions",
        {key: response.get(key) for key in ("capture_key", "import_key", "status", "identity_status", "normalized_rows", "exception_count", "browser_write_allowed")},
        {"source_key": source_key, "operator_confirmed": True, "sanitized": True, "credentials_captured": False},
    )
    return response


def resolve_identity(payload: dict[str, Any]) -> dict[str, Any]:
    import_key = str(payload.get("import_key") or "").strip()
    decision = str(payload.get("decision") or "").strip().lower()
    rationale = str(payload.get("rationale") or "").strip()
    actor = str(payload.get("actor") or "Devarsh").strip() or "Devarsh"
    if payload.get("operator_confirmed") is not True:
        raise ValueError("operator_confirmed must be true")
    if decision not in {"confirm", "reject"}:
        raise ValueError("decision must be confirm or reject")
    if len(rationale) < 10:
        raise ValueError("a substantive identity-review rationale is required")
    source = _access_by_key(actor, import_key, "portfolio_identity_review")
    if decision == "confirm" and not source.get("source_identity_hash"):
        raise ValueError("the report contains no source identity to confirm")
    if decision == "confirm":
        core.run_psql_text(
            f"""
            INSERT INTO client_data.client_source_identities (
                client_id,account_id,broker,source_identity_hash,status,verified_by,verified_at,evidence
            ) VALUES (
                {int(source['client_id'])},{int(source['account_id'])},{core.sql_literal(source['broker'])},
                {core.sql_literal(source['source_identity_hash'])},'verified',{core.sql_literal(actor)},now(),
                jsonb_build_array(jsonb_build_object('import_key',{core.sql_literal(import_key)},'rationale',{core.sql_literal(rationale)}))
            )
            ON CONFLICT (broker,source_identity_hash) DO UPDATE SET
                client_id=EXCLUDED.client_id,account_id=EXCLUDED.account_id,status='verified',
                verified_by=EXCLUDED.verified_by,verified_at=now(),evidence=EXCLUDED.evidence;
            UPDATE client_data.secure_client_imports
            SET identity_status='resolved',
                status=CASE WHEN status IN ('needs_identity_review','blocked_identity_mismatch') THEN 'parsed' ELSE status END,
                updated_at=now()
            WHERE id={int(source['id'])};
            INSERT INTO client_data.client_import_audit (import_id,event_type,actor,event_status,metadata)
            VALUES ({int(source['id'])},'identity_review',{core.sql_literal(actor)},'confirmed',
                    jsonb_build_object('rationale',{core.sql_literal(rationale)},'broker_write_allowed',false));
            """
        )
        identity_status = "resolved"
    else:
        core.run_psql_text(
            f"""
            UPDATE client_data.secure_client_imports SET identity_status='mismatch',status='rejected',updated_at=now()
            WHERE id={int(source['id'])};
            INSERT INTO client_data.client_import_audit (import_id,event_type,actor,event_status,metadata)
            VALUES ({int(source['id'])},'identity_review',{core.sql_literal(actor)},'rejected',
                    jsonb_build_object('rationale',{core.sql_literal(rationale)},'broker_write_allowed',false));
            """
        )
        identity_status = "rejected"
    result = {"ok": True, "import_key": import_key, "identity_status": identity_status, "broker_write_allowed": False}
    if decision == "confirm":
        processing = run_import(import_key, actor)
        result.update({key: processing.get(key) for key in (
            "status", "normalized_rows", "exception_count", "reconciliation_status",
            "current_holdings_status", "cash_status",
        )})
    core.audit_api_write(
        "ai_os_resolve_client_import_identity", "resolve_client_import_identity", actor,
        "client_data.secure_client_imports", result,
        {"import_key": import_key, "decision": decision, "operator_confirmed": True},
    )
    return result


def evidence(query: dict[str, list[str]]) -> dict[str, Any]:
    import_key = str(query.get("import_key", [""])[0]).strip()
    actor = str(query.get("actor", ["Devarsh"])[0]).strip() or "Devarsh"
    limit = max(1, min(int(query.get("limit", ["200"])[0]), 500))
    offset = max(0, int(query.get("offset", ["0"])[0]))
    source = _access_by_key(actor, import_key, "portfolio_read")
    rows = core.run_psql_json(
        f"""
        SELECT row_number,left(row_hash,12) evidence_hash,layer,symbol,instrument_name,
               transaction_type,purchase_date,sale_date,transaction_date,quantity,
               buy_price,buy_value,sell_price,sell_value,holding_period_days,
               realized_gain,speculative_gain,taxable_gain,short_term_gain,long_term_gain,
               total_charges,average_price,market_price,market_value,
               cash_balance,available_funds,collateral_value,tax_period
        FROM client_data.client_import_rows WHERE import_id={int(source['id'])}
        ORDER BY row_number,layer LIMIT {limit} OFFSET {offset}
        """
    )
    exceptions = core.run_psql_json(
        f"""
        SELECT row_number,exception_code,severity,field_name,message,status
        FROM client_data.client_import_exceptions WHERE import_id={int(source['id'])}
        ORDER BY CASE severity WHEN 'blocking' THEN 1 WHEN 'error' THEN 2 WHEN 'warning' THEN 3 ELSE 4 END,row_number
        LIMIT {limit}
        """
    )
    totals = core.run_psql_json(
        f"SELECT count(*) AS total_rows FROM client_data.client_import_rows WHERE import_id={int(source['id'])}"
    )
    total_rows = int((totals[0] if totals else {}).get("total_rows") or 0)
    return {
        "import_key": import_key, "status": source.get("status"),
        "identity_status": source.get("identity_status"), "rows": rows,
        "exceptions": exceptions, "limit": limit, "offset": offset,
        "total_rows": total_rows, "has_more": offset + len(rows) < total_rows,
        "raw_payload_included": False, "broker_write_allowed": False,
    }


def portfolio_snapshot_rows() -> dict[str, list[dict[str, Any]]]:
    imports = core.run_psql_json(
        """
        SELECT control.*
        FROM client_data.v_secure_client_import_control control
        JOIN portfolio.clients client ON client.client_code=control.client_code
        JOIN client_data.client_access_grants access_grant ON access_grant.client_id=client.id
        WHERE lower(access_grant.actor)=lower('Devarsh') AND access_grant.active
          AND (access_grant.expires_at IS NULL OR access_grant.expires_at > now())
          AND 'portfolio_read'=ANY(access_grant.scopes)
        ORDER BY control.received_at DESC LIMIT 100
        """
    )
    exceptions = core.run_psql_json(
        """
        SELECT exception.*
        FROM client_data.v_client_import_exception_control exception
        JOIN portfolio.clients client ON client.client_code=exception.client_code
        JOIN client_data.client_access_grants access_grant ON access_grant.client_id=client.id
        WHERE lower(access_grant.actor)=lower('Devarsh') AND access_grant.active
          AND (access_grant.expires_at IS NULL OR access_grant.expires_at > now())
          AND 'portfolio_read'=ANY(access_grant.scopes)
          AND exception.status='open'
        ORDER BY exception.created_at DESC LIMIT 200
        """
    )
    derived_holdings = core.run_psql_json(
        """
        SELECT holding.*
        FROM client_data.v_client_import_derived_holdings holding
        JOIN portfolio.clients client ON client.client_code=holding.client_code
        JOIN client_data.client_access_grants access_grant ON access_grant.client_id=client.id
        WHERE lower(access_grant.actor)=lower('Devarsh') AND access_grant.active
          AND (access_grant.expires_at IS NULL OR access_grant.expires_at > now())
          AND 'portfolio_read'=ANY(access_grant.scopes)
        ORDER BY holding.display_name,holding.account_name,holding.symbol
        LIMIT 1000
        """
    )
    reconciliation = core.run_psql_json(
        """
        SELECT control.*
        FROM client_data.v_client_import_reconciliation_control control
        JOIN portfolio.clients client ON client.client_code=control.client_code
        JOIN client_data.client_access_grants access_grant ON access_grant.client_id=client.id
        WHERE lower(access_grant.actor)=lower('Devarsh') AND access_grant.active
          AND (access_grant.expires_at IS NULL OR access_grant.expires_at > now())
          AND 'portfolio_read'=ANY(access_grant.scopes)
        ORDER BY control.reconciled_at DESC NULLS LAST
        LIMIT 200
        """
    )
    holdings_comparison = core.run_psql_json(
        """
        WITH fifo_imported AS (
            SELECT import.client_id,upper(trim(lot.symbol)) symbol,
                   sum(lot.remaining_quantity) derived_quantity,
                   min(import.source_period_start) source_period_start,
                   max(import.source_period_end) source_period_end,
                   string_agg(DISTINCT account.account_name, ', ' ORDER BY account.account_name) imported_accounts,
                   'source_period_fifo'::text evidence_basis
            FROM client_data.client_import_derived_lots lot
            JOIN client_data.secure_client_imports import ON import.id=lot.import_id
            JOIN portfolio.accounts account ON account.id=import.account_id
            WHERE import.identity_status='resolved' AND import.report_kind='broker_transactions'
            GROUP BY import.client_id,upper(trim(lot.symbol))
        ), latest_capture_import AS (
            SELECT DISTINCT ON (import.client_id,import.account_id)
                   import.id,import.client_id,import.account_id,import.source_as_of
            FROM client_data.secure_client_imports import
            WHERE import.identity_status='resolved' AND import.report_kind='browser_visible_capture'
              AND EXISTS (SELECT 1 FROM client_data.client_import_rows row WHERE row.import_id=import.id AND row.layer='holding')
            ORDER BY import.client_id,import.account_id,import.source_as_of DESC NULLS LAST,import.received_at DESC
        ), captured_current AS (
            SELECT capture.client_id,upper(trim(coalesce(row.symbol,row.instrument_name))) symbol,
                   sum(row.quantity) derived_quantity,
                   min(capture.source_as_of::date) source_period_start,
                   max(capture.source_as_of::date) source_period_end,
                   string_agg(DISTINCT account.account_name, ', ' ORDER BY account.account_name) imported_accounts,
                   'authorized_visible_holdings_capture'::text evidence_basis
            FROM latest_capture_import capture
            JOIN client_data.client_import_rows row ON row.import_id=capture.id AND row.layer='holding'
            JOIN portfolio.accounts account ON account.id=capture.account_id
            WHERE coalesce(row.symbol,row.instrument_name) IS NOT NULL
            GROUP BY capture.client_id,upper(trim(coalesce(row.symbol,row.instrument_name)))
        ), imported AS (
            SELECT * FROM captured_current
            UNION ALL
            SELECT fifo.* FROM fifo_imported fifo
            WHERE NOT EXISTS (
                SELECT 1 FROM captured_current captured
                WHERE captured.client_id=fifo.client_id AND captured.symbol=fifo.symbol
            )
        ), canonical AS (
            SELECT account.client_id,upper(trim(position.symbol)) symbol,
                   sum(position.quantity) canonical_quantity,max(position.as_of) canonical_as_of,
                   string_agg(DISTINCT account.account_name, ', ' ORDER BY account.account_name) canonical_accounts
            FROM portfolio.v_latest_positions position
            JOIN portfolio.accounts account ON account.id=position.account_id
            WHERE account.client_id IN (SELECT DISTINCT client_id FROM imported)
            GROUP BY account.client_id,upper(trim(position.symbol))
        ), comparison AS (
            SELECT coalesce(imported.client_id,canonical.client_id) client_id,
                   coalesce(imported.symbol,canonical.symbol) symbol,
                   imported.derived_quantity,canonical.canonical_quantity,
                   imported.source_period_start,imported.source_period_end,canonical.canonical_as_of,
                   imported.imported_accounts,canonical.canonical_accounts,imported.evidence_basis
            FROM imported FULL OUTER JOIN canonical
              ON canonical.client_id=imported.client_id AND canonical.symbol=imported.symbol
        )
        SELECT client.client_code,client.display_name,comparison.imported_accounts,comparison.canonical_accounts,
               comparison.symbol,comparison.derived_quantity,comparison.canonical_quantity,
               comparison.derived_quantity-comparison.canonical_quantity AS quantity_difference,
               comparison.source_period_start,comparison.source_period_end,comparison.canonical_as_of,
               comparison.evidence_basis,
               CASE WHEN comparison.derived_quantity IS NULL THEN 'current_snapshot_only'
                    WHEN comparison.canonical_quantity IS NULL THEN 'import_only'
                    WHEN abs(comparison.derived_quantity-comparison.canonical_quantity) <= 0.000001 THEN 'matched'
                    ELSE 'quantity_break' END AS comparison_status,
               'Same-client imported evidence versus latest warehouse position. A current browser capture supersedes period-only FIFO for the same security; identifiers are not guessed and neither source is promoted or altered.'::text AS methodology
        FROM comparison
        JOIN portfolio.clients client ON client.id=comparison.client_id
        JOIN client_data.client_access_grants access_grant ON access_grant.client_id=client.id
        WHERE lower(access_grant.actor)=lower('Devarsh') AND access_grant.active
          AND (access_grant.expires_at IS NULL OR access_grant.expires_at > now())
          AND 'portfolio_read'=ANY(access_grant.scopes)
        ORDER BY client.display_name,comparison.symbol
        LIMIT 1000
        """
    )
    browser_captures = core.run_psql_json(
        """
        SELECT capture.*
        FROM client_data.v_client_browser_capture_control capture
        JOIN portfolio.clients client ON client.client_code=capture.client_code
        JOIN client_data.client_access_grants access_grant ON access_grant.client_id=client.id
        WHERE lower(access_grant.actor)=lower('Devarsh') AND access_grant.active
          AND (access_grant.expires_at IS NULL OR access_grant.expires_at > now())
          AND 'portfolio_read'=ANY(access_grant.scopes)
        ORDER BY capture.captured_at DESC LIMIT 100
        """
    )
    workspace_status = core.run_psql_json(
        """
        WITH accessible AS (
            SELECT DISTINCT client.id client_id,client.client_code,client.display_name
            FROM portfolio.clients client
            JOIN client_data.client_access_grants access_grant ON access_grant.client_id=client.id
            WHERE lower(access_grant.actor)=lower('Devarsh') AND access_grant.active
              AND (access_grant.expires_at IS NULL OR access_grant.expires_at > now())
              AND 'portfolio_read'=ANY(access_grant.scopes)
              AND client.active
        ), import_summary AS (
            SELECT import.client_id,
                   count(*) FILTER (WHERE import.report_kind='broker_transactions') transaction_report_count,
                   count(*) FILTER (WHERE import.report_kind IN ('aditya_birla_money_capital_gains','tax_report')) capital_gain_report_count,
                   coalesce(sum(import.transaction_count) FILTER (WHERE import.report_kind='broker_transactions'),0) historical_transaction_rows,
                   coalesce(sum(import.lot_count) FILTER (WHERE import.report_kind IN ('aditya_birla_money_capital_gains','tax_report')),0) capital_gain_lot_rows,
                   min(import.source_period_start) historical_period_start,
                   max(import.source_period_end) historical_period_end,
                   max(import.received_at) latest_import_received_at,
                   bool_and(import.immutable) immutable_evidence
            FROM client_data.secure_client_imports import
            WHERE import.identity_status='resolved' AND import.status <> 'rejected'
            GROUP BY import.client_id
        ), open_lots AS (
            SELECT import.client_id,count(*) open_lot_rows,
                   count(*) FILTER (WHERE lot.quality_status <> 'complete_for_covered_period') incomplete_lot_rows
            FROM client_data.client_import_derived_lots lot
            JOIN client_data.secure_client_imports import ON import.id=lot.import_id
            WHERE import.identity_status='resolved'
            GROUP BY import.client_id
        ), exception_summary AS (
            SELECT import.client_id,
                   count(*) FILTER (WHERE exception.status='open') open_exception_count,
                   count(*) FILTER (WHERE exception.status='open' AND exception.severity='blocking') blocking_exception_count,
                   count(*) FILTER (WHERE exception.status='open' AND exception.exception_code='opening_position_missing') opening_history_exception_count,
                   count(*) FILTER (WHERE exception.status='open' AND exception.exception_code='missing_corporate_action') corporate_action_exception_count
            FROM client_data.client_import_exceptions exception
            JOIN client_data.secure_client_imports import ON import.id=exception.import_id
            GROUP BY import.client_id
        ), latest_capture AS (
            SELECT DISTINCT ON (capture.client_id,capture.account_id)
                   capture.client_id,capture.account_id,capture.import_id,capture.captured_at,capture.status
            FROM client_data.client_browser_capture_sessions capture
            WHERE capture.sanitized AND NOT capture.credentials_captured AND NOT capture.browser_write_allowed
            ORDER BY capture.client_id,capture.account_id,capture.captured_at DESC
        ), current_capture AS (
            SELECT capture.client_id,count(*) capture_count,max(capture.captured_at) latest_capture_at,
                   count(*) FILTER (WHERE row.layer='holding') current_holding_rows,
                   count(*) FILTER (WHERE row.layer IN ('fund_balance','cash')) current_cash_rows,
                   count(*) FILTER (WHERE row.layer='holding' AND (row.market_price IS NOT NULL OR row.market_value IS NOT NULL)) priced_holding_rows
            FROM latest_capture capture
            LEFT JOIN client_data.client_import_rows row ON row.import_id=capture.import_id
            GROUP BY capture.client_id
        )
        SELECT accessible.client_code,accessible.display_name,
               coalesce(import_summary.transaction_report_count,0) transaction_report_count,
               coalesce(import_summary.capital_gain_report_count,0) capital_gain_report_count,
               coalesce(import_summary.historical_transaction_rows,0) historical_transaction_rows,
               coalesce(import_summary.capital_gain_lot_rows,0) capital_gain_lot_rows,
               import_summary.historical_period_start,import_summary.historical_period_end,
               import_summary.latest_import_received_at,coalesce(import_summary.immutable_evidence,false) immutable_evidence,
               coalesce(open_lots.open_lot_rows,0) open_lot_rows,
               coalesce(open_lots.incomplete_lot_rows,0) incomplete_lot_rows,
               coalesce(exception_summary.open_exception_count,0) open_exception_count,
               coalesce(exception_summary.blocking_exception_count,0) blocking_exception_count,
               coalesce(exception_summary.opening_history_exception_count,0) opening_history_exception_count,
               coalesce(exception_summary.corporate_action_exception_count,0) corporate_action_exception_count,
               coalesce(current_capture.capture_count,0) current_capture_count,
               current_capture.latest_capture_at,
               coalesce(current_capture.current_holding_rows,0) current_holding_rows,
               coalesce(current_capture.current_cash_rows,0) current_cash_rows,
               coalesce(current_capture.priced_holding_rows,0) priced_holding_rows,
               CASE WHEN coalesce(import_summary.historical_transaction_rows,0)>0
                          AND coalesce(import_summary.capital_gain_lot_rows,0)>0 THEN 'source_backed'
                    WHEN coalesce(import_summary.historical_transaction_rows,0)>0
                          OR coalesce(import_summary.capital_gain_lot_rows,0)>0 THEN 'partial'
                    ELSE 'missing' END historical_status,
               CASE WHEN coalesce(current_capture.current_holding_rows,0)>0 THEN 'captured_needs_reconciliation'
                    ELSE 'pending_current_capture' END current_holdings_status,
               CASE WHEN coalesce(current_capture.current_cash_rows,0)>0 THEN 'captured_needs_reconciliation'
                    ELSE 'pending_current_capture' END current_cash_status,
               CASE WHEN coalesce(current_capture.current_holding_rows,0)=0 OR coalesce(current_capture.current_cash_rows,0)=0
                         THEN 'blocked_missing_current_holdings_or_cash'
                    WHEN coalesce(exception_summary.opening_history_exception_count,0)>0
                         OR coalesce(exception_summary.corporate_action_exception_count,0)>0
                         THEN 'blocked_history_exceptions'
                    ELSE 'eligible_for_review_not_final' END performance_status,
               CASE WHEN coalesce(current_capture.current_holding_rows,0)=0 THEN 'blocked_missing_current_holdings'
                    WHEN coalesce(current_capture.priced_holding_rows,0)<coalesce(current_capture.current_holding_rows,0)
                         THEN 'blocked_missing_current_prices'
                    ELSE 'eligible_for_review_not_final' END risk_status,
               'Historical exports are primary evidence. Current browser or broker capture is complementary and never overwrites imports.'::text methodology,
               false broker_write_allowed,false client_record_mutation_allowed
        FROM accessible
        LEFT JOIN import_summary ON import_summary.client_id=accessible.client_id
        LEFT JOIN open_lots ON open_lots.client_id=accessible.client_id
        LEFT JOIN exception_summary ON exception_summary.client_id=accessible.client_id
        LEFT JOIN current_capture ON current_capture.client_id=accessible.client_id
        ORDER BY accessible.display_name
        """
    )
    realized_summary = core.run_psql_json(
        """
        SELECT client.client_code,client.display_name,import.import_key,import.report_kind,
               min(row.purchase_date) earliest_purchase_date,max(row.sale_date) latest_sale_date,
               count(*) FILTER (WHERE row.layer='tax_lot') realized_lot_rows,
               sum(coalesce(row.realized_gain,row.taxable_gain)) FILTER (WHERE row.layer='tax_lot') source_realized_gain,
               sum(row.short_term_gain) FILTER (WHERE row.layer='tax_lot') source_short_term_gain,
               sum(row.long_term_gain) FILTER (WHERE row.layer='tax_lot') source_long_term_gain,
               import.source_period_start,import.source_period_end,left(import.sha256,12) checksum_prefix,
               'Source-reported lot values; not recalculated tax advice'::text methodology
        FROM client_data.secure_client_imports import
        JOIN client_data.client_import_rows row ON row.import_id=import.id
        JOIN portfolio.clients client ON client.id=import.client_id
        JOIN client_data.client_access_grants access_grant ON access_grant.client_id=client.id
        WHERE lower(access_grant.actor)=lower('Devarsh') AND access_grant.active
          AND (access_grant.expires_at IS NULL OR access_grant.expires_at > now())
          AND 'portfolio_read'=ANY(access_grant.scopes)
          AND import.identity_status='resolved'
          AND import.report_kind IN ('aditya_birla_money_capital_gains','tax_report')
        GROUP BY client.client_code,client.display_name,import.import_key,import.report_kind,
                 import.source_period_start,import.source_period_end,import.sha256
        ORDER BY import.source_period_end DESC NULLS LAST
        """
    )
    return {
        "client_browser_captures": browser_captures,
        "client_imports": imports,
        "client_import_exceptions": exceptions,
        "client_import_derived_holdings": derived_holdings,
        "client_import_reconciliation": reconciliation,
        "client_import_holdings_comparison": holdings_comparison,
        "client_import_workspace_status": workspace_status,
        "client_import_realized_summary": realized_summary,
    }
