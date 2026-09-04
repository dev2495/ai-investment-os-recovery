"""Opt-in local browser fixture: actual runtime API/SQL, synthetic records only.

Never deployed. Requires the same narrowly guarded temporary PG DSN as the tests.
UI: VITE_AI_OS_API_URL=http://127.0.0.1:18765 npm run dev -- --port 15177
"""
from __future__ import annotations

from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
import json
import os
import signal
import threading
import urllib.parse

from test_agent_runtime_postgres import database
from _ai_os_runtime.api import ai_os_api_server as server
from _ai_os_runtime.api.agent_runtime import AgentRuntime, TaskControl
from _ai_os_runtime.api.agent_runtime_api import RuntimeAPI, overlay_office_presence


def main():
    if os.environ.get("AI_OS_SYNTHETIC_BROWSER_FIXTURE") != "1":
        raise SystemExit("Synthetic fixture requires explicit AI_OS_SYNTHETIC_BROWSER_FIXTURE=1")
    fixture = database.__wrapped__()
    execute, _dsn = next(fixture)
    stop = threading.Event()
    server.RUNTIME_API = RuntimeAPI(execute)
    server.OPERATOR_TOKEN = ""
    server.ALLOW_TOKENLESS_LOOPBACK = True
    server.ALLOWED_ORIGINS = {"http://127.0.0.1:15177"}
    profiles = []
    jobs = []
    runtimes = []
    for title in ("Synthetic Reader", "Synthetic Stale Worker", "Synthetic Receipt Review"):
        agent = int(execute(f"INSERT INTO agent.profiles(agent_name,department,role_scope) VALUES('{title}','research','Synthetic test only') RETURNING id"))
        task = int(execute(f"INSERT INTO agent.tasks(title,objective,owner_agent,recovery_policy) VALUES('Synthetic test','No private data or model calls','{title}','idempotent_read') RETURNING id"))
        runtime = AgentRuntime(execute)
        lease = runtime.claim(task, title)
        lease.checkpoint("read_local_test", "READING")
        profiles.append({"agent_name": title, "department_key": "research", "department": "research", "display_title": title,
                         "current_work_title": "Synthetic test task", "current_task_id": task, "presence_state": "executing"})
        jobs.append(task)
        runtimes.append((runtime, lease))
    execute(f"UPDATE agent.task_leases SET expires_at=now()-interval '1 second' WHERE id={runtimes[1][1].claim['lease_id']}")
    runtimes[2][1].checkpoint("uncertain_test_output", "WRITING", side_effect=True)
    runtimes[2][1].finish("blocked")

    def snapshot():
        runtime = {**server.RUNTIME_API.snapshot(), "synthetic_only": True}
        return overlay_office_presence({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "projection_meta": {"source_status": "synthetic_test", "privacy_mode": "synthetic_only", "broker_write_allowed": False},
            "agents": [dict(row) for row in profiles], "live_office_agent_activity": [dict(row) for row in profiles],
            "live_office_rooms": [{"room_key": "research", "room_name": "Research · synthetic", "agent_count": 3}],
            "execution_control": [{"global_execution_locked": True}], "agent_messages": [], "issues": [],
        }, runtime)

    server.build_office_snapshot = snapshot

    class FixtureHandler(server.AiOsApiHandler):
        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            if path == "/test-fixture/info":
                self._send_json({"synthetic_only": True, "tasks": jobs})
            elif path == "/api/office/snapshot" or path.startswith("/api/v1/"):
                super().do_GET()
            elif path.startswith("/api/"):
                # Non-runtime shell surfaces remain empty, never fabricated live.
                self._send_json({"generated_at": datetime.now(timezone.utc).isoformat(), "synthetic_only": True})
            else:
                self._send_json({"error": "fixture_route_not_found"}, 404)

    def worker():
        runtime, lease = runtimes[0]
        while not stop.wait(0.5):
            if lease:
                try:
                    reply = runtime.heartbeat(lease.claim["lease_id"], lease.token)
                    if reply.get("control_requested"):
                        lease.checkpoint("apply_control", "READING")
                except TaskControl:
                    lease = None
                except Exception:
                    # A synthetic worker also fails closed; never silently restart.
                    stop.set()
            else:
                lease = runtime.claim(jobs[0], "Synthetic Reader")
                if lease:
                    lease.checkpoint("resume_local_test", "READING")

    http = ThreadingHTTPServer(("127.0.0.1", 18765), FixtureHandler)
    worker_thread = threading.Thread(target=worker, daemon=True)
    worker_thread.start()
    http_thread = threading.Thread(target=http.serve_forever, daemon=True)
    http_thread.start()
    def end(*_):
        stop.set()
    signal.signal(signal.SIGTERM, end)
    signal.signal(signal.SIGINT, end)
    print(json.dumps({"url": "http://127.0.0.1:18765", "synthetic_only": True, "tasks": jobs}), flush=True)
    try:
        stop.wait()
    finally:
        stop.set()
        worker_thread.join(timeout=3)
        http.shutdown()
        http.server_close()
        # Allow finite SSE handlers to observe a closed client before DB teardown.
        try:
            next(fixture)
        except StopIteration:
            pass


if __name__ == "__main__":
    main()
