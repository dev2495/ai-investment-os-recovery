BEGIN;

INSERT INTO core.source_systems (
    name, source_type, location, sensitivity, status, notes
) VALUES (
    'Official company investor relations reports',
    'primary_company_filing',
    'company investor-relations and annual-report URLs',
    'public',
    'active',
    'Primary company annual reports collected with retained URL, artifact, page, and extraction lineage.'
)
ON CONFLICT (name) DO UPDATE SET
    source_type=EXCLUDED.source_type,
    location=EXCLUDED.location,
    sensitivity=EXCLUDED.sensitivity,
    status=EXCLUDED.status,
    notes=EXCLUDED.notes;

INSERT INTO sector_intelligence.metric_definitions (
    metric_key, metric_name, metric_family, value_type, unit, frequency,
    aggregation_method, higher_is_better, formula_expression,
    required_inputs, methodology_version, active
) VALUES
    ('reported_revenue','Reported Revenue','financial','numeric','INR million','annual','sum',true,NULL,'["revenue_from_operations"]'::jsonb,'sector-fundamentals-v1',true),
    ('reported_profit_after_tax','Reported Profit After Tax','financial','numeric','INR million','annual','sum',true,NULL,'["profit_after_tax"]'::jsonb,'sector-fundamentals-v1',true),
    ('reported_basic_eps','Reported Basic EPS','financial','numeric','INR/share','annual','median',true,NULL,'["basic_eps"]'::jsonb,'sector-fundamentals-v1',true),
    ('reported_total_assets','Reported Total Assets','financial','numeric','INR million','annual','sum',NULL,NULL,'["total_assets"]'::jsonb,'sector-fundamentals-v1',true),
    ('reported_total_equity','Reported Total Equity','financial','numeric','INR million','annual','sum',true,NULL,'["total_equity"]'::jsonb,'sector-fundamentals-v1',true),
    ('reported_operating_cash_flow','Reported Operating Cash Flow','financial','numeric','INR million','annual','sum',true,NULL,'["operating_cash_flow"]'::jsonb,'sector-fundamentals-v1',true),
    ('reported_trade_receivables','Reported Trade Receivables','financial','numeric','INR million','annual','sum',false,NULL,'["trade_receivables"]'::jsonb,'sector-fundamentals-v1',true),
    ('price_to_earnings','Price To Earnings','valuation','numeric','multiple','daily','median',false,'latest point-in-time close / latest available positive annual basic EPS','["reported_basic_eps","latest_close"]'::jsonb,'sector-fundamentals-v1',true),
    ('net_profit_margin','Net Profit Margin','financial','numeric','percent','annual','ratio_of_sums',true,'100 * sum(profit_after_tax) / sum(revenue)','["reported_profit_after_tax","reported_revenue"]'::jsonb,'sector-fundamentals-v1',true),
    ('return_on_equity','Return On Equity Snapshot','financial','numeric','percent','annual','ratio_of_sums',true,'100 * sum(profit_after_tax) / sum(period_end_equity)','["reported_profit_after_tax","reported_total_equity"]'::jsonb,'sector-fundamentals-v1',true)
ON CONFLICT (metric_key) DO UPDATE SET
    metric_name=EXCLUDED.metric_name,
    metric_family=EXCLUDED.metric_family,
    value_type=EXCLUDED.value_type,
    unit=EXCLUDED.unit,
    frequency=EXCLUDED.frequency,
    aggregation_method=EXCLUDED.aggregation_method,
    higher_is_better=EXCLUDED.higher_is_better,
    formula_expression=EXCLUDED.formula_expression,
    required_inputs=EXCLUDED.required_inputs,
    methodology_version=EXCLUDED.methodology_version,
    active=EXCLUDED.active,
    updated_at=now();

CREATE UNIQUE INDEX IF NOT EXISTS uq_sector_metric_observation_lineage
ON sector_intelligence.metric_observations (
    metric_definition_id,
    coalesce(taxonomy_node_id,0),
    coalesce(symbol_id,0),
    observed_at,
    coalesce(period_end,DATE '0001-01-01'),
    coalesce(calculation_version,''),
    coalesce(input_fingerprint,'')
);

CREATE OR REPLACE VIEW sector_intelligence.v_fundamental_constituent_coverage AS
WITH active_members AS (
    SELECT node.id AS taxonomy_node_id,node.taxonomy_key,node.node_name,
           membership.symbol_id,symbol.symbol,symbol.exchange
    FROM sector_intelligence.taxonomy_nodes node
    JOIN sector_intelligence.instrument_membership_history membership
      ON membership.taxonomy_node_id=node.id
     AND membership.valid_from<=CURRENT_DATE
     AND (membership.valid_to IS NULL OR membership.valid_to>=CURRENT_DATE)
    JOIN trading.symbols symbol ON symbol.id=membership.symbol_id
), latest AS (
    SELECT DISTINCT ON (observation.symbol_id,definition.metric_key)
           observation.symbol_id,definition.metric_key,observation.observed_at,
           observation.value_numeric,observation.source_system_id,
           observation.source_reference,observation.input_fingerprint,
           observation.quality_status
    FROM sector_intelligence.metric_observations observation
    JOIN sector_intelligence.metric_definitions definition
      ON definition.id=observation.metric_definition_id
    WHERE definition.metric_key IN (
        'reported_revenue','reported_profit_after_tax','reported_basic_eps',
        'reported_total_assets','reported_total_equity',
        'reported_operating_cash_flow','reported_trade_receivables',
        'price_to_earnings'
    )
      AND observation.quality_status IN ('observed','validated')
    ORDER BY observation.symbol_id,definition.metric_key,
             observation.observed_at DESC,observation.id DESC
)
SELECT member.taxonomy_node_id,member.taxonomy_key,member.node_name,
       member.symbol_id,member.symbol,member.exchange,
       count(latest.metric_key) FILTER (
           WHERE latest.metric_key IN ('reported_revenue','reported_profit_after_tax','reported_basic_eps')
       ) AS core_fact_count,
       bool_and(latest.source_system_id IS NOT NULL
                AND coalesce(latest.source_reference,'')<>''
                AND coalesce(latest.input_fingerprint,'')<>'')
           FILTER (WHERE latest.metric_key IN ('reported_revenue','reported_profit_after_tax','reported_basic_eps'))
           AS core_lineage_complete,
       max(latest.observed_at) AS latest_fundamental_at,
       max(latest.value_numeric) FILTER (WHERE latest.metric_key='price_to_earnings') AS price_to_earnings,
       max(latest.observed_at) FILTER (WHERE latest.metric_key='price_to_earnings') AS valuation_at
FROM active_members member
LEFT JOIN latest ON latest.symbol_id=member.symbol_id
GROUP BY member.taxonomy_node_id,member.taxonomy_key,member.node_name,
         member.symbol_id,member.symbol,member.exchange;

COMMENT ON VIEW sector_intelligence.v_fundamental_constituent_coverage IS
'Truthful active-constituent coverage. A company is core-covered only when revenue, PAT, and EPS all retain source lineage.';

COMMIT;
