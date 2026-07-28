BEGIN;

ALTER TABLE agent.response_evidence_ledger
    DROP CONSTRAINT IF EXISTS response_evidence_ledger_evidence_status_check;

ALTER TABLE agent.response_evidence_ledger
    ADD CONSTRAINT response_evidence_ledger_evidence_status_check
    CHECK (evidence_status IN (
        'deterministic_source_snapshot',
        'source_backed_unverified',
        'unverified',
        'conflicted',
        'warehouse_verified',
        'warehouse_partial'
    ));

COMMIT;
