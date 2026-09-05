"""Deterministic, provider-free Phase 2 runtime stress acceptance harness.

This is intentionally a manual acceptance test, not part of the default pytest
suite. It creates one uniquely named database on a disposable PostgreSQL cluster,
exercises the canonical lease/event functions, prints a JSON receipt, and drops
only that database.

Run from the repository root with::

    AI_OS_TEST_PG_DSN='host=/private/tmp/aios-phase2-pg.X port=55439 user=phase2_test dbname=postgres' \
      python -m _ai_os_runtime.tests.phase2_runtime_stress

No model, provider, network, filesystem-artifact, research, or broker call is
made by this harness.
"""
from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5


SQL_ROOT = Path(__file__).resolve().parents[1] / "postgres" / "init"
AGENT_COUNT = 100
WORKER_COUNT = 4
TASK_COUNT = 1_000
STEPS_PER_TASK = 8
EXPECTED_EVENT_COUNT = TASK_COUNT * (STEPS_PER_TASK + 2)
RECONNECT_CHECKS = 100
DATABASE_PATTERN = re.compile(r"phase2_stress_[0-9a-f]{32}")
SOCKET_PATTERN = re.compile(r"aios-phase2-pg\.[A-Za-z0-9_-]{1,80}")
APPLIED_MIGRATIONS = (
    "256_agent_runtime_leases_v1.sql",
    "257_agent_runtime_policy_events_v1.sql",
    "258_agent_conversations_handoffs_v1.sql",
    "259_agent_model_fabric_v1.sql",
    "261_charlie_chief_of_staff_v1.sql",
)
PINNED_MIGRATIONS = APPLIED_MIGRATIONS[:-1] + (
    "260_ai_os_doctor_and_routines_v1.sql",
    APPLIED_MIGRATIONS[-1],
)
STEP_STATES = (
    "PLANNING",
    "READING",
    "PARSING",
    "EXTRACTING",
    "CALCULATING",
    "ANALYZING",
    "WRITING",
    "VALIDATING",
)


class StressRefusal(RuntimeError):
    """The requested target is not a disposable Phase 2 PostgreSQL cluster."""


@dataclass(frozen=True)
class TaskRow:
    index: int
    task_id: int
    agent_id: int
    agent_name: str


def _require_psycopg():
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - environment gate
        raise StressRefusal("psycopg is required in the isolated test runtime") from exc
    return psycopg


def validate_admin_dsn(dsn: str) -> dict[str, str]:
    """Accept only the named user/database on a private-tmp Unix socket."""
    if not isinstance(dsn, str) or not dsn.strip() or len(dsn) > 2_048:
        raise StressRefusal("AI_OS_TEST_PG_DSN must be a bounded synthetic DSN")
    _require_psycopg()
    from psycopg.conninfo import conninfo_to_dict

    try:
        settings = conninfo_to_dict(dsn)
    except Exception as exc:
        raise StressRefusal("AI_OS_TEST_PG_DSN is not valid PostgreSQL conninfo") from exc
    host = settings.get("host", "")
    host_path = Path(host)
    if (
        settings.get("user") != "phase2_test"
        or settings.get("dbname") != "postgres"
        or settings.get("hostaddr")
        or settings.get("password")
        or host_path.parent != Path("/private/tmp")
        or not SOCKET_PATTERN.fullmatch(host_path.name)
        or (host_path.exists() and (not host_path.is_dir() or host_path.is_symlink()))
    ):
        raise StressRefusal(
            "refusing non-disposable PostgreSQL target; require phase2_test@postgres "
            "on /private/tmp/aios-phase2-pg.* without TCP or a password"
        )
    return settings


def _assert_private_test_server(connection: Any, socket_path: str) -> None:
    row = connection.execute(
        "SELECT current_user,current_database(),current_setting('data_directory')"
    ).fetchone()
    socket_root = Path(socket_path).resolve()
    current_user = os.fsdecode(row[0])
    current_database = os.fsdecode(row[1])
    data_directory = Path(os.fsdecode(row[2])).resolve()
    if (
        current_user != "phase2_test"
        or current_database != "postgres"
        or data_directory.parent != socket_root
        or data_directory.name != "data"
    ):
        raise StressRefusal("connected server is not the expected private-tmp test cluster")


