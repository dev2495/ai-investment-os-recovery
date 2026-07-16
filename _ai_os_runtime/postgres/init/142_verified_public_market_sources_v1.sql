BEGIN;

CREATE TABLE IF NOT EXISTS market.macro_observations (
    id BIGSERIAL PRIMARY KEY,
    source_key TEXT NOT NULL REFERENCES core.data_source_registry(source_key),
    series_key TEXT NOT NULL,
    series_name TEXT NOT NULL,
    geography TEXT NOT NULL,
    observation_date DATE NOT NULL,
    observation_value NUMERIC,
    unit TEXT,
    frequency TEXT,
    source_url TEXT NOT NULL,
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    retrieved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(source_key,series_key,geography,observation_date)
);

CREATE INDEX IF NOT EXISTS idx_macro_observations_series_date
ON market.macro_observations(series_key,geography,observation_date DESC);

INSERT INTO core.data_source_registry (
    source_key,source_name,source_type,provider,connection_mode,status,
    freshness_target_minutes,owner_agent,sensitivity,notes,metadata
)
VALUES
    ('sec_edgar','SEC EDGAR submissions and XBRL','regulatory_filings_api','SEC','official_json_api','active',1440,'Filings Analyst','public',
     'Official SEC submissions and company-facts APIs; compliant User-Agent and source URL required.',
     '{"location":"https://data.sec.gov","authentication":"none","official":true,"bulk_archives":true,"license_review":"SEC automated access policy"}'::jsonb),
    ('world_bank_macro','World Bank Open Data indicators','macro_api','World Bank','official_json_api','active',1440,'Macro Researcher','public',
     'Official World Bank indicator API used for slow-moving macro series.',
     '{"location":"https://api.worldbank.org/v2","authentication":"none","official":true,"format":"json"}'::jsonb),
    ('ecb_data_api','ECB Data Portal exchange rates','macro_market_api','European Central Bank','official_csv_api','active',1440,'Macro Researcher','public',
     'Official ECB Data Portal API used for reference FX observations.',
     '{"location":"https://data-api.ecb.europa.eu/service/data","authentication":"none","official":true,"format":"csvdata"}'::jsonb),
    ('fred_macro','FRED and ALFRED macro data','macro_api','Federal Reserve Bank of St. Louis','official_json_api','planned',1440,'Macro Researcher','public',
     'High-value macro source registered but blocked until a secret reference for the required API key is configured.',
     '{"location":"https://api.stlouisfed.org/fred","authentication":"api_key_required","official":true,"secret_ref_only":true}'::jsonb),
    ('gdelt_news','GDELT global event and news index','news_api','GDELT','public_json_api','planned',60,'Alternative Data Analyst','public',
     'Registered as an optional source. Activation remains blocked until rate-limit behavior and usage policy are accepted.',
     '{"location":"https://api.gdeltproject.org/api/v2/doc/doc","authentication":"none","latest_check":"http_429","activation_required":true}'::jsonb)
ON CONFLICT (source_key) DO UPDATE SET
    source_name=EXCLUDED.source_name,source_type=EXCLUDED.source_type,provider=EXCLUDED.provider,
    connection_mode=EXCLUDED.connection_mode,status=EXCLUDED.status,
    freshness_target_minutes=EXCLUDED.freshness_target_minutes,owner_agent=EXCLUDED.owner_agent,
    sensitivity=EXCLUDED.sensitivity,notes=EXCLUDED.notes,
    metadata=core.data_source_registry.metadata || EXCLUDED.metadata,updated_at=now();

INSERT INTO core.source_connector_profiles (
    connector_key,connector_name,source_key,connector_type,provider,access_mode,status,
    freshness_target_minutes,requires_api_key,requires_browser_session,base_url,
    owner_agent,sensitivity,health_status,last_error,notes,config
)
VALUES
    ('sec_edgar_connector','SEC EDGAR official API connector','sec_edgar','official_json_api','SEC','read_only','configured',1440,false,false,'https://data.sec.gov','Filings Analyst','public','unchecked',NULL,
     'Read-only public filings and XBRL connector.',
     '{"user_agent_required":true,"endpoints":["submissions","companyfacts"],"bulk_preferred_for_large_jobs":true}'::jsonb),
    ('world_bank_macro_connector','World Bank macro connector','world_bank_macro','official_json_api','World Bank','read_only','configured',1440,false,false,'https://api.worldbank.org/v2','Macro Researcher','public','unchecked',NULL,
     'Read-only public macro indicator connector.',
     '{"countries":["IND","USA"],"series":["NY.GDP.MKTP.CD","NY.GDP.MKTP.KD.ZG","FP.CPI.TOTL.ZG"]}'::jsonb),
    ('ecb_data_api_connector','ECB Data Portal connector','ecb_data_api','official_csv_api','European Central Bank','read_only','configured',1440,false,false,'https://data-api.ecb.europa.eu/service/data','Macro Researcher','public','unchecked',NULL,
     'Read-only ECB reference FX connector.',
     '{"series":["EXR/D.USD.EUR.SP00.A","EXR/D.GBP.EUR.SP00.A","EXR/D.JPY.EUR.SP00.A"]}'::jsonb),
    ('fred_macro_connector','FRED macro connector','fred_macro','official_json_api','Federal Reserve Bank of St. Louis','read_only','planned',1440,true,false,'https://api.stlouisfed.org/fred','Macro Researcher','public','needs_secret','FRED requires a registered API key reference.',
     'Configured only after an API key secret reference is supplied.',
     '{"secret_ref_only":true,"alfred_point_in_time_preferred":true}'::jsonb),
    ('gdelt_news_connector','GDELT news connector','gdelt_news','public_json_api','GDELT','read_only','planned',60,false,false,'https://api.gdeltproject.org/api/v2/doc/doc','Alternative Data Analyst','public','needs_activation','Public endpoint returned HTTP 429 during verification.',
     'Do not schedule until bounded backoff and usage policy are approved.',
     '{"rate_limit_backoff_required":true,"activation_required":true}'::jsonb)
