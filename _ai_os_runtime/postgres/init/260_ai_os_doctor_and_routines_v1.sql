\set ON_ERROR_STOP on

BEGIN;

-- Phase 2 M6/M7: one Doctor registry and five versioned routines on the
-- existing workflow schedule authority. Nothing is enabled by this migration.
-- No provider call, model call, credential action, client write or broker write
-- is performed or granted.

CREATE TABLE IF NOT EXISTS ops.doctor_check_registry (
    check_key TEXT PRIMARY KEY,
    component TEXT NOT NULL,
    check_name TEXT NOT NULL,
    description TEXT NOT NULL,
    runner_key TEXT NOT NULL,
    failure_severity TEXT NOT NULL DEFAULT 'high'
        CHECK (failure_severity IN ('info','low','medium','high','critical')),
    timeout_seconds INTEGER NOT NULL DEFAULT 5 CHECK (timeout_seconds BETWEEN 1 AND 30),
    safe_fix_key TEXT,
    enabled BOOLEAN NOT NULL DEFAULT true,
    configuration JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (NOT core.jsonb_contains_raw_secret(configuration)),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ops.doctor_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    mode TEXT NOT NULL CHECK (mode IN ('scan','baseline','safe_fix','test')),
    status TEXT NOT NULL CHECK (status IN ('running','passed','degraded','failed')),
    requested_by TEXT NOT NULL,
    selected_component TEXT,
    selected_agent_key TEXT,
    selected_model_route TEXT,
    check_count INTEGER NOT NULL DEFAULT 0 CHECK (check_count >= 0),
    passed_count INTEGER NOT NULL DEFAULT 0 CHECK (passed_count >= 0),
    warning_count INTEGER NOT NULL DEFAULT 0 CHECK (warning_count >= 0),
    failed_count INTEGER NOT NULL DEFAULT 0 CHECK (failed_count >= 0),
    unknown_count INTEGER NOT NULL DEFAULT 0 CHECK (unknown_count >= 0),
    summary JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (NOT core.jsonb_contains_raw_secret(summary)),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    external_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (external_write_allowed=false)
);

CREATE TABLE IF NOT EXISTS ops.doctor_check_results (
    id BIGSERIAL PRIMARY KEY,
    doctor_run_id BIGINT NOT NULL REFERENCES ops.doctor_runs(id) ON DELETE CASCADE,
    check_key TEXT NOT NULL REFERENCES ops.doctor_check_registry(check_key) ON DELETE RESTRICT,
    component TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('passed','warning','failed','unknown','skipped')),
    severity TEXT NOT NULL CHECK (severity IN ('info','low','medium','high','critical')),
    headline TEXT NOT NULL,
    observed JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (NOT core.jsonb_contains_raw_secret(observed)),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (NOT core.jsonb_contains_raw_secret(evidence)),
    actionable_fix TEXT,
    last_known_good_at TIMESTAMPTZ,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    duration_ms INTEGER NOT NULL DEFAULT 0 CHECK (duration_ms >= 0),
    UNIQUE (doctor_run_id, check_key)
);

