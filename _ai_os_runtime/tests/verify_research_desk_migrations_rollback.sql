\set ON_ERROR_STOP on
BEGIN;

-- All data mutations below are rolled back. Run only in a disposable database.

DO $structural$
DECLARE
    secured_table_count INTEGER;
    hardened_function_count INTEGER;
BEGIN
    IF (SELECT count(*) FROM core.schema_migrations WHERE migration_number IN (244, 245, 246, 247, 248, 249)) <> 6 THEN
        RAISE EXCEPTION 'expected migration ledger rows 244-249';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM agent.model_routes route
        WHERE route.route_name = 'openrouter_public_lead_deepseek_v4_pro'
          AND route.default_provider = 'openrouter'
          AND route.default_model = 'deepseek/deepseek-v4-pro-0813'
          AND route.enabled
    ) OR NOT EXISTS (
        SELECT 1 FROM research.public_model_canary_runs canary
        WHERE canary.candidate_route = 'openrouter_public_lead_deepseek_v4_pro_canary'
          AND canary.status = 'completed'
          AND canary.selected_for_role
          AND coalesce((canary.score->>'structured_output_valid')::boolean, false)
    ) THEN
        RAISE EXCEPTION 'selected public lead route is not backed by a successful structured-output canary';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_roles
        WHERE rolname = 'ai_os_research_runtime'
          AND NOT rolcanlogin
          AND NOT rolsuper
          AND NOT rolcreatedb
          AND NOT rolcreaterole
    ) THEN
        RAISE EXCEPTION 'scoped runtime role is missing or over-privileged';
    END IF;

    SELECT count(*) INTO secured_table_count
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE (n.nspname, c.relname) IN (
        ('knowledge','index_runs'),
        ('knowledge','graph_nodes'),
        ('knowledge','graph_edges'),
        ('knowledge','unresolved_links'),
        ('research','followed_sources'),
        ('research','followed_source_versions'),
        ('research','people_or_authors'),
        ('research','person_source_profiles'),
        ('research','followed_source_items'),
        ('research','source_item_entities'),
        ('research','source_item_claims'),
        ('research','source_scorecards'),
        ('research','idea_cards'),
        ('research','idea_card_evidence'),
        ('research','idea_triage'),
        ('research','followed_source_refresh_runs'),
        ('market','scanner_definitions'),
        ('market','scanner_metric_definitions'),
        ('market','scanner_versions'),
        ('market','scanner_validations'),
        ('market','scanner_schedules'),
        ('market','scanner_runs'),
        ('market','scanner_run_universe'),
        ('market','scanner_results'),
        ('market','scanner_result_metrics'),
        ('market','scanner_result_metric_inputs'),
        ('market','scanner_alerts')
    )
      AND c.relrowsecurity
      AND c.relforcerowsecurity;

    IF secured_table_count <> 27 THEN
        RAISE EXCEPTION 'expected 27 new tables with enabled and forced RLS, found %', secured_table_count;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE (n.nspname, c.relname) IN (
            ('knowledge','obsidian_notes'),
            ('knowledge','note_links'),
            ('knowledge','vector_documents')
        )
          AND c.relrowsecurity
    ) THEN
        RAISE EXCEPTION 'legacy knowledge RLS changed unexpectedly';
    END IF;

    IF (SELECT count(*) FROM market.scanner_definitions WHERE scope_key = 'global:public') <> 9
       OR (SELECT count(*) FROM market.scanner_versions WHERE scope_key = 'global:public' AND status = 'draft') <> 9
    THEN
        RAISE EXCEPTION 'expected nine draft-only scanner templates';
    END IF;

    IF EXISTS (
        SELECT 1 FROM market.scanner_versions
        WHERE scope_key = 'global:public' AND status <> 'draft'
    ) OR EXISTS (
        SELECT 1 FROM market.scanner_runs WHERE scope_key = 'global:public'
    ) OR EXISTS (
        SELECT 1 FROM market.scanner_alerts WHERE scope_key = 'global:public'
    ) THEN
        RAISE EXCEPTION 'scanner seed created executable state, runs or alerts';
    END IF;

    SELECT count(*) INTO hardened_function_count
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE (n.nspname, p.proname) IN (
        ('knowledge','enforce_unresolved_link_scope'),
        ('research','validate_source_item_claim_promotion'),
        ('market','validate_scanner_version_publication'),
        ('market','validate_scanner_schedule_gate'),
        ('market','validate_scanner_universe_point_in_time'),
        ('market','validate_scanner_metric_input_cutoff')
    )
      AND p.prosecdef
      AND EXISTS (
          SELECT 1 FROM unnest(COALESCE(p.proconfig, ARRAY[]::text[])) AS cfg
          WHERE cfg LIKE 'search_path=pg_catalog,%'
      );

    IF hardened_function_count <> 6 THEN
        RAISE EXCEPTION 'expected six hardened legacy-read trigger functions, found %', hardened_function_count;
    END IF;

    IF has_table_privilege('ai_os_research_runtime', 'knowledge.graph_nodes', 'DELETE')
       OR has_table_privilege('ai_os_research_runtime', 'research.idea_cards', 'DELETE')
       OR has_table_privilege('ai_os_research_runtime', 'research.followed_source_refresh_runs', 'DELETE')
       OR has_table_privilege('ai_os_research_runtime', 'market.scanner_runs', 'DELETE')
    THEN
        RAISE EXCEPTION 'runtime role must not have destructive table privileges';
    END IF;

    IF NOT has_table_privilege('ai_os_research_runtime', 'research.companies', 'SELECT')
       OR NOT has_table_privilege('ai_os_research_runtime', 'research.financial_ratio_results', 'SELECT')
       OR NOT has_table_privilege('ai_os_research_runtime', 'market.universe_memberships', 'SELECT')
       OR NOT has_table_privilege('ai_os_research_runtime', 'trading.symbols', 'SELECT')
       OR NOT has_table_privilege('ai_os_research_runtime', 'agent.approvals', 'SELECT')
    THEN
        RAISE EXCEPTION 'runtime role is missing an allowlisted legacy read dependency';
    END IF;

    IF has_schema_privilege('ai_os_research_runtime', 'portfolio', 'USAGE')
       OR has_table_privilege('ai_os_research_runtime', 'research.companies', 'INSERT')
       OR has_table_privilege('ai_os_research_runtime', 'agent.approvals', 'UPDATE')
       OR has_table_privilege('ai_os_research_runtime', 'trading.order_intents', 'SELECT')
       OR has_table_privilege('ai_os_research_runtime', 'trading.order_intents', 'INSERT')
    THEN
        RAISE EXCEPTION 'runtime role escaped the read-only Research Desk boundary';
    END IF;
