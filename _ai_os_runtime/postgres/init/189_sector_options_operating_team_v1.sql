BEGIN;

INSERT INTO agent.department_registry (
    department_key,department_name,mission,lead_agent,status,priority,
    core_workflows,required_next_builds,guardrails
) VALUES (
    'sector','Sector Intelligence Office',
    'Own Indian sector taxonomy, fundamentals, valuation, breadth, relative strength, flows, custom indices, research committees, and portfolio-level sector conclusions.',
    'Sector Portfolio Manager','active','critical',
    ARRAY['sector source validation','sector fundamental aggregation','sector market monitor','custom index governance','sector committee review'],
    ARRAY['licensed sector packages','primary filing evidence','validated market and ownership observations'],
    '{"source_required":true,"seed_data_allowed":false,"human_capital_approval":true,"broker_order_allowed":false,"tradingview_role":"artifact_consumer_only"}'::jsonb
)
ON CONFLICT (department_key) DO UPDATE SET
    department_name=EXCLUDED.department_name,mission=EXCLUDED.mission,
    lead_agent=EXCLUDED.lead_agent,status=EXCLUDED.status,priority=EXCLUDED.priority,
    core_workflows=EXCLUDED.core_workflows,required_next_builds=EXCLUDED.required_next_builds,
    guardrails=EXCLUDED.guardrails,updated_at=now();

WITH roles(agent_name,department,display_title,role_scope,persona,default_model_route,default_tools) AS (
    VALUES
    ('Sector Portfolio Manager','sector','Head Of Sector Intelligence',
     'Own sector coverage priorities, custom-index governance, committee packets, cross-sector opportunity cost, and portfolio-level sector conclusions.',
     'Cross-sectional portfolio manager who challenges crowding, stale classifications, and unsupported rotation narratives.',
     'research_company_analysis',ARRAY['postgres','sector_warehouse','obsidian','qdrant_search']),
    ('Sector Fundamental Analyst','sector','Sector Fundamental Analyst',
     'Own sector revenue, margin, ROCE, leverage, valuation-band, market-share, capacity, raw-material, and peer aggregation evidence.',
     'Industry analyst who reconciles bottom-up company facts before drawing sector conclusions.',
     'research_company_analysis',ARRAY['postgres','sector_warehouse','filing_evidence','obsidian']),
    ('Sector Market Structure Analyst','sector','Sector Market Structure Analyst',
     'Own sector price, volume, delivery, futures OI, options flow, breadth, relative strength, regime, and liquidity observations.',
     'Market-structure analyst who labels event time, staleness, liquidity, and calculation assumptions.',
     'always_on_daily_driver',ARRAY['postgres','market_data','sector_warehouse','tradingview_controller']),
    ('Sector Flow And Ownership Analyst','sector','Sector Flow And Ownership Analyst',
     'Own FII, DII, mutual-fund, promoter, insider, bulk, block, pledge, and shareholding-change evidence by sector.',
     'Ownership analyst who separates reported holdings, transaction flow, and inference.',
     'research_company_analysis',ARRAY['postgres','filing_evidence','sector_warehouse','obsidian']),
    ('Sector Data Steward','sector','Sector Data Steward',
     'Validate licensed or primary-source sector packages, effective-dated memberships, lineage, duplicate hashes, and freshness blocks.',
     'Data steward who rejects unlicensed, synthetic, stale, or lineage-free sector inputs.',
     'agent_worker_deterministic',ARRAY['postgres','sector_importer','data_quality_checks']),
    ('Options Data Quality Agent','data','Options Data Quality Agent',
     'Own immutable option-chain batches, quote freshness, liquidity filters, valuation-policy evidence, analytics readiness, and replay coverage.',
     'Point-in-time data-quality owner who blocks IV and Greeks whenever source or valuation inputs are unverified.',
     'agent_worker_deterministic',ARRAY['postgres','zerodha_read_only','options_math_engine','data_quality_checks'])
)
INSERT INTO agent.profiles (
    agent_name,department,role_scope,default_model_route,default_tools,
    permission_level,status,guardrails,output_targets,display_title,
    persona,operating_style,mental_models,escalation_rules,daily_cadence,
    cost_policy,human_interface
)
SELECT agent_name,department,role_scope,default_model_route,default_tools,
       'write_with_approval','active',
       '{"evidence_required":true,"no_broker_orders":true,"no_seed_data":true,"human_approval_for_capital":true}'::jsonb,
       ARRAY['agent.tasks','agent.inbox_items','agent.output_artifacts','knowledge.obsidian_notes'],
       display_title,persona,
       'Retrieve point-in-time role-scoped evidence, run deterministic calculations where applicable, state gaps and dissent, then create a durable handoff.',
       ARRAY['source_lineage','point_in_time','base_rates','opportunity_cost'],
       '{"capital_action":"Charlie Munger","risk_exception":"Risk Agent","source_failure":"Data Steward","runtime_failure":"Jarvis"}'::jsonb,
       'Event-driven inbox plus daily freshness review; unresolved material items enter the executive brief.',
       'local_first_cloud_only_after_approval',
       'Assign work through Charlie or the Agent Office. Every conclusion shows source, as-of time, assumptions, owner, and review state.'
