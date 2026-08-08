BEGIN;

INSERT INTO agent.tool_registry (
    tool_name,tool_type,owning_agent,permission_level,enabled,description,config
) VALUES
    ('ai_os_sector_intelligence_snapshot','mcp_tool','Sector Portfolio Manager','read_only',true,
     'Read effective-dated sector taxonomy, aggregates, valuations, flows, custom indices, committee state, freshness and acceptance evidence.',
     '{"api":"/api/sector-intelligence/snapshot","reads":["sector_intelligence.v_sector_hierarchy","sector_intelligence.v_custom_index_control","sector_intelligence.v_sector_data_freshness","sector_intelligence.v_sector_committee_control"],"seed_data_allowed":false,"broker_order_allowed":false}'::jsonb),
    ('ai_os_sector_intelligence_engine','deterministic_worker','Sector Market Structure Analyst','write_with_approval',true,
     'Calculate governed custom-sector-index history, rebalances, breadth, relative strength and chart artifacts from validated warehouse observations.',
     '{"api":"/api/sector-intelligence/run","script":"_ai_os_runtime/scripts/run_sector_intelligence_engine.py","writes":["sector_intelligence.custom_index_rebalances","sector_intelligence.custom_index_points","sector_intelligence.generated_chart_artifacts"],"source_required":true,"seed_data_allowed":false,"broker_order_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type=EXCLUDED.tool_type,owning_agent=EXCLUDED.owning_agent,
    permission_level=EXCLUDED.permission_level,enabled=EXCLUDED.enabled,
    description=EXCLUDED.description,config=EXCLUDED.config;

INSERT INTO agent.tool_alias_registry (
    alias_name,implementation_tool_name,capability_class,access_contract,notes
) VALUES
    ('sector_warehouse','ai_os_sector_intelligence_snapshot','sector','read_only','Validated effective-dated sector read model.'),
    ('sector_intelligence_engine','ai_os_sector_intelligence_engine','sector','write_with_approval','Deterministic sector calculations and chart artifacts.'),
    ('sector_importer','ai_os_import_sector_intelligence_package','sector','write_with_approval','Licensed or primary-source sector package import.'),
    ('sector_intelligence_package_importer','ai_os_import_sector_intelligence_package','sector','write_with_approval','Licensed or primary-source sector package import.'),
    ('filing_evidence','ai_os_corporate_filing_inbox','filings','read_only','Stored primary filing evidence and lineage.'),
    ('filing_evidence_reader','ai_os_corporate_filing_inbox','filings','read_only','Stored primary filing evidence and lineage.'),
    ('zerodha_read_only','ai_os_zerodha_read_snapshot','market_data','write_db_manual_only','GET-only broker snapshot and market-data synchronization.'),
    ('institutional_options_materializer','ai_os_materialize_institutional_options','options','write_db_scheduled','Immutable options batches and validated deterministic analytics.'),
    ('options_math_engine','ai_os_materialize_institutional_options','options','write_db_scheduled','Black-Scholes-Merton or Black-76 analytics using validated point-in-time policies.')
ON CONFLICT (alias_name) DO UPDATE SET
    implementation_tool_name=EXCLUDED.implementation_tool_name,
    capability_class=EXCLUDED.capability_class,
    access_contract=EXCLUDED.access_contract,
    notes=EXCLUDED.notes,active=true,updated_at=now();

-- Automatic TradingView control stays disabled until macOS Accessibility is
-- granted. Employees can still create governed tasks for the logged-in
-- TradingView Desktop workspace without pretending the action was executed.
UPDATE agent.profiles
SET default_tools=array_replace(
        array_replace(default_tools,'tradingview_controller','tradingview_task_queue'),
        'tradingview_desktop_controller','tradingview_task_queue'
    ),
    updated_at=now()
WHERE status='active'
  AND (default_tools @> ARRAY['tradingview_controller']::TEXT[]
       OR default_tools @> ARRAY['tradingview_desktop_controller']::TEXT[]);

UPDATE agent.skills
SET required_tools=array_replace(
        array_replace(required_tools,'tradingview_controller','tradingview_task_queue'),
        'tradingview_desktop_controller','tradingview_task_queue'
    ),
    risk_notes=concat_ws(' ',risk_notes,
        'TradingView Desktop actions are queued for user-visible handoff until the controller has explicit macOS Accessibility permission.'),
    updated_at=now()
WHERE status='active'
  AND (required_tools @> ARRAY['tradingview_controller']::TEXT[]
       OR required_tools @> ARRAY['tradingview_desktop_controller']::TEXT[]);

UPDATE agent.agent_model_assignments assignment
SET fallback_route='agent_worker_deterministic',
    notes=concat_ws(' ',nullif(assignment.notes,''),
        'Deterministic evidence fallback is the pre-model operating route; intended primary route is preserved.'),
    context_policy=concat_ws(' ',assignment.context_policy,
        'If the primary model route is unavailable, use only source-backed deterministic tools and defer model judgment.'),
    updated_at=now()
FROM agent.profiles profile
WHERE profile.agent_name=assignment.agent_name
  AND profile.status='active'
  AND assignment.fallback_route IS DISTINCT FROM 'agent_worker_deterministic';

COMMIT;