END
$structural$;

DO $graph_scope$
DECLARE
    node_a BIGINT;
    node_b BIGINT;
    expected_failure BOOLEAN := false;
BEGIN
    INSERT INTO knowledge.graph_nodes (
        scope_key, node_key, node_type, label, authority, created_by
    ) VALUES (
        'verify:scope-a', 'verify-node-a', 'entity', 'A', 'unknown', 'verification'
    ) RETURNING id INTO node_a;

    INSERT INTO knowledge.graph_nodes (
        scope_key, node_key, node_type, label, authority, created_by
    ) VALUES (
        'verify:scope-b', 'verify-node-b', 'entity', 'B', 'unknown', 'verification'
    ) RETURNING id INTO node_b;

    BEGIN
        INSERT INTO knowledge.graph_edges (
            scope_key, edge_key, from_node_id, to_node_id, edge_type, source_kind, created_by
        ) VALUES (
            'verify:scope-a', 'verify-cross-scope', node_a, node_b, 'LINKED_TO', 'verification', 'verification'
        );
    EXCEPTION WHEN OTHERS THEN
        expected_failure := position('cross-scope graph edge rejected' in SQLERRM) > 0;
    END;

    IF NOT expected_failure THEN
        RAISE EXCEPTION 'cross-scope graph edge trigger did not reject the edge';
    END IF;
END
$graph_scope$;

SET LOCAL ROLE ai_os_research_runtime;
SELECT set_config('ai_os.scope_key', 'verify:scope-a', true);

