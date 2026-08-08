import importlib.util
import sys
from pathlib import Path
from unittest import TestCase


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("register_operating_peer_set", SCRIPTS / "register_operating_peer_set.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class OperatingPeerRegistryTests(TestCase):
    def test_validates_required_primary_source_phrases(self):
        peer = {
            "symbol": "BHARATWIRE",
            "source_url": "https://nsearchives.nseindia.com/example.html",
            "required_phrases": ["Bharat Wire Ropes Limited", "manufacturing of wire, wire ropes, slings"],
        }
        result = MODULE.validate_peer(
            peer,
            b"<html><body>BHARAT WIRE ROPES LIMITED - MANUFACTURING OF WIRE, WIRE ROPES, SLINGS</body></html>",
        )
        self.assertEqual(result["symbol"], "BHARATWIRE")
        self.assertEqual(len(result["content_hash"]), 64)

    def test_rejects_unapproved_or_unsupported_evidence(self):
        with self.assertRaises(ValueError):
            MODULE.validate_peer(
                {"symbol": "X", "source_url": "http://example.com", "required_phrases": ["wire ropes"]},
                b"wire ropes",
            )
        with self.assertRaises(ValueError):
            MODULE.validate_peer(
                {"symbol": "X", "source_url": "https://www.nseindia.com/example", "required_phrases": ["wire ropes"]},
                b"unrelated company",
            )
