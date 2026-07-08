CREATE OR REPLACE VIEW agent.v_output_artifact_registry_v2 AS
WITH registry AS (
    SELECT
        'worker_run:' || run.id::TEXT AS artifact_key,
        'worker_output'::TEXT AS artifact_family,
        coalesce(nullif(run.skill_family, ''), 'agent_worker')::TEXT AS artifact_type,
        coalesce(nullif(run.task_title, ''), nullif(run.skill_name, ''), 'Worker output')::TEXT AS title,
        run.output_summary AS summary,
        run.agent_name AS owner_agent,
        run.display_title AS owner_title,
        run.department,
        run.skill_key,
        run.skill_name,
        run.task_id,
        NULL::BIGINT AS approval_id,
        run.widget_id,
        run.widget_key,
        NULL::TEXT AS symbol,
        NULL::TEXT AS company_name,
        NULL::TEXT AS strategy_name,
        run.output_note_path AS note_path,
        NULL::TEXT AS local_path,
        NULL::TEXT AS source_url,
        NULL::TEXT AS content_hash,
        NULL::TEXT AS sensitivity,
        run.status AS status,
        jsonb_build_object(
            'source_view', 'agent.v_recent_worker_runs',
            'run_id', run.id,
            'task_id', run.task_id,
            'widget_key', run.widget_key,
            'run_mode', run.run_mode,
            'evidence', run.evidence
        ) AS evidence,
        false AS capital_action_allowed,
        false AS live_execution_allowed,
        run.created_at,
        run.updated_at,
        coalesce(run.finished_at, run.updated_at, run.created_at) AS latest_activity_at
    FROM agent.v_recent_worker_runs run
    WHERE nullif(run.output_note_path, '') IS NOT NULL

    UNION ALL

    SELECT
        'strategy_committee_memo:' || review.id::TEXT AS artifact_key,
        'committee_memo'::TEXT AS artifact_family,
        'strategy_committee_memo'::TEXT AS artifact_type,
        coalesce(review.strategy_name, 'Strategy committee memo') AS title,
        concat_ws(' · ', review.recommended_decision, review.proposed_mode, review.risk_level) AS summary,
        coalesce(review.decided_by, review.created_by, 'Strategy Review Committee') AS owner_agent,
        'Strategy Review Committee'::TEXT AS owner_title,
        'quant'::TEXT AS department,
        NULL::TEXT AS skill_key,
        NULL::TEXT AS skill_name,
        NULL::BIGINT AS task_id,
        review.approval_id,
        NULL::BIGINT AS widget_id,
        NULL::TEXT AS widget_key,
        NULL::TEXT AS symbol,
        NULL::TEXT AS company_name,
        review.strategy_name,
        review.memo_note_path AS note_path,
        NULL::TEXT AS local_path,
        NULL::TEXT AS source_url,
        NULL::TEXT AS content_hash,
        NULL::TEXT AS sensitivity,
        review.memo_status AS status,
        jsonb_build_object(
            'source_view', 'strategy.v_strategy_committee_queue',
            'review_id', review.id,
            'strategy_id', review.strategy_id,
            'backtest_run_id', review.backtest_run_id,
            'optimization_run_id', review.optimization_run_id,
            'validation_review_id', review.validation_review_id,
            'decision_status', review.decision_status,
            'paper_monitor_allowed', review.paper_monitor_allowed,
            'live_execution_allowed', review.live_execution_allowed,
            'risk_summary', review.risk_summary
        ) AS evidence,
        false AS capital_action_allowed,
        coalesce(review.live_execution_allowed, false) AS live_execution_allowed,
        review.created_at,
        review.updated_at,
        coalesce(review.memo_generated_at, review.updated_at, review.created_at) AS latest_activity_at
    FROM strategy.v_strategy_committee_queue review
    WHERE nullif(review.memo_note_path, '') IS NOT NULL

    UNION ALL

    SELECT
        'long_term_committee_memo:' || review.id::TEXT AS artifact_key,
        'committee_memo'::TEXT AS artifact_family,
        'long_term_committee_memo'::TEXT AS artifact_type,
        coalesce(review.thesis_title, review.company_name, review.symbol, 'Long-term committee memo') AS title,
        concat_ws(' · ', review.recommended_decision, review.review_status, review.decision_status) AS summary,
        coalesce(review.decided_by, review.created_by, 'Long-Term Investment Committee') AS owner_agent,
        'Long-Term Investment Committee'::TEXT AS owner_title,
        'portfolio'::TEXT AS department,
        NULL::TEXT AS skill_key,
        NULL::TEXT AS skill_name,
        review.task_id,
        review.approval_id,
        NULL::BIGINT AS widget_id,
        NULL::TEXT AS widget_key,
        review.symbol,
        review.company_name,
        NULL::TEXT AS strategy_name,
        review.memo_note_path AS note_path,
        NULL::TEXT AS local_path,
        NULL::TEXT AS source_url,
        NULL::TEXT AS content_hash,
        NULL::TEXT AS sensitivity,
        review.memo_status AS status,
        jsonb_build_object(
            'source_view', 'portfolio.v_long_term_committee_queue',
            'review_id', review.id,
            'holding_thesis_id', review.holding_thesis_id,
            'client_count', review.client_count,
            'clients', review.clients,
            'source_gaps', review.source_gaps,
            'required_followups', review.required_followups,
            'proposed_action', review.proposed_action,
            'capital_action_allowed', review.capital_action_allowed,
            'live_execution_allowed', review.live_execution_allowed
        ) AS evidence,
        coalesce(review.capital_action_allowed, false) AS capital_action_allowed,
        coalesce(review.live_execution_allowed, false) AS live_execution_allowed,
        review.created_at,
        review.updated_at,
        coalesce(review.decided_at, review.updated_at, review.created_at) AS latest_activity_at
    FROM portfolio.v_long_term_committee_queue review
    WHERE nullif(review.memo_note_path, '') IS NOT NULL

    UNION ALL

    SELECT
        'long_term_specialist_output:' || output.id::TEXT AS artifact_key,
        'specialist_output'::TEXT AS artifact_family,
        coalesce(nullif(output.module_key, ''), 'long_term_specialist_output')::TEXT AS artifact_type,
        concat_ws(' · ', output.symbol, output.module_name) AS title,
        concat_ws(' · ', output.output_status, output.source_status, output.confidence) AS summary,
        output.agent_name AS owner_agent,
        output.display_title AS owner_title,
        output.department,
        output.skill_key,
        output.skill_name,
        output.task_id,
        NULL::BIGINT AS approval_id,
        NULL::BIGINT AS widget_id,
        NULL::TEXT AS widget_key,
        output.symbol,
        output.company_name,
        NULL::TEXT AS strategy_name,
        coalesce(nullif(output.note_path, ''), nullif(output.task_output_note_path, '')) AS note_path,
        NULL::TEXT AS local_path,
        NULL::TEXT AS source_url,
        NULL::TEXT AS content_hash,
        NULL::TEXT AS sensitivity,
        output.output_status AS status,
        jsonb_build_object(
            'source_view', 'portfolio.v_long_term_specialist_outputs',
            'output_id', output.id,
            'assignment_id', output.assignment_id,
            'committee_review_id', output.committee_review_id,
            'findings', output.findings,
            'source_gaps', output.source_gaps,
            'recommendations', output.recommendations,
            'metrics', output.metrics,
            'evidence', output.evidence
        ) AS evidence,
        false AS capital_action_allowed,
        false AS live_execution_allowed,
        output.created_at,
        output.updated_at,
        coalesce(output.updated_at, output.created_at) AS latest_activity_at
    FROM portfolio.v_long_term_specialist_outputs output
    WHERE nullif(coalesce(output.note_path, output.task_output_note_path), '') IS NOT NULL

    UNION ALL

    SELECT
        'long_term_research_update:' || update_row.id::TEXT AS artifact_key,
        'research_note'::TEXT AS artifact_family,
        coalesce(nullif(update_row.update_kind, ''), 'long_term_research_update')::TEXT AS artifact_type,
        concat_ws(' · ', update_row.symbol, update_row.update_kind, update_row.checklist_key, update_row.model_key) AS title,
        concat_ws(' · ', update_row.status, 'score ' || update_row.score::TEXT, 'expected CAGR ' || update_row.expected_cagr_pct::TEXT) AS summary,
        coalesce(update_row.created_by, 'Research Analyst') AS owner_agent,
        'Long-Term Research'::TEXT AS owner_title,
        'research'::TEXT AS department,
        NULL::TEXT AS skill_key,
        NULL::TEXT AS skill_name,
        NULL::BIGINT AS task_id,
        NULL::BIGINT AS approval_id,
        NULL::BIGINT AS widget_id,
        NULL::TEXT AS widget_key,
        update_row.symbol,
        update_row.company_name,
        NULL::TEXT AS strategy_name,
        update_row.note_path,
        NULL::TEXT AS local_path,
        NULL::TEXT AS source_url,
        NULL::TEXT AS content_hash,
        NULL::TEXT AS sensitivity,
        update_row.status,
        jsonb_build_object(
            'source_view', 'portfolio.v_long_term_research_updates',
            'research_update_id', update_row.id,
            'holding_thesis_id', update_row.holding_thesis_id,
            'findings', update_row.findings,
            'assumptions', update_row.assumptions,
            'outputs', update_row.outputs,
            'source_summary', update_row.source_summary,
            'evidence', update_row.evidence
        ) AS evidence,
        false AS capital_action_allowed,
        false AS live_execution_allowed,
        update_row.created_at,
        update_row.created_at AS updated_at,
        update_row.created_at AS latest_activity_at
    FROM portfolio.v_long_term_research_updates update_row
    WHERE nullif(update_row.note_path, '') IS NOT NULL

    UNION ALL

    SELECT
        'long_term_monte_carlo:' || run.id::TEXT AS artifact_key,
        'risk_model'::TEXT AS artifact_family,
        'long_term_monte_carlo'::TEXT AS artifact_type,
        concat_ws(' · ', run.symbol, 'Monte Carlo', run.horizon_years::TEXT || 'Y') AS title,
        concat_ws(' · ', run.run_status, run.simulation_count::TEXT || ' simulations') AS summary,
        coalesce(run.created_by, 'Valuation Agent') AS owner_agent,
        'Valuation Agent'::TEXT AS owner_title,
        'research'::TEXT AS department,
        NULL::TEXT AS skill_key,
        NULL::TEXT AS skill_name,
        NULL::BIGINT AS task_id,
        NULL::BIGINT AS approval_id,
        NULL::BIGINT AS widget_id,
        NULL::TEXT AS widget_key,
        run.symbol,
        run.company_name,
        NULL::TEXT AS strategy_name,
        run.note_path,
        NULL::TEXT AS local_path,
        NULL::TEXT AS source_url,
        NULL::TEXT AS content_hash,
        NULL::TEXT AS sensitivity,
        run.run_status AS status,
        jsonb_build_object(
            'source_view', 'portfolio.v_long_term_monte_carlo_runs',
            'run_id', run.id,
            'holding_thesis_id', run.holding_thesis_id,
            'valuation_model_id', run.valuation_model_id,
            'probability_summary', run.probability_summary,
            'percentile_summary', run.percentile_summary,
            'warnings', run.warnings,
            'evidence', run.evidence
        ) AS evidence,
        false AS capital_action_allowed,
        false AS live_execution_allowed,
        run.created_at,
        run.created_at AS updated_at,
        run.created_at AS latest_activity_at
    FROM portfolio.v_long_term_monte_carlo_runs run
    WHERE nullif(run.note_path, '') IS NOT NULL

    UNION ALL

    SELECT
        'special_situation_memo:' || memo.id::TEXT AS artifact_key,
        'special_situation_memo'::TEXT AS artifact_family,
        coalesce(nullif(memo.event_type, ''), 'special_situation')::TEXT AS artifact_type,
        coalesce(memo.memo_title, memo.company_name, memo.symbol, 'Special situation memo') AS title,
        memo.summary,
        coalesce(memo.created_by, memo.task_owner_agent, 'Special Situations Analyst') AS owner_agent,
        'Special Situations Analyst'::TEXT AS owner_title,
        'research'::TEXT AS department,
        NULL::TEXT AS skill_key,
        NULL::TEXT AS skill_name,
        memo.task_id,
        memo.approval_id,
        NULL::BIGINT AS widget_id,
        NULL::TEXT AS widget_key,
        memo.symbol,
        memo.company_name,
        NULL::TEXT AS strategy_name,
        memo.note_path,
        NULL::TEXT AS local_path,
        memo.source_url,
        NULL::TEXT AS content_hash,
        NULL::TEXT AS sensitivity,
        memo.memo_status AS status,
        jsonb_build_object(
            'source_view', 'research.v_special_situation_memos',
            'memo_id', memo.id,
            'filing_id', memo.filing_id,
            'filing_event_id', memo.filing_event_id,
            'extracted_terms', memo.extracted_terms,
            'risk_flags', memo.risk_flags,
            'required_followups', memo.required_followups,
            'latest_spread_status', memo.latest_spread_status,
            'latest_decision', memo.latest_decision
        ) AS evidence,
        false AS capital_action_allowed,
        false AS live_execution_allowed,
        memo.created_at,
        memo.updated_at,
        coalesce(memo.updated_at, memo.created_at) AS latest_activity_at
    FROM research.v_special_situation_memos memo
    WHERE nullif(memo.note_path, '') IS NOT NULL

    UNION ALL

    SELECT
        'ai_output_inventory:' || artifact.artifact_id::TEXT AS artifact_key,
        'indexed_ai_output'::TEXT AS artifact_family,
        coalesce(nullif(artifact.artifact_family, ''), artifact.artifact_type, 'ai_output')::TEXT AS artifact_type,
        coalesce(artifact.title, artifact.local_path, artifact.source_url, 'Indexed AI output') AS title,
        artifact.summary,
        'Knowledge Librarian'::TEXT AS owner_agent,
        'Knowledge Librarian'::TEXT AS owner_title,
        'knowledge'::TEXT AS department,
        NULL::TEXT AS skill_key,
        NULL::TEXT AS skill_name,
        NULL::BIGINT AS task_id,
        NULL::BIGINT AS approval_id,
        NULL::BIGINT AS widget_id,
        NULL::TEXT AS widget_key,
        NULL::TEXT AS symbol,
        artifact.company_or_topic AS company_name,
        NULL::TEXT AS strategy_name,
        NULL::TEXT AS note_path,
        artifact.local_path,
        artifact.source_url,
        artifact.content_hash,
        artifact.sensitivity,
        'indexed'::TEXT AS status,
        jsonb_build_object(
            'source_view', 'research.v_ai_output_inventory',
            'artifact_id', artifact.artifact_id,
            'source_system', artifact.source_system,
            'root_label', artifact.root_label,
            'mime_type', artifact.mime_type,
            'size_bytes', artifact.size_bytes,
            'source_last_modified_at', artifact.source_last_modified_at
        ) AS evidence,
        false AS capital_action_allowed,
        false AS live_execution_allowed,
        artifact.captured_at AS created_at,
        artifact.captured_at AS updated_at,
        artifact.captured_at AS latest_activity_at
    FROM research.v_ai_output_inventory artifact
    WHERE nullif(coalesce(artifact.local_path, artifact.source_url), '') IS NOT NULL
)
SELECT
    artifact_key,
    artifact_family,
    artifact_type,
    title,
    summary,
    owner_agent,
    owner_title,
    department,
    skill_key,
    skill_name,
    task_id,
    approval_id,
    widget_id,
    widget_key,
    symbol,
    company_name,
    strategy_name,
    note_path,
    local_path,
    source_url,
    content_hash,
    sensitivity,
    status,
    evidence,
    capital_action_allowed,
    live_execution_allowed,
    created_at,
    updated_at,
    latest_activity_at,
    coalesce(nullif(note_path, ''), nullif(local_path, ''), nullif(source_url, '')) AS artifact_location
