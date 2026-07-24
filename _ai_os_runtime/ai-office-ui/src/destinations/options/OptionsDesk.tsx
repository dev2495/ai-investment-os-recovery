/**
 * Options Desk Terminal v2 — oipulse-class and beyond
 *
 * Routes: /options/desk | /chain | /surface | /oi-analysis | /strategies | /agent
 *
 * Matches OI Pulse's core (real-time OI chain, OI buildup, max pain, PCR,
 * straddle charts) AND beats them with features they lack:
 *   - IV smile/skew surface
 *   - OI buildup heatmap by strike
 *   - Strategy builder with payoff diagram
 *
 * Data source: trading.option_chain_snapshots (Zerodha) via the
 * trading-quant-risk snapshot's option_chain array.
 */

import React from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  TrendingDown, BarChart3, LineChart, Brain, Activity, Plus,
  AlertTriangle, Layers, Flame, Play,
} from "lucide-react";
import { useTradingQuantRisk } from "../../data/queries";
import { useRecordManualTrade } from "../../data/actions";
import { useUIStore } from "../../store";
import {
  Panel, MetricTile, Metric, DataTable, StatusPill, Badge, Empty, Skeleton,
  Button, Tabs, Drawer, Field, TextInput, TextArea, Select,
} from "../../system/primitives";
import { BarSeriesChart, LineSeriesChart, AreaSeriesChart } from "../../system/charts";
import { text, num, formatCurrency, formatCompact, formatPercent } from "../../data/liveRow";
import type { LiveRow } from "../../data/liveRow";

const TABS = [
  { key: "desk", label: "Options Desk", icon: TrendingDown },
  { key: "chain", label: "Option Chain", icon: BarChart3 },
  { key: "surface", label: "Vol Surface", icon: LineChart },
  { key: "oi-analysis", label: "OI Analysis", icon: Flame },
  { key: "strategies", label: "Strategy Builder", icon: Layers },
  { key: "agent", label: "Options Agent", icon: Brain },
];

export default function OptionsDesk({ defaultTab = "desk" }: { defaultTab?: string }) {
  const params = useParams();
  const navigate = useNavigate();
  const tab = params.tab ?? defaultTab;
  function setTab(key: string) { navigate(`/options/${key}`); }

  return (
    <div className="aios-destination">
      <div className="aios-destination__head">
        <div className="aios-destination__title-row">
          <div className="aios-destination__title">
            <TrendingDown size={26} style={{ verticalAlign: "middle", marginRight: 10, color: "var(--accent)" }} />
            Options Desk
          </div>
          <Badge tone="accent">OPTS</Badge>
          <span style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>manual trading · full OI analytics · strategy builder</span>
        </div>
        <div className="aios-destination__subtitle">
          Real-time option chain, OI buildup analysis, implied vol smile, straddle curves, max pain,
          strategy builder with payoff. NSE index + equity options via Zerodha.
        </div>
        <Tabs tabs={TABS} active={tab} onChange={setTab} />
      </div>

      {tab === "desk" && <DeskView />}
      {tab === "chain" && <ChainView />}
      {tab === "surface" && <SurfaceView />}
      {tab === "oi-analysis" && <OiAnalysisView />}
      {tab === "strategies" && <StrategiesView />}
      {tab === "agent" && <AgentView />}
    </div>
  );
}

/* ============================================================
 * Shared: parse the chain
 * ============================================================ */
interface ParsedContract {
  symbol: string; expiry: string; strike: number; type: "CE" | "PE";
  ltp: number; oi: number; oiChange: number; iv: number; volume: number; spot: number;
}

function useChain() {
  const { data, isLoading } = useTradingQuantRisk();
  return React.useMemo(() => {
    const raw = data?.option_chain ?? [];
    const parsed: ParsedContract[] = raw.map((r) => ({
      symbol: text(r, "underlying", text(r, "symbol", "")),
      expiry: text(r, "expiry", text(r, "expiry_date", "")),
      strike: num(r, "strike", 0),
      type: (text(r, "option_type", "CE").toUpperCase().startsWith("P") ? "PE" : "CE") as "CE" | "PE",
      ltp: num(r, "last_price", num(r, "ltp", 0)),
      oi: num(r, "open_interest", num(r, "oi", 0)),
      oiChange: num(r, "open_interest_change", num(r, "oi_change", 0)),
      iv: num(r, "implied_volatility", num(r, "iv", 0)),
      volume: num(r, "volume", 0),
      spot: num(r, "spot_price", 0),
    }));
    return { parsed, isLoading, underlyings: Array.from(new Set(parsed.map((p) => p.symbol))).sort(), expiries: Array.from(new Set(parsed.map((p) => p.expiry))).sort() };
  }, [data?.option_chain, isLoading]);
}

