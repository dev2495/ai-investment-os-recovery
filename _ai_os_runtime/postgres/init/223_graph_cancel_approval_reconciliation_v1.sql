BEGIN;

-- A cancelled graph cannot leave a live approval card behind. Keep the
-- decision record, but close it as cancelled rather than implying a human
-- approved or rejected the underlying research case.
WITH orphaned AS (
    SELECT DISTINCT approval.id
    FROM agent.graph_runs graph_run
    JOIN agent.graph_node_runs node_run ON node_run.graph_run_id=graph_run.id
    JOIN agent.approvals approval ON approval.id=node_run.approval_id
    WHERE graph_run.run_status='cancelled'
      AND approval.status='pending'
)
UPDATE agent.approvals approval
SET status='cancelled',
    decided_by='Graph cancellation reconciliation',
    decided_at=now(),
    rationale=concat_ws(E'\n',nullif(approval.rationale,''),
        'Cancelled because the linked graph run was cancelled; no approval decision was made.')
FROM orphaned
WHERE approval.id=orphaned.id;

CREATE OR REPLACE VIEW agent.v_orphaned_graph_approvals AS
SELECT graph_run.id AS graph_run_id,graph_run.graph_key,graph_run.run_status,
       node_run.id AS graph_node_run_id,node_run.status AS node_status,
       approval.id AS approval_id,approval.status AS approval_status,
       approval.created_at
FROM agent.graph_runs graph_run
JOIN agent.graph_node_runs node_run ON node_run.graph_run_id=graph_run.id
JOIN agent.approvals approval ON approval.id=node_run.approval_id
WHERE graph_run.run_status IN ('cancelled','failed','completed')
  AND approval.status='pending';

COMMENT ON VIEW agent.v_orphaned_graph_approvals IS
'Integrity monitor: terminal graph runs must not retain pending human approvals.';

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM agent.v_orphaned_graph_approvals) THEN
        RAISE EXCEPTION 'terminal graph runs still have pending approvals';
    END IF;
END $$;

COMMIT;
