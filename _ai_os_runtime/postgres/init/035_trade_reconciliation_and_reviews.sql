CREATE TABLE IF NOT EXISTS books.broker_reconciliation_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    run_ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_scope TEXT NOT NULL DEFAULT 'attached_broker_transactions',
    status TEXT NOT NULL DEFAULT 'completed',
    total_broker_rows INTEGER NOT NULL DEFAULT 0,
    staged_routes INTEGER NOT NULL DEFAULT 0,
    promoted_routes INTEGER NOT NULL DEFAULT 0,
    history_links INTEGER NOT NULL DEFAULT 0,
    active_exposure_links INTEGER NOT NULL DEFAULT 0,
    unmapped_rows INTEGER NOT NULL DEFAULT 0,
    duplicate_trade_refs INTEGER NOT NULL DEFAULT 0,
    amount_mismatch_rows INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::JSONB,
    created_by TEXT NOT NULL DEFAULT 'Jarvis',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS books.broker_reconciliation_issues (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT REFERENCES books.broker_reconciliation_runs(id) ON DELETE CASCADE,
    issue_key TEXT NOT NULL,
    issue_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'medium',
    broker_transaction_id BIGINT REFERENCES client_data.attached_broker_transactions(id) ON DELETE SET NULL,
    trade_activity_id BIGINT REFERENCES trading.trade_activity_ledger(id) ON DELETE SET NULL,
    symbol TEXT,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    owner_agent TEXT NOT NULL DEFAULT 'Data Steward',
    evidence JSONB NOT NULL DEFAULT '[]'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, issue_key)
);

CREATE TABLE IF NOT EXISTS trading.post_trade_reviews (
    id BIGSERIAL PRIMARY KEY,
    trade_activity_id BIGINT NOT NULL REFERENCES trading.trade_activity_ledger(id) ON DELETE CASCADE,
    book_position_id BIGINT REFERENCES books.book_positions(id) ON DELETE SET NULL,
    book_key TEXT REFERENCES books.investment_books(book_key) ON DELETE SET NULL,
    purpose_key TEXT REFERENCES books.position_purposes(purpose_key) ON DELETE SET NULL,
    review_type TEXT NOT NULL DEFAULT 'post_trade',
    review_status TEXT NOT NULL DEFAULT 'queued',
    owner_agent TEXT NOT NULL DEFAULT 'Trading Desk Agent',
    due_at TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '1 day'),
    pre_trade_thesis TEXT,
    planned_exit TEXT,
    actual_exit TEXT,
    execution_quality NUMERIC,
    rule_violations TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    lessons TEXT,
    next_action TEXT NOT NULL DEFAULT 'Complete post-trade review with setup, risk, execution, outcome, and lesson.',
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    inbox_item_id BIGINT REFERENCES agent.inbox_items(id) ON DELETE SET NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (trade_activity_id)
);

CREATE INDEX IF NOT EXISTS idx_broker_recon_runs_created ON books.broker_reconciliation_runs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_broker_recon_issues_run ON books.broker_reconciliation_issues (run_id, severity, status);
CREATE INDEX IF NOT EXISTS idx_post_trade_reviews_status ON trading.post_trade_reviews (review_status, due_at);
CREATE INDEX IF NOT EXISTS idx_post_trade_reviews_trade ON trading.post_trade_reviews (trade_activity_id);