DO $rls_isolation$
BEGIN
    IF (SELECT count(*) FROM knowledge.graph_nodes WHERE node_key = 'verify-node-a') <> 1 THEN
        RAISE EXCEPTION 'scope-a row is not visible to scope-a';
    END IF;
    IF EXISTS (SELECT 1 FROM knowledge.graph_nodes WHERE node_key = 'verify-node-b') THEN
        RAISE EXCEPTION 'scope-b row leaked into scope-a';
    END IF;

    INSERT INTO knowledge.graph_nodes (
        scope_key, node_key, node_type, label, authority, created_by
    ) VALUES (
        'verify:scope-a', 'verify-runtime-node', 'entity', 'Runtime A', 'unknown', 'verification'
    );

    BEGIN
        INSERT INTO knowledge.graph_nodes (
            scope_key, node_key, node_type, label, authority, created_by
        ) VALUES (
            'verify:scope-b', 'verify-runtime-cross-scope', 'entity', 'Runtime B', 'unknown', 'verification'
        );
        RAISE EXCEPTION 'RLS_INSERT_UNEXPECTEDLY_SUCCEEDED';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM = 'RLS_INSERT_UNEXPECTEDLY_SUCCEEDED' THEN
            RAISE;
        END IF;
    END;
END
$rls_isolation$;

RESET ROLE;
SELECT set_config('ai_os.scope_key', '', true);

DO $following_invariants$
DECLARE
    feed_id BIGINT;
    source_id BIGINT;
    version_id BIGINT;
BEGIN
    INSERT INTO research.feed_registry (
        feed_key, feed_name, feed_type, provider, url, status, owner_agent
    ) VALUES (
        'verify-feed', 'Verification Feed', 'rss', 'verification',
        'https://example.invalid/feed', 'planned', 'News Analyst'
    ) RETURNING id INTO feed_id;

    INSERT INTO research.followed_sources (
        scope_key, source_key, feed_registry_id, status, followed_by
    ) VALUES (
        'verify:scope-a', 'verify-source', feed_id, 'pending_review', 'verification'
    ) RETURNING id INTO source_id;

    INSERT INTO research.followed_source_versions (
        scope_key, followed_source_id, version, definition_hash, source_type,
        adapter_key, source_url, copyright_policy, approved_by, approved_at,
        status, created_by
    ) VALUES (
        'verify:scope-a', source_id, 1,
        'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
        'rss', 'rss_atom', 'https://example.invalid/feed',
        'metadata and permitted excerpt only', 'verification', now(),
        'active', 'verification'
    ) RETURNING id INTO version_id;

    UPDATE research.followed_sources
       SET current_version_id = version_id, status = 'active'
     WHERE id = source_id;

    IF NOT EXISTS (
        SELECT 1 FROM research.followed_sources
        WHERE id = source_id AND current_version_id = version_id AND status = 'active'
    ) THEN
        RAISE EXCEPTION 'followed source current-version invariant failed';
    END IF;

    INSERT INTO research.followed_source_refresh_runs (
        scope_key, run_key, idempotency_key, followed_source_id, source_version_id,
        trigger_kind, status, due_at, finished_at, items_upserted, created_by
    ) VALUES (
        'verify:scope-a', 'verify-refresh-run', 'verify-refresh-idempotency', source_id, version_id,
        'manual', 'completed', now(), now(), 1, 'verification'
    );

    IF (SELECT count(*) FROM research.v_followed_source_refresh_status
        WHERE scope_key='verify:scope-a' AND followed_source_id=source_id
          AND latest_run_status='completed' AND items_upserted=1) <> 1 THEN
        RAISE EXCEPTION 'followed source refresh lineage view failed';
    END IF;
END
$following_invariants$;

DO $scanner_invariants$
DECLARE
    approval_id BIGINT;
    definition_id BIGINT;
    version_id BIGINT;
    metric_definition_id BIGINT;
    symbol_id BIGINT;
    membership_id BIGINT;
    run_id BIGINT;
    run_universe_id BIGINT;
    result_id BIGINT;
    result_metric_id BIGINT;
    quote_before_id BIGINT;
    quote_after_id BIGINT;
    stored_available_at TIMESTAMPTZ;
    immutable_rejected BOOLEAN := false;
    unsafe_dsl_rejected BOOLEAN := false;
    draft_run_rejected BOOLEAN := false;
    pit_rejected BOOLEAN := false;
