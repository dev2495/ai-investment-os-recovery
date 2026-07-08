CREATE TABLE IF NOT EXISTS core.external_component_installs (
    id BIGSERIAL PRIMARY KEY,
    source_system_id BIGINT NOT NULL REFERENCES core.source_systems(id),
    component_name TEXT NOT NULL,
    install_root TEXT NOT NULL,
    repo_url TEXT,
    git_commit TEXT,
    version TEXT,
    install_status TEXT NOT NULL DEFAULT 'installed',
    build_status TEXT NOT NULL DEFAULT 'not_built',
    build_preset TEXT,
    qt_prefix TEXT,
    app_bundle_path TEXT,
    binary_path TEXT,
    runtime_mode TEXT NOT NULL DEFAULT 'local_development_install',
    requires_sandbox_escape BOOLEAN NOT NULL DEFAULT false,
    storage_location TEXT NOT NULL DEFAULT 'external_ssd',
    notes TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    installed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_system_id, component_name, install_root)
);

CREATE INDEX IF NOT EXISTS idx_external_component_installs_status
    ON core.external_component_installs (install_status, build_status);

WITH source AS (
    INSERT INTO core.source_systems (name, source_type, location, sensitivity, status, notes)
    VALUES (
        'FinceptTerminal reference repo',
        'external_git_repo_local_clone',
        '/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime/external_components/FinceptTerminal',
        'public',
        'installed_external_component',
        'FinceptTerminal cloned and built locally on the external SSD. User approved direct leverage/install on 2026-07-02; keep client data and credentials in the AI OS warehouse/secret layer, not inside the external component.'
    )
    ON CONFLICT (name) DO UPDATE SET
        source_type = EXCLUDED.source_type,
        location = EXCLUDED.location,
        sensitivity = EXCLUDED.sensitivity,
        status = EXCLUDED.status,
        notes = EXCLUDED.notes
    RETURNING id
)
INSERT INTO core.external_component_installs (
    source_system_id,
    component_name,
    install_root,
    repo_url,
    git_commit,
    version,
    install_status,
    build_status,
    build_preset,
    qt_prefix,
    app_bundle_path,
    binary_path,
    runtime_mode,
    requires_sandbox_escape,
    storage_location,
    notes,
    metadata
)
SELECT
    source.id,
    'FinceptTerminal native Qt app',
    '/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime/external_components/FinceptTerminal',
    'https://github.com/Fincept-Corporation/FinceptTerminal',
    '6d82e1f',
    '4.1.0',
    'installed',
    'build_success',
    'macos-release',
    '/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime/external_components/FinceptTerminal/.qt/6.8.3/macos',
    '/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime/external_components/FinceptTerminal/fincept-qt/build/macos-release/FinceptTerminal.app',
    '/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime/external_components/FinceptTerminal/fincept-qt/build/macos-release/FinceptTerminal.app/Contents/MacOS/FinceptTerminal',
    'local_development_install',
    true,
    'external_ssd',
    'Built with CMake macos-release outside the Codex sandbox because Qt build tools need access to macOS hw.optional.neon. Runtime links to the SSD-local Qt 6.8.3 prefix and Homebrew OpenSSL.',
    '{
        "qt_version":"6.8.3",
        "cmake_version":"4.3.4",
        "ninja_version":"1.13.2",
        "binary_arch":"arm64",
        "app_bundle_size":"91M",
        "build_steps":"752/752",
        "features_confirmed_by_build":[
            "MCP tools",
            "agent configuration",
            "portfolio monitor",
            "equity research",
            "news/RSS",
            "broker adapters",
            "FNO/options analytics",
            "backtesting",
            "algo alerts and deploy dashboard",
            "node editor",
            "AI quant lab",
            "report builder"
        ],
        "known_runtime_notes":[
            "not packaged with macdeployqt yet",
            "requires SSD Qt rpath and Homebrew OpenSSL on this machine",
            "launch outside Codex sandbox for Qt CPU feature access"
        ]
    }'::jsonb
FROM source
ON CONFLICT (source_system_id, component_name, install_root) DO UPDATE SET
    repo_url = EXCLUDED.repo_url,
    git_commit = EXCLUDED.git_commit,
    version = EXCLUDED.version,
    install_status = EXCLUDED.install_status,
    build_status = EXCLUDED.build_status,
    build_preset = EXCLUDED.build_preset,
    qt_prefix = EXCLUDED.qt_prefix,
    app_bundle_path = EXCLUDED.app_bundle_path,
    binary_path = EXCLUDED.binary_path,
    runtime_mode = EXCLUDED.runtime_mode,
    requires_sandbox_escape = EXCLUDED.requires_sandbox_escape,
    storage_location = EXCLUDED.storage_location,
    notes = EXCLUDED.notes,
    metadata = EXCLUDED.metadata,
    updated_at = now();

