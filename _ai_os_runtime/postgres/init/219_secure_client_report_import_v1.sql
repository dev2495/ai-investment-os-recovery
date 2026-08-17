BEGIN;

CREATE TABLE IF NOT EXISTS client_data.client_access_grants (
    id BIGSERIAL PRIMARY KEY,
    actor TEXT NOT NULL,
    client_id BIGINT NOT NULL REFERENCES portfolio.clients(id),
    scopes TEXT[] NOT NULL DEFAULT ARRAY['portfolio_read']::text[],
    granted_by TEXT NOT NULL,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ,
    active BOOLEAN NOT NULL DEFAULT true,
    reason TEXT NOT NULL,
    UNIQUE (actor, client_id)
);

CREATE INDEX IF NOT EXISTS idx_client_access_grants_actor
    ON client_data.client_access_grants (lower(actor), active, client_id);

INSERT INTO client_data.client_access_grants (actor, client_id, scopes, granted_by, reason)
SELECT
    'Devarsh',
    client.id,
    ARRAY['portfolio_read','portfolio_import','portfolio_reconcile','portfolio_identity_review']::text[],
    'AI OS operator bootstrap',
    'Single-operator private office access. Future users require an explicit client-scoped grant.'
FROM portfolio.clients client
WHERE client.active
ON CONFLICT (actor, client_id) DO UPDATE SET
    scopes = EXCLUDED.scopes,
    active = true,
    reason = EXCLUDED.reason;

CREATE TABLE IF NOT EXISTS client_data.client_source_identities (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES portfolio.clients(id),
    account_id BIGINT NOT NULL REFERENCES portfolio.accounts(id),
    broker TEXT NOT NULL,
    source_identity_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'verified' CHECK (status IN ('pending','verified','rejected','superseded')),
    verified_by TEXT,
    verified_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (broker, source_identity_hash)
);

CREATE TABLE IF NOT EXISTS client_data.secure_client_imports (
    id BIGSERIAL PRIMARY KEY,
    import_key TEXT NOT NULL UNIQUE,
    client_id BIGINT NOT NULL REFERENCES portfolio.clients(id),
    account_id BIGINT NOT NULL REFERENCES portfolio.accounts(id),
    broker TEXT NOT NULL,
    report_kind TEXT NOT NULL CHECK (report_kind IN (
        'aditya_birla_money_capital_gains','broker_transactions','holdings_statement',
        'broker_ledger','contract_note','portfolio_snapshot','tax_report','browser_visible_capture','other'
    )),
    original_file_name TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    file_bytes BIGINT NOT NULL CHECK (file_bytes > 0),
    mime_type TEXT NOT NULL,
    sensitivity TEXT NOT NULL DEFAULT 'client_private' CHECK (sensitivity = 'client_private'),
    immutable BOOLEAN NOT NULL DEFAULT true,
    parser_key TEXT NOT NULL DEFAULT 'secure_client_report_v1',
    parser_version TEXT NOT NULL DEFAULT '1.0.0',
    status TEXT NOT NULL DEFAULT 'quarantined' CHECK (status IN (
        'quarantined','stored_unparsed','parsed','needs_identity_review',
        'blocked_identity_mismatch','reconciled','rejected','failed'
    )),
    identity_status TEXT NOT NULL DEFAULT 'unresolved' CHECK (identity_status IN (
        'unresolved','needs_review','resolved','mismatch','not_present'
    )),
    source_identity_hash TEXT,
    source_period_start DATE,
    source_period_end DATE,
    source_as_of TIMESTAMPTZ,
    transaction_count INTEGER NOT NULL DEFAULT 0,
    lot_count INTEGER NOT NULL DEFAULT 0,
    charge_count INTEGER NOT NULL DEFAULT 0,
    tax_summary_count INTEGER NOT NULL DEFAULT 0,
    exception_count INTEGER NOT NULL DEFAULT 0,
    reconciliation_status TEXT NOT NULL DEFAULT 'not_run' CHECK (reconciliation_status IN (
        'not_run','matched','breaks','incomplete','blocked'
    )),
    reconciliation_difference NUMERIC,
    quality_flags TEXT[] NOT NULL DEFAULT ARRAY[]::text[],
    coverage JSONB NOT NULL DEFAULT '{}'::jsonb,
    parser_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    raw_artifact_id BIGINT REFERENCES core.raw_artifacts(id),
    received_by TEXT NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    parsed_at TIMESTAMPTZ,
    reconciled_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (client_id, account_id, sha256, report_kind)
);

