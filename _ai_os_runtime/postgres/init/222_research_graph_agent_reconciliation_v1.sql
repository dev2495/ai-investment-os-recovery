BEGIN;

WITH active_research_graph AS (
    SELECT version.id AS graph_version_id
    FROM agent.graph_definitions definition
    JOIN agent.graph_versions version
      ON version.graph_key=definition.graph_key
     AND version.version=definition.active_version
    WHERE definition.graph_key='research_to_investment_decision'
      AND definition.status='active'
      AND version.status='active'
)
UPDATE agent.graph_nodes node
SET owner_agent=CASE node.node_key
    WHEN 'bear_case' THEN 'Bear Case Agent'
    WHEN 'valuation' THEN 'Valuation Agent'
    ELSE node.owner_agent
END
FROM active_research_graph graph
WHERE node.graph_version_id=graph.graph_version_id
  AND (
      (node.node_key='bear_case' AND node.owner_agent<>'Bear Case Agent')
      OR (node.node_key='valuation' AND node.owner_agent<>'Valuation Agent')
  );

DO $$
DECLARE
    missing_count INTEGER;
BEGIN
    SELECT count(*)::INTEGER INTO missing_count
    FROM agent.graph_nodes node
    JOIN agent.graph_versions version ON version.id=node.graph_version_id
    JOIN agent.graph_definitions definition
      ON definition.graph_key=version.graph_key
     AND definition.active_version=version.version
    LEFT JOIN agent.profiles profile
      ON profile.agent_name=node.owner_agent AND profile.status='active'
    WHERE definition.graph_key='research_to_investment_decision'
      AND node.node_type IN ('agent_task','committee','approval_gate')
      AND profile.agent_name IS NULL;
    IF missing_count <> 0 THEN
        RAISE EXCEPTION 'research graph still references % unavailable active agent owners',missing_count;
    END IF;
END;
$$;

COMMIT;
