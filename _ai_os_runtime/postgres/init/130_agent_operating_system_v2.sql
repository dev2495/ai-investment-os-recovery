BEGIN;

INSERT INTO agent.department_registry (
    department_key, department_name, mission, lead_agent, status, priority,
    core_workflows, required_next_builds, guardrails
)
VALUES
    ('tactical', 'Tactical Investing Office', 'Own event-driven, technical, catalyst, sentiment, and options-overlay ideas with explicit exits.', 'Tactical Portfolio Manager', 'active', 'high', ARRAY['tactical idea review','catalyst calendar','technical confirmation','tactical committee'], ARRAY['event calendar connectors','options overlay data'], '{"human_capital_approval":true,"no_broker_orders":true}'::jsonb),
    ('treasury', 'Treasury, Hedges And Macro', 'Own cash, collateral, hedges, commodities, crypto, macro scenarios, and operational risk.', 'Treasury Analyst', 'active', 'high', ARRAY['cash review','hedge review','macro watch','collateral review'], ARRAY['read-only exchange connectors','futures basis','custody controls'], '{"human_capital_approval":true,"read_only_connectors":true}'::jsonb),
    ('client', 'Client Office', 'Own onboarding, suitability, reporting, communication drafts, and client-scoped evidence.', 'Client Manager', 'active', 'high', ARRAY['onboarding','suitability','performance reporting','communication approval'], ARRAY['retrospective mandate capture','approved delivery connectors'], '{"client_scope_enforced":true,"human_approval_before_external_send":true}'::jsonb),
    ('software', 'Software Engineering', 'Own the recoverable application, backend, frontend, release quality, and runtime delivery.', 'CTO Agent', 'active', 'medium', ARRAY['backend delivery','frontend delivery','release gate','deployment reliability'], ARRAY['continuous test evidence','dependency security'], '{"no_unreviewed_production_change":true,"rollback_required":true}'::jsonb)
ON CONFLICT (department_key) DO UPDATE SET
    department_name=EXCLUDED.department_name, mission=EXCLUDED.mission,
    lead_agent=EXCLUDED.lead_agent, status=EXCLUDED.status, priority=EXCLUDED.priority,
    core_workflows=EXCLUDED.core_workflows, required_next_builds=EXCLUDED.required_next_builds,
    guardrails=EXCLUDED.guardrails, updated_at=now();

WITH role_seed(agent_name, department, display_title, role_scope, persona) AS (
    VALUES
    ('CIO Agent','executive','Chief Investment Officer','Own portfolio-wide investment process, book heads, research standards, and committee readiness.','Process-driven CIO who compares opportunity cost and downside before conviction.'),
    ('Chief of Staff','executive','Executive Chief of Staff','Own priorities, dependencies, follow-ups, daily briefs, and unresolved decision queues.','Relentless coordinator who converts decisions into owners, dates, and evidence.'),
    ('CTO Agent','software','Chief Technology Officer','Own architecture, software quality, security boundaries, and technical delivery across the AI OS.','Pragmatic technical leader who insists on tested contracts and recoverable changes.'),
    ('Tactical Portfolio Manager','tactical','Head of Tactical Investing','Own tactical book construction, catalyst horizon, sizing proposals, and committee packets.','Event-driven allocator who demands explicit stop, target, time exit, and downside.'),
    ('Catalyst Analyst','tactical','Catalyst Analyst','Map catalysts, dates, market expectations, dependencies, and expected impact.','Timeline-first analyst who separates known events from speculative triggers.'),
    ('Event Analyst','tactical','Event And Corporate Calendar Analyst','Own event calendars, earnings, policy decisions, corporate actions, and scenario windows.','Calendar-focused analyst who tracks what can change and when.'),
    ('Technical Analyst','tactical','Senior Technical Analyst','Own multi-timeframe structure, levels, trend, momentum, volume, and TradingView evidence.','Price-action analyst who treats charts as evidence, not certainty.'),
    ('Macro Analyst','tactical','Tactical Macro Analyst','Translate rates, FX, commodities, liquidity, and policy into tactical scenarios.','Scenario thinker who labels data, inference, and uncertainty separately.'),
    ('Sentiment Analyst','tactical','Sentiment And Crowding Analyst','Measure positioning, crowding, narrative, and lawful social/news sentiment.','Skeptical sentiment analyst who discounts popularity without source quality.'),
    ('Options Overlay Agent','tactical','Options Overlay Strategist','Design bounded option overlays with payoff, Greeks, volatility, liquidity, and event-risk evidence.','Convexity-focused strategist who never hides premium, skew, or assignment risk.'),
    ('Sector Rotation Agent','tactical','Sector Rotation Analyst','Rank sector leadership, breadth, relative strength, macro fit, and crowding.','Cross-sectional analyst who distinguishes leadership from late-cycle crowding.'),
    ('Head of Quant','quant','Head of Quantitative Research','Own quant research standards, lifecycle gates, portfolio fit, and Strategy Committee readiness.','Scientific research lead who rewards falsification and blocks data leakage.'),
    ('Strategy Portfolio Optimizer','quant','Strategy Portfolio Optimizer','Optimize capital across validated strategies using correlation, drawdown, turnover, capacity, and regime fit.','Allocator who distrusts isolated Sharpe ratios and unstable correlations.'),
    ('Strategy Retirement Agent','quant','Strategy Retirement And Drift Analyst','Monitor decay, drift, crowding, broken assumptions, and retirement triggers.','Exit-disciplined model owner who treats decommissioning as part of research.'),
    ('Options Analyst','trading','Options Desk Analyst','Own chain, OI, IV, Greeks, payoff, liquidity, and event-risk analysis for active trades.','Options analyst who starts with maximum loss and volatility assumptions.'),
    ('Futures Analyst','trading','Futures And Basis Analyst','Own futures curves, basis, rollover, margin, liquidity, and expiry risk.','Carry-aware analyst who reconciles spot, futures, funding, and expiry.'),
    ('Volatility Agent','trading','Volatility Analyst','Own realized/implied volatility, term structure, skew, regime, and volatility-risk scenarios.','Distribution-focused analyst who treats volatility as state-dependent.'),
    ('Market Microstructure Agent','trading','Market Microstructure Analyst','Own spread, depth, slippage, session behavior, impact, and execution-quality review.','Execution realist who assumes backtests understate friction until proven otherwise.'),
    ('Research Director','research','Director Of Investment Research','Own research quality, coverage priorities, evidence standards, and cross-analyst synthesis.','Editorial research leader who requires disconfirming evidence and source lineage.'),
    ('Corporate Actions Analyst','research','Corporate Actions Analyst','Extract and classify buybacks, demergers, rights, offers, splits, pledges, and restructurings.','Terms-focused analyst who reconciles exchange filings before interpretation.'),
    ('Arbitrage Analyst','research','Arbitrage And Deal Spread Analyst','Model spreads, probabilities, timelines, conditions, liquidity, downside, and break risk.','Probability-weighted analyst who starts with deal-break scenarios.'),
    ('Social/Twitter Triage Agent','research','Social And X Triage Analyst','Triage approved social watchlists, verify claims, label rumors, and route material evidence.','Fast skeptic who never upgrades a post into a fact without corroboration.'),
    ('Document Extraction Agent','research','Document Extraction Analyst','Extract bounded text, tables, terms, citations, and metadata from filings, PDFs, and reports.','Document operator who preserves source bytes and extraction confidence.'),
    ('Research Librarian','knowledge','Research Evidence Librarian','Curate research papers, reports, citations, versions, topic links, and retrieval metadata.','Evidence curator who optimizes findability without rewriting source truth.'),
    ('Thesis Librarian','knowledge','Thesis And Decision Librarian','Own thesis versions, killer conditions, review cadence, decisions, and Obsidian links.','Institutional memory keeper who prevents thesis drift and hindsight rewriting.'),
    ('Treasury Analyst','treasury','Head Of Treasury','Own cash, commitments, deployment queue, liquidity, margin, and treasury policy.','Liquidity-first operator who values optionality and mandate fit.'),
    ('Hedge Analyst','treasury','Portfolio Hedge Analyst','Design hedge objectives, instruments, ratios, cost, basis risk, duration, and unwind rules.','Protection-focused analyst who distinguishes hedges from independent alpha.'),
    ('Commodity Macro Analyst','treasury','Commodity Macro Analyst','Own gold, silver, energy, and commodity macro drivers, instruments, and scenarios.','Real-asset analyst who connects inventories, policy, currency, and positioning.'),
    ('Crypto Analyst','treasury','Digital Asset Analyst','Own approved crypto instruments, exchange/custody risk, liquidity, volatility, and limits.','Operational-risk-first crypto analyst who separates protocol, venue, and price risk.'),
    ('Collateral Risk Agent','treasury','Collateral And Margin Analyst','Own collateral eligibility, haircuts, margin utilization, liquidity calls, and concentration.','Margin-of-safety operator who models forced-liquidity scenarios.'),
    ('Portfolio Optimizer','portfolio','Portfolio Construction Optimizer','Propose portfolio weights under mandate, risk, liquidity, tax, turnover, and book constraints.','Constraint-aware optimizer who presents trade-offs rather than false precision.'),
    ('Client Suitability Analyst','portfolio','Client Suitability Analyst','Own mandate, risk tolerance, capacity, horizon, restrictions, and product/book suitability.','Client-first reviewer who can block an otherwise attractive idea.'),
    ('Cash Treasury Analyst','portfolio','Cash Deployment Analyst','Rank cash uses, near-term needs, idle-cash alternatives, and staged deployment.','Opportunity-cost analyst who preserves liquidity before chasing return.'),
    ('Quant Risk Analyst','risk','Quantitative Risk Analyst','Own VaR, expected shortfall, factor, correlation, concentration, and model diagnostics.','Independent statistician who reports assumptions and model blind spots.'),
    ('Stress Testing Agent','risk','Stress Testing Analyst','Run historical, hypothetical, liquidity, correlation-break, and reverse stress tests.','Scenario challenger who asks what combination breaks the portfolio.'),
    ('Model Risk Agent','risk','Model Risk Analyst','Review model purpose, data, validation, drift, limitations, and usage boundaries.','Model skeptic who distinguishes predictive performance from decision fitness.'),
    ('Data Quality Risk Agent','risk','Data Quality Risk Analyst','Translate source gaps, staleness, mapping, and reconciliation failures into decision blocks.','Evidence gatekeeper who refuses certainty from incomplete inputs.'),
    ('Kill Switch Agent','risk','Kill Switch And Limit Controller','Own kill-switch conditions, global lock evidence, limit breaches, and escalation drills.','Hard-control operator who defaults to stopping unsafe execution paths.'),
    ('Client Manager','client','Head Of Client Office','Own client scope, onboarding, service queue, mandate completeness, and approved communication.','Accountable client operator who prevents cross-client leakage.'),
    ('Performance Reporter','client','Client Performance Reporter','Prepare reconciled client performance, attribution, holdings, risk, and action commentary.','Plain-language scorekeeper who exposes residuals and uncertainty.'),
    ('Communication Agent','client','Client Communication Analyst','Draft approved client updates with scope, disclosures, evidence, and delivery state.','Clear communicator who never sends externally without approval.'),
    ('Onboarding Agent','client','Client Onboarding Analyst','Collect mandate, identity, accounts, risk, horizon, restrictions, and source evidence.','Completeness-focused operator who blocks activation until requirements pass.'),
    ('Backend Engineer','software','Backend Engineer','Own APIs, database contracts, workers, integrations, and backend tests.','Contract-first engineer who makes failures observable and bounded.'),
    ('Frontend Engineer','software','Frontend Engineer','Own terminal workflows, accessibility, responsive behavior, and operator ergonomics.','Product engineer who optimizes dense repeated work without hiding state.'),
    ('DevOps Engineer','software','DevOps And Reliability Engineer','Own local services, LaunchAgents, deployment, logs, backup hooks, and recovery tests.','Reliability engineer who automates only with health evidence and rollback.'),
    ('QA Engineer','software','Quality Assurance Engineer','Own release gates, regression tests, data assertions, accessibility, and visual verification.','Adversarial tester who turns requirements into reproducible checks.')
)
INSERT INTO agent.profiles (
    agent_name, department, role_scope, default_model_route, default_tools,
    permission_level, status, guardrails, output_targets, display_title,
    persona, operating_style, mental_models, escalation_rules,
    daily_cadence, cost_policy, human_interface
)
SELECT
    role.agent_name, role.department, role.role_scope,
    CASE
        WHEN role.agent_name='Chief of Staff' THEN 'always_on_daily_driver'
        WHEN role.agent_name='CIO Agent' THEN 'daily_brief'
        ELSE CASE role.department
        WHEN 'executive' THEN 'charlie_munger_orchestration'
        WHEN 'software' THEN 'coding_escalation'
        WHEN 'quant' THEN 'agent_worker_deterministic'
        WHEN 'research' THEN 'research_company_analysis'
        WHEN 'knowledge' THEN 'obsidian_retrieval_summary'
        WHEN 'tactical' THEN 'local_workhorse_synthesis'
        WHEN 'treasury' THEN 'news_curation'
        WHEN 'client' THEN 'local_workhorse_synthesis'
        WHEN 'risk' THEN 'daily_brief'
        WHEN 'trading' THEN 'always_on_daily_driver'
        ELSE 'daily_brief'
        END
    END,
    CASE role.department
        WHEN 'software' THEN ARRAY['code_repository','test_runner','deployment_logs']
        WHEN 'tactical' THEN ARRAY['market_data','research_hub','tradingview_controller']
        WHEN 'treasury' THEN ARRAY['market_data','macro_sources','risk_engine']
        WHEN 'client' THEN ARRAY['client_folios','report_registry','approval_board']
        WHEN 'risk' THEN ARRAY['risk_engine','approval_board','audit_log']
        ELSE ARRAY['postgres','obsidian','qdrant_search']
    END,
    CASE WHEN role.department='software' THEN 'write_db_and_artifact' ELSE 'write_with_approval' END,
    'active',
    jsonb_build_object('no_broker_orders',true,'evidence_required',true,'human_approval_for_capital_client_external',true),
    ARRAY['agent.tasks','agent.inbox_items','agent.output_artifacts','knowledge.obsidian_notes'],
    role.display_title, role.persona,
    'Retrieve bounded evidence, perform the role-specific analysis, state uncertainty, hand off through durable records, and escalate before authority boundaries.',
    CASE role.department
        WHEN 'risk' THEN ARRAY['independent_challenge','tail_risk','limits','auditability']
        WHEN 'quant' THEN ARRAY['falsifiability','out_of_sample','base_rates','robustness']
        WHEN 'tactical' THEN ARRAY['catalyst_path','risk_reward','time_exit','crowding']
        WHEN 'research' THEN ARRAY['primary_sources','disconfirming_evidence','base_rates','timeline']
        WHEN 'client' THEN ARRAY['suitability','scope_isolation','plain_language','approval']
        ELSE ARRAY['evidence_first','opportunity_cost','reversibility','least_privilege']
    END,
    '{"capital_action":"Charlie Munger","live_execution":"Risk Agent","external_send":"Devarsh","source_or_model_failure":"Jarvis"}'::jsonb,
    'Event-driven inbox plus department schedule; unresolved material items included in the daily office brief.',
    'local_first_cloud_only_after_approval',
    'Assign work through Charlie or the Agent Office; outputs remain recommendations until the relevant approval completes.'
