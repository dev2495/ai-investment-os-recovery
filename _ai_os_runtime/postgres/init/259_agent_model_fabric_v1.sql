-- Extend the canonical AI OS model-route, assignment, approval and call ledgers.
-- This migration enables no route, promotes no binding and grants no paid call.
BEGIN;

CREATE TABLE IF NOT EXISTS agent.model_binding_versions (
    id BIGSERIAL PRIMARY KEY,
    binding_key TEXT NOT NULL CHECK (binding_key ~ '^[a-zA-Z0-9_.-]{1,120}$'),
    version INTEGER NOT NULL CHECK (version > 0),
    selector_kind TEXT NOT NULL CHECK (selector_kind IN ('agent','role')),
    selector_value TEXT NOT NULL CHECK (length(selector_value) BETWEEN 1 AND 2000),
    task_class TEXT NOT NULL CHECK (task_class ~ '^[a-zA-Z0-9_.-]{1,120}$'),
    primary_route TEXT NOT NULL REFERENCES agent.model_routes(route_name),
    fallback_routes TEXT[] NOT NULL DEFAULT '{}' CHECK (cardinality(fallback_routes) <= 3),
    fallback_policy TEXT NOT NULL DEFAULT 'fail_closed'
        CHECK (fallback_policy IN ('fail_closed','explicit_degraded')),
    reasoning_profile TEXT NOT NULL DEFAULT 'none'
        CHECK (reasoning_profile IN ('none','low','medium','high','xhigh')),
    context_budget INTEGER NOT NULL CHECK (context_budget BETWEEN 256 AND 131072),
    max_output_tokens INTEGER NOT NULL CHECK (max_output_tokens BETWEEN 1 AND 16384),
    temperature NUMERIC NOT NULL CHECK (temperature BETWEEN 0 AND 2),
    privacy_classes TEXT[] NOT NULL DEFAULT ARRAY['public','internal'],
    required_evaluations TEXT[] NOT NULL
        DEFAULT ARRAY['numeric','citation','missing_data','prompt_injection'],
    route_snapshot JSONB NOT NULL
        CHECK (jsonb_typeof(route_snapshot) = 'object' AND pg_column_size(route_snapshot) < 65536),
    created_by TEXT NOT NULL CHECK (length(created_by) BETWEEN 1 AND 160),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (binding_key, version),
    CHECK (privacy_classes <@ ARRAY['public','internal','client_private','restricted']::TEXT[]),
    CHECK (fallback_policy = 'explicit_degraded' OR cardinality(fallback_routes) = 0)
);

CREATE TABLE IF NOT EXISTS agent.model_binding_heads (
    binding_key TEXT PRIMARY KEY,
    version_id BIGINT NOT NULL REFERENCES agent.model_binding_versions(id),
    enabled BOOLEAN NOT NULL DEFAULT false,
    updated_by TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS agent.model_route_qualifications (
    id BIGSERIAL PRIMARY KEY,
    route_name TEXT NOT NULL REFERENCES agent.model_routes(route_name),
    task_class TEXT NOT NULL,
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    endpoint_key TEXT NOT NULL,
    route_fingerprint TEXT NOT NULL CHECK (length(route_fingerprint) = 64),
    adapter_version TEXT NOT NULL,
    runtime_version TEXT NOT NULL,
    packet_key TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('passed','failed')),
    scores JSONB NOT NULL CHECK (jsonb_typeof(scores) = 'object' AND pg_column_size(scores) < 8192),
    reasoning_profiles TEXT[] NOT NULL DEFAULT ARRAY['none'],
    tools_verified BOOLEAN NOT NULL DEFAULT false,
    structured_output_verified BOOLEAN NOT NULL DEFAULT false,
    latency_ms INTEGER NOT NULL CHECK (latency_ms >= 0),
    human_reviewer TEXT,
    approval_id BIGINT REFERENCES agent.approvals(id),
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp() + interval '7 days',
    CHECK (expires_at > created_at AND expires_at <= created_at + interval '31 days')
);
CREATE INDEX IF NOT EXISTS idx_model_qualification_lookup
    ON agent.model_route_qualifications (route_name, task_class, created_at DESC);

