/**
 * Today Destination
 *
 * Replaces Mission Control. Progressive disclosure — not a wall of 13 panels.
 *
 * Sections:
 *   1. Hero strip — NAV, exposure, breaches, approvals, freshness (at a glance)
 *   2. Charlie's Daily Brief — the generated brief
 *   3. Needs Your Decision — the inline approval spine
 *   4. What Charlie Delegated — active delegations + worker runs
 *   5. What Matters Now — prioritized news/events with evidence
 *   6. Freshness alerts — stale data sources (governance requirement)
 */

import React from "react";
import {
  Sparkles,
  Gavel,
  Send,
  Newspaper,
  AlertTriangle,
  TrendingUp,
  Wallet,
  ShieldAlert,
  Clock,
  CheckCircle2,
  Inbox,
} from "lucide-react";
import { useMissionControl } from "../../data/queries";
import { useUIStore } from "../../store";
import {
  Panel,
  MetricTile,
  Metric,
  Badge,
  StatusPill,
  ScrollList,
  Empty,
  Skeleton,
  Button,
} from "../../system/primitives";
import { text, num, bool, timestamp, formatRelative, formatCompact } from "../../data/liveRow";
import { TodayCss } from "./Today.css";

export default function TodayDestination() {
  const { data: mission, isLoading, error } = useMissionControl();
  const openEvidence = useUIStore((s) => s.openEvidence);
  const setAssistantScope = useUIStore((s) => s.setAssistantScope);

  if (error) {
    return (
      <div className="aios-destination">
        <Panel variant="risk" icon={AlertTriangle} title="Cannot reach mission control">
          <div style={{ padding: "var(--space-4)", color: "var(--text-muted)" }}>
            {error.message}
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
        <div className="aios-destination__head">
          <div className="aios-destination__title-row">
            <div className="aios-destination__title">Today</div>
            <Badge tone="accent" dot pulse>
              {mission ? formatRelative(mission.generated_at) : "loading"}
            </Badge>
          </div>
          <div className="aios-destination__subtitle">
            Your daily brief, decisions, and what the office is working on.
          </div>
        </div>

        {/* Hero strip */}
        <HeroStrip mission={mission} loading={isLoading} />

        <div className="aios-today__grid">
          {/* Left column: brief + decisions */}
          <div className="aios-today__col">
            <DailyBrief mission={mission} loading={isLoading} onAskCharlie={() => setAssistantScope("charlie")} />
            <NeedsDecision mission={mission} loading={isLoading} onOpenEvidence={openEvidence} />
          </div>

          {/* Right column: delegations + news + freshness */}
          <div className="aios-today__col">
            <Delegations mission={mission} loading={isLoading} onOpenEvidence={openEvidence} />
            <WhatMattersNow mission={mission} loading={isLoading} onOpenEvidence={openEvidence} />
            <FreshnessAlerts mission={mission} loading={isLoading} />
          </div>
        </div>
      </div>
    </>
  );
}

/* ============================================================
 * HERO STRIP — at-a-glance metrics
 * ============================================================ */
function HeroStrip({ mission, loading }: { mission: ReturnType<typeof useMissionControl>["data"]; loading: boolean }) {
  if (loading || !mission) {
    return (
      <div className="aios-today__hero">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} style={{ height: 88, borderRadius: "var(--radius-md)" }} />
        ))}
      </div>
    );
  }
  const approvals = mission.approvals?.length ?? 0;
  const breaches = mission.execution_control?.filter((r) => text(r, "kind") === "risk_event").length ?? 0;
  const staleSources = mission.source_freshness?.filter((r) => text(r, "status") === "stale").length ?? 0;

  const navRow = mission.metrics?.find((r) => text(r, "metric") === "portfolio_nav");
  const navValue = navRow ? num(navRow, "value") : 0;
  const exposureRow = mission.metrics?.find((r) => text(r, "metric") === "gross_book_exposure");
  const exposureValue = exposureRow ? num(exposureRow, "value") : 0;

  return (
    <div className="aios-today__hero">
      <MetricTile>
        <Metric label="Net Asset Value" value={navRow ? formatCompact(navValue, "INR") : "—"} size="lg" sub="latest holdings across active clients" />
      </MetricTile>
      <MetricTile>
        <Metric label="Gross Exposure" value={exposureRow ? formatCompact(exposureValue, "INR") : "—"} size="lg" sub="book-assigned positions" />
      </MetricTile>
      <MetricTile tone={breaches > 0 ? "risk" : "ok"}>
        <Metric label="Risk Breaches" value={breaches} size="lg" sub={breaches > 0 ? `${breaches} active` : "within limits"} />
      </MetricTile>
      <MetricTile tone={approvals > 0 ? "warn" : "ok"}>
        <Metric label="Pending Approvals" value={approvals} size="lg" sub={approvals > 0 ? "awaiting you" : "all clear"} />
      </MetricTile>
      <MetricTile tone={staleSources > 0 ? "warn" : "ok"}>
        <Metric label="Stale Sources" value={staleSources} size="lg" sub={staleSources > 0 ? "need refresh" : "fresh"} />
      </MetricTile>
    </div>
  );
}

