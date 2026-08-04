/**
 * Institutional Options Desk beta.
 *
 * Routes: /options/desk | /chain | /surface | /oi-analysis | /strategies | /agent
 *
 * Calculated analytics are displayed only when their deterministic result has
 * passed the institutional validation contract. Broker data remains read-only.
 */

import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
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
import { text, num, raw, formatCurrency, formatCompact, formatPercent, formatRelative } from "../../data/liveRow";
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
  const location = useLocation();
  const navigate = useNavigate();
  const tab = location.pathname.split("/").filter(Boolean).slice(-1)[0] ?? defaultTab;
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
          Real-time option chain, OI buildup analysis, provider-qualified vol analytics, straddle curves, max pain,
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
  ltp: number; oi: number; oiChange: number | null; iv: number | null; volume: number; spot: number;
  delta: number | null; gamma: number | null; theta: number | null; vega: number | null;
}

function optionalNum(row: LiveRow, key: string): number | null {
  const source = raw(row, key);
  if (source === null || source === undefined || source === "") return null;
  const parsed = typeof source === "number" ? source : Number(source);
  return Number.isFinite(parsed) ? parsed : null;
}

function booleanValue(row: LiveRow, key: string): boolean {
  const value = raw(row, key);
  return value === true || value === "true" || value === 1 || value === "1";
}

function ivPercent(iv: number): number {
  return iv > 3 ? iv : iv * 100;
}

function useChain() {
  const { data, isLoading } = useTradingQuantRisk();
  return React.useMemo(() => {
    const institutional = data?.institutional_option_chain ?? [];
    const raw = institutional.length > 0 ? institutional : data?.option_chain ?? [];
    const oiChanges = new Map(
      (data?.option_oi_change ?? []).map((row) => {
        const key = [text(row, "underlying"), text(row, "expiry", text(row, "expiry_date")), num(row, "strike", 0), text(row, "option_type").toUpperCase()].join("|");
        return [key, optionalNum(row, "open_interest_change")] as const;
      }),
    );
    const parsed: ParsedContract[] = raw.map((r) => {
      const greeksValidated = booleanValue(r, "greeks_validated");
      return ({
      symbol: text(r, "underlying", text(r, "symbol", "")),
      expiry: text(r, "expiry", text(r, "expiry_date", "")),
      strike: num(r, "strike", 0),
      type: (text(r, "option_type", "CE").toUpperCase().startsWith("P") ? "PE" : "CE") as "CE" | "PE",
      ltp: num(r, "last_price", num(r, "ltp", 0)),
      oi: num(r, "open_interest", num(r, "oi", 0)),
      oiChange: oiChanges.get([text(r, "underlying", text(r, "symbol", "")), text(r, "expiry", text(r, "expiry_date")), num(r, "strike", 0), text(r, "option_type", "CE").toUpperCase()].join("|")) ?? null,
      iv: greeksValidated ? optionalNum(r, "implied_volatility") : null,
      volume: num(r, "volume", 0),
      spot: num(r, "spot_price", num(r, "reference_spot", 0)),
      delta: greeksValidated ? optionalNum(r, "delta") : null,
      gamma: greeksValidated ? optionalNum(r, "gamma") : null,
      theta: greeksValidated ? optionalNum(r, "theta") : null,
      vega: greeksValidated ? optionalNum(r, "vega") : null,
    });
    });
    return { parsed, isLoading, underlyings: Array.from(new Set(parsed.map((p) => p.symbol))).sort(), expiries: Array.from(new Set(parsed.map((p) => p.expiry))).sort() };
  }, [data?.institutional_option_chain, data?.option_chain, data?.option_oi_change, isLoading]);
}

/* ============================================================
 * DESK — analytics overview per underlying
 * ============================================================ */
