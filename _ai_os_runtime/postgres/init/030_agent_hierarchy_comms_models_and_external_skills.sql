CREATE TABLE IF NOT EXISTS agent.model_catalog (
    model_key TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    model_family TEXT NOT NULL,
    deployment_target TEXT NOT NULL DEFAULT 'local',
    estimated_disk_gb NUMERIC(10, 2),
    context_window_hint TEXT,
    current_status TEXT NOT NULL DEFAULT 'planned',
    best_for TEXT[] NOT NULL DEFAULT '{}',
    avoid_for TEXT[] NOT NULL DEFAULT '{}',
    cost_tier TEXT NOT NULL DEFAULT 'local',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent.agent_model_assignments (
    agent_name TEXT PRIMARY KEY REFERENCES agent.profiles(agent_name) ON DELETE CASCADE,
    primary_route TEXT REFERENCES agent.model_routes(route_name) ON DELETE SET NULL,
    primary_model_key TEXT REFERENCES agent.model_catalog(model_key) ON DELETE SET NULL,
    fallback_route TEXT REFERENCES agent.model_routes(route_name) ON DELETE SET NULL,
    escalation_route TEXT REFERENCES agent.model_routes(route_name) ON DELETE SET NULL,
    context_policy TEXT NOT NULL,
    cost_policy TEXT NOT NULL DEFAULT 'local_first',
    max_autonomous_cost_tier TEXT NOT NULL DEFAULT 'local',
    escalation_triggers TEXT[] NOT NULL DEFAULT '{}',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent.org_hierarchy (
    agent_name TEXT PRIMARY KEY REFERENCES agent.profiles(agent_name) ON DELETE CASCADE,
    reports_to_agent TEXT REFERENCES agent.profiles(agent_name) ON DELETE SET NULL,
    department_key TEXT REFERENCES agent.department_registry(department_key) ON DELETE SET NULL,
    role_rank INTEGER NOT NULL DEFAULT 100,
    hierarchy_level TEXT NOT NULL DEFAULT 'specialist',
    authority_scope TEXT NOT NULL,
    decision_rights TEXT[] NOT NULL DEFAULT '{}',
    must_consult TEXT[] NOT NULL DEFAULT '{}',
    can_delegate_to TEXT[] NOT NULL DEFAULT '{}',
    approval_required_for TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent.agent_characters (
    agent_name TEXT PRIMARY KEY REFERENCES agent.profiles(agent_name) ON DELETE CASCADE,
    character_key TEXT NOT NULL UNIQUE,
    character_name TEXT NOT NULL,
    avatar_role TEXT NOT NULL,
    visual_traits TEXT NOT NULL,
    voice_style TEXT NOT NULL,
    office_location TEXT NOT NULL,
    animation_state TEXT NOT NULL DEFAULT 'working',
    color_token TEXT NOT NULL DEFAULT '#4f46e5',
    icon_hint TEXT NOT NULL DEFAULT 'user-round',
    character_prompt TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent.mailboxes (
    mailbox_key TEXT PRIMARY KEY,
    agent_name TEXT NOT NULL REFERENCES agent.profiles(agent_name) ON DELETE CASCADE,
    display_name TEXT NOT NULL,
    channel_type TEXT NOT NULL DEFAULT 'internal_email',
    address TEXT NOT NULL UNIQUE,
    purpose TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    notification_policy JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_mailboxes_agent ON agent.mailboxes(agent_name);

CREATE TABLE IF NOT EXISTS agent.agent_messages (
    id BIGSERIAL PRIMARY KEY,
    thread_key TEXT NOT NULL,
    from_agent TEXT REFERENCES agent.profiles(agent_name) ON DELETE SET NULL,
    to_agent TEXT REFERENCES agent.profiles(agent_name) ON DELETE SET NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'unread',
    related_task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    related_skill_key TEXT REFERENCES agent.skills(skill_key) ON DELETE SET NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    read_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_agent_messages_thread ON agent.agent_messages(thread_key);
CREATE INDEX IF NOT EXISTS idx_agent_messages_to_status ON agent.agent_messages(to_agent, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_messages_from ON agent.agent_messages(from_agent, created_at DESC);

INSERT INTO agent.model_catalog (
    model_key, provider, model_name, model_family, deployment_target, estimated_disk_gb,
    context_window_hint, current_status, best_for, avoid_for, cost_tier, notes
)
VALUES
    ('ollama_llama3_2_3b', 'ollama', 'llama3.2:3b', 'small_generalist', 'ssd_local_ollama', 2.00, 'short to medium context', 'installed_local', ARRAY['daily driver','routing','summaries','status checks','news triage'], ARRAY['deep valuation','large filings','complex code generation'], 'local', 'Default cheap always-on worker model when Ollama is running.'),
    ('ollama_qwen3_4b', 'ollama', 'qwen3:4b', 'small_reasoning', 'ssd_local_ollama', 2.50, 'medium context', 'installed_local', ARRAY['structured reasoning','light research','tool planning'], ARRAY['large research packs','long PDF synthesis'], 'local', 'Good local upgrade over the 3B daily driver when latency is acceptable.'),
    ('ollama_qwen3_8b', 'ollama', 'qwen3:8b', 'workhorse_reasoning', 'ssd_local_ollama', 5.50, 'medium context', 'planned_or_optional', ARRAY['research synthesis','strategy drafting','portfolio notes'], ARRAY['very large context tasks'], 'local_plus', 'Use if SSD model pull is approved and RAM pressure is acceptable.'),
    ('ollama_qwen3_14b', 'ollama', 'qwen3:14b', 'heavier_reasoning', 'ssd_local_ollama', 9.50, 'medium context', 'planned_or_optional', ARRAY['Charlie deep reviews','filing analysis','strategy generation'], ARRAY['always-on background work on 16GB machines'], 'local_plus', 'Escalation local model only when hardware allows it.'),
    ('ollama_mxbai_embed_large', 'ollama', 'mxbai-embed-large', 'embedding', 'ssd_local_ollama', 0.67, 'embedding only', 'installed_local', ARRAY['Qdrant indexing','vault retrieval','research artifact retrieval'], ARRAY['chat generation'], 'local', 'Embedding model for Obsidian, research reports, strategies, and journals.'),
    ('codex_gpt5_coding', 'codex', 'gpt-5-codex', 'frontier_coding', 'cloud_on_approval', NULL, 'large context', 'available_on_request', ARRAY['codebase changes','hard debugging','repo integration'], ARRAY['cheap continuous monitoring'], 'cloud', 'Use selectively for engineering work and difficult system fixes.'),
    ('frontier_investment_review', 'cloud_optional', 'frontier_on_approval', 'frontier_reasoning', 'cloud_on_approval', NULL, 'large context', 'available_on_request', ARRAY['large legal documents','multi-company special situations','client-facing reports'], ARRAY['routine scans','background jobs'], 'cloud', 'Budgeted escalation route only after Charlie/Jarvis marks the need.')
ON CONFLICT (model_key) DO UPDATE SET
    provider = EXCLUDED.provider,
    model_name = EXCLUDED.model_name,
    model_family = EXCLUDED.model_family,
    deployment_target = EXCLUDED.deployment_target,
    estimated_disk_gb = EXCLUDED.estimated_disk_gb,
    context_window_hint = EXCLUDED.context_window_hint,
    current_status = EXCLUDED.current_status,
    best_for = EXCLUDED.best_for,
    avoid_for = EXCLUDED.avoid_for,
    cost_tier = EXCLUDED.cost_tier,
    notes = EXCLUDED.notes,
    updated_at = now();

INSERT INTO agent.model_routes (
    route_name, task_class, default_provider, default_model, escalation_provider,
    escalation_model, max_cost_tier, notes, enabled
)
VALUES
    ('frontier_investment_review', 'investment_review', 'cloud_optional', 'frontier_on_approval', '', '', 'cloud', 'Human-approved frontier escalation for large filings, client-ready reports, complex special situations, and high-stakes investment review.', true)
ON CONFLICT (route_name) DO UPDATE SET
    task_class = EXCLUDED.task_class,
    default_provider = EXCLUDED.default_provider,
    default_model = EXCLUDED.default_model,
    escalation_provider = EXCLUDED.escalation_provider,
    escalation_model = EXCLUDED.escalation_model,
    max_cost_tier = EXCLUDED.max_cost_tier,
    notes = EXCLUDED.notes,
    enabled = EXCLUDED.enabled;

UPDATE agent.profiles
SET display_title = 'Strategy Intake Analyst',
    persona = 'Structured interviewer. Converts raw trading ideas into precise strategy specs and missing-data questions.',
    operating_style = 'Asks for timeframe, universe, entry, exit, sizing, stop, invalidation, and data source before routing.',
    mental_models = ARRAY['falsifiability','data_requirements','edge_definition','constraint_capture'],
    human_interface = 'Use when you want to describe a raw strategy idea in plain language.'
WHERE agent_name = 'Strategy Intake Agent';

UPDATE agent.profiles
SET display_title = 'Strategy Research Analyst',
    persona = 'Quant research scout. Finds comparable patterns, prior reports, and testable variants.',
    operating_style = 'Uses journals, research artifacts, and market context to produce hypotheses for the quant desk.',
    mental_models = ARRAY['pattern_library','base_rates','regime_fit','variant_generation'],
    human_interface = 'Use for strategy variants and research-backed trading hypotheses.'
WHERE agent_name = 'Strategy Research Agent';

UPDATE agent.profiles
SET display_title = 'Browser Research Runner',
    persona = 'Cautious browser operator. Collects public web evidence and snapshots without making investment calls.',
    operating_style = 'Reads first, records source URLs, screenshots when useful, and sends findings back to the requesting specialist.',
    mental_models = ARRAY['source_verification','least_privilege','evidence_capture','web_safety'],
    human_interface = 'Use when an agent needs website/document retrieval.'
WHERE agent_name = 'Browser Research Runner';

UPDATE agent.profiles
SET display_title = 'Execution Safety Officer',
    persona = 'Hard gatekeeper. Treats live execution as disabled unless explicit human approval and connector safety are present.',
    operating_style = 'Checks mandate, risk, broker mode, order type, kill switch, and audit trail before any execution path.',
    mental_models = ARRAY['kill_switch','mandate_gate','audit_trail','blast_radius'],
    human_interface = 'Use for anything that could become a real order.'
WHERE agent_name = 'Execution Safety Agent';

UPDATE agent.profiles
SET display_title = 'Trade Journal Coach',
    persona = 'Pattern extractor. Learns from real and paper trades without pretending the past predicts the future.',
    operating_style = 'Labels setup, rule adherence, mistake class, emotional context, regime, and improvement loop.',
    mental_models = ARRAY['feedback_loop','mistake_taxonomy','setup_quality','process_over_outcome'],
    human_interface = 'Use when you enter old journals, manual trades, or want lessons from trading history.'
WHERE agent_name = 'Trade Journal Learning Agent';

INSERT INTO agent.agent_model_assignments (
    agent_name, primary_route, primary_model_key, fallback_route, escalation_route,
    context_policy, cost_policy, max_autonomous_cost_tier, escalation_triggers, notes
)
VALUES
    ('Charlie Munger', 'charlie_munger_orchestration', 'ollama_qwen3_4b', 'always_on_daily_driver', 'coding_escalation', 'Retrieve portfolio, research, messages, and latest worker outputs before deciding. Use cloud only for long legal/client documents or hard code tasks.', 'local_first_escalate_only_for_deep_work', 'local_plus', ARRAY['large filing pack','client-facing investment memo','complex system implementation'], 'Charlie should feel smart but cheap by default.'),
    ('Jarvis', 'jarvis_runtime', 'ollama_llama3_2_3b', 'agent_worker_deterministic', 'coding_escalation', 'Prefer deterministic SQL/tools. Use LLM only to summarize or route user intent.', 'local_first', 'local', ARRAY['API failure repeated','code edit required','ambiguous cross-department request'], 'Jarvis is runtime, not investment alpha.'),
    ('Portfolio Manager', 'daily_brief', 'ollama_llama3_2_3b', 'local_workhorse_synthesis', 'frontier_investment_review', 'Always retrieve latest client positions, thesis age, risk events, and mailbox instructions.', 'local_first', 'local_plus', ARRAY['client-facing report','multi-client rebalance','large tax-sensitive review'], 'Client-private; no external sharing.'),
    ('Research Analyst', 'research_company_analysis', 'ollama_qwen3_4b', 'local_workhorse_synthesis', 'frontier_investment_review', 'Retrieve filings, prior research, portfolio holdings, and disconfirming evidence.', 'local_first_escalate_for_long_reports', 'local_plus', ARRAY['full annual report','large transcript pack','deep valuation model'], 'Local unless a long document needs cloud-grade synthesis.'),
    ('News Analyst', 'news_event_triage', 'ollama_llama3_2_3b', 'news_curation', 'frontier_investment_review', 'Use source URL, timestamp, symbol, materiality, and rumor/fact labels.', 'local_first', 'local', ARRAY['breaking event affecting major holding','conflicting source reports'], 'Fast low-cost triage.'),
    ('Filings Analyst', 'filing_analysis', 'ollama_qwen3_4b', 'local_workhorse_synthesis', 'frontier_investment_review', 'Parse filing facts before opinion. Summarize, do not overquote.', 'local_first_escalate_for_large_pdf', 'local_plus', ARRAY['large PDF','scheme document','legal conditions'], 'Escalate only for document complexity.'),
    ('Special Situations Agent', 'filing_analysis', 'ollama_qwen3_4b', 'local_heavy_reasoning', 'frontier_investment_review', 'Require timeline, spread, downside, probability, conditions, liquidity, and approval gates.', 'local_first_escalate_for_deal_docs', 'local_plus', ARRAY['merger scheme','open offer','delisting','reverse merger'], 'Event-driven but risk-first.'),
    ('Strategy Generator', 'strategy_generation', 'ollama_qwen3_4b', 'local_workhorse_synthesis', 'coding_escalation', 'Turn ideas into testable specs; never mark generated ideas as live.', 'local_first_escalate_for_complex_code', 'local_plus', ARRAY['complex signal code','large strategy family generation'], 'Creativity bounded by validation.'),
    ('Strategy Intake Agent', 'strategy_intake', 'ollama_llama3_2_3b', 'strategy_generation', 'coding_escalation', 'Ask missing questions and create structured strategy records.', 'local_first', 'local', ARRAY['strategy requires new code'], 'Cheap intake.'),
    ('Strategy Research Agent', 'strategy_generation', 'ollama_qwen3_4b', 'local_workhorse_synthesis', 'frontier_investment_review', 'Search journals, research artifacts, and market data before proposing variants.', 'local_first', 'local_plus', ARRAY['broad literature-style review'], 'Research scout for quant.'),
    ('Backtest Engineer', 'strategy_backtest', 'ollama_llama3_2_3b', 'agent_worker_deterministic', 'coding_escalation', 'Prefer Python/vectorbt tools and deterministic reports over LLM speculation.', 'local_tools_first', 'local', ARRAY['new backtester code','failing tests twice'], 'Tool-first.'),
    ('Optimizer Agent', 'strategy_optimizer', 'ollama_llama3_2_3b', 'agent_worker_deterministic', 'coding_escalation', 'Use walk-forward, sensitivity, and overfit checks before optimization claims.', 'local_tools_first', 'local', ARRAY['complex optimization harness'], 'Tool-first.'),
    ('Model Validation Agent', 'strategy_generation', 'ollama_qwen3_4b', 'local_workhorse_synthesis', 'frontier_investment_review', 'Challenge leakage, costs, sample size, and regime fit.', 'local_first', 'local_plus', ARRAY['activation review for large capital'], 'Can block strategy activation.'),
    ('Trading Desk Agent', 'daily_brief', 'ollama_llama3_2_3b', 'jarvis_runtime', 'coding_escalation', 'Read alerts and chart tasks. Execution remains paper/manual unless explicitly approved.', 'local_first', 'local', ARRAY['TradingView automation failure','broker connector change'], 'Intraday desk, not autonomous trader.'),
    ('Execution Safety Agent', 'daily_brief', 'ollama_llama3_2_3b', 'jarvis_runtime', 'frontier_investment_review', 'Block execution without human approval, risk review, and connector mode proof.', 'local_first', 'local', ARRAY['real broker action requested'], 'Hard approval gate.'),
    ('Risk Agent', 'daily_brief', 'ollama_qwen3_4b', 'local_workhorse_synthesis', 'frontier_investment_review', 'Retrieve portfolio, strategy validation, and drawdown data before risk opinions.', 'local_first', 'local_plus', ARRAY['client-facing risk action','large drawdown event'], 'Independent challenge function.'),
    ('Data Steward', 'jarvis_intake', 'ollama_llama3_2_3b', 'agent_worker_deterministic', 'coding_escalation', 'Use lineage, checksums, row counts, reconciliation, and no-seed policy.', 'local_first', 'local', ARRAY['new importer code','schema migration failure'], 'Data truth keeper.'),
    ('Librarian Agent', 'obsidian_retrieval_summary', 'ollama_llama3_2_3b', 'local_embedding_retrieval', 'coding_escalation', 'Keep Obsidian and Qdrant synchronized with evidence paths.', 'local_first', 'local', ARRAY['vault index failure','deduplication tool required'], 'Memory keeper.'),
    ('Browser Research Runner', 'news_curation', 'ollama_llama3_2_3b', 'jarvis_runtime', 'coding_escalation', 'Browser actions must be evidence-only and source-preserving.', 'local_first', 'local', ARRAY['browser controller failure','authenticated site workflow'], 'No autonomous destructive browser actions.'),
    ('Trade Journal Learning Agent', 'trade_journal_learning', 'ollama_llama3_2_3b', 'local_workhorse_synthesis', 'frontier_investment_review', 'Retrieve journals and ledger, extract patterns, then route to Strategy Generator.', 'local_first', 'local_plus', ARRAY['large historical journal ingestion'], 'Learns process, not predictions.'),
    ('Automation Engineer', 'agent_worker_deterministic', 'ollama_llama3_2_3b', 'jarvis_runtime', 'coding_escalation', 'Build automations only after tool permissions and approval states are explicit.', 'local_first', 'local', ARRAY['new daemon','MCP/server integration','browser automation code'], 'Engineering route.')
ON CONFLICT (agent_name) DO UPDATE SET
    primary_route = EXCLUDED.primary_route,
    primary_model_key = EXCLUDED.primary_model_key,
    fallback_route = EXCLUDED.fallback_route,
    escalation_route = EXCLUDED.escalation_route,
    context_policy = EXCLUDED.context_policy,
    cost_policy = EXCLUDED.cost_policy,
    max_autonomous_cost_tier = EXCLUDED.max_autonomous_cost_tier,
    escalation_triggers = EXCLUDED.escalation_triggers,
    notes = EXCLUDED.notes,
    updated_at = now();

INSERT INTO agent.org_hierarchy (
    agent_name, reports_to_agent, department_key, role_rank, hierarchy_level,
    authority_scope, decision_rights, must_consult, can_delegate_to, approval_required_for
)
VALUES
    ('Charlie Munger', NULL, 'executive', 1, 'chief_orchestrator', 'Final internal investment-office routing and decision review before human approval.', ARRAY['assign work','challenge conclusions','approve internal research priority'], ARRAY['Risk Agent','Portfolio Manager'], ARRAY['Jarvis','Portfolio Manager','Research Analyst','Strategy Generator','Risk Agent'], ARRAY['live trade','client-facing advice','external publication']),
    ('Jarvis', 'Charlie Munger', 'runtime', 2, 'chief_of_staff', 'Owns runtime, queues, widgets, MCPs, and work dispatch.', ARRAY['dispatch worker jobs','refresh widgets','create tasks','route tool calls'], ARRAY['Charlie Munger'], ARRAY['Automation Engineer','Data Steward','Librarian Agent','Browser Research Runner'], ARRAY['broker execution','deleting source data']),
    ('Portfolio Manager', 'Charlie Munger', 'portfolio', 10, 'department_head', 'Owns portfolio state, allocation review, client folio actions, and portfolio briefs.', ARRAY['request research','request risk review','propose rebalance'], ARRAY['Risk Agent','Charlie Munger'], ARRAY['Research Analyst','Data Steward'], ARRAY['trade/rebalance recommendation']),
    ('Research Analyst', 'Charlie Munger', 'research', 20, 'department_head', 'Owns company research and thesis maintenance.', ARRAY['write research notes','request filings analysis','open idea tickets'], ARRAY['Filings Analyst','Special Situations Agent'], ARRAY['Filings Analyst','Browser Research Runner','Librarian Agent'], ARRAY['buy/sell recommendation']),
    ('News Analyst', 'Research Analyst', 'news', 30, 'specialist', 'Owns news, exchange announcements, social watchlists, and urgency routing.', ARRAY['create news inbox','route material filings'], ARRAY['Filings Analyst'], ARRAY['Browser Research Runner'], ARRAY['rumor-based action']),
    ('Filings Analyst', 'Research Analyst', 'research', 31, 'specialist', 'Owns filing extraction and corporate action classification.', ARRAY['write filing note','route special situation'], ARRAY['Special Situations Agent'], ARRAY['Browser Research Runner'], ARRAY['investment action']),
    ('Special Situations Agent', 'Research Analyst', 'research', 32, 'specialist', 'Owns demergers, mergers, buybacks, open offers, delistings, and arbitrage reviews.', ARRAY['create event idea','request risk gate'], ARRAY['Risk Agent','Charlie Munger'], ARRAY['Filings Analyst','Portfolio Manager'], ARRAY['capital allocation']),
    ('Strategy Generator', 'Charlie Munger', 'quant', 40, 'department_head', 'Owns trading-system ideation and candidate strategy design.', ARRAY['create strategy candidate','request backtest'], ARRAY['Model Validation Agent','Risk Agent'], ARRAY['Strategy Intake Agent','Strategy Research Agent','Backtest Engineer','Optimizer Agent'], ARRAY['live strategy activation']),
    ('Strategy Intake Agent', 'Strategy Generator', 'quant', 41, 'specialist', 'Structures user strategy ideas into machine-testable specs.', ARRAY['create strategy intake'], ARRAY['Strategy Generator'], ARRAY['Strategy Research Agent'], ARRAY['strategy activation']),
    ('Strategy Research Agent', 'Strategy Generator', 'quant', 42, 'specialist', 'Finds research-backed strategy variants and journal-derived hypotheses.', ARRAY['create strategy hypothesis'], ARRAY['Strategy Generator'], ARRAY['Trade Journal Learning Agent'], ARRAY['strategy activation']),
    ('Backtest Engineer', 'Strategy Generator', 'quant', 43, 'specialist', 'Runs reproducible backtests and creates artifacts.', ARRAY['run/publish backtest artifact'], ARRAY['Model Validation Agent'], ARRAY['Optimizer Agent'], ARRAY['live strategy activation']),
    ('Optimizer Agent', 'Strategy Generator', 'quant', 44, 'specialist', 'Optimizes strategy parameters with overfit controls.', ARRAY['run optimization review'], ARRAY['Model Validation Agent'], ARRAY['Backtest Engineer'], ARRAY['live strategy activation']),
    ('Model Validation Agent', 'Strategy Generator', 'quant', 45, 'independent_reviewer', 'Challenges strategy validity before activation.', ARRAY['block strategy activation','request retest'], ARRAY['Risk Agent'], ARRAY['Backtest Engineer','Optimizer Agent'], ARRAY['approval override']),
    ('Trading Desk Agent', 'Charlie Munger', 'trading', 50, 'department_head', 'Owns alerts, paper trades, TradingView tasks, manual trade capture, and intraday watch.', ARRAY['log manual trade','log paper trade','request chart task'], ARRAY['Execution Safety Agent','Risk Agent'], ARRAY['Browser Research Runner','Automation Engineer'], ARRAY['live broker execution']),
    ('Execution Safety Agent', 'Trading Desk Agent', 'trading', 51, 'hard_gate', 'Blocks live order paths unless mandate, risk, and human approval are present.', ARRAY['block execution','request approval'], ARRAY['Risk Agent','Charlie Munger'], ARRAY[]::text[], ARRAY['any broker write']),
    ('Trade Journal Learning Agent', 'Trading Desk Agent', 'trading', 52, 'specialist', 'Learns from old journals, manual trades, and paper trades.', ARRAY['create trade lesson','request strategy idea'], ARRAY['Strategy Generator'], ARRAY['Strategy Research Agent'], ARRAY['strategy activation']),
    ('Risk Agent', 'Charlie Munger', 'risk', 60, 'independent_reviewer', 'Owns risk gates, concentration checks, and approval challenge.', ARRAY['block action','request more evidence','approve internal risk pass'], ARRAY['Charlie Munger'], ARRAY['Portfolio Manager','Model Validation Agent'], ARRAY['final human approval']),
    ('Data Steward', 'Jarvis', 'data', 70, 'specialist', 'Owns data lineage, import quality, and reconciliation.', ARRAY['approve data source for analysis','flag stale data'], ARRAY['Jarvis'], ARRAY['Librarian Agent'], ARRAY['source deletion']),
    ('Librarian Agent', 'Jarvis', 'knowledge', 80, 'specialist', 'Owns Obsidian, Qdrant, research folders, and retrieval hygiene.', ARRAY['write research output note','request reindex'], ARRAY['Research Analyst'], ARRAY['Data Steward'], ARRAY['vault restructuring']),
    ('Browser Research Runner', 'Jarvis', 'data', 90, 'tool_operator', 'Operates browser/public web evidence capture for specialists.', ARRAY['capture source evidence'], ARRAY['requesting specialist'], ARRAY[]::text[], ARRAY['authenticated/destructive browser action']),
    ('Automation Engineer', 'Jarvis', 'automation', 100, 'builder', 'Builds daemons, MCP adapters, browser automations, and notification routers.', ARRAY['propose automation','implement approved adapter'], ARRAY['Jarvis','Execution Safety Agent'], ARRAY['Data Steward'], ARRAY['live external write automation'])
ON CONFLICT (agent_name) DO UPDATE SET
    reports_to_agent = EXCLUDED.reports_to_agent,
    department_key = EXCLUDED.department_key,
    role_rank = EXCLUDED.role_rank,
    hierarchy_level = EXCLUDED.hierarchy_level,
    authority_scope = EXCLUDED.authority_scope,
    decision_rights = EXCLUDED.decision_rights,
    must_consult = EXCLUDED.must_consult,
    can_delegate_to = EXCLUDED.can_delegate_to,
    approval_required_for = EXCLUDED.approval_required_for,
    updated_at = now();

INSERT INTO agent.agent_characters (
    agent_name, character_key, character_name, avatar_role, visual_traits,
    voice_style, office_location, animation_state, color_token, icon_hint, character_prompt
)
VALUES
    ('Charlie Munger', 'charlie_munger', 'Charlie Munger', 'chief_orchestrator', 'Older sharp-eyed capital allocator at the central desk, plain suit, no decoration, expression says prove it.', 'Blunt, rational, compressed, downside-first.', 'Executive desk', 'reviewing_decision_memo', '#b45309', 'landmark', 'Represent Charlie as the skeptical investment-office chief who forces inversion, margin of safety, and opportunity cost before any action.'),
    ('Jarvis', 'jarvis_runtime', 'Jarvis', 'runtime_operator', 'Calm systems operator at a command wall with queues, logs, widgets, and tool health panels.', 'Precise, operational, concise.', 'Runtime command wall', 'dispatching_jobs', '#2563eb', 'gauge', 'Represent Jarvis as the always-on operating layer that turns user intent into tasks, widgets, evidence, and safe tool calls.'),
    ('Portfolio Manager', 'portfolio_manager', 'Portfolio Manager', 'portfolio_lead', 'Focused allocator with client books, exposure map, and thesis cards.', 'Practical, risk-adjusted, client-aware.', 'Portfolio desk', 'checking_exposures', '#059669', 'briefcase', 'Represent the portfolio lead as owner of client folios, allocation, drift, and long-term action lists.'),
    ('Research Analyst', 'research_analyst', 'Research Analyst', 'equity_researcher', 'Quiet analyst surrounded by filings, transcripts, and company research folders.', 'Skeptical, source-bound, thesis-driven.', 'Research library', 'writing_thesis', '#7c3aed', 'file-search', 'Represent the equity researcher as patient, evidence-first, and focused on durable company theses.'),
    ('News Analyst', 'news_analyst', 'News Analyst', 'news_curator', 'Fast desk with source feeds, exchange alerts, and credibility tags.', 'Fast, skeptical, materiality-first.', 'News monitor', 'triaging_feed', '#dc2626', 'radio', 'Represent the news analyst as source-quality focused and allergic to rumor-driven action.'),
    ('Filings Analyst', 'filings_analyst', 'Filings Analyst', 'filing_specialist', 'Legal-document specialist with highlighted filings, timelines, and corporate action tables.', 'Precise, legalistic, dates-first.', 'Filings desk', 'extracting_terms', '#9333ea', 'file-text', 'Represent the filings analyst as the document truth extractor before narrative.'),
    ('Special Situations Agent', 'special_situations', 'Special Situations Analyst', 'event_driven_analyst', 'Event analyst with deal timelines, spread board, and downside scenarios.', 'Event-driven, skeptical, probability-weighted.', 'Special situations desk', 'mapping_deal_path', '#be123c', 'git-merge', 'Represent the special situations analyst as focused on conditions, timelines, spreads, and failure modes.'),
    ('Strategy Generator', 'strategy_generator', 'Strategy Generator', 'quant_idea_lead', 'Quant strategist with signal whiteboard and regime map.', 'Creative but testable.', 'Quant lab', 'drafting_hypothesis', '#0f766e', 'sparkles', 'Represent the strategy generator as creative only when each idea is falsifiable and testable.'),
    ('Strategy Intake Agent', 'strategy_intake', 'Strategy Intake Analyst', 'strategy_interviewer', 'Structured interviewer with checklist forms and rule cards.', 'Clarifying, structured, concise.', 'Quant intake station', 'structuring_request', '#0891b2', 'clipboard-list', 'Represent the intake analyst as the agent that turns rough ideas into exact specs.'),
    ('Strategy Research Agent', 'strategy_research', 'Strategy Research Analyst', 'quant_research_scout', 'Research scout with journals, prior trades, and pattern library.', 'Curious, comparative, evidence-seeking.', 'Quant research shelf', 'searching_patterns', '#0284c7', 'search', 'Represent the strategy research analyst as a scout for comparable setups and variants.'),
    ('Backtest Engineer', 'backtest_engineer', 'Backtest Engineer', 'quant_engineer', 'Engineer at reproducible backtest console with data lineage and charts.', 'Tool-first, reproducible, no hype.', 'Backtest bench', 'running_backtest', '#16a34a', 'flask-conical', 'Represent the backtest engineer as deterministic and suspicious of unverified performance.'),
    ('Optimizer Agent', 'optimizer_agent', 'Strategy Optimizer', 'optimizer', 'Parameter-grid operator with heatmaps and walk-forward panels.', 'Robustness-first, overfit-aware.', 'Optimization pod', 'testing_sensitivity', '#65a30d', 'sliders-horizontal', 'Represent optimizer as the agent that prefers simple robust ranges over perfect hindsight.'),
    ('Model Validation Agent', 'model_validation', 'Model Validation Agent', 'validation_reviewer', 'Independent reviewer with leakage, costs, and sample-size red flags.', 'Adversarial, precise, gatekeeping.', 'Validation desk', 'challenging_results', '#ca8a04', 'shield-check', 'Represent validation as the independent quant challenge function.'),
    ('Trading Desk Agent', 'trading_desk', 'Trading Desk Agent', 'trading_operator', 'Intraday desk with alerts, charts, paper blotter, and TradingView task queue.', 'Fast, disciplined, non-autonomous.', 'Trading desk', 'watching_alerts', '#ea580c', 'line-chart', 'Represent the trading desk as alert monitor and manual/paper trade recorder, not an autonomous broker.'),
    ('Execution Safety Agent', 'execution_safety', 'Execution Safety Officer', 'execution_gatekeeper', 'Strict control officer beside a locked order ticket and kill switch.', 'Hard no until approval is clear.', 'Execution gate', 'checking_mandate', '#991b1b', 'lock-keyhole', 'Represent safety as the gate that blocks broker writes without proof and approval.'),
    ('Trade Journal Learning Agent', 'trade_journal', 'Trade Journal Coach', 'journal_analyst', 'Coach reading old trade journals with mistake taxonomy and setup tags.', 'Pattern-focused, process-first.', 'Journal review desk', 'tagging_lessons', '#4f46e5', 'book-open', 'Represent journal learning as extracting process lessons from real history.'),
    ('Risk Agent', 'risk_agent', 'Risk Officer', 'risk_challenger', 'Independent risk officer with concentration map, drawdown controls, and approval queue.', 'Adversarial, calm, downside-aware.', 'Risk desk', 'reviewing_limits', '#b91c1c', 'shield-alert', 'Represent risk as independent challenge before capital moves.'),
    ('Data Steward', 'data_steward', 'Data Steward', 'data_engineer', 'Data engineer with lineage graph, checksums, row counts, and stale-source flags.', 'Exact, lineage-first, no seed data.', 'Data spine', 'reconciling_sources', '#475569', 'database-zap', 'Represent data steward as the keeper of data truth and no-seed policy.'),
    ('Librarian Agent', 'librarian', 'Knowledge Librarian', 'memory_keeper', 'Knowledge keeper organizing Obsidian graph, Qdrant collections, and research folders.', 'Orderly, retrieval-aware, evidence-preserving.', 'Knowledge vault', 'indexing_notes', '#6d28d9', 'library', 'Represent librarian as durable memory and retrieval hygiene.'),
    ('Browser Research Runner', 'browser_runner', 'Browser Research Runner', 'browser_operator', 'Browser operator with source snapshots and public web evidence tray.', 'Cautious, source-preserving.', 'Browser station', 'capturing_sources', '#0369a1', 'globe', 'Represent browser runner as a limited tool operator that captures evidence for specialists.'),
    ('Automation Engineer', 'automation_engineer', 'Automation Engineer', 'automation_builder', 'Builder with launchd daemons, MCP adapters, browser controllers, and notification lines.', 'Pragmatic, safe-by-design.', 'Automation workbench', 'building_adapter', '#0d9488', 'wrench', 'Represent automation as the builder of approved system connectors and workers.')
ON CONFLICT (agent_name) DO UPDATE SET
    character_key = EXCLUDED.character_key,
    character_name = EXCLUDED.character_name,
    avatar_role = EXCLUDED.avatar_role,
    visual_traits = EXCLUDED.visual_traits,
    voice_style = EXCLUDED.voice_style,
    office_location = EXCLUDED.office_location,
    animation_state = EXCLUDED.animation_state,
    color_token = EXCLUDED.color_token,
    icon_hint = EXCLUDED.icon_hint,
    character_prompt = EXCLUDED.character_prompt,
    updated_at = now();

INSERT INTO agent.mailboxes (
    mailbox_key, agent_name, display_name, channel_type, address, purpose, status, notification_policy
)
SELECT
    lower(regexp_replace(p.agent_name, '[^a-zA-Z0-9]+', '-', 'g')) AS mailbox_key,
    p.agent_name,
    coalesce(p.display_title, p.agent_name) || ' Inbox' AS display_name,
    'internal_email',
    lower(regexp_replace(p.agent_name, '[^a-zA-Z0-9]+', '.', 'g')) || '@ai-office.local',
    'Internal AI office messages, assignments, review requests, and specialist handoffs.',
    'active',
    jsonb_build_object('surface_in_dashboard', true, 'digest_to', 'Charlie Munger', 'private_to_agent', true)
FROM agent.profiles p
WHERE p.status = 'active'
ON CONFLICT (mailbox_key) DO UPDATE SET
    agent_name = EXCLUDED.agent_name,
    display_name = EXCLUDED.display_name,
    address = EXCLUDED.address,
    purpose = EXCLUDED.purpose,
    status = EXCLUDED.status,
    notification_policy = EXCLUDED.notification_policy,
    updated_at = now();

INSERT INTO agent.agent_messages (
    thread_key, from_agent, to_agent, subject, body, priority, status, related_skill_key, metadata
)
VALUES
    ('office-operating-protocol', 'Charlie Munger', 'Jarvis', 'Run the office through evidence, not vibes', 'Keep every agent handoff as a task, inbox item, message, worker run, or Obsidian note. If evidence is missing, say so and route the next action instead of inventing a conclusion.', 'high', 'unread', 'route_user_request', '{"seeded_protocol":true}'::jsonb),
    ('portfolio-research-loop', 'Portfolio Manager', 'Research Analyst', 'Holdings need thesis maintenance', 'For portfolio positions, maintain company notes, thesis drift, catalysts, and disconfirming evidence. Send special-situation items to the event desk and risk items to Risk.', 'high', 'unread', 'company_research_note', '{"seeded_protocol":true}'::jsonb),
    ('news-filings-loop', 'News Analyst', 'Filings Analyst', 'Exchange announcements must become filing facts', 'When NSE/BSE or global news points to a corporate action, extract dates, conditions, affected securities, and source URLs before routing any idea.', 'high', 'unread', 'analyze_corporate_filing', '{"seeded_protocol":true}'::jsonb),
    ('quant-validation-loop', 'Strategy Generator', 'Model Validation Agent', 'No generated strategy goes live without challenge', 'Generated strategies are hypotheses only. Require backtest lineage, costs, walk-forward or robustness checks, and risk review before activation.', 'high', 'unread', 'validate_strategy_model', '{"seeded_protocol":true}'::jsonb),
    ('trading-safety-loop', 'Trading Desk Agent', 'Execution Safety Agent', 'Live execution stays gated', 'Manual and paper trades can be logged. Broker writes stay blocked until explicit human approval, mandate proof, risk pass, and connector mode proof are present.', 'critical', 'unread', NULL, '{"seeded_protocol":true,"skill_to_link_after_seed":"openalgo_execution_guarded"}'::jsonb)
ON CONFLICT DO NOTHING;

INSERT INTO agent.skills (
    skill_key, skill_name, skill_family, skill_type, owner_department, status,
    execution_mode, permission_level, trigger_phrases, input_sources,
    output_targets, required_tools, risk_notes, prompt_template, config
)
VALUES
    ('fincept_tool_rag_catalog', 'Fincept Tool RAG Catalog', 'fincept', 'tool_catalog', 'runtime', 'active', 'adapter_planned', 'read_only', ARRAY['fincept tools','tool rag','tool catalog'], ARRAY['FinceptTerminal MCP service','FinceptTerminal ToolRetriever'], ARRAY['agent.tool_registry','agent.skills'], ARRAY['fincept_terminal_local_checkout'], 'Imported as a pattern and catalog until a direct runtime adapter is enabled.', 'Use Fincept MCP/Tool RAG patterns to retrieve the smallest relevant tool set for an agent task.', '{"source_repo":"https://github.com/Fincept-Corporation/FinceptTerminal","local_path":"_ai_os_runtime/external_components/FinceptTerminal","direct_runtime_adapter":"planned","evidence":["fincept-qt/src/mcp/ToolRetriever.h","fincept-qt/src/mcp/McpService.h"]}'::jsonb),
    ('fincept_equity_research_tools', 'Fincept Equity Research Tools', 'fincept', 'research', 'research', 'active', 'adapter_planned', 'read_only', ARRAY['fincept research','equity tools','company analysis'], ARRAY['FinceptTerminal EquityResearchTools','research artifacts'], ARRAY['research.ideas','knowledge.obsidian_notes'], ARRAY['fincept_terminal_local_checkout','postgres_read_model'], 'Do not claim Fincept has run live analysis until adapter execution is wired.', 'Use Fincept equity research surfaces as component patterns for company research and report flow.', '{"source_repo":"https://github.com/Fincept-Corporation/FinceptTerminal","direct_runtime_adapter":"planned","evidence":["fincept-qt/src/mcp/tools/EquityResearchTools.cpp"]}'::jsonb),
    ('fincept_report_builder', 'Fincept Report Builder', 'fincept', 'reporting', 'portfolio', 'active', 'adapter_planned', 'read_only', ARRAY['fincept report','research report','client report'], ARRAY['FinceptTerminal ReportBuilderTools','portfolio positions','research notes'], ARRAY['knowledge.obsidian_notes','client reports'], ARRAY['fincept_terminal_local_checkout','obsidian_writeback'], 'Client reports require human review.', 'Use Fincept report-builder patterns for research and client-ready PDF/report flows.', '{"source_repo":"https://github.com/Fincept-Corporation/FinceptTerminal","direct_runtime_adapter":"planned","evidence":["fincept-qt/src/mcp/tools/ReportBuilderTools.cpp"]}'::jsonb),
    ('fincept_news_rss_analysis', 'Fincept News And RSS Analysis', 'fincept', 'news', 'news', 'active', 'adapter_planned', 'read_only', ARRAY['fincept news','rss feeds','news analysis'], ARRAY['FinceptTerminal rss/news tables','market.news_items'], ARRAY['market.news_items','agent.inbox_items'], ARRAY['fincept_terminal_local_checkout','news_feed_reader'], 'News must keep source URL and materiality labels.', 'Use Fincept RSS/news-analysis schema and UI patterns for market news ingestion.', '{"source_repo":"https://github.com/Fincept-Corporation/FinceptTerminal","direct_runtime_adapter":"planned","evidence":["fincept-qt/src/storage/sqlite/migrations/v031_rss_feeds.cpp","fincept-qt/src/storage/sqlite/migrations/v035_news_analysis.cpp"]}'::jsonb),
    ('fincept_options_iv_oi_suite', 'Fincept Options IV/OI Suite', 'fincept', 'options_analytics', 'trading', 'active', 'adapter_planned', 'read_only', ARRAY['oi','iv history','options analytics','straddle'], ARRAY['FinceptTerminal OI/IV stores','trading option data'], ARRAY['trading.signals','ops.dashboard_widgets'], ARRAY['fincept_terminal_local_checkout','postgres_read_model'], 'Analytics only; no order execution.', 'Use Fincept options storage and analytics patterns for IV, OI, and option dashboard widgets.', '{"source_repo":"https://github.com/Fincept-Corporation/FinceptTerminal","direct_runtime_adapter":"planned","evidence":["fincept-qt/src/storage/sqlite/migrations/v025_oi_snapshots.cpp","fincept-qt/src/storage/sqlite/migrations/v028_iv_history.cpp"]}'::jsonb),
    ('fincept_alpha_arena_research', 'Fincept Alpha Arena Research', 'fincept', 'quant_research', 'quant', 'active', 'adapter_planned', 'read_only', ARRAY['alpha arena','factor research','fincept quant'], ARRAY['FinceptTerminal alpha arena','strategy candidates'], ARRAY['strategy.generated_ideas','strategy.validation_reviews'], ARRAY['fincept_terminal_local_checkout'], 'Alpha ideas require independent backtest and validation in our warehouse.', 'Use Fincept Alpha Arena patterns for strategy idea libraries and factor comparison.', '{"source_repo":"https://github.com/Fincept-Corporation/FinceptTerminal","direct_runtime_adapter":"planned","evidence":["fincept-qt/src/storage/sqlite/migrations/v024_alpha_arena.cpp","fincept-qt/src/storage/sqlite/migrations/v050_alpha_arena_rewrite.cpp"]}'::jsonb),
    ('fincept_historical_data_store', 'Fincept Historical Data Store', 'fincept', 'data_store', 'data', 'active', 'adapter_planned', 'read_only', ARRAY['historical data','fincept historify','ohlcv store'], ARRAY['FinceptTerminal HistoricalDataStore','trading.ohlcv'], ARRAY['trading.ohlcv','core.data_source_checks'], ARRAY['fincept_terminal_local_checkout'], 'Do not duplicate or overwrite warehouse OHLCV without lineage.', 'Use Fincept historify/OpenAlgo-inspired storage design as a component reference.', '{"source_repo":"https://github.com/Fincept-Corporation/FinceptTerminal","direct_runtime_adapter":"planned","evidence":["fincept-qt/src/storage/HistoricalDataStore.h","fincept-qt/src/storage/sqlite/migrations/v033_historify.cpp"]}'::jsonb),
    ('fincept_agent_chat_sessions', 'Fincept Agent Chat Sessions', 'fincept', 'agent_runtime', 'runtime', 'active', 'reference_pattern', 'read_only', ARRAY['agent chat','fincept agents','sessions'], ARRAY['FinceptTerminal chat/session repos','agent.chat_turns'], ARRAY['agent.chat_turns','agent.agent_messages'], ARRAY['fincept_terminal_local_checkout'], 'Pattern only until session runtime is bridged.', 'Use Fincept agent/session UX patterns to improve Charlie/Jarvis chat and team routing.', '{"source_repo":"https://github.com/Fincept-Corporation/FinceptTerminal","direct_runtime_adapter":"planned","evidence":["fincept-qt/src/screens/agent_config/AgentChatPanel.cpp","fincept-qt/src/storage/repositories/ChatRepository.cpp"]}'::jsonb),
    ('fincept_mcp_bridge', 'Fincept MCP Bridge', 'fincept', 'mcp_bridge', 'automation', 'active', 'adapter_planned', 'write_with_approval', ARRAY['fincept mcp','external mcp','tool bridge'], ARRAY['FinceptTerminal TerminalMcpBridge','core.mcp_integration_registry'], ARRAY['agent.tool_registry','agent.mcp_audit_log'], ARRAY['fincept_terminal_local_checkout'], 'External MCP tool calls require allowlists and audit logging.', 'Use Fincept bridge patterns for internal/external MCP discovery and execution.', '{"source_repo":"https://github.com/Fincept-Corporation/FinceptTerminal","direct_runtime_adapter":"planned","evidence":["fincept-qt/src/mcp/TerminalMcpBridge.h","fincept-qt/src/mcp/McpManager.h"]}'::jsonb),
    ('fincept_gov_macro_data', 'Fincept Government And Macro Data', 'fincept', 'macro_data', 'research', 'active', 'adapter_planned', 'read_only', ARRAY['macro data','government data','treasury data'], ARRAY['FinceptTerminal gov data panels','macro feeds'], ARRAY['market.news_items','research.ideas'], ARRAY['fincept_terminal_local_checkout'], 'Macro context is not a trade by itself.', 'Use Fincept government/macro panels as reference for macro dashboards.', '{"source_repo":"https://github.com/Fincept-Corporation/FinceptTerminal","direct_runtime_adapter":"planned","evidence":["fincept-qt/src/screens/gov_data"]}'::jsonb),

    ('openalgo_market_data_api', 'OpenAlgo Market Data API', 'openalgo', 'market_data', 'data', 'active', 'api_adapter_planned', 'read_only', ARRAY['openalgo data','quotes','historical ohlcv'], ARRAY['OpenAlgo REST API','market data'], ARRAY['trading.ohlcv','market.price_quotes'], ARRAY['openalgo_local_api'], 'Requires explicit local OpenAlgo API key/config before use.', 'Use OpenAlgo quotes, depth, OHLCV, symbol services, and broker-neutral market data as a source adapter.', '{"source_repo":"https://github.com/marketcalls/openalgo","okf_path":"okf/api","direct_runtime_adapter":"planned","source_docs":["https://docs.openalgo.in/"]}'::jsonb),
    ('openalgo_execution_guarded', 'OpenAlgo Execution Guarded', 'openalgo', 'execution', 'trading', 'planned', 'api_adapter_planned', 'write_with_approval', ARRAY['openalgo order','execute order','place order'], ARRAY['OpenAlgo order-management API'], ARRAY['trading.trade_activity_ledger','agent.approvals'], ARRAY['openalgo_local_api','approval_gate_writer'], 'Live broker writes stay disabled until human approval, risk pass, and kill switch exist.', 'Use OpenAlgo execution API only through Execution Safety Agent and paper/manual workflow first.', '{"source_repo":"https://github.com/marketcalls/openalgo","okf_path":"okf/skills/execution.md","direct_runtime_adapter":"blocked_until_approved"}'::jsonb),
    ('openalgo_indicator_scanner', 'OpenAlgo Indicator Scanner', 'openalgo', 'technical_indicators', 'trading', 'active', 'api_adapter_planned', 'read_only', ARRAY['indicator scanner','technical indicator','supertrend','rsi scanner'], ARRAY['OpenAlgo indicators','live feed'], ARRAY['trading.signals','strategy.generated_ideas'], ARRAY['openalgo_local_api'], 'Signals are alerts, not trades.', 'Use OpenAlgo indicator and scanner skill patterns for intraday/technical monitoring.', '{"source_repo":"https://github.com/marketcalls/openalgo","okf_path":"okf/skills/indicators.md","direct_runtime_adapter":"planned"}'::jsonb),
    ('openalgo_vectorbt_backtesting', 'OpenAlgo VectorBT Backtesting', 'openalgo', 'backtesting', 'quant', 'active', 'local_python_planned', 'write_with_approval', ARRAY['vectorbt','backtest','optimize','tearsheet'], ARRAY['OpenAlgo skills backtesting','trading.ohlcv'], ARRAY['strategy.backtest_runs','strategy.performance_snapshots','knowledge.obsidian_notes'], ARRAY['local_python_backtester','vectorbt'], 'Backtests must include costs, benchmark, and no-lookahead checks.', 'Use OpenAlgo VectorBT skill package as our main backtest/optimization template source.', '{"source_repo":"https://github.com/marketcalls/openalgo","okf_path":"okf/skills/backtesting.md","source_docs":["https://docs.openalgo.in/skills/backtesting"],"direct_runtime_adapter":"planned"}'::jsonb),
    ('openalgo_options_analytics', 'OpenAlgo Options Analytics Suite', 'openalgo', 'options_analytics', 'trading', 'active', 'api_adapter_planned', 'read_only', ARRAY['option chain','greeks','iv smile','max pain','straddle chart'], ARRAY['OpenAlgo options services','TradingView chart tasks'], ARRAY['ops.dashboard_widgets','trading.signals'], ARRAY['openalgo_local_api','tradingview_desktop_controller'], 'Analytics only; no options execution without approval.', 'Use OpenAlgo option chain, Greeks, IV smile, max pain, vol surface, OI tracker, and straddle chart patterns.', '{"source_repo":"https://github.com/marketcalls/openalgo","okf_path":"okf/tools/options-suite.md","direct_runtime_adapter":"planned"}'::jsonb),
    ('openalgo_websocket_streaming', 'OpenAlgo WebSocket Streaming', 'openalgo', 'streaming', 'trading', 'planned', 'api_adapter_planned', 'read_only', ARRAY['live ltp','websocket','streaming quote'], ARRAY['OpenAlgo websocket-streaming'], ARRAY['trading.signals','market.price_quotes'], ARRAY['openalgo_local_api'], 'Streaming alerts must be rate-limited and logged.', 'Use OpenAlgo live LTP/quote/depth streams for intraday monitors when local API is configured.', '{"source_repo":"https://github.com/marketcalls/openalgo","okf_path":"okf/api/websocket-streaming","direct_runtime_adapter":"planned"}'::jsonb),
    ('openalgo_whatsapp_alerts', 'OpenAlgo WhatsApp Alerts', 'openalgo', 'notification', 'automation', 'planned', 'api_adapter_planned', 'write_with_approval', ARRAY['whatsapp alert','send alert'], ARRAY['OpenAlgo whatsapp-services'], ARRAY['notifications','agent.inbox_items'], ARRAY['openalgo_local_api'], 'External message sending requires approval and rate limits.', 'Use OpenAlgo send-only WhatsApp alert concept after notification policy is approved.', '{"source_repo":"https://github.com/marketcalls/openalgo","okf_path":"okf/api/whatsapp-services","direct_runtime_adapter":"planned"}'::jsonb),

    ('vibe_mcp_tool_catalog', 'Vibe-Trading MCP Tool Catalog', 'vibe_trading', 'mcp_tools', 'runtime', 'active', 'external_mcp_planned', 'read_only', ARRAY['vibe mcp','trading mcp','54 tools'], ARRAY['Vibe-Trading MCP plugin'], ARRAY['agent.tool_registry','core.mcp_integration_registry'], ARRAY['vibe_trading_mcp'], 'Direct Vibe MCP use requires environment isolation and connector review.', 'Use Vibe-Trading MCP catalog as a reference for research, market data, options, and swarm tools.', '{"source_repo":"https://github.com/HKUDS/Vibe-Trading","direct_runtime_adapter":"planned","source_docs":["https://github.com/HKUDS/Vibe-Trading"]}'::jsonb),
    ('vibe_research_autopilot', 'Vibe Research Autopilot', 'vibe_trading', 'research_autopilot', 'quant', 'active', 'reference_pattern', 'read_only', ARRAY['research autopilot','hypothesis to backtest'], ARRAY['Vibe-Trading research goal runtime','strategy candidates'], ARRAY['strategy.generated_ideas','strategy.backtest_runs'], ARRAY['local_python_backtester','qdrant_vector_search'], 'Autopilot must not bypass validation.', 'Use Vibe hypothesis to research goal to backtest loop as our quant workflow pattern.', '{"source_repo":"https://github.com/HKUDS/Vibe-Trading","direct_runtime_adapter":"planned","reference":"Research Autopilot loop"}'::jsonb),
    ('vibe_swarm_investment_committee', 'Vibe Swarm Investment Committee', 'vibe_trading', 'multi_agent_review', 'executive', 'active', 'reference_pattern', 'read_only', ARRAY['swarm','investment committee','multi agent review'], ARRAY['Vibe-Trading swarm presets','agent.profiles'], ARRAY['agent.agent_messages','agent.approvals','knowledge.obsidian_notes'], ARRAY['agent_mailbox_router'], 'Swarm output is advisory and must be source-backed.', 'Use Vibe swarm status and committee pattern for Charlie-led multi-agent review.', '{"source_repo":"https://github.com/HKUDS/Vibe-Trading","direct_runtime_adapter":"planned","reference":"run_swarm and swarm status cards"}'::jsonb),
    ('vibe_shadow_account_learning', 'Vibe Shadow Account Learning', 'vibe_trading', 'trade_learning', 'trading', 'active', 'reference_pattern', 'read_only', ARRAY['shadow account','extract strategy from trades','trade learning'], ARRAY['trading.trade_journals','trading.trade_activity_ledger'], ARRAY['strategy.generated_ideas','knowledge.obsidian_notes'], ARRAY['qdrant_vector_search','postgres_read_model'], 'Shadow strategy is not a live strategy until validated.', 'Use Vibe shadow-account extraction and backtest pattern for your historical trade journals.', '{"source_repo":"https://github.com/HKUDS/Vibe-Trading","direct_runtime_adapter":"planned","reference":"extract_shadow_strategy/run_shadow_backtest"}'::jsonb),
    ('vibe_trade_journal_analysis', 'Vibe Trade Journal Analysis', 'vibe_trading', 'trade_journal', 'trading', 'active', 'reference_pattern', 'read_only', ARRAY['analyze trade journal','journal analysis'], ARRAY['trading.trade_journals','Obsidian journals'], ARRAY['strategy.generated_ideas','knowledge.obsidian_notes'], ARRAY['qdrant_vector_search'], 'Extract process lessons, not predictions.', 'Use Vibe journal analysis tool contract for old trade notes and manual logs.', '{"source_repo":"https://github.com/HKUDS/Vibe-Trading","direct_runtime_adapter":"planned","reference":"analyze_trade_journal"}'::jsonb),
    ('vibe_market_screening', 'Vibe Market Screening', 'vibe_trading', 'screening', 'research', 'active', 'external_mcp_planned', 'read_only', ARRAY['screen market','stock news','fund flow','block trades'], ARRAY['Vibe data tools','market/news feeds'], ARRAY['research.ideas','agent.inbox_items'], ARRAY['vibe_trading_mcp'], 'Screening output requires source and liquidity checks.', 'Use Vibe screening/data tool set as a future MCP-backed source for idea discovery.', '{"source_repo":"https://github.com/HKUDS/Vibe-Trading","direct_runtime_adapter":"planned","reference_tools":["screen_market","get_stock_news","get_fund_flow","get_block_trades"]}'::jsonb),
    ('vibe_options_analysis', 'Vibe Options Analysis', 'vibe_trading', 'options_analytics', 'trading', 'active', 'external_mcp_planned', 'read_only', ARRAY['analyze options','options chain'], ARRAY['Vibe options tools','option chains'], ARRAY['trading.signals','ops.dashboard_widgets'], ARRAY['vibe_trading_mcp'], 'Options analysis is not options execution.', 'Use Vibe analyze_options/options-chain contract as a secondary options analytics source.', '{"source_repo":"https://github.com/HKUDS/Vibe-Trading","direct_runtime_adapter":"planned","reference_tools":["analyze_options","get_options_chain"]}'::jsonb),
    ('vibe_run_library_reports', 'Vibe Run Library Reports', 'vibe_trading', 'reporting', 'knowledge', 'active', 'reference_pattern', 'read_only', ARRAY['run library','reports','past runs'], ARRAY['Vibe run library','agent.worker_runs'], ARRAY['knowledge.obsidian_notes','ops.dashboard_widgets'], ARRAY['obsidian_writeback'], 'Run reports need source artifacts and status.', 'Use Vibe run library pattern for searchable agent runs and post-run reports.', '{"source_repo":"https://github.com/HKUDS/Vibe-Trading","direct_runtime_adapter":"planned","reference":"reports/run library"}'::jsonb),
    ('vibe_im_channels', 'Vibe IM Channel Runtime', 'vibe_trading', 'communication', 'automation', 'planned', 'external_adapter_planned', 'write_with_approval', ARRAY['telegram','slack','discord','email','wechat','teams'], ARRAY['Vibe channel adapters'], ARRAY['notifications','agent.mailboxes'], ARRAY['notification_router'], 'External messaging requires approval, auth, and private data controls.', 'Use Vibe channel architecture as a reference for future notifications and remote access.', '{"source_repo":"https://github.com/HKUDS/Vibe-Trading","direct_runtime_adapter":"planned","reference":"IM channel runtime"}'::jsonb),
    ('vibe_safety_runtime_patterns', 'Vibe Safety Runtime Patterns', 'vibe_trading', 'safety', 'risk', 'active', 'reference_pattern', 'read_only', ARRAY['safety','runtime guard','sandbox','ssrf','kill switch'], ARRAY['Vibe security/runtime docs','agent guardrails'], ARRAY['agent.approvals','risk.events'], ARRAY['approval_gate_writer'], 'Use as safety pattern, not proof of our own safety until implemented.', 'Use Vibe guardrails such as read-only connectors, mandate gates, shell opt-in, CSRF/SSRF protection, and isolated file roots.', '{"source_repo":"https://github.com/HKUDS/Vibe-Trading","direct_runtime_adapter":"planned","reference":"safety/runtime hardening"}'::jsonb)
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
    ('Jarvis','fincept_tool_rag_catalog','working',false,'{"uses":"tool retrieval and MCP catalog pattern"}'::jsonb),
    ('Automation Engineer','fincept_mcp_bridge','working',true,'{"uses":"future adapter build"}'::jsonb),
    ('Research Analyst','fincept_equity_research_tools','working',false,'{"uses":"research component pattern"}'::jsonb),
    ('Portfolio Manager','fincept_report_builder','working',false,'{"uses":"client/research reports"}'::jsonb),
    ('News Analyst','fincept_news_rss_analysis','working',false,'{"uses":"news ingestion pattern"}'::jsonb),
    ('Trading Desk Agent','fincept_options_iv_oi_suite','working',false,'{"uses":"options analytics widgets"}'::jsonb),
    ('Strategy Generator','fincept_alpha_arena_research','working',false,'{"uses":"factor and alpha idea library"}'::jsonb),
    ('Data Steward','fincept_historical_data_store','working',false,'{"uses":"historical data store pattern"}'::jsonb),
    ('Jarvis','fincept_agent_chat_sessions','working',false,'{"uses":"agent chat/session UX pattern"}'::jsonb),
    ('Research Analyst','fincept_gov_macro_data','working',false,'{"uses":"macro context"}'::jsonb),
    ('Data Steward','openalgo_market_data_api','working',true,'{"uses":"future local OpenAlgo API data adapter"}'::jsonb),
    ('Execution Safety Agent','openalgo_execution_guarded','expert',true,'{"uses":"hard gate for any broker write path"}'::jsonb),
    ('Trading Desk Agent','openalgo_indicator_scanner','working',false,'{"uses":"technical alert/scanner pattern"}'::jsonb),
    ('Backtest Engineer','openalgo_vectorbt_backtesting','expert',true,'{"uses":"primary backtest skill package pattern"}'::jsonb),
    ('Optimizer Agent','openalgo_vectorbt_backtesting','working',false,'{"uses":"optimization and tearsheet pattern"}'::jsonb),
    ('Trading Desk Agent','openalgo_options_analytics','expert',true,'{"uses":"option chain/greeks/straddle widgets"}'::jsonb),
    ('Trading Desk Agent','openalgo_websocket_streaming','working',false,'{"uses":"future live quote stream"}'::jsonb),
    ('Automation Engineer','openalgo_whatsapp_alerts','working',false,'{"uses":"future notification channel"}'::jsonb),
    ('Jarvis','vibe_mcp_tool_catalog','working',false,'{"uses":"MCP exposure pattern"}'::jsonb),
    ('Strategy Generator','vibe_research_autopilot','working',false,'{"uses":"hypothesis to backtest loop"}'::jsonb),
    ('Charlie Munger','vibe_swarm_investment_committee','expert',true,'{"uses":"multi-agent committee review pattern"}'::jsonb),
    ('Trade Journal Learning Agent','vibe_shadow_account_learning','expert',true,'{"uses":"old trade history to strategy lessons"}'::jsonb),
    ('Trade Journal Learning Agent','vibe_trade_journal_analysis','expert',true,'{"uses":"journal ingestion and lesson extraction"}'::jsonb),
    ('Research Analyst','vibe_market_screening','working',false,'{"uses":"idea screening once MCP adapter exists"}'::jsonb),
    ('Trading Desk Agent','vibe_options_analysis','working',false,'{"uses":"secondary options analytics source"}'::jsonb),
    ('Librarian Agent','vibe_run_library_reports','working',false,'{"uses":"run library and report archive pattern"}'::jsonb),
    ('Automation Engineer','vibe_im_channels','working',false,'{"uses":"future external notification routes"}'::jsonb),
    ('Risk Agent','vibe_safety_runtime_patterns','expert',true,'{"uses":"runtime guardrail patterns"}'::jsonb)
ON CONFLICT (agent_name, skill_key) DO UPDATE SET
    proficiency = EXCLUDED.proficiency,
    is_primary = EXCLUDED.is_primary,
    activation_rules = EXCLUDED.activation_rules,
    updated_at = now();

CREATE OR REPLACE VIEW agent.v_agent_model_matrix AS
SELECT
    p.agent_name,
    p.department,
    p.display_title,
    ama.primary_route,
    mr.default_provider AS route_provider,
    mr.default_model AS route_default_model,
    mc.model_key,
    mc.provider AS assigned_provider,
    mc.model_name AS assigned_model,
    mc.model_family,
    mc.deployment_target,
    mc.estimated_disk_gb,
    mc.current_status AS model_status,
    ama.fallback_route,
    ama.escalation_route,
    ama.context_policy,
    ama.cost_policy,
    ama.max_autonomous_cost_tier,
    ama.escalation_triggers,
    ama.notes,
    ama.updated_at
FROM agent.profiles p
LEFT JOIN agent.agent_model_assignments ama ON ama.agent_name = p.agent_name
LEFT JOIN agent.model_routes mr ON mr.route_name = ama.primary_route
LEFT JOIN agent.model_catalog mc ON mc.model_key = ama.primary_model_key
WHERE p.status = 'active';

CREATE OR REPLACE VIEW agent.v_agent_org_chart AS
SELECT
    oh.agent_name,
    p.display_title,
    oh.reports_to_agent,
    rpt.display_title AS reports_to_title,
    oh.department_key,
    dr.department_name,
    oh.role_rank,
    oh.hierarchy_level,
    oh.authority_scope,
    oh.decision_rights,
    oh.must_consult,
    oh.can_delegate_to,
    oh.approval_required_for,
    ch.character_name,
    ch.avatar_role,
    ch.visual_traits,
    ch.voice_style,
    ch.office_location,
    ch.animation_state,
    ch.color_token,
    ch.icon_hint,
    mb.address AS mailbox_address,
    mb.mailbox_key,
    oh.updated_at
FROM agent.org_hierarchy oh
JOIN agent.profiles p ON p.agent_name = oh.agent_name
LEFT JOIN agent.profiles rpt ON rpt.agent_name = oh.reports_to_agent
LEFT JOIN agent.department_registry dr ON dr.department_key = oh.department_key
LEFT JOIN agent.agent_characters ch ON ch.agent_name = oh.agent_name
LEFT JOIN agent.mailboxes mb ON mb.agent_name = oh.agent_name
WHERE p.status = 'active';

CREATE OR REPLACE VIEW agent.v_agent_mailboxes AS
SELECT
    mb.mailbox_key,
    mb.agent_name,
    p.display_title,
    mb.display_name,
    mb.channel_type,
    mb.address,
    mb.purpose,
    mb.status,
    count(msg.id) FILTER (WHERE msg.status = 'unread') AS unread_count,
    max(msg.created_at) AS latest_message_at,
    mb.notification_policy,
    mb.updated_at
FROM agent.mailboxes mb
JOIN agent.profiles p ON p.agent_name = mb.agent_name
LEFT JOIN agent.agent_messages msg ON msg.to_agent = mb.agent_name
GROUP BY mb.mailbox_key, mb.agent_name, p.display_title, mb.display_name, mb.channel_type,
         mb.address, mb.purpose, mb.status, mb.notification_policy, mb.updated_at;

CREATE OR REPLACE VIEW agent.v_agent_message_threads AS
SELECT
    msg.id,
    msg.thread_key,
    msg.from_agent,
    fp.display_title AS from_title,
    msg.to_agent,
    tp.display_title AS to_title,
    msg.subject,
    msg.body,
    msg.priority,
    msg.status,
    msg.related_task_id,
    msg.related_skill_key,
    msg.metadata,
    msg.created_at,
    msg.read_at
FROM agent.agent_messages msg
LEFT JOIN agent.profiles fp ON fp.agent_name = msg.from_agent
LEFT JOIN agent.profiles tp ON tp.agent_name = msg.to_agent
ORDER BY msg.created_at DESC;

CREATE OR REPLACE VIEW agent.v_external_skill_stack AS
SELECT
    s.skill_key,
    s.skill_name,
    s.skill_family AS source_family,
    s.skill_type,
    s.owner_department,
    dr.department_name AS owner_department_name,
    s.status,
    s.execution_mode,
    s.permission_level,
    s.required_tools,
    s.risk_notes,
    s.config ->> 'source_repo' AS source_repo,
    s.config ->> 'local_path' AS local_path,
    s.config ->> 'direct_runtime_adapter' AS direct_runtime_adapter,
    array_remove(array_agg(DISTINCT asm.agent_name ORDER BY asm.agent_name), NULL) AS assigned_agents,
    s.updated_at
FROM agent.skills s
LEFT JOIN agent.department_registry dr ON dr.department_key = s.owner_department
LEFT JOIN agent.agent_skill_map asm ON asm.skill_key = s.skill_key
WHERE s.skill_family IN ('fincept', 'openalgo', 'vibe_trading')
GROUP BY s.skill_key, s.skill_name, s.skill_family, s.skill_type, s.owner_department,
         dr.department_name, s.status, s.execution_mode, s.permission_level,
         s.required_tools, s.risk_notes, s.config, s.updated_at;

CREATE OR REPLACE VIEW agent.v_agent_office_overview AS
SELECT
    (SELECT count(*) FROM agent.profiles WHERE status = 'active') AS active_agents,
    (SELECT count(*) FROM agent.department_registry WHERE status = 'active') AS active_departments,
    (SELECT count(*) FROM agent.skills WHERE status = 'active') AS active_skills,
    (SELECT count(*) FROM agent.skills WHERE skill_family = 'fincept') AS fincept_skills,
    (SELECT count(*) FROM agent.skills WHERE skill_family = 'openalgo') AS openalgo_skills,
    (SELECT count(*) FROM agent.skills WHERE skill_family = 'vibe_trading') AS vibe_trading_skills,
    (SELECT count(*) FROM agent.mailboxes WHERE status = 'active') AS active_mailboxes,
    (SELECT count(*) FROM agent.agent_messages WHERE status = 'unread') AS unread_agent_messages,
    (SELECT count(*) FROM agent.agent_model_assignments) AS model_assignments;
