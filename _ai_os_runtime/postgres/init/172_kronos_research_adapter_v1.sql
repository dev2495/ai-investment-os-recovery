
BEGIN;

CREATE TABLE IF NOT EXISTS strategy.kronos_forecast_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    graph_run_id BIGINT REFERENCES agent.graph_runs(id) ON DELETE SET NULL,
    graph_node_run_id BIGINT REFERENCES agent.graph_node_runs(id) ON DELETE SET NULL,
    symbol_id BIGINT NOT NULL REFERENCES trading.symbols(id),
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    as_of TIMESTAMPTZ NOT NULL,
    lookback INTEGER NOT NULL CHECK (lookback BETWEEN 32 AND 2048),
    horizon INTEGER NOT NULL CHECK (horizon BETWEEN 1 AND 256),
    path_count INTEGER NOT NULL CHECK (path_count BETWEEN 20 AND 256),
    model_variant TEXT NOT NULL DEFAULT 'mini',
    model_repo TEXT NOT NULL,
    model_revision TEXT NOT NULL,
    tokenizer_repo TEXT NOT NULL,
    tokenizer_revision TEXT NOT NULL,
    source_code_repo TEXT NOT NULL,
    source_code_revision TEXT NOT NULL,
    source_row_count INTEGER NOT NULL CHECK (source_row_count >= 32),
    source_start_ts TIMESTAMPTZ NOT NULL,
    source_end_ts TIMESTAMPTZ NOT NULL,
    source_hash TEXT NOT NULL,
    output_hash TEXT,
    runtime_kind TEXT NOT NULL DEFAULT 'isolated_python',
    device TEXT,
    seed_base BIGINT NOT NULL,
    temperature NUMERIC NOT NULL CHECK (temperature > 0 AND temperature <= 5),
    top_p NUMERIC NOT NULL CHECK (top_p > 0 AND top_p <= 1),
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued','running','completed','failed','validation_failed')),
    research_only BOOLEAN NOT NULL DEFAULT true CHECK (research_only),
    direct_signal BOOLEAN NOT NULL DEFAULT false CHECK (NOT direct_signal),
    broker_order_allowed BOOLEAN NOT NULL DEFAULT false CHECK (NOT broker_order_allowed),
    input_contract JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_contract JSONB NOT NULL DEFAULT '{}'::jsonb,
    validation JSONB NOT NULL DEFAULT '{}'::jsonb,
    error JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_kronos_runs_graph
    ON strategy.kronos_forecast_runs(graph_run_id, graph_node_run_id);
CREATE INDEX IF NOT EXISTS idx_kronos_runs_symbol
    ON strategy.kronos_forecast_runs(symbol, exchange, timeframe, as_of DESC);
CREATE INDEX IF NOT EXISTS idx_kronos_runs_status
    ON strategy.kronos_forecast_runs(status, created_at DESC);

CREATE TABLE IF NOT EXISTS strategy.kronos_forecast_paths (
    id BIGSERIAL PRIMARY KEY,
    forecast_run_id BIGINT NOT NULL REFERENCES strategy.kronos_forecast_runs(id) ON DELETE CASCADE,
    path_index INTEGER NOT NULL CHECK (path_index >= 1),
    step_index INTEGER NOT NULL CHECK (step_index >= 1),
    forecast_ts TIMESTAMPTZ NOT NULL,
    open NUMERIC NOT NULL,
    high NUMERIC NOT NULL,
    low NUMERIC NOT NULL,
    close NUMERIC NOT NULL,
    volume NUMERIC NOT NULL,
    amount NUMERIC,
    close_return NUMERIC,
    ohlc_valid BOOLEAN NOT NULL,
    volume_valid BOOLEAN NOT NULL,
    raw_output JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (forecast_run_id, path_index, step_index)
);

CREATE INDEX IF NOT EXISTS idx_kronos_paths_run_ts
    ON strategy.kronos_forecast_paths(forecast_run_id, forecast_ts, path_index);

CREATE TABLE IF NOT EXISTS strategy.kronos_forecast_scores (
    id BIGSERIAL PRIMARY KEY,
    forecast_run_id BIGINT NOT NULL REFERENCES strategy.kronos_forecast_runs(id) ON DELETE CASCADE,
    score_kind TEXT NOT NULL
        CHECK (score_kind IN ('ex_ante_distribution','realized_calibration','walk_forward_validation')),
    evaluation_start_ts TIMESTAMPTZ,
    evaluation_end_ts TIMESTAMPTZ,
    realized_points INTEGER NOT NULL DEFAULT 0 CHECK (realized_points >= 0),
    interval_coverage NUMERIC,
    directional_accuracy NUMERIC,
    crps NUMERIC,
    mean_interval_width NUMERIC,
    ohlc_validity NUMERIC,
    volume_validity NUMERIC,
    validation_status TEXT NOT NULL DEFAULT 'needs_review'
        CHECK (validation_status IN ('needs_review','passed','failed','insufficient_evidence')),
    feature_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    scored_by TEXT NOT NULL DEFAULT 'kronos_inference_adapter',
    scored_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (forecast_run_id, score_kind, evaluation_end_ts)
);

