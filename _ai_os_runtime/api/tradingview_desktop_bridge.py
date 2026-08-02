#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


TRADINGVIEW_DESKTOP_APP = Path(
    os.environ.get("AI_OS_TRADINGVIEW_DESKTOP_APP", "/Applications/TradingView.app")
)
TRADINGVIEW_DESKTOP_BUNDLE_ID = "com.tradingview.tradingviewapp.desktop"


def probe_desktop() -> dict:
    installed = TRADINGVIEW_DESKTOP_APP.exists()
    running = False
    version = None
    automation_permission = False
    errors: list[str] = []

    if installed:
        try:
            process = subprocess.run(
                ["/usr/bin/pgrep", "-f", f"{TRADINGVIEW_DESKTOP_APP}/Contents/MacOS/TradingView"],
                text=True,
                capture_output=True,
                check=False,
                timeout=3,
            )
            running = process.returncode == 0 and bool(process.stdout.strip())
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(f"process_probe:{type(exc).__name__}")
        try:
            version_result = subprocess.run(
                [
                    "/usr/libexec/PlistBuddy",
                    "-c",
                    "Print :CFBundleShortVersionString",
                    str(TRADINGVIEW_DESKTOP_APP / "Contents" / "Info.plist"),
                ],
                text=True,
                capture_output=True,
                check=False,
                timeout=3,
            )
            version = version_result.stdout.strip() or None
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(f"version_probe:{type(exc).__name__}")

    if sys.platform == "darwin":
        try:
            permission_result = subprocess.run(
                [
                    "/usr/bin/osascript",
                    "-e",
                    'tell application "System Events" to get UI elements enabled',
                ],
                text=True,
                capture_output=True,
                check=False,
                timeout=3,
            )
            automation_permission = permission_result.stdout.strip().lower() == "true"
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(f"accessibility_probe:{type(exc).__name__}")

    return {
        "installed": installed,
        "running": running,
        "version": version,
        "bundle_id": TRADINGVIEW_DESKTOP_BUNDLE_ID,
        "automation_permission": automation_permission,
        "session_state": "user_managed",
        "interaction_mode": (
            "clipboard_menu"
            if installed and sys.platform == "darwin"
            else "direct_url"
            if installed
            else "unavailable"
        ),
        "authoritative_market_data": False,
        "broker_execution_allowed": False,
        "errors": errors,
        "next_action": (
            "Install TradingView Desktop on this node."
            if not installed
            else "Grant Accessibility access to the AI OS service for automatic TradingView clipboard-menu handoff."
            if sys.platform == "darwin" and not automation_permission
            else None
        ),
    }


def open_link_in_desktop(target_url: str) -> dict:
    if not target_url.startswith("https://www.tradingview.com/"):
        raise ValueError("target_url must be an https://www.tradingview.com/ link")
    status = probe_desktop()
    if not status["installed"]:
        return {"status": "app_missing", "desktop": status, "target_url": target_url}

    if sys.platform == "darwin":
        subprocess.run(
            ["/usr/bin/pbcopy"],
            input=target_url,
            text=True,
            capture_output=True,
            check=True,
            timeout=5,
        )
        if not status["automation_permission"]:
            launch = subprocess.Popen(
                ["/usr/bin/open", "-g", "-a", "TradingView"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return {
                "status": "permission_required",
                "handoff": "clipboard_prepared",
                "clipboard_prepared": True,
                "launch_pid": launch.pid,
                "desktop": status,
                "target_url": target_url,
                "next_action": "In TradingView, choose TradingView > Open link from clipboard, or grant Accessibility permission for automatic handoff.",
            }

        script = f'''set openedLink to false
tell application id "{TRADINGVIEW_DESKTOP_BUNDLE_ID}" to activate
delay 0.5
tell application "System Events"
  tell process "TradingView"
    repeat with topMenu in every menu bar item of menu bar 1
      try
        if exists menu item "Open link from clipboard" of menu 1 of topMenu then
          click menu item "Open link from clipboard" of menu 1 of topMenu
          set openedLink to true
          exit repeat
        end if
      end try
    end repeat
  end tell
end tell
if openedLink is false then error "TradingView Open link from clipboard menu item was not found"
'''
        completed = subprocess.run(
            ["/usr/bin/osascript", "-e", script],
            text=True,
            capture_output=True,
            check=False,
            timeout=15,
        )
        if completed.returncode != 0:
            error = (completed.stderr or completed.stdout or "TradingView Desktop automation failed").strip()
            raise RuntimeError(error)
        return {
            "status": "opened",
            "handoff": "clipboard_menu",
            "clipboard_prepared": True,
            "desktop": probe_desktop(),
            "target_url": target_url,
        }

    try:
        direct = subprocess.Popen(
            ["/usr/bin/open", "-g", "-a", "TradingView", target_url],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        direct_error = f"{type(exc).__name__}: {exc}"
    else:
        return {
            "status": "handoff_requested",
            "handoff": "direct_url_async",
            "launch_pid": direct.pid,
            "desktop": status,
            "target_url": target_url,
        }

    return {
        "status": "permission_required",
        "handoff": "direct_url_failed",
        "error": direct_error,
        "desktop": status,
        "target_url": target_url,
    }
