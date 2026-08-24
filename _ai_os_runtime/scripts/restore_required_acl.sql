\set ON_ERROR_STOP on

-- pg_restore runs with --no-privileges so no ACL from the globals or archive
-- is trusted. Rebuild only the reviewed Research Desk v1 runtime contract.
BEGIN;

DO $role_guard$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'ai_os_research_runtime'
          AND NOT rolcanlogin
          AND NOT rolsuper
          AND NOT rolcreatedb
          AND NOT rolcreaterole
          AND NOT rolinherit
          AND NOT rolreplication
          AND NOT rolbypassrls
    ) THEN
        RAISE EXCEPTION 'safe ai_os_research_runtime role is required before ACL restore';
    END IF;
END
$role_guard$;

REVOKE ALL ON SCHEMA core, knowledge, research, market, agent, trading
FROM ai_os_research_runtime;
GRANT USAGE ON SCHEMA core, knowledge, research, market, agent, trading
TO ai_os_research_runtime;
REVOKE ALL ON SCHEMA portfolio FROM ai_os_research_runtime;

REVOKE ALL ON FUNCTION
    knowledge.enforce_unresolved_link_scope(),
    research.validate_source_item_claim_promotion(),
    market.validate_scanner_version_publication(),
    market.validate_scanner_schedule_gate(),
    market.validate_scanner_universe_point_in_time(),
    market.validate_scanner_metric_input_cutoff()
FROM PUBLIC, ai_os_research_runtime;
GRANT EXECUTE ON FUNCTION
    knowledge.enforce_unresolved_link_scope(),
    research.validate_source_item_claim_promotion(),
    market.validate_scanner_version_publication(),
    market.validate_scanner_schedule_gate(),
    market.validate_scanner_universe_point_in_time(),
    market.validate_scanner_metric_input_cutoff()
TO ai_os_research_runtime;
REVOKE ALL ON FUNCTION core.ai_os_scope_key() FROM ai_os_research_runtime;
GRANT EXECUTE ON FUNCTION core.ai_os_scope_key() TO ai_os_research_runtime;

REVOKE ALL ON TABLE
    knowledge.index_runs,
    knowledge.graph_nodes,
    knowledge.graph_edges,
    knowledge.unresolved_links
FROM PUBLIC, ai_os_research_runtime;
GRANT SELECT, INSERT, UPDATE ON TABLE
    knowledge.index_runs,
    knowledge.graph_nodes,
    knowledge.graph_edges,
    knowledge.unresolved_links
TO ai_os_research_runtime;

REVOKE ALL ON TABLE
    research.followed_sources,
    research.followed_source_versions,
    research.people_or_authors,
    research.person_source_profiles,
    research.followed_source_items,
    research.source_item_entities,
    research.source_item_claims,
    research.source_scorecards,
    research.idea_cards,
    research.idea_card_evidence,
    research.idea_triage,
    research.followed_source_refresh_runs
FROM PUBLIC, ai_os_research_runtime;
GRANT SELECT, INSERT, UPDATE ON TABLE
    research.followed_sources,
    research.followed_source_versions,
    research.people_or_authors,
    research.person_source_profiles,
    research.followed_source_items,
    research.source_item_entities,
    research.source_item_claims,
    research.source_scorecards,
    research.idea_cards,
    research.idea_card_evidence,
    research.idea_triage,
    research.followed_source_refresh_runs
TO ai_os_research_runtime;

REVOKE ALL ON TABLE
    market.scanner_definitions,
    market.scanner_metric_definitions,
    market.scanner_versions,
    market.scanner_validations,
    market.scanner_schedules,
    market.scanner_runs,
    market.scanner_run_universe,
    market.scanner_results,
    market.scanner_result_metrics,
    market.scanner_result_metric_inputs,
    market.scanner_alerts
FROM PUBLIC, ai_os_research_runtime;
GRANT SELECT, INSERT, UPDATE ON TABLE
    market.scanner_definitions,
    market.scanner_metric_definitions,
    market.scanner_versions,
    market.scanner_validations,
    market.scanner_schedules,
    market.scanner_runs,
    market.scanner_run_universe,
    market.scanner_results,
    market.scanner_result_metrics,
    market.scanner_result_metric_inputs,
    market.scanner_alerts
TO ai_os_research_runtime;

