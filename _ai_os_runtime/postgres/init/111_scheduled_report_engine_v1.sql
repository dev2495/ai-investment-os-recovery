CREATE TABLE IF NOT EXISTS ops.report_schedules (
    id BIGSERIAL PRIMARY KEY,
    report_key TEXT NOT NULL UNIQUE,
    report_name TEXT NOT NULL,
    report_family TEXT NOT NULL,
    cadence TEXT NOT NULL CHECK (cadence IN ('daily', 'weekly', 'monthly', 'manual')),
    owner_agent TEXT NOT NULL,
    skill_key TEXT REFERENCES agent.skills(skill_key) ON DELETE SET NULL,
    target_folder TEXT NOT NULL,
    approval_required BOOLEAN NOT NULL DEFAULT false,
    enabled BOOLEAN NOT NULL DEFAULT true,
    source_views TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    description TEXT NOT NULL,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ops.report_runs (
    id BIGSERIAL PRIMARY KEY,
    schedule_id BIGINT NOT NULL REFERENCES ops.report_schedules(id) ON DELETE CASCADE,
    run_key TEXT NOT NULL UNIQUE,
    period_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    worker_run_id BIGINT REFERENCES agent.worker_runs(id) ON DELETE SET NULL,
    output_note_path TEXT,
    summary TEXT,
    source_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (schedule_id, period_key)
);

CREATE INDEX IF NOT EXISTS idx_report_runs_schedule ON ops.report_runs (schedule_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_report_runs_status ON ops.report_runs (status, created_at DESC);

INSERT INTO ops.report_schedules (
    report_key, report_name, report_family, cadence, owner_agent, skill_key,
    target_folder, approval_required, enabled, source_views, description, config
)
VALUES
    ('daily_market_brief', 'Daily Market Brief', 'market_brief', 'daily', 'News Analyst', 'daily_office_brief', 'ai memory/00 AI OS/Briefs/Daily', false, true, ARRAY['trading.ohlcv','market.news_items','core.v_latest_data_source_freshness'], 'Market data, news, signals, and freshness evidence without an autonomous trading recommendation.', '{"run_after_local":"07:45"}'::jsonb),
    ('daily_portfolio_brief', 'Daily Portfolio Brief', 'portfolio_brief', 'daily', 'Portfolio Manager', 'portfolio_daily_brief', 'ai memory/00 AI OS/Briefs/Daily', false, true, ARRAY['portfolio.positions','books.v_symbol_book_exposure','risk.v_portfolio_risk_limit_checks'], 'Cross-client positions, books, concentration, thesis gaps, and risk exceptions.', '{"run_after_local":"07:50"}'::jsonb),
    ('daily_agent_activity', 'Daily Agent Activity Brief', 'agent_activity', 'daily', 'Jarvis', 'daily_office_brief', 'ai memory/00 AI OS/Briefs/Daily', false, true, ARRAY['agent.v_live_office_agent_activity','agent.tasks','agent.worker_runs'], 'Employee workload, durable handoffs, completed outputs, blocked work, and approvals.', '{"run_after_local":"07:55"}'::jsonb),
    ('data_source_freshness', 'Data Source Freshness Report', 'operations_report', 'daily', 'Data Steward', 'model_runtime_check', 'ai memory/00 AI OS/Reports/Scheduled', false, true, ARRAY['core.v_latest_data_source_freshness','core.v_recent_data_source_checks'], 'Freshness, missing checks, stale sources, row counts, and linked risk events.', '{"run_after_local":"08:00"}'::jsonb),
    ('provider_readiness', 'Provider Readiness Report', 'operations_report', 'daily', 'Jarvis', 'model_runtime_check', 'ai memory/00 AI OS/Reports/Scheduled', false, true, ARRAY['core.v_provider_readiness_board','agent.v_model_endpoint_control'], 'Model, MCP, browser, and connector readiness with assignment gates.', '{"run_after_local":"08:05"}'::jsonb),
    ('model_cost', 'Model Cost Report', 'cost_report', 'daily', 'Jarvis', 'model_runtime_check', 'ai memory/00 AI OS/Reports/Scheduled', false, true, ARRAY['agent.v_model_cost_summary','agent.v_model_route_cost_summary'], 'Recorded local/cloud model cost events and cap state; absence of cost events is stated explicitly.', '{"run_after_local":"08:10"}'::jsonb),
    ('full_system_status', 'Full System Status Report', 'operations_report', 'daily', 'Jarvis', 'model_runtime_check', 'ai memory/00 AI OS/Reports/Scheduled', false, true, ARRAY['core.v_control_plane_snapshot','core.v_os_blueprint_summary','trading.v_execution_control_state'], 'System, blueprint, storage, provider, connector, worker, and execution-safety status.', '{"run_after_local":"08:15"}'::jsonb),
    ('weekly_risk', 'Weekly Risk Report', 'risk_report', 'weekly', 'Risk Agent', 'daily_office_brief', 'ai memory/00 AI OS/Reports/Scheduled', false, true, ARRAY['risk.events','risk.v_portfolio_risk_limit_checks','books.v_cross_book_conflicts'], 'Independent weekly risk review across clients, books, strategies, limits, and execution gates.', '{"weekday":1,"run_after_local":"08:20"}'::jsonb),
    ('weekly_research_digest', 'Weekly Research Digest', 'research_digest', 'weekly', 'Research Analyst', 'daily_office_brief', 'ai memory/00 AI OS/Reports/Scheduled', false, true, ARRAY['portfolio.v_long_term_research_updates','research.v_corporate_filing_inbox','agent.v_output_artifact_registry_v2'], 'Weekly filings, long-term thesis updates, special situations, research outputs, and open evidence gaps.', '{"weekday":1,"run_after_local":"08:25"}'::jsonb),
    ('monthly_client_report', 'Monthly Client Report Drafts', 'client_report', 'monthly', 'Portfolio Manager', 'portfolio_daily_brief', 'ai memory/00 AI OS/Reports/Client Drafts', true, true, ARRAY['portfolio.clients','portfolio.positions','books.v_client_book_exposure'], 'Draft-only monthly client folio report. Sending and recommendations require human approval.', '{"month_day":1,"run_after_local":"08:30","draft_only":true}'::jsonb)
ON CONFLICT (report_key) DO UPDATE SET
    report_name = EXCLUDED.report_name,
    report_family = EXCLUDED.report_family,
    cadence = EXCLUDED.cadence,
    owner_agent = EXCLUDED.owner_agent,
    skill_key = EXCLUDED.skill_key,
    target_folder = EXCLUDED.target_folder,
    approval_required = EXCLUDED.approval_required,
    enabled = EXCLUDED.enabled,
    source_views = EXCLUDED.source_views,
    description = EXCLUDED.description,
    config = EXCLUDED.config,
    updated_at = now();

CREATE OR REPLACE VIEW ops.v_report_schedule_status AS
SELECT
    schedule.id,
    schedule.report_key,
    schedule.report_name,
    schedule.report_family,
    schedule.cadence,
    schedule.owner_agent,
    schedule.skill_key,
    schedule.target_folder,
    schedule.approval_required,
    schedule.enabled,
    schedule.source_views,
    schedule.description,
    schedule.config,
    latest.id AS latest_run_id,
    latest.run_key AS latest_run_key,
    latest.period_key AS latest_period_key,
    latest.status AS latest_status,
    latest.output_note_path AS latest_output_note_path,
    latest.summary AS latest_summary,
    latest.finished_at AS latest_finished_at,
    CASE schedule.cadence
        WHEN 'daily' THEN coalesce(latest.period_key, '') <> to_char(now() AT TIME ZONE 'Asia/Kolkata', 'YYYY-MM-DD')
        WHEN 'weekly' THEN coalesce(latest.period_key, '') <> to_char(now() AT TIME ZONE 'Asia/Kolkata', 'IYYY-"W"IW')
        WHEN 'monthly' THEN coalesce(latest.period_key, '') <> to_char(now() AT TIME ZONE 'Asia/Kolkata', 'YYYY-MM')
        ELSE false
    END AS due_now,
    schedule.updated_at
FROM ops.report_schedules schedule
LEFT JOIN LATERAL (
    SELECT run.*
    FROM ops.report_runs run
    WHERE run.schedule_id = schedule.id
    ORDER BY run.created_at DESC
    LIMIT 1
) latest ON true;

CREATE OR REPLACE VIEW ops.v_recent_report_runs AS
SELECT
    run.id,
    run.run_key,
    run.period_key,
    schedule.report_key,
    schedule.report_name,
    schedule.report_family,
    schedule.cadence,
    schedule.owner_agent,
    schedule.approval_required,
    run.status,
    run.task_id,
    run.worker_run_id,
    run.output_note_path,
    run.summary,
    run.source_snapshot,
    run.evidence,
    run.error_message,
    run.started_at,
    run.finished_at,
    run.updated_at
FROM ops.report_runs run
JOIN ops.report_schedules schedule ON schedule.id = run.schedule_id
ORDER BY run.created_at DESC;