BEGIN
    INSERT INTO agent.approvals (
        approval_type, title, owner_agent, status, requested_action, decided_by, decided_at
    ) VALUES (
        'scanner_publish', 'Verification scanner publication', 'Fundamental Research Analyst',
        'approved', '{"verification":true}'::jsonb, 'verification', now()
    ) RETURNING id INTO approval_id;

    INSERT INTO market.scanner_definitions (
        scope_key, scanner_key, name, description, owner_agent, status, created_by
    ) VALUES (
        'verify:scope-a', 'verification_scanner', 'Verification Scanner',
        'Disposable invariant fixture', 'Fundamental Research Analyst', 'draft', 'verification'
    ) RETURNING id INTO definition_id;

    INSERT INTO market.scanner_versions (
        scope_key, scanner_definition_id, version, status, definition_json,
        definition_hash, calculation_revision, publish_approval_id, created_by
    ) VALUES (
        'verify:scope-a', definition_id, 1, 'published',
        '{"root":{"op":"and","args":[]},"executable":true}'::jsonb,
        'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
        'verification-v1', approval_id, 'verification'
    ) RETURNING id INTO version_id;

    UPDATE market.scanner_definitions
       SET current_published_version_id = version_id, status = 'active'
     WHERE id = definition_id;

    BEGIN
        UPDATE market.scanner_versions
           SET definition_json = '{"root":{"op":"or","args":[]}}'::jsonb
         WHERE id = version_id;
    EXCEPTION WHEN OTHERS THEN
        immutable_rejected := position('published scanner versions are immutable' in SQLERRM) > 0;
    END;
    IF NOT immutable_rejected THEN
        RAISE EXCEPTION 'published scanner immutability trigger did not reject mutation';
    END IF;

    BEGIN
        INSERT INTO market.scanner_versions (
            scope_key, scanner_definition_id, version, status, definition_json,
            definition_hash, calculation_revision, created_by
        ) VALUES (
            'verify:scope-a', definition_id, 2, 'draft',
            '{"sql":"select 1"}'::jsonb,
            'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc',
            'verification-v2', 'verification'
        );
    EXCEPTION WHEN check_violation THEN
        unsafe_dsl_rejected := true;
    END;
    IF NOT unsafe_dsl_rejected THEN
        RAISE EXCEPTION 'unsafe scanner DSL was accepted';
    END IF;

    BEGIN
        INSERT INTO market.scanner_runs (
            scope_key, run_key, idempotency_key, scanner_version_id,
            as_of_date, as_of_cutoff_at, universe_key, universe_hash,
            engine_revision, code_revision, status, created_by
        )
        SELECT
            'global:public', 'verify-draft-run', 'verify-draft-run', v.id,
            DATE '2026-08-24', TIMESTAMPTZ '2026-08-24 18:00:00+00',
            'verify', repeat('d',64), 'verify', 'verify', 'queued', 'verification'
        FROM market.scanner_versions v
        WHERE v.scope_key = 'global:public'
        ORDER BY v.id
        LIMIT 1;
    EXCEPTION WHEN OTHERS THEN
        draft_run_rejected := position('current published scanner version' in SQLERRM) > 0;
    END;
    IF NOT draft_run_rejected THEN
        RAISE EXCEPTION 'draft scanner template was executable';
    END IF;

    INSERT INTO market.scanner_metric_definitions (
        scope_key, metric_key, version, label, value_type, unit,
        implementation_key, source_kind, definition_hash, code_revision,
        status, created_by
    ) VALUES (
        'verify:scope-a', 'verify_price', 1, 'Verification Price', 'numeric', 'INR',
        'price_quote.latest', 'price_quote',
        'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd',
        'verification-v1', 'active', 'verification'
    ) RETURNING id INTO metric_definition_id;

    INSERT INTO trading.symbols (
        symbol, exchange, instrument_type, name, currency, active
    ) VALUES (
        'VERIFY244', 'NSE', 'EQ', 'Verification Symbol', 'INR', true
    ) RETURNING id INTO symbol_id;

    INSERT INTO market.universe_memberships (
        universe_key, symbol_id, valid_from, membership_status,
        source_ref, verification_status
    ) VALUES (
        'verify-universe', symbol_id, DATE '2026-01-01', 'observed',
        'verification', 'verified'
    ) RETURNING id INTO membership_id;

    INSERT INTO market.scanner_runs (
        scope_key, run_key, idempotency_key, scanner_version_id,
        as_of_date, as_of_cutoff_at, universe_key, universe_hash,
        engine_revision, code_revision, status, total_symbols,
        eligible_symbols, created_by
    ) VALUES (
        'verify:scope-a', 'verify-run', 'verify-run', version_id,
        DATE '2026-08-24', TIMESTAMPTZ '2026-08-24 18:00:00+00',
        'verify-universe',
        'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
        'verification-v1', 'verification-v1', 'completed', 1, 1, 'verification'
    ) RETURNING id INTO run_id;

    INSERT INTO market.scanner_run_universe (
        scope_key, scanner_run_id, universe_membership_id, symbol_id,
        eligibility_status, data_completeness, input_snapshot_hash
    ) VALUES (
        'verify:scope-a', run_id, membership_id, symbol_id, 'eligible', 1,
        'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
    ) RETURNING id INTO run_universe_id;

    INSERT INTO market.scanner_results (
        scope_key, scanner_run_id, scanner_run_universe_id,
        symbol_id, rank, passed, score, data_completeness
    ) VALUES (
        'verify:scope-a', run_id, run_universe_id, symbol_id, 1, true, 1, 1
    ) RETURNING id INTO result_id;

    INSERT INTO market.scanner_result_metrics (
        scope_key, scanner_result_id, metric_definition_id,
        metric_key, metric_version, calculation_status,
        value_numeric, unit, as_of_date
    ) VALUES (
        'verify:scope-a', result_id, metric_definition_id,
        'verify_price', 1, 'validated', 100, 'INR', DATE '2026-08-24'
    ) RETURNING id INTO result_metric_id;

    INSERT INTO market.price_quotes (
        source_key, provider, provider_symbol, symbol, exchange,
        currency, price, quote_ts
    ) VALUES (
        'verification', 'verification', 'VERIFY244', 'VERIFY244', 'NSE',
        'INR', 100, TIMESTAMPTZ '2026-08-24 17:00:00+00'
    ) RETURNING id INTO quote_before_id;

    INSERT INTO market.scanner_result_metric_inputs (
        scope_key, result_metric_id, input_role, price_quote_id,
        source_available_at
    ) VALUES (
        'verify:scope-a', result_metric_id, 'price', quote_before_id, now()
    ) RETURNING source_available_at INTO stored_available_at;

    IF stored_available_at IS DISTINCT FROM TIMESTAMPTZ '2026-08-24 17:00:00+00' THEN
        RAISE EXCEPTION 'PIT trigger did not derive the source availability timestamp';
    END IF;

    INSERT INTO market.price_quotes (
        source_key, provider, provider_symbol, symbol, exchange,
        currency, price, quote_ts
    ) VALUES (
        'verification', 'verification', 'VERIFY244_LATE', 'VERIFY244', 'NSE',
        'INR', 101, TIMESTAMPTZ '2026-08-24 19:00:00+00'
    ) RETURNING id INTO quote_after_id;

    BEGIN
        INSERT INTO market.scanner_result_metric_inputs (
            scope_key, result_metric_id, input_role, price_quote_id,
            source_available_at
        ) VALUES (
            'verify:scope-a', result_metric_id, 'late_price', quote_after_id, now()
        );
    EXCEPTION WHEN OTHERS THEN
        pit_rejected := position('point-in-time cutoff violation' in SQLERRM) > 0;
    END;
    IF NOT pit_rejected THEN
        RAISE EXCEPTION 'PIT cutoff trigger accepted a future quote';
    END IF;
END
$scanner_invariants$;

ROLLBACK;

SELECT 'verification_passed' AS result;
