import type { LiveRow, TradingViewCdpStatus } from "./live";

export interface SystemHealthSnapshot {
  generated_at: string;
  runtime_root: string;
  vault_root: string;
  tradingview_cdp: TradingViewCdpStatus;
  storage: {
    vault_mounted: boolean;
    ollama_models_external: boolean;
    docker_raw_external: boolean;
    heavy_state_external: boolean;
  };
  recovery: {
    backup_root: string;
    current_exists: boolean;
    previous_exists: boolean;
    created_at?: string;
    format_version?: string;
    repo_commit?: string;
    postgres_dump_exists: boolean;
    postgres_dump_bytes: number;
    qdrant_snapshot_exists: boolean;
    qdrant_snapshot_bytes: number;
    qdrant_snapshot_name?: string;
    vault_copy_exists: boolean;
    vault_file_count: number;
    checksums_exist: boolean;
    latest_restore_drill: Record<string, unknown>;
    backup_schedule_installed: boolean;
    report_schedule_installed: boolean;
  };
  data_mode: {
    seed_data_allowed: boolean;
    source: string;
  };
  payload_profile: {
    query_count: number;
    row_count: number;
  };
  metrics: LiveRow[];
  blueprint_summary: LiveRow[];
  blueprint_domains: LiveRow[];
  blueprint_sync_runs: LiveRow[];
  data_sources: LiveRow[];
  data_source_checks: LiveRow[];
  source_freshness: LiveRow[];
  source_freshness_scheduler_runs: LiveRow[];
  runtime_daemons: LiveRow[];
  model_routes: LiveRow[];
  model_endpoints: LiveRow[];
  provider_readiness_summary: LiveRow[];
  provider_readiness_board: LiveRow[];
  connector_health_checks: LiveRow[];
  browser_session_checks: LiveRow[];
  execution_control: LiveRow[];
  pipeline_readiness: LiveRow[];
}

const API_URL = (import.meta.env.VITE_AI_OS_API_URL || "http://127.0.0.1:8765").replace(/\/$/, "");

export async function fetchSystemHealthSnapshot(): Promise<SystemHealthSnapshot> {
  const response = await fetch(`${API_URL}/api/system-health/snapshot`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`System Health API returned ${response.status}`);
  }
  return response.json() as Promise<SystemHealthSnapshot>;
}
