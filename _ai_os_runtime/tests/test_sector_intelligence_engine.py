from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = RUNTIME_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

import run_sector_intelligence_engine as engine


AS_OF = date(2026, 7, 31)


def membership(symbol_id: int, symbol: str, **values: object) -> dict[str, object]:
    return {
        "symbol_id": symbol_id,
        "symbol": symbol,
        "valid_from": "2025-01-01",
        "valid_to": None,
        "observed_at": "2026-07-30T18:00:00+00:00",
        "source_reference": f"official:{symbol}",
        "evidence": [{"source": "official taxonomy"}],
        **values,
    }


def prices(symbol_id: int, first: float, last: float) -> list[dict[str, object]]:
    return [
        {"symbol_id": symbol_id, "ts": "2026-06-30T10:00:00+00:00", "close": first, "evidence": [{"source": "exchange"}]},
        {"symbol_id": symbol_id, "ts": "2026-07-31T10:00:00+00:00", "close": last, "evidence": [{"source": "exchange"}]},
    ]


class SectorIntelligenceMathTests(unittest.TestCase):
    def test_all_weighting_methods_and_cap_normalization(self) -> None:
        rows = [
            membership(1, "NSE:A", market_cap=80, free_float_factor=0.5, quality_score=9, momentum_score=2, custom_score=5),
            membership(2, "NSE:B", market_cap=15, free_float_factor=0.8, quality_score=3, momentum_score=5, custom_score=3),
            membership(3, "NSE:C", market_cap=5, free_float_factor=1.0, quality_score=1, momentum_score=3, custom_score=2),
        ]
        expected_leaders = {
            "equal": 1,
            "market_cap": 1,
            "free_float_market_cap": 1,
            "quality": 1,
            "momentum": 2,
            "custom": 1,
        }
        for method, leader in expected_leaders.items():
            with self.subTest(method=method):
                computed = engine.compute_weights(rows, method, AS_OF, 0.50)
                self.assertTrue(math.isclose(sum(item["target_weight"] for item in computed), 1.0, abs_tol=1e-10))
                self.assertLessEqual(max(item["target_weight"] for item in computed), 0.50 + 1e-12)
                best = max(computed, key=lambda item: item["target_weight"])
                self.assertEqual(best["symbol_id"], leader)

    def test_index_history_relative_strength_breadth_and_rankings(self) -> None:
        weights = engine.compute_weights(
            [membership(1, "NSE:A"), membership(2, "NSE:B")], "equal", AS_OF
        )
        history = engine.compute_index_history(
            7,
            weights,
            prices(1, 100, 110) + prices(2, 200, 180),
            date(2026, 6, 30),
            AS_OF,
            1000,
        )
        self.assertEqual([round(item["index_value"], 6) for item in history], [1000.0, 1000.0])
        later_history = engine.compute_index_history(
            7,
            weights,
            prices(1, 100, 110) + prices(2, 200, 180),
            date(2026, 7, 1),
            AS_OF,
            1000,
        )
        self.assertEqual(len(later_history), 1)
        self.assertEqual(later_history[0]["ts"][:10], "2026-07-31")

        benchmark = [
            {"ts": "2026-06-30T10:00:00+00:00", "close": 100, "evidence": ["exchange"]},
            {"ts": "2026-07-31T10:00:00+00:00", "close": 105, "evidence": ["exchange"]},
        ]
        rs = engine.compute_relative_strength(
            {11: prices(99, 100, 120), 12: prices(98, 100, 101)}, benchmark, AS_OF, "1M"
        )
        self.assertEqual(next(item for item in rs if item["taxonomy_node_id"] == 11)["rank_value"], 1)
        self.assertAlmostEqual(next(item for item in rs if item["taxonomy_node_id"] == 11)["relative_return"], 0.15)

        evidence_rows = [
            {"symbol_id": 1, "return": 0.02, "observed_at": "2026-07-31T10:00:00+00:00", "evidence": ["exchange"]},
            {"symbol_id": 2, "return": -0.01, "observed_at": "2026-07-31T10:00:00+00:00", "evidence": ["exchange"]},
            {"symbol_id": 3, "return": 0.0, "observed_at": "2026-07-31T10:00:00+00:00", "evidence": ["exchange"]},
        ]
        breadth = engine.compute_breadth(11, evidence_rows, AS_OF, "1D")
        self.assertEqual((breadth["positive_count"], breadth["negative_count"], breadth["unchanged_count"]), (1, 1, 1))
        self.assertEqual(breadth["breadth_value"], 0.0)

        rankings = engine.compute_rankings(
            [
                {"taxonomy_node_id": 11, "score": 2.0, "observed_at": "2026-07-31T10:00:00+00:00", "evidence": ["calculation"]},
                {"taxonomy_node_id": 12, "score": 5.0, "observed_at": "2026-07-31T10:00:00+00:00", "evidence": ["calculation"]},
            ],
            AS_OF,
            "composite",
            "1M",
        )
        self.assertEqual([(item["taxonomy_node_id"], item["rank_value"]) for item in rankings], [(12, 1), (11, 2)])


