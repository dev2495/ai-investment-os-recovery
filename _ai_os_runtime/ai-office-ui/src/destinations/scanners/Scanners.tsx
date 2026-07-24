/**
 * Scanners Terminal — intraday + swing screeners
 *
 * Routes: /scanners/momentum | /breakouts | /volume | /ideas | /options-flow
 *
 * Surfaces tradeable setups from the live data warehouse:
 *   - Momentum (signals with direction + strength)
 *   - Breakouts (positions + watchlist near highs)
 *   - Volume/OI spurt (option chain with big OI change)
 *   - Generated ideas (strategy discovery candidates)
 *   - Options flow (unusual OI buildup)
 *
 * Every result links to evidence + can be added to the watchlist or sent
 * to Charlie for deeper analysis. No fake data — all derived from the
 * trading-quant-risk + research-ideas snapshots.
 */

import React from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Radar, TrendingUp, Zap, Activity, Lightbulb, Flame, Plus,
  ChevronRight, Star, Send, Filter,
} from "lucide-react";
import { useTradingQuantRisk, useResearchIdeas } from "../../data/queries";
import { useUpsertWatchlist } from "../../data/actions";
import { useUIStore } from "../../store";
import {
  Panel, MetricTile, Metric, DataTable, StatusPill, Badge, Empty, Skeleton,
  Button, Tabs, TextInput,
} from "../../system/primitives";
import { text, num, formatRelative, formatCompact, formatPercent, formatCurrency } from "../../data/liveRow";
import type { LiveRow } from "../../data/liveRow";

const TABS = [
  { key: "momentum", label: "Momentum", icon: TrendingUp },
  { key: "breakouts", label: "Breakouts", icon: Zap },
  { key: "volume", label: "Volume / OI Spurt", icon: Activity },
  { key: "ideas", label: "Generated Ideas", icon: Lightbulb },
  { key: "options-flow", label: "Options Flow", icon: Flame },
];

export default function Scanners({ defaultTab = "momentum" }: { defaultTab?: string }) {
  const params = useParams();
  const navigate = useNavigate();
  const tab = params.tab ?? defaultTab;
  function setTab(key: string) { navigate(`/scanners/${key}`); }

  return (
    <div className="aios-destination">
      <div className="aios-destination__head">
        <div className="aios-destination__title-row">
          <div className="aios-destination__title">
            <Radar size={26} style={{ verticalAlign: "middle", marginRight: 10, color: "var(--accent)" }} />
            Scanners
          </div>
          <Badge tone="accent">SCAN</Badge>
          <span style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>intraday + swing setups from live data</span>
        </div>
        <div className="aios-destination__subtitle">
          Momentum signals, breakout candidates, volume/OI spurts, generated ideas, and unusual options flow.
          Every result links to evidence and can be watchlisted or sent to Charlie.
        </div>
        <Tabs tabs={TABS} active={tab} onChange={setTab} />
      </div>

      {tab === "momentum" && <MomentumScanner />}
      {tab === "breakouts" && <BreakoutScanner />}
      {tab === "volume" && <VolumeScanner />}
      {tab === "ideas" && <IdeasScanner />}
      {tab === "options-flow" && <OptionsFlowScanner />}
    </div>
  );
}

/* ============================================================
 * Shared result row actions
 * ============================================================ */
function ResultActions({ symbol, thesis, onWatch }: { symbol: string; thesis?: string; onWatch: (s: string, t?: string) => void }) {
  const setAssistantScope = useUIStore((s) => s.setAssistantScope);
  const setAssistantOpen = useUIStore((s) => s.setAssistantOpen);
  return (
    <div style={{ display: "flex", gap: "var(--space-1)" }}>
      <Button size="sm" variant="ghost" icon={Star} onClick={() => onWatch(symbol, thesis)}>Watch</Button>
      <Button size="sm" variant="ghost" icon={Send} onClick={() => { setAssistantScope("charlie"); setAssistantOpen(true); sessionStorage.setItem("aios:pending-charlie-question", `Deep-dive on ${symbol}: thesis, risk, and is this a trade?`); }}>Analyze</Button>
    </div>
  );
}

function useWatchlistAdd() {
  const mut = useUpsertWatchlist();
  const pushToast = useUIStore((s) => s.pushToast);
  return React.useCallback((symbol: string, thesis?: string) => {
    mut.mutate(
      { symbol, item_type: "idea", priority: "medium", thesis, actor: "Devarsh" },
      { onSuccess: () => pushToast({ title: "Added to watchlist", message: symbol, tone: "ok", duration: 2500 }), onError: (e) => pushToast({ title: "Failed", message: e.message, tone: "risk", duration: 4000 }) }
    );
  }, [mut, pushToast]);
}

/* ============================================================
 * MOMENTUM — signals with direction + strength
 * ============================================================ */
