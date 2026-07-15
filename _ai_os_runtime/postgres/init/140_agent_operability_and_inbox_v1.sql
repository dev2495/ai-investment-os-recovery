BEGIN;

ALTER TABLE agent.inbox_items
    ADD COLUMN IF NOT EXISTS claimed_by TEXT,
    ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS resolved_by TEXT,
    ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS resolution_note TEXT;

CREATE INDEX IF NOT EXISTS idx_inbox_owner_status
    ON agent.inbox_items (owner_agent, status, updated_at DESC);

CREATE OR REPLACE VIEW agent.v_agent_operating_readiness AS
WITH run_stats AS (
    SELECT agent_name,count(*)::int AS worker_runs,
           count(*) FILTER (WHERE status='completed')::int AS completed_runs,
           count(*) FILTER (WHERE status IN ('failed','blocked'))::int AS failed_runs,
           max(finished_at) AS latest_worker_finished_at
    FROM agent.worker_runs GROUP BY agent_name
), task_stats AS (
    SELECT owner_agent AS agent_name,
           count(*) FILTER (WHERE status IN ('queued','in_progress','needs_review','blocked'))::int AS open_tasks,
           count(*) FILTER (WHERE status='blocked')::int AS blocked_tasks
    FROM agent.tasks GROUP BY owner_agent
), route_state AS (
    SELECT assignment.agent_name,assignment.primary_route,assignment.fallback_route,
           primary_route.runtime_status AS primary_route_status,
           fallback_route.runtime_status AS fallback_route_status,
           (primary_route.runtime_status='ready' OR fallback_route.runtime_status='ready') AS model_route_ready
    FROM agent.agent_model_assignments assignment
    LEFT JOIN agent.v_model_route_runtime_control primary_route
      ON primary_route.route_name=assignment.primary_route
    LEFT JOIN agent.v_model_route_runtime_control fallback_route
      ON fallback_route.route_name=assignment.fallback_route
)
SELECT p.agent_name,p.display_title,p.department,
       (h.agent_name IS NOT NULL) AS hierarchy_ready,
       (m.agent_name IS NOT NULL) AS mailbox_ready,
       (c.agent_name IS NOT NULL) AS character_ready,
       coalesce(route.model_route_ready,false) AS model_route_ready,
       (coalesce(sk.skill_count,0)>0) AS skills_ready,
       coalesce(sk.skill_count,0)::int AS skill_count,
       coalesce(rs.worker_runs,0) AS worker_runs,coalesce(rs.completed_runs,0) AS completed_runs,
       coalesce(rs.failed_runs,0) AS failed_runs,coalesce(ts.open_tasks,0) AS open_tasks,
       coalesce(ts.blocked_tasks,0) AS blocked_tasks,rs.latest_worker_finished_at,
       round((
           10*(h.agent_name IS NOT NULL)::int +
           10*(m.agent_name IS NOT NULL)::int +
           10*(c.agent_name IS NOT NULL)::int +
           10*(a.agent_name IS NOT NULL)::int +
           10*(coalesce(sk.skill_count,0)>0)::int +
           25*coalesce(route.model_route_ready,false)::int +
           25*(coalesce(rs.completed_runs,0)>0)::int
       )::numeric,2) AS operating_readiness_score,
       CASE WHEN coalesce(rs.worker_runs,0)=0 THEN NULL ELSE round(100.0*rs.completed_runs/greatest(rs.worker_runs,1),2) END AS reliability_score,
       CASE WHEN coalesce(rs.worker_runs,0)>=10 THEN 'measured' WHEN coalesce(rs.worker_runs,0)>=3 THEN 'limited' ELSE 'insufficient_history' END AS reliability_confidence,
       CASE
           WHEN h.agent_name IS NULL OR m.agent_name IS NULL OR c.agent_name IS NULL OR a.agent_name IS NULL OR coalesce(sk.skill_count,0)=0 THEN 'incomplete_structure'
           WHEN NOT coalesce(route.model_route_ready,false) THEN 'model_pending'
           WHEN coalesce(rs.completed_runs,0)=0 THEN 'untested'
           ELSE 'operational'
       END AS readiness_status,
       route.primary_route AS primary_model_route,
       route.fallback_route AS fallback_model_route,
       route.primary_route_status,
       route.fallback_route_status,
       (a.agent_name IS NOT NULL) AS model_assignment_ready,
       (coalesce(rs.completed_runs,0)>0) AS runtime_tested
FROM agent.profiles p
LEFT JOIN agent.org_hierarchy h ON h.agent_name=p.agent_name
LEFT JOIN agent.mailboxes m ON m.agent_name=p.agent_name AND m.status='active'
LEFT JOIN agent.agent_characters c ON c.agent_name=p.agent_name
LEFT JOIN agent.agent_model_assignments a ON a.agent_name=p.agent_name
LEFT JOIN route_state route ON route.agent_name=p.agent_name
LEFT JOIN (SELECT agent_name,count(*)::int AS skill_count FROM agent.agent_skill_map GROUP BY agent_name) sk ON sk.agent_name=p.agent_name
LEFT JOIN run_stats rs ON rs.agent_name=p.agent_name
LEFT JOIN task_stats ts ON ts.agent_name=p.agent_name
WHERE p.status='active';

