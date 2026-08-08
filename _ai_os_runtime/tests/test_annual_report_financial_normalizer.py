import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


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
    assert MODULE.page_kind("Consolidated Statement of Cash Flows") == "cash_flow"


def test_line_pair_joins_wrapped_cash_flow_rows() -> None:
    lines = [
        "Purchase of property, plant and equipment, capital work in progress and intangible",
        "assets (19,806) (24,465)",
    ]
    assert MODULE.line_pair(lines, 0) == (
        (-19806.0, -24465.0),
        "Purchase of property, plant and equipment, capital work in progress and intangible assets (19,806) (24,465)",
    )


def test_extracts_balances_and_cash_flow_with_statement_context(monkeypatch) -> None:
    class Page:
        def __init__(self, text):
            self.text = text

        def extract_text(self):
            return self.text

    class Reader:
        pages = [
            Page("""Consolidated Balance Sheet
ASSETS
Inventories 11 95,782 98,491
Trade receivables 12(i) 64,342 52,763
Cash and cash equivalents 12(ii) 24,184 26,072
TOTAL 4,21,182 3,74,794
EQUITY AND LIABILITIES
Total equity 3,30,208 2,75,171
Non-current liabilities
Borrowings 16(i) 2,413 14,540
Current liabilities
Borrowings 19(i) 12,141 19,216
Total liabilities 90,974 99,623"""),
            Page("""Consolidated Statement of Cash Flows
Net cash flow from operating activities 65,534 42,176
Purchase of property, plant and equipment, capital work in progress and intangible
assets (19,806) (24,465)
Dividend paid (9,137) (8,380)"""),
        ]

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=lambda _: Reader()))
    facts, _ = MODULE.extract_annual_report(Path("ignored.pdf"), 2026)
    by_key = {row["fact_key"]: row for row in facts}
    assert by_key["total_assets"]["current_value"] == 421182.0
    assert by_key["non_current_borrowings"]["current_value"] == 2413.0
    assert by_key["current_borrowings"]["current_value"] == 12141.0
    assert by_key["operating_cash_flow"]["current_value"] == 65534.0
    assert by_key["capital_expenditure"]["current_value"] == -19806.0
    assert by_key["dividends_paid"]["current_value"] == -9137.0


def test_normalizer_retains_review_and_execution_guards() -> None:
    source = PATH.read_text()
    assert "machine_extracted_unreviewed" in source
    assert '"broker_write_allowed": False' in source
    assert "--persist" in source
    assert "portfolio.orders" not in source


def test_single_segment_declaration_is_exact_and_normalized(monkeypatch) -> None:
    class Page:
        def extract_text(self):
            return 'Accordingly, the Company has a single operating segment, i.e., \u201cWire &\nWire Ropes\u201d.'

    class Reader:
        pages = [Page()]

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=lambda _: Reader()))
    result = MODULE.extract_single_segment_declaration(Path("ignored.pdf"))
    assert result is not None
    assert result["segment_key"] == "wire_wire_ropes"
    assert result["segment_name"] == "Wire & Wire Ropes"
    assert result["page_number"] == 1