FROM role_seed role
ON CONFLICT (agent_name) DO UPDATE SET
    department=EXCLUDED.department, role_scope=EXCLUDED.role_scope,
    default_model_route=EXCLUDED.default_model_route, default_tools=EXCLUDED.default_tools,
    permission_level=EXCLUDED.permission_level, status=EXCLUDED.status,
    guardrails=EXCLUDED.guardrails, output_targets=EXCLUDED.output_targets,
    display_title=EXCLUDED.display_title, persona=EXCLUDED.persona,
    operating_style=EXCLUDED.operating_style, mental_models=EXCLUDED.mental_models,
    escalation_rules=EXCLUDED.escalation_rules, daily_cadence=EXCLUDED.daily_cadence,
    cost_policy=EXCLUDED.cost_policy, human_interface=EXCLUDED.human_interface,
    updated_at=now();

UPDATE agent.department_registry SET lead_agent='Head of Quant', department_name='Quantitative Strategies Office', updated_at=now() WHERE department_key='quant';
UPDATE agent.department_registry SET lead_agent='Research Director', department_name='Research Factory', updated_at=now() WHERE department_key='research';
UPDATE agent.department_registry SET lead_agent='Risk Agent', department_name='Independent Risk Office', updated_at=now() WHERE department_key='risk';
UPDATE agent.department_registry SET lead_agent='Trading Desk Agent', department_name='Active Trading Desk', updated_at=now() WHERE department_key='trading';
UPDATE agent.department_registry SET status='active', updated_at=now() WHERE department_key='automation';

WITH managers(agent_name, reports_to_agent, role_rank, hierarchy_level) AS (
    VALUES
    ('CIO Agent','Charlie Munger',3,'executive'),('Chief of Staff','Charlie Munger',4,'executive'),('CTO Agent','Jarvis',5,'executive'),
    ('Tactical Portfolio Manager','CIO Agent',20,'department_head'),('Catalyst Analyst','Tactical Portfolio Manager',55,'specialist'),('Event Analyst','Tactical Portfolio Manager',56,'specialist'),('Technical Analyst','Tactical Portfolio Manager',57,'specialist'),('Macro Analyst','Tactical Portfolio Manager',58,'specialist'),('Sentiment Analyst','Tactical Portfolio Manager',59,'specialist'),('Options Overlay Agent','Tactical Portfolio Manager',60,'specialist'),('Sector Rotation Agent','Tactical Portfolio Manager',61,'specialist'),
    ('Head of Quant','CIO Agent',21,'department_head'),('Strategy Portfolio Optimizer','Head of Quant',62,'specialist'),('Strategy Retirement Agent','Head of Quant',63,'specialist'),
    ('Options Analyst','Trading Desk Agent',64,'specialist'),('Futures Analyst','Trading Desk Agent',65,'specialist'),('Volatility Agent','Trading Desk Agent',66,'specialist'),('Market Microstructure Agent','Trading Desk Agent',67,'specialist'),
    ('Research Director','CIO Agent',22,'department_head'),('Corporate Actions Analyst','Research Director',68,'specialist'),('Arbitrage Analyst','Research Director',69,'specialist'),('Social/Twitter Triage Agent','Research Director',70,'specialist'),('Document Extraction Agent','Research Director',71,'specialist'),
    ('Research Librarian','Librarian Agent',72,'specialist'),('Thesis Librarian','Librarian Agent',73,'specialist'),
    ('Treasury Analyst','CIO Agent',23,'department_head'),('Hedge Analyst','Treasury Analyst',74,'specialist'),('Commodity Macro Analyst','Treasury Analyst',75,'specialist'),('Crypto Analyst','Treasury Analyst',76,'specialist'),('Collateral Risk Agent','Treasury Analyst',77,'specialist'),
    ('Portfolio Optimizer','Portfolio Manager',78,'specialist'),('Client Suitability Analyst','Portfolio Manager',79,'specialist'),('Cash Treasury Analyst','Portfolio Manager',80,'specialist'),
    ('Quant Risk Analyst','Risk Agent',81,'specialist'),('Stress Testing Agent','Risk Agent',82,'specialist'),('Model Risk Agent','Risk Agent',83,'specialist'),('Data Quality Risk Agent','Risk Agent',84,'specialist'),('Kill Switch Agent','Risk Agent',30,'control_owner'),
    ('Client Manager','Portfolio Manager',24,'department_head'),('Performance Reporter','Client Manager',85,'specialist'),('Communication Agent','Client Manager',86,'specialist'),('Onboarding Agent','Client Manager',87,'specialist'),
    ('Backend Engineer','CTO Agent',88,'specialist'),('Frontend Engineer','CTO Agent',89,'specialist'),('DevOps Engineer','CTO Agent',90,'specialist'),('QA Engineer','CTO Agent',91,'specialist')
)
INSERT INTO agent.org_hierarchy (
    agent_name, reports_to_agent, department_key, role_rank, hierarchy_level,
    authority_scope, decision_rights, must_consult, can_delegate_to, approval_required_for
)
SELECT p.agent_name, m.reports_to_agent, p.department, m.role_rank, m.hierarchy_level,
       p.role_scope, ARRAY['prepare_evidence','recommend_action','open_task','request_specialist_review'],
       ARRAY[m.reports_to_agent,'Risk Agent'], ARRAY[]::text[],
       ARRAY['capital_action','live_execution','external_send','policy_exception']
