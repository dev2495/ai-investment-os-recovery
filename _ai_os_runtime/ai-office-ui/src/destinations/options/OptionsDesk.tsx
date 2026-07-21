/**
 * Options Desk Terminal
 *
 * Routes: /options/desk | /chain | /surface | /agent
 *
 * The options home — manual trade entry (you trade options manually,
 * automate over time), live option chain with Greeks, implied vol surface,
 * and a direct line to the options specialist agent.
 *
 * Live execution is NOT here — by design. This is research, analysis, and
 * manual ticket entry that flows into the blotter.
 */

import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  TrendingDown, BarChart3, LineChart, Brain, Plus, Calculator,
  AlertTriangle, Target, Activity,
} from "lucide-react";
import { useTradingQuantRisk } from "../../data/queries";
import { useRecordManualTrade } from "../../data/actions";
import { useUIStore } from "../../store";
import {
  Panel, MetricTile, Metric, DataTable, StatusPill, Badge, Empty, Skeleton,
  Button, Tabs, Drawer, Field, TextInput, TextArea, Select, SegmentedControl,
} from "../../system/primitives";
import { AreaSeriesChart } from "../../system/charts";
import { text, num, formatRelative, formatCurrency, formatCompact, formatPercent } from "../../data/liveRow";
import type { LiveRow } from "../../data/liveRow";

const TABS = [
  { key: "desk", label: "Options Desk", icon: TrendingDown },
  { key: "chain", label: "Option Chain", icon: BarChart3 },
  { key: "surface", label: "Vol Surface", icon: LineChart },
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
          <span style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>manual trading · automate over time</span>
        </div>
        <div className="aios-destination__subtitle">
          Option chains with Greeks, implied vol surface, manual trade entry, and a specialist options agent.
          No live execution — by design.
        </div>
        <Tabs tabs={TABS} active={tab} onChange={setTab} />
      </div>

      {tab === "desk" && <DeskView />}
      {tab === "chain" && <ChainView />}
      {tab === "surface" && <SurfaceView />}
      {tab === "agent" && <AgentView />}
    </div>
  );
}

/* ============================================================
 * DESK — overview + manual ticket
 * ============================================================ */
function DeskView() {
  const { data, isLoading } = useTradingQuantRisk();
  const surface = data?.options_surface ?? [];
  const blotter = data?.trade_activity?.filter((r) => text(r, "asset_class", "").includes("option") || text(r, "instrument_type", "").includes("option")) ?? [];
  const [showTicket, setShowTicket] = React.useState(false);

  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile><Metric label="Open Option Positions" value={blotter.length} /></MetricTile>
        <MetricTile><Metric label="Symbols w/ Surface" value={new Set(surface.map((r) => text(r, "symbol"))).size} /></MetricTile>
        <MetricTile><Metric label="ATM IV (NIFTY)" value={formatPercent(num(surface.find((r) => text(r, "symbol") === "NIFTY"), "atm_iv", 0))} /></MetricTile>
      </div>

      <Panel icon={TrendingDown} title="Options Blotter"
        actions={<Button size="sm" variant="primary" icon={Plus} onClick={() => setShowTicket(true)}>New Option Trade</Button>}
      >
        {isLoading ? <SkeletonGrid rows={4} /> : blotter.length === 0 ? (
          <Empty icon={TrendingDown} title="No option trades yet" description="Record a manual option trade to populate the blotter." action={<Button size="sm" icon={Plus} onClick={() => setShowTicket(true)}>Record trade</Button>} />
        ) : (
          <DataTable
            columns={[
              { key: "symbol", header: "Underlying", render: (r) => <strong>{text(r, "symbol")}</strong> },
              { key: "strike", header: "Strike", align: "right", render: (r) => num(r, "strike", 0) },
              { key: "type", header: "Type", render: (r) => text(r, "option_type", "—") },
              { key: "expiry", header: "Expiry", render: (r) => text(r, "expiry_date", "—") },
              { key: "qty", header: "Qty", align: "right", render: (r) => num(r, "quantity", 0) },
              { key: "premium", header: "Premium", align: "right", render: (r) => formatCurrency(num(r, "premium", num(r, "price", 0))) },
              { key: "side", header: "Side", render: (r) => <StatusPill status={text(r, "side", "buy")} /> },
            ]}
            rows={blotter}
            rowKey={(r, i) => String(text(r, "trade_id", text(r, "id", i)))}
          />
        )}
      </Panel>

      <OptionTicketDrawer open={showTicket} onClose={() => setShowTicket(false)} />
    </>
  );
}

function OptionTicketDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const tradeMut = useRecordManualTrade();
  const pushToast = useUIStore((s) => s.pushToast);
  const [form, setForm] = React.useState({
    symbol: "",
    side: "buy" as "buy" | "sell",
    quantity: 1,
    price: 0,
    option_type: "CE",
    strike: 0,
    expiry_date: "",
    notes: "",
  });

  function submit() {
    if (!form.symbol || !form.strike || !form.expiry_date) {
      pushToast({ title: "Symbol, strike, and expiry required", tone: "warn", duration: 2500 });
      return;
    }
    tradeMut.mutate(
      { symbol: form.symbol, side: form.side, quantity: Number(form.quantity), price: Number(form.price), trade_date: form.expiry_date, notes: `${form.option_type} ${form.strike} ${form.expiry_date} — ${form.notes}`, actor: "Devarsh" },
      {
        onSuccess: () => { pushToast({ title: "Option trade recorded", message: `${form.symbol} ${form.option_type} ${form.strike}`, tone: "ok", duration: 3000 }); onClose(); },
        onError: (e) => pushToast({ title: "Record failed", message: e.message, tone: "risk", duration: 5000 }),
      }
    );
  }

  return (
    <Drawer open={open} onClose={onClose} title="Record Option Trade" icon={Plus} width={520}
      footer={<div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)" }}><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" icon={Plus} onClick={submit} disabled={tradeMut.isPending}>Record</Button></div>}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <Field label="Underlying Symbol" required><TextInput value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value.toUpperCase() })} placeholder="e.g. NIFTY" /></Field>
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
          <AlertTriangle size={12} style={{ display: "inline", marginRight: 6 }} />
          Manual record only. No live order is placed. This flows into the blotter for tracking.
        </div>
      </div>
    </Drawer>
  );
}

/* ============================================================
 * CHAIN — live option chain with Greeks
 * ============================================================ */
function ChainView() {
  const { data, isLoading } = useTradingQuantRisk();
  const chain = data?.option_chain ?? [];
  const [symbol, setSymbol] = React.useState("");
  const filtered = symbol ? chain.filter((r) => text(r, "symbol").toUpperCase() === symbol.toUpperCase()) : chain;

  return (
    <>
      <Panel icon={BarChart3} title="Option Chain"
        actions={<TextInput placeholder="Filter symbol…" value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} style={{ width: 160 }} />}
      >
        {isLoading ? <SkeletonGrid rows={6} /> : filtered.length === 0 ? (
          <Empty icon={BarChart3} title="No option chain data" description="Chain data populates from the Zerodha market data sync." />
        ) : (
          <DataTable
            columns={[
              { key: "symbol", header: "Symbol", render: (r) => <strong>{text(r, "symbol")}</strong> },
              { key: "strike", header: "Strike", align: "right", render: (r) => num(r, "strike", 0) },
              { key: "type", header: "Type", render: (r) => text(r, "option_type", "—") },
              { key: "expiry", header: "Expiry", render: (r) => text(r, "expiry_date", "—") },
              { key: "ltp", header: "LTP", align: "right", render: (r) => formatCurrency(num(r, "last_price", num(r, "ltp", 0))) },
              { key: "iv", header: "IV", align: "right", render: (r) => formatPercent(num(r, "implied_volatility", num(r, "iv", 0))) },
              { key: "delta", header: "Δ", align: "right", render: (r) => num(r, "delta", 0).toFixed(2) },
              { key: "gamma", header: "Γ", align: "right", render: (r) => num(r, "gamma", 0).toFixed(3) },
              { key: "theta", header: "Θ", align: "right", render: (r) => num(r, "theta", 0).toFixed(2) },
              { key: "oi", header: "OI", align: "right", render: (r) => formatCompact(num(r, "open_interest", num(r, "oi", 0))) },
            ]}
            rows={filtered.slice(0, 100)}
            rowKey={(r, i) => String(text(r, "instrument_token", text(r, "id", i)))}
            dense
          />
        )}
      </Panel>
    </>
  );
}

