from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sync_zerodha_market_data.py"
MIGRATION = ROOT / "postgres" / "init" / "201_zerodha_symbol_canonicalization_v1.sql"
SPEC = importlib.util.spec_from_file_location("sync_zerodha_market_data", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(module)


def test_broker_instrument_types_are_canonicalized() -> None:
    assert module.canonical_instrument_type("NSE", "EQ") == "equity"
    assert module.canonical_instrument_type("NFO", "CE") == "option"
    assert module.canonical_instrument_type("NFO", "PE") == "option"
    assert module.canonical_instrument_type("NFO", "FUT") == "future"
    assert module.canonical_instrument_type("NSE", "INDEX") == "index"


def test_historical_sync_verifies_committed_rows() -> None:
    source = SCRIPT.read_text()
    assert "historical candles were returned but none committed" in source
    assert '"api_rows": len(values)' in source
    assert '"rows": committed_rows' in source


def test_migration_merges_eq_candles_into_canonical_equities() -> None:
    sql = MIGRATION.read_text()
    assert "INSERT INTO trading.ohlcv" in sql
    assert "canonical.instrument_type='equity'" in sql
    assert "DELETE FROM trading.ohlcv" in sql
    assert "SET active=false" in sql