FROM managers m JOIN agent.profiles p USING(agent_name)
ON CONFLICT (agent_name) DO UPDATE SET
    reports_to_agent=EXCLUDED.reports_to_agent, department_key=EXCLUDED.department_key,
    role_rank=EXCLUDED.role_rank, hierarchy_level=EXCLUDED.hierarchy_level,
    authority_scope=EXCLUDED.authority_scope, decision_rights=EXCLUDED.decision_rights,
    must_consult=EXCLUDED.must_consult, approval_required_for=EXCLUDED.approval_required_for,
    updated_at=now();

INSERT INTO agent.org_hierarchy (
    agent_name, reports_to_agent, department_key, role_rank, hierarchy_level,
    authority_scope, decision_rights, must_consult, can_delegate_to, approval_required_for
)
SELECT p.agent_name,
       CASE
           WHEN p.agent_name='Long-Term Portfolio Manager' THEN 'Portfolio Manager'
           WHEN p.agent_name IN ('Bear Case Agent','Company Analyst','Filings and Transcript Analyst','Financial Statement Analyst','Forensic Accounting Agent','Industry Analyst','Management Analyst','Portfolio Fit Agent','Quality Score Agent','Valuation Agent') THEN 'Long-Term Portfolio Manager'
           WHEN p.agent_name='Strategy Committee Secretary' THEN 'Head of Quant'
           ELSE CASE p.department WHEN 'quant' THEN 'Head of Quant' WHEN 'research' THEN 'Research Director' ELSE 'Charlie Munger' END
       END,
       p.department, 95, 'specialist', p.role_scope,
       ARRAY['prepare_evidence','recommend_action','open_task'], ARRAY['Charlie Munger','Risk Agent'], ARRAY[]::text[],
       ARRAY['capital_action','live_execution','external_send']
FROM agent.profiles p
LEFT JOIN agent.org_hierarchy h USING(agent_name)
WHERE p.status='active' AND h.agent_name IS NULL
ON CONFLICT (agent_name) DO NOTHING;

UPDATE agent.org_hierarchy SET reports_to_agent='Head of Quant', updated_at=now()
WHERE department_key='quant' AND agent_name NOT IN ('Head of Quant');
UPDATE agent.org_hierarchy SET reports_to_agent='Research Director', updated_at=now()
WHERE department_key='research' AND agent_name NOT IN ('Research Director');

INSERT INTO agent.mailboxes (mailbox_key, agent_name, display_name, address, purpose, notification_policy)
SELECT lower(regexp_replace(p.agent_name,'[^a-zA-Z0-9]+','-','g')), p.agent_name, p.display_title,
       lower(regexp_replace(p.agent_name,'[^a-zA-Z0-9]+','-','g')) || '@ai-office.local',
       p.role_scope, '{"critical":"immediate","high":"hourly","normal":"daily_digest","low":"weekly_digest"}'::jsonb
FROM agent.profiles p WHERE p.status='active'
ON CONFLICT (mailbox_key) DO UPDATE SET
    display_name=EXCLUDED.display_name, purpose=EXCLUDED.purpose,
    notification_policy=EXCLUDED.notification_policy, status='active', updated_at=now();

WITH ranked AS (
    SELECT mailbox_key, row_number() OVER (
        PARTITION BY agent_name
        ORDER BY CASE WHEN mailbox_key=lower(regexp_replace(agent_name,'[^a-zA-Z0-9]+','-','g')) THEN 0 ELSE 1 END,
                 created_at, mailbox_key
    ) AS row_rank
    FROM agent.mailboxes WHERE status='active'
)
UPDATE agent.mailboxes mailbox
SET status='retired_alias', updated_at=now()
FROM ranked
WHERE mailbox.mailbox_key=ranked.mailbox_key AND ranked.row_rank>1;

CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_mailboxes_one_active_agent
    ON agent.mailboxes(agent_name) WHERE status='active';

CREATE OR REPLACE VIEW agent.v_agent_org_chart AS
SELECT
    oh.agent_name,p.display_title,oh.reports_to_agent,rpt.display_title AS reports_to_title,
    oh.department_key,dr.department_name,oh.role_rank,oh.hierarchy_level,
    oh.authority_scope,oh.decision_rights,oh.must_consult,oh.can_delegate_to,
    oh.approval_required_for,ch.character_name,ch.avatar_role,ch.visual_traits,
    ch.voice_style,ch.office_location,ch.animation_state,ch.color_token,ch.icon_hint,
    mb.address AS mailbox_address,mb.mailbox_key,oh.updated_at
FROM agent.org_hierarchy oh
JOIN agent.profiles p ON p.agent_name=oh.agent_name
LEFT JOIN agent.profiles rpt ON rpt.agent_name=oh.reports_to_agent
LEFT JOIN agent.department_registry dr ON dr.department_key=oh.department_key
LEFT JOIN agent.agent_characters ch ON ch.agent_name=oh.agent_name
LEFT JOIN agent.mailboxes mb ON mb.agent_name=oh.agent_name AND mb.status='active'
WHERE p.status='active';

CREATE OR REPLACE VIEW agent.v_agent_mailboxes AS
SELECT
    mb.mailbox_key,mb.agent_name,p.display_title,mb.display_name,mb.channel_type,
    mb.address,mb.purpose,mb.status,
    count(msg.id) FILTER (WHERE msg.status='unread') AS unread_count,
    max(msg.created_at) AS latest_message_at,mb.notification_policy,mb.updated_at
FROM agent.mailboxes mb
JOIN agent.profiles p ON p.agent_name=mb.agent_name AND p.status='active'
LEFT JOIN agent.agent_messages msg ON msg.to_agent=mb.agent_name
WHERE mb.status='active'
GROUP BY mb.mailbox_key,mb.agent_name,p.display_title,mb.display_name,mb.channel_type,
         mb.address,mb.purpose,mb.status,mb.notification_policy,mb.updated_at;

INSERT INTO agent.agent_characters (
    agent_name, character_key, character_name, avatar_role, visual_traits,
    voice_style, office_location, animation_state, color_token, icon_hint, character_prompt
)
SELECT p.agent_name, lower(regexp_replace(p.agent_name,'[^a-zA-Z0-9]+','-','g')), p.display_title, p.department,
       'Institutional office attire; department marker; evidence and task status visible.',
       p.persona, p.department || ' office', 'working',
       CASE p.department WHEN 'risk' THEN '#ef7568' WHEN 'portfolio' THEN '#d6ad5c' WHEN 'client' THEN '#57b6a2' WHEN 'research' THEN '#65aee8' WHEN 'tactical' THEN '#d8965a' WHEN 'quant' THEN '#8c7ad8' WHEN 'trading' THEN '#df6d85' WHEN 'treasury' THEN '#62a9a1' WHEN 'software' THEN '#8da399' ELSE '#7798b8' END,
       CASE p.department WHEN 'risk' THEN 'shield-alert' WHEN 'portfolio' THEN 'briefcase-business' WHEN 'research' THEN 'file-search' WHEN 'tactical' THEN 'crosshair' WHEN 'quant' THEN 'sigma' WHEN 'trading' THEN 'chart-candlestick' WHEN 'treasury' THEN 'landmark' WHEN 'client' THEN 'users-round' WHEN 'software' THEN 'code-2' ELSE 'user-round' END,
       p.persona || ' ' || p.operating_style || ' Never invent evidence, bypass a limit, place an order, send externally, or approve your own exception.'
FROM agent.profiles p WHERE p.status='active'
ON CONFLICT (agent_name) DO UPDATE SET
    character_name=EXCLUDED.character_name, avatar_role=EXCLUDED.avatar_role,
    visual_traits=EXCLUDED.visual_traits, voice_style=EXCLUDED.voice_style,
    office_location=EXCLUDED.office_location, color_token=EXCLUDED.color_token,
    icon_hint=EXCLUDED.icon_hint, character_prompt=EXCLUDED.character_prompt, updated_at=now();