/* ============================================================
 * SURFACE — implied vol surface + skew
 * ============================================================ */
function SurfaceView() {
  const { data, isLoading } = useTradingQuantRisk();
  const surface = data?.options_surface ?? [];

  return (
    <>
      <Panel icon={LineChart} title="Implied Volatility Surface">
        {isLoading ? <Skeleton style={{ height: 240 }} /> : surface.length === 0 ? (
          <Empty icon={LineChart} title="No vol surface data" description="The surface builds from the option chain once market data is synced." />
        ) : (
          <DataTable
            columns={[
              { key: "symbol", header: "Symbol", render: (r) => <strong>{text(r, "symbol")}</strong> },
              { key: "atm", header: "ATM IV", align: "right", render: (r) => formatPercent(num(r, "atm_iv", 0)) },
              { key: "skew", header: "Skew", align: "right", render: (r) => <span style={{ color: num(r, "skew", 0) < 0 ? "var(--status-risk)" : "var(--status-ok)" }}>{num(r, "skew", 0).toFixed(2)}</span> },
              { key: "term", header: "Term Structure", align: "right", render: (r) => num(r, "term_structure_slope", 0).toFixed(3) },
              { key: "pcr", header: "P/C Ratio", align: "right", render: (r) => num(r, "put_call_ratio", 0).toFixed(2) },
              { key: "max_pain", header: "Max Pain", align: "right", render: (r) => num(r, "max_pain", 0) },
            ]}
            rows={surface}
            rowKey={(r, i) => String(text(r, "symbol", `s-${i}`))}
          />
        )}
      </Panel>
    </>
  );
}

/* ============================================================
 * AGENT — talk to the options specialist
 * ============================================================ */
function AgentView() {
  const setAssistantScope = useUIStore((s) => s.setAssistantScope);
  const setAssistantOpen = useUIStore((s) => s.setAssistantOpen);

  const quickPrompts = [
    "Analyze the NIFTY vol surface — where is skew richest?",
    "What's the optimal hedge for a long delta portfolio right now?",
    "Build a calendar spread thesis for BANKNIFTY",
    "Explain the put-call parity violation I should never ignore",
  ];

  return (
    <Panel icon={Brain} title="Options Agent">
      <div style={{ padding: "var(--space-6)", textAlign: "center" }}>
        <div style={{
          width: 72, height: 72, borderRadius: "50%", margin: "0 auto var(--space-4)",
          background: "var(--accent-soft)", color: "var(--accent)",
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <Brain size={32} />
        </div>
        <h3 style={{ marginBottom: "var(--space-1)" }}>Options Specialist</h3>
        <p style={{ color: "var(--text-muted)", maxWidth: 420, margin: "0 auto var(--space-5)" }}>
          A dedicated agent for options strategy, Greeks analysis, vol arbitrage, and risk.
          It can analyze surfaces, build spread theses, and flag mispricings.
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", maxWidth: 480, margin: "0 auto" }}>
          {quickPrompts.map((p) => (
            <button
              key={p}
              onClick={() => { setAssistantScope({ agentKey: "options_agent", agentName: "Options Agent" }); setAssistantOpen(true); sessionStorage.setItem("aios:pending-charlie-question", p); }}
              style={{ padding: "var(--space-3)", background: "var(--surface-soft)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", cursor: "pointer", fontSize: "var(--text-sm)", color: "var(--text-secondary)", textAlign: "left" }}
            >
              {p}
            </button>
          ))}
        </div>
        <Button variant="primary" icon={Brain} style={{ marginTop: "var(--space-5)" }} onClick={() => { setAssistantScope({ agentKey: "options_agent", agentName: "Options Agent" }); setAssistantOpen(true); }}>Open options agent chat</Button>
      </div>
    </Panel>
  );
}

function SkeletonGrid({ rows = 4 }: { rows?: number }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", padding: "var(--space-3)" }}>
      {Array.from({ length: rows }).map((_, i) => <Skeleton key={i} style={{ height: 40 }} />)}
    </div>
  );
}
