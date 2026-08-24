\set ON_ERROR_STOP on

-- pg_dump archives preserve RLS policy role references, while the raw
-- pg_dumpall globals file can also contain login roles and password verifiers.
-- Restore only this exact, credential-free runtime identity before pg_restore.
DO $restore_roles$
DECLARE
    runtime_role_oid oid;
BEGIN
    SELECT oid
    INTO runtime_role_oid
    FROM pg_roles
    WHERE rolname = 'ai_os_research_runtime';

    IF runtime_role_oid IS NULL THEN
        EXECUTE 'CREATE ROLE ai_os_research_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS';
        SELECT oid
        INTO runtime_role_oid
        FROM pg_roles
        WHERE rolname = 'ai_os_research_runtime';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE oid = runtime_role_oid
          AND (
              rolcanlogin
              OR rolsuper
              OR rolcreatedb
              OR rolcreaterole
              OR rolinherit
              OR rolreplication
              OR rolbypassrls
          )
    ) THEN
        RAISE EXCEPTION 'unsafe pre-existing ai_os_research_runtime role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_auth_members
        WHERE roleid = runtime_role_oid OR member = runtime_role_oid
    ) THEN
        RAISE EXCEPTION 'unexpected ai_os_research_runtime role membership';
    END IF;
END
$restore_roles$;

SELECT rolname,
       rolcanlogin,
       rolsuper,
       rolcreatedb,
       rolcreaterole,
       rolinherit,
       rolreplication,
       rolbypassrls
FROM pg_roles
WHERE rolname = 'ai_os_research_runtime';
