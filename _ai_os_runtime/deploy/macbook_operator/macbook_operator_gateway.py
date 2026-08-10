#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


HOST = os.environ.get("AI_OS_OPERATOR_GATEWAY_HOST", "127.0.0.1")
PORT = int(os.environ.get("AI_OS_OPERATOR_GATEWAY_PORT", "8765"))
UPSTREAM = os.environ.get(
    "AI_OS_UPSTREAM_API",
    "https://devarshs-imac.tail8dd383.ts.net:8443",
).rstrip("/")
REQUEST_TIMEOUT = float(os.environ.get("AI_OS_OPERATOR_GATEWAY_TIMEOUT", "300"))
LOCAL_MODEL_ENDPOINTS = {
    "qwen_gguf": "http://100.75.156.32:11435/v1/models",
    "qwen_mlx": "http://100.75.156.32:11436/v1/models",
    "ollama": "http://127.0.0.1:11434/api/version",
}
HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}
SENSITIVE_QUERY_KEYS = {"request_token", "access_token", "refresh_token", "api_key", "token"}


def sanitized_path(path: str) -> str:
    parsed = urllib.parse.urlsplit(path)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    safe_query = [
        (key, "[redacted]" if key.lower() in SENSITIVE_QUERY_KEYS else value)
        for key, value in query
    ]
    return urllib.parse.urlunsplit(("", "", parsed.path, urllib.parse.urlencode(safe_query), ""))


def probe_json(url: str, timeout: float = 3.0) -> dict:
    try:
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return {"ok": 200 <= response.status < 300, "status": response.status, "payload": payload}
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


class OperatorGatewayHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    upstream_base = UPSTREAM

    def log_message(self, format: str, *args: object) -> None:
        safe_args = tuple(sanitized_path(arg) if isinstance(arg, str) and arg.startswith("/") else arg for arg in args)
        super().log_message(format, *safe_args)

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _node_health(self) -> None:
        upstream = probe_json(f"{self.upstream_base}/api/liveness", 5.0)
        models = {name: probe_json(url) for name, url in LOCAL_MODEL_ENDPOINTS.items()}
        self._send_json(
            {
                "ok": bool(upstream.get("ok")) and any(result.get("ok") for result in models.values()),
                "node": "macbook_operator",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "upstream": {"base_url": self.upstream_base, **upstream},
                "local_models": models,
                "authority": {
                    "warehouse": "imac",
                    "operator_ui": "macbook_or_imac",
                    "local_model_compute": "macbook",
                    "broker_writes": False,
                },
            },
            200 if upstream.get("ok") else 503,
        )

    def _proxy(self) -> None:
        if self.path == "/api/node/health":
            self._node_health()
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in HOP_BY_HOP and key.lower() not in {"host", "content-length"}
        }
        headers["Host"] = urllib.parse.urlsplit(self.upstream_base).netloc
        request = urllib.request.Request(
            f"{self.upstream_base}{self.path}",
            data=body,
            headers=headers,
            method=self.command,
        )
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT, context=ssl.create_default_context()) as response:
                response_body = response.read()
                self.send_response(response.status)
                for key, value in response.headers.items():
                    if key.lower() not in HOP_BY_HOP and key.lower() != "content-length":
                        self.send_header(key, value)
                self.send_header("Content-Length", str(len(response_body)))
                self.end_headers()
                self.wfile.write(response_body)
        except urllib.error.HTTPError as exc:
            response_body = exc.read()
            self.send_response(exc.code)
            for key, value in exc.headers.items():
                if key.lower() not in HOP_BY_HOP and key.lower() != "content-length":
                    self.send_header(key, value)
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)
        except (OSError, TimeoutError, urllib.error.URLError) as exc:
            self._send_json(
                {
                    "error": "upstream_unavailable",
                    "message": "The iMac AI OS backend is temporarily unreachable.",
                    "upstream": self.upstream_base,
                    "detail": f"{type(exc).__name__}: {exc}",
                    "broker_writes": False,
                },
                502,
            )

    do_GET = _proxy
    do_POST = _proxy
    do_PUT = _proxy
    do_PATCH = _proxy
    do_DELETE = _proxy
    do_OPTIONS = _proxy


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), OperatorGatewayHandler)
    print(f"AI OS MacBook operator gateway listening on http://{HOST}:{PORT} -> {UPSTREAM}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
