BEGIN;

CREATE TABLE IF NOT EXISTS ops.zerodha_auth_challenges (
    id BIGSERIAL PRIMARY KEY,
    challenge_hash TEXT NOT NULL UNIQUE,
    requested_by TEXT NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    callback_status TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (expires_at > requested_at)
);

CREATE INDEX IF NOT EXISTS zerodha_auth_challenges_pending_idx
    ON ops.zerodha_auth_challenges (expires_at)
    WHERE consumed_at IS NULL;

COMMIT;
