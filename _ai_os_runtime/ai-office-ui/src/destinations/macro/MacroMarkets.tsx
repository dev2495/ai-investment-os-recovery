/**
 * Macro & Markets Terminal
 *
 * Routes: /macro/dashboard | /markets | /news | /calendar
 *
 * Macro observations, regime, market quotes, news feed, and the market
 * calendar (earnings, ex-dates, RBI/Fed, holidays).
 */

import React from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Globe2, TrendingUp, Newspaper, Calendar, Activity, Sparkles } from "lucide-react";
import { useMissionControl, useResearchIdeas } from "../../data/queries";
import { useIngestMarketNews } from "../../data/actions";
import { useUIStore } from "../../store";
import {
  Panel, MetricTile, Metric, DataTable, StatusPill, Badge, Empty, Skeleton,
  Button, Tabs,
} from "../../system/primitives";
import { text, num, formatRelative, formatCompact } from "../../data/liveRow";

const TABS = [
  { key: "dashboard", label: "Macro Dashboard", icon: Globe2 },
  { key: "markets", label: "Markets", icon: TrendingUp },
  { key: "news", label: "News & Events", icon: Newspaper },
  { key: "calendar", label: "Market Calendar", icon: Calendar },
];

export default function MacroMarkets({ defaultTab = "dashboard" }: { defaultTab?: string }) {
  const params = useParams();
  const navigate = useNavigate();
  const tab = params.tab ?? defaultTab;
  function setTab(key: string) { navigate(`/macro/${key}`); }

  return (
    <div className="aios-destination">
      <div className="aios-destination__head">
        <div className="aios-destination__title-row">
          <div className="aios-destination__title">
            <Globe2 size={26} style={{ verticalAlign: "middle", marginRight: 10, color: "var(--accent)" }} />
            Macro & Markets
          </div>
          <Badge tone="accent">MACRO</Badge>
        </div>
        <div className="aios-destination__subtitle">
          Macro observations, regime, indices, sector rotation, news, and the market calendar.
        </div>
        <Tabs tabs={TABS} active={tab} onChange={setTab} />
      </div>

      {tab === "dashboard" && <DashboardView />}
      {tab === "markets" && <MarketsView />}
      {tab === "news" && <NewsView />}
      {tab === "calendar" && <CalendarView />}
    </div>
  );
}

function DashboardView() {
  const { data: mission, isLoading } = useMissionControl();
  const { data: research } = useResearchIdeas();
  const macros = research?.market_events ?? mission?.market_events ?? [];
  const holidays = mission?.market_holidays ?? [];

  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile><Metric label="Macro Observations" value={macros.length} /></MetricTile>
        <MetricTile><Metric label="Upcoming Holidays" value={holidays.length} /></MetricTile>
        <MetricTile><Metric label="News Items" value={research?.latest_news?.length ?? mission?.latest_news?.length ?? 0} /></MetricTile>
        <MetricTile><Metric label="Feeds" value={research?.feed_registry?.length ?? 0} /></MetricTile>
      </div>

      <Panel icon={Activity} title="Macro Observations">
        {isLoading ? <SkeletonGrid rows={4} /> : macros.length === 0 ? (
          <Empty icon={Activity} title="No macro observations" description="Macro data (rates, FX, commodities, regime) populates from the macro ingestion pipeline." />
        ) : (
          <DataTable
            columns={[
              { key: "indicator", header: "Indicator", render: (r) => <strong>{text(r, "indicator_name", text(r, "name", text(r, "title")))}</strong> },
              { key: "value", header: "Value", align: "right", render: (r) => <strong>{text(r, "value", text(r, "observation_value", "—"))}</strong> },
              { key: "unit", header: "Unit", render: (r) => text(r, "unit", "") },
              { key: "period", header: "Period", render: (r) => text(r, "period", text(r, "as_of", "—")) },
              { key: "source", header: "Source", render: (r) => text(r, "source", "") },
              { key: "when", header: "When", render: (r) => formatRelative(text(r, "published_at", text(r, "observed_at", text(r, "created_at")))) },
            ]}
            rows={macros}
            rowKey={(r, i) => String(text(r, "observation_id", text(r, "id", i)))}
          />
        )}
      </Panel>
    </>
  );
}