function MomentumScanner() {
  const { data, isLoading } = useTradingQuantRisk();
  const signals = data?.signals ?? [];
  const [filter, setFilter] = React.useState("");
  const addWatch = useWatchlistAdd();

  const filtered = signals.filter((s) => {
    if (!filter) return true;
    return text(s, "symbol", "").toLowerCase().includes(filter.toLowerCase());
  }).sort((a, b) => num(b, "strength", num(b, "confidence", 0)) - num(a, "strength", num(a, "confidence", 0)));

  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile><Metric label="Total Signals" value={signals.length} /></MetricTile>
        <MetricTile tone="ok"><Metric label="Bullish" value={signals.filter((s) => ["buy", "long", "bullish"].some(w => text(s, "direction", text(s, "side", "")).toLowerCase().includes(w))).length} /></MetricTile>
        <MetricTile tone="risk"><Metric label="Bearish" value={signals.filter((s) => ["sell", "short", "bearish"].some(w => text(s, "direction", text(s, "side", "")).toLowerCase().includes(w))).length} /></MetricTile>
        <MetricTile><Metric label="Strong (≥0.7)" value={signals.filter((s) => num(s, "strength", num(s, "confidence", 0)) >= 0.7).length} /></MetricTile>
      </div>

      <Panel icon={TrendingUp} title="Momentum Signals"
        actions={<TextInput placeholder="Filter symbol…" value={filter} onChange={(e) => setFilter(e.target.value)} style={{ width: 160 }} />}
      >
        {isLoading ? <SkeletonRows n={6} /> : filtered.length === 0 ? (
          <Empty icon={TrendingUp} title="No momentum signals" description="Signals fire from active strategy monitors and scanners. Start paper monitors in the Quant Lab to generate them." />
        ) : (
          <DataTable
            columns={[
              { key: "symbol", header: "Symbol", render: (r) => <strong>{text(r, "symbol")}</strong> },
              { key: "type", header: "Signal", render: (r) => text(r, "signal_type", text(r, "name", "signal")) },
              { key: "dir", header: "Direction", render: (r) => <StatusPill status={text(r, "direction", text(r, "side", "neutral"))} /> },
              { key: "strategy", header: "Strategy", render: (r) => text(r, "strategy_name", "—") },
              { key: "strength", header: "Strength", align: "right", render: (r) => <StrengthBar value={num(r, "strength", num(r, "confidence", 0))} /> },
              { key: "when", header: "When", render: (r) => <span style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>{formatRelative(text(r, "generated_at", text(r, "created_at")))}</span> },
              { key: "actions", header: "", render: (r) => <ResultActions symbol={text(r, "symbol")} thesis={text(r, "description", text(r, "thesis"))} onWatch={addWatch} /> },
            ]}
            rows={filtered.slice(0, 60)}
            rowKey={(r, i) => String(text(r, "signal_id", text(r, "id", i)))}
          />
        )}
      </Panel>
    </>
  );
}

function StrengthBar({ value }: { value: number }) {
  const pct = Math.min(100, Math.max(0, value * 100));
  const color = pct >= 70 ? "var(--status-ok)" : pct >= 40 ? "var(--status-warn)" : "var(--status-risk)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", justifyContent: "flex-end" }}>
      <div style={{ width: 50, height: 5, background: "var(--bg-sunken)", borderRadius: 3, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color }} />
      </div>
      <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", minWidth: 32 }}>{value.toFixed(2)}</span>
    </div>
  );
}

/* ============================================================
 * BREAKOUTS — only explicit breakout signals from the warehouse
 * ============================================================ */
function BreakoutScanner() {
  const { data: tqr } = useTradingQuantRisk();
  const addWatch = useWatchlistAdd();

  const candidates = React.useMemo(() => {
    const explicitSignals = (tqr?.signals ?? []).filter((signal) => {
      const kind = `${text(signal, "signal_type")} ${text(signal, "name")} ${text(signal, "description")}`.toLowerCase();
      return kind.includes("breakout") && num(signal, "strength", num(signal, "confidence", 0)) >= 0.6;
    });
    const map = new Map<string, LiveRow>();
    for (const s of explicitSignals) {
      const sym = text(s, "symbol");
      if (sym) map.set(sym, { ...s, source: "signal" } as LiveRow);
    }
    return Array.from(map.values());
  }, [tqr?.signals]);

  return (
    <Panel icon={Zap} title="Breakout Candidates"
      actions={<Badge tone="accent">{candidates.length} candidates</Badge>}
    >
      {candidates.length === 0 ? (
        <Empty icon={Zap} title="No verified breakout signals" description="This scanner only shows stored breakout signals with strength of at least 0.6; holdings and watchlist membership are not treated as evidence." />
      ) : (
        <DataTable
          columns={[
            { key: "symbol", header: "Symbol", render: (r) => <strong>{text(r, "symbol")}</strong> },
            { key: "source", header: "Source", render: (r) => <Badge>{text(r, "source", "scan")}</Badge> },
            { key: "why", header: "Why", render: (r) => text(r, "signal_type", text(r, "thesis", text(r, "catalyst", "—"))) },
            { key: "strength", header: "Signal Strength", align: "right", render: (r) => num(r, "strength", num(r, "confidence", 0)).toFixed(2) },
            { key: "actions", header: "", render: (r) => <ResultActions symbol={text(r, "symbol")} thesis={text(r, "thesis")} onWatch={addWatch} /> },
          ]}
          rows={candidates}
          rowKey={(r, i) => text(r, "symbol", `c-${i}`)}
        />
      )}
    </Panel>
  );
}