def _ddl(filename: str, table: str) -> str:
    source = (SQL_ROOT / filename).read_text(encoding="utf-8")
    match = re.search(
        rf"CREATE TABLE IF NOT EXISTS agent\.{re.escape(table)} \([\s\S]*?\n\);",
        source,
    )
    if not match:
        raise AssertionError(f"canonical DDL not found for agent.{table}")
    return match.group()


def _run_script(connection: Any, statement: str) -> None:
    cursor = connection.execute(statement)
    while cursor.nextset():
        pass


def _bootstrap(connection: Any) -> dict[str, str]:
    """Install the smallest canonical substrate needed by migrations 256-261."""
    connection.execute("CREATE SCHEMA agent")
    for filename, table in (
        ("002_intelligence_os.sql", "model_routes"),
        ("007_agent_profiles.sql", "profiles"),
        ("002_intelligence_os.sql", "tasks"),
        ("002_intelligence_os.sql", "approvals"),
        ("002_intelligence_os.sql", "tool_registry"),
    ):
        connection.execute(_ddl(filename, table))
    connection.execute("ALTER TABLE agent.profiles ADD COLUMN display_title text")
    connection.execute("CREATE TABLE agent.skills(skill_key text PRIMARY KEY)")
    connection.execute(
        """CREATE TABLE agent.mailboxes(
        mailbox_key text PRIMARY KEY, agent_name text NOT NULL REFERENCES agent.profiles(agent_name),
        display_name text NOT NULL, channel_type text NOT NULL DEFAULT 'internal_email',
        address text NOT NULL UNIQUE, purpose text NOT NULL, status text NOT NULL DEFAULT 'active',
        notification_policy jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now())"""
    )
    connection.execute(
        """CREATE TABLE agent.agent_messages(
        id bigserial PRIMARY KEY, thread_key text NOT NULL, from_agent text REFERENCES agent.profiles(agent_name),
        to_agent text REFERENCES agent.profiles(agent_name), subject text NOT NULL, body text NOT NULL,
        priority text NOT NULL DEFAULT 'medium', status text NOT NULL DEFAULT 'unread',
        related_task_id bigint REFERENCES agent.tasks(id), related_skill_key text REFERENCES agent.skills(skill_key),
        metadata jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now(), read_at timestamptz)"""
    )
    connection.execute(
        "CREATE TABLE agent.committee_registry(committee_key text PRIMARY KEY,committee_name text NOT NULL)"
    )
    connection.execute(
        """CREATE TABLE agent.committee_packets(
        id bigserial PRIMARY KEY, packet_key text NOT NULL UNIQUE,
        committee_key text NOT NULL REFERENCES agent.committee_registry(committee_key),
        title text NOT NULL, decision_question text NOT NULL,
        packet_status text NOT NULL DEFAULT 'collecting_positions', evidence jsonb NOT NULL DEFAULT '[]',
        metadata jsonb NOT NULL DEFAULT '{}', opened_by text NOT NULL,
        opened_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now())"""
    )
    connection.execute("CREATE SCHEMA research")
    connection.execute(
        """CREATE TABLE research.companies(
        id bigserial PRIMARY KEY, company_key text NOT NULL UNIQUE, legal_name text NOT NULL,
        display_name text, primary_symbol text NOT NULL, primary_exchange text NOT NULL,
        status text NOT NULL DEFAULT 'active', created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now(), UNIQUE(primary_exchange,primary_symbol))"""
    )
    connection.execute(
        """CREATE TABLE research.research_cases(
        id bigserial PRIMARY KEY, case_key text NOT NULL UNIQUE, request_text text NOT NULL DEFAULT 'synthetic',
        company_id bigint REFERENCES research.companies(id), company_name text, ticker text, exchange text,
        status text NOT NULL DEFAULT 'active', updated_at timestamptz NOT NULL DEFAULT now())"""
    )

    fingerprints: dict[str, str] = {}
    for name in PINNED_MIGRATIONS:
        payload = (SQL_ROOT / name).read_bytes()
        fingerprints[name] = hashlib.sha256(payload).hexdigest()
    # Migration 260 owns Doctor/routine dependencies and has its own acceptance
    # harness. This stress database applies the runtime/collaboration/model/Charlie
    # migrations that share the lease/event substrate, twice for replay safety.
    for name in APPLIED_MIGRATIONS:
        statement = (SQL_ROOT / name).read_text(encoding="utf-8")
        _run_script(connection, statement)
        _run_script(connection, statement)
    # Installed environments intentionally remain fail-closed. This disposable
    # provider-free stress database opts into claims explicitly so the test can
    # exercise contention, fencing, replay, and reconnect behavior without
    # weakening the production default.
    connection.execute("UPDATE agent.runtime_settings SET claim_mode='enabled' WHERE singleton")
    if connection.execute("SELECT claim_mode FROM agent.runtime_settings WHERE singleton").fetchone()[0] != "enabled":
        raise AssertionError("disposable stress runtime did not explicitly enable claims")
    return fingerprints