CREATE INDEX IF NOT EXISTS idx_doctor_results_check_time
    ON ops.doctor_check_results(check_key, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_doctor_results_attention
    ON ops.doctor_check_results(status, severity, observed_at DESC);

CREATE TABLE IF NOT EXISTS ops.doctor_baselines (
    check_key TEXT PRIMARY KEY REFERENCES ops.doctor_check_registry(check_key) ON DELETE CASCADE,
    source_result_id BIGINT NOT NULL REFERENCES ops.doctor_check_results(id) ON DELETE RESTRICT,
    observed_digest TEXT NOT NULL CHECK (observed_digest ~ '^[0-9a-f]{64}$'),
    baseline JSONB NOT NULL CHECK (NOT core.jsonb_contains_raw_secret(baseline)),
    captured_by TEXT NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ops.doctor_safe_fix_receipts (
    id BIGSERIAL PRIMARY KEY,
    receipt_key TEXT NOT NULL UNIQUE,
    doctor_run_id BIGINT NOT NULL REFERENCES ops.doctor_runs(id) ON DELETE RESTRICT,
    check_key TEXT NOT NULL REFERENCES ops.doctor_check_registry(check_key) ON DELETE RESTRICT,
    safe_fix_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('applied','no_change','failed','refused')),
    requested_by TEXT NOT NULL,
    before_evidence JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (NOT core.jsonb_contains_raw_secret(before_evidence)),
    after_evidence JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (NOT core.jsonb_contains_raw_secret(after_evidence)),
    result_summary TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    credential_change_allowed BOOLEAN NOT NULL DEFAULT false CHECK (credential_change_allowed=false)
);

INSERT INTO ops.doctor_check_registry
    (check_key,component,check_name,description,runner_key,failure_severity,timeout_seconds,safe_fix_key,configuration)
VALUES
    ('postgres_migration_level','database','Postgres and migration level','Connect to the canonical database and confirm the migration ledger reached this contract.','postgres_migration_level','critical',5,NULL,'{"minimum_migration":260}'),
    ('external_ssd_storage','storage','External SSD storage','Confirm the configured SSD is mounted, writable and has bounded free capacity without falling back to internal storage.','external_ssd_storage','critical',5,NULL,'{"minimum_free_gb":1,"expected_root":"/Volumes/Devarsh SSD/AI OS Data"}'),
    ('api_readiness','services','API readiness','Probe the canonical local API readiness endpoint.','api_readiness','critical',5,NULL,'{}'),
    ('redis_health','services','Redis health','Probe the existing local Redis endpoint.','redis_health','medium',3,NULL,'{}'),
    ('qdrant_health','knowledge','Qdrant health','Probe the existing local Qdrant endpoint and collection inventory.','qdrant_health','high',5,NULL,'{}'),
    ('obsidian_index_lag','obsidian','Obsidian index drift','Compare managed note modification and index timestamps and count unresolved links.','obsidian_index_lag','high',5,NULL,'{"warn_after_seconds":900}'),
    ('backup_restore_receipt','backup','Backup and restore receipt','Find the newest local backup and isolated restore-drill evidence.','backup_restore_receipt','critical',5,NULL,'{"max_restore_age_hours":168}'),
    ('worker_heartbeat','agents','Worker and daemon heartbeat','Check registered worker and daemon heartbeat age.','worker_heartbeat','high',5,NULL,'{"worker_stale_seconds":180}'),
    ('expired_task_leases','agents','Expired task leases','Detect active leases whose server-side expiry has elapsed.','expired_task_leases','high',5,'release_expired_leases','{}'),
    ('queue_backlog','agents','Task and message backlog','Count bounded failed, retrying, blocked and stale queued work.','queue_backlog','medium',5,NULL,'{"warning_count":25}'),
    ('routine_scheduler','routines','Routine schedule authority','Check the existing workflow scheduler and latest routine run without creating a second scheduler.','routine_scheduler','high',5,NULL,'{}'),
    ('model_route_health','models','Model route integrity','Check enabled route binding, endpoint qualification freshness, adapter identity and cost caps.','model_route_health','high',8,NULL,'{"qualification_max_age_hours":168}'),
    ('zerodha_session_stream','zerodha','Zerodha session, stream and quote freshness','Read the existing Zerodha health surfaces; report daily login and stale quotes without exposing secrets.','zerodha_session_stream','critical',5,NULL,'{"fresh_quote_seconds":20,"daily_login_human_owned":true}'),
    ('tradingview_connector','tradingview','TradingView connector','Read the current native TradingView connector state without attempting chart or account mutation.','tradingview_connector','medium',5,NULL,'{}'),
    ('pythia_optional','services','Pythia optional runtime','Probe the configured Pythia health endpoint when installed; absence is an explicit skipped state.','pythia_optional','low',5,NULL,'{"optional":true}'),
    ('ui_asset_equality','services','UI asset equality','Compare source and deployed UI asset manifests when the local probe has both roots.','ui_asset_equality','high',8,NULL,'{}'),
    ('launchd_services','services','LaunchAgent supervision','Inspect only the allowlisted AI OS LaunchAgent labels.','launchd_services','high',8,NULL,'{}'),
    ('configuration_drift','configuration','Watched configuration drift','Hash the bounded watched-file list and compare it with the captured baseline.','configuration_drift','high',8,NULL,'{}'),
    ('execution_safety_locks','safety','Execution safety locks','Confirm broker writes remain false and the global execution control remains locked.','execution_safety_locks','critical',5,NULL,'{}'),
    ('client_scope_isolation','safety','Client scope isolation','Confirm forced RLS remains enabled on scoped private/client tables.','client_scope_isolation','critical',5,NULL,'{}'),
    ('changed_file_secret_scan','safety','Changed-file secret scan','Scan only changed filenames/content for secret-shaped values and return counts, never matching values.','changed_file_secret_scan','critical',10,NULL,'{}')
ON CONFLICT (check_key) DO UPDATE SET
    component=EXCLUDED.component,check_name=EXCLUDED.check_name,description=EXCLUDED.description,
    runner_key=EXCLUDED.runner_key,failure_severity=EXCLUDED.failure_severity,
    timeout_seconds=EXCLUDED.timeout_seconds,safe_fix_key=EXCLUDED.safe_fix_key,
    configuration=EXCLUDED.configuration,updated_at=now();

CREATE OR REPLACE VIEW ops.v_doctor_latest AS
SELECT result.check_key,registry.check_name,result.component,result.status,result.severity,
       result.headline,result.observed,result.evidence,result.actionable_fix,
       result.last_known_good_at,result.observed_at,result.duration_ms,
       run.run_key,run.mode,run.status AS run_status,run.requested_by,
       false AS broker_write_allowed
FROM ops.doctor_check_registry registry
LEFT JOIN LATERAL (
    SELECT value.* FROM ops.doctor_check_results value
    WHERE value.check_key=registry.check_key ORDER BY value.observed_at DESC,value.id DESC LIMIT 1
) result ON true
LEFT JOIN ops.doctor_runs run ON run.id=result.doctor_run_id
WHERE registry.enabled;

-- Versioned routines. Control state is separate from immutable versions.
CREATE TABLE IF NOT EXISTS agent.routine_definitions (
    routine_key TEXT PRIMARY KEY,
    routine_name TEXT NOT NULL,
    description TEXT NOT NULL,
    owner_agent TEXT NOT NULL REFERENCES agent.profiles(agent_name) ON DELETE RESTRICT,
    schedule_key TEXT NOT NULL UNIQUE REFERENCES agent.workflow_schedules(schedule_key) ON DELETE RESTRICT,
    current_version INTEGER NOT NULL CHECK (current_version > 0),
    control_state TEXT NOT NULL DEFAULT 'disabled' CHECK (control_state IN ('disabled','enabled','paused')),
    last_controlled_by TEXT,
    last_controlled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent.routine_versions (
    routine_key TEXT NOT NULL REFERENCES agent.routine_definitions(routine_key) ON DELETE CASCADE,
    version INTEGER NOT NULL CHECK (version > 0),
    skill_key TEXT NOT NULL REFERENCES agent.skills(skill_key) ON DELETE RESTRICT,
    trigger_kind TEXT NOT NULL CHECK (trigger_kind IN ('schedule','event','manual')),
    event_filter JSONB NOT NULL DEFAULT '{}'::jsonb,
    input_policy JSONB NOT NULL DEFAULT '{}'::jsonb,
    idempotency_template TEXT NOT NULL,
    permission_class TEXT NOT NULL CHECK (permission_class IN ('read_only','internal_safe_write')),
    timeout_seconds INTEGER NOT NULL CHECK (timeout_seconds BETWEEN 5 AND 900),
    cooldown_seconds INTEGER NOT NULL CHECK (cooldown_seconds BETWEEN 0 AND 86400),
    retry_policy JSONB NOT NULL,
    cost_budget_usd NUMERIC(12,6) NOT NULL DEFAULT 0 CHECK (cost_budget_usd=0),
    stale_data_policy JSONB NOT NULL,
    approval_policy JSONB NOT NULL,
    output_destinations TEXT[] NOT NULL DEFAULT '{}',
    allowed_tools TEXT[] NOT NULL DEFAULT '{}',
    definition_hash TEXT NOT NULL CHECK (definition_hash ~ '^[0-9a-f]{64}$'),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (routine_key,version),
    CONSTRAINT routine_version_no_raw_secrets CHECK (
        NOT core.jsonb_contains_raw_secret(event_filter)
        AND NOT core.jsonb_contains_raw_secret(input_policy)
        AND NOT core.jsonb_contains_raw_secret(retry_policy)
        AND NOT core.jsonb_contains_raw_secret(stale_data_policy)
        AND NOT core.jsonb_contains_raw_secret(approval_policy)
        AND NOT core.jsonb_contains_raw_secret(metadata)
    )
);

-- A published routine version is evidence. Corrections are inserted as the
-- next version and then selected by routine_definitions.current_version.
CREATE OR REPLACE FUNCTION agent.reject_published_routine_version_edit()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
BEGIN
    RAISE EXCEPTION 'published routine versions are immutable; insert a new version';
END
$fn$;

DO $trigger$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname='trg_routine_versions_immutable'
          AND tgrelid='agent.routine_versions'::regclass
          AND NOT tgisinternal
    ) THEN
        CREATE TRIGGER trg_routine_versions_immutable
        BEFORE UPDATE OR DELETE ON agent.routine_versions
        FOR EACH ROW EXECUTE FUNCTION agent.reject_published_routine_version_edit();
    END IF;
END
$trigger$;

CREATE TABLE IF NOT EXISTS agent.routine_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    routine_key TEXT NOT NULL,
    routine_version INTEGER NOT NULL,
    trigger_kind TEXT NOT NULL CHECK (trigger_kind IN ('schedule','event','manual','test')),
    event_hash TEXT,
    idempotency_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running','completed','partial','failed','refused')),
    requested_by TEXT NOT NULL,
    input_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (NOT core.jsonb_contains_raw_secret(input_snapshot)),
    result_summary TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (NOT core.jsonb_contains_raw_secret(evidence)),
    output_artifact_path TEXT,
    output_artifact_hash TEXT CHECK (output_artifact_hash IS NULL OR output_artifact_hash ~ '^[0-9a-f]{64}$'),
    error_code TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    model_cost_usd NUMERIC(12,6) NOT NULL DEFAULT 0 CHECK (model_cost_usd=0),
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    external_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (external_write_allowed=false),
    client_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (client_write_allowed=false),
    FOREIGN KEY (routine_key,routine_version)
        REFERENCES agent.routine_versions(routine_key,version) ON DELETE RESTRICT,
    UNIQUE (routine_key,idempotency_key),
    CONSTRAINT routine_event_hash_shape CHECK (event_hash IS NULL OR event_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT routine_artifact_local_ssd CHECK (
        output_artifact_path IS NULL OR output_artifact_path LIKE '/Volumes/Devarsh SSD/AI OS Data/%'
    )
);

CREATE INDEX IF NOT EXISTS idx_routine_runs_status_time
    ON agent.routine_runs(status,started_at DESC);
CREATE INDEX IF NOT EXISTS idx_routine_runs_routine_time
    ON agent.routine_runs(routine_key,started_at DESC);

CREATE TABLE IF NOT EXISTS agent.routine_control_events (
    id BIGSERIAL PRIMARY KEY,
    routine_key TEXT NOT NULL REFERENCES agent.routine_definitions(routine_key) ON DELETE RESTRICT,
    prior_state TEXT NOT NULL,
    new_state TEXT NOT NULL,
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false)
);

