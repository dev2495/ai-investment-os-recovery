UPDATE agent.local_model_registry
SET eval_suite='conversation_v1',
    promotion_status='candidate',
    allowed_task_classes=ARRAY['conversation','task_intake','evidence_bound_summary'],
    notes='Conversation-only Bonsai candidate. It failed mid_v1 and must not perform filing analysis, valuation, strategy research, deterministic arithmetic, approval, capital, or execution work.',
    updated_at=now()
WHERE model_name='prism-ml/Bonsai-27B-Q1_0';