def _json_call(connection: Any, statement: str, params: tuple[Any, ...]) -> dict[str, Any]:
    value = connection.execute(statement, params).fetchone()[0]
    if not isinstance(value, dict):
        raise AssertionError("runtime database response was not a JSON object")
    return value


def _token_hash(database_name: str, worker_id: str, task_id: int) -> str:
    return hashlib.sha256(f"{database_name}:{worker_id}:{task_id}:synthetic".encode()).hexdigest()


def _claim(connection: Any, worker_id: str, task: TaskRow, database_name: str) -> tuple[dict[str, Any], str]:
    token = _token_hash(database_name, worker_id, task.task_id)
    result = _json_call(
        connection,
        "SELECT agent.claim_runtime_task(%s,%s,%s,%s,false)",
        (worker_id, task.task_id, task.agent_id, token),
    )
    return result, token


def _exercise_claim(
    connection: Any,
    worker_id: str,
    task: TaskRow,
    claim: dict[str, Any],
    token: str,
    *,
    release: bool,
) -> dict[str, Any] | None:
    if not claim or claim.get("broker_write_allowed") is not False:
        raise AssertionError(f"task {task.task_id} was not safely claimed")
    lease_id = int(claim["lease_id"])
    for step_number, state in enumerate(STEP_STATES, start=1):
        result = _json_call(
            connection,
            "SELECT agent.record_runtime_step(%s,%s,%s,%s,%s,false)",
            (worker_id, lease_id, token, f"stress_{step_number}", state),
        )
        if result.get("side_effect_status") != "none":
            raise AssertionError("synthetic stress step unexpectedly recorded a side effect")
    if not release:
        return {"task": task, "worker_id": worker_id, "lease_id": lease_id}
    finished = _json_call(
        connection,
        "SELECT agent.finish_runtime_lease(%s,%s,%s,'needs_review',%s)",
        (worker_id, lease_id, token, f"synthetic-stress:{task.task_id}"),
    )
    if finished.get("broker_write_allowed") is not False or finished.get("lease_status") != "RELEASED":
        raise AssertionError("lease did not finish through the safe runtime contract")
    return None


def _seed(connection: Any) -> list[TaskRow]:
    connection.execute(
        """INSERT INTO agent.profiles(agent_name,department,role_scope,max_parallel_tasks)
        SELECT 'Stress Agent '||lpad(value::text,3,'0'),'research','Synthetic lease/event acceptance only',1
        FROM generate_series(0,%s) value""",
        (AGENT_COUNT - 1,),
    )
    connection.execute(
        """INSERT INTO agent.tasks(
          title,objective,owner_agent,status,priority,source_kind,source_ref,agent_id,
          runtime_protocol,runtime_state,task_class,recovery_policy,runtime_scope,data_class,runtime_context)
        SELECT 'Stress task '||value,'Synthetic read-only state transition',profile.agent_name,
          'queued','normal','phase2_runtime_stress','stress:'||value,profile.id,
          'lease_v1','PLANNING','general','idempotent_read','internal','internal',
          jsonb_build_object('synthetic',true,'stress_index',value)
        FROM generate_series(0,%s) value
        JOIN agent.profiles profile ON profile.agent_name='Stress Agent '||lpad((value%%%s)::text,3,'0')""",
        (TASK_COUNT - 1, AGENT_COUNT),
    )
    rows = connection.execute(
        """SELECT (task.runtime_context->>'stress_index')::integer,task.id,task.agent_id,profile.agent_name
        FROM agent.tasks task JOIN agent.profiles profile ON profile.id=task.agent_id
        WHERE task.source_kind='phase2_runtime_stress' ORDER BY 1"""
    ).fetchall()
    tasks = [TaskRow(*row) for row in rows]
    if len(tasks) != TASK_COUNT:
        raise AssertionError("synthetic task seed count is not exact")
    return tasks