CREATE OR REPLACE FUNCTION books.run_broker_reconciliation(
    p_actor TEXT DEFAULT 'Jarvis'
) RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    inserted_run_id BIGINT;
BEGIN
    INSERT INTO books.broker_reconciliation_runs (
        run_key,
        total_broker_rows,
        staged_routes,
        promoted_routes,
        history_links,
        active_exposure_links,
        unmapped_rows,
        duplicate_trade_refs,
        amount_mismatch_rows,
        notes,
        evidence,
        created_by
    )
    SELECT
        'broker-recon-' || to_char(now(), 'YYYYMMDDHH24MISSMS'),
        (SELECT count(*) FROM client_data.attached_broker_transactions),
        (SELECT count(*) FROM books.broker_transaction_import_routes WHERE status = 'staged'),
        (SELECT count(*) FROM books.broker_transaction_import_routes WHERE status = 'promoted'),
        (SELECT count(*) FROM books.trade_book_links WHERE broker_transaction_id IS NOT NULL AND affects_active_exposure = false),
        (SELECT count(*) FROM books.trade_book_links WHERE broker_transaction_id IS NOT NULL AND affects_active_exposure = true),
        (
            SELECT count(*)
            FROM client_data.attached_broker_transactions bt
            LEFT JOIN books.broker_transaction_import_routes r ON r.broker_transaction_id = bt.id
            WHERE r.id IS NULL
        ),
        (
            SELECT count(*)
            FROM (
                SELECT source_file_id, trade_no, count(*) AS rows_seen
                FROM client_data.attached_broker_transactions
                WHERE trade_no IS NOT NULL
                GROUP BY source_file_id, trade_no
                HAVING count(*) > 1
            ) duplicates
        ),
        (
            SELECT count(*)
            FROM client_data.attached_broker_transactions
            WHERE quantity IS NOT NULL
              AND coalesce(net_rate, market_rate) IS NOT NULL
              AND amount IS NOT NULL
              AND abs(abs(amount) - abs(quantity * coalesce(net_rate, market_rate))) > greatest(10, abs(amount) * 0.05)
        ),
        'Broker reconciliation generated from parsed attached transactions and broker route/link tables.',
        jsonb_build_array(
            jsonb_build_object('table', 'client_data.attached_broker_transactions'),
            jsonb_build_object('table', 'books.broker_transaction_import_routes'),
            jsonb_build_object('table', 'books.trade_book_links')
        ),
        p_actor
    RETURNING id INTO inserted_run_id;

    INSERT INTO books.broker_reconciliation_issues (
        run_id, issue_key, issue_type, severity, broker_transaction_id,
        symbol, description, owner_agent, evidence
    )
    SELECT
        inserted_run_id,
        'unmapped-broker-transaction-' || bt.id::TEXT,
        'unmapped_broker_transaction',
        'critical',
        bt.id,
        bt.trading_symbol,
        'Broker transaction has not been classified into an import route.',
        'Data Steward',
        jsonb_build_array(jsonb_build_object('table', 'client_data.attached_broker_transactions', 'id', bt.id))
    FROM client_data.attached_broker_transactions bt
    LEFT JOIN books.broker_transaction_import_routes r ON r.broker_transaction_id = bt.id
    WHERE r.id IS NULL
    ON CONFLICT (run_id, issue_key) DO NOTHING;

    INSERT INTO books.broker_reconciliation_issues (
        run_id, issue_key, issue_type, severity, broker_transaction_id,
        symbol, description, owner_agent, evidence
    )
    SELECT
        inserted_run_id,
        'duplicate-trade-ref-' || duplicate_rows.source_file_id::TEXT || '-' || duplicate_rows.trade_no,
        'duplicate_trade_reference',
        'medium',
        duplicate_rows.sample_broker_transaction_id,
        duplicate_rows.sample_symbol,
        'Broker trade number appears more than once in the same source file; verify whether this is a split fill or duplicate import.',
        'Data Steward',
        jsonb_build_array(
            jsonb_build_object('source_file_id', duplicate_rows.source_file_id),
            jsonb_build_object('trade_no', duplicate_rows.trade_no),
            jsonb_build_object('rows_seen', duplicate_rows.rows_seen)
        )
    FROM (
        SELECT
            source_file_id,
            trade_no,
            min(id) AS sample_broker_transaction_id,
            min(trading_symbol) AS sample_symbol,
            count(*) AS rows_seen
        FROM client_data.attached_broker_transactions
        WHERE trade_no IS NOT NULL
        GROUP BY source_file_id, trade_no
        HAVING count(*) > 1
    ) duplicate_rows
    ON CONFLICT (run_id, issue_key) DO NOTHING;

    INSERT INTO books.broker_reconciliation_issues (
        run_id, issue_key, issue_type, severity, broker_transaction_id,
        symbol, description, owner_agent, evidence
    )
    SELECT
        inserted_run_id,
        'amount-mismatch-' || bt.id::TEXT,
        'amount_mismatch',
        'medium',
        bt.id,
        bt.trading_symbol,
        'Broker amount differs materially from quantity multiplied by rate; fees/taxes may explain this but row needs reconciliation.',
        'Data Steward',
        jsonb_build_array(jsonb_build_object('table', 'client_data.attached_broker_transactions', 'id', bt.id))
    FROM client_data.attached_broker_transactions bt
    WHERE bt.quantity IS NOT NULL
      AND coalesce(bt.net_rate, bt.market_rate) IS NOT NULL
      AND bt.amount IS NOT NULL
      AND abs(abs(bt.amount) - abs(bt.quantity * coalesce(bt.net_rate, bt.market_rate))) > greatest(10, abs(bt.amount) * 0.05)
    ON CONFLICT (run_id, issue_key) DO NOTHING;

    INSERT INTO agent.tasks (
        title, objective, owner_agent, status, priority, approval_required,
        source_kind, source_ref, output_format, output_note_path, evidence
    )
    VALUES (
        'Broker reconciliation review #' || inserted_run_id::TEXT,
        'Review broker import reconciliation issues, confirm route quality, and decide which broker rows should be promoted into trade history.',
        'Data Steward',
        'queued',
        CASE
            WHEN (SELECT unmapped_rows + duplicate_trade_refs FROM books.broker_reconciliation_runs WHERE id = inserted_run_id) > 0 THEN 'high'
            ELSE 'medium'
        END,
        false,
        'books.broker_reconciliation_runs',
        inserted_run_id::TEXT,
        'obsidian_note',
        'ai memory/00 AI OS/Agent Outputs/Broker Reconciliation/broker-reconciliation-' || inserted_run_id::TEXT || '.md',
        jsonb_build_array(jsonb_build_object('table', 'books.broker_reconciliation_runs', 'id', inserted_run_id))
    );

    INSERT INTO agent.inbox_items (
        task_id, title, owner_agent, status, priority, recommended_action, evidence, target_workspace
    )
    SELECT
        t.id,
        'Broker reconciliation ready #' || inserted_run_id::TEXT,
        'Data Steward',
        'queued',
        t.priority,
        'Review reconciliation summary and route exceptions before promoting broker rows into trade history.',
        jsonb_build_array(jsonb_build_object('table', 'books.broker_reconciliation_runs', 'id', inserted_run_id)),
        'system'
    FROM agent.tasks t
    WHERE t.source_kind = 'books.broker_reconciliation_runs'
      AND t.source_ref = inserted_run_id::TEXT
    ORDER BY t.id DESC
    LIMIT 1;

    RETURN inserted_run_id;
