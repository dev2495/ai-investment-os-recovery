BEGIN;
CREATE OR REPLACE VIEW ops.v_doctor_latest AS
SELECT registry.check_key,registry.check_name,registry.component,
       coalesce(result.status,'not_run') AS status,
       coalesce(result.severity,registry.failure_severity) AS severity,
       result.headline,result.observed,result.evidence,result.actionable_fix,
       result.last_known_good_at,result.observed_at,result.duration_ms,
       run.run_key,run.mode,run.status AS run_status,run.requested_by,
       false AS broker_write_allowed
FROM ops.doctor_check_registry registry
LEFT JOIN LATERAL (
    SELECT value.* FROM ops.doctor_check_results value
    WHERE value.check_key=registry.check_key ORDER BY value.observed_at DESC,value.id DESC LIMIT 1
) result ON true
LEFT JOIN ops.doctor_runs run ON run.id=result.doctor_run_id
WHERE registry.enabled;
INSERT INTO core.schema_migrations(migration_number,migration_key,definition_checksum_sha256,description,metadata)
VALUES(266,'266_doctor_unrun_identity_v1',encode(sha256(convert_to('266_doctor_unrun_identity_v1','UTF8')),'hex'),
 'Preserve Doctor registry identities before the first observed check; explicitly not run',
 '{"synthetic_healthy":false,"broker_write_allowed":false}') ON CONFLICT(migration_number) DO NOTHING;
DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM core.schema_migrations WHERE migration_number=266
  AND migration_key='266_doctor_unrun_identity_v1'
  AND definition_checksum_sha256=encode(sha256(convert_to('266_doctor_unrun_identity_v1','UTF8')),'hex')) THEN
  RAISE EXCEPTION 'migration 266 ledger mismatch';
 END IF;
END $$;
COMMIT;
