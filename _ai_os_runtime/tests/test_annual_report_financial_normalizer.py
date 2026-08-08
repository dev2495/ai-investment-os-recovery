import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts" / "normalize_annual_report_financials.py"
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("normalizer", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_reported_pair_removes_note_number_but_rejects_ambiguous_rows() -> None:
    assert MODULE.reported_pair("Revenue from operations 20 2,17,106 2,04,609") == (217106.0, 204609.0)
    assert MODULE.reported_pair("Total Revenue 342,476 308,761") == (342476.0, 308761.0)
    assert MODULE.reported_pair("Profit for the year - - 30,221 - 30,221") is None


def test_page_kind_requires_consolidated_statement_heading() -> None:
    assert MODULE.page_kind("Consolidated Statement of Profit and Loss") == "income_statement"
    assert MODULE.page_kind("Consolidated Balance Sheet") == "balance_sheet"
    assert MODULE.page_kind("Standalone Statement of Profit and Loss") is None


def test_normalizer_retains_review_and_execution_guards() -> None:
    source = PATH.read_text()
    assert "machine_extracted_unreviewed" in source
    assert '"broker_write_allowed": False' in source
    assert "--persist" in source
    assert "portfolio.orders" not in source
