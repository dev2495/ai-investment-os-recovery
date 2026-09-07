BEGIN;
ALTER TABLE research.research_cases ADD COLUMN IF NOT EXISTS validated_handoffs jsonb NOT NULL DEFAULT '{}';

-- The handoff transition and every linked update commit together. These are
-- evidence attachments, never a research or investment approval.
CREATE OR REPLACE FUNCTION agent.propagate_validated_handoff() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE parent agent.tasks; receipt agent.runtime_output_receipts; case_id bigint; packet_id bigint; attachment jsonb;
BEGIN
    IF NEW.state<>'VALIDATED' OR OLD.state='VALIDATED' THEN RETURN NEW; END IF;
    SELECT * INTO parent FROM agent.tasks WHERE id=NEW.parent_task_id FOR UPDATE;
    SELECT * INTO receipt FROM agent.runtime_output_receipts WHERE id=NEW.receipt_id;
    IF receipt.validated_at IS NULL OR receipt.validated_by IS DISTINCT FROM NEW.validated_by
      OR parent.runtime_scope<>NEW.runtime_scope OR parent.client_id IS DISTINCT FROM NEW.client_id
      OR parent.book_id IS DISTINCT FROM NEW.book_id THEN RAISE EXCEPTION 'validated handoff scope mismatch'; END IF;
    attachment:=jsonb_build_object('handoff_id',NEW.id,'receipt_id',receipt.id,'artifact_ref',receipt.artifact_ref,
      'evidence_refs',receipt.evidence_refs,'validated_by',NEW.validated_by,'validated_at',NEW.validated_at,
      'research_readiness_changed',false);
    UPDATE agent.tasks SET runtime_context=jsonb_set(runtime_context,'{validated_handoffs}',
      coalesce(runtime_context->'validated_handoffs','{}')||jsonb_build_object(NEW.id::text,attachment)),
      updated_at=clock_timestamp() WHERE id=parent.id;
    IF coalesce(parent.runtime_context->>'research_case_id','') ~ '^[1-9][0-9]{0,17}$' THEN
      case_id:=(parent.runtime_context->>'research_case_id')::bigint;
      -- The canonical research registry is house-only; client/book work cannot
      -- project into it without a separately scoped research-case contract.
      IF NEW.client_id IS NOT NULL OR NEW.book_id IS NOT NULL OR NEW.runtime_scope<>'internal' THEN
        RAISE EXCEPTION 'house research case cannot receive scoped client handoff'; END IF;
      UPDATE research.research_cases SET validated_handoffs=validated_handoffs||jsonb_build_object(NEW.id::text,attachment),
        updated_at=clock_timestamp() WHERE id=case_id;
      IF NOT FOUND THEN RAISE EXCEPTION 'linked research case missing'; END IF;
    END IF;
    IF coalesce(parent.runtime_context->>'committee_packet_id','') ~ '^[1-9][0-9]{0,17}$' THEN
      packet_id:=(parent.runtime_context->>'committee_packet_id')::bigint;
      UPDATE agent.committee_packets SET metadata=jsonb_set(metadata,'{validated_handoffs}',
        coalesce(metadata->'validated_handoffs','{}')||jsonb_build_object(NEW.id::text,attachment)),
        updated_at=clock_timestamp() WHERE id=packet_id AND runtime_scope=NEW.runtime_scope
        AND client_id IS NOT DISTINCT FROM NEW.client_id AND book_id IS NOT DISTINCT FROM NEW.book_id;
      IF NOT FOUND THEN RAISE EXCEPTION 'linked committee scope mismatch'; END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE OR REPLACE TRIGGER validated_handoff_propagation AFTER UPDATE OF state ON agent.task_handoffs
FOR EACH ROW EXECUTE FUNCTION agent.propagate_validated_handoff();

-- Recovery is derived from persisted tasks, leases and receipts after restart;
-- it never fabricates acknowledgements or independent validation.
CREATE OR REPLACE VIEW agent.v_handoff_recovery AS
SELECT h.*, CASE
 WHEN h.state='REQUESTED' THEN 'acknowledge'
 WHEN h.state='ACKNOWLEDGED' THEN 'accept'
 WHEN h.state='RETURNED' THEN 'independent_validation'
 WHEN t.status='needs_review' AND EXISTS(SELECT 1 FROM agent.runtime_output_receipts r WHERE r.task_id=t.id)
   THEN 'return_receipt'
 WHEN t.status IN ('failed','cancelled') THEN 'reconcile_terminal_child'
 WHEN EXISTS(SELECT 1 FROM agent.task_leases l WHERE l.task_id=t.id AND l.status='ACTIVE' AND l.expires_at>clock_timestamp())
   THEN 'wait_for_worker'
 ELSE 'resume_same_child' END recovery_action
FROM agent.task_handoffs h JOIN agent.tasks t ON t.id=h.child_task_id
WHERE h.state NOT IN ('VALIDATED','FAILED','CANCELLED','REJECTED');
DO $$ BEGIN
 IF to_regclass('core.schema_migrations') IS NOT NULL THEN
 INSERT INTO core.schema_migrations(migration_number,migration_key,definition_checksum_sha256,description,metadata)
 VALUES(263,'263_handoff_parent_propagation_v1','e64c22ea974c0236e85b0abb2de5a9b86c907a09bc7ae4fb993f966845b34cc2',
 'Atomic validated handoff attachments and durable recovery projection','{"broker_write_allowed":false}')
 ON CONFLICT(migration_number) DO NOTHING;
 IF NOT EXISTS(SELECT 1 FROM core.schema_migrations WHERE migration_number=263
 AND migration_key='263_handoff_parent_propagation_v1'
 AND definition_checksum_sha256='e64c22ea974c0236e85b0abb2de5a9b86c907a09bc7ae4fb993f966845b34cc2') THEN
 RAISE EXCEPTION 'migration 263 ledger mismatch'; END IF;
 END IF;
END $$;
COMMIT;