REVOKE ALL ON SEQUENCE
    knowledge.index_runs_id_seq,
    knowledge.graph_nodes_id_seq,
    knowledge.graph_edges_id_seq,
    knowledge.unresolved_links_id_seq,
    research.followed_sources_id_seq,
    research.followed_source_versions_id_seq,
    research.people_or_authors_id_seq,
    research.person_source_profiles_id_seq,
    research.followed_source_items_id_seq,
    research.source_item_entities_id_seq,
    research.source_item_claims_id_seq,
    research.source_scorecards_id_seq,
    research.idea_cards_id_seq,
    research.idea_card_evidence_id_seq,
    research.idea_triage_id_seq,
    research.followed_source_refresh_runs_id_seq,
    market.scanner_definitions_id_seq,
    market.scanner_metric_definitions_id_seq,
    market.scanner_versions_id_seq,
    market.scanner_validations_id_seq,
    market.scanner_schedules_id_seq,
    market.scanner_runs_id_seq,
    market.scanner_run_universe_id_seq,
    market.scanner_results_id_seq,
    market.scanner_result_metrics_id_seq,
    market.scanner_result_metric_inputs_id_seq,
    market.scanner_alerts_id_seq
FROM ai_os_research_runtime;
GRANT USAGE, SELECT ON SEQUENCE
    knowledge.index_runs_id_seq,
    knowledge.graph_nodes_id_seq,
    knowledge.graph_edges_id_seq,
    knowledge.unresolved_links_id_seq,
    research.followed_sources_id_seq,
    research.followed_source_versions_id_seq,
    research.people_or_authors_id_seq,
    research.person_source_profiles_id_seq,
    research.followed_source_items_id_seq,
    research.source_item_entities_id_seq,
    research.source_item_claims_id_seq,
    research.source_scorecards_id_seq,
    research.idea_cards_id_seq,
    research.idea_card_evidence_id_seq,
    research.idea_triage_id_seq,
    research.followed_source_refresh_runs_id_seq,
    market.scanner_definitions_id_seq,
    market.scanner_metric_definitions_id_seq,
    market.scanner_versions_id_seq,
    market.scanner_validations_id_seq,
    market.scanner_schedules_id_seq,
    market.scanner_runs_id_seq,
    market.scanner_run_universe_id_seq,
    market.scanner_results_id_seq,
    market.scanner_result_metrics_id_seq,
    market.scanner_result_metric_inputs_id_seq,
    market.scanner_alerts_id_seq
TO ai_os_research_runtime;

REVOKE ALL ON TABLE
    knowledge.v_note_entity_links,
    knowledge.v_note_case_links,
    knowledge.v_note_evidence_links,
    research.v_following_feed,
    research.v_idea_inbox,
    research.v_followed_source_refresh_status
FROM ai_os_research_runtime;
GRANT SELECT ON TABLE
    knowledge.v_note_entity_links,
    knowledge.v_note_case_links,
    knowledge.v_note_evidence_links,
    research.v_following_feed,
    research.v_idea_inbox,
    research.v_followed_source_refresh_status
TO ai_os_research_runtime;

REVOKE ALL ON TABLE
    agent.approvals,
    market.universe_memberships,
    research.companies,
    research.company_statement_facts,
    research.corporate_filings,
    research.financial_formula_definitions,
    research.financial_ratio_inputs,
    research.financial_ratio_results,
    research.statement_fact_definitions,
    trading.symbols
FROM ai_os_research_runtime;
GRANT SELECT ON TABLE
    agent.approvals,
    market.universe_memberships,
    research.companies,
    research.company_statement_facts,
    research.corporate_filings,
    research.financial_formula_definitions,
    research.financial_ratio_inputs,
    research.financial_ratio_results,
    research.statement_fact_definitions,
    trading.symbols
TO ai_os_research_runtime;

REVOKE ALL ON TABLE trading.order_intents FROM ai_os_research_runtime;

DO $least_privilege_guard$
BEGIN
    IF NOT has_table_privilege('ai_os_research_runtime', 'knowledge.graph_nodes', 'SELECT,INSERT,UPDATE')
       OR NOT has_table_privilege('ai_os_research_runtime', 'research.followed_sources', 'SELECT,INSERT,UPDATE')
       OR NOT has_table_privilege('ai_os_research_runtime', 'market.scanner_runs', 'SELECT,INSERT,UPDATE')
       OR NOT has_table_privilege('ai_os_research_runtime', 'research.companies', 'SELECT')
    THEN
        RAISE EXCEPTION 'Research Desk restore ACL is incomplete';
    END IF;

    IF has_table_privilege('ai_os_research_runtime', 'knowledge.graph_nodes', 'DELETE')
       OR has_table_privilege('ai_os_research_runtime', 'research.companies', 'INSERT')
       OR has_schema_privilege('ai_os_research_runtime', 'portfolio', 'USAGE')
       OR has_table_privilege('ai_os_research_runtime', 'trading.order_intents', 'SELECT')
       OR has_table_privilege('ai_os_research_runtime', 'trading.order_intents', 'INSERT')
    THEN
        RAISE EXCEPTION 'Research Desk restore ACL escaped its least-privilege boundary';
    END IF;
END
$least_privilege_guard$;

COMMIT;
