BEGIN;

INSERT INTO core.source_systems (
    name,source_type,location,sensitivity,status,notes
) VALUES (
    'NSE Indices historical valuation data',
    'primary_index_report',
    'https://www.niftyindices.com/reports/historical-data',
    'public',
    'active',
    'Official daily index P/E, P/B, and dividend-yield history. Annual raw responses and hashes are retained on the SSD.'
)
ON CONFLICT (name) DO UPDATE SET
    source_type=EXCLUDED.source_type,
    location=EXCLUDED.location,
    sensitivity=EXCLUDED.sensitivity,
    status=EXCLUDED.status,
    notes=EXCLUDED.notes;

CREATE TABLE IF NOT EXISTS sector_intelligence.index_valuation_history (
    id BIGSERIAL PRIMARY KEY,
    taxonomy_node_id BIGINT NOT NULL REFERENCES sector_intelligence.taxonomy_nodes(id) ON DELETE CASCADE,
    valuation_date DATE NOT NULL,
    price_to_earnings NUMERIC,
    price_to_book NUMERIC,
    dividend_yield_percent NUMERIC,
    source_system_id BIGINT NOT NULL REFERENCES core.source_systems(id) ON DELETE RESTRICT,
    source_reference TEXT NOT NULL,
    source_artifact_path TEXT NOT NULL,
    source_artifact_sha256 TEXT NOT NULL,
    request_number TEXT,
    input_fingerprint TEXT NOT NULL,
    quality_status TEXT NOT NULL DEFAULT 'observed',
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_sector_index_valuation_value CHECK (
        price_to_earnings IS NOT NULL
        OR price_to_book IS NOT NULL
        OR dividend_yield_percent IS NOT NULL
    ),
    CONSTRAINT chk_sector_index_valuation_positive CHECK (
        (price_to_earnings IS NULL OR price_to_earnings>0)
        AND (price_to_book IS NULL OR price_to_book>0)
        AND (dividend_yield_percent IS NULL OR dividend_yield_percent>=0)
    ),
    CONSTRAINT chk_sector_index_valuation_hash CHECK (
        source_artifact_sha256 ~ '^[0-9a-f]{64}$'
        AND input_fingerprint ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT chk_sector_index_valuation_quality CHECK (
        quality_status IN ('observed','validated','rejected')
    ),
    UNIQUE (taxonomy_node_id,valuation_date,source_system_id)
);

CREATE INDEX IF NOT EXISTS idx_sector_index_valuation_history_node_date
ON sector_intelligence.index_valuation_history (
    taxonomy_node_id,valuation_date DESC
);

ALTER TABLE sector_intelligence.research_coverage
    ADD COLUMN IF NOT EXISTS dossier_sections JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS source_cutoff_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS dossier_fingerprint TEXT;

ALTER TABLE sector_intelligence.sector_committee_packets
    ADD COLUMN IF NOT EXISTS packet_fingerprint TEXT;

CREATE OR REPLACE VIEW sector_intelligence.v_sector_underwrite_control AS
WITH latest_coverage AS (
    SELECT DISTINCT ON (coverage.taxonomy_node_id)
           coverage.*
    FROM sector_intelligence.research_coverage coverage
    ORDER BY coverage.taxonomy_node_id,coverage.version DESC,coverage.updated_at DESC
), latest_packet AS (
    SELECT DISTINCT ON (packet.taxonomy_node_id)
           packet.*
    FROM sector_intelligence.sector_committee_packets packet
    ORDER BY packet.taxonomy_node_id,packet.as_of_date DESC,packet.updated_at DESC
), valuation AS (
    SELECT history.taxonomy_node_id,
           count(*) FILTER (WHERE history.price_to_earnings IS NOT NULL) AS pe_observation_count,
           min(history.valuation_date) FILTER (WHERE history.price_to_earnings IS NOT NULL) AS earliest_pe_date,
           max(history.valuation_date) FILTER (WHERE history.price_to_earnings IS NOT NULL) AS latest_pe_date,
           max(history.ingested_at) AS latest_ingested_at
    FROM sector_intelligence.index_valuation_history history
    WHERE history.quality_status IN ('observed','validated')
    GROUP BY history.taxonomy_node_id
)
SELECT node.id AS taxonomy_node_id,node.taxonomy_key,node.node_name,
       coverage.id AS coverage_id,coverage.coverage_status,coverage.owner_agent,
       coverage.version AS dossier_version,coverage.last_reviewed_at,
       coverage.next_review_due_at,coverage.thesis_summary,
       coverage.evidence_references,coverage.data_gaps,coverage.monitoring_indicators,
       coverage.dossier_sections,coverage.source_cutoff_at,coverage.dossier_fingerprint,
       packet.id AS committee_packet_id,packet.packet_key,packet.packet_type,
       packet.as_of_date AS packet_as_of_date,packet.decision_question,
       packet.proposed_action,packet.independent_positions,packet.dissent_summary,
       packet.risk_challenges,packet.status AS committee_status,
       packet.human_final_required,packet.capital_action_allowed,packet.packet_fingerprint,
       coalesce(valuation.pe_observation_count,0) AS pe_observation_count,
       valuation.earliest_pe_date,valuation.latest_pe_date,valuation.latest_ingested_at
FROM sector_intelligence.taxonomy_nodes node
LEFT JOIN latest_coverage coverage ON coverage.taxonomy_node_id=node.id
LEFT JOIN latest_packet packet ON packet.taxonomy_node_id=node.id
LEFT JOIN valuation ON valuation.taxonomy_node_id=node.id;

CREATE OR REPLACE FUNCTION sector_intelligence.run_acceptance_gates_v4(
    p_run_key TEXT,
    p_taxonomy_node_id BIGINT,
    p_as_of_date DATE,
    p_started_by TEXT DEFAULT 'Sector Portfolio Manager'
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_v3_id BIGINT;
    v_run_id BIGINT;
    v_history_count INTEGER;
    v_history_start DATE;
    v_history_end DATE;
    v_band_count INTEGER;
    v_dossier_count INTEGER;
    v_committee_count INTEGER;
    v_portfolio_fit_count INTEGER;
BEGIN
    v_v3_id := sector_intelligence.run_acceptance_gates_v3(
        p_run_key || '-v3-baseline',
        p_taxonomy_node_id,
        p_as_of_date,
        p_started_by
    );

    INSERT INTO sector_intelligence.acceptance_runs (
        run_key,taxonomy_node_id,as_of_date,status,gate_version,started_by
    ) VALUES (
        p_run_key,p_taxonomy_node_id,p_as_of_date,'running','sector-acceptance-v4',p_started_by
    )
    ON CONFLICT (taxonomy_node_id,as_of_date,gate_version) DO UPDATE SET
        run_key=EXCLUDED.run_key,status='running',started_by=EXCLUDED.started_by,
        summary='{}'::jsonb,started_at=now(),finished_at=NULL
    RETURNING id INTO v_run_id;

    DELETE FROM sector_intelligence.acceptance_gate_results
    WHERE acceptance_run_id=v_run_id;

    INSERT INTO sector_intelligence.acceptance_gate_results (
        acceptance_run_id,gate_key,gate_name,status,observed_value,
        threshold_value,comparator,evidence,failure_reason,checked_by
    )
    SELECT v_run_id,result.gate_key,result.gate_name,result.status,
           result.observed_value,result.threshold_value,result.comparator,
           result.evidence,result.failure_reason,result.checked_by
    FROM sector_intelligence.acceptance_gate_results result
    WHERE result.acceptance_run_id=v_v3_id
      AND result.gate_key NOT IN (
          'sector_dossier','committee_dissent','portfolio_fit','ten_year_valuation_history'
      );

    SELECT count(*)::int,min(history.valuation_date),max(history.valuation_date)
    INTO v_history_count,v_history_start,v_history_end
    FROM sector_intelligence.index_valuation_history history
    WHERE history.taxonomy_node_id=p_taxonomy_node_id
      AND history.valuation_date<=p_as_of_date
      AND history.valuation_date>=p_as_of_date-INTERVAL '10 years'
      AND history.price_to_earnings>0
      AND history.source_system_id IS NOT NULL
      AND coalesce(history.source_reference,'')<>''
      AND coalesce(history.source_artifact_path,'')<>''
      AND history.source_artifact_sha256 ~ '^[0-9a-f]{64}$'
      AND history.input_fingerprint ~ '^[0-9a-f]{64}$'
      AND history.quality_status IN ('observed','validated');

    SELECT count(*)::int INTO v_band_count
    FROM sector_intelligence.valuation_bands band
    JOIN sector_intelligence.metric_definitions definition
      ON definition.id=band.metric_definition_id
    WHERE band.taxonomy_node_id=p_taxonomy_node_id
      AND band.as_of_date=p_as_of_date
      AND definition.metric_key='price_to_earnings'
      AND band.lookback_years>=10
      AND band.observation_count=v_history_count
      AND band.minimum_value IS NOT NULL
      AND band.median_value IS NOT NULL
      AND band.maximum_value IS NOT NULL
      AND coalesce(band.input_fingerprint,'')<>'';

    SELECT count(*)::int INTO v_dossier_count
    FROM sector_intelligence.research_coverage coverage
    WHERE coverage.taxonomy_node_id=p_taxonomy_node_id
      AND coverage.version=(
          SELECT max(latest.version)
          FROM sector_intelligence.research_coverage latest
          WHERE latest.taxonomy_node_id=p_taxonomy_node_id
      )
      AND coverage.coverage_status IN ('active','monitoring','review_due')
      AND coverage.last_reviewed_at::date<=p_as_of_date
      AND coverage.source_cutoff_at::date<=p_as_of_date
      AND coalesce(coverage.thesis_summary,'')<>''
      AND jsonb_typeof(coverage.evidence_references)='array'
      AND jsonb_array_length(coverage.evidence_references)>=3
      AND jsonb_typeof(coverage.monitoring_indicators)='array'
      AND jsonb_array_length(coverage.monitoring_indicators)>=3
      AND jsonb_typeof(coverage.dossier_sections)='object'
      AND coverage.dossier_sections ?& ARRAY[
          'executive_conclusion','industry_structure','business_models',
          'constituent_fundamentals','valuation','market_structure',
          'ownership_and_flows','macro_sensitivities','portfolio_fit',
          'opportunity_cost','bull_case','base_case','bear_case',
          'monitoring','evidence_gaps'
      ]
      AND coalesce(coverage.dossier_fingerprint,'')<>'';

    SELECT count(*)::int INTO v_committee_count
    FROM sector_intelligence.sector_committee_packets packet
    WHERE packet.taxonomy_node_id=p_taxonomy_node_id
      AND packet.as_of_date<=p_as_of_date
      AND packet.status IN ('ready','decided')
      AND jsonb_typeof(packet.independent_positions)='array'
      AND jsonb_array_length(packet.independent_positions)>=5
      AND coalesce(packet.dissent_summary,'')<>''
      AND jsonb_typeof(packet.risk_challenges)='array'
      AND jsonb_array_length(packet.risk_challenges)>=1
      AND packet.human_final_required=true
      AND packet.capital_action_allowed=false
      AND coalesce(packet.packet_fingerprint,'')<>'';

    SELECT count(*)::int INTO v_portfolio_fit_count
    FROM sector_intelligence.sector_committee_packets packet
    WHERE packet.taxonomy_node_id=p_taxonomy_node_id
      AND packet.as_of_date<=p_as_of_date
      AND jsonb_typeof(packet.evidence_snapshot->'portfolio_fit')='object'
      AND jsonb_typeof(packet.evidence_snapshot->'opportunity_cost')='object'
      AND packet.evidence_snapshot->'portfolio_fit' ?& ARRAY['status','conclusion','evidence']
      AND packet.evidence_snapshot->'opportunity_cost' ?& ARRAY['status','conclusion','evidence']
      AND jsonb_typeof(packet.evidence_snapshot->'portfolio_fit'->'evidence')='array'
      AND jsonb_array_length(packet.evidence_snapshot->'portfolio_fit'->'evidence')>=1
      AND jsonb_typeof(packet.evidence_snapshot->'opportunity_cost'->'evidence')='array'
      AND jsonb_array_length(packet.evidence_snapshot->'opportunity_cost'->'evidence')>=1;

    INSERT INTO sector_intelligence.acceptance_gate_results (
        acceptance_run_id,gate_key,gate_name,status,observed_value,
        threshold_value,comparator,evidence,failure_reason,checked_by
    ) VALUES
    (
        v_run_id,'ten_year_valuation_history','Ten-Year Valuation History',
        CASE WHEN v_history_count>=2000
                  AND v_history_start<=p_as_of_date-INTERVAL '10 years'+INTERVAL '7 days'
                  AND v_band_count>=1
             THEN 'passed' ELSE 'blocked' END,
        v_history_count,2000,'gte',
        jsonb_build_object(
            'point_in_time_observations',v_history_count,
            'earliest_date',v_history_start,
            'latest_date',v_history_end,
            'reconciled_band_count',v_band_count,
            'raw_artifact_and_hash_required',true,
            'backdating_allowed',false
        ),
        CASE WHEN v_history_count>=2000
                  AND v_history_start<=p_as_of_date-INTERVAL '10 years'+INTERVAL '7 days'
                  AND v_band_count>=1
             THEN NULL
             ELSE format('Requires at least 2,000 source-backed daily P/E rows spanning ten years and a reconciled band; found %s rows from %s to %s and %s bands',
                         v_history_count,v_history_start,v_history_end,v_band_count) END,
        'Sector Valuation Analyst'
    ),
    (
        v_run_id,'sector_dossier','Versioned Sector Research Dossier',
        CASE WHEN v_dossier_count>=1 THEN 'passed' ELSE 'blocked' END,
        v_dossier_count,1,'gte',
        jsonb_build_object(
            'required_sections',15,
            'minimum_evidence_references',3,
            'minimum_monitoring_indicators',3,
            'point_in_time_source_cutoff_required',true
        ),
        CASE WHEN v_dossier_count>=1 THEN NULL
             ELSE 'No complete versioned 15-section sector dossier with source cutoff, monitoring indicators, evidence gaps, and fingerprint is available' END,
        'Sector Fundamental Analyst'
    ),
    (
        v_run_id,'committee_dissent','Sector Committee And Dissent',
        CASE WHEN v_committee_count>=1 THEN 'passed' ELSE 'blocked' END,
        v_committee_count,1,'gte',
        jsonb_build_object(
            'minimum_independent_positions',5,
            'dissent_required',true,
            'risk_challenge_required',true,
            'human_final_required',true,
            'capital_action_allowed',false
        ),
        CASE WHEN v_committee_count>=1 THEN NULL
             ELSE 'No ready committee packet has five independent positions, explicit dissent, risk challenge, fingerprint, and human-final control' END,
        'Sector Portfolio Manager'
    ),
    (
        v_run_id,'portfolio_fit','Portfolio Fit And Opportunity Cost',
        CASE WHEN v_portfolio_fit_count>=1 THEN 'passed' ELSE 'blocked' END,
        v_portfolio_fit_count,1,'gte',
        jsonb_build_object(
            'portfolio_fit_evidence_required',true,
            'opportunity_cost_evidence_required',true,
            'capital_action_allowed',false
        ),
        CASE WHEN v_portfolio_fit_count>=1 THEN NULL
             ELSE 'No committee packet contains structured portfolio-fit and opportunity-cost conclusions with evidence arrays' END,
        'Portfolio Fit Agent'
    );

    UPDATE sector_intelligence.acceptance_runs run
    SET status=CASE WHEN EXISTS (
            SELECT 1 FROM sector_intelligence.acceptance_gate_results result
            WHERE result.acceptance_run_id=v_run_id
              AND result.status IN ('failed','blocked')
        ) THEN 'blocked' ELSE 'passed' END,
        summary=(
            SELECT jsonb_build_object(
                'gate_count',count(*),
                'passed_count',count(*) FILTER (WHERE status='passed'),
                'failed_count',count(*) FILTER (WHERE status='failed'),
                'blocked_count',count(*) FILTER (WHERE status='blocked'),
                'valuation_history_count',v_history_count,
                'valuation_history_start',v_history_start,
                'valuation_history_end',v_history_end,
                'dossier_ready',v_dossier_count>=1,
                'committee_ready',v_committee_count>=1,
                'portfolio_fit_ready',v_portfolio_fit_count>=1,
                'broker_write_allowed',false,
                'capital_action_allowed',false
            )
            FROM sector_intelligence.acceptance_gate_results
            WHERE acceptance_run_id=v_run_id
        ),
        finished_at=now()
    WHERE run.id=v_run_id;

    RETURN v_run_id;
END;
$$;

COMMENT ON FUNCTION sector_intelligence.run_acceptance_gates_v4(TEXT,BIGINT,DATE,TEXT) IS
'Institutional sector acceptance requiring stored ten-year daily valuation history, a complete versioned dossier, five independent committee positions with dissent, and evidence-based portfolio fit. No capital or broker authority.';

INSERT INTO agent.tool_registry (
    tool_name,tool_type,owning_agent,permission_level,enabled,description,config
) VALUES (
    'ai_os_build_sector_underwrite',
    'mcp_tool',
    'Sector Portfolio Manager',
    'write_db_manual_only',
    true,
    'Collect official NSE Indices valuation history, build a source-backed sector dossier, and open a human-final committee packet.',
    '{"script":"_ai_os_runtime/scripts/build_sector_underwrite.py","writes":["sector_intelligence.index_valuation_history","sector_intelligence.valuation_bands","sector_intelligence.research_coverage","sector_intelligence.sector_committee_packets"],"broker_write_allowed":false,"capital_action_allowed":false,"seed_data_allowed":false}'::jsonb
)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type=EXCLUDED.tool_type,
    owning_agent=EXCLUDED.owning_agent,
    permission_level=EXCLUDED.permission_level,
    enabled=EXCLUDED.enabled,
    description=EXCLUDED.description,
    config=EXCLUDED.config;

COMMIT;
