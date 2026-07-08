INSERT INTO agent.model_routes (
    route_name,
    task_class,
    default_provider,
    default_model,
    escalation_provider,
    escalation_model,
    max_cost_tier,
    notes,
    enabled
)
VALUES
    (
        'charlie_munger_orchestration',
        'orchestration_and_investment_judgment',
        'ollama',
        'qwen3:14b',
        'codex_or_cloud',
        '',
        'hybrid',
        'Main orchestrator route. Local-first judgment, routing, mental models, inversion, evidence checks, and specialist delegation; escalate only for long or hard synthesis.',
        true
    ),
    (
        'jarvis_runtime',
        'runtime_tool_routing',
        'ollama',
        'qwen3:8b',
        'codex_or_cloud',
        '',
        'local',
        'Runtime layer for tool execution, retrieval, command normalization, MCP calls, and write-back plumbing.',
        true
    )
ON CONFLICT (route_name) DO UPDATE SET
    task_class = EXCLUDED.task_class,
    default_provider = EXCLUDED.default_provider,
    default_model = EXCLUDED.default_model,
    escalation_provider = EXCLUDED.escalation_provider,
    escalation_model = EXCLUDED.escalation_model,
    max_cost_tier = EXCLUDED.max_cost_tier,
    notes = EXCLUDED.notes,
    enabled = EXCLUDED.enabled;

INSERT INTO agent.profiles (
    agent_name,
    department,
    role_scope,
    default_model_route,
    default_tools,
    permission_level,
    status,
    guardrails,
    output_targets
)
VALUES
    (
        'Charlie Munger',
        'orchestration',
        'Main orchestrator. Routes work through Jarvis runtime and specialist agents; applies mental models, inversion, opportunity cost, evidence checks, and blunt risk review before decisions.',
        'charlie_munger_orchestration',
        ARRAY[
            'jarvis_runtime',
            'postgres_read_model',
            'qdrant_vector_search',
            'obsidian_note_index',
            'obsidian_writeback',
            'client_ledger_reader',
            'research_inventory_reader',
            'component_review_reader'
        ],
        'write_with_approval',
        'active',
        '{
            "must_route_specialist_work": true,
            "must_require_evidence": true,
            "use_inversion": true,
            "state_opportunity_cost": true,
            "separate_facts_assumptions_recommendations": true,
            "no_live_trade_without_approval": true,
            "client_private_data_requires_safe_views": true
        }'::jsonb,
        ARRAY['agent.tasks','agent.inbox_items','knowledge.obsidian_notes','research.ideas','client_data.safe_dataset_registry']
    ),
    (
        'Jarvis',
        'runtime',
        'Runtime and tool layer. Normalizes commands, retrieves context, calls MCP tools, maintains run state, and writes approved outputs for Charlie Munger and specialist agents.',
        'jarvis_runtime',
        ARRAY['postgres_read_model','qdrant_vector_search','obsidian_note_index','obsidian_writeback','mcp_tool_dispatch'],
        'write_with_approval',
        'active',
        '{
            "not_main_orchestrator": true,
            "execute_only_routed_work": true,
            "must_require_evidence": true,
            "no_live_trade_without_approval": true
        }'::jsonb,
        ARRAY['agent.tasks','agent.run_log','knowledge.obsidian_notes']
    )
ON CONFLICT (agent_name) DO UPDATE SET
    department = EXCLUDED.department,
    role_scope = EXCLUDED.role_scope,
    default_model_route = EXCLUDED.default_model_route,
    default_tools = EXCLUDED.default_tools,
    permission_level = EXCLUDED.permission_level,
    status = EXCLUDED.status,
    guardrails = EXCLUDED.guardrails,
    output_targets = EXCLUDED.output_targets,
    updated_at = now();

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    (
        'jarvis_runtime',
        'runtime',
        'Jarvis',
        'write_with_approval',
        true,
        'Local runtime layer that executes MCP/tool calls, retrieval, and approved write-back for the orchestrator and specialist agents.',
        '{"runtime_root":"/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime"}'::jsonb
    ),
    (
        'client_ledger_reader',
        'mcp_tool_group',
        'Portfolio Manager',
        'read_only',
        true,
        'Read-only client transaction ledger tools over attached broker and historical option-log imports.',
        '{"tools":["ai_os_client_3081282_summary","ai_os_client_3081282_symbol_dates","ai_os_client_3081282_trade_timeline"]}'::jsonb
    ),
    (
        'research_inventory_reader',
        'mcp_tool_group',
        'Librarian Agent',
        'read_only',
        true,
        'Read-only tools over AI-generated research reports, dashboards, models, source audits, and data packs.',
        '{"tools":["ai_os_research_outputs","ai_os_research_output_detail"]}'::jsonb
    ),
    (
        'component_review_reader',
        'mcp_tool_group',
        'Coding Lead Agent',
        'read_only',
        true,
        'Read-only component review tools for external repos and legacy software inventories.',
        '{"tools":["ai_os_fincept_component_review","ai_os_component_inventory"]}'::jsonb
    )
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

CREATE OR REPLACE VIEW agent.v_orchestration_stack AS
SELECT
    agent_name,
    department,
    role_scope,
    default_model_route,
    default_tools,
    permission_level,
    guardrails,
    CASE
        WHEN agent_name = 'Charlie Munger' THEN 'main_orchestrator'
        WHEN agent_name = 'Jarvis' THEN 'runtime_layer'
        ELSE 'specialist_agent'
    END AS stack_role
FROM agent.profiles
WHERE status = 'active'
ORDER BY
    CASE
        WHEN agent_name = 'Charlie Munger' THEN 1
        WHEN agent_name = 'Jarvis' THEN 2
        ELSE 3
    END,
    department,
    agent_name;
