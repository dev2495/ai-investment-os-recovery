BEGIN;

CREATE TABLE IF NOT EXISTS research.market_research_heartbeat_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status IN (
        'running','no_material_change','source_blocked','deduped','workflow_created','failed'
    )),
    lookback_minutes INTEGER NOT NULL CHECK (lookback_minutes BETWEEN 5 AND 1440),
    cooldown_minutes INTEGER NOT NULL CHECK (cooldown_minutes BETWEEN 15 AND 10080),
    candidate_count INTEGER NOT NULL DEFAULT 0 CHECK (candidate_count >= 0),
    material_candidate_count INTEGER NOT NULL DEFAULT 0 CHECK (material_candidate_count >= 0),
    selected_news_id BIGINT REFERENCES market.news_items(id) ON DELETE SET NULL,
    source_fingerprint TEXT,
    graph_run_id BIGINT REFERENCES agent.graph_runs(id) ON DELETE SET NULL,
    graph_created BOOLEAN NOT NULL DEFAULT false,
    skip_reason TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0 CHECK (retry_count BETWEEN 0 AND 10),
    next_retry_at TIMESTAMPTZ,
    cooldown_until TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    error_message TEXT,
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed = false),
    live_execution_allowed BOOLEAN NOT NULL DEFAULT false CHECK (live_execution_allowed = false),
    capital_action_allowed BOOLEAN NOT NULL DEFAULT false CHECK (capital_action_allowed = false),
    created_by TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_market_research_heartbeat_runs_recent
    ON research.market_research_heartbeat_runs (started_at DESC);

CREATE INDEX IF NOT EXISTS ix_market_research_heartbeat_runs_source
    ON research.market_research_heartbeat_runs (selected_news_id, source_fingerprint, started_at DESC);

CREATE OR REPLACE VIEW research.v_market_research_heartbeat_runs AS
SELECT run.id,run.run_key,run.status,run.lookback_minutes,run.cooldown_minutes,
       run.candidate_count,run.material_candidate_count,run.selected_news_id,
       news.source_name,news.source_url,news.title AS selected_title,
       news.published_at AS source_published_at,news.captured_at AS source_captured_at,
       run.source_fingerprint,run.graph_run_id,run.graph_created,run.skip_reason,
       run.retry_count,run.next_retry_at,run.cooldown_until,run.evidence,
       run.error_message,run.broker_write_allowed,run.live_execution_allowed,
       run.capital_action_allowed,run.created_by,run.started_at,run.finished_at,
       run.created_at,run.updated_at
FROM research.market_research_heartbeat_runs run
LEFT JOIN market.news_items news ON news.id=run.selected_news_id;

COMMENT ON TABLE research.market_research_heartbeat_runs IS
'Auditable bounded public-market heartbeat entry records. A run may create a research graph only from cited current public evidence; it can never write to a broker or allocate capital.';

COMMENT ON VIEW research.v_market_research_heartbeat_runs IS
'Read-only operating view for heartbeat materiality, source fingerprint, graph linkage, retry/cooldown, and fail-closed safety state.';

COMMIT;
