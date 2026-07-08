CREATE TABLE IF NOT EXISTS ops.browser_profiles (
    id BIGSERIAL PRIMARY KEY,
    profile_key TEXT NOT NULL UNIQUE,
    profile_name TEXT NOT NULL,
    browser_name TEXT NOT NULL DEFAULT 'chromium',
    use_case TEXT NOT NULL,
    profile_path TEXT,
    remote_debugging_host TEXT NOT NULL DEFAULT '127.0.0.1',
    remote_debugging_port INTEGER,
    target_base_url TEXT,
    status TEXT NOT NULL DEFAULT 'configured',
    owner_agent TEXT NOT NULL DEFAULT 'Browser Research Runner',
    sensitivity TEXT NOT NULL DEFAULT 'private',
    permission_level TEXT NOT NULL DEFAULT 'browser_read_capture',
    health_status TEXT NOT NULL DEFAULT 'unchecked',
    last_checked_at TIMESTAMPTZ,
    last_error TEXT,
    notes TEXT,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_browser_profiles_status ON ops.browser_profiles (status);
CREATE INDEX IF NOT EXISTS idx_browser_profiles_health ON ops.browser_profiles (health_status);

CREATE TABLE IF NOT EXISTS ops.browser_profile_connector_links (
    id BIGSERIAL PRIMARY KEY,
    profile_key TEXT NOT NULL REFERENCES ops.browser_profiles(profile_key) ON DELETE CASCADE,
    connector_key TEXT NOT NULL REFERENCES core.source_connector_profiles(connector_key) ON DELETE CASCADE,
    link_status TEXT NOT NULL DEFAULT 'active',
    required_for TEXT NOT NULL DEFAULT 'browser_session',
    owner_agent TEXT NOT NULL DEFAULT 'Data Steward',
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (profile_key, connector_key)
);

CREATE INDEX IF NOT EXISTS idx_browser_profile_links_connector ON ops.browser_profile_connector_links (connector_key);

CREATE TABLE IF NOT EXISTS ops.browser_session_checks (
    id BIGSERIAL PRIMARY KEY,
    profile_key TEXT NOT NULL REFERENCES ops.browser_profiles(profile_key) ON DELETE CASCADE,
    connector_key TEXT REFERENCES core.source_connector_profiles(connector_key) ON DELETE SET NULL,
    check_type TEXT NOT NULL DEFAULT 'cdp_or_profile',
    status TEXT NOT NULL,
    remote_debugging_host TEXT,
    remote_debugging_port INTEGER,
    browser_label TEXT,
    target_base_url TEXT,
    error_message TEXT,
    sample_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    checked_by TEXT NOT NULL DEFAULT 'Jarvis',
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_browser_session_checks_profile ON ops.browser_session_checks (profile_key, checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_browser_session_checks_connector ON ops.browser_session_checks (connector_key, checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_browser_session_checks_status ON ops.browser_session_checks (status);

CREATE OR REPLACE FUNCTION ops.register_browser_profile(payload JSONB)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_profile_key TEXT := lower(regexp_replace(coalesce(nullif(payload->>'profile_key', ''), payload->>'profile_name', ''), '[^a-zA-Z0-9]+', '_', 'g'));
    v_result JSONB;
BEGIN
    v_profile_key := trim(both '_' FROM v_profile_key);
    IF v_profile_key = '' THEN
        RAISE EXCEPTION 'profile_key or profile_name is required';
    END IF;

    INSERT INTO ops.browser_profiles (
        profile_key, profile_name, browser_name, use_case, profile_path,
        remote_debugging_host, remote_debugging_port, target_base_url,
        status, owner_agent, sensitivity, permission_level, notes, config,
        updated_at
    )
    VALUES (
        v_profile_key,
        coalesce(nullif(payload->>'profile_name', ''), v_profile_key),
        coalesce(nullif(payload->>'browser_name', ''), 'chromium'),
        coalesce(nullif(payload->>'use_case', ''), 'browser automation'),
        nullif(payload->>'profile_path', ''),
        coalesce(nullif(payload->>'remote_debugging_host', ''), '127.0.0.1'),
        nullif(payload->>'remote_debugging_port', '')::INTEGER,
        nullif(payload->>'target_base_url', ''),
        coalesce(nullif(payload->>'status', ''), 'configured'),
        coalesce(nullif(payload->>'owner_agent', ''), 'Browser Research Runner'),
        coalesce(nullif(payload->>'sensitivity', ''), 'private'),
        coalesce(nullif(payload->>'permission_level', ''), 'browser_read_capture'),
        nullif(payload->>'notes', ''),
        coalesce(payload->'config', '{}'::jsonb),
        now()
    )
    ON CONFLICT (profile_key) DO UPDATE SET
        profile_name = EXCLUDED.profile_name,
        browser_name = EXCLUDED.browser_name,
        use_case = EXCLUDED.use_case,
        profile_path = EXCLUDED.profile_path,
        remote_debugging_host = EXCLUDED.remote_debugging_host,
        remote_debugging_port = EXCLUDED.remote_debugging_port,
        target_base_url = EXCLUDED.target_base_url,
        status = EXCLUDED.status,
        owner_agent = EXCLUDED.owner_agent,
        sensitivity = EXCLUDED.sensitivity,
        permission_level = EXCLUDED.permission_level,
        notes = EXCLUDED.notes,
        config = EXCLUDED.config,
        updated_at = now()
    RETURNING to_jsonb(ops.browser_profiles.*) INTO v_result;

    RETURN v_result;
END;
$$;

CREATE OR REPLACE FUNCTION ops.attach_browser_profile_to_connector(
    p_profile_key TEXT,
    p_connector_key TEXT,
    p_actor TEXT DEFAULT 'Jarvis'
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_result JSONB;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM ops.browser_profiles WHERE profile_key = p_profile_key) THEN
        RAISE EXCEPTION 'browser profile not found: %', p_profile_key;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM core.source_connector_profiles WHERE connector_key = p_connector_key) THEN
        RAISE EXCEPTION 'source connector not found: %', p_connector_key;
    END IF;

    INSERT INTO ops.browser_profile_connector_links (
        profile_key, connector_key, link_status, owner_agent, evidence, updated_at
    )
    VALUES (
        p_profile_key,
        p_connector_key,
        'active',
        p_actor,
        jsonb_build_array(jsonb_build_object('source', 'ops.attach_browser_profile_to_connector', 'actor', p_actor)),
        now()
    )
    ON CONFLICT (profile_key, connector_key) DO UPDATE SET
        link_status = 'active',
        owner_agent = EXCLUDED.owner_agent,
        evidence = EXCLUDED.evidence,
        updated_at = now()
    RETURNING to_jsonb(ops.browser_profile_connector_links.*) INTO v_result;

    UPDATE core.source_connector_profiles
    SET requires_browser_session = true,
        config = jsonb_set(
            jsonb_set(coalesce(config, '{}'::jsonb), '{browser_profile}', to_jsonb(p_profile_key), true),
            '{browser_profile_linked_at}', to_jsonb(now()::TEXT), true
        ),
        updated_at = now()
    WHERE connector_key = p_connector_key;

    RETURN v_result;
END;
$$;

CREATE OR REPLACE FUNCTION ops.record_browser_session_check(payload JSONB)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_profile_key TEXT := nullif(payload->>'profile_key', '');
    v_connector_key TEXT := nullif(payload->>'connector_key', '');
    v_status TEXT := coalesce(nullif(payload->>'status', ''), 'unknown');
    v_result JSONB;
BEGIN
    IF v_profile_key IS NULL THEN
        RAISE EXCEPTION 'profile_key is required';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM ops.browser_profiles WHERE profile_key = v_profile_key) THEN
        RAISE EXCEPTION 'browser profile not found: %', v_profile_key;
    END IF;

    INSERT INTO ops.browser_session_checks (
        profile_key, connector_key, check_type, status,
        remote_debugging_host, remote_debugging_port, browser_label,
        target_base_url, error_message, sample_payload, checked_by
    )
    VALUES (
        v_profile_key,
        v_connector_key,
        coalesce(nullif(payload->>'check_type', ''), 'cdp_or_profile'),
        v_status,
        nullif(payload->>'remote_debugging_host', ''),
        nullif(payload->>'remote_debugging_port', '')::INTEGER,
        nullif(payload->>'browser_label', ''),
        nullif(payload->>'target_base_url', ''),
        nullif(payload->>'error_message', ''),
        coalesce(payload->'sample_payload', '{}'::jsonb),
        coalesce(nullif(payload->>'checked_by', ''), 'Jarvis')
    )
    RETURNING to_jsonb(ops.browser_session_checks.*) INTO v_result;

    UPDATE ops.browser_profiles
    SET health_status = v_status,
        last_checked_at = now(),
        last_error = nullif(payload->>'error_message', ''),
        updated_at = now()
    WHERE profile_key = v_profile_key;

    RETURN v_result;
END;
$$;

INSERT INTO ops.browser_profiles (
    profile_key, profile_name, browser_name, use_case, profile_path,
    remote_debugging_host, remote_debugging_port, target_base_url, status,
    owner_agent, sensitivity, permission_level, notes, config
)
VALUES
    (
        'tradingview_desktop_cdp',
        'TradingView Desktop CDP',
        'TradingView Desktop',
        'TradingView chart automation, screenshots, Pine/chart workflows',
        NULL,
        '127.0.0.1',
        9222,
        'https://www.tradingview.com',
        'configured',
        'Trading Desk Agent',
        'private_trading',
        'browser_desktop_control_gated',
        'Requires TradingView Desktop to be relaunched with localhost CDP port 9222. Broker execution remains disabled.',
        '{"execution_allowed":false,"requires_human_gate_for":["alert_create","alert_delete","ui_evaluate","tab_close"]}'::jsonb
    ),
    (
        'public_research_playwright',
        'Public Research Playwright Profile',
        'Chromium',
        'NSE/BSE filings, public web evidence, news source capture',
        '_ai_os_runtime/browser_profiles/public_research',
        '127.0.0.1',
        NULL,
        NULL,
        'configured',
        'Browser Research Runner',
        'public',
        'browser_read_capture',
        'Public-source browser profile stored under the external SSD runtime root.',
        '{"login_required":false,"public_sources_only":true}'::jsonb
    ),
    (
        'x_watchlist_manual_profile',
        'X Watchlist Manual Review Profile',
        'Safari/Chrome',
        'Manual social watchlist review and evidence capture',
        '_ai_os_runtime/browser_profiles/x_watchlist_manual',
        '127.0.0.1',
        NULL,
        'https://x.com',
        'planned',
        'News Analyst',
        'private',
        'browser_read_manual_login',
        'Requires manual logged-in browser review. Rumors must never be treated as filing evidence.',
        '{"login_required":true,"manual_review_required":true}'::jsonb
    )
ON CONFLICT (profile_key) DO UPDATE SET
    profile_name = EXCLUDED.profile_name,
    browser_name = EXCLUDED.browser_name,
    use_case = EXCLUDED.use_case,
    profile_path = EXCLUDED.profile_path,
    remote_debugging_host = EXCLUDED.remote_debugging_host,
    remote_debugging_port = EXCLUDED.remote_debugging_port,
    target_base_url = EXCLUDED.target_base_url,
    status = EXCLUDED.status,
    owner_agent = EXCLUDED.owner_agent,
    sensitivity = EXCLUDED.sensitivity,
    permission_level = EXCLUDED.permission_level,
    notes = EXCLUDED.notes,
    config = EXCLUDED.config,
    updated_at = now();

SELECT ops.attach_browser_profile_to_connector('tradingview_desktop_cdp', 'tradingview_mcp_connector', 'Jarvis')
WHERE EXISTS (SELECT 1 FROM core.source_connector_profiles WHERE connector_key = 'tradingview_mcp_connector');

SELECT ops.attach_browser_profile_to_connector('public_research_playwright', 'nse_filings_connector', 'Jarvis')
WHERE EXISTS (SELECT 1 FROM core.source_connector_profiles WHERE connector_key = 'nse_filings_connector');

SELECT ops.attach_browser_profile_to_connector('public_research_playwright', 'bse_filings_connector', 'Jarvis')
WHERE EXISTS (SELECT 1 FROM core.source_connector_profiles WHERE connector_key = 'bse_filings_connector');

SELECT ops.attach_browser_profile_to_connector('x_watchlist_manual_profile', 'x_watchlist_connector', 'Jarvis')
WHERE EXISTS (SELECT 1 FROM core.source_connector_profiles WHERE connector_key = 'x_watchlist_connector');

CREATE OR REPLACE VIEW ops.v_browser_profile_control AS
SELECT
    bp.id,
    bp.profile_key,
    bp.profile_name,
    bp.browser_name,
    bp.use_case,
    bp.profile_path,
    bp.remote_debugging_host,
    bp.remote_debugging_port,
    bp.target_base_url,
    bp.status,
    bp.owner_agent,
    bp.sensitivity,
    bp.permission_level,
    bp.health_status,
    bp.last_checked_at,
    bp.last_error,
    bp.notes,
    bp.config,
    coalesce(array_agg(bpcl.connector_key ORDER BY bpcl.connector_key) FILTER (WHERE bpcl.connector_key IS NOT NULL), ARRAY[]::TEXT[]) AS linked_connectors,
    bp.updated_at
FROM ops.browser_profiles bp
LEFT JOIN ops.browser_profile_connector_links bpcl
    ON bpcl.profile_key = bp.profile_key
   AND bpcl.link_status = 'active'
GROUP BY bp.id
ORDER BY
    CASE bp.health_status
        WHEN 'available' THEN 1
        WHEN 'profile_ready' THEN 2
        WHEN 'unchecked' THEN 3
        WHEN 'cdp_unavailable' THEN 4
        WHEN 'profile_missing' THEN 5
        ELSE 6
    END,
    bp.profile_key;

CREATE OR REPLACE VIEW ops.v_browser_connector_links AS
SELECT
    bpcl.id,
    bpcl.profile_key,
    bp.profile_name,
    bp.browser_name,
    bp.health_status AS profile_health_status,
    bp.remote_debugging_host,
    bp.remote_debugging_port,
    bpcl.connector_key,
    scp.connector_name,
    scp.source_key,
    scp.provider,
    scp.health_status AS connector_health_status,
    bpcl.link_status,
    bpcl.required_for,
    bpcl.owner_agent,
    bpcl.evidence,
    bpcl.updated_at
FROM ops.browser_profile_connector_links bpcl
JOIN ops.browser_profiles bp ON bp.profile_key = bpcl.profile_key
JOIN core.source_connector_profiles scp ON scp.connector_key = bpcl.connector_key
ORDER BY bpcl.connector_key;

CREATE OR REPLACE VIEW ops.v_browser_session_checks AS
SELECT DISTINCT ON (profile_key, coalesce(connector_key, ''), check_type)
    id,
    profile_key,
    connector_key,
    check_type,
    status,
    remote_debugging_host,
    remote_debugging_port,
    browser_label,
    target_base_url,
    error_message,
    sample_payload,
    checked_by,
    checked_at
FROM ops.browser_session_checks
ORDER BY profile_key, coalesce(connector_key, ''), check_type, checked_at DESC;

CREATE OR REPLACE FUNCTION core.run_source_connector_health_check(
    p_connector_key TEXT,
    p_actor TEXT DEFAULT 'Jarvis'
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    connector core.source_connector_profiles%ROWTYPE;
    latest_browser ops.browser_session_checks%ROWTYPE;
    v_browser_profile TEXT;
    v_status TEXT;
    v_error TEXT;
    v_rows_seen BIGINT;
    v_sample JSONB;
    v_result JSONB;
BEGIN
    SELECT * INTO connector
    FROM core.source_connector_profiles
    WHERE connector_key = p_connector_key;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'source connector not found: %', p_connector_key;
    END IF;

    v_browser_profile := nullif(connector.config->>'browser_profile', '');
    IF v_browser_profile IS NULL THEN
        SELECT profile_key INTO v_browser_profile
        FROM ops.browser_profile_connector_links
        WHERE connector_key = connector.connector_key
          AND link_status = 'active'
        ORDER BY updated_at DESC
        LIMIT 1;
    END IF;

    IF v_browser_profile IS NOT NULL THEN
        SELECT * INTO latest_browser
        FROM ops.browser_session_checks
        WHERE profile_key = v_browser_profile
          AND (connector_key = connector.connector_key OR connector_key IS NULL)
        ORDER BY
            CASE WHEN connector_key = connector.connector_key THEN 1 ELSE 2 END,
            checked_at DESC
        LIMIT 1;
    END IF;

    IF connector.status IN ('disabled', 'inactive', 'retired') THEN
        v_status := 'inactive';
        v_error := 'Connector is not enabled.';
        v_rows_seen := NULL;
    ELSIF connector.requires_api_key AND coalesce(connector.secret_ref, '') = '' THEN
        v_status := 'needs_secret';
        v_error := 'Connector requires credentials; store only secret_ref, never raw secrets.';
        v_rows_seen := NULL;
    ELSIF connector.requires_browser_session AND v_browser_profile IS NULL THEN
        v_status := 'needs_browser';
        v_error := 'Connector requires a browser session/profile before live checks.';
        v_rows_seen := NULL;
    ELSIF connector.requires_browser_session AND latest_browser.id IS NULL THEN
        v_status := 'needs_browser_check';
        v_error := 'Browser profile is attached, but no browser session check has been recorded yet.';
        v_rows_seen := NULL;
    ELSIF connector.requires_browser_session AND latest_browser.status NOT IN ('available', 'profile_ready') THEN
        v_status := 'browser_unavailable';
        v_error := coalesce(latest_browser.error_message, 'Browser profile check is not available.');
        v_rows_seen := NULL;
    ELSIF connector.status IN ('planned', 'candidate', 'mapped') THEN
        v_status := 'needs_activation';
        v_error := 'Connector is registered but not marked configured/active yet.';
        v_rows_seen := NULL;
    ELSE
        v_status := 'configured';
        v_error := NULL;
        v_rows_seen := 1;
    END IF;

    v_sample := jsonb_build_object(
        'source_key', connector.source_key,
        'connector_type', connector.connector_type,
        'provider', connector.provider,
        'access_mode', connector.access_mode,
        'base_url_present', coalesce(connector.base_url, '') <> '',
        'browser_profile', v_browser_profile,
        'browser_status', latest_browser.status,
        'secret_policy', CASE WHEN connector.requires_api_key THEN 'secret_ref_only' ELSE 'no_secret_required' END
    );

    INSERT INTO core.connector_health_checks (
        target_kind, target_key, check_name, check_type, status,
        rows_seen, error_message, sample_payload, checked_by
    )
    VALUES (
        'data_source_connector', connector.connector_key, 'source connector configuration check',
        'configuration', v_status, v_rows_seen, v_error, v_sample, coalesce(nullif(p_actor, ''), 'Jarvis')
    )
    RETURNING to_jsonb(core.connector_health_checks.*) INTO v_result;

    UPDATE core.source_connector_profiles
    SET health_status = v_status,
        last_checked_at = now(),
        last_latency_ms = NULL,
        last_rows_seen = v_rows_seen,
        last_error = v_error,
        updated_at = now()
    WHERE connector_key = connector.connector_key;

    RETURN v_result;
END;
$$;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_register_browser_profile', 'mcp_tool', 'Automation Engineer', 'write_db_manual_only', true, 'Register or update a browser profile for public research or TradingView control.', '{"writes":["ops.browser_profiles"],"secrets":"none"}'::jsonb),
    ('ai_os_attach_browser_profile', 'mcp_tool', 'Automation Engineer', 'write_db_manual_only', true, 'Attach a browser profile to a source connector and update connector browser requirements.', '{"writes":["ops.browser_profile_connector_links","core.source_connector_profiles"]}'::jsonb),
    ('ai_os_check_browser_profile', 'mcp_tool', 'Browser Research Runner', 'browser_read', true, 'Run a browser/CDP/profile readiness check and store evidence.', '{"writes":["ops.browser_session_checks"],"reads":["ops.browser_profiles"]}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

UPDATE core.control_plane_modules
SET warehouse_objects = ARRAY(
        SELECT DISTINCT obj
        FROM unnest(warehouse_objects || ARRAY[
            'ops.browser_profiles',
            'ops.browser_profile_connector_links',
            'ops.browser_session_checks',
            'ops.v_browser_profile_control',
            'ops.v_browser_connector_links',
            'ops.v_browser_session_checks'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_register_browser_profile',
            'ai_os_attach_browser_profile',
            'ai_os_check_browser_profile'
        ]::TEXT[]) AS tool
    ),
    next_action = 'Use browser profiles and session checks before marking browser-dependent connectors live.',
    updated_at = now()
WHERE module_key IN ('data_sources', 'trading_desk', 'research_inbox');