FROM roles
ON CONFLICT (agent_name) DO UPDATE SET
    department=EXCLUDED.department,role_scope=EXCLUDED.role_scope,
    default_model_route=EXCLUDED.default_model_route,default_tools=EXCLUDED.default_tools,
    permission_level=EXCLUDED.permission_level,status=EXCLUDED.status,
    guardrails=EXCLUDED.guardrails,output_targets=EXCLUDED.output_targets,
    display_title=EXCLUDED.display_title,persona=EXCLUDED.persona,
    operating_style=EXCLUDED.operating_style,mental_models=EXCLUDED.mental_models,
    escalation_rules=EXCLUDED.escalation_rules,daily_cadence=EXCLUDED.daily_cadence,
    cost_policy=EXCLUDED.cost_policy,human_interface=EXCLUDED.human_interface,
    updated_at=now();

WITH skills(skill_key,skill_name,owner_department,input_sources,output_targets,required_tools,risk_notes,prompt_template) AS (
    VALUES
    ('sector_portfolio_management','Sector Portfolio Management','sector',
     ARRAY['sector_intelligence.v_sector_data_freshness','sector_intelligence.v_custom_index_control','sector_intelligence.v_sector_committee_control','portfolio.v_latest_positions'],
     ARRAY['sector_intelligence.sector_committee_packets','agent.output_artifacts','knowledge.obsidian_notes'],
     ARRAY['postgres_read_model','sector_intelligence_engine','obsidian_writeback'],
     'No allocation or rotation recommendation without current source coverage, independent risk, and human committee approval.',
     'Compare sector fundamentals, valuation, market structure, ownership, macro sensitivity, crowding, and portfolio fit. Preserve dissent and missing evidence.'),
    ('sector_fundamental_review','Sector Fundamental Review','sector',
     ARRAY['sector_intelligence.sector_aggregates','sector_intelligence.valuation_bands','sector_intelligence.market_share_observations','sector_intelligence.capacity_observations','research.company_statement_facts'],
     ARRAY['sector_intelligence.research_coverage','agent.output_artifacts','knowledge.obsidian_notes'],
     ARRAY['postgres_read_model','filing_evidence_reader','obsidian_writeback'],
     'Aggregates must retain constituent coverage, weighting method, source lineage, and as-of date.',
     'Build a source-linked sector fundamental teardown and identify leaders, challengers, improvers, deteriorators, and evidence gaps.'),
    ('sector_market_structure_review','Sector Market Structure Review','sector',
     ARRAY['sector_intelligence.market_monitor_observations','sector_intelligence.relative_strength_observations','sector_intelligence.breadth_observations','sector_intelligence.flow_observations'],
     ARRAY['sector_intelligence.sector_rankings','sector_intelligence.generated_chart_artifacts','agent.output_artifacts'],
     ARRAY['postgres_read_model','sector_intelligence_engine','tradingview_desktop_controller'],
     'TradingView is a logged-in visualization workspace only; calculations and history remain in the deterministic warehouse.',
     'Review multi-horizon relative strength, breadth, volume, delivery, derivatives, liquidity, and regime with freshness flags.'),
    ('sector_flow_ownership_review','Sector Flow And Ownership Review','sector',
     ARRAY['sector_intelligence.flow_observations','sector_intelligence.ownership_observations','research.corporate_filings'],
     ARRAY['sector_intelligence.research_coverage','agent.output_artifacts','knowledge.obsidian_notes'],
     ARRAY['postgres_read_model','filing_evidence_reader'],
     'Reported holdings, transaction flows, and inferred positioning must remain separately labelled.',
     'Reconcile institutional, promoter, insider, bulk, block, pledge, and shareholding evidence by sector and period.'),
    ('sector_data_quality_control','Sector Data Quality Control','sector',
     ARRAY['sector_intelligence.source_import_runs','sector_intelligence.taxonomy_nodes','sector_intelligence.instrument_membership_history'],
     ARRAY['sector_intelligence.source_import_runs','agent.output_artifacts'],
     ARRAY['sector_intelligence_package_importer','postgres_read_model','data_quality_checks'],
     'Reject seed data, duplicate package hashes, missing evidence, invalid effective dates, and unsupported memberships.',
     'Validate the package schema, source rights, hashes, effective dates, identifiers, row counts, lineage, and freshness before persistence.'),
    ('options_data_quality_control','Institutional Options Data Quality Control','data',
     ARRAY['trading.option_chain_snapshot_batches','trading.option_chain_contract_snapshots','trading.option_valuation_policies','ops.institutional_pipeline_runs'],
     ARRAY['trading.option_iv_greeks_results','trading.option_analytics_alerts','agent.output_artifacts'],
     ARRAY['institutional_options_materializer','options_math_engine','postgres_read_model'],
     'Never substitute provider IV or Greeks for validated calculations; stale, illiquid, or policy-missing batches remain blocked.',
     'Validate event time, receipt time, quote freshness, liquidity, rates, dividends, model family, replay coverage, and deterministic output status.')
)
INSERT INTO agent.skills (
    skill_key,skill_name,skill_family,skill_type,owner_department,status,
    execution_mode,permission_level,trigger_phrases,input_sources,output_targets,
    required_tools,risk_notes,prompt_template,config
)
SELECT skill_key,skill_name,'institutional_intelligence','operating_skill',owner_department,'active',
       'deterministic_tools_then_local_model','write_with_approval',ARRAY[lower(skill_name)],
       input_sources,output_targets,required_tools,risk_notes,prompt_template,
       '{"seed_data_allowed":false,"live_execution_allowed":false,"broker_order_allowed":false}'::jsonb
