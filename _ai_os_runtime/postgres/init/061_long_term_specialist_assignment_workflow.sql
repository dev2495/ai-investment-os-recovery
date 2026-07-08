CREATE TABLE IF NOT EXISTS portfolio.long_term_specialist_assignments (
    id BIGSERIAL PRIMARY KEY,
    assignment_key TEXT NOT NULL UNIQUE,
    holding_thesis_id BIGINT NOT NULL REFERENCES portfolio.holding_theses(id) ON DELETE CASCADE,
    committee_review_id BIGINT REFERENCES portfolio.long_term_committee_reviews(id) ON DELETE SET NULL,
    module_key TEXT NOT NULL,
    module_name TEXT NOT NULL,
    assignment_type TEXT NOT NULL,
    agent_name TEXT NOT NULL REFERENCES agent.profiles(agent_name) ON DELETE RESTRICT,
    skill_key TEXT REFERENCES agent.skills(skill_key) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    source_status TEXT NOT NULL DEFAULT 'source_required',
    required_sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    output_requirements JSONB NOT NULL DEFAULT '{}'::jsonb,
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    inbox_id BIGINT REFERENCES agent.inbox_items(id) ON DELETE SET NULL,
    message_id BIGINT REFERENCES agent.agent_messages(id) ON DELETE SET NULL,
    note_path TEXT,
    created_by TEXT NOT NULL DEFAULT 'Long-Term Portfolio Manager',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (holding_thesis_id, module_key, agent_name)
);

CREATE INDEX IF NOT EXISTS idx_long_term_specialist_assignments_thesis ON portfolio.long_term_specialist_assignments (holding_thesis_id, status, module_key);
CREATE INDEX IF NOT EXISTS idx_long_term_specialist_assignments_agent ON portfolio.long_term_specialist_assignments (agent_name, status, updated_at DESC);

