CREATE OR REPLACE FUNCTION strategy.slug_key(p_value TEXT)
RETURNS TEXT
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT trim(both '-' FROM regexp_replace(lower(coalesce(p_value, 'strategy')), '[^a-z0-9]+', '-', 'g'))
$$;

CREATE OR REPLACE FUNCTION strategy.create_strategy_arsenal_intake(
    p_created_by TEXT,
    p_intake_text TEXT,
    p_strategy_name TEXT DEFAULT NULL,
    p_strategy_family TEXT DEFAULT 'quant',
    p_asset_class TEXT DEFAULT 'equity',
    p_symbols TEXT[] DEFAULT ARRAY[]::TEXT[],
    p_universe TEXT DEFAULT NULL,
    p_timeframe TEXT DEFAULT 'mixed',
    p_intent_tags TEXT[] DEFAULT ARRAY[]::TEXT[],
    p_constraints_text TEXT DEFAULT NULL,
    p_risk_notes TEXT DEFAULT NULL,
    p_requested_outputs TEXT[] DEFAULT ARRAY['structured_spec','candidate','backtest_queue','validation_review']::TEXT[],
    p_source_kind TEXT DEFAULT 'charlie_command',
    p_source_ref TEXT DEFAULT 'ai_office_strategy_intake'
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_intake_id BIGINT;
    v_idea_id BIGINT;
    v_candidate_id BIGINT;
    v_task_id BIGINT;
    v_inbox_id BIGINT;
    v_now_key TEXT := to_char(clock_timestamp(), 'YYYYMMDDHH24MISSMS');
    v_clean_name TEXT := nullif(trim(coalesce(p_strategy_name, '')), '');
    v_strategy_name TEXT := coalesce(v_clean_name, 'Strategy idea ' || v_now_key);
    v_intake_key TEXT := 'strategy-intake-' || v_now_key || '-' || left(strategy.slug_key(coalesce(v_clean_name, p_strategy_family, 'idea')), 40);
    v_idea_key TEXT := 'strategy-idea-' || v_now_key || '-' || left(strategy.slug_key(coalesce(v_clean_name, p_strategy_family, 'idea')), 40);
    v_candidate_key TEXT := 'strategy-candidate-' || v_now_key || '-' || left(strategy.slug_key(coalesce(v_clean_name, p_strategy_family, 'idea')), 40);
BEGIN
    IF nullif(trim(coalesce(p_intake_text, '')), '') IS NULL THEN
        RAISE EXCEPTION 'intake_text is required';
    END IF;

    INSERT INTO strategy.strategy_intakes (
        intake_key,
        created_by,
        intake_text,
        strategy_name,
        strategy_family,
        asset_class,
        symbols,
        universe,
        timeframe,
        intent_tags,
        constraints_text,
        risk_notes,
        requested_outputs,
        source_kind,
        source_ref,
        status,
        owner_agent,
        assigned_agents,
        structured_spec,
        evidence
    )
    VALUES (
        v_intake_key,
        coalesce(nullif(trim(p_created_by), ''), 'Devarsh'),
        trim(p_intake_text),
        v_strategy_name,
        coalesce(nullif(trim(p_strategy_family), ''), 'quant'),
        coalesce(nullif(trim(p_asset_class), ''), 'equity'),
        coalesce(p_symbols, ARRAY[]::TEXT[]),
        nullif(trim(coalesce(p_universe, '')), ''),
        coalesce(nullif(trim(p_timeframe), ''), 'mixed'),
        coalesce(p_intent_tags, ARRAY[]::TEXT[]),
        nullif(trim(coalesce(p_constraints_text, '')), ''),
        nullif(trim(coalesce(p_risk_notes, '')), ''),
        coalesce(p_requested_outputs, ARRAY['structured_spec','candidate','backtest_queue','validation_review']::TEXT[]),
        coalesce(nullif(trim(p_source_kind), ''), 'charlie_command'),
        coalesce(nullif(trim(p_source_ref), ''), 'ai_office_strategy_intake'),
        'queued',
        'Strategy Intake Agent',
        ARRAY['Strategy Intake Agent','Strategy Generator','Backtest Engineer','Optimizer Agent','Model Validation Agent']::TEXT[],
        jsonb_build_object(
            'raw_intake', trim(p_intake_text),
            'strategy_name', v_strategy_name,
            'strategy_family', coalesce(nullif(trim(p_strategy_family), ''), 'quant'),
            'asset_class', coalesce(nullif(trim(p_asset_class), ''), 'equity'),
            'symbols', coalesce(p_symbols, ARRAY[]::TEXT[]),
            'universe', nullif(trim(coalesce(p_universe, '')), ''),
            'timeframe', coalesce(nullif(trim(p_timeframe), ''), 'mixed'),
            'paper_first', true,
            'live_execution_allowed', false,
            'required_gates', ARRAY['data_lineage','baseline_backtest','transaction_costs','walk_forward_or_oos','model_validation','human_approval']::TEXT[]
        ),
        jsonb_build_array(
            jsonb_build_object('source', coalesce(nullif(trim(p_source_kind), ''), 'charlie_command'), 'source_ref', coalesce(nullif(trim(p_source_ref), ''), 'ai_office_strategy_intake'))
        )
    )
    RETURNING id INTO v_intake_id;

    INSERT INTO strategy.generated_ideas (
        idea_key,
        intake_id,
        title,
        idea_type,
        symbols,
        universe,
        timeframe,
        thesis,
        edge_hypothesis,
        entry_rules,
        exit_rules,
        risk_rules,
        data_requirements,
        assumptions,
        invalidation_tests,
        priority_score,
        risk_score,
        status,
        owner_agent,
        evidence
    )
    VALUES (
        v_idea_key,
        v_intake_id,
        v_strategy_name,
        'strategy_hypothesis',
        coalesce(p_symbols, ARRAY[]::TEXT[]),
        nullif(trim(coalesce(p_universe, '')), ''),
        coalesce(nullif(trim(p_timeframe), ''), 'mixed'),
        trim(p_intake_text),
        'Hypothesis must be proven against historical data before any alert or execution path is enabled.',
        jsonb_build_object('source', 'user_intake', 'draft_required', true, 'rules_text', trim(p_intake_text)),
        jsonb_build_object('source', 'user_intake', 'needs_explicit_exits', true),
        jsonb_build_object('max_loss_required', true, 'position_sizing_required', true, 'paper_first', true),
        ARRAY['daily_ohlcv_or_intraday_bars','corporate_actions','transaction_costs','slippage_model','survivorship_bias_check']::TEXT[],
        ARRAY['User intent is a research request, not validated alpha.','No live execution until backtest, validation, and approval gates pass.']::TEXT[],
        ARRAY['Fails after transaction costs','Fails out-of-sample or walk-forward','Performance concentrated in too few trades','Signal depends on unavailable future data','Drawdown exceeds mandate']::TEXT[],
        50,
        50,
        'candidate',
        'Strategy Generator',
        jsonb_build_array(jsonb_build_object('table', 'strategy.strategy_intakes', 'id', v_intake_id))
    )
    RETURNING id INTO v_idea_id;

    INSERT INTO strategy.strategy_candidates (
        name,
        source_kind,
        source_ref,
        hypothesis,
        universe,
        timeframe,
        entry_rules,
        exit_rules,
        risk_rules,
        status,
        owner_agent,
        intake_id,
        generated_idea_id,
        candidate_key,
        structured_spec,
        validation_status,
        activation_gate
    )
    VALUES (
        v_strategy_name,
        'strategy_intake',
        v_intake_key,
        trim(p_intake_text),
        nullif(trim(coalesce(p_universe, '')), ''),
        coalesce(nullif(trim(p_timeframe), ''), 'mixed'),
        jsonb_build_object('draft_rules', trim(p_intake_text), 'needs_parser_review', true),
        jsonb_build_object('needs_stop_or_exit', true, 'needs_time_exit', true),
        jsonb_build_object('paper_first', true, 'max_loss_required', true, 'human_approval_required', true),
        'research',
        'Backtest Engineer',
        v_intake_id,
        v_idea_id,
        v_candidate_key,
        jsonb_build_object(
            'intake_id', v_intake_id,
            'idea_id', v_idea_id,
            'strategy_name', v_strategy_name,
            'symbols', coalesce(p_symbols, ARRAY[]::TEXT[]),
            'requested_outputs', coalesce(p_requested_outputs, ARRAY['structured_spec','candidate','backtest_queue','validation_review']::TEXT[]),
            'activation_sequence', ARRAY['structure_rules','baseline_backtest','optimizer_if_promising','validation_review','paper_alerts','human_approval']::TEXT[]
        ),
        'not_started',
        'paper_first_backtest_required'
    )
    RETURNING id INTO v_candidate_id;

    INSERT INTO agent.tasks (
        title,
        objective,
        owner_agent,
        status,
        priority,
        approval_required,
        source_kind,
        source_ref,
        output_format,
        output_note_path,
        evidence
    )
    VALUES (
        'Structure and backtest strategy candidate: ' || v_strategy_name,
        'Convert the intake into explicit rules, check data availability, run a baseline backtest with costs, and send the result to validation. Do not enable live execution.',
        'Backtest Engineer',
        'queued',
        'high',
        false,
        'strategy.strategy_candidates',
        v_candidate_id::TEXT,
        'markdown+json',
        'ai memory/03 Strategies/Backtests/' || v_candidate_key || '.md',
        jsonb_build_array(
            jsonb_build_object('table', 'strategy.strategy_intakes', 'id', v_intake_id),
            jsonb_build_object('table', 'strategy.generated_ideas', 'id', v_idea_id),
            jsonb_build_object('table', 'strategy.strategy_candidates', 'id', v_candidate_id)
        )
    )
    RETURNING id INTO v_task_id;

    INSERT INTO agent.inbox_items (
        task_id,
        title,
        owner_agent,
        status,
        priority,
        recommended_action,
        evidence,
        target_workspace
    )
    VALUES (
        v_task_id,
        'Strategy candidate queued: ' || v_strategy_name,
        'Backtest Engineer',
        'queued',
        'high',
        'Define exact entry/exit/risk rules, verify data lineage, and run baseline backtest before paper alerts.',
        jsonb_build_array(
            jsonb_build_object('table', 'strategy.strategy_intakes', 'id', v_intake_id),
            jsonb_build_object('table', 'strategy.strategy_candidates', 'id', v_candidate_id),
            jsonb_build_object('task_id', v_task_id)
        ),
        'quant'
    )
    RETURNING id INTO v_inbox_id;

    UPDATE strategy.strategy_intakes
    SET status = 'candidate_queued',
        updated_at = now()
    WHERE id = v_intake_id;

    RETURN jsonb_build_object(
        'intake_id', v_intake_id,
        'intake_key', v_intake_key,
        'idea_id', v_idea_id,
        'idea_key', v_idea_key,
        'candidate_id', v_candidate_id,
        'candidate_key', v_candidate_key,
        'task_id', v_task_id,
        'inbox_id', v_inbox_id,
        'activation_gate', 'paper_first_backtest_required',
        'live_execution_allowed', false
    );
END;
$$;

CREATE OR REPLACE VIEW strategy.v_strategy_arsenal_queue AS
SELECT
    sc.id AS candidate_id,
    coalesce(sc.candidate_key, 'candidate_' || sc.id::TEXT) AS candidate_key,
    sc.name AS strategy_name,
    sc.status AS candidate_status,
    sc.validation_status,
    sc.activation_gate,
    sc.owner_agent,
    sc.universe,
    sc.timeframe,
    si.id AS intake_id,
    si.intake_key,
    si.created_by,
    si.strategy_family,
    si.asset_class,
    si.symbols,
    gi.id AS idea_id,
    gi.idea_key,
    gi.edge_hypothesis,
    count(DISTINCT br.id) AS backtest_runs,
    count(DISTINCT opt.id) AS optimization_runs,
    count(DISTINCT vr.id) AS validation_reviews,
    count(DISTINCT t.id) FILTER (WHERE t.status IN ('queued','running','needs_review')) AS open_tasks,
    max(t.updated_at) AS latest_task_at,
    sc.created_at,
    sc.updated_at
FROM strategy.strategy_candidates sc
LEFT JOIN strategy.strategy_intakes si ON si.id = sc.intake_id
LEFT JOIN strategy.generated_ideas gi ON gi.id = sc.generated_idea_id
LEFT JOIN strategy.backtest_runs br ON br.strategy_id = sc.id
LEFT JOIN strategy.optimization_runs opt ON opt.strategy_id = sc.id
LEFT JOIN strategy.validation_reviews vr ON vr.strategy_id = sc.id
LEFT JOIN agent.tasks t ON t.source_kind = 'strategy.strategy_candidates' AND t.source_ref = sc.id::TEXT
GROUP BY sc.id, si.id, gi.id
ORDER BY sc.created_at DESC;

CREATE OR REPLACE VIEW strategy.v_strategy_arsenal_summary AS
SELECT 'strategy_intakes' AS metric, count(*)::TEXT AS value, 'User and Charlie strategy instructions captured for structuring.' AS interpretation
FROM strategy.strategy_intakes
UNION ALL
SELECT 'generated_ideas', count(*)::TEXT, 'Generated or structured hypotheses awaiting proof.'
FROM strategy.generated_ideas
UNION ALL
SELECT 'strategy_candidates', count(*)::TEXT, 'Strategy candidates in research, backtest, paper, or production gates.'
FROM strategy.strategy_candidates
UNION ALL
SELECT 'candidates_without_backtest', count(*)::TEXT, 'Candidates that still need a baseline backtest.'
FROM strategy.strategy_candidates sc
WHERE NOT EXISTS (SELECT 1 FROM strategy.backtest_runs br WHERE br.strategy_id = sc.id)
UNION ALL
SELECT 'candidates_without_validation', count(*)::TEXT, 'Candidates that still need Model Validation review.'
FROM strategy.strategy_candidates sc
WHERE NOT EXISTS (SELECT 1 FROM strategy.validation_reviews vr WHERE vr.strategy_id = sc.id)
UNION ALL
SELECT 'live_execution_blocked', count(*)::TEXT, 'Candidates explicitly blocked from live execution by activation gates.'
FROM strategy.strategy_candidates
WHERE coalesce(activation_gate, '') <> 'live_approved';
