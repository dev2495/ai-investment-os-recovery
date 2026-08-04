/**
 * AI Investment OS — TanStack Query Hooks
 *
 * One query per snapshot endpoint. All snapshot queries share a coordinated
 * 30s refetch interval (single source of truth) — replacing the old per-
 * workspace `setInterval` storms that re-fetched the same data and leaked
 * across workspace switches.
 *
 * Mutations invalidate the relevant queries so the UI updates optimistically.
 */

import { useQuery, useMutation, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import { get, post, SNAPSHOT_REFETCH_MS } from "./client";
import {
  MissionControlSchema,
  SystemHealthSchema,
  PortfolioOfficeSchema,
  ResearchIdeasSchema,
  TradingQuantRiskSchema,
  SectorIntelligenceSchema,
  StrategyArsenalSchema,
  ReportsSchema,
  IntegrationGatewaySchema,
  OfficeSnapshotSchema,
  DepartmentTerminalSchema,
  GraphControlSnapshotSchema,
  EntityEvidenceSchema,
  ChatResponseSchema,
  WorkspaceConfigSchema,
  validateSnapshot,
} from "./schemas";
import type {
  MissionControl,
  SystemHealth,
  PortfolioOffice,
  ResearchIdeas,
  TradingQuantRisk,
  SectorIntelligence,
  StrategyArsenal,
  Reports,
  IntegrationGateway,
  OfficeSnapshot,
  DepartmentTerminal,
  GraphControlSnapshot,
  EntityEvidence,
  ChatResponse,
  WorkspaceConfig,
} from "./schemas";
import type { LiveRow } from "./liveRow";

/* ============================================================
 * Query keys (centralized for invalidation)
 * ============================================================ */
export const queryKeys = {
  missionControl: ["mission-control"] as const,
  systemHealth: ["system-health"] as const,
  portfolioOffice: ["portfolio-office"] as const,
  researchIdeas: ["research-ideas"] as const,
  tradingQuantRisk: ["trading-quant-risk"] as const,
  sectorIntelligence: ["sector-intelligence"] as const,
  strategyArsenal: ["strategy-arsenal"] as const,
  reports: ["reports"] as const,
  integrationGateway: ["integration-gateway"] as const,
  office: ["office"] as const,
  graphControl: (runId?: number | null) => ["graph-control", runId ?? "all"] as const,
  zerodhaAuth: ["zerodha-auth"] as const,
  tradingViewDesktop: ["tradingview-desktop"] as const,
  departmentTerminal: (workspace: string) => ["department-terminal", workspace] as const,
  evidence: (kind: string, key: string) => ["evidence", kind, key] as const,
  workspaceConfig: (profileKey: string) => ["workspace-config", profileKey] as const,
};

/* ============================================================
 * Common options for all snapshot queries
 * ============================================================ */
const snapshotQueryOptions = {
  refetchInterval: SNAPSHOT_REFETCH_MS,
  refetchOnWindowFocus: true,
  refetchIntervalInBackground: false,
  placeholderData: keepPreviousData, // smooth transitions, no flicker on refetch
  staleTime: 10_000, // consider fresh for 10s before background refetch
  retry: (failureCount: number) => failureCount < 2, // don't hammer a dead server
  retryDelay: (attempt: number) => Math.min(1000 * 2 ** attempt, 15_000),
} as const;

/* ============================================================
 * Snapshot queries
 * ============================================================ */

export function useMissionControl() {
  return useQuery<MissionControl>({
    queryKey: queryKeys.missionControl,
    queryFn: async () => {
      const data = await get("/api/mission-control/snapshot");
      return validateSnapshot(MissionControlSchema, data, "mission-control");
    },
    ...snapshotQueryOptions,
  });
}

export function useSystemHealth() {
  return useQuery<SystemHealth>({
    queryKey: queryKeys.systemHealth,
    queryFn: async () => {
      const data = await get("/api/system-health/snapshot");
      return validateSnapshot(SystemHealthSchema, data, "system-health");
    },
    ...snapshotQueryOptions,
  });
}

export function useZerodhaAuthStatus() {
  return useQuery<LiveRow>({
    queryKey: queryKeys.zerodhaAuth,
    queryFn: () => get<LiveRow>("/api/zerodha/auth/status"),
    ...snapshotQueryOptions,
    refetchInterval: 60_000,
  });
}

export function useBeginZerodhaAuth() {
  return useMutation<LiveRow, Error, void>({
    mutationFn: () => post<LiveRow>("/api/zerodha/auth/begin", { actor: "Devarsh" }),
  });
}

export function useExchangeZerodhaToken() {
  const queryClient = useQueryClient();
  return useMutation<LiveRow, Error, string>({
    mutationFn: (requestToken) =>
      post<LiveRow>("/api/zerodha/auth/exchange", {
        request_token: requestToken,
        actor: "Devarsh",
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.zerodhaAuth }),
        queryClient.invalidateQueries({ queryKey: queryKeys.missionControl }),
        queryClient.invalidateQueries({ queryKey: queryKeys.tradingQuantRisk }),
      ]);
    },
  });
}