/* ============================================================
 * DAILY BRIEF
 * ============================================================ */
function DailyBrief({ mission, loading, onAskCharlie }: { mission: ReturnType<typeof useMissionControl>["data"]; loading: boolean; onAskCharlie: () => void }) {
  const briefRows = mission?.news_brief ?? mission?.latest_reports ?? [];
  return (
    <Panel
      icon={Sparkles}
      title="Charlie's Daily Brief"
      actions={<Button size="sm" variant="ghost" icon={Send} onClick={onAskCharlie}>Ask Charlie</Button>}
    >
      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
          <Skeleton variant="text" />
          <Skeleton variant="text" width="85%" />
          <Skeleton variant="text" width="70%" />
        </div>
      ) : briefRows.length === 0 ? (
        <Empty icon={Sparkles} title="No brief yet" description="Ask Charlie to generate today's brief." action={<Button size="sm" onClick={onAskCharlie}>Generate brief</Button>} />
      ) : (
        <ScrollList>
          {briefRows.slice(0, 8).map((row, i) => (
            <div key={i} className="aios-today__brief-line">
              <span className="aios-today__brief-bullet">›</span>
              <div>
                <div className="aios-today__brief-title">{text(row, "headline", text(row, "title", text(row, "summary", text(row, "label", "Brief item"))))}</div>
                {text(row, "detail", text(row, "source", "")) && (
                  <div className="aios-today__brief-meta">{text(row, "detail", text(row, "source", ""))}</div>
                )}
              </div>
            </div>
          ))}
        </ScrollList>
      )}
    </Panel>
  );
}

/* ============================================================
 * NEEDS YOUR DECISION — inline approval spine
 * ============================================================ */