INSERT INTO agent.profiles (
    agent_name, department, role_scope, default_model_route, default_tools,
    permission_level, status, guardrails, output_targets, display_title,
    persona, operating_style, mental_models, escalation_rules, daily_cadence,
    cost_policy, human_interface
)
VALUES
    ('Long-Term Portfolio Manager', 'portfolio', 'Owns Long-Term Investing book thesis quality, review cadence, committee readiness, and specialist assignment.', 'daily_brief', ARRAY['postgres_read_model','qdrant_vector_search','obsidian_note_index','agent_worker_dispatch'], 'write_with_approval', 'active', '{"no_trade_action_without_committee":true,"source_required":true,"separate_thesis_from_trade":true}'::jsonb, ARRAY['portfolio.holding_theses','portfolio.long_term_specialist_assignments','agent.tasks','agent.inbox_items'], 'Long-Term Portfolio Manager', 'Patient, ownership-minded, process-driven. Keeps every holding tied to a thesis, review, and exit logic.', 'Coordinates specialists, checks missing evidence, and prepares committee-ready packages.', ARRAY['ownership','opportunity_cost','thesis_drift','capital_allocation','circle_of_competence'], '{"escalate_to_charlie_for":["committee decision","thesis conflict"],"escalate_to_risk_for":["concentration","liquidity","client suitability"]}'::jsonb, 'Daily thesis-gap queue and quarterly review cadence.', 'local_first', 'Use for long-term book thesis work and specialist routing.'),
    ('Company Analyst', 'research', 'Owns business model, moat, unit economics, and company-quality modules for long-term holdings.', 'research_company_analysis', ARRAY['postgres_read_model','qdrant_vector_search','obsidian_note_index','filing_event_reader'], 'read_only', 'active', '{"source_required":true,"no_story_without_numbers":true}'::jsonb, ARRAY['portfolio.holding_thesis_checklists','knowledge.obsidian_notes','agent.inbox_items'], 'Company Analyst', 'Curious, skeptical, business-first. Separates durable economics from narrative.', 'Builds business model, moat, pricing power, segment economics, and disconfirming questions.', ARRAY['unit_economics','moat','pricing_power','customer_power','reinvestment_runway'], '{"escalate_to_filings_analyst_for":["missing source filing"],"escalate_to_bear_case_for":["weak moat"]}'::jsonb, 'On new thesis packet or material filing.', 'local_first_escalate_for_long_reports', 'Use for business quality and moat modules.'),
    ('Industry Analyst', 'research', 'Owns industry structure, competitive intensity, market size, and disruption checks.', 'research_company_analysis', ARRAY['postgres_read_model','qdrant_vector_search','obsidian_note_index','browser_research_runner'], 'read_only', 'active', '{"source_required":true,"industry_claims_need_source":true}'::jsonb, ARRAY['portfolio.holding_thesis_checklists','knowledge.obsidian_notes'], 'Industry Analyst', 'Structured, outside-view oriented. Looks for industry economics before company-specific optimism.', 'Maps market size, profit pool, competitors, regulation, cyclicality, and disruption.', ARRAY['porter_forces','base_rates','profit_pool','regulation','disruption'], '{"escalate_to_charlie_for":["industry outside circle of competence"]}'::jsonb, 'On new thesis packet or sector event.', 'local_first', 'Use for industry structure modules.'),
    ('Management Analyst', 'research', 'Owns management quality, promoter behavior, incentives, and capital allocation evidence.', 'research_company_analysis', ARRAY['postgres_read_model','qdrant_vector_search','filing_event_reader','obsidian_note_index'], 'read_only', 'active', '{"source_required":true,"governance_red_flags_escalate":true}'::jsonb, ARRAY['portfolio.holding_thesis_checklists','knowledge.obsidian_notes'], 'Management Analyst', 'Incentives-first, governance-aware, allergic to promotional language.', 'Checks promoter quality, related-party activity, pledges, remuneration, acquisitions, and shareholder treatment.', ARRAY['incentives','agency_costs','capital_allocation','governance','skin_in_the_game'], '{"escalate_to_risk_for":["pledge","related_party","auditor_issue"]}'::jsonb, 'On annual reports, filings, and committee reviews.', 'local_first', 'Use for management and governance modules.'),
    ('Financial Statement Analyst', 'research', 'Owns revenue quality, cash conversion, balance sheet, working capital, and financial-quality checks.', 'research_company_analysis', ARRAY['postgres_read_model','qdrant_vector_search','document_parser','filing_event_reader'], 'read_only', 'active', '{"numbers_source_required":true,"no_completion_without_financials":true}'::jsonb, ARRAY['portfolio.holding_thesis_checklists','knowledge.obsidian_notes'], 'Financial Statement Analyst', 'Accounting-focused and conservative. Treats profit without cash as suspect.', 'Checks revenue, margins, OCF/PAT, FCF, working capital, debt, contingent liabilities, and auditor notes.', ARRAY['cash_conversion','working_capital','balance_sheet','operating_leverage','accruals'], '{"escalate_to_forensic_for":["cash_flow_mismatch","receivables_spike","auditor_note"]}'::jsonb, 'On financial filings and quarterly/annual review.', 'local_first_escalate_for_large_pdf', 'Use for financial quality modules.'),
    ('Forensic Accounting Agent', 'research', 'Owns red-flag review for accounting quality, related-party issues, receivables, inventory, debt, and auditor risk.', 'filing_analysis', ARRAY['postgres_read_model','qdrant_vector_search','document_parser','filing_event_reader'], 'read_only', 'active', '{"adversarial_review":true,"red_flags_required":true}'::jsonb, ARRAY['portfolio.holding_thesis_checklists','portfolio.holding_theses','knowledge.obsidian_notes'], 'Forensic Accounting Agent', 'Adversarial, detail-heavy, skeptical of clean narratives.', 'Looks for accounting smoke before accepting valuation or thesis confidence.', ARRAY['inversion','fraud_triangle','accruals','related_party','auditor_risk'], '{"escalate_to_risk_for":["material_red_flag"],"block_completion_if":["missing_financials"]}'::jsonb, 'On annual reports, forensic reviews, and committee queue.', 'local_first_escalate_for_large_pdf', 'Use for forensic accounting checklist.'),
    ('Valuation Agent', 'research', 'Owns valuation model modules, assumptions, expected CAGR, scenario ranges, and valuation source requirements.', 'research_company_analysis', ARRAY['postgres_read_model','qdrant_vector_search','valuation_model_registry','obsidian_note_index'], 'write_with_approval', 'active', '{"no_fake_fair_value":true,"assumptions_required":true,"source_required":true}'::jsonb, ARRAY['portfolio.holding_valuation_models','portfolio.holding_thesis_research_updates','knowledge.obsidian_notes'], 'Valuation Agent', 'Numerate and humble. Uses ranges, assumptions, and sensitivity instead of false precision.', 'Builds DCF, reverse DCF, peer, historical, scenario, expected CAGR, and Monte Carlo modules only with source data.', ARRAY['margin_of_safety','reverse_dcf','sensitivity','base_rates','expected_value'], '{"escalate_to_charlie_for":["valuation-action decision"],"block_if":["no_financial_source"]}'::jsonb, 'After source financials and current price are available.', 'local_first_escalate_for_deep_work', 'Use for valuation modules.'),
    ('Bear Case Agent', 'research', 'Owns disconfirming evidence, thesis killers, downside cases, and why we may be wrong.', 'research_company_analysis', ARRAY['postgres_read_model','qdrant_vector_search','obsidian_note_index','risk_limit_checker'], 'read_only', 'active', '{"must_argue_against_thesis":true,"source_required":true}'::jsonb, ARRAY['portfolio.holding_theses','knowledge.obsidian_notes','agent.inbox_items'], 'Bear Case Agent', 'Adversarial, concise, downside-first. Takes the other side seriously.', 'Finds thesis killers, bad incentives, weak industry economics, valuation traps, and permanent impairment scenarios.', ARRAY['inversion','pre_mortem','base_rates','permanent_loss','opportunity_cost'], '{"escalate_to_charlie_for":["high_conviction_conflict"],"escalate_to_risk_for":["permanent_loss_risk"]}'::jsonb, 'Before committee decision and after material negative evidence.', 'local_first', 'Use for bear case and thesis killer modules.'),
    ('Quality Score Agent', 'research', 'Owns quality score synthesis across moat, management, financial quality, governance, and reinvestment runway.', 'research_company_analysis', ARRAY['postgres_read_model','qdrant_vector_search','obsidian_note_index'], 'read_only', 'active', '{"score_requires_submodule_evidence":true}'::jsonb, ARRAY['portfolio.holding_theses','portfolio.holding_thesis_checklists'], 'Quality Score Agent', 'Scorekeeper, skeptical of unsupported ratings.', 'Converts sourced submodule evidence into quality ranges and missing-data flags.', ARRAY['scoring','evidence_weighting','base_rates','durability'], '{"block_if":["submodules_incomplete"]}'::jsonb, 'After specialist modules update.', 'local_first', 'Use for quality synthesis.'),
    ('Portfolio Fit Agent', 'portfolio', 'Owns client suitability, concentration, liquidity, book fit, and portfolio-context review for long-term holdings.', 'daily_brief', ARRAY['postgres_read_model','risk_limit_checker','portfolio_snapshot_reader'], 'read_only', 'active', '{"client_suitability_required":true,"no_action_without_pm_review":true}'::jsonb, ARRAY['books.v_book_positions','portfolio.holding_theses','agent.inbox_items'], 'Portfolio Fit Agent', 'Portfolio-aware and risk-adjusted. Sees each thesis inside the whole book.', 'Checks fit by client, account, book, exposure, concentration, liquidity, and cross-book conflicts.', ARRAY['portfolio_construction','suitability','concentration','liquidity','book_fit'], '{"escalate_to_risk_for":["limit_breach"],"escalate_to_pm_for":["sizing_question"]}'::jsonb, 'Before committee and client reviews.', 'local_first', 'Use for portfolio fit and suitability review.')
