BEGIN;

UPDATE agent.agent_messages
SET related_skill_key = CASE
        WHEN to_agent = 'Strategy Research Agent' THEN 'generate_strategy_hypothesis'
        WHEN to_agent = 'Research Analyst' THEN 'company_research_note'
        ELSE related_skill_key
    END,
    metadata = metadata || jsonb_build_object(
        'specialist_skill_routed_at', now(),
        'specialist_skill_routing', 'research_source_v1'
    )
WHERE metadata->>'source' = 'research_source_intake'
  AND to_agent IN ('Strategy Research Agent', 'Research Analyst')
  AND related_skill_key IS DISTINCT FROM CASE
        WHEN to_agent = 'Strategy Research Agent' THEN 'generate_strategy_hypothesis'
        WHEN to_agent = 'Research Analyst' THEN 'company_research_note'
        ELSE related_skill_key
      END;

WITH shallow_tasks AS (
    SELECT task.id
    FROM agent.tasks task
    JOIN agent.agent_messages message ON message.generated_task_id = task.id
    WHERE message.metadata->>'source' = 'research_source_intake'
      AND task.status = 'needs_review'
      AND EXISTS (
          SELECT 1
          FROM agent.worker_runs run
          WHERE run.task_id = task.id
            AND run.skill_key = 'route_user_request'
      )
), requeued AS (
    UPDATE agent.tasks task
    SET status = 'queued',
        output_note_path = NULL,
        evidence = coalesce(task.evidence, '[]'::jsonb) || jsonb_build_array(
            jsonb_build_object(
                'source', '166_research_source_specialist_routing_v1',
                'reason', 'replace generic mailbox receipt with source-aware specialist output',
                'requeued_at', now()
            )
        ),
        updated_at = now()
    FROM shallow_tasks
    WHERE task.id = shallow_tasks.id
    RETURNING task.id
)
UPDATE agent.inbox_items inbox
SET status = 'queued',
    recommended_action = 'Run the assigned research specialist skill and review the source-aware evidence or test plan.',
    updated_at = now()
WHERE inbox.task_id IN (SELECT id FROM requeued);

COMMIT;