CREATE OR REPLACE VIEW agent.v_agent_operating_summary AS
SELECT metric,value,interpretation FROM (
    SELECT 1 AS rank,'active_agents'::text metric,count(*)::bigint value,'Active governed AI employees.'::text interpretation FROM agent.v_agent_operating_readiness
    UNION ALL SELECT 2,'operational_agents',count(*) FILTER (WHERE readiness_status='operational'),'Agents with complete structure, a usable deterministic/model route, and at least one successful worker run.' FROM agent.v_agent_operating_readiness
    UNION ALL SELECT 3,'untested_agents',count(*) FILTER (WHERE readiness_status='untested'),'Structurally ready agents that still require a successful bounded worker run.' FROM agent.v_agent_operating_readiness
    UNION ALL SELECT 4,'model_pending_agents',count(*) FILTER (WHERE readiness_status='model_pending'),'Agents whose primary and fallback routes are not currently usable.' FROM agent.v_agent_operating_readiness
    UNION ALL SELECT 5,'active_departments',count(*) FILTER (WHERE status='active'),'Active role-scoped departments.' FROM agent.department_registry
    UNION ALL SELECT 6,'active_schedules',count(*) FILTER (WHERE enabled),'Materializing schedules; open-task dedupe prevents spam.' FROM agent.workflow_schedules
    UNION ALL SELECT 7,'structured_committees',count(*) FILTER (WHERE status='active'),'Committees with chair, quorum, members, challenge mandate, and human final gate.' FROM agent.committee_registry
    UNION ALL SELECT 8,'active_mailboxes',count(*) FILTER (WHERE status='active'),'Durable internal mailboxes.' FROM agent.mailboxes
) summary ORDER BY rank;