/* ============================================================
 * DESK — analytics overview per underlying
 * ============================================================ */
function DeskView() {
  const { parsed, underlyings, isLoading } = useChain();
  const [showTicket, setShowTicket] = React.useState(false);
  const analytics = React.useMemo(() => computeAnalytics(parsed), [parsed]);

  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile><Metric label="Underlyings" value={underlyings.length} /></MetricTile>
        <MetricTile><Metric label="Contracts" value={parsed.length} /></MetricTile>
        <MetricTile><Metric label="Total OI" value={formatCompact(parsed.reduce((a, c) => a + c.oi, 0))} /></MetricTile>
        <MetricTile><Metric label="Avg IV" value={parsed.length ? formatPercent(parsed.reduce((a, c) => a + c.iv, 0) / parsed.length / 100, { digits: 1 }) : "—"} /></MetricTile>
      </div>

      <Panel icon={Activity} title="Live Analytics per Underlying">
        {isLoading ? <SkeletonRows n={3} /> : analytics.length === 0 ? (
          <Empty icon={Activity} title="No option chain data" description="Run the Zerodha market data sync to populate the chain." />
        ) : (
          <DataTable
            columns={[
              { key: "symbol", header: "Underlying", render: (r) => <strong>{text(r, "symbol")}</strong> },
              { key: "spot", header: "Spot", align: "right", render: (r) => num(r, "spot", 0).toFixed(2) },
              { key: "atm", header: "ATM IV", align: "right", render: (r) => formatPercent(num(r, "atm_iv", 0) / 100, { digits: 1 }) },
              { key: "pcr", header: "PCR", align: "right", render: (r) => <span style={{ color: num(r, "pcr", 0) > 1.2 ? "var(--status-warn)" : num(r, "pcr", 0) < 0.8 ? "var(--status-info)" : "var(--text)" }}>{num(r, "pcr", 0).toFixed(2)}</span> },
              { key: "maxpain", header: "Max Pain", align: "right", render: (r) => num(r, "max_pain", 0).toFixed(0) },
              { key: "callwall", header: "Call Wall", align: "right", render: (r) => num(r, "call_wall", 0).toFixed(0) },
              { key: "putwall", header: "Put Wall", align: "right", render: (r) => num(r, "put_wall", 0).toFixed(0) },
            ]}
            rows={analytics}
            rowKey={(r, i) => text(r, "symbol", `a-${i}`)}
          />
        )}
      </Panel>

      <Panel icon={TrendingDown} title="Options Blotter"
        actions={<Button size="sm" variant="primary" icon={Plus} onClick={() => setShowTicket(true)}>New Option Trade</Button>}
      >
        <Empty icon={TrendingDown} title="No option trades recorded" description="Record a manual option trade — it flows into the blotter and journal." action={<Button size="sm" icon={Plus} onClick={() => setShowTicket(true)}>Record trade</Button>} />
      </Panel>

      <OptionTicketDrawer open={showTicket} onClose={() => setShowTicket(false)} />
    </>
  );
}

