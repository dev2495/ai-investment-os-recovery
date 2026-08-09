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


def test_reported_eps_pair_uses_last_two_values_after_note_number() -> None:
    assert MODULE.reported_eps_pair("Basic earnings per equity share 42 54.28 48.00") == (54.28, 48.0)


def test_page_kind_requires_consolidated_statement_heading() -> None:
    assert MODULE.page_kind("Consolidated Statement of Profit and Loss") == "income_statement"
    assert MODULE.page_kind("Consolidated Balance Sheet") == "balance_sheet"
    assert MODULE.page_kind("Standalone Statement of Profit and Loss") is None
    assert MODULE.page_kind("Consolidated Statement of Cash Flows") == "cash_flow"
    assert MODULE.page_kind("Consolidated Statement of Cash Flow") == "cash_flow"
    assert MODULE.page_kind("Consolidated Statement of Profit & Loss") == "income_statement"


def test_page_unit_uses_the_statement_scale_without_guessing() -> None:
    assert MODULE.page_unit("All amounts in crores of INR") == "INR crore"
    assert MODULE.page_unit("(In INR Million)") == "INR million"
    assert MODULE.page_unit("(` million)") == "INR million"
    assert MODULE.page_unit("Figures in lakh") == "INR lakh"
    assert MODULE.page_unit("Consolidated Balance Sheet") is None


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


def test_extracts_numbered_income_rows_and_aggregated_receivables(monkeypatch) -> None:
    class Page:
        def __init__(self, text):
            self.text = text

        def extract_text(self):
            return self.text

    class Reader:
        pages = [
            Page("""Consolidated Statement of Profit and Loss
I Revenue from Operations 50 568,154 529,883
X Profit after tax (VIII-IX) 48,055 42,530
Basic earnings per equity share 42 54.28 48.00"""),
            Page("""Consolidated Balance Sheet
ASSETS
(ii) Trade Receivables 15
(1) Billed 75,369 65,486
(2) Unbilled 58,208 49,984
EQUITY AND LIABILITIES"""),
            Page("""Consolidated Statement of Cash Flow
Net cash generated from operating activities (A) 61,720 57,857
Purchase of Property, Plant and Equipment and Intangible
Assets (6,957) (5,935)
Payment of dividend (40,255) (38,418)"""),
        ]

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=lambda _: Reader()))
    facts, _ = MODULE.extract_annual_report(Path("ignored.pdf"), 2026)
    by_key = {row["fact_key"]: row for row in facts}
    assert by_key["revenue_from_operations"]["current_value"] == 568154.0
    assert by_key["profit_after_tax"]["current_value"] == 48055.0
    assert by_key["basic_eps"]["current_value"] == 54.28
    assert by_key["trade_receivables"]["current_value"] == 133577.0
    assert by_key["operating_cash_flow"]["current_value"] == 61720.0
    assert by_key["capital_expenditure"]["current_value"] == -6957.0
    assert by_key["dividends_paid"]["current_value"] == -40255.0


def test_reported_and_unbilled_receivables_are_combined(monkeypatch) -> None:
    class Page:
        def extract_text(self):
            return """Consolidated Balance Sheet
ASSETS
Trade receivables 11 135,901 117,745
Unbilled receivables 76,823 64,280"""

    class Reader:
        pages = [Page()]

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=lambda _: Reader()))
    facts, _ = MODULE.extract_annual_report(Path("ignored.pdf"), 2026)
    receivables = next(row for row in facts if row["fact_key"] == "trade_receivables")
    assert receivables["current_value"] == 212724.0
    assert receivables["comparative_value"] == 182025.0


def test_billed_and_unbilled_receivables_are_aggregated(monkeypatch) -> None:
    class Page:
        def extract_text(self):
            return """Consolidated Balance Sheet
ASSETS
(i) Trade receivables - billed 3.5(a) 18,000 17,000
(ii) Trade receivables - unbilled 3.5(a) 601 1,022"""

    class Reader:
        pages = [Page()]

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=lambda _: Reader()))
    facts, _ = MODULE.extract_annual_report(Path("ignored.pdf"), 2026)
    receivables = next(row for row in facts if row["fact_key"] == "trade_receivables")
    assert receivables["current_value"] == 18601.0
    assert receivables["comparative_value"] == 18022.0


def test_nci_only_dividend_is_not_used_as_company_dividend(monkeypatch) -> None:
    class Page:
        def extract_text(self):
            return """Consolidated Statement of Cash Flows
Dividends paid to the NCI (154) (121)
Dividends paid (8,500) (7,900)"""

    class Reader:
        pages = [Page()]

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=lambda _: Reader()))
    facts, _ = MODULE.extract_annual_report(Path("ignored.pdf"), 2026)
    dividends = next(row for row in facts if row["fact_key"] == "dividends_paid")
    assert dividends["current_value"] == -8500.0


def test_ampersand_income_statement_retains_reported_unit(monkeypatch) -> None:
    class Page:
        def extract_text(self):
            return """Consolidated Statement of Profit & Loss
(In INR Million)
Revenue from operations 26 119,387.17 98,215.87
Net Profit for the year 14,001.61 10,934.91
Basic (In INR) 91.22 72.44"""

    class Reader:
        pages = [Page()]

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=lambda _: Reader()))
    facts, _ = MODULE.extract_annual_report(Path("ignored.pdf"), 2025)
    by_key = {row["fact_key"]: row for row in facts}
    assert by_key["revenue_from_operations"]["unit"] == "INR million"
    assert by_key["profit_after_tax"]["current_value"] == 14001.61
    assert by_key["basic_eps"]["unit"] == "INR/share"


def test_normalizer_retains_review_and_execution_guards() -> None:
    source = PATH.read_text()
    assert "filing.extraction_status IN ('captured','extracted')" in source
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
