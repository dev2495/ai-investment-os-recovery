import React from "react";
import { ExternalLink, MessageCircle, Send, X } from "lucide-react";
import type { OfficeSnapshot } from "../../data/schemas";
import type { LiveRow } from "../../data/liveRow";
import { formatCurrency, formatRelative, num, raw, text } from "../../data/liveRow";
import { hasLiveLease, runtimePresence, useLeaseClock } from "../../data/runtimePresence";
import { useControlAgentTask, useDelegateAgentTask } from "../../data/actions";
import { useUIStore } from "../../store";
import { Button, StatusPill } from "../../system/primitives";
import { LivingAgentPanelCss } from "./LivingAgentPanel.css";

type DetailKey =
  | "task_steps"
  | "agent_handoffs"
  | "agent_sources"
  | "agent_artifacts"
  | "agent_model_calls"
  | "agent_tool_calls"
  | "agent_approvals"
  | "agent_incidents"
  | "agent_routines"
  | "agent_scorecards";

export type LivingAgentContext = Pick<OfficeSnapshot,
  | "generated_at"
  | "agent_messages"
  | "priority_tasks"
  | "runtime"
  | DetailKey
>;

export interface LivingAgentPanelProps {
  agent: LiveRow;
  context?: Partial<LivingAgentContext>;
  variant?: "surface" | "overlay";
  lowPower?: boolean;
  onClose?: () => void;
  onTalk?: (agent: LiveRow) => void;
  onInspectTask?: (agent: LiveRow) => void;
  onOpenWorkspace?: (agent: LiveRow) => void;
}

function firstText(row: LiveRow | null | undefined, keys: string[]): string {
  for (const key of keys) {
    const candidate = raw(row, key);
    if (candidate !== null && candidate !== undefined && String(candidate).trim()) return String(candidate).trim();
  }
  return "";
}