function computeAnalytics(chain: ParsedContract[]): LiveRow[] {
  const bySymbol = new Map<string, ParsedContract[]>();
  for (const c of chain) {
    if (!bySymbol.has(c.symbol)) bySymbol.set(c.symbol, []);
    bySymbol.get(c.symbol)!.push(c);
  }
  const out: LiveRow[] = [];
  for (const [symbol, contracts] of bySymbol) {
    const spot = contracts[0]?.spot || 0;
    const calls = contracts.filter((c) => c.type === "CE");
    const puts = contracts.filter((c) => c.type === "PE");
    const totalCallOi = calls.reduce((a, c) => a + c.oi, 0);
    const totalPutOi = puts.reduce((a, c) => a + c.oi, 0);
    const pcr = totalCallOi > 0 ? totalPutOi / totalCallOi : 0;
    const atm = spot > 0 ? contracts.reduce((best, c) => Math.abs(c.strike - spot) < Math.abs(best.strike - spot) ? c : best, contracts[0]) : undefined;
    const strikes = Array.from(new Set(contracts.map((c) => c.strike))).sort((a, b) => a - b);
    let maxPain = 0; let minPayout = Infinity;
    for (const s of strikes) {
      let payout = 0;
      for (const c of contracts) {
        const intrinsic = c.type === "CE" ? Math.max(0, s - c.strike) : Math.max(0, c.strike - s);
        payout += intrinsic * c.oi;
      }
      if (payout < minPayout) { minPayout = payout; maxPain = s; }
    }
    const callWall = calls.reduce((best, c) => c.oi > best.oi ? c : best, calls[0]);
    const putWall = puts.reduce((best, c) => c.oi > best.oi ? c : best, puts[0]);
    out.push({ symbol, spot, atm_iv: atm?.iv ?? 0, pcr, max_pain: maxPain, call_wall: callWall?.strike ?? 0, put_wall: putWall?.strike ?? 0, total_call_oi: totalCallOi, total_put_oi: totalPutOi } as LiveRow);
  }
  return out;
}

/* ============================================================
 * CHAIN
 * ============================================================ */
function ChainView() {
  const { parsed, underlyings, expiries, isLoading } = useChain();
  const [symbol, setSymbol] = React.useState("");
  const [expiry, setExpiry] = React.useState("");
  React.useEffect(() => {
    if (!symbol && underlyings.length) setSymbol(underlyings[0]);
    if (!expiry && expiries.length) setExpiry(expiries[0]);
  }, [underlyings, expiries, symbol, expiry]);

  const filtered = parsed.filter((c) => (!symbol || c.symbol === symbol) && (!expiry || c.expiry === expiry));
  const spot = filtered[0]?.spot ?? 0;
  const atmStrike = spot > 0 ? filtered.reduce((best, c) => Math.abs(c.strike - spot) < Math.abs(best.strike - spot) ? c : best, filtered[0])?.strike : 0;

  return (
    <>
      <Panel icon={BarChart3} title="Option Chain"
        actions={<>
          <Select value={symbol} onChange={(e) => setSymbol(e.target.value)} style={{ width: 120 }}>{underlyings.map((u) => <option key={u}>{u}</option>)}</Select>
          <Select value={expiry} onChange={(e) => setExpiry(e.target.value)} style={{ width: 130 }}>{expiries.map((e) => <option key={e}>{e}</option>)}</Select>
        </>}
      >
        {isLoading ? <SkeletonRows n={6} /> : filtered.length === 0 ? (
          <Empty icon={BarChart3} title="No chain data for this selection" />
        ) : (
          <DataTable
            columns={[
              { key: "strike", header: "Strike", align: "right", render: (r) => <strong style={{ color: num(r, "strike", 0) === atmStrike ? "var(--accent)" : "var(--text)" }}>{num(r, "strike", 0)}</strong> },
              { key: "type", header: "Type", render: (r) => <StatusPill status={text(r, "type")} /> },
              { key: "ltp", header: "LTP", align: "right", render: (r) => formatCurrency(num(r, "ltp", 0)) },
              { key: "oi", header: "OI", align: "right", render: (r) => formatCompact(num(r, "oi", 0)) },
              { key: "oichg", header: "OI Chg", align: "right", render: (r) => <span style={{ color: num(r, "oiChange", 0) >= 0 ? "var(--status-ok)" : "var(--status-risk)" }}>{num(r, "oiChange", 0) >= 0 ? "+" : ""}{formatCompact(num(r, "oiChange", 0))}</span> },
              { key: "iv", header: "IV", align: "right", render: (r) => formatPercent(num(r, "iv", 0) / 100, { digits: 1 }) },
              { key: "vol", header: "Vol", align: "right", render: (r) => formatCompact(num(r, "volume", 0)) },
            ]}
            rows={filtered as unknown as LiveRow[]}
            rowKey={(r, i) => `${text(r, "type")}-${num(r, "strike", 0)}-${i}`}
            dense
          />
        )}
      </Panel>
      <div style={{ fontSize: "var(--text-xs)", color: "var(--text-faint)", textAlign: "right" }}>Spot: <strong>{spot.toFixed(2)}</strong> · {filtered.length} contracts · ATM strike highlighted</div>
    </>
  );
}

