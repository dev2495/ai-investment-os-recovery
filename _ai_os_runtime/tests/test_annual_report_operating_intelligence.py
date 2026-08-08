import importlib.util
import sys
from pathlib import Path
from unittest import TestCase, mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "normalize_annual_report_operating_intelligence",
    SCRIPTS / "normalize_annual_report_operating_intelligence.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class FakePage:
    def __init__(self, text):
        self.text = text

    def extract_text(self):
        return self.text


class FakeReader:
    def __init__(self, _path):
        self.pages = [
            FakePage(
                "THE YEAR IN PERSPECTIVE Dear Shareholders Profit after tax stood at 491 Crore. "
                "We are in the process of installing a 4 MWp rooftop solar PV system. "
                "Going forward, we intend to invest approximately ₹200–250 Crore annually to further expand capacity."
            ),
            FakePage(
                "PRODUCTION VOLUME VIA PRODUCTS - STANDALONE (Qty in MT) "
                "Products FY 2025-26 FY 2024-25 Wire Ropes 74,629 76,126 "
                "Wire/Strands/LRPC 97,971 90,934 Conveyor Cord 3,460 3,870. "
                "Over the last three years, augmenting our rope and wire capacity by 40,000 MT."
            ),
            FakePage(
                "We completed the installation of 2.2 MWp of on-site solar power capacity at our Ranchi plant. "
                "The remaining 1.8 MWp capacity under Phase II is expected to be commissioned during FY 2026-27."
            ),
        ]


class OperatingIntelligenceExtractionTests(TestCase):
    def test_extracts_only_explicit_operating_facts_and_commitments(self):
        fake_pypdf = mock.Mock(PdfReader=FakeReader)
        with mock.patch.dict(sys.modules, {"pypdf": fake_pypdf}):
            result = MODULE.extract_report(Path("annual-report.pdf"), 2026)

        values = {(row["kpi_key"], row["period_end"]): row["value_numeric"] for row in result["observations"]}
        self.assertEqual(values[("wire_ropes_production_mt", "2026-03-31")], 74629)
        self.assertEqual(values[("wire_ropes_production_mt", "2025-03-31")], 76126)
        self.assertEqual(values[("wire_strands_lrpc_production_mt", "2026-03-31")], 97971)
        self.assertEqual(values[("conveyor_cord_production_mt", "2026-03-31")], 3460)
        self.assertEqual(values[("rope_wire_capacity_added_mt", "2026-03-31")], 40000)
        self.assertEqual(values[("onsite_solar_installed_mwp", "2026-03-31")], 2.2)
        self.assertEqual(result["communication"]["page_start"], 1)
        self.assertEqual(result["communication"]["page_end"], 3)
        claims = {row["claim_key"]: row for row in result["claims"]}
        self.assertEqual(claims["solar_phase_2_commissioning"]["target_value"], 1.8)
        self.assertEqual(claims["solar_phase_2_commissioning"]["target_period_end"], "2027-03-31")
        self.assertEqual(claims["annual_growth_capex_lower_bound"]["target_value"], 200)
        self.assertIn("upper bound 250", claims["annual_growth_capex_lower_bound"]["target_unit"])
        self.assertEqual(claims["rooftop_solar_installation"]["target_value"], 4.0)
        self.assertEqual(claims["rooftop_solar_installation"]["metric_key"], "onsite_solar_installed_mwp")

    def test_does_not_invent_numeric_market_share(self):
        class MarketShareReader:
            def __init__(self, _path):
                self.pages = [FakePage("Our global market share is small, but we now have the capabilities to win more.")]

        with mock.patch.dict(sys.modules, {"pypdf": mock.Mock(PdfReader=MarketShareReader)}):
            result = MODULE.extract_report(Path("annual-report.pdf"), 2026)
        self.assertEqual(result["observations"], [])
        self.assertEqual(result["claims"], [])
        self.assertIsNone(result["communication"])

    def test_kpi_definition_start_is_earliest_observation(self):
        results = [
            {"observations": [{"kpi_key": "wire_ropes_production_mt", "period_end": "2026-03-31"}]},
            {"observations": [{"kpi_key": "wire_ropes_production_mt", "period_end": "2025-03-31"}]},
        ]
        starts = {
            key: min(
                observation["period_end"]
                for result in results
                for observation in result["observations"]
                if observation["kpi_key"] == key
            )
            for key in {
                observation["kpi_key"]
                for result in results
                for observation in result["observations"]
            }
        }
        self.assertEqual(starts, {"wire_ropes_production_mt": "2025-03-31"})

    def test_claim_outcome_is_truthful_about_partial_delivery(self):
        self.assertEqual(MODULE.outcome_status(4.0, 4.0), "met")
        self.assertEqual(MODULE.outcome_status(4.0, 2.2), "partially_met")
        self.assertEqual(MODULE.outcome_status(4.0, 0.0), "missed")
