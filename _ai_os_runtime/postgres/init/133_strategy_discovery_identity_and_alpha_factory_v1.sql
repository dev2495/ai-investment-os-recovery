BEGIN;

ALTER TABLE strategy.strategy_discovery_candidates
    ADD COLUMN IF NOT EXISTS opportunity_fingerprint TEXT,
    ADD COLUMN IF NOT EXISTS source_fingerprint TEXT,
    ADD COLUMN IF NOT EXISTS is_canonical BOOLEAN NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS canonical_candidate_id BIGINT,
    ADD COLUMN IF NOT EXISTS first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS seen_count INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS suppressed_reason TEXT,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

DROP INDEX IF EXISTS strategy.uq_strategy_discovery_canonical_opportunity;

UPDATE strategy.strategy_discovery_candidates candidate
SET opportunity_fingerprint = 'opp_v2:' || md5(concat_ws('|',
        regexp_replace(
            lower(trim(regexp_replace(candidate.title,
                '^(research-sourced strategy:|journal pattern strategy:|signal-sourced strategy:|component pattern:)[[:space:]]*',
                '', 'i'))),
            '\\s+', ' ', 'g'
        ),
        array_to_string(ARRAY(
            SELECT upper(trim(symbol_value))
            FROM unnest(candidate.symbols) AS symbol_value
            WHERE trim(symbol_value) <> ''
            ORDER BY upper(trim(symbol_value))
        ), ','),
        lower(coalesce(candidate.universe, '')),
        lower(coalesce(candidate.timeframe, '')),
        lower(coalesce(candidate.template, ''))
    )),
    source_fingerprint = 'src_v2:' || md5(concat_ws('|',
        regexp_replace(
            lower(trim(regexp_replace(candidate.title,
                '^(research-sourced strategy:|journal pattern strategy:|signal-sourced strategy:|component pattern:)[[:space:]]*',
                '', 'i'))),
            '\\s+', ' ', 'g'
        ),
        array_to_string(ARRAY(
            SELECT upper(trim(symbol_value))
            FROM unnest(candidate.symbols) AS symbol_value
            WHERE trim(symbol_value) <> ''
            ORDER BY upper(trim(symbol_value))
        ), ','),
        lower(coalesce(candidate.universe, '')),
        lower(coalesce(candidate.timeframe, '')),
        lower(coalesce(candidate.template, '')),
        regexp_replace(lower(trim(coalesce(candidate.thesis, ''))), '\\s+', ' ', 'g'),
        regexp_replace(lower(trim(coalesce(candidate.catalyst, ''))), '\\s+', ' ', 'g')
    )),
    first_seen_at = least(candidate.first_seen_at, candidate.created_at),
    last_seen_at = greatest(candidate.last_seen_at, candidate.created_at),
    updated_at = now();

WITH ranked AS (
    SELECT
        candidate.id,
        first_value(candidate.id) OVER (
            PARTITION BY candidate.opportunity_fingerprint
            ORDER BY
                EXISTS (
                    SELECT 1
                    FROM strategy.strategy_discovery_triage_decisions decision
                    WHERE decision.discovery_candidate_id = candidate.id
                ) DESC,
                (candidate.optimizer_status IN ('completed', 'reused')) DESC,
                (candidate.optimizer_run_id IS NOT NULL) DESC,
                candidate.created_at DESC,
                candidate.id DESC
        ) AS canonical_id,
        row_number() OVER (
            PARTITION BY candidate.opportunity_fingerprint
            ORDER BY
                EXISTS (
                    SELECT 1
                    FROM strategy.strategy_discovery_triage_decisions decision
                    WHERE decision.discovery_candidate_id = candidate.id
                ) DESC,
                (candidate.optimizer_status IN ('completed', 'reused')) DESC,
                (candidate.optimizer_run_id IS NOT NULL) DESC,
                candidate.created_at DESC,
                candidate.id DESC
        ) AS identity_rank,
        count(*) OVER (PARTITION BY candidate.opportunity_fingerprint) AS identity_count,
        min(candidate.created_at) OVER (PARTITION BY candidate.opportunity_fingerprint) AS first_seen,
        max(candidate.created_at) OVER (PARTITION BY candidate.opportunity_fingerprint) AS last_seen
    FROM strategy.strategy_discovery_candidates candidate
)
UPDATE strategy.strategy_discovery_candidates candidate
SET is_canonical = ranked.identity_rank = 1,
    canonical_candidate_id = ranked.canonical_id,
    seen_count = greatest(candidate.seen_count, ranked.identity_count),
    first_seen_at = least(candidate.first_seen_at, ranked.first_seen),
    last_seen_at = greatest(candidate.last_seen_at, ranked.last_seen),
    suppressed_reason = CASE
        WHEN ranked.identity_rank = 1 THEN NULL
        ELSE 'same opportunity identity as canonical discovery candidate ' || ranked.canonical_id
    END,
    status = CASE
        WHEN ranked.identity_rank = 1 AND candidate.status = 'superseded_duplicate' AND candidate.optimizer_status = 'reused'
            THEN 'optimizer_reused'
        WHEN ranked.identity_rank = 1 AND candidate.status = 'superseded_duplicate' AND candidate.optimizer_status = 'completed'
            THEN 'optimizer_routed'
        WHEN ranked.identity_rank = 1 AND candidate.status = 'superseded_duplicate' AND candidate.route_to_optimizer
            THEN 'idea_created'
        WHEN ranked.identity_rank = 1 AND candidate.status = 'superseded_duplicate'
            THEN 'reference_only'
        WHEN ranked.identity_rank = 1 THEN candidate.status
        ELSE 'superseded_duplicate'
    END,
    updated_at = now()
