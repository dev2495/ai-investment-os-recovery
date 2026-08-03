BEGIN;

UPDATE ops.browser_profiles
SET profile_name = 'TradingView Desktop (user managed)',
    browser_name = 'TradingView Desktop',
    use_case = 'Open governed chart and template links in the user signed-in TradingView Desktop application',
    profile_path = NULL,
    remote_debugging_host = NULL,
    remote_debugging_port = NULL,
    status = 'retired',
    permission_level = 'native_desktop_handoff_only',
    notes = 'The separate managed Chromium/CDP TradingView profile is retired. The AI OS may hand chart links to the existing user-managed TradingView Desktop app. It is not an authoritative market-data source and cannot place broker orders.',
    config = jsonb_build_object(
        'backend', 'native_desktop',
        'session_state', 'user_managed',
        'interaction_mode', 'clipboard_menu',
        'managed_browser_allowed', false,
        'cdp_allowed', false,
        'authoritative_market_data', false,
        'execution_allowed', false,
        'broker_order_allowed', false
    ),
    updated_at = now()
WHERE profile_key = 'tradingview_desktop_cdp';

UPDATE core.department_provider_policies
SET status = 'retired',
    guardrails = jsonb_build_object(
        'backend', 'native_desktop',
        'session_state', 'user_managed',
        'managed_browser_allowed', false,
        'authoritative_market_data', false,
        'broker_order_allowed', false
    ),
    reason = 'The managed TradingView browser is retired. Chart requests use the signed-in native Desktop application; warehouse data and broker execution remain separate.',
    updated_at = now()
WHERE policy_key = 'global-tradingview-browser-block-until-ready';

UPDATE core.mcp_integration_registry
SET status = 'retired',
    risk_notes = 'Retired: separate managed browser/CDP control is replaced by native TradingView Desktop handoff.',
    config = config || jsonb_build_object('managed_browser_allowed', false, 'authoritative_market_data', false, 'broker_order_allowed', false),
    updated_at = now()
WHERE integration_key IN ('tradingview_data_mcp_candidate', 'tradingview_desktop_mcp_candidate');

COMMIT;