INSERT INTO agent.agent_model_assignments (
    agent_name, primary_route, primary_model_key, fallback_route, escalation_route,
    context_policy, cost_policy, max_autonomous_cost_tier, escalation_triggers, notes
)
SELECT p.agent_name, p.default_model_route, 'ollama_llama3_2_3b',
       CASE WHEN p.default_model_route='coding_escalation' THEN 'agent_worker_deterministic' ELSE 'local_workhorse_synthesis' END,
       CASE WHEN p.department='software' THEN 'coding_escalation' ELSE 'frontier_investment_review' END,
       'Retrieve only role-scoped SQL, Obsidian, Qdrant, task, and message evidence before reasoning. Preserve citations and privacy class.',
       'local_first_cloud_only_after_human_approval', 'local',
       ARRAY['bounded local route failed','material high-stakes decision','document exceeds local context','code change required'],
       'Daily work is deterministic or local. Cloud is an explicit audited escalation, never an autonomous default.'
FROM agent.profiles p
LEFT JOIN agent.agent_model_assignments a USING(agent_name)
WHERE p.status='active' AND a.agent_name IS NULL
ON CONFLICT (agent_name) DO NOTHING;

UPDATE agent.agent_model_assignments
SET primary_route='always_on_daily_driver',
    primary_model_key='ollama_llama3_2_3b',
    fallback_route='agent_worker_deterministic',
    escalation_route='charlie_munger_orchestration',
    notes='Recurring executive briefs use the installed lightweight local route. Charlie review is an explicit escalation.',
    updated_at=now()
WHERE agent_name='Chief of Staff';

INSERT INTO agent.model_cost_caps (
    agent_name,daily_cap_usd,monthly_cap_usd,max_cost_tier,
    cloud_requires_approval,autonomous_cloud_allowed,hard_stop_on_breach,
    alert_threshold_pct,notes,evidence,updated_by
)
SELECT p.agent_name,0,0,'local',true,false,true,80,
       'Local-first hard cap. Cloud has zero autonomous budget and requires a separate audited human approval.',
       jsonb_build_array(jsonb_build_object('source','agent.agent_model_assignments','primary_route',a.primary_route,'cost_policy',a.cost_policy)),
       'AI Engineering'
FROM agent.profiles p
JOIN agent.agent_model_assignments a USING(agent_name)
WHERE p.status='active'
ON CONFLICT (agent_name) DO UPDATE SET
    max_cost_tier=EXCLUDED.max_cost_tier,
    cloud_requires_approval=true,autonomous_cloud_allowed=false,
    hard_stop_on_breach=true,alert_threshold_pct=EXCLUDED.alert_threshold_pct,
    notes=EXCLUDED.notes,evidence=EXCLUDED.evidence,updated_by=EXCLUDED.updated_by,updated_at=now();

WITH skill_seed(skill_key, skill_name, skill_family, owner_department) AS (
    VALUES
    ('executive_priority_management','Executive Priority Management','executive','executive'),
    ('technology_governance','Technology Governance','engineering','software'),
    ('tactical_idea_review','Tactical Idea Review','tactical','tactical'),
    ('catalyst_event_analysis','Catalyst And Event Analysis','tactical','tactical'),
    ('technical_market_analysis','Technical Market Analysis','tactical','tactical'),
    ('sentiment_crowding_review','Sentiment And Crowding Review','tactical','tactical'),
    ('options_overlay_review','Options Overlay Review','tactical','tactical'),
    ('sector_rotation_review','Sector Rotation Review','tactical','tactical'),
    ('head_quant_governance','Quant Research Governance','quant','quant'),
    ('strategy_portfolio_optimization','Strategy Portfolio Optimization','quant','quant'),
    ('options_iv_greeks_review','Options IV OI And Greeks Review','trading','trading'),
    ('futures_basis_review','Futures Basis And Rollover Review','trading','trading'),
    ('volatility_regime_review','Volatility Regime Review','trading','trading'),
    ('market_microstructure_review','Market Microstructure Review','trading','trading'),
    ('corporate_actions_special_situations','Corporate Actions And Special Situations','research','research'),
    ('arbitrage_spread_review','Arbitrage Spread Review','research','research'),
    ('document_extraction','Document Extraction And Citation','research','research'),
    ('research_evidence_curation','Research Evidence Curation','knowledge','knowledge'),
    ('social_watchlist_triage','Approved Social Watchlist Triage','research','research'),
    ('treasury_cash_review','Treasury Cash Review','treasury','treasury'),
    ('hedge_design_review','Hedge Design Review','treasury','treasury'),
    ('commodity_macro_review','Commodity Macro Review','treasury','treasury'),
    ('crypto_operational_risk_review','Crypto Operational Risk Review','treasury','treasury'),
    ('collateral_margin_review','Collateral And Margin Review','treasury','treasury'),
    ('portfolio_optimization','Portfolio Construction Optimization','portfolio','portfolio'),
    ('client_suitability_review','Client Suitability Review','client','client'),
    ('cash_deployment_review','Cash Deployment Review','portfolio','portfolio'),
    ('quant_risk_review','Quantitative Portfolio Risk Review','risk','risk'),
    ('portfolio_stress_test','Portfolio Stress Testing','risk','risk'),
    ('model_risk_review','Model Risk Review','risk','risk'),
    ('data_quality_risk_review','Data Quality Risk Review','risk','risk'),
    ('kill_switch_governance','Kill Switch Governance','risk','risk'),
    ('client_management','Client Office Management','client','client'),
    ('client_performance_reporting','Client Performance Reporting','client','client'),
    ('client_communication_governance','Client Communication Governance','client','client'),
    ('backend_engineering','Backend Engineering','engineering','software'),
    ('frontend_engineering','Frontend Engineering','engineering','software'),
    ('devops_reliability','DevOps Reliability','engineering','software'),
    ('qa_release_gate','Quality Assurance Release Gate','engineering','software')
)
INSERT INTO agent.skills (
    skill_key, skill_name, skill_family, skill_type, owner_department, status,
    execution_mode, permission_level, trigger_phrases, input_sources,
    output_targets, required_tools, risk_notes, prompt_template, config
)
SELECT s.skill_key, s.skill_name, s.skill_family, 'operating_skill', s.owner_department, 'active',
       'deterministic_tools_then_local_model', 'write_with_approval', ARRAY[lower(s.skill_name)],
       ARRAY['agent.tasks','core.raw_artifacts','knowledge.obsidian_notes'],
       ARRAY['agent.worker_runs','agent.output_artifacts','knowledge.obsidian_notes'],
       ARRAY['postgres','obsidian','qdrant_search'],
       'Evidence required. Capital, client delivery, live execution, and policy exceptions remain human-gated.',
       'Retrieve role-scoped evidence, perform the named analysis, state uncertainty and objections, then route a durable output.',
       '{"seed_data_allowed":false,"broker_order_allowed":false,"external_send_allowed":false}'::jsonb
FROM skill_seed s
ON CONFLICT (skill_key) DO UPDATE SET
    skill_name=EXCLUDED.skill_name, skill_family=EXCLUDED.skill_family,
    owner_department=EXCLUDED.owner_department, status=EXCLUDED.status,
    execution_mode=EXCLUDED.execution_mode, permission_level=EXCLUDED.permission_level,
    input_sources=EXCLUDED.input_sources, output_targets=EXCLUDED.output_targets,
    required_tools=EXCLUDED.required_tools, risk_notes=EXCLUDED.risk_notes,
    prompt_template=EXCLUDED.prompt_template, config=EXCLUDED.config, updated_at=now();

WITH mappings(agent_name, skill_key) AS (
    VALUES
    ('CIO Agent','executive_priority_management'),('Chief of Staff','executive_priority_management'),('CTO Agent','technology_governance'),
    ('Tactical Portfolio Manager','tactical_idea_review'),('Catalyst Analyst','catalyst_event_analysis'),('Event Analyst','catalyst_event_analysis'),('Technical Analyst','technical_market_analysis'),('Macro Analyst','catalyst_event_analysis'),('Sentiment Analyst','sentiment_crowding_review'),('Options Overlay Agent','options_overlay_review'),('Sector Rotation Agent','sector_rotation_review'),
    ('Head of Quant','head_quant_governance'),('Strategy Portfolio Optimizer','strategy_portfolio_optimization'),('Strategy Retirement Agent','strategy_retirement_review'),
    ('Options Analyst','options_iv_greeks_review'),('Futures Analyst','futures_basis_review'),('Volatility Agent','volatility_regime_review'),('Market Microstructure Agent','market_microstructure_review'),
    ('Research Director','research_evidence_curation'),('Corporate Actions Analyst','corporate_actions_special_situations'),('Arbitrage Analyst','arbitrage_spread_review'),('Social/Twitter Triage Agent','social_watchlist_triage'),('Document Extraction Agent','document_extraction'),('Research Librarian','research_evidence_curation'),('Thesis Librarian','write_obsidian_note'),
    ('Treasury Analyst','treasury_cash_review'),('Hedge Analyst','hedge_design_review'),('Commodity Macro Analyst','commodity_macro_review'),('Crypto Analyst','crypto_operational_risk_review'),('Collateral Risk Agent','collateral_margin_review'),
    ('Portfolio Optimizer','portfolio_optimization'),('Client Suitability Analyst','client_suitability_review'),('Cash Treasury Analyst','cash_deployment_review'),
    ('Quant Risk Analyst','quant_risk_review'),('Stress Testing Agent','portfolio_stress_test'),('Model Risk Agent','model_risk_review'),('Data Quality Risk Agent','data_quality_risk_review'),('Kill Switch Agent','kill_switch_governance'),
    ('Client Manager','client_management'),('Performance Reporter','client_performance_reporting'),('Communication Agent','client_communication_governance'),('Onboarding Agent','client_onboarding_governance'),
    ('Backend Engineer','backend_engineering'),('Frontend Engineer','frontend_engineering'),('DevOps Engineer','devops_reliability'),('QA Engineer','qa_release_gate'),
    ('MCP Integration Engineer','technology_governance'),('Data Engineer','source_data_ingestion_review'),('Data Quality Analyst','data_quality_risk_review'),('Alternative Data Analyst','research_evidence_curation'),('Macro Researcher','commodity_macro_review'),('News Editor','global_market_news_digest'),('Capital Allocation Agent','portfolio_optimization'),('Compliance Agent','risk_gate_review'),('AI Runtime Engineer','model_runtime_check')
)
INSERT INTO agent.agent_skill_map (agent_name, skill_key, proficiency, is_primary, activation_rules)
SELECT m.agent_name, m.skill_key, 'lead', true, '{"task_or_schedule":true,"evidence_required":true}'::jsonb
FROM mappings m
JOIN agent.profiles p USING(agent_name)
JOIN agent.skills s USING(skill_key)
ON CONFLICT (agent_name, skill_key) DO UPDATE SET
    proficiency=EXCLUDED.proficiency, is_primary=EXCLUDED.is_primary,
    activation_rules=EXCLUDED.activation_rules, updated_at=now();

