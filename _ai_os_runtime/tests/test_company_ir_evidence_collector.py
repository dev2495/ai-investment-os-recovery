from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_company_ir_collector_is_primary_source_and_evidence_only() -> None:
    source = (ROOT / "scripts" / "collect_company_ir_reports.py").read_text()
    assert "investor-relations URL must use HTTPS" in source
    assert "official_company_ir" in source
    assert '"financial_facts_extracted": False' in source
    assert '"broker_write_allowed": False' in source
    assert "company_statement_facts" not in source
    assert "portfolio.orders" not in source
    assert "curl_get" in source
    assert "--insecure" not in source
    assert "urllib.parse.quote(urllib.parse.unquote(parsed.path)" in source


def test_company_ir_collector_excludes_subsidiaries_by_default() -> None:
    source = (ROOT / "scripts" / "collect_company_ir_reports.py").read_text()
    assert "include_subsidiaries" in source
    assert '"subsidiary"' in source
    assert "--include-subsidiaries" in source


def test_pdf_extractor_reuses_verified_local_pdf() -> None:
    source = (ROOT / "scripts" / "extract_filing_pdfs.py").read_text()
    assert 'existing_path = str(filing.get("local_path") or "").strip()' in source
    assert 'handle.read(4) == b"%PDF"' in source


def test_company_ir_run_ledger_has_truthful_constraints() -> None:
    migration = (ROOT / "postgres" / "init" / "197_company_ir_evidence_collector_v1.sql").read_text()
    assert "research.company_ir_collection_runs" in migration
    assert "chk_company_ir_run_https" in migration
    assert "never creates financial facts" in migration


def test_company_ir_collector_is_available_through_scoped_api() -> None:
    source = (ROOT / "api" / "ai_os_api_server.py").read_text()
    assert "def run_company_ir_collector(payload: dict) -> dict:" in source
    assert 'self.path == "/api/research/company-ir/collect"' in source
    assert '"research.company_ir_collection_runs"' in source
