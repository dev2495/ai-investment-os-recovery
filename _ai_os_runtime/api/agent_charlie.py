"""Deterministic chief-of-staff control over durable Agent OS records.

Natural language is classified into an allowlisted command set. Unknown or
ambiguous entities stop for input; this module never guesses a company, calls a
model, promotes research readiness, approves spend, or enables broker writes.
"""
from __future__ import annotations

import json
import re

try:
    from .agent_collaboration import CollaborationAPI, _json
    from .agent_os_policy import Principal, request_key, safe_text
    from .agent_runtime import literal
    from .agent_runtime_api import RuntimeAPI, RuntimeRequestError, positive_id
except ImportError:
    from agent_collaboration import CollaborationAPI, _json
    from agent_os_policy import Principal, request_key, safe_text
    from agent_runtime import literal
    from agent_runtime_api import RuntimeAPI, RuntimeRequestError, positive_id


ALIASES = {
    "forensic": ("Forensic Accounting Agent",),
    "valuation": ("Valuation Agent", "Sector Valuation Analyst"),
    "industry": ("Industry Analyst",),
    "risk": ("Risk Agent",),
    "portfolio": ("Portfolio Manager", "Long-Term Portfolio Manager"),
    "research": ("Research Director", "Research Analyst"),
    "company": ("Company Analyst", "Research Analyst"),
}


