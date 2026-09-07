"""Scoped durable conversations and handoffs on the canonical agent tables.

This adapter stores messages; it never impersonates an agent, invokes a model,
marks research ready, or grants trading/credential access.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re

try:
    from .agent_os_policy import Principal, evidence_refs, request_key, safe_text
    from .agent_runtime import literal
    from .agent_runtime_api import RuntimeAPI, RuntimeRequestError, cursor_id, positive_id
except ImportError:
    from agent_os_policy import Principal, evidence_refs, request_key, safe_text
    from agent_runtime import literal
    from agent_runtime_api import RuntimeAPI, RuntimeRequestError, cursor_id, positive_id


_THREAD = re.compile(r"[a-zA-Z0-9_.:-]{8,120}")
_ROOMS = {"direct", "department", "case", "strategy", "client", "committee", "incident", "approval"}
_PRIORITIES = {"low", "medium", "high", "critical"}
_HANDOFF_ACTIONS = {"acknowledge", "accept", "reject", "start", "return", "validate", "cancel", "fail"}


def _json(value, *, limit=8000, label="Structured value") -> str:
    if not isinstance(value, (dict, list)):
        raise RuntimeRequestError(f"{label} must be a JSON object or list.")
    encoded = json.dumps(value, separators=(",", ":"), sort_keys=True)
    if len(encoded) > limit or "\x00" in encoded:
        raise RuntimeRequestError(f"{label} exceeds its bounded size.")
    # Reuse the credential detector without requiring arbitrary JSON to be text.
    safe_text(encoded, limit)
    return encoded


def thread_key(value) -> str:
    if not isinstance(value, str) or not _THREAD.fullmatch(value):
        raise RuntimeRequestError("A stable thread key (8–120 safe characters) is required.")
    return value


class CollaborationAPI(RuntimeAPI):
    def __init__(self, execute, principal: Principal | None = None):
        super().__init__(execute)
        self.principal = principal or Principal()

    def _scope(self, payload: dict | None = None) -> tuple[str, int | None, int | None]:
        payload = payload or {}
        if payload.get("runtime_scope", self.principal.scope) != self.principal.scope:
            raise RuntimeRequestError("Workspace scope cannot be promoted by request data.", 403)
        book = positive_id(payload["book_id"]) if payload.get("book_id") is not None else None
        client = positive_id(payload["client_id"]) if payload.get("client_id") is not None else None
        if book is not None and book not in self.principal.books:
            raise RuntimeRequestError("Book is not authorized for this workspace.", 403)
        if client is not None and client not in self.principal.clients:
            raise RuntimeRequestError("Client is not authorized for this workspace.", 403)
        return self.principal.scope, book, client

    def _thread(self, key: str) -> dict:
        key = thread_key(key)
        rows = self.rows(f"""SELECT thread_key,room_type,title,runtime_scope,book_id,client_id,data_class,
            context,created_by,created_at,retention_days,archived_at
            FROM agent.conversation_threads t WHERE thread_key={literal(key)} AND {self.principal.clause('t')}""")
        if not rows:
            raise RuntimeRequestError("Conversation not found in the authorized workspace.", 404)
        return rows[0]

    def _agent(self, agent_id) -> dict:
        agent_id = positive_id(agent_id)
        rows = self.rows(f"""SELECT p.id,p.agent_key,p.agent_name,p.display_title,p.department,p.role_scope,
            p.default_model_route,p.default_tools,p.permission_level,p.status,p.guardrails,p.output_targets,
            p.role_version,w.workspace_key,w.owner_agent_id,w.escalation_agent_id,w.room_key,
            w.allowed_task_classes,w.allowed_scopes,w.allowed_books,w.allowed_clients,w.allowed_data_classes,
            w.denied_capabilities,w.daily_token_budget,w.capability_status
            FROM agent.profiles p LEFT JOIN agent.agent_workspaces w ON w.agent_id=p.id WHERE p.id={agent_id}""")
        if not rows:
            raise RuntimeRequestError("Agent not found.", 404)
        return rows[0]

    def create_thread(self, payload: dict) -> dict:
        self.principal.require("message")
        allowed = {"thread_key", "room_type", "title", "runtime_scope", "book_id", "client_id", "data_class", "context", "retention_days"}
        if not isinstance(payload, dict) or set(payload) - allowed:
            raise RuntimeRequestError("Thread request contains unsupported fields.")
        key = thread_key(payload.get("thread_key"))
        room = payload.get("room_type")
        if room not in _ROOMS:
            raise RuntimeRequestError("Unsupported conversation room type.")
        title = safe_text(payload.get("title"), 240)
        scope, book, client = self._scope(payload)
        data_class = payload.get("data_class", "internal")
        if data_class not in {"public", "internal", "house_confidential", "client_private"}:
            raise RuntimeRequestError("Unsupported data class.")
        if data_class == "client_private" and client is None:
            raise RuntimeRequestError("Client-private rooms require an authorized client.")
        context = payload.get("context", {})
        context_json = _json(context, label="Thread context")
        retention = payload.get("retention_days", 365)
        if isinstance(retention, bool) or not isinstance(retention, int) or not 30 <= retention <= 3650:
            raise RuntimeRequestError("Retention must be 30–3650 days.")
        result = self._value(f"""WITH inserted AS (
            INSERT INTO agent.conversation_threads(thread_key,room_type,title,runtime_scope,book_id,client_id,
                data_class,context,created_by,retention_days)
            VALUES({literal(key)},{literal(room)},{literal(title)},{literal(scope)},{literal(book)},{literal(client)},
                {literal(data_class)},{literal(context_json)}::jsonb,{literal(self.principal.user_id)},{retention})
            ON CONFLICT(thread_key) DO NOTHING RETURNING thread_key)
            SELECT json_build_object('created',EXISTS(SELECT 1 FROM inserted))::text;""")
        thread = self._thread(key)
        expected = {"room_type": room, "title": title, "runtime_scope": scope, "book_id": book, "client_id": client, "data_class": data_class}
        if any(thread.get(field) != value for field, value in expected.items()):
            raise RuntimeRequestError("Thread idempotency key is already bound to different context.", 409)
        if result["created"]:
            self._value(f"SELECT agent.append_scoped_runtime_event('thread_created','RECORDED',NULL,NULL,'operator',{literal(self.principal.user_id)},NULL,{literal(key)})::text;")
        return {"thread": thread, "created": result["created"], "broker_write_allowed": False}

    def threads(self, limit=100) -> dict:
        self.principal.require("read")
        limit = max(1, min(200, int(limit)))
        rows = self.rows(f"""SELECT t.thread_key,t.room_type,t.title,t.data_class,t.created_at,t.archived_at,
            (SELECT count(*) FROM agent.agent_messages m WHERE m.conversation_key=t.thread_key) message_count,
            (SELECT max(created_at) FROM agent.agent_messages m WHERE m.conversation_key=t.thread_key) last_message_at
            FROM agent.conversation_threads t WHERE {self.principal.clause('t')}
            ORDER BY coalesce((SELECT max(created_at) FROM agent.agent_messages m WHERE m.conversation_key=t.thread_key),t.created_at) DESC LIMIT {limit}""")
        return {"threads": rows, "generated_at": datetime.now(timezone.utc).isoformat(), "broker_write_allowed": False}

    def messages(self, key: str, after=0, limit=100) -> dict:
        self.principal.require("read")
        thread = self._thread(key)
        after = cursor_id(after)
        limit = max(1, min(200, int(limit)))
        rows = self.rows(f"""SELECT id,conversation_key,from_agent_id,to_agent_id,sender_user_id,subject,body,
            priority,status,related_task_id,attachments,mentions,processing_status,created_at,read_at
            FROM agent.agent_messages WHERE conversation_key={literal(thread['thread_key'])} AND id>{after}
            ORDER BY id LIMIT {limit + 1}""")
        more = len(rows) > limit
        rows = rows[:limit]
        return {"thread": thread, "messages": rows, "cursor": rows[-1]["id"] if rows else after,
                "has_more": more, "broker_write_allowed": False}

    def send_message(self, key: str, payload: dict, *, to_agent_id=None) -> dict:
        self.principal.require("message")
        allowed = {"request_key", "subject", "body", "priority", "to_agent_id", "from_agent_id", "attachments", "mentions", "related_task_id"}
        if not isinstance(payload, dict) or set(payload) - allowed:
            raise RuntimeRequestError("Message contains unsupported fields.")
        thread = self._thread(key)
        request = request_key(payload.get("request_key"))
        subject = safe_text(payload.get("subject", "Agent message"), 240)
        body = safe_text(payload.get("body"), 8000)
        priority = payload.get("priority", "medium")
        if priority not in _PRIORITIES:
            raise RuntimeRequestError("Unsupported message priority.")
        recipient = positive_id(to_agent_id if to_agent_id is not None else payload["to_agent_id"]) if (to_agent_id is not None or payload.get("to_agent_id") is not None) else None
        sender = self.principal.agent_id
        if sender is None and payload.get("from_agent_id") is not None:
            sender = positive_id(payload["from_agent_id"])
        if sender is not None:
            self._agent(sender)
        if recipient is not None:
            self._agent(recipient)
        if sender is not None and sender == recipient:
            raise RuntimeRequestError("Sender and recipient must be distinct.")
        attachments = evidence_refs(payload.get("attachments", []))
        mentions = payload.get("mentions", [])
        if not isinstance(mentions, list) or len(mentions) > 20:
            raise RuntimeRequestError("Provide at most 20 agent mentions.")
        mentions = [positive_id(value) for value in mentions]
        related = positive_id(payload["related_task_id"]) if payload.get("related_task_id") is not None else None
        if related is not None and not self.rows(f"SELECT id FROM agent.tasks t WHERE id={related} AND {self.principal.clause('t')}"):
            raise RuntimeRequestError("Related task is not in this workspace.", 404)
        sender_name = self._agent(sender)["agent_name"] if sender is not None else None
        recipient_name = self._agent(recipient)["agent_name"] if recipient is not None else None
        attachments_json = _json(attachments, label="Message attachments")
        mentions_sql = "ARRAY[" + ",".join(map(str, mentions)) + "]::bigint[]" if mentions else "'{}'::bigint[]"
        row = self._value(f"""WITH inserted AS (
            INSERT INTO agent.agent_messages(thread_key,conversation_key,from_agent,to_agent,from_agent_id,to_agent_id,
                sender_user_id,subject,body,priority,status,related_task_id,attachments,mentions,idempotency_key,
                processing_status,runtime_scope,book_id,client_id)
            VALUES({literal(thread['thread_key'])},{literal(thread['thread_key'])},{literal(sender_name)},{literal(recipient_name)},
                {literal(sender)},{literal(recipient)},{literal(None if sender is not None else self.principal.user_id)},
                {literal(subject)},{literal(body)},{literal(priority)},'unread',{literal(related)},
                {literal(attachments_json)}::jsonb,{mentions_sql},{literal(request)},'pending',
                {literal(thread['runtime_scope'])},{literal(thread.get('book_id'))},{literal(thread.get('client_id'))})
            ON CONFLICT(conversation_key,idempotency_key) WHERE idempotency_key IS NOT NULL DO NOTHING RETURNING *)
            SELECT result::text FROM (
                SELECT json_build_object('created',true,'message',row_to_json(i)) result FROM inserted i
                UNION ALL
                SELECT json_build_object('created',false,'message',row_to_json(m)) FROM agent.agent_messages m
                WHERE m.conversation_key={literal(thread['thread_key'])} AND m.idempotency_key={literal(request)}
            ) resolved LIMIT 1;""")
        message = row["message"]
        if message["body"] != body or message.get("to_agent_id") != recipient or message.get("from_agent_id") != sender:
            raise RuntimeRequestError("Message idempotency key is already bound to different content.", 409)
        if row["created"]:
            self._value(f"SELECT agent.append_scoped_runtime_event('message_sent','RECORDED',{literal(related)},{literal(sender)},'operator',{literal(self.principal.user_id)},NULL,{literal(thread['thread_key'])})::text;")
        return {"message": message, "created": row["created"], "queued_for_processing": True,
                "delivery_is_completion": False, "broker_write_allowed": False}

    def acknowledge(self, message_id, *, acknowledge=True) -> dict:
        self.principal.require("read")
        message_id = positive_id(message_id)
        rows = self.rows(f"""SELECT m.id,m.conversation_key FROM agent.agent_messages m
            JOIN agent.conversation_threads t ON t.thread_key=m.conversation_key
            WHERE m.id={message_id} AND {self.principal.clause('t')}""")
        if not rows:
            raise RuntimeRequestError("Message not found in the authorized workspace.", 404)
        result = self._value(f"SELECT agent.runtime_message_receipt({message_id},{literal(self.principal.user_id)},{literal(bool(acknowledge))})::text;")
        event = "message_acknowledged" if acknowledge else "message_read"
        self._value(f"SELECT agent.append_scoped_runtime_event({literal(event)},'RECORDED',NULL,{literal(self.principal.agent_id)},'operator',{literal(self.principal.user_id)},NULL,{literal(rows[0]['conversation_key'])})::text;")
        return {"receipt": result, "broker_write_allowed": False}

    def create_handoff(self, payload: dict) -> dict:
        self.principal.require("handoff")
        allowed = {"request_key", "thread_key", "from_agent_id", "to_agent_id", "parent_task_id", "question", "expected_output_schema", "evidence_refs"}
        if not isinstance(payload, dict) or set(payload) - allowed:
            raise RuntimeRequestError("Handoff contains unsupported fields.")
        request = request_key(payload.get("request_key"))
        thread = self._thread(payload.get("thread_key"))
        parent = positive_id(payload.get("parent_task_id"))
        rows = self.rows(f"SELECT id FROM agent.tasks t WHERE id={parent} AND {self.principal.clause('t')}")
        if not rows:
            raise RuntimeRequestError("Parent task not found in this workspace.", 404)
        sender = self.principal.agent_id or positive_id(payload.get("from_agent_id"))
        recipient = positive_id(payload.get("to_agent_id"))
        self._agent(sender); self._agent(recipient)
        question = safe_text(payload.get("question"), 4000)
        refs = evidence_refs(payload.get("evidence_refs", []))
        schema = payload.get("expected_output_schema", {"type": "object", "required": ["summary", "evidence_refs", "missing_data"]})
        if not isinstance(schema, dict) or schema.get("type") != "object" or not {"summary", "evidence_refs", "missing_data"}.issubset(set(schema.get("required", []))):
            raise RuntimeRequestError("Handoff output schema must require summary, evidence_refs and missing_data.")
        result = self._value(f"SELECT agent.create_task_handoff({literal(request)},{literal(thread['thread_key'])},{sender},{recipient},{parent},{literal(question)},{literal(_json(schema,limit=4000,label='Output schema'))}::jsonb,{literal(_json(refs,label='Evidence references'))}::jsonb)::text;")
        return result

    def advance_handoff(self, handoff_id, action: str, payload: dict | None = None) -> dict:
        self.principal.require("handoff")
        handoff_id = positive_id(handoff_id)
        if action not in _HANDOFF_ACTIONS:
            raise RuntimeRequestError("Unsupported handoff action.")
        payload = payload or {}
        if set(payload) - {"actor_agent_id", "receipt_id", "note"}:
            raise RuntimeRequestError("Handoff action contains unsupported fields.")
        rows = self.rows(f"SELECT id FROM agent.task_handoffs h WHERE id={handoff_id} AND {self.principal.clause('h')}")
        if not rows:
            raise RuntimeRequestError("Handoff not found in this workspace.", 404)
        actor = self.principal.agent_id or positive_id(payload.get("actor_agent_id"))
        receipt = positive_id(payload["receipt_id"]) if payload.get("receipt_id") is not None else None
        note = safe_text(payload["note"], 2000) if payload.get("note") is not None else None
        try:
            return self._value(f"SELECT agent.advance_task_handoff({handoff_id},{literal(action)},{actor},{literal(receipt)},{literal(note)})::text;")
        except Exception as exc:
            raise RuntimeRequestError("Handoff state, ownership, lease or cited receipt requirement is not satisfied.", 409) from exc

    def agent_detail(self, agent_id) -> dict:
        self.principal.require("read")
        agent = self._agent(agent_id)
        agent_id = agent["id"]
        presence = self.rows(f"SELECT * FROM agent.v_runtime_presence WHERE agent_id={agent_id}")
        tasks = self.rows(f"""SELECT id,status,runtime_state,control_requested,task_class,runtime_scope,book_id,client_id,
            updated_at FROM agent.tasks t WHERE agent_id={agent_id} AND {self.principal.clause('t')}
            ORDER BY updated_at DESC LIMIT 50""")
        handoffs = self.rows(f"""SELECT id,thread_key,parent_task_id,child_task_id,from_agent_id,to_agent_id,state,due_at,updated_at,
            (receipt_id IS NOT NULL) has_receipt,(validated_at IS NOT NULL) independently_validated
            FROM agent.task_handoffs h WHERE (from_agent_id={agent_id} OR to_agent_id={agent_id}) AND {self.principal.clause('h')}
            ORDER BY updated_at DESC LIMIT 50""")
        return {"agent": agent, "presence": presence[0] if presence else {"state": "OFFLINE", "has_live_lease": False},
                "tasks": tasks, "handoffs": handoffs, "broker_write_allowed": False}

    def redirect_task(self, task_id, payload: dict) -> dict:
        self.principal.require("control")
        task_id = positive_id(task_id)
        if not isinstance(payload, dict) or set(payload) - {"objective", "source_policy"} or payload.get("source_policy") != "primary_only":
            raise RuntimeRequestError("Redirect requires an objective and primary_only source policy.")
        objective = safe_text(payload.get("objective"), 4000)
        if not self.rows(f"SELECT id FROM agent.tasks t WHERE id={task_id} AND {self.principal.clause('t')}"):
            raise RuntimeRequestError("Task not found in the authorized workspace.", 404)
        return self._value(f"SELECT agent.redirect_runtime_task({task_id},{literal(self.principal.user_id)},{literal(objective)},'{{\"source_policy\":\"primary_only\"}}'::jsonb)::text;")

    def handoffs(self) -> list:
        self.principal.require("read")
        return self.rows(f"""SELECT h.id,h.thread_key,h.parent_task_id,h.child_task_id,h.from_agent_id,h.to_agent_id,
            h.state,h.updated_at,r.recovery_action FROM agent.task_handoffs h
            LEFT JOIN agent.v_handoff_recovery r ON r.id=h.id WHERE {self.principal.clause('h')}
            ORDER BY h.updated_at DESC LIMIT 100""")

    def overview(self) -> dict:
        self.principal.require("read")
        agents = self.rows("""SELECT p.id,p.agent_key,p.agent_name,p.display_title,p.department,p.status,
            w.room_key,w.capability_status,v.state,v.task_id,v.worker_id,v.expires_at,v.has_live_lease
            FROM agent.profiles p LEFT JOIN agent.agent_workspaces w ON w.agent_id=p.id
            LEFT JOIN agent.v_runtime_presence v ON v.agent_id=p.id ORDER BY p.department,p.agent_name LIMIT 500""")
        tasks = self.rows(f"""SELECT id,agent_id,status,runtime_state,control_requested,task_class,updated_at
            FROM agent.tasks t WHERE runtime_protocol='lease_v1' AND {self.principal.clause('t')}
            ORDER BY updated_at DESC LIMIT 100""")
        handoffs = self.rows(f"""SELECT id,thread_key,parent_task_id,child_task_id,from_agent_id,to_agent_id,state,updated_at
            FROM agent.task_handoffs h WHERE {self.principal.clause('h')} ORDER BY updated_at DESC LIMIT 100""")
        return {"available": True, "generated_at": datetime.now(timezone.utc).isoformat(), "agents": agents,
                "tasks": tasks, "handoffs": handoffs, "presence_contract": "unexpired_lease_and_healthy_worker",
                "research_readiness_inferred": False, "broker_write_allowed": False}
