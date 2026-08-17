BEGIN;

CREATE OR REPLACE FUNCTION sector_intelligence.run_acceptance_gates_v2(
    p_run_key TEXT,
    p_taxonomy_node_id BIGINT,
    p_as_of_date DATE,
    p_started_by TEXT DEFAULT 'Sector Portfolio Manager'
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_baseline_id BIGINT;
    v_run_id BIGINT;
    v_active_count INTEGER;
    v_coverage_threshold INTEGER;
    v_core_covered INTEGER;
    v_valuation_covered INTEGER;
    v_valuation_history INTEGER;
BEGIN
    v_baseline_id := sector_intelligence.run_acceptance_gates(
        p_run_key || '-v1-baseline',
        p_taxonomy_node_id,
        p_as_of_date,
        p_started_by
    );

    INSERT INTO sector_intelligence.acceptance_runs (
        run_key,taxonomy_node_id,as_of_date,status,gate_version,started_by
    ) VALUES (
        p_run_key,p_taxonomy_node_id,p_as_of_date,'running','sector-acceptance-v2',p_started_by
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
    WHERE result.acceptance_run_id=v_baseline_id
      AND result.gate_key<>'fundamental_valuation_breadth';

    SELECT count(*)::int INTO v_active_count
    FROM sector_intelligence.instrument_membership_history membership
    WHERE membership.taxonomy_node_id=p_taxonomy_node_id
      AND membership.valid_from<=p_as_of_date
      AND (membership.valid_to IS NULL OR membership.valid_to>=p_as_of_date);
    v_coverage_threshold := greatest(1,ceil(v_active_count*0.70)::int);

    WITH active_members AS (
        SELECT membership.symbol_id
        FROM sector_intelligence.instrument_membership_history membership
        WHERE membership.taxonomy_node_id=p_taxonomy_node_id
          AND membership.valid_from<=p_as_of_date
          AND (membership.valid_to IS NULL OR membership.valid_to>=p_as_of_date)
    ), latest AS (
        SELECT DISTINCT ON (observation.symbol_id,definition.metric_key)
               observation.symbol_id,definition.metric_key,
               observation.source_system_id,observation.source_reference,
               observation.input_fingerprint
        FROM sector_intelligence.metric_observations observation
        JOIN sector_intelligence.metric_definitions definition
          ON definition.id=observation.metric_definition_id
        JOIN active_members member ON member.symbol_id=observation.symbol_id
        WHERE definition.metric_key IN (
            'reported_revenue','reported_profit_after_tax','reported_basic_eps'
        )
          AND observation.observed_at::date<=p_as_of_date
          AND observation.quality_status IN ('observed','validated')
        ORDER BY observation.symbol_id,definition.metric_key,
                 observation.observed_at DESC,observation.id DESC
    )
    SELECT count(*)::int INTO v_core_covered
    FROM (
        SELECT symbol_id
        FROM latest
        GROUP BY symbol_id
        HAVING count(DISTINCT metric_key)=3
           AND bool_and(source_system_id IS NOT NULL
                        AND coalesce(source_reference,'')<>''
                        AND coalesce(input_fingerprint,'')<>'')
    ) covered;

    SELECT count(DISTINCT observation.symbol_id)::int INTO v_valuation_covered
    FROM sector_intelligence.metric_observations observation
    JOIN sector_intelligence.metric_definitions definition
      ON definition.id=observation.metric_definition_id
    JOIN sector_intelligence.instrument_membership_history membership
      ON membership.symbol_id=observation.symbol_id
     AND membership.taxonomy_node_id=p_taxonomy_node_id
     AND membership.valid_from<=p_as_of_date
     AND (membership.valid_to IS NULL OR membership.valid_to>=p_as_of_date)
    WHERE definition.metric_key='price_to_earnings'
      AND observation.observed_at::date<=p_as_of_date
      AND observation.value_numeric>0
      AND observation.source_system_id IS NOT NULL
      AND coalesce(observation.source_reference,'')<>''
      AND coalesce(observation.input_fingerprint,'')<>''
      AND observation.quality_status IN ('observed','validated');

    SELECT count(*)::int INTO v_valuation_history
    FROM sector_intelligence.valuation_bands band
    JOIN sector_intelligence.metric_definitions definition
      ON definition.id=band.metric_definition_id
    WHERE band.taxonomy_node_id=p_taxonomy_node_id
      AND band.as_of_date<=p_as_of_date
      AND definition.metric_key='price_to_earnings'
      AND band.lookback_years>=10
      AND band.observation_count>=2000
      AND band.minimum_value IS NOT NULL
      AND band.median_value IS NOT NULL
      AND band.maximum_value IS NOT NULL
      AND coalesce(band.input_fingerprint,'')<>'';

    INSERT INTO sector_intelligence.acceptance_gate_results (
        acceptance_run_id,gate_key,gate_name,status,observed_value,
        threshold_value,comparator,evidence,failure_reason,checked_by
    ) VALUES
    (
        v_run_id,'fundamental_constituent_coverage','Source-Backed Fundamental Coverage',
        CASE WHEN v_core_covered>=v_coverage_threshold THEN 'passed' ELSE 'blocked' END,
        v_core_covered,v_coverage_threshold,'gte',
        jsonb_build_object(
            'active_constituents',v_active_count,
            'required_coverage_percent',70,
            'required_metrics',jsonb_build_array('reported_revenue','reported_profit_after_tax','reported_basic_eps'),
            'lineage_required',true
        ),
        CASE WHEN v_core_covered>=v_coverage_threshold THEN NULL
             ELSE format('Only %s of %s constituents have revenue, PAT, EPS, and complete source lineage; %s required',
                         v_core_covered,v_active_count,v_coverage_threshold) END,
        'Sector Fundamental Data Steward'
    ),
    (
        v_run_id,'current_valuation_coverage','Current Point-In-Time Valuation Coverage',
        CASE WHEN v_valuation_covered>=v_coverage_threshold THEN 'passed' ELSE 'blocked' END,
        v_valuation_covered,v_coverage_threshold,'gte',
        jsonb_build_object(
            'active_constituents',v_active_count,
            'required_coverage_percent',70,
            'metric','price_to_earnings',
            'positive_eps_required',true,
            'point_in_time_price_required',true
        ),
        CASE WHEN v_valuation_covered>=v_coverage_threshold THEN NULL
             ELSE format('Only %s of %s constituents have a source-backed current P/E; %s required',
                         v_valuation_covered,v_active_count,v_coverage_threshold) END,
        'Sector Valuation Analyst'
    ),
    (
        v_run_id,'ten_year_valuation_history','Ten-Year Valuation History',
        CASE WHEN v_valuation_history>=1 THEN 'passed' ELSE 'blocked' END,
        v_valuation_history,1,'gte',
        jsonb_build_object(
            'metric','price_to_earnings',
            'minimum_lookback_years',10,
            'minimum_point_in_time_observations',2000,
            'backdating_allowed',false
        ),
        CASE WHEN v_valuation_history>=1 THEN NULL
             ELSE 'No reproducible ten-year P/E band with at least 2,000 point-in-time observations is available' END,
        'Sector Valuation Analyst'
    );

    UPDATE sector_intelligence.acceptance_runs run
    SET status=CASE
            WHEN EXISTS (
                SELECT 1 FROM sector_intelligence.acceptance_gate_results result
                WHERE result.acceptance_run_id=v_run_id
                  AND result.status IN ('failed','blocked')
            ) THEN 'blocked'
            ELSE 'passed'
        END,
        summary=(
            SELECT jsonb_build_object(
                'gate_count',count(*),
                'passed_count',count(*) FILTER (WHERE status='passed'),
                'failed_count',count(*) FILTER (WHERE status='failed'),
                'blocked_count',count(*) FILTER (WHERE status='blocked'),
                'fundamental_coverage',jsonb_build_object(
                    'covered',v_core_covered,
                    'required',v_coverage_threshold,
                    'active_constituents',v_active_count
                ),
                'valuation_coverage',jsonb_build_object(
                    'covered',v_valuation_covered,
                    'required',v_coverage_threshold
                ),
                'broker_write_allowed',false
            )
            FROM sector_intelligence.acceptance_gate_results
            WHERE acceptance_run_id=v_run_id
        ),
        finished_at=now()
    WHERE run.id=v_run_id;
    RETURN v_run_id;
END;
$$;

COMMENT ON FUNCTION sector_intelligence.run_acceptance_gates_v2(TEXT,BIGINT,DATE,TEXT) IS
'Strict sector acceptance: 70 percent source-backed constituent fundamentals and valuation, plus genuine ten-year valuation history. No backdating.';

COMMIT;