function NeedsDecision({ mission, loading, onOpenEvidence }: { mission: ReturnType<typeof useMissionControl>["data"]; loading: boolean; onOpenEvidence: (t: { kind: string; key: string; title: string }) => void }) {
  const approvals = mission?.approvals ?? [];
  return (
    <Panel
      icon={Gavel}
      title="Needs Your Decision"
      actions={approvals.length > 0 ? <Badge tone="warn" dot pulse>{approvals.length}</Badge> : undefined}
    >
      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
          {Array.from({ length: 2 }).map((_, i) => <Skeleton key={i} style={{ height: 48 }} />)}
        </div>
      ) : approvals.length === 0 ? (
        <Empty icon={CheckCircle2} title="Nothing pending" description="You're all caught up." />
      ) : (
        <ScrollList>
          {approvals.map((approval, i) => {
            const key = String(text(approval, "approval_id", text(approval, "id", i)));
            const title = text(approval, "title", text(approval, "subject", text(approval, "approval_type", "Approval")));
            const status = text(approval, "status", "pending");
            const ts = timestamp(approval, "created_at");
            return (
              <div
                key={i}
                className="aios-today__decision"
                onClick={() => onOpenEvidence({ kind: "approval", key, title })}
              >
                <div className="aios-today__decision-icon">
                  <Gavel size={14} />
                </div>
                <div className="aios-today__decision-main">
                  <div className="aios-today__decision-title">{title}</div>
                  <div className="aios-today__decision-meta">
                    <StatusPill status={status} />
                    {ts && <span>· {formatRelative(ts)}</span>}
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
 * DELEGATIONS — what Charlie dispatched
 * ============================================================ */
function Delegations({ mission, loading, onOpenEvidence }: { mission: ReturnType<typeof useMissionControl>["data"]; loading: boolean; onOpenEvidence: (t: { kind: string; key: string; title: string }) => void }) {
  const queue = mission?.agent_worker_queue ?? [];
  const runs = mission?.agent_worker_runs ?? [];
  const combined = [...queue, ...runs.slice(0, 5)];
  return (
    <Panel icon={Inbox} title="What Charlie Delegated">
      {loading ? (
        <Skeleton style={{ height: 80 }} />
      ) : combined.length === 0 ? (
        <Empty icon={Inbox} title="No active delegations" description="Tasks dispatched to the team will appear here." />
      ) : (
        <ScrollList>
          {combined.slice(0, 8).map((row, i) => {
            const title = text(row, "task_name", text(row, "title", text(row, "workflow_key", "Delegated task")));
            const agent = text(row, "agent_key", text(row, "owner_agent", ""));
            const status = text(row, "status", text(row, "run_status", ""));
            return (
              <div key={i} className="aios-today__delegation" onClick={() => onOpenEvidence({ kind: "task", key: String(text(row, "task_id", text(row, "id", i))), title })}>
                <div className="aios-today__delegation-agent">{agent.slice(0, 2).toUpperCase()}</div>
                <div className="aios-today__delegation-main">
                  <div className="aios-today__delegation-title">{title}</div>
                  <div className="aios-today__delegation-meta">
                    {agent && <span>{agent}</span>}
                    <StatusPill status={status} />
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
 * WHAT MATTERS NOW — prioritized news/events
 * ============================================================ */
function WhatMattersNow({ mission, loading, onOpenEvidence }: { mission: ReturnType<typeof useMissionControl>["data"]; loading: boolean; onOpenEvidence: (t: { kind: string; key: string; title: string }) => void }) {
  const news = [...(mission?.latest_news ?? []), ...(mission?.market_events ?? [])].slice(0, 8);
  return (
    <Panel icon={Newspaper} title="What Matters Now">
      {loading ? (
        <Skeleton style={{ height: 80 }} />
      ) : news.length === 0 ? (
        <Empty icon={Newspaper} title="No market events" description="The news desk will surface items as they come in." />
      ) : (
        <ScrollList>
          {news.map((row, i) => {
            const headline = text(row, "headline", text(row, "title", text(row, "summary", "Event")));
            const source = text(row, "source", text(row, "symbol", ""));
            const ts = timestamp(row, "published_at", timestamp(row, "event_date", timestamp(row, "created_at")));
            const severity = text(row, "severity", text(row, "priority", ""));
            return (
              <div key={i} className="aios-today__news" onClick={() => onOpenEvidence({ kind: "artifact", key: String(text(row, "id", i)), title: headline })}>
                <div className="aios-today__news-main">
                  <div className="aios-today__news-headline">{headline}</div>
                  <div className="aios-today__news-meta">
                    {source && <span>{source}</span>}
                    {ts && <span>· {formatRelative(ts)}</span>}
                    {severity && <StatusPill status={severity} />}
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
 * FRESHNESS ALERTS — stale data sources
 * ============================================================ */
function FreshnessAlerts({ mission, loading }: { mission: ReturnType<typeof useMissionControl>["data"]; loading: boolean }) {
  const stale = mission?.source_freshness?.filter((r) => {
    const status = text(r, "status", text(r, "freshness_status", ""));
    return status.toLowerCase().includes("stale") || status.toLowerCase().includes("aging") || status.toLowerCase().includes("overdue");
  }) ?? [];
  const fresh = mission?.source_freshness?.filter((r) => !stale.includes(r)).slice(0, 4) ?? [];
  return (
    <Panel icon={Clock} title="Source Freshness">
      {loading ? (
        <Skeleton style={{ height: 60 }} />
      ) : mission?.source_freshness?.length === 0 ? (
        <Empty icon={Clock} title="No freshness data" />
      ) : (
        <ScrollList>
          {stale.map((row, i) => (
            <FreshnessRow key={`s${i}`} row={row} stale />
          ))}
          {fresh.map((row, i) => (
            <FreshnessRow key={`f${i}`} row={row} />
          ))}
        </ScrollList>
      )}
    </Panel>
  );
}

function FreshnessRow({ row, stale }: { row: Record<string, unknown>; stale?: boolean }) {
  const name = text(row, "source_name", text(row, "name", text(row, "source_key", "Source")));
  const status = text(row, "status", text(row, "freshness_status", ""));
  const lastCheck = timestamp(row, "last_check_at", timestamp(row, "checked_at", timestamp(row, "updated_at")));
  return (
    <div className={`aios-today__freshness ${stale ? "aios-today__freshness--stale" : ""}`}>
      <div className="aios-today__freshness-name">{name}</div>
      <StatusPill status={status} />
      {lastCheck && <span className="aios-today__freshness-time">{formatRelative(lastCheck)}</span>}
    </div>
  );
}
