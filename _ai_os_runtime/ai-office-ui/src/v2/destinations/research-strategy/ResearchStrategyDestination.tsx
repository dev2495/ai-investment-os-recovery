import React from "react";
import { BookOpenCheck, CalendarDays, FileSearch, FlaskConical, Newspaper, Radar, RefreshCw, Sparkles, Workflow } from "lucide-react";
import { useAction, useReports, useResearchIdeas, useStrategyArsenal, queryKeys } from "../../data/queries";
import { formatCompact, formatCurrency, num, text, truncate } from "../../data/liveRow";
import { Freshness, LiveTable, MetricCell, MetricStrip, RowTitle, SourceLink, StatusCell, WorkspaceError, WorkspaceGrid, countStatus } from "../../data/WorkspaceKit";
import { Badge, Button, Panel, StatusPill, Tabs } from "../../system/primitives";
import { BarSeriesChart, DonutChart } from "../../system/charts";
import { useUIStore } from "../../store";

const TABS = [
  { key: "ideas", label: "Ideas" },
  { key: "theses", label: "Long-term Research" },
  { key: "filings", label: "Filings" },
  { key: "special", label: "Special Situations" },
  { key: "news", label: "News & Sources" },
  { key: "strategy", label: "Strategy Lab" },
  { key: "reports", label: "Reports" },
];

export default function ResearchStrategyDestination() {
  const query = useResearchIdeas();
  const strategy = useStrategyArsenal();
  const reports = useReports();
  const [tab, setTab] = React.useState("ideas");
  const data = query.data;
  const openFilings = countStatus(data?.corporate_filings ?? [], ["new", "open", "review"]);
  const materialNews = (data?.news_brief ?? []).filter((row) => num(row, "materiality_score") >= 0.6 || num(row, "materiality_score") >= 60).length;

  return (
    <div className="aios-destination">
      <div className="aios-destination__head">
        <div className="aios-destination__title-row"><div className="aios-destination__title">Research & Strategy</div><Freshness generatedAt={data?.generated_at} /></div>
        <div className="aios-destination__subtitle">A source-linked research factory for long-term holdings, filings, special situations, market intelligence and systematic strategy discovery.</div>
        <Tabs tabs={TABS.map((item) => item.key === "filings" ? { ...item, count: openFilings } : item)} active={tab} onChange={setTab} />
      </div>
      <WorkspaceError error={query.error} />
      <MetricStrip>
        <MetricCell label="Active theses" value={data?.long_term_theses.length ?? 0} detail={`${data?.coverage_queue.length ?? 0} coverage tasks`} />
        <MetricCell label="Filing intelligence" value={data?.filing_intelligence.length ?? 0} tone={openFilings ? "warn" : "ok"} detail={`${data?.corporate_filings.length ?? 0} collected`} />
        <MetricCell label="Curated news" value={data?.news_brief.length ?? 0} detail={`${materialNews} high materiality`} />
        <MetricCell label="Special situations" value={data?.special_situations.length ?? 0} detail={`${data?.special_memos.length ?? 0} memos`} />
        <MetricCell label="Generated ideas" value={data?.generated_ideas.length ?? 0} detail={`${data?.idea_dossiers.length ?? 0} dossiers`} />
        <MetricCell label="Strategies" value={strategy.data?.control_board.length ?? 0} detail="gated lifecycle" />
      </MetricStrip>
      {data ? <ResearchTab tab={tab} data={data} strategy={strategy.data} reports={reports.data} /> : null}
    </div>
  );
}

type ResearchData = NonNullable<ReturnType<typeof useResearchIdeas>["data"]>;
type StrategyData = ReturnType<typeof useStrategyArsenal>["data"];
type ReportsData = ReturnType<typeof useReports>["data"];

function ResearchTab({ tab, data, strategy, reports }: { tab: string; data: ResearchData; strategy: StrategyData; reports: ReportsData }) {
  if (tab === "ideas") return <Ideas data={data} />;
  if (tab === "theses") return <Theses data={data} />;
  if (tab === "filings") return <Filings data={data} />;
  if (tab === "special") return <SpecialSituations data={data} />;
  if (tab === "news") return <NewsSources data={data} />;
  if (tab === "strategy") return <StrategyLab data={strategy} />;
  return <Reports data={reports} research={data} />;
}

