#!/usr/bin/env python3
"""Serve a built single-page app with history-route fallback."""

from __future__ import annotations

import argparse
import os
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


class SpaRequestHandler(SimpleHTTPRequestHandler):
    index_path: Path

    def _request_path_exists(self) -> bool:
        path = unquote(urlsplit(self.path).path).lstrip("/")
        candidate = Path(self.directory or ".") / path
        return candidate.exists()

    def _should_fallback(self) -> bool:
        path = unquote(urlsplit(self.path).path)
        return (
            self.command in {"GET", "HEAD"}
            and not path.startswith("/assets/")
            and not self._request_path_exists()
        )

    def send_head(self):  # type: ignore[no-untyped-def]
        if self._should_fallback():
            content = self.index_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command == "HEAD":
                return None
            from io import BytesIO

            return BytesIO(content)
        return super().send_head()

    def end_headers(self) -> None:
        path = unquote(urlsplit(self.path).path)
        if path == "/" or path.endswith("/index.html"):
            self.send_header("Cache-Control", "no-store")
        elif path.startswith("/assets/"):
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        super().end_headers()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", required=True, type=int)
    args = parser.parse_args()

    root = Path(args.directory).expanduser().resolve()
    index_path = root / "index.html"
    if not index_path.is_file():
        raise SystemExit(f"SPA index is missing: {index_path}")

    os.chdir(root)
    SpaRequestHandler.index_path = index_path
    server = ThreadingHTTPServer((args.host, args.port), SpaRequestHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