/* ============================================================
 * SURFACE — IV smile
 * ============================================================ */
function SurfaceView() {
  const { parsed, underlyings, expiries, isLoading } = useChain();
  const [symbol, setSymbol] = React.useState("");
  const [expiry, setExpiry] = React.useState("");
  React.useEffect(() => {
    if (!symbol && underlyings.length) setSymbol(underlyings[0]);
    if (!expiry && expiries.length) setExpiry(expiries[0]);
  }, [underlyings, expiries, symbol, expiry]);

  const filtered = parsed.filter((c) => c.symbol === symbol && c.expiry === expiry);
  const spot = filtered[0]?.spot ?? 0;
  const aggregated = React.useMemo(() => {
    const map = new Map<number, { strike: number; ceIv?: number; peIv?: number }>();
    for (const c of filtered) {
      const ex = map.get(c.strike) ?? { strike: c.strike };
      if (c.type === "CE") ex.ceIv = c.iv; else ex.peIv = c.iv;
      map.set(c.strike, ex);
    }
    return Array.from(map.values()).sort((a, b) => a.strike - b.strike);
  }, [filtered]);

  return (
    <>
      <Panel icon={LineChart} title={`Implied Volatility Smile — ${symbol} ${expiry}`}
        actions={<>
          <Select value={symbol} onChange={(e) => setSymbol(e.target.value)} style={{ width: 120 }}>{underlyings.map((u) => <option key={u}>{u}</option>)}</Select>
          <Select value={expiry} onChange={(e) => setExpiry(e.target.value)} style={{ width: 130 }}>{expiries.map((e) => <option key={e}>{e}</option>)}</Select>
        </>}
      >
        {isLoading ? <Skeleton style={{ height: 280 }} /> : aggregated.length === 0 ? (
          <Empty icon={LineChart} title="No IV data" description="Sync the Zerodha option chain to see the vol smile." />
        ) : (
          <LineSeriesChart
            data={aggregated as unknown as Record<string, number | string>[]}
            series={[{ key: "ceIv", name: "Call IV", color: "#c94f49" }, { key: "peIv", name: "Put IV", color: "#2f78a7" }]}
            xKey="strike" height={300}
          />
        )}
      </Panel>
      <div style={{ fontSize: "var(--text-xs)", color: "var(--text-faint)", textAlign: "center" }}>
        Spot: <strong>{spot.toFixed(2)}</strong> · Steep put skew (left side elevated) = demand for downside protection.
      </div>
    </>
  );
}

/* ============================================================
 * OI ANALYSIS — OI by strike, OI buildup, straddle curve
 * ============================================================ */