FROM ranked
WHERE ranked.id = candidate.id;

WITH best_optimizer AS (
    SELECT DISTINCT ON (candidate.opportunity_fingerprint)
        candidate.opportunity_fingerprint,
        candidate.optimizer_run_id,
        candidate.optimizer_run_key,
        candidate.optimizer_status,
        candidate.research_gate,
        candidate.next_required_action
    FROM strategy.strategy_discovery_candidates candidate
    WHERE candidate.optimizer_run_id IS NOT NULL
      AND candidate.optimizer_status IN ('completed', 'reused')
    ORDER BY
        candidate.opportunity_fingerprint,
        CASE candidate.optimizer_status WHEN 'completed' THEN 1 ELSE 2 END,
        candidate.last_seen_at DESC,
        candidate.id DESC
)
UPDATE strategy.strategy_discovery_candidates canonical
SET optimizer_run_id = best_optimizer.optimizer_run_id,
    optimizer_run_key = best_optimizer.optimizer_run_key,
    optimizer_status = best_optimizer.optimizer_status,
    research_gate = best_optimizer.research_gate,
    next_required_action = best_optimizer.next_required_action,
    updated_at = now()
FROM best_optimizer
WHERE canonical.is_canonical
  AND canonical.opportunity_fingerprint = best_optimizer.opportunity_fingerprint;

CREATE TABLE IF NOT EXISTS strategy.strategy_discovery_observations (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES strategy.strategy_discovery_runs(id) ON DELETE CASCADE,
    discovery_candidate_id BIGINT REFERENCES strategy.strategy_discovery_candidates(id) ON DELETE SET NULL,
    opportunity_fingerprint TEXT NOT NULL,
    source_fingerprint TEXT NOT NULL,
    source_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, opportunity_fingerprint, source_fingerprint)
);

CREATE INDEX IF NOT EXISTS idx_strategy_discovery_observation_opportunity
ON strategy.strategy_discovery_observations (opportunity_fingerprint, observed_at DESC);

INSERT INTO strategy.strategy_discovery_observations (
    run_id, discovery_candidate_id, opportunity_fingerprint,
    source_fingerprint, source_refs, evidence, observed_at
)
SELECT
    candidate.run_id,
    candidate.canonical_candidate_id,
    candidate.opportunity_fingerprint,
    candidate.source_fingerprint,
    jsonb_build_array(jsonb_build_object(
        'source_kind', candidate.source_kind,
        'source_ref', candidate.source_ref
    )),
    candidate.evidence,
    candidate.created_at
FROM strategy.strategy_discovery_candidates candidate
ON CONFLICT (run_id, opportunity_fingerprint, source_fingerprint) DO NOTHING;

UPDATE strategy.strategy_discovery_candidates candidate
SET seen_count = observation.observation_count,
    first_seen_at = observation.first_seen_at,
    last_seen_at = observation.last_seen_at,
    updated_at = now()