WITH source AS (
    SELECT id FROM core.source_systems WHERE name = 'FinceptTerminal reference repo'
),
components AS (
    SELECT * FROM (
        VALUES
        (
            'native terminal shell',
            'frontend_component',
            'fincept-qt',
            'reuse_and_adapt',
            'high',
            'installed',
            'Native C++20/Qt6 terminal-class shell built locally; use as installed sidecar and design source for dense AI Office workflows.',
            'ops',
            ARRAY['ops.browser_runs','agent.agent_runs'],
            'Use as local component/reference. Do not store AI OS client data or credentials inside Fincept runtime state.',
            '{"installed":true,"repo_component":"fincept-qt","build_status":"success"}'::jsonb
        ),
        (
            'portfolio and equity research workbench',
            'product_component',
            'fincept-qt/src/screens/portfolio',
            'reuse_and_integrate',
            'critical',
            'installed',
            'Built portfolio monitor, equity research, risk, optimization, transactions, heatmap, reports, and insights surfaces.',
            'portfolio',
            ARRAY['portfolio.positions','portfolio.snapshots','research.ideas','risk.strategy_risk_reviews'],
            'Map concepts to AI OS Postgres schemas. Client-private data remains in warehouse and safe views.',
            '{"installed":true,"screen_groups":["portfolio","equity_research"],"bridge_target":"folio_manager_dashboard"}'::jsonb
        ),
        (
            'mcp and agent workflow stack',
            'agent_component',
            'fincept-qt/src/mcp',
            'reuse_and_integrate',
            'critical',
            'installed',
            'Built MCP service/client/manager, TerminalMcpBridge, agent tools, agent config panels, teams, workflows, planner, and agentic tasks.',
            'agent',
            ARRAY['agent.tool_registry','agent.agent_profiles','agent.agent_runs'],
            'Bridge through our MCP server and registry first. Keep Charlie as orchestrator and Jarvis as runtime/tool layer.',
            '{"installed":true,"screen_groups":["agent_config","node_editor"],"tools":["TerminalMcpBridge","AgentsTools","McpServersTools"]}'::jsonb
        ),
        (
            'broker market data and live trading adapters',
            'integration_component',
            'fincept-qt/src/trading',
            'reuse_and_wrap',
            'high',
            'installed',
            'Built Indian and global broker adapters, broker websockets, live trading tools, pending orders, and instrument parsers.',
            'trading',
            ARRAY['trading.signals','trading.symbols','portfolio.trades','agent.approvals'],
            'Paper/shadow mode first. Any live order path must pass our approval center and credential isolation.',
            '{"installed":true,"brokers_seen":["Zerodha","AngelOne","Fyers","Upstox","Kotak","Dhan","AliceBlue","Groww","FivePaisa","IIFL","Motilal","Shoonya","Samco","Flattrade","ICICIDirect","IBKR","Alpaca"],"paper_first":true}'::jsonb
        ),
        (
            'quant lab backtesting and strategy workbench',
            'strategy_component',
            'fincept-qt/src/screens/ai_quant_lab',
            'reuse_and_wrap',
            'high',
            'installed',
            'Built AI Quant Lab, backtesting, algo trading, FNO strategy builder, option chain/OI/FII-DII, indicators, alpha arena, and strategy deploy panels.',
            'strategy',
            ARRAY['strategy.strategy_candidates','strategy.backtest_runs','trading.signals'],
            'Use for research/backtests first. Live deployment remains gated by paper/shadow validation.',
            '{"installed":true,"screen_groups":["ai_quant_lab","backtesting","algo_trading","fno","alpha_arena"],"paper_first":true}'::jsonb
        ),
        (
            'news filings and research intelligence workbench',
            'research_component',
            'fincept-qt/src/screens/news',
            'reuse_and_adapt',
            'high',
            'installed',
            'Built news/RSS, EDGAR MCP tools, equity research news/sentiment, geopolitics, government data, report builder, web scraper, and notes surfaces.',
            'research',
            ARRAY['research.ideas','research.filing_events','core.raw_artifacts'],
            'Use our own source attribution and filing/news ingestion. Do not mix unsourced agent conclusions into client outputs.',
            '{"installed":true,"screen_groups":["news","equity_research","geopolitics","gov_data","report_builder"],"filings":["EDGAR"],"next_sources":["NSE","BSE","SEC","RSS","Twitter/X"]}'::jsonb
        )
    ) AS rows (
        component_name,
        component_type,
        source_path,
        reuse_mode,
        priority,
        status,
        description,
        target_schema,
        target_tables,
        safety_notes,
        metadata
    )
)
INSERT INTO core.source_components (
    source_system_id,
    component_name,
    component_type,
    source_path,
    reuse_mode,
    priority,
    status,
    description,
    target_schema,
    target_tables,
    safety_notes,
    metadata
)
SELECT
    source.id,
    components.component_name,
    components.component_type,
    components.source_path,
    components.reuse_mode,
    components.priority,
    components.status,
    components.description,
    components.target_schema,
    components.target_tables,
    components.safety_notes,
    components.metadata
