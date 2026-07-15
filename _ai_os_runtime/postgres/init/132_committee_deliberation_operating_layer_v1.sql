CREATE TABLE IF NOT EXISTS agent.committee_packets (
    id BIGSERIAL PRIMARY KEY,
    packet_key TEXT NOT NULL UNIQUE,
    committee_key TEXT NOT NULL REFERENCES agent.committee_registry(committee_key),
    committee_item_key TEXT,
    source_view TEXT,
    source_id BIGINT,
    title TEXT NOT NULL,
    decision_question TEXT NOT NULL,
    packet_status TEXT NOT NULL DEFAULT 'collecting_positions'
        CHECK (packet_status IN ('collecting_positions','deliberating','awaiting_human','closed','cancelled')),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    due_at TIMESTAMPTZ,
    opened_by TEXT NOT NULL,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_committee_packets_open_item
ON agent.committee_packets (committee_key, committee_item_key)
WHERE committee_item_key IS NOT NULL
  AND packet_status IN ('collecting_positions','deliberating','awaiting_human');

CREATE INDEX IF NOT EXISTS idx_committee_packets_status
ON agent.committee_packets (packet_status, due_at, updated_at DESC);

CREATE TABLE IF NOT EXISTS agent.committee_positions (
    id BIGSERIAL PRIMARY KEY,
    packet_id BIGINT NOT NULL REFERENCES agent.committee_packets(id) ON DELETE CASCADE,
    agent_name TEXT NOT NULL REFERENCES agent.profiles(agent_name),
    stance TEXT NOT NULL CHECK (stance IN ('support','oppose','conditional','abstain','request_more_evidence','block')),
    recommendation TEXT NOT NULL,
    confidence NUMERIC(5,2) NOT NULL CHECK (confidence >= 0 AND confidence <= 100),
    thesis TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    conditions JSONB NOT NULL DEFAULT '[]'::jsonb,
    independent_submission BOOLEAN NOT NULL DEFAULT true,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (packet_id, agent_name)
);

CREATE INDEX IF NOT EXISTS idx_committee_positions_packet
ON agent.committee_positions (packet_id, submitted_at);

CREATE TABLE IF NOT EXISTS agent.committee_discussion_messages (
    id BIGSERIAL PRIMARY KEY,
    packet_id BIGINT NOT NULL REFERENCES agent.committee_packets(id) ON DELETE CASCADE,
    from_agent TEXT NOT NULL REFERENCES agent.profiles(agent_name),
    reply_to_position_id BIGINT REFERENCES agent.committee_positions(id) ON DELETE SET NULL,
    message_type TEXT NOT NULL DEFAULT 'challenge'
        CHECK (message_type IN ('challenge','response','clarification','risk_objection','evidence_update','chair_synthesis')),
    body TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_committee_discussion_packet
ON agent.committee_discussion_messages (packet_id, created_at);

CREATE TABLE IF NOT EXISTS agent.committee_sessions (
    id BIGSERIAL PRIMARY KEY,
    packet_id BIGINT NOT NULL UNIQUE REFERENCES agent.committee_packets(id) ON DELETE CASCADE,
    chair_agent TEXT NOT NULL REFERENCES agent.profiles(agent_name),
    session_status TEXT NOT NULL DEFAULT 'collecting_positions'
        CHECK (session_status IN ('collecting_positions','deliberating','awaiting_human','closed','cancelled')),
    quorum_required INTEGER NOT NULL,
    counted_positions INTEGER NOT NULL DEFAULT 0,
    quorum_met BOOLEAN NOT NULL DEFAULT false,
    committee_recommendation TEXT,
    decision_status TEXT NOT NULL DEFAULT 'pending',
    minutes TEXT,
    dissent_summary TEXT,
    conditions JSONB NOT NULL DEFAULT '[]'::jsonb,
    human_final_decision TEXT,
    decided_by TEXT,
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent.committee_followups (
    id BIGSERIAL PRIMARY KEY,
    packet_id BIGINT NOT NULL REFERENCES agent.committee_packets(id) ON DELETE CASCADE,
    owner_agent TEXT NOT NULL REFERENCES agent.profiles(agent_name),
    title TEXT NOT NULL,
    objective TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued','in_progress','completed','blocked','cancelled')),
    due_at TIMESTAMPTZ,
    related_task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_committee_followups_packet
ON agent.committee_followups (packet_id, status, due_at);

CREATE OR REPLACE VIEW agent.v_committee_packet_control AS
WITH position_counts AS (
    SELECT p.packet_id,
           count(*) FILTER (WHERE m.vote_type <> 'non_voting')::int AS counted_positions,
           count(*) FILTER (WHERE p.stance = 'support')::int AS support_count,
           count(*) FILTER (WHERE p.stance = 'oppose')::int AS oppose_count,
           count(*) FILTER (WHERE p.stance = 'conditional')::int AS conditional_count,
           count(*) FILTER (WHERE p.stance IN ('block','request_more_evidence'))::int AS challenge_count,
           jsonb_agg(jsonb_build_object(
               'agent_name',p.agent_name,'stance',p.stance,'recommendation',p.recommendation,
               'confidence',p.confidence,'submitted_at',p.submitted_at
           ) ORDER BY p.submitted_at) AS position_summary
    FROM agent.committee_positions p
    JOIN agent.committee_packets packet ON packet.id=p.packet_id
    JOIN agent.committee_memberships m ON m.committee_key=packet.committee_key AND m.agent_name=p.agent_name
    GROUP BY p.packet_id
), followup_counts AS (
    SELECT packet_id,count(*)::int followup_count,
           count(*) FILTER (WHERE status IN ('queued','in_progress','blocked'))::int open_followup_count
    FROM agent.committee_followups GROUP BY packet_id
), discussion_counts AS (
    SELECT packet_id,count(*)::int discussion_count,max(created_at) latest_discussion_at
    FROM agent.committee_discussion_messages GROUP BY packet_id
)
SELECT packet.id,packet.packet_key,packet.committee_key,registry.committee_name,
       registry.chair_agent,registry.mandate,registry.quorum,registry.decision_options,
       registry.human_final_required,packet.committee_item_key,packet.source_view,packet.source_id,
       packet.title,packet.decision_question,packet.packet_status,packet.evidence,packet.metadata,
       packet.due_at,packet.opened_by,packet.opened_at,packet.closed_at,packet.updated_at,
       coalesce(position_counts.counted_positions,0) AS counted_positions,
       coalesce(position_counts.support_count,0) AS support_count,
       coalesce(position_counts.oppose_count,0) AS oppose_count,
       coalesce(position_counts.conditional_count,0) AS conditional_count,
       coalesce(position_counts.challenge_count,0) AS challenge_count,
       coalesce(position_counts.position_summary,'[]'::jsonb) AS position_summary,
       coalesce(followup_counts.followup_count,0) AS followup_count,
       coalesce(followup_counts.open_followup_count,0) AS open_followup_count,
       coalesce(discussion_counts.discussion_count,0) AS discussion_count,
       discussion_counts.latest_discussion_at,
       session.id AS session_id,session.session_status,session.quorum_met,
       session.committee_recommendation,session.decision_status,session.minutes,
       session.dissent_summary,session.conditions,session.human_final_decision,
       session.decided_by,session.decided_at,
       greatest(packet.updated_at,coalesce(discussion_counts.latest_discussion_at,'epoch'::timestamptz),coalesce(session.updated_at,'epoch'::timestamptz)) AS latest_activity_at
FROM agent.committee_packets packet
JOIN agent.committee_registry registry USING(committee_key)
LEFT JOIN position_counts ON position_counts.packet_id=packet.id
LEFT JOIN followup_counts ON followup_counts.packet_id=packet.id
LEFT JOIN discussion_counts ON discussion_counts.packet_id=packet.id
LEFT JOIN agent.committee_sessions session ON session.packet_id=packet.id;

CREATE OR REPLACE VIEW agent.v_committee_position_control AS
SELECT p.id,p.packet_id,packet.packet_key,packet.committee_key,registry.committee_name,
       p.agent_name,profile.display_title,membership.committee_role,membership.vote_type,
       membership.challenge_mandate,p.stance,p.recommendation,p.confidence,p.thesis,
       p.evidence,p.conditions,p.independent_submission,p.submitted_at,p.updated_at,
       CASE WHEN packet.packet_status='collecting_positions' THEN true ELSE false END AS sealed_from_peers
FROM agent.committee_positions p
JOIN agent.committee_packets packet ON packet.id=p.packet_id
JOIN agent.committee_registry registry USING(committee_key)
JOIN agent.profiles profile ON profile.agent_name=p.agent_name
JOIN agent.committee_memberships membership ON membership.committee_key=packet.committee_key AND membership.agent_name=p.agent_name;

CREATE OR REPLACE VIEW agent.v_committee_followup_control AS
SELECT f.id,f.packet_id,packet.packet_key,packet.committee_key,registry.committee_name,
       f.owner_agent,profile.display_title AS owner_title,f.title,f.objective,f.status,
       f.due_at,f.related_task_id,task.status AS task_status,f.evidence,f.created_at,f.updated_at
FROM agent.committee_followups f
JOIN agent.committee_packets packet ON packet.id=f.packet_id
JOIN agent.committee_registry registry USING(committee_key)
JOIN agent.profiles profile ON profile.agent_name=f.owner_agent
LEFT JOIN agent.tasks task ON task.id=f.related_task_id;

CREATE OR REPLACE FUNCTION agent.open_committee_packet(
    p_committee_item_key TEXT,
    p_title TEXT,
    p_decision_question TEXT,
    p_opened_by TEXT,
    p_due_at TIMESTAMPTZ DEFAULT NULL,
    p_evidence JSONB DEFAULT '[]'::jsonb
) RETURNS JSONB LANGUAGE plpgsql AS $$
DECLARE
    v_item RECORD;
    v_committee_key TEXT;
    v_packet_id BIGINT;
    v_packet_key TEXT;
BEGIN
    SELECT * INTO v_item FROM agent.v_committee_room_items WHERE committee_item_key=p_committee_item_key LIMIT 1;
    IF NOT FOUND THEN RAISE EXCEPTION 'committee room item not found: %',p_committee_item_key; END IF;
    v_committee_key := CASE
        WHEN p_committee_item_key LIKE 'strategy:%' THEN 'strategy'
        WHEN p_committee_item_key LIKE 'long_term:%' THEN 'long_term'
        WHEN p_committee_item_key LIKE 'special:%' THEN 'special_situations'
        ELSE NULL END;
    IF v_committee_key IS NULL THEN RAISE EXCEPTION 'committee lane is not mapped: %',p_committee_item_key; END IF;

    SELECT id INTO v_packet_id FROM agent.committee_packets
    WHERE committee_key=v_committee_key AND committee_item_key=p_committee_item_key
      AND packet_status IN ('collecting_positions','deliberating','awaiting_human') LIMIT 1;
    IF v_packet_id IS NULL THEN
        v_packet_key := 'committee-' || v_committee_key || '-' || to_char(clock_timestamp(),'YYYYMMDDHH24MISSMS');
        INSERT INTO agent.committee_packets (
            packet_key,committee_key,committee_item_key,source_view,source_id,title,
            decision_question,evidence,due_at,opened_by,metadata
        ) VALUES (
            v_packet_key,v_committee_key,p_committee_item_key,v_item.source_view,v_item.source_id,
            coalesce(nullif(trim(p_title),''),v_item.title),p_decision_question,
            coalesce(p_evidence,'[]'::jsonb) || jsonb_build_array(jsonb_build_object(
                'source_view',v_item.source_view,'source_id',v_item.source_id,
                'room_state',v_item.room_state,'recommended_next_action',v_item.recommended_next_action
            )),p_due_at,p_opened_by,
            jsonb_build_object('subject_name',v_item.subject_name,'symbol',v_item.symbol,'exchange',v_item.exchange,'risk_level',v_item.risk_level)
        ) RETURNING id INTO v_packet_id;

        INSERT INTO agent.committee_sessions (packet_id,chair_agent,quorum_required)
        SELECT v_packet_id,chair_agent,quorum FROM agent.committee_registry WHERE committee_key=v_committee_key;

        WITH tasks AS (
            INSERT INTO agent.tasks (title,objective,owner_agent,status,priority,approval_required,source_kind,source_ref,output_format,evidence)
            SELECT 'Independent committee position: ' || coalesce(nullif(trim(p_title),''),v_item.title),
                   'Submit an independent evidence-backed position before reading peer positions. Address your challenge mandate: ' || membership.challenge_mandate,
                   membership.agent_name,'queued',CASE WHEN membership.vote_type='veto_recommendation' THEN 'high' ELSE 'normal' END,
                   false,'committee_packet_position',v_packet_id::text || ':' || membership.agent_name,
                   'committee_position',jsonb_build_array(jsonb_build_object('table','agent.committee_packets','id',v_packet_id))
            FROM agent.committee_memberships membership
            WHERE membership.committee_key=v_committee_key AND membership.required
            RETURNING id,title,owner_agent,priority,evidence
        )
        INSERT INTO agent.inbox_items (task_id,title,owner_agent,status,priority,recommended_action,evidence,target_workspace)
        SELECT id,title,owner_agent,'queued',priority,
               'Submit your sealed independent position with evidence, recommendation, confidence, and conditions.',
               evidence,'committees' FROM tasks;

        INSERT INTO agent.agent_messages (thread_key,from_agent,to_agent,subject,body,priority,status,related_task_id,metadata)
        SELECT 'committee:' || v_packet_id,registry.chair_agent,membership.agent_name,
               'Independent position requested: ' || coalesce(nullif(trim(p_title),''),v_item.title),
               'Do not anchor on peer opinions. Submit evidence, recommendation, confidence, conditions, and the strongest disconfirming argument under your role mandate.',
               CASE WHEN membership.vote_type='veto_recommendation' THEN 'high' ELSE 'medium' END,'unread',task.id,
               jsonb_build_object('packet_id',v_packet_id,'committee_key',v_committee_key,'sealed_until_quorum',true)
        FROM agent.committee_memberships membership
        JOIN agent.committee_registry registry USING(committee_key)
        JOIN agent.tasks task ON task.source_kind='committee_packet_position' AND task.source_ref=v_packet_id::text || ':' || membership.agent_name
        WHERE membership.committee_key=v_committee_key AND membership.required;
    END IF;
    RETURN (SELECT to_jsonb(row) FROM (SELECT * FROM agent.v_committee_packet_control WHERE id=v_packet_id) row);
END $$;

CREATE OR REPLACE FUNCTION agent.submit_committee_position(
    p_packet_id BIGINT,p_agent_name TEXT,p_stance TEXT,p_recommendation TEXT,
    p_confidence NUMERIC,p_thesis TEXT,p_evidence JSONB DEFAULT '[]'::jsonb,
    p_conditions JSONB DEFAULT '[]'::jsonb
) RETURNS JSONB LANGUAGE plpgsql AS $$
DECLARE v_packet agent.committee_packets%ROWTYPE; v_count INTEGER; v_quorum INTEGER;
BEGIN
    SELECT * INTO v_packet FROM agent.committee_packets WHERE id=p_packet_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'committee packet not found: %',p_packet_id; END IF;
    IF v_packet.packet_status NOT IN ('collecting_positions','deliberating') THEN RAISE EXCEPTION 'committee packet is not accepting positions'; END IF;
    IF NOT EXISTS (SELECT 1 FROM agent.committee_memberships WHERE committee_key=v_packet.committee_key AND agent_name=p_agent_name) THEN
        RAISE EXCEPTION 'agent is not a member of this committee: %',p_agent_name;
    END IF;
    INSERT INTO agent.committee_positions (packet_id,agent_name,stance,recommendation,confidence,thesis,evidence,conditions)
    VALUES (p_packet_id,p_agent_name,p_stance,p_recommendation,p_confidence,p_thesis,coalesce(p_evidence,'[]'::jsonb),coalesce(p_conditions,'[]'::jsonb))
    ON CONFLICT (packet_id,agent_name) DO UPDATE SET stance=excluded.stance,recommendation=excluded.recommendation,
        confidence=excluded.confidence,thesis=excluded.thesis,evidence=excluded.evidence,conditions=excluded.conditions,updated_at=now();
    UPDATE agent.tasks SET status='completed',updated_at=now()
    WHERE source_kind='committee_packet_position' AND source_ref=p_packet_id::text || ':' || p_agent_name;
    UPDATE agent.inbox_items SET status='done',updated_at=now()
    WHERE task_id IN (SELECT id FROM agent.tasks WHERE source_kind='committee_packet_position' AND source_ref=p_packet_id::text || ':' || p_agent_name);
    SELECT count(*) FILTER (WHERE membership.vote_type<>'non_voting'),registry.quorum
      INTO v_count,v_quorum
    FROM agent.committee_positions position
    JOIN agent.committee_memberships membership ON membership.committee_key=v_packet.committee_key AND membership.agent_name=position.agent_name
    JOIN agent.committee_registry registry ON registry.committee_key=v_packet.committee_key
    WHERE position.packet_id=p_packet_id GROUP BY registry.quorum;
    UPDATE agent.committee_packets SET packet_status=CASE WHEN coalesce(v_count,0)>=v_quorum THEN 'deliberating' ELSE 'collecting_positions' END,updated_at=now() WHERE id=p_packet_id;
    UPDATE agent.committee_sessions SET counted_positions=coalesce(v_count,0),quorum_met=coalesce(v_count,0)>=v_quorum,
        session_status=CASE WHEN coalesce(v_count,0)>=v_quorum THEN 'deliberating' ELSE 'collecting_positions' END,updated_at=now()
    WHERE packet_id=p_packet_id;
    RETURN (SELECT to_jsonb(row) FROM (SELECT * FROM agent.v_committee_position_control WHERE packet_id=p_packet_id AND agent_name=p_agent_name) row);
END $$;

CREATE OR REPLACE FUNCTION agent.add_committee_discussion(
    p_packet_id BIGINT,p_from_agent TEXT,p_message_type TEXT,p_body TEXT,
    p_reply_to_position_id BIGINT DEFAULT NULL,p_evidence JSONB DEFAULT '[]'::jsonb
) RETURNS JSONB LANGUAGE plpgsql AS $$
DECLARE v_packet agent.committee_packets%ROWTYPE; v_id BIGINT;
BEGIN
    SELECT * INTO v_packet FROM agent.committee_packets WHERE id=p_packet_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'committee packet not found: %',p_packet_id; END IF;
    IF v_packet.packet_status NOT IN ('deliberating','awaiting_human') THEN RAISE EXCEPTION 'discussion opens only after quorum'; END IF;
    IF NOT EXISTS (SELECT 1 FROM agent.committee_positions WHERE packet_id=p_packet_id AND agent_name=p_from_agent) THEN
        RAISE EXCEPTION 'submit an independent position before joining discussion';
    END IF;
    INSERT INTO agent.committee_discussion_messages (packet_id,from_agent,reply_to_position_id,message_type,body,evidence)
    VALUES (p_packet_id,p_from_agent,p_reply_to_position_id,p_message_type,p_body,coalesce(p_evidence,'[]'::jsonb)) RETURNING id INTO v_id;
    UPDATE agent.committee_packets SET updated_at=now() WHERE id=p_packet_id;
    RETURN (SELECT to_jsonb(row) FROM (SELECT * FROM agent.committee_discussion_messages WHERE id=v_id) row);
END $$;

CREATE OR REPLACE FUNCTION agent.synthesize_committee_session(
    p_packet_id BIGINT,p_chair_agent TEXT,p_recommendation TEXT,p_minutes TEXT,
    p_dissent_summary TEXT DEFAULT NULL,p_conditions JSONB DEFAULT '[]'::jsonb
) RETURNS JSONB LANGUAGE plpgsql AS $$
DECLARE v_packet agent.committee_packets%ROWTYPE; v_registry agent.committee_registry%ROWTYPE; v_count INTEGER;
BEGIN
    SELECT * INTO v_packet FROM agent.committee_packets WHERE id=p_packet_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'committee packet not found: %',p_packet_id; END IF;
    SELECT * INTO v_registry FROM agent.committee_registry WHERE committee_key=v_packet.committee_key;
    SELECT count(*) FILTER (WHERE membership.vote_type<>'non_voting') INTO v_count
    FROM agent.committee_positions position
    JOIN agent.committee_memberships membership ON membership.committee_key=v_packet.committee_key AND membership.agent_name=position.agent_name
    WHERE position.packet_id=p_packet_id;
    IF coalesce(v_count,0)<v_registry.quorum THEN RAISE EXCEPTION 'quorum not met: % of %',coalesce(v_count,0),v_registry.quorum; END IF;
    IF p_chair_agent<>v_registry.chair_agent THEN RAISE EXCEPTION 'only the registered chair can synthesize this committee'; END IF;
    IF NOT (p_recommendation=ANY(v_registry.decision_options)) THEN RAISE EXCEPTION 'recommendation is not allowed for this committee: %',p_recommendation; END IF;
    UPDATE agent.committee_sessions SET session_status=CASE WHEN v_registry.human_final_required THEN 'awaiting_human' ELSE 'closed' END,
        counted_positions=v_count,quorum_met=true,committee_recommendation=p_recommendation,
        decision_status=CASE WHEN v_registry.human_final_required THEN 'committee_recommendation' ELSE 'final' END,
        minutes=p_minutes,dissent_summary=p_dissent_summary,conditions=coalesce(p_conditions,'[]'::jsonb),updated_at=now()
    WHERE packet_id=p_packet_id;
    UPDATE agent.committee_packets SET packet_status=CASE WHEN v_registry.human_final_required THEN 'awaiting_human' ELSE 'closed' END,
        closed_at=CASE WHEN v_registry.human_final_required THEN NULL ELSE now() END,updated_at=now() WHERE id=p_packet_id;
    RETURN (SELECT to_jsonb(row) FROM (SELECT * FROM agent.v_committee_packet_control WHERE id=p_packet_id) row);
END $$;

CREATE OR REPLACE FUNCTION agent.record_committee_human_decision(
    p_packet_id BIGINT,p_decision TEXT,p_decided_by TEXT,p_rationale TEXT
) RETURNS JSONB LANGUAGE plpgsql AS $$
BEGIN
    IF nullif(trim(p_decided_by),'') IS NULL THEN RAISE EXCEPTION 'decided_by is required'; END IF;
    UPDATE agent.committee_sessions SET session_status='closed',decision_status='human_final',
        human_final_decision=p_decision,decided_by=p_decided_by,decided_at=now(),
        minutes=coalesce(minutes,'') || E'\n\nHuman final rationale: ' || p_rationale,updated_at=now()
    WHERE packet_id=p_packet_id AND session_status='awaiting_human';
    IF NOT FOUND THEN RAISE EXCEPTION 'committee packet is not awaiting a human decision'; END IF;
    UPDATE agent.committee_packets SET packet_status='closed',closed_at=now(),updated_at=now() WHERE id=p_packet_id;
    UPDATE agent.tasks SET status='completed',updated_at=now() WHERE source_kind='committee_packet_position' AND source_ref LIKE p_packet_id::text || ':%';
    UPDATE agent.inbox_items SET status='done',updated_at=now() WHERE task_id IN (SELECT id FROM agent.tasks WHERE source_kind='committee_packet_position' AND source_ref LIKE p_packet_id::text || ':%');
    RETURN (SELECT to_jsonb(row) FROM (SELECT * FROM agent.v_committee_packet_control WHERE id=p_packet_id) row);
END $$;

INSERT INTO agent.tool_registry (tool_name,tool_type,owning_agent,permission_level,enabled,description,config)
VALUES
('ai_os_open_committee_packet','mcp_tool','Charlie Munger','write_with_approval',true,'Open a durable committee packet and dispatch sealed independent position assignments.','{"writes":["agent.committee_packets","agent.committee_sessions","agent.tasks","agent.inbox_items","agent.agent_messages"],"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb),
('ai_os_submit_committee_position','mcp_tool','Committee Member Agents','write_scoped',true,'Submit an independent evidence-backed committee position before peer deliberation.','{"writes":["agent.committee_positions"],"sealed_until_quorum":true,"capital_action_allowed":false}'::jsonb),
('ai_os_committee_deliberation','mcp_tool','Committee Chairs','write_with_approval',true,'Record post-quorum challenges, minutes, conditions, recommendation, and human final decision.','{"writes":["agent.committee_discussion_messages","agent.committee_sessions","agent.committee_followups"],"human_final_required":true,"live_execution_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET tool_type=excluded.tool_type,owning_agent=excluded.owning_agent,
permission_level=excluded.permission_level,enabled=excluded.enabled,description=excluded.description,config=excluded.config;