WITH skill_seed(skill_key,skill_name,owner_department,permission_level,input_sources,output_targets,required_tools,risk_notes,config) AS (
    VALUES
      ('daily_system_health_routine','Daily System Health Routine','runtime','read_only',ARRAY['ops.doctor_check_registry','core.runtime_daemon_heartbeats'],ARRAY['ops.doctor_runs','ops.doctor_check_results'],ARRAY['ai_os_doctor'],'Read-only health classification. Safe fixes require a separate explicit call.','{"model_calls":false,"broker_write_allowed":false}'::jsonb),
      ('obsidian_incremental_index_routine','Obsidian Incremental Index Routine','knowledge','internal_safe_write',ARRAY['knowledge.obsidian_notes','external SSD vault'],ARRAY['knowledge.obsidian_notes','knowledge.note_links','knowledge.index_runs'],ARRAY['index_obsidian_vault'],'Preserve human content and write only the managed index database.','{"managed_blocks_only":true,"model_calls":false,"broker_write_allowed":false}'::jsonb),
      ('research_company_change_monitor_routine','Research Company Change Monitor Routine','research','internal_safe_write',ARRAY['research.corporate_filings','market.news_items','research.watchlist_items'],ARRAY['research.company_research_updates','research.research_case_source_jobs'],ARRAY['company_research_monitor'],'Authorized stored sources only; no source fetch or paid model call.','{"authorized_stored_sources_only":true,"model_calls":false,"broker_write_allowed":false}'::jsonb),
      ('stale_task_and_lease_reaper_routine','Stale Task And Lease Reaper Routine','software','internal_safe_write',ARRAY['agent.task_leases','agent.task_steps','agent.workers'],ARRAY['agent.task_leases','agent.tasks','agent.task_events'],ARRAY['release_expired_leases'],'Requeue only idempotent reads with no uncertain side effect; otherwise block for reconciliation.','{"receipt_aware":true,"model_calls":false,"broker_write_allowed":false}'::jsonb),
      ('zerodha_session_stream_watch_routine','Zerodha Session And Stream Watch Routine','runtime','read_only',ARRAY['market.v_zerodha_stream_health','market.live_quote_state'],ARRAY['ops.doctor_runs','ops.doctor_check_results'],ARRAY['zerodha_health_read'],'Daily login remains human-owned; never read or expose credential values.','{"get_only":true,"daily_login_human_owned":true,"model_calls":false,"broker_write_allowed":false}'::jsonb)
)
INSERT INTO agent.skills (
    skill_key,skill_name,skill_family,skill_type,owner_department,status,execution_mode,
    permission_level,trigger_phrases,input_sources,output_targets,required_tools,
    risk_notes,prompt_template,config
)
SELECT skill_key,skill_name,'operations','routine',owner_department,'active','deterministic_allowlist',
       permission_level,ARRAY[lower(skill_name)],input_sources,output_targets,required_tools,
       risk_notes,'Execute the versioned allowlisted routine, persist a receipt and stop at every authority boundary.',config
