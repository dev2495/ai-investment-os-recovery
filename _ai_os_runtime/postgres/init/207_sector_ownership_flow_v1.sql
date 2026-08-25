BEGIN;

INSERT INTO core.source_systems (
    name, source_type, location, sensitivity, status, notes
) VALUES
    (
        'NSE corporate shareholding filings',
        'primary_exchange_filing',
        'https://www.nseindia.com/companies-listing/corporate-filings-shareholding-pattern',
        'public',
        'active',
        'Official NSE shareholding master records with XBRL filing links and retained raw response hashes.'
    ),
    (
        'NSE bulk and block deal archives',
        'primary_exchange_report',
        'https://www.nseindia.com/report-detail/display-bulk-and-block-deals',
        'public',
        'active',
        'Official NSE constituent-level bulk and block deal records with retained raw response hashes.'
    )
ON CONFLICT (name) DO UPDATE SET
    source_type=EXCLUDED.source_type,
    location=EXCLUDED.location,
    sensitivity=EXCLUDED.sensitivity,
    status=EXCLUDED.status,
    notes=EXCLUDED.notes;

CREATE UNIQUE INDEX IF NOT EXISTS uq_sector_flow_source_lineage
ON sector_intelligence.flow_observations (
    coalesce(taxonomy_node_id,0),
    coalesce(symbol_id,0),
    observed_at,
    flow_actor,
    flow_type,
    source_system_id,
    coalesce(source_reference,''),
    net_value
);

CREATE INDEX IF NOT EXISTS idx_sector_ownership_node_period
ON sector_intelligence.ownership_observations (
    taxonomy_node_id,period_end DESC,symbol_id
);

CREATE OR REPLACE VIEW sector_intelligence.v_sector_ownership_flow_coverage AS
WITH nodes AS (
    SELECT id AS taxonomy_node_id,taxonomy_key,node_name
    FROM sector_intelligence.taxonomy_nodes
), flow_coverage AS (
    SELECT taxonomy_node_id,
           count(*) AS flow_observation_count,
           count(DISTINCT symbol_id) AS flow_symbol_count,
           max(observed_at) AS latest_flow_at
    FROM sector_intelligence.flow_observations
    WHERE symbol_id IS NOT NULL
      AND source_system_id IS NOT NULL
      AND coalesce(source_reference,'')<>''
      AND jsonb_typeof(evidence)='array'
      AND jsonb_array_length(evidence)>0
    GROUP BY taxonomy_node_id
), ownership_coverage AS (
    SELECT taxonomy_node_id,
           count(*) AS ownership_observation_count,
           count(DISTINCT symbol_id) AS ownership_symbol_count,
           max(period_end) AS latest_ownership_period_end
    FROM sector_intelligence.ownership_observations
    WHERE source_system_id IS NOT NULL
      AND coalesce(source_reference,'')<>''
      AND jsonb_typeof(evidence)='array'
      AND jsonb_array_length(evidence)>0
    GROUP BY taxonomy_node_id
)
SELECT nodes.taxonomy_node_id,nodes.taxonomy_key,nodes.node_name,
       coalesce(flow_coverage.flow_observation_count,0) AS flow_observation_count,
       coalesce(flow_coverage.flow_symbol_count,0) AS flow_symbol_count,
       flow_coverage.latest_flow_at,
       coalesce(ownership_coverage.ownership_observation_count,0) AS ownership_observation_count,
       coalesce(ownership_coverage.ownership_symbol_count,0) AS ownership_symbol_count,
       ownership_coverage.latest_ownership_period_end
FROM nodes
LEFT JOIN flow_coverage USING (taxonomy_node_id)
LEFT JOIN ownership_coverage USING (taxonomy_node_id);