FROM registry;

CREATE OR REPLACE VIEW agent.v_output_artifact_summary AS
SELECT
    artifact_family AS metric,
    count(*)::TEXT AS value,
    min(created_at) AS first_seen_at,
    max(latest_activity_at) AS latest_seen_at,
    count(*) FILTER (WHERE nullif(note_path, '') IS NOT NULL)::BIGINT AS obsidian_note_rows,
    count(*) FILTER (WHERE nullif(local_path, '') IS NOT NULL)::BIGINT AS local_file_rows,
    count(*) FILTER (WHERE nullif(source_url, '') IS NOT NULL)::BIGINT AS source_url_rows,
    'Generated output artifacts currently visible to the AI office registry.'::TEXT AS interpretation
FROM agent.v_output_artifact_registry_v2
GROUP BY artifact_family
UNION ALL
SELECT
    'total_artifacts' AS metric,
    count(*)::TEXT AS value,
    min(created_at) AS first_seen_at,
    max(latest_activity_at) AS latest_seen_at,
    count(*) FILTER (WHERE nullif(note_path, '') IS NOT NULL)::BIGINT AS obsidian_note_rows,
    count(*) FILTER (WHERE nullif(local_path, '') IS NOT NULL)::BIGINT AS local_file_rows,
    count(*) FILTER (WHERE nullif(source_url, '') IS NOT NULL)::BIGINT AS source_url_rows,
    'All generated reports, memos, worker outputs, models, and indexed AI-output files in one registry.'::TEXT AS interpretation
