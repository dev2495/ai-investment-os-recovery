BEGIN;

ALTER TABLE agent.graph_edges
    DROP CONSTRAINT IF EXISTS graph_edges_condition_type_check;
ALTER TABLE agent.graph_edges
    ADD CONSTRAINT graph_edges_condition_type_check
    CHECK (condition_type IN (
        'always','state_equals','state_present','approved','rejected',
        'node_output_equals','node_output_not_equals'
    ));

ALTER TABLE agent.graph_node_runs
    ADD COLUMN IF NOT EXISTS committee_packet_id BIGINT
        REFERENCES agent.committee_packets(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_graph_node_runs_committee
    ON agent.graph_node_runs(committee_packet_id)
    WHERE committee_packet_id IS NOT NULL;

CREATE OR REPLACE FUNCTION agent.open_graph_committee_packet(
    p_graph_run_id BIGINT,
    p_graph_node_run_id BIGINT,
    p_committee_key TEXT,
    p_opened_by TEXT
) RETURNS JSONB LANGUAGE plpgsql AS $$
DECLARE
    v_graph RECORD;
    v_registry agent.committee_registry%ROWTYPE;
    v_packet_id BIGINT;
    v_packet_key TEXT;
    v_item_key TEXT;
    v_question TEXT;
BEGIN
    SELECT run.graph_key,run.subject_type,run.subject_ref,run.input_payload,
           run.working_state,node_run.id AS graph_node_run_id,node.node_key,
           node.node_name,node.configuration
      INTO v_graph
    FROM agent.graph_runs run
    JOIN agent.graph_node_runs node_run ON node_run.graph_run_id=run.id
    JOIN agent.graph_nodes node ON node.id=node_run.graph_node_id
    WHERE run.id=p_graph_run_id
      AND node_run.id=p_graph_node_run_id
      AND node.node_type='committee'
    FOR UPDATE OF node_run;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'graph committee node not found: run %, node %',
            p_graph_run_id,p_graph_node_run_id;
    END IF;

    SELECT * INTO v_registry
    FROM agent.committee_registry
    WHERE committee_key=p_committee_key AND status='active';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'active committee not found: %',p_committee_key;
    END IF;

    v_item_key := 'graph:' || p_graph_run_id::TEXT || ':' || v_graph.node_key;
    v_question := coalesce(
        nullif(v_graph.configuration->>'decision_question',''),
        'Which governed outcome should follow from this evidence packet?'
    );

    SELECT id INTO v_packet_id
    FROM agent.committee_packets
    WHERE committee_key=p_committee_key
      AND committee_item_key=v_item_key
      AND packet_status IN ('collecting_positions','deliberating','awaiting_human')
    ORDER BY id DESC
    LIMIT 1;

    IF v_packet_id IS NULL THEN
        v_packet_key := 'graph-committee-' || p_graph_run_id::TEXT || '-'
            || regexp_replace(v_graph.node_key,'[^a-zA-Z0-9_-]+','-','g')
            || '-' || to_char(clock_timestamp(),'YYYYMMDDHH24MISSMS');
        INSERT INTO agent.committee_packets (
            packet_key,committee_key,committee_item_key,source_view,source_id,
            title,decision_question,evidence,opened_by,metadata
        ) VALUES (
            v_packet_key,p_committee_key,v_item_key,'agent.v_graph_run_status',
            p_graph_run_id,v_graph.node_name,v_question,
            jsonb_build_array(jsonb_build_object(
                'source_table','agent.graph_runs',
                'graph_run_id',p_graph_run_id,
                'graph_node_run_id',p_graph_node_run_id,
                'graph_key',v_graph.graph_key,
                'input_payload',v_graph.input_payload,
                'working_state',v_graph.working_state,
                'broker_writes_allowed',false
            )),
            p_opened_by,
            jsonb_strip_nulls(jsonb_build_object(
                'graph_run_id',p_graph_run_id,
                'graph_node_run_id',p_graph_node_run_id,
                'node_key',v_graph.node_key,
                'subject_type',v_graph.subject_type,
                'subject_ref',v_graph.subject_ref
            ))
        ) RETURNING id INTO v_packet_id;

        INSERT INTO agent.committee_sessions (
            packet_id,chair_agent,quorum_required
        ) VALUES (
            v_packet_id,v_registry.chair_agent,v_registry.quorum
        );

        WITH tasks AS (
            INSERT INTO agent.tasks (
                title,objective,owner_agent,status,priority,approval_required,
                source_kind,source_ref,output_format,evidence
            )
            SELECT
                'Independent graph committee position: ' || v_graph.node_name,
                'Submit a sealed, independent, evidence-backed position before reading peers. '
                    || 'Address this challenge mandate: ' || membership.challenge_mandate,
                membership.agent_name,'queued',
                CASE WHEN membership.vote_type='veto_recommendation' THEN 'high' ELSE 'normal' END,
                false,'committee_packet_position',
                v_packet_id::TEXT || ':' || membership.agent_name,
                'committee_position',
                jsonb_build_array(jsonb_build_object(
                    'table','agent.committee_packets','id',v_packet_id,
                    'graph_run_id',p_graph_run_id,
                    'graph_node_run_id',p_graph_node_run_id
                ))
            FROM agent.committee_memberships membership
            WHERE membership.committee_key=p_committee_key AND membership.required
            RETURNING id,title,owner_agent,priority,evidence
        )
        INSERT INTO agent.inbox_items (
            task_id,title,owner_agent,status,priority,recommended_action,
            evidence,target_workspace
        )
        SELECT id,title,owner_agent,'queued',priority,
               'Submit a sealed independent position with primary evidence, confidence, conditions, and the strongest disconfirming case.',
               evidence,'committees'
        FROM tasks;

        INSERT INTO agent.agent_messages (
            thread_key,from_agent,to_agent,subject,body,priority,status,
            related_task_id,related_skill_key,metadata
        )
        SELECT
            'committee:' || v_packet_id,v_registry.chair_agent,
            membership.agent_name,
            'Independent position requested: ' || v_graph.node_name,
            'Do not anchor on peer opinions. Use the graph evidence as-of state, cite sources, preserve dissent, and do not propose an order.',
            CASE WHEN membership.vote_type='veto_recommendation' THEN 'high' ELSE 'medium' END,
            'unread',task.id,'tradingagents_checkpointed_committee',
            jsonb_build_object(
                'packet_id',v_packet_id,
                'committee_key',p_committee_key,
                'graph_run_id',p_graph_run_id,
                'graph_node_run_id',p_graph_node_run_id,
                'sealed_until_quorum',true,
                'broker_writes_allowed',false
            )
        FROM agent.committee_memberships membership
        JOIN agent.tasks task
          ON task.source_kind='committee_packet_position'
         AND task.source_ref=v_packet_id::TEXT || ':' || membership.agent_name
        WHERE membership.committee_key=p_committee_key AND membership.required;
    END IF;

    UPDATE agent.graph_node_runs
    SET committee_packet_id=v_packet_id,status='running',
        started_at=coalesce(started_at,now()),updated_at=now()
    WHERE id=p_graph_node_run_id
      AND status IN ('ready','queued','running');

    INSERT INTO agent.graph_events (
        graph_run_id,graph_node_run_id,event_type,severity,actor,event_payload
    ) VALUES (
        p_graph_run_id,p_graph_node_run_id,'committee_packet_opened','info',
        p_opened_by,jsonb_build_object(
            'committee_packet_id',v_packet_id,
            'committee_key',p_committee_key,
            'sealed_positions',true,
            'human_final_required',v_registry.human_final_required
        )
    );

    RETURN (
        SELECT to_jsonb(row)
        FROM (
            SELECT * FROM agent.v_committee_packet_control
            WHERE id=v_packet_id
        ) row
    );
END $$;

CREATE OR REPLACE VIEW agent.v_graph_node_run_detail AS
SELECT node_run.id AS graph_node_run_id,node_run.graph_run_id,run.graph_key,
       node.node_key,node.node_name,node.node_type,node.owner_agent,node.skill_key,
       node.autonomy_level,node.approval_required,node.retry_limit,node.timeout_seconds,
       node.configuration,node_run.attempt,node_run.status,node_run.task_id,
       task.title AS task_title,task.status AS task_status,task.output_note_path,
       node_run.worker_run_id,worker.status AS worker_status,worker.output_summary,
       node_run.message_id,node_run.approval_id,approval.status AS approval_status,
       node_run.input_payload,node_run.output_payload,node_run.evidence,node_run.error,
       node_run.started_at,node_run.finished_at,node_run.created_at,node_run.updated_at,
       node_run.committee_packet_id,packet.packet_status AS committee_packet_status,
       session.session_status AS committee_session_status,
       session.committee_recommendation,session.human_final_decision,
       registry.decision_options AS committee_decision_options,
       approval.requested_action AS approval_requested_action,
       approval.decided_by AS approval_decided_by
FROM agent.graph_node_runs node_run
JOIN agent.graph_runs run ON run.id=node_run.graph_run_id
JOIN agent.graph_nodes node ON node.id=node_run.graph_node_id
LEFT JOIN agent.tasks task ON task.id=node_run.task_id
LEFT JOIN agent.worker_runs worker ON worker.id=node_run.worker_run_id
LEFT JOIN agent.approvals approval ON approval.id=node_run.approval_id
LEFT JOIN agent.committee_packets packet ON packet.id=node_run.committee_packet_id
LEFT JOIN agent.committee_sessions session ON session.packet_id=packet.id
LEFT JOIN agent.committee_registry registry ON registry.committee_key=packet.committee_key;

UPDATE agent.graph_nodes node
SET configuration=node.configuration || patch.configuration
FROM agent.graph_versions version
JOIN (VALUES
    ('research_to_investment_decision','committee','{"committee_key":"long_term","decision_question":"Choose the long-term research disposition after reviewing independent positions and dissent."}'::jsonb),
    ('strategy_research_lifecycle','committee','{"committee_key":"strategy","decision_question":"Choose the strategy research disposition; the maximum autonomous outcome is paper monitoring."}'::jsonb),
    ('kronos_forecast_research','committee','{"committee_key":"model_review","decision_question":"Choose whether this pinned Kronos forecast feature is acceptable for further research, conditional revision, or rejection."}'::jsonb)
) AS patch(graph_key,node_key,configuration)
  ON version.graph_key=patch.graph_key AND version.version=1
WHERE node.graph_version_id=version.id AND node.node_key=patch.node_key;

UPDATE agent.graph_edges edge
SET edge_kind='conditional',
    condition_type='node_output_equals',
    condition='{"path":"decision","equals":"paper_monitor"}'::jsonb,
    priority=10,
    label='Start paper monitor',
    enabled=true
FROM agent.graph_versions version
WHERE edge.graph_version_id=version.id
  AND version.graph_key='strategy_research_lifecycle'
  AND version.version=1
  AND edge.from_node_key='promotion_gate'
  AND edge.to_node_key='paper_monitor'
  AND edge.edge_kind='success';

INSERT INTO agent.graph_edges (
    graph_version_id,from_node_key,to_node_key,edge_kind,condition_type,
    condition,priority,label
)
SELECT version.id,edge.from_key,edge.to_key,'conditional',edge.condition_type,
       edge.condition,edge.priority,edge.label
FROM agent.graph_versions version
JOIN (VALUES
    ('promotion_gate','paper_monitor','node_output_equals',
     '{"path":"decision","equals":"paper_monitor"}'::jsonb,10,'Start paper monitor'),
    ('promotion_gate','checkpoint','node_output_not_equals',
     '{"path":"decision","equals":"paper_monitor"}'::jsonb,20,'Record non-promotion decision')
) AS edge(from_key,to_key,condition_type,condition,priority,label)
ON version.graph_key='strategy_research_lifecycle' AND version.version=1
ON CONFLICT (graph_version_id,from_node_key,to_node_key,edge_kind) DO UPDATE SET
    condition_type=EXCLUDED.condition_type,condition=EXCLUDED.condition,
    priority=EXCLUDED.priority,enabled=true,label=EXCLUDED.label;

INSERT INTO agent.graph_nodes (
    graph_version_id,node_key,node_name,node_type,owner_agent,skill_key,
    autonomy_level,approval_required,retry_limit,timeout_seconds,
    configuration,on_error,ui_position
)
SELECT version.id,'model_decision','Human model feature decision','approval_gate',
       'Charlie Munger',NULL::TEXT,'human_approval',true,0,86400,
       '{"approval_type":"model_feature_decision","maximum_scope":"research_feature","decision_question":"Choose the governed disposition for this pinned Kronos forecast feature after reviewing model-risk evidence and committee dissent."}'::jsonb,
       'request_human','{"x":0,"y":910}'::jsonb
FROM agent.graph_versions version
WHERE version.graph_key='kronos_forecast_research' AND version.version=1
ON CONFLICT (graph_version_id,node_key) DO UPDATE SET
    node_name=EXCLUDED.node_name,node_type=EXCLUDED.node_type,
    owner_agent=EXCLUDED.owner_agent,skill_key=EXCLUDED.skill_key,
    autonomy_level=EXCLUDED.autonomy_level,
    approval_required=EXCLUDED.approval_required,
    retry_limit=EXCLUDED.retry_limit,timeout_seconds=EXCLUDED.timeout_seconds,
    configuration=EXCLUDED.configuration,on_error=EXCLUDED.on_error,
    ui_position=EXCLUDED.ui_position;

UPDATE agent.graph_nodes node
SET ui_position='{"x":0,"y":1040}'::jsonb
FROM agent.graph_versions version
WHERE node.graph_version_id=version.id
  AND version.graph_key='kronos_forecast_research'
  AND version.version=1
  AND node.node_key='end';

UPDATE agent.graph_edges edge
SET enabled=false
FROM agent.graph_versions version
WHERE edge.graph_version_id=version.id
  AND version.graph_key='kronos_forecast_research'
  AND version.version=1
  AND edge.from_node_key='committee'
  AND edge.to_node_key='end';

INSERT INTO agent.graph_edges (
    graph_version_id,from_node_key,to_node_key,edge_kind,condition_type,
    condition,priority,label
)
SELECT version.id,edge.from_key,edge.to_key,'success','always','{}'::jsonb,
       edge.priority,edge.label
FROM agent.graph_versions version
JOIN (VALUES
    ('committee','model_decision',10,'Human decision'),
    ('model_decision','end',10,'Complete')
) AS edge(from_key,to_key,priority,label)
ON version.graph_key='kronos_forecast_research' AND version.version=1
ON CONFLICT (graph_version_id,from_node_key,to_node_key,edge_kind) DO UPDATE SET
    condition_type=EXCLUDED.condition_type,condition=EXCLUDED.condition,
    priority=EXCLUDED.priority,enabled=true,label=EXCLUDED.label;

DO $$
DECLARE
    version_row RECORD;
    validation JSONB;
BEGIN
    FOR version_row IN
        SELECT id,graph_key,version
        FROM agent.graph_versions
        WHERE graph_key IN (
            'daily_office_intelligence',
            'research_to_investment_decision',
            'strategy_research_lifecycle',
            'kronos_forecast_research'
        )
          AND version=1
    LOOP
        UPDATE agent.graph_versions version
        SET definition_hash=md5(coalesce((
            SELECT string_agg(
                node.node_key || ':' || node.node_type || ':' || coalesce(node.skill_key,'')
                || ':' || node.autonomy_level || ':' || node.configuration::TEXT
                || ':' || node.output_contract::TEXT,
                '|' ORDER BY node.node_key
            )
            FROM agent.graph_nodes node
            WHERE node.graph_version_id=version_row.id
        ),'') || '//' || coalesce((
            SELECT string_agg(
                edge.from_node_key || '>' || edge.to_node_key || ':' || edge.edge_kind
                || ':' || edge.condition_type || ':' || edge.condition::TEXT,
                '|' ORDER BY edge.from_node_key,edge.to_node_key,edge.edge_kind
            )
            FROM agent.graph_edges edge
            WHERE edge.graph_version_id=version_row.id AND edge.enabled=true
        ),''))
        WHERE version.id=version_row.id;

        validation := agent.validate_graph_version(version_row.id);
        IF NOT coalesce((validation->>'valid')::BOOLEAN,false) THEN
            RAISE EXCEPTION 'graph version failed validation after committee bridge: % v%: %',
                version_row.graph_key,version_row.version,validation;
        END IF;
        UPDATE agent.graph_versions
        SET status='active'
        WHERE id=version_row.id;
    END LOOP;
END;
$$;

INSERT INTO agent.tool_registry (
    tool_name,tool_type,owning_agent,permission_level,enabled,description,config
) VALUES
(
    'ai_os_open_graph_committee_packet','mcp_tool','Jarvis','write_scoped',true,
    'Open a sealed, quorum-bound committee packet for a governed graph node and dispatch independent position tasks.',
    '{"writes":["agent.committee_packets","agent.committee_sessions","agent.tasks","agent.inbox_items","agent.agent_messages","agent.graph_node_runs"],"sealed_until_quorum":true,"human_final_required":true,"capital_action_allowed":false,"broker_order_allowed":false}'::jsonb
),
(
    'ai_os_resolve_graph_decision','api_tool','Charlie Munger','write_with_approval',true,
    'Record one validated human graph decision, close the linked committee packet, and resume the bounded graph.',
    '{"writes":["agent.approvals","agent.committee_sessions","agent.committee_packets","agent.graph_node_runs","agent.waiting_on_principal"],"human_decision_required":true,"broker_order_allowed":false}'::jsonb
)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type=excluded.tool_type,owning_agent=excluded.owning_agent,
    permission_level=excluded.permission_level,enabled=excluded.enabled,
    description=excluded.description,config=excluded.config;

COMMIT;
