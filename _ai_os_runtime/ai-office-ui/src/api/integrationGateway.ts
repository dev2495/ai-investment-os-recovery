import type {
  LiveRow,
  RegisterModelEndpointInput,
  RegisterSourceConnectorInput,
  RunProviderReadinessSweepInput
} from "./live";

export interface IntegrationGatewaySnapshot {
  generated_at: string;
  runtime_root: string;
  vault_root: string;
  data_mode: {
    seed_data_allowed: boolean;
    raw_secrets_allowed: boolean;
    arbitrary_commands_allowed: boolean;
    source: string;
  };
  payload_profile: { query_count: number; row_count: number };
  summary: LiveRow[];
  plugins: LiveRow[];
  schema_mappings: LiveRow[];
  jobs: LiveRow[];
  model_routes: LiveRow[];
  provider_readiness: LiveRow[];
  execution_control: LiveRow[];
  market_data_readiness: LiveRow[];
  market_data_contracts: LiveRow[];
  market_data_imports: LiveRow[];
  market_data_quality: LiveRow[];
  market_bias_readiness: LiveRow[];
}

export interface UpsertSchemaMappingInput {
  mapping_key?: string;
  plugin_key: string;
  dataset_key: string;
  target_relation: string;
  source_schema?: Record<string, unknown>;
  field_mappings: Record<string, unknown>;
  transformations?: unknown[];
  primary_key_fields: string[];
  timestamp_field?: string;
  schema_version?: string;
  status?: string;
  owner_agent?: string;
  notes?: string;
  actor?: string;
}

export interface UpsertIntegrationJobInput {
  job_key?: string;
  plugin_key: string;
  job_name: string;
  job_type: "poll" | "import" | "stream" | "aggregate" | "health_check" | "provider_probe";
  executor_key: "market_news_ingestion" | "filings_collection" | "tick_ohlcv_aggregation" | "tradingview_quote_refresh" | "public_source_check" | "provider_readiness" | "legacy_market_data_ingestion";
  schedule_cron?: string;
  enabled?: boolean;
  run_mode?: "manual" | "schedule" | "manual_or_schedule" | "daemon";
  timeout_seconds?: number;
  parameters?: Record<string, unknown>;
  approval_required?: boolean;
  owner_agent?: string;
  notes?: string;
  actor?: string;
}

const API_URL = (import.meta.env.VITE_AI_OS_API_URL || "http://127.0.0.1:8765").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) }
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.message || payload?.error || `HTTP ${response.status}`);
  return payload as T;
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "POST", body: JSON.stringify(body) });
}

export function fetchIntegrationGateway(): Promise<IntegrationGatewaySnapshot> {
  return request("/api/integration-gateway/snapshot");
}

export function registerGatewaySource(input: RegisterSourceConnectorInput & Record<string, unknown>): Promise<LiveRow> {
  return post("/api/data-sources/connectors/register", input);
}

export function registerGatewayModel(input: RegisterModelEndpointInput & Record<string, unknown>): Promise<LiveRow> {
  return post("/api/models/endpoints/register", input);
}

export function checkGatewaySource(connectorKey: string): Promise<LiveRow> {
  return post("/api/data-sources/connectors/check", { connector_key: connectorKey, actor: "Jarvis" });
}

export function checkGatewayModel(endpointKey: string): Promise<LiveRow> {
  return post("/api/models/endpoints/check", { endpoint_key: endpointKey, actor: "Jarvis" });
}

export function runGatewayReadiness(input: RunProviderReadinessSweepInput = {}): Promise<LiveRow> {
  return post("/api/providers/readiness/run", input);
}

export function upsertGatewayMapping(input: UpsertSchemaMappingInput): Promise<LiveRow> {
  return post("/api/integrations/schema-mappings/upsert", input);
}

export function validateGatewayMapping(mappingKey: string): Promise<LiveRow> {
  return post("/api/integrations/schema-mappings/validate", { mapping_key: mappingKey, actor: "Data Quality Agent" });
}

export function upsertGatewayJob(input: UpsertIntegrationJobInput): Promise<LiveRow> {
  return post("/api/integrations/jobs/upsert", input);
}

export function runGatewayJob(jobKey: string): Promise<LiveRow> {
  return post("/api/integrations/jobs/run", { job_key: jobKey, actor: "Jarvis" });
}