function firstNumber(row: LiveRow | null | undefined, keys: string[]): number | null {
  for (const key of keys) {
    const candidate = raw(row, key);
    if (candidate === null || candidate === undefined || candidate === "") continue;
    const parsed = Number(candidate);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function isRedacted(row: LiveRow): boolean {
  return text(row, "office_visibility") === "redacted";
}

function belongsToAgent(row: LiveRow, agentName: string, taskId: number): boolean {
  const directKeys = ["agent_name", "owner_agent", "to_agent", "from_agent", "assigned_agent", "requested_by_agent"];
  if (directKeys.some((key) => text(row, key) === agentName)) return true;
  if (!taskId) return false;
  return ["task_id", "related_task_id", "parent_task_id", "child_task_id"].some((key) => num(row, key) === taskId);
}

function relatedRows(rows: LiveRow[] | undefined, agentName: string, taskId: number): LiveRow[] {
  return (rows ?? []).filter((row) => belongsToAgent(row, agentName, taskId));
}

function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds < 0) return "Not recorded";
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${minutes}m`;
}

function elapsedSeconds(agent: LiveRow, task: LiveRow): number | null {
  const recorded = firstNumber(agent, ["elapsed_seconds", "task_elapsed_seconds"])
    ?? firstNumber(task, ["elapsed_seconds", "duration_seconds"]);
  if (recorded !== null) return recorded;
  const startedAt = firstText(agent, ["current_step_started_at", "presence_started_at", "current_task_started_at"])
    || firstText(task, ["started_at"]);
  const started = Date.parse(startedAt);
  return Number.isFinite(started) ? Math.max(0, (Date.now() - started) / 1000) : null;
}

function display(value: string): string {
  return value || "Not recorded";
}

function rowTitle(row: LiveRow, fallback: string): string {
  return firstText(row, ["title", "name", "subject", "step_key", "artifact_name", "source_name", "routine_name", "model", "tool_name"]) || fallback;
}

function RecordList({ rows, empty, fallback }: { rows: LiveRow[]; empty: string; fallback: string }) {
  if (rows.length === 0) return <div className="living-agent-panel__empty">{empty}</div>;
  return (
    <div className="living-agent-panel__records">
      {rows.slice(0, 4).map((row, index) => {
        const detail = firstText(row, ["summary", "detail", "state", "status", "source_kind", "event_type"]);
        const at = firstText(row, ["occurred_at", "created_at", "updated_at", "started_at"]);
        return (
          <div className="living-agent-panel__record" key={String(raw(row, "id") ?? raw(row, "key") ?? `${fallback}-${index}`)}>
            <strong>{rowTitle(row, fallback)}</strong>{detail ? ` · ${detail}` : ""}
            {at && <time dateTime={at}>{formatRelative(at)}</time>}
          </div>
        );
      })}
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  const missing = !value;
  return (
    <div className="living-agent-panel__fact">
      <span className="living-agent-panel__label">{label}</span>
      <b className={missing ? "is-missing" : undefined}>{display(value)}</b>
    </div>
  );
}

export function LivingAgentPanel({
  agent,
  context,
  variant = "surface",
  lowPower = false,
  onClose,
  onTalk,
  onInspectTask,
  onOpenWorkspace,
}: LivingAgentPanelProps) {
  useLeaseClock();
  const delegateTask = useDelegateAgentTask();
  const controlTask = useControlAgentTask();
  const [control, setControl] = React.useState<"pause" | "resume" | "cancel" | "redirect" | null>(null);
  const [redirectObjective, setRedirectObjective] = React.useState("");
  const pushToast = useUIStore((state) => state.pushToast);
  const panelRef = React.useRef<HTMLElement>(null);
  const [showDelegate, setShowDelegate] = React.useState(false);
  const [objective, setObjective] = React.useState("");
  const agentName = text(agent, "agent_name", "Unnamed agent");
  const taskId = num(agent, "current_task_id");
  const runtimeTasks = Array.isArray(context?.runtime?.tasks) ? context?.runtime?.tasks as LiveRow[] : [];
  const task = [...(context?.priority_tasks ?? []), ...runtimeTasks].find((row) => num(row, "id") === taskId) ?? {};
  const steps = relatedRows(context?.task_steps, agentName, taskId);
  const messages = relatedRows(context?.agent_messages, agentName, taskId);
  const handoffs = relatedRows(context?.agent_handoffs, agentName, taskId);
  const sources = relatedRows(context?.agent_sources, agentName, taskId);
  const artifacts = relatedRows(context?.agent_artifacts, agentName, taskId);
  const modelCalls = relatedRows(context?.agent_model_calls, agentName, taskId);
  const toolCalls = relatedRows(context?.agent_tool_calls, agentName, taskId);
  const approvals = relatedRows(context?.agent_approvals, agentName, taskId);
  const incidents = relatedRows(context?.agent_incidents, agentName, taskId);
  const routines = relatedRows(context?.agent_routines, agentName, taskId);
  const scorecards = relatedRows(context?.agent_scorecards, agentName, taskId);
  const latestStep = steps[0] ?? {};
  const latestModel = modelCalls[0] ?? {};
  const latestTool = toolCalls[0] ?? {};
  const latestArtifact = artifacts[0] ?? {};
  const nextRoutine = routines[0] ?? {};
  const presence = runtimePresence(agent);
  const live = hasLiveLease(agent);
  const blocked = presence.toLowerCase().includes("block") || num(agent, "blocked_task_count") > 0;
  const stale = presence === "STALE";
  const progress = firstNumber(agent, ["progress_percent", "task_progress_percent"])
    ?? firstNumber(task, ["progress_percent"]);
  const boundedProgress = progress === null ? null : Math.max(0, Math.min(100, progress));
  const leaseExpiry = firstText(agent, ["lease_expires_at", "expires_at"]);
  const currentTask = isRedacted(agent)
    ? "Private scoped assignment"
    : firstText(agent, ["current_task_title", "current_work_title", "presence_title"])
      || firstText(task, ["title", "objective"]);
  const currentStep = firstText(agent, ["current_step_title", "current_step_key"])
    || firstText(latestStep, ["title", "step_key"]);
  const scope = isRedacted(agent) ? "Private scoped work" : firstText(agent, ["scope_ref", "company_symbol", "strategy_name", "portfolio_name", "book_name"]);
  const route = firstText(agent, ["resolved_model_route", "latest_model_route"])
    || firstText(latestModel, ["resolved_route", "model_route"]);
  const model = firstText(agent, ["current_model", "latest_model", "assigned_model"])
    || firstText(latestModel, ["resolved_model", "model"]);
  const tool = firstText(agent, ["current_tool", "latest_tool_name"])
    || firstText(latestTool, ["tool_name", "tool_key"]);
  const sourceCount = firstNumber(agent, ["source_count", "current_source_count"])
    ?? firstNumber(task, ["source_count"])
    ?? (sources.length ? sources.length : null);
  const taskCost = firstNumber(agent, ["task_cost_inr", "current_task_cost_inr"])
    ?? firstNumber(task, ["task_cost_inr", "cost_inr"]);
  const blocker = firstText(agent, ["blocker_title", "blocker_reason", "presence_reason"])
    || firstText(task, ["blocker_title", "blocker_reason"])
    || (incidents.length ? rowTitle(incidents[0], "Recorded incident") : "");
  const artifact = firstText(agent, ["last_artifact_title", "latest_artifact_title"])
    || rowTitle(latestArtifact, "");
  const routine = firstText(agent, ["next_routine", "next_routine_name"])
    || rowTitle(nextRoutine, "");

  React.useEffect(() => {
    panelRef.current?.focus();
  }, [agentName]);

  React.useEffect(() => {
    setShowDelegate(false);
    setObjective("");
    setControl(null);
    setRedirectObjective("");
  }, [agentName]);

  function submitControl() {
    if (!control || !taskId) return;
    controlTask.mutate({ taskId, action: control, objective: redirectObjective.trim() }, {
      onSuccess: (receipt) => {
        pushToast({ title: `Task #${taskId}: ${control} recorded`, message: raw(receipt, "waiting_for_safe_boundary") === true ? "The worker will apply this change at its next safe boundary." : "The server returned the task control receipt.", tone: "ok", duration: 5000 });
        setControl(null);
        setRedirectObjective("");
      },
      onError: (error) => pushToast({ title: "Task control could not be applied", message: error.message, tone: "risk", duration: 6000 }),
    });
  }

  function submitDelegation() {
    const trimmed = objective.trim();
    if (!trimmed) return;
    delegateTask.mutate({
      to_agent: agentName,
      objective: trimmed,
      priority: "high",
      workspace: text(agent, "department_key", text(agent, "department", "office")),
      actor: "Devarsh",
    }, {
      onSuccess: (result) => {
        pushToast({
          title: `Task queued to ${agentName}`,
          message: `Task #${num(result, "task_id")} is durable and visible in the Office.`,
          tone: "ok",
          duration: 5000,
        });
        setShowDelegate(false);
        setObjective("");
      },
      onError: (error) => pushToast({ title: "Delegation failed", message: error.message, tone: "risk", duration: 6000 }),
    });
  }

  return (
    <>
      <style>{LivingAgentPanelCss}</style>
      <section
        ref={panelRef}
        className={`living-agent-panel living-agent-panel--${variant}`}
        data-low-power={lowPower}
        tabIndex={-1}
        aria-label={`${agentName} agent inspector`}
        onKeyDown={(event) => {
          if (event.key === "Escape" && onClose) {
            event.preventDefault();
            onClose();
          }
        }}
      >
        <header className="living-agent-panel__head">
          <div className="living-agent-panel__identity">
            <div className="living-agent-panel__eyebrow">{text(agent, "department_name", text(agent, "department", "Unassigned"))}</div>
            <h3 className="living-agent-panel__name">{agentName}</h3>
            <div className="living-agent-panel__role">{display(firstText(agent, ["display_title", "role_scope"]))}</div>
          </div>
          <div className="living-agent-panel__head-actions">
            <StatusPill status={presence} dot pulse={live && !lowPower}>{presence.replace(/_/g, " ")}</StatusPill>
            {onClose && <Button size="sm" variant="ghost" icon={X} aria-label="Close agent inspector" onClick={onClose}>Close</Button>}
          </div>
        </header>

        <div className={`living-agent-panel__lease ${live ? "is-live" : blocked ? "is-blocked" : stale ? "is-stale" : ""}`} role="status" aria-live="polite">
          <strong>{live ? "Live worker lease" : stale ? "Worker lease expired" : blocked ? "Blocked" : "Runtime not verified"}</strong>
          <span>{live ? "Working state is backed by an unexpired lease." : stale ? "Refresh before treating this agent as idle or complete." : blocked ? display(blocker) : "No live worker lease is recorded for this agent."}</span>
          <time dateTime={leaseExpiry || undefined}>{leaseExpiry ? `expires ${formatRelative(leaseExpiry)}` : "expiry not recorded"}</time>
        </div>

        <div className="living-agent-panel__work">
          <div className="living-agent-panel__assignment">
            <span className="living-agent-panel__label">Current assignment</span>
            <strong>{display(currentTask)}</strong>
            <p><b>Step:</b> {display(currentStep)}{scope ? ` · Scope: ${scope}` : " · Scope: Not recorded"}</p>
          </div>
          <div className="living-agent-panel__progress-block">
            <div className="living-agent-panel__progress-head"><span>Recorded progress</span><strong>{boundedProgress === null ? "Not recorded" : `${Math.round(boundedProgress)}%`}</strong></div>
            {boundedProgress !== null && <div className="living-agent-panel__progress" role="progressbar" aria-label="Recorded task progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(boundedProgress)}><span style={{ width: `${boundedProgress}%` }} /></div>}
            <div className="living-agent-panel__progress-meta">
              <span>Elapsed<b>{formatDuration(elapsedSeconds(agent, task))}</b></span>
              <span>Task ID<b>{taskId ? `#${taskId}` : "Not recorded"}</b></span>
            </div>
          </div>
        </div>

        <div className="living-agent-panel__facts" aria-label="Agent task facts">
          <Fact label="Resolved route" value={route} />
          <Fact label="Model" value={model} />
          <Fact label="Current tool" value={tool} />
          <Fact label="Sources" value={sourceCount === null ? "" : String(sourceCount)} />
          <Fact label="Task cost" value={taskCost === null ? "" : formatCurrency(taskCost, "INR", { maximumFractionDigits: 2 })} />
          <Fact label="Blocker" value={blocker} />
          <Fact label="Last artifact" value={artifact} />
          <Fact label="Next routine" value={routine} />
        </div>

        <div className="living-agent-panel__sections">
          <details className="living-agent-panel__section">
            <summary>Messages and handoffs <span>{messages.length + handoffs.length || "none"}</span></summary>
            <RecordList rows={[...messages, ...handoffs]} empty="No recorded messages or handoffs for this agent." fallback="Recorded handoff" />
          </details>
          <details className="living-agent-panel__section">
            <summary>Sources and artifacts <span>{sources.length + artifacts.length || "none"}</span></summary>
            <RecordList rows={[...sources, ...artifacts]} empty="No agent-linked sources or artifacts were returned." fallback="Recorded evidence" />
          </details>
          <details className="living-agent-panel__section">
            <summary>Model and tool calls <span>{modelCalls.length + toolCalls.length || "none"}</span></summary>
            <RecordList rows={[...modelCalls, ...toolCalls]} empty="No model or tool-call records were returned." fallback="Recorded call" />
          </details>
          <details className="living-agent-panel__section">
            <summary>Approvals, incidents and scorecard <span>{approvals.length + incidents.length + scorecards.length || "none"}</span></summary>
            <RecordList rows={[...approvals, ...incidents, ...scorecards]} empty="No approvals, incidents or scorecard records were returned." fallback="Recorded operation" />
          </details>
        </div>

        <div className="living-agent-panel__actions">
          {onTalk && <Button variant="primary" icon={MessageCircle} onClick={() => onTalk(agent)}>Talk to {agentName}</Button>}
          <Button icon={Send} onClick={() => setShowDelegate((open) => !open)} aria-expanded={showDelegate}>Delegate task</Button>
          {isRedacted(agent)
            ? onOpenWorkspace && <Button icon={ExternalLink} onClick={() => onOpenWorkspace(agent)}>Open private workspace</Button>
            : taskId > 0 && onInspectTask && <Button icon={ExternalLink} onClick={() => onInspectTask(agent)}>Inspect task</Button>}
          {!isRedacted(agent) && onOpenWorkspace && <Button variant="ghost" onClick={() => onOpenWorkspace(agent)}>Open department</Button>}
        </div>

        {!isRedacted(agent) && taskId > 0 && !["completed", "cancelled", "canceled", "superseded"].includes(text(task, "status").toLowerCase()) && (
          <div className="living-agent-panel__delegate" aria-label="Task controls">
            <div className="living-agent-panel__actions">
              {(["pause", "resume", "cancel", "redirect"] as const).map((action) => <Button key={action} size="sm" disabled={controlTask.isPending} onClick={() => setControl(action)}>{action[0].toUpperCase() + action.slice(1)} task</Button>)}
            </div>
            {control && <div>
              <p>{control === "redirect" ? "Update the objective using primary sources only. An active worker applies the change at its next safe boundary." : `Apply ${control} to task #${taskId}? The server checks its current state before changing it.`}</p>
              {control === "redirect" && <label>Updated objective<textarea aria-label="Updated objective" value={redirectObjective} onChange={(event) => setRedirectObjective(event.target.value)} rows={3} /></label>}
              <div className="living-agent-panel__actions"><Button variant="primary" disabled={controlTask.isPending || (control === "redirect" && !redirectObjective.trim())} onClick={submitControl}>Confirm {control}</Button><Button variant="ghost" onClick={() => setControl(null)}>Keep current task</Button></div>
            </div>}
          </div>
        )}

        {showDelegate && (
          <div className="living-agent-panel__delegate">
            <label className="living-agent-panel__label" htmlFor={`agent-delegate-${agentName.replace(/[^a-z0-9]/gi, "-")}`}>Assignment for {agentName}</label>
            <textarea
              id={`agent-delegate-${agentName.replace(/[^a-z0-9]/gi, "-")}`}
              value={objective}
              onChange={(event) => setObjective(event.target.value)}
              placeholder="State the exact deliverable, evidence required, and review gate."
              rows={3}
            />
            <div className="living-agent-panel__actions">
              <Button variant="primary" disabled={!objective.trim() || delegateTask.isPending} onClick={submitDelegation}>{delegateTask.isPending ? "Queuing…" : "Queue assignment"}</Button>
              <Button variant="ghost" onClick={() => setShowDelegate(false)}>Cancel</Button>
            </div>
          </div>
        )}
      </section>
    </>
  );
}
