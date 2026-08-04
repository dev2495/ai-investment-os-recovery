BEGIN;

CREATE OR REPLACE FUNCTION research.open_real_company_acceptance_run(
    p_run_key TEXT,
    p_company_id BIGINT,
    p_holding_thesis_id BIGINT,
    p_dossier_version_id BIGINT,
    p_data_as_of TIMESTAMPTZ,
    p_started_by TEXT
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_verification_evidence_id BIGINT;
    v_existing_company_id BIGINT;
    v_run_id BIGINT;
BEGIN
    SELECT company.real_company_verification_evidence_id
    INTO v_verification_evidence_id
    FROM research.companies company
    JOIN research.fundamental_evidence evidence
      ON evidence.id=company.real_company_verification_evidence_id
     AND evidence.company_id=company.id
     AND evidence.verification_status='human_verified'
    WHERE company.id=p_company_id
      AND company.status='active'
      AND company.real_company_verified_at IS NOT NULL;

    IF v_verification_evidence_id IS NULL THEN
        RAISE EXCEPTION 'company % is not verified as a real company with human-verified evidence',p_company_id;
    END IF;

    SELECT company_id INTO v_existing_company_id
    FROM research.fundamental_acceptance_runs
    WHERE run_key=p_run_key;

    IF v_existing_company_id IS NOT NULL AND v_existing_company_id<>p_company_id THEN
        RAISE EXCEPTION 'fundamental acceptance run_key % already belongs to company %',p_run_key,v_existing_company_id;
    END IF;

    INSERT INTO research.fundamental_acceptance_runs (
        run_key,company_id,holding_thesis_id,dossier_version_id,run_status,
        real_company_verified,verification_evidence_id,data_as_of,started_by,
        started_at,completed_at,notes
    ) VALUES (
        p_run_key,p_company_id,p_holding_thesis_id,p_dossier_version_id,'opened',
        true,v_verification_evidence_id,p_data_as_of,p_started_by,now(),NULL,NULL
    )
    ON CONFLICT (run_key) DO UPDATE SET
        holding_thesis_id=EXCLUDED.holding_thesis_id,
        dossier_version_id=EXCLUDED.dossier_version_id,
        run_status='opened',
        real_company_verified=true,
        verification_evidence_id=EXCLUDED.verification_evidence_id,
        data_as_of=EXCLUDED.data_as_of,
        started_by=EXCLUDED.started_by,
        started_at=now(),
        completed_at=NULL,
        notes=NULL
    RETURNING id INTO v_run_id;

    RETURN v_run_id;
END;
$$;

COMMENT ON FUNCTION research.open_real_company_acceptance_run IS
    'Opens or replay-safely refreshes one real-company acceptance run. A run key cannot move between companies.';

COMMIT;