function OiAnalysisView() {
  const { parsed, underlyings, expiries, isLoading } = useChain();
  const [symbol, setSymbol] = React.useState("");
  const [expiry, setExpiry] = React.useState("");
  React.useEffect(() => {
    if (!symbol && underlyings.length) setSymbol(underlyings[0]);
    if (!expiry && expiries.length) setExpiry(expiries[0]);
  }, [underlyings, expiries, symbol, expiry]);

  const filtered = parsed.filter((c) => c.symbol === symbol && c.expiry === expiry);
  const oiByStrike = React.useMemo(() => {
    const map = new Map<number, { strike: number; CE: number; PE: number; ceChg: number; peChg: number }>();
    for (const c of filtered) {
      const ex = map.get(c.strike) ?? { strike: c.strike, CE: 0, PE: 0, ceChg: 0, peChg: 0 };
      if (c.type === "CE") { ex.CE = c.oi; ex.ceChg = c.oiChange; } else { ex.PE = c.oi; ex.peChg = c.oiChange; }
      map.set(c.strike, ex);
    }
    return Array.from(map.values()).sort((a, b) => a.strike - b.strike);
  }, [filtered]);
  const oiChange = React.useMemo(() => oiByStrike.map((d) => ({ strike: d.strike, CE: d.ceChg, PE: d.peChg })), [oiByStrike]);
  const straddle = React.useMemo(() => {
    const map = new Map<number, { strike: number; straddle: number }>();
    for (const c of filtered) {
      const ex = map.get(c.strike) ?? { strike: c.strike, straddle: 0 };
      ex.straddle += c.ltp;
      map.set(c.strike, ex);
    }
    return Array.from(map.values()).sort((a, b) => a.strike - b.strike);
  }, [filtered]);

  const totalCallOi = oiByStrike.reduce((a, d) => a + d.CE, 0);
  const totalPutOi = oiByStrike.reduce((a, d) => a + d.PE, 0);
  const pcr = totalCallOi > 0 ? totalPutOi / totalCallOi : 0;

  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile><Metric label="Total Call OI" value={formatCompact(totalCallOi)} /></MetricTile>
        <MetricTile><Metric label="Total Put OI" value={formatCompact(totalPutOi)} /></MetricTile>
        <MetricTile tone={pcr > 1.2 ? "warn" : pcr < 0.8 ? "ok" : "default"}><Metric label="Put/Call Ratio" value={pcr.toFixed(2)} sub={pcr > 1.2 ? "bearish tilt" : pcr < 0.8 ? "bullish tilt" : "balanced"} /></MetricTile>
      </div>

      <Panel icon={BarChart3} title={`Open Interest by Strike — ${symbol} ${expiry}`}
        actions={<><Select value={symbol} onChange={(e) => setSymbol(e.target.value)} style={{ width: 120 }}>{underlyings.map((u) => <option key={u}>{u}</option>)}</Select><Select value={expiry} onChange={(e) => setExpiry(e.target.value)} style={{ width: 130 }}>{expiries.map((e) => <option key={e}>{e}</option>)}</Select></>}
      >
        {isLoading || oiByStrike.length === 0 ? <Skeleton style={{ height: 300 }} /> : (
          <BarSeriesChart data={oiByStrike as unknown as Record<string, number | string>[]} bars={[{ key: "CE", name: "Call OI", color: "#c94f49" }, { key: "PE", name: "Put OI", color: "#2d8b69" }]} xKey="strike" height={300} />
        )}
      </Panel>

      <Panel icon={Flame} title="OI Buildup (Change in OI) — where money is flowing">
        {oiChange.length === 0 ? <Empty icon={Flame} title="No OI change data" /> : (
          <BarSeriesChart data={oiChange as unknown as Record<string, number | string>[]} bars={[{ key: "CE", name: "Call OI Chg", color: "#c94f49" }, { key: "PE", name: "Put OI Chg", color: "#2d8b69" }]} xKey="strike" height={260} />
        )}
        <div style={{ fontSize: "var(--text-xs)", color: "var(--text-faint)", textAlign: "center", marginTop: "var(--space-2)" }}>Positive bars = OI being added. Call buildup = resistance forming; Put buildup = support forming.</div>
      </Panel>

      <Panel icon={Activity} title="Straddle Curve (CE + PE premium by strike)">
        {straddle.length === 0 ? <Empty icon={Activity} title="No straddle data" /> : (
          <AreaSeriesChart data={straddle as unknown as Record<string, number | string>[]} series={[{ key: "straddle", name: "Straddle" }]} xKey="strike" height={240} />
        )}
        <div style={{ fontSize: "var(--text-xs)", color: "var(--text-faint)", textAlign: "center", marginTop: "var(--space-2)" }}>The straddle minimum marks the market's expected settlement — often near max pain.</div>
      </Panel>
    </>
  );
}

/* ============================================================
 * STRATEGY BUILDER
 * ============================================================ */
interface Leg { id: string; type: "CE" | "PE"; action: "buy" | "sell"; strike: number; qty: number; premium: number; }

