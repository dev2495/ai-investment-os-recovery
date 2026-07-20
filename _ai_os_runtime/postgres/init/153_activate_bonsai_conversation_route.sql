DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM agent.local_model_registry
        WHERE model_name='prism-ml/Bonsai-27B-Q1_0'
          AND eval_suite='conversation_v1'
          AND promotion_status='approved'
          AND coalesce(last_eval_score,0) >= 0.8
    ) THEN
        RAISE EXCEPTION 'Bonsai conversation route activation refused: exact conversation_v1 promotion evidence is missing';
    END IF;
END $$;

UPDATE agent.model_routes
SET default_provider='local_openai',
    default_model='prism-ml/Bonsai-27B-Q1_0',
    max_cost_tier='local_plus',
    notes='Conversation-only private MacBook route. Research, arithmetic, approvals, capital, and execution remain owned by deterministic tools and specialist pipelines.'
WHERE route_name='charlie_munger_orchestration';

UPDATE agent.model_endpoints
SET status='active',
    health_status='healthy',
    last_checked_at=now(),
    last_error=NULL,
    updated_at=now()
WHERE endpoint_key='bonsai_27b_q1_local_openai';