FROM agent.v_output_artifact_registry_v2;

CREATE OR REPLACE VIEW agent.v_output_artifact_gaps AS
SELECT
    'worker_run_missing_note'::TEXT AS gap_type,
    'agent.v_recent_worker_runs'::TEXT AS source_view,
    run.id::TEXT AS source_id,
    coalesce(run.task_title, run.skill_name, 'Worker run') AS title,
    run.agent_name AS owner_agent,
    run.status,
    run.created_at,
    run.updated_at,
    'Completed or recent worker run has no output_note_path for Obsidian traceability.'::TEXT AS gap_reason
FROM agent.v_recent_worker_runs run
WHERE run.status IN ('completed', 'done', 'success')
  AND nullif(run.output_note_path, '') IS NULL

UNION ALL

SELECT
    'long_term_research_update_missing_note'::TEXT AS gap_type,
    'portfolio.v_long_term_research_updates'::TEXT AS source_view,
    update_row.id::TEXT AS source_id,
    concat_ws(' · ', update_row.symbol, update_row.update_kind, update_row.checklist_key, update_row.model_key) AS title,
    coalesce(update_row.created_by, 'Research Analyst') AS owner_agent,
    update_row.status,
    update_row.created_at,
    update_row.created_at AS updated_at,
    'Long-term research update exists without a note_path.'::TEXT AS gap_reason
