/**
 * Today — your personal home screen
 *
 * Not a wall of panels. A curated briefing FOR YOU:
 *   1. Hero strip — NAV, exposure, breaches, approvals, freshness
 *   2. Ask Charlie bar — natural-language command surface (front and center)
 *   3. Needs Your Decision — the approval spine
 *   4. Your Watchlist — symbols you're tracking, with delta + thesis link
 *   5. Ideas to Review — research/quant ideas awaiting your read
 *   6. Research Ready Overnight — theses, specialist outputs, filings completed
 *   7. What Matters Now — prioritized news/events
 *   8. Freshness alerts — stale data sources
 */

import React from "react";
import {
  Sparkles, Gavel, Send, Newspaper, AlertTriangle, Clock, CheckCircle2, Inbox, ExternalLink,
  Star, Lightbulb, BookOpen, FileText, ChevronRight, Activity, ListTodo,
  UserRoundCog, ShieldCheck, RotateCcw,
} from "lucide-react";
import { useMissionControl, useResearchIdeas } from "../../data/queries";
import { useDelegateAgentTask, useUpdateInboxItem } from "../../data/actions";
import { useUIStore } from "../../store";
import {
  Panel, MetricTile, Metric, Badge, StatusPill, ScrollList, Empty, Skeleton, Button,
  Field, Select, TextArea,
} from "../../system/primitives";
import { text, num, bool, timestamp, formatRelative, formatCompact, formatPercent } from "../../data/liveRow";
import { TodayCss } from "./Today.css";
import type { LiveRow } from "../../data/liveRow";

const QUICK_COMMANDS = [
  "Give me my morning brief",
  "What changed in my portfolio overnight?",
  "Show me options opportunities in NIFTY",
  "Scan for momentum setups today",
  "What research is ready for me to review?",
  "Start research on USHAMART",
];

export default function TodayDestination() {
  const { data: mission, isLoading, error } = useMissionControl();
  const { data: research } = useResearchIdeas();
  const openEvidence = useUIStore((s) => s.openEvidence);
  const setAssistantScope = useUIStore((s) => s.setAssistantScope);
  const setAssistantOpen = useUIStore((s) => s.setAssistantOpen);

  function askCharlie(q: string) {
    setAssistantScope("charlie");
    setAssistantOpen(true);
    window.dispatchEvent(new CustomEvent("aios:assistant-send", { detail: q }));
  }

  if (error) {
    return (
      <div className="aios-destination">
        <style>{TodayCss}</style>
        <Panel variant="risk" icon={AlertTriangle} title="Cannot reach mission control">
          <div style={{ padding: "var(--space-4)", color: "var(--text-muted)" }}>
            {error.message}. The API server may be starting up or the warehouse (Docker/Postgres) may be down.
            <div style={{ marginTop: "var(--space-3)" }}>
              <Button size="sm" onClick={() => window.location.reload()}>Retry</Button>
            </div>
          </div>
        </Panel>
      </div>
    );
  }

  return (
    <>
      <style>{TodayCss}</style>
      <div className="aios-destination">
        {/* Header */}
        <div className="aios-destination__head">
          <div className="aios-destination__title-row">
            <div className="aios-destination__title">Good day, Devarsh</div>
            <Badge tone="accent" dot pulse>
              {mission ? formatRelative(mission.generated_at) : "loading"}
            </Badge>
          </div>
          <div className="aios-destination__subtitle">Your personal briefing — decisions, watchlist, ideas, and what the office did overnight.</div>
        </div>

        {/* Hero metrics */}
        <HeroStrip mission={mission} loading={isLoading} />

        {/* Charlie command bar */}
        <Panel icon={Sparkles} title="Ask Charlie" bodyFlush>
          <div className="aios-today__charlie-bar">
            <input
              className="aios-today__charlie-input"
              placeholder="Ask Charlie, or say: Start research on <company / ticker / idea>…"
              onKeyDown={(e) => { if (e.key === "Enter") { const v = (e.target as HTMLInputElement).value.trim(); if (v) askCharlie(v); (e.target as HTMLInputElement).value = ""; } }}
            />
            <button className="aios-today__charlie-send" onClick={() => { const el = document.querySelector<HTMLInputElement>(".aios-today__charlie-input"); const v = el?.value.trim(); if (v) { askCharlie(v); if (el) el.value = ""; } }}>
              <Send size={14} /> Ask
            </button>
          </div>
          <div className="aios-today__quick-cmds">
            {QUICK_COMMANDS.map((cmd) => (
              <button key={cmd} className="aios-today__quick-cmd" onClick={() => askCharlie(cmd)}>{cmd}</button>
            ))}
          </div>
        </Panel>

        <CompanyResearch mission={mission} loading={isLoading} onAsk={askCharlie} />

        <ThesisMaterialFeed mission={mission} loading={isLoading} />

        <DelegationPanel mission={mission} loading={isLoading} />

        <div className="aios-today__grid">
          <div className="aios-today__col">
            <WorkQueue mission={mission} loading={isLoading} onOpenEvidence={openEvidence} />
            <NeedsDecision mission={mission} loading={isLoading} onOpenEvidence={openEvidence} />
            <Watchlist mission={mission} research={research} loading={isLoading} onOpenEvidence={openEvidence} onAsk={askCharlie} />
          </div>

          <div className="aios-today__col">
            <AutonomousResearchRuns mission={mission} loading={isLoading} />
            <AgentActivity mission={mission} loading={isLoading} onOpenEvidence={openEvidence} />
            <FreshnessAlerts mission={mission} loading={isLoading} />
            <IdeasToReview research={research} loading={isLoading} onOpenEvidence={openEvidence} onAsk={askCharlie} />
            <ResearchReady research={research} loading={isLoading} onOpenEvidence={openEvidence} />
            <WhatMattersNow mission={mission} loading={isLoading} onOpenEvidence={openEvidence} />
          </div>
        </div>
      </div>
    </>
  );
}