ON CONFLICT (connector_key) DO UPDATE SET
    connector_name=EXCLUDED.connector_name,source_key=EXCLUDED.source_key,
    connector_type=EXCLUDED.connector_type,provider=EXCLUDED.provider,
    access_mode=EXCLUDED.access_mode,status=EXCLUDED.status,
    freshness_target_minutes=EXCLUDED.freshness_target_minutes,
    requires_api_key=EXCLUDED.requires_api_key,requires_browser_session=EXCLUDED.requires_browser_session,
    base_url=EXCLUDED.base_url,owner_agent=EXCLUDED.owner_agent,sensitivity=EXCLUDED.sensitivity,
    notes=EXCLUDED.notes,config=EXCLUDED.config,updated_at=now();

CREATE OR REPLACE VIEW market.v_macro_observations AS
SELECT observation.id,observation.source_key,source.source_name,source.provider,
       observation.series_key,observation.series_name,observation.geography,
       observation.observation_date,observation.observation_value,
       observation.unit,observation.frequency,observation.source_url,
       observation.retrieved_at,observation.raw_payload
FROM market.macro_observations observation
JOIN core.data_source_registry source USING(source_key)
ORDER BY observation.observation_date DESC,observation.series_key,observation.geography;

CREATE OR REPLACE VIEW market.v_macro_source_readiness AS
SELECT source.source_key,source.source_name,source.provider,source.status,
       connector.health_status,connector.last_checked_at,connector.last_rows_seen,connector.last_error,
       count(observation.id)::BIGINT AS observation_count,
       count(DISTINCT observation.series_key)::BIGINT AS series_count,
       max(observation.observation_date) AS latest_observation_date,
       CASE
           WHEN source.status<>'active' THEN 'gated'
           WHEN connector.health_status IN ('configured','active','healthy') AND count(observation.id)>0 THEN 'ready'
           WHEN connector.health_status IN ('configured','active','healthy') THEN 'connected_empty'
           ELSE 'degraded'
       END AS readiness_status
FROM core.data_source_registry source
JOIN core.source_connector_profiles connector USING(source_key)
LEFT JOIN market.macro_observations observation USING(source_key)
WHERE source.source_key IN ('world_bank_macro','ecb_data_api','fred_macro')
GROUP BY source.source_key,source.source_name,source.provider,source.status,
         connector.health_status,connector.last_checked_at,connector.last_rows_seen,connector.last_error;

INSERT INTO agent.tool_registry (tool_name,tool_type,owning_agent,permission_level,enabled,description,config)
VALUES
    ('ai_os_ingest_public_macro_data','mcp_tool','Macro Researcher','write_db_scheduled',true,
     'Fetch verified World Bank and ECB public observations, upsert them with source lineage, and store connector health evidence.',
     '{"script":"_ai_os_runtime/scripts/ingest_public_macro_data.py","reads":["World Bank API","ECB Data Portal API"],"writes":["market.macro_observations","core.connector_health_checks","core.data_source_checks"],"seed_data_allowed":false,"live_execution_allowed":false}'::jsonb),
    ('ai_os_macro_source_readiness','mcp_tool','Macro Researcher','read_only',true,
     'Read public macro observations and connector readiness, including credential-gated sources.',
     '{"reads":["market.v_macro_observations","market.v_macro_source_readiness"],"source_required":true}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    owning_agent=EXCLUDED.owning_agent,permission_level=EXCLUDED.permission_level,
    enabled=EXCLUDED.enabled,description=EXCLUDED.description,config=EXCLUDED.config;

COMMIT;