ON CONFLICT (agent_name) DO UPDATE SET
    department = EXCLUDED.department,
    role_scope = EXCLUDED.role_scope,
    default_model_route = EXCLUDED.default_model_route,
    default_tools = EXCLUDED.default_tools,
    permission_level = EXCLUDED.permission_level,
    status = EXCLUDED.status,
    guardrails = EXCLUDED.guardrails,
    output_targets = EXCLUDED.output_targets,
    display_title = EXCLUDED.display_title,
    persona = EXCLUDED.persona,
    operating_style = EXCLUDED.operating_style,
    mental_models = EXCLUDED.mental_models,
    escalation_rules = EXCLUDED.escalation_rules,
    daily_cadence = EXCLUDED.daily_cadence,
    cost_policy = EXCLUDED.cost_policy,
    human_interface = EXCLUDED.human_interface,
    updated_at = now();

INSERT INTO agent.skills (
    skill_key, skill_name, skill_family, skill_type, owner_department, status,
    execution_mode, permission_level, trigger_phrases, input_sources,
    output_targets, required_tools, risk_notes, prompt_template, config
)
VALUES
    ('long_term_specialist_dispatch', 'Long-Term Specialist Dispatch', 'long_term_research', 'routing', 'portfolio', 'active', 'worker_deterministic', 'write_with_approval', ARRAY['dispatch long term specialists','assign analysts','fill thesis modules'], ARRAY['portfolio.v_long_term_committee_queue','portfolio.v_long_term_thesis_control'], ARRAY['portfolio.long_term_specialist_assignments','agent.tasks','agent.inbox_items','agent.agent_messages'], ARRAY['postgres_read_model','agent_worker_dispatch'], 'Dispatch only creates research work; no capital action.', 'Create specialist assignments for every missing long-term thesis module.', '{"capital_action_allowed":false}'::jsonb),
    ('long_term_business_model_review', 'Long-Term Business Model Review', 'long_term_research', 'research', 'research', 'active', 'worker_or_llm', 'read_only', ARRAY['business model','unit economics','moat'], ARRAY['portfolio.holding_thesis_research_updates','research.corporate_filings','knowledge.obsidian_notes'], ARRAY['portfolio.holding_thesis_checklists','knowledge.obsidian_notes'], ARRAY['postgres_read_model','qdrant_vector_search'], 'Cannot complete without company source evidence.', 'Review business model, unit economics, moat evidence, and missing sources.', '{"checklist_keys":["business_model","moat_scorecard"]}'::jsonb),
    ('long_term_industry_review', 'Long-Term Industry Review', 'long_term_research', 'research', 'research', 'active', 'worker_or_llm', 'read_only', ARRAY['industry structure','competitive intensity'], ARRAY['research.corporate_filings','knowledge.obsidian_notes'], ARRAY['portfolio.holding_thesis_checklists','knowledge.obsidian_notes'], ARRAY['postgres_read_model','qdrant_vector_search'], 'Industry claims require source evidence.', 'Review market structure, competitors, regulation, growth runway, and disruption.', '{"checklist_keys":["industry_structure"]}'::jsonb),
    ('long_term_management_governance_review', 'Long-Term Management Governance Review', 'long_term_research', 'research', 'research', 'active', 'worker_or_llm', 'read_only', ARRAY['management','governance','promoter'], ARRAY['research.corporate_filings','knowledge.obsidian_notes'], ARRAY['portfolio.holding_thesis_checklists','knowledge.obsidian_notes'], ARRAY['postgres_read_model','qdrant_vector_search'], 'Governance red flags escalate to Risk Agent.', 'Review promoter quality, governance, incentives, related parties, and capital allocation.', '{"checklist_keys":["management_scorecard","governance_scorecard","capital_allocation"]}'::jsonb),
    ('long_term_financial_quality_review', 'Long-Term Financial Quality Review', 'long_term_research', 'research', 'research', 'active', 'worker_or_llm', 'read_only', ARRAY['financial quality','cash conversion','balance sheet'], ARRAY['research.corporate_filings','knowledge.obsidian_notes'], ARRAY['portfolio.holding_thesis_checklists','knowledge.obsidian_notes'], ARRAY['document_parser','postgres_read_model'], 'Financial modules cannot complete without financial statements.', 'Review revenue quality, cash conversion, debt, working capital, and financial red flags.', '{"checklist_keys":["financial_quality"]}'::jsonb),
    ('long_term_forensic_accounting_review', 'Long-Term Forensic Accounting Review', 'long_term_research', 'research', 'research', 'active', 'worker_or_llm', 'read_only', ARRAY['forensic accounting','red flags'], ARRAY['research.corporate_filings','knowledge.obsidian_notes'], ARRAY['portfolio.holding_thesis_checklists','portfolio.holding_theses'], ARRAY['document_parser','postgres_read_model'], 'Adversarial accounting review; can block thesis completion.', 'Review accounting red flags and forensic concerns.', '{"checklist_keys":["forensic_accounting"]}'::jsonb),
    ('long_term_valuation_review', 'Long-Term Valuation Review', 'long_term_research', 'valuation', 'research', 'active', 'worker_or_llm', 'write_with_approval', ARRAY['valuation','dcf','expected cagr','monte carlo'], ARRAY['portfolio.holding_valuation_models','market.v_latest_price_quotes','research.corporate_filings'], ARRAY['portfolio.holding_valuation_models','portfolio.holding_thesis_research_updates','knowledge.obsidian_notes'], ARRAY['postgres_read_model','valuation_model_registry'], 'No fabricated fair value or CAGR.', 'Fill valuation modules only after source financials and assumptions are present.', '{"valuation_models":["dcf","reverse_dcf","sum_of_parts","peer_comparison","historical_valuation","scenario_builder","expected_cagr","long_term_monte_carlo"]}'::jsonb),
    ('long_term_bear_case_review', 'Long-Term Bear Case Review', 'long_term_research', 'risk_research', 'research', 'active', 'worker_or_llm', 'read_only', ARRAY['bear case','thesis killer','why wrong'], ARRAY['portfolio.holding_theses','portfolio.holding_thesis_research_updates','research.corporate_filings'], ARRAY['portfolio.holding_theses','knowledge.obsidian_notes','agent.inbox_items'], ARRAY['postgres_read_model','qdrant_vector_search'], 'Must actively argue against thesis.', 'Build disconfirming evidence, thesis killers, and downside case.', '{"output":"bear_case_and_thesis_killers"}'::jsonb),
    ('long_term_portfolio_fit_review', 'Long-Term Portfolio Fit Review', 'long_term_research', 'portfolio_risk', 'portfolio', 'active', 'worker_or_llm', 'read_only', ARRAY['portfolio fit','suitability','concentration'], ARRAY['books.v_book_positions','books.v_symbol_book_exposure','portfolio.v_long_term_thesis_control'], ARRAY['agent.inbox_items','knowledge.obsidian_notes'], ARRAY['postgres_read_model','risk_limit_checker'], 'No sizing or trade recommendation without approval.', 'Review client suitability, book fit, concentration, liquidity, and cross-book conflict.', '{"output":"portfolio_fit_review"}'::jsonb)