function CompanyResearch({ mission, loading, onAsk }: {
  mission: ReturnType<typeof useMissionControl>["data"];
  loading: boolean;
  onAsk: (q: string) => void;
}) {
  const cases = mission?.research_cases ?? [];
  const attention = cases.filter((row) => ["proposed", "review", "blocked"].includes(text(row, "status"))).length;
  return (
    <Panel
      icon={BookOpen}
      title="Company research"
      actions={<div className="aios-today__research-actions"><Button size="sm" variant="ghost" icon={Sparkles} onClick={() => onAsk("Start long-term research on ")}>New research</Button><a href="/research/cases">View all <ChevronRight size={14}/></a></div>}
    >
      {loading ? <SkeletonRows n={3} /> : cases.length === 0 ? (
        <Empty icon={BookOpen} title="No company research in progress" description="Ask Charlie to start a source-governed company underwrite." />
      ) : <div className="aios-today__case-board">
        <div className="aios-today__case-summary"><strong>{cases.length}</strong><span>open cases</span><i/>{attention ? <><strong>{attention}</strong><span>need your attention</span></> : <span>No case needs a decision</span>}</div>
        <div className="aios-today__case-list">{cases.slice(0, 6).map((row) => {
          const id = num(row, "id"); const total = num(row, "agent_total"); const done = num(row, "agent_done");
          const status = text(row, "status");
          const displayStatus = status === "active" && num(row, "source_count") === 0 ? "awaiting_sources" : status;
          const progress = total ? Math.round((done / total) * 100) : 0;
          return <a href={text(row, "href", `/research/cases?case_id=${id}`)} key={id} className="aios-today__case-row">
            <div className="aios-today__case-company"><span>{text(row, "exchange")}:{text(row, "ticker")}</span><strong>{text(row, "company_name")}</strong></div>
            <div className="aios-today__case-progress"><div><i style={{width: `${progress}%`}}/></div><span>{total ? `${done}/${total} workstreams` : text(row,"status") === "proposed" ? "awaiting explicit start" : `${num(row,"source_count")} sources`}</span></div>
            <div className="aios-today__case-action"><StatusPill status={displayStatus}/><span>{text(row, "next_action")}</span></div>
            <ChevronRight size={16}/>
          </a>;
        })}</div>
      </div>}
    </Panel>
  );
}

