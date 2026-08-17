from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_parser():
    spec = importlib.util.spec_from_file_location(
        "secure_client_report_parser",
        ROOT / "scripts" / "ingest_secure_client_report.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_aditya_birla_style_lots_and_exceptions_are_deterministic() -> None:
    module = load_parser()
    html = b"""
    <table>
      <tr><td>Client Code</td><td>MASKED-REF</td></tr>
    </table>
    <table>
      <tr>
        <th>Scrip Name</th><th>Purchase Date</th><th>Sale Date</th><th>Units</th>
        <th>Buy Value</th><th>Sale Value</th><th>Realised Gain</th><th>Brokerage</th><th>Type</th>
      </tr>
      <tr><td>ALPHA LTD</td><td>01/04/2023</td><td>02/04/2024</td><td>10</td><td>1000</td><td>1300</td><td>295</td><td>5</td><td>Market</td></tr>
      <tr><td>BONUS LTD</td><td>bad-date</td><td>01/05/2024</td><td>-4</td><td>0</td><td>400</td><td>400</td><td>0</td><td>Off Market</td></tr>
      <tr><td>SPLIT LTD</td><td>01/05/2024</td><td>01/06/2024</td><td>5</td><td>0</td><td>500</td><td>500</td><td>0</td><td>Market</td></tr>
      <tr><td>Total</td><td></td><td></td><td></td><td>1000</td><td>1700</td><td>695</td><td>5</td><td></td></tr>
    </table>
    """
    tables = module.parse_html_tables(html)
    rows, exceptions = module.parse_report(tables)
    assert len(rows) == 4
    assert [row.layer for row in rows] == ["tax_lot", "tax_lot", "tax_lot", "tax_summary"]
    codes = {item.code for item in exceptions}
    assert {"malformed_date", "negative_quantity", "zero_or_missing_cost", "missing_corporate_action", "off_market_or_manual"} <= codes
    assert module.extract_identity(tables)
    assert all("MASKED-REF" not in item.message for item in exceptions)


def test_pdf_is_preserved_but_not_presented_as_structured_rows(tmp_path: Path) -> None:
    module = load_parser()
    source = tmp_path / "report.pdf"
    source.write_bytes(b"%PDF-1.7\nnot-a-real-pdf")
    tables, issue = module.load_tables(source)
    assert tables == []
    assert issue == "structured_excel_required"


def test_control_surface_has_scoped_access_and_no_broker_write_route() -> None:
    migration = (ROOT / "postgres" / "init" / "219_secure_client_report_import_v1.sql").read_text(encoding="utf-8")
    api = (ROOT / "api" / "client_import_api.py").read_text(encoding="utf-8")
    wrapper = (ROOT / "api" / "ai_os_api_runtime.py").read_text(encoding="utf-8")
    frontend = (ROOT / "ai-office-ui" / "src" / "destinations" / "portfolio" / "PortfolioTerminal.tsx").read_text(encoding="utf-8")
    assert "client_access_grants" in migration
    assert "portfolio_identity_review" in migration
    assert "WHERE import.identity_status='resolved'" in migration
    assert "AND import.identity_status='resolved'" in (ROOT / "scripts" / "ingest_secure_client_report.py").read_text(encoding="utf-8")
    assert "checksum-addressed" in api
    assert "X-AI-OS-Client-Code" in wrapper
    assert "raw_payload_included" in api
    assert "broker_write_allowed\": False" in api
    assert "Secure Broker Report Intake" in frontend
    assert "Normalized Transaction Evidence" in frontend
    assert "/api/client-imports/upload" not in frontend


def test_options_desk_exposes_provenance_liquidity_and_staleness() -> None:
    options = (ROOT / "ai-office-ui" / "src" / "destinations" / "options" / "OptionsDesk.tsx").read_text(encoding="utf-8")
    registry = (ROOT / "postgres" / "init" / "168_tradingagents_mrchartist_capabilities_v1.sql").read_text(encoding="utf-8")
    assert "https://github.com/MrChartist/india-s-best-option-hub" in registry
    assert "Market Data Provenance" in options
    assert "spreadBps" in options
    assert "liquidity_status" in options
    assert "batch_freshness_status" in options
    assert "broker writes locked" in options.lower()


def load_client_import_api():
    import types
    sys.modules["ai_os_api_server"] = types.SimpleNamespace()
    spec = importlib.util.spec_from_file_location(
        "client_import_api_for_test",
        ROOT / "api" / "client_import_api.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_browser_capture_sanitizes_visible_holdings_and_fund_rows() -> None:
    api = load_client_import_api()
    parser = load_parser()
    source = """
    <script>ignored</script>
    <table>
      <tr><th>Symbol</th><th>Qty</th><th>Avg Price</th><th>LTP</th><th>Market Value</th></tr>
      <tr><td>ALPHA</td><td>10</td><td>100</td><td>110</td><td>1100</td></tr>
      <tr style="display: none"><td>HIDDEN</td><td>99</td><td>1</td><td>1</td><td>99</td></tr>
    </table>
    """
    clean, summary = api.sanitize_visible_browser_content(source, "text/html")
    assert b"HIDDEN" not in clean
    assert b"script" not in clean.lower()
    assert summary == {"tables": 1, "cells": 10}
    rows, exceptions = parser.parse_report(parser.parse_html_tables(clean))
    assert len(rows) == 1 and rows[0].layer == "holding"
    assert str(rows[0].values["market_value"]) == "1100"
    assert exceptions == []

    funds, _ = api.sanitize_visible_browser_content(
        "Available Funds\t25000\nCollateral Value\t5000", "text/plain"
    )
    fund_rows, fund_exceptions = parser.parse_report(parser.parse_html_tables(funds))
    assert len(fund_rows) == 1 and fund_rows[0].layer == "fund_balance"
    assert str(fund_rows[0].values["available_funds"]) == "25000"
    assert fund_exceptions == []


def test_browser_capture_rejects_credentials_and_has_no_browser_write_surface() -> None:
    api_module = load_client_import_api()
    try:
        api_module.sanitize_visible_browser_content(
            "<table><tr><td>Authorization: Bearer secret</td><td>x</td></tr></table>",
            "text/html",
        )
    except ValueError as exc:
        assert "credentials" in str(exc)
    else:
        raise AssertionError("credential-like content was accepted")

    api = (ROOT / "api" / "client_import_api.py").read_text(encoding="utf-8")
    wrapper = (ROOT / "api" / "ai_os_api_runtime.py").read_text(encoding="utf-8")
    migration = (ROOT / "postgres" / "init" / "220_governed_browser_client_capture_v1.sql").read_text(encoding="utf-8")
    assert "/api/client-browser-captures/submit" in wrapper
    assert "3 * 1024 * 1024" in wrapper
    assert "payload.get(\"url\")" not in api
    assert "page_title must be a short label, not a URL" in api
    assert "credentials_captured',false" in api
    assert "browser_write_allowed',false" in api
    assert "CHECK (NOT credentials_captured)" in migration
    assert "CHECK (NOT browser_write_allowed)" in migration


def test_client_workspace_separates_historical_evidence_from_current_state() -> None:
    api = (ROOT / "api" / "client_import_api.py").read_text(encoding="utf-8")
    schema = (ROOT / "ai-office-ui" / "src" / "data" / "schemas.ts").read_text(encoding="utf-8")
    frontend = (ROOT / "ai-office-ui" / "src" / "destinations" / "portfolio" / "PortfolioTerminal.tsx").read_text(encoding="utf-8")
    assert "client_import_workspace_status" in api
    assert "client_import_realized_summary" in api
    assert "pending_current_capture" in api
    assert "blocked_missing_current_holdings_or_cash" in api
    assert "false broker_write_allowed,false client_record_mutation_allowed" in api
    assert "total_rows" in api and "has_more" in api
    assert "client_import_workspace_status" in schema
    assert "Authorized Client Evidence Workspace" in frontend
    assert "Historical exports are primary evidence" in api
    assert "Performance / CAGR" in frontend
    assert "Broker writes and client-record mutation locked" in frontend