function StrategiesView() {
  const { parsed, underlyings, expiries } = useChain();
  const [symbol, setSymbol] = React.useState("NIFTY");
  const [expiry, setExpiry] = React.useState("");
  const [spot, setSpot] = React.useState(22000);
  const [legs, setLegs] = React.useState<Leg[]>([]);
  const [showAdd, setShowAdd] = React.useState(false);

  React.useEffect(() => {
    if (!expiry && expiries.length) setExpiry(expiries[0]);
    const s = parsed.find((c) => c.symbol === symbol)?.spot;
    if (s) setSpot(s);
  }, [parsed, symbol, expiries, expiry]);

  const payoff = React.useMemo(() => {
    if (legs.length === 0) return [];
    const min = spot * 0.85; const max = spot * 1.15; const steps = 60;
    return Array.from({ length: steps }, (_, i) => {
      const s = min + ((max - min) * i) / (steps - 1);
      let pnl = 0;
      for (const leg of legs) {
        const intrinsic = leg.type === "CE" ? Math.max(0, s - leg.strike) : Math.max(0, leg.strike - s);
        const sign = leg.action === "buy" ? 1 : -1;
        pnl += sign * (intrinsic - leg.premium) * leg.qty;
      }
      return { spot: Math.round(s), pnl: Math.round(pnl) };
    });
  }, [legs, spot]);

  function addLeg(leg: Omit<Leg, "id">) { setLegs((prev) => [...prev, { ...leg, id: `leg-${Date.now()}` }]); setShowAdd(false); }
  function removeLeg(id: string) { setLegs((prev) => prev.filter((l) => l.id !== id)); }
  function loadPreset(name: string) {
    const atm = Math.round(spot / 50) * 50;
    if (name === "long-straddle") setLegs([
      { id: "l1", type: "CE", action: "buy", strike: atm, qty: 1, premium: 200 },
      { id: "l2", type: "PE", action: "buy", strike: atm, qty: 1, premium: 200 },
    ]);
    if (name === "iron-condor") setLegs([
      { id: "l1", type: "CE", action: "sell", strike: atm + 200, qty: 1, premium: 80 },
      { id: "l2", type: "CE", action: "buy", strike: atm + 400, qty: 1, premium: 40 },
      { id: "l3", type: "PE", action: "sell", strike: atm - 200, qty: 1, premium: 80 },
      { id: "l4", type: "PE", action: "buy", strike: atm - 400, qty: 1, premium: 40 },
    ]);
    if (name === "bull-call-spread") setLegs([
      { id: "l1", type: "CE", action: "buy", strike: atm, qty: 1, premium: 200 },
      { id: "l2", type: "CE", action: "sell", strike: atm + 200, qty: 1, premium: 100 },
    ]);
  }

  return (
    <>
      <Panel icon={Layers} title="Strategy Builder"
        actions={<>
          <Select value={symbol} onChange={(e) => setSymbol(e.target.value)} style={{ width: 110 }}>{underlyings.map((u) => <option key={u}>{u}</option>)}</Select>
          <Select value={expiry} onChange={(e) => setExpiry(e.target.value)} style={{ width: 120 }}>{expiries.map((e) => <option key={e}>{e}</option>)}</Select>
        </>}
      >
        <div style={{ display: "flex", gap: "var(--space-2)", marginBottom: "var(--space-3)", flexWrap: "wrap" }}>
          <Button size="sm" variant="ghost" onClick={() => loadPreset("long-straddle")}>Long Straddle</Button>
          <Button size="sm" variant="ghost" onClick={() => loadPreset("iron-condor")}>Iron Condor</Button>
          <Button size="sm" variant="ghost" onClick={() => loadPreset("bull-call-spread")}>Bull Call Spread</Button>
          <Button size="sm" variant="ghost" icon={Plus} onClick={() => setShowAdd(true)}>Add Leg</Button>
          <Button size="sm" variant="ghost" onClick={() => setLegs([])}>Clear</Button>
        </div>
        {legs.length === 0 ? (
          <Empty icon={Layers} title="No legs yet" description="Load a preset or add legs manually to see the payoff diagram." />
        ) : (
          <DataTable
            columns={[
              { key: "action", header: "Action", render: (r) => <StatusPill status={text(r, "action")} /> },
              { key: "type", header: "Type", render: (r) => text(r, "type") },
              { key: "strike", header: "Strike", align: "right", render: (r) => num(r, "strike", 0) },
              { key: "qty", header: "Qty", align: "right", render: (r) => num(r, "qty", 0) },
              { key: "premium", header: "Premium", align: "right", render: (r) => formatCurrency(num(r, "premium", 0)) },
              { key: "x", header: "", render: (r) => <Button size="sm" variant="subtle" onClick={() => removeLeg(text(r, "id"))}>×</Button> },
            ]}
            rows={legs as unknown as LiveRow[]}
            rowKey={(r) => text(r, "id")}
            dense
          />
        )}
      </Panel>

      {legs.length > 0 && (
        <Panel icon={LineChart} title="Payoff at Expiry">
          <AreaSeriesChart data={payoff as unknown as Record<string, number | string>[]} series={[{ key: "pnl", name: "P&L", color: "#0f766e" }]} xKey="spot" height={300} yFormat={(v) => formatCompact(v)} />
          <div style={{ fontSize: "var(--text-xs)", color: "var(--text-faint)", textAlign: "center", marginTop: "var(--space-2)" }}>Spot at <strong>{spot.toFixed(0)}</strong>. Breakevens where the curve crosses zero.</div>
        </Panel>
      )}

      <AddLegDrawer open={showAdd} onClose={() => setShowAdd(false)} onAdd={addLeg} defaultStrike={Math.round(spot / 50) * 50} />
    </>
  );
}