function ThesisMaterialFeed({ mission, loading }: {
  mission: ReturnType<typeof useMissionControl>["data"];
  loading: boolean;
}) {
  const items = mission?.thesis_material_feed ?? [];
  return (
    <Panel
      icon={ShieldCheck}
      title="Sourced thesis changes & decisions"
      actions={items.length ? <Badge tone="warn">{items.length} material</Badge> : <Badge tone="ok">clear</Badge>}
    >
      {loading ? <SkeletonRows n={3} /> : items.length === 0 ? (
        <Empty icon={ShieldCheck} title="No material governed change" description="Generic news and unproven summaries are excluded from this feed." />
      ) : (
        <div className="aios-today__thesis-feed">
          {items.map((row, index) => {
            const origin = text(row, "origin_kind", "source");
            const href = text(row, "href", "/fundamental/theses");
            const sourceUrl = text(row, "source_url", "");
            const confidence = row.confidence_pct === null || row.confidence_pct === undefined
              ? "" : num(row, "confidence_pct").toFixed(0) + "% confidence";
            return (
              <article className={"aios-today__thesis-change aios-today__thesis-change--" + origin} key={text(row, "item_key", String(index))}>
                <div className="aios-today__thesis-origin">
                  <Badge tone={origin === "source" ? "accent" : origin === "agent_draft" ? "warn" : "default"}>
                    {origin === "source" ? "source-driven" : origin.replace(/_/g, " ")}
                  </Badge>
                  <StatusPill status={text(row, "severity", text(row, "status", "review"))} />
                </div>
                <a className="aios-today__thesis-main" href={href}>
                  <div className="aios-today__thesis-title">
                    <strong>{text(row, "symbol", "—")}</strong>
                    <span>{text(row, "title", "Research item")}</span>
                    <ChevronRight size={14} />
                  </div>
                  <p>{text(row, "summary", "Exact evidence review required.")}</p>
                  <div className="aios-today__thesis-meta">
                    <span>{text(row, "company_name")}</span>
                    <span>{text(row, "source_name", "governed record")}</span>
                    <span>{text(row, "source_time") ? formatRelative(text(row, "source_time")) : "event-driven"}</span>
                    <span>{text(row, "freshness_status", "unknown freshness")}</span>
                    {confidence ? <span>{confidence}</span> : null}
                  </div>
                </a>
                {sourceUrl ? <a className="aios-today__thesis-source" href={sourceUrl} rel="noreferrer" target="_blank" aria-label={"Open source for " + text(row, "title")}><ExternalLink size={14} />Evidence</a> : null}
              </article>
            );
          })}
        </div>
      )}
    </Panel>
  );
}

/* ============================================================
 * HERO STRIP
 * ============================================================ */
function HeroStrip({ mission, loading }: { mission: ReturnType<typeof useMissionControl>["data"]; loading: boolean }) {
  if (loading || !mission) {
    return (
      <div className="aios-today__hero">
        {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} style={{ height: 88, borderRadius: "var(--radius-md)" }} />)}
      </div>
    );
  }
  const approvals = mission.approvals?.filter((row) =>
    ["pending", "requested", "needs_review"].includes(text(row, "status").toLowerCase())
  ).length ?? 0;
  const breaches = mission.risk_events?.length ?? 0;
  const staleSources = mission.source_freshness?.filter((row) => {
    const status = text(row, "status", text(row, "freshness_status", "")).toLowerCase();
    return ["stale", "aging", "overdue", "error", "missing"].some((flag) => status.includes(flag));
  }).length ?? 0;
  const openWork = mission.inbox?.filter((row) =>
    !["done", "resolved", "closed", "cancelled"].includes(text(row, "status").toLowerCase())
  ).length ?? 0;
  const navRow = mission.metrics?.find((row) => {
    const key = text(row, "metric_key", text(row, "metric", "")).toLowerCase();
    const label = text(row, "label", "").toLowerCase();
    return key.includes("nav") || label.includes("nav");
  });
  const navValue = navRow ? num(navRow, "value") : 0;

  return (
    <div className="aios-today__hero">
      <MetricTile><Metric label="Confirmed NAV" value={navValue > 0 ? formatCompact(navValue, "INR") : "—"} size="lg" sub={navValue > 0 ? "source-backed total" : "awaiting sufficient inputs"} /></MetricTile>
      <MetricTile tone={breaches > 0 ? "risk" : "ok"}>
        <Metric label="Open Risk Events" value={breaches} size="lg" sub={breaches > 0 ? "needs attention" : "no open event"} />
      </MetricTile>
      <MetricTile tone={approvals > 0 ? "warn" : "ok"}>
        <Metric label="Pending Decisions" value={approvals} size="lg" sub={approvals > 0 ? "awaiting you" : "all clear"} />
      </MetricTile>
      <MetricTile tone={openWork > 0 ? "warn" : "ok"}>
        <Metric label="Open Work" value={openWork} size="lg" sub={openWork > 0 ? "tracked in the real inbox" : "queue clear"} />
      </MetricTile>
      <MetricTile tone={staleSources > 0 ? "warn" : "ok"}>
        <Metric label="Feed Attention" value={staleSources} size="lg" sub={staleSources > 0 ? "stale, missing, or failed" : "checks healthy"} />
      </MetricTile>
    </div>
  );
}

const DELEGATION_SCOPES = {
  personal: { label: "Personal workspace", workspace: "command", dataBoundary: "personal_private_local_only" },
  client: { label: "Client portfolio - private", workspace: "portfolio", dataBoundary: "client_private_local_only" },
  market: { label: "Market monitoring", workspace: "market", dataBoundary: "public_or_approved_internal" },
  research: { label: "Research and sources", workspace: "research", dataBoundary: "public_or_approved_internal" },
  strategy: { label: "Strategy design", workspace: "strategy", dataBoundary: "personal_private_local_only" },
  options: { label: "Options analysis - private", workspace: "options", dataBoundary: "trading_private_local_only" },
} as const;