def _register_workers(connection_factory: Any, database_name: str) -> tuple[list[Any], list[str]]:
    connections: list[Any] = []
    workers: list[str] = []
    for index in range(WORKER_COUNT):
        connection = connection_factory()
        worker_id = str(uuid5(NAMESPACE_URL, f"{database_name}:worker:{index}"))
        registered = _json_call(
            connection,
            "SELECT agent.register_runtime_worker(%s,%s,%s,'stress-v1',1)",
            (worker_id, f"phase2-stress-worker-{index}", 9_001 + index),
        )
        configured = _json_call(
            connection,
            "SELECT agent.configure_runtime_worker(%s,%s,%s)",
            (worker_id, ["general"], ["postgres.synthetic_read"]),
        )
        if registered.get("broker_write_allowed") is not False or configured.get("broker_write_allowed") is not False:
            raise AssertionError("worker registration violated the broker-write lock")
        connections.append(connection)
        workers.append(worker_id)
    return connections, workers


def _assert_active_caps(connection: Any) -> dict[str, int]:
    active = connection.execute(
        """SELECT count(*)::integer,
        coalesce((SELECT max(value) FROM (
          SELECT count(*) value FROM agent.task_leases
          WHERE status='ACTIVE' GROUP BY worker_id
        ) grouped),0)::integer,
        coalesce((SELECT max(value) FROM (
          SELECT count(*) value FROM agent.task_leases
          WHERE status='ACTIVE' GROUP BY agent_id
        ) grouped),0)::integer
        FROM agent.task_leases WHERE status='ACTIVE'"""
    ).fetchone()
    result = {"total": active[0], "per_worker": active[1], "per_agent": active[2]}
    if result != {"total": WORKER_COUNT, "per_worker": 1, "per_agent": 1}:
        raise AssertionError(f"active lease caps were not observed exactly: {result}")
    return result


def _replay_checks(test_dsn: str, event_ids: list[int]) -> dict[str, Any]:
    psycopg = _require_psycopg()
    page_size = 37
    upper = len(event_ids) - page_size - 1
    if upper < 1:
        raise AssertionError("insufficient events for cursor replay")
    for check in range(RECONNECT_CHECKS):
        position = (check * 97) % upper
        cursor = event_ids[position]
        expected = event_ids[position + 1 : position + 1 + page_size]
        with psycopg.connect(test_dsn, autocommit=True) as reconnect:
            actual = [
                row[0]
                for row in reconnect.execute(
                    """SELECT event.id FROM agent.task_events event
                    JOIN agent.tasks task ON task.id=event.task_id
                    WHERE task.source_kind='phase2_runtime_stress' AND event.id>%s
                    ORDER BY event.id LIMIT %s""",
                    (cursor, page_size),
                ).fetchall()
            ]
        if actual != expected or len(actual) != len(set(actual)):
            raise AssertionError(f"cursor replay mismatch at reconnect {check}")
    return {"checks": RECONNECT_CHECKS, "page_size": page_size, "authority": "postgres"}