function AddLegDrawer({ open, onClose, onAdd, defaultStrike }: { open: boolean; onClose: () => void; onAdd: (leg: Omit<Leg, "id">) => void; defaultStrike: number }) {
  const [leg, setLeg] = React.useState<Omit<Leg, "id">>({ type: "CE", action: "buy", strike: defaultStrike, qty: 1, premium: 100 });
  return (
    <Drawer open={open} onClose={onClose} title="Add Leg" icon={Plus} width={440}
      footer={<div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)" }}><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" icon={Plus} onClick={() => onAdd(leg)}>Add</Button></div>}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-3)" }}>
          <Field label="Type"><Select value={leg.type} onChange={(e) => setLeg({ ...leg, type: e.target.value as "CE" | "PE" })}><option>CE</option><option>PE</option></Select></Field>
          <Field label="Action"><Select value={leg.action} onChange={(e) => setLeg({ ...leg, action: e.target.value as "buy" | "sell" })}><option value="buy">Buy</option><option value="sell">Sell</option></Select></Field>
        </div>
        <Field label="Strike"><TextInput type="number" value={leg.strike} onChange={(e) => setLeg({ ...leg, strike: Number(e.target.value) })} /></Field>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-3)" }}>
          <Field label="Quantity"><TextInput type="number" value={leg.qty} onChange={(e) => setLeg({ ...leg, qty: Number(e.target.value) })} /></Field>
          <Field label="Premium"><TextInput type="number" value={leg.premium} onChange={(e) => setLeg({ ...leg, premium: Number(e.target.value) })} /></Field>
        </div>
      </div>
    </Drawer>
  );
}

/* ============================================================
 * AGENT
 * ============================================================ */