type DelegationScope = keyof typeof DELEGATION_SCOPES;

function DelegationPanel({ mission, loading }: {
  mission: ReturnType<typeof useMissionControl>["data"];
  loading: boolean;
}) {
  const delegate = useDelegateAgentTask();
  const pushToast = useUIStore((state) => state.pushToast);
  const [agent, setAgent] = React.useState("");
  const [scope, setScope] = React.useState<DelegationScope>("personal");
  const [priority, setPriority] = React.useState<"low" | "medium" | "high" | "critical">("high");
  const [objective, setObjective] = React.useState("");
  const targets = mission?.agent_targets ?? [];

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const assignment = DELEGATION_SCOPES[scope];
    if (!agent || !objective.trim()) return;
    delegate.mutate({
      to_agent: agent,
      objective: objective.trim(),
      priority,
      workspace: assignment.workspace,
      data_boundary: assignment.dataBoundary,
      actor: "Devarsh",
    }, {
      onSuccess: (result) => {
        const taskId = num(result, "task_id", 0);
        pushToast({
          title: "Real task queued",
          message: taskId ? `Task ${taskId} is visible in the work queue and audit trail.` : "The assignment is visible in the governed work queue.",
          tone: "ok",
          duration: 4500,
        });
        setObjective("");
      },
      onError: (mutationError) => pushToast({
        title: "Delegation failed",
        message: mutationError.message,
        tone: "risk",
        duration: 6000,
      }),
    });
  }

  return (
    <Panel icon={UserRoundCog} title="Delegate Real Work" actions={<Badge tone="info">governed queue</Badge>}>
      {loading ? <Skeleton style={{ height: 132 }} /> : targets.length === 0 ? (
        <Empty icon={UserRoundCog} title="No active specialists available" description="The employee registry returned no role-scoped agents." />
      ) : (
        <form className="aios-today__delegate-form" onSubmit={submit}>
          <div className="aios-today__delegate-fields">
            <Field label="Specialist" required>
              <Select value={agent} onChange={(event) => setAgent(event.target.value)} aria-label="Specialist agent">
                <option value="">Choose an accountable specialist...</option>
                {targets.map((row, index) => {
                  const agentName = text(row, "agent_name");
                  const title = text(row, "display_title", agentName);
                  const department = text(row, "department_name", "");
                  return <option key={agentName || index} value={agentName}>{title}{department ? ` - ${department}` : ""}</option>;
                })}
              </Select>
            </Field>
            <Field label="Private scope" required>
              <Select value={scope} onChange={(event) => setScope(event.target.value as DelegationScope)} aria-label="Assignment scope">
                {Object.entries(DELEGATION_SCOPES).map(([key, value]) => <option key={key} value={key}>{value.label}</option>)}
              </Select>
            </Field>
            <Field label="Priority" required>
              <Select value={priority} onChange={(event) => setPriority(event.target.value as typeof priority)} aria-label="Assignment priority">
                <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option>
              </Select>
            </Field>
          </div>
          <Field label="Objective" hint="State the outcome, evidence expected, and any deadline." required>
            <TextArea value={objective} onChange={(event) => setObjective(event.target.value)} rows={3} maxLength={4000} placeholder="Example: review today's source failures and prepare a cited recovery brief. Do not change client records or place trades." />
          </Field>
          <div className="aios-today__delegate-footer">
            <div className="aios-today__safety-note"><ShieldCheck size={14} /> Role-scoped and audited. Broker writes and client-record changes remain locked.</div>
            <Button type="submit" variant="primary" icon={Send} disabled={!agent || !objective.trim() || delegate.isPending}>{delegate.isPending ? "Queuing..." : "Delegate"}</Button>
          </div>
        </form>
      )}
    </Panel>
  );
}

