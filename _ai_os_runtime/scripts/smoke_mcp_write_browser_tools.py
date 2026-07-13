#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


RUNTIME_ROOT = Path(os.environ.get("AI_OS_RUNTIME_ROOT") or Path(__file__).absolute().parents[1])
VAULT_ROOT = Path(os.environ.get("AI_OS_VAULT_ROOT") or RUNTIME_ROOT.parent)
SERVER_PATH = RUNTIME_ROOT / "mcp_server" / "ai_os_mcp_server.py"
MARKER = "CODEX-MCP-SMOKE"


def parse_tool_content(response: dict) -> object:
    result = response.get("result") or {}
    content = result.get("content") or []
    if not content:
        return None
    return json.loads(content[0]["text"])


def run_sql_json(sql: str) -> dict:
    command = [
        "docker", "exec", "-i", "ai_os_postgres", "psql",
        "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os",
    ]
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return json.loads(completed.stdout.strip() or "{}")


def cleanup_smoke_rows() -> dict:
    sql = f"""
    WITH deleted_browser_runs AS (
        DELETE FROM ops.browser_runs
        WHERE target_url ILIKE '%{MARKER}%'
           OR notes ILIKE '%{MARKER}%'
           OR metadata::text ILIKE '%{MARKER}%'
        RETURNING id
    ),
    deleted_artifacts AS (
        DELETE FROM core.raw_artifacts
        WHERE title ILIKE '%{MARKER}%'
           OR source_url ILIKE '%{MARKER}%'
           OR local_path ILIKE '%{MARKER}%'
           OR metadata::text ILIKE '%{MARKER}%'
        RETURNING id
    ),
    deleted_ideas AS (
        DELETE FROM research.ideas
        WHERE title ILIKE '%{MARKER}%'
           OR source_ref ILIKE '%{MARKER}%'
           OR evidence::text ILIKE '%{MARKER}%'
        RETURNING id
    ),
    deleted_approvals AS (
        DELETE FROM agent.approvals
        WHERE title ILIKE '%{MARKER}%'
           OR requested_action::text ILIKE '%{MARKER}%'
        RETURNING id
    ),
    deleted_inbox AS (
        DELETE FROM agent.inbox_items
        WHERE title ILIKE '%{MARKER}%'
           OR evidence::text ILIKE '%{MARKER}%'
        RETURNING id
    ),
    deleted_tasks AS (
        DELETE FROM agent.tasks
        WHERE title ILIKE '%{MARKER}%'
           OR objective ILIKE '%{MARKER}%'
           OR source_ref ILIKE '%{MARKER}%'
           OR evidence::text ILIKE '%{MARKER}%'
        RETURNING id
    ),
    deleted_audit AS (
        DELETE FROM agent.mcp_audit_log
        WHERE request_payload::text ILIKE '%{MARKER}%'
           OR result_payload::text ILIKE '%{MARKER}%'
           OR target_id ILIKE '%{MARKER}%'
        RETURNING id
    )
    SELECT json_build_object(
        'browser_runs', (SELECT count(*) FROM deleted_browser_runs),
        'artifacts', (SELECT count(*) FROM deleted_artifacts),
        'ideas', (SELECT count(*) FROM deleted_ideas),
        'approvals', (SELECT count(*) FROM deleted_approvals),
        'inbox', (SELECT count(*) FROM deleted_inbox),
        'tasks', (SELECT count(*) FROM deleted_tasks),
        'audit', (SELECT count(*) FROM deleted_audit)
    )::text;
    """
    note_deletes = 0
    for note in (VAULT_ROOT / "ai memory" / "00 AI OS" / "Agent Outputs").glob("*codex-mcp-smoke*.md"):
        note.unlink()
        note_deletes += 1
    result = run_sql_json(sql)
    result["notes"] = note_deletes
    subprocess.run([str(RUNTIME_ROOT / "scripts" / "index_obsidian_vault.py")], cwd=VAULT_ROOT, text=True, capture_output=True, check=False)
    return result


