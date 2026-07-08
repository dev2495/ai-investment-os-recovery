CREATE OR REPLACE VIEW agent.v_active_agents AS
SELECT
    agent_name,
    department,
    role_scope,
    default_model_route,
    default_tools,
    permission_level,
    output_targets,
    guardrails
FROM agent.profiles
WHERE status = 'active'
ORDER BY department, agent_name;

CREATE OR REPLACE VIEW agent.v_open_tasks AS
SELECT
    id,
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
    created_at,
    updated_at
FROM agent.tasks
WHERE status IN ('queued', 'in_progress', 'blocked')
ORDER BY
    CASE priority
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'normal' THEN 3
        ELSE 4
    END,
    created_at;

CREATE OR REPLACE VIEW client_data.v_p2cursor_source_summary AS
SELECT
    sf.id AS source_file_id,
    sf.original_path,
    sf.file_type,
    sf.size_bytes,
    sf.import_status,
    sf.registered_at,
    coalesce(count(rows.id), 0) AS staged_row_count,
    sf.profile
FROM client_data.source_files sf
LEFT JOIN client_data.p2cursor_csv_rows rows
    ON rows.source_file_id = sf.id
GROUP BY
    sf.id,
    sf.original_path,
    sf.file_type,
    sf.size_bytes,
    sf.import_status,
    sf.registered_at,
    sf.profile
ORDER BY sf.file_type, sf.original_path;

CREATE OR REPLACE VIEW knowledge.v_obsidian_note_index AS
SELECT
    id,
    note_path,
    title,
    note_type,
    tags,
    content_hash,
    body_summary,
    last_modified_at,
    indexed_at
FROM knowledge.obsidian_notes
ORDER BY note_path;

CREATE OR REPLACE VIEW portfolio.v_latest_positions AS
SELECT DISTINCT ON (account_id, symbol, exchange, instrument_type)
    id,
    account_id,
    symbol,
    exchange,
    instrument_type,
    quantity,
    average_price,
    market_price,
    market_value,
    unrealized_pnl,
    as_of,
    source_system_id
FROM portfolio.positions
ORDER BY account_id, symbol, exchange, instrument_type, as_of DESC;

CREATE OR REPLACE VIEW trading.v_recent_signals AS
SELECT
    id,
    ts,
    source_system_id,
    strategy,
    symbol,
    exchange,
    action,
    price,
    quantity,
    confidence,
    status,
    payload
FROM trading.signals
ORDER BY ts DESC
LIMIT 500;

CREATE OR REPLACE VIEW strategy.v_open_alerts AS
SELECT
    id,
    ts,
    alert_rule_id,
    instance_id,
    source_signal_id,
    symbol,
    exchange,
    timeframe,
    severity,
    status,
    title,
    message,
    payload
FROM strategy.alert_events
WHERE status IN ('new', 'acknowledged')
ORDER BY ts DESC;

CREATE OR REPLACE VIEW market.v_recent_news AS
SELECT
    id,
    source_name,
    source_url,
    title,
    publisher,
    published_at,
    captured_at,
    symbols,
    topics,
    geography,
    sentiment,
    relevance_score
FROM market.news_items
ORDER BY coalesce(published_at, captured_at) DESC
LIMIT 500;