function WorkQueue({ mission, loading, onOpenEvidence }: {
  mission: ReturnType<typeof useMissionControl>["data"];
  loading: boolean;
  onOpenEvidence: (target: { kind: string; key: string; title: string }) => void;
}) {
  const updateInbox = useUpdateInboxItem();
  const pushToast = useUIStore((state) => state.pushToast);
  const items = (mission?.inbox ?? []).slice(0, 12);
  const openCount = items.filter((row) => !["done", "resolved", "closed", "cancelled"].includes(text(row, "status").toLowerCase())).length;

  function update(row: LiveRow, action: "claim" | "resolve" | "block" | "reopen") {
    const inboxId = num(row, "id");
    if (!inboxId) return;
    updateInbox.mutate({
      inbox_id: inboxId,
      action,
      actor: "Devarsh",
      resolution_note: action === "resolve" ? "Resolved from the Today command center after human review." : action === "block" ? "Blocked from the Today command center pending evidence or dependency." : undefined,
    }, {
      onSuccess: () => pushToast({ title: `Work item ${action}ed`, tone: "ok", duration: 3000 }),
      onError: (mutationError) => pushToast({ title: "Queue update failed", message: mutationError.message, tone: "risk", duration: 5000 }),
    });
  }

  return (
    <Panel icon={ListTodo} title="Work Queue" actions={openCount ? <Badge tone="warn" dot>{openCount} open</Badge> : <Badge tone="ok">clear</Badge>}>
      {loading ? <SkeletonRows n={4} /> : items.length === 0 ? (
        <Empty icon={Inbox} title="No tracked work" description="Delegate a bounded assignment above; it will appear here with accountable ownership." />
      ) : (
        <ScrollList>
          {items.map((row, index) => {
            const status = text(row, "status", "queued").toLowerCase();
            const title = text(row, "title", `Work item ${index + 1}`);
            const taskId = text(row, "task_id", "");
            const inboxId = num(row, "id");
            const isClosed = ["done", "resolved", "closed", "completed"].includes(status);
            return (
              <div key={inboxId || index} className="aios-today__work-record">
                <button type="button" className="aios-today__work-main" onClick={() => onOpenEvidence({ kind: "task", key: taskId || String(inboxId), title })} disabled={!taskId && !inboxId}>
                  <div className="aios-today__work-title">{title}</div>
                  <div className="aios-today__work-meta">
                    <StatusPill status={status} /><span>{text(row, "owner_agent", "unassigned")}</span><span>{text(row, "target_workspace", "command")}</span><span>{formatRelative(text(row, "updated_at", text(row, "created_at")))}</span>
                  </div>
                </button>
                <div className="aios-today__work-actions">
                  {status === "queued" && <Button size="sm" variant="ghost" onClick={() => update(row, "claim")} disabled={updateInbox.isPending}>Claim</Button>}
                  {isClosed || status === "blocked" ? <Button size="sm" variant="ghost" icon={RotateCcw} onClick={() => update(row, "reopen")} disabled={updateInbox.isPending}>Reopen</Button> : status !== "queued" ? (
                    <><Button size="sm" variant="ghost" onClick={() => update(row, "resolve")} disabled={updateInbox.isPending}>Resolve</Button><Button size="sm" variant="ghost" onClick={() => update(row, "block")} disabled={updateInbox.isPending}>Block</Button></>
                  ) : null}
                </div>
              </div>
            );
          })}
        </ScrollList>
      )}
    </Panel>
  );
}

function AgentActivity({ mission, loading, onOpenEvidence }: {
  mission: ReturnType<typeof useMissionControl>["data"];
  loading: boolean;
  onOpenEvidence: (target: { kind: string; key: string; title: string }) => void;
}) {
  const activity = [
    ...(mission?.agent_worker_runs ?? []).map((row) => ({ row, kind: "run" as const })),
    ...(mission?.agent_messages ?? []).map((row) => ({ row, kind: "message" as const })),
  ].sort((left, right) => {
    const leftAt = Date.parse(text(left.row, "updated_at", text(left.row, "created_at", text(left.row, "started_at", "")))) || 0;
    const rightAt = Date.parse(text(right.row, "updated_at", text(right.row, "created_at", text(right.row, "started_at", "")))) || 0;
    return rightAt - leftAt;
  }).slice(0, 10);
  const failures = activity.filter(({ row }) => {
    const status = text(row, "status", text(row, "run_status", text(row, "processing_status", ""))).toLowerCase();
    return status.includes("fail") || status.includes("error") || Boolean(text(row, "error_message", ""));
  }).length;

  return (
    <Panel icon={Activity} title="Agent Activity" actions={failures ? <Badge tone="risk">{failures} failed</Badge> : <Badge tone="ok">audited</Badge>}>
      {loading ? <SkeletonRows n={4} /> : activity.length === 0 ? (
        <Empty icon={Activity} title="No recorded activity" description="Only real worker runs and agent messages appear here." />
      ) : (
        <ScrollList>
          {activity.map(({ row, kind }, index) => {
            const status = text(row, "run_status", text(row, "processing_status", text(row, "status", "recorded")));
            const title = kind === "message" ? text(row, "subject", "Agent message") : text(row, "task_title", text(row, "workflow_key", "Worker run"));
            const from = text(row, "from_title", text(row, "from_agent", text(row, "agent_name", text(row, "agent_key", "worker"))));
            const to = text(row, "to_title", text(row, "to_agent", ""));
            const evidenceKey = kind === "message" ? text(row, "thread_key", "") : text(row, "task_id", text(row, "id", ""));
            const errorMessage = text(row, "error_message", "");
            return (
              <button type="button" key={`${kind}-${evidenceKey || index}`} className="aios-today__activity-record" onClick={() => evidenceKey && onOpenEvidence({ kind: kind === "message" ? "message_thread" : "task", key: evidenceKey, title })} disabled={!evidenceKey}>
                <div className="aios-today__activity-head"><span>{title}</span><StatusPill status={status} /></div>
                <div className="aios-today__activity-meta">{from}{to ? ` -> ${to}` : ""} · {formatRelative(text(row, "updated_at", text(row, "created_at", text(row, "started_at"))))}</div>
                {errorMessage && <div className="aios-today__activity-error">{errorMessage}</div>}
              </button>
            );
          })}
        </ScrollList>
      )}
    </Panel>
  );
}

