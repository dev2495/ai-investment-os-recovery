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
  Sparkles, Gavel, Send, Newspaper, AlertTriangle, Clock, CheckCircle2, Inbox,
  Star, Lightbulb, BookOpen, FileText, TrendingUp, ChevronRight, Activity,
} from "lucide-react";
import { useMissionControl, useResearchIdeas } from "../../data/queries";
import { useUIStore } from "../../store";
import {
  Panel, MetricTile, Metric, Badge, StatusPill, ScrollList, Empty, Skeleton, Button,
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
  "Add RELIANCE to my watchlist",
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
    sessionStorage.setItem("aios:pending-charlie-question", q);
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
              placeholder="Ask anything, or tell Charlie to build a dashboard, run a scan, or brief you…"
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

        <div className="aios-today__grid">
          {/* Left column: decisions + watchlist */}
          <div className="aios-today__col">
            <NeedsDecision mission={mission} loading={isLoading} onOpenEvidence={openEvidence} />
            <Watchlist mission={mission} research={research} loading={isLoading} onOpenEvidence={openEvidence} onAsk={askCharlie} />
          </div>

          {/* Right column: ideas + research-ready + news + freshness */}
          <div className="aios-today__col">
            <IdeasToReview research={research} loading={isLoading} onOpenEvidence={openEvidence} onAsk={askCharlie} />
            <ResearchReady research={research} loading={isLoading} onOpenEvidence={openEvidence} />
            <WhatMattersNow mission={mission} loading={isLoading} onOpenEvidence={openEvidence} />
            <FreshnessAlerts mission={mission} loading={isLoading} />
          </div>
        </div>
      </div>
    </>
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
  const approvals = mission.approvals?.length ?? 0;
  const breaches = mission.execution_control?.filter((r) => text(r, "kind") === "risk_event").length ?? 0;
  const staleSources = mission.source_freshness?.filter((r) => text(r, "status").includes("stale")).length ?? 0;
  const navRow = mission.metrics?.find((r) => text(r, "metric_key", "").includes("nav") || text(r, "label", "").toLowerCase().includes("nav"));
  const navValue = navRow ? num(navRow, "value") : 0;

  return (
    <div className="aios-today__hero">
      <MetricTile><Metric label="Net Asset Value" value={navValue > 0 ? formatCompact(navValue, "INR") : "—"} size="lg" sub="across all clients" /></MetricTile>
      <MetricTile tone={breaches > 0 ? "risk" : "ok"}>
        <Metric label="Risk Breaches" value={breaches} size="lg" sub={breaches > 0 ? "needs attention" : "within limits"} />
      </MetricTile>
      <MetricTile tone={approvals > 0 ? "warn" : "ok"}>
        <Metric label="Pending Decisions" value={approvals} size="lg" sub={approvals > 0 ? "awaiting you" : "all clear"} />
      </MetricTile>
      <MetricTile tone={staleSources > 0 ? "warn" : "ok"}>
        <Metric label="Stale Sources" value={staleSources} size="lg" sub={staleSources > 0 ? "need refresh" : "fresh"} />
      </MetricTile>
      <MetricTile><Metric label="Watchlist" value={mission.watchlist?.length ?? 0} size="lg" sub="tracked symbols" /></MetricTile>
    </div>
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
  const approvals = mission?.approvals ?? [];
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
    return status.toLowerCase().includes("stale") || status.toLowerCase().includes("aging") || status.toLowerCase().includes("overdue");
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
