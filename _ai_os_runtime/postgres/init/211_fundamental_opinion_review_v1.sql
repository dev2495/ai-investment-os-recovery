BEGIN;

ALTER TABLE research.fundamental_specialist_opinions
    ADD COLUMN IF NOT EXISTS reviewed_by TEXT,
    ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS review_rationale TEXT;

COMMENT ON COLUMN research.fundamental_specialist_opinions.review_rationale IS
    'Explicit operator rationale for reviewed, dissent, or rejected specialist opinions. Review never authorizes capital or broker action.';

COMMIT;