export function useTradingViewDesktopStatus() {
  return useQuery<LiveRow>({
    queryKey: queryKeys.tradingViewDesktop,
    queryFn: () => get<LiveRow>("/api/tradingview/desktop-status"),
    ...snapshotQueryOptions,
    refetchInterval: 30_000,
  });
}

export function usePortfolioOffice() {
  return useQuery<PortfolioOffice>({
    queryKey: queryKeys.portfolioOffice,
    queryFn: async () => {
      const data = await get("/api/portfolio-office/snapshot");
      return validateSnapshot(PortfolioOfficeSchema, data, "portfolio-office");
    },
    ...snapshotQueryOptions,
  });
}

export function useResearchIdeas() {
  return useQuery<ResearchIdeas>({
    queryKey: queryKeys.researchIdeas,
    queryFn: async () => {
      const data = await get("/api/research-ideas/snapshot");
      return validateSnapshot(ResearchIdeasSchema, data, "research-ideas");
    },
    ...snapshotQueryOptions,
  });
}

export function useSectorIntelligence() {
  return useQuery<SectorIntelligence>({
    queryKey: queryKeys.sectorIntelligence,
    queryFn: async () => {
      const data = await get("/api/sector-intelligence/snapshot");
      return validateSnapshot(SectorIntelligenceSchema, data, "sector-intelligence");
    },
    ...snapshotQueryOptions,
  });
}

export function useTradingQuantRisk() {
  return useQuery<TradingQuantRisk>({
    queryKey: queryKeys.tradingQuantRisk,
    queryFn: async () => {
      const data = await get("/api/trading-quant-risk/snapshot");
      return validateSnapshot(TradingQuantRiskSchema, data, "trading-quant-risk");
    },
    ...snapshotQueryOptions,
  });
}

export function useStrategyArsenal() {
  return useQuery<StrategyArsenal>({
    queryKey: queryKeys.strategyArsenal,
    queryFn: async () => {
      const data = await get("/api/strategy-arsenal/snapshot");
      return validateSnapshot(StrategyArsenalSchema, data, "strategy-arsenal");
    },
    ...snapshotQueryOptions,
  });
}

export function useReports() {
  return useQuery<Reports>({
    queryKey: queryKeys.reports,
    queryFn: async () => {
      const data = await get("/api/reports/snapshot");
      return validateSnapshot(ReportsSchema, data, "reports");
    },
    ...snapshotQueryOptions,
  });
}

export function useIntegrationGateway() {
  return useQuery<IntegrationGateway>({
    queryKey: queryKeys.integrationGateway,
    queryFn: async () => {
      const data = await get("/api/integration-gateway/snapshot");
      return validateSnapshot(IntegrationGatewaySchema, data, "integration-gateway");
    },
    ...snapshotQueryOptions,
  });
}

export function useOfficeSnapshot() {
  return useQuery<OfficeSnapshot>({
    queryKey: queryKeys.office,
    queryFn: async () => {
      const data = await get("/api/office/snapshot");
      return validateSnapshot(OfficeSnapshotSchema, data, "office");
    },
    // Office ticks more frequently for the live 3D view
    refetchInterval: 15_000,
    refetchOnWindowFocus: true,
    placeholderData: keepPreviousData,
    staleTime: 5_000,
    retry: (failureCount: number) => failureCount < 2,
  });
}

export function useGraphControlSnapshot(runId?: number | null) {
  return useQuery<GraphControlSnapshot>({
    queryKey: queryKeys.graphControl(runId),
    queryFn: async () => {
      const data = await get("/api/graph-control/snapshot", {
        query: runId ? { run_id: runId } : undefined,
      });
      return validateSnapshot(GraphControlSnapshotSchema, data, "graph-control");
    },
    refetchInterval: 10_000,
    refetchOnWindowFocus: true,
    placeholderData: keepPreviousData,
    staleTime: 3_000,
    retry: (failureCount: number) => failureCount < 2,
  });
}

