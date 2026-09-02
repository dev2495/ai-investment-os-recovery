import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ResearchRuntimeIntegrationContractTests(unittest.TestCase):
    def test_redundant_research_daemon_is_opt_in(self):
        supervisor = (ROOT / "deploy" / "imac-backend" / "bin" / "supervisor.sh").read_text(encoding="utf-8")
        self.assertIn('AI_OS_ENABLE_RESEARCH_AGENT_DAEMON:-0', supervisor)
        self.assertIn('AI_OS_PDF_PYTHON', supervisor)

    def test_supervisor_replaces_only_expected_non_loopback_ollama(self):
        supervisor = (ROOT / "deploy" / "imac-backend" / "bin" / "supervisor.sh").read_text(encoding="utf-8")
        self.assertIn("stop_non_loopback_ollama_listener", supervisor)
        self.assertIn('[[ "${command_line}" == *"ollama serve"* ]]', supervisor)
        self.assertIn('/Applications/Ollama.app/Contents/MacOS/Ollama', supervisor)
        self.assertIn('OLLAMA_HOST="127.0.0.1:${AI_OS_OLLAMA_PORT}"', supervisor)
        self.assertIn('grep -Ev \'^(127\\.0\\.0\\.1|\\[::1\\]):\'', supervisor)

    def test_backend_start_and_stop_cover_the_runtime_api_entrypoint(self):
        control = (ROOT / "deploy" / "imac-backend" / "bin" / "aios-imac").read_text(encoding="utf-8")
        self.assertGreaterEqual(control.count("/_ai_os_runtime/api/ai_os_api_runtime.py"), 2)

    def test_standalone_daemon_pdf_runtime_is_external_ssd_and_fails_closed(self):
        service = (ROOT / "launchd" / "aios-agent-daemon-service.sh").read_text(encoding="utf-8")
        plist = (ROOT / "launchd" / "com.devarsh.aios.agent-daemon.plist").read_text(encoding="utf-8")
        governed_runtime = "/Volumes/Devarsh SSD/AI OS Data/runtime/pdf-extraction/bin/python"
        for source in (service, plist):
            self.assertIn(governed_runtime, source)
            self.assertNotIn(".cache/codex-runtimes", source)
        self.assertIn("external-SSD governed root", service)
        self.assertIn("requires the governed external-SSD PDF runtime", service)
        self.assertIn("import pypdf", service)
        self.assertGreaterEqual(service.count("exit 78"), 3)

    def test_integrated_worker_has_distinct_durable_heartbeat(self):
        daemon = (ROOT / "scripts" / "run_agent_message_daemon.py").read_text(encoding="utf-8")
        self.assertIn('daemon_key="research_case_worker"', daemon)
        self.assertIn('"integrated_into_agent_message_daemon": True', daemon)

    def test_source_completion_dispatch_is_scoped_to_latest_preflight(self):
        source_runtime = (ROOT / "api" / "research_case_source_runtime.py").read_text(encoding="utf-8")
        self.assertIn("preflight_id=preflight.id", source_runtime)
        self.assertNotIn(
            "SELECT count(*) FROM research.research_case_model_runs WHERE research_case_id={case_id})::integer model_run_count",
            source_runtime,
        )

    def test_source_and_monitor_refresh_preserve_terminal_research_blocks(self):
        source_runtime = (ROOT / "api" / "research_case_source_runtime.py").read_text(encoding="utf-8")
        monitor_runtime = (ROOT / "api" / "research_monitor_runtime.py").read_text(encoding="utf-8")
        self.assertIn("TERMINAL_RESEARCH_LEAD_STATUS_SQL", source_runtime)
        self.assertIn("ready.get(\"case_status\") != \"blocked\"", source_runtime)
        self.assertIn("status IN ('proposed','blocked')", source_runtime)
        self.assertIn("status IN ('completed','review','blocked')", monitor_runtime)
        for terminal_status in ("cost_ceiling_blocked", "independent_review_blocked", "agent_run_blocked"):
            self.assertIn(terminal_status, source_runtime)

    def test_new_approved_preflight_advances_iteration_instead_of_overwriting_history(self):
        runtime = (ROOT / "api" / "research_case_agent_runtime.py").read_text(encoding="utf-8")
        self.assertIn("lifetime_run_count", runtime)
        self.assertIn("iteration = max_iteration + 1 if force_new_iteration or lifetime_run_count > 0 else 1", runtime)
        self.assertIn("Fresh analysis iteration is running automatically", runtime)

    def test_pdf_callers_do_not_use_internal_codex_runtime(self):
        targets = [
            ROOT / "scripts" / "run_strategy_discovery_scheduler.py",
            ROOT / "scripts" / "run_agent_message_daemon.py",
            ROOT / "scripts" / "extract_long_term_source_document.py",
            ROOT / "scripts" / "ingest_research_paper.py",
            ROOT / "api" / "research_case_source_runtime.py",
            ROOT / "api" / "ai_os_api_server.py",
            ROOT / "api" / "client_import_api.py",
        ]
        for target in targets:
            source = target.read_text(encoding="utf-8")
            self.assertNotIn(".cache/codex-runtimes", source, str(target))
            self.assertIn("governed_pdf", source, str(target))

    def test_pdf_retry_reuses_report_row(self):
        report = (ROOT / "api" / "research_case_report.py").read_text(encoding="utf-8")
        retry = report.split("def retry_pending_research_case_report", 1)[1]
        self.assertIn("retry_research_case_report_pdf", retry)
        self.assertNotIn("generate_research_case_report", retry)

    def test_case_report_download_never_falls_back_to_html(self):
        server = (ROOT / "api" / "ai_os_api_server.py").read_text(encoding="utf-8")
        route = server.split('case_report_match = re.fullmatch', 1)[1].split(
            'report_delivery_match = re.fullmatch', 1
        )[0]
        self.assertIn('pdf_artifact = available_report_artifact(report_row.get("pdf_path"))', route)
        self.assertIn('selected = pdf_artifact if action == "download" else html_artifact', route)
        self.assertIn('"error": "report_delivery_not_ready"', route)
        self.assertIn('"html_view_available": bool(html_artifact)', route)
        self.assertIn('"pdf_download_available": bool(pdf_artifact)', route)
        self.assertIn('"repair_endpoint": "/api/research/cases/report-delivery/repair"', route)
        self.assertIn("}, 409)", route)
        self.assertNotIn(
            'if action == "download" and report_rows[0].get("pdf_path") else',
            route,
        )

    def test_thesis_and_valuation_consume_exchange_aware_quote_truth(self):
        workspace = (ROOT / "api" / "long_term_thesis_workspace.py").read_text(encoding="utf-8")
        workbench = (ROOT / "api" / "valuation_workbench.py").read_text(encoding="utf-8")
        builder = (ROOT / "scripts" / "build_fundamental_valuation_suite.py").read_text(encoding="utf-8")
        agent_runtime = (ROOT / "api" / "research_case_agent_runtime.py").read_text(encoding="utf-8")
        self.assertIn('"market_price_anchor"', workspace)
        self.assertIn("upper(exchange)={exchange_sql}", workspace)
        self.assertIn("resolve_market_price", workbench)
        for consumer in (workspace, builder, agent_runtime):
            self.assertIn("valuation_price_entitled", consumer)
            self.assertIn("verified_zerodha_instrument", consumer)
            self.assertIn("broker_write_allowed", consumer)
        self.assertIn("resolve_market_price", builder)
        self.assertIn("resolve_market_price", agent_runtime)
        self.assertIn("decision_usable", builder)
        self.assertIn("market_quote_status", agent_runtime)

    def test_research_quote_path_preserves_canonical_zerodha_surfaces(self):
        required_scripts = [
            "sync_zerodha_read_only.py",
            "sync_zerodha_market_data.py",
            "stream_zerodha_live.py",
            "configure_zerodha_imac.sh",
            "renew_zerodha_session_imac.sh",
            "install_zerodha_stream_imac.sh",
        ]
        for file_name in required_scripts:
            self.assertTrue((ROOT / "scripts" / file_name).is_file(), file_name)
        self.assertTrue((ROOT / "launchd" / "aios-zerodha-stream-service.sh").is_file())
        resolver = (ROOT / "api" / "market_price_resolver.py").read_text(encoding="utf-8")
        workspace = (ROOT / "api" / "long_term_thesis_workspace.py").read_text(encoding="utf-8")
        builder = (ROOT / "scripts" / "build_fundamental_valuation_suite.py").read_text(encoding="utf-8")
        for consumer in (workspace, builder):
            self.assertIn("market.live_quote_state", consumer)
            self.assertIn("market.price_quotes", consumer)
            self.assertIn("market.zerodha_instruments", consumer)
            self.assertIn("source_priority", consumer)
        self.assertIn("provider", resolver)
        self.assertIn("quote_timestamp", resolver)
        self.assertIn("freshness", resolver)
        self.assertIn("decision_usable", resolver)
        self.assertIn('"broker_write_allowed": False', resolver)

    def test_research_following_and_vector_refresh_are_bounded_and_incremental(self):
        monitor = (ROOT / "scripts" / "run_research_following_monitor.py").read_text(encoding="utf-8")
        indexer = (ROOT / "scripts" / "index_qdrant_documents.py").read_text(encoding="utf-8")
        self.assertIn("operator-approved Research Following", monitor)
        self.assertIn("sources_due", monitor)
        self.assertIn('"broker_write_allowed": False', monitor)
        self.assertIn("index_all_collections_incremental", indexer)
        self.assertIn("--rebuild-all", indexer)
        self.assertIn("external Devarsh SSD data root is unavailable", indexer)

    def test_zerodha_health_migration_matches_live_tool_registry_schema(self):
        migration = (ROOT / "postgres" / "init" / "252_zerodha_research_quote_health_v1.sql").read_text(encoding="utf-8")
        self.assertIn("UPDATE agent.tool_registry", migration)
        self.assertIn("WHERE tool_name = 'ai_os_zerodha_live_prices'", migration)
        self.assertNotIn("updated_at = now()", migration)

    def test_scanner_publication_verifies_exact_approved_request(self):
        service = (ROOT / "services" / "scanner_engine" / "service.py").read_text(encoding="utf-8")
        publish = service.split("def publish_scanner", 1)[1].split("def _load_company_metrics", 1)[0]
        self.assertIn("approval_type='scanner_publish'", publish)
        self.assertIn("status='approved'", publish)
        self.assertIn("scanner_version_id", publish)
        self.assertIn("scope_key", publish)


    def test_glm53_daily_driver_promotion_is_reviewed_and_public_only(self):
        runtime = (ROOT / "api" / "research_model_runtime.py").read_text(encoding="utf-8")
        server = (ROOT / "api" / "ai_os_api_server.py").read_text(encoding="utf-8")
        self.assertIn("def review_and_promote_public_model_canary", runtime)
        self.assertIn("reviewed_response_hash does not match", runtime)
        self.assertIn("citation score >= 90, numeric score >= 95", runtime)
        self.assertIn("'research.public.daily_driver'", runtime)
        self.assertIn("'broker_write_allowed',false", runtime)
        self.assertIn("/api/research/model-runs/canary/review-promote", server)
        self.assertIn('"canaries": """', server)
        canary_wrapper = server.split("def run_research_public_model_canary", 1)[1].split(
            "def review_and_promote_research_public_model_canary", 1
        )[0]
        self.assertIn('if key not in {"response_output", "response_preview"}', canary_wrapper)
        self.assertIn('"raw_response_stored"] = False', canary_wrapper)

    def test_report_delivery_repair_uses_api_filesystem_not_database_server_files(self):
        server = (ROOT / "api" / "ai_os_api_server.py").read_text(encoding="utf-8")
        repair = server.split("def repair_research_case_report_delivery", 1)[1].split(
            "def repair_research_case", 1
        )[0]
        self.assertNotIn("pg_stat_file", repair)
        self.assertIn("stored_report_artifact_exists", repair)
        self.assertIn("ssd_root.is_mount()", repair)
        self.assertIn("candidate.stat().st_size > 0", repair)


if __name__ == "__main__":
    unittest.main()
