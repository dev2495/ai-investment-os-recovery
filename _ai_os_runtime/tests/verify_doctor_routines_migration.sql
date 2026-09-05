\set ON_ERROR_STOP on

-- Run only on a disposable database after migration 260. Every mutation rolls back.
BEGIN;

DO $test$
DECLARE
    first_run JSONB;
    duplicate_run JSONB;
    failed_as_expected BOOLEAN;
    fixture_hash TEXT := repeat('d',64);
    fixture_key TEXT := 'research_company_change_monitor:'||repeat('d',64);
BEGIN
    IF (SELECT count(*) FROM ops.doctor_check_registry)<>21 THEN
        RAISE EXCEPTION 'Doctor registry count mismatch';
    END IF;
    IF (SELECT count(*) FROM agent.routine_definitions) < 5 THEN
        RAISE EXCEPTION 'routine registry incomplete';
    END IF;
    IF EXISTS (
        SELECT 1 FROM agent.routine_versions
        WHERE routine_key=ANY(ARRAY[
            'daily_system_health','obsidian_incremental_index',
            'research_company_change_monitor','stale_task_and_lease_reaper',
            'zerodha_session_and_stream_watch'
        ]) AND cost_budget_usd<>0
    ) THEN RAISE EXCEPTION 'routine model budget is not zero'; END IF;
    IF EXISTS (
        SELECT 1 FROM agent.routine_runs
        WHERE broker_write_allowed OR external_write_allowed OR client_write_allowed
    ) THEN RAISE EXCEPTION 'unsafe routine run flags found'; END IF;

    failed_as_expected := false;
    BEGIN
        PERFORM agent.control_routine(
            'research_company_change_monitor','enable','migration-fixture',
            'No confirmation fixture',false
        );
    EXCEPTION WHEN OTHERS THEN
        failed_as_expected := position('confirmation' IN SQLERRM)>0;
    END;
    IF NOT failed_as_expected THEN
        RAISE EXCEPTION 'routine control accepted missing confirmation';
    END IF;

    PERFORM agent.control_routine(
        'research_company_change_monitor','enable','migration-fixture',
        'Explicit disposable migration fixture control',true
    );

    failed_as_expected := false;
    BEGIN
        PERFORM agent.start_routine_run(
            'research_company_change_monitor','event',NULL,
            'research_company_change_monitor:null-hash','{}','migration-fixture',false
        );
    EXCEPTION WHEN OTHERS THEN
        failed_as_expected := position('event trigger requires' IN SQLERRM)>0;
    END;
    IF NOT failed_as_expected THEN
        RAISE EXCEPTION 'event run accepted no event hash';
    END IF;

    first_run := agent.start_routine_run(
        'research_company_change_monitor','event',fixture_hash,fixture_key,
        '{"source":"fixture-safe"}','migration-fixture',false
    );
    IF NOT (first_run->>'created')::boolean THEN
        RAISE EXCEPTION 'first fixture event was not created';
    END IF;
    PERFORM agent.finish_routine_run(
        first_run->>'run_key','completed','fixture complete','[]',
        '/Volumes/Devarsh SSD/AI OS Data/artifacts/routines/migration-fixture.json',
        repeat('e',64),NULL
    );
    duplicate_run := agent.start_routine_run(
        'research_company_change_monitor','event',fixture_hash,fixture_key,
        '{"source":"fixture-safe"}','migration-fixture',false
    );
    IF NOT (duplicate_run->>'duplicate')::boolean THEN
        RAISE EXCEPTION 'duplicate event was not suppressed';
    END IF;

    failed_as_expected := false;
    BEGIN
        UPDATE agent.routine_versions SET cooldown_seconds=cooldown_seconds+1
        WHERE routine_key='daily_system_health' AND version=1;
    EXCEPTION WHEN OTHERS THEN
        failed_as_expected := position('immutable' IN SQLERRM)>0;
    END;
    IF NOT failed_as_expected THEN
        RAISE EXCEPTION 'published routine version was mutable';
    END IF;

    IF EXISTS (
        SELECT 1 FROM agent.routine_definitions definition
        JOIN agent.routine_versions version
          ON version.routine_key=definition.routine_key
         AND version.version=definition.current_version
        JOIN agent.workflow_schedules schedule USING(schedule_key)
        WHERE (version.trigger_kind='schedule'
               AND schedule.enabled<>(definition.control_state='enabled'))
           OR (version.trigger_kind='event' AND schedule.enabled)
    ) THEN RAISE EXCEPTION 'routine and schedule state mismatch'; END IF;
    IF NOT EXISTS (
        SELECT 1 FROM agent.routine_definitions definition
        JOIN agent.routine_versions version
          ON version.routine_key=definition.routine_key
         AND version.version=definition.current_version
        JOIN agent.workflow_schedules schedule USING(schedule_key)
        WHERE definition.routine_key='research_company_change_monitor'
          AND definition.control_state='enabled'
          AND version.trigger_kind='event'
          AND NOT schedule.enabled
    ) THEN RAISE EXCEPTION 'event handling was not enabled safely'; END IF;
END
$test$;

ROLLBACK;