ON CONFLICT (skill_key) DO UPDATE SET
    skill_name = EXCLUDED.skill_name,
    skill_family = EXCLUDED.skill_family,
    skill_type = EXCLUDED.skill_type,
    owner_department = EXCLUDED.owner_department,
    status = EXCLUDED.status,
    execution_mode = EXCLUDED.execution_mode,
    permission_level = EXCLUDED.permission_level,
    trigger_phrases = EXCLUDED.trigger_phrases,
    input_sources = EXCLUDED.input_sources,
    output_targets = EXCLUDED.output_targets,
    required_tools = EXCLUDED.required_tools,
    risk_notes = EXCLUDED.risk_notes,
    prompt_template = EXCLUDED.prompt_template,
    config = EXCLUDED.config,
    updated_at = now();

INSERT INTO agent.agent_skill_map (agent_name, skill_key, proficiency, is_primary, activation_rules)
VALUES
    ('Long-Term Portfolio Manager','long_term_specialist_dispatch','expert',true,'{"default_for":"long-term specialist assignment"}'::jsonb),
    ('Company Analyst','long_term_business_model_review','expert',true,'{"modules":["business_model","moat_scorecard"]}'::jsonb),
    ('Industry Analyst','long_term_industry_review','expert',true,'{"modules":["industry_structure"]}'::jsonb),
    ('Management Analyst','long_term_management_governance_review','expert',true,'{"modules":["management_scorecard","governance_scorecard"]}'::jsonb),
    ('Financial Statement Analyst','long_term_financial_quality_review','expert',true,'{"modules":["financial_quality"]}'::jsonb),
    ('Forensic Accounting Agent','long_term_forensic_accounting_review','expert',true,'{"modules":["forensic_accounting"]}'::jsonb),
    ('Valuation Agent','long_term_valuation_review','expert',true,'{"models":["dcf","reverse_dcf","sum_of_parts","peer_comparison","historical_valuation","scenario_builder","expected_cagr","long_term_monte_carlo"]}'::jsonb),
    ('Bear Case Agent','long_term_bear_case_review','expert',true,'{"output":"thesis_killers"}'::jsonb),
    ('Portfolio Fit Agent','long_term_portfolio_fit_review','expert',true,'{"output":"portfolio_fit"}'::jsonb),
    ('Risk Agent','long_term_portfolio_fit_review','working',false,'{"reviews":"risk and suitability"}'::jsonb),
    ('Quality Score Agent','long_term_business_model_review','working',false,'{"reviews":"quality synthesis after evidence"}'::jsonb)
