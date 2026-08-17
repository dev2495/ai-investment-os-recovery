from __future__ import annotations

import importlib.util
import socket
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ingest_research_source.py"
SPEC = importlib.util.spec_from_file_location("ingest_research_source_security", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class ResearchSourceSecurityTest(unittest.TestCase):
    def test_rejects_loopback_and_private_dns_results(self) -> None:
        for address in ("127.0.0.1", "10.0.0.8", "192.168.1.10", "169.254.1.1"):
            with self.subTest(address=address), mock.patch.object(
                module.socket,
                "getaddrinfo",
                return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))],
            ):
                with self.assertRaisesRegex(ValueError, "non-public"):
                    module.validate_public_https("https://example.com/research.pdf")

    def test_requires_https_without_embedded_credentials(self) -> None:
        for url in ("http://example.com/a", "https://user:secret@example.com/a"):
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, "public HTTPS"):
                module.validate_public_https(url)

    def test_accepts_public_https_resolution(self) -> None:
        with mock.patch.object(
            module.socket,
            "getaddrinfo",
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
        ):
            parsed = module.validate_public_https("https://example.com/research.pdf")
        self.assertEqual(parsed.hostname, "example.com")

    def test_redirect_handler_fails_closed_before_following(self) -> None:
        handler = module.RejectRedirectHandler()
        with self.assertRaisesRegex(ValueError, "redirects are not followed"):
            handler.redirect_request(None, None, 302, "Found", {}, "https://127.0.0.1/private")


if __name__ == "__main__":
    unittest.main()