CREATE OR REPLACE VIEW strategy.v_kronos_research_runs AS
SELECT run.id AS forecast_run_id,run.run_key,run.task_id,run.graph_run_id,
       run.graph_node_run_id,run.symbol,run.exchange,run.timeframe,run.as_of,
       run.lookback,run.horizon,run.path_count,run.model_variant,
       run.model_repo,run.model_revision,run.tokenizer_repo,
       run.tokenizer_revision,run.source_code_revision,run.source_row_count,
       run.source_start_ts,run.source_end_ts,run.source_hash,run.output_hash,
       run.runtime_kind,run.device,run.status,run.research_only,
       run.direct_signal,run.broker_order_allowed,run.validation,run.error,
       run.evidence,run.started_at,run.finished_at,run.created_at,run.updated_at,
       coalesce(path_stats.stored_paths,0)::INTEGER AS stored_paths,
       coalesce(path_stats.stored_points,0)::INTEGER AS stored_points,
       path_stats.ohlc_validity,path_stats.volume_validity,
       score.validation_status,score.feature_payload,score.scored_at
FROM strategy.kronos_forecast_runs run
LEFT JOIN LATERAL (
    SELECT count(DISTINCT path.path_index) AS stored_paths,
           count(*) AS stored_points,
           avg(path.ohlc_valid::INTEGER)::NUMERIC AS ohlc_validity,
           avg(path.volume_valid::INTEGER)::NUMERIC AS volume_validity
    FROM strategy.kronos_forecast_paths path
    WHERE path.forecast_run_id=run.id
) path_stats ON true
LEFT JOIN LATERAL (
    SELECT item.validation_status,item.feature_payload,item.scored_at
    FROM strategy.kronos_forecast_scores item
    WHERE item.forecast_run_id=run.id
      AND item.score_kind='ex_ante_distribution'
    ORDER BY item.scored_at DESC,item.id DESC
    LIMIT 1
) score ON true;

INSERT INTO agent.tool_registry (
    tool_name,tool_type,owning_agent,permission_level,enabled,description,config
)
VALUES (
    'kronos_inference_adapter','local_model_adapter','Feature Engineer',
    'write_scoped',false,
    'Pinned research-only Kronos mini adapter. Reads canonical OHLCV and writes stochastic paths, distribution features, hashes, and validation evidence. It cannot create signals or orders.',
    '{
      "runtime_status":"setup_required",
      "research_only":true,
      "live_execution_allowed":false,
      "broker_order_allowed":false,
      "minimum_paths":20,
      "source_code_repo":"https://github.com/shiyu-coder/Kronos",
      "source_code_revision":"67b630e67f6a18c9e9be918d9b4337c960db1e9a",
      "model_repo":"NeoQuasar/Kronos-mini",
      "model_revision":"f4e68697d9d5aed55cef5c96aabc3376bcad9f81",
      "model_sha256":"a7d5f37e2e9fbd9891f7d7d4f72574512dd1f704fee14223e0a8cd0fbf54197c",
      "tokenizer_repo":"NeoQuasar/Kronos-Tokenizer-2k",
      "tokenizer_revision":"26966d0035065a0cae0ebad7af8ece35bc1fb51c",
      "tokenizer_sha256":"b97ec46b3b72160509e289183eaf7bdf5f0dac5bb9b49522f6d46638a99a8717",
      "storage_root":"/Volumes/Devarsh SSD/AI OS Data/models/kronos-runtime"
    }'::jsonb
)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type=EXCLUDED.tool_type,
    owning_agent=EXCLUDED.owning_agent,
    permission_level=EXCLUDED.permission_level,
    enabled=agent.tool_registry.enabled,
    description=EXCLUDED.description,
    config=EXCLUDED.config || agent.tool_registry.config;

INSERT INTO core.control_plane_modules (
    module_key,module_name,category,status,priority,owner_agent,ui_workspace,
    description,warehouse_objects,mcp_tools,next_action,metadata
)
VALUES (
    'kronos_research_adapter','Kronos Research Adapter','quant_research',
    'setup_required','high','Feature Engineer','graph-studio',
    'Pinned, local stochastic OHLCV forecast paths with point-in-time lineage and model-risk review. Forecasts are research features, never direct trade signals.',
    ARRAY['trading.ohlcv','strategy.kronos_forecast_runs','strategy.kronos_forecast_paths','strategy.kronos_forecast_scores'],
    ARRAY['kronos_inference_adapter'],
    'Run scripts/setup_kronos_runtime.sh on the iMac, verify immutable revisions and weights, then activate the tool.',
    '{
      "research_only":true,
      "broker_writes":false,
      "human_model_decision":true,
      "synthetic_fallback_allowed":false,
      "storage":"external_ssd"
    }'::jsonb
)
ON CONFLICT (module_key) DO UPDATE SET
    module_name=EXCLUDED.module_name,category=EXCLUDED.category,
    status=CASE WHEN core.control_plane_modules.status='active' THEN 'active' ELSE EXCLUDED.status END,
    priority=EXCLUDED.priority,owner_agent=EXCLUDED.owner_agent,
    ui_workspace=EXCLUDED.ui_workspace,description=EXCLUDED.description,
    warehouse_objects=EXCLUDED.warehouse_objects,mcp_tools=EXCLUDED.mcp_tools,
    next_action=EXCLUDED.next_action,metadata=EXCLUDED.metadata,updated_at=now();

COMMIT;
