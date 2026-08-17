BEGIN;

ALTER TABLE client_data.secure_client_imports
    DROP CONSTRAINT IF EXISTS secure_client_imports_report_kind_check;
ALTER TABLE client_data.secure_client_imports
    ADD CONSTRAINT secure_client_imports_report_kind_check CHECK (report_kind IN (
        'aditya_birla_money_capital_gains','broker_transactions','holdings_statement',
        'broker_ledger','contract_note','portfolio_snapshot','tax_report','browser_visible_capture','other'
    ));

ALTER TABLE client_data.client_import_rows
    DROP CONSTRAINT IF EXISTS client_import_rows_layer_check;
ALTER TABLE client_data.client_import_rows
    ADD CONSTRAINT client_import_rows_layer_check CHECK (layer IN (
        'transaction','tax_lot','holding','fund_balance','charge','tax_summary','corporate_action','cash'
    ));
ALTER TABLE client_data.client_import_rows ADD COLUMN IF NOT EXISTS average_price NUMERIC;
ALTER TABLE client_data.client_import_rows ADD COLUMN IF NOT EXISTS market_price NUMERIC;
ALTER TABLE client_data.client_import_rows ADD COLUMN IF NOT EXISTS market_value NUMERIC;
ALTER TABLE client_data.client_import_rows ADD COLUMN IF NOT EXISTS cash_balance NUMERIC;
ALTER TABLE client_data.client_import_rows ADD COLUMN IF NOT EXISTS available_funds NUMERIC;
ALTER TABLE client_data.client_import_rows ADD COLUMN IF NOT EXISTS collateral_value NUMERIC;

CREATE TABLE IF NOT EXISTS client_data.client_browser_capture_sessions (
    id BIGSERIAL PRIMARY KEY,
    capture_key TEXT NOT NULL UNIQUE,
    import_id BIGINT NOT NULL REFERENCES client_data.secure_client_imports(id) ON DELETE CASCADE,
    client_id BIGINT NOT NULL REFERENCES portfolio.clients(id),
    account_id BIGINT NOT NULL REFERENCES portfolio.accounts(id),
    source_key TEXT NOT NULL CHECK (source_key IN (
        'aditya_birla_money_authenticated_portfolio','zerodha_authenticated_portfolio',
        'authorized_broker_portfolio','authorized_portfolio_tracker'
    )),
    page_title TEXT,
    captured_at TIMESTAMPTZ NOT NULL,
    consent_actor TEXT NOT NULL,
    consent_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    capture_scope TEXT NOT NULL DEFAULT 'user_selected_visible_content',
    content_type TEXT NOT NULL CHECK (content_type IN ('text/html','text/plain')),
    sanitized BOOLEAN NOT NULL DEFAULT true CHECK (sanitized),
    credentials_captured BOOLEAN NOT NULL DEFAULT false CHECK (NOT credentials_captured),
    browser_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (NOT browser_write_allowed),
    status TEXT NOT NULL DEFAULT 'captured' CHECK (status IN (
        'captured','parsed','needs_review','approved_preview','rejected','failed'
    )),
    retry_count INTEGER NOT NULL DEFAULT 0,
    field_mapping JSONB NOT NULL DEFAULT '{}'::jsonb,
    preview_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_client_browser_capture_sessions_client
    ON client_data.client_browser_capture_sessions (client_id, captured_at DESC);

CREATE OR REPLACE VIEW client_data.v_client_browser_capture_control AS
SELECT capture.capture_key,import.import_key,client.client_code,client.display_name,
       account.account_code,account.account_name,capture.source_key,capture.page_title,
       capture.captured_at,capture.consent_actor,capture.consent_at,capture.capture_scope,
       capture.content_type,capture.sanitized,capture.credentials_captured,
       capture.browser_write_allowed,capture.status,capture.retry_count,
       capture.field_mapping,capture.preview_summary,capture.last_error,
       left(import.sha256,12) checksum_prefix,import.identity_status,
       import.reconciliation_status,import.exception_count,import.updated_at
FROM client_data.client_browser_capture_sessions capture
JOIN client_data.secure_client_imports import ON import.id=capture.import_id
JOIN portfolio.clients client ON client.id=capture.client_id
JOIN portfolio.accounts account ON account.id=capture.account_id
ORDER BY capture.captured_at DESC;

COMMENT ON TABLE client_data.client_browser_capture_sessions IS
    'Explicit user-initiated capture of selected visible browser content. URLs, cookies, credentials, hidden fields, scripts, and broker writes are excluded.';

COMMIT;
