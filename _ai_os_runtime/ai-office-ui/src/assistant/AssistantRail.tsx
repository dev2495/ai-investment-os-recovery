/**
 * Charlie — Personal Assistant Rail
 *
 * A persistent right rail (collapsible) that's always there across all
 * destinations. Charlie is your chief of staff: he can answer questions,
 * surface evidence, delegate to departments, and route approvals.
 *
 * - Context-aware (knows which destination you're viewing)
 * - Uses the existing /api/chat (tool-intent inference + governed model
 *   routing + Qdrant retrieval)
 * - 4 reasoning routes (local / fast / deep / review)
 * - Inline evidence chips → open the evidence drawer
 * - Scoped agent chat (click an agent in the 3D office → switches scope)
 */

import React from "react";
import { useLocation } from "react-router-dom";
import {
  Sparkles,
  Send,
  PanelRightClose,
  Brain,
  Zap,
  Microscope,
  ClipboardCheck,
  BookOpenCheck,
  Lightbulb,
  Trash2,
} from "lucide-react";
import { useUIStore } from "../store";
import { useChat, useDepartmentTerminal } from "../data/queries";
import {
  useProposeArchitectureChange,
  useUpdateWorkspaceConfig,
  useCreateAgentMessage,
  useMaterializeWidgets,
  useApproveResearchModelPreflight,
  useProposeResearchCase,
  useStartResearchCase,
} from "../data/actions";
import { AssistantRailCss } from "./AssistantRail.css";
import { text, formatRelative, initials } from "../data/liveRow";
import type { LiveRow } from "../data/liveRow";
import { useNavigate } from "react-router-dom";

type ReasoningRoute = "local" | "fast" | "research" | "deep" | "review";

/** An actionable proposal Charlie surfaces — governance, delegation, screen change. */
interface AssistantAction {
  id: string;
  kind: "governance" | "delegate" | "screen" | "widget" | "evidence_open" | "navigate" | "research_review_start" | "research_start" | "research_distinct" | "research_pick";
  label: string;
  description?: string;
  /** Payload for the action — interpreted by the dispatch table. */
  payload: Record<string, unknown>;
  /** Whether the action was already executed. */
  executed?: boolean;
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  route?: string;
  evidence?: Array<{ kind: string; key: string; label: string }>;
  actions?: AssistantAction[];
  operations?: Array<{ tool: string; status: string; detail?: string }>;
  assistantName?: string;
  assistantTitle?: string;
  ts: number;
}

const ROUTES: Array<{ key: ReasoningRoute; label: string; icon: typeof Brain; desc: string }> = [
  { key: "local", label: "Private", icon: Brain, desc: "Natural local Charlie with private portfolio context" },
  { key: "fast", label: "Fast", icon: Zap, desc: "Gemini Flash quick answer with verified local stack snapshot; no client data" },
  { key: "research", label: "Research", icon: BookOpenCheck, desc: "Gemini 3.6 Flash multimodal research; explicit use, no client data" },
  { key: "deep", label: "Deep", icon: Microscope, desc: "Terra deep research; explicit use, no client data" },
  { key: "review", label: "Review", icon: ClipboardCheck, desc: "Sol frontier review; explicit use, no client data" },
];

const ROUTE_CONFIG: Record<ReasoningRoute, { routeName: string; privateContext: boolean }> = {
  local: { routeName: "charlie_munger_orchestration", privateContext: true },
  fast: { routeName: "openrouter_gemini36_research", privateContext: false },
  research: { routeName: "openrouter_gemini36_research", privateContext: false },
  deep: { routeName: "openrouter_terra_research", privateContext: false },
  review: { routeName: "openrouter_sol_review", privateContext: false },
};


const RESEARCH_START_PATTERN = /^\s*(?:please\s+)?(?:(?:can|could|would|will)\s+you\s+)?(?:start|begin|launch|initiate|open|create|do)\s+(?:(?:a\s+new|a|new)\s+)?(?:(?:long[-\s]?term|fundamental|equity|investment|company|public[-\s]?company)\s+)*(?:research(?:\s+case)?|analysis|dossier|report)\s+(?:on|for|about|into)\s+(.+?)\s*$/i;

function extractResearchStartEntity(command: string): string | null {
  let candidate = command.trim().replace(/[\s.,:;\-–—!?]+$/g, "").trim();
  let matched = false;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const result = candidate.match(RESEARCH_START_PATTERN);
    if (!result) break;
    matched = true;
    const nested = String(result[1] || "").trim().replace(/[\s.,:;\-–—!?]+$/g, "").trim();
    if (!nested || nested === candidate) break;
    candidate = nested;
  }
  if (candidate.length >= 2 && ((candidate.startsWith("\"") && candidate.endsWith("\"")) || (candidate.startsWith("'") && candidate.endsWith("'")))) {
    candidate = candidate.slice(1, -1).trim();
  }
  return matched && candidate ? candidate : null;
}

