BEGIN;

CREATE OR REPLACE FUNCTION trading.run_option_acceptance_gates(
    p_run_key TEXT,
    p_exchange TEXT,
    p_underlying TEXT,
    p_expiry DATE,
    p_window_start TIMESTAMPTZ,
    p_window_end TIMESTAMPTZ,
    p_started_by TEXT DEFAULT 'Options Data Quality Agent'
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_run_id BIGINT;
    v_gate_version CONSTANT TEXT := 'institutional-options-acceptance-v1';
    v_batch_count INTEGER;
    v_contract_count INTEGER;
    v_validated_greeks_ratio NUMERIC;
    v_liquid_contract_ratio NUMERIC;
    v_stale_contract_ratio NUMERIC;
    v_replay_coverage_ratio NUMERIC;
    v_paper_attribution_coverage_ratio NUMERIC;
BEGIN
    IF p_window_start >= p_window_end THEN
        RAISE EXCEPTION 'option acceptance window_start must be before window_end';
    END IF;

    SELECT count(DISTINCT batch.id),count(contract.id),
           count(result.id) FILTER (WHERE result.calculation_status='validated')::numeric
               / nullif(count(contract.id),0),
           count(contract.id) FILTER (WHERE contract.liquidity_status='liquid')::numeric
               / nullif(count(contract.id),0),
           count(contract.id) FILTER (WHERE contract.staleness_status='stale')::numeric
               / nullif(count(contract.id),0)
    INTO v_batch_count,v_contract_count,v_validated_greeks_ratio,
         v_liquid_contract_ratio,v_stale_contract_ratio
    FROM trading.option_chain_snapshot_batches batch
    LEFT JOIN trading.option_chain_contract_snapshots contract ON contract.batch_id=batch.id
    LEFT JOIN LATERAL (
        SELECT calculated.id,calculated.calculation_status
        FROM trading.option_iv_greeks_results calculated
        WHERE calculated.contract_snapshot_id=contract.id
          AND calculated.calculation_status='validated'
        ORDER BY calculated.validated_at DESC,calculated.id DESC LIMIT 1
    ) result ON true
    WHERE batch.exchange=upper(p_exchange)
      AND upper(batch.underlying)=upper(p_underlying)
      AND batch.expiry=p_expiry
      AND batch.minute_ts BETWEEN p_window_start AND p_window_end
      AND batch.quality_status IN ('passed','warning');

    SELECT least(1,coalesce(count(DISTINCT frame.batch_id)::numeric/nullif(v_batch_count,0),0))
    INTO v_replay_coverage_ratio
    FROM trading.option_replay_sessions session
    JOIN trading.option_replay_frames frame ON frame.replay_session_id=session.id
    WHERE session.exchange=upper(p_exchange)
      AND upper(session.underlying)=upper(p_underlying)
      AND session.expiry=p_expiry
      AND session.replay_start<=p_window_start AND session.replay_end>=p_window_end
      AND session.point_in_time_enforced=true;

    SELECT least(1,coalesce(count(DISTINCT attribution.entry_batch_id)::numeric/nullif(v_batch_count,0),0))
    INTO v_paper_attribution_coverage_ratio
    FROM trading.option_paper_trade_attributions attribution
    JOIN trading.option_chain_snapshot_batches batch ON batch.id=attribution.entry_batch_id
    WHERE batch.exchange=upper(p_exchange)
      AND upper(batch.underlying)=upper(p_underlying)
      AND batch.expiry=p_expiry
      AND batch.minute_ts BETWEEN p_window_start AND p_window_end
      AND attribution.paper_only=true
      AND attribution.quality_status IN ('passed','warning');

    INSERT INTO trading.option_acceptance_gate_runs (
        run_key,exchange,underlying,expiry,window_start,window_end,status,
        contracts_expected,contracts_observed,minute_batches_expected,minute_batches_observed,
        validated_greeks_ratio,liquid_contract_ratio,stale_contract_ratio,
        replay_coverage_ratio,paper_attribution_coverage_ratio,gate_version,summary
    ) VALUES (
        p_run_key,upper(p_exchange),upper(p_underlying),p_expiry,p_window_start,p_window_end,'running',
        NULL,v_contract_count,2,v_batch_count,v_validated_greeks_ratio,v_liquid_contract_ratio,
        v_stale_contract_ratio,v_replay_coverage_ratio,v_paper_attribution_coverage_ratio,
        v_gate_version,jsonb_build_object('started_by',p_started_by,'broker_write_allowed',false)
    )
    ON CONFLICT (run_key) DO UPDATE SET
        exchange=EXCLUDED.exchange,underlying=EXCLUDED.underlying,expiry=EXCLUDED.expiry,
        window_start=EXCLUDED.window_start,window_end=EXCLUDED.window_end,status='running',
        contracts_observed=EXCLUDED.contracts_observed,
        minute_batches_expected=EXCLUDED.minute_batches_expected,
        minute_batches_observed=EXCLUDED.minute_batches_observed,
        validated_greeks_ratio=EXCLUDED.validated_greeks_ratio,
        liquid_contract_ratio=EXCLUDED.liquid_contract_ratio,
        stale_contract_ratio=EXCLUDED.stale_contract_ratio,
        replay_coverage_ratio=EXCLUDED.replay_coverage_ratio,
        paper_attribution_coverage_ratio=EXCLUDED.paper_attribution_coverage_ratio,
        gate_version=EXCLUDED.gate_version,summary=EXCLUDED.summary,
        started_at=now(),finished_at=NULL
    RETURNING id INTO v_run_id;

    DELETE FROM trading.option_acceptance_gate_results WHERE acceptance_run_id=v_run_id;

    WITH eligible_batches AS (
        SELECT batch.id
        FROM trading.option_chain_snapshot_batches batch
        WHERE batch.exchange=upper(p_exchange) AND upper(batch.underlying)=upper(p_underlying)
          AND batch.expiry=p_expiry AND batch.minute_ts BETWEEN p_window_start AND p_window_end
          AND batch.quality_status IN ('passed','warning')
    ), gate_observations AS (
        SELECT * FROM (VALUES
            ('multi_minute_capture','Multi-Minute Source Capture',v_batch_count::numeric,2::numeric,'gte',
             jsonb_build_object('window_start',p_window_start,'window_end',p_window_end)),
            ('contract_coverage','Observed Option Contracts',v_contract_count::numeric,1::numeric,'gte',
             jsonb_build_object('quality_batches',v_batch_count)),
            ('validated_iv_greeks','Validated IV And Greeks',coalesce(v_validated_greeks_ratio,0),0.70::numeric,'gte',
             jsonb_build_object('ratio',v_validated_greeks_ratio,'requires','converged source-backed deterministic results')),
            ('liquidity_staleness','Liquidity And Stale Exclusions',
             CASE WHEN coalesce(v_liquid_contract_ratio,0)>=0.25 AND coalesce(v_stale_contract_ratio,1)<=0.25 THEN 1 ELSE 0 END,
             1::numeric,'eq',jsonb_build_object('liquid_ratio',v_liquid_contract_ratio,'stale_ratio',v_stale_contract_ratio)),
            ('straddle_oi_history','Straddle And OI History',
             CASE WHEN (SELECT count(*) FROM trading.option_premium_series series JOIN eligible_batches batch ON batch.id=series.batch_id
                         WHERE series.series_type='atm_straddle' AND series.quality_status IN ('passed','warning'))>=2
                       AND (SELECT count(*) FROM trading.option_oi_heatmap_cells cell JOIN eligible_batches batch ON batch.id=cell.batch_id
                            WHERE cell.quality_status IN ('passed','warning'))>=1
                  THEN 1 ELSE 0 END,1::numeric,'eq',
             jsonb_build_object('requires','at least two straddle points and populated OI analytics')), 
            ('volatility_surface','IV Rank Skew And Term Structure',
             (SELECT count(DISTINCT metric.metric_type)::numeric FROM trading.option_volatility_metrics metric
              JOIN eligible_batches batch ON batch.id=metric.batch_id
              WHERE metric.quality_status IN ('passed','warning')
                AND metric.metric_type IN ('iv_percentile','iv_rank','skew','term_structure')),3::numeric,'gte',
             jsonb_build_object('requires','IV percentile or rank, skew, and term structure')),
            ('exposure_estimates','GEX DEX Vanna Charm And Gamma Flip',
             (SELECT count(DISTINCT estimate.metric_name)::numeric FROM trading.option_exposure_estimates estimate
              JOIN eligible_batches batch ON batch.id=estimate.batch_id
              WHERE estimate.quality_status IN ('passed','warning') AND estimate.metric_value IS NOT NULL
                AND estimate.metric_name IN ('gex','dex','vanna','charm','gamma_flip')),5::numeric,'gte',
             jsonb_build_object('requires','GEX, DEX, vanna, charm, and gamma flip with explicit assumptions')),
            ('point_in_time_replay','Point-In-Time Replay',coalesce(v_replay_coverage_ratio,0),1::numeric,'gte',
             jsonb_build_object('coverage_ratio',v_replay_coverage_ratio,'lookahead_allowed',false)),
            ('specialist_brief','Evidence-Backed Options Specialist Brief',
             (SELECT count(*)::numeric FROM trading.option_specialist_observations observation
              JOIN eligible_batches batch ON batch.id=observation.batch_id
              WHERE observation.observation_status='published'
                AND observation.quality_status IN ('passed','warning')
                AND jsonb_array_length(observation.evidence_refs)>0),1::numeric,'gte',
             jsonb_build_object('human_review_required',true)),
            ('paper_attribution','Paper Trade Attribution',coalesce(v_paper_attribution_coverage_ratio,0),0.01::numeric,'gte',
             jsonb_build_object('coverage_ratio',v_paper_attribution_coverage_ratio,'paper_only',true)),
            ('zero_broker_writes','Zero Broker Writes',0::numeric,0::numeric,'zero',
             jsonb_build_object('database_constraints_enforced',true,'capital_action_allowed',false))
        ) item(gate_key,gate_name,observed_value,threshold_value,comparator,evidence)
    )
    INSERT INTO trading.option_acceptance_gate_results (
        acceptance_run_id,gate_key,gate_name,status,observed_value,threshold_value,
        comparator,evidence,failure_reason,checked_by
    )
    SELECT v_run_id,gate_key,gate_name,
           CASE WHEN comparator='zero' AND observed_value=0 THEN 'passed'
                WHEN comparator='eq' AND observed_value=threshold_value THEN 'passed'
                WHEN comparator='gte' AND observed_value>=threshold_value THEN 'passed'
                ELSE 'blocked' END,
           observed_value,threshold_value,comparator,evidence,
           CASE WHEN (comparator='zero' AND observed_value=0)
                  OR (comparator='eq' AND observed_value=threshold_value)
                  OR (comparator='gte' AND observed_value>=threshold_value) THEN NULL
                ELSE gate_name || ' is incomplete: observed ' || observed_value || ', required ' || comparator || ' ' || threshold_value END,
           'Options Data Quality Agent'
    FROM gate_observations;

    UPDATE trading.option_acceptance_gate_runs run
    SET status=CASE WHEN EXISTS (
            SELECT 1 FROM trading.option_acceptance_gate_results result
            WHERE result.acceptance_run_id=v_run_id AND result.status<>'passed'
        ) THEN 'blocked' ELSE 'passed' END,
        summary=run.summary || (SELECT jsonb_build_object(
            'gate_count',count(*),'passed_count',count(*) FILTER (WHERE status='passed'),
            'blocked_count',count(*) FILTER (WHERE status='blocked'),
            'broker_write_allowed',false
        ) FROM trading.option_acceptance_gate_results WHERE acceptance_run_id=v_run_id),
        finished_at=now()
    WHERE run.id=v_run_id;

    RETURN v_run_id;
END;
$$;

COMMENT ON FUNCTION trading.run_option_acceptance_gates IS
    'Evaluates source-backed institutional options acceptance without creating orders, approvals, market rows, or synthetic evidence.';

COMMIT;