CREATE OR REPLACE VIEW agent.v_live_agent_worker_queue AS
WITH dashboard_jobs AS (
    SELECT j.task_id,j.title,j.objective,j.owner_agent,j.status AS task_status,j.priority,j.source_kind,j.source_ref,j.output_note_path,
           j.widget_id,j.widget_key,j.widget_title,j.workspace,j.widget_type,
           CASE WHEN j.widget_key='portfolio_latest_positions' THEN 'portfolio_snapshot_review' WHEN j.widget_key='market_signal_monitor' THEN 'monitor_strategy_alerts' WHEN j.widget_key='strategy_lab_queue' THEN 'strategy_lab_review' WHEN j.widget_key='research_filings_inbox' THEN 'analyze_corporate_filing' WHEN j.widget_key='model_runtime_status' THEN 'model_runtime_check' WHEN j.widget_key='command_daily_brief' THEN 'daily_office_brief' ELSE 'refresh_dashboard_widget' END AS suggested_skill_key,
           j.inbox_item_id,j.inbox_status,j.created_at,j.updated_at
    FROM agent.v_dashboard_agent_jobs j
), message_jobs AS (
    SELECT t.id,t.title,t.objective,t.owner_agent,t.status,t.priority,t.source_kind,t.source_ref,t.output_note_path,
           NULL::bigint,NULL::text,'Agent Mailbox'::text,coalesce(nullif(p.department,''),'command'),'agent_message'::text,
           coalesce(msg.related_skill_key,msg.metadata->>'skill_key','route_user_request'),inbox.id,inbox.status,t.created_at,t.updated_at
    FROM agent.tasks t
    LEFT JOIN agent.agent_messages msg ON msg.generated_task_id=t.id
    LEFT JOIN LATERAL (
        SELECT item.id,item.status FROM agent.inbox_items item WHERE item.task_id=t.id
        ORDER BY item.updated_at DESC,item.id DESC LIMIT 1
    ) inbox ON true
    LEFT JOIN agent.profiles p ON p.agent_name=t.owner_agent
    WHERE t.source_kind='agent_message'
), schedule_jobs AS (
    SELECT t.id,t.title,t.objective,t.owner_agent,t.status,t.priority,t.source_kind,t.source_ref,t.output_note_path,
           NULL::bigint,NULL::text,'Scheduled Workflow'::text,coalesce(nullif(p.department,''),'command'),'workflow_schedule'::text,
           s.skill_key,inbox.id,inbox.status,t.created_at,t.updated_at
    FROM agent.tasks t
    JOIN agent.workflow_schedules s ON s.schedule_key=t.source_ref
    LEFT JOIN LATERAL (
        SELECT item.id,item.status FROM agent.inbox_items item WHERE item.task_id=t.id
        ORDER BY item.updated_at DESC,item.id DESC LIMIT 1
    ) inbox ON true
    LEFT JOIN agent.profiles p ON p.agent_name=t.owner_agent
    WHERE t.source_kind='workflow_schedule'
), governed_jobs AS (
    SELECT t.id,t.title,t.objective,t.owner_agent,t.status,t.priority,t.source_kind,t.source_ref,t.output_note_path,
           NULL::bigint,NULL::text,
           CASE WHEN t.source_kind='committee_packet_position' THEN 'Committee Position' ELSE 'Governed Task' END::text,
           coalesce(nullif(p.department,''),'command'),
           CASE WHEN t.source_kind='committee_packet_position' THEN 'committee_position' ELSE 'governed_task' END::text,
           CASE
               WHEN t.source_kind='committee_packet_position' THEN 'strategy_committee_memo'
               WHEN t.source_kind='position_object_gap' THEN 'portfolio_snapshot_review'
               WHEN t.source_kind LIKE 'strategy.%' THEN 'strategy_lab_review'
               WHEN t.source_kind LIKE 'portfolio.%' OR t.source_kind LIKE 'holding_thesis%' THEN 'portfolio_snapshot_review'
               WHEN t.source_kind LIKE 'research.%' THEN 'analyze_corporate_filing'
               WHEN t.source_kind LIKE 'client_%' OR t.source_kind LIKE 'client.%' THEN 'client_management'
               WHEN t.source_kind LIKE 'books.%' THEN 'broker_import_reconciliation'
               WHEN t.source_kind LIKE 'core.%' OR t.source_kind LIKE 'ops.%' THEN 'source_data_ingestion_review'
               WHEN t.source_kind='smoke' THEN 'qa_release_gate'
               ELSE coalesce(primary_skill.skill_key,'route_user_request')
           END,
           inbox.id,inbox.status,t.created_at,t.updated_at
    FROM agent.tasks t
    LEFT JOIN agent.profiles p ON p.agent_name=t.owner_agent
    LEFT JOIN LATERAL (
        SELECT mapping.skill_key FROM agent.agent_skill_map mapping
        JOIN agent.skills skill ON skill.skill_key=mapping.skill_key AND skill.status='active'
        WHERE mapping.agent_name=t.owner_agent
        ORDER BY mapping.is_primary DESC,mapping.skill_key LIMIT 1
    ) primary_skill ON true
    LEFT JOIN LATERAL (
        SELECT item.id,item.status FROM agent.inbox_items item WHERE item.task_id=t.id
        ORDER BY item.updated_at DESC,item.id DESC LIMIT 1
    ) inbox ON true
    WHERE t.source_kind NOT IN ('agent_message','workflow_schedule')
      AND NOT EXISTS (SELECT 1 FROM dashboard_jobs dashboard WHERE dashboard.task_id=t.id)
), queued AS (
    SELECT * FROM dashboard_jobs
    UNION ALL SELECT * FROM message_jobs
    UNION ALL SELECT * FROM schedule_jobs
    UNION ALL SELECT * FROM governed_jobs
)
SELECT q.task_id,q.title,q.objective,q.owner_agent,q.task_status,q.priority,q.source_kind,q.source_ref,q.output_note_path,
       q.widget_id,q.widget_key,q.widget_title,q.workspace,q.widget_type,q.suggested_skill_key,
       s.skill_name AS suggested_skill_name,s.skill_family AS suggested_skill_family,s.execution_mode AS suggested_execution_mode,
       last_run.id AS latest_worker_run_id,last_run.status AS latest_worker_status,last_run.finished_at AS latest_worker_finished_at,last_run.output_note_path AS latest_output_note_path,
       q.inbox_item_id,q.inbox_status,q.created_at,q.updated_at
FROM queued q LEFT JOIN agent.skills s ON s.skill_key=q.suggested_skill_key
LEFT JOIN LATERAL (SELECT wr.* FROM agent.worker_runs wr WHERE wr.task_id=q.task_id ORDER BY wr.created_at DESC LIMIT 1) last_run ON true
ORDER BY CASE q.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
         CASE q.task_status WHEN 'queued' THEN 1 WHEN 'in_progress' THEN 2 WHEN 'needs_review' THEN 3 WHEN 'completed' THEN 4 ELSE 5 END,q.updated_at DESC;

INSERT INTO agent.tool_registry (
    tool_name,tool_type,owning_agent,permission_level,enabled,description,config
)
VALUES (
    'ai_os_update_inbox_status','mcp_tool','Jarvis','write_scoped',true,
    'Claim, reassign, resolve, block, or reopen a governed inbox item while keeping its linked task synchronized.',
    '{"writes":["agent.inbox_items","agent.tasks"],"actions":["claim","reassign","resolve","block","reopen"],"human_final_capital_action_allowed":false,"live_execution_allowed":false}'::jsonb
)
ON CONFLICT (tool_name) DO UPDATE SET
    owning_agent=EXCLUDED.owning_agent,permission_level=EXCLUDED.permission_level,
    enabled=EXCLUDED.enabled,description=EXCLUDED.description,config=EXCLUDED.config;

COMMIT;