export function useDepartmentTerminal(workspace: string | null) {
  return useQuery<DepartmentTerminal>({
    queryKey: queryKeys.departmentTerminal(workspace ?? ""),
    queryFn: async () => {
      const data = await get("/api/department-terminal/snapshot", { query: { workspace: workspace! } });
      return validateSnapshot(DepartmentTerminalSchema, data, `department-terminal:${workspace}`);
    },
    enabled: Boolean(workspace),
    ...snapshotQueryOptions,
  });
}

/* ============================================================
 * Evidence (on-demand, not polled)
 * ============================================================ */

export function useEntityEvidence(kind: string | null, key: string | null) {
  return useQuery<EntityEvidence>({
    queryKey: queryKeys.evidence(kind ?? "", key ?? ""),
    queryFn: async () => {
      const data = await get(`/api/evidence/entity/${encodeURIComponent(kind!)}/${encodeURIComponent(key!)}`);
      return validateSnapshot(EntityEvidenceSchema, data, `evidence:${kind}:${key}`);
    },
    enabled: Boolean(kind && key),
    staleTime: 60_000,
    placeholderData: keepPreviousData,
    retry: 1,
  });
}

/* ============================================================
 * Workspace config
 * ============================================================ */

export function useWorkspaceConfig(profileKey = "devarsh") {
  return useQuery<WorkspaceConfig>({
    queryKey: queryKeys.workspaceConfig(profileKey),
    queryFn: async () => {
      const data = await get("/api/workspaces/config", { query: { profile_key: profileKey } });
      return validateSnapshot(WorkspaceConfigSchema, data, "workspace-config");
    },
    staleTime: 5 * 60_000,
  });
}

/* ============================================================
 * Chat (Charlie) — mutation, not polled
 * ============================================================ */

export interface ChatInput {
  message: string;
  session_key?: string;
  actor?: string;
  workspace?: string;
  route_name?: string;
  deterministic_only?: boolean;
  include_client_context?: boolean;
  privacy_class?: string;
  cloud_approved?: boolean;
  contains_client_data?: boolean;
  metadata?: Record<string, unknown>;
}

export function useChat() {
  return useMutation<ChatResponse, Error, ChatInput>({
    mutationFn: async (input) => {
      const data = await post("/api/chat", input, { timeoutMs: 300_000 });
      return validateSnapshot(ChatResponseSchema, data, "chat");
    },
  });
}

/* ============================================================
 * Generic action mutations (POST endpoints that return LiveRow)
 *
 * Each invalidates the relevant snapshot queries after success so the UI
 * reflects the change without a manual refresh.
 * ============================================================ */

export function useAction<TBody = Record<string, unknown>>(
  path: string,
  options?: { invalidate?: readonly (readonly string[])[] }
) {
  const queryClient = useQueryClient();
  return useMutation<LiveRow, Error, TBody>({
    mutationFn: (body) => post<LiveRow>(path, body),
    onSuccess: () => {
      if (options?.invalidate) {
        for (const key of options.invalidate) {
          queryClient.invalidateQueries({ queryKey: key });
        }
      }
    },
  });
}

/* ============================================================
 * Specific named actions (the ones the UI calls most often)
 * ============================================================ */

export function useResolveApproval() {
  const queryClient = useQueryClient();
  return useMutation<LiveRow, Error, Record<string, unknown>>({
    mutationFn: (body) => post("/api/approvals/resolve", body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mission-control"] });
      queryClient.invalidateQueries({ queryKey: ["portfolio-office"] });
      queryClient.invalidateQueries({ queryKey: ["office"] });
    },
  });
}

export function useEngageKillSwitch() {
  const queryClient = useQueryClient();
  return useMutation<LiveRow, Error, Record<string, unknown>>({
    mutationFn: (body) => post("/api/execution/global-kill-switch/engage", body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["trading-quant-risk"] });
      queryClient.invalidateQueries({ queryKey: ["office"] });
    },
  });
}

export function useMaterializeSchedules() {
  const queryClient = useQueryClient();
  return useMutation<LiveRow, Error, { actor?: string; limit?: number }>({
    mutationFn: (body) => post("/api/agents/schedules/run", body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mission-control"] });
    },
  });
}

export function useRunScheduledReports() {
  const queryClient = useQueryClient();
  return useMutation<LiveRow, Error, { report_key?: string; force?: boolean; actor?: string }>({
    mutationFn: (body) => post("/api/reports/run", body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reports"] });
    },
  });
}