FROM source
CROSS JOIN components
ON CONFLICT (source_system_id, component_name) DO UPDATE SET
    component_type = EXCLUDED.component_type,
    source_path = EXCLUDED.source_path,
    reuse_mode = EXCLUDED.reuse_mode,
    priority = EXCLUDED.priority,
    status = EXCLUDED.status,
    description = EXCLUDED.description,
    target_schema = EXCLUDED.target_schema,
    target_tables = EXCLUDED.target_tables,
    safety_notes = EXCLUDED.safety_notes,
    metadata = EXCLUDED.metadata,
    updated_at = now();

WITH source AS (
    SELECT id FROM core.source_systems WHERE name = 'FinceptTerminal reference repo'
)
INSERT INTO core.raw_artifacts (
    source_system_id,
    artifact_type,
    title,
    source_url,
    local_path,
    content_hash,
    mime_type,
    sensitivity,
    metadata
)
SELECT
    source.id,
    'external_component_build',
    'FinceptTerminal local build record',
    'https://github.com/Fincept-Corporation/FinceptTerminal',
    '/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime/external_components/FinceptTerminal/fincept-qt/build/macos-release/FinceptTerminal.app',
    'fincept-build-6d82e1f-qt683-macos-release',
    'application/x-macos-app-bundle',
    'public',
    '{
        "build_status":"success",
        "build_preset":"macos-release",
        "git_commit":"6d82e1f",
        "qt_version":"6.8.3",
        "binary_arch":"arm64",
        "app_bundle_size":"91M",
        "verification":["cmake configure success","cmake build 752/752 success","binary file check arm64","otool dependency check"]
    }'::jsonb
FROM source
ON CONFLICT (source_system_id, source_url, local_path, content_hash) DO UPDATE SET
    artifact_type = EXCLUDED.artifact_type,
    title = EXCLUDED.title,
    mime_type = EXCLUDED.mime_type,
    sensitivity = EXCLUDED.sensitivity,
    metadata = EXCLUDED.metadata,
    captured_at = now();

CREATE OR REPLACE VIEW core.v_external_component_installs AS
SELECT
    eci.id,
    ss.name AS source_system,
    ss.status AS source_status,
    eci.component_name,
    eci.version,
    eci.git_commit,
    eci.install_status,
    eci.build_status,
    eci.build_preset,
    eci.runtime_mode,
    eci.requires_sandbox_escape,
    eci.storage_location,
    eci.install_root,
    eci.qt_prefix,
    eci.app_bundle_path,
    eci.binary_path,
    eci.notes,
    eci.metadata,
    eci.updated_at
FROM core.external_component_installs eci
JOIN core.source_systems ss ON ss.id = eci.source_system_id;

CREATE OR REPLACE VIEW core.v_fincept_install_status AS
SELECT
    eci.source_system,
    eci.component_name,
    eci.version,
    eci.git_commit,
    eci.install_status,
    eci.build_status,
    eci.runtime_mode,
    eci.requires_sandbox_escape,
    eci.install_root,
    eci.app_bundle_path,
    eci.binary_path,
    eci.metadata -> 'features_confirmed_by_build' AS features_confirmed_by_build,
    eci.metadata -> 'known_runtime_notes' AS known_runtime_notes,
    eci.updated_at
FROM core.v_external_component_installs eci
WHERE eci.source_system = 'FinceptTerminal reference repo';