function Ideas({ data }: { data: ResearchData }) {
  const ideaTypes = Object.entries(data.generated_ideas.reduce<Record<string, number>>((acc, row) => {
    const key = text(row, "idea_type", "Other"); acc[key] = (acc[key] ?? 0) + 1; return acc;
  }, {})).map(([name, value]) => ({ name, value }));
  return <WorkspaceGrid><Panel icon={Sparkles} title="Idea mix"><DonutChart data={ideaTypes} height={240} /></Panel><Panel icon={Radar} title="Watchlist" actions={<Badge>{data.watchlist.length} monitored</Badge>}><LiveTable rows={data.watchlist} emptyTitle="No watchlist items" limit={16} columns={[
    { key: "symbol", label: "Company", render: (row) => <RowTitle row={row} titleKeys={["symbol", "company_name"]} detailKeys={["thesis", "catalyst"]} /> },
    { key: "priority", label: "Priority", render: (row) => <StatusCell row={row} keys={["priority", "status"]} /> }, { key: "review_on", label: "Review" },
  ]} /></Panel><Panel className="aios-workspace-span" icon={Sparkles} title="Generated idea pipeline"><LiveTable rows={data.generated_ideas} emptyTitle="No generated ideas" columns={[
    { key: "title", label: "Idea", render: (row) => <RowTitle row={row} titleKeys={["title"]} detailKeys={["thesis", "edge_hypothesis"]} /> },
    { key: "symbols", label: "Symbols" }, { key: "idea_type", label: "Type" }, { key: "timeframe", label: "Horizon" },
    { key: "priority_score", label: "Priority", align: "right" }, { key: "risk_score", label: "Risk", align: "right" },
    { key: "status", label: "Status", render: (row) => <StatusCell row={row} /> },
  ]} /></Panel><Panel className="aios-workspace-span" icon={BookOpenCheck} title="Decision-ready dossiers"><LiveTable rows={data.idea_dossiers} emptyTitle="No idea dossiers" columns={[
    { key: "title", label: "Dossier", render: (row) => <RowTitle row={row} titleKeys={["title", "dossier_key"]} detailKeys={["summary", "thesis"]} /> },
    { key: "symbols", label: "Symbols" }, { key: "owner_agent", label: "Owner" }, { key: "status", label: "Status", render: (row) => <StatusCell row={row} /> },
  ]} /></Panel></WorkspaceGrid>;
}

function Theses({ data }: { data: ResearchData }) {
  return <WorkspaceGrid><Panel className="aios-workspace-span" icon={BookOpenCheck} title="Long-term company theses"><LiveTable rows={data.long_term_theses} emptyTitle="No long-term theses" columns={[
    { key: "symbol", label: "Company", render: (row) => <RowTitle row={row} titleKeys={["symbol", "company_name"]} detailKeys={["thesis_summary", "thesis_title"]} /> },
    { key: "long_term_gross_exposure", label: "Exposure", align: "right", render: (row) => formatCurrency(num(row, "long_term_gross_exposure")) },
    { key: "moat_score", label: "Moat", align: "right" }, { key: "management_score", label: "Management", align: "right" },
    { key: "financial_quality_score", label: "Quality", align: "right" }, { key: "expected_cagr_pct", label: "Expected CAGR", align: "right", render: (row) => `${num(row, "expected_cagr_pct").toFixed(1)}%` },
    { key: "decision_status", label: "Decision", render: (row) => <StatusCell row={row} keys={["decision_status", "thesis_status"]} /> },
  ]} /></Panel><Panel icon={Workflow} title="Coverage queue"><LiveTable rows={data.coverage_queue} emptyTitle="Coverage complete" columns={[
    { key: "symbol", label: "Gap", render: (row) => <RowTitle row={row} titleKeys={["symbol"]} detailKeys={["recommended_action", "gap_type"]} /> },
    { key: "severity", label: "Severity", render: (row) => <StatusCell row={row} keys={["severity"]} /> }, { key: "owner_agent", label: "Owner" },
  ]} /></Panel><Panel icon={FlaskConical} title="Monte Carlo"><LiveTable rows={data.long_term_monte_carlo_runs} emptyTitle="No Monte Carlo runs" columns={[
    { key: "symbol", label: "Company" }, { key: "simulation_count", label: "Paths", align: "right" }, { key: "horizon_years", label: "Years", align: "right" },
    { key: "run_status", label: "Status", render: (row) => <StatusCell row={row} keys={["run_status"]} /> },
  ]} /></Panel></WorkspaceGrid>;
}

