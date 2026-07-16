BEGIN;

INSERT INTO agent.tool_registry (
    tool_name, tool_type, owning_agent, permission_level, enabled, description, config
)
VALUES
    ('local_release_test_runner','local_command_contract','QA Engineer','write_with_approval',true,
     'Run the bounded UI and MCP release test suites from the checked-in project scripts.',
     '{"working_directory":"_ai_os_runtime/ai-office-ui","commands":["npm test","npm run test:a11y"],"arbitrary_command_allowed":false,"writes_production":false}'::jsonb),
    ('software_repository_reader','local_filesystem','CTO Agent','read_only',true,
     'Read the checked-in AI OS repository and component inventory without modifying source.',
     '{"root":"AI_OS_ACTIVE_RECOVERY_20260710/ai-investment-os","reads":["git","source","component inventory"],"write_allowed":false}'::jsonb),
    ('deployment_health_reader','runtime_health','DevOps Engineer','read_only',true,
     'Read loopback service, daemon, Docker, and deployment health evidence.',
     '{"reads":["ai_os_runtime_daemon_health","docker health","API health","UI health"],"restart_allowed":false}'::jsonb),
    ('source_credibility_policy','policy_engine','News Editor','read_only',true,
     'Resolve source class, official-source status, provenance, and corroboration requirements from stored feed metadata.',
     '{"reads":["research.feed_registry","core.data_source_registry","core.data_source_checks"],"scoring":"deterministic policy labels","model_required":false}'::jsonb),
    ('macro_data_reader','read_model','Macro Researcher','read_only',true,
     'Read verified public macro observations and official central-bank source records.',
     '{"reads":["market.macro_observations","research.feed_registry","core.data_source_checks"],"source_required":true}'::jsonb),
    ('market_watch_reader','read_model','Trading Desk Agent','read_only',true,
     'Read stored quotes, OHLCV readiness, TradingView scanner quotes, signals, and alerts.',
     '{"reads":["market.price_quotes","trading.ohlcv","trading.signals","strategy.alert_events"],"live_execution_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type=EXCLUDED.tool_type, owning_agent=EXCLUDED.owning_agent,
    permission_level=EXCLUDED.permission_level, enabled=EXCLUDED.enabled,
    description=EXCLUDED.description, config=EXCLUDED.config;

CREATE TABLE IF NOT EXISTS agent.tool_alias_registry (
    alias_name TEXT PRIMARY KEY,
    implementation_tool_name TEXT NOT NULL REFERENCES agent.tool_registry(tool_name),
    capability_class TEXT NOT NULL,
    access_contract TEXT NOT NULL DEFAULT 'role_scoped',
    notes TEXT,
    active BOOLEAN NOT NULL DEFAULT true,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO agent.tool_alias_registry (
    alias_name, implementation_tool_name, capability_class, access_contract, notes
)
VALUES
    ('postgres','postgres_read_model','warehouse','read_only','Shared warehouse read alias.'),
    ('obsidian','obsidian_note_index','knowledge','read_only','Shared Obsidian retrieval alias.'),
    ('qdrant_search','qdrant_vector_search','retrieval','read_only','Shared semantic retrieval alias.'),
    ('market_data','ai_os_market_data_readiness','market_data','read_only','Market-data readiness and stored-data entry point.'),
    ('research_hub','ai_os_research_hub_summary','research','read_only','Research inventory and evidence hub.'),
    ('risk_engine','ai_os_institutional_portfolio_risk','risk','read_only','Institutional portfolio-risk read model.'),
    ('approval_board','ai_os_approval_board','governance','read_only','Approval board read model.'),
    ('tradingview_controller','ai_os_execute_tradingview_chart_action','browser_chart','browser_capture','Governed TradingView browser action.'),
    ('tradingview_desktop_controller','ai_os_execute_tradingview_chart_action','browser_chart','browser_capture','Governed TradingView desktop action.'),
    ('audit_log','ai_os_control_plane_snapshot','governance','read_only','Control-plane and audit evidence reader.'),
    ('filing_event_reader','ai_os_corporate_filing_inbox','filings','read_only','Corporate filing and filing-event reader.'),
    ('risk_limit_checker','ai_os_portfolio_risk_limit_checks','risk','read_only','Portfolio limit-check reader.'),
    ('approval_gate_writer','ai_os_create_approval','governance','write_with_approval','Creates a governed approval request only.'),
    ('client_folios','ai_os_portfolio_intelligence_v2','portfolio','read_only','Client folio and position intelligence.'),
    ('code_repository','software_repository_reader','engineering','read_only','Checked-in repository reader.'),
    ('deployment_logs','deployment_health_reader','engineering','read_only','Runtime and deployment health evidence.'),
    ('macro_sources','macro_data_reader','macro','read_only','Verified macro observations and source checks.'),
    ('official_macro_feeds','macro_data_reader','macro','read_only','Official macro source alias.'),
    ('report_registry','ai_os_output_artifact_registry','knowledge','read_only','Report and artifact registry.'),
    ('test_runner','local_release_test_runner','engineering','write_with_approval','Bounded checked-in release tests.'),
    ('agent_worker_dispatch','agent_worker_run_once','orchestration','write_with_approval','Bounded agent worker dispatcher.'),
    ('local_python_backtester','ai_os_queue_strategy_backtest','quant','write_with_approval','Queues deterministic local backtests.'),
    ('vectorbt','ai_os_queue_strategy_backtest','quant','write_with_approval','Vectorized backtest contract through governed queue.'),
    ('walk_forward_runner','ai_os_run_user_defined_strategy_optimizer','quant','write_with_approval','Walk-forward and robustness optimizer.'),
    ('news_feed_reader','ai_os_ingest_market_news','news','write_db','Source-backed RSS/news ingestion.'),
    ('news_feeds','ai_os_ingest_market_news','news','write_db','Source-backed RSS/news ingestion.'),
    ('source_credibility_scorer','source_credibility_policy','news','read_only','Deterministic provenance policy.'),
    ('book_exposure','ai_os_portfolio_intelligence_v2','portfolio','read_only','Cross-book exposure reader.'),
    ('portfolio_snapshot_reader','ai_os_portfolio_intelligence_v2','portfolio','read_only','Latest portfolio snapshot reader.'),
    ('portfolio_intelligence','ai_os_portfolio_intelligence_v2','portfolio','read_only','Portfolio intelligence reader.'),
    ('portfolio_positions','ai_os_position_objects_v9','portfolio','read_only','Purpose-aware position objects.'),
    ('data_quality_checker','ai_os_data_source_checks','data_quality','read_only','Stored data-source quality checks.'),
    ('data_quality_checks','ai_os_data_source_checks','data_quality','read_only','Stored data-source quality checks.'),
    ('source_registry','ai_os_source_lineage','data','read_only','Source registry and lineage.'),
    ('source_registry_writer','ai_os_register_source_connector','data','write_db_manual_only','Governed connector registration.'),
    ('tradingview_task_queue','ai_os_tradingview_tasks','browser_chart','read_only','TradingView task queue.'),
    ('agent_inbox_writer','ai_os_create_task','orchestration','write_with_approval','Creates governed tasks and inbox work.'),
    ('book_attribution','ai_os_client_accounting_run','portfolio','write_db_manual_only','Client/book accounting and attribution run.'),
    ('broker_import_router','ai_os_run_p2cursor_reconciliation','data','write_db_manual_only','Broker archive reconciliation path.'),
    ('browser_research','browser_research_runner','browser','browser_read','Bounded browser research.'),
    ('committee_rooms','ai_os_committee_room','governance','read_only','Committee room and packets.'),
    ('component_inventory_reader','ai_os_component_inventory','engineering','read_only','Component inventory reader.'),
    ('connector_health','ai_os_check_source_connector','data','write_db_manual_only','Source connector configuration check.'),
    ('filing_alerts','ai_os_corporate_filing_inbox','filings','read_only','Material filing alert reader.'),
    ('filing_event_extractor','ai_os_extract_filing_pdf_text','filings','document_read','Filing document extraction.'),
    ('document_parser','ai_os_extract_filing_pdf_text','filings','document_read','Filing PDF/text parser.'),
    ('fincept_terminal_local_checkout','ai_os_fincept_install_status','component','read_only','Installed Fincept component status.'),
    ('freshness_monitor','ai_os_check_source_freshness','data_quality','write_db_manual_only','Source freshness check.'),
    ('health_checks','ai_os_runtime_daemon_health','runtime','read_only','Runtime health checks.'),
    ('ingestion_pipelines','ai_os_run_legacy_market_data_ingestion','data','write_with_approval','Governed ingestion pipeline.'),
    ('lineage','ai_os_source_lineage','data','read_only','Source lineage reader.'),
    ('market_watch','market_watch_reader','market_data','read_only','Stored market watch data.'),
    ('mcp_registry','ai_os_control_plane_snapshot','runtime','read_only','MCP and control-plane registry.'),
    ('mcp_tool_dispatch','jarvis_runtime','orchestration','write_with_approval','Jarvis MCP dispatcher.'),
    ('model_endpoints','ai_os_model_runtime_control','runtime','read_only','Model endpoint control.'),
    ('provider_readiness','ai_os_provider_readiness_board','runtime','read_only','Provider readiness board.'),
    ('usage_costs','ai_os_model_cost_ledger','runtime','read_only','Model usage and cost ledger.'),
    ('obsidian_note_writer','ai_os_write_obsidian_note','knowledge','write_with_approval','Governed Obsidian writeback.'),
    ('performance_attribution','ai_os_client_accounting_run','portfolio','write_db_manual_only','Client and book attribution.'),
    ('reconciliation','ai_os_holding_reconciliation_control','data_quality','write_db_manual_only','Holding reconciliation control.'),
    ('research_folder_writer','ai_os_write_obsidian_note','knowledge','write_with_approval','Structured research-folder writeback.'),
    ('research_note_writer','ai_os_write_obsidian_note','knowledge','write_with_approval','Structured research-note writeback.'),
    ('risk_event_reader','ai_os_institutional_portfolio_risk','risk','read_only','Risk event and institutional risk reader.'),
    ('risk_limits','ai_os_portfolio_risk_limit_checks','risk','read_only','Risk limit reader.'),
    ('scenario_engine','ai_os_run_institutional_portfolio_risk','risk','write_with_approval','Institutional scenario and stress engine.'),
    ('scheduler','ai_os_report_scheduler_status','automation','read_only','Governed scheduler status.'),
    ('workflow_registry','ai_os_orchestration_stack','automation','read_only','Workflow and orchestration registry.'),
    ('source_checks','ai_os_data_source_checks','data_quality','read_only','Source check reader.'),
    ('special_situation_screener','ai_os_special_situation_memos','research','read_only','Special-situation and arbitrage screen.'),
    ('strategy_spec_writer','ai_os_parse_strategy_dsl','quant','write_with_approval','Machine-testable strategy DSL writer.'),
    ('strategy_validation_review','ai_os_record_strategy_validation','quant','write_with_approval','Strategy validation record.'),
    ('tool_registry','ai_os_control_plane_snapshot','runtime','read_only','Enabled tool registry reader.'),
    ('trade_journal','ai_os_trade_activity','trading','read_only','Manual, paper, and system trade activity.'),
    ('trade_ledger_writer','ai_os_record_manual_trade','trading','write_db_manual_only','Manual trade ledger writer.'),
    ('valuation_model_registry','ai_os_update_long_term_valuation_model','research','write_with_approval','Long-term valuation model registry.'),
    ('openalgo_local_api','ai_os_market_data_readiness','component','read_only','OpenAlgo remains a local component contract until its API is configured.'),
    ('vibe_trading_mcp','ai_os_component_inventory','component','read_only','Vibe-Trading remains a reviewed component pattern, not an ungoverned external runtime.'),
    ('agent_mailbox_router','ai_os_triage_agent_message','orchestration','write_with_approval','Durable agent mailbox router.')
ON CONFLICT (alias_name) DO UPDATE SET
    implementation_tool_name=EXCLUDED.implementation_tool_name,
    capability_class=EXCLUDED.capability_class,
    access_contract=EXCLUDED.access_contract,
    notes=EXCLUDED.notes, active=true, updated_at=now();

CREATE OR REPLACE VIEW agent.v_agent_tool_capabilities AS
WITH primary_skill AS (
    SELECT DISTINCT ON (mapping.agent_name)
           mapping.agent_name,mapping.skill_key
    FROM agent.agent_skill_map mapping
    JOIN agent.skills skill USING(skill_key)
    WHERE skill.status='active'
    ORDER BY mapping.agent_name,mapping.is_primary DESC,mapping.skill_key
), requested AS (
    SELECT profile.agent_name,'profile_default'::TEXT AS request_source,
           unnest(coalesce(profile.default_tools,'{}'::TEXT[])) AS requested_tool
    FROM agent.profiles profile WHERE profile.status='active'
    UNION
    SELECT primary_skill.agent_name,'primary_skill'::TEXT,
           unnest(coalesce(skill.required_tools,'{}'::TEXT[]))
    FROM primary_skill JOIN agent.skills skill USING(skill_key)
), distinct_requested AS (
    SELECT DISTINCT agent_name,request_source,requested_tool FROM requested
)
SELECT requested.agent_name,requested.request_source,requested.requested_tool,
       coalesce(direct.tool_name,implementation.tool_name) AS implementation_tool_name,
       coalesce(direct.tool_type,implementation.tool_type) AS tool_type,
       coalesce(direct.permission_level,implementation.permission_level) AS permission_level,
       coalesce(direct.enabled,implementation.enabled,false) AS enabled,
       CASE WHEN direct.tool_name IS NOT NULL THEN 'direct'
            WHEN alias.alias_name IS NOT NULL AND implementation.tool_name IS NOT NULL THEN 'alias'
            ELSE 'missing' END AS resolution_type,
       alias.capability_class,alias.access_contract
FROM distinct_requested requested
LEFT JOIN agent.tool_registry direct
  ON direct.tool_name=requested.requested_tool
LEFT JOIN agent.tool_alias_registry alias
  ON alias.alias_name=requested.requested_tool AND alias.active
LEFT JOIN agent.tool_registry implementation
  ON implementation.tool_name=alias.implementation_tool_name;

CREATE OR REPLACE VIEW agent.v_agent_capability_readiness AS
SELECT profile.agent_name,
       count(cap.requested_tool)::INT AS requested_tool_count,
       count(cap.implementation_tool_name)::INT AS resolved_tool_count,
       count(*) FILTER (WHERE cap.enabled)::INT AS ready_tool_count,
       count(*) FILTER (WHERE cap.implementation_tool_name IS NULL OR NOT cap.enabled)::INT AS missing_tool_count,
       coalesce(array_agg(cap.requested_tool ORDER BY cap.requested_tool)
           FILTER (WHERE cap.implementation_tool_name IS NULL OR NOT cap.enabled),'{}'::TEXT[]) AS missing_tools,
       (count(cap.requested_tool)>0 AND
        count(*) FILTER (WHERE cap.implementation_tool_name IS NULL OR NOT cap.enabled)=0) AS tools_ready
FROM agent.profiles profile
LEFT JOIN agent.v_agent_tool_capabilities cap ON cap.agent_name=profile.agent_name
WHERE profile.status='active'
GROUP BY profile.agent_name;

UPDATE agent.agent_model_assignments assignment
SET fallback_route='agent_worker_deterministic',
    notes=concat_ws(' ',nullif(assignment.notes,''),
        'Previous fallback route:',coalesce(assignment.fallback_route,'none') || '.',
        'Deterministic evidence fallback enabled for pre-model operation; primary model route is unchanged.'),
    context_policy=concat_ws(' ',assignment.context_policy,
        'When the primary model is unavailable, execute only deterministic source-backed tools and explicitly defer model judgment.'),
    updated_at=now()
WHERE coalesce((
          SELECT primary_state.runtime_status
          FROM agent.v_model_route_runtime_control primary_state
          WHERE primary_state.route_name=assignment.primary_route
      ),'unavailable')<>'ready'
  AND coalesce((
          SELECT fallback_state.runtime_status
          FROM agent.v_model_route_runtime_control fallback_state
          WHERE fallback_state.route_name=assignment.fallback_route
      ),'unavailable')<>'ready';

-- Until the model-installation phase, automatic task gating must select the
-- deterministic worker. Intended model routes remain preserved in
-- agent.agent_model_assignments and can be promoted after live model checks.
UPDATE agent.profiles
SET default_model_route='agent_worker_deterministic',updated_at=now()
WHERE status='active' AND default_model_route<>'agent_worker_deterministic';

CREATE TABLE IF NOT EXISTS agent.employee_activation_records (
    id BIGSERIAL PRIMARY KEY,
    campaign_key TEXT NOT NULL,
    agent_name TEXT NOT NULL REFERENCES agent.profiles(agent_name),
    task_id BIGINT REFERENCES agent.tasks(id),
    worker_run_id BIGINT REFERENCES agent.worker_runs(id),
    primary_skill_key TEXT REFERENCES agent.skills(skill_key),
    status TEXT NOT NULL DEFAULT 'queued',
    operating_mode TEXT NOT NULL DEFAULT 'deterministic_evidence',
    acceptance_checks JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(campaign_key,agent_name)
);

CREATE TABLE IF NOT EXISTS agent.fund_function_registry (
    function_key TEXT PRIMARY KEY,
    function_name TEXT NOT NULL,
    department_key TEXT NOT NULL,
    function_class TEXT NOT NULL,
    criticality TEXT NOT NULL DEFAULT 'standard',
    objective TEXT NOT NULL,
    evidence_standard TEXT NOT NULL,
    human_final_required BOOLEAN NOT NULL DEFAULT false,
    live_execution_allowed BOOLEAN NOT NULL DEFAULT false,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_fund_function_no_live_execution CHECK (live_execution_allowed=false)
);

CREATE TABLE IF NOT EXISTS agent.fund_function_assignments (
    function_key TEXT NOT NULL REFERENCES agent.fund_function_registry(function_key) ON DELETE CASCADE,
    agent_name TEXT NOT NULL REFERENCES agent.profiles(agent_name) ON DELETE CASCADE,
    responsibility TEXT NOT NULL CHECK (responsibility IN ('owner','reviewer','challenger')),
    required BOOLEAN NOT NULL DEFAULT true,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY(function_key,agent_name,responsibility)
);

INSERT INTO agent.fund_function_registry (
    function_key,function_name,department_key,function_class,criticality,
    objective,evidence_standard,human_final_required
)
SELECT regexp_replace(lower(profile.department || '__' || profile.agent_name),'[^a-z0-9]+','_','g'),
       profile.display_title,profile.department,
       CASE WHEN profile.department IN ('portfolio','quant','research','risk','trading','tactical','treasury')
            THEN 'investment_office' ELSE 'operating_office' END,
       CASE WHEN profile.department IN ('executive','portfolio','risk','trading','client') THEN 'critical' ELSE 'standard' END,
       profile.role_scope,
       'Every material output requires stored source lineage, role-scoped tools, a durable task/worker record, explicit uncertainty, and independent review.',
       profile.department IN ('executive','portfolio','risk','trading','client')
FROM agent.profiles profile
WHERE profile.status='active'
ON CONFLICT (function_key) DO UPDATE SET
    function_name=EXCLUDED.function_name,department_key=EXCLUDED.department_key,
    function_class=EXCLUDED.function_class,criticality=EXCLUDED.criticality,
    objective=EXCLUDED.objective,evidence_standard=EXCLUDED.evidence_standard,
    human_final_required=EXCLUDED.human_final_required,status='active',updated_at=now();

INSERT INTO agent.fund_function_assignments (function_key,agent_name,responsibility,evidence)
SELECT regexp_replace(lower(profile.department || '__' || profile.agent_name),'[^a-z0-9]+','_','g'),
       profile.agent_name,'owner',
       jsonb_build_array(jsonb_build_object('source','agent.profiles','role_scope',profile.role_scope))
FROM agent.profiles profile WHERE profile.status='active'
ON CONFLICT DO NOTHING;

INSERT INTO agent.fund_function_assignments (function_key,agent_name,responsibility,evidence)
SELECT function.function_key,
       CASE WHEN hierarchy.reports_to_agent IS NOT NULL AND hierarchy.reports_to_agent<>owner.agent_name
            THEN hierarchy.reports_to_agent ELSE 'Charlie Munger' END,
       'reviewer',
       jsonb_build_array(jsonb_build_object('source','agent.org_hierarchy','review_contract','independent supervisory review'))
FROM agent.fund_function_registry function
JOIN agent.fund_function_assignments owner
  ON owner.function_key=function.function_key AND owner.responsibility='owner'
LEFT JOIN agent.org_hierarchy hierarchy ON hierarchy.agent_name=owner.agent_name
WHERE function.status='active'
ON CONFLICT DO NOTHING;

INSERT INTO agent.fund_function_assignments (function_key,agent_name,responsibility,evidence)
SELECT function.function_key,'Risk Agent','challenger',
       '[{"source":"agent.fund_function_registry","challenge":"limits, downside, client mandate, data quality, and execution boundary"}]'::jsonb
FROM agent.fund_function_registry function
WHERE function.department_key IN ('portfolio','quant','research','trading','tactical','treasury')
  AND NOT EXISTS (
      SELECT 1 FROM agent.fund_function_assignments existing
      WHERE existing.function_key=function.function_key
        AND existing.agent_name='Risk Agent'
        AND existing.responsibility='challenger'
  );

CREATE OR REPLACE VIEW agent.v_fund_function_coverage AS
SELECT function.function_key,function.function_name,function.department_key,
       function.function_class,function.criticality,function.objective,
       function.human_final_required,function.live_execution_allowed,
       count(*) FILTER (WHERE assignment.responsibility='owner')::INT AS owner_count,
       count(*) FILTER (WHERE assignment.responsibility='reviewer')::INT AS reviewer_count,
       count(*) FILTER (WHERE assignment.responsibility='challenger')::INT AS challenger_count,
       array_agg(assignment.agent_name ORDER BY assignment.responsibility,assignment.agent_name)
           FILTER (WHERE assignment.agent_name IS NOT NULL) AS assigned_agents,
       bool_and(profile.status='active') FILTER (WHERE assignment.agent_name IS NOT NULL) AS assigned_agents_active,
       CASE
           WHEN count(*) FILTER (WHERE assignment.responsibility='owner')=0 THEN 'missing_owner'
           WHEN count(*) FILTER (WHERE assignment.responsibility='reviewer')=0 THEN 'missing_reviewer'
           WHEN NOT coalesce(bool_and(profile.status='active') FILTER (WHERE assignment.agent_name IS NOT NULL),false) THEN 'inactive_assignment'
           ELSE 'covered'
       END AS coverage_status
FROM agent.fund_function_registry function
LEFT JOIN agent.fund_function_assignments assignment USING(function_key)
LEFT JOIN agent.profiles profile USING(agent_name)
WHERE function.status='active'
GROUP BY function.function_key,function.function_name,function.department_key,
         function.function_class,function.criticality,function.objective,
         function.human_final_required,function.live_execution_allowed;

CREATE OR REPLACE VIEW agent.v_agent_operating_readiness AS
WITH run_stats AS (
    SELECT agent_name,count(*)::INT AS worker_runs,
           count(*) FILTER (WHERE status='completed')::INT AS completed_runs,
           count(*) FILTER (WHERE status IN ('failed','blocked'))::INT AS failed_runs,
           max(finished_at) AS latest_worker_finished_at
    FROM agent.worker_runs GROUP BY agent_name
), task_stats AS (
    SELECT owner_agent AS agent_name,
           count(*) FILTER (WHERE status IN ('queued','in_progress','needs_review','blocked'))::INT AS open_tasks,
           count(*) FILTER (WHERE status='blocked')::INT AS blocked_tasks
    FROM agent.tasks GROUP BY owner_agent
), route_state AS (
    SELECT assignment.agent_name,assignment.primary_route,assignment.fallback_route,
           primary_route.runtime_status AS primary_route_status,
           fallback_route.runtime_status AS fallback_route_status,
           primary_route.default_provider AS primary_provider,
           (primary_route.runtime_status='ready' OR fallback_route.runtime_status='ready') AS execution_route_ready,
           (primary_route.runtime_status='ready' AND primary_route.default_provider NOT IN ('local_python','deterministic','local_tools')) AS model_reasoning_ready
    FROM agent.agent_model_assignments assignment
    LEFT JOIN agent.v_model_route_runtime_control primary_route ON primary_route.route_name=assignment.primary_route
    LEFT JOIN agent.v_model_route_runtime_control fallback_route ON fallback_route.route_name=assignment.fallback_route
)
SELECT profile.agent_name,profile.display_title,profile.department,
       (hierarchy.agent_name IS NOT NULL) AS hierarchy_ready,
       (mailbox.agent_name IS NOT NULL) AS mailbox_ready,
       (character.agent_name IS NOT NULL) AS character_ready,
       coalesce(route.execution_route_ready,false) AS model_route_ready,
       (coalesce(skills.skill_count,0)>0) AS skills_ready,
       coalesce(skills.skill_count,0)::INT AS skill_count,
       coalesce(run_stats.worker_runs,0) AS worker_runs,
       coalesce(run_stats.completed_runs,0) AS completed_runs,
       coalesce(run_stats.failed_runs,0) AS failed_runs,
       coalesce(task_stats.open_tasks,0) AS open_tasks,
       coalesce(task_stats.blocked_tasks,0) AS blocked_tasks,
       run_stats.latest_worker_finished_at,
       round((
           8*(hierarchy.agent_name IS NOT NULL)::INT +
           8*(mailbox.agent_name IS NOT NULL)::INT +
           8*(character.agent_name IS NOT NULL)::INT +
           8*(assignment.agent_name IS NOT NULL)::INT +
           13*(coalesce(skills.skill_count,0)>0)::INT +
           20*coalesce(capability.tools_ready,false)::INT +
           15*coalesce(route.execution_route_ready,false)::INT +
           20*(coalesce(run_stats.completed_runs,0)>0)::INT
       )::NUMERIC,2) AS operating_readiness_score,
       CASE WHEN coalesce(run_stats.worker_runs,0)=0 THEN NULL
            ELSE round(100.0*run_stats.completed_runs/greatest(run_stats.worker_runs,1),2) END AS reliability_score,
       CASE WHEN coalesce(run_stats.worker_runs,0)>=10 THEN 'measured'
            WHEN coalesce(run_stats.worker_runs,0)>=3 THEN 'limited'
            ELSE 'insufficient_history' END AS reliability_confidence,
       CASE
           WHEN hierarchy.agent_name IS NULL OR mailbox.agent_name IS NULL OR character.agent_name IS NULL
             OR assignment.agent_name IS NULL OR coalesce(skills.skill_count,0)=0 THEN 'incomplete_structure'
           WHEN NOT coalesce(capability.tools_ready,false) THEN 'capability_pending'
           WHEN NOT coalesce(route.execution_route_ready,false) THEN 'route_pending'
           WHEN coalesce(run_stats.completed_runs,0)=0 THEN 'untested'
           ELSE 'operational'
       END AS readiness_status,
       route.primary_route AS primary_model_route,route.fallback_route AS fallback_model_route,
       route.primary_route_status,route.fallback_route_status,
       (assignment.agent_name IS NOT NULL) AS model_assignment_ready,
       (coalesce(run_stats.completed_runs,0)>0) AS runtime_tested,
       coalesce(route.model_reasoning_ready,false) AS model_reasoning_ready,
       coalesce(capability.tools_ready,false) AS tools_ready,
       coalesce(capability.requested_tool_count,0) AS requested_tool_count,
       coalesce(capability.resolved_tool_count,0) AS resolved_tool_count,
       coalesce(capability.ready_tool_count,0) AS ready_tool_count,
       coalesce(capability.missing_tool_count,0) AS missing_tool_count,
       coalesce(capability.missing_tools,'{}'::TEXT[]) AS missing_tools,
       CASE WHEN coalesce(route.model_reasoning_ready,false) THEN 'model_augmented'
            ELSE 'deterministic_evidence' END AS operating_mode
FROM agent.profiles profile
LEFT JOIN agent.org_hierarchy hierarchy ON hierarchy.agent_name=profile.agent_name
LEFT JOIN agent.mailboxes mailbox ON mailbox.agent_name=profile.agent_name AND mailbox.status='active'
LEFT JOIN agent.agent_characters character ON character.agent_name=profile.agent_name
LEFT JOIN agent.agent_model_assignments assignment ON assignment.agent_name=profile.agent_name
LEFT JOIN route_state route ON route.agent_name=profile.agent_name
LEFT JOIN (SELECT agent_name,count(*)::INT AS skill_count FROM agent.agent_skill_map GROUP BY agent_name) skills ON skills.agent_name=profile.agent_name
LEFT JOIN agent.v_agent_capability_readiness capability ON capability.agent_name=profile.agent_name
LEFT JOIN run_stats ON run_stats.agent_name=profile.agent_name
LEFT JOIN task_stats ON task_stats.agent_name=profile.agent_name
WHERE profile.status='active';

CREATE OR REPLACE VIEW agent.v_employee_activation_status AS
SELECT record.id,record.campaign_key,record.agent_name,profile.display_title,profile.department,
       record.task_id,record.worker_run_id,record.primary_skill_key,record.status,
       record.operating_mode,record.acceptance_checks,record.evidence,
       readiness.readiness_status,readiness.operating_mode AS current_operating_mode,
       readiness.operating_readiness_score,readiness.tools_ready,
       readiness.model_reasoning_ready,record.started_at,record.finished_at,record.updated_at
FROM agent.employee_activation_records record
JOIN agent.profiles profile USING(agent_name)
LEFT JOIN agent.v_agent_operating_readiness readiness USING(agent_name);

CREATE OR REPLACE VIEW agent.v_agent_operating_summary AS
SELECT metric,value,interpretation FROM (
    SELECT 1 rank,'active_agents'::TEXT metric,count(*)::BIGINT value,'Active governed AI employees.'::TEXT interpretation FROM agent.v_agent_operating_readiness
    UNION ALL SELECT 2,'operational_agents',count(*) FILTER (WHERE readiness_status='operational'),'Employees with complete structure, resolved tools, a usable route, and successful bounded work.' FROM agent.v_agent_operating_readiness
    UNION ALL SELECT 3,'deterministic_evidence_agents',count(*) FILTER (WHERE readiness_status='operational' AND operating_mode='deterministic_evidence'),'Operational employees restricted to source-backed deterministic work until models are installed.' FROM agent.v_agent_operating_readiness
    UNION ALL SELECT 4,'model_augmented_agents',count(*) FILTER (WHERE readiness_status='operational' AND operating_mode='model_augmented'),'Operational employees with a usable model reasoning route.' FROM agent.v_agent_operating_readiness
    UNION ALL SELECT 5,'untested_agents',count(*) FILTER (WHERE readiness_status='untested'),'Structurally and technically ready employees awaiting a bounded acceptance run.' FROM agent.v_agent_operating_readiness
    UNION ALL SELECT 6,'capability_pending_agents',count(*) FILTER (WHERE readiness_status='capability_pending'),'Employees with unresolved required tool entitlements.' FROM agent.v_agent_operating_readiness
    UNION ALL SELECT 7,'covered_fund_functions',count(*) FILTER (WHERE coverage_status='covered'),'Registered fund functions with an owner and independent reviewer.' FROM agent.v_fund_function_coverage
    UNION ALL SELECT 8,'uncovered_fund_functions',count(*) FILTER (WHERE coverage_status<>'covered'),'Must remain zero.' FROM agent.v_fund_function_coverage
    UNION ALL SELECT 9,'active_departments',count(*) FILTER (WHERE status='active'),'Active role-scoped departments.' FROM agent.department_registry
    UNION ALL SELECT 10,'active_schedules',count(*) FILTER (WHERE enabled),'Materializing schedules; agent work remains request-driven.' FROM agent.workflow_schedules
    UNION ALL SELECT 11,'structured_committees',count(*) FILTER (WHERE status='active'),'Committees with chair, quorum, challenge, and human-final gate.' FROM agent.committee_registry
    UNION ALL SELECT 12,'active_mailboxes',count(*) FILTER (WHERE status='active'),'Durable internal mailboxes.' FROM agent.mailboxes
) summary ORDER BY rank;

INSERT INTO agent.tool_registry (tool_name,tool_type,owning_agent,permission_level,enabled,description,config)
VALUES
    ('ai_os_agent_capability_readiness','mcp_tool','Jarvis','read_only',true,
     'Read role-scoped tool entitlement resolution, missing capability aliases, operating mode, and acceptance evidence.',
     '{"reads":["agent.v_agent_tool_capabilities","agent.v_agent_capability_readiness","agent.v_agent_operating_readiness","agent.v_employee_activation_status"]}'::jsonb),
    ('ai_os_fund_function_coverage','mcp_tool','Charlie Munger','read_only',true,
     'Read every active hedge-fund and operating-office function with owner, reviewer, challenger, and coverage status.',
     '{"reads":["agent.v_fund_function_coverage","agent.fund_function_assignments"],"human_final_required":true,"live_execution_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    owning_agent=EXCLUDED.owning_agent,permission_level=EXCLUDED.permission_level,
    enabled=EXCLUDED.enabled,description=EXCLUDED.description,config=EXCLUDED.config;

COMMIT;