class CharlieAPI:
    def __init__(self, execute, principal: Principal | None = None):
        self.execute = execute
        self.principal = principal or Principal()
        self.runtime = RuntimeAPI(execute)
        self.collaboration = CollaborationAPI(execute, self.principal)

    def _value(self, query: str):
        return self.runtime._value(query)

    def _relation(self, name: str) -> bool:
        return bool(self._value(f"SELECT (to_regclass({literal(name)}) IS NOT NULL)::text;"))

    def _response(self, **changes) -> dict:
        result = {
            "understood_objective": None, "context": {}, "affected_entities": [],
            "affected_books_or_clients": {"books": list(self.principal.books), "clients": list(self.principal.clients)},
            "plan_id": None, "tasks": [], "agents": [], "current_state": "RECORDED",
            "model_routes": [], "sources": [], "source_freshness": "not_recorded",
            "calculations": [], "artifacts": [], "conclusion": None, "confidence": None,
            "bear_case": None, "dissent": [], "contradictions": [], "missing_data": [],
            "risk_flags": [], "approvals_needed": [], "memory_written": False,
            "next_action": None, "broker_write_allowed": False,
        }
        result.update(changes)
        return result

    def _resolve_agent(self, role: str) -> dict:
        candidates = ALIASES[role]
        names = ",".join(literal(value) for value in candidates)
        rows = self.runtime.rows(f"""SELECT id,agent_key,agent_name,display_title,department,status
            FROM agent.profiles WHERE agent_name IN ({names}) AND status='active'
            ORDER BY array_position(ARRAY[{names}],agent_name) LIMIT 2""")
        if not rows:
            raise RuntimeRequestError(f"No active canonical {role} agent is registered.", 409)
        return rows[0]

    @staticmethod
    def _tokens(value: str) -> str:
        return " " + re.sub(r"[^a-z0-9]+", " ", value.lower()).strip() + " "

    def _company(self, text: str, context: dict) -> dict | None:
        explicit_case = context.get("research_case_id")
        if explicit_case is not None:
            explicit_case = positive_id(explicit_case)
            if not self._relation("research.research_cases"):
                raise RuntimeRequestError("Research Case registry is not installed.", 409)
            rows = self.runtime.rows(f"""SELECT rc.id research_case_id,rc.company_id,rc.company_name,
                rc.ticker,rc.exchange,rc.status FROM research.research_cases rc WHERE rc.id={explicit_case}""")
            if not rows:
                raise RuntimeRequestError("Research Case was not found; context was not guessed.", 404)
            return rows[0]
        if not self._relation("research.companies"):
            return None
        companies = self.runtime.rows("""SELECT c.id company_id,coalesce(c.display_name,c.legal_name) company_name,
            c.legal_name,c.primary_symbol ticker,c.primary_exchange exchange,
            (SELECT rc.id FROM research.research_cases rc WHERE rc.company_id=c.id
             AND rc.status IN ('active','collecting','review','blocked','completed') ORDER BY rc.updated_at DESC,rc.id DESC LIMIT 1) research_case_id
            FROM research.companies c WHERE c.status='active' ORDER BY c.id LIMIT 1000""")
        haystack = self._tokens(text)
        matches = []
        for row in companies:
            values = {str(row.get("ticker") or ""), str(row.get("company_name") or ""), str(row.get("legal_name") or "")}
            if any(value and self._tokens(value).strip() and self._tokens(value) in haystack for value in values):
                matches.append(row)
        unique = {row["company_id"]: row for row in matches}
        if len(unique) > 1:
            raise RuntimeRequestError("More than one registered company matched. Specify the exact company or Research Case.", 409)
        return next(iter(unique.values()), None)

    def _task_for_agent(self, agent_id: int, context: dict, *, statuses=("queued", "in_progress", "paused", "blocked", "needs_review")) -> dict | None:
        explicit = context.get("task_id")
        status_sql = ",".join(literal(value) for value in statuses)
        if explicit is not None:
            explicit = positive_id(explicit)
            rows = self.runtime.rows(f"SELECT * FROM agent.tasks t WHERE id={explicit} AND agent_id={agent_id} AND {self.principal.clause('t')}")
        else:
            rows = self.runtime.rows(f"""SELECT * FROM agent.tasks t WHERE agent_id={agent_id}
                AND status IN ({status_sql}) AND {self.principal.clause('t')} ORDER BY updated_at DESC,id DESC LIMIT 2""")
        if not rows:
            return None
        if explicit is None and len(rows) > 1 and rows[0]["updated_at"] == rows[1]["updated_at"]:
            raise RuntimeRequestError("Two active tasks are equally current. Specify task_id.", 409)
        return rows[0]

    def _record(self, request: str, command: str, intent: str, status: str, response: dict) -> dict:
        encoded = _json(response, limit=40000, label="Charlie response")
        row = self._value(f"""WITH inserted AS (
            INSERT INTO agent.charlie_commands(request_key,raw_command,intent,runtime_scope,actor_user_id,status,response)
            VALUES({literal(request)},{literal(command)},{literal(intent)},{literal(self.principal.scope)},
                {literal(self.principal.user_id)},{literal(status)},{literal(encoded)}::jsonb)
            ON CONFLICT(request_key) DO NOTHING RETURNING *)
            SELECT result::text FROM (
              SELECT json_build_object('created',true,'command',row_to_json(i)) result FROM inserted i
              UNION ALL SELECT json_build_object('created',false,'command',row_to_json(c))
              FROM agent.charlie_commands c WHERE c.request_key={literal(request)}) x LIMIT 1;""")
        existing = row["command"]
        if existing["raw_command"] != command or existing["actor_user_id"] != self.principal.user_id:
            raise RuntimeRequestError("Charlie request key is already bound to a different command.", 409)
        return existing["response"] if not row["created"] else response

    def _complete(self, command_id: int, response: dict, status="APPLIED") -> dict:
        encoded = _json(response, limit=40000, label="Charlie response")
        self._value(f"""UPDATE agent.charlie_commands SET response={literal(encoded)}::jsonb,
            status={literal(status)},updated_at=clock_timestamp() WHERE id={command_id}
            RETURNING json_build_object('updated',true)::text;""")
        return response

    def _plan(self, request: str, command: str, intent: str, understood: str, context: dict,
              company: dict | None, agent: dict, task_title: str, task_objective: str) -> dict:
        scope, book, client = self.collaboration._scope(context)
        plan_context = {key: value for key, value in context.items() if key in {"task_id", "research_case_id", "source_policy", "priority", "horizon"}}
        if company:
            plan_context.update({key: company.get(key) for key in ("company_id", "research_case_id", "ticker", "exchange") if company.get(key) is not None})
        entities = [{key: company.get(key) for key in ("company_id", "company_name", "ticker", "exchange", "research_case_id")} ] if company else []
        budget = _json({"paid_model_calls": 0}, label="Plan budget")
        result = self._value(f"""SELECT agent.create_charlie_plan({literal(request)},{literal(self.principal.user_id)},
            {literal(command)},{literal(intent)},{literal(understood)},{literal(_json(plan_context,label='Plan context'))}::jsonb,
            {literal(_json(entities,label='Affected entities'))}::jsonb,{literal(scope)},{literal(book)},{literal(client)},
            {literal('client_private' if client else 'internal')},{agent['id']},{literal(task_title)},{literal(task_objective)},
            'research','bounded_internal_draft','internal_draft',{literal(budget)}::jsonb)::text;""")
        response = self._response(
            understood_objective=understood, context=plan_context, affected_entities=entities,
            plan_id=result.get("plan_id"), tasks=[{"task_id": result.get("task_id"), "status": "queued", "completion": False}],
            agents=[{"agent_id": agent["id"], "agent_name": agent["agent_name"]}], current_state="QUEUED",
            model_routes=["local_first; paid route requires separate preflight and approval"],
            conclusion="The work is durably planned and queued; no analytical conclusion exists yet.",
            confidence="not_assessed", missing_data=["specialist output", "independent validation"],
            approvals_needed=[], next_action="A compatible worker must claim the canonical task and return a cited receipt.",
        )
        return self._complete(result["command_id"], response, "PLANNED")

    def command(self, payload: dict) -> dict:
        self.principal.require("plan")
        allowed = {"request_key", "command", "context"}
        if not isinstance(payload, dict) or set(payload) - allowed:
            raise RuntimeRequestError("Charlie command contains unsupported fields.")
        request = request_key(payload.get("request_key"))
        command = safe_text(payload.get("command"), 8000)
        context = payload.get("context", {})
        _json(context, limit=4000, label="Charlie context")
        lower = self._tokens(command)
        existing = self.runtime.rows(f"""SELECT raw_command,actor_user_id,response
            FROM agent.charlie_commands WHERE request_key={literal(request)}""")
        if existing:
            if (existing[0]["raw_command"] != command
                    or existing[0]["actor_user_id"] != self.principal.user_id):
                raise RuntimeRequestError(
                    "Charlie request key is already bound to a different command.", 409
                )
            # A replay returns the exact persisted response and cannot repeat a
            # committee invitation, task transition, event or model policy write.
            return existing[0]["response"]

        if " live agent " in lower or " every live agent " in lower or " what each is doing " in lower or " stack status " in lower:
            overview = self.collaboration.overview()
            response = self._response(
                understood_objective="Show current evidence-backed agent runtime state.", current_state="OBSERVED",
                agents=overview["agents"], tasks=overview["tasks"],
                conclusion="Presence is shown only for healthy workers with unexpired leases.",
                next_action="Open an agent to inspect its lease, task, handoffs and policy snapshot.",
            )
            return self._record(request, command, "show_live_agents", "APPLIED", response)

        company = self._company(command, context)
        if " ask " in lower and " forensic " in lower:
            if not company or not company.get("research_case_id"):
                return self._record(request, command, "delegate_forensic", "WAITING_FOR_INPUT", self._response(
                    understood_objective="Delegate a forensic review.", current_state="WAITING_FOR_INPUT",
                    missing_data=["one existing verified company and active Research Case"],
                    next_action="Provide the exact registered company or research_case_id; no company was guessed."))
            agent = self._resolve_agent("forensic")
            name = company.get("company_name") or company.get("ticker")
            return self._plan(request, command, "delegate_forensic", f"Explain why {name} cash conversion weakened using cited primary evidence.",
                context, company, agent, f"Forensic cash-conversion review — {name}",
                "Assess cash conversion drivers, contradictions and missing denominators from stored primary evidence; return a cited artifact.")

        if " pause " in lower and " valuation " in lower:
            agent = self._resolve_agent("valuation")
            task = self._task_for_agent(agent["id"], context, statuses=("queued", "in_progress"))
            if not task:
                return self._record(request, command, "pause_task", "WAITING_FOR_INPUT", self._response(
                    understood_objective="Pause a Valuation task at a safe boundary.", current_state="WAITING_FOR_INPUT",
                    agents=[agent], missing_data=["one active Valuation task"], next_action="Specify task_id or start a valuation task."))
            control = self.runtime.control(task["id"], "pause")
            response = self._response(understood_objective="Pause the Valuation task at its next safe boundary.",
                context={"task_id": task["id"]}, tasks=[control], agents=[agent], current_state="PAUSE_REQUESTED",
                next_action="The worker will release at a checkpoint; pause requested is not pause completed.")
            return self._record(request, command, "pause_task", "WAITING_FOR_SAFE_BOUNDARY", response)

        if " resume " in lower and " task " in lower:
            task_id = context.get("task_id")
            if task_id is None:
                rows = self.runtime.rows(f"""SELECT response->'context'->>'task_id' task_id FROM agent.charlie_commands
                    WHERE actor_user_id={literal(self.principal.user_id)} AND response->'context'->>'task_id' IS NOT NULL
                    ORDER BY id DESC LIMIT 1""")
                task_id = rows[0]["task_id"] if rows else None
            if task_id is None:
                return self._record(request, command, "resume_task", "WAITING_FOR_INPUT", self._response(
                    understood_objective="Resume a paused task.", current_state="WAITING_FOR_INPUT",
                    missing_data=["task_id"], next_action="Specify the paused task."))
            task_id = positive_id(task_id)
            if " primary source " in lower or " primary sources " in lower:
                self._value(f"UPDATE agent.tasks SET runtime_context=runtime_context||'{{\"source_policy\":\"primary_only\"}}'::jsonb WHERE id={task_id} RETURNING '{{\"updated\":true}}'::jsonb::text;")
            self._value(f"SELECT agent.apply_pending_runtime_redirect({task_id},{literal(self.principal.user_id)})::text;")
            control = self.runtime.control(task_id, "resume")
            response = self._response(understood_objective="Resume the paused task with its stored policy context.",
                context={"task_id": task_id, "source_policy": "primary_only" if " primary " in lower else "unchanged"},
                tasks=[control], current_state="QUEUED", next_action="A compatible worker may now claim it; queued is not completed.")
            return self._record(request, command, "resume_task", "APPLIED", response)

        if " redirect " in lower and " industry " in lower:
            agent = self._resolve_agent("industry")
            task = self._task_for_agent(agent["id"], context)
            target = company.get("company_name") if company else "the specified company"
            objective = f"Compare {target} with its closest listed peers using primary evidence, explicit selection criteria and disconfirmers."
            if not task:
                if not company or not company.get("research_case_id"):
                    return self._record(request, command, "redirect_task", "WAITING_FOR_INPUT", self._response(
                        understood_objective=objective, current_state="WAITING_FOR_INPUT",
                        missing_data=["existing Industry task or registered Research Case"], next_action="Specify task_id or research_case_id."))
                return self._plan(request, command, "redirect_task", objective, context, company, agent,
                    f"Industry peer comparison — {target}", objective)
            result = self._value(f"""SELECT agent.redirect_runtime_task({task['id']},{literal(self.principal.user_id)},{literal(objective)},
                {literal(_json({'redirected_by_charlie': True, 'source_policy': 'primary_only'},label='Redirect context'))}::jsonb)::text;""")
            response = self._response(understood_objective=objective, context={"task_id": task["id"]},
                affected_entities=[company] if company else [], tasks=[result], agents=[agent],
                current_state="WAITING_FOR_SAFE_BOUNDARY" if result["waiting_for_safe_boundary"] else "REDIRECTED",
                next_action="Resume after the old worker releases the lease." if result["waiting_for_safe_boundary"] else "A compatible worker may claim the redirected task.")
            return self._record(request, command, "redirect_task", "WAITING_FOR_SAFE_BOUNDARY" if result["waiting_for_safe_boundary"] else "APPLIED", response)

        if " invite " in lower and " committee " in lower:
            if not company:
                return self._record(request, command, "committee_invite", "WAITING_FOR_INPUT", self._response(
                    understood_objective="Invite Risk and Portfolio to an existing committee packet.", current_state="WAITING_FOR_INPUT",
                    missing_data=["registered company or Research Case"], next_action="Specify the exact company or research_case_id."))
            label = company.get("company_name") or company.get("ticker")
            packets = self.runtime.rows(f"""SELECT id,packet_key,title,packet_status FROM agent.committee_packets
                WHERE lower(title) LIKE {literal('%' + str(label).lower() + '%')} AND packet_status NOT IN ('closed','cancelled')
                ORDER BY updated_at DESC,id DESC LIMIT 2""")
            if len(packets) != 1:
                return self._record(request, command, "committee_invite", "WAITING_FOR_INPUT", self._response(
                    understood_objective=f"Invite Risk and Portfolio to the {label} committee.", current_state="WAITING_FOR_INPUT",
                    missing_data=["one unambiguous active committee packet"], next_action="Specify committee packet ID."))
            agents = [self._resolve_agent("risk"), self._resolve_agent("portfolio")]
            for agent in agents:
                self._value(f"""INSERT INTO agent.committee_invitations(packet_id,agent_id,invited_by)
                    VALUES({packets[0]['id']},{agent['id']},{literal(self.principal.user_id)}) ON CONFLICT DO NOTHING
                    RETURNING coalesce(json_build_object('invited',true)::text,'{{}}');""")
                self._value(f"SELECT agent.append_scoped_runtime_event('committee_invited','INVITED',NULL,{agent['id']},'operator',{literal(self.principal.user_id)},NULL,NULL,NULL,{packets[0]['id']})::text;")
            response = self._response(understood_objective=f"Invite Risk and Portfolio to the {label} committee.",
                context={"committee_id": packets[0]["id"]}, affected_entities=[company], agents=agents,
                current_state="INVITED", next_action="Invited agents must acknowledge and independently submit positions.")
            return self._record(request, command, "committee_invite", "APPLIED", response)

        if " stop all paid " in lower or (" paid model " in lower and " stop " in lower):
            if not company or not company.get("research_case_id"):
                return self._record(request, command, "stop_paid_models", "WAITING_FOR_INPUT", self._response(
                    understood_objective="Stop paid model calls for one Research Case.", current_state="WAITING_FOR_INPUT",
                    missing_data=["research_case_id"], next_action="Specify the existing Research Case; no scope was guessed."))
            result = self._value(f"SELECT agent.stop_paid_runtime_case({company['research_case_id']},{literal(self.principal.user_id)})::text;")
            response = self._response(understood_objective="Stop paid model calls for this Research Case without stopping local work.",
                context={"research_case_id": company["research_case_id"]}, affected_entities=[company], tasks=[result],
                current_state="PAID_MODEL_WORK_STOPPED", model_routes=["local routes remain eligible"],
                conclusion="The persisted case gate is active; providers must recheck it before every attempt.",
                next_action="Continue bounded local work or request a separately approved paid preflight later.")
            return self._record(request, command, "stop_paid_models", "APPLIED", response)

        if " local research route " in lower and " red team " in lower:
            scope, book, client = self.collaboration._scope(context)
            key = f"charlie:{scope}:book:{book or 0}:client:{client or 0}"
            self._value(f"""INSERT INTO agent.charlie_route_policies(policy_key,runtime_scope,book_id,client_id,created_by)
                VALUES({literal(key)},{literal(scope)},{literal(book)},{literal(client)},{literal(self.principal.user_id)})
                ON CONFLICT(policy_key) DO UPDATE SET routine_route_class='local',red_team_route_class='cloud_approval_required',
                public_cloud_requires_approval=true,updated_at=clock_timestamp() RETURNING json_build_object('policy_key',policy_key)::text;""")
            response = self._response(understood_objective="Use local research routes for routine work and reserve public cloud for approved red-team work.",
                context={"policy_key": key}, current_state="POLICY_RECORDED", model_routes=["routine:local", "red_team:cloud_approval_required"],
                approvals_needed=["privacy and spend approval before any public-cloud call"], next_action="Model Fabric enforces this policy per attempt.")
            return self._record(request, command, "route_policy", "APPLIED", response)

        if " blocked " in lower and " explain " in lower:
            task_id = positive_id(context["task_id"]) if context.get("task_id") is not None else None
            clause = f"t.id={task_id}" if task_id else "t.status='blocked'"
            rows = self.runtime.rows(f"""SELECT t.id,t.agent_id,t.status,t.runtime_state,t.updated_at,
                (SELECT e.reason_code FROM agent.task_events e WHERE e.task_id=t.id ORDER BY e.id DESC LIMIT 1) reason_code
                FROM agent.tasks t WHERE {clause} AND {self.principal.clause('t')} ORDER BY t.updated_at DESC LIMIT 2""")
            if not rows:
                response = self._response(understood_objective="Explain a blocked agent task.", current_state="WAITING_FOR_INPUT",
                    missing_data=["blocked task_id"], next_action="Specify a blocked task.")
                return self._record(request, command, "explain_blocker", "WAITING_FOR_INPUT", response)
            response = self._response(understood_objective="Explain the persisted blocker without exposing raw secrets.",
                context={"task_id": rows[0]["id"]}, tasks=rows[:1], current_state="BLOCKED",
                conclusion=rows[0].get("reason_code") or "No bounded reason code was recorded.",
                missing_data=[] if rows[0].get("reason_code") else ["bounded blocker reason"],
                next_action="Open Doctor or the task event trail before choosing an allowlisted repair.")
            return self._record(request, command, "explain_blocker", "APPLIED", response)

        if " artifact " in lower and " citation " in lower and " handoff " in lower:
            rows = self.runtime.rows(f"""SELECT h.id handoff_id,h.state,r.artifact_ref,r.content_hash,r.evidence_refs,r.validated_at
                FROM agent.task_handoffs h JOIN agent.runtime_output_receipts r ON r.id=h.receipt_id
                WHERE {self.principal.clause('h')} ORDER BY h.updated_at DESC,h.id DESC LIMIT 1""")
            if not rows:
                response = self._response(understood_objective="Show the last handoff artifact and citations.",
                    current_state="WAITING_FOR_INPUT", missing_data=["returned handoff receipt"], next_action="Complete and return a cited handoff first.")
                return self._record(request, command, "show_handoff_artifact", "WAITING_FOR_INPUT", response)
            response = self._response(understood_objective="Show the last handoff artifact and its stored evidence references.",
                context={"handoff_id": rows[0]["handoff_id"]}, current_state=rows[0]["state"],
                artifacts=[{"artifact_ref": rows[0]["artifact_ref"], "content_hash": rows[0]["content_hash"], "validated_at": rows[0]["validated_at"]}],
                sources=rows[0]["evidence_refs"], next_action="Validate independently if validated_at is not recorded.")
            return self._record(request, command, "show_handoff_artifact", "APPLIED", response)

        if " research " in lower and company and company.get("research_case_id"):
            agent = self._resolve_agent("research")
            label = company.get("company_name") or company.get("ticker")
            return self._plan(request, command, "research_plan", f"Perform the requested bounded Research Case work for {label}.",
                context, company, agent, f"Charlie research plan — {label}", command)

        return self._record(request, command, "needs_clarification", "WAITING_FOR_INPUT", self._response(
            understood_objective=command, current_state="WAITING_FOR_INPUT",
            missing_data=["a supported action and unambiguous existing entity"],
            next_action="Name an existing company, Research Case, task or agent and the action to take. Nothing was queued."))
