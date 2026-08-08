from __future__ import annotations

import importlib.util
import sys
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sync_sector_zerodha_history.py"
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("sync_sector_zerodha_history", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(module)


def test_date_chunks_cover_range_without_overlap() -> None:
    chunks = list(module.date_chunks(date(2020, 1, 1), date(2026, 8, 8), 1500))
    assert chunks[0][0] == date(2020, 1, 1)
    assert chunks[-1][1] == date(2026, 8, 8)
    for left, right in zip(chunks, chunks[1:]):
        assert right[0] == left[1] + timedelta(days=1)


def test_script_retains_read_only_and_daily_login_guards() -> None:
    source = SCRIPT.read_text()
    assert '"broker_write_allowed": False' in source
    assert "daily Zerodha login is required" in source
    assert "--persist" in source
    assert "place_order" not in source
    assert "broker_order" not in source
