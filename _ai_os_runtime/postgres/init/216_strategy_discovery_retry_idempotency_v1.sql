-- Preserve the latest actionable strategy-discovery review while collapsing
-- historical scheduler retries that represent the same unchanged hypothesis.
WITH normalized AS (
    SELECT
        task.id,
        regexp_replace(
            task.title,
            E' \\[strategy_discovery[^]]+ #[0-9]+\\]$',
            ''
        ) AS stable_title,
        row_number() OVER (
            PARTITION BY regexp_replace(
                task.title,
                E' \\[strategy_discovery[^]]+ #[0-9]+\\]$',
                ''
            )
            ORDER BY task.id DESC
        ) AS freshness_rank
    FROM agent.tasks task
    WHERE task.title LIKE 'Structure and backtest strategy candidate:%'
      AND task.status IN ('queued', 'in_progress', 'blocked', 'needs_review')
), superseded AS (
    UPDATE agent.tasks task
    SET status = 'superseded',
        evidence = CASE
            WHEN jsonb_typeof(task.evidence) = 'array' THEN task.evidence
            ELSE '[]'::jsonb
        END || jsonb_build_array(jsonb_build_object(
            'reason', 'unchanged strategy-discovery retry superseded by newest review',
            'migration', '216_strategy_discovery_retry_idempotency_v1',
            'superseded_at', now()
        )),
        updated_at = now()
    FROM normalized
    WHERE task.id = normalized.id
      AND normalized.freshness_rank > 1
    RETURNING task.id
)
UPDATE agent.inbox_items inbox
SET status = 'superseded',
    evidence = CASE
        WHEN jsonb_typeof(inbox.evidence) = 'array' THEN inbox.evidence
        ELSE '[]'::jsonb
    END || jsonb_build_array(jsonb_build_object(
        'reason', 'linked strategy-discovery retry task was superseded',
        'migration', '216_strategy_discovery_retry_idempotency_v1',
        'superseded_at', now()
    )),
    updated_at = now()
WHERE inbox.task_id IN (SELECT id FROM superseded)
  AND inbox.status IN ('new', 'queued', 'in_progress', 'blocked', 'needs_review');

UPDATE agent.tool_registry
SET config = config || jsonb_build_object(
    'unchanged_failure_cooldown', true,
    'optimizer_cooldown_hours', 168,
    'retry_after_source_change', true,
    'audit_preserved', true
)
WHERE tool_name IN ('ai_os_run_strategy_discovery', 'ai_os_run_strategy_discovery_scheduler');
