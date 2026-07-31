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

    def test_open_link_reports_permission_gate_without_touching_ui(self) -> None:
        gated = {
            "installed": True,
            "running": True,
            "automation_permission": False,
        }
        with (
            mock.patch.object(tradingview_desktop_bridge, "probe_desktop", return_value=gated),
            mock.patch.object(tradingview_desktop_bridge.subprocess, "run") as run,
        ):
            result = tradingview_desktop_bridge.open_link_in_desktop(
                "https://www.tradingview.com/chart/?symbol=NSE%3ARELIANCE"
            )

        self.assertEqual(result["status"], "permission_required")
        run.assert_not_called()

    def test_open_link_uses_clipboard_and_accessibility_menu(self) -> None:
        ready = {
            "installed": True,
            "running": True,
            "automation_permission": True,
        }
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with (
            mock.patch.object(tradingview_desktop_bridge, "probe_desktop", return_value=ready),
            mock.patch.object(tradingview_desktop_bridge.subprocess, "run", return_value=completed) as run,
        ):
            result = tradingview_desktop_bridge.open_link_in_desktop(
                "https://www.tradingview.com/chart/?symbol=NSE%3ARELIANCE"
            )

        self.assertEqual(result["status"], "opened")
        commands = [call.args[0][0] for call in run.call_args_list]
        self.assertEqual(commands, ["/usr/bin/pbcopy", "/usr/bin/osascript"])

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