FROM skills
ON CONFLICT (skill_key) DO UPDATE SET
    skill_name=EXCLUDED.skill_name,skill_family=EXCLUDED.skill_family,
    owner_department=EXCLUDED.owner_department,status=EXCLUDED.status,
    execution_mode=EXCLUDED.execution_mode,permission_level=EXCLUDED.permission_level,
    input_sources=EXCLUDED.input_sources,output_targets=EXCLUDED.output_targets,
    required_tools=EXCLUDED.required_tools,risk_notes=EXCLUDED.risk_notes,
    prompt_template=EXCLUDED.prompt_template,config=EXCLUDED.config,updated_at=now();

WITH hierarchy(agent_name,reports_to_agent,role_rank,hierarchy_level) AS (
    VALUES
    ('Sector Portfolio Manager','CIO Agent',25,'department_head'),
    ('Sector Fundamental Analyst','Sector Portfolio Manager',92,'specialist'),
    ('Sector Market Structure Analyst','Sector Portfolio Manager',93,'specialist'),
    ('Sector Flow And Ownership Analyst','Sector Portfolio Manager',94,'specialist'),
    ('Sector Data Steward','Sector Portfolio Manager',95,'control_owner'),
    ('Options Data Quality Agent','Data Steward',96,'control_owner')
)
INSERT INTO agent.org_hierarchy (
    agent_name,reports_to_agent,department_key,role_rank,hierarchy_level,
    authority_scope,decision_rights,must_consult,can_delegate_to,approval_required_for
)
SELECT profile.agent_name,hierarchy.reports_to_agent,profile.department,
       hierarchy.role_rank,hierarchy.hierarchy_level,profile.role_scope,
       ARRAY['prepare_evidence','run_deterministic_analysis','recommend_review','open_task'],
       ARRAY[hierarchy.reports_to_agent,'Risk Agent'],ARRAY[]::text[],
       ARRAY['capital_action','live_execution','external_send','policy_exception']
FROM hierarchy JOIN agent.profiles profile USING(agent_name)
ON CONFLICT (agent_name) DO UPDATE SET
    reports_to_agent=EXCLUDED.reports_to_agent,department_key=EXCLUDED.department_key,
    role_rank=EXCLUDED.role_rank,hierarchy_level=EXCLUDED.hierarchy_level,
    authority_scope=EXCLUDED.authority_scope,decision_rights=EXCLUDED.decision_rights,
    must_consult=EXCLUDED.must_consult,approval_required_for=EXCLUDED.approval_required_for,
    updated_at=now();

WITH mappings(agent_name,skill_key,is_primary) AS (
    VALUES
    ('Sector Portfolio Manager','sector_portfolio_management',true),
    ('Sector Fundamental Analyst','sector_fundamental_review',true),
    ('Sector Market Structure Analyst','sector_market_structure_review',true),
    ('Sector Flow And Ownership Analyst','sector_flow_ownership_review',true),
    ('Sector Data Steward','sector_data_quality_control',true),
    ('Options Data Quality Agent','options_data_quality_control',true),
    ('Options Analyst','options_data_quality_control',false),
    ('Sector Rotation Agent','sector_market_structure_review',false),
    ('Data Steward','sector_data_quality_control',false)
)
INSERT INTO agent.agent_skill_map (agent_name,skill_key,proficiency,is_primary,activation_rules)
SELECT agent_name,skill_key,CASE WHEN is_primary THEN 'expert' ELSE 'working' END,is_primary,
       '{"source_required":true,"capital_action_allowed":false,"broker_order_allowed":false}'::jsonb
