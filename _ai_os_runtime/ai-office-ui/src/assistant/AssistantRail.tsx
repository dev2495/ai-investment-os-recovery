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
  Lightbulb,
} from "lucide-react";
import { useUIStore } from "../store";
import { useChat } from "../data/queries";
import {
  useProposeArchitectureChange,
  useUpdateWorkspaceConfig,
  useCreateAgentMessage,
  useMaterializeWidgets,
} from "../data/actions";
import { AssistantRailCss } from "./AssistantRail.css";
import { text, formatRelative, initials } from "../data/liveRow";
import type { LiveRow } from "../data/liveRow";
import { useNavigate } from "react-router-dom";

type ReasoningRoute = "local" | "fast" | "deep" | "review";

/** An actionable proposal Charlie surfaces — governance, delegation, screen change. */
interface AssistantAction {
  id: string;
  kind: "governance" | "delegate" | "screen" | "widget" | "evidence_open" | "navigate";
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
  ts: number;
}

const ROUTES: Array<{ key: ReasoningRoute; label: string; icon: typeof Brain; desc: string }> = [
  { key: "local", label: "Local", icon: Brain, desc: "Deterministic, on-device, private" },
  { key: "fast", label: "Fast", icon: Zap, desc: "Quick governed model" },
  { key: "deep", label: "Deep", icon: Microscope, desc: "Thorough, retrieval-augmented" },
  { key: "review", label: "Review", icon: ClipboardCheck, desc: "Adversarial self-check" },
];

const QUICK_ACTIONS = [
  { label: "What do I need to decide today?", icon: ClipboardCheck },
  { label: "Summarize my portfolio risk", icon: Brain },
  { label: "What's fresh in research?", icon: Lightbulb },
  { label: "Show me the latest breaches", icon: Zap },
  { label: "Propose a new screen for the firm", icon: Sparkles },
];

export function AssistantRail() {
  const open = useUIStore((s) => s.assistantOpen);
  const setOpen = useUIStore((s) => s.setAssistantOpen);
  const scope = useUIStore((s) => s.assistantScope);
  const openEvidence = useUIStore((s) => s.openEvidence);

  const location = useLocation();
  const chat = useChat();

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
    window.localStorage.setItem("aios:charlie-conversation", JSON.stringify(messages.slice(-80)));
  }, [messages]);

  /** Auto-scroll to bottom on new message. */
  React.useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, chat.isPending]);

  function send(message: string) {
    const trimmed = message.trim();
    if (!trimmed || chat.isPending) return;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: trimmed,
      ts: Date.now(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");

    const scopedAgent = scope === "charlie" ? "Charlie Munger" : scope.agentName;
    const scopedMessage = scope === "charlie" ? trimmed : `Act as ${scope.agentName}, the requested specialist. Coordinate through Charlie and answer with source-backed evidence. User request: ${trimmed}`;
    const routeName = route === "local" ? "charlie_munger_orchestration" : route;
    chat.mutate(
      {
        message: scopedMessage,
        session_key: "devarsh-charlie-primary",
        actor: "Devarsh",
        workspace: destContext.toLowerCase().replace(/[^a-z]/g, "_"),
        route_name: routeName,
        deterministic_only: route === "local",
        include_client_context: true,
        privacy_class: "private_investment_office",
        contains_client_data: destContext === "Portfolio",
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

          // Tool intents → governance proposals (e.g. "add a new agent")
          for (const intent of data.tool_intents ?? []) {
            const toolName = text(intent, "tool_name", text(intent, "name", ""));
            const reason = text(intent, "reason", text(intent, "description", ""));
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

          // Agent jobs → delegation proposals (dispatch to a specialist)
          for (const job of data.agent_jobs ?? []) {
            const agent = text(job, "agent_key", text(job, "to_agent", "specialist"));
            const task = text(job, "task_name", text(job, "workflow_key", "delegated task"));
            actions.push({
              id: `act-${Date.now()}-${actions.length}`,
              kind: "delegate",
              label: `Delegate to ${agent}`,
              description: task,
              payload: { to_agent: agent, task_name: task, raw: job },
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

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  if (!open) return null;

  const scopeName = scope === "charlie" ? "Charlie" : scope.agentName;
  const scopeInitials = scope === "charlie" ? "CM" : initials(scope.agentName);

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
                {scope === "charlie" ? "Chief of Staff · Orchestrator" : "Specialist agent"}
              </div>
            </div>
          </div>
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
                I can pull evidence, surface decisions, delegate to departments, and route approvals.
              </div>
              <div className="aios-assistant__quick">
                {QUICK_ACTIONS.map((qa) => (
                  <button
                    key={qa.label}
                    className="aios-assistant__quick-btn"
                    onClick={() => send(qa.label)}
                    disabled={chat.isPending}
                  >
                    <qa.icon size={13} />
                    {qa.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <MessageBubble key={msg.id} msg={msg} onEvidence={openEvidence} />
          ))}

          {chat.isPending && (
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
            disabled={chat.isPending}
          />
          <button
            className="aios-assistant__send"
            onClick={() => send(input)}
            disabled={!input.trim() || chat.isPending}
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
}: {
  msg: ChatMessage;
  onEvidence: (t: { kind: string; key: string; title: string }) => void;
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
    </div>
  );
}
