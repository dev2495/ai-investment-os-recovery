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
  ResearchCaseTrackerSchema,
  SystemHealthSchema,
  PortfolioOfficeSchema,
  ResearchIdeasSchema,
  LongTermThesisWorkspaceSchema,
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
  BlueprintRegistrySchema,
  validateSnapshot,
} from "./schemas";
import type {
  MissionControl,
  ResearchCaseTracker,
  SystemHealth,
  PortfolioOffice,
  ResearchIdeas,
  LongTermThesisWorkspace,
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
  BlueprintRegistry,
} from "./schemas";
import type { LiveRow } from "./liveRow";

type SnapshotHookOptions = {
  enabled?: boolean;
  refetchInterval?: number | false;
};

export interface ResearchMonitoringPayload {
  generated_at: string;
  pagination: LiveRow;
  companies: LiveRow[];
  monitor_runs: LiveRow[];
  private_data_egress_allowed?: boolean;
  external_write_allowed?: boolean;
  broker_write_allowed?: boolean;
}

export interface ResearchUpdatesPayload {
  generated_at: string;
  scope: string;
  pagination: LiveRow;
  items: LiveRow[];
}

export interface ResearchFollowingPayload {
  scope_key: string;
  sources: LiveRow[];
  items: LiveRow[];
  ideas: LiveRow[];
  quarantine: LiveRow[];
  page: LiveRow;
  broker_write_allowed: boolean;
  external_write_allowed: boolean;
}

export interface FundamentalScannersPayload {
  items: LiveRow[];
  page: LiveRow;
  broker_write_allowed: boolean;
  external_write_allowed: boolean;
}

export interface ResearchKnowledgePayload {
  scope_key: string;
  query: string;
  items: LiveRow[];
  nodes: LiveRow[];
  edges: LiveRow[];
  notes: LiveRow[];
  unresolved_links: LiveRow[];
  page: LiveRow;
  privacy: string;
  broker_write_allowed: boolean;
  external_write_allowed: boolean;
}

/* ============================================================
 * Query keys (centralized for invalidation)
 * ============================================================ */