/* ============================================================
 * NEEDS YOUR DECISION
 * ============================================================ */
function NeedsDecision({ mission, loading, onOpenEvidence }: {
  mission: ReturnType<typeof useMissionControl>["data"];
  loading: boolean;
  onOpenEvidence: (t: { kind: string; key: string; title: string }) => void;
}) {
  const approvals = mission?.approvals?.filter((row) =>
    ["pending", "requested", "needs_review"].includes(text(row, "status").toLowerCase())
  ) ?? [];
  return (
    <Panel icon={Gavel} title="Needs Your Decision"
      actions={approvals.length > 0 ? <Badge tone="warn" dot pulse>{approvals.length}</Badge> : undefined}
    >
      {loading ? <SkeletonRows n={2} /> : approvals.length === 0 ? (
        <Empty icon={CheckCircle2} title="Nothing pending" description="You're all caught up." />
      ) : (
        <ScrollList>
          {approvals.map((a, i) => {
            const key = String(text(a, "approval_id", text(a, "id", i)));
            const title = text(a, "title", text(a, "subject", text(a, "approval_type", "Approval")));
            return (
              <div key={i} className="aios-today__decision" onClick={() => onOpenEvidence({ kind: "approval", key, title })}>
                <div className="aios-today__decision-icon"><Gavel size={14} /></div>
                <div className="aios-today__decision-main">
                  <div className="aios-today__decision-title">{title}</div>
                  <div className="aios-today__decision-meta">
                    <StatusPill status={text(a, "status", "pending")} />
                    <span>· {formatRelative(text(a, "created_at"))}</span>
                  </div>
                </div>
                <ChevronRight size={14} style={{ color: "var(--text-faint)" }} />
              </div>
            );
          })}
        </ScrollList>
      )}
    </Panel>
  );
}

/* ============================================================
 * YOUR WATCHLIST — the personal tracker
 * ============================================================ */
function Watchlist({ mission, research, loading, onOpenEvidence, onAsk }: {
  mission: ReturnType<typeof useMissionControl>["data"];
  research: ReturnType<typeof useResearchIdeas>["data"];
  loading: boolean;
  onOpenEvidence: (t: { kind: string; key: string; title: string }) => void;
  onAsk: (q: string) => void;
}) {
  const watchlist = mission?.watchlist ?? research?.watchlist ?? [];
  return (
    <Panel icon={Star} title="Your Watchlist"
      actions={<Button size="sm" variant="ghost" icon={Sparkles} onClick={() => onAsk("Suggest 3 symbols to add to my watchlist based on current research")}>Suggest</Button>}
    >
      {loading ? <SkeletonRows n={3} /> : watchlist.length === 0 ? (
        <Empty icon={Star} title="Watchlist empty" description="Tell Charlie to add symbols, or use the Fundamental Idea Generator." />
      ) : (
        <ScrollList>
          {watchlist.map((row, i) => {
            const symbol = text(row, "symbol");
            const itemType = text(row, "item_type", "research");
            const priority = text(row, "priority", "medium");
            const thesis = text(row, "thesis", "");
            const catalyst = text(row, "catalyst", "");
            const reviewOn = text(row, "review_on", "");
            return (
              <div key={i} className="aios-today__watch-item" onClick={() => onOpenEvidence({ kind: "strategy", key: String(text(row, "id", i)), title: symbol })}>
                <div className="aios-today__watch-symbol">
                  <strong>{symbol}</strong>
                  <StatusPill status={itemType} />
                </div>
                <div className="aios-today__watch-thesis">{thesis || text(row, "company_name", "")}</div>
                <div className="aios-today__watch-meta">
                  <Badge tone={priority === "critical" || priority === "high" ? "risk" : priority === "medium" ? "warn" : "default"}>{priority}</Badge>
                  {catalyst && <span>· catalyst: {catalyst}</span>}
                  {reviewOn && <span>· review {reviewOn}</span>}
                </div>
              </div>
            );
          })}
        </ScrollList>
      )}
    </Panel>
  );
}