function Filings({ data }: { data: ResearchData }) {
  const collect = useAction<Record<string, unknown>>("/api/research/filings/collect", { invalidate: [queryKeys.researchIdeas] });
  const extract = useAction<Record<string, unknown>>("/api/research/filings/extract-pdfs", { invalidate: [queryKeys.researchIdeas] });
  const notify = useUIStore((state) => state.pushToast);
  const run = (kind: "collect" | "extract") => {
    const action = kind === "collect" ? collect : extract;
    action.mutate({ actor: "Filings Analyst" }, { onSuccess: () => notify({ title: kind === "collect" ? "Filing collectors refreshed" : "PDF extraction queued", tone: "ok", duration: 5000 }), onError: (error) => notify({ title: "Research action failed", message: error.message, tone: "risk", duration: 8000 }) });
  };
  return <WorkspaceGrid><Panel className="aios-workspace-span" icon={FileSearch} title="Corporate filing intelligence" actions={<div style={{display:"flex",gap:8}}><Button size="sm" icon={RefreshCw} onClick={() => run("collect")} disabled={collect.isPending}>Collect NSE/BSE</Button><Button size="sm" icon={FileSearch} onClick={() => run("extract")} disabled={extract.isPending}>Extract PDFs</Button></div>}><LiveTable rows={data.filing_intelligence} emptyTitle="No filing intelligence" columns={[
    { key: "title", label: "Filing", render: (row) => <RowTitle row={row} titleKeys={["title"]} detailKeys={["why_it_matters", "company_name"]} /> },
    { key: "symbol", label: "Symbol" }, { key: "event_type", label: "Event" }, { key: "priority", label: "Priority", render: (row) => <StatusCell row={row} keys={["priority", "evidence_state"]} /> },
    { key: "opportunity_score", label: "Opportunity", align: "right" }, { key: "risk_score", label: "Risk", align: "right" },
    { key: "source", label: "Evidence", render: (row) => <SourceLink row={row} /> },
  ]} /></Panel><Panel icon={Workflow} title="Collector runs"><LiveTable rows={data.filing_collector_runs} emptyTitle="No collector runs" columns={[
    { key: "source_name", label: "Source" }, { key: "row_count", label: "Rows", align: "right" }, { key: "status", label: "Status", render: (row) => <StatusCell row={row} /> },
  ]} /></Panel><Panel icon={FileSearch} title="PDF extraction"><LiveTable rows={data.filing_pdf_extraction_runs} emptyTitle="No extraction runs" columns={[
    { key: "run_key", label: "Run" }, { key: "document_count", label: "Documents", align: "right" }, { key: "status", label: "Status", render: (row) => <StatusCell row={row} /> },
  ]} /></Panel></WorkspaceGrid>;
}

function SpecialSituations({ data }: { data: ResearchData }) {
  return <WorkspaceGrid><Panel className="aios-workspace-span" icon={Radar} title="Special situations radar"><LiveTable rows={data.special_situations} emptyTitle="No special situations" columns={[
    { key: "title", label: "Situation", render: (row) => <RowTitle row={row} titleKeys={["title", "company_name", "symbol"]} detailKeys={["description", "why_it_matters"]} /> },
    { key: "event_type", label: "Type" }, { key: "symbol", label: "Symbol" }, { key: "opportunity_score", label: "Opportunity", align: "right" },
    { key: "risk_score", label: "Risk", align: "right" }, { key: "status", label: "Status", render: (row) => <StatusCell row={row} keys={["event_status", "status", "urgency"]} /> },
    { key: "source", label: "Source", render: (row) => <SourceLink row={row} /> },
  ]} /></Panel><Panel icon={BookOpenCheck} title="Committee memos"><LiveTable rows={data.special_memos} emptyTitle="No special-situation memos" columns={[
    { key: "title", label: "Memo", render: (row) => <RowTitle row={row} titleKeys={["title", "memo_key"]} detailKeys={["summary", "recommendation"]} /> },
    { key: "status", label: "Status", render: (row) => <StatusCell row={row} /> },
  ]} /></Panel><Panel icon={FlaskConical} title="Event spreads"><LiveTable rows={data.special_spreads} emptyTitle="No spread calculations" columns={[
    { key: "symbol", label: "Symbol" }, { key: "gross_spread_pct", label: "Gross spread", align: "right" }, { key: "annualized_return_pct", label: "Annualised", align: "right" },
    { key: "status", label: "Status", render: (row) => <StatusCell row={row} /> },
  ]} /></Panel></WorkspaceGrid>;
}