UPDATE agent.workflow_registry SET owner_agent='Librarian Agent', updated_at=now() WHERE owner_agent='Knowledge Librarian';
UPDATE agent.workflow_registry SET owner_agent='Trading Desk Agent', updated_at=now() WHERE owner_agent='Trading Desk';
UPDATE agent.workflow_registry SET owner_agent='Trade Journal Learning Agent', updated_at=now() WHERE owner_agent='Trade Journal Coach';
UPDATE agent.workflow_registry SET owner_agent='Research Librarian', updated_at=now() WHERE owner_agent='Research Librarian';

CREATE TABLE IF NOT EXISTS agent.workflow_schedules (
    schedule_key TEXT PRIMARY KEY,
    workflow_key TEXT NOT NULL REFERENCES agent.workflow_registry(workflow_key) ON DELETE CASCADE,
    owner_agent TEXT NOT NULL REFERENCES agent.profiles(agent_name) ON DELETE CASCADE,
    skill_key TEXT NOT NULL REFERENCES agent.skills(skill_key) ON DELETE RESTRICT,
    schedule_name TEXT NOT NULL,
    cadence_seconds INTEGER NOT NULL CHECK (cadence_seconds >= 300),
    schedule_timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    schedule_window JSONB NOT NULL DEFAULT '{}'::jsonb,
    priority TEXT NOT NULL DEFAULT 'medium',
    enabled BOOLEAN NOT NULL DEFAULT true,
    approval_required BOOLEAN NOT NULL DEFAULT false,
    dedupe_open_task BOOLEAN NOT NULL DEFAULT true,
    next_run_at TIMESTAMPTZ NOT NULL,
    last_materialized_at TIMESTAMPTZ,
    last_task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'scheduled',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent.workflow_schedule_runs (
    id BIGSERIAL PRIMARY KEY,
    schedule_key TEXT NOT NULL REFERENCES agent.workflow_schedules(schedule_key) ON DELETE CASCADE,
    due_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    inbox_item_id BIGINT REFERENCES agent.inbox_items(id) ON DELETE SET NULL,
    actor TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_workflow_schedules_due ON agent.workflow_schedules(enabled, next_run_at);
CREATE INDEX IF NOT EXISTS idx_workflow_schedule_runs_key ON agent.workflow_schedule_runs(schedule_key, created_at DESC);

INSERT INTO agent.workflow_registry (
    workflow_key, workflow_name, workflow_type, owner_agent, trigger_type,
    status, permission_level, input_sources, output_targets, approval_required,
    schedule_hint, notes, metadata
)
VALUES
    ('executive_daily_brief_v2','Executive Daily Office Brief','operating_cycle','Chief of Staff','scheduled','active','write_db_and_artifact',ARRAY['agent.tasks','risk.events','market.news_items'],ARRAY['agent.worker_runs','knowledge.obsidian_notes'],false,'every four hours while the office is active','Materialize one bounded command brief; unresolved actions stay in review.','{"broker_order_allowed":false}'::jsonb),
    ('portfolio_review_cycle_v2','Portfolio Review Cycle','operating_cycle','Portfolio Manager','scheduled','active','write_db_and_artifact',ARRAY['portfolio.v_latest_positions','risk.events'],ARRAY['agent.worker_runs','agent.inbox_items'],false,'morning and close','Review exposure, thesis age, breaks, cash, and action queue.','{"broker_order_allowed":false}'::jsonb),
    ('long_term_coverage_cycle_v2','Long-Term Coverage Cycle','research_cycle','Long-Term Portfolio Manager','scheduled','active','write_db_and_artifact',ARRAY['portfolio.v_latest_positions','portfolio.holding_theses'],ARRAY['agent.worker_runs','knowledge.obsidian_notes'],false,'daily','Route stale or incomplete holding coverage to specialists.','{"capital_action_allowed":false}'::jsonb),
    ('tactical_event_cycle_v2','Tactical Event And Catalyst Cycle','research_cycle','Tactical Portfolio Manager','scheduled','active','write_db_and_artifact',ARRAY['research.filing_events','market.news_items'],ARRAY['agent.worker_runs','agent.inbox_items'],false,'every thirty minutes','Scan source-backed events; proposals require committee review.','{"capital_action_allowed":false}'::jsonb),
    ('quant_research_cycle_v2','Quant Research Review Cycle','quant_cycle','Head of Quant','scheduled','active','write_db_and_artifact',ARRAY['strategy.strategy_registry','strategy.validation_reviews'],ARRAY['agent.worker_runs','agent.inbox_items'],false,'hourly','Review lifecycle gaps and route bounded research.','{"live_execution_allowed":false}'::jsonb),
    ('trading_monitor_cycle_v2','Trading And Alert Monitor','trading_cycle','Trading Desk Agent','scheduled','active','write_db_and_artifact',ARRAY['trading.signals','strategy.v_open_alerts'],ARRAY['agent.worker_runs','agent.inbox_items'],false,'every fifteen minutes','Monitor alerts, setup evidence, and execution lock.','{"broker_order_allowed":false}'::jsonb),
    ('research_factory_cycle_v2','Research Factory Intake Cycle','research_cycle','Research Director','scheduled','active','write_db_and_artifact',ARRAY['research.corporate_filings','core.raw_artifacts'],ARRAY['agent.worker_runs','agent.inbox_items'],false,'every thirty minutes','Prioritize material filings and extraction gaps.','{"capital_action_allowed":false}'::jsonb),
    ('treasury_macro_cycle_v2','Treasury And Macro Cycle','treasury_cycle','Treasury Analyst','scheduled','active','write_db_and_artifact',ARRAY['market.news_items','trading.v_crypto_commodity_watchlist'],ARRAY['agent.worker_runs','knowledge.obsidian_notes'],false,'hourly','Review cash, collateral, macro, commodities, and crypto watch.','{"broker_order_allowed":false}'::jsonb),
    ('risk_control_cycle_v2','Independent Risk Control Cycle','risk_cycle','Risk Agent','scheduled','active','write_db_and_artifact',ARRAY['risk.events','books.v_book_exposures'],ARRAY['agent.worker_runs','agent.inbox_items'],false,'every thirty minutes','Review open breaches, stress, and execution controls.','{"independent_challenge":true}'::jsonb),
    ('client_office_cycle_v2','Client Office Review Cycle','client_cycle','Client Manager','scheduled','active','write_db_and_artifact',ARRAY['portfolio.clients','portfolio.accounts'],ARRAY['agent.worker_runs','agent.inbox_items'],false,'daily','Review onboarding, suitability, reports, and account breaks.','{"external_send_allowed":false}'::jsonb),
    ('data_quality_cycle_v2','Data Quality Control Cycle','data_cycle','Data Quality Analyst','scheduled','active','write_db_and_artifact',ARRAY['core.data_source_checks','core.source_artifact_lineage'],ARRAY['agent.worker_runs','agent.inbox_items'],false,'every fifteen minutes','Review freshness, completeness, lineage, and reconciliation.','{"seed_data_allowed":false}'::jsonb),
    ('model_runtime_cycle_v2','Model Runtime Control Cycle','runtime_cycle','AI Runtime Engineer','scheduled','active','write_db_and_artifact',ARRAY['agent.model_endpoints','core.provider_readiness_runs'],ARRAY['agent.worker_runs','agent.inbox_items'],false,'every thirty minutes','Review endpoint health, route readiness, privacy, and cost.','{"autonomous_cloud_allowed":false}'::jsonb),
    ('knowledge_memory_cycle_v2','Knowledge And Memory Cycle','knowledge_cycle','Librarian Agent','scheduled','active','write_db_and_artifact',ARRAY['knowledge.obsidian_notes','core.raw_artifacts'],ARRAY['agent.worker_runs','knowledge.obsidian_notes'],false,'every two hours','Review index freshness, duplicate notes, and writeback gaps.','{"source_truth_preserved":true}'::jsonb)
ON CONFLICT (workflow_key) DO UPDATE SET
    workflow_name=EXCLUDED.workflow_name, workflow_type=EXCLUDED.workflow_type,
    owner_agent=EXCLUDED.owner_agent, trigger_type=EXCLUDED.trigger_type,
    status=EXCLUDED.status, permission_level=EXCLUDED.permission_level,
    input_sources=EXCLUDED.input_sources, output_targets=EXCLUDED.output_targets,
    approval_required=EXCLUDED.approval_required, schedule_hint=EXCLUDED.schedule_hint,
    notes=EXCLUDED.notes, metadata=EXCLUDED.metadata, updated_at=now();

INSERT INTO agent.workflow_schedules (
    schedule_key, workflow_key, owner_agent, skill_key, schedule_name,
    cadence_seconds, priority, enabled, approval_required, next_run_at, metadata
)
VALUES
    ('executive-daily-brief','executive_daily_brief_v2','Chief of Staff','daily_office_brief','Executive office brief',14400,'high',true,false,now(),'{"session":"all"}'::jsonb),
    ('portfolio-review','portfolio_review_cycle_v2','Portfolio Manager','portfolio_daily_brief','Portfolio morning and close review',43200,'high',true,false,now()+interval '10 minutes','{}'::jsonb),
    ('long-term-coverage','long_term_coverage_cycle_v2','Long-Term Portfolio Manager','long_term_specialist_dispatch','Long-term coverage review',86400,'medium',true,false,now()+interval '20 minutes','{}'::jsonb),
    ('tactical-event-scan','tactical_event_cycle_v2','Tactical Portfolio Manager','tactical_idea_review','Tactical event scan',1800,'high',true,false,now()+interval '5 minutes','{}'::jsonb),
    ('quant-research-review','quant_research_cycle_v2','Head of Quant','strategy_lab_review','Quant lifecycle review',3600,'medium',true,false,now()+interval '15 minutes','{}'::jsonb),
    ('trading-alert-monitor','trading_monitor_cycle_v2','Trading Desk Agent','monitor_strategy_alerts','Trading alert monitor',900,'high',true,false,now()+interval '3 minutes','{"paper_only":true}'::jsonb),
    ('research-factory-intake','research_factory_cycle_v2','Research Director','analyze_corporate_filing','Research factory intake',1800,'high',true,false,now()+interval '7 minutes','{}'::jsonb),
    ('treasury-macro-watch','treasury_macro_cycle_v2','Treasury Analyst','commodity_macro_review','Treasury and macro watch',3600,'medium',true,false,now()+interval '12 minutes','{}'::jsonb),
    ('risk-control-review','risk_control_cycle_v2','Risk Agent','risk_gate_review','Independent risk review',1800,'critical',true,false,now()+interval '2 minutes','{}'::jsonb),
    ('client-office-review','client_office_cycle_v2','Client Manager','client_management','Client office review',86400,'medium',true,false,now()+interval '30 minutes','{}'::jsonb),
    ('data-quality-review','data_quality_cycle_v2','Data Quality Analyst','source_data_ingestion_review','Data quality review',900,'high',true,false,now()+interval '4 minutes','{}'::jsonb),
    ('model-runtime-review','model_runtime_cycle_v2','AI Runtime Engineer','model_runtime_check','Model runtime review',1800,'medium',true,false,now()+interval '6 minutes','{}'::jsonb),
    ('knowledge-memory-review','knowledge_memory_cycle_v2','Librarian Agent','write_obsidian_note','Knowledge and memory review',7200,'medium',true,false,now()+interval '25 minutes','{}'::jsonb)
ON CONFLICT (schedule_key) DO UPDATE SET
    workflow_key=EXCLUDED.workflow_key, owner_agent=EXCLUDED.owner_agent,
    skill_key=EXCLUDED.skill_key, schedule_name=EXCLUDED.schedule_name,
    cadence_seconds=EXCLUDED.cadence_seconds, priority=EXCLUDED.priority,
    enabled=EXCLUDED.enabled, approval_required=EXCLUDED.approval_required,
    metadata=EXCLUDED.metadata, updated_at=now();

CREATE OR REPLACE FUNCTION agent.materialize_due_workflow_schedules(p_limit INTEGER DEFAULT 10, p_actor TEXT DEFAULT 'Jarvis')
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    schedule_row RECORD;
    existing_task_id BIGINT;
    created_task_id BIGINT;
    created_inbox_id BIGINT;
    results JSONB := '[]'::jsonb;
BEGIN
    FOR schedule_row IN
        SELECT * FROM agent.workflow_schedules
        WHERE enabled=true AND status='scheduled' AND next_run_at<=now()
        ORDER BY CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END, next_run_at
        FOR UPDATE SKIP LOCKED
        LIMIT greatest(1, least(coalesce(p_limit,10),50))
    LOOP
        existing_task_id := NULL;
        IF schedule_row.dedupe_open_task THEN
            SELECT id INTO existing_task_id FROM agent.tasks
            WHERE source_kind='workflow_schedule' AND source_ref=schedule_row.schedule_key
              AND status IN ('queued','in_progress','needs_review','blocked')
            ORDER BY created_at DESC LIMIT 1;
        END IF;

        created_task_id := existing_task_id;
        created_inbox_id := NULL;
        IF existing_task_id IS NULL THEN
            INSERT INTO agent.tasks (
                title, objective, owner_agent, status, priority, approval_required,
                source_kind, source_ref, output_format, evidence
            ) VALUES (
                'Scheduled: ' || schedule_row.schedule_name,
                'Run ' || schedule_row.schedule_name || ' using skill ' || schedule_row.skill_key || '. Retrieve current evidence, record gaps and objections, and write a bounded output. No capital, broker, client-delivery, or external authority is granted.',
                schedule_row.owner_agent, 'queued', schedule_row.priority,
                schedule_row.approval_required, 'workflow_schedule', schedule_row.schedule_key,
                'obsidian_note', jsonb_build_array(jsonb_build_object('source','agent.workflow_schedules','schedule_key',schedule_row.schedule_key,'due_at',schedule_row.next_run_at,'skill_key',schedule_row.skill_key))
            ) RETURNING id INTO created_task_id;

            INSERT INTO agent.inbox_items (
                task_id, title, owner_agent, status, priority, recommended_action,
                evidence, target_workspace
            ) VALUES (
                created_task_id, 'Scheduled work: ' || schedule_row.schedule_name,
                schedule_row.owner_agent, 'queued', schedule_row.priority,
                'Run the assigned skill with current evidence, write the output, and escalate material decisions through Charlie and Risk.',
                jsonb_build_array(jsonb_build_object('source','agent.workflow_schedules','schedule_key',schedule_row.schedule_key)),
                coalesce((SELECT department FROM agent.profiles WHERE agent_name=schedule_row.owner_agent),'command')
            ) RETURNING id INTO created_inbox_id;
        END IF;

        INSERT INTO agent.workflow_schedule_runs (schedule_key,due_at,status,task_id,inbox_item_id,actor,evidence)
        VALUES (
            schedule_row.schedule_key, schedule_row.next_run_at,
            CASE WHEN existing_task_id IS NULL THEN 'materialized' ELSE 'deduped_open_task' END,
            created_task_id, created_inbox_id, p_actor,
            jsonb_build_array(jsonb_build_object('source','agent.materialize_due_workflow_schedules','owner_agent',schedule_row.owner_agent,'skill_key',schedule_row.skill_key))
        );

        UPDATE agent.workflow_schedules
        SET last_materialized_at=now(), last_task_id=created_task_id,
            next_run_at=greatest(now(),schedule_row.next_run_at)+make_interval(secs=>schedule_row.cadence_seconds),
            updated_at=now()
        WHERE schedule_key=schedule_row.schedule_key;

        results := results || jsonb_build_array(jsonb_build_object(
            'schedule_key',schedule_row.schedule_key,
            'status',CASE WHEN existing_task_id IS NULL THEN 'materialized' ELSE 'deduped_open_task' END,
            'task_id',created_task_id,'inbox_item_id',created_inbox_id,
            'owner_agent',schedule_row.owner_agent,'skill_key',schedule_row.skill_key
        ));
    END LOOP;
    RETURN jsonb_build_object('processed',jsonb_array_length(results),'results',results,'actor',p_actor,'generated_at',now());
END;
$$;

CREATE OR REPLACE VIEW agent.v_workflow_schedule_control AS
SELECT s.schedule_key, s.schedule_name, s.workflow_key, w.workflow_name,
       s.owner_agent, p.display_title AS owner_title, p.department,
       s.skill_key, sk.skill_name, s.cadence_seconds, s.schedule_timezone,
       s.schedule_window, s.priority, s.enabled, s.approval_required,
       s.dedupe_open_task, s.next_run_at, s.last_materialized_at, s.last_task_id,
       t.status AS last_task_status, s.status,
       CASE WHEN NOT s.enabled THEN 'disabled'
            WHEN s.next_run_at<=now() THEN 'due'
            WHEN t.status IN ('queued','in_progress','needs_review','blocked') THEN 'waiting_on_open_task'
            ELSE 'scheduled' END AS schedule_state,
       extract(epoch FROM (s.next_run_at-now()))::bigint AS seconds_until_due,
       s.metadata, s.updated_at
FROM agent.workflow_schedules s
JOIN agent.workflow_registry w USING(workflow_key)
JOIN agent.profiles p ON p.agent_name=s.owner_agent
JOIN agent.skills sk USING(skill_key)
LEFT JOIN agent.tasks t ON t.id=s.last_task_id;

CREATE TABLE IF NOT EXISTS agent.committee_registry (
    committee_key TEXT PRIMARY KEY,
    committee_name TEXT NOT NULL,
    chair_agent TEXT NOT NULL REFERENCES agent.profiles(agent_name),
    mandate TEXT NOT NULL,
    quorum INTEGER NOT NULL CHECK(quorum>=2),
    decision_options TEXT[] NOT NULL,
    human_final_required BOOLEAN NOT NULL DEFAULT true,
    status TEXT NOT NULL DEFAULT 'active',
    guardrails JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent.committee_memberships (
    committee_key TEXT NOT NULL REFERENCES agent.committee_registry(committee_key) ON DELETE CASCADE,
    agent_name TEXT NOT NULL REFERENCES agent.profiles(agent_name) ON DELETE CASCADE,
    committee_role TEXT NOT NULL,
    vote_type TEXT NOT NULL DEFAULT 'advisory',
    challenge_mandate TEXT NOT NULL,
    required BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (committee_key, agent_name)
);

INSERT INTO agent.committee_registry (committee_key,committee_name,chair_agent,mandate,quorum,decision_options,human_final_required,guardrails)
VALUES
    ('executive','Executive Committee','Charlie Munger','Prioritize office work, resolve cross-department conflicts, and prepare human decisions.',4,ARRAY['approve_internal_priority','revise','defer','reject'],true,'{"no_capital_authority":true}'::jsonb),
    ('long_term','Long-Term Investment Committee','Charlie Munger','Review source-backed long-term theses, valuation, risk, portfolio fit, and exit discipline.',5,ARRAY['reject','watchlist','more_research','starter_position','add','hold','trim','sell','hedge'],true,'{"capital_action_requires_human":true}'::jsonb),
    ('tactical','Tactical Committee','Charlie Munger','Review catalyst, timing, technical, macro, sentiment, option overlay, and tactical risk.',5,ARRAY['reject','watchlist','paper_trade','revise','approve_proposal'],true,'{"capital_action_requires_human":true}'::jsonb),
    ('strategy','Strategy Committee','Head of Quant','Review data, backtest, robustness, costs, capacity, risk, paper monitoring, and retirement.',6,ARRAY['reject','revise','paper_monitor','limited_live_proposal','retire'],true,'{"live_execution_requires_human":true}'::jsonb),
    ('special_situations','Special Situations Committee','Research Director','Review legal terms, timeline, spread, probability, break risk, liquidity, and downside.',5,ARRAY['reject','watchlist','more_research','paper_trade','capital_proposal'],true,'{"capital_action_requires_human":true}'::jsonb),
    ('risk','Risk Committee','Risk Agent','Independently challenge exposure, limits, stress, liquidity, model, data, and execution risk.',5,ARRAY['clear','warn','request_evidence','reduce_size','block','kill_switch'],true,'{"independent_challenge":true}'::jsonb),
    ('capital','Capital Allocation Committee','CIO Agent','Allocate risk budgets across books and clients after opportunity-cost and risk review.',5,ARRAY['reject','revise','defer','recommend_approval'],true,'{"capital_action_requires_human":true}'::jsonb),
    ('data_tools','Data And Tool Committee','Data Steward','Review source quality, lineage, licenses, MCP permissions, tool risk, and connector readiness.',4,ARRAY['approve_internal','revise','block','retire_connector'],true,'{"external_write_requires_human":true}'::jsonb),
    ('client_review','Client Review Committee','Client Manager','Review onboarding, mandate, suitability, performance, reporting, and communication scope.',4,ARRAY['approve_internal','conditional','revise','block'],true,'{"external_send_requires_human":true}'::jsonb),
    ('model_review','Model Review Committee','Model Risk Agent','Review model purpose, readiness, privacy, cost, validation, drift, and allowed use.',4,ARRAY['approve_internal','conditional','revise','block','retire_model'],true,'{"cloud_use_requires_human":true}'::jsonb),
    ('execution_approval','Execution Approval Committee','Execution Safety Agent','Review order intent, mandate, risk, broker mode, kill switch, and pre-trade evidence.',4,ARRAY['reject','revise','paper_only','recommend_limited_live'],true,'{"broker_order_allowed":false}'::jsonb)
ON CONFLICT (committee_key) DO UPDATE SET
    committee_name=EXCLUDED.committee_name, chair_agent=EXCLUDED.chair_agent,
    mandate=EXCLUDED.mandate, quorum=EXCLUDED.quorum,
    decision_options=EXCLUDED.decision_options, human_final_required=EXCLUDED.human_final_required,
    guardrails=EXCLUDED.guardrails, status='active', updated_at=now();

WITH membership(committee_key,agent_name,committee_role,vote_type,challenge_mandate) AS (
    VALUES
    ('executive','Charlie Munger','chair','chair','Mental models, opportunity cost, final internal synthesis'),('executive','Jarvis','operator','advisory','Runtime feasibility and queue state'),('executive','CIO Agent','investment lead','voting','Portfolio-wide opportunity cost'),('executive','Risk Agent','independent risk','veto_recommendation','Limits and downside'),('executive','Chief of Staff','secretary','non_voting','Actions, owners, and follow-up'),
    ('long_term','Charlie Munger','chair','chair','Decision quality'),('long_term','Long-Term Portfolio Manager','book head','voting','Thesis and ownership horizon'),('long_term','Company Analyst','research lead','voting','Business evidence'),('long_term','Valuation Agent','valuation','voting','Price and return distribution'),('long_term','Risk Agent','risk','veto_recommendation','Permanent impairment'),('long_term','Bear Case Agent','devils advocate','voting','Disconfirming evidence'),('long_term','Portfolio Fit Agent','portfolio fit','voting','Concentration and mandate'),
    ('tactical','Charlie Munger','chair','chair','Decision quality'),('tactical','Tactical Portfolio Manager','book head','voting','Setup and sizing'),('tactical','Technical Analyst','technical','voting','Price confirmation'),('tactical','Macro Analyst','macro','voting','Regime context'),('tactical','Options Overlay Agent','options','voting','Convexity and Greeks'),('tactical','Risk Agent','risk','veto_recommendation','Loss and overlap'),
    ('strategy','Head of Quant','chair','chair','Scientific standard'),('strategy','Model Validation Agent','validation','veto_recommendation','Leakage and overfit'),('strategy','Backtest Engineer','backtest','voting','Reproducibility'),('strategy','Capacity/Liquidity Analyst','capacity','voting','Market impact'),('strategy','Strategy Portfolio Optimizer','portfolio fit','voting','Correlation and allocation'),('strategy','Risk Agent','risk','veto_recommendation','Tail and activation limits'),('strategy','Strategy Committee Secretary','secretary','non_voting','Minutes and conditions'),
    ('special_situations','Research Director','chair','chair','Research standard'),('special_situations','Special Situations Agent','deal lead','voting','Terms and timeline'),('special_situations','Arbitrage Analyst','spread','voting','Probability and downside'),('special_situations','Corporate Actions Analyst','filings','voting','Source terms'),('special_situations','Risk Agent','risk','veto_recommendation','Break risk'),
    ('risk','Risk Agent','chair','chair','Independent control'),('risk','Quant Risk Analyst','quant risk','voting','VaR ES and factors'),('risk','Stress Testing Agent','stress','voting','Scenario failure'),('risk','Model Risk Agent','model risk','voting','Model limitations'),('risk','Data Quality Risk Agent','data risk','voting','Input readiness'),('risk','Kill Switch Agent','control','veto_recommendation','Execution lock'),
    ('capital','CIO Agent','chair','chair','Opportunity cost'),('capital','Capital Allocation Agent','allocator','voting','Book budgets'),('capital','Portfolio Manager','portfolio','voting','Client and position context'),('capital','Portfolio Optimizer','optimizer','voting','Constraint solution'),('capital','Risk Agent','risk','veto_recommendation','Risk budget'),
    ('data_tools','Data Steward','chair','chair','Source truth'),('data_tools','MCP Integration Engineer','tools','voting','Permission boundaries'),('data_tools','Data Quality Analyst','quality','voting','Freshness and completeness'),('data_tools','Compliance Agent','compliance','veto_recommendation','Terms and audit'),
    ('client_review','Client Manager','chair','chair','Client scope'),('client_review','Client Suitability Analyst','suitability','veto_recommendation','Mandate fit'),('client_review','Performance Reporter','reporting','voting','Reconciled outcomes'),('client_review','Compliance Agent','compliance','veto_recommendation','Privacy and approval'),
    ('model_review','Model Risk Agent','chair','chair','Allowed use'),('model_review','AI Runtime Engineer','runtime','voting','Readiness and cost'),('model_review','Data Quality Risk Agent','data','voting','Evaluation data'),('model_review','Compliance Agent','privacy','veto_recommendation','Privacy and retention'),
    ('execution_approval','Execution Safety Agent','chair','chair','Pre-trade safety'),('execution_approval','Risk Agent','risk','veto_recommendation','Limits'),('execution_approval','Trading Desk Agent','desk','voting','Order intent'),('execution_approval','Kill Switch Agent','control','veto_recommendation','Global lock')
)
INSERT INTO agent.committee_memberships (committee_key,agent_name,committee_role,vote_type,challenge_mandate)
SELECT * FROM membership
ON CONFLICT (committee_key,agent_name) DO UPDATE SET
    committee_role=EXCLUDED.committee_role, vote_type=EXCLUDED.vote_type,
    challenge_mandate=EXCLUDED.challenge_mandate, updated_at=now();

CREATE OR REPLACE VIEW agent.v_committee_membership_roster AS
SELECT c.committee_key,c.committee_name,c.chair_agent,c.mandate,c.quorum,
       c.decision_options,c.human_final_required,c.status,c.guardrails,
       count(m.agent_name)::int AS member_count,
       count(*) FILTER (WHERE m.required)::int AS required_member_count,
       jsonb_agg(jsonb_build_object(
           'agent_name',m.agent_name,'title',p.display_title,'department',p.department,
           'committee_role',m.committee_role,'vote_type',m.vote_type,
           'challenge_mandate',m.challenge_mandate,'required',m.required
       ) ORDER BY CASE m.committee_role WHEN 'chair' THEN 1 WHEN 'secretary' THEN 3 ELSE 2 END,p.display_title) AS members,
       c.updated_at
FROM agent.committee_registry c
JOIN agent.committee_memberships m USING(committee_key)
JOIN agent.profiles p ON p.agent_name=m.agent_name
GROUP BY c.committee_key;

CREATE OR REPLACE VIEW agent.v_agent_operating_readiness AS
WITH run_stats AS (
    SELECT agent_name,count(*)::int AS worker_runs,
           count(*) FILTER (WHERE status='completed')::int AS completed_runs,
           count(*) FILTER (WHERE status IN ('failed','blocked'))::int AS failed_runs,
           max(finished_at) AS latest_worker_finished_at
    FROM agent.worker_runs GROUP BY agent_name
), task_stats AS (
    SELECT owner_agent AS agent_name,
           count(*) FILTER (WHERE status IN ('queued','in_progress','needs_review','blocked'))::int AS open_tasks,
           count(*) FILTER (WHERE status='blocked')::int AS blocked_tasks
    FROM agent.tasks GROUP BY owner_agent
)
SELECT p.agent_name,p.display_title,p.department,
       (h.agent_name IS NOT NULL) AS hierarchy_ready,
       (m.agent_name IS NOT NULL) AS mailbox_ready,
       (c.agent_name IS NOT NULL) AS character_ready,
       (a.agent_name IS NOT NULL) AS model_route_ready,
       (coalesce(sk.skill_count,0)>0) AS skills_ready,
       coalesce(sk.skill_count,0)::int AS skill_count,
       coalesce(rs.worker_runs,0) AS worker_runs,coalesce(rs.completed_runs,0) AS completed_runs,
       coalesce(rs.failed_runs,0) AS failed_runs,coalesce(ts.open_tasks,0) AS open_tasks,
       coalesce(ts.blocked_tasks,0) AS blocked_tasks,rs.latest_worker_finished_at,
       round((20*(h.agent_name IS NOT NULL)::int + 20*(m.agent_name IS NOT NULL)::int + 20*(c.agent_name IS NOT NULL)::int + 20*(a.agent_name IS NOT NULL)::int + 20*(coalesce(sk.skill_count,0)>0)::int)::numeric,2) AS operating_readiness_score,
       CASE WHEN coalesce(rs.worker_runs,0)=0 THEN NULL ELSE round(100.0*rs.completed_runs/greatest(rs.worker_runs,1),2) END AS reliability_score,
       CASE WHEN coalesce(rs.worker_runs,0)>=10 THEN 'measured' WHEN coalesce(rs.worker_runs,0)>=3 THEN 'limited' ELSE 'insufficient_history' END AS reliability_confidence,
       CASE WHEN h.agent_name IS NOT NULL AND m.agent_name IS NOT NULL AND c.agent_name IS NOT NULL AND a.agent_name IS NOT NULL AND coalesce(sk.skill_count,0)>0 THEN 'ready' ELSE 'incomplete' END AS readiness_status
FROM agent.profiles p
LEFT JOIN agent.org_hierarchy h ON h.agent_name=p.agent_name
LEFT JOIN agent.mailboxes m ON m.agent_name=p.agent_name AND m.status='active'
LEFT JOIN agent.agent_characters c ON c.agent_name=p.agent_name
LEFT JOIN agent.agent_model_assignments a ON a.agent_name=p.agent_name
LEFT JOIN (SELECT agent_name,count(*)::int AS skill_count FROM agent.agent_skill_map GROUP BY agent_name) sk ON sk.agent_name=p.agent_name
LEFT JOIN run_stats rs ON rs.agent_name=p.agent_name
LEFT JOIN task_stats ts ON ts.agent_name=p.agent_name
WHERE p.status='active';

CREATE OR REPLACE VIEW agent.v_agent_operating_summary AS
SELECT metric,value,interpretation FROM (
    SELECT 1 AS rank,'active_agents'::text metric,count(*)::bigint value,'Active governed AI employees.'::text interpretation FROM agent.v_agent_operating_readiness
    UNION ALL SELECT 2,'operating_ready',count(*) FILTER (WHERE readiness_status='ready'),'Agents with hierarchy, mailbox, character, model route, and at least one skill.' FROM agent.v_agent_operating_readiness
    UNION ALL SELECT 3,'active_departments',count(*) FILTER (WHERE status='active'),'Active role-scoped departments.' FROM agent.department_registry
    UNION ALL SELECT 4,'active_schedules',count(*) FILTER (WHERE enabled),'Materializing schedules; open-task dedupe prevents spam.' FROM agent.workflow_schedules
    UNION ALL SELECT 5,'structured_committees',count(*) FILTER (WHERE status='active'),'Committees with chair, quorum, members, challenge mandate, and human final gate.' FROM agent.committee_registry
    UNION ALL SELECT 6,'active_mailboxes',count(*) FILTER (WHERE status='active'),'Durable internal mailboxes.' FROM agent.mailboxes
) summary ORDER BY rank;

CREATE OR REPLACE VIEW agent.v_live_agent_worker_queue AS
WITH dashboard_jobs AS (
    SELECT j.task_id,j.title,j.objective,j.owner_agent,j.status AS task_status,j.priority,j.source_kind,j.source_ref,j.output_note_path,
           j.widget_id,j.widget_key,j.widget_title,j.workspace,j.widget_type,
           CASE WHEN j.widget_key='portfolio_latest_positions' THEN 'portfolio_snapshot_review' WHEN j.widget_key='market_signal_monitor' THEN 'monitor_strategy_alerts' WHEN j.widget_key='strategy_lab_queue' THEN 'strategy_lab_review' WHEN j.widget_key='research_filings_inbox' THEN 'analyze_corporate_filing' WHEN j.widget_key='model_runtime_status' THEN 'model_runtime_check' WHEN j.widget_key='command_daily_brief' THEN 'daily_office_brief' ELSE 'refresh_dashboard_widget' END AS suggested_skill_key,
           j.inbox_item_id,j.inbox_status,j.created_at,j.updated_at
    FROM agent.v_dashboard_agent_jobs j
), message_jobs AS (
    SELECT t.id,t.title,t.objective,t.owner_agent,t.status,t.priority,t.source_kind,t.source_ref,t.output_note_path,
           NULL::bigint,NULL::text,'Agent Mailbox'::text,coalesce(nullif(p.department,''),'command'),'agent_message'::text,
           coalesce(msg.related_skill_key,msg.metadata->>'skill_key','route_user_request'),inbox.id,inbox.status,t.created_at,t.updated_at
    FROM agent.tasks t
    LEFT JOIN agent.agent_messages msg ON msg.generated_task_id=t.id
    LEFT JOIN LATERAL (
        SELECT item.id,item.status
        FROM agent.inbox_items item
        WHERE item.task_id=t.id
        ORDER BY item.updated_at DESC,item.id DESC
        LIMIT 1
    ) inbox ON true
    LEFT JOIN agent.profiles p ON p.agent_name=t.owner_agent
    WHERE t.source_kind='agent_message'
), schedule_jobs AS (
    SELECT t.id,t.title,t.objective,t.owner_agent,t.status,t.priority,t.source_kind,t.source_ref,t.output_note_path,
           NULL::bigint,NULL::text,'Scheduled Workflow'::text,coalesce(nullif(p.department,''),'command'),'workflow_schedule'::text,
           s.skill_key,inbox.id,inbox.status,t.created_at,t.updated_at
    FROM agent.tasks t
    JOIN agent.workflow_schedules s ON s.schedule_key=t.source_ref
    LEFT JOIN LATERAL (
        SELECT item.id,item.status
        FROM agent.inbox_items item
        WHERE item.task_id=t.id
        ORDER BY item.updated_at DESC,item.id DESC
        LIMIT 1
    ) inbox ON true
    LEFT JOIN agent.profiles p ON p.agent_name=t.owner_agent
    WHERE t.source_kind='workflow_schedule'
), queued AS (
    SELECT * FROM dashboard_jobs UNION ALL SELECT * FROM message_jobs UNION ALL SELECT * FROM schedule_jobs
)
SELECT q.task_id,q.title,q.objective,q.owner_agent,q.task_status,q.priority,q.source_kind,q.source_ref,q.output_note_path,
       q.widget_id,q.widget_key,q.widget_title,q.workspace,q.widget_type,q.suggested_skill_key,
       s.skill_name AS suggested_skill_name,s.skill_family AS suggested_skill_family,s.execution_mode AS suggested_execution_mode,
       last_run.id AS latest_worker_run_id,last_run.status AS latest_worker_status,last_run.finished_at AS latest_worker_finished_at,last_run.output_note_path AS latest_output_note_path,
       q.inbox_item_id,q.inbox_status,q.created_at,q.updated_at
FROM queued q LEFT JOIN agent.skills s ON s.skill_key=q.suggested_skill_key
LEFT JOIN LATERAL (SELECT wr.* FROM agent.worker_runs wr WHERE wr.task_id=q.task_id ORDER BY wr.created_at DESC LIMIT 1) last_run ON true
ORDER BY CASE q.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
         CASE q.task_status WHEN 'queued' THEN 1 WHEN 'in_progress' THEN 2 WHEN 'needs_review' THEN 3 WHEN 'completed' THEN 4 ELSE 5 END,q.updated_at DESC;

INSERT INTO agent.tool_registry (
    tool_name,tool_type,owning_agent,permission_level,enabled,description,config
)
VALUES (
    'ai_os_materialize_agent_schedules','mcp_tool','Jarvis','write_db_and_artifact',true,
    'Materialize due governed workflow schedules into deduplicated tasks and inbox items.',
    '{"writes":["agent.tasks","agent.inbox_items","agent.workflow_schedule_runs"],"function":"agent.materialize_due_workflow_schedules","capital_action_allowed":false,"live_execution_allowed":false}'::jsonb
)
ON CONFLICT (tool_name) DO UPDATE SET
    owning_agent=EXCLUDED.owning_agent,permission_level=EXCLUDED.permission_level,
    enabled=EXCLUDED.enabled,description=EXCLUDED.description,config=EXCLUDED.config;

COMMIT;