/* ============================================================
 * IDEAS TO REVIEW — fundamental + quant ideas queued for your read
 * ============================================================ */
function IdeasToReview({ research, loading, onOpenEvidence, onAsk }: {
  research: ReturnType<typeof useResearchIdeas>["data"];
  loading: boolean;
  onOpenEvidence: (t: { kind: string; key: string; title: string }) => void;
  onAsk: (q: string) => void;
}) {
  const ideas = [...(research?.generated_ideas ?? []), ...(research?.discovery_candidates ?? [])].slice(0, 6);
  return (
    <Panel icon={Lightbulb} title="Ideas to Review"
      actions={<Button size="sm" variant="ghost" icon={Sparkles} onClick={() => onAsk("Generate 3 fresh investment ideas — one fundamental, one quant, one special situation")}>Generate</Button>}
    >
      {loading ? <SkeletonRows n={3} /> : ideas.length === 0 ? (
        <Empty icon={Lightbulb} title="No ideas queued" description="Run the fundamental or quant idea generators to surface candidates." />
      ) : (
        <ScrollList>
          {ideas.map((idea, i) => {
            const symbol = text(idea, "symbol", text(idea, "name", text(idea, "title", `Idea ${i}`)));
            const thesis = text(idea, "thesis", text(idea, "idea_thesis", text(idea, "description", "")));
            const source = text(idea, "source", text(idea, "idea_type", "idea"));
            return (
              <div key={i} className="aios-today__idea" onClick={() => onOpenEvidence({ kind: "strategy", key: String(text(idea, "id", i)), title: symbol })}>
                <div className="aios-today__idea-head">
                  <strong>{symbol}</strong>
                  <Badge tone="accent">{source}</Badge>
                </div>
                <div className="aios-today__idea-thesis">{thesis.slice(0, 140)}{thesis.length > 140 ? "…" : ""}</div>
              </div>
            );
          })}
        </ScrollList>
      )}
    </Panel>
  );
}

/* ============================================================
 * RESEARCH READY OVERNIGHT — theses, specialist outputs, filings
 * ============================================================ */
function ResearchReady({ research, loading, onOpenEvidence }: {
  research: ReturnType<typeof useResearchIdeas>["data"];
  loading: boolean;
  onOpenEvidence: (t: { kind: string; key: string; title: string }) => void;
}) {
  const theses = research?.long_term_theses ?? [];
  const outputs = research?.long_term_research_updates ?? [];
  const filings = research?.corporate_filings ?? [];
  const recent = [...theses, ...outputs, ...filings].slice(0, 6);
  return (
    <Panel icon={BookOpen} title="Research Ready">
      {loading ? <SkeletonRows n={3} /> : recent.length === 0 ? (
        <Empty icon={BookOpen} title="Nothing new" description="Research outputs from overnight will appear here." />
      ) : (
        <ScrollList>
          {recent.map((row, i) => {
            const title = text(row, "symbol", text(row, "title", text(row, "subject", "Research output")));
            const kind = text(row, "module_key", text(row, "filing_type", text(row, "type", "output")));
            const ts = text(row, "completed_at", text(row, "updated_at", text(row, "created_at", text(row, "published_at"))));
            return (
              <div key={i} className="aios-today__research" onClick={() => onOpenEvidence({ kind: "artifact", key: String(text(row, "id", i)), title })}>
                <FileText size={14} style={{ color: "var(--accent)", flexShrink: 0, marginTop: 2 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 500, fontSize: "var(--text-sm)" }}>{title}</div>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{kind} · {ts ? formatRelative(ts) : ""}</div>
                </div>
              </div>
            );
          })}
        </ScrollList>
      )}
    </Panel>
  );
}

/* ============================================================
 * AUTONOMOUS RESEARCH — bounded heartbeat audit trail
 * ============================================================ */