function AgentView() {
  const setAssistantScope = useUIStore((s) => s.setAssistantScope);
  const setAssistantOpen = useUIStore((s) => s.setAssistantOpen);
  const prompts = [
    "Analyze the NIFTY OI buildup — where is resistance and support forming?",
    "What's the max pain for this week's BANKNIFTY expiry?",
    "Build an iron condor thesis for NIFTY given current IV",
    "Is the put-call skew signaling a hedge?",
    "Which strikes have the biggest OI change today?",
  ];
  return (
    <Panel icon={Brain} title="Options Agent">
      <div style={{ padding: "var(--space-6)", textAlign: "center" }}>
        <div style={{ width: 72, height: 72, borderRadius: "50%", margin: "0 auto var(--space-4)", background: "var(--accent-soft)", color: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center" }}><Brain size={32} /></div>
        <h3 style={{ marginBottom: "var(--space-1)" }}>Options Specialist</h3>
        <p style={{ color: "var(--text-muted)", maxWidth: 420, margin: "0 auto var(--space-5)" }}>OI analysis, vol surface reading, strategy construction, and edge identification. Talks you through the Greeks and the flow.</p>
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", maxWidth: 480, margin: "0 auto" }}>
          {prompts.map((p) => (
            <button key={p} onClick={() => { setAssistantScope({ agentKey: "options_agent", agentName: "Options Agent" }); setAssistantOpen(true); sessionStorage.setItem("aios:pending-charlie-question", p); }}
              style={{ padding: "var(--space-3)", background: "var(--surface-soft)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", cursor: "pointer", fontSize: "var(--text-sm)", color: "var(--text-secondary)", textAlign: "left" }}>{p}</button>
          ))}
        </div>
        <Button variant="primary" icon={Brain} style={{ marginTop: "var(--space-5)" }} onClick={() => { setAssistantScope({ agentKey: "options_agent", agentName: "Options Agent" }); setAssistantOpen(true); }}>Open options agent chat</Button>
      </div>
    </Panel>
  );
}

/* ============================================================
 * Manual ticket
 * ============================================================ */
function OptionTicketDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const tradeMut = useRecordManualTrade();
  const pushToast = useUIStore((s) => s.pushToast);
  const [form, setForm] = React.useState({ symbol: "", side: "buy" as "buy" | "sell", quantity: 1, price: 0, option_type: "CE", strike: 0, expiry_date: "", notes: "" });

  function submit() {
    if (!form.symbol || !form.strike || !form.expiry_date) { pushToast({ title: "Symbol, strike, and expiry required", tone: "warn", duration: 2500 }); return; }
    tradeMut.mutate(
      { symbol: form.symbol, side: form.side, quantity: Number(form.quantity), price: Number(form.price), trade_date: form.expiry_date, notes: `${form.option_type} ${form.strike} ${form.expiry_date} — ${form.notes}`, actor: "Devarsh" },
      { onSuccess: () => { pushToast({ title: "Option trade recorded", message: `${form.symbol} ${form.option_type} ${form.strike}`, tone: "ok", duration: 3000 }); onClose(); }, onError: (e) => pushToast({ title: "Record failed", message: e.message, tone: "risk", duration: 5000 }) }
    );
  }

  return (
    <Drawer open={open} onClose={onClose} title="Record Option Trade" icon={Plus} width={520}
      footer={<div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)" }}><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" icon={Play} onClick={submit} disabled={tradeMut.isPending}>Record</Button></div>}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <Field label="Underlying" required><TextInput value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value.toUpperCase() })} placeholder="e.g. NIFTY" /></Field>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-3)" }}>
          <Field label="Type"><Select value={form.option_type} onChange={(e) => setForm({ ...form, option_type: e.target.value })}><option>CE</option><option>PE</option></Select></Field>
          <Field label="Strike" required><TextInput type="number" value={form.strike} onChange={(e) => setForm({ ...form, strike: Number(e.target.value) })} /></Field>
          <Field label="Expiry" required><TextInput type="date" value={form.expiry_date} onChange={(e) => setForm({ ...form, expiry_date: e.target.value })} /></Field>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-3)" }}>
          <Field label="Side"><Select value={form.side} onChange={(e) => setForm({ ...form, side: e.target.value as "buy" | "sell" })}><option value="buy">Buy</option><option value="sell">Sell</option></Select></Field>
          <Field label="Qty (lots)"><TextInput type="number" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })} /></Field>
          <Field label="Premium"><TextInput type="number" value={form.price} onChange={(e) => setForm({ ...form, price: Number(e.target.value) })} /></Field>
        </div>
        <Field label="Notes / Strategy"><TextArea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} rows={2} placeholder="e.g. Bull call spread, earnings play, hedge..." /></Field>
        <div style={{ padding: "var(--space-3)", background: "var(--status-warn-soft)", borderRadius: "var(--radius-sm)", fontSize: "var(--text-xs)", color: "var(--status-warn)" }}>
          <AlertTriangle size={12} style={{ display: "inline", marginRight: 6 }} />Manual record only. No live order is placed.
        </div>
      </div>
    </Drawer>
  );
}

function SkeletonRows({ n = 3 }: { n?: number }) {
  return <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", padding: "var(--space-2)" }}>{Array.from({ length: n }).map((_, i) => <Skeleton key={i} style={{ height: 44 }} />)}</div>;
}