CREATE TABLE IF NOT EXISTS agent.model_binding_audit (
    id BIGSERIAL PRIMARY KEY,
    binding_key TEXT NOT NULL,
    version_id BIGINT NOT NULL REFERENCES agent.model_binding_versions(id),
    prior_version_id BIGINT REFERENCES agent.model_binding_versions(id),
    action TEXT NOT NULL CHECK (action IN ('proposed','promoted','disabled','rolled_back')),
    actor TEXT NOT NULL,
    approval_id BIGINT REFERENCES agent.approvals(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- Attempt receipts supplement, rather than replace, model_call_decisions and
-- model_usage_events. A running/uncertain row is never replayed automatically.
CREATE TABLE IF NOT EXISTS agent.model_fabric_attempts (
    id BIGSERIAL PRIMARY KEY,
    request_id UUID NOT NULL,
    decision_id BIGINT NOT NULL,
    binding_version_id BIGINT REFERENCES agent.model_binding_versions(id),
    qualification_id BIGINT REFERENCES agent.model_route_qualifications(id),
    route_name TEXT NOT NULL REFERENCES agent.model_routes(route_name),
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    agent_name TEXT NOT NULL REFERENCES agent.profiles(agent_name),
    task_id BIGINT REFERENCES agent.tasks(id),
    preflight_id BIGINT,
    status TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running','completed','failed','uncertain')),
    reserved_cost_usd NUMERIC NOT NULL DEFAULT 0 CHECK (reserved_cost_usd >= 0),
    actual_cost_usd NUMERIC CHECK (actual_cost_usd >= 0),
    prompt_tokens BIGINT CHECK (prompt_tokens >= 0),
    completion_tokens BIGINT CHECK (completion_tokens >= 0),
    latency_ms INTEGER CHECK (latency_ms >= 0),
    error_code TEXT,
    response_hash TEXT,
    degraded BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    finished_at TIMESTAMPTZ,
    UNIQUE (request_id, route_name)
);
CREATE INDEX IF NOT EXISTS idx_model_fabric_reservations
    ON agent.model_fabric_attempts (agent_name, created_at DESC);

DO $$ BEGIN
    IF to_regclass('agent.agent_model_assignments') IS NOT NULL THEN
        ALTER TABLE agent.agent_model_assignments
            ADD COLUMN IF NOT EXISTS fabric_bindings JSONB NOT NULL DEFAULT '{}';
    END IF;
    IF to_regclass('agent.model_call_decisions') IS NOT NULL THEN
        ALTER TABLE agent.model_call_decisions
            ADD COLUMN IF NOT EXISTS fabric_request_id UUID,
            ADD COLUMN IF NOT EXISTS fabric_binding_version_id BIGINT
                REFERENCES agent.model_binding_versions(id),
            ADD COLUMN IF NOT EXISTS fabric_request_hash TEXT,
            ADD COLUMN IF NOT EXISTS fabric_state TEXT,
            ADD COLUMN IF NOT EXISTS fabric_result JSONB NOT NULL DEFAULT '{}';
        CREATE UNIQUE INDEX IF NOT EXISTS uq_model_fabric_request_id
            ON agent.model_call_decisions (fabric_request_id)
            WHERE fabric_request_id IS NOT NULL;
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'model_fabric_attempt_decision_fk'
              AND conrelid = 'agent.model_fabric_attempts'::regclass
        ) THEN
            ALTER TABLE agent.model_fabric_attempts
                ADD CONSTRAINT model_fabric_attempt_decision_fk
                FOREIGN KEY (decision_id) REFERENCES agent.model_call_decisions(id);
        END IF;
    END IF;
END $$;

CREATE OR REPLACE FUNCTION agent.guard_model_fabric_history()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Model Fabric version, qualification and audit history is immutable';
END $$;
CREATE OR REPLACE TRIGGER model_binding_immutable
    BEFORE UPDATE OR DELETE ON agent.model_binding_versions
    FOR EACH ROW EXECUTE FUNCTION agent.guard_model_fabric_history();
CREATE OR REPLACE TRIGGER model_qualification_immutable
    BEFORE UPDATE OR DELETE ON agent.model_route_qualifications
    FOR EACH ROW EXECUTE FUNCTION agent.guard_model_fabric_history();
CREATE OR REPLACE TRIGGER model_binding_audit_immutable
    BEFORE UPDATE OR DELETE ON agent.model_binding_audit
    FOR EACH ROW EXECUTE FUNCTION agent.guard_model_fabric_history();

CREATE OR REPLACE FUNCTION agent.guard_model_binding_head()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM agent.model_binding_versions
        WHERE id = NEW.version_id AND binding_key = NEW.binding_key
    ) THEN
        RAISE EXCEPTION 'binding head must reference its own immutable version';
    END IF;
    RETURN NEW;
END $$;
CREATE OR REPLACE TRIGGER model_binding_head_contract
    BEFORE INSERT OR UPDATE ON agent.model_binding_heads
    FOR EACH ROW EXECUTE FUNCTION agent.guard_model_binding_head();

CREATE OR REPLACE FUNCTION agent.guard_model_fabric_attempt()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'model call receipts cannot be deleted';
    END IF;
    IF OLD.status <> 'running' OR NEW.status NOT IN ('completed','failed','uncertain') THEN
        RAISE EXCEPTION 'terminal or uncertain model attempts cannot be replayed or rewritten';
    END IF;
    IF ROW(
        NEW.request_id, NEW.decision_id, NEW.route_name, NEW.model_name,
        NEW.provider, NEW.agent_name, NEW.task_id, NEW.preflight_id,
        NEW.reserved_cost_usd, NEW.binding_version_id, NEW.qualification_id
    ) IS DISTINCT FROM ROW(
        OLD.request_id, OLD.decision_id, OLD.route_name, OLD.model_name,
        OLD.provider, OLD.agent_name, OLD.task_id, OLD.preflight_id,
        OLD.reserved_cost_usd, OLD.binding_version_id, OLD.qualification_id
    ) THEN
        RAISE EXCEPTION 'model call identity and cost reservation are immutable';
    END IF;
    RETURN NEW;
END $$;
CREATE OR REPLACE TRIGGER model_fabric_attempt_contract
    BEFORE UPDATE OR DELETE ON agent.model_fabric_attempts
    FOR EACH ROW EXECUTE FUNCTION agent.guard_model_fabric_attempt();

COMMIT;