FROM skill_seed
ON CONFLICT (skill_key) DO UPDATE SET
    skill_name=EXCLUDED.skill_name,status='active',execution_mode=EXCLUDED.execution_mode,
    permission_level=EXCLUDED.permission_level,input_sources=EXCLUDED.input_sources,
    output_targets=EXCLUDED.output_targets,required_tools=EXCLUDED.required_tools,
    risk_notes=EXCLUDED.risk_notes,prompt_template=EXCLUDED.prompt_template,
    config=EXCLUDED.config,updated_at=now();

WITH workflow_seed(workflow_key,workflow_name,owner_agent,trigger_type,permission_level,input_sources,output_targets,notes) AS (
    VALUES
      ('daily_system_health_routine_v1','Daily System Health Routine','Jarvis','scheduled','read_only',ARRAY['ops.doctor_check_registry'],ARRAY['ops.doctor_runs'],'Run the deterministic Doctor; create no external side effect.'),
      ('obsidian_incremental_index_routine_v1','Obsidian Incremental Index Routine','Librarian Agent','scheduled','write_db_and_artifact',ARRAY['knowledge.obsidian_notes'],ARRAY['knowledge.index_runs'],'Update the existing managed index while preserving human content.'),
      ('research_company_change_monitor_routine_v1','Research Company Change Monitor Routine','Research Director','event','write_db_and_artifact',ARRAY['research.corporate_filings','market.news_items'],ARRAY['research.company_research_updates'],'Reuse the existing company monitor with event-hash deduplication and no paid model.'),
      ('stale_task_and_lease_reaper_routine_v1','Stale Task And Lease Reaper Routine','DevOps Engineer','scheduled','write_db_and_artifact',ARRAY['agent.task_leases'],ARRAY['agent.task_events'],'Use the existing receipt-aware lease reaper only.'),
      ('zerodha_session_stream_watch_routine_v1','Zerodha Session And Stream Watch Routine','Jarvis','scheduled','read_only',ARRAY['market.v_zerodha_stream_health'],ARRAY['ops.doctor_runs'],'Observe existing GET-only Zerodha health; credentials and login remain human-owned.')
)
INSERT INTO agent.workflow_registry (
    workflow_key,workflow_name,workflow_type,owner_agent,trigger_type,status,permission_level,
    input_sources,output_targets,approval_required,schedule_hint,notes,metadata
)
SELECT workflow_key,workflow_name,'bounded_routine',owner_agent,trigger_type,'active',permission_level,
       input_sources,output_targets,false,'disabled until explicit operator enablement',notes,
       '{"second_scheduler_created":false,"model_calls":false,"broker_write_allowed":false,"external_write_allowed":false}'::jsonb
FROM workflow_seed
ON CONFLICT (workflow_key) DO UPDATE SET
    workflow_name=EXCLUDED.workflow_name,owner_agent=EXCLUDED.owner_agent,
    trigger_type=EXCLUDED.trigger_type,status='active',permission_level=EXCLUDED.permission_level,input_sources=EXCLUDED.input_sources,
    output_targets=EXCLUDED.output_targets,notes=EXCLUDED.notes,metadata=EXCLUDED.metadata,updated_at=now();

WITH schedule_seed(schedule_key,workflow_key,owner_agent,skill_key,schedule_name,cadence_seconds,priority,offset_minutes) AS (
    VALUES
      ('routine-daily-system-health','daily_system_health_routine_v1','Jarvis','daily_system_health_routine','Daily system health',86400,'high',5),
      ('routine-obsidian-incremental-index','obsidian_incremental_index_routine_v1','Librarian Agent','obsidian_incremental_index_routine','Obsidian incremental index',3600,'medium',10),
      ('routine-research-company-change-monitor','research_company_change_monitor_routine_v1','Research Director','research_company_change_monitor_routine','Research company change monitor',1800,'high',15),
      ('routine-stale-task-and-lease-reaper','stale_task_and_lease_reaper_routine_v1','DevOps Engineer','stale_task_and_lease_reaper_routine','Stale task and lease reaper',300,'high',20),
      ('routine-zerodha-session-stream-watch','zerodha_session_stream_watch_routine_v1','Jarvis','zerodha_session_stream_watch_routine','Zerodha session and stream watch',300,'critical',25)
)
INSERT INTO agent.workflow_schedules (
    schedule_key,workflow_key,owner_agent,skill_key,schedule_name,cadence_seconds,
    schedule_timezone,priority,enabled,approval_required,dedupe_open_task,next_run_at,status,metadata
)
SELECT schedule_key,workflow_key,owner_agent,skill_key,schedule_name,cadence_seconds,
       'Asia/Kolkata',priority,false,false,true,now()+make_interval(mins=>offset_minutes),'scheduled',
       '{"routine_contract":"v1","disabled_safe_default":true,"model_calls":false,"broker_write_allowed":false}'::jsonb
