from __future__ import annotations

import datetime as dt
import sys
import unittest
from decimal import Decimal
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME_ROOT / "scripts"))

import build_sector_underwrite as underwrite


class SectorUnderwriteTests(unittest.TestCase):
    def test_windows_cover_range_without_exceeding_official_limit(self) -> None:
        start = dt.date(2016, 7, 26)
        end = dt.date(2026, 8, 9)
        windows = underwrite.annual_windows(start, end)
        self.assertEqual(windows[0][0], start)
        self.assertEqual(windows[-1][1], end)
        self.assertTrue(all((right - left).days <= 364 for left, right in windows))
        self.assertTrue(all(windows[index][1] + dt.timedelta(days=1) == windows[index + 1][0]
                            for index in range(len(windows) - 1)))

    def test_normalization_rejects_invalid_values_and_deduplicates_dates(self) -> None:
        rows = underwrite.normalize_history([
            {"DATE": "01 Jan 2025", "pe": "34.06", "pb": "8.98", "divYield": "1.9",
             "RequestNumber": "one", "Index Name": "Nifty IT"},
            {"DATE": "01 Jan 2025", "pe": "35", "pb": "9", "divYield": "2",
             "RequestNumber": "two", "Index Name": "Nifty IT"},
            {"DATE": "02 Jan 2025", "pe": "-1", "pb": "0", "divYield": "-1"},
            {"DATE": "not-a-date", "pe": "20"},
        ])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["price_to_earnings"], Decimal("35"))
        self.assertEqual(rows[0]["request_number"], "two")
        self.assertEqual(len(rows[0]["input_fingerprint"]), 64)

    def test_percentiles_are_deterministic_and_use_latest_value(self) -> None:
        rows = [
            {"price_to_earnings": Decimal(value), "valuation_date": dt.date(2025, 1, index + 1),
             "input_fingerprint": str(index) * 64}
            for index, value in enumerate(("10", "20", "30", "40", "50"))
        ]
        stats = underwrite.valuation_statistics(rows)
        self.assertEqual(stats["current_value"], Decimal("50"))
        self.assertEqual(stats["median_value"], Decimal("30"))
        self.assertEqual(stats["p10_value"], Decimal("14.0"))
        self.assertEqual(stats["observation_count"], 5)
        self.assertEqual(stats["percentile_rank"], Decimal("90"))

    def test_dossier_is_complete_but_does_not_fabricate_missing_evidence(self) -> None:
        evidence = {
            "fundamentals": {"member_count": 10, "lineage_complete_count": 10,
                             "current_pe_count": 10, "latest_fundamental_at": "2026-08-08"},
            "flows": {"observation_count": 36, "symbol_count": 8,
                      "latest_at": "2026-06-24", "net_value": "100"},
            "ownership": {"observation_count": 636, "symbol_count": 10,
                          "latest_period_end": "2026-06-30"},
            "indices": {"definition_count": 4, "active_count": 4},
            "portfolio": {"positions": [{"symbol": "INFY", "as_of": "2025-09-17"}],
                          "sector_market_value": "83971.1", "total_market_value": "23472021.79",
                          "latest_portfolio_as_of": "2026-06-30"},
        }
        stats = {"current_value": Decimal("30"), "percentile_rank": Decimal("55"),
                 "observation_count": 2500, "median_value": Decimal("27")}
        sections, references, monitoring, thesis = underwrite.build_dossier(
            {"taxonomy_key": "nifty-it", "node_name": "Nifty IT"},
            dt.date(2026, 8, 9), stats, evidence,
            [{"path": "/Volumes/Devarsh SSD/official.json", "sha256": "a" * 64}],
        )
        self.assertEqual(tuple(sections), underwrite.DOSSIER_SECTION_KEYS)
        self.assertEqual(len(sections), 15)
        self.assertEqual(sections["macro_sensitivities"]["status"], "gap")
        self.assertEqual(sections["macro_sensitivities"]["evidence"], [])
        self.assertIn("block any allocation recommendation", thesis)
        self.assertGreaterEqual(len(references), 3)
        self.assertGreaterEqual(len(monitoring), 3)

    def test_committee_is_independent_dissenting_and_human_final(self) -> None:
        sections = {
            "valuation": {"status": "source_backed"},
            "constituent_fundamentals": {"status": "source_backed"},
            "ownership_and_flows": {"status": "source_backed"},
            "portfolio_fit": {"status": "evaluated", "conclusion": "Measured", "evidence": [{"value": 1}]},
            "opportunity_cost": {"status": "incomplete", "conclusion": "Blocked", "evidence": [{"value": 1}]},
        }
        snapshot, positions, dissent, risk = underwrite.build_committee(
            sections, {}, {}, [{"source": "official"}], [{"gap": "one"}]
        )
        self.assertGreaterEqual(len(positions), 5)
        self.assertEqual(len({position["agent"] for position in positions}), len(positions))
        self.assertIn("dissent", dissent.lower())
        self.assertGreaterEqual(len(risk), 1)
        self.assertTrue(snapshot["controls"]["human_final_required"])
        self.assertFalse(snapshot["controls"]["capital_action_allowed"])
        self.assertFalse(snapshot["controls"]["broker_write_allowed"])

    def test_v4_gate_requires_real_history_dossier_and_dissent(self) -> None:
        migration = (RUNTIME_ROOT / "postgres" / "init" / "208_sector_underwrite_valuation_v1.sql").read_text()
        self.assertIn("v_history_count>=2000", migration)
        self.assertIn("INTERVAL '10 years'+INTERVAL '7 days'", migration)
        self.assertIn("jsonb_array_length(packet.independent_positions)>=5", migration)
        self.assertIn("coverage.dossier_sections ?& ARRAY[", migration)
        self.assertIn("SELECT max(latest.version)", migration)
        self.assertIn("'critical_evidence_gaps'", migration)
        self.assertIn("'historical_membership'", migration)
        self.assertIn("'missing_evidence_may_not_be_inferred',true", migration)
        self.assertIn("'current_constituent_substitution_allowed',false", migration)
        self.assertIn("packet.capital_action_allowed=false", migration)
        self.assertIn('"market_share_and_capacity_history"', (
            RUNTIME_ROOT / "scripts" / "build_sector_underwrite.py"
        ).read_text())

    def test_api_mcp_and_frontend_expose_only_the_governed_builder(self) -> None:
        api = (RUNTIME_ROOT / "api" / "ai_os_api_server.py").read_text()
        mcp = (RUNTIME_ROOT / "mcp_server" / "ai_os_mcp_server.py").read_text()
        actions = (RUNTIME_ROOT / "ai-office-ui" / "src" / "data" / "actions.ts").read_text()
        screen = (RUNTIME_ROOT / "ai-office-ui" / "src" / "destinations" / "sector" / "SectorIntelligence.tsx").read_text()
        self.assertIn('"/api/sector-intelligence/underwrite/build"', api)
        self.assertIn("run_acceptance_gates_v4(", api)
        self.assertIn('"ai_os_build_sector_underwrite"', mcp)
        self.assertIn('"capital_action_allowed"] = False', mcp)
        self.assertIn('"broker_write_allowed"] = False', mcp)
        self.assertIn('"/api/sector-intelligence/underwrite/build"', actions)
        self.assertIn("Build Institutional Sector Underwrite", screen)
        self.assertIn("Capital and broker authority stay locked", screen)

    def test_dossier_version_is_stable_for_the_same_point_in_time_cutoff(self) -> None:
        source = (RUNTIME_ROOT / "scripts" / "build_sector_underwrite.py").read_text()
        self.assertIn("source_cutoff_at::date AS source_cutoff_date", source)
        self.assertIn("same_cutoff = bool(", source)
        self.assertIn('"evidence_sources": [', source)


if __name__ == "__main__":
    unittest.main()
