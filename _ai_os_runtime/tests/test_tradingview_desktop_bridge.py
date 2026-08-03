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
        self.assertEqual(status["interaction_mode"], "unavailable")
        self.assertNotIn("browser", status["next_action"].lower())
        self.assertFalse(status["broker_execution_allowed"])

    def test_probe_uses_stable_process_name(self) -> None:
        app = pathlib.Path("/Applications/TradingView.app")
        pgrep = subprocess.CompletedProcess(args=[], returncode=0, stdout="56576\n", stderr="")
        version = subprocess.CompletedProcess(args=[], returncode=0, stdout="3.3.0\n", stderr="")
        permission = subprocess.CompletedProcess(args=[], returncode=0, stdout="true\n", stderr="")
        with (
            mock.patch.object(tradingview_desktop_bridge, "TRADINGVIEW_DESKTOP_APP", app),
            mock.patch.object(pathlib.Path, "exists", return_value=True),
            mock.patch.object(tradingview_desktop_bridge.sys, "platform", "darwin"),
            mock.patch.object(
                tradingview_desktop_bridge.subprocess,
                "run",
                side_effect=[pgrep, version, permission],
            ) as run,
        ):
            status = tradingview_desktop_bridge.probe_desktop()

        self.assertTrue(status["running"])
        self.assertEqual(run.call_args_list[0].args[0], ["/usr/bin/pgrep", "-x", "TradingView"])

    def test_open_link_rejects_non_tradingview_url(self) -> None:
        with self.assertRaisesRegex(ValueError, "tradingview.com"):
            tradingview_desktop_bridge.open_link_in_desktop("https://example.com/chart")

    def test_macos_open_prepares_clipboard_without_accessibility_permission(self) -> None:
        ready = {
            "installed": True,
            "running": True,
            "automation_permission": False,
        }
        target_url = "https://www.tradingview.com/chart/?symbol=NSE%3ARELIANCE"
        process = mock.Mock(pid=4321)
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with (
            mock.patch.object(tradingview_desktop_bridge, "probe_desktop", return_value=ready),
            mock.patch.object(tradingview_desktop_bridge.sys, "platform", "darwin"),
            mock.patch.object(tradingview_desktop_bridge.subprocess, "run", return_value=completed) as run,
            mock.patch.object(
                tradingview_desktop_bridge.subprocess,
                "Popen",
                return_value=process,
            ) as popen,
        ):
            result = tradingview_desktop_bridge.open_link_in_desktop(target_url)

        self.assertEqual(result["status"], "permission_required")
        self.assertEqual(result["handoff"], "clipboard_prepared")
        self.assertTrue(result["clipboard_prepared"])
        self.assertEqual(result["launch_pid"], 4321)
        self.assertEqual(run.call_args.args[0], ["/usr/bin/pbcopy"])
        popen.assert_called_once_with(
            ["/usr/bin/open", "-g", "-a", "TradingView"],
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
            mock.patch.object(tradingview_desktop_bridge.sys, "platform", "darwin"),
            mock.patch.object(tradingview_desktop_bridge.subprocess, "Popen") as popen,
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
        self.assertTrue(result["clipboard_prepared"])
        commands = [call.args[0][0] for call in run.call_args_list]
        self.assertEqual(commands, ["/usr/bin/pbcopy", "/usr/bin/osascript"])
        popen.assert_not_called()

    def test_compatibility_chart_action_uses_native_desktop_only(self) -> None:
        native_result = {
            "status": "done",
            "execution_surface": "native_desktop",
            "broker_order_allowed": False,
        }
        with mock.patch.object(
            ai_os_api_server,
            "execute_tradingview_desktop_plan",
            return_value=native_result,
        ) as execute:
            result = ai_os_api_server.execute_tradingview_chart_action({
                "symbol": "RELIANCE",
                "exchange": "NSE",
                "timeframe": "15",
                "capture_screenshot": True,
            })

        self.assertEqual(result, native_result)
        request = execute.call_args.args[0]
        self.assertEqual(request["metadata"]["execution_surface"], "native_desktop")
        self.assertEqual(request["compiled_plan"]["capture_status"], "not_performed")
        self.assertEqual(request["compiled_plan"]["panes"][0]["symbol"], "NSE:RELIANCE")

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
        self.assertNotIn("cdp_fallback", result["desktop"])

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
        self.assertIn('desktopMode !== "clipboard_menu"', frontend)
        self.assertIn("status === \"handoff_requested\"", frontend)
        self.assertIn('disabled={busy || !desktopInstalled}', frontend)
        self.assertIn('"Prepare App Link"', frontend)
        self.assertNotIn('disabled={busy || !desktopRunning}', frontend)
        self.assertIn('label="Desktop Workspace"', frontend)
        self.assertNotIn("useCaptureTradingViewChart", frontend)
        self.assertNotIn("CDP Capture", frontend)
        self.assertNotIn("localhost:9333", frontend)

    def test_active_runtime_does_not_start_a_managed_tradingview_browser(self) -> None:
        runtime_root = pathlib.Path(__file__).resolve().parents[1]
        active_files = [
            runtime_root / "scripts" / "start_ai_office_live.sh",
            runtime_root / "scripts" / "run_ai_office_supervisor.command",
            runtime_root / "deploy" / "imac-backend" / "bin" / "supervisor.sh",
            runtime_root / "launchd" / "aios-agent-daemon-service.sh",
        ]
        for path in active_files:
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("launch_tradingview_browser", source, path.name)
            self.assertNotIn("tradingview-browser", source, path.name)
            self.assertNotIn("TRADINGVIEW_CDP", source, path.name)

        api_source = pathlib.Path(ai_os_api_server.__file__).read_text(encoding="utf-8")
        self.assertIn('"tradingview_desktop": probe_tradingview_desktop()', api_source)
        self.assertIn("managed TradingView browser/CDP surface is retired", api_source)

        stop_source = (runtime_root / "scripts" / "stop_ai_office_live.sh").read_text(encoding="utf-8")
        self.assertNotIn("tradingview-browser", stop_source)
        self.assertNotIn("tradingview_browser.pid", stop_source)

    def test_desktop_plan_opens_every_chart_in_the_native_app(self) -> None:
        payload = {
            "actor": "Devarsh",
            "symbol": "NIFTY",
            "symbols": ["NSE:NIFTY", "NSE:INDIAVIX"],
            "compiled_plan": {
                "panes": [
                    {"url": "https://www.tradingview.com/chart/?symbol=NSE%3ANIFTY"},
                    {"url": "https://www.tradingview.com/chart/?symbol=NSE%3AINDIAVIX"},
                ]
            },
        }
        persisted = {"id": 121, "status": "done"}
        with (
            mock.patch.object(ai_os_api_server, "create_tradingview_task", return_value={"id": 121}),
            mock.patch.object(
                ai_os_api_server,
                "open_link_in_desktop",
                side_effect=[
                    {"status": "opened", "handoff": "clipboard_menu"},
                    {"status": "opened", "handoff": "clipboard_menu"},
                ],
            ) as desktop_open,
            mock.patch.object(ai_os_api_server, "run_psql_json_statement", return_value=[persisted]) as write_query,
            mock.patch.object(ai_os_api_server.time, "sleep"),
            mock.patch.object(ai_os_api_server, "audit_api_write"),
        ):
            result = ai_os_api_server.execute_tradingview_desktop_plan(payload)

        self.assertEqual(desktop_open.call_count, 2)
        self.assertEqual(result["execution_surface"], "native_desktop")
        self.assertFalse(result["broker_order_allowed"])
        self.assertIn("execution_surface", write_query.call_args.args[0])

    def test_template_execution_uses_native_desktop_plan(self) -> None:
        source = pathlib.Path(ai_os_api_server.__file__).read_text(encoding="utf-8")
        template_block = source.split("def execute_tradingview_template_action", 1)[1].split(
            "def resolve_tradingview_template_approval", 1
        )[0]

        self.assertIn("execute_tradingview_desktop_plan(merged_payload)", template_block)
        self.assertNotIn("execute_tradingview_chart_action(merged_payload)", template_block)

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

        self.assertIn('title="Desktop App Templates"', frontend)
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

    def test_charlie_routes_relative_strength_template_without_duplicate_open(self) -> None:
        with (
            mock.patch.object(
                ai_os_api_server,
                "execute_tradingview_template_action",
                return_value={"status": "approval_required", "template_key": "relative_strength_ratio_chart"},
            ) as template_action,
            mock.patch.object(ai_os_api_server, "open_tradingview_desktop_chart") as desktop_open,
        ):
            operations = ai_os_api_server.execute_charlie_safe_tools(
                "Build RELIANCE versus NIFTY relative strength chart in TradingView"
            )

        self.assertEqual(len(operations), 1)
        self.assertEqual(operations[0]["tool"], "execute_tradingview_template_action")
        payload = template_action.call_args.args[0]
        self.assertEqual(payload["template_key"], "relative_strength_ratio_chart")
        self.assertEqual(payload["symbol"], "RELIANCE")
        self.assertEqual(payload["parameters"]["benchmark"], "NIFTY")
        desktop_open.assert_not_called()

    def test_charlie_straddle_template_names_missing_contract_fields(self) -> None:
        with mock.patch.object(ai_os_api_server, "execute_tradingview_template_action") as template_action:
            operations = ai_os_api_server.execute_charlie_safe_tools(
                "Open NIFTY straddle four chart layout in TradingView"
            )

        self.assertEqual(operations[0]["status"], "needs_input")
        self.assertIn("expiry", operations[0]["detail"])
        self.assertIn("call_symbol", operations[0]["detail"])
        self.assertIn("put_symbol", operations[0]["detail"])
        template_action.assert_not_called()

    def test_charlie_fundamental_dashboard_uses_filing_cross_check(self) -> None:
        with mock.patch.object(
            ai_os_api_server,
            "execute_tradingview_template_action",
            return_value={"status": "approval_required", "template_key": "fundamental_ratio_dashboard"},
        ) as template_action:
            operations = ai_os_api_server.execute_charlie_safe_tools(
                "Build RELIANCE fundamental ratio dashboard in TradingView"
            )

        self.assertEqual(operations[0]["status"], "approval_required")
        payload = template_action.call_args.args[0]
        self.assertTrue(payload["parameters"]["filing_cross_check_required"])
        self.assertIn("RETURN_ON_INVESTED_CAPITAL", payload["parameters"]["fields"])


    def test_final_migration_retires_managed_browser_in_favour_of_native_desktop(self) -> None:
        runtime_root = pathlib.Path(__file__).resolve().parents[1]
        migration = (
            runtime_root
            / "postgres"
            / "init"
            / "181_tradingview_native_desktop_only_v1.sql"
        ).read_text(encoding="utf-8")

        self.assertIn("native_desktop", migration)
        self.assertIn("user_managed", migration)
        self.assertIn("managed_browser_allowed", migration)
        self.assertIn("authoritative_market_data", migration)
        self.assertIn("broker_order_allowed", migration)
        self.assertIn("status = ", migration)

if __name__ == "__main__":
    unittest.main()
