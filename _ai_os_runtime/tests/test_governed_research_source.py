import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "collect_governed_research_source.py"
if not MODULE_PATH.exists():
    MODULE_PATH = Path(__file__).with_name("collect_governed_research_source.py")
spec = importlib.util.spec_from_file_location("collector", MODULE_PATH)
collector = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(collector)


class GovernedResearchSourceTests(unittest.TestCase):
    def test_canonical_url_strips_tracking_and_fragment(self):
        self.assertEqual(
            collector.canonicalize_url("https://SOIC.substack.com/p/a?utm_source=x&b=2&a=1#comments"),
            "https://soic.substack.com/p/a?a=1&b=2",
        )

    def test_rejects_non_https(self):
        with self.assertRaises(ValueError):
            collector.canonicalize_url("http://forum.valuepickr.com/t/example")

    def test_provider_hostname_boundary(self):
        self.assertTrue(collector.hostname_allowed("forum.valuepickr.com", r"(^|\.)valuepickr\.com$"))
        self.assertFalse(collector.hostname_allowed("valuepickr.com.attacker.example", r"(^|\.)valuepickr\.com$"))

    def test_html_metadata_and_visible_text(self):
        parsed = collector.parse_html_document(
            b'<html><head><meta property="og:title" content="Company note"><meta name="author" content="Analyst">'
            b'<meta property="article:published_time" content="2026-05-06T00:00:00Z"><script>secret()</script></head>'
            b'<body><article>Safety critical wire rope analysis.</article></body></html>'
        )
        self.assertEqual(parsed["title"], "Company note")
        self.assertEqual(parsed["author"], "Analyst")
        self.assertEqual(parsed["published_at"], "2026-05-06T00:00:00Z")
        self.assertIn("Safety critical", parsed["text"])
        self.assertNotIn("secret", parsed["text"])


if __name__ == "__main__":
    unittest.main()
