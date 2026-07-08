WITH ranked AS (
    SELECT
        id,
        row_number() OVER (
            PARTITION BY title, owner_agent, source_kind, source_ref
            ORDER BY id
        ) AS duplicate_rank
    FROM agent.tasks
    WHERE status IN ('queued', 'in_progress', 'blocked')
      AND source_kind IS NOT NULL
      AND source_ref IS NOT NULL
)
DELETE FROM agent.tasks
USING ranked
WHERE agent.tasks.id = ranked.id
  AND ranked.duplicate_rank > 1;

CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_tasks_open_source_work
ON agent.tasks (title, owner_agent, source_kind, source_ref)
WHERE status IN ('queued', 'in_progress', 'blocked')
  AND source_kind IS NOT NULL
  AND source_ref IS NOT NULL;