export const queryKeys = {
  missionControl: ["mission-control"] as const,
  researchCases: (page: number, status: string, caseId: number) => ["research-cases", page, status || "all", caseId || "latest"] as const,
  researchMonitoring: (page: number, pageSize: number) => ["research-monitoring", page, pageSize] as const,
  researchUpdates: (scope: string, status: string, materiality: string, symbol: string, page: number, pageSize: number) =>
    ["research-updates", scope, status, materiality || "all", symbol || "all", page, pageSize] as const,
  fundamentalScanner: ["fundamental-scanner"] as const,
  researchFollowingSources: (cursor: number, limit: number) => ["research-following-sources", cursor, limit] as const,
  researchKnowledge: (page: number, pageSize: number, query: string, family: string) =>
    ["research-knowledge", page, pageSize, query || "all", family || "all"] as const,
  systemHealth: ["system-health"] as const,
  portfolioOffice: ["portfolio-office"] as const,
  researchIdeas: ["research-ideas"] as const,
  longTermThesis: (thesisId: number | null, factsPage: number, evidencePage: number, symbol = "", exchange = "") =>
    ["long-term-thesis", thesisId ?? "default", factsPage, evidencePage, symbol || "none", exchange || "any"] as const,
  tradingQuantRisk: ["trading-quant-risk"] as const,
  optionsDaily: ["options-daily"] as const,
  sectorIntelligence: ["sector-intelligence"] as const,
  strategyArsenal: ["strategy-arsenal"] as const,
  reports: ["reports"] as const,
  integrationGateway: ["integration-gateway"] as const,
  office: ["office"] as const,
  graphControl: (runId?: number | null) => ["graph-control", runId ?? "all"] as const,
  zerodhaAuth: ["zerodha-auth"] as const,
  zerodhaMarket: ["zerodha-market"] as const,
  companyIRSources: ["company-ir-sources"] as const,
  tradingViewDesktop: ["tradingview-desktop"] as const,
  departmentTerminal: (workspace: string) => ["department-terminal", workspace] as const,
  evidence: (kind: string, key: string) => ["evidence", kind, key] as const,
  workspaceConfig: (profileKey: string) => ["workspace-config", profileKey] as const,
  blueprintRequirements: (status = "", domainKey = "", priority = "") =>
    ["blueprint-requirements", status || "all", domainKey || "all", priority || "all"] as const,
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

export function useMissionControl(options: SnapshotHookOptions = {}) {
  return useQuery<MissionControl>({
    queryKey: queryKeys.missionControl,
    queryFn: async () => {
      const data = await get("/api/daily/command", { timeoutMs: 12_000 });
      return validateSnapshot(MissionControlSchema, data, "mission-control");
    },
    ...snapshotQueryOptions,
    enabled: options.enabled ?? true,
    refetchInterval: options.refetchInterval ?? SNAPSHOT_REFETCH_MS,
  });
}

export function useResearchCases(filters: { page?: number; pageSize?: number; status?: string; caseId?: number; enabled?: boolean; refetchInterval?: number | false } = {}) {
  const page = filters.page ?? 1;
  const pageSize = Math.max(1, Math.min(50, filters.pageSize ?? 12));
  const status = filters.status ?? "";
  const caseId = filters.caseId ?? 0;
  return useQuery<ResearchCaseTracker>({
    queryKey: [...queryKeys.researchCases(page, status, caseId), pageSize],
    queryFn: async () => {
      const data = await get("/api/research/cases", { query: { page, page_size: pageSize, status: status || undefined, case_id: caseId || undefined }, timeoutMs: 12_000 });
      return validateSnapshot(ResearchCaseTrackerSchema, data, "research-cases");
    },
    ...snapshotQueryOptions,
    enabled: filters.enabled ?? true,
    refetchInterval: filters.refetchInterval ?? SNAPSHOT_REFETCH_MS,
  });
}

export function useResearchMonitoring(page = 1, pageSize = 20, options: SnapshotHookOptions = {}) {
  const boundedSize = Math.max(1, Math.min(100, pageSize));
  return useQuery<ResearchMonitoringPayload>({
    queryKey: queryKeys.researchMonitoring(page, boundedSize),
    queryFn: () => get<ResearchMonitoringPayload>("/api/research/monitoring", {
      query: { page, page_size: boundedSize },
      timeoutMs: 12_000,
    }),
    staleTime: 60_000,
    retry: 0,
    refetchOnWindowFocus: false,
    placeholderData: keepPreviousData,
    enabled: options.enabled ?? true,
    refetchInterval: options.refetchInterval ?? false,
  });
}

export function useResearchUpdates(filters: { scope?: string; status?: string; materiality?: string; symbol?: string; page?: number; pageSize?: number; enabled?: boolean } = {}) {
  const scope = filters.scope ?? "decision_required";
  const status = filters.status ?? "new";
  const materiality = filters.materiality ?? "";
  const symbol = filters.symbol ?? "";
  const page = filters.page ?? 1;
  const pageSize = Math.max(1, Math.min(50, filters.pageSize ?? 20));
  return useQuery<ResearchUpdatesPayload>({
    queryKey: queryKeys.researchUpdates(scope, status, materiality, symbol, page, pageSize),
    queryFn: () => get<ResearchUpdatesPayload>("/api/today/research-updates", {
      query: { scope, status, materiality: materiality || undefined, symbol: symbol || undefined, page, page_size: pageSize },
      timeoutMs: 12_000,
    }),
    staleTime: 60_000,
    retry: 0,
    refetchOnWindowFocus: false,
    placeholderData: keepPreviousData,
    enabled: filters.enabled ?? true,
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

export function useBlueprintRequirements(filters: { status?: string; domainKey?: string; priority?: string } = {}) {
  const status = filters.status ?? "";
  const domainKey = filters.domainKey ?? "";
  const priority = filters.priority ?? "";
  return useQuery<BlueprintRegistry>({
    queryKey: queryKeys.blueprintRequirements(status, domainKey, priority),
    queryFn: async () => {
      const data = await get("/api/blueprint/requirements", {
        query: {
          status: status || undefined,
          domain_key: domainKey || undefined,
          priority: priority || undefined,
          limit: 160,
        },
      });
      return validateSnapshot(BlueprintRegistrySchema, data, "blueprint-requirements");
    },
    ...snapshotQueryOptions,
  });
}

export function useZerodhaAuthStatus(enabled = true) {
  return useQuery<LiveRow>({
    queryKey: queryKeys.zerodhaAuth,
    queryFn: () => get<LiveRow>("/api/zerodha/auth/status"),
    ...snapshotQueryOptions,
    enabled,
    refetchInterval: 60_000,
  });
}

export function useZerodhaMarketStatus(enabled = true) {
  return useQuery<LiveRow>({
    queryKey: queryKeys.zerodhaMarket,
    queryFn: () => get<LiveRow>("/api/zerodha/market/status"),
    ...snapshotQueryOptions,
    enabled,
    refetchInterval: 15_000,
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
        queryClient.invalidateQueries({ queryKey: queryKeys.zerodhaMarket }),
        queryClient.invalidateQueries({ queryKey: queryKeys.missionControl }),
        queryClient.invalidateQueries({ queryKey: queryKeys.tradingQuantRisk }),
      ]);
    },
  });
}

export function useExchangeZerodhaCallbackUrl() {
  const queryClient = useQueryClient();
  return useMutation<LiveRow, Error, string>({
    mutationFn: (callbackUrl) =>
      post<LiveRow>("/api/zerodha/auth/exchange-url", {
        callback_url: callbackUrl,
        actor: "Devarsh",
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.zerodhaAuth }),
        queryClient.invalidateQueries({ queryKey: queryKeys.zerodhaMarket }),
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

export function useResearchIdeas(options: SnapshotHookOptions = {}) {
  return useQuery<ResearchIdeas>({
    queryKey: queryKeys.researchIdeas,
    queryFn: async () => {
      const data = await get("/api/research/daily", { timeoutMs: 12_000 });
      return validateSnapshot(ResearchIdeasSchema, data, "research-ideas");
    },
    ...snapshotQueryOptions,
    enabled: options.enabled ?? true,
    refetchInterval: options.refetchInterval ?? SNAPSHOT_REFETCH_MS,
  });
}

export function useFundamentalScanner(options: SnapshotHookOptions = {}) {
  return useQuery<FundamentalScannersPayload>({
    queryKey: queryKeys.fundamentalScanner,
    queryFn: () => get<FundamentalScannersPayload>("/api/fundamental-scanners", {
      query: { limit: 48, cursor: 0 }, timeoutMs: 12_000,
    }),
    staleTime: 60_000,
    retry: 0,
    refetchOnWindowFocus: false,
    enabled: options.enabled ?? true,
    refetchInterval: options.refetchInterval ?? false,
  });
}

export function useCreateFundamentalScanner() {
  const client = useQueryClient();
  return useMutation<LiveRow, Error, { instruction: string; name?: string }>({
    mutationFn: (payload) => post<LiveRow>("/api/fundamental-scanners/from-natural-language", payload),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.fundamentalScanner }),
  });
}

export function useScannerAction() {
  const client = useQueryClient();
  return useMutation<LiveRow, Error, { scannerId: number; action: "clone" | "validate" | "publish-request" | "publish" | "run"; payload?: LiveRow }>({
    mutationFn: ({ scannerId, action, payload }) => post<LiveRow>(`/api/fundamental-scanners/${scannerId}/${action}`, payload ?? {}),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.fundamentalScanner }),
  });
}