function AutonomousResearchRuns({ mission, loading }: {
  mission: ReturnType<typeof useMissionControl>["data"];
  loading: boolean;
}) {
  const runs = mission?.market_research_heartbeats ?? [];
  return (
    <Panel icon={Activity} title="Autonomous Research Runs">
      {loading ? <SkeletonRows n={3} /> : runs.length === 0 ? (
        <Empty icon={Activity} title="No heartbeat runs yet" />
      ) : (
        <ScrollList>
          {runs.slice(0, 6).map((row, i) => {
            const graphId = num(row, "graph_run_id", 0);
            const status = text(row, "status", "unknown");
            const title = text(row, "selected_title", text(row, "skip_reason", "Public-market heartbeat"));
            const source = text(row, "source_name", "governed public sources");
            const startedAt = text(row, "started_at", text(row, "created_at"));
            return (
              <div
                key={text(row, "run_key", String(i))}
                className="aios-today__research"
                role={graphId ? "link" : undefined}
                tabIndex={graphId ? 0 : undefined}
                onClick={graphId ? () => window.location.assign(`/firm/graphs?run=${graphId}`) : undefined}
                onKeyDown={graphId ? (event) => { if (event.key === "Enter") window.location.assign(`/firm/graphs?run=${graphId}`); } : undefined}
              >
                <Activity size={14} style={{ color: "var(--accent)", flexShrink: 0, marginTop: 2 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: "var(--space-2)" }}>
                    <div style={{ fontWeight: 500, fontSize: "var(--text-sm)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{title}</div>
                    <StatusPill status={status} />
                  </div>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", marginTop: 3 }}>
                    {source} · {num(row, "material_candidate_count")} material / {num(row, "candidate_count")} checked
                    {graphId ? ` · graph #${graphId}` : ""}
                    {startedAt ? ` · ${formatRelative(startedAt)}` : ""}
                  </div>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--text-faint)", marginTop: 2 }}>
                    Read-only evidence; duplicate cooldown active; broker and capital writes locked.
                  </div>
                </div>
              </div>
            );
          })}
        </ScrollList>
      )}
    </Panel>
  );
}

/* ============================================================
 * WHAT MATTERS NOW — news/events
 * ============================================================ */
function WhatMattersNow({ mission, loading, onOpenEvidence }: {
  mission: ReturnType<typeof useMissionControl>["data"];
  loading: boolean;
  onOpenEvidence: (t: { kind: string; key: string; title: string }) => void;
}) {
  const news = [...(mission?.latest_news ?? []), ...(mission?.market_events ?? [])].slice(0, 8);
  return (
    <Panel icon={Newspaper} title="What Matters Now">
      {loading ? <SkeletonRows n={3} /> : news.length === 0 ? (
        <Empty icon={Newspaper} title="No market events" />
      ) : (
        <ScrollList>
          {news.map((row, i) => {
            const headline = text(row, "headline", text(row, "title", text(row, "summary", "Event")));
            const source = text(row, "source", text(row, "symbol", ""));
            const ts = text(row, "published_at", text(row, "event_date", text(row, "created_at")));
            return (
              <div key={i} className="aios-today__news" onClick={() => onOpenEvidence({ kind: "artifact", key: String(text(row, "id", i)), title: headline })}>
                <div className="aios-today__news-headline">{headline}</div>
                <div className="aios-today__news-meta">
                  {source && <span>{source}</span>}
                  {ts && <span>· {formatRelative(ts)}</span>}
                </div>
              </div>
            );
          })}
        </ScrollList>
      )}
    </Panel>
  );
}

/* ============================================================
 * FRESHNESS ALERTS
 * ============================================================ */
function FreshnessAlerts({ mission, loading }: { mission: ReturnType<typeof useMissionControl>["data"]; loading: boolean }) {
  const stale = mission?.source_freshness?.filter((r) => {
    const status = text(r, "status", text(r, "freshness_status", ""));
    return ["stale", "aging", "overdue", "error", "missing"].some((flag) => status.toLowerCase().includes(flag));
  }) ?? [];
  const fresh = mission?.source_freshness?.filter((r) => !stale.includes(r)).slice(0, 4) ?? [];
  return (
    <Panel icon={Clock} title="Source Freshness">
      {loading ? <Skeleton style={{ height: 60 }} /> : mission?.source_freshness?.length === 0 ? (
        <Empty icon={Clock} title="No freshness data" />
      ) : (
        <ScrollList>
          {stale.map((row, i) => <FreshnessRow key={`s${i}`} row={row} stale />)}
          {fresh.map((row, i) => <FreshnessRow key={`f${i}`} row={row} />)}
        </ScrollList>
      )}
    </Panel>
  );
}

function FreshnessRow({ row, stale }: { row: LiveRow; stale?: boolean }) {
  const name = text(row, "source_name", text(row, "name", text(row, "source_key", "Source")));
  const status = text(row, "status", text(row, "freshness_status", ""));
  const lastCheck = text(row, "last_check_at", text(row, "checked_at", text(row, "updated_at")));
  return (
    <div className={`aios-today__freshness ${stale ? "aios-today__freshness--stale" : ""}`}>
      <div className="aios-today__freshness-name">{name}</div>
      <StatusPill status={status} />
      {lastCheck && <span className="aios-today__freshness-time">{formatRelative(lastCheck)}</span>}
    </div>
  );
}

function SkeletonRows({ n = 3 }: { n?: number }) {
  return <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", padding: "var(--space-2)" }}>{Array.from({ length: n }).map((_, i) => <Skeleton key={i} style={{ height: 48 }} />)}</div>;
}