class SectorIntelligencePointInTimeTests(unittest.TestCase):
    def test_membership_is_selected_as_of_date_without_lookahead(self) -> None:
        rows = [
            membership(1, "NSE:A", valid_to="2026-07-15", observed_at="2026-07-01T00:00:00+00:00"),
            membership(2, "NSE:B", valid_from="2026-07-16"),
            membership(3, "NSE:C", valid_from="2026-08-01", observed_at="2026-08-01T00:00:00+00:00"),
        ]
        self.assertEqual([row["symbol_id"] for row in engine.active_memberships(rows, date(2026, 7, 10))], [1])
        self.assertEqual([row["symbol_id"] for row in engine.active_memberships(rows, AS_OF)], [2])

    def test_missing_or_future_evidence_blocks_instead_of_fabricating(self) -> None:
        missing = membership(1, "NSE:A", market_cap=None)
        with self.assertRaises(engine.EvidenceError):
            engine.compute_weights([missing], "market_cap", AS_OF)
        future = membership(1, "NSE:A", market_cap=10, observed_at="2026-08-01T00:00:00+00:00")
        with self.assertRaises(engine.EvidenceError):
            engine.compute_weights([future], "market_cap", AS_OF)

        result = engine.run_engine(
            {
                "as_of_date": AS_OF.isoformat(),
                "index": {"index_id": 7, "index_key": "blocked", "index_name": "Blocked", "weighting_method": "market_cap", "base_value": 1000},
                "memberships": [missing],
                "prices": [],
            }
        )
        self.assertEqual(result["status"], "blocked_missing_evidence")
        self.assertEqual(result["weights"], [])
        self.assertFalse(result["governance"]["seed_or_fabricated_data"])


class SectorIntelligenceSafetyAndCliTests(unittest.TestCase):
    def valid_payload(self) -> dict[str, object]:
        return {
            "as_of_date": AS_OF.isoformat(),
            "index": {
                "index_id": 7,
                "index_key": "quality_basket",
                "index_name": "Quality Basket",
                "taxonomy_node_id": 11,
                "weighting_method": "equal",
                "weight_cap": 0.7,
                "base_value": 1000,
                "effective_date": "2026-06-30",
            },
            "memberships": [
                membership(1, "NSE:A", observed_at="2026-06-29T18:00:00+00:00"),
                membership(2, "NSE:B", observed_at="2026-06-29T18:00:00+00:00"),
            ],
            "prices": prices(1, 100, 110) + prices(2, 200, 210),
        }

    def test_execution_guard_and_tradingview_consumer_contract(self) -> None:
        result = engine.run_engine(self.valid_payload())
        self.assertEqual(result["status"], "completed")
        self.assertFalse(result["governance"]["broker_writes_allowed"])
        self.assertFalse(result["governance"]["capital_action_allowed"])
        self.assertFalse(result["governance"]["tradingview_authoritative"])
        self.assertFalse(result["governance"]["tradingview_execution_allowed"])
        self.assertEqual({item["target_workspace"] for item in result["tradingview_artifacts"]}, {"tradingview_desktop"})
        self.assertTrue(all(item["broker_order_allowed"] is False for item in result["tradingview_artifacts"]))
        sql = engine.build_persistence_sql(result)
        self.assertIn("broker-write guard violated", sql)
        self.assertNotIn("INSERT INTO trading.orders", sql)
        self.assertNotIn("INSERT INTO broker", sql)
        self.assertIn("INSERT INTO sector_intelligence.relative_strength_observations", sql)
        self.assertIn("IS NOT DISTINCT FROM", sql)
        self.assertIn("INSERT INTO sector_intelligence.breadth_observations", sql)
        self.assertIn("INSERT INTO sector_intelligence.sector_rankings", sql)

    def test_json_cli_dry_run_never_touches_database(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
            json.dump(self.valid_payload(), handle)
            input_path = Path(handle.name)
        try:
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS_ROOT / "run_sector_intelligence_engine.py"), "--input", str(input_path), "--dry-run"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            output = json.loads(completed.stdout)
            self.assertEqual(output["status"], "completed")
            self.assertEqual(output["database"], {"persisted": False, "dry_run": True})
            self.assertFalse(output["governance"]["broker_writes_allowed"])
        finally:
            input_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