END;
$$;

CREATE OR REPLACE FUNCTION trading.ensure_post_trade_review(
    p_trade_activity_id BIGINT,
    p_actor TEXT DEFAULT 'Jarvis'
) RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    trade_row trading.trade_activity_ledger%ROWTYPE;
    book_row books.book_positions%ROWTYPE;
    inserted_review_id BIGINT;
    inserted_task_id BIGINT;
    inserted_inbox_id BIGINT;
BEGIN
    SELECT *
    INTO trade_row
    FROM trading.trade_activity_ledger
    WHERE id = p_trade_activity_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'trade activity % not found', p_trade_activity_id;
    END IF;

    SELECT *
    INTO book_row
    FROM books.book_positions
    WHERE source_trade_id = p_trade_activity_id
    LIMIT 1;

    INSERT INTO trading.post_trade_reviews (
        trade_activity_id, book_position_id, book_key, purpose_key,
        review_type, review_status, owner_agent, due_at, pre_trade_thesis,
        planned_exit, next_action, evidence
    )
    VALUES (
        trade_row.id,
        book_row.id,
        book_row.book_key,
        book_row.purpose_key,
        CASE WHEN trade_row.execution_mode = 'paper' THEN 'paper_trade_review' ELSE 'post_trade' END,
        'queued',
        CASE WHEN trade_row.execution_mode = 'paper' THEN 'Strategy Generator' ELSE 'Trading Desk Agent' END,
        CASE WHEN trade_row.execution_mode = 'paper' THEN now() + INTERVAL '2 days' ELSE now() + INTERVAL '1 day' END,
        trade_row.thesis,
        CASE
            WHEN trade_row.stop_loss IS NOT NULL AND trade_row.target_price IS NOT NULL THEN
                'Stop ' || trade_row.stop_loss::TEXT || '; target ' || trade_row.target_price::TEXT
            WHEN trade_row.stop_loss IS NOT NULL THEN
                'Stop ' || trade_row.stop_loss::TEXT || '; target missing'
            WHEN trade_row.target_price IS NOT NULL THEN
                'Target ' || trade_row.target_price::TEXT || '; stop missing'
            ELSE 'Stop/target/time exit missing'
        END,
        'Complete post-trade review: setup, sizing, execution, exit discipline, P&L, mistake, and lesson.',
        jsonb_build_array(
            jsonb_build_object('table', 'trading.trade_activity_ledger', 'id', trade_row.id),
            jsonb_build_object('table', 'books.book_positions', 'id', book_row.id)
        )
    )
    ON CONFLICT (trade_activity_id) DO UPDATE SET
        book_position_id = EXCLUDED.book_position_id,
        book_key = EXCLUDED.book_key,
        purpose_key = EXCLUDED.purpose_key,
        pre_trade_thesis = coalesce(trading.post_trade_reviews.pre_trade_thesis, EXCLUDED.pre_trade_thesis),
        planned_exit = coalesce(trading.post_trade_reviews.planned_exit, EXCLUDED.planned_exit),
        updated_at = now()
    RETURNING id INTO inserted_review_id;

    SELECT task_id, inbox_item_id
    INTO inserted_task_id, inserted_inbox_id
    FROM trading.post_trade_reviews
    WHERE id = inserted_review_id;

    IF inserted_task_id IS NULL THEN
        INSERT INTO agent.tasks (
            title, objective, owner_agent, status, priority, approval_required,
            source_kind, source_ref, output_format, output_note_path, evidence
        )
        VALUES (
            'Post-trade review: ' || trade_row.symbol || ' #' || trade_row.id::TEXT,
            'Complete post-trade review for trade #' || trade_row.id::TEXT || ': setup, book, risk, execution quality, rule violations, and lessons.',
            CASE WHEN trade_row.execution_mode = 'paper' THEN 'Strategy Generator' ELSE 'Trading Desk Agent' END,
            'queued',
            CASE WHEN trade_row.execution_mode = 'manual_actual' THEN 'high' ELSE 'medium' END,
            false,
            'trading.post_trade_reviews',
            inserted_review_id::TEXT,
            'obsidian_note',
            'ai memory/00 AI OS/Agent Outputs/Post Trade Reviews/trade-' || trade_row.id::TEXT || '-review.md',
            jsonb_build_array(
                jsonb_build_object('table', 'trading.trade_activity_ledger', 'id', trade_row.id),
                jsonb_build_object('table', 'trading.post_trade_reviews', 'id', inserted_review_id)
            )
        )
        RETURNING id INTO inserted_task_id;
    END IF;

    IF inserted_inbox_id IS NULL THEN
        INSERT INTO agent.inbox_items (
            task_id, title, owner_agent, status, priority, recommended_action, evidence, target_workspace
        )
        VALUES (
            inserted_task_id,
            'Post-trade review queued: ' || trade_row.symbol,
            CASE WHEN trade_row.execution_mode = 'paper' THEN 'Strategy Generator' ELSE 'Trading Desk Agent' END,
            'queued',
            CASE WHEN trade_row.execution_mode = 'manual_actual' THEN 'high' ELSE 'medium' END,
            'Review the trade and record outcome, rule adherence, mistakes, and strategy implications.',
            jsonb_build_array(jsonb_build_object('table', 'trading.post_trade_reviews', 'id', inserted_review_id)),
            'trading'
        )
        RETURNING id INTO inserted_inbox_id;
    END IF;

    UPDATE trading.post_trade_reviews
    SET task_id = inserted_task_id,
        inbox_item_id = inserted_inbox_id,
        updated_at = now()
    WHERE id = inserted_review_id;

    RETURN inserted_review_id;