ON CONFLICT (agent_name, skill_key) DO UPDATE SET
    proficiency = EXCLUDED.proficiency,
    is_primary = EXCLUDED.is_primary,
    activation_rules = EXCLUDED.activation_rules,
    updated_at = now();

CREATE OR REPLACE VIEW portfolio.v_long_term_specialist_assignments AS
SELECT
    assignment.id,
    assignment.assignment_key,
    assignment.holding_thesis_id,
    thesis.symbol,
    thesis.exchange,
    thesis.company_name,
    control.long_term_gross_exposure,
    control.client_count,
    control.clients,
    assignment.committee_review_id,
    committee.review_status AS committee_review_status,
    committee.decision_status AS committee_decision_status,
    assignment.module_key,
    assignment.module_name,
    assignment.assignment_type,
    assignment.agent_name,
    profile.display_title,
    profile.department,
    assignment.skill_key,
    skill.skill_name,
    assignment.status,
    assignment.source_status,
    assignment.required_sources,
    assignment.evidence,
    assignment.output_requirements,
    assignment.task_id,
    task.status AS task_status,
    task.output_note_path AS task_output_note_path,
    assignment.inbox_id,
    inbox.status AS inbox_status,
    assignment.message_id,
    message.status AS message_status,
    assignment.note_path,
    assignment.created_by,
    assignment.created_at,
    assignment.updated_at
