"""Real PostgreSQL ownership/expiry tests; never connect to production.

Run with AI_OS_TEST_PG_DSN='host=/private/tmp/... user=phase2_test dbname=postgres'.
Creates a uniquely named synthetic database; teardown drops only that exact DB.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
from pathlib import Path
import re
import threading
from uuid import uuid4

import pytest

from _ai_os_runtime.api.agent_collaboration import CollaborationAPI
from _ai_os_runtime.api.agent_os_policy import Principal
from _ai_os_runtime.api.agent_charlie import CharlieAPI
from _ai_os_runtime.api.agent_runtime import AgentRuntime, LeaseSession, TaskControl, fence_sql, token_hash
from _ai_os_runtime.api.agent_runtime_api import RuntimeRequestError

SQL_ROOT = Path(__file__).resolve().parents[1] / "postgres" / "init"


@pytest.fixture(scope="module")
def database():
    dsn = os.environ.get("AI_OS_TEST_PG_DSN")
    if not dsn:
        pytest.skip("isolated PostgreSQL DSN not configured")
    psycopg = pytest.importorskip("psycopg")
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    from psycopg import sql
    settings = conninfo_to_dict(dsn)
    if not settings.get("host", "").startswith("/private/tmp/aios-phase2-pg.") or settings.get("user") != "phase2_test":
        pytest.fail("refusing non-synthetic PostgreSQL target")
    dbname = "phase2_test_" + uuid4().hex
    admin = psycopg.connect(dsn, autocommit=True)
    admin.execute(sql.SQL("CREATE DATABASE {} ENCODING 'UTF8' TEMPLATE template0").format(sql.Identifier(dbname)))
    test_dsn = make_conninfo(dsn, dbname=dbname)

    def execute(statement: str):
        with psycopg.connect(test_dsn, autocommit=True) as conn:
            cursor = conn.execute(statement)
            value = None
            while True:
                if cursor.description:
                    value = cursor.fetchone()[0]
                if not cursor.nextset():
                    break
            if isinstance(value, (dict, list)):
                return json.dumps(value, default=str)
            return str(value).lower() if isinstance(value, bool) else str(value) if value is not None else ""

    execute("CREATE SCHEMA agent")
    # Use original checked-in DDL, not an invented replacement task schema.
    for filename, table in [("002_intelligence_os.sql","model_routes"), ("007_agent_profiles.sql","profiles"),
                            ("002_intelligence_os.sql","tasks"), ("002_intelligence_os.sql","approvals")]:
        source = (SQL_ROOT / filename).read_text()
        ddl = re.search(rf"CREATE TABLE IF NOT EXISTS agent\.{table} \([\s\S]*?\n\);", source)
        assert ddl
        execute(ddl.group())
    execute("ALTER TABLE agent.profiles ADD COLUMN display_title text")
    # Minimal canonical collaboration dependencies. The production migration
    # extends these installed tables; it does not replace them.
    execute("CREATE TABLE agent.skills(skill_key text PRIMARY KEY)")
    execute("""CREATE TABLE agent.mailboxes(
        mailbox_key text PRIMARY KEY, agent_name text NOT NULL REFERENCES agent.profiles(agent_name),
        display_name text NOT NULL, channel_type text NOT NULL DEFAULT 'internal_email',
        address text NOT NULL UNIQUE, purpose text NOT NULL, status text NOT NULL DEFAULT 'active',
        notification_policy jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now())""")
    execute("""CREATE TABLE agent.agent_messages(
        id bigserial PRIMARY KEY, thread_key text NOT NULL, from_agent text REFERENCES agent.profiles(agent_name),
        to_agent text REFERENCES agent.profiles(agent_name), subject text NOT NULL, body text NOT NULL,
        priority text NOT NULL DEFAULT 'medium', status text NOT NULL DEFAULT 'unread',
        related_task_id bigint REFERENCES agent.tasks(id), related_skill_key text REFERENCES agent.skills(skill_key),
        metadata jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now(), read_at timestamptz)""")
    execute("""CREATE TABLE agent.committee_registry(
        committee_key text PRIMARY KEY, committee_name text NOT NULL)""")
    execute("""CREATE TABLE agent.committee_packets(
        id bigserial PRIMARY KEY, packet_key text NOT NULL UNIQUE,
        committee_key text NOT NULL REFERENCES agent.committee_registry(committee_key),
        title text NOT NULL, decision_question text NOT NULL,
        packet_status text NOT NULL DEFAULT 'collecting_positions', evidence jsonb NOT NULL DEFAULT '[]',
        metadata jsonb NOT NULL DEFAULT '{}', opened_by text NOT NULL,
        opened_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now())""")
    execute("CREATE SCHEMA research")
    execute("""CREATE TABLE research.companies(
        id bigserial PRIMARY KEY, company_key text NOT NULL UNIQUE, legal_name text NOT NULL,
        display_name text, primary_symbol text NOT NULL, primary_exchange text NOT NULL,
        status text NOT NULL DEFAULT 'active', created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now(), UNIQUE(primary_exchange,primary_symbol))""")
    execute("""CREATE TABLE research.research_cases(
        id bigserial PRIMARY KEY, case_key text NOT NULL UNIQUE, request_text text NOT NULL DEFAULT 'synthetic',
        company_id bigint REFERENCES research.companies(id), company_name text, ticker text, exchange text,
        status text NOT NULL DEFAULT 'active', updated_at timestamptz NOT NULL DEFAULT now())""")
    execute("""CREATE TABLE research.research_case_evidence(
        id bigserial PRIMARY KEY,research_case_id bigint NOT NULL REFERENCES research.research_cases(id),
        source_kind text NOT NULL,source_identifier text NOT NULL,source_url text,local_artifact_path text,
        publication_date date,effective_date date,captured_at timestamptz NOT NULL DEFAULT now(),
        parser_status text NOT NULL DEFAULT 'pending',validation_status text NOT NULL DEFAULT 'pending',
        citation_locator jsonb NOT NULL DEFAULT '{}')""")
    execute("""CREATE TABLE research.research_case_blockers(
        id bigserial PRIMARY KEY,research_case_id bigint NOT NULL REFERENCES research.research_cases(id),
        blocker_key text NOT NULL,stage_key text NOT NULL,title text NOT NULL,detail text NOT NULL,
        system_action text,user_action text,status text NOT NULL DEFAULT 'open',severity text NOT NULL DEFAULT 'high',
        retry_count integer NOT NULL DEFAULT 0,next_retry_at timestamptz,updated_at timestamptz NOT NULL DEFAULT now())""")
    migration = (SQL_ROOT / "256_agent_runtime_leases_v1.sql").read_text()
    execute(migration)
    # Reapply proves non-destructive migration idempotence.
    execute(migration)
    for name in ("257_agent_runtime_policy_events_v1.sql", "258_agent_conversations_handoffs_v1.sql", "261_charlie_chief_of_staff_v1.sql"):
        extension = (SQL_ROOT / name).read_text()
        execute(extension)
        execute(extension)
    # Production intentionally boots fail-closed. This disposable fixture opts
    # into claim execution explicitly so ownership, fencing, and replay tests
    # exercise the runtime without weakening the installed default.
    execute("UPDATE agent.runtime_settings SET claim_mode='enabled' WHERE singleton")
    assert execute("SELECT claim_mode FROM agent.runtime_settings WHERE singleton") == "enabled"
    yield execute, test_dsn
    assert re.fullmatch(r"phase2_test_[a-f0-9]{32}", dbname)
    admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(dbname)))
    admin.close()


@pytest.fixture
def job(database):
    execute, dsn = database
    name = "Synthetic Analyst " + uuid4().hex
    agent_id = int(execute(f"INSERT INTO agent.profiles(agent_name,department,role_scope) VALUES ('{name}','research','Synthetic tests only') RETURNING id"))
    task_id = int(execute(f"INSERT INTO agent.tasks(title,objective,owner_agent,recovery_policy) VALUES ('Synthetic task','No real research','{name}','idempotent_read') RETURNING id"))
    runtime = AgentRuntime(execute)
    runtime.register()
    return execute, dsn, name, agent_id, task_id, runtime


def expire(execute, lease):
    execute(f"UPDATE agent.task_leases SET expires_at=clock_timestamp()-interval '1 second' WHERE id={lease.claim['lease_id']}")


def test_two_workers_one_owner(job):
    execute, _, name, _, task, runtime = job
    other = AgentRuntime(execute)
    other.register()
    barrier = threading.Barrier(2)
    def claim(worker):
        barrier.wait()
        return worker.claim(task, name)
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        results = list(pool.map(claim, [runtime, other]))
    assert sum(item is not None for item in results) == 1
    assert execute(f"SELECT count(*) FROM agent.task_leases WHERE task_id={task} AND status='ACTIVE'") == "1"


def test_expiry_requeues_read_and_fences_late_worker(job):
    execute, _, name, _, task, runtime = job
    lease = runtime.claim(task, name)
    lease.checkpoint("read", "READING")
    expire(execute, lease)
    result = runtime.reap()
    assert result["requeued"] >= 1
    other = AgentRuntime(execute)
    replacement = other.claim(task, name)
    assert replacement and replacement.claim["attempt"] == 2
    with pytest.raises(Exception, match="lease ownership lost"):
        runtime.heartbeat(lease.claim["lease_id"], lease.token, state="WRITING")
    assert execute(f"SELECT count(*) FROM agent.task_leases WHERE task_id={task} AND status='ACTIVE'") == "1"


def test_expiry_after_side_effect_never_replays(job):
    execute, _, name, _, task, runtime = job
    lease = runtime.claim(task, name)
    lease.checkpoint("write_artifact", "WRITING", side_effect=True)
    expire(execute, lease)
    runtime.reap()
    assert execute(f"SELECT status FROM agent.tasks WHERE id={task}") == "blocked"
    assert AgentRuntime(execute).claim(task, name) is None


def test_committed_output_survives_worker_loss(job):
    execute, _, name, _, task, runtime = job
    lease = runtime.claim(task, name)
    with lease:
        lease.checkpoint("output", "WRITING", side_effect=True)
        execute(fence_sql(f"UPDATE agent.tasks SET status='needs_review',output_note_path='synthetic/output.md' WHERE id={task}"))
    expire(execute, lease)
    runtime.reap()
    assert execute(f"SELECT status FROM agent.tasks WHERE id={task}") == "needs_review"
    assert execute(f"SELECT runtime_state FROM agent.tasks WHERE id={task}") == "WAITING_FOR_APPROVAL"
    assert AgentRuntime(execute).claim(task, name) is None


def test_wrong_owner_token_and_illegal_terminal_heartbeat(job):
    execute, _, name, _, task, runtime = job
    lease = runtime.claim(task, name)
    with pytest.raises(Exception, match="ownership lost"):
        runtime.heartbeat(lease.claim["lease_id"], "x"*64)
    with pytest.raises(Exception, match="terminal"):
        runtime.heartbeat(lease.claim["lease_id"], lease.token, state="COMPLETED")
    with pytest.raises(Exception, match="self-validate"):
        lease.finish("completed", "synthetic-receipt")
    assert token_hash(lease.token) in execute(f"SELECT token_hash FROM agent.task_leases WHERE task_id={task}")
    assert lease.token not in repr(lease)


def test_duplicate_heartbeat_does_not_extend_lease(job):
    execute, _, name, _, task, runtime = job
    lease = runtime.claim(task, name)
    request = str(uuid4())
    first = runtime.heartbeat(lease.claim["lease_id"], lease.token, state="READING", request_key=request)
    duplicate = runtime.heartbeat(lease.claim["lease_id"], lease.token, state="READING", request_key=request)
    assert duplicate["duplicate"] is True
    assert duplicate["expires_at"] == first["expires_at"]
    assert execute(f"SELECT count(*) FROM agent.worker_heartbeats WHERE request_key='{request}'") == "1"


def test_transaction_rollback_releases_claim(job):
    execute, dsn, name, agent, task, runtime = job
    import psycopg
    with psycopg.connect(dsn) as conn:
        conn.execute("SELECT agent.claim_runtime_task(%s,%s,%s,%s,false)", (runtime.worker_id, task, agent, "f"*64))
        conn.rollback()
    assert execute(f"SELECT status FROM agent.tasks WHERE id={task}") == "queued"
    assert AgentRuntime(execute).claim(task, name) is not None


def test_legacy_update_and_managed_write_fence(job):
    execute, _, name, _, task, runtime = job
    execute(f"UPDATE agent.tasks SET evidence='[]'::jsonb WHERE id={task}")
    lease = runtime.claim(task, name)
    with pytest.raises(Exception, match="fenced"):
        execute(f"UPDATE agent.tasks SET status='completed' WHERE id={task}")
    with lease:
        execute(fence_sql(f"UPDATE agent.tasks SET evidence='[]'::jsonb WHERE id={task}"))


def test_dependency_and_approval_gates_preserved(job):
    execute, _, name, _, task, runtime = job
    execute(f"UPDATE agent.tasks SET approval_required=true WHERE id={task}")
    assert runtime.claim(task, name) is None
    execute(f"INSERT INTO agent.approvals(task_id,approval_type,title,owner_agent,status) VALUES({task},'synthetic','Test','{name}','approved')")
    parent = execute(f"INSERT INTO agent.tasks(title,objective,owner_agent) VALUES('Parent','test','{name}') RETURNING id")
    execute(f"INSERT INTO agent.task_dependencies VALUES({task},{parent})")
    assert runtime.claim(task, name) is None
    execute(f"UPDATE agent.tasks SET status='completed' WHERE id={parent}")
    assert runtime.claim(task, name) is not None


def test_pause_at_boundary_and_resume(job):
    from _ai_os_runtime.api.agent_runtime import TaskControl
    execute, _, name, _, task, runtime = job
    lease = runtime.claim(task, name)
    runtime.control(task, "pause")
    with pytest.raises(TaskControl):
        lease.checkpoint("read", "READING")
    assert execute(f"SELECT status FROM agent.tasks WHERE id={task}") == "paused"
    runtime.control(task, "resume")
    assert execute(f"SELECT status FROM agent.tasks WHERE id={task}") == "queued"
    assert AgentRuntime(execute).claim(task, name) is not None


def test_identity_immutable_and_presence_never_faked(job):
    execute, _, name, agent, task, runtime = job
    key = execute(f"SELECT agent_key FROM agent.profiles WHERE id={agent}")
    execute(f"UPDATE agent.profiles SET display_title='Renamed title' WHERE id={agent}")
    assert execute(f"SELECT agent_key FROM agent.profiles WHERE id={agent}") == key
    with pytest.raises(Exception, match="immutable"):
        execute(f"UPDATE agent.profiles SET agent_key='different' WHERE id={agent}")
    assert execute(f"SELECT has_live_lease FROM agent.v_runtime_presence WHERE agent_id={agent}") == "false"
    lease = runtime.claim(task, name)
    assert execute(f"SELECT has_live_lease FROM agent.v_runtime_presence WHERE agent_id={agent}") == "true"
    expire(execute, lease)
    assert execute(f"SELECT state FROM agent.v_runtime_presence WHERE agent_id={agent}") == "STALE"


def test_event_immutability(job):
    execute, _, name, _, task, runtime = job
    runtime.claim(task, name)
    with pytest.raises(Exception, match="append-only"):
        execute(f"UPDATE agent.task_events SET state='COMPLETED' WHERE task_id={task}")
    assert execute(f"SELECT count(*) FROM agent.task_events WHERE task_id={task}") == "1"


def test_worker_and_agent_parallelism_caps(job):
    execute, _, name, agent, task, runtime = job
    runtime.claim(task, name)
    second_task = int(execute(f"INSERT INTO agent.tasks(title,objective,owner_agent) VALUES('Second','test','{name}') RETURNING id"))
    assert runtime.claim(second_task, name) is None
    assert AgentRuntime(execute).claim(second_task, name) is None


def test_scoped_threads_messages_receipts_and_deduplication(job):
    execute, _, name, agent, task, runtime = job
    api = CollaborationAPI(execute, Principal(user_id="operator_test", agent_id=agent))
    key = "case:synthetic:thread"
    created = api.create_thread({"thread_key": key, "room_type": "case", "title": "Synthetic case"})
    assert created["created"] is True
    assert api.create_thread({"thread_key": key, "room_type": "case", "title": "Synthetic case"})["created"] is False
    sent = api.send_message(key, {
        "request_key": "message:test:0001", "subject": "Source check", "body": "Check the stored source packet.",
        "related_task_id": task, "attachments": [{"table": "research.corporate_filings", "id": 11}],
    })
    assert sent["created"] is True
    assert sent["delivery_is_completion"] is False
    duplicate = api.send_message(key, {
        "request_key": "message:test:0001", "subject": "Source check", "body": "Check the stored source packet.",
        "related_task_id": task, "attachments": [{"table": "research.corporate_filings", "id": 11}],
    })
    assert duplicate["created"] is False
    with pytest.raises(RuntimeRequestError, match="idempotency"):
        api.send_message(key, {"request_key": "message:test:0001", "body": "Different work."})
    receipt = api.acknowledge(sent["message"]["id"])
    assert receipt["receipt"]["acknowledged_at"]
    messages = api.messages(key)
    assert messages["cursor"] == sent["message"]["id"]
    assert messages["messages"][0]["attachments"][0]["id"] == 11
    with pytest.raises(RuntimeRequestError, match="Credential-like"):
        api.send_message(key, {"request_key": "message:test:0002", "body": "api_key=sk-this-must-not-be-stored"})
    assert execute("SELECT count(*) FROM agent.task_events WHERE event_type IN ('thread_created','message_sent','message_acknowledged')") == "3"


def test_client_scope_is_not_visible_to_shared_office(job):
    execute, _, _, _, _, _ = job
    client_api = CollaborationAPI(execute, Principal(user_id="client_operator", scope="internal", clients=(91,)))
    client_api.create_thread({
        "thread_key": "client:91:private", "room_type": "client", "title": "Private client room",
        "client_id": 91, "data_class": "client_private",
    })
    shared = CollaborationAPI(execute, Principal(user_id="shared_operator"))
    assert all(row["thread_key"] != "client:91:private" for row in shared.threads()["threads"])
    with pytest.raises(RuntimeRequestError, match="not found"):
        shared.messages("client:91:private")


def test_handoff_requires_live_owner_cited_receipt_and_independent_validation(job):
    execute, _, sender_name, sender, parent_task, parent_runtime = job
    parent_lease = parent_runtime.claim(parent_task, sender_name)
    assert parent_lease
    recipient_name = "Synthetic Recipient " + uuid4().hex
    recipient = int(execute(f"INSERT INTO agent.profiles(agent_name,department,role_scope) VALUES ('{recipient_name}','research','Synthetic handoff only') RETURNING id"))
    execute(f"UPDATE agent.agent_workspaces SET allowed_task_classes=ARRAY['general','handoff'] WHERE agent_id={recipient}")
    sender_api = CollaborationAPI(execute, Principal(user_id="sender_test", agent_id=sender))
    recipient_api = CollaborationAPI(execute, Principal(user_id="recipient_test", agent_id=recipient))
    thread = "handoff:test:thread"
    sender_api.create_thread({"thread_key": thread, "room_type": "direct", "title": "Handoff test"})
    handoff = sender_api.create_handoff({
        "request_key": "handoff:test:0001", "thread_key": thread, "from_agent_id": sender,
        "to_agent_id": recipient, "parent_task_id": parent_task,
        "question": "Return a bounded source assessment with cited evidence.",
        "evidence_refs": [{"table": "research.corporate_filings", "id": 21}],
    })
    assert handoff["state"] == "REQUESTED"
    assert sender_api.create_handoff({
        "request_key": "handoff:test:0001", "thread_key": thread, "from_agent_id": sender,
        "to_agent_id": recipient, "parent_task_id": parent_task,
        "question": "Return a bounded source assessment with cited evidence.",
        "evidence_refs": [{"table": "research.corporate_filings", "id": 21}],
    })["duplicate"] is True
    recipient_api.advance_handoff(handoff["handoff_id"], "acknowledge")
    recipient_api.advance_handoff(handoff["handoff_id"], "accept")
    worker = AgentRuntime(execute, supported_task_classes=("general", "handoff"))
    child_lease = worker.claim(handoff["child_task_id"], recipient_name)
    assert child_lease
    recipient_api.advance_handoff(handoff["handoff_id"], "start")
    step = child_lease.checkpoint("source_assessment", "WRITING", side_effect=True)
    output = child_lease.runtime._call(
        "record_runtime_receipt", child_lease.runtime.worker_id, child_lease.claim["lease_id"], token_hash(child_lease.token),
        step["step_id"], "handoff-output", "artifacts/synthetic-handoff.json", "a" * 64,
        json.dumps([{"table": "research.corporate_filings", "id": 21}]),
    )
    child_lease.finish("needs_review", f"runtime_receipt:{output['receipt_id']}")
    recipient_api.advance_handoff(handoff["handoff_id"], "return", {"receipt_id": output["receipt_id"]})
    with pytest.raises(RuntimeRequestError, match="requirement"):
        recipient_api.advance_handoff(handoff["handoff_id"], "validate", {"receipt_id": output["receipt_id"], "note": "Self approval"})
    validated = sender_api.advance_handoff(handoff["handoff_id"], "validate", {
        "receipt_id": output["receipt_id"], "note": "Evidence locator and bounded output independently checked."
    })
    assert validated["state"] == "VALIDATED"
    assert validated["research_readiness_changed"] is False
    assert execute(f"SELECT status FROM agent.tasks WHERE id={handoff['child_task_id']}") == "completed"
    assert execute(f"SELECT count(*) FROM agent.task_dependencies WHERE task_id={parent_task} AND depends_on_task_id={handoff['child_task_id']}") == "1"


def test_charlie_exact_commands_create_durable_work_and_report_truth(job):
    execute, _, _, _, _, _ = job
    names = {
        "Forensic Accounting Agent": "research", "Valuation Agent": "research", "Industry Analyst": "research",
        "Risk Agent": "risk", "Portfolio Manager": "portfolio", "Research Director": "research",
    }
    ids = {}
    for name, department in names.items():
        ids[name] = int(execute(f"INSERT INTO agent.profiles(agent_name,department,role_scope) VALUES ('{name}','{department}','Synthetic exact-command test') RETURNING id"))
        execute(f"UPDATE agent.agent_workspaces SET allowed_task_classes=ARRAY['general','research','handoff','committee'] WHERE agent_id={ids[name]}")
    wipro = int(execute("""INSERT INTO research.companies(company_key,legal_name,display_name,primary_symbol,primary_exchange)
        VALUES('nse_wipro','Wipro Limited','Wipro','WIPRO','NSE') RETURNING id"""))
    wipro_case = int(execute(f"""INSERT INTO research.research_cases(case_key,company_id,company_name,ticker,exchange,status)
        VALUES('case-wipro',{wipro},'Wipro','WIPRO','NSE','active') RETURNING id"""))
    shivalik = int(execute("""INSERT INTO research.companies(company_key,legal_name,display_name,primary_symbol,primary_exchange)
        VALUES('nse_sbcl','Shivalik Bimetal Controls Limited','Shivalik Bimetal','SBCL','NSE') RETURNING id"""))
    shivalik_case = int(execute(f"""INSERT INTO research.research_cases(case_key,company_id,company_name,ticker,exchange,status)
        VALUES('case-shivalik',{shivalik},'Shivalik Bimetal','SBCL','NSE','active') RETURNING id"""))
    execute("INSERT INTO agent.committee_registry(committee_key,committee_name) VALUES('long_term','Long-term committee')")
    packet = int(execute("""INSERT INTO agent.committee_packets(packet_key,committee_key,title,decision_question,opened_by)
        VALUES('wipro-test-packet','long_term','Wipro committee','What evidence remains?','test') RETURNING id"""))
    evidence = int(execute(f"""INSERT INTO research.research_case_evidence(
        research_case_id,source_kind,source_identifier,source_url,local_artifact_path,publication_date,
        parser_status,validation_status,citation_locator)
        VALUES({wipro_case},'annual_report','wipro-fy26','https://example.invalid/wipro-fy26',
        'artifacts/wipro/fy26.pdf','2026-06-30','parsed','validated','{{"page":84}}') RETURNING id"""))
    blocker = int(execute(f"""INSERT INTO research.research_case_blockers(
        research_case_id,blocker_key,stage_key,title,detail,system_action,user_action,severity)
        VALUES({wipro_case},'cash_conversion_denominator','financials','Cash conversion denominator missing',
        'CFO and PAT periods are not aligned.','Re-extract audited statements.',NULL,'high') RETURNING id"""))
    charlie = CharlieAPI(execute, Principal(user_id="charlie_operator"))

    status = charlie.command({"request_key": "charlie:test:live", "command": "Charlie, show every live agent and what each is doing.", "context": {}})
    assert status["current_state"] == "OBSERVED"
    assert status["broker_write_allowed"] is False

    repair = charlie.command({
        "request_key": "charlie:test:repair",
        "command": "Charlie, review Wipro's current evidence debt and create a bounded repair plan. Use no paid model without approval.",
        "context": {},
    })
    assert repair["current_state"] == "QUEUED"
    assert len(repair["tasks"]) == 4
    assert repair["sources"][0]["evidence_id"] == evidence
    assert f"high:Cash conversion denominator missing" in repair["risk_flags"]
    assert execute(f"SELECT count(*) FROM agent.task_dependencies WHERE task_id={repair['tasks'][0]['task_id']}") == "3"
    assert execute(f"SELECT missing_data @> '[]'::jsonb FROM agent.plans WHERE id={repair['plan_id']}") == "true"
    assert execute(f"SELECT bool_and(runtime_context->>'paid_model_work_paused'='true') FROM agent.tasks WHERE id IN ({','.join(str(row['task_id']) for row in repair['tasks'])})") == "true"

    delegated = charlie.command({"request_key": "charlie:test:forensic", "command": "Charlie, ask the Forensic Analyst why Wipro cash conversion weakened and show the exact source packet.", "context": {}})
    assert delegated["current_state"] == "QUEUED"
    assert delegated["tasks"][0]["completion"] is False
    assert delegated["sources"][0]["evidence_id"] == evidence
    assert delegated["sources"][0]["citation_locator"] == {"page": 84}
    forensic_task = delegated["tasks"][0]["task_id"]
    assert execute(f"SELECT count(*) FROM agent.plan_tasks WHERE task_id={forensic_task}") == "1"
    assert execute(f"SELECT runtime_context->>'research_case_id' FROM agent.tasks WHERE id={forensic_task}") == str(wipro_case)

    paid = charlie.command({"request_key": "charlie:test:paid", "command": "Charlie, stop all paid-model calls for this case.", "context": {"research_case_id": wipro_case}})
    assert paid["current_state"] == "PAID_MODEL_WORK_STOPPED"
    assert execute(f"SELECT runtime_context->>'paid_model_work_paused' FROM agent.tasks WHERE id={forensic_task}") == "true"

    valuation_task = int(execute(f"""INSERT INTO agent.tasks(title,objective,owner_agent,agent_id,runtime_protocol,runtime_state,task_class,recovery_policy)
        VALUES('Valuation test','Review valuation','Valuation Agent',{ids['Valuation Agent']},'lease_v1','PLANNING','research','idempotent_read') RETURNING id"""))
    valuation_runtime = AgentRuntime(execute, supported_task_classes=("general", "research"))
    valuation_lease = valuation_runtime.claim(valuation_task, "Valuation Agent")
    assert valuation_lease
    paused = charlie.command({"request_key": "charlie:test:pause", "command": "Charlie, pause the Valuation Analyst.", "context": {"task_id": valuation_task}})
    assert paused["current_state"] == "PAUSE_REQUESTED"
    with pytest.raises(TaskControl, match="pause"):
        valuation_lease.checkpoint("safe_point", "ANALYZING")
    assert execute(f"SELECT status FROM agent.tasks WHERE id={valuation_task}") == "paused"
    resumed = charlie.command({"request_key": "charlie:test:resume", "command": "Charlie, resume that task with primary sources only.", "context": {"task_id": valuation_task}})
    assert resumed["current_state"] == "QUEUED"
    assert execute(f"SELECT runtime_context->>'source_policy' FROM agent.tasks WHERE id={valuation_task}") == "primary_only"

    industry_task = int(execute(f"""INSERT INTO agent.tasks(title,objective,owner_agent,agent_id,runtime_protocol,runtime_state,task_class,recovery_policy,runtime_context)
        VALUES('Industry test','Old peer objective','Industry Analyst',{ids['Industry Analyst']},'lease_v1','PLANNING','research','idempotent_read',
        '{{"research_case_id":{shivalik_case}}}'::jsonb) RETURNING id"""))
    redirected = charlie.command({"request_key": "charlie:test:redirect", "command": "Charlie, redirect the Industry Analyst to compare Shivalik with its closest listed peers.", "context": {"task_id": industry_task}})
    assert redirected["current_state"] == "REDIRECTED"
    assert "closest listed peers" in execute(f"SELECT objective FROM agent.tasks WHERE id={industry_task}")

    invited = charlie.command({"request_key": "charlie:test:invite", "command": "Charlie, invite Risk and Portfolio to the Wipro committee.", "context": {}})
    assert invited["current_state"] == "INVITED"
    assert execute(f"SELECT count(*) FROM agent.committee_invitations WHERE packet_id={packet}") == "2"
    event_count = execute("SELECT count(*) FROM agent.task_events WHERE event_type='committee_invited'")
    assert charlie.command({"request_key": "charlie:test:invite", "command": "Charlie, invite Risk and Portfolio to the Wipro committee.", "context": {}}) == invited
    assert execute(f"SELECT count(*) FROM agent.committee_invitations WHERE packet_id={packet}") == "2"
    assert execute("SELECT count(*) FROM agent.task_events WHERE event_type='committee_invited'") == event_count
    with pytest.raises(RuntimeRequestError, match="different command"):
        charlie.command({"request_key": "charlie:test:invite", "command": "Charlie, invite Risk and Portfolio to another committee.", "context": {}})

    routed = charlie.command({"request_key": "charlie:test:routes", "command": "Charlie, use the local research route for routine work and reserve the cloud route for red team.", "context": {}})
    assert routed["current_state"] == "POLICY_RECORDED"
    assert routed["approvals_needed"]
    assert execute("SELECT public_cloud_requires_approval FROM agent.charlie_route_policies LIMIT 1") == "true"

    with pytest.raises(RuntimeRequestError, match="not handled"):
        charlie.command({"request_key": "charlie:test:unknown", "command": "Please do something helpful.", "context": {}})
    assert execute("SELECT count(*) FROM agent.tasks WHERE source_ref='charlie:test:unknown'") == "0"
    assert execute("SELECT count(*) FROM agent.charlie_commands") == "9"


def test_charlie_active_redirect_waits_for_safe_boundary(job):
    execute, _, _, _, _, _ = job
    agent_id = int(execute("INSERT INTO agent.profiles(agent_name,department,role_scope) VALUES('Boundary Industry Analyst','research','Synthetic redirect boundary') RETURNING id"))
    execute(f"UPDATE agent.agent_workspaces SET allowed_task_classes=ARRAY['general','research'] WHERE agent_id={agent_id}")
    task = int(execute(f"""INSERT INTO agent.tasks(title,objective,owner_agent,agent_id,runtime_protocol,runtime_state,task_class,recovery_policy)
        VALUES('Boundary redirect','Old objective','Boundary Industry Analyst',{agent_id},'lease_v1','PLANNING','research','idempotent_read') RETURNING id"""))
    lease = AgentRuntime(execute, supported_task_classes=("general", "research")).claim(task, "Boundary Industry Analyst")
    assert lease
    result = json.loads(execute(f"SELECT agent.redirect_runtime_task({task},'boundary_test','New objective','{{}}')::text"))
    assert result["waiting_for_safe_boundary"] is True
    assert execute(f"SELECT objective FROM agent.tasks WHERE id={task}") == "Old objective"
    with pytest.raises(TaskControl):
        lease.checkpoint("redirect_boundary", "ANALYZING")
    applied = json.loads(execute(f"SELECT agent.apply_pending_runtime_redirect({task},'boundary_test')::text"))
    assert applied["applied"] is True
    assert execute(f"SELECT objective FROM agent.tasks WHERE id={task}") == "New objective"
