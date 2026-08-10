from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from _ai_os_runtime.deploy.macbook_operator.macbook_operator_gateway import (
    OperatorGatewayHandler,
    sanitized_path,
)


class UpstreamHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args: object) -> None:
        return

    def _respond(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        payload = json.dumps({"path": self.path, "method": self.command, "body": body.decode()}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = _respond
    do_POST = _respond


class MacBookOperatorGatewayTests(unittest.TestCase):
    def test_sensitive_query_values_are_redacted(self) -> None:
        safe = sanitized_path("/api/zerodha/auth/callback?request_token=secret&status=success")
        self.assertNotIn("secret", safe)
        self.assertIn("status=success", safe)

    def test_gateway_forwards_get_and_post_without_changing_contract(self) -> None:
        upstream = ThreadingHTTPServer(("127.0.0.1", 0), UpstreamHandler)
        upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        upstream_thread.start()

        class TestGateway(OperatorGatewayHandler):
            upstream_base = f"http://127.0.0.1:{upstream.server_port}"

            def log_message(self, *_args: object) -> None:
                return

        gateway = ThreadingHTTPServer(("127.0.0.1", 0), TestGateway)
        gateway_thread = threading.Thread(target=gateway.serve_forever, daemon=True)
        gateway_thread.start()
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{gateway.server_port}/api/liveness?node=macbook",
                timeout=3,
            ) as response:
                get_payload = json.load(response)
            request = urllib.request.Request(
                f"http://127.0.0.1:{gateway.server_port}/api/chat",
                data=b'{"message":"hello"}',
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=3) as response:
                post_payload = json.load(response)
        finally:
            gateway.shutdown()
            upstream.shutdown()
            gateway.server_close()
            upstream.server_close()

        self.assertEqual(get_payload["path"], "/api/liveness?node=macbook")
        self.assertEqual(post_payload["method"], "POST")
        self.assertEqual(json.loads(post_payload["body"]), {"message": "hello"})


if __name__ == "__main__":
    unittest.main()