CREATE OR REPLACE FUNCTION sector_intelligence.run_acceptance_gates_v3(
    p_run_key TEXT,
    p_taxonomy_node_id BIGINT,
    p_as_of_date DATE,
    p_started_by TEXT DEFAULT 'Sector Portfolio Manager'
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_v2_id BIGINT;
    v_run_id BIGINT;
    v_flow_count INTEGER;
    v_flow_symbols INTEGER;
    v_ownership_count INTEGER;
    v_ownership_symbols INTEGER;
BEGIN
    v_v2_id := sector_intelligence.run_acceptance_gates_v2(
        p_run_key || '-v2-baseline',
        p_taxonomy_node_id,
        p_as_of_date,
        p_started_by
    );

    INSERT INTO sector_intelligence.acceptance_runs (
        run_key,taxonomy_node_id,as_of_date,status,gate_version,started_by
    ) VALUES (
        p_run_key,p_taxonomy_node_id,p_as_of_date,'running','sector-acceptance-v3',p_started_by
    )
    ON CONFLICT (taxonomy_node_id,as_of_date,gate_version) DO UPDATE SET
        run_key=EXCLUDED.run_key,status='running',started_by=EXCLUDED.started_by,
        summary='{}'::jsonb,started_at=now(),finished_at=NULL
    RETURNING id INTO v_run_id;

    DELETE FROM sector_intelligence.acceptance_gate_results
    WHERE acceptance_run_id=v_run_id;

    INSERT INTO sector_intelligence.acceptance_gate_results (
        acceptance_run_id,gate_key,gate_name,status,observed_value,
        threshold_value,comparator,evidence,failure_reason,checked_by
    )
    SELECT v_run_id,result.gate_key,result.gate_name,result.status,
           result.observed_value,result.threshold_value,result.comparator,
           result.evidence,result.failure_reason,result.checked_by
    FROM sector_intelligence.acceptance_gate_results result
    WHERE result.acceptance_run_id=v_v2_id
      AND result.gate_key<>'flows_and_ownership';

    WITH active_members AS (
        SELECT membership.symbol_id
        FROM sector_intelligence.instrument_membership_history membership
        WHERE membership.taxonomy_node_id=p_taxonomy_node_id
          AND membership.valid_from<=p_as_of_date
          AND (membership.valid_to IS NULL OR membership.valid_to>=p_as_of_date)
    )
    SELECT count(*)::int,count(DISTINCT flow.symbol_id)::int
    INTO v_flow_count,v_flow_symbols
    FROM sector_intelligence.flow_observations flow
    JOIN active_members member ON member.symbol_id=flow.symbol_id
    WHERE flow.taxonomy_node_id=p_taxonomy_node_id
      AND flow.observed_at::date<=p_as_of_date
      AND flow.flow_type IN ('bulk_deal','block_deal','insider_trade','promoter_transaction')
      AND flow.source_system_id IS NOT NULL
      AND coalesce(flow.source_reference,'')<>''
      AND jsonb_typeof(flow.evidence)='array'
      AND jsonb_array_length(flow.evidence)>0;

    WITH active_members AS (
        SELECT membership.symbol_id
        FROM sector_intelligence.instrument_membership_history membership
        WHERE membership.taxonomy_node_id=p_taxonomy_node_id
          AND membership.valid_from<=p_as_of_date
          AND (membership.valid_to IS NULL OR membership.valid_to>=p_as_of_date)
    )
    SELECT count(*)::int,count(DISTINCT ownership.symbol_id)::int
    INTO v_ownership_count,v_ownership_symbols
    FROM sector_intelligence.ownership_observations ownership
    JOIN active_members member ON member.symbol_id=ownership.symbol_id
    WHERE ownership.taxonomy_node_id=p_taxonomy_node_id
      AND ownership.period_end<=p_as_of_date
      AND ownership.observation_type='shareholding_pattern'
      AND ownership.source_system_id IS NOT NULL
      AND coalesce(ownership.source_reference,'')<>''
      AND jsonb_typeof(ownership.evidence)='array'
      AND jsonb_array_length(ownership.evidence)>0;

    INSERT INTO sector_intelligence.acceptance_gate_results (
        acceptance_run_id,gate_key,gate_name,status,observed_value,
        threshold_value,comparator,evidence,failure_reason,checked_by
    ) VALUES (
        v_run_id,'flows_and_ownership','Flows And Ownership Evidence',
        CASE WHEN v_flow_count>=1 AND v_ownership_count>=1 THEN 'passed' ELSE 'blocked' END,
        least(v_flow_count,v_ownership_count),1,'gte',
        jsonb_build_object(
            'constituent_level_flow_observations',v_flow_count,
            'flow_symbols',v_flow_symbols,
            'source_backed_ownership_observations',v_ownership_count,
            'ownership_symbols',v_ownership_symbols,
            'active_membership_required',true,
            'source_reference_required',true,
            'evidence_array_required',true,
            'market_wide_flow_substitution_allowed',false
        ),
        CASE WHEN v_flow_count>=1 AND v_ownership_count>=1 THEN NULL
             ELSE format('Requires both an official constituent-level transaction flow and an official ownership filing; found %s flows and %s ownership observations',
                         v_flow_count,v_ownership_count) END,
        'Sector Flow And Ownership Analyst'
    );

    UPDATE sector_intelligence.acceptance_runs run
    SET status=CASE WHEN EXISTS (
            SELECT 1 FROM sector_intelligence.acceptance_gate_results result
            WHERE result.acceptance_run_id=v_run_id
              AND result.status IN ('failed','blocked')
        ) THEN 'blocked' ELSE 'passed' END,
        summary=(
            SELECT jsonb_build_object(
                'gate_count',count(*),
                'passed_count',count(*) FILTER (WHERE status='passed'),
                'failed_count',count(*) FILTER (WHERE status='failed'),
                'blocked_count',count(*) FILTER (WHERE status='blocked'),
                'flow_count',v_flow_count,
                'flow_symbols',v_flow_symbols,
                'ownership_count',v_ownership_count,
                'ownership_symbols',v_ownership_symbols,
                'broker_write_allowed',false,
                'capital_action_allowed',false
            )
            FROM sector_intelligence.acceptance_gate_results
            WHERE acceptance_run_id=v_run_id
        ),
        finished_at=now()
    WHERE run.id=v_run_id;

    RETURN v_run_id;
END;
$$;

COMMENT ON FUNCTION sector_intelligence.run_acceptance_gates_v3(TEXT,BIGINT,DATE,TEXT) IS
'Strict sector acceptance requiring both source-backed ownership and constituent-level flow evidence. Market-wide totals cannot substitute. No capital or broker authority.';

INSERT INTO agent.tool_registry (
    tool_name,tool_type,owning_agent,permission_level,enabled,description,config
) VALUES (
    'ai_os_sync_sector_ownership_flows',
    'mcp_tool',
    'Sector Flow And Ownership Analyst',
    'write_db_manual_only',
    true,
    'Collect official NSE shareholding filings and constituent-level bulk/block deals with retained raw evidence.',
    '{"script":"_ai_os_runtime/scripts/sync_sector_ownership_flows.py","writes":["sector_intelligence.ownership_observations","sector_intelligence.flow_observations"],"broker_write_allowed":false,"capital_action_allowed":false,"seed_data_allowed":false}'::jsonb
)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type=EXCLUDED.tool_type,
    owning_agent=EXCLUDED.owning_agent,
    permission_level=EXCLUDED.permission_level,
    enabled=EXCLUDED.enabled,
    description=EXCLUDED.description,
    config=EXCLUDED.config;

COMMIT;
