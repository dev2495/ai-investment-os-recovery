#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.parse

import ai_os_api_server as core
import client_import_api


_build_portfolio_snapshot = core.build_portfolio_office_snapshot
_handler_get = core.AiOsApiHandler.do_GET
_handler_post = core.AiOsApiHandler.do_POST


def build_portfolio_office_snapshot() -> dict:
    snapshot = _build_portfolio_snapshot()
    snapshot.update(client_import_api.portfolio_snapshot_rows())
    return snapshot


def send_json(self: core.AiOsApiHandler, payload: object, status: int = 200) -> None:
    data = json.dumps(payload, indent=2, sort_keys=True, default=str).encode("utf-8")
    self.send_response(status)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Content-Length", str(len(data)))
    self.send_header("Cache-Control", "no-store")
    self.send_header("Access-Control-Allow-Origin", self._cors_origin())
    self.send_header("Vary", "Origin")
    self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    self.send_header(
        "Access-Control-Allow-Headers",
        "Content-Type, Authorization, X-AI-OS-Operator-Token, X-AI-OS-File-Name, "
        "X-AI-OS-Client-Code, X-AI-OS-Account-Code, X-AI-OS-Report-Kind, X-AI-OS-Actor",
    )
    self.end_headers()
    self.wfile.write(data)


def do_get(self: core.AiOsApiHandler) -> None:
    request_path = urllib.parse.urlparse(self.path).path
    if request_path != "/api/client-imports/evidence":
        _handler_get(self)
        return
    try:
        self._authorize_request(write=False)
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        self._send_json(client_import_api.evidence(query))
    except PermissionError as exc:
        self._send_json({"error": "forbidden", "message": str(exc)}, 403)
    except ValueError as exc:
        self._send_json({"error": "bad_request", "message": str(exc)}, 400)
    except Exception as exc:  # noqa: BLE001
        self._send_json({"error": type(exc).__name__, "message": str(exc)}, 500)


def do_post(self: core.AiOsApiHandler) -> None:
    request_path = urllib.parse.urlparse(self.path).path
    if request_path not in {
        "/api/client-imports/upload",
        "/api/client-imports/reprocess",
        "/api/client-imports/identity/resolve",
        "/api/client-browser-captures/submit",
    }:
        _handler_post(self)
        return
    try:
        self._authorize_request(write=True)
        if request_path == "/api/client-imports/upload":
            self._send_json(client_import_api.receive_upload(self), 201)
            return
        if request_path == "/api/client-browser-captures/submit":
            try:
                content_length = int(self.headers.get("Content-Length", "0") or "0")
            except ValueError as exc:
                raise ValueError("Content-Length must be an integer") from exc
            if content_length <= 0 or content_length > 3 * 1024 * 1024:
                raise ValueError("browser capture request must be between 1 byte and 3 MB")
        payload = self._read_body()
        if request_path == "/api/client-browser-captures/submit":
            self._send_json(client_import_api.receive_browser_capture(payload), 201)
            return
        if request_path == "/api/client-imports/reprocess":
            import_key = str(payload.get("import_key") or "").strip()
            actor = str(payload.get("actor") or "Devarsh").strip() or "Devarsh"
            if payload.get("operator_confirmed") is not True:
                raise ValueError("operator_confirmed must be true")
            self._send_json(client_import_api.run_import(import_key, actor), 201)
            return
        self._send_json(client_import_api.resolve_identity(payload), 200)
    except PermissionError as exc:
        self._send_json({"error": "forbidden", "message": str(exc)}, 403)
    except ValueError as exc:
        self._send_json({"error": "bad_request", "message": str(exc)}, 400)
    except Exception as exc:  # noqa: BLE001
        self._send_json({"error": type(exc).__name__, "message": str(exc)}, 500)


core.build_portfolio_office_snapshot = build_portfolio_office_snapshot
core.AiOsApiHandler._send_json = send_json
core.AiOsApiHandler.do_GET = do_get
core.AiOsApiHandler.do_POST = do_post


if __name__ == "__main__":
    raise SystemExit(core.main())