FROM portfolio.v_long_term_research_updates update_row
WHERE nullif(update_row.note_path, '') IS NULL

UNION ALL

SELECT
    'strategy_committee_missing_memo'::TEXT AS gap_type,
    'strategy.v_strategy_committee_queue'::TEXT AS source_view,
    review.id::TEXT AS source_id,
    coalesce(review.strategy_name, 'Strategy committee review') AS title,
    coalesce(review.created_by, 'Strategy Review Committee') AS owner_agent,
    review.review_status AS status,
    review.created_at,
    review.updated_at,
    'Strategy committee review exists without a generated memo_note_path.'::TEXT AS gap_reason
FROM strategy.v_strategy_committee_queue review
WHERE review.review_status IN ('opened', 'needs_review', 'pending_decision')
  AND nullif(review.memo_note_path, '') IS NULL

UNION ALL

SELECT
    'long_term_committee_missing_memo'::TEXT AS gap_type,
    'portfolio.v_long_term_committee_queue'::TEXT AS source_view,
    review.id::TEXT AS source_id,
    coalesce(review.thesis_title, review.company_name, review.symbol, 'Long-term committee review') AS title,
    coalesce(review.created_by, 'Long-Term Investment Committee') AS owner_agent,
    review.review_status AS status,
    review.created_at,
    review.updated_at,
    'Long-term committee review exists without a generated memo_note_path.'::TEXT AS gap_reason
FROM portfolio.v_long_term_committee_queue review
WHERE review.review_status IN ('opened', 'needs_review', 'pending_decision')
  AND nullif(review.memo_note_path, '') IS NULL;

INSERT INTO agent.tool_registry (
    tool_name, tool_type, owning_agent, permission_level, enabled, description, config
) VALUES (
    'ai_os_output_artifact_registry',
    'mcp_tool',
    'Knowledge Librarian',
    'read_only',
    true,
    'Read the unified generated output artifact registry, including memos, reports, worker outputs, models, and traceability gaps.',
    '{"reads":["agent.v_output_artifact_registry_v2","agent.v_output_artifact_summary","agent.v_output_artifact_gaps"],"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb
) ON CONFLICT (tool_name) DO UPDATE SET
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;
