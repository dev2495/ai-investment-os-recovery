"""Bounded autonomous collection and extraction for approved Research Cases."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
EXTRACTOR = RUNTIME_ROOT / "scripts" / "extract_filing_pdfs.py"
SCRIPT_ROOT = RUNTIME_ROOT / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from governed_pdf_runtime import governed_pdf_python  # noqa: E402


def _extractor_python() -> str:
    """Use the governed SSD PDF runtime; never fall back when it is unavailable."""
    return governed_pdf_python(verify_import=True)


def queue_case_sources(case_id: int, actor: str, *, run_statement, sql_literal) -> dict[str, Any]:
    rows = run_statement(f"""
      WITH case_row AS (
        SELECT id,ticker FROM research.research_cases WHERE id={int(case_id)}
      ), ranked AS (
        SELECT filing.id,filing.source_url,filing.local_path,filing.extraction_status,
          CASE WHEN lower(coalesce(filing.filing_type,'')) LIKE '%annual%' THEN 1 ELSE 2 END source_rank,
          row_number() OVER (PARTITION BY CASE WHEN lower(coalesce(filing.filing_type,'')) LIKE '%annual%' THEN 1 ELSE 2 END
            ORDER BY coalesce((filing.payload->>'fiscal_year_end')::integer,extract(year from filing.filed_at)::integer,0) DESC,
                     coalesce(filing.filed_at,filing.created_at) DESC,filing.id DESC) within_rank
        FROM research.corporate_filings filing JOIN case_row ON upper(filing.symbol)=upper(case_row.ticker)
        WHERE filing.source_url IS NOT NULL
          AND (filing.source_name IN ('Company IR','NSE','BSE') OR filing.source_url ILIKE 'https://%')
          AND filing.extraction_status NOT IN ('rejected_non_annual_report')
      ), bounded AS (
        SELECT * FROM ranked WHERE (source_rank=1 AND within_rank<=6) OR (source_rank=2 AND within_rank<=8)
      ), inserted AS (
        INSERT INTO research.research_case_source_jobs (
          research_case_id,corporate_filing_id,job_kind,status,priority,source_url,artifact_path,created_by
        ) SELECT {int(case_id)},id,'extract_official_filing',
          CASE WHEN extraction_status IN ('extracted','validated','human_reviewed') THEN 'completed' ELSE 'queued' END,
          source_rank*10+within_rank,source_url,local_path,{sql_literal(actor)} FROM bounded
        ON CONFLICT (research_case_id,corporate_filing_id,job_kind) DO UPDATE SET
          status=CASE WHEN EXCLUDED.status='completed' THEN 'completed'
            WHEN research.research_case_source_jobs.status IN ('completed','running') THEN research.research_case_source_jobs.status
            ELSE EXCLUDED.status END,
          source_url=EXCLUDED.source_url,artifact_path=EXCLUDED.artifact_path,updated_at=now()
        RETURNING id,status
      ), source_count AS (SELECT count(*)::integer count FROM bounded),
      blocker AS (
        INSERT INTO research.research_case_blockers (
          research_case_id,blocker_key,stage_key,title,detail,system_action,user_action,status,severity,metadata
        ) SELECT {int(case_id)},'official_source_discovery','sources','No qualified official source is available',
          'The stack found neither an operator-verified company IR document nor a captured NSE/BSE filing for this ticker.',
          'The source collector will retry the approved exchange and IR registries.','Add an official IR URL only if the company is not present in those registries.',
          'open','high',jsonb_build_object('automatic_retry',true)
        FROM source_count WHERE count=0
        ON CONFLICT (research_case_id,blocker_key) DO UPDATE SET status='open',detail=EXCLUDED.detail,updated_at=now()
        RETURNING id
      ), resolved AS (
        UPDATE research.research_case_blockers SET status='resolved',resolved_at=now(),
          resolution='Official source candidates were found by the stack.',updated_at=now()
        WHERE research_case_id={int(case_id)} AND blocker_key='official_source_discovery'
          AND (SELECT count FROM source_count)>0 AND status<>'resolved' RETURNING id
      ), updated_case AS (
        UPDATE research.research_cases SET status=CASE WHEN status='proposed' THEN status ELSE 'collecting' END,
          lead_status=CASE WHEN status='proposed' THEN lead_status ELSE 'collecting_official_sources' END,
          current_goal=CASE WHEN status='proposed' THEN current_goal ELSE 'Collect and parse bounded official filings automatically' END,
          last_progress_at=now(),updated_at=now()
        WHERE id={int(case_id)} AND (SELECT count(*) FROM inserted WHERE status='queued')>0 RETURNING id
      ), event AS (
        INSERT INTO research.research_case_events (research_case_id,event_type,event_status,event_summary,actor,event_payload)
        SELECT {int(case_id)},'source_collection',
          CASE WHEN (SELECT count FROM source_count)>0 THEN 'queued' ELSE 'blocked' END,
          CASE WHEN (SELECT count FROM source_count)>0
            THEN 'The stack queued bounded official filings for local extraction; no user download is required.'
            ELSE 'No approved official source was found; automatic registry retry remains open.' END,
          {sql_literal(actor)},jsonb_build_object('candidate_count',(SELECT count FROM source_count),'automatic',true)
        RETURNING id
      ) SELECT coalesce(json_agg(json_build_object('candidate_count',(SELECT count FROM source_count),
        'queued',(SELECT count(*) FROM inserted WHERE status='queued'),
        'already_extracted',(SELECT count(*) FROM inserted WHERE status='completed'),
        'event_id',event.id)),'[]'::json)::text FROM event
    """)
    return rows[0] if rows else {"candidate_count": 0, "queued": 0, "already_extracted": 0}


def _claim(run_statement) -> dict[str, Any] | None:
    rows = run_statement("""
      WITH candidate AS (
        SELECT job.id FROM research.research_case_source_jobs job
        JOIN research.research_cases case_row ON case_row.id=job.research_case_id
        WHERE job.status IN ('queued','retry_wait')
          AND (job.next_retry_at IS NULL OR job.next_retry_at<=now())
          AND case_row.status IN ('collecting','active','blocked')
        ORDER BY job.priority,job.id FOR UPDATE SKIP LOCKED LIMIT 1
      ), claimed AS (
        UPDATE research.research_case_source_jobs job SET status='running',attempt=attempt+1,
          started_at=now(),updated_at=now() FROM candidate WHERE job.id=candidate.id RETURNING job.*
      ) SELECT coalesce(json_agg(row_to_json(claimed)),'[]'::json)::text FROM claimed
    """)
    return rows[0] if rows else None


def run_source_once(*, run_statement, sql_literal, sql_jsonb) -> dict[str, Any]:
    job = _claim(run_statement)
    if not job:
        return {"status": "idle"}
    job_id = int(job["id"]); case_id = int(job["research_case_id"])
    filing_id = int(job.get("corporate_filing_id") or 0)
    command = [_extractor_python(), str(EXTRACTOR), "--filing-id", str(filing_id), "--actor", "Research Source Collector"]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=360, check=False)
    try:
        result = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        result = {"ok": False, "stdout_preview": (completed.stdout or "")[:1000]}
    ok = completed.returncode == 0 and bool(result.get("ok"))
    if ok:
        run_statement(f"""
          WITH job_updated AS (
            UPDATE research.research_case_source_jobs SET status='completed',finished_at=now(),
              result={sql_jsonb(result)},error_detail=NULL,updated_at=now() WHERE id={job_id} RETURNING research_case_id
          ), blocker_resolved AS (
            UPDATE research.research_case_blockers SET status='resolved',next_retry_at=NULL,resolved_at=now(),
              resolution='Successful local SSD extraction superseded the prior parser failure.',
              system_action='Resolved automatically after successful local extraction.',updated_at=now()
            WHERE research_case_id={case_id} AND blocker_key={sql_literal('source_job:'+str(job_id))}
            RETURNING id
          ), event AS (
            INSERT INTO research.research_case_events (research_case_id,event_type,event_status,event_summary,actor,event_payload)
            SELECT {case_id},'source_extraction','completed','An official filing was downloaded or read from cache and extracted locally on Devarsh SSD.',
              'Research Source Collector',{sql_jsonb({'source_job_id': job_id, 'corporate_filing_id': filing_id})} RETURNING id
          ) SELECT coalesce(json_agg(row_to_json(event)),'[]'::json)::text FROM event
        """)
        from api.ai_os_api_server import sync_research_case_official_sources
        sync = sync_research_case_official_sources(case_id, "Research Source Collector")
        remaining = run_statement(f"""
          WITH counts AS (SELECT
              count(*) FILTER(WHERE status IN ('queued','running','retry_wait'))::integer remaining,
              count(*) FILTER(WHERE status='blocked')::integer blocked
            FROM research.research_case_source_jobs WHERE research_case_id={case_id}),
          updated AS (UPDATE research.research_cases SET
            status=CASE WHEN (SELECT blocked FROM counts)>0 THEN 'blocked' WHEN (SELECT remaining FROM counts)=0 THEN 'active' ELSE 'collecting' END,
            lead_status=CASE WHEN (SELECT blocked FROM counts)>0 THEN 'source_extraction_blocked' WHEN (SELECT remaining FROM counts)=0 THEN 'sources_ready' ELSE 'collecting_official_sources' END,
            current_goal=CASE WHEN (SELECT remaining FROM counts)=0 THEN 'Run specialist analysis from the qualified public packet' ELSE current_goal END,
            last_progress_at=now(),updated_at=now() WHERE id={case_id} RETURNING id)
          SELECT coalesce(json_agg(json_build_object('remaining',counts.remaining,'blocked',counts.blocked)),'[]'::json)::text FROM counts
        """)
        remaining_row = remaining[0] if remaining else {}
        remaining_count = int(remaining_row.get("remaining") or 0)
        blocked_count = int(remaining_row.get("blocked") or 0)
        runtime = None
        if remaining_count == 0 and blocked_count == 0:
            from api import ai_os_api_server as server
            from run_agent_worker_once import psql_json
            readiness = psql_json(f"""
              SELECT preflight.id preflight_id,preflight.status preflight_status,
                (SELECT count(*) FROM research.research_case_model_runs
                  WHERE research_case_id={case_id} AND preflight_id=preflight.id)::integer model_run_count
              FROM research.model_run_preflights preflight
              WHERE preflight.research_case_id={case_id} AND preflight.request_kind='research_case'
              ORDER BY preflight.id DESC LIMIT 1
            """)
            ready = readiness[0] if readiness else {}
            if ready.get("preflight_status") == "approved" and int(ready.get("model_run_count") or 0) == 0:
                runtime = server.prepare_research_case_runtime(
                    case_id,int(ready["preflight_id"]),actor="Research Source Collector",
                    run_rows=psql_json,run_statement=run_statement,sql_literal=sql_literal,sql_jsonb=sql_jsonb,
                )
        return {"status":"source_completed","case_id":case_id,"source_job_id":job_id,"remaining":remaining_count,"blocked":blocked_count,"sync":sync,"autonomous_runtime":runtime}
    error = ((completed.stderr or completed.stdout or "extractor failed").strip())[:2000]
    if "pypdf is required" in error.lower():
        display_error = "The governed SSD PDF parser was unavailable for this attempt; the local runtime will be checked before retry."
    elif "timed out" in error.lower() or "timeoutexpired" in error.lower():
        display_error = "The official filing parser exceeded its bounded time window; the cached SSD document is preserved for retry."
    else:
        display_error = "The official filing could not be parsed on this attempt; the source document is preserved on SSD and a bounded retry is scheduled."
    retrying = int(job.get("attempt") or 0) < int(job.get("max_attempts") or 3)
    job_status = "retry_wait" if retrying else "blocked"
    blocker_status = "retrying" if retrying else "open"
    run_statement(f"""
      WITH updated AS (
        UPDATE research.research_case_source_jobs SET status={sql_literal(job_status)},
          next_retry_at=CASE WHEN {str(retrying).lower()} THEN now()+interval '15 minutes' ELSE NULL END,
          error_detail={sql_literal(error)},finished_at=CASE WHEN {str(retrying).lower()} THEN NULL ELSE now() END,updated_at=now()
        WHERE id={job_id} RETURNING id
      ), blocker AS (
        INSERT INTO research.research_case_blockers (research_case_id,blocker_key,stage_key,title,detail,system_action,user_action,status,severity,retry_count,next_retry_at,metadata)
        VALUES ({case_id},{sql_literal('source_job:'+str(job_id))},'sources','Official filing extraction failed',
          {sql_literal(display_error)},'The stack will retry locally with bounded cooldown.',
          CASE WHEN {str(retrying).lower()} THEN NULL ELSE 'Open the source link and review the exact parser exception.' END,
          {sql_literal(blocker_status)},'high',{int(job.get('attempt') or 0)+1},
          CASE WHEN {str(retrying).lower()} THEN now()+interval '15 minutes' ELSE NULL END,
          {sql_jsonb({'source_job_id':job_id,'corporate_filing_id':filing_id,'technical_detail':error})})
        ON CONFLICT (research_case_id,blocker_key) DO UPDATE SET title=EXCLUDED.title,detail=EXCLUDED.detail,
          system_action=EXCLUDED.system_action,user_action=EXCLUDED.user_action,status=EXCLUDED.status,
          retry_count=EXCLUDED.retry_count,next_retry_at=EXCLUDED.next_retry_at,metadata=EXCLUDED.metadata,updated_at=now() RETURNING id
      ) SELECT coalesce(json_agg(row_to_json(blocker)),'[]'::json)::text FROM blocker
    """)
    return {"status":"source_retry_wait" if retrying else "source_blocked","case_id":case_id,"source_job_id":job_id,"error":error}
