BEGIN;

UPDATE ops.browser_profiles
SET profile_name = 'TradingView Managed Browser CDP',
    browser_name = 'Chrome for Testing - TradingView',
    use_case = 'TradingView chart automation, screenshots, indicators, formula charts, and governed chart workflows',
    profile_path = '/Volumes/Devarsh SSD/AI OS Data/browser-profiles/tradingview-cft',
    remote_debugging_host = '127.0.0.1',
    remote_debugging_port = 9333,
    status = 'configured',
    permission_level = 'browser_chart_control_gated',
    notes = 'Primary backend is a Playwright-managed Chrome for Testing profile on the external SSD. TradingView Desktop port 9222 remains an optional secondary backend. Broker execution remains disabled.',
    config = coalesce(config, '{}'::jsonb) || jsonb_build_object(
        'backend', 'chrome_for_testing',
        'primary_cdp_port', 9333,
        'secondary_desktop_cdp_port', 9222,
        'profile_storage', 'external_ssd',
        'execution_allowed', false,
        'requires_human_gate_for', jsonb_build_array('alert_create', 'alert_delete', 'ui_evaluate', 'tab_close', 'broker_order')
    ),
    updated_at = now()
WHERE profile_key = 'tradingview_desktop_cdp';

UPDATE core.department_provider_policies
SET guardrails = coalesce(guardrails, '{}'::jsonb) || '{"requires_cdp_port":9333,"backend":"chrome_for_testing"}'::jsonb,
    reason = 'TradingView chart control is blocked until the managed browser CDP endpoint and artifact quality gate are available.',
    updated_at = now()
WHERE policy_key = 'global-tradingview-browser-block-until-ready';

COMMIT;