/* ============================================================
 * VOLUME / OI SPURT — option chain contracts with big OI change
 * ============================================================ */
function VolumeScanner() {
  const { data, isLoading } = useTradingQuantRisk();
  const chain = data?.option_chain ?? [];
  const addWatch = useWatchlistAdd();

  // OI spurt = biggest absolute OI change
  const spurts = React.useMemo(() =>
    [...chain]
      .filter((c) => Math.abs(num(c, "open_interest_change", num(c, "oi_change", 0))) > 0)
      .sort((a, b) => Math.abs(num(b, "open_interest_change", num(b, "oi_change", 0))) - Math.abs(num(a, "open_interest_change", num(a, "oi_change", 0))))
      .slice(0, 40),
    [chain]
  );

  return (
    <Panel icon={Activity} title="Volume / OI Spurt Scanner">
      {isLoading ? <SkeletonRows n={6} /> : spurts.length === 0 ? (
        <Empty icon={Activity} title="No OI spurt data" description="Contracts with significant OI change appear here once the Zerodha chain is synced." />
      ) : (
        <DataTable
          columns={[
            { key: "symbol", header: "Underlying", render: (r) => <strong>{text(r, "underlying", text(r, "symbol"))}</strong> },
            { key: "strike", header: "Strike", align: "right", render: (r) => num(r, "strike", 0) },
            { key: "type", header: "Type", render: (r) => <StatusPill status={text(r, "option_type", "CE")} /> },
            { key: "oi", header: "OI", align: "right", render: (r) => formatCompact(num(r, "open_interest", num(r, "oi", 0))) },
            { key: "oichg", header: "OI Change", align: "right", render: (r) => {
              const chg = num(r, "open_interest_change", num(r, "oi_change", 0));
              return <span style={{ color: chg >= 0 ? "var(--status-ok)" : "var(--status-risk)", fontWeight: 600 }}>{chg >= 0 ? "+" : ""}{formatCompact(chg)}</span>;
            } },
            { key: "iv", header: "IV", align: "right", render: (r) => formatPercent(num(r, "implied_volatility", num(r, "iv", 0)) / 100, { digits: 1 }) },
            { key: "actions", header: "", render: (r) => <ResultActions symbol={`${text(r, "underlying", text(r, "symbol"))} ${num(r, "strike", 0)}${text(r, "option_type", "CE")}`} thesis={`OI spurt: ${num(r, "open_interest_change", 0) > 0 ? "building" : "unwinding"}`} onWatch={addWatch} /> },
          ]}
          rows={spurts}
          rowKey={(r, i) => String(text(r, "id", text(r, "trading_symbol", i)))}
          dense
        />
      )}
    </Panel>
  );
}

/* ============================================================
 * GENERATED IDEAS — strategy discovery candidates
 * ============================================================ */
function IdeasScanner() {
  const { data, isLoading } = useResearchIdeas();
  const addWatch = useWatchlistAdd();
  const ideas = [...(data?.generated_ideas ?? []), ...(data?.discovery_candidates ?? [])];
  const [filter, setFilter] = React.useState("");
  const filtered = filter ? ideas.filter((r) => text(r, "symbol", text(r, "name", text(r, "title", ""))).toLowerCase().includes(filter.toLowerCase())) : ideas;

  return (
    <Panel icon={Lightbulb} title="Generated Idea Scanner"
      actions={<TextInput placeholder="Filter…" value={filter} onChange={(e) => setFilter(e.target.value)} style={{ width: 140 }} />}
    >
      {isLoading ? <SkeletonRows n={4} /> : filtered.length === 0 ? (
        <Empty icon={Lightbulb} title="No generated ideas" description="Run the fundamental or quant idea generators, or strategy discovery." />
      ) : (
        <DataTable
          columns={[
            { key: "symbol", header: "Symbol", render: (r) => <strong>{text(r, "symbol", text(r, "name"))}</strong> },
            { key: "type", header: "Type", render: (r) => <Badge tone="accent">{text(r, "idea_type", text(r, "source", "idea"))}</Badge> },
            { key: "thesis", header: "Thesis", render: (r) => text(r, "thesis", text(r, "idea_thesis", text(r, "description", "—"))) },
            { key: "actions", header: "", render: (r) => <ResultActions symbol={text(r, "symbol", text(r, "name"))} thesis={text(r, "thesis")} onWatch={addWatch} /> },
          ]}
          rows={filtered.slice(0, 40)}
          rowKey={(r, i) => String(text(r, "idea_id", text(r, "id", i)))}
        />
      )}
    </Panel>
  );
}