def _verify(connection: Any, test_dsn: str, stale: dict[str, Any], peak: dict[str, int]) -> dict[str, Any]:
    task = stale["task"]
    connection.execute(
        "UPDATE agent.task_leases SET expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
        (stale["lease_id"],),
    )
    connection.execute(
        "UPDATE agent.workers SET last_heartbeat_at=clock_timestamp()-interval '181 seconds' WHERE id=%s",
        (stale["worker_id"],),
    )
    stale_presence = connection.execute(
        "SELECT state,has_live_lease,broker_write_allowed FROM agent.v_runtime_presence WHERE agent_id=%s",
        (task.agent_id,),
    ).fetchone()
    if stale_presence != ("STALE", False, False):
        raise AssertionError(f"expired lease was not truthfully stale: {stale_presence}")
    reaped = _json_call(connection, "SELECT agent.reap_runtime_leases(100)", ())
    if reaped != {"expired": 1, "requeued": 1, "blocked": 0, "broker_write_allowed": False}:
        raise AssertionError(f"unexpected expiry reconciliation: {reaped}")

    lease_counts = connection.execute(
        """SELECT count(*)::integer,count(DISTINCT task_id)::integer,max(attempt)::integer,
        count(*) FILTER(WHERE status='RELEASED')::integer,
        count(*) FILTER(WHERE status='EXPIRED')::integer,
        count(*) FILTER(WHERE status='ACTIVE')::integer
        FROM agent.task_leases"""
    ).fetchone()
    if lease_counts != (TASK_COUNT, TASK_COUNT, 1, TASK_COUNT - 1, 1, 0):
        raise AssertionError(f"lease ownership was not exactly once: {lease_counts}")
    duplicate_ownership = connection.execute(
        "SELECT count(*) FROM (SELECT task_id FROM agent.task_leases GROUP BY task_id HAVING count(*)<>1) value"
    ).fetchone()[0]
    if duplicate_ownership:
        raise AssertionError("duplicate task ownership detected")

    event_counts = dict(
        connection.execute(
            """SELECT event.event_type,count(*)::integer FROM agent.task_events event
            JOIN agent.tasks task ON task.id=event.task_id
            WHERE task.source_kind='phase2_runtime_stress' GROUP BY event.event_type"""
        ).fetchall()
    )
    expected = {
        "task_claimed": TASK_COUNT,
        "step_started": TASK_COUNT * STEPS_PER_TASK,
        "lease_released": TASK_COUNT - 1,
        "lease_expired": 1,
    }
    if event_counts != expected or sum(event_counts.values()) != EXPECTED_EVENT_COUNT:
        raise AssertionError(f"typed event totals differ: {event_counts}")
    invalid_events = connection.execute(
        """SELECT count(*) FROM agent.task_events event
        JOIN agent.tasks task ON task.id=event.task_id
        LEFT JOIN agent.runtime_event_types type ON type.event_type=event.event_type
        WHERE task.source_kind='phase2_runtime_stress' AND (
          type.event_type IS NULL OR event.runtime_scope<>'internal' OR event.actor_type<>'runtime'
          OR event.risk_class<>'internal_read' OR event.book_id IS NOT NULL OR event.client_id IS NOT NULL)"""
    ).fetchone()[0]
    if invalid_events:
        raise AssertionError("one or more stress events violated their typed/scope contract")
    event_ids = [
        row[0]
        for row in connection.execute(
            """SELECT event.id FROM agent.task_events event JOIN agent.tasks task ON task.id=event.task_id
            WHERE task.source_kind='phase2_runtime_stress' ORDER BY event.id"""
        ).fetchall()
    ]
    if len(event_ids) != EXPECTED_EVENT_COUNT or any(b <= a for a, b in zip(event_ids, event_ids[1:])):
        raise AssertionError("durable event IDs are not strictly monotonic")
    replay = _replay_checks(test_dsn, event_ids)

    checkpoint_id = connection.execute("SELECT agent.checkpoint_runtime_events('internal')").fetchone()[0]
    through_id, snapshot = connection.execute(
        "SELECT through_event_id,snapshot FROM agent.event_checkpoints WHERE id=%s", (checkpoint_id,)
    ).fetchone()
    reset_page = connection.execute(
        "SELECT count(*) FROM agent.task_events WHERE runtime_scope='internal' AND id>%s", (event_ids[-1] + 100,)
    ).fetchone()[0]
    if through_id != event_ids[-1] or len(snapshot.get("tasks", [])) != TASK_COUNT or reset_page != 0:
        raise AssertionError("cursor reset did not recover from the durable checkpoint")

    safety = connection.execute(
        """SELECT
          (SELECT count(*) FROM agent.profiles WHERE agent_name LIKE 'Stress Agent %%')::integer,
          (SELECT count(*) FROM agent.workers)::integer,
          (SELECT bool_and(NOT broker_write_allowed) FROM agent.v_runtime_presence
             WHERE agent_name LIKE 'Stress Agent %%'),
          (SELECT status FROM agent.workers WHERE id=%s),
          (SELECT runtime_state FROM agent.tasks WHERE id=%s)""",
        (stale["worker_id"], task.task_id),
    ).fetchone()
    if safety != (AGENT_COUNT, WORKER_COUNT, True, "STALE", "RETRYING"):
        raise AssertionError(f"final safety truth differs: {safety}")
    return {
        "agents": safety[0],
        "workers": safety[1],
        "tasks_claimed_exactly_once": lease_counts[0],
        "lease_status": {"released": lease_counts[3], "expired": lease_counts[4], "active": lease_counts[5]},
        "observed_peak_active": peak,
        "typed_events": sum(event_counts.values()),
        "event_counts": event_counts,
        "replay": replay,
        "cursor_reset": {"empty_future_page": True, "checkpoint_id": checkpoint_id, "through_event_id": through_id},
        "stale_presence_before_reap": {"state": stale_presence[0], "has_live_lease": stale_presence[1]},
        "expired_task_after_reap": "RETRYING",
        "broker_write_allowed": False,
        "provider_calls": 0,
        "model_calls": 0,
        "external_writes": 0,
    }