function DeskView() {
  const { parsed, underlyings, isLoading } = useChain();
  const { data: tradingData } = useTradingQuantRisk();
  const [showTicket, setShowTicket] = React.useState(false);
  const analytics = React.useMemo(() => computeAnalytics(parsed), [parsed]);
  const validIv = parsed.map((contract) => contract.iv).filter((iv): iv is number => iv !== null && iv > 0);
  const acceptance = tradingData?.option_acceptance ?? [];
  const openAnalyticsAlerts = (tradingData?.option_analytics_alerts ?? []).filter((row) => text(row, "status") === "open");
  const specialistObservations = tradingData?.option_specialist_observations ?? [];
  const replaySessions = tradingData?.option_replays ?? [];
  const optionTrades = React.useMemo(
    () => (tradingData?.trade_activity ?? []).filter((row) => {
      const instrumentType = text(row, "instrument_type", text(row, "asset_class", "")).toLowerCase();
      const optionType = text(row, "option_type", "").toUpperCase();
      const notes = text(row, "notes", text(row, "thesis", "")).toUpperCase();
      return instrumentType.includes("option") || ["CE", "PE"].includes(optionType) || /\b(CE|PE)\b/.test(notes);
    }),
    [tradingData?.trade_activity],
  );

  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile><Metric label="Underlyings" value={underlyings.length} /></MetricTile>
        <MetricTile><Metric label="Contracts" value={parsed.length} /></MetricTile>
        <MetricTile><Metric label="Total OI" value={formatCompact(parsed.reduce((a, c) => a + c.oi, 0))} /></MetricTile>
        <MetricTile><Metric label="Avg IV" value={validIv.length ? `${(validIv.reduce((sum, iv) => sum + ivPercent(iv), 0) / validIv.length).toFixed(1)}%` : "Unavailable"} sub={validIv.length ? undefined : "Kite quotes do not supply IV"} /></MetricTile>
      </div>

      <Panel icon={AlertTriangle} title="Institutional Analytics Readiness">
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: "var(--space-3)" }}>
          <MetricTile tone={acceptance.some((row) => text(row, "status") === "passed") ? "ok" : "warn"}>
            <Metric label="Acceptance Runs" value={acceptance.length} sub={acceptance.length ? text(acceptance[0], "status", "pending") : "not yet demonstrated"} />
          </MetricTile>
          <MetricTile tone={openAnalyticsAlerts.length ? "warn" : "default"}>
            <Metric label="Open Alerts" value={openAnalyticsAlerts.length} sub="evidence-backed analytics alerts" />
          </MetricTile>
          <MetricTile><Metric label="Replay Sessions" value={replaySessions.length} sub="point-in-time, paper only" /></MetricTile>
          <MetricTile><Metric label="Specialist Notes" value={specialistObservations.length} sub="human review required" /></MetricTile>
        </div>
        {acceptance.length === 0 && (
          <div style={{ marginTop: "var(--space-3)", color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>
            IV, Greeks, exposure and replay capabilities remain unavailable until a real live-market acceptance run passes. No broker write is permitted.
          </div>
        )}
      </Panel>

      <Panel icon={Activity} title="Live Analytics per Underlying">
        {isLoading ? <SkeletonRows n={3} /> : analytics.length === 0 ? (
          <Empty icon={Activity} title="No option chain data" description="Run the Zerodha market data sync to populate the chain." />
        ) : (
          <DataTable
            columns={[
              { key: "symbol", header: "Underlying", render: (r) => <strong>{text(r, "symbol")}</strong> },
              { key: "spot", header: "Spot", align: "right", render: (r) => num(r, "spot", 0).toFixed(2) },
              { key: "atm", header: "ATM IV", align: "right", render: (r) => optionalNum(r, "atm_iv") === null ? "—" : `${ivPercent(optionalNum(r, "atm_iv")!).toFixed(1)}%` },
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
        {optionTrades.length === 0 ? (
          <Empty icon={TrendingDown} title="No option trades recorded" description="Record a manual option trade - it flows into the blotter and journal." action={<Button size="sm" icon={Plus} onClick={() => setShowTicket(true)}>Record trade</Button>} />
        ) : (
          <DataTable
            columns={[
              { key: "contract", header: "Contract", render: (row) => {
                const parts = [
                  text(row, "symbol"),
                  text(row, "expiry_date"),
                  num(row, "strike", 0) || "",
                  text(row, "option_type"),
                ].filter(Boolean);
                return <><strong>{parts.join(" ")}</strong><div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{text(row, "strategy_name", text(row, "thesis", "manual option trade"))}</div></>;
              } },
              { key: "side", header: "Side", render: (row) => <StatusPill status={text(row, "side", text(row, "direction"))} /> },
              { key: "quantity", header: "Qty", align: "right", render: (row) => num(row, "quantity", num(row, "qty", 0)) },
              { key: "price", header: "Premium", align: "right", render: (row) => formatCurrency(num(row, "price", num(row, "trade_price", 0))) },
              { key: "book", header: "Book", render: (row) => text(row, "book_key", text(row, "book_name", "unassigned")) },
              { key: "when", header: "Recorded", render: (row) => formatRelative(text(row, "trade_ts", text(row, "created_at"))) },
            ]}
            rows={optionTrades}
            rowKey={(row, index) => text(row, "trade_id", text(row, "id", `option-trade-${index}`))}
            dense
          />
        )}
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
    out.push({ symbol, spot, atm_iv: atm?.iv ?? null, pcr, max_pain: maxPain, call_wall: callWall?.strike ?? 0, put_wall: putWall?.strike ?? 0, total_call_oi: totalCallOi, total_put_oi: totalPutOi } as LiveRow);
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
              { key: "oichg", header: "OI Chg", align: "right", render: (r) => optionalNum(r, "oiChange") === null ? "—" : <span style={{ color: optionalNum(r, "oiChange")! >= 0 ? "var(--status-ok)" : "var(--status-risk)" }}>{optionalNum(r, "oiChange")! >= 0 ? "+" : ""}{formatCompact(optionalNum(r, "oiChange")!)}</span> },
              { key: "iv", header: "IV", align: "right", render: (r) => optionalNum(r, "iv") === null ? "—" : `${ivPercent(optionalNum(r, "iv")!).toFixed(1)}%` },
              { key: "delta", header: "Delta", align: "right", render: (r) => optionalNum(r, "delta")?.toFixed(3) ?? "—" },
              { key: "gamma", header: "Gamma", align: "right", render: (r) => optionalNum(r, "gamma")?.toFixed(4) ?? "—" },
              { key: "theta", header: "Theta", align: "right", render: (r) => optionalNum(r, "theta")?.toFixed(2) ?? "—" },
              { key: "vega", header: "Vega", align: "right", render: (r) => optionalNum(r, "vega")?.toFixed(2) ?? "—" },
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

  const filtered = parsed.filter((c) => c.symbol === symbol && c.expiry === expiry && c.iv !== null && c.iv > 0);
  const spot = filtered[0]?.spot ?? 0;
  const aggregated = React.useMemo(() => {
    const map = new Map<number, { strike: number; ceIv?: number; peIv?: number }>();
    for (const c of filtered) {
      const ex = map.get(c.strike) ?? { strike: c.strike };
      if (c.type === "CE") ex.ceIv = ivPercent(c.iv!); else ex.peIv = ivPercent(c.iv!);
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
      if (c.type === "CE") { ex.CE = c.oi; ex.ceChg = c.oiChange ?? 0; } else { ex.PE = c.oi; ex.peChg = c.oiChange ?? 0; }
      map.set(c.strike, ex);
    }
    return Array.from(map.values()).sort((a, b) => a.strike - b.strike);
  }, [filtered]);
  const oiChange = React.useMemo(() => parsed.some((contract) => contract.oiChange !== null) ? oiByStrike.map((d) => ({ strike: d.strike, CE: d.ceChg, PE: d.peChg })) : [], [oiByStrike, parsed]);
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
  const { parsed, underlyings } = useChain();
  const [symbol, setSymbol] = React.useState("");
  const [expiry, setExpiry] = React.useState("");
  const [legs, setLegs] = React.useState<Leg[]>([]);
  const [showAdd, setShowAdd] = React.useState(false);

  const symbolExpiries = React.useMemo(
    () => Array.from(new Set(parsed.filter((contract) => contract.symbol === symbol).map((contract) => contract.expiry))).sort(),
    [parsed, symbol],
  );
  React.useEffect(() => {
    if (underlyings.length && !underlyings.includes(symbol)) setSymbol(underlyings[0]);
  }, [underlyings, symbol]);
  React.useEffect(() => {
    if (symbolExpiries.length && !symbolExpiries.includes(expiry)) setExpiry(symbolExpiries[0]);
  }, [symbolExpiries, expiry]);

  const activeContracts = React.useMemo(
    () => parsed.filter((contract) => contract.symbol === symbol && contract.expiry === expiry),
    [parsed, symbol, expiry],
  );
  const spot = activeContracts.find((contract) => contract.spot > 0)?.spot ?? 0;
  const strikes = Array.from(new Set(activeContracts.map((contract) => contract.strike))).sort((a, b) => a - b);
  const atmIndex = spot > 0 && strikes.length
    ? strikes.reduce((best, strike, index) => Math.abs(strike - spot) < Math.abs(strikes[best] - spot) ? index : best, 0)
    : -1;
  const atmStrike = atmIndex >= 0 ? strikes[atmIndex] : 0;

  const payoff = React.useMemo(() => {
    if (legs.length === 0 || spot <= 0) return [];
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
    const contract = (type: "CE" | "PE", index: number) => {
      const strike = strikes[index];
      return strike === undefined
        ? undefined
        : activeContracts.find((item) => item.type === type && item.strike === strike && item.ltp > 0);
    };
    const leg = (item: ParsedContract, action: "buy" | "sell", id: string): Leg => ({
      id: `${id}-${Date.now()}`,
      type: item.type,
      action,
      strike: item.strike,
      qty: 1,
      premium: item.ltp,
    });

    if (name === "long-straddle") {
      const call = contract("CE", atmIndex);
      const put = contract("PE", atmIndex);
      if (call && put) setLegs([leg(call, "buy", "straddle-call"), leg(put, "buy", "straddle-put")]);
    }
    if (name === "iron-condor") {
      const shortCall = contract("CE", atmIndex + 1);
      const longCall = contract("CE", atmIndex + 2);
      const shortPut = contract("PE", atmIndex - 1);
      const longPut = contract("PE", atmIndex - 2);
      if (shortCall && longCall && shortPut && longPut) {
        setLegs([
          leg(shortCall, "sell", "condor-short-call"),
          leg(longCall, "buy", "condor-long-call"),
          leg(shortPut, "sell", "condor-short-put"),
          leg(longPut, "buy", "condor-long-put"),
        ]);
      }
    }
    if (name === "bull-call-spread") {
      const longCall = contract("CE", atmIndex);
      const shortCall = contract("CE", atmIndex + 1);
      if (longCall && shortCall) setLegs([leg(longCall, "buy", "spread-long-call"), leg(shortCall, "sell", "spread-short-call")]);
    }
  }

  const liveChainReady = spot > 0 && activeContracts.some((contract) => contract.ltp > 0);

  return (
    <>
      <Panel icon={Layers} title="Strategy Builder"
        actions={<>
          <Select value={symbol} onChange={(e) => setSymbol(e.target.value)} style={{ width: 110 }}>{underlyings.map((u) => <option key={u}>{u}</option>)}</Select>
          <Select value={expiry} onChange={(e) => setExpiry(e.target.value)} style={{ width: 130 }}>{symbolExpiries.map((e) => <option key={e}>{e}</option>)}</Select>
        </>}
      >
        <div style={{ display: "flex", gap: "var(--space-2)", marginBottom: "var(--space-3)", flexWrap: "wrap" }}>
          <Button size="sm" variant="ghost" onClick={() => loadPreset("long-straddle")} disabled={!liveChainReady}>Long Straddle</Button>
          <Button size="sm" variant="ghost" onClick={() => loadPreset("iron-condor")} disabled={!liveChainReady}>Iron Condor</Button>
          <Button size="sm" variant="ghost" onClick={() => loadPreset("bull-call-spread")} disabled={!liveChainReady}>Bull Call Spread</Button>
          <Button size="sm" variant="ghost" icon={Plus} onClick={() => setShowAdd(true)} disabled={!liveChainReady}>Add Leg</Button>
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

      <AddLegDrawer open={showAdd} onClose={() => setShowAdd(false)} onAdd={addLeg} defaultStrike={atmStrike} />
    </>
  );
}

function AddLegDrawer({ open, onClose, onAdd, defaultStrike }: { open: boolean; onClose: () => void; onAdd: (leg: Omit<Leg, "id">) => void; defaultStrike: number }) {
  const [leg, setLeg] = React.useState<Omit<Leg, "id">>({ type: "CE", action: "buy", strike: defaultStrike, qty: 1, premium: 0 });
  React.useEffect(() => {
    if (open) setLeg({ type: "CE", action: "buy", strike: defaultStrike, qty: 1, premium: 0 });
  }, [open, defaultStrike]);
  return (
    <Drawer open={open} onClose={onClose} title="Add Leg" icon={Plus} width={440}
      footer={<div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)" }}><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" icon={Plus} onClick={() => onAdd(leg)} disabled={leg.strike <= 0 || leg.premium <= 0 || leg.qty <= 0}>Add</Button></div>}
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
      {
        symbol: form.symbol,
        exchange: "NFO",
        instrument_type: "option",
        option_type: form.option_type as "CE" | "PE",
        strike: Number(form.strike),
        expiry_date: form.expiry_date,
        strategy_name: form.notes.trim() || undefined,
        setup_type: form.notes.trim() || "manual_option_trade",
        side: form.side,
        quantity: Number(form.quantity),
        price: Number(form.price),
        thesis: form.notes.trim() || undefined,
        notes: form.notes.trim() || undefined,
        tags: ["option", form.option_type.toLowerCase(), "manual_actual"],
        actor: "Devarsh",
      },
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
