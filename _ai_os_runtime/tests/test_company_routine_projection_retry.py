from _ai_os_runtime.api.routine_runtime import RoutineRuntime
from _ai_os_runtime.tests.test_routine_runtime import FakeRoutineDatabase


def test_projection_receipt_only_after_success_and_restart_retries():
    db = FakeRoutineDatabase()
    pending = [{'run_key': 'stable', 'artifact': {}, 'managed_note_path': 'managed'}]
    def query(sql):
        if 'routine:definition' in sql:
            return db.query(sql)
        return pending if "projection_status='pending'" in sql else []
    def statement(sql):
        if 'UPDATE agent.company_routine_outputs' in sql:
            pending.clear()
        return []
    def fail(row):
        raise OSError('vault unavailable')
    first = RoutineRuntime(query, statement, artifact_writer=lambda *a: {}, note_projector=fail)
    assert first.dispatch_company_events()['status'] == 'partial'
    assert len(pending) == 1
    writes = []
    restarted = RoutineRuntime(query, statement, artifact_writer=lambda *a: {}, note_projector=lambda row: writes.append(row))
    assert restarted.dispatch_company_events()['status'] == 'completed'
    assert restarted.dispatch_company_events()['status'] == 'completed'
    assert len(writes) == 1
