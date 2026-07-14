CREATE TABLE IF NOT EXISTS research.paper_sources (
    source_key TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    base_url TEXT NOT NULL,
    ingestion_method TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    owner_agent TEXT NOT NULL DEFAULT 'Research Librarian',
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS research.research_papers (
    id BIGSERIAL PRIMARY KEY,
    paper_key TEXT NOT NULL UNIQUE,
    source_key TEXT REFERENCES research.paper_sources(source_key) ON DELETE SET NULL,
    title TEXT NOT NULL,
    authors TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    published_date DATE,
    doi TEXT,
    source_url TEXT,
    pdf_url TEXT,
    local_pdf_path TEXT,
    local_text_path TEXT,
    abstract TEXT,
    extracted_text TEXT,
    page_count INTEGER,
    content_hash TEXT,
    topics TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    asset_classes TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    markets TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    methodology_tags TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    extraction_status TEXT NOT NULL DEFAULT 'registered',
    review_status TEXT NOT NULL DEFAULT 'unreviewed',
    owner_agent TEXT NOT NULL DEFAULT 'Research Librarian',
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_research_papers_status ON research.research_papers (extraction_status, review_status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_research_papers_topics ON research.research_papers USING GIN (topics);

CREATE TABLE IF NOT EXISTS research.paper_ingestion_runs (
    id BIGSERIAL PRIMARY KEY,
    paper_id BIGINT REFERENCES research.research_papers(id) ON DELETE SET NULL,
    status TEXT NOT NULL,
    parser_name TEXT,
    bytes_downloaded BIGINT NOT NULL DEFAULT 0,
    page_count INTEGER,
    extracted_chars INTEGER NOT NULL DEFAULT 0,
    artifact_id BIGINT REFERENCES core.raw_artifacts(id) ON DELETE SET NULL,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    created_by TEXT NOT NULL DEFAULT 'Research Paper Ingestor'
);

CREATE TABLE IF NOT EXISTS research.paper_strategy_hypotheses (
    id BIGSERIAL PRIMARY KEY,
    hypothesis_key TEXT NOT NULL UNIQUE,
    paper_id BIGINT NOT NULL REFERENCES research.research_papers(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    edge_hypothesis TEXT NOT NULL,
    market_scope TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    asset_classes TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    timeframe TEXT,
    signal_definition JSONB NOT NULL DEFAULT '{}'::jsonb,
    data_requirements JSONB NOT NULL DEFAULT '{}'::jsonb,
    implementation_notes TEXT,
    invalidation_tests JSONB NOT NULL DEFAULT '[]'::jsonb,
    limitations JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'research_queue',
    owner_agent TEXT NOT NULL DEFAULT 'Strategy Research Agent',
    promoted_idea_id BIGINT REFERENCES strategy.generated_ideas(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO research.paper_sources (source_key, source_name, source_type, base_url, ingestion_method, config)
VALUES
    ('arxiv', 'arXiv', 'preprint_repository', 'https://arxiv.org', 'url_or_pdf', '{"api":"https://export.arxiv.org/api/query","public":true}'::jsonb),
    ('crossref', 'Crossref', 'doi_metadata', 'https://api.crossref.org', 'doi_metadata', '{"public":true}'::jsonb),
    ('ssrn', 'SSRN', 'working_paper_repository', 'https://www.ssrn.com', 'manual_url_or_pdf', '{"browser_terms_apply":true}'::jsonb),
    ('nber', 'NBER', 'working_paper_repository', 'https://www.nber.org', 'metadata_and_public_pdf_when_allowed', '{"license_check_required":true}'::jsonb),
    ('local', 'Local Research Library', 'local_document', 'file://local', 'local_pdf', '{"allowed_roots":["vault","external_artifacts"]}'::jsonb)
ON CONFLICT (source_key) DO UPDATE SET
    source_name = EXCLUDED.source_name,
    source_type = EXCLUDED.source_type,
    base_url = EXCLUDED.base_url,
    ingestion_method = EXCLUDED.ingestion_method,
    config = EXCLUDED.config,
    updated_at = now();

CREATE OR REPLACE VIEW research.v_research_paper_queue AS
SELECT
    p.id, p.paper_key, p.source_key, s.source_name, p.title, p.authors,
    p.published_date, p.doi, p.source_url, p.pdf_url, p.local_pdf_path,
    p.local_text_path, left(p.abstract, 1200) AS abstract, p.page_count,
    p.topics, p.asset_classes, p.markets, p.methodology_tags,
    p.extraction_status, p.review_status, p.owner_agent,
    count(h.id) AS hypothesis_count,
    max(r.finished_at) AS latest_ingestion_at,
    p.evidence, p.metadata, p.created_at, p.updated_at
FROM research.research_papers p
LEFT JOIN research.paper_sources s ON s.source_key = p.source_key
LEFT JOIN research.paper_strategy_hypotheses h ON h.paper_id = p.id
LEFT JOIN research.paper_ingestion_runs r ON r.paper_id = p.id
GROUP BY p.id, s.source_name
ORDER BY CASE p.review_status WHEN 'needs_review' THEN 1 WHEN 'unreviewed' THEN 2 ELSE 3 END, p.updated_at DESC;

CREATE OR REPLACE VIEW research.v_paper_strategy_hypotheses AS
SELECT h.*, p.paper_key, p.title AS paper_title, p.authors, p.published_date,
       p.doi, p.source_url, p.pdf_url, p.extraction_status, p.review_status
FROM research.paper_strategy_hypotheses h
JOIN research.research_papers p ON p.id = h.paper_id
ORDER BY CASE h.status WHEN 'research_queue' THEN 1 WHEN 'needs_review' THEN 2 WHEN 'approved_for_backtest' THEN 3 ELSE 4 END,
         h.updated_at DESC;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_ingest_research_paper', 'mcp_tool', 'Research Librarian', 'write_db_and_artifact', true, 'Register, download when permitted, extract, hash, and queue a research paper with source evidence.', '{"api_route":"/api/research/papers/ingest","writes":["research.research_papers","research.paper_ingestion_runs","core.raw_artifacts"],"live_execution_allowed":false}'::jsonb),
    ('ai_os_generate_paper_strategy_hypotheses', 'mcp_tool', 'Strategy Research Agent', 'write_with_approval', true, 'Create source-linked testable strategy hypotheses from an extracted paper; promotion to backtest remains separate.', '{"api_route":"/api/research/papers/hypotheses","writes":["research.paper_strategy_hypotheses","agent.tasks","agent.inbox_items"],"auto_promote":false,"live_execution_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET tool_type=EXCLUDED.tool_type, owning_agent=EXCLUDED.owning_agent, permission_level=EXCLUDED.permission_level, enabled=EXCLUDED.enabled, description=EXCLUDED.description, config=EXCLUDED.config;

INSERT INTO agent.workflow_registry (
    workflow_key, workflow_name, workflow_type, owner_agent, trigger_type, status,
    permission_level, input_sources, output_targets, approval_required,
    schedule_hint, notes, metadata
)
VALUES (
    'research_paper_to_strategy_hypothesis', 'Research Paper To Strategy Hypothesis',
    'research_factory', 'Research Librarian', 'manual_url_local_or_scheduled_metadata',
    'active', 'write_with_approval',
    ARRAY['research.paper_sources','PDF/URL','local research library']::TEXT[],
    ARRAY['research.research_papers','research.paper_strategy_hypotheses','agent.tasks','knowledge.obsidian_notes']::TEXT[],
    false, 'manual now; scheduled source discovery after source-policy validation',
    'Extracts evidence first, then queues falsifiable hypotheses. It never converts a paper directly into a live strategy.',
    '{"source_backed":true,"human_review_before_backtest":true,"live_execution_allowed":false,"seed_data_allowed":false}'::jsonb
)
ON CONFLICT (workflow_key) DO UPDATE SET workflow_name=EXCLUDED.workflow_name, workflow_type=EXCLUDED.workflow_type, owner_agent=EXCLUDED.owner_agent, trigger_type=EXCLUDED.trigger_type, status=EXCLUDED.status, permission_level=EXCLUDED.permission_level, input_sources=EXCLUDED.input_sources, output_targets=EXCLUDED.output_targets, approval_required=EXCLUDED.approval_required, schedule_hint=EXCLUDED.schedule_hint, notes=EXCLUDED.notes, metadata=EXCLUDED.metadata, updated_at=now();
