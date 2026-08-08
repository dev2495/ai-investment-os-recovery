import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("company_ir_collector", SCRIPTS / "collect_company_ir_reports.py")
COLLECTOR = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(COLLECTOR)


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


def test_ir_discovery_requires_document_level_annual_report_label(monkeypatch) -> None:
    html = b"""<html><body>
      <a href='/annual-reports/2025-2026/newspaper-ad-post-dispatch.pdf'>Annual AGM newspaper ad</a>
      <a href='/annual-reports/2025-2026/annual-return-2025-26.pdf'>Annual return 2025-26</a>
      <a href='/annual-reports/2025-2026/company-integrated-annual-report-2025-26.pdf'>Integrated Annual Report 2025-26</a>
    </body></html>"""
    monkeypatch.setattr(COLLECTOR, "fetch_bytes", lambda *_args, **_kwargs: html)
    rows = COLLECTOR.discover_reports("https://company.example/annual-reports/", False, 10)
    assert len(rows) == 1
    assert rows[0]["url"].endswith("company-integrated-annual-report-2025-26.pdf")


def test_pdf_extractor_reuses_verified_local_pdf() -> None:
    source = (ROOT / "scripts" / "extract_filing_pdfs.py").read_text()
    assert 'existing_path = str(filing.get("local_path") or "").strip()' in source
    assert 'handle.read(4) == b"%PDF"' in source
    assert "except OSError as exc:" in source
    assert 'errors.append(f"{command[0]}: {type(exc).__name__}: {exc}")' in source


def test_api_prefers_managed_node_pdf_runtime() -> None:
    api = (ROOT / "api" / "ai_os_api_server.py").read_text()
    requirements = (ROOT / "requirements-pdf.txt").read_text()
    assert 'AI_OS_NODE/runtime/python/bin/python3' in api
    assert "NODE_PDF_PYTHON" in api
    assert "pypdf[crypto]==" in requirements


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


def test_direct_official_pdf_has_explicit_fiscal_year_and_canonical_url() -> None:
    report = COLLECTOR.direct_report(
        "https://company.example/investors/Annual%20Report%202025-26.pdf?download=1#page=2",
        2026,
    )
    assert report["url"] == "https://company.example/investors/Annual%20Report%202025-26.pdf?download=1"
    assert report["fiscal_year_start"] == 2025
    assert report["fiscal_year_end"] == 2026


def test_direct_official_document_rejects_non_pdf_or_http() -> None:
    for url in (
        "http://company.example/investors/annual-report.pdf",
        "https://company.example/investors/annual-report.html",
    ):
        try:
            COLLECTOR.direct_report(url, 2026)
        except ValueError:
            continue
        raise AssertionError(f"unsafe direct document accepted: {url}")


def test_scoped_api_accepts_direct_document_with_explicit_year() -> None:
    source = (ROOT / "api" / "ai_os_api_server.py").read_text()
    assert 'payload.get("document_url")' in source
    assert '"--fiscal-year-end"' in source
    assert "provide exactly one investor_relations_url or document_url" in source


def test_governed_ir_source_registry_requires_https_and_operator_verification() -> None:
    migration = (ROOT / "postgres" / "init" / "204_company_ir_source_registry_v1.sql").read_text()
    assert "research.company_ir_sources" in migration
    assert "chk_company_ir_source_https" in migration
    assert "chk_company_ir_source_document_year" in migration
    assert "broker_write_allowed" in migration
    api = (ROOT / "api" / "ai_os_api_server.py").read_text()
    assert "def register_company_ir_source(payload: dict) -> dict:" in api
    assert "operator confirmation is required to register a primary source" in api
    assert 'self.path == "/api/research/company-ir/sources"' in api
    assert 'self.path == "/api/research/company-ir/sources/collect"' in api
    registration = api[api.index("def register_company_ir_source"):api.index("def collect_registered_company_ir_source")]
    assert "output = run_psql_text" in registration
    assert "rows = json.loads(output" in registration
    assert "run_psql_json(f\"\"\"" not in registration
    collection = api[api.index("def collect_registered_company_ir_source"):api.index("def run_filing_pdf_extractor")]
    assert "except Exception:" in collection
    assert "last_collection_run_id" in collection
    assert "investor_relations_url" in collection
    assert "operator_verified_official_ir" in registration
    assert "INSERT INTO research.companies" in registration
    assert "sync_real_company_intake" in collection


def test_fundamental_coverage_exposes_source_registration_and_collection() -> None:
    frontend = (ROOT / "ai-office-ui" / "src" / "destinations" / "fundamental" / "FundamentalResearch.tsx").read_text()
    assert "function CompanyIRSourceRegistry()" in frontend
    assert "Register source" in frontend
    assert "collectSource(row)" in frontend
