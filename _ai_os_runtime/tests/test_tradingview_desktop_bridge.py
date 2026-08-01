import pathlib
import subprocess
import unittest
from unittest import mock

from _ai_os_runtime.api import ai_os_api_server
from _ai_os_runtime.api import tradingview_desktop_bridge


class TradingViewDesktopBridgeTests(unittest.TestCase):
    def test_probe_reports_missing_app_without_claiming_a_session(self) -> None:
        with (
            mock.patch.object(
                tradingview_desktop_bridge,
                "TRADINGVIEW_DESKTOP_APP",
                pathlib.Path("/definitely/missing/TradingView.app"),
            ),
            mock.patch.object(tradingview_desktop_bridge.sys, "platform", "linux"),
        ):
            status = tradingview_desktop_bridge.probe_desktop()

        self.assertFalse(status["installed"])
        self.assertFalse(status["running"])
        self.assertFalse(status["automation_permission"])
        self.assertEqual(status["session_state"], "user_managed")
        self.assertFalse(status["broker_execution_allowed"])

    def test_open_link_rejects_non_tradingview_url(self) -> None:
        with self.assertRaisesRegex(ValueError, "tradingview.com"):
            tradingview_desktop_bridge.open_link_in_desktop("https://example.com/chart")

    def test_open_link_uses_direct_url_without_accessibility_permission(self) -> None:
        ready = {
            "installed": True,
            "running": True,
            "automation_permission": False,
        }
        target_url = "https://www.tradingview.com/chart/?symbol=NSE%3ARELIANCE"
        process = mock.Mock(pid=4321)
        with (
            mock.patch.object(tradingview_desktop_bridge, "probe_desktop", return_value=ready),
            mock.patch.object(
                tradingview_desktop_bridge.subprocess,
                "Popen",
                return_value=process,
            ) as popen,
        ):
            result = tradingview_desktop_bridge.open_link_in_desktop(target_url)

        self.assertEqual(result["status"], "handoff_requested")
        self.assertEqual(result["handoff"], "direct_url_async")
        self.assertEqual(result["launch_pid"], 4321)
        popen.assert_called_once_with(
            ["/usr/bin/open", "-g", "-a", "TradingView", target_url],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    def test_open_link_uses_clipboard_and_accessibility_menu(self) -> None:
        ready = {
            "installed": True,
            "running": True,
            "automation_permission": True,
        }
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with (
            mock.patch.object(tradingview_desktop_bridge, "probe_desktop", return_value=ready),
            mock.patch.object(tradingview_desktop_bridge.subprocess, "Popen", side_effect=OSError("direct failed")),
            mock.patch.object(
                tradingview_desktop_bridge.subprocess,
                "run",
                side_effect=[completed, completed],
            ) as run,
        ):
            result = tradingview_desktop_bridge.open_link_in_desktop(
                "https://www.tradingview.com/chart/?symbol=NSE%3ARELIANCE"
            )

        self.assertEqual(result["status"], "opened")
        self.assertEqual(result["handoff"], "clipboard_menu")
        commands = [call.args[0][0] for call in run.call_args_list]
        self.assertEqual(commands, ["/usr/bin/pbcopy", "/usr/bin/osascript"])

    def test_cdp_command_enables_websocket_on_node_20(self) -> None:
        command = ai_os_api_server.tradingview_cdp_node_command(
            pathlib.Path("/tmp/execute.mjs"),
            {"symbol": "NSE:RELIANCE", "timeframe": "D"},
        )

        self.assertEqual(command[:2], ["node", "--experimental-websocket"])
        self.assertEqual(command[2:4], ["/tmp/execute.mjs", "--payload-json"])
        self.assertIn('"symbol": "NSE:RELIANCE"', command[4])

    def test_api_serializes_permission_gated_task_as_one_json_document(self) -> None:
        task = {"id": 91, "task_title": "Open TradingView Desktop: NSE:RELIANCE"}
        updated = {
            **task,
            "status": "waiting_input",
            "result_summary": "TradingView Desktop requires Accessibility permission.",
        }
        with (
            mock.patch.object(ai_os_api_server, "create_tradingview_task", return_value=task),
            mock.patch.object(
                ai_os_api_server,
                "open_link_in_desktop",
                return_value={
                    "status": "permission_required",
                    "desktop": {"installed": True, "running": True, "automation_permission": False},
                },
            ),
            mock.patch.object(
                ai_os_api_server,
                "run_psql_json_statement",
                return_value=[updated],
            ) as json_query,
            mock.patch.object(
                ai_os_api_server,
                "probe_tradingview_cdp",
                return_value={"available": True, "port": 9333},
            ),
            mock.patch.object(ai_os_api_server, "audit_api_write"),
        ):
            result = ai_os_api_server.open_tradingview_desktop_chart(
                {"symbol": "RELIANCE", "exchange": "NSE", "timeframe": "15"}
            )

        sql = json_query.call_args.args[0]
        self.assertIn("WITH updated AS", sql)
        self.assertIn("json_agg(row_to_json(updated))", sql)
        self.assertEqual(result["status"], "permission_required")
        self.assertEqual(result["task"]["status"], "waiting_input")
        self.assertTrue(result["desktop"]["cdp_fallback"]["available"])

    def test_frontend_can_launch_an_installed_stopped_desktop(self) -> None:
        frontend = (
            pathlib.Path(__file__).resolve().parents[1]
            / "ai-office-ui"
            / "src"
            / "destinations"
            / "trading"
            / "TradingDesk.tsx"
        ).read_text(encoding="utf-8")

        self.assertIn("const desktopInstalled = Boolean(desktopStatus.installed)", frontend)
        self.assertIn("status === \"handoff_requested\"", frontend)
        self.assertIn('disabled={busy || !desktopInstalled}', frontend)
        self.assertNotIn('disabled={busy || !desktopRunning}', frontend)

    def test_template_parameter_reads_nested_allowlisted_payload(self) -> None:
        payload = {
            "parameters": {"benchmark": "NSE:NIFTY", "unexpected": "ignored"},
            "metadata": {"benchmark": "NSE:BANKNIFTY"},
        }

        self.assertEqual(
            ai_os_api_server.tradingview_parameter(payload, "benchmark"),
            "NSE:NIFTY",
        )
        self.assertEqual(
            ai_os_api_server.sanitize_tradingview_template_parameters(payload),
            {"benchmark": "NSE:NIFTY"},
        )

    def test_ratio_template_compiles_nested_benchmark(self) -> None:
        template = {
            "template_key": "relative_strength_ratio_chart",
            "default_exchange": "NSE",
            "default_timeframe": "D",
        }

        plan = ai_os_api_server.compile_tradingview_template_plan(
            template,
            {
                "symbol": "RELIANCE",
                "parameters": {"benchmark": "NSE:NIFTY"},
            },
            ["RELIANCE"],
        )

        self.assertTrue(plan["execution_ready"])
        self.assertEqual(plan["symbol_expression"], "100*NSE:RELIANCE/NSE:NIFTY")
        self.assertFalse(plan["broker_order_allowed"])

    def test_market_regime_template_compiles_four_chart_board(self) -> None:
        template = {
            "template_key": "market_regime_four_pane",
            "default_exchange": "NSE",
            "default_timeframe": "D",
        }
        parameters = {
            "equity_index": "NSE:NIFTY",
            "volatility_index": "NSE:INDIAVIX",
            "bond_yield": "TVC:IN10Y",
            "currency": "FX_IDC:USDINR",
        }

        plan = ai_os_api_server.compile_tradingview_template_plan(
            template,
            {"symbol": "NIFTY", "parameters": parameters},
            ["NIFTY"],
        )

        self.assertTrue(plan["execution_ready"])
        self.assertEqual(plan["fulfillment"], "complete_four_chart_evidence_board")
        self.assertEqual(len(plan["panes"]), 4)
        self.assertEqual(plan["validated_parameters"], parameters)
        self.assertFalse(plan["broker_order_allowed"])

    def test_incomplete_gated_template_is_rejected_before_approval_write(self) -> None:
        template = {
            "template_key": "create_alert_request",
            "template_name": "Create Alert Request",
            "category": "alert",
            "action_kind": "alert_request",
            "default_exchange": "NSE",
            "default_timeframe": "D",
            "default_chart_layout": "single",
            "requires_symbol": True,
            "approval_required": True,
            "execution_mode": "human_gated_request",
            "status": "gated",
            "owner_agent": "Trading Desk Agent",
            "description": "Create a governed TradingView alert request.",
            "risk_notes": "Manual confirmation required.",
            "default_payload": {},
        }
        with (
            mock.patch.object(ai_os_api_server, "run_psql_json", return_value=[template]),
            mock.patch.object(ai_os_api_server, "run_psql_json_statement") as write_query,
        ):
            with self.assertRaisesRegex(ValueError, "required: condition"):
                ai_os_api_server.execute_tradingview_template_action(
                    {"template_key": "create_alert_request", "symbol": "RELIANCE"}
                )

        write_query.assert_not_called()

    def test_frontend_exposes_advanced_template_parameters(self) -> None:
        frontend = (
            pathlib.Path(__file__).resolve().parents[1]
            / "ai-office-ui"
            / "src"
            / "destinations"
            / "trading"
            / "TradingDesk.tsx"
        ).read_text(encoding="utf-8")

        self.assertIn('title="Advanced Chart Templates"', frontend)
        self.assertIn('parameters: templateParametersFor(templateKey)', frontend)
        for label in (
            "Benchmark",
            "Hedge Ratio",
            "Call Symbol",
            "Financial Fields",
            "Bond Yield",
            "Alert Condition",
        ):
            self.assertIn(f'"{label}"', frontend)

    def test_charlie_routes_explicit_desktop_chart_command(self) -> None:
        with mock.patch.object(
            ai_os_api_server,
            "open_tradingview_desktop_chart",
            return_value={"status": "opened", "target_url": "https://www.tradingview.com/chart/"},
        ) as desktop_open:
            operations = ai_os_api_server.execute_charlie_safe_tools(
                "Open RELIANCE in TradingView at 15 minutes"
            )

        self.assertEqual(operations[0]["tool"], "open_tradingview_desktop")
        self.assertEqual(operations[0]["status"], "opened")
        payload = desktop_open.call_args.args[0]
        self.assertEqual(payload["symbol"], "RELIANCE")
        self.assertEqual(payload["timeframe"], "15")


if __name__ == "__main__":
    unittest.main()