export function useResearchFollowingSources(cursor = 0, limit = 30) {
  return useQuery<ResearchFollowingPayload>({
    queryKey: queryKeys.researchFollowingSources(cursor, limit),
    queryFn: () => get<ResearchFollowingPayload>("/api/research/following", { query: { cursor, limit }, timeoutMs: 12_000 }),
    staleTime: 60_000,
    retry: 0,
    refetchOnWindowFocus: false,
  });
}

export function useFollowResearchSource() {
  const client = useQueryClient();
  return useMutation<LiveRow, Error, LiveRow>({
    mutationFn: (payload) => post<LiveRow>("/api/research/following", payload),
    onSuccess: () => client.invalidateQueries({ queryKey: ["research-following-sources"] }),
  });
}

export function useRefreshResearchSource() {
  const client = useQueryClient();
  return useMutation<LiveRow, Error, { followed_source_id: number }>({
    mutationFn: (payload) => post<LiveRow>("/api/research/following/refresh", payload),
    onSuccess: () => client.invalidateQueries({ queryKey: ["research-following-sources"] }),
  });
}

export function useLongTermThesisWorkspace(
  thesisId: number | null,
  factsPage = 1,
  evidencePage = 1,
  pageSize = 12,
  symbol = "",
  exchange = "",
) {
  return useQuery<LongTermThesisWorkspace>({
    queryKey: queryKeys.longTermThesis(thesisId, factsPage, evidencePage, symbol, exchange),
    queryFn: async () => {
      const data = await get("/api/research/long-term-thesis", {
        query: {
          thesis_id: thesisId || undefined,
          facts_page: factsPage,
          evidence_page: evidencePage,
          page_size: pageSize,
          profile: "dashboard",
          symbol: symbol || undefined,
          exchange: exchange || undefined,
        },
        // The authenticated Tailscale bridge adds transport latency to a source-backed
        // ten-year report; keep the loading state rather than aborting a valid response.
        timeoutMs: 30_000,
      });
      return validateSnapshot(LongTermThesisWorkspaceSchema, data, "long-term-thesis");
    },
    ...snapshotQueryOptions,
    refetchInterval: 60_000,
  });
}

