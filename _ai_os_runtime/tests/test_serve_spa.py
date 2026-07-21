from __future__ import annotations

import functools
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from _ai_os_runtime.scripts.serve_spa import SpaRequestHandler


class SpaServerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        (root / "assets").mkdir()
        (root / "index.html").write_text("<main>AI Office</main>", encoding="utf-8")
        (root / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")
        SpaRequestHandler.index_path = root / "index.html"
        handler = functools.partial(SpaRequestHandler, directory=str(root))
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp_dir.cleanup()

    def test_history_route_returns_index(self) -> None:
        with urllib.request.urlopen(f"{self.base_url}/today", timeout=2) as response:
            self.assertEqual(response.status, 200)
            self.assertIn(b"AI Office", response.read())
            self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_asset_is_served_and_missing_asset_stays_404(self) -> None:
        with urllib.request.urlopen(f"{self.base_url}/assets/app.js", timeout=2) as response:
            self.assertEqual(response.status, 200)
            self.assertIn("immutable", response.headers["Cache-Control"])
        with self.assertRaises(urllib.error.HTTPError) as failure:
            urllib.request.urlopen(f"{self.base_url}/assets/missing.js", timeout=2)
        self.assertEqual(failure.exception.code, 404)
        failure.exception.close()


if __name__ == "__main__":
    unittest.main()