FROM (
    SELECT opportunity_fingerprint,
           count(*)::integer AS observation_count,
           min(observed_at) AS first_seen_at,
           max(observed_at) AS last_seen_at
    FROM strategy.strategy_discovery_observations
    GROUP BY opportunity_fingerprint
) observation
WHERE candidate.opportunity_fingerprint = observation.opportunity_fingerprint;

ALTER TABLE strategy.strategy_discovery_candidates
    ALTER COLUMN opportunity_fingerprint SET NOT NULL,
    ALTER COLUMN source_fingerprint SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_strategy_discovery_canonical_opportunity
ON strategy.strategy_discovery_candidates (opportunity_fingerprint)
WHERE is_canonical;

CREATE INDEX IF NOT EXISTS idx_strategy_discovery_opportunity
ON strategy.strategy_discovery_candidates (opportunity_fingerprint, last_seen_at DESC);

CREATE INDEX IF NOT EXISTS idx_strategy_discovery_canonical_state
ON strategy.strategy_discovery_candidates (is_canonical, status, priority_score DESC);

UPDATE strategy.generated_ideas idea
SET idea_key = 'discovery_opportunity_' || replace(candidate.opportunity_fingerprint, ':', '_'),
    updated_at = now()
FROM strategy.strategy_discovery_candidates candidate
WHERE candidate.is_canonical
  AND candidate.generated_idea_id = idea.id
  AND NOT EXISTS (
      SELECT 1
      FROM strategy.generated_ideas conflict
      WHERE conflict.idea_key = 'discovery_opportunity_' || replace(candidate.opportunity_fingerprint, ':', '_')
        AND conflict.id <> idea.id
  );

CREATE OR REPLACE VIEW strategy.v_strategy_discovery_canonical_queue AS
SELECT
    triage.*,
    candidate.opportunity_fingerprint,
    candidate.source_fingerprint,
    candidate.first_seen_at,
    candidate.last_seen_at,
    candidate.seen_count,
    candidate.is_canonical,
    candidate.canonical_candidate_id,
    candidate.suppressed_reason,
    greatest(0, (
        SELECT count(*) - 1
        FROM strategy.strategy_discovery_candidates duplicate
        WHERE duplicate.opportunity_fingerprint = candidate.opportunity_fingerprint
    ))::bigint AS suppressed_duplicate_count
FROM strategy.v_strategy_discovery_triage_queue triage
JOIN strategy.strategy_discovery_candidates candidate ON candidate.id = triage.id
WHERE candidate.is_canonical;

CREATE OR REPLACE VIEW strategy.v_strategy_discovery_governance_summary AS
SELECT 'canonical_opportunities'::text AS metric, count(*)::bigint AS value,
       'Unique source-backed opportunities visible to the operator.'::text AS interpretation
FROM strategy.strategy_discovery_candidates
WHERE is_canonical
UNION ALL
SELECT 'suppressed_duplicates', count(*),
       'Historical discovery rows retained as evidence but removed from the operating queue.'
FROM strategy.strategy_discovery_candidates
WHERE NOT is_canonical
UNION ALL
SELECT 'pending_triage', count(*),
       'Canonical opportunities awaiting a recorded triage decision.'
FROM strategy.v_strategy_discovery_canonical_queue
WHERE triage_status = 'pending'
UNION ALL
SELECT 'optimizer_ready', count(*),
       'Canonical opportunities with completed or reused optimizer evidence.'
FROM strategy.strategy_discovery_candidates
WHERE is_canonical AND optimizer_status IN ('completed', 'reused')
UNION ALL
SELECT 'cooldown_reuses', count(*),
       'Canonical opportunities currently reusing unchanged recent optimizer evidence.'
FROM strategy.strategy_discovery_candidates
WHERE is_canonical AND optimizer_status = 'reused';