def run(dsn: str) -> dict[str, Any]:
    psycopg = _require_psycopg()
    from psycopg import sql
    from psycopg.conninfo import make_conninfo

    settings = validate_admin_dsn(dsn)
    database_name = "phase2_stress_" + uuid4().hex
    if not DATABASE_PATTERN.fullmatch(database_name):
        raise AssertionError("generated database name violated the cleanup guard")
    admin = psycopg.connect(dsn, autocommit=True)
    created = False
    worker_connections: list[Any] = []
    started = time.perf_counter()
    result: dict[str, Any] | None = None
    try:
        _assert_private_test_server(admin, settings["host"])
        admin.execute(
            sql.SQL("CREATE DATABASE {} ENCODING 'UTF8' TEMPLATE template0").format(sql.Identifier(database_name))
        )
        created = True
        test_dsn = make_conninfo(dsn, dbname=database_name)
        with psycopg.connect(test_dsn, autocommit=True) as connection:
            setup_started = time.perf_counter()
            fingerprints = _bootstrap(connection)
            tasks = _seed(connection)

            def connection_factory():
                return psycopg.connect(test_dsn, autocommit=True)

            worker_connections, workers = _register_workers(connection_factory, database_name)
            setup_seconds = time.perf_counter() - setup_started

            race_barrier = threading.Barrier(WORKER_COUNT)

            def contend(index: int):
                race_barrier.wait(timeout=10)
                return index, _claim(worker_connections[index], workers[index], tasks[0], database_name)

            with concurrent.futures.ThreadPoolExecutor(max_workers=WORKER_COUNT) as pool:
                contested = list(pool.map(contend, range(WORKER_COUNT)))
            winners = [(index, item) for index, item in contested if item[0]]
            if len(winners) != 1:
                raise AssertionError(f"concurrent claim did not produce one owner: {len(winners)}")
            winner_index, (winner_claim, winner_token) = winners[0]

            heartbeat_key = str(uuid5(NAMESPACE_URL, f"{database_name}:heartbeat-idempotency"))
            first_heartbeat = _json_call(
                worker_connections[winner_index],
                "SELECT agent.heartbeat_runtime_lease(%s,%s,%s,%s,NULL)",
                (workers[winner_index], winner_claim["lease_id"], winner_token, heartbeat_key),
            )
            duplicate_heartbeat = _json_call(
                worker_connections[winner_index],
                "SELECT agent.heartbeat_runtime_lease(%s,%s,%s,%s,NULL)",
                (workers[winner_index], winner_claim["lease_id"], winner_token, heartbeat_key),
            )
            if (
                first_heartbeat.get("broker_write_allowed") is not False
                or duplicate_heartbeat.get("duplicate") is not True
                or duplicate_heartbeat.get("expires_at") != first_heartbeat.get("expires_at")
            ):
                raise AssertionError("heartbeat idempotency changed ownership or expiry")
            _exercise_claim(
                worker_connections[winner_index],
                workers[winner_index],
                tasks[0],
                winner_claim,
                winner_token,
                release=True,
            )

            first_claim_ready = [threading.Event() for _ in range(WORKER_COUNT)]
            release_first_claims = threading.Event()

            def work_partition(index: int) -> dict[str, Any] | None:
                stale_result = None
                partition = [task for task in tasks[1:] if task.index % WORKER_COUNT == index]
                for position, task in enumerate(partition):
                    claim, token = _claim(worker_connections[index], workers[index], task, database_name)
                    if not claim:
                        raise AssertionError(f"worker {index} could not claim task {task.index}")
                    if position == 0:
                        first_claim_ready[index].set()
                        if not release_first_claims.wait(timeout=15):
                            raise AssertionError("active-cap observation barrier timed out")
                    stale_result = _exercise_claim(
                        worker_connections[index],
                        workers[index],
                        task,
                        claim,
                        token,
                        release=task.index != TASK_COUNT - 1,
                    ) or stale_result
                return stale_result

            processing_started = time.perf_counter()
            with concurrent.futures.ThreadPoolExecutor(max_workers=WORKER_COUNT) as pool:
                futures = [pool.submit(work_partition, index) for index in range(WORKER_COUNT)]
                for event in first_claim_ready:
                    if not event.wait(timeout=15):
                        raise AssertionError("not all four bounded workers obtained a lease")
                peak = _assert_active_caps(connection)
                release_first_claims.set()
                stale_candidates = [future.result(timeout=180) for future in futures]
            processing_seconds = time.perf_counter() - processing_started
            stale_items = [item for item in stale_candidates if item is not None]
            if len(stale_items) != 1 or stale_items[0]["task"].index != TASK_COUNT - 1:
                raise AssertionError("exactly one deterministic stale lease was not retained")
            verification_started = time.perf_counter()
            result = _verify(connection, test_dsn, stale_items[0], peak)
            verification_seconds = time.perf_counter() - verification_started
            result.update(
                {
                    "verdict": "PASS",
                    "database_class": "disposable_private_tmp",
                    "database_name_redacted": database_name[:14] + "...",
                    "migration_replay_passes": 2,
                    "applied_migrations": list(APPLIED_MIGRATIONS),
                    "pinned_migration_sha256": fingerprints,
                    "migration_260_scope": "covered_by_separate_doctor_routine_acceptance",
                    "heartbeat_idempotency": True,
                    "concurrent_claim_contenders": WORKER_COUNT,
                    "concurrent_claim_winners": 1,
                    "timings_seconds": {
                        "setup": round(setup_seconds, 3),
                        "processing": round(processing_seconds, 3),
                        "verification_and_reconnect": round(verification_seconds, 3),
                        "total_before_cleanup": round(time.perf_counter() - started, 3),
                    },
                    "live_24_hour_soak": "NOT_RUN",
                }
            )
    finally:
        if "release_first_claims" in locals():
            release_first_claims.set()
        for connection in worker_connections:
            try:
                connection.close()
            except Exception:
                pass
        if created:
            if not DATABASE_PATTERN.fullmatch(database_name):
                raise AssertionError("cleanup target guard refused generated database")
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",
                (database_name,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database_name)))
        admin.close()
    if result is None:
        raise AssertionError("stress harness produced no result")
    result["cleanup"] = "OWN_DATABASE_DROPPED"
    result["timings_seconds"]["total_with_cleanup"] = round(time.perf_counter() - started, 3)
    return result


def main() -> int:
    dsn = os.environ.get("AI_OS_TEST_PG_DSN", "")
    receipt = run(dsn)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - manual acceptance entrypoint
    raise SystemExit(main())
