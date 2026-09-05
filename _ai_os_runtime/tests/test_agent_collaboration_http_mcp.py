"""Authenticated HTTP/MCP compatibility for durable Agent OS collaboration."""
from __future__ import annotations

from contextlib import contextmanager
from http.server import ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import sys
import threading
import urllib.error
import urllib.request
from unittest.mock import patch
from uuid import uuid4

import pytest

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME_ROOT / "api"))
sys.path.insert(0, str(RUNTIME_ROOT / "scripts"))
from test_agent_runtime_postgres import database
from _ai_os_runtime.api import ai_os_api_server as api_server
from _ai_os_runtime.api.agent_os_policy import Principal
from _ai_os_runtime.api.agent_runtime_api import RuntimeAPI


MCP_PATH = Path(__file__).parents[1] / "mcp_server" / "ai_os_mcp_server.py"
MCP_SPEC = importlib.util.spec_from_file_location("ai_os_mcp_server_agent_os_contract", MCP_PATH)
assert MCP_SPEC and MCP_SPEC.loader
MCP = importlib.util.module_from_spec(MCP_SPEC)
MCP_SPEC.loader.exec_module(MCP)


@contextmanager
def live_api(monkeypatch, execute, principal: Principal):
    monkeypatch.setattr(api_server, "RUNTIME_API", RuntimeAPI(execute))
    monkeypatch.setattr(api_server, "AGENT_OS_PRINCIPAL", principal)
    monkeypatch.setattr(api_server, "OPERATOR_TOKEN", "synthetic-agent-os-operator")
    monkeypatch.setattr(api_server, "ALLOW_TOKENLESS_LOOPBACK", False)
    http = ThreadingHTTPServer(("127.0.0.1", 0), api_server.AiOsApiHandler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{http.server_port}"
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=2)


def request(base: str, path: str, payload=None, *, authorized=True):
    headers = {"Authorization": "Bearer synthetic-agent-os-operator"} if authorized else {}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
    return urllib.request.urlopen(urllib.request.Request(base + path, data=data, headers=headers), timeout=5)


def test_authenticated_conversation_handoff_and_charlie_routes(database, monkeypatch):
    execute, _ = database
    suffix = uuid4().hex
    sender_name = f"HTTP Sender {suffix}"
    recipient_name = f"HTTP Recipient {suffix}"
    sender = int(execute(
        f"INSERT INTO agent.profiles(agent_name,department,role_scope) VALUES('{sender_name}','research','Synthetic HTTP only') RETURNING id"
    ))
    recipient = int(execute(
        f"INSERT INTO agent.profiles(agent_name,department,role_scope) VALUES('{recipient_name}','research','Synthetic HTTP only') RETURNING id"
    ))
    execute(f"UPDATE agent.agent_workspaces SET allowed_task_classes=ARRAY['general','handoff'] WHERE agent_id IN ({sender},{recipient})")
    parent_task = int(execute(
        f"INSERT INTO agent.tasks(title,objective,owner_agent,agent_id,runtime_protocol,runtime_state,task_class,recovery_policy) "
        f"VALUES('HTTP synthetic','No private content','{sender_name}',{sender},'lease_v1','PLANNING','general','idempotent_read') "
        "RETURNING id"
    ))
    thread_key = f"http:test:{suffix}"
    principal = Principal(user_id="http_operator")

    with live_api(monkeypatch, execute, principal) as base:
        with pytest.raises(urllib.error.HTTPError) as failure:
            request(base, "/api/v1/agent-os/overview", authorized=False)
        assert failure.value.code == 403

        created = json.load(request(base, "/api/v1/threads", {
            "thread_key": thread_key, "room_type": "direct", "title": "Synthetic HTTP thread",
        }))
        assert created["created"] is True

        message_payload = {
            "thread_key": thread_key,
            "request_key": f"message:{suffix}",
            "subject": "Check stored evidence",
            "body": "Read the bounded stored source packet.",
            "related_task_id": parent_task,
        }
        sent = json.load(request(base, f"/api/v1/agents/{recipient}/message", message_payload))
        assert sent["created"] is True
        assert sent["delivery_is_completion"] is False
        assert sent["message"]["sender_user_id"] == "http_operator"
        assert sent["message"]["to_agent_id"] == recipient
        duplicate = json.load(request(base, f"/api/v1/agents/{recipient}/message", message_payload))
        assert duplicate["created"] is False

        messages = json.load(request(base, f"/api/v1/threads/{thread_key}?after_id=0&limit=10"))
        assert messages["messages"][0]["id"] == sent["message"]["id"]
        acknowledged = json.load(request(base, f"/api/v1/messages/{sent['message']['id']}/ack", {}))
        assert acknowledged["receipt"]["acknowledged_at"]

        detail = json.load(request(base, f"/api/v1/agents/{recipient}"))
        assert detail["agent"]["id"] == recipient
        assert "objective" not in json.dumps(detail)
        overview = json.load(request(base, "/api/v1/agent-os/overview"))
        assert overview["broker_write_allowed"] is False
        assert "No private content" not in json.dumps(overview)

        handoff_payload = {
            "request_key": f"handoff:{suffix}", "thread_key": thread_key,
            "from_agent_id": sender, "to_agent_id": recipient, "parent_task_id": parent_task,
            "question": "Return a cited bounded assessment.",
            "evidence_refs": [{"table": "research.corporate_filings", "id": 77}],
        }
        handoff = json.load(request(base, "/api/v1/handoffs", handoff_payload))
        assert handoff["state"] == "REQUESTED"
        replay = json.load(request(base, "/api/v1/handoffs", handoff_payload))
        assert replay["duplicate"] is True
        acknowledged_handoff = json.load(request(
            base, f"/api/v1/handoffs/{handoff['handoff_id']}/acknowledge", {"actor_agent_id": recipient}
        ))
        assert acknowledged_handoff["state"] == "ACKNOWLEDGED"

        charlie = json.load(request(base, "/api/v1/charlie/commands", {
            "request_key": f"charlie:{suffix}",
            "command": "Charlie, show every live agent and what each is doing.",
            "context": {},
        }))
        assert charlie["current_state"] == "OBSERVED"
        assert charlie["broker_write_allowed"] is False

        with pytest.raises(urllib.error.HTTPError) as failure:
            request(base, f"/api/v1/agents/{recipient}/message", {**message_payload, "from_agent_id": sender})
        assert failure.value.code == 403
        with pytest.raises(urllib.error.HTTPError) as failure:
            request(base, f"/api/v1/agents/{recipient}/message", {
                **message_payload, "request_key": f"secret:{suffix}", "body": "api_key=not-accepted"
            })
        assert failure.value.code == 400