CREATE INDEX IF NOT EXISTS idx_secure_client_imports_client
    ON client_data.secure_client_imports (client_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_secure_client_imports_status
    ON client_data.secure_client_imports (status, identity_status, received_at DESC);

CREATE TABLE IF NOT EXISTS client_data.client_import_rows (
    id BIGSERIAL PRIMARY KEY,
    import_id BIGINT NOT NULL REFERENCES client_data.secure_client_imports(id) ON DELETE CASCADE,
    row_number INTEGER NOT NULL,
    row_hash TEXT NOT NULL,
    layer TEXT NOT NULL CHECK (layer IN ('transaction','tax_lot','holding','fund_balance','charge','tax_summary','corporate_action','cash')),
    symbol TEXT,
    isin TEXT,
    instrument_name TEXT,
    transaction_type TEXT,
    purchase_date DATE,
    sale_date DATE,
    transaction_date DATE,
    quantity NUMERIC,
    average_price NUMERIC,
    market_price NUMERIC,
    market_value NUMERIC,
    cash_balance NUMERIC,
    available_funds NUMERIC,
    collateral_value NUMERIC,
    buy_price NUMERIC,
    buy_value NUMERIC,
    sell_price NUMERIC,
    sell_value NUMERIC,
    holding_period_days INTEGER,
    realized_gain NUMERIC,
    speculative_gain NUMERIC,
    taxable_gain NUMERIC,
    short_term_gain NUMERIC,
    long_term_gain NUMERIC,
    total_charges NUMERIC,
    tax_period TEXT,
    normalized_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (import_id, layer, row_hash)
);

CREATE INDEX IF NOT EXISTS idx_client_import_rows_import_layer
    ON client_data.client_import_rows (import_id, layer, row_number);
CREATE INDEX IF NOT EXISTS idx_client_import_rows_symbol_dates
    ON client_data.client_import_rows (symbol, purchase_date, sale_date);

CREATE TABLE IF NOT EXISTS client_data.client_import_derived_lots (
    id BIGSERIAL PRIMARY KEY,
    import_id BIGINT NOT NULL REFERENCES client_data.secure_client_imports(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    opening_row_hash TEXT NOT NULL,
    purchase_date DATE NOT NULL,
    original_quantity NUMERIC NOT NULL CHECK (original_quantity > 0),
    remaining_quantity NUMERIC NOT NULL CHECK (remaining_quantity > 0),
    unit_cost NUMERIC,
    remaining_cost_basis NUMERIC,
    methodology TEXT NOT NULL DEFAULT 'FIFO over source-covered transaction rows only',
    quality_status TEXT NOT NULL CHECK (quality_status IN ('complete_for_covered_period','missing_cost','opening_history_incomplete')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (import_id, symbol, opening_row_hash)
);

CREATE TABLE IF NOT EXISTS client_data.client_import_reconciliation_matches (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES portfolio.accounts(id),
    capital_gain_import_id BIGINT NOT NULL REFERENCES client_data.secure_client_imports(id) ON DELETE CASCADE,
    transaction_import_id BIGINT REFERENCES client_data.secure_client_imports(id) ON DELETE CASCADE,
    capital_gain_row_id BIGINT NOT NULL REFERENCES client_data.client_import_rows(id) ON DELETE CASCADE,
    transaction_row_id BIGINT REFERENCES client_data.client_import_rows(id) ON DELETE CASCADE,
    match_status TEXT NOT NULL CHECK (match_status IN ('matched','ambiguous','unmatched')),
    confidence NUMERIC NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    quantity_difference NUMERIC,
    price_difference NUMERIC,
    value_difference NUMERIC,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (capital_gain_import_id, capital_gain_row_id)
);

CREATE TABLE IF NOT EXISTS client_data.client_import_exceptions (
    id BIGSERIAL PRIMARY KEY,
    import_id BIGINT NOT NULL REFERENCES client_data.secure_client_imports(id) ON DELETE CASCADE,
    row_number INTEGER,
    row_hash TEXT,
    exception_code TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('info','warning','error','blocking')),
    field_name TEXT,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','accepted','resolved','rejected')),
    resolution_note TEXT,
    resolved_by TEXT,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE NULLS NOT DISTINCT (import_id, row_number, exception_code, field_name)
);

CREATE INDEX IF NOT EXISTS idx_client_import_exceptions_open
    ON client_data.client_import_exceptions (import_id, status, severity, exception_code);

CREATE TABLE IF NOT EXISTS client_data.client_import_audit (
    id BIGSERIAL PRIMARY KEY,
    import_id BIGINT NOT NULL REFERENCES client_data.secure_client_imports(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    event_status TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE VIEW client_data.v_secure_client_import_control AS
SELECT
    import.id,
    import.import_key,
    client.client_code,
    client.display_name,
    account.account_code,
    account.account_name,
    import.broker,
    import.report_kind,
    import.sha256,
    left(import.sha256, 12) AS checksum_prefix,
    import.file_bytes,
    import.mime_type,
    import.immutable,
    import.parser_key,
    import.parser_version,
    import.status,
    import.identity_status,
    import.source_period_start,
    import.source_period_end,
    import.source_as_of,
    import.transaction_count,
    import.lot_count,
    import.charge_count,
    import.tax_summary_count,
    import.exception_count,
    import.reconciliation_status,
    import.reconciliation_difference,
    import.quality_flags,
    import.coverage,
    import.parser_summary,
    import.received_by,
    import.received_at,
    import.parsed_at,
    import.reconciled_at,
    import.updated_at,
    coalesce((
        SELECT jsonb_object_agg(summary.exception_code, summary.exception_count)
        FROM (
            SELECT exception.exception_code, count(*) AS exception_count
            FROM client_data.client_import_exceptions exception
            WHERE exception.import_id = import.id AND exception.status = 'open'
            GROUP BY exception.exception_code
        ) summary
    ), '{}'::jsonb) AS open_exception_summary
FROM client_data.secure_client_imports import
JOIN portfolio.clients client ON client.id = import.client_id
JOIN portfolio.accounts account ON account.id = import.account_id
ORDER BY import.received_at DESC;

CREATE OR REPLACE VIEW client_data.v_client_import_exception_control AS
SELECT
    exception.id,
    import.import_key,
    client.client_code,
    exception.row_number,
    exception.exception_code,
    exception.severity,
    exception.field_name,
    exception.message,
    exception.status,
    exception.resolution_note,
    exception.resolved_by,
    exception.resolved_at,
    exception.created_at
FROM client_data.client_import_exceptions exception
JOIN client_data.secure_client_imports import ON import.id = exception.import_id
JOIN portfolio.clients client ON client.id = import.client_id
ORDER BY
    CASE exception.severity WHEN 'blocking' THEN 1 WHEN 'error' THEN 2 WHEN 'warning' THEN 3 ELSE 4 END,
    exception.row_number NULLS FIRST,
    exception.id;

CREATE OR REPLACE VIEW client_data.v_client_import_derived_holdings AS
SELECT
    import.import_key,
    client.client_code,
    client.display_name,
    account.account_code,
    account.account_name,
    lot.symbol,
    sum(lot.remaining_quantity) AS derived_quantity,
    min(lot.purchase_date) AS earliest_open_buy_date,
    max(lot.purchase_date) AS latest_open_buy_date,
    sum(lot.remaining_cost_basis) AS derived_cost_basis,
    CASE WHEN sum(lot.remaining_quantity) <> 0
         THEN sum(lot.remaining_cost_basis) / sum(lot.remaining_quantity) END AS derived_average_cost,
    count(*) AS open_lot_count,
    CASE WHEN bool_and(lot.quality_status='complete_for_covered_period')
         THEN 'complete_for_covered_period' ELSE 'incomplete' END AS quality_status,
    min(import.source_period_start) AS source_period_start,
    max(import.source_period_end) AS source_period_end,
    'FIFO over imported transaction rows; opening history before source period is not estimated'::text AS methodology
FROM client_data.client_import_derived_lots lot
JOIN client_data.secure_client_imports import ON import.id=lot.import_id
JOIN portfolio.clients client ON client.id=import.client_id
JOIN portfolio.accounts account ON account.id=import.account_id
WHERE import.identity_status='resolved'
GROUP BY import.import_key,client.client_code,client.display_name,account.account_code,
         account.account_name,lot.symbol;

CREATE OR REPLACE VIEW client_data.v_client_import_reconciliation_control AS
SELECT
    capital.import_key AS capital_gain_import_key,
    max(transaction_import.import_key) AS transaction_import_key,
    client.client_code,
    account.account_code,
    count(*) AS capital_gain_lot_rows,
    count(*) FILTER (WHERE match.match_status='matched') AS matched_rows,
    count(*) FILTER (WHERE match.match_status='ambiguous') AS ambiguous_rows,
    count(*) FILTER (WHERE match.match_status='unmatched') AS unmatched_rows,
    sum(abs(coalesce(match.value_difference,0))) AS absolute_value_difference,
    min(match.created_at) AS reconciled_at,
    'Sale date + absolute quantity, then price/value tolerance; unmatched rows remain exceptions'::text AS methodology
FROM client_data.client_import_reconciliation_matches match
JOIN client_data.secure_client_imports capital ON capital.id=match.capital_gain_import_id
LEFT JOIN client_data.secure_client_imports transaction_import ON transaction_import.id=match.transaction_import_id
JOIN portfolio.clients client ON client.id=capital.client_id
JOIN portfolio.accounts account ON account.id=match.account_id
GROUP BY capital.import_key,client.client_code,account.account_code;

COMMENT ON TABLE client_data.secure_client_imports IS
    'Immutable, checksum-addressed client report intake. Raw source rows remain client_private and are never logged by the API.';
COMMENT ON TABLE client_data.client_import_rows IS
    'Normalized client report evidence. Promotion into canonical trades, holdings, cash, or NAV requires identity resolution and reconciliation.';

COMMIT;