export function useCompanyIRSources() {
  return useQuery<LiveRow>({
    queryKey: queryKeys.companyIRSources,
    queryFn: () => get<LiveRow>("/api/research/company-ir/sources", { query: { status: "all" } }),
    ...snapshotQueryOptions,
    refetchInterval: 60_000,
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

export function useOptionsDaily(page = 1, pageSize = 48) {
  return useQuery<TradingQuantRisk>({
    queryKey: [...queryKeys.optionsDaily, page, pageSize],
    queryFn: async () => {
      const data = await get("/api/options/daily", {
        query: { page, page_size: pageSize },
        timeoutMs: 12_000,
      });
      return validateSnapshot(TradingQuantRiskSchema, data, "options-daily");
    },
    ...snapshotQueryOptions,
    refetchInterval: 60_000,
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

export function useReports(options: SnapshotHookOptions = {}) {
  return useQuery<Reports>({
    queryKey: queryKeys.reports,
    queryFn: async () => {
      const data = await get("/api/reports/snapshot");
      return validateSnapshot(ReportsSchema, data, "reports");
    },
    ...snapshotQueryOptions,
    enabled: options.enabled ?? true,
    refetchInterval: options.refetchInterval ?? SNAPSHOT_REFETCH_MS,
  });
}

export function useResearchKnowledge(filters: { page?: number; pageSize?: number; query?: string; family?: string; enabled?: boolean } = {}) {
  const page = filters.page ?? 1;
  const pageSize = Math.max(1, Math.min(50, filters.pageSize ?? 40));
  const query = filters.query?.trim() ?? "";
  const family = filters.family ?? "";
  return useQuery<ResearchKnowledgePayload>({
    queryKey: queryKeys.researchKnowledge(page, pageSize, query, family),
    queryFn: async () => {
      return get<ResearchKnowledgePayload>("/api/research/knowledge", {
        query: { cursor: (page - 1) * pageSize, limit: pageSize, q: query || undefined, node_type: family || undefined },
        timeoutMs: 12_000,
      });
    },
    staleTime: 120_000,
    retry: 0,
    refetchOnWindowFocus: false,
    placeholderData: keepPreviousData,
    enabled: filters.enabled ?? true,
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
      const data = await get("/api/graphs/daily", {
        query: runId ? { run_id: runId } : undefined,
        timeoutMs: 12_000,
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