def test_server_principal_enforces_client_isolation(database, monkeypatch):
    execute, _ = database
    suffix = uuid4().hex
    thread_key = f"client:test:{suffix}"
    with live_api(monkeypatch, execute, Principal(user_id="client_operator", clients=(91,))) as base:
        created = json.load(request(base, "/api/v1/threads", {
            "thread_key": thread_key, "room_type": "client", "title": "Synthetic client room",
            "client_id": 91, "data_class": "client_private",
        }))
        assert created["thread"]["client_id"] == 91
        with pytest.raises(urllib.error.HTTPError) as failure:
            request(base, "/api/v1/threads", {
                "thread_key": f"other:{suffix}", "room_type": "client", "title": "Denied scope",
                "client_id": 92, "data_class": "client_private",
            })
        assert failure.value.code == 403
        monkeypatch.setattr(api_server, "AGENT_OS_PRINCIPAL", Principal(user_id="shared_operator"))
        with pytest.raises(urllib.error.HTTPError) as failure:
            request(base, f"/api/v1/threads/{thread_key}")
        assert failure.value.code == 404


def test_missing_additive_schema_returns_truthful_unavailable(monkeypatch):
    with live_api(monkeypatch, lambda _sql: "false", Principal(user_id="http_operator")) as base:
        with pytest.raises(urllib.error.HTTPError) as failure:
            request(base, "/api/v1/agent-os/overview")
        assert failure.value.code == 503
        body = json.loads(failure.value.read())
        assert body["error"] == "agent_os_request_rejected"
        assert "no action was taken" in body["message"]


def test_mcp_agent_os_tools_are_bounded_and_route_only_to_api():
    names = {
        "ai_os_agent_os_overview", "ai_os_inspect_agent", "ai_os_list_agent_threads",
        "ai_os_create_agent_thread", "ai_os_send_agent_message", "ai_os_ack_agent_message",
        "ai_os_create_agent_handoff", "ai_os_advance_agent_handoff", "ai_os_charlie_command",
    }
    assert names <= MCP.TOOLS.keys()
    for name in names:
        schema = MCP.TOOLS[name]["inputSchema"]
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert "broker" not in schema.get("properties", {})
        assert "order" not in schema.get("properties", {})

    with pytest.raises(ValueError, match="confirmation"):
        MCP.TOOLS["ai_os_send_agent_message"]["handler"]({
            "agent_id": 7, "thread_key": "thread:test:1", "request_key": "message:test:1", "body": "hello"
        })
    with patch.object(MCP, "post_api_json", return_value={"created": True}) as post:
        result = MCP.TOOLS["ai_os_send_agent_message"]["handler"]({
            "agent_id": 7, "thread_key": "thread:test:1", "request_key": "message:test:1",
            "body": "hello", "operator_confirmed": True,
        })
    assert json.loads(result["content"][0]["text"]) == {"created": True}
    assert post.call_args.args[0] == "/api/v1/agents/7/message"
    assert post.call_args.args[1] == {
        "thread_key": "thread:test:1", "request_key": "message:test:1", "body": "hello"
    }

    with patch.object(MCP, "post_api_json", return_value={"current_state": "QUEUED"}) as post:
        MCP.TOOLS["ai_os_charlie_command"]["handler"]({
            "request_key": "charlie:test:1", "command": "Charlie, inspect the stack.",
            "context": {}, "operator_confirmed": True,
        })
    assert post.call_args.args[0] == "/api/v1/charlie/commands"
    assert "operator_confirmed" not in post.call_args.args[1]


def test_launchd_payload_copies_required_agent_os_modules():
    source = (Path(__file__).parents[1] / "scripts" / "start_ai_office_live.sh").read_text()
    for name in ("agent_os_policy.py", "agent_collaboration.py", "agent_charlie.py"):
        assert f'api/{name}" "${{AIOS_SERVICE_DIR}}/api/{name}' in source