END;
$$;

CREATE OR REPLACE VIEW books.v_broker_reconciliation_latest AS
SELECT *
FROM books.broker_reconciliation_runs
ORDER BY created_at DESC, id DESC
LIMIT 1;

CREATE OR REPLACE VIEW books.v_broker_reconciliation_issues AS
SELECT
    i.id,
    i.run_id,
    r.run_key,
    i.issue_key,
    i.issue_type,
    i.severity,
    i.status,
    i.broker_transaction_id,
    i.trade_activity_id,
    i.symbol,
    i.description,
    i.owner_agent,
    i.evidence,
    i.created_at,
    i.updated_at
FROM books.broker_reconciliation_issues i
JOIN books.broker_reconciliation_runs r ON r.id = i.run_id
ORDER BY
    CASE i.severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
    i.created_at DESC;

CREATE OR REPLACE VIEW trading.v_post_trade_review_queue AS
SELECT
    r.id,
    r.trade_activity_id,
    r.book_position_id,
    r.book_key,
    ib.book_name,
    r.purpose_key,
    pp.purpose_name,
    r.review_type,
    r.review_status,
    r.owner_agent,
    r.due_at,
    t.execution_mode,
    t.source_kind,
    t.client_code,
    t.account_code,
    t.strategy_key,
    t.symbol,
    t.exchange,
    t.instrument_type,
    t.side,
    t.quantity,
    t.price,
    t.trade_ts,
    t.thesis,
    r.planned_exit,
    r.actual_exit,
    r.execution_quality,
    r.rule_violations,
    r.lessons,
    r.next_action,
    r.task_id,
    r.inbox_item_id,
    r.created_at,
    r.updated_at
