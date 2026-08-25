BEGIN;

CREATE TABLE IF NOT EXISTS sector_intelligence.acceptance_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    taxonomy_node_id BIGINT NOT NULL REFERENCES sector_intelligence.taxonomy_nodes(id) ON DELETE RESTRICT,
    as_of_date DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running','passed','failed','blocked')),
    gate_version TEXT NOT NULL,
    started_by TEXT NOT NULL,
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    UNIQUE (taxonomy_node_id, as_of_date, gate_version)
);

CREATE TABLE IF NOT EXISTS sector_intelligence.acceptance_gate_results (
    id BIGSERIAL PRIMARY KEY,
    acceptance_run_id BIGINT NOT NULL REFERENCES sector_intelligence.acceptance_runs(id) ON DELETE CASCADE,
    gate_key TEXT NOT NULL,
    gate_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('passed','failed','blocked','not_applicable')),
    observed_value NUMERIC,
    threshold_value NUMERIC,
    comparator TEXT CHECK (comparator IN ('gte','lte','eq','not_null','zero')),
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    failure_reason TEXT,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    checked_by TEXT NOT NULL DEFAULT 'Sector Data Steward',
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    UNIQUE (acceptance_run_id, gate_key),
    CONSTRAINT chk_sector_acceptance_failure_reason CHECK (
        status NOT IN ('failed','blocked') OR failure_reason IS NOT NULL
    )
);