function MarketsView() {
  const { data: research } = useResearchIdeas();
  const quotes = research?.market_events?.filter((r) => text(r, "indicator_name", text(r, "name")).toLowerCase().includes("index")) ?? [];

  return (
    <Panel icon={TrendingUp} title="Market Quotes">
      {quotes.length === 0 ? (
        <Empty icon={TrendingUp} title="No index quotes" description="NIFTY, BANKNIFTY, SENSEX quotes flow from the market data sync." />
      ) : (
        <DataTable
          columns={[
            { key: "name", header: "Index", render: (r) => <strong>{text(r, "indicator_name", text(r, "name"))}</strong> },
            { key: "value", header: "Value", align: "right", render: (r) => formatCompact(num(r, "value", 0)) },
            { key: "change", header: "Change", align: "right", render: (r) => <span style={{ color: num(r, "change_pct", 0) >= 0 ? "var(--status-ok)" : "var(--status-risk)" }}>{num(r, "change_pct", 0).toFixed(2)}%</span> },
          ]}
          rows={quotes}
          rowKey={(r, i) => String(text(r, "id", i))}
        />
      )}
    </Panel>
  );
}

function NewsView() {
  const { data: mission } = useMissionControl();
  const { data: research } = useResearchIdeas();
  const news = [...(research?.latest_news ?? []), ...(mission?.latest_news ?? [])];
  const newsMut = useIngestMarketNews();
  const pushToast = useUIStore((s) => s.pushToast);
  const openEvidence = useUIStore((s) => s.openEvidence);

  return (
    <Panel icon={Newspaper} title="News & Events"
      actions={<Button size="sm" variant="ghost" icon={Sparkles} onClick={() => newsMut.mutate({ actor: "Devarsh" }, { onSuccess: () => pushToast({ title: "News ingestion triggered", tone: "ok", duration: 3000 }), onError: (e) => pushToast({ title: "Ingest failed", message: e.message, tone: "risk", duration: 5000 }) })} disabled={newsMut.isPending}>Ingest news</Button>}
    >
      {news.length === 0 ? (
        <Empty icon={Newspaper} title="No news" description="The news desk ingests market news, corporate actions, and exchange announcements." />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", padding: "var(--space-2)" }}>
          {news.slice(0, 30).map((item, i) => (
            <div key={i} onClick={() => openEvidence({ kind: "artifact", key: String(text(item, "id", i)), title: text(item, "headline", text(item, "title")) })}
              style={{ padding: "var(--space-3)", borderBottom: "1px solid var(--border-subtle)", cursor: "pointer" }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
                <strong style={{ fontSize: "var(--text-sm)" }}>{text(item, "headline", text(item, "title", "News item"))}</strong>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--text-faint)" }}>{formatRelative(text(item, "published_at", text(item, "created_at")))}</span>
              </div>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{text(item, "source", text(item, "symbol", ""))}</div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

function CalendarView() {
  const { data: mission } = useMissionControl();
  const events = mission?.market_events ?? [];
  const holidays = mission?.market_holidays ?? [];

  return (
    <>
      <Panel icon={Calendar} title="Market Calendar">
        {events.length === 0 ? (
          <Empty icon={Calendar} title="No upcoming events" description="Earnings, ex-dates, and economic events appear here." />
        ) : (
          <DataTable
            columns={[
              { key: "date", header: "Date", render: (r) => <strong>{text(r, "event_date", text(r, "date"))}</strong> },
              { key: "event", header: "Event", render: (r) => text(r, "event_name", text(r, "title")) },
              { key: "symbol", header: "Symbol", render: (r) => text(r, "symbol", "") },
              { key: "type", header: "Type", render: (r) => <StatusPill status={text(r, "event_type", "info")} /> },
            ]}
            rows={events}
            rowKey={(r, i) => String(text(r, "event_id", text(r, "id", i)))}
          />
        )}
      </Panel>

      {holidays.length > 0 && (
        <Panel icon={Calendar} title="Market Holidays">
          <DataTable
            columns={[
              { key: "date", header: "Date", render: (r) => text(r, "holiday_date", text(r, "date")) },
              { key: "name", header: "Holiday", render: (r) => text(r, "holiday_name", text(r, "name")) },
              { key: "exchange", header: "Exchange", render: (r) => text(r, "exchange", "NSE") },
            ]}
            rows={holidays}
            rowKey={(r, i) => String(text(r, "holiday_id", text(r, "id", i)))}
          />
        </Panel>
      )}
    </>
  );
}

function SkeletonGrid({ rows = 4 }: { rows?: number }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", padding: "var(--space-3)" }}>
      {Array.from({ length: rows }).map((_, i) => <Skeleton key={i} style={{ height: 40 }} />)}
    </div>
  );
}