def main() -> int:
    cleanup_before = cleanup_smoke_rows()
    process = subprocess.Popen(
        [str(SERVER_PATH)],
        cwd=RUNTIME_ROOT.parent,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    request_id = 0

    def call(method: str, params: dict | None = None) -> dict:
        nonlocal request_id
        request_id += 1
        message = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        process.stdin.write(json.dumps(message) + "\n")
        process.stdin.flush()
        line = process.stdout.readline()
        if not line:
            stderr = process.stderr.read() if process.stderr else ""
            raise RuntimeError(f"MCP server exited without response. stderr={stderr}")
        response = json.loads(line)
        if "error" in response:
            raise RuntimeError(response["error"])
        return response

    try:
        call("initialize", {"protocolVersion": "2024-11-05"})
        tools = call("tools/list")["result"]["tools"]
        tool_names = {tool["name"] for tool in tools}
        required = {
            "ai_os_mcp_capabilities",
            "ai_os_mcp_audit_log",
            "ai_os_create_task",
            "ai_os_update_task_status",
            "ai_os_list_inbox",
            "ai_os_update_inbox_status",
            "ai_os_create_approval",
            "ai_os_decide_approval",
            "ai_os_create_research_idea",
            "ai_os_record_raw_artifact",
            "ai_os_write_obsidian_note",
            "ai_os_start_browser_run",
            "ai_os_complete_browser_run",
            "ai_os_browser_runs",
        }
        missing = sorted(required - tool_names)
        if missing:
            raise RuntimeError(f"Missing MCP tools: {missing}")

        capabilities = parse_tool_content(call("tools/call", {"name": "ai_os_mcp_capabilities", "arguments": {}}))
        task = parse_tool_content(
            call(
                "tools/call",
                {
                    "name": "ai_os_create_task",
                    "arguments": {
                        "title": f"{MARKER} task",
                        "objective": f"{MARKER} verify task write path",
                        "owner_agent": "Jarvis",
                        "priority": "medium",
                        "source_ref": MARKER,
                        "evidence": [{"marker": MARKER}],
                        "target_workspace": "system",
                    },
                },
            )
        )
        approval = parse_tool_content(
            call(
                "tools/call",
                {
                    "name": "ai_os_create_approval",
                    "arguments": {
                        "task_id": task["id"],
                        "title": f"{MARKER} approval",
                        "approval_type": "system_change",
                        "requested_action": {"marker": MARKER},
                        "rationale": "Smoke test approval.",
                    },
                },
            )
        )
        decision = parse_tool_content(
            call(
                "tools/call",
                {
                    "name": "ai_os_decide_approval",
                    "arguments": {
                        "approval_id": approval["id"],
                        "decision": "approved",
                        "decided_by": "Codex smoke",
                        "rationale": MARKER,
                    },
                },
            )
        )
        idea = parse_tool_content(
            call(
                "tools/call",
                {
                    "name": "ai_os_create_research_idea",
                    "arguments": {
                        "title": f"{MARKER} research idea",
                        "idea_type": "smoke_test",
                        "symbols": ["SMOKE"],
                        "source_ref": MARKER,
                        "thesis": "Smoke test thesis.",
                        "opportunity_score": 1,
                        "risk_score": 1,
                        "evidence": [{"marker": MARKER}],
                    },
                },
            )
        )
        artifact = parse_tool_content(
            call(
                "tools/call",
                {
                    "name": "ai_os_record_raw_artifact",
                    "arguments": {
                        "title": f"{MARKER} artifact",
                        "artifact_type": "smoke_artifact",
                        "source_url": f"https://example.com/?marker={MARKER}",
                        "content_text": f"{MARKER} artifact body",
                        "metadata": {"marker": MARKER},
                    },
                },
            )
        )
        browser_run = parse_tool_content(
            call(
                "tools/call",
                {
                    "name": "ai_os_start_browser_run",
                    "arguments": {
                        "task_id": task["id"],
                        "target_url": f"https://example.com/?marker={MARKER}",
                        "status": "running",
                        "notes": MARKER,
                        "metadata": {"marker": MARKER},
                    },
                },
            )
        )
        completed_browser = parse_tool_content(
            call(
                "tools/call",
                {
                    "name": "ai_os_complete_browser_run",
                    "arguments": {
                        "browser_run_id": browser_run["id"],
                        "page_title": f"{MARKER} page",
                        "extracted_text_preview": f"{MARKER} preview",
                        "extracted_artifact_id": artifact["id"],
                        "notes": MARKER,
                        "metadata": {"marker": MARKER},
                    },
                },
            )
        )
        note = parse_tool_content(
            call(
                "tools/call",
                {
                    "name": "ai_os_write_obsidian_note",
                    "arguments": {
                        "title": f"{MARKER} note",
                        "body": f"{MARKER} note body.",
                        "folder": "agent_outputs",
                        "tags": ["ai-os", "mcp-smoke"],
                        "source_refs": [MARKER],
                    },
                },
            )
        )
        task_done = parse_tool_content(
            call(
                "tools/call",
                {
                    "name": "ai_os_update_task_status",
                    "arguments": {
                        "task_id": task["id"],
                        "status": "done",
                        "output_note_path": note["note_path"],
                        "evidence": [{"marker": MARKER, "artifact_id": artifact["id"]}],
                    },
                },
            )
        )
        inbox_done = parse_tool_content(
            call(
                "tools/call",
                {
                    "name": "ai_os_update_inbox_status",
                    "arguments": {
                        "inbox_id": task["inbox_item_id"],
                        "status": "done",
                        "recommended_action": MARKER,
                    },
                },
            )
        )
        browser_history = parse_tool_content(call("tools/call", {"name": "ai_os_browser_runs", "arguments": {"limit": 5}}))
        audit = parse_tool_content(call("tools/call", {"name": "ai_os_mcp_audit_log", "arguments": {"limit": 20}}))
    finally:
        try:
            process.stdin.close()
        except Exception:
            pass
        process.terminate()
        process.wait(timeout=5)
        cleanup_after = cleanup_smoke_rows()

    print(
        json.dumps(
            {
                "tool_count": len(tool_names),
                "capability_mcp_tools": len((capabilities or {}).get("mcp_tools", [])),
                "capability_internal_tools": len((capabilities or {}).get("internal_capabilities", [])),
                "task_id": task["id"],
                "approval_status": decision["status"],
                "idea_id": idea["id"],
                "artifact_id": artifact["id"],
                "browser_run_status": completed_browser["status"],
                "note_path": note["note_path"],
                "task_status": task_done["status"],
                "inbox_status": inbox_done["status"],
                "browser_history_rows": len(browser_history or []),
                "audit_rows": len(audit or []),
                "cleanup_before": cleanup_before,
                "cleanup_after": cleanup_after,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"{type(exc).__name__}: {exc}\n")
        raise SystemExit(1)