FROM schedule_seed
ON CONFLICT (schedule_key) DO UPDATE SET
    workflow_key=EXCLUDED.workflow_key,owner_agent=EXCLUDED.owner_agent,skill_key=EXCLUDED.skill_key,
    schedule_name=EXCLUDED.schedule_name,cadence_seconds=EXCLUDED.cadence_seconds,
    schedule_timezone=EXCLUDED.schedule_timezone,priority=EXCLUDED.priority,
    approval_required=false,dedupe_open_task=true,status='scheduled',
    metadata=EXCLUDED.metadata,updated_at=now();

WITH definition_seed(routine_key,routine_name,description,owner_agent,schedule_key) AS (
    VALUES
      ('daily_system_health','Daily system health','Run the full Doctor registry and persist only actionable degradation.','Jarvis','routine-daily-system-health'),
      ('obsidian_incremental_index','Obsidian incremental index','Update the existing managed Obsidian index from the external SSD vault.','Librarian Agent','routine-obsidian-incremental-index'),
      ('research_company_change_monitor','Research company change monitor','Review already-authorized filing/news changes for followed companies exactly once per event.','Research Director','routine-research-company-change-monitor'),
      ('stale_task_and_lease_reaper','Stale task and lease reaper','Use the existing fenced receipt-aware recovery function for expired leases.','DevOps Engineer','routine-stale-task-and-lease-reaper'),
      ('zerodha_session_and_stream_watch','Zerodha session and stream watch','Report existing session, WebSocket and quote freshness without credential or broker mutation.','Jarvis','routine-zerodha-session-stream-watch')
)
INSERT INTO agent.routine_definitions
    (routine_key,routine_name,description,owner_agent,schedule_key,current_version,control_state)
SELECT routine_key,routine_name,description,owner_agent,schedule_key,1,'disabled'
FROM definition_seed
ON CONFLICT (routine_key) DO UPDATE SET
    routine_name=EXCLUDED.routine_name,description=EXCLUDED.description,
    owner_agent=EXCLUDED.owner_agent,schedule_key=EXCLUDED.schedule_key,
    updated_at=now();

WITH version_seed(
    routine_key,skill_key,trigger_kind,event_filter,input_policy,idempotency_template,
    permission_class,timeout_seconds,cooldown_seconds,retry_policy,stale_data_policy,
    approval_policy,output_destinations,allowed_tools,definition_hash,metadata
) AS (
    VALUES
      ('daily_system_health','daily_system_health_routine','schedule','{}'::jsonb,'{"private_payload_allowed":false}'::jsonb,'daily_system_health:{due_at}','read_only',60,300,'{"max_attempts":2,"backoff_seconds":[30,120]}'::jsonb,'{"unknown_is_not_healthy":true}'::jsonb,'{"enable_requires_explicit_confirmation":true,"safe_fix_separate":true}'::jsonb,ARRAY['ops.doctor_runs'],ARRAY['ai_os_doctor'],'77c390ac27342527877855597701b218434c50074a411296ac3204558efc96e2','{"model_calls":false}'::jsonb),
      ('obsidian_incremental_index','obsidian_incremental_index_routine','schedule','{}'::jsonb,'{"vault_root":"external_ssd_only","preserve_human_content":true}'::jsonb,'obsidian_incremental_index:{due_at}','internal_safe_write',600,300,'{"max_attempts":2,"backoff_seconds":[60,300]}'::jsonb,'{"missing_ssd":"refuse","index_lag":"report"}'::jsonb,'{"enable_requires_explicit_confirmation":true}'::jsonb,ARRAY['knowledge.index_runs'],ARRAY['index_obsidian_vault'],'f0a2e546e1b2a523dce87b4e41480b85c8ea91ef7396cd9a78a85ef17fb6acb1','{"model_calls":false,"managed_index_only":true}'::jsonb),
      ('research_company_change_monitor','research_company_change_monitor_routine','event','{"event_types":["filing","catalyst"],"authorized_sources_only":true}'::jsonb,'{"public_or_authorized_stored_source_only":true}'::jsonb,'research_company_change_monitor:{event_hash}','internal_safe_write',300,900,'{"max_attempts":2,"backoff_seconds":[60,300]}'::jsonb,'{"missing_source":"record_evidence_debt","stale_source":"do_not_infer_change"}'::jsonb,'{"paid_model":"separate_preflight","decision_change":"human_review"}'::jsonb,ARRAY['research.company_research_updates','research.research_case_source_jobs'],ARRAY['company_research_monitor'],'ac7498c00f99a933de44b0de56bd845932f8234f72cd2ce8256e824b861580b0','{"model_calls":false,"source_fetches":false}'::jsonb),
      ('stale_task_and_lease_reaper','stale_task_and_lease_reaper_routine','schedule','{}'::jsonb,'{"receipt_aware":true,"idempotent_read_requeue_only":true}'::jsonb,'stale_task_and_lease_reaper:{due_at}','internal_safe_write',60,60,'{"max_attempts":1,"backoff_seconds":[]}'::jsonb,'{"uncertain_side_effect":"block_for_reconciliation"}'::jsonb,'{"enable_requires_explicit_confirmation":true}'::jsonb,ARRAY['agent.task_events'],ARRAY['release_expired_leases'],'c58bcb728075b8414d726f852403e8ad14367db5bb7af3b7575a2c17a7ee97d4','{"model_calls":false}'::jsonb),
      ('zerodha_session_and_stream_watch','zerodha_session_stream_watch_routine','schedule','{}'::jsonb,'{"read_health_only":true,"never_reveal_secret":true}'::jsonb,'zerodha_session_and_stream_watch:{due_at}','read_only',30,60,'{"max_attempts":2,"backoff_seconds":[15,60]}'::jsonb,'{"stale_quote":"block_or_label_fallback","daily_login":"human_action"}'::jsonb,'{"credential_action":"prohibited","broker_action":"prohibited"}'::jsonb,ARRAY['ops.doctor_runs'],ARRAY['zerodha_health_read'],'8c3c4c062dadba9df0e0640c6bf9c2bd774610000e23adfd2926f0696e4a165f','{"model_calls":false,"get_only":true}'::jsonb)
)
INSERT INTO agent.routine_versions (
    routine_key,version,skill_key,trigger_kind,event_filter,input_policy,idempotency_template,
    permission_class,timeout_seconds,cooldown_seconds,retry_policy,cost_budget_usd,
    stale_data_policy,approval_policy,output_destinations,allowed_tools,definition_hash,metadata
)
SELECT routine_key,1,skill_key,trigger_kind,event_filter,input_policy,idempotency_template,
       permission_class,timeout_seconds,cooldown_seconds,retry_policy,0,
       stale_data_policy,approval_policy,output_destinations,allowed_tools,definition_hash,metadata
