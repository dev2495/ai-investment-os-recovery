BEGIN;

CREATE OR REPLACE FUNCTION sector_intelligence.activate_price_baseline(
    p_taxonomy_node_id BIGINT,
    p_as_of_date DATE,
    p_actor TEXT DEFAULT 'Sector Portfolio Manager'
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_node sector_intelligence.taxonomy_nodes%ROWTYPE;
    v_membership_observed_date DATE;
    v_effective_date DATE;
    v_member_count INTEGER;
    v_covered_count INTEGER;
    v_source_system_id BIGINT;
    v_metric_id BIGINT;
    v_equal_id BIGINT;
    v_momentum_id BIGINT;
    v_equal_key TEXT;
    v_momentum_key TEXT;
    v_fingerprint TEXT;
BEGIN
    SELECT * INTO v_node
    FROM sector_intelligence.taxonomy_nodes node
    WHERE node.id=p_taxonomy_node_id
      AND node.country_code='IN'
      AND node.valid_from<=p_as_of_date
      AND (node.valid_to IS NULL OR node.valid_to>=p_as_of_date);
    IF v_node.id IS NULL THEN
        RAISE EXCEPTION 'taxonomy node % is not active on %', p_taxonomy_node_id, p_as_of_date;
    END IF;
    IF v_node.source_system_id IS NULL OR coalesce(v_node.source_reference,'')='' THEN
        RAISE EXCEPTION 'taxonomy node % lacks source lineage', p_taxonomy_node_id;
    END IF;

    SELECT count(*), max(membership.created_at::date)
      INTO v_member_count, v_membership_observed_date
    FROM sector_intelligence.instrument_membership_history membership
    WHERE membership.taxonomy_node_id=p_taxonomy_node_id
      AND membership.valid_from<=p_as_of_date
      AND (membership.valid_to IS NULL OR membership.valid_to>=p_as_of_date)
      AND membership.source_system_id IS NOT NULL
      AND coalesce(membership.source_reference,'')<>''
      AND jsonb_array_length(membership.evidence)>0;
    IF v_member_count=0 THEN
        RAISE EXCEPTION 'sector has no source-backed active constituents';
    END IF;

    SELECT common.trade_date
      INTO v_effective_date
    FROM (
        SELECT bar.ts::date AS trade_date, count(DISTINCT bar.symbol_id) AS covered
        FROM trading.ohlcv bar
        JOIN sector_intelligence.instrument_membership_history membership
          ON membership.symbol_id=bar.symbol_id
         AND membership.taxonomy_node_id=p_taxonomy_node_id
         AND membership.valid_from<=p_as_of_date
         AND (membership.valid_to IS NULL OR membership.valid_to>=p_as_of_date)
        WHERE bar.timeframe='1d'
          AND bar.ts::date BETWEEN greatest(v_node.valid_from,v_membership_observed_date) AND p_as_of_date
          AND bar.close>0 AND bar.source_system_id IS NOT NULL
        GROUP BY bar.ts::date
        HAVING count(DISTINCT bar.symbol_id)=v_member_count
        ORDER BY bar.ts::date
        LIMIT 1
    ) common;
    IF v_effective_date IS NULL THEN
        RAISE EXCEPTION 'no common post-observation daily close exists for all % constituents', v_member_count;
    END IF;

    WITH active AS (
        SELECT membership.symbol_id
        FROM sector_intelligence.instrument_membership_history membership
        WHERE membership.taxonomy_node_id=p_taxonomy_node_id
          AND membership.valid_from<=p_as_of_date
          AND (membership.valid_to IS NULL OR membership.valid_to>=p_as_of_date)
    ), bounded AS (
        SELECT active.symbol_id, ending.close AS end_close, starting.close AS start_close,
               ending.ts AS end_ts, starting.ts AS start_ts, ending.source_system_id
        FROM active
        JOIN LATERAL (
            SELECT bar.close,bar.ts,bar.source_system_id FROM trading.ohlcv bar
            WHERE bar.symbol_id=active.symbol_id AND bar.timeframe='1d'
              AND bar.ts::date<=v_effective_date AND bar.close>0 AND bar.source_system_id IS NOT NULL
            ORDER BY bar.ts DESC LIMIT 1
        ) ending ON true
        JOIN LATERAL (
            SELECT bar.close,bar.ts FROM trading.ohlcv bar
            WHERE bar.symbol_id=active.symbol_id AND bar.timeframe='1d'
              AND bar.ts::date<=v_effective_date-126 AND bar.close>0 AND bar.source_system_id IS NOT NULL
            ORDER BY bar.ts DESC LIMIT 1
        ) starting ON true
    )
    SELECT count(*), min(source_system_id),
           md5(string_agg(symbol_id||':'||start_ts||':'||start_close||':'||end_ts||':'||end_close,'|' ORDER BY symbol_id))
      INTO v_covered_count,v_source_system_id,v_fingerprint
    FROM bounded;
    IF v_covered_count<>v_member_count THEN
        RAISE EXCEPTION '126-day momentum evidence covers % of % constituents', v_covered_count, v_member_count;
    END IF;

    INSERT INTO sector_intelligence.metric_definitions (
        metric_key,metric_name,metric_family,value_type,unit,frequency,
        aggregation_method,higher_is_better,formula_expression,required_inputs,
        methodology_version,active
    ) VALUES (
        'momentum_score','126-Day Cross-Sectional Momentum Rank','price','numeric','rank','daily',
        'percentile',true,'rank(close_t / close_t_minus_126_calendar_days - 1)',
        '["daily_close","effective_membership"]'::jsonb,'sector-momentum-rank-v1',true
    ) ON CONFLICT (metric_key) DO UPDATE SET
        metric_name=EXCLUDED.metric_name,formula_expression=EXCLUDED.formula_expression,
        required_inputs=EXCLUDED.required_inputs,methodology_version=EXCLUDED.methodology_version,
        active=true,updated_at=now()
    RETURNING id INTO v_metric_id;

    DELETE FROM sector_intelligence.metric_observations observation
    USING sector_intelligence.instrument_membership_history membership
    WHERE observation.metric_definition_id=v_metric_id
      AND observation.symbol_id=membership.symbol_id
      AND membership.taxonomy_node_id=p_taxonomy_node_id
      AND observation.observed_at::date=v_effective_date
      AND observation.calculation_version='sector-momentum-rank-v1';

    WITH active AS (
        SELECT membership.symbol_id
        FROM sector_intelligence.instrument_membership_history membership
        WHERE membership.taxonomy_node_id=p_taxonomy_node_id
          AND membership.valid_from<=p_as_of_date
          AND (membership.valid_to IS NULL OR membership.valid_to>=p_as_of_date)
    ), bounded AS (
        SELECT active.symbol_id, ending.close AS end_close, starting.close AS start_close,
               ending.ts AS end_ts, starting.ts AS start_ts, ending.source_system_id,
               ending.close/starting.close-1 AS momentum_return
        FROM active
        JOIN LATERAL (
            SELECT bar.close,bar.ts,bar.source_system_id FROM trading.ohlcv bar
            WHERE bar.symbol_id=active.symbol_id AND bar.timeframe='1d'
              AND bar.ts::date<=v_effective_date AND bar.close>0 AND bar.source_system_id IS NOT NULL
            ORDER BY bar.ts DESC LIMIT 1
        ) ending ON true
        JOIN LATERAL (
            SELECT bar.close,bar.ts FROM trading.ohlcv bar
            WHERE bar.symbol_id=active.symbol_id AND bar.timeframe='1d'
              AND bar.ts::date<=v_effective_date-126 AND bar.close>0 AND bar.source_system_id IS NOT NULL
            ORDER BY bar.ts DESC LIMIT 1
        ) starting ON true
    ), ranked AS (
        SELECT bounded.*, rank() OVER (ORDER BY momentum_return, symbol_id)::numeric AS momentum_rank
        FROM bounded
    )
    INSERT INTO sector_intelligence.metric_observations (
        metric_definition_id,symbol_id,observed_at,period_start,period_end,value_numeric,
        source_system_id,source_reference,calculation_version,input_fingerprint,
        quality_status,metadata
    )
    SELECT v_metric_id,symbol_id,(v_effective_date::timestamp+time '23:59:00') AT TIME ZONE 'UTC',
           start_ts::date,end_ts::date,momentum_rank,source_system_id,
           'derived://zerodha/126d-momentum-rank/'||v_effective_date,
           'sector-momentum-rank-v1',v_fingerprint,'validated',
           jsonb_build_object('raw_return',momentum_return,'start_close',start_close,
                              'end_close',end_close,'start_ts',start_ts,'end_ts',end_ts,
                              'lookahead_allowed',false,'broker_write_allowed',false)
    FROM ranked;

    v_equal_key := 'sector:'||p_taxonomy_node_id||':equal';
    v_momentum_key := 'sector:'||p_taxonomy_node_id||':momentum-126d';
    INSERT INTO sector_intelligence.custom_index_definitions (
        index_key,index_name,taxonomy_node_id,base_date,base_value,currency,weighting_method,
        selection_rules,weighting_rules,rebalance_frequency,calculation_methodology,
        methodology_version,status,created_by
    ) VALUES (
        v_equal_key,v_node.node_name||' Equal Weight',p_taxonomy_node_id,v_effective_date,1000,'INR','equal',
        jsonb_build_object('membership','effective_official_basket','as_of_date',p_as_of_date),
        jsonb_build_object('method','equal','weight_cap',0.20),'monthly',
        'point_in_time_price_return','sector-price-baseline-v1','validated',p_actor
    ) ON CONFLICT (index_key) DO UPDATE SET
        base_date=EXCLUDED.base_date,selection_rules=EXCLUDED.selection_rules,
        weighting_rules=EXCLUDED.weighting_rules,methodology_version=EXCLUDED.methodology_version,
        status='validated',updated_at=now()
    RETURNING id INTO v_equal_id;

    INSERT INTO sector_intelligence.custom_index_definitions (
        index_key,index_name,taxonomy_node_id,base_date,base_value,currency,weighting_method,
        selection_rules,weighting_rules,rebalance_frequency,calculation_methodology,
        methodology_version,status,created_by
    ) VALUES (
        v_momentum_key,v_node.node_name||' 126D Momentum',p_taxonomy_node_id,v_effective_date,1000,'INR','momentum',
        jsonb_build_object('membership','effective_official_basket','as_of_date',p_as_of_date),
        jsonb_build_object('method','cross_sectional_rank','metric_key','momentum_score','lookback_calendar_days',126,'weight_cap',0.20),
        'monthly','point_in_time_price_return','sector-price-baseline-v1','validated',p_actor
    ) ON CONFLICT (index_key) DO UPDATE SET
        base_date=EXCLUDED.base_date,selection_rules=EXCLUDED.selection_rules,
        weighting_rules=EXCLUDED.weighting_rules,methodology_version=EXCLUDED.methodology_version,
        status='validated',updated_at=now()
    RETURNING id INTO v_momentum_id;

    INSERT INTO sector_intelligence.custom_index_constituents (
        index_id,symbol_id,valid_from,inclusion_reason,source_membership_id
    )
    SELECT definition.id,membership.symbol_id,v_effective_date,
           'Effective official constituent with retained daily price evidence',membership.id
    FROM sector_intelligence.instrument_membership_history membership
    CROSS JOIN (VALUES (v_equal_id),(v_momentum_id)) definition(id)
    WHERE membership.taxonomy_node_id=p_taxonomy_node_id
      AND membership.valid_from<=p_as_of_date
      AND (membership.valid_to IS NULL OR membership.valid_to>=p_as_of_date)
    ON CONFLICT (index_id,symbol_id,valid_from) DO UPDATE SET
        inclusion_reason=EXCLUDED.inclusion_reason,source_membership_id=EXCLUDED.source_membership_id;

    RETURN jsonb_build_object(
        'status','activated','taxonomy_node_id',p_taxonomy_node_id,'taxonomy_key',v_node.taxonomy_key,
        'node_name',v_node.node_name,'as_of_date',p_as_of_date,'effective_date',v_effective_date,
        'member_count',v_member_count,'momentum_covered_count',v_covered_count,
        'momentum_input_fingerprint',v_fingerprint,
        'indices',jsonb_build_array(
            jsonb_build_object('index_id',v_equal_id,'index_key',v_equal_key,'weighting_method','equal'),
            jsonb_build_object('index_id',v_momentum_id,'index_key',v_momentum_key,'weighting_method','momentum')
        ),
        'source_reference',v_node.source_reference,'broker_write_allowed',false,
        'capital_action_allowed',false,'seed_or_fabricated_data',false
    );
END;
$$;

COMMENT ON FUNCTION sector_intelligence.activate_price_baseline(BIGINT,DATE,TEXT) IS
    'Creates source-bounded equal and momentum sector indices from effective memberships and retained Zerodha daily closes. Never grants execution authority.';

COMMIT;
