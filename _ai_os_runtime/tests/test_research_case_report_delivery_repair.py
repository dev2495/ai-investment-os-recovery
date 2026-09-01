from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
from _ai_os_runtime.api import ai_os_api_server


class ResearchCaseReportDeliveryRepairTests(unittest.TestCase):
    def test_requires_explicit_operator_confirmation(self) -> None:
        with self.assertRaisesRegex(ValueError, "operator_confirmed"):
            ai_os_api_server.repair_research_case_report_delivery({
                "research_case_id": 12,
                "operator_confirmed": False,
            })

    def test_retries_existing_html_on_same_report_without_research_rerun(self) -> None:
        database_rows = [
            [{"id": 12, "status": "blocked"}],
            [{"blocker_key": "report_pdf_render", "status": "open"}],
            [{"id": 91, "report_version": 3, "html_path": "/Volumes/Devarsh SSD/report.html", "pdf_path": None, "html_exists": True, "pdf_exists": False}],
        ]
        retry_result = {
            "status": "report_retry_completed",
            "ok": True,
            "research_case_id": 12,
            "report_id": 91,
            "report_version": 3,
            "html_path": "/Volumes/Devarsh SSD/report.html",
            "pdf_path": "/Volumes/Devarsh SSD/report.pdf",
            "pdf_hash": "abc",
        }
        with (
            mock.patch.object(ai_os_api_server, "run_psql_json", side_effect=database_rows),
            mock.patch.object(ai_os_api_server, "retry_research_case_report_pdf", return_value=retry_result) as retry,
            mock.patch.object(ai_os_api_server, "generate_research_case_report") as generate,
            mock.patch.object(ai_os_api_server, "audit_api_write"),
        ):
            result = ai_os_api_server.repair_research_case_report_delivery({
                "research_case_id": 12,
                "operator_confirmed": True,
                "actor": "Test operator",
            })

        retry.assert_called_once_with(91, "Test operator")
        generate.assert_not_called()
        self.assertTrue(result["pdf_download_available"])
        self.assertEqual(result["model_runs_created"], 0)
        self.assertEqual(result["source_jobs_created"], 0)
        self.assertFalse(result["model_preflight_created"])
        self.assertFalse(result["paid_research_rerun_required"])
        self.assertFalse(result["broker_write_allowed"])
        self.assertFalse(result["external_write_allowed"])

    def test_rebuilds_delivery_from_persisted_case_when_report_row_is_missing(self) -> None:
        database_rows = [
            [{"id": 15, "status": "blocked"}],
            [{"blocker_key": "research_pack_generation", "status": "open"}],
            [],
        ]
        generated = {
            "ok": True,
            "status": "generated",
            "research_case_id": 15,
            "report_id": 101,
            "report_version": 1,
            "html_path": "/Volumes/Devarsh SSD/report.html",
            "pdf_path": None,
            "content_state": "draft",
            "delivery_state": "html_ready_pdf_retry",
        }
        with (
            mock.patch.object(ai_os_api_server, "run_psql_json", side_effect=database_rows),
            mock.patch.object(ai_os_api_server, "generate_research_case_report", return_value=generated) as generate,
            mock.patch.object(ai_os_api_server, "retry_research_case_report_pdf") as retry,
            mock.patch.object(ai_os_api_server, "audit_api_write"),
        ):
            result = ai_os_api_server.repair_research_case_report_delivery({
                "research_case_id": 15,
                "operator_confirmed": True,
            })

        generate.assert_called_once_with(15, "Devarsh")
        retry.assert_not_called()
        self.assertTrue(result["html_view_available"])
        self.assertFalse(result["pdf_download_available"])
        self.assertEqual(result["delivery_state"], "html_ready_pdf_retry")
        self.assertEqual(result["model_runs_created"], 0)
        self.assertEqual(result["source_jobs_created"], 0)

    def test_already_ready_artifact_resolves_delivery_blocker_without_rerun(self) -> None:
        database_rows = [
            [{"id": 12, "status": "review"}],
            [{"blocker_key": "report_pdf_render", "status": "open"}],
            [{"id": 91, "report_version": 3, "html_path": "/Volumes/Devarsh SSD/report.html", "pdf_path": "/Volumes/Devarsh SSD/report.pdf", "html_exists": True, "pdf_exists": True}],
        ]
        with (
            mock.patch.object(ai_os_api_server, "run_psql_json", side_effect=database_rows),
            mock.patch.object(ai_os_api_server, "run_psql_json_statement", return_value=[{"id": 7}]) as resolve,
            mock.patch.object(ai_os_api_server, "generate_research_case_report") as generate,
            mock.patch.object(ai_os_api_server, "retry_research_case_report_pdf") as retry,
            mock.patch.object(ai_os_api_server, "audit_api_write"),
        ):
            result = ai_os_api_server.repair_research_case_report_delivery({
                "research_case_id": 12,
                "operator_confirmed": True,
            })

        resolve.assert_called_once()
        generate.assert_not_called()
        retry.assert_not_called()
        self.assertEqual(result["status"], "report_already_ready")
        self.assertTrue(result["html_view_available"])
        self.assertTrue(result["pdf_download_available"])
        self.assertEqual(result["model_runs_created"], 0)
        self.assertEqual(result["source_jobs_created"], 0)

    def test_rejects_non_delivery_blocker(self) -> None:
        database_rows = [
            [{"id": 17, "status": "blocked"}],
            [],
        ]
        with (
            mock.patch.object(ai_os_api_server, "run_psql_json", side_effect=database_rows),
            mock.patch.object(ai_os_api_server, "generate_research_case_report") as generate,
            mock.patch.object(ai_os_api_server, "retry_research_case_report_pdf") as retry,
        ):
            with self.assertRaisesRegex(ValueError, "No open report-delivery blocker"):
                ai_os_api_server.repair_research_case_report_delivery({
                    "research_case_id": 17,
                    "operator_confirmed": True,
                })
        generate.assert_not_called()
        retry.assert_not_called()


if __name__ == "__main__":
    unittest.main()