CREATE OR REPLACE VIEW strategy.v_strategy_arsenal_canonical_control_board AS
WITH enriched AS (
    SELECT
        board.*,
        coalesce(discovery.opportunity_fingerprint, 'candidate:' || board.candidate_id::text) AS opportunity_fingerprint,
        discovery.source_fingerprint,
        coalesce(discovery.seen_count, 1) AS discovery_seen_count,
        coalesce(discovery.last_seen_at, board.updated_at) AS discovery_last_seen_at,
        count(*) OVER (
            PARTITION BY coalesce(discovery.opportunity_fingerprint, 'candidate:' || board.candidate_id::text)
        ) AS duplicate_candidate_count,
        row_number() OVER (
            PARTITION BY coalesce(discovery.opportunity_fingerprint, 'candidate:' || board.candidate_id::text)
            ORDER BY
                board.gates_passed DESC,
                board.updated_at DESC NULLS LAST,
                board.candidate_id DESC
        ) AS canonical_rank
    FROM strategy.v_strategy_arsenal_control_board board
    LEFT JOIN strategy.strategy_discovery_candidates discovery
      ON discovery.id = board.discovery_candidate_id
)
SELECT *
FROM enriched
WHERE canonical_rank = 1;

CREATE OR REPLACE VIEW strategy.v_strategy_arsenal_canonical_summary AS
WITH board AS MATERIALIZED (
    SELECT * FROM strategy.v_strategy_arsenal_canonical_control_board
), totals AS (
    SELECT
        count(*)::bigint AS total_candidates,
        count(*) FILTER (WHERE origin_type = 'operator_submitted')::bigint AS operator_submitted,
        count(*) FILTER (WHERE origin_type = 'system_discovery')::bigint AS system_discovered,
        count(*) FILTER (WHERE parse_status = 'passed')::bigint AS dsl_passed,
        count(*) FILTER (WHERE data_quality_status = 'passed')::bigint AS data_quality_passed,
        count(*) FILTER (WHERE latest_backtest_run_id IS NOT NULL)::bigint AS backtested,
        count(*) FILTER (WHERE latest_optimization_run_id IS NOT NULL)::bigint AS optimized,
        count(*) FILTER (WHERE validation_gate_status = 'validation_passed')::bigint AS validation_passed,
        count(*) FILTER (WHERE promotion_stage = 'committee_review_required')::bigint AS committee_pending,
        count(*) FILTER (WHERE paper_monitor_session_id IS NOT NULL)::bigint AS paper_monitoring,
        count(*) FILTER (WHERE broker_order_allowed IS true)::bigint AS broker_orders_allowed
    FROM board
)
SELECT metric, value, interpretation
FROM totals
CROSS JOIN LATERAL (
    VALUES
        ('total_candidates'::text, totals.total_candidates, 'Canonical strategy candidates with a complete gate record.'::text),
        ('operator_submitted', totals.operator_submitted, 'Candidates submitted by Devarsh or Charlie.'),
        ('system_discovered', totals.system_discovered, 'Unique candidates generated from the source-backed discovery loop.'),
        ('dsl_passed', totals.dsl_passed, 'Candidates with a parsed machine-testable rule specification.'),
        ('data_quality_passed', totals.data_quality_passed, 'Candidates with sufficient point-in-time data for the configured gate.'),
        ('backtested', totals.backtested, 'Candidates with at least one baseline backtest.'),
        ('optimized', totals.optimized, 'Candidates with at least one optimization run.'),
        ('validation_passed', totals.validation_passed, 'Candidates that passed the model-validation gate.'),
        ('committee_pending', totals.committee_pending, 'Validated candidates requiring Strategy Committee review.'),
        ('paper_monitoring', totals.paper_monitoring, 'Candidates with a paper-monitor session.'),
        ('broker_orders_allowed', totals.broker_orders_allowed, 'Must remain zero until a separately approved production execution phase.')
) summary(metric, value, interpretation);

INSERT INTO agent.tool_registry (
    tool_name, tool_type, owning_agent, permission_level, enabled,
    description, config
)
VALUES (
    'ai_os_strategy_discovery_governance', 'mcp_tool',
    'Strategy Discovery Agent', 'read_only', true,
    'Read canonical strategy opportunities, duplicate suppression, cooldown reuse, provenance, and triage state.',
    '{"reads":["strategy.v_strategy_discovery_canonical_queue","strategy.v_strategy_discovery_governance_summary","strategy.v_strategy_arsenal_canonical_control_board"],"seed_data_allowed":false,"broker_order_allowed":false}'::jsonb
)
ON CONFLICT (tool_name) DO UPDATE SET
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

COMMIT;