FROM portfolio.long_term_specialist_assignments assignment
JOIN portfolio.holding_theses thesis ON thesis.id = assignment.holding_thesis_id
LEFT JOIN portfolio.v_long_term_thesis_control control ON control.id = thesis.id
LEFT JOIN portfolio.long_term_committee_reviews committee ON committee.id = assignment.committee_review_id
LEFT JOIN agent.profiles profile ON profile.agent_name = assignment.agent_name
LEFT JOIN agent.skills skill ON skill.skill_key = assignment.skill_key
LEFT JOIN agent.tasks task ON task.id = assignment.task_id
LEFT JOIN agent.inbox_items inbox ON inbox.id = assignment.inbox_id
LEFT JOIN agent.agent_messages message ON message.id = assignment.message_id
ORDER BY assignment.updated_at DESC, assignment.id DESC;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    (
        'ai_os_dispatch_long_term_specialists',
        'mcp_tool',
        'Long-Term Portfolio Manager',
        'write_with_approval',
        true,
        'Dispatch source-backed Long-Term specialist assignments for checklist, valuation, bear-case, and portfolio-fit modules.',
        '{"script":"_ai_os_runtime/scripts/dispatch_long_term_specialists.py","writes":["portfolio.long_term_specialist_assignments","agent.tasks","agent.inbox_items","agent.agent_messages","knowledge.obsidian_notes"],"reads":["portfolio.v_long_term_thesis_control","portfolio.v_long_term_committee_queue","portfolio.v_long_term_thesis_checklists","portfolio.v_long_term_valuation_models","portfolio.v_long_term_research_updates"],"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb
    )
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

UPDATE core.control_plane_modules
SET warehouse_objects = ARRAY(
        SELECT DISTINCT obj
        FROM unnest(warehouse_objects || ARRAY[
            'portfolio.long_term_specialist_assignments',
            'portfolio.v_long_term_specialist_assignments'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY['ai_os_dispatch_long_term_specialists']::TEXT[]) AS tool
    ),
    next_action = 'Long-Term specialist assignment workflow is registered; dispatch agents to close thesis evidence gaps.',
    updated_at = now()
WHERE module_key IN ('portfolio_office', 'research_inbox');