/* ============================================================
 * OPTIONS FLOW — unusual OI buildup by underlying
 * ============================================================ */
function OptionsFlowScanner() {
  const { data, isLoading } = useTradingQuantRisk();
  const chain = data?.option_chain ?? [];
  const addWatch = useWatchlistAdd();

  // Aggregate net OI change by underlying + type (call writing vs put writing)
  const flow = React.useMemo(() => {
    const map = new Map<string, { underlying: string; callBuild: number; putBuild: number; totalOi: number }>();
    for (const c of chain) {
      const u = text(c, "underlying", text(c, "symbol", ""));
      if (!u) continue;
      const ex = map.get(u) ?? { underlying: u, callBuild: 0, putBuild: 0, totalOi: 0 };
      const chg = num(c, "open_interest_change", num(c, "oi_change", 0));
      const oi = num(c, "open_interest", num(c, "oi", 0));
      const type = text(c, "option_type", "CE").toUpperCase().startsWith("P") ? "PE" : "CE";
      if (type === "CE") ex.callBuild += chg; else ex.putBuild += chg;
      ex.totalOi += oi;
      map.set(u, ex);
    }
    return Array.from(map.values()).sort((a, b) => Math.abs(b.callBuild) + Math.abs(b.putBuild) - Math.abs(a.callBuild) - Math.abs(a.putBuild));
  }, [chain]);

  return (
    <Panel icon={Flame} title="Options Flow — net OI buildup by underlying">
      {isLoading ? <SkeletonRows n={4} /> : flow.length === 0 ? (
        <Empty icon={Flame} title="No flow data" description="Aggregated OI buildup by underlying appears here once the chain is synced." />
      ) : (
        <DataTable
          columns={[
            { key: "underlying", header: "Underlying", render: (r) => <strong>{text(r, "underlying")}</strong> },
            { key: "callBuild", header: "Call OI Chg", align: "right", render: (r) => {
              const v = num(r, "callBuild", 0);
              return <span style={{ color: v > 0 ? "var(--status-risk)" : "var(--status-ok)", fontWeight: 600 }}>{v >= 0 ? "+" : ""}{formatCompact(v)}</span>;
            } },
            { key: "putBuild", header: "Put OI Chg", align: "right", render: (r) => {
              const v = num(r, "putBuild", 0);
              return <span style={{ color: v > 0 ? "var(--status-ok)" : "var(--status-risk)", fontWeight: 600 }}>{v >= 0 ? "+" : ""}{formatCompact(v)}</span>;
            } },
            { key: "read", header: "Concentration", render: (r) => {
              const cb = num(r, "callBuild", 0); const pb = num(r, "putBuild", 0);
              if (Math.abs(pb) > Math.abs(cb) * 1.25) return <StatusPill tone="ok" status="put-led">Put-side OI led</StatusPill>;
              if (Math.abs(cb) > Math.abs(pb) * 1.25) return <StatusPill tone="risk" status="call-led">Call-side OI led</StatusPill>;
              if (Math.abs(cb) + Math.abs(pb) > 0) return <StatusPill tone="warn" status="two-sided">Two-sided OI</StatusPill>;
              return <StatusPill status="flat">Flat</StatusPill>;
            } },
            { key: "totalOi", header: "Total OI", align: "right", render: (r) => formatCompact(num(r, "totalOi", 0)) },
            { key: "actions", header: "", render: (r) => <ResultActions symbol={text(r, "underlying")} thesis={`Options OI change: call ${num(r, "callBuild", 0)}, put ${num(r, "putBuild", 0)}; direction unverified without price and trade-side evidence.`} onWatch={addWatch} /> },
          ]}
          rows={flow}
          rowKey={(r, i) => text(r, "underlying", `f-${i}`)}
        />
      )}
      <div style={{ fontSize: "var(--text-xs)", color: "var(--text-faint)", textAlign: "center", marginTop: "var(--space-3)" }}>
        OI change alone does not identify buyers versus writers or establish direction. The table reports where open-interest change is concentrated.
      </div>
    </Panel>
  );
}

function SkeletonRows({ n = 3 }: { n?: number }) {
  return <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", padding: "var(--space-2)" }}>{Array.from({ length: n }).map((_, i) => <Skeleton key={i} style={{ height: 44 }} />)}</div>;
}