FROM version_seed
ON CONFLICT (routine_key,version) DO NOTHING;

CREATE OR REPLACE FUNCTION agent.start_routine_run(
    p_routine_key TEXT,
    p_trigger_kind TEXT,
    p_event_hash TEXT,
    p_idempotency_key TEXT,
    p_input JSONB,
    p_actor TEXT,
    p_test_mode BOOLEAN DEFAULT false
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=agent,core,pg_temp
AS $fn$
DECLARE
    definition agent.routine_definitions;
    version_row agent.routine_versions;
    created_id BIGINT;
    selected_run agent.routine_runs;
    normalized_trigger TEXT := CASE WHEN p_test_mode THEN 'test' ELSE lower(coalesce(p_trigger_kind,'')) END;
BEGIN
    SELECT * INTO definition FROM agent.routine_definitions WHERE routine_key=p_routine_key FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'unknown routine'; END IF;
    SELECT * INTO version_row FROM agent.routine_versions
      WHERE routine_key=p_routine_key AND version=definition.current_version;
    IF NOT FOUND THEN RAISE EXCEPTION 'routine version unavailable'; END IF;
    IF NOT p_test_mode AND definition.control_state<>'enabled' THEN
        RAISE EXCEPTION 'routine is not explicitly enabled';
    END IF;
    IF NOT p_test_mode AND version_row.trigger_kind='schedule'
       AND NOT EXISTS (SELECT 1 FROM agent.workflow_schedules schedule
         WHERE schedule.schedule_key=definition.schedule_key AND schedule.enabled) THEN
        RAISE EXCEPTION 'scheduled routine is not enabled on the canonical scheduler';
    END IF;
    IF NOT p_test_mode AND version_row.trigger_kind='event'
       AND EXISTS (SELECT 1 FROM agent.workflow_schedules schedule
         WHERE schedule.schedule_key=definition.schedule_key AND schedule.enabled) THEN
        RAISE EXCEPTION 'event routine must not enable periodic materialization';
    END IF;
    IF normalized_trigger NOT IN ('schedule','event','manual','test') THEN RAISE EXCEPTION 'invalid routine trigger'; END IF;
    IF NOT p_test_mode AND version_row.trigger_kind='event' AND normalized_trigger<>'event' THEN RAISE EXCEPTION 'event routine requires an event trigger'; END IF;
    IF NOT p_test_mode AND version_row.trigger_kind='schedule' AND normalized_trigger NOT IN ('schedule','manual') THEN RAISE EXCEPTION 'scheduled routine rejects event triggers'; END IF;
    IF coalesce(length(p_idempotency_key),0) NOT BETWEEN 8 AND 240 THEN RAISE EXCEPTION 'bounded idempotency key required'; END IF;
    IF normalized_trigger='event' AND p_event_hash IS NULL THEN RAISE EXCEPTION 'event trigger requires a sha256 event hash'; END IF;
    IF p_event_hash IS NOT NULL AND p_event_hash !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'event hash must be sha256'; END IF;
    IF core.jsonb_contains_raw_secret(coalesce(p_input,'{}'::jsonb)) THEN RAISE EXCEPTION 'secret-shaped routine input refused'; END IF;
    IF version_row.cost_budget_usd<>0 THEN RAISE EXCEPTION 'autonomous routine model budget must remain zero'; END IF;

    INSERT INTO agent.routine_runs(
        run_key,routine_key,routine_version,trigger_kind,event_hash,idempotency_key,
        status,requested_by,input_snapshot
    ) VALUES (
        p_routine_key||'-'||to_char(clock_timestamp(),'YYYYMMDDHH24MISSUS')||'-'||substr(md5(random()::text),1,8),
        p_routine_key,definition.current_version,normalized_trigger,p_event_hash,p_idempotency_key,
        'running',p_actor,coalesce(p_input,'{}'::jsonb)
    ) ON CONFLICT (routine_key,idempotency_key) DO NOTHING RETURNING id INTO created_id;

    SELECT * INTO selected_run FROM agent.routine_runs
      WHERE routine_key=p_routine_key AND idempotency_key=p_idempotency_key;
    RETURN jsonb_build_object(
        'run_id',selected_run.id,'run_key',selected_run.run_key,'routine_key',selected_run.routine_key,
        'routine_version',selected_run.routine_version,'status',selected_run.status,
        'created',(created_id IS NOT NULL),'duplicate',(created_id IS NULL),
        'test_mode',p_test_mode,'model_cost_usd',0,'broker_write_allowed',false,
        'external_write_allowed',false,'client_write_allowed',false
    );
END
$fn$;

CREATE OR REPLACE FUNCTION agent.finish_routine_run(
    p_run_key TEXT,
    p_status TEXT,
    p_summary TEXT,
    p_evidence JSONB DEFAULT '[]'::jsonb,
    p_artifact_path TEXT DEFAULT NULL,
    p_artifact_hash TEXT DEFAULT NULL,
    p_error_code TEXT DEFAULT NULL
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=agent,core,pg_temp
AS $fn$
DECLARE selected_run agent.routine_runs;
BEGIN
    IF p_status NOT IN ('completed','partial','failed','refused') THEN RAISE EXCEPTION 'invalid terminal routine status'; END IF;
    IF core.jsonb_contains_raw_secret(coalesce(p_evidence,'[]'::jsonb)) THEN RAISE EXCEPTION 'secret-shaped routine evidence refused'; END IF;
    IF p_artifact_path IS NOT NULL AND p_artifact_path NOT LIKE '/Volumes/Devarsh SSD/AI OS Data/%' THEN
        RAISE EXCEPTION 'routine artifact must remain on external SSD';
    END IF;
    IF p_artifact_hash IS NOT NULL AND p_artifact_hash !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'artifact hash must be sha256'; END IF;
    UPDATE agent.routine_runs SET status=p_status,result_summary=left(p_summary,2000),
        evidence=coalesce(p_evidence,'[]'::jsonb),output_artifact_path=p_artifact_path,
        output_artifact_hash=p_artifact_hash,error_code=left(p_error_code,120),finished_at=clock_timestamp()
    WHERE run_key=p_run_key AND status='running' RETURNING * INTO selected_run;
    IF NOT FOUND THEN RAISE EXCEPTION 'routine run is not active'; END IF;
    RETURN jsonb_build_object('run_id',selected_run.id,'run_key',selected_run.run_key,
        'routine_key',selected_run.routine_key,'status',selected_run.status,
        'finished_at',selected_run.finished_at,'model_cost_usd',0,
        'broker_write_allowed',false,'external_write_allowed',false,'client_write_allowed',false);
END
$fn$;

CREATE OR REPLACE FUNCTION agent.control_routine(
    p_routine_key TEXT,p_action TEXT,p_actor TEXT,p_reason TEXT,p_confirmed BOOLEAN
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=agent,pg_temp
AS $fn$
DECLARE definition agent.routine_definitions; desired TEXT; version_trigger TEXT; schedule_enabled BOOLEAN;
BEGIN
    IF NOT p_confirmed THEN RAISE EXCEPTION 'explicit routine control confirmation required'; END IF;
    IF length(trim(coalesce(p_actor,''))) NOT BETWEEN 1 AND 160 THEN RAISE EXCEPTION 'bounded routine actor required'; END IF;
    IF length(trim(coalesce(p_reason,''))) NOT BETWEEN 8 AND 500 THEN RAISE EXCEPTION 'bounded routine control reason required'; END IF;
    desired := CASE lower(p_action) WHEN 'enable' THEN 'enabled' WHEN 'pause' THEN 'paused' WHEN 'disable' THEN 'disabled' ELSE NULL END;
    IF desired IS NULL THEN RAISE EXCEPTION 'unsupported routine action'; END IF;
    SELECT * INTO definition FROM agent.routine_definitions WHERE routine_key=p_routine_key FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'unknown routine'; END IF;
    SELECT trigger_kind INTO version_trigger FROM agent.routine_versions
      WHERE routine_key=p_routine_key AND version=definition.current_version;
    IF NOT FOUND THEN RAISE EXCEPTION 'routine version unavailable'; END IF;
    schedule_enabled := (desired='enabled' AND version_trigger='schedule');
    INSERT INTO agent.routine_control_events(routine_key,prior_state,new_state,actor,reason)
      VALUES(p_routine_key,definition.control_state,desired,p_actor,left(p_reason,500));
    UPDATE agent.routine_definitions SET control_state=desired,last_controlled_by=p_actor,
      last_controlled_at=clock_timestamp(),updated_at=clock_timestamp() WHERE routine_key=p_routine_key;
    UPDATE agent.workflow_schedules SET enabled=schedule_enabled,updated_at=clock_timestamp()
      WHERE schedule_key=definition.schedule_key;
    RETURN jsonb_build_object('routine_key',p_routine_key,'prior_state',definition.control_state,
      'control_state',desired,'schedule_enabled',schedule_enabled,'trigger_kind',version_trigger,'broker_write_allowed',false);
END
$fn$;

REVOKE ALL ON FUNCTION agent.start_routine_run(TEXT,TEXT,TEXT,TEXT,JSONB,TEXT,BOOLEAN) FROM PUBLIC;
REVOKE ALL ON FUNCTION agent.finish_routine_run(TEXT,TEXT,TEXT,JSONB,TEXT,TEXT,TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION agent.control_routine(TEXT,TEXT,TEXT,TEXT,BOOLEAN) FROM PUBLIC;

CREATE OR REPLACE VIEW agent.v_routine_control AS
SELECT definition.routine_key,definition.routine_name,definition.description,
       definition.owner_agent,definition.current_version,definition.control_state,
       definition.schedule_key,schedule.enabled AS schedule_enabled,schedule.next_run_at,
       schedule.last_materialized_at,schedule.cadence_seconds,schedule.schedule_timezone,
       version.skill_key,version.trigger_kind,version.permission_class,version.timeout_seconds,
       version.cooldown_seconds,version.retry_policy,version.cost_budget_usd,
       version.stale_data_policy,version.approval_policy,version.output_destinations,
       version.allowed_tools,latest.run_key AS last_run_key,latest.status AS last_run_status,
       latest.started_at AS last_run_at,latest.finished_at AS last_finished_at,
       false AS broker_write_allowed
FROM agent.routine_definitions definition
JOIN agent.routine_versions version
  ON version.routine_key=definition.routine_key AND version.version=definition.current_version
JOIN agent.workflow_schedules schedule ON schedule.schedule_key=definition.schedule_key
LEFT JOIN LATERAL (
    SELECT run.run_key,run.status,run.started_at,run.finished_at
    FROM agent.routine_runs run WHERE run.routine_key=definition.routine_key
    ORDER BY run.started_at DESC,run.id DESC LIMIT 1
) latest ON true;

CREATE OR REPLACE VIEW agent.v_routine_run_history AS
SELECT run.id,run.run_key,run.routine_key,definition.routine_name,run.routine_version,
       run.trigger_kind,run.event_hash,run.idempotency_key,run.status,run.requested_by,
       run.result_summary,run.evidence,run.output_artifact_path,run.output_artifact_hash,
       run.error_code,run.started_at,run.finished_at,run.model_cost_usd,
       false AS broker_write_allowed,false AS external_write_allowed,false AS client_write_allowed
FROM agent.routine_runs run
JOIN agent.routine_definitions definition USING(routine_key);

INSERT INTO agent.tool_registry(tool_name,tool_type,owning_agent,permission_level,enabled,description,config)
VALUES
 ('ai_os_doctor','runtime_health','Jarvis','read_only',true,'Run bounded Doctor checks and read persisted drift evidence. Safe repair is a separate allowlisted operator action.','{"reads":["ops.doctor_check_registry","ops.v_doctor_latest"],"writes":["ops.doctor_runs","ops.doctor_check_results"],"secrets_returned":false,"broker_write_allowed":false}'),
 ('ai_os_doctor_safe_fix','runtime_repair','DevOps Engineer','write_db_manual_only',true,'Apply only a named allowlisted safe fix with before/after receipt; currently limited to the existing expired-lease reaper.','{"allowlist":["release_expired_leases"],"credential_change_allowed":false,"broker_write_allowed":false}'),
 ('ai_os_routine_control','routine_control','Jarvis','write_db_manual_only',true,'List, test, explicitly enable or pause versioned routines on the existing workflow scheduler.','{"functions":["agent.start_routine_run","agent.finish_routine_run","agent.control_routine"],"default_state":"disabled","paid_model_calls":false,"broker_write_allowed":false}')
ON CONFLICT(tool_name) DO UPDATE SET
  tool_type=EXCLUDED.tool_type,owning_agent=EXCLUDED.owning_agent,
  permission_level=EXCLUDED.permission_level,enabled=EXCLUDED.enabled,
  description=EXCLUDED.description,config=EXCLUDED.config;

INSERT INTO core.schema_migrations(
    migration_number,migration_key,definition_checksum_sha256,description,metadata
)
VALUES (
    260,
    '260_ai_os_doctor_and_routines_v1',
    '881a28749e8a6e50268ab9ae5b8c69dfea7c6c3cb2b28c84b49485303b143384',
    'AI OS Doctor evidence registry, allowlisted safe fix receipt and five disabled versioned routines on the existing schedule authority',
    '{"doctor_checks":21,"routine_count":5,"routines_enabled":false,"second_scheduler_created":false,"autonomous_model_cost_usd":0,"credential_change_allowed":false,"broker_write_allowed":false,"external_write_allowed":false}'::jsonb
)
ON CONFLICT(migration_number) DO NOTHING;

DO $guard$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM core.schema_migrations
        WHERE migration_number=260
          AND migration_key='260_ai_os_doctor_and_routines_v1'
          AND definition_checksum_sha256='881a28749e8a6e50268ab9ae5b8c69dfea7c6c3cb2b28c84b49485303b143384'
    ) THEN RAISE EXCEPTION 'migration 260 ledger mismatch'; END IF;
    IF (
        SELECT count(*)
        FROM agent.routine_definitions
        WHERE routine_key=ANY(ARRAY[
            'daily_system_health','obsidian_incremental_index',
            'research_company_change_monitor','stale_task_and_lease_reaper',
            'zerodha_session_and_stream_watch'
        ])
    )<>5 THEN RAISE EXCEPTION 'routine seed is incomplete'; END IF;
    -- Re-running migrations must not undo an operator's later explicit control
    -- decision. Scheduled routines mirror control state; event routines stay
    -- off periodic materialization even when event handling is enabled.
    IF EXISTS (
        SELECT 1
        FROM agent.routine_definitions definition
        JOIN agent.routine_versions version
          ON version.routine_key=definition.routine_key AND version.version=definition.current_version
        JOIN agent.workflow_schedules schedule USING(schedule_key)
        WHERE definition.routine_key=ANY(ARRAY[
            'daily_system_health','obsidian_incremental_index',
            'research_company_change_monitor','stale_task_and_lease_reaper',
            'zerodha_session_and_stream_watch'
        ])
          AND ((version.trigger_kind='schedule' AND schedule.enabled<>(definition.control_state='enabled'))
            OR (version.trigger_kind='event' AND schedule.enabled))
    ) THEN RAISE EXCEPTION 'routine definition and schedule control state differ'; END IF;
    IF EXISTS (
        SELECT 1 FROM agent.routine_versions
        WHERE routine_key=ANY(ARRAY[
            'daily_system_health','obsidian_incremental_index',
            'research_company_change_monitor','stale_task_and_lease_reaper',
            'zerodha_session_and_stream_watch'
        ]) AND cost_budget_usd<>0
    )
       THEN RAISE EXCEPTION 'routine autonomous model cost must remain zero'; END IF;
END
$guard$;

COMMIT;