function NewsSources({ data }: { data: ResearchData }) {
  return <WorkspaceGrid><Panel className="aios-workspace-span" icon={Newspaper} title="Curated market intelligence"><div className="aios-brief-list">{data.news_brief.slice(0, 30).map((row, index) => <article className="aios-brief-item" key={text(row,"id",index)}><div><h4>{text(row,"title")}</h4><p>{truncate(text(row,"why_it_matters"),220)}</p></div><div style={{display:"grid",justifyItems:"end",gap:7}}><StatusPill status={text(row,"materiality_score")}>Score {text(row,"materiality_score","-")}</StatusPill><SourceLink row={row}/></div></article>)}</div></Panel><Panel icon={Radar} title="Followed sources" actions={<Badge>{data.feed_registry.length} feeds</Badge>}><LiveTable rows={data.feed_registry} emptyTitle="No feeds registered" columns={[
    { key: "source_name", label: "Source", render: (row) => <RowTitle row={row} titleKeys={["feed_name", "source_name", "name"]} detailKeys={["url", "feed_url", "source_url"]} /> },
    { key: "feed_type", label: "Type", render: (row) => text(row, "feed_type", text(row, "source_type")) }, { key: "status", label: "Health", render: (row) => <StatusCell row={row} keys={["status", "health_status"]} /> },
  ]} /></Panel><Panel icon={CalendarDays} title="Market calendar"><LiveTable rows={[...data.market_events, ...data.market_holidays]} emptyTitle="No upcoming events" columns={[
    { key: "company_name", label: "Event", render: (row) => <RowTitle row={row} titleKeys={["company_name", "holiday_name", "symbol"]} detailKeys={["purpose", "description"]} /> },
    { key: "event_date", label: "Date", render: (row) => text(row,"event_date",text(row,"holiday_date")) }, { key: "event_type", label: "Type", render: (row) => text(row,"event_type",text(row,"session_status")) },
  ]} /></Panel></WorkspaceGrid>;
}

function StrategyLab({ data }: { data: StrategyData }) {
  if (!data) return null;
  const board = data.control_board ?? [];
  const statusData = Object.entries(board.reduce<Record<string, number>>((acc, row) => { const key=text(row,"candidate_status","unknown"); acc[key]=(acc[key]??0)+1; return acc; },{})).map(([status,count])=>({status,count}));
  return <WorkspaceGrid><Panel icon={FlaskConical} title="Candidate lifecycle"><BarSeriesChart data={statusData} xKey="status" bars={[{key:"count",name:"Candidates"}]} height={250}/></Panel><Panel icon={Workflow} title="Discovery queue"><LiveTable rows={data.discovery_triage} emptyTitle="No discovery candidates" columns={[
    { key:"strategy_name",label:"Candidate",render:(row)=><RowTitle row={row} titleKeys={["strategy_name","title"]} detailKeys={["edge_hypothesis","source_ref"]}/> },
    { key:"triage_status",label:"Triage",render:(row)=><StatusCell row={row} keys={["triage_status","status"]}/> },
  ]}/></Panel><Panel className="aios-workspace-span" icon={FlaskConical} title="Strategy control board"><LiveTable rows={board} emptyTitle="No strategy candidates" columns={[
    {key:"strategy_name",label:"Strategy",render:(row)=><RowTitle row={row} titleKeys={["strategy_name"]} detailKeys={["edge_hypothesis","strategy_family"]}/>},
    {key:"timeframe",label:"Timeframe"},{key:"validation_status",label:"Validation",render:(row)=><StatusCell row={row} keys={["validation_status"]}/>},
    {key:"activation_gate",label:"Gate",render:(row)=><StatusCell row={row} keys={["activation_gate"]}/>},{key:"owner_agent",label:"Owner"},
  ]}/></Panel></WorkspaceGrid>;
}

function Reports({ data, research }: { data: ReportsData; research: ResearchData }) {
  const rows = data?.report_runs ?? research.output_artifacts;
  return <WorkspaceGrid><Panel className="aios-workspace-span" icon={BookOpenCheck} title="Research output library"><LiveTable rows={rows ?? []} emptyTitle="No reports generated" columns={[
    { key:"report_name",label:"Report",render:(row)=><RowTitle row={row} titleKeys={["report_name","title","file_name"]} detailKeys={["summary","output_note_path"]}/>},
    {key:"report_family",label:"Family"},{key:"owner_agent",label:"Owner"},{key:"status",label:"Status",render:(row)=><StatusCell row={row}/>},{key:"finished_at",label:"Completed"},
  ]}/></Panel></WorkspaceGrid>;
}