FROM trading.post_trade_reviews r
JOIN trading.trade_activity_ledger t ON t.id = r.trade_activity_id
LEFT JOIN books.investment_books ib ON ib.book_key = r.book_key
LEFT JOIN books.position_purposes pp ON pp.purpose_key = r.purpose_key
ORDER BY
    CASE r.review_status WHEN 'queued' THEN 1 WHEN 'in_review' THEN 2 WHEN 'completed' THEN 3 ELSE 4 END,
    r.due_at ASC,
    r.id DESC;

INSERT INTO agent.skills (
    skill_key, skill_name, skill_family, skill_type, owner_department, status,
    execution_mode, permission_level, trigger_phrases, input_sources, output_targets,
    required_tools, risk_notes, prompt_template, config
)
VALUES
    (
        'broker_import_reconciliation',
        'Broker Import Reconciliation',
        'data_quality',
        'reconciliation',
        'data',
        'active',
        'worker_deterministic',
        'write_with_approval',
        ARRAY['broker reconciliation','reconcile broker imports','broker import queue'],
        ARRAY['client_data.attached_broker_transactions','books.broker_transaction_import_routes','books.trade_book_links'],
        ARRAY['books.broker_reconciliation_runs','books.broker_reconciliation_issues','agent.inbox_items'],
        ARRAY['postgres_read_model','broker_import_router'],
        'Broker rows are history evidence unless explicitly promoted; never execute broker actions.',
        'Summarize broker import coverage, route quality, exceptions, and safe next action.',
        '{"dashboard_view":"books.v_broker_reconciliation_latest"}'::JSONB
    ),
    (
        'post_trade_review',
        'Post Trade Review',
        'trading',
        'review',
        'trading',
        'active',
        'worker_or_llm',
        'write_with_approval',
        ARRAY['post trade review','review trade','trade lesson','what went wrong'],
        ARRAY['trading.trade_activity_ledger','trading.post_trade_reviews','books.book_positions'],
        ARRAY['trading.trade_journals','knowledge.obsidian_notes','agent.inbox_items'],
        ARRAY['postgres_read_model','obsidian_writeback'],
        'Reviews trades; does not recommend live execution without approval.',
        'Review setup, sizing, execution, rule adherence, outcome, lesson, and strategy implications.',
        '{"dashboard_view":"trading.v_post_trade_review_queue"}'::JSONB
    )
ON CONFLICT (skill_key) DO UPDATE SET
    skill_name = EXCLUDED.skill_name,
    skill_family = EXCLUDED.skill_family,
    skill_type = EXCLUDED.skill_type,
    owner_department = EXCLUDED.owner_department,
    status = EXCLUDED.status,
    execution_mode = EXCLUDED.execution_mode,
    permission_level = EXCLUDED.permission_level,
    trigger_phrases = EXCLUDED.trigger_phrases,
    input_sources = EXCLUDED.input_sources,
    output_targets = EXCLUDED.output_targets,
    required_tools = EXCLUDED.required_tools,
    risk_notes = EXCLUDED.risk_notes,
    prompt_template = EXCLUDED.prompt_template,
    config = EXCLUDED.config,
    updated_at = now();

INSERT INTO agent.agent_skill_map (agent_name, skill_key, proficiency, is_primary, activation_rules)
VALUES
    ('Data Steward', 'broker_import_reconciliation', 'expert', true, '{"default_for":"broker import queue"}'::JSONB),
    ('Trading Desk Agent', 'post_trade_review', 'expert', true, '{"default_for":"manual actual trades"}'::JSONB),
    ('Strategy Generator', 'post_trade_review', 'working', false, '{"default_for":"paper strategy trades"}'::JSONB),
    ('Trade Journal Learning Agent', 'post_trade_review', 'expert', false, '{"default_for":"lesson extraction"}'::JSONB)
ON CONFLICT (agent_name, skill_key) DO UPDATE SET
    proficiency = EXCLUDED.proficiency,
    is_primary = EXCLUDED.is_primary,
    activation_rules = EXCLUDED.activation_rules,
    updated_at = now();
