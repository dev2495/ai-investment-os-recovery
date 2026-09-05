"""Isolated Model Fabric behavior tests; no paid provider or production DB."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import threading
from uuid import uuid4

import pytest

from _ai_os_runtime.api.agent_model_fabric import (
    FabricError, ModelFabric, ModelRequest, ProviderAdapter, parse_stream,
)


# Reuse the exact isolated Postgres safety boundary without changing it.
from _ai_os_runtime.tests.test_agent_runtime_postgres import database  # noqa: F401
SQL_ROOT = Path(__file__).resolve().parents[1] / "postgres" / "init"


class ProviderHandler(BaseHTTPRequestHandler):
    models = ["local-model-a", "local-model-b"]
    calls = []

    def log_message(self, *_):
        pass

    def _send(self, payload):
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/tags":
            self._send({
                "models": [{"name": name, "digest": "synthetic-r1"}
                           for name in self.models]
            })
            return
        assert self.path == "/v1/models"
        self._send({"data": [{"id": name, "revision": "synthetic-r1"}
                             for name in self.models]})

    def do_POST(self):
        if self.path == "/api/chat":
            size = int(self.headers["Content-Length"])
            payload = json.loads(self.rfile.read(size))
            self.calls.append(payload)
            content = "bounded synthetic result"
            if payload.get("format"):
                content = json.dumps({
                    "answer": 17, "source": "public_packet_A",
                    "missing": ["latest_margin"], "injected_ignored": True,
                })
            self._send({
                "model": payload["model"],
                "message": {"content": content},
                "done": True, "done_reason": "stop",
                "prompt_eval_count": 21, "eval_count": 9,
            })
            return
        assert self.path == "/v1/chat/completions"
        size = int(self.headers["Content-Length"])
        payload = json.loads(self.rfile.read(size))
        self.calls.append(payload)
        if "response_format" in payload:
            content = json.dumps({
                "answer": 17, "source": "public_packet_A",
                "missing": ["latest_margin"], "injected_ignored": True,
            })
        else:
            content = "bounded synthetic result"
        self._send({
            "model": payload["model"],
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 21, "completion_tokens": 9, "cost": 0},
        })


@pytest.fixture(scope="module")
def provider_server():
    ProviderHandler.calls.clear()
    server = ThreadingHTTPServer(("127.0.0.1", 0), ProviderHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/v1", ProviderHandler.calls
    server.shutdown()
    thread.join(timeout=3)
    server.server_close()


def _ddl(name, table):
    source = (SQL_ROOT / name).read_text()
    match = re.search(
        rf"CREATE TABLE IF NOT EXISTS agent\.{table} \([\s\S]*?\n\);", source
    )
    assert match, (name, table)
    return match.group()


@pytest.fixture(scope="module")
def fabric_db(database):
    """Layer checked-in canonical model DDL onto the existing isolated fixture."""
    execute, dsn = database
    for name, table in (
        ("025_chat_operating_layer.sql", "chat_turns"),
        ("030_agent_hierarchy_comms_models_and_external_skills.sql", "model_catalog"),
        ("030_agent_hierarchy_comms_models_and_external_skills.sql",
         "agent_model_assignments"),
        ("046_model_source_onboarding_control.sql", "model_endpoints"),
        ("084_model_cost_ledger_v1.sql", "model_cost_rates"),
        ("084_model_cost_ledger_v1.sql", "model_usage_events"),
        ("084_model_cost_ledger_v1.sql", "model_cost_caps"),
        ("126_model_call_control_plane_v1.sql", "model_privacy_policies"),
        ("126_model_call_control_plane_v1.sql", "model_call_decisions"),
    ):
        execute(_ddl(name, table))
    execute("""
        INSERT INTO agent.model_privacy_policies(
          privacy_class,local_model_allowed,cloud_model_allowed,
          cloud_requires_approval,cache_allowed,redaction_required_for_cloud,
          max_context_chars,retention_days,policy_statement)
        VALUES
          ('public',true,true,true,true,false,24000,30,'synthetic public policy'),
          ('internal',true,true,true,true,true,18000,14,'synthetic internal policy'),
          ('client_private',true,false,true,false,true,12000,0,'synthetic private policy'),
          ('restricted',true,false,true,false,true,8000,0,'synthetic restricted policy')
    """)
    migration = (SQL_ROOT / "259_agent_model_fabric_v1.sql").read_text()
    execute(migration)
    execute(migration)
    yield execute, dsn


@pytest.fixture
def fabric_environment(fabric_db, provider_server):
    execute, _ = fabric_db
    base_url, calls = provider_server
    suffix = uuid4().hex[:10]
    agent_name = "Fabric Analyst " + suffix
    agent_id = int(execute(f"""
        INSERT INTO agent.profiles(
          agent_name,department,role_scope,status)
        VALUES ('{agent_name}','research','research.forensics','active')
        RETURNING id
    """))
    execute(f"""
        INSERT INTO agent.agent_model_assignments(
          agent_name,context_policy,cost_policy,max_autonomous_cost_tier)
        VALUES ('{agent_name}','public synthetic only','local_first','local')
    """)
    execute(f"""
        INSERT INTO agent.model_cost_caps(
          agent_name,daily_cap_usd,monthly_cap_usd,max_cost_tier,
          cloud_requires_approval,autonomous_cloud_allowed,hard_stop_on_breach)
        VALUES ('{agent_name}',0,0,'local',true,false,true)
    """)
    execute(f"""
        UPDATE agent.agent_workspaces SET
          allowed_task_classes=ARRAY['filing_analysis'],
          allowed_scopes=ARRAY['internal'],
          allowed_data_classes=ARRAY['public','internal','client_private']
        WHERE agent_id={agent_id}
    """)
    task_id = int(execute(f"""
        INSERT INTO agent.tasks(title,objective,owner_agent,status,task_class,
          runtime_protocol,runtime_scope,data_class,recovery_policy)
        VALUES ('Synthetic filing analysis','Synthetic adapter test','{agent_name}',
          'in_progress','filing_analysis','lease_v1','internal','internal','idempotent_read')
        RETURNING id
    """))
    routes = []
    for index, model in enumerate(("local-model-a", "local-model-b"), 1):
        route = "fabric_local_" + suffix + "_" + str(index)
        endpoint = route + "_endpoint"
        execute(f"""
          INSERT INTO agent.model_routes(
            route_name,task_class,default_provider,default_model,max_cost_tier,enabled)
          VALUES ('{route}','filing_analysis','local_openai','{model}','local',true);
          INSERT INTO agent.model_endpoints(
            endpoint_key,endpoint_name,provider,model_name,route_name,endpoint_type,
            base_url,status,cost_tier,capabilities,requires_api_key,health_status,config)
          VALUES ('{endpoint}','{endpoint}','local_openai','{model}','{route}','local',
            '{base_url}','active','local',ARRAY['structured_output'],false,'healthy',
            '{{"runtime_version":"synthetic-r1"}}'::jsonb)
        """)
        routes.append(route)
    fabric = ModelFabric(execute)
    return execute, fabric, calls, agent_name, agent_id, task_id, routes


def _binding(fabric, agent_id, route, fallbacks=None, binding_key=None):
    key_name = binding_key or "research_forensic_" + uuid4().hex[:12]
    agent_key = fabric.rows(
        f"SELECT agent_key FROM agent.profiles WHERE id={agent_id}"
    )[0]["agent_key"]
    return fabric.propose({
        "binding_key": key_name, "selector_kind": "agent",
        "selector_value": agent_key, "task_class": "filing_analysis",
        "primary_route": route, "fallback_routes": fallbacks or [],
        "fallback_policy": "explicit_degraded" if fallbacks else "fail_closed",
        "reasoning_profile": "none", "context_budget": 2048,
        "max_output_tokens": 160, "temperature": 0.1,
        "privacy_classes": ["public", "internal", "client_private"],
    }, "Synthetic Operator")


def _request(agent_id, task_id, request_id=None, **overrides):
    payload = {
        "request_id": request_id or str(uuid4()),
        "agent_id": agent_id, "task_id": task_id,
        "task_class": "filing_analysis",
        "messages": [{"role": "user", "content": "Return bounded synthetic result."}],
        "reasoning_profile": "none", "context_budget": 2048,
        "max_output_tokens": 160, "temperature": 0.1,
        "privacy_class": "internal", "contains_client_data": False,
        "public_only": False, "cost_ceiling": 0,
    }
    payload.update(overrides)
    return payload


def test_local_route_qualification_switch_disable_and_idempotency(fabric_environment):
    execute, fabric, calls, _, agent_id, task_id, routes = fabric_environment
    qualifications = [
        fabric.qualify(route, "filing_analysis", "Synthetic Reviewer")
        for route in routes
    ]
    assert all(item["state"] == "passed" for item in qualifications)
    first = _binding(fabric, agent_id, routes[0])
    promoted = fabric.promote(first["id"], "Synthetic Operator")
    assert promoted["agents_assigned"] == 1
    stable_id = str(uuid4())
    before = len(calls)
    result = fabric.execute(_request(agent_id, task_id, stable_id))
    assert result["model"] == "local-model-a"
    assert result["status"] == "completed"
    replay = fabric.execute(_request(agent_id, task_id, stable_id))
    assert replay["idempotent_replay"] is True
    assert len(calls) == before + 1

    second = _binding(
        fabric, agent_id, routes[1], binding_key=first["binding_key"])
    fabric.promote(second["id"], "Synthetic Operator")
    switched = fabric.execute(_request(agent_id, task_id))
    assert switched["model"] == "local-model-b"
    fabric.disable(second["binding_key"], "Synthetic Operator")
    with pytest.raises(FabricError, match="one_active_qualified_binding_required"):
        fabric.execute(_request(agent_id, task_id))
    assert fabric.rollback(second["binding_key"], first["id"], "Synthetic Operator")[
        "version_id"
    ] == first["id"]
    assert fabric.execute(_request(agent_id, task_id))["model"] == "local-model-a"
    assert execute("SELECT count(*) FROM agent.model_usage_events") != "0"


def test_explicit_fallback_never_uses_global_default(fabric_environment):
    execute, fabric, _, _, agent_id, task_id, routes = fabric_environment
    for route in routes:
        fabric.qualify(route, "filing_analysis", "Synthetic Reviewer")
    version = _binding(fabric, agent_id, routes[0], [routes[1]])
    fabric.promote(version["id"], "Synthetic Operator")
    execute(f"""
        UPDATE agent.model_endpoints SET status='disabled'
        WHERE route_name='{routes[0]}'
    """)
    result = fabric.execute(_request(agent_id, task_id))
    assert result["route_name"] == routes[1]
    assert result["degraded"] is True
    attempted = fabric.rows("""
      SELECT route_name FROM agent.model_fabric_attempts ORDER BY id DESC LIMIT 1
    """)
    assert attempted[0]["route_name"] == routes[1]


def test_private_cloud_and_unapproved_paid_route_fail_closed(fabric_environment):
    execute, fabric, _, agent_name, agent_id, task_id, _ = fabric_environment
    suffix = uuid4().hex[:10]
    route = "fabric_cloud_" + suffix
    execute(f"""
      INSERT INTO agent.model_routes(
        route_name,task_class,default_provider,default_model,max_cost_tier,enabled)
      VALUES ('{route}','filing_analysis','openrouter','synthetic/cloud','cloud_low',true);
      INSERT INTO agent.model_endpoints(
        endpoint_key,endpoint_name,provider,model_name,route_name,endpoint_type,
        base_url,status,cost_tier,capabilities,requires_api_key,secret_ref,
        health_status,config)
      VALUES ('{route}_endpoint','{route}','openrouter','synthetic/cloud','{route}',
        'cloud','https://openrouter.ai/api/v1','active','cloud_low',
        ARRAY['structured_output'],true,'AI_OS_OPENROUTER_API_KEY','healthy',
        '{{"reasoning_map":{{"none":"none"}}}}'::jsonb);
      INSERT INTO agent.model_route_qualifications(
        route_name,task_class,provider,model_name,endpoint_key,route_fingerprint,
        adapter_version,runtime_version,packet_key,state,scores,reasoning_profiles,
        tools_verified,structured_output_verified,latency_ms,human_reviewer,created_by)
      VALUES ('{route}','filing_analysis','openrouter','synthetic/cloud',
        '{route}_endpoint','{"0"*64}','aios-fabric-v1','synthetic',
        'reviewed-canary','passed','{{"numeric":100,"citation":100,
        "missing_data":100,"prompt_injection":100}}'::jsonb,ARRAY['none'],
        false,true,1,'Named Reviewer','Synthetic Operator')
    """)
    # Replace qualification fingerprint with the real immutable route fingerprint
    # by inserting a second row; qualification history itself cannot be edited.
    route_row = fabric._route(route)
    execute(f"""
      INSERT INTO agent.model_route_qualifications(
        route_name,task_class,provider,model_name,endpoint_key,route_fingerprint,
        adapter_version,runtime_version,packet_key,state,scores,reasoning_profiles,
        tools_verified,structured_output_verified,latency_ms,human_reviewer,created_by)
      VALUES ('{route}','filing_analysis','openrouter','synthetic/cloud',
        '{route}_endpoint','{route_row["fingerprint"]}','aios-fabric-v1','synthetic',
        'reviewed-canary','passed','{{"numeric":100,"citation":100,
        "missing_data":100,"prompt_injection":100}}'::jsonb,ARRAY['none'],
        false,true,1,'Named Reviewer','Synthetic Operator')
    """)
    version = _binding(fabric, agent_id, route)
    with pytest.raises(FabricError, match="named_binding_approval_required"):
        fabric.promote(version["id"], "Synthetic Operator")
    approval = int(execute(f"""
      INSERT INTO agent.approvals(
        task_id,approval_type,title,owner_agent,status,requested_action,
        decided_by,decided_at)
      VALUES ({task_id},'model_binding_change','Synthetic binding','AI Runtime Engineer',
        'approved','{{"version_id":{version["id"]},"action":"promoted"}}'::jsonb,
        'Named Approver',now()) RETURNING id
    """))
    fabric.promote(version["id"], "Synthetic Operator", approval)
    execute(f"""
      UPDATE agent.tasks SET data_class='client_private',
        client_id=42 WHERE id={task_id};
      UPDATE agent.agent_workspaces SET allowed_clients=ARRAY[42]
        WHERE agent_id={agent_id}
    """)
    with pytest.raises(FabricError, match="private_cloud_egress_denied"):
        fabric.execute(_request(
            agent_id, task_id, privacy_class="client_private",
            contains_client_data=True, public_only=True,
        ))
    execute(f"""
      UPDATE agent.tasks SET data_class='public',client_id=NULL WHERE id={task_id}
    """)
    with pytest.raises(FabricError, match="approved_model_preflight_required"):
        fabric.execute(_request(
            agent_id, task_id, privacy_class="public", public_only=True,
        ))
    assert execute("""
      SELECT count(*) FROM agent.model_fabric_attempts WHERE provider='openrouter'
    """) == "0"


def test_provider_adapters_require_exact_identity_privacy_and_effort(provider_server):
    base_url, _ = provider_server
    local = {
        "default_provider": "local_openai", "default_model": "local-model-a",
        "base_url": base_url, "capabilities": [], "config": {},
    }
    req = ModelRequest.parse(_request(1, 1))
    assert ProviderAdapter(local).identity()["model"] == "local-model-a"
    with pytest.raises(FabricError, match="reasoning_control_unsupported"):
        ProviderAdapter(local).body(ModelRequest.parse({
            **_request(1, 1), "reasoning_profile": "high",
        }))
    with pytest.raises(FabricError, match="private_provider_must_be_literal_loopback"):
        ProviderAdapter({**local, "base_url": "https://private.example/v1"})

    tool_schema = {
        "type": "object", "additionalProperties": False,
        "properties": {"filing_id": {"type": "integer"}},
        "required": ["filing_id"],
    }
    tool_request = ModelRequest.parse({
        **_request(1, 1),
        "tools": [{"type": "function", "function": {
            "name": "read_public_filing", "description": "Synthetic tool",
            "parameters": tool_schema,
        }}],
    })
    tool_route = {**local, "capabilities": ["tools"]}
    tool_body = ProviderAdapter(tool_route).body(tool_request)
    assert tool_body["tools"] == tool_request.tools

    ollama = {
        "default_provider": "ollama", "default_model": "local-model-a",
        "base_url": base_url.removesuffix("/v1"),
        "capabilities": ["structured_output"],
        "config": {"supports_think": True,
                   "reasoning_map": {"high": "high"}},
    }
    ollama_adapter = ProviderAdapter(ollama)
    assert ollama_adapter.identity()["revision"] == "synthetic-r1"
    ollama_body = ollama_adapter.body(ModelRequest.parse({
        **_request(1, 1), "reasoning_profile": "high",
    }))
    assert ollama_body["think"] == "high"
    assert ollama_adapter.complete(req)["model"] == "local-model-a"

    seen = {}
    def transport(method, url, headers, body):
        seen.update({"method": method, "url": url, "headers": headers, "body": body})
        return {"data": [{"id": "synthetic/cloud", "revision": "r1"}]}
    cloud = {
        "default_provider": "openrouter", "default_model": "synthetic/cloud",
        "base_url": "https://openrouter.ai/api/v1", "capabilities": [],
        "requires_api_key": True, "secret_ref": "AI_OS_OPENROUTER_API_KEY",
        "config": {"reasoning_map": {"high": "high"}},
    }
    adapter = ProviderAdapter(
        cloud, secret_resolver=lambda _: "synthetic-secret", transport=transport
    )
    adapter.identity()
    body = adapter.body(ModelRequest.parse({
        **_request(1, 1), "reasoning_profile": "high",
    }))
    assert body["model"] == "synthetic/cloud"
    assert body["reasoning"] == {"exclude": True, "effort": "high"}
    assert body["provider"] == {
        "zdr": True, "data_collection": "deny",
        "require_parameters": True, "allow_fallbacks": False,
    }
    assert "synthetic-secret" not in repr(adapter)
    assert seen["headers"]["Authorization"] == "Bearer synthetic-secret"


def test_stream_parser_discards_reasoning_and_rejects_interruption():
    raw = (
        b'data: {"model":"m","choices":[{"delta":{"content":"ok"},'
        b'"finish_reason":"stop"}]}\n'
        b'data: {"model":"m","choices":[],"usage":{"prompt_tokens":2,'
        b'"completion_tokens":1},"reasoning":"never retain"}\n'
        b'data: [DONE]\n'
    )
    parsed = parse_stream(raw, "local_openai")
    assert parsed["choices"][0]["message"]["content"] == "ok"
    assert "reasoning" not in parsed
    with pytest.raises(FabricError, match="provider_stream_interrupted"):
        parse_stream(raw.replace(b"data: [DONE]\n", b""), "local_openai")


def test_binding_and_qualification_history_are_immutable(fabric_environment):
    execute, fabric, _, _, agent_id, _, routes = fabric_environment
    qualification = fabric.qualify(routes[0], "filing_analysis", "Reviewer")
    version = _binding(fabric, agent_id, routes[0])
    with pytest.raises(Exception, match="history is immutable"):
        execute(f"""
          UPDATE agent.model_binding_versions SET version=99 WHERE id={version["id"]}
        """)
    with pytest.raises(Exception, match="history is immutable"):
        execute(f"""
          DELETE FROM agent.model_route_qualifications WHERE id={qualification["id"]}
        """)