FROM mappings
ON CONFLICT (agent_name,skill_key) DO UPDATE SET
    proficiency=EXCLUDED.proficiency,is_primary=EXCLUDED.is_primary,
    activation_rules=EXCLUDED.activation_rules,updated_at=now();

INSERT INTO agent.mailboxes (mailbox_key,agent_name,display_name,address,purpose,notification_policy)
SELECT lower(regexp_replace(profile.agent_name,'[^a-zA-Z0-9]+','-','g')),
       profile.agent_name,profile.display_title,
       lower(regexp_replace(profile.agent_name,'[^a-zA-Z0-9]+','-','g')) || '@ai-office.local',
       profile.role_scope,
       '{"critical":"immediate","high":"hourly","normal":"daily_digest","low":"weekly_digest"}'::jsonb
FROM agent.profiles profile
WHERE profile.agent_name IN (
    'Sector Portfolio Manager','Sector Fundamental Analyst','Sector Market Structure Analyst',
    'Sector Flow And Ownership Analyst','Sector Data Steward','Options Data Quality Agent'
)
ON CONFLICT (mailbox_key) DO UPDATE SET
    display_name=EXCLUDED.display_name,purpose=EXCLUDED.purpose,
    notification_policy=EXCLUDED.notification_policy,status='active',updated_at=now();

INSERT INTO agent.agent_characters (
    agent_name,character_key,character_name,avatar_role,visual_traits,
    voice_style,office_location,animation_state,color_token,icon_hint,character_prompt
)
SELECT profile.agent_name,lower(regexp_replace(profile.agent_name,'[^a-zA-Z0-9]+','-','g')),
       profile.display_title,profile.department,
       'Institutional office attire; sector or data-quality marker; evidence freshness and current task visible.',
       profile.persona,profile.department || ' office','working',
       CASE WHEN profile.department='sector' THEN '#2f8f83' ELSE '#42617a' END,
       CASE WHEN profile.department='sector' THEN 'network' ELSE 'database-zap' END,
       profile.persona || ' ' || profile.operating_style ||
       ' Speak in first person. Facts and event time first. Never invent evidence, silently default a model input, place an order, or approve your own exception.'
FROM agent.profiles profile
WHERE profile.agent_name IN (
    'Sector Portfolio Manager','Sector Fundamental Analyst','Sector Market Structure Analyst',
    'Sector Flow And Ownership Analyst','Sector Data Steward','Options Data Quality Agent'
)
ON CONFLICT (agent_name) DO UPDATE SET
    character_name=EXCLUDED.character_name,avatar_role=EXCLUDED.avatar_role,
    visual_traits=EXCLUDED.visual_traits,voice_style=EXCLUDED.voice_style,
    office_location=EXCLUDED.office_location,animation_state=EXCLUDED.animation_state,
    color_token=EXCLUDED.color_token,icon_hint=EXCLUDED.icon_hint,
    character_prompt=EXCLUDED.character_prompt,updated_at=now();

INSERT INTO agent.agent_model_assignments (
    agent_name,primary_route,primary_model_key,fallback_route,escalation_route,
    context_policy,cost_policy,max_autonomous_cost_tier,escalation_triggers,notes
)
SELECT profile.agent_name,profile.default_model_route,'ollama_llama3_2_3b',
       'agent_worker_deterministic','frontier_investment_review',
       'Retrieve only role-scoped point-in-time SQL, Obsidian, Qdrant, task, and message evidence. Preserve citations and privacy class.',
       'local_first_cloud_only_after_human_approval','local',
       ARRAY['bounded local route failed','material high-stakes committee decision','source document exceeds local context'],
       'Deterministic calculations and local synthesis are the default. Cloud escalation is explicit, audited, and may not receive client-private rows.'
FROM agent.profiles profile
WHERE profile.agent_name IN (
    'Sector Portfolio Manager','Sector Fundamental Analyst','Sector Market Structure Analyst',
    'Sector Flow And Ownership Analyst','Sector Data Steward','Options Data Quality Agent'
)
ON CONFLICT (agent_name) DO UPDATE SET
    primary_route=EXCLUDED.primary_route,fallback_route=EXCLUDED.fallback_route,
    escalation_route=EXCLUDED.escalation_route,context_policy=EXCLUDED.context_policy,
    cost_policy=EXCLUDED.cost_policy,max_autonomous_cost_tier=EXCLUDED.max_autonomous_cost_tier,
    escalation_triggers=EXCLUDED.escalation_triggers,notes=EXCLUDED.notes,updated_at=now();

COMMIT;