function extractResearchRequest(command: string): string | null {
  const explicit = extractResearchStartEntity(command);
  if (explicit) return explicit;
  const normalized = command.trim();
  if (!normalized || normalized.endsWith("?")) return null;
  const imperative = normalized.match(/^\s*(?:please\s+)?(?:research|underwrite|analyse|analyze)\s+(?:company\s+)?(.+)/i);
  if (!imperative) return null;
  const entity = String(imperative[1] || "").trim();
  return entity || null;
}
const QUICK_ACTIONS = [
  { label: "What do I need to decide today?", icon: ClipboardCheck },
  { label: "Summarize my portfolio risk", icon: Brain },
  { label: "What's fresh in research?", icon: Lightbulb },
  { label: "Show me the latest breaches", icon: Zap },
  { label: "Create a new strategy called…", icon: Sparkles },
  { label: "Start research on USHAMART", icon: Microscope },
];

export function AssistantRail() {
  const open = useUIStore((s) => s.assistantOpen);
  const setOpen = useUIStore((s) => s.setAssistantOpen);
  const pendingAssistantMessage = useUIStore((s) => s.pendingAssistantMessage);
  const consumeAssistantMessage = useUIStore((s) => s.consumeAssistantMessage);
  const scope = useUIStore((s) => s.assistantScope);
  const openEvidence = useUIStore((s) => s.openEvidence);

  const location = useLocation();
  const navigate = useNavigate();
  const chat = useChat();
  const employeeDirectory = useDepartmentTerminal("agents");
  const proposeArchitecture = useProposeArchitectureChange();
  const updateWorkspace = useUpdateWorkspaceConfig();
  const createAgentMessage = useCreateAgentMessage();
  const materializeWidgets = useMaterializeWidgets();
  const proposeResearchCase = useProposeResearchCase();
  const startResearchCase = useStartResearchCase();
  const approveResearchPreflight = useApproveResearchModelPreflight();
  const assistantPending = chat.isPending || proposeResearchCase.isPending;

  const [messages, setMessages] = React.useState<ChatMessage[]>(() => {
    try {
      const stored = window.localStorage.getItem("aios:charlie-conversation");
      return stored ? JSON.parse(stored) as ChatMessage[] : [];
    } catch {
      return [];
    }
  });
  const [input, setInput] = React.useState("");
  const [route, setRoute] = React.useState<ReasoningRoute>("local");
  const scrollRef = React.useRef<HTMLDivElement | null>(null);
  const scopeProfile = React.useMemo(() => {
    if (scope === "charlie") return employeeDirectory.data?.primary?.find((row) => text(row, "agent_name") === "Charlie Munger");
    return employeeDirectory.data?.primary?.find((row) => text(row, "agent_name") === scope.agentName);
  }, [employeeDirectory.data?.primary, scope]);

  /** Destination context — tells Charlie where you are. */
  const destContext = React.useMemo(() => {
    const path = location.pathname;
    if (path.startsWith("/today")) return "Today";
    if (path.startsWith("/portfolio")) return "Portfolio";
    if (path.startsWith("/research")) return "Research & Strategy";
    if (path.startsWith("/risk-trading")) return "Risk & Trading";
    if (path.startsWith("/firm")) return "The Firm";
    return "the office";
  }, [location.pathname]);

  /** Pick up a pending question from the command palette. */
  React.useEffect(() => {
    const pending = sessionStorage.getItem("aios:pending-charlie-question");
    if (pending && open) {
      sessionStorage.removeItem("aios:pending-charlie-question");
      send(pending);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  React.useEffect(() => {
    if (!pendingAssistantMessage || !open || assistantPending) return;
    send(pendingAssistantMessage.message);
    consumeAssistantMessage(pendingAssistantMessage.id);
    // send is a component-local dispatcher; the durable store command is the effect dependency.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingAssistantMessage?.id, open, assistantPending, consumeAssistantMessage]);

  React.useEffect(() => {
    const handlePrefill = (event: Event) => {
      const detail = (event as CustomEvent<string>).detail;
      if (!detail) return;
      setOpen(true);
      setInput(detail);
    };
    window.addEventListener("aios:assistant-prefill", handlePrefill);
    return () => window.removeEventListener("aios:assistant-prefill", handlePrefill);
  }, [setOpen]);

  React.useEffect(() => {
    const handleSend = (event: Event) => {
      const detail = (event as CustomEvent<string>).detail?.trim();
      if (!detail) return;
      setOpen(true);
      send(detail);
    };
    window.addEventListener("aios:assistant-send", handleSend);
    return () => window.removeEventListener("aios:assistant-send", handleSend);
    // send intentionally uses the latest render state; listener is refreshed with it.
  });

  React.useEffect(() => {
    window.localStorage.setItem("aios:charlie-conversation", JSON.stringify(messages.slice(-80)));
  }, [messages]);

  /** Auto-scroll to bottom on new message. */
  React.useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, assistantPending]);

  function send(message: string) {
    const trimmed = message.trim();
    if (!trimmed || assistantPending) return;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: trimmed,
      ts: Date.now(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");

    const researchEntity = extractResearchRequest(trimmed);
    if (researchEntity) {
      proposeResearchCase.mutate(
        { request_text: trimmed, entity: researchEntity, actor: "Devarsh via Charlie" },
        {
          onSuccess: (data) => {
            const result = data as Record<string, unknown>;
            const caseRow = result.research_case && typeof result.research_case === "object" ? result.research_case as LiveRow : {};
            const preflight = result.model_preflight && typeof result.model_preflight === "object" ? result.model_preflight as LiveRow : {};
            const matches = Array.isArray(result.matches) ? result.matches as LiveRow[] : [];
            const status = String(result.status || "");
            const caseId = Number(caseRow.id || 0);
            const thesisId = Number(caseRow.holding_thesis_id || 0);
            const actions: AssistantAction[] = [];
            let content = String(result.detail || "Research proposal returned without a readable status.");

            if (status === "proposed") {
              const preflightId = Number(preflight.id || 0);
              const estimated = Number(preflight.estimated_cost_usd || 0);
              const hardMax = Number(preflight.hard_max_cost_usd || 0);
              const exchangeRate = Number(preflight.exchange_rate_inr_per_usd || 87);
              content = `Resolved ${text(caseRow, "exchange")}:${text(caseRow, "ticker")} to ${text(caseRow, "company_name")}. Research Case #${caseId} is proposed—not started. Estimated run cost is INR ${(estimated * exchangeRate).toFixed(2)} / USD ${estimated.toFixed(3)} with a hard stop of INR ${(hardMax * exchangeRate).toFixed(2)} / USD ${hardMax.toFixed(3)}. Public-source model packet only; private data stays on the external SSD.`;
              actions.push({ id: `act-${Date.now()}-start`, kind: "research_review_start", label: `Review cost & start Research Case #${caseId}`, description: "Review the final paid-run boundary. A separate confirmation is required before any model or agent work starts.", payload: { research_case_id: caseId, model_preflight_id: preflightId, estimated_cost_usd: estimated, hard_max_cost_usd: hardMax, exchange_rate_inr_per_usd: exchangeRate, company_name: String(caseRow.company_name || caseRow.ticker || researchEntity) } });
            } else if (status === "blocked_conflict" || status === "open_case_conflict") {
              content = String(result.detail || "An existing mandate needs attention, but it does not block a distinct new mandate.");
              actions.push({ id: `act-${Date.now()}-view`, kind: "navigate", label: `View / repair Case #${caseId}`, description: "Open the existing case and its exact source exceptions.", payload: { path: `/research/cases?case_id=${caseId}` } });
              actions.push({ id: `act-${Date.now()}-distinct`, kind: "research_distinct", label: "Propose a distinct re-underwrite", description: "Creates a separate mandate and still requires explicit cost approval and Start.", payload: { entity: String(caseRow.ticker || researchEntity), company_id: Number(caseRow.company_id || 0), mandate: `Re-underwrite ${String(caseRow.ticker || researchEntity)} valuation, capital allocation, operating drivers and disconfirming evidence as a distinct long-term decision mandate.` } });
            } else if (status === "needs_input" || status === "needs_confirmation") {
              content = String(result.detail || `I could not uniquely resolve ${researchEntity}. No case or agent work was created.`);
              for (const match of matches.slice(0, 5)) {
                actions.push({ id: `act-${Date.now()}-pick-${String(match.company_id)}`, kind: "research_pick", label: `Use ${String(match.exchange)}:${String(match.ticker)} · ${String(match.legal_name || match.display_name)}`, description: "Confirm this verified listed company and generate the source/work plan. No agents start yet.", payload: { entity: String(match.ticker), company_id: Number(match.company_id || 0) } });
              }
            } else if (caseId) {
              content = `Research Case #${caseId} is ${status || "available"}. No duplicate case or model run was created.`;
              actions.push({ id: `act-${Date.now()}-open`, kind: "navigate", label: `Open Research Case #${caseId}`, payload: { path: `/research/cases?case_id=${caseId}` } });
            }

            setMessages((current) => [...current, { id: `a-${Date.now()}`, role: "assistant", content, actions, assistantName: "Charlie", assistantTitle: "Chief of Staff · Orchestrator", ts: Date.now() }]);
          },
          onError: (error) => setMessages((current) => [...current, { id: `e-${Date.now()}`, role: "system", content: `Research proposal failed: ${error.message}`, ts: Date.now() }]),
        },
      );
      return;
    }
    const scopedAgent = scope === "charlie" ? "Charlie Munger" : scope.agentName;
    const routeConfig = ROUTE_CONFIG[route];
    chat.mutate(
      {
        message: trimmed,
        session_key: `devarsh-assistant-${scopedAgent.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`,
        actor: "Devarsh",
        workspace: destContext.toLowerCase().replace(/[^a-z]/g, "_"),
        route_name: routeConfig.routeName,
        deterministic_only: false,
        include_client_context: routeConfig.privateContext,
        privacy_class: routeConfig.privateContext ? "client_private" : "internal",
        cloud_approved: !routeConfig.privateContext,
        contains_client_data: routeConfig.privateContext && destContext === "Portfolio",
        metadata: { assistant_scope: scopedAgent, ui_destination: destContext },
      },
      {
        onSuccess: (data) => {
          const evidence = (data.retrieval_hits ?? []).slice(0, 3).map((hit) => ({
            kind: text(hit, "entity_kind", "artifact"),
            key: String(text(hit, "entity_key", text(hit, "id", ""))),
            label: text(hit, "title", text(hit, "name", "evidence")),
          }));

          // Extract actionable intents from Charlie's response.
          // These become proposal cards the user can accept/reject — Charlie
          // never mutates the stack unilaterally; he proposes, you decide.
          const actions: AssistantAction[] = [];
          const operations = (data.tool_intents ?? []).filter((intent) => text(intent, "tool", text(intent, "tool_name", "")) !== "propose_research_case").map((intent) => ({
            tool: text(intent, "tool", text(intent, "tool_name", "office_action")),
            status: text(intent, "status", "completed"),
            detail: text(intent, "detail", ""),
          }));

          // Tool intents → governance proposals (e.g. "add a new agent")
          for (const intent of data.tool_intents ?? []) {
            const toolName = text(intent, "tool", text(intent, "tool_name", text(intent, "name", "")));
            const reason = text(intent, "reason", text(intent, "description", ""));
            if (toolName === "propose_research_case") {
              const rawResult = intent.result && typeof intent.result === "object" ? intent.result as Record<string, unknown> : {};
              const caseRow = rawResult.research_case && typeof rawResult.research_case === "object" ? rawResult.research_case as Record<string, unknown> : {};
              const preflight = rawResult.model_preflight && typeof rawResult.model_preflight === "object" ? rawResult.model_preflight as Record<string, unknown> : {};
              const caseId = Number(caseRow.id || 0);
              const preflightId = Number(preflight.id || 0);
              const costUsd = Number(preflight.estimated_cost_usd || 0);
              const hardMaxUsd = Number(preflight.hard_max_cost_usd || 0);
              const exchangeRate = Number(preflight.exchange_rate_inr_per_usd || 87);
              const resultStatus = String(rawResult.status || intent.status || "");
              const matches = Array.isArray(rawResult.matches) ? rawResult.matches as Array<Record<string, unknown>> : [];
              if (resultStatus === "proposed" || (resultStatus === "active" && caseId)) {
                actions.push({ id: `act-${Date.now()}-${actions.length}`, kind: resultStatus === "proposed" ? "research_review_start" : "navigate", label: resultStatus === "proposed" ? `Review cost & start Research Case #${caseId}` : `Open Research Case #${caseId}`, description: resultStatus === "proposed" ? `${String(caseRow.company_name || caseRow.ticker)} · ${String(caseRow.horizon || "3–5 years")} · 11 specialist, synthesis and review roles · estimated INR ${(costUsd * exchangeRate).toFixed(2)} / USD ${costUsd.toFixed(3)}, hard stop INR ${(hardMaxUsd * exchangeRate).toFixed(2)} / USD ${hardMaxUsd.toFixed(3)} · public model packet only · private data stays on SSD · no broker, client or external writes. A second confirmation is required.` : "Open the durable case workspace.", payload: { research_case_id: caseId, model_preflight_id: preflightId, estimated_cost_usd: costUsd, hard_max_cost_usd: hardMaxUsd, exchange_rate_inr_per_usd: exchangeRate, company_name: String(caseRow.company_name || caseRow.ticker || "company"), path: `/research/cases?case_id=${caseId}`, raw: rawResult } });
              } else if (resultStatus === "blocked_conflict" || resultStatus === "open_case_conflict") {
                actions.push({ id: `act-${Date.now()}-${actions.length}`, kind: "navigate", label: `View / repair Case #${caseId}`, description: String(rawResult.detail || "Open the existing case and its exact evidence exceptions."), payload: { path: `/research/cases?case_id=${caseId}` } });
                actions.push({ id: `act-${Date.now()}-${actions.length}`, kind: "research_distinct", label: "Propose a distinct re-underwrite", description: "Create a separate mandate for valuation, FY2026 capex returns and disconfirming evidence. This does not resume or duplicate the blocked mandate, and still requires explicit Start.", payload: { entity: String(caseRow.ticker || caseRow.company_name || ""), company_id: Number(caseRow.company_id || 0), mandate: `Re-underwrite ${String(caseRow.ticker || caseRow.company_name)} valuation, FY2026 capex returns, operating drivers and disconfirming evidence as a distinct long-term decision mandate.` } });
              } else if (resultStatus === "needs_input") {
                for (const match of matches.slice(0, 5)) actions.push({ id: `act-${Date.now()}-${actions.length}`, kind: "research_pick", label: `Use ${String(match.exchange)}:${String(match.ticker)} · ${String(match.legal_name || match.display_name)}`, description: "Confirm this verified entity and generate the mandate/source plan. No agents start yet.", payload: { entity: String(match.ticker), company_id: Number(match.company_id || 0) } });
              }
            }
            if (toolName.includes("architecture") || toolName.includes("governance")) {
              actions.push({
                id: `act-${Date.now()}-${actions.length}`,
                kind: "governance",
                label: `Propose: ${text(intent, "title", toolName)}`,
                description: reason,
                payload: { tool_name: toolName, raw: intent },
              });
            }
          }

          // Backend-created jobs are already durable. Surface a tracking action
          // instead of creating a duplicate delegation.
          for (const job of data.agent_jobs ?? []) {
            const agent = text(job, "agent_key", text(job, "to_agent", "specialist"));
            const task = text(job, "task_name", text(job, "workflow_key", "delegated task"));
            actions.push({
              id: `act-${Date.now()}-${actions.length}`,
              kind: "navigate",
              label: `Track ${agent}`,
              description: task,
              payload: { path: "/firm/departments", task_name: task, raw: job },
            });
          }

          // Widget intents → screen/widget proposals
          for (const widget of data.widget_intents ?? []) {
            const wkey = text(widget, "widget_key", text(widget, "name", "widget"));
            actions.push({
              id: `act-${Date.now()}-${actions.length}`,
              kind: "widget",
              label: `Materialize widget: ${wkey}`,
              description: text(widget, "description", ""),
              payload: { widget_key: wkey, raw: widget },
            });
          }

          const assistantMsg: ChatMessage = {
            id: `a-${Date.now()}`,
            role: "assistant",
            content: data.message || "(no response)",
            route: text(data.route, "route_name", route),
            evidence,
            actions,
            operations,
            assistantName: text(data.assistant_identity, "agent_name", scopedAgent),
            assistantTitle: text(data.assistant_identity, "display_title", text(scopeProfile ?? {}, "display_title", "Investment office employee")),
            ts: Date.now(),
          };
          setMessages((prev) => [...prev, assistantMsg]);
        },
        onError: (err) => {
          const errorMsg: ChatMessage = {
            id: `e-${Date.now()}`,
            role: "system",
            content: `I couldn't reach the model layer: ${err.message}`,
            ts: Date.now(),
          };
          setMessages((prev) => [...prev, errorMsg]);
        },
      }
    );
  }

  function executeAction(action: AssistantAction) {
    if (action.executed) return;
    const markDone = () => {
      setMessages((current) => current.map((message) => ({
        ...message,
        actions: message.actions?.map((item) => item.id === action.id ? { ...item, executed: true } : item),
      })));
    };
    const fail = (error: Error) => {
      setMessages((current) => [...current, {
        id: `e-${Date.now()}`,
        role: "system",
        content: `Action failed: ${error.message}`,
        ts: Date.now(),
      }]);
    };

    if (action.kind === "research_review_start") {
      const caseId = Number(action.payload.research_case_id || 0);
      const preflightId = Number(action.payload.model_preflight_id || 0);
      const estimated = Number(action.payload.estimated_cost_usd || 0);
      const hardMax = Number(action.payload.hard_max_cost_usd || 0);
      const exchangeRate = Number(action.payload.exchange_rate_inr_per_usd || 87);
      const companyName = String(action.payload.company_name || "the selected company");
      if (!caseId || !preflightId) { fail(new Error("This proposal is stale. Re-run Start research to generate a fresh case and cost estimate.")); return; }
      const confirmed = window.confirm(`Final paid-run confirmation\n\n${companyName} · Research Case #${caseId}\nEstimated: INR ${(estimated * exchangeRate).toFixed(2)} / USD ${estimated.toFixed(3)}\nHard stop: INR ${(hardMax * exchangeRate).toFixed(2)} / USD ${hardMax.toFixed(3)}\n\nOnly a bounded public-source packet may leave the Mac. Private and client data remain on the external SSD. Broker, client, capital and external writes remain locked.\n\nChoose OK only to explicitly approve the cost and start.`);
      if (!confirmed) return;
      action = { ...action, kind: "research_start" };
    }
    if (action.kind === "research_start") {
      const caseId = Number(action.payload.research_case_id || 0);
      const preflightId = Number(action.payload.model_preflight_id || 0);
      if (!preflightId) { fail(new Error("This proposal is stale and has no cost preflight. Re-run Start research so Charlie can show a fresh estimate.")); return; }
      const startNow = () => startResearchCase.mutate(
        { research_case_id: caseId, model_preflight_id: preflightId, operator_confirmed: true, actor: "Devarsh via Charlie explicit confirmation" },
        {
          onSuccess: (data) => {
            const row = data.research_case && typeof data.research_case === "object" ? data.research_case as LiveRow : {};
            const id = Number(row.id || caseId);
            const graph = data.graph && typeof data.graph === "object" ? data.graph as LiveRow : {};
            const graphId = Number(row.graph_run_id || graph.graph_run_id || 0);
            const runtime = data.autonomous_runtime && typeof data.autonomous_runtime === "object" ? data.autonomous_runtime as LiveRow : {};
            const workstreamPath = `/research/cases?case_id=${id}`;
            const waitingForSources = data.model_dispatch_allowed === false || text(runtime, "status") === "waiting_for_qualified_public_sources";
            const successContent = waitingForSources
              ? `Research Case #${id} is collecting sources in graph run #${graphId}. Zero paid model roles were dispatched because no qualified public evidence is available yet. Add or collect an authorized source, then review a fresh cost preflight. Private data remains on the external SSD; broker, client, capital and external writes remain locked.`
              : `Research Case #${id} is active. ${Number(runtime.model_run_count ?? 0)} bounded public-research roles were durably created in graph run #${graphId}; lead synthesis, independent review and committee brief end at human decision. No broker, client, capital or external write was authorized.`;
            markDone();
            setMessages((current) => [...current, {
              id: `a-${Date.now()}`,
              role: "assistant",
              content: successContent,
              actions: [{ id: `act-${Date.now()}-open`, kind: "navigate", label: `Open ${text(row, "ticker", "company")} research workstream`, description: `Case #${id} · graph run #${graphId} · ${waitingForSources ? "collecting sources" : "active"}`, payload: { path: workstreamPath } }],
              ts: Date.now(),
            }]);
          },
          onError: fail,
        },
      );
      approveResearchPreflight.mutate({ preflight_id: preflightId, operator_confirmed: true, actor: "Devarsh via Charlie explicit confirmation" }, { onSuccess: startNow, onError: fail });
      return;
    }
    if (action.kind === "research_distinct" || action.kind === "research_pick") {
      const distinct = action.kind === "research_distinct";
      proposeResearchCase.mutate({ request_text: `Start long-term research on ${String(action.payload.entity || "company")}`, entity: String(action.payload.entity || ""), company_id: Number(action.payload.company_id || 0) || undefined, mandate: action.payload.mandate ? String(action.payload.mandate) : undefined, create_distinct_confirmed: distinct, actor: "Devarsh via Charlie" }, { onSuccess: (data) => { const row = data.research_case && typeof data.research_case === "object" ? data.research_case as LiveRow : {}; const preflight = data.model_preflight && typeof data.model_preflight === "object" ? data.model_preflight as LiveRow : {}; const id = Number(row.id || 0); const preflightId = Number(preflight.id || 0); const estimated = Number(preflight.estimated_cost_usd || 0); const hardMax = Number(preflight.hard_max_cost_usd || 0); const exchangeRate = Number(preflight.exchange_rate_inr_per_usd || 87); markDone(); setMessages((current) => [...current, { id: `a-${Date.now()}`, role: "assistant", content: `Resolved ${text(row, "exchange")}:${text(row, "ticker")} to ${text(row, "company_name")}. Proposed Research Case #${id}: ${text(row, "mandate")}. Estimated run cost is INR ${(estimated * exchangeRate).toFixed(2)} / USD ${estimated.toFixed(3)} with a hard stop of INR ${(hardMax * exchangeRate).toFixed(2)} / USD ${hardMax.toFixed(3)}. Private work remains on the external SSD.`, actions: [{ id: `act-${Date.now()}-start`, kind: "research_review_start", label: `Review cost & start Research Case #${id}`, description: "Review the final paid-run boundary. A separate confirmation is required before any model or agent work starts.", payload: { research_case_id: id, model_preflight_id: preflightId, estimated_cost_usd: estimated, hard_max_cost_usd: hardMax, exchange_rate_inr_per_usd: exchangeRate, company_name: String(row.company_name || row.ticker || "company") } }], ts: Date.now() }]); }, onError: fail });
      return;
    }
    if (action.kind === "governance") {
      proposeArchitecture.mutate({
        title: action.label.replace(/^Propose:\s*/, ""),
        change_type: "other",
        description: action.description || "Architecture change proposed through Charlie.",
        rationale: "Requested from the Charlie operator conversation.",
        risk_level: "medium",
        proposed_by: "Devarsh via Charlie",
        metadata: action.payload,
      }, { onSuccess: markDone, onError: fail });
      return;
    }
    if (action.kind === "delegate") {
      createAgentMessage.mutate({
        to_agent: String(action.payload.to_agent || "Research Analyst"),
        subject: String(action.payload.task_name || action.label),
        message: action.description || String(action.payload.task_name || "Review Charlie's delegated task."),
        priority: "medium",
        workspace: destContext,
        metadata: { source: "charlie_conversation", ...action.payload },
      }, { onSuccess: markDone, onError: fail });
      return;
    }
    if (action.kind === "widget") {
      materializeWidgets.mutate(
        { actor: "Devarsh via Charlie", include_existing: false, limit: 20 },
        { onSuccess: markDone, onError: fail },
      );
      return;
    }
    if (action.kind === "screen") {
      updateWorkspace.mutate(
        { profile_key: "devarsh", preferences: action.payload },
        { onSuccess: markDone, onError: fail },
      );
      return;
    }
    if (action.kind === "navigate" && typeof action.payload.path === "string") {
      navigate(action.payload.path);
      markDone();
    }
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  if (!open) return null;

  const scopeName = scope === "charlie" ? "Charlie" : scope.agentName;
  const scopeInitials = scope === "charlie" ? "CM" : initials(scope.agentName);
  const scopeRole = text(scopeProfile ?? {}, "display_title", scope === "charlie" ? "Chief of Staff · Orchestrator" : "Investment office employee");
  const scopeState = text(scopeProfile ?? {}, "live_state", "ready");
  const scopeRoute = text(scopeProfile ?? {}, "primary_route", ROUTE_CONFIG[route].routeName);

  return (
    <>
      <style>{AssistantRailCss}</style>
      <aside className="aios-assistant" role="complementary" aria-label="Charlie assistant">
        {/* Header */}
        <div className="aios-assistant__head">
          <div className="aios-assistant__identity">
            <div className="aios-assistant__avatar">
              {scopeInitials}
              <span className="aios-assistant__avatar-status" />
            </div>
            <div>
              <div className="aios-assistant__name">{scopeName}</div>
              <div className="aios-assistant__role">
                {scopeRole}
              </div>
            </div>
          </div>
          <button
            className="aios-assistant__collapse"
            onClick={() => setMessages([])}
            aria-label="Clear this conversation"
            title="Clear this conversation"
          >
            <Trash2 size={15} />
          </button>
          <button
            className="aios-assistant__collapse"
            onClick={() => setOpen(false)}
            aria-label="Collapse assistant"
          >
            <PanelRightClose size={16} />
          </button>
        </div>

        {/* Context strip */}
        <div className="aios-assistant__context">
          <span className="micro">Context</span>
          <span className="aios-assistant__context-dest">{destContext}</span>
          <span style={{ marginLeft: "auto", fontSize: "var(--text-2xs)", color: "var(--text-muted)" }}>{scopeState} · {scopeRoute.replace(/_/g, " ")}</span>
        </div>

        {/* Messages */}
        <div className="aios-assistant__messages" ref={scrollRef}>
          {messages.length === 0 && (
            <div className="aios-assistant__welcome">
              <Sparkles size={28} />
              <div className="aios-assistant__welcome-title">
                {scope === "charlie"
                  ? "Good to see you. What's on your mind?"
                  : `Ready to dig in — ask me anything.`}
              </div>
              <div className="aios-assistant__welcome-sub">
                {scope === "charlie"
                  ? "Tell me what you need. I can answer, retrieve evidence, delegate real work, create research intakes, and track the result."
                  : text(scopeProfile ?? {}, "human_interface", text(scopeProfile ?? {}, "role_scope", "Ask for evidence-linked work within this employee's mandate."))}
              </div>
              <div className="aios-assistant__quick">
                {QUICK_ACTIONS.map((qa) => (
                  <button
                    key={qa.label}
                    className="aios-assistant__quick-btn"
                    onClick={() => send(qa.label)}
                    disabled={assistantPending}
                  >
                    <qa.icon size={13} />
                    {qa.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <MessageBubble key={msg.id} msg={msg} onEvidence={openEvidence} onAction={executeAction} />
          ))}

          {assistantPending && (
            <div className="aios-assistant__typing">
              <span /> <span /> <span />
            </div>
          )}
        </div>

        {/* Reasoning route selector */}
        <div className="aios-assistant__routes">
          {ROUTES.map((r) => (
            <button
              key={r.key}
              className={`aios-assistant__route ${route === r.key ? "aios-assistant__route--active" : ""}`}
              onClick={() => setRoute(r.key)}
              title={r.desc}
            >
              <r.icon size={12} />
              {r.label}
            </button>
          ))}
        </div>

        {/* Input */}
        <div className="aios-assistant__input-wrap">
          <textarea
            className="aios-assistant__input"
            placeholder={`Message ${scopeName}…`}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            disabled={assistantPending}
          />
          <button
            className="aios-assistant__send"
            onClick={() => send(input)}
            disabled={!input.trim() || assistantPending}
            aria-label="Send message"
          >
            <Send size={14} />
          </button>
        </div>
      </aside>
    </>
  );
}

function MessageBubble({
  msg,
  onEvidence,
  onAction,
}: {
  msg: ChatMessage;
  onEvidence: (t: { kind: string; key: string; title: string }) => void;
  onAction: (action: AssistantAction) => void;
}) {
  if (msg.role === "system") {
    return (
      <div className="aios-assistant__msg aios-assistant__msg--system">
        {msg.content}
      </div>
    );
  }
  return (
    <div className={`aios-assistant__msg aios-assistant__msg--${msg.role}`}>
      <div className="aios-assistant__msg-content">{msg.content}</div>
      {msg.evidence && msg.evidence.length > 0 && (
        <div className="aios-assistant__evidence">
          <span className="micro">Evidence</span>
          <div className="aios-assistant__evidence-chips">
            {msg.evidence.map((ev, i) => (
              <button
                key={i}
                className="aios-assistant__evidence-chip"
                onClick={() => onEvidence({ kind: ev.kind, key: ev.key, title: ev.label })}
              >
                {ev.label}
              </button>
            ))}
          </div>
        </div>
      )}
      {msg.route && (
        <div className="aios-assistant__msg-meta">
          via {msg.route} · {formatRelative(new Date(msg.ts).toISOString())}
        </div>
      )}
      {msg.operations && msg.operations.length > 0 && (
        <div className="aios-assistant__evidence">
          <span className="micro">Office actions</span>
          <div className="aios-assistant__evidence-chips">
            {msg.operations.map((operation, index) => (
              <span key={`${operation.tool}-${index}`} className="aios-assistant__evidence-chip" title={operation.detail}>
                {operation.tool.replace(/_/g, " ")} · {operation.status}
              </span>
            ))}
          </div>
        </div>
      )}
      {msg.actions && msg.actions.length > 0 && (
        <div className="aios-assistant__actions">
          {msg.actions.map((action) => (
            <button
              key={action.id}
              className="aios-assistant__action"
              onClick={() => onAction(action)}
              disabled={action.executed}
              title={action.description}
            >
              <Sparkles size={12} />
              <span className="aios-assistant__action-copy"><strong>{action.executed ? "Accepted" : action.label}</strong>{action.description ? <small>{action.description}</small> : null}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