CREATE OR REPLACE FUNCTION sector_intelligence.run_acceptance_gates(
    p_run_key TEXT,
    p_taxonomy_node_id BIGINT,
    p_as_of_date DATE,
    p_started_by TEXT DEFAULT 'Sector Portfolio Manager'
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_run_id BIGINT;
    v_gate_version CONSTANT TEXT := 'sector-acceptance-v1';
    v_node sector_intelligence.taxonomy_nodes%ROWTYPE;
BEGIN
    SELECT * INTO v_node
    FROM sector_intelligence.taxonomy_nodes node
    WHERE node.id=p_taxonomy_node_id
      AND node.country_code='IN'
      AND node.valid_from <= p_as_of_date
      AND (node.valid_to IS NULL OR node.valid_to >= p_as_of_date);

    IF v_node.id IS NULL THEN
        RAISE EXCEPTION 'taxonomy node % is not an active real Indian sector at %', p_taxonomy_node_id, p_as_of_date;
    END IF;
    IF v_node.source_system_id IS NULL OR coalesce(v_node.source_reference,'')='' THEN
        RAISE EXCEPTION 'taxonomy node % lacks source lineage', p_taxonomy_node_id;
    END IF;

    INSERT INTO sector_intelligence.acceptance_runs (
        run_key,taxonomy_node_id,as_of_date,status,gate_version,started_by
    ) VALUES (
        p_run_key,p_taxonomy_node_id,p_as_of_date,'running',v_gate_version,p_started_by
    )
    ON CONFLICT (taxonomy_node_id,as_of_date,gate_version) DO UPDATE SET
        run_key=EXCLUDED.run_key,status='running',started_by=EXCLUDED.started_by,
        summary='{}'::jsonb,started_at=now(),finished_at=NULL
    RETURNING id INTO v_run_id;

    DELETE FROM sector_intelligence.acceptance_gate_results WHERE acceptance_run_id=v_run_id;

    WITH gate_observations AS (
        SELECT * FROM (VALUES
            ('effective_memberships','Effective-Dated Constituents',
             (SELECT count(*)::numeric FROM sector_intelligence.instrument_membership_history membership
              WHERE membership.taxonomy_node_id=p_taxonomy_node_id
                AND membership.valid_from<=p_as_of_date
                AND (membership.valid_to IS NULL OR membership.valid_to>=p_as_of_date)
                AND membership.source_system_id IS NOT NULL
                AND coalesce(membership.source_reference,'')<>''
                AND jsonb_array_length(membership.evidence)>0), 1::numeric,
             jsonb_build_object('taxonomy_node_id',p_taxonomy_node_id,'as_of_date',p_as_of_date)),
            ('two_weighting_methods','Two Point-In-Time Weighting Methods',
             (SELECT count(DISTINCT definition.weighting_method)::numeric
              FROM sector_intelligence.custom_index_definitions definition
              JOIN sector_intelligence.custom_index_rebalances rebalance ON rebalance.index_id=definition.id
              JOIN sector_intelligence.custom_index_history history ON history.index_id=definition.id
              WHERE definition.taxonomy_node_id=p_taxonomy_node_id
                AND rebalance.effective_date<=p_as_of_date AND history.ts::date<=p_as_of_date
                AND definition.weighting_method IN ('equal','market_cap','free_float_market_cap','quality','momentum','custom')
                AND coalesce(rebalance.input_fingerprint,'')<>'' AND coalesce(history.input_fingerprint,'')<>''), 2::numeric,
             jsonb_build_object('required','two distinct weighting methods with retained history')),
            ('reconciled_index_history','Reconciled Index History',
             (SELECT count(*)::numeric FROM sector_intelligence.custom_index_history history
              JOIN sector_intelligence.custom_index_definitions definition ON definition.id=history.index_id
              WHERE definition.taxonomy_node_id=p_taxonomy_node_id AND history.ts::date<=p_as_of_date
                AND history.quality_status IN ('calculated','validated')
                AND coalesce(history.input_fingerprint,'')<>'' AND coalesce(history.calculation_version,'')<>''), 2::numeric,
             jsonb_build_object('requires','multiple point-in-time reproducible index observations')),
            ('fundamental_valuation_breadth','Fundamental And Valuation Breadth',
             ((SELECT count(*) FROM sector_intelligence.sector_aggregates aggregate
               WHERE aggregate.taxonomy_node_id=p_taxonomy_node_id AND aggregate.as_of_date<=p_as_of_date
                 AND aggregate.covered_count>0 AND coalesce(aggregate.input_fingerprint,'')<>'')
              +(SELECT count(*) FROM sector_intelligence.valuation_bands band
                WHERE band.taxonomy_node_id=p_taxonomy_node_id AND band.as_of_date<=p_as_of_date
                  AND band.observation_count>0 AND coalesce(band.input_fingerprint,'')<>''))::numeric, 2::numeric,
             jsonb_build_object('requires','at least one aggregate and one valuation observation')),
            ('relative_strength_breadth','Relative Strength And Breadth',
             ((SELECT count(*) FROM sector_intelligence.relative_strength_observations observation
               WHERE observation.taxonomy_node_id=p_taxonomy_node_id AND observation.as_of_date<=p_as_of_date
                 AND coalesce(observation.input_fingerprint,'')<>'')
              +(SELECT count(*) FROM sector_intelligence.breadth_observations observation
                WHERE observation.taxonomy_node_id=p_taxonomy_node_id AND observation.as_of_date<=p_as_of_date
                  AND coalesce(observation.input_fingerprint,'')<>''))::numeric, 2::numeric,
             jsonb_build_object('requires','source-bounded relative strength and breadth')),
            ('flows_and_ownership','Flows And Ownership Evidence',
             ((SELECT count(*) FROM sector_intelligence.flow_observations observation
               WHERE observation.taxonomy_node_id=p_taxonomy_node_id AND observation.observed_at::date<=p_as_of_date
                 AND observation.source_system_id IS NOT NULL AND jsonb_array_length(observation.evidence)>0)
              +(SELECT count(*) FROM sector_intelligence.ownership_observations observation
                WHERE observation.taxonomy_node_id=p_taxonomy_node_id AND observation.period_end<=p_as_of_date
                  AND observation.source_system_id IS NOT NULL AND jsonb_array_length(observation.evidence)>0))::numeric, 2::numeric,
             jsonb_build_object('requires','at least one flow and one ownership observation')),
            ('sector_dossier','Versioned Sector Research Dossier',
             (SELECT count(*)::numeric FROM sector_intelligence.research_coverage coverage
              WHERE coverage.taxonomy_node_id=p_taxonomy_node_id
                AND coverage.coverage_status IN ('active','monitoring','review_due')
                AND coverage.last_reviewed_at::date<=p_as_of_date
                AND coalesce(coverage.thesis_summary,'')<>''
                AND jsonb_array_length(coverage.evidence_references)>0), 1::numeric,
             jsonb_build_object('requires','reviewed thesis, evidence, gaps, and monitoring indicators')),
            ('committee_dissent','Sector Committee And Dissent',
             (SELECT count(*)::numeric FROM sector_intelligence.sector_committee_packets packet
              WHERE packet.taxonomy_node_id=p_taxonomy_node_id AND packet.as_of_date<=p_as_of_date
                AND packet.status IN ('ready','decided')
                AND jsonb_array_length(packet.independent_positions)>0
                AND coalesce(packet.dissent_summary,'')<>''
                AND packet.human_final_required=true AND packet.capital_action_allowed=false), 1::numeric,
             jsonb_build_object('requires','independent positions, dissent, risk challenge, and human final gate')),
            ('portfolio_fit','Portfolio Fit And Opportunity Cost',
             (SELECT count(*)::numeric FROM sector_intelligence.sector_committee_packets packet
              WHERE packet.taxonomy_node_id=p_taxonomy_node_id AND packet.as_of_date<=p_as_of_date
                AND packet.evidence_snapshot ? 'portfolio_fit'
                AND packet.evidence_snapshot ? 'opportunity_cost'), 1::numeric,
             jsonb_build_object('requires','portfolio_fit and opportunity_cost in committee evidence snapshot')),
            ('tradingview_handoff','Native TradingView Desktop Handoff',
             (SELECT count(DISTINCT artifact.artifact_type)::numeric
              FROM sector_intelligence.generated_chart_artifacts artifact
              WHERE artifact.taxonomy_node_id=p_taxonomy_node_id
                AND artifact.target_workspace='tradingview_desktop'
                AND artifact.generated_at::date<=p_as_of_date
                AND coalesce(artifact.source_state_fingerprint,'')<>''
                AND (artifact.expires_at IS NULL OR artifact.expires_at::date>=p_as_of_date)), 2::numeric,
             jsonb_build_object('requires','at least two native artifact types backed by deterministic state'))
        ) item(gate_key,gate_name,observed_value,threshold_value,evidence)
    )
    INSERT INTO sector_intelligence.acceptance_gate_results (
        acceptance_run_id,gate_key,gate_name,status,observed_value,threshold_value,
        comparator,evidence,failure_reason,checked_by
    )
    SELECT v_run_id,gate_key,gate_name,
           CASE WHEN observed_value>=threshold_value THEN 'passed' ELSE 'blocked' END,
           observed_value,threshold_value,'gte',evidence,
           CASE WHEN observed_value<threshold_value
                THEN gate_name || ' is incomplete: observed ' || observed_value || ', required ' || threshold_value
                ELSE NULL END,
           'Sector Data Steward'
    FROM gate_observations;

    UPDATE sector_intelligence.acceptance_runs run
    SET status=CASE WHEN EXISTS (
            SELECT 1 FROM sector_intelligence.acceptance_gate_results result
            WHERE result.acceptance_run_id=v_run_id AND result.status<>'passed'
        ) THEN 'blocked' ELSE 'passed' END,
        summary=(SELECT jsonb_build_object(
            'gate_count',count(*),'passed_count',count(*) FILTER (WHERE status='passed'),
            'blocked_count',count(*) FILTER (WHERE status='blocked'),
            'broker_write_allowed',false
        ) FROM sector_intelligence.acceptance_gate_results WHERE acceptance_run_id=v_run_id),
        finished_at=now()
    WHERE run.id=v_run_id;

    RETURN v_run_id;
END;
$$;

CREATE OR REPLACE VIEW sector_intelligence.v_acceptance_gate_summary AS
SELECT run.id AS acceptance_run_id,run.run_key,node.taxonomy_key,node.node_name,
       run.as_of_date,run.status,run.gate_version,
       count(result.id) AS gate_count,
       count(result.id) FILTER (WHERE result.status='passed') AS passed_count,
       count(result.id) FILTER (WHERE result.status='failed') AS failed_count,
       count(result.id) FILTER (WHERE result.status='blocked') AS blocked_count,
       jsonb_agg(jsonb_build_object(
           'gate_key',result.gate_key,'gate_name',result.gate_name,'status',result.status,
           'observed_value',result.observed_value,'threshold_value',result.threshold_value,
           'failure_reason',result.failure_reason,'evidence',result.evidence
       ) ORDER BY result.id) FILTER (WHERE result.id IS NOT NULL) AS gates,
       run.started_by,run.started_at,run.finished_at,false AS broker_write_allowed
FROM sector_intelligence.acceptance_runs run
JOIN sector_intelligence.taxonomy_nodes node ON node.id=run.taxonomy_node_id
LEFT JOIN sector_intelligence.acceptance_gate_results result ON result.acceptance_run_id=run.id
GROUP BY run.id,node.taxonomy_key,node.node_name;

COMMENT ON TABLE sector_intelligence.acceptance_runs IS
    'Durable real-sector acceptance snapshots. A passed run proves evidence gates only and never grants capital or broker authority.';

COMMIT;
