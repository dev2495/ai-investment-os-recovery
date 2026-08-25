import React from "react";
import {
  AlertTriangle,
  Download,
  BookOpen,
  Building2,
  CalendarClock,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ClipboardCheck,
  ExternalLink,
  FileSearch,
  FileText,
  Gavel,
  History,
  Landmark,
  LineChart,
  LockKeyhole,
  RefreshCw,
  Scale,
  Send,
  ShieldCheck,
  Sparkles,
  Target,
  Users,
} from "lucide-react";
import {
  useLongTermThesisWorkspace,
} from "../../data/queries";
import { API_BASE_URL } from "../../data/client";
import {
  useGenerateThesisReport,
  usePreflightThesisReport,
  useOpenLongTermCommittee,
  useResolveLongTermCommittee,
  useUpsertWatchlist,
} from "../../data/actions";
import type { LiveRow } from "../../data/liveRow";
import { bool, formatCurrency, num, text, value } from "../../data/liveRow";
import { useUIStore } from "../../store";
import { Badge, Button, StatusPill } from "../../system/primitives";
import { FinancialQualityWorkspace } from "./FinancialQualityWorkspace";
import { ResearchCaseWorkspace, reportViewUrl } from "./ResearchCaseWorkspace";
import "./LongTermThesisWorkspace.css";
import "./ThesisDecisionWorkspaces.css";
import "./ReportLedger.css";
import { UshaMultiYearReport } from "./UshaMultiYearReport";
import { ValuationWorkbench } from "./ValuationWorkbench";

const PAGE_SIZE = 12;

const NAV_ITEMS = [
  ["thesis", "Thesis"],
  ["research-case", "Start Research"],
  ["business", "Business & moat"],
  ["stewardship", "Stewardship"],
  ["financials", "Financial quality"],
  ["valuation", "Valuation"],
  ["catalysts", "Catalysts"],
  ["risks", "Risks"],
  ["evidence", "Evidence"],
  ["agents", "Agent debate"],
  ["watchlist", "Watchlist"],
  ["decision", "Decision"],
] as const;

function rows(raw: unknown): LiveRow[] {
  return Array.isArray(raw) ? raw.filter((item): item is LiveRow => Boolean(item && typeof item === "object")) : [];
}

function record(raw: unknown): LiveRow {
  return raw && typeof raw === "object" && !Array.isArray(raw) ? raw as LiveRow : {};
}

function date(raw: unknown, fallback = "not recorded"): string {
  if (!raw) return fallback;
  const parsed = new Date(String(raw));
  return Number.isNaN(parsed.getTime())
    ? String(raw)
    : new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(parsed);
}

function compactNumber(raw: unknown): string {
  const parsed = Number(raw ?? 0);
  return Number.isFinite(parsed) ? new Intl.NumberFormat("en-IN", { notation: "compact", maximumFractionDigits: 1 }).format(parsed) : "—";
}

function humanSummaryItem(raw: unknown): string {
  if (raw === null || raw === undefined || raw === "") return "";
  if (typeof raw === "string") return raw;
  const item = record(raw);
  const label = text(item, "item", text(item, "gap", text(item, "dimension", text(item, "claim", text(item, "killer", "")))));
  const detail = text(item, "reason", text(item, "impact", text(item, "source_needed", text(item, "test", ""))));
  if (label && detail) return `${label}: ${detail}`;
  if (label) return label;
  return Object.entries(item)
    .filter(([, value]) => value !== null && value !== undefined && value !== "" && !Array.isArray(value))
    .map(([key, value]) => `${key.replace(/_/g, " ")}: ${String(value)}`)
    .join(" · ");
}

function jsonSummary(raw: unknown): string {
  if (raw === null || raw === undefined || raw === "") return "Not recorded";
  if (typeof raw === "string") return raw;
  if (Array.isArray(raw)) {
    const summaries = raw.map(humanSummaryItem).filter(Boolean);
    return summaries.length ? summaries.join(" · ") : "Not recorded";
  }
  return humanSummaryItem(raw) || "Not recorded";
}

function markdownSummary(raw: unknown): string {
  return String(raw ?? "")
    .split("\n")
    .map((line) => line.replace(/^#{1,6}\s*/, "").replace(/^[-*]\s*/, "").replace(/`/g, "").trim())
    .filter((line) => line && !line.toLowerCase().startsWith("evidence inventory"))
    .slice(0, 5)
    .join(" ");
}

function sourceHref(row: LiveRow): string {
  return text(row, "source_url", text(row, "attachment_url", ""));
}

function Citation({ row, label }: { row: LiveRow; label?: string }) {
  const href = sourceHref(row);
  const title = label || text(row, "source_title", text(row, "title", text(row, "source_name", "Primary evidence")));
  return href ? (
    <a className="ltw-citation" href={href} rel="noreferrer" target="_blank">
      <FileText size={13} aria-hidden="true" />
      <span>{title}</span>
      <ExternalLink size={12} aria-hidden="true" />
    </a>
  ) : <span className="ltw-citation ltw-citation--missing"><AlertTriangle size={13} />Source locator missing</span>;
}
function canonicalEvidenceStatus(raw: unknown): string {
  const state = String(raw ?? "").toLowerCase().replace(/[ -]/g, "_");
  if (["human_reviewed", "human_validated", "reviewed", "approved"].includes(state)) return "Human-reviewed";
  if (["validated", "machine_validated", "verified"].includes(state)) return "Validated";
  if (["machine_extracted", "extracted"].includes(state)) return "Machine-extracted";
  if (["parsed", "parse_complete"].includes(state)) return "Parsed";
  if (["source_captured", "captured", "registered", "active", "source_linked", "covered"].includes(state)) return "Source captured";
  if (["stale", "expired"].includes(state)) return "Stale";
  return "Missing";
}

function decisionReadiness(raw: unknown): string {
  const state = String(raw ?? "").toLowerCase();
  return state.includes("human") || state.includes("final") ? "Human-reviewed" : "Review required";
}


function ResearchSection({
  id,
  eyebrow,
  title,
  state,
  source,
  children,
}: {
  id: string;
  eyebrow: string;
  title: string;
  state?: string;
  source?: LiveRow;
  children: React.ReactNode;
}) {
  return (
    <section className="ltw-section" id={id}>
      <header>
        <div><span>{eyebrow}</span><h2>{title}</h2></div>
        <div className="ltw-section-state">
          <span><small>Coverage</small><b>{source ? "Source captured" : "Missing"}</b></span>
          <span><small>Quality</small><b>{canonicalEvidenceStatus(source?.verification_status ?? source?.evidence_verification_status ?? state)}</b></span>
          <span><small>Decision</small><b>{decisionReadiness(state)}</b></span>
        </div>
      </header>
      <div className="ltw-section__body">{children}</div>
      <footer>{source ? <><Citation row={source} /><span className="ltw-layer-note">Section citation; evidence quality and investment decision remain separate gates.</span></> : <span className="ltw-source-gap"><AlertTriangle size={13} />Section citation missing. Agent evidence elsewhere does not make this section decision-ready.</span>}</footer>
    </section>
  );
}

function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="ltw-empty"><FileSearch size={19} /><div><strong>{title}</strong><p>{detail}</p></div></div>;
}

function Opinion({ row }: { row?: LiveRow }) {
  if (!row) return <EmptyState title="Opinion unavailable" detail="No source-backed specialist opinion is stored for this lane." />;
  return (
    <article className="ltw-opinion">
      <div className="ltw-opinion__head">
        <div><span>{text(row, "specialist_key").replace(/_/g, " ")}</span><strong>{text(row, "agent_name")}</strong></div>
        <div><Badge tone={text(row, "opinion_status") === "dissent" ? "warn" : "default"}>{text(row, "opinion_status").replace(/_/g, " ")}</Badge><b>{canonicalEvidenceStatus(row.evidence_verification_status)} · {num(row, "confidence_pct", 0)}% confidence</b></div>
      </div>
      <p>{text(row, "conclusion", "No conclusion recorded.")}</p>
      <details><summary>Disconfirming evidence and follow-ups</summary><p>{text(row, "disconfirming_evidence", "No disconfirming evidence recorded.")}</p><p>{jsonSummary(value(row, "required_followups", []))}</p></details>
      <Citation row={row} label={text(row, "source_title", "Opinion evidence")} />
    </article>
  );
}

function Pager({ page, total, onChange }: { page: number; total: number; onChange: (next: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  return <div className="ltw-pager"><Button aria-label="Previous page" disabled={page <= 1} icon={ChevronLeft} onClick={() => onChange(page - 1)} size="sm" variant="ghost">Previous</Button><span>Page {page} of {pages} · {total} rows</span><Button aria-label="Next page" disabled={page >= pages} iconRight={ChevronRight} onClick={() => onChange(page + 1)} size="sm" variant="ghost">Next</Button></div>;
}

function FinancialMetric({ label, metric, scale = 100, suffix = "" }: { label: string; metric: LiveRow; scale?: number; suffix?: string }) {
  const raw = metric.value;
  const shown = raw === null || raw === undefined ? "Not computable" : `${(Number(raw) / scale).toLocaleString("en-IN", { maximumFractionDigits: 1 })}${suffix}`;
  return <div><span>{label}</span><strong>{shown}</strong>{sourceHref(metric) ? <a href={sourceHref(metric)} target="_blank" rel="noreferrer">FY{num(metric, "fiscal_year")} · p.{text(metric, "page_number", "?")} <ExternalLink size={11} /></a> : <small>{text(metric, "status", "Source gap")}</small>}</div>;
}

function InvestmentBrief({ selected, business, moat, opinions, risks, filings, models, financialHistory, productionRatios, validationChecks, valuationWorkbench }: {
  selected: LiveRow; business?: LiveRow; moat?: LiveRow; opinions: Map<string, LiveRow>; risks: LiveRow[]; filings: LiveRow[]; models: LiveRow[];
  financialHistory: LiveRow[]; productionRatios: LiveRow[]; validationChecks: LiveRow[]; valuationWorkbench: LiveRow;
}) {
  const pack = record(selected.research_pack);
  const packSection = (key: string) => record(pack[key]);
  const valuationPack = packSection("forecasts_valuation");
  const moatPack = packSection("moat_quality");
  const riskPack = packSection("catalysts_risks");
  const killers = rows(selected.thesis_killers);
  const history = [...financialHistory].sort((a, b) => num(a, "fiscal_year") - num(b, "fiscal_year"));
  const years = history.map((row) => num(row, "fiscal_year"));
  const fact = (year: number, key: string) => rows(history.find((row) => num(row, "fiscal_year") === year)?.facts).find((row) => text(row, "fact_key") === key);
  const factValue = (year: number, key: string) => { const row = fact(year, key); return row?.value === null || row?.value === undefined ? null : Number(row.value); };
  const ratio = (year: number, key: string) => productionRatios.find((row) => text(row, "formula_key") === key && Number(text(row, "period_end").slice(0, 4)) === year);
  const ratioValue = (year: number, key: string) => { const row = ratio(year, key); return row?.value === null || row?.value === undefined ? null : Number(row.value); };
  const latestYear = years[years.length - 1] || 0;
  const firstYear = years[0] || 0;
  const revenue = latestYear ? factValue(latestYear, "revenue_from_operations") : null;
  const firstRevenue = firstYear ? factValue(firstYear, "revenue_from_operations") : null;
  const pat = latestYear ? factValue(latestYear, "profit_after_tax") : null;
  const cfo = latestYear ? factValue(latestYear, "operating_cash_flow") : null;
  const capex = latestYear ? factValue(latestYear, "capital_expenditure") : null;
  const fcf = cfo === null || capex === null ? null : cfo - Math.abs(capex);
  const currentDebt = latestYear ? factValue(latestYear, "current_borrowings") : null;
  const nonCurrentDebt = latestYear ? factValue(latestYear, "non_current_borrowings") : null;
  const cashEquivalents = latestYear ? factValue(latestYear, "cash_and_cash_equivalents") : null;
  const otherBankBalances = latestYear ? factValue(latestYear, "other_bank_balances") : null;
  const debt = currentDebt === null || nonCurrentDebt === null ? null : currentDebt + nonCurrentDebt;
  const cash = cashEquivalents === null || otherBankBalances === null ? null : cashEquivalents + otherBankBalances;
  const netCash = debt === null || cash === null ? null : cash - debt;
  const eps = latestYear ? factValue(latestYear, "basic_eps") : null;
  const equity = latestYear ? factValue(latestYear, "total_equity") : null;
  const ebitdaMargin = latestYear ? ratioValue(latestYear, "ebitda_margin") : null;
  const ebitda = revenue === null || ebitdaMargin === null ? null : revenue * ebitdaMargin / 100;
  const priceAnchor = record(valuationWorkbench.current_price);
  const currentPrice = priceAnchor.decision_usable === true && priceAnchor.value !== null && priceAnchor.value !== undefined
    ? num(priceAnchor, "value")
    : null;
  const sharesCrore = pat && eps ? (pat / 100) / eps : null;
  const marketCapCrore = currentPrice && sharesCrore ? currentPrice * sharesCrore : null;
  const enterpriseValueCrore = marketCapCrore === null || netCash === null ? null : marketCapCrore - netCash / 100;
  const currentPe = currentPrice && eps ? currentPrice / eps : null;
  const currentPb = marketCapCrore !== null && equity ? marketCapCrore / (equity / 100) : null;
  const currentEvEbitda = enterpriseValueCrore !== null && ebitda ? enterpriseValueCrore / (ebitda / 100) : null;
  const currentPfcf = marketCapCrore !== null && fcf && fcf > 0 ? marketCapCrore / (fcf / 100) : null;
  const cagr = firstRevenue && revenue && latestYear > firstYear ? (Math.pow(revenue / firstRevenue, 1 / (latestYear - firstYear)) - 1) * 100 : null;
  const money = (value: number | null) => value === null ? "Not available" : `₹${(value / 100).toLocaleString("en-IN", { maximumFractionDigits: 1 })}cr`;
  const percent = (value: number | null) => value === null ? "Not computable" : `${value.toFixed(1)}%`;
  const ratioText = (value: number | null) => value === null ? "Not computable" : `${value.toFixed(2)}×`;
  const currentModels = models.filter((row) => ["complete", "validated", "human_reviewed"].includes(text(row, "status").toLowerCase()) && row.fair_value_base !== null && row.fair_value_base !== undefined).slice(0, 4);
  const revenueTrend = years.map((year) => factValue(year, "revenue_from_operations")).filter((value): value is number => value !== null).map((value) => value / 100);
  const profitTrend = years.map((year) => factValue(year, "profit_after_tax")).filter((value): value is number => value !== null).map((value) => value / 100);
  const trendLabels = years.map((year) => `FY${String(year).slice(-2)}`);
  const source = latestYear ? fact(latestYear, "revenue_from_operations") : undefined;
  const validationPass = validationChecks.filter((row) => text(row, "status") === "pass").length;
  const financialStory = history.length
    ? `${text(selected, "legal_name", text(selected, "company_name"))} grew revenue from ${money(firstRevenue)} in FY${firstYear} to ${money(revenue)} in FY${latestYear}${cagr === null ? "" : `, a ${cagr.toFixed(1)}% CAGR`}. Latest PAT was ${money(pat)}, CFO ${money(cfo)} and FCF ${money(fcf)}. ${netCash === null ? "Balance-sheet net cash is not computable." : `Cash less borrowings was ${money(netCash)}.`} All ${validationPass} stored statement checks pass; this is deterministic validation, not human investment approval.`
    : "No comparable validated financial history is available. Missing periods remain visible and are not inferred.";
  const removeStaleFinancialGap = (raw: string) => raw.split(/(?<=[.!?])\s+/).filter((sentence) => !/no validated financial|all financial figures are machine-extracted and unvalidated|cannot be numerically substantiated without validated financial/i.test(sentence)).join(" ");
  const thesisNarrative = removeStaleFinancialGap(text(selected, "thesis_summary", "No approved thesis conclusion is recorded."));
  const moatNarrative = removeStaleFinancialGap(text(moatPack, "summary", text(opinions.get("moat"), "disconfirming_evidence", "Pricing power, customer captivity and reinvestment returns remain open proof tests.")));
  return <section className="ltw-investment-brief" id="thesis">
    <header><div><span>Executive investment brief · evidence through FY{latestYear || "—"}</span><h2>{text(selected, "decision_status", "Research decision pending").replace(/_/g, " ")}</h2></div><p>{text(selected, "thesis_status", "under research").replace(/_/g, " ")} · human decision pending</p></header>
    <div className="ltw-brief-grid">
      <article className="ltw-brief-company"><span>What the company does</span><h3>{text(selected, "legal_name", text(selected, "company_name"))}</h3><p>{text(selected, "business_model", markdownSummary(business?.content_markdown) || "A source-backed business description is still being reviewed.")}</p>{business ? <Citation row={business} /> : null}</article>
      <article><span>Why own—or avoid</span><p>{thesisNarrative}</p><small>{history.length ? `The financial base below is reconciled through FY${latestYear}; moat, management and valuation conclusions remain subject to human review.` : markdownSummary(moat?.content_markdown) || text(moatPack, "summary", text(opinions.get("moat"), "conclusion", "Durable moat evidence is not yet established."))}</small>{moat ? <Citation row={moat} /> : null}</article>
      <article><span>Moat proof and disconfirmers</span><p>{moatNarrative}</p><small>{rows(moatPack.coverage_gaps).length ? jsonSummary(moatPack.coverage_gaps) : jsonSummary(value(opinions.get("moat") || {}, "required_followups", []))}</small></article>
    </div>
    <section className="ltw-company-financial-story">
      <header><span>Story behind the numbers</span><h3>{history.length ? `${years.length}-year consolidated history` : "Financial evidence gap"}</h3><p>{financialStory}</p>{source ? <Citation row={source} label="Latest annual report" /> : null}</header>
      {history.length ? <><div className="ltw-ir-charts"><figure><figcaption>Revenue · ₹ crore</figcaption><MiniTrend values={revenueTrend} labels={trendLabels}/></figure><figure><figcaption>PAT · ₹ crore</figcaption><MiniTrend values={profitTrend} labels={trendLabels}/></figure></div>
      <div className="ltw-table-wrap"><table className="ltw-company-history"><thead><tr><th>Decision metric</th>{years.map((year) => <th key={year}>FY{year}</th>)}</tr></thead><tbody>
        {[
          ["Revenue", (year:number) => money(factValue(year,"revenue_from_operations"))],
          ["PAT", (year:number) => money(factValue(year,"profit_after_tax"))],
          ["CFO", (year:number) => money(factValue(year,"operating_cash_flow"))],
          ["Capex", (year:number) => money(factValue(year,"capital_expenditure"))],
          ["FCF", (year:number) => { const ocf=factValue(year,"operating_cash_flow"), cx=factValue(year,"capital_expenditure"); return ocf===null||cx===null?"Not available":money(ocf-Math.abs(cx)); }],
          ["EBITDA margin", (year:number) => percent(ratioValue(year,"ebitda_margin"))],
          ["PAT margin", (year:number) => percent(ratioValue(year,"pat_margin"))],
          ["CFO / PAT", (year:number) => percent(ratioValue(year,"cfo_pat"))],
          ["ROE", (year:number) => percent(ratioValue(year,"roe"))],
          ["ROCE proxy", (year:number) => percent(ratioValue(year,"roce_proxy"))],
          ["Asset turnover", (year:number) => ratioText(ratioValue(year,"asset_turnover"))],
          ["Current ratio", (year:number) => ratioText(ratioValue(year,"current_ratio"))],
          ["Total assets", (year:number) => money(factValue(year,"total_assets"))],
          ["Total equity", (year:number) => money(factValue(year,"total_equity"))],
        ].map(([label, get]) => <tr key={String(label)}><th>{String(label)}</th>{years.map((year) => <td key={year}>{(get as (year:number)=>string)(year)}</td>)}</tr>)}
      </tbody></table></div>
      <details><summary>Formula, source pages and validation</summary><p>Consolidated · INR lakh source basis · displayed in ₹ crore. FCF = CFO − absolute capex outflow. ROCE proxy and all other ratios use versioned formulas and only accepted inputs.</p><p>{validationPass}/{validationChecks.length} validation checks pass.</p><div className="ltw-table-wrap"><table><thead><tr><th>Ratio</th><th>Period</th><th>Value</th><th>Formula</th><th>Inputs</th></tr></thead><tbody>{productionRatios.map((row) => <tr key={num(row,"id")}><td>{text(row,"label")}</td><td>{text(row,"period_end")}</td><td>{row.value===null||row.value===undefined?"Not computable":`${num(row,"value").toLocaleString("en-IN",{maximumFractionDigits:2})}${text(row,"unit")==="percent"?"%":text(row,"unit")==="ratio"?"×":""}`}</td><td>{text(row,"expression")}</td><td>{Array.isArray(row.inputs)?row.inputs.map((input,index)=><small key={index}>{text(record(input),"input_role").replace(/_/g," ")} · {num(record(input),"value").toLocaleString("en-IN")} lakh · p.{num(record(input),"source_page")}</small>):"Unavailable"}</td></tr>)}</tbody></table></div></details></> : null}
    </section>
    <div className="ltw-brief-lower">
      <article><span>Valuation and expected return</span>{currentModels.length ? currentModels.map((row) => <div className="ltw-brief-model" key={num(row, "id")}><strong>{text(row, "model_name")}</strong><p>{`${formatCurrency(num(row, "fair_value_low"))} / ${formatCurrency(num(row, "fair_value_base"))} / ${formatCurrency(num(row, "fair_value_high"))}`}</p><small>Bear / base / bull · calculated, not operator-reviewed · as of {date(row.updated_at)}</small></div>) : currentPrice && history.length ? <><p>At ₹{currentPrice.toLocaleString("en-IN")} per share, the market is paying approximately {currentPe?.toFixed(1) ?? "—"}× FY{latestYear} earnings, {currentPb?.toFixed(1) ?? "—"}× book, {currentEvEbitda?.toFixed(1) ?? "—"}× EBITDA and {currentPfcf?.toFixed(1) ?? "—"}× free cash flow.</p><div className="ltw-valuation-diagnostics"><span><small>Market cap</small><b>{marketCapCrore === null ? "Not computable" : `₹${marketCapCrore.toLocaleString("en-IN", { maximumFractionDigits: 0 })}cr`}</b></span><span><small>Enterprise value</small><b>{enterpriseValueCrore === null ? "Not computable" : `₹${enterpriseValueCrore.toLocaleString("en-IN", { maximumFractionDigits: 0 })}cr`}</b></span><span><small>Share basis</small><b>{sharesCrore === null ? "Not computable" : `${sharesCrore.toFixed(2)}cr`}</b></span></div><small>Share basis = validated PAT ÷ basic EPS. EV uses validated cash and borrowings. These are market-implied diagnostics, not fair value. DCF and reverse DCF remain withheld until forecast, WACC and terminal assumptions are explicitly reviewed.</small></> : <p>DCF, reverse DCF and peer valuation are withheld until current price, share basis and reviewed forecast assumptions are available.</p>}<a href="#valuation">Open valuation assumptions and sensitivities</a></article>
      <article><span>Top risks and kill conditions</span>{risks.slice(0, 3).map((row) => <div key={num(row, "id")}><strong>{text(row, "category").replace(/_/g, " ")}</strong><p>{text(row, "conclusion")}</p><Citation row={row} /></div>)}{!risks.length && killers.length ? killers.slice(0, 3).map((row, i) => <p key={i}>{text(row, "killer")} — {text(row, "test")}</p>) : null}{!risks.length && !killers.length ? <p>{text(riskPack, "summary", "No source-backed risk synthesis is available.")}</p> : null}<a href="#risks">Open full bear case</a></article>
      <article><span>Catalysts and next events</span>{filings.slice(0, 3).map((row, index) => <div key={num(row, "filing_id", index)}><strong>{text(row, "title")}</strong><small>{date(row.filed_at)} · {text(row, "event_type").replace(/_/g, " ")}</small><Citation row={row} label="Original filing" /></div>)}{!filings.length ? <p>No current catalyst is linked.</p> : null}<a href="#catalysts">Open timeline</a></article>
    </div>
    <footer><div><strong>Decision ask</strong><p>Continue research; validate moat evidence and valuation assumptions before any investment conclusion.</p></div><div><a className="ltw-brief-action" href="#research-case">Start or repair research</a><a href="#financials">Open methods and raw evidence</a></div></footer>
  </section>;
}

const USHA_REPORT = "https://ushamartin.com/public/upload/investorrelations/Annual-Report-FY-2025-26.pdf";

function MiniTrend({ values, labels }: { values: number[]; labels: string[] }) {
  const width=420,height=126,pad=25,max=Math.max(...values),min=Math.min(...values),span=Math.max(1,max-min);
  const x=(i:number)=>pad+i*(width-pad*2)/Math.max(1,values.length-1), y=(v:number)=>height-pad-(v-min)/span*(height-pad*2);
  return <svg className="ltw-ir-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${labels.join(" to ")} trend`}><line x1={pad} x2={width-pad} y1={height-pad} y2={height-pad}/><polyline points={values.map((v,i)=>`${x(i)},${y(v)}`).join(" ")}/>{values.map((v,i)=><g key={labels[i]}><circle cx={x(i)} cy={y(v)} r="4"/><text x={x(i)} y={height-7} textAnchor="middle">{labels[i]}</text><text x={x(i)} y={y(v)-9} textAnchor="middle">{v.toLocaleString("en-IN",{maximumFractionDigits:1})}</text></g>)}</svg>;
}

function UshaInvestorReport({ guidance, models, filings, thesisKillers, onResearch }: { guidance: LiveRow[]; models: LiveRow[]; filings: LiveRow[]; thesisKillers: LiveRow[]; onResearch: () => void }) {
  const dcf=models.find((r)=>text(r,"model_type")==="dcf")||{}, multiples=models.find((r)=>text(r,"model_type")==="multiples")||{};
  const assumptions=record(dcf.assumptions), priceSource=record(assumptions.current_price_source), price=num(assumptions,"current_price",0);
  return <article className="ltw-ir" id="thesis">
    <nav className="ltw-ir-nav"><a href="#ir-view">Investment view</a><a href="#ir-business">Business &amp; segments</a><a href="#ir-financials">Financial model</a><a href="#ir-capital">Capital returns</a><a href="#ir-valuation">Valuation</a><a href="#ir-risks">Catalysts &amp; risks</a><a href="#ir-decision">Decision</a></nav>
    <section className="ltw-ir-hero" id="ir-view"><div><span>Preliminary initiation · no capital action</span><h2>Operating quality improved sharply; valuation still fails the proof test.</h2><p>FY2026 revenue grew 6.2%, EBITDA margin expanded 2.7 percentage points and free cash flow reached ₹457.3 crore. The balance sheet moved from ₹76.8 crore net debt to ₹96.3 crore net cash. Against the last stored quote of ₹{price.toLocaleString("en-IN")}, the unreviewed DCF base is ₹{num(dcf,"fair_value_base").toFixed(0)}—evidence for deeper underwriting, not a buy decision.</p><div className="ltw-ir-proof"><span>Consolidated as reported</span><span>FY ended 31 Mar 2026</span><span>Annual report pp.240–243, 310–311</span></div></div><aside><span>Decision posture</span><strong>Research / avoid adding</strong><p>Wait for valuation re-underwrite, segment economics and capex delivery.</p><button onClick={onResearch}>Start or repair research</button></aside></section>
    <section className="ltw-ir-change"><header><span>What changed</span><h3>Three improvements; three open questions</h3></header><div>{[["01","Margin inflected","EBITDA +21.6% on 6.2% revenue growth."],["02","Cash strengthened","CFO/PAT 133.4%; FCF/PAT 93.1%."],["03","Net cash","₹145.5cr borrowings versus ₹241.8cr cash."],["?","Margin durability","No validated price/volume/raw-material bridge."],["?","Capex returns","₹200–250cr annual plan remains unproven."],["?","Fair value","Models are calculated, not reviewed or backtested."]].map((x,i)=><article className={i>2?"is-question":""} key={x[1]}><b>{x[0]}</b><strong>{x[1]}</strong><p>{x[2]}</p></article>)}</div></section>
    <section className="ltw-ir-section" id="ir-business"><header><span>Business architecture</span><h2>A concentrated wire-rope franchise with a small loss-making “Others” segment</h2><p>Wire &amp; Wire Ropes contributed 97.9% of FY2026 revenue. The simple mix helps analysis but leaves the thesis exposed to one engine.</p></header><div className="ltw-ir-split"><div><h3>Segment bridge · ₹ crore</h3><table><thead><tr><th>FY2026</th><th>Revenue</th><th>Result*</th><th>Assets</th><th>Capital employed</th></tr></thead><tbody><tr><td>Wire &amp; Wire Ropes</td><td>3,613.1</td><td>650.4</td><td>3,664.5</td><td>3,132.0</td></tr><tr><td>Others</td><td>78.0</td><td>(1.6)</td><td>64.5</td><td>42.4</td></tr><tr className="total"><td>Consolidated</td><td>3,691.1</td><td>657.6 EBIT</td><td>4,211.8</td><td>Unallocated items bridge</td></tr></tbody></table><small>* Result before finance and tax. Annual Report p.310.</small></div><aside><h3>Moat evidence</h3><p><strong>Supported:</strong> selected high-end OceanMax orders moved from the UK plant to Ranchi and met customer requirements.</p><p><strong>Not proven:</strong> market share, pricing power, switching costs, customer concentration and peer returns.</p><a href={USHA_REPORT} target="_blank" rel="noreferrer">Primary report · pp.20, 310 <ExternalLink size={12}/></a></aside></div></section>
    <section className="ltw-ir-section" id="ir-financials"><header><span>Financial story</span><h2>Profit and cash grew faster than revenue; the reconciled base is strong but historically incomplete</h2><p>FY2025–FY2026 values reconcile. Earlier facts are sparse, so unsupported 3/5/10-year CAGR cells stay blank.</p></header><div className="ltw-ir-charts"><figure><figcaption>Revenue · ₹ crore</figcaption><MiniTrend values={[3474.2,3691.1]} labels={["FY25","FY26"]}/><small>EBITDA ₹636.5cr → ₹774.0cr</small></figure><figure><figcaption>Free cash flow · ₹ crore</figcaption><MiniTrend values={[177.1,457.3]} labels={["FY25","FY26"]}/><small>CFO ₹421.8cr → ₹655.3cr</small></figure></div><div className="ltw-ir-table"><table><thead><tr><th>₹ crore / ratio</th><th>FY2025</th><th>FY2026</th><th>Read-through</th></tr></thead><tbody><tr><td>Revenue</td><td>3,474.2</td><td>3,691.1</td><td>+6.2%</td></tr><tr><td>EBITDA / margin</td><td>636.5 / 18.3%</td><td>774.0 / 21.0%</td><td>+21.6%; +2.7pp</td></tr><tr><td>EBIT / continuing PAT</td><td>538.6 / 406.3</td><td>657.6 / 491.2</td><td>+22.1% / +20.9%</td></tr><tr><td>CFO / FCF</td><td>421.8 / 177.1</td><td>655.3 / 457.3</td><td>Conversion expanded</td></tr><tr><td>Capex / revenue</td><td>7.0%</td><td>5.4%</td><td>Lower in-period intensity</td></tr><tr><td>Current / quick ratio</td><td>2.84x / 1.43x</td><td>3.28x / 1.90x</td><td>Liquidity strengthened</td></tr><tr><td>Interest coverage</td><td>18.2x</td><td>33.5x</td><td>Financing risk reduced</td></tr></tbody></table></div><details><summary>Evidence, formulas and missing periods</summary><p>Revenue/EBITDA/PAT p.241; CFO/capex pp.242–243; balance sheet p.240. FY2012–FY2024 lacks consistent EBIT, working-capital and capital-employed components.</p></details></section>
    <section className="ltw-ir-section" id="ir-capital"><header><span>Capital efficiency</span><h2>FY2026 return bridge: margin expansion outweighed modest turnover dilution</h2><p>Financing capital = equity + borrowings − cash, averaged across FY2025/FY2026. Calculated—not issuer-reported—ROCE.</p></header><div className="ltw-ir-bridge"><div><span>EBIT margin</span><strong>17.81%</strong><small>657.6 ÷ 3,691.1</small></div><b>×</b><div><span>Capital turnover</span><strong>1.22×</strong><small>Revenue ÷ ₹3,017.2cr</small></div><b>=</b><div className="result"><span>ROCE</span><strong>21.79%</strong><small>pre-tax</small></div><div className="result secondary"><span>ROIC</span><strong>16.74%</strong><small>NOPAT using reported ETR</small></div></div><div className="ltw-ir-capital"><p><strong>Reinvestment:</strong> capex ₹198.1cr, 5.4% of revenue; maintenance vs growth is undisclosed.</p><p><strong>Allocation:</strong> ₹91.4cr dividends; no sourced FY2026 buyback/acquisition amount.</p><p><strong>Segment returns:</strong> capex and cash flow are absent, so full segment ROIC is unavailable.</p></div></section>
    <section className="ltw-ir-section" id="ir-valuation"><header><span>Valuation · quote {date(priceSource.quote_ts)}</span><h2>The stored quote embeds substantially more value than the unreviewed cash-flow base</h2><p>These are scenarios, not price targets. Operator review and replay remain open.</p></header><div className="ltw-ir-valuations"><article><span>10-year DCF</span><strong>₹{num(dcf,"fair_value_base").toFixed(0)}</strong><p>Bear ₹{num(dcf,"fair_value_low").toFixed(0)} · Bull ₹{num(dcf,"fair_value_high").toFixed(0)}</p><small>8% growth; 12% discount; 4% terminal growth; normalized FCF ₹177.1cr.</small></article><article><span>Earnings multiple</span><strong>₹{num(multiples,"fair_value_base").toFixed(0)}</strong><p>18× / 25× / 32× = ₹{num(multiples,"fair_value_low").toFixed(0)} / ₹{num(multiples,"fair_value_base").toFixed(0)} / ₹{num(multiples,"fair_value_high").toFixed(0)}</p><small>No compatible peer set is validated.</small></article><article><span>Stored quote</span><strong>₹{price.toFixed(1)}</strong><p>{text(priceSource,"provider_symbol","BSE:USHAMART")}</p><small>Read-only historical quote; refresh before decision.</small></article></div><table className="ltw-ir-sensitivity"><thead><tr><th>Scenario</th><th>Growth</th><th>Discount</th><th>Terminal</th><th>Fair value</th></tr></thead><tbody><tr><td>Bear</td><td>3%</td><td>14%</td><td>3%</td><td>₹58</td></tr><tr><td>Base</td><td>8%</td><td>12%</td><td>4%</td><td>₹104</td></tr><tr><td>Bull</td><td>12%</td><td>11%</td><td>5%</td><td>₹175</td></tr></tbody></table></section>
    <section className="ltw-ir-section" id="ir-risks"><header><span>Management, catalysts and risk</span><h2>Capex delivery is the forward monitor; valuation and concentration are the main risks</h2></header><div className="ltw-ir-guidance"><table><thead><tr><th>Commitment</th><th>Target</th><th>Observed</th><th>Status</th></tr></thead><tbody>{guidance.map((r)=><tr key={num(r,"claim_id")}><td>{text(r,"metric_key").replace(/_/g," ")}</td><td>{num(r,"target_value")} {text(r,"target_unit")} by {text(r,"target_period_end")}</td><td>{r.actual_value==null?"Not yet evidenced":`${num(r,"actual_value")} ${text(r,"actual_unit")}`}</td><td>{text(r,"outcome_status",text(r,"claim_status")).replace(/_/g," ")}</td></tr>)}</tbody></table></div><div className="ltw-ir-risk-grid"><div><h3>Catalysts</h3><p>Remaining 1.8 MWp solar phase due FY2027.</p><p>₹200–250cr annual growth capex for elevators, cranes and mining.</p><p>{filings[0]?text(filings[0],"title"):"No newer material filing in this view."}</p></div><div><h3>Kill conditions</h3>{thesisKillers.slice(0,4).map((r,i)=><p key={i}><strong>{text(r,"killer").replace(/_/g," ")}:</strong> {text(r,"test")}</p>)}</div></div></section>
    <section className="ltw-ir-decision" id="ir-decision"><div><span>Current decision</span><h2>Continue research; do not convert momentum into valuation certainty.</h2><p>Refresh price, human-review extraction, complete the operating bridge, validate capex returns and re-run valuation.</p></div><aside><strong>No capital action authorized</strong><button onClick={onResearch}>Open Research Case</button><a href="#decision">Human decision record</a></aside></section>
    <details className="ltw-ir-evidence"><summary>Evidence &amp; method appendix</summary><p>External-SSD source hash verified. Eight statement/cash-flow checks pass. Geography fails reconciliation by ₹95.4cr FY2026 and ₹90.9cr FY2025, so it is withheld. Machine extraction is not human review.</p><a href={USHA_REPORT} target="_blank" rel="noreferrer">Official annual report <ExternalLink size={12}/></a></details>
  </article>;
}

export default function LongTermThesisWorkspace() {
  const [thesisId, setThesisId] = React.useState<number | null>(() => {
    const parsed = Number(new URLSearchParams(window.location.search).get("thesis_id"));
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  });
  const [factsPage, setFactsPage] = React.useState(1);
  const [evidencePage, setEvidencePage] = React.useState(1);
  const [decisionOpen, setDecisionOpen] = React.useState(false);
  const [researchOpsOpen, setResearchOpsOpen] = React.useState(() => window.location.hash === "#research-case");
  const [evidenceDrawerOpen, setEvidenceDrawerOpen] = React.useState(false);
  const [decision, setDecision] = React.useState({ choice: "research_more", rationale: "", confirmed: false });
  const [reportPreflight, setReportPreflight] = React.useState<LiveRow | null>(null);
  const query = useLongTermThesisWorkspace(thesisId, factsPage, evidencePage, PAGE_SIZE);
  const pushToast = useUIStore((state) => state.pushToast);
  const setAssistantOpen = useUIStore((state) => state.setAssistantOpen);
  const reportAction = useGenerateThesisReport();
  const reportPreflightAction = usePreflightThesisReport();
  const committeeAction = useOpenLongTermCommittee();
  const committeeDecision = useResolveLongTermCommittee();
  const watchlistAction = useUpsertWatchlist();
  const data = query.data;
  const selected = data?.selected_thesis ?? null;
  const selectedId = num(selected, "id", 0);
  const requestedSymbol = React.useMemo(() => new URLSearchParams(window.location.search).get("symbol")?.trim().toUpperCase() || "", []);
  const caseReportId = num(record(selected?.metadata), "report_id", 0);

  React.useEffect(() => {
    if (!requestedSymbol || !data?.theses.length) return;
    const match = data.theses.find((row) => text(row, "symbol").toUpperCase() === requestedSymbol);
    const matchId = num(match, "id", 0);
    if (matchId > 0 && matchId !== selectedId) {
      setThesisId(matchId);
      setFactsPage(1);
      setEvidencePage(1);
    }
  }, [data?.theses, requestedSymbol, selectedId]);
  const coverage = data?.coverage[0] ?? {};
  const freshness = data?.freshness[0] ?? {};
  const execution = data?.execution_control[0] ?? {};
  const opinions = React.useMemo(() => new Map((data?.specialist_opinions ?? []).map((row) => [text(row, "specialist_key"), row])), [data?.specialist_opinions]);
  const sections = React.useMemo(() => new Map((data?.dossier_sections ?? []).map((row) => [text(row, "section_key"), row])), [data?.dossier_sections]);
  const busy = reportAction.isPending || reportPreflightAction.isPending || committeeAction.isPending || watchlistAction.isPending || committeeDecision.isPending;

  React.useEffect(() => {
    document.body.classList.add("aios-thesis-context");
    setAssistantOpen(false);
    return () => document.body.classList.remove("aios-thesis-context");
  }, [setAssistantOpen]);

  React.useEffect(() => {
    const syncResearchHash = () => { if (window.location.hash === "#research-case") setResearchOpsOpen(true); };
    window.addEventListener("hashchange", syncResearchHash);
    return () => window.removeEventListener("hashchange", syncResearchHash);
  }, []);

  React.useEffect(() => {
    if (!data || !window.location.hash) return;
    const target = window.location.hash.slice(1);
    window.requestAnimationFrame(() => document.getElementById(target)?.scrollIntoView({ block: "start" }));
  }, [data, selectedId]);

  function mutate(label: string, mutation: { mutate: (input: never, options: { onSuccess: () => void; onError: (error: Error) => void }) => void }, input: Record<string, unknown>) {
    mutation.mutate(input as never, {
      onSuccess: () => { pushToast({ title: label, tone: "ok", duration: 3500 }); void query.refetch(); },
      onError: (error) => pushToast({ title: `${label} failed`, message: error.message, tone: "risk", duration: 6000 }),
    });
  }

  if (query.isLoading && !data) {
    return <main className="thesis-workspace"><div className="ltw-loading" role="status" aria-label="Loading thesis workspace"><span /><span /><span /><span /></div></main>;
  }
  if (query.isError && !data) {
    return <main className="thesis-workspace"><div className="ltw-failure" role="alert"><AlertTriangle size={24} /><h1>Thesis workspace could not load</h1><p>{query.error.message}</p><Button icon={RefreshCw} onClick={() => void query.refetch()} variant="primary">Retry bounded request</Button></div></main>;
  }
  if (!selected || !data) {
    return <main className="thesis-workspace"><div className="ltw-failure"><BookOpen size={24} /><h1>No persisted thesis</h1><p>This workspace does not invent a thesis. Initialize one from a canonical long-term holding first.</p></div></main>;
  }

  const thesisSource = data.thesis_versions[0] ?? {};
  const businessSection = sections.get("business_model") ?? sections.get("company_business_model");
  const moatSection = sections.get("moat_industry_structure") ?? sections.get("moat");
  const managementSection = sections.get("management_governance_capital_allocation");
  const financeSection = sections.get("financial_quality");
  const valuationSection = sections.get("valuation");
  const catalystSection = sections.get("catalysts_thesis_killers_monitoring");
  const committee = data.committee[0];
  const factsTotal = num(data.pagination, "facts_total", 0);
  const evidenceTotal = num(data.pagination, "evidence_total", 0);
  const extracted = num(coverage, "filings_extracted", 0);
  const registered = num(coverage, "filings_registered", 0);
  const extractionPct = registered ? (extracted / registered) * 100 : 0;
  const matrixRows = data.source_matrix ?? [];
  const pipelineRows = data.source_pipeline ?? [];
  const matrixCovered = matrixRows.filter((row) => text(row, "coverage_status") === "covered").length;
  const matrixPending = matrixRows.filter((row) => text(row, "coverage_status") === "pending_review").length;
  const matrixMissing = matrixRows.filter((row) => text(row, "coverage_status") === "missing").length;
  const matrixStale = matrixRows.filter((row) => text(row, "coverage_status") === "stale").length;
  const matrixDebt = matrixRows.reduce((total, row) => total + num(row, "coverage_debt", 0), 0);
  const latestBrief = data.cited_briefs[0];
  const latestThesisReport = data.thesis_reports[0];

  return (
    <main className="thesis-workspace">
      <header className="ltw-masthead">
        <div className="ltw-masthead__identity">
          <span>Long-term investment thesis</span>
          <div><h1>{text(selected, "legal_name", text(selected, "company_name", text(selected, "symbol")))}</h1><Badge>{text(selected, "exchange")}:{text(selected, "symbol")}</Badge></div>
          <p>{text(selected, "thesis_title")} · version {num(selected, "dossier_version_number", 0) || num(thesisSource, "version_number", 1)}</p>
        </div>
        <label className="ltw-company-select"><span>Company workspace</span><select value={selectedId} onChange={(event) => { setThesisId(Number(event.target.value)); setFactsPage(1); setEvidencePage(1); }}>{data.theses.map((row) => <option key={num(row, "id")} value={num(row, "id")}>{text(row, "symbol")} · {text(row, "legal_name", text(row, "company_name"))}</option>)}</select></label>
        <div className="ltw-masthead__actions">
          {latestThesisReport ? <><a className="ltw-case-report-link" href={reportViewUrl(num(latestThesisReport, "id"))} target="_blank" rel="noreferrer"><FileText size={16} />Open latest thesis report</a><a className="ltw-case-report-link ltw-case-report-link--quiet" href={`${API_BASE_URL}/api/research/thesis-reports/${num(latestThesisReport, "id")}/download`}><Download size={16} />Download thesis PDF</a></> : caseReportId ? <><a className="ltw-case-report-link" href={`${API_BASE_URL}/api/research/case-reports/${caseReportId}/view`}><FileText size={16} />Open research pack</a><a className="ltw-case-report-link ltw-case-report-link--quiet" href={`${API_BASE_URL}/api/research/case-reports/${caseReportId}/download`}><Download size={16} />Download case PDF</a></> : null}
          <Button disabled={busy} icon={Download} onClick={() => reportPreflightAction.mutate({ holding_thesis_id: selectedId, actor: "Devarsh" }, { onSuccess: (result) => { setReportPreflight(result); pushToast({ title: "Report estimate ready", message: "Review the local-only scope and explicitly confirm generation.", tone: "info", duration: 5000 }); }, onError: (error) => pushToast({ title: "Report estimate failed", message: error.message, tone: "risk", duration: 6000 }) })}>{reportPreflightAction.isPending ? "Estimating report..." : "Full Report - PDF + HTML"}</Button>
          <Button disabled={busy} icon={RefreshCw} onClick={() => void query.refetch()} variant="primary">Refresh</Button>
        </div>
      </header>

      {reportPreflight ? <section className="ltw-report-preflight" aria-live="polite"><div><span>Report generation estimate</span><strong>Local render - $0.00 paid-model/data cost</strong><p>{num(record(reportPreflight.source_snapshot), "validated_fact_count", 0)} validated facts across FY{num(record(reportPreflight.source_snapshot), "fiscal_year_start", 0)}-FY{num(record(reportPreflight.source_snapshot), "fiscal_year_end", 0)}. No external egress; outputs remain on the external SSD.</p></div><div><Button disabled={busy} icon={Download} onClick={() => reportAction.mutate({ holding_thesis_id: selectedId, report_preflight_id: num(reportPreflight, "id"), operator_confirmed: true, actor: "Devarsh" }, { onSuccess: () => { setReportPreflight(null); pushToast({ title: "Versioned thesis report generated", message: "The dated PDF and HTML companion are stored on the external SSD.", tone: "ok", duration: 5000 }); void query.refetch(); }, onError: (error) => pushToast({ title: "Report generation failed", message: error.message, tone: "risk", duration: 6000 }) })}>{reportAction.isPending ? "Generating..." : "Confirm and generate"}</Button><Button disabled={busy} onClick={() => setReportPreflight(null)} variant="ghost">Cancel</Button></div></section> : null}

      <div className="ltw-safety-strip">
        <span><LockKeyhole size={14} />{bool(execution, "global_execution_locked", true) ? "Execution locked" : "Execution state requires review"}</span>
        <span>Local-private · no private-data egress</span>
        <span>Generated {date(data.generated_at)}</span>
        {query.isFetching ? <span className="ltw-refreshing">Refreshing bounded data…</span> : null}
      </div>

      {text(selected, "symbol") === "USHAMART" ? <UshaMultiYearReport data={data} onResearch={() => { setResearchOpsOpen(true); window.setTimeout(() => document.getElementById("research-case")?.scrollIntoView({ behavior: "smooth" }), 30); }} /> : <InvestmentBrief selected={selected} business={businessSection} moat={moatSection} opinions={opinions} risks={data.governance_observations} filings={data.filings} models={data.valuation_models} financialHistory={data.financial_history} productionRatios={data.financial_production_ratios} validationChecks={data.financial_validation_checks} valuationWorkbench={record(data.valuation_workbench)} />}

      <section id="valuation-workbench" aria-label="Valuation and expected return">
        <ValuationWorkbench workbench={record(data.valuation_workbench)} />
      </section>

      <details className="ltw-research-operations ltw-frontstage-drawer" open={researchOpsOpen} onToggle={(event) => setResearchOpsOpen(event.currentTarget.open)}>
        <summary><div><span>Research Operations</span><strong>Start, repair or inspect a governed Research Case</strong></div><Badge tone={data.research_cases.some((row) => text(row, "status") === "blocked") ? "risk" : "default"}>{data.research_cases.length} case{data.research_cases.length === 1 ? "" : "s"}</Badge></summary>
        <ResearchCaseWorkspace selected={selected} cases={data.research_cases} agents={[]} workItems={[]} evidence={[]} events={[]} preflights={[]} modelRuns={[]} onRefresh={() => void query.refetch()} />
      </details>

      <details className="ltw-operations-summary"><summary>Research Operations · coverage, freshness and system gates</summary><section className="ltw-coverage" aria-label="Coverage summary">
        <div><span>Gross long-term exposure</span><strong>{formatCurrency(num(selected, "long_term_gross_exposure", 0))}</strong><small>{num(selected, "client_count", 0)} clients · {num(selected, "position_count", 0)} positions</small></div>
        <div><span>Normalized facts</span><strong>{num(coverage, "normalized_statement_facts", 0)}</strong><small>{num(coverage, "current_statement_facts", 0)} current · {num(coverage, "statement_companies", 0)} companies</small></div>
        <div><span>Evidence coverage</span><strong>{num(coverage, "evidence_records", 0)}</strong><small>{num(coverage, "evidence_companies", 0)} companies · {num(coverage, "active_ir_sources", 0)} active IR sources</small></div>
        <div className="ltw-coverage--debt"><span>Filing extraction debt</span><strong>{extracted} / {registered}</strong><small>{extractionPct.toFixed(1)}% extracted · conclusions remain gated</small></div>
      </section></details>

      <details className="ltw-evidence-drawer" open={evidenceDrawerOpen} onToggle={(event) => setEvidenceDrawerOpen(event.currentTarget.open)}>
        <summary><div><span>Evidence &amp; method</span><strong>Open the source ledger, calculations, validation and legacy research workspace</strong></div><Badge>{factsTotal} facts · {evidenceTotal} sources</Badge></summary>
      <div className="ltw-layout">
        <nav className="ltw-nav" aria-label="Thesis sections">{NAV_ITEMS.map(([id, label], index) => <a href={`#${id}`} key={id}><span>{String(index + 1).padStart(2, "0")}</span>{label}</a>)}</nav>
        <div className="ltw-document">
          <ResearchSection id="change-log" eyebrow="01 · thesis record" title="Thesis provenance and change log" state={text(selected, "thesis_status")} source={thesisSource}>
            <div className="ltw-thesis-lead"><blockquote>{text(selected, "thesis_summary", "No persisted thesis summary.")}</blockquote><dl><div><dt>Owner</dt><dd>{text(selected, "primary_owner_agent")}</dd></div><div><dt>Decision state</dt><dd>{text(selected, "decision_status")}</dd></div><div><dt>Research cutoff</dt><dd>{date(selected.source_cutoff_at)}</dd></div><div><dt>Next review</dt><dd>{date(selected.next_review_due_at)}</dd></div></dl></div>
            <div className="ltw-change-log"><h3><History size={15} />Durable versions</h3>{data.thesis_versions.map((row) => <article key={num(row, "id")}><span>v{num(row, "version_number")}</span><div><strong>{text(row, "change_type").replace(/_/g, " ")}</strong><p>{text(row, "thesis_summary")}</p></div><time>{date(row.created_at)}</time></article>)}</div>
          </ResearchSection>


          <ResearchSection id="business" eyebrow="02 · underwriting" title="Company, moat and industry structure" state={text(moatSection, "section_status", "source required")} source={moatSection || businessSection}>
            <div className="ltw-two-column"><div><h3><Building2 size={15} />Business model</h3><p>{text(selected, "business_model", markdownSummary(businessSection?.content_markdown) || "Business-model evidence is not yet persisted in the thesis record.")}</p></div><div><h3><Landmark size={15} />Industry structure</h3><p>{text(selected, "industry_structure", markdownSummary(moatSection?.content_markdown) || "Industry structure is not yet quantified.")}</p></div></div>
            <div className="ltw-opinion-grid"><Opinion row={opinions.get("business_model")} /><Opinion row={opinions.get("moat")} /><Opinion row={opinions.get("industry")} /></div>
            {text(selected, "symbol") === "USHAMART" ? <div className="ltw-segment-workbench"><header><div><span>Disclosed segment architecture</span><h3>Segment economics and reconciliation</h3></div><Badge>{data.segment_facts.length ? `${new Set(data.segment_facts.map((row) => text(row, "segment_name"))).size} disclosed segment` : "Unavailable"}</Badge></header><div className="ltw-table-wrap"><table><thead><tr><th>Segment</th><th>FY2025 revenue</th><th>FY2026 revenue</th><th>FY2026 result before finance/tax</th><th>FY2026 assets / liabilities</th><th>Source</th></tr></thead><tbody><tr><td><strong>Wire &amp; Wire Ropes</strong></td><td>₹3,374.3cr</td><td>₹3,613.1cr</td><td>₹650.4cr</td><td>₹3,664.5cr / ₹532.5cr</td><td><a className="ltw-citation" href="https://ushamartin.com/public/upload/investorrelations/Annual-Report-FY-2025-26.pdf" target="_blank" rel="noreferrer">Annual report · p.310</a></td></tr><tr><td><strong>Others</strong></td><td>₹99.9cr</td><td>₹78.0cr</td><td>(₹1.6cr)</td><td>₹64.5cr / ₹22.1cr</td><td><a className="ltw-citation" href="https://ushamartin.com/public/upload/investorrelations/Annual-Report-FY-2025-26.pdf" target="_blank" rel="noreferrer">Annual report · p.310</a></td></tr></tbody></table></div><div className="ltw-segment-gaps"><strong>Explicit gaps</strong><p>Segment capex, cash conversion, capacity/price/volume mix and customer concentration are not disclosed. Business-segment revenue, result, assets and liabilities reconcile on p.310. Geographic revenue on p.311 does not reconcile to consolidated revenue (FY2026 gap ₹95.4 crore), so geographic mix remains withheld.</p></div></div> : <div className="ltw-segment-workbench"><header><div><span>Disclosed segment architecture</span><h3>Company-scoped segment evidence</h3></div><Badge>{data.segment_facts.length ? `${new Set(data.segment_facts.map((row) => text(row, "segment_name"))).size} segments linked` : "Unavailable"}</Badge></header><div className="ltw-segment-gaps"><strong>Exact coverage state</strong><p>{data.segment_facts.length ? `${data.segment_facts.length} company-scoped segment facts are linked in the evidence ledger. Open the raw fact ledger below for their periods, units and citations.` : "No validated segment revenue, profit, capital employed or reconciliation facts are linked for this company."}</p></div></div>}
          </ResearchSection>

          <ResearchSection id="stewardship" eyebrow="03 · stewardship" title="Management, governance and capital allocation" state={text(managementSection, "section_status", "review required")} source={managementSection || opinions.get("governance")}>
            <div className="ltw-opinion-grid"><Opinion row={opinions.get("management")} /><Opinion row={opinions.get("governance")} /><Opinion row={opinions.get("capital_allocation")} /></div>
            <div className="ltw-guidance"><header><span>Management guidance versus delivery</span><h3>Exact commitments</h3></header>{data.management_guidance.length ? <div className="ltw-table-wrap"><table><thead><tr><th>Metric / commitment</th><th>Target</th><th>Horizon / given</th><th>Actual progress</th><th>Delivery</th><th>Evidence</th></tr></thead><tbody>{data.management_guidance.map((row) => <tr key={num(row, "claim_id")}><td><strong>{text(row, "metric_key").replace(/_/g, " ")}</strong><small>{text(row, "claim_text")}</small></td><td>{text(row, "target_operator")} {num(row, "target_value")} {text(row, "target_unit")}</td><td>{text(row, "target_period_end")}<small>Given {text(row, "claim_date")}</small></td><td>{row.actual_value === null || row.actual_value === undefined ? "Not yet due / no outcome" : `${num(row, "actual_value")} ${text(row, "actual_unit")}`}<small>{text(row, "assessment")}</small></td><td><StatusPill status={text(row, "outcome_status", text(row, "claim_status"))} /></td><td><Citation row={row} label="Guidance source" />{text(row, "outcome_source_url") ? <a className="ltw-citation" href={text(row, "outcome_source_url")} target="_blank" rel="noreferrer">Outcome evidence <ExternalLink size={11} /></a> : null}</td></tr>)}</tbody></table></div> : <EmptyState title="No exact management guidance" detail="The workspace will not infer promises from generic management commentary." />}</div>
            {data.governance_observations.length ? <div className="ltw-observations"><h3>Forensic observations</h3>{data.governance_observations.map((row) => <article key={num(row, "id")}><StatusPill status={text(row, "severity")} /><div><strong>{text(row, "category").replace(/_/g, " ")}</strong><p>{text(row, "conclusion")}</p></div><Citation row={row} /></article>)}</div> : <EmptyState title="No structured governance observations" detail="Absence of a stored red flag is not evidence that governance is clean." />}
          </ResearchSection>

          {text(selected, "symbol") === "USHAMART" ? <ResearchSection id="financials" eyebrow="04 · investor decision workspace" title="Financial Quality" state={data.financial_facts.length ? "machine extracted" : "missing"} source={data.financial_facts[0] || financeSection}>
            {data.financial_production_runs[0] ? <div className="ltw-guidance"><header><span>What changed and why it matters</span><h3>Profitability, cash conversion and balance-sheet quality improved in FY2026</h3><p>Revenue grew 6.2%, pre-exception EBITDA rose 21.6% and FCF increased from ₹177.1 crore to ₹457.3 crore. CFO / continuing PAT improved to 133.4%, while net debt of ₹76.8 crore moved to net cash of ₹96.3 crore. All values reconcile to the consolidated FY2026 annual report and FY2025 comparatives.</p></header><div className="ltw-table-wrap"><table><thead><tr><th>Decision metric</th><th>FY2025</th><th>FY2026</th><th>Investor read-through</th></tr></thead><tbody><tr><td><strong>Revenue</strong></td><td>₹3,474.2cr</td><td>₹3,691.1cr</td><td>6.2% growth</td></tr><tr><td><strong>EBITDA / margin</strong></td><td>₹636.5cr / 18.3%</td><td>₹774.0cr / 21.0%</td><td>Margin +2.7pp</td></tr><tr><td><strong>CFO / FCF</strong></td><td>₹421.8cr / ₹177.1cr</td><td>₹655.3cr / ₹457.3cr</td><td>Cash conversion strengthened</td></tr><tr><td><strong>CFO / continuing PAT</strong></td><td>103.8%</td><td>133.4%</td><td>Earnings backed by cash</td></tr><tr><td><strong>Net debt / (cash)</strong></td><td>₹76.8cr</td><td>(₹96.3cr)</td><td>Balance sheet moved to net cash</td></tr><tr><td><strong>Interest coverage</strong></td><td>18.2x</td><td>33.5x</td><td>Financing headroom improved</td></tr></tbody></table></div><details><summary>Evidence and calculation method</summary><p>Consolidated · INR lakh · Annual Report pp. 240–243 · SHA-256 verified · deterministic validation, not human reviewed.</p><div className="ltw-table-wrap"><table><thead><tr><th>Metric</th><th>Period</th><th>Value</th><th>Formula / basis</th><th>Inputs and page citations</th></tr></thead><tbody>{data.financial_production_ratios.map((row) => <tr key={num(row, "id")}><td>{text(row, "label")}</td><td>{text(row, "period_end")}</td><td>{row.value === null || row.value === undefined ? "Not computable" : `${num(row, "value").toLocaleString("en-IN", { maximumFractionDigits: 2 })}${text(row, "unit") === "percent" ? "%" : text(row, "unit") === "lakh" ? " INR lakh" : "x"}`}</td><td>{text(row, "expression")}<small>{jsonSummary(row.basis)}</small></td><td>{Array.isArray(row.inputs) ? row.inputs.map((input, index) => <small key={index}>{text(record(input), "input_role").replace(/_/g, " ")}: {num(record(input), "value").toLocaleString("en-IN")} lakh · p.{num(record(input), "source_page")}</small>) : "Inputs unavailable"}</td></tr>)}</tbody></table></div>{data.financial_validation_checks.map((row) => <p key={num(row, "id")}><strong>{text(row, "check_type").replace(/_/g, " ")}</strong> · {text(row, "period_end")} · {text(row, "explanation")} · pp. {Array.isArray(row.source_pages) ? row.source_pages.join(", ") : "?"}</p>)}</details></div> : null}
            <details className="ltw-research-operations"><summary><div><span>Method and raw fact ledger</span><strong>As-reported facts, normalization and calculation audit</strong></div></summary>            <FinancialQualityWorkspace quality={record(data.financial_quality)} facts={data.financial_facts} page={factsPage} total={factsTotal} onPage={setFactsPage} />
            </details>
          </ResearchSection> : <ResearchSection id="financials" eyebrow="04 · evidence appendix" title="Financial calculation ledger" state={data.financial_facts.length ? "source captured" : "missing"} source={data.financial_facts[0] || financeSection}><details className="ltw-research-operations"><summary><div><span>Method and raw fact ledger</span><strong>Company-scoped as-reported facts, normalization and calculation audit</strong></div></summary><FinancialQualityWorkspace quality={record(data.financial_quality)} facts={data.financial_facts} page={factsPage} total={factsTotal} onPage={setFactsPage} /></details></ResearchSection>}

          <ResearchSection id="valuation" eyebrow="05 · valuation workbench" title="Assumptions, scenarios and model status" state={text(selected, "valuation_status")} source={valuationSection || data.valuation_models[0]}>
            {data.valuation_models.length ? <div className="ltw-models">{data.valuation_models.map((row) => { const status = text(row, "status").toLowerCase(); const assumptions = record(row.assumptions); const outputs = record(row.outputs); const calculated = ["complete", "validated", "human_reviewed", "approved"].includes(status); const humanReviewed = ["human_reviewed", "approved"].includes(status); const scenario = (value: unknown) => calculated && value !== null && value !== undefined ? formatCurrency(Number(value)) : "Not available"; return <details key={num(row, "id")}><summary><div><strong>{text(row, "model_name")}</strong><span>{text(row, "model_type").replace(/_/g, " ")} · as of {date(row.updated_at)}</span></div><StatusPill status={humanReviewed ? "human_reviewed" : calculated ? "calculated_unreviewed" : text(row, "status")} /></summary><div className="ltw-model-detail"><div className="ltw-model-meaning"><strong>What it means</strong><p>{text(row, "model_type") === "reverse_dcf" ? "The growth the current market price requires—not a fair-value target." : text(row, "model_type") === "dcf" ? "Present value under explicit cash-flow growth, discount-rate and terminal-growth scenarios." : text(row, "model_type") === "relative_valuation" ? "Earnings-multiple sensitivity; not a peer comparison unless compatible peer observations are linked." : "A calculated model artifact. Treat it as a scenario, not certainty."}</p><small>Market price: {assumptions.current_price === null || assumptions.current_price === undefined ? "Not recorded" : formatCurrency(num(assumptions, "current_price"))} · price source/as-of {jsonSummary(assumptions.current_price_source)}</small></div><dl><div><dt>Bear scenario</dt><dd>{scenario(row.fair_value_low)}</dd></div><div><dt>Base scenario</dt><dd>{scenario(row.fair_value_base)}</dd></div><div><dt>Bull scenario</dt><dd>{scenario(row.fair_value_high)}</dd></div><div><dt>Expected CAGR / IRR</dt><dd>{calculated && row.expected_cagr_pct !== null && row.expected_cagr_pct !== undefined ? num(row, "expected_cagr_pct").toFixed(1) + "%" : "Not available"}</dd></div></dl><p><b>Provenance / model inputs:</b> {jsonSummary(assumptions)}</p><p><b>Formula, horizon, uncertainty, sensitivity and backtest status:</b> {jsonSummary(outputs)}</p>{!humanReviewed ? <p><b>Gate:</b> Values are calculation-complete but not operator-reviewed. They cannot support a recommendation or capital decision.</p> : null}</div></details>; })}</div> : <EmptyState title="No valuation model" detail="Fair value and expected return remain unavailable until source-backed assumptions are persisted." />}
            {data.monte_carlo_runs[0] ? <div className="ltw-wacc-gate"><AlertTriangle size={16} /><p><strong>Scenario distribution withheld.</strong> A {compactNumber(data.monte_carlo_runs[0].simulation_count)}-run artifact exists, but its methodology/replay is not human-validated. Probability and drawdown outputs are therefore not presented as decision evidence.</p></div> : null}
          </ResearchSection>

          <ResearchSection id="catalysts" eyebrow="06 · monitoring timeline" title="Catalysts, filings and news" state={data.filings.length ? "source linked" : "coverage missing"} source={data.filings[0] || catalystSection}>
            <div className="ltw-timeline">{[...data.filings.map((row) => ({ ...row, kind: "Filing", when: row.filed_at })), ...data.news.map((row) => ({ ...row, kind: "News", when: row.published_at || row.captured_at }))].sort((a, b) => new Date(String(b.when || 0)).getTime() - new Date(String(a.when || 0)).getTime()).slice(0, 18).map((row, index) => <article key={`${text(row, "kind")}-${num(row, "filing_id", num(row, "id", index))}`}><time>{date(row.when)}</time><span>{text(row, "kind")}</span><div><strong>{text(row, "title")}</strong><p>{text(row, "event_type", text(row, "publisher", text(row, "source_name"))).replace(/_/g, " ")}</p></div><Citation row={row} label="Open original" /></article>)}</div>
            {!data.filings.length && !data.news.length ? <EmptyState title="No current catalysts" detail="No symbol-linked filing or news record is available in this bounded page." /> : null}
          </ResearchSection>

          <ResearchSection id="risks" eyebrow="07 · adversarial review" title="Bear case, risks and red flags" state={text(opinions.get("bear_case"), "opinion_status", "review required")} source={opinions.get("bear_case") || catalystSection}>
            <Opinion row={opinions.get("bear_case")} />
            <div className="ltw-killers"><h3><Target size={16} />Thesis killers</h3>{rows(selected.thesis_killers).map((row, index) => <article key={`${text(row, "killer")}-${index}`}><span>{String(index + 1).padStart(2, "0")}</span><div><strong>{text(row, "killer").replace(/_/g, " ")}</strong><p>{text(row, "test")}</p></div></article>)}</div>
            <div className="ltw-exit"><strong>Exit discipline</strong><p>{text(selected, "exit_criteria", "Exit criteria are not recorded.")}</p></div>
          </ResearchSection>

          <ResearchSection id="evidence" eyebrow="08 · evidence library" title="Filings, transcripts, news and first-party sources" state={matrixRows.length > 0 && matrixCovered === matrixRows.length ? "covered" : matrixPending > 0 ? "review required" : "missing"} source={data.fundamental_evidence[0]}>
            <div className="ltw-source-governance">
              <div className="ltw-source-governance__head">
                <div><span>Source-to-section contract</span><h3>{matrixCovered}/{matrixRows.length} data points covered</h3></div>
                <div className="ltw-source-governance__stats">
                  <span className="is-pending">{matrixPending} pending review</span>
                  <span className="is-missing">{matrixMissing} missing</span>
                  <span>{matrixStale} stale</span>
                  <span>{matrixDebt} source-count debt</span>
                </div>
              </div>
              {matrixRows.length ? (
                <div className="ltw-matrix-wrap">
                  <table className="ltw-matrix">
                    <thead><tr><th>Section / data point</th><th>Gate</th><th>Freshness</th><th>Coverage</th><th>Citation</th></tr></thead>
                    <tbody>{matrixRows.map((row) => {
                      const source = rows(row.sources)[0];
                      return <tr key={text(row, "requirement_key")}>
                        <td><strong>{text(row, "requirement_label")}</strong><small>{text(row, "section_key").replace(/_/g, " ")} · {text(row, "requirement_key")}</small></td>
                        <td><span>{num(row, "minimum_source_count")} source{num(row, "minimum_source_count") === 1 ? "" : "s"}</span><small>{text(row, "minimum_validation").replace(/_/g, " ")}{bool(row, "extraction_required", false) ? " · parsed" : ""}</small></td>
                        <td>{row.max_age_days ? num(row, "max_age_days") + " days" : "event-driven"}</td>
                        <td><StatusPill status={text(row, "coverage_status")} /><small>{num(row, "coverage_debt")} debt</small></td>
                        <td>{source ? <Citation row={source} label="Exact source" /> : <span className="ltw-source-gap">Not linked</span>}</td>
                      </tr>;
                    })}</tbody>
                  </table>
                </div>
              ) : <EmptyState title="Coverage matrix unavailable" detail="The governed requirement matrix did not return for this company; no section is treated as covered." />}
              <div className="ltw-pipeline">
                <div className="ltw-pipeline__title"><div><strong>Review and exception queue</strong><span>Capture, parsing, validation and section linking remain separate gates.</span></div><Badge tone={pipelineRows.length ? "warn" : "ok"}>{pipelineRows.length} sources</Badge></div>
                {pipelineRows.length ? pipelineRows.map((row) => <article key={num(row, "source_item_id")}>
                  <div><strong>{text(row, "source_title")}</strong><p>{text(row, "source_kind").replace(/_/g, " ")} · captured {date(row.captured_at)} · {text(row, "next_gate").replace(/_/g, " ")}</p></div>
                  <div className="ltw-pipeline__states"><Badge>{canonicalEvidenceStatus(row.parser_status)}</Badge><Badge>{canonicalEvidenceStatus(row.validation_status)}</Badge><span>{num(row, "proposed_link_count")} proposed / {num(row, "validated_link_count")} validated</span></div>
                  <Citation row={row} label="Open official source" />
                </article>) : <EmptyState title="No governed source items" detail="Register and reconcile official or authorized sources before linking evidence." />}
              </div>
              {latestBrief ? <div className="ltw-brief-ledger"><FileText size={16} /><div><strong>Latest cited coverage brief · {text(latestBrief, "brief_status").replace(/_/g, " ")}</strong><p>{text(latestBrief, "artifact_path")} · SHA-256 {text(latestBrief, "artifact_hash").slice(0, 12)}… · generated {date(latestBrief.generated_at)}</p></div></div> : null}
            </div>
            <div className="ltw-debt"><AlertTriangle size={18} /><div><strong>{registered - extracted} registered filings still lack extraction</strong><p>Only {extracted} of {registered} filings are extracted. Unextracted documents count as coverage debt, not supporting evidence.</p></div></div>
            <div className="ltw-source-columns"><div><h3>Governed evidence</h3>{data.fundamental_evidence.map((row) => <article key={num(row, "id")}><div><strong>{text(row, "source_title")}</strong><p>{text(row, "source_type").replace(/_/g, " ")} · as of {date(row.source_as_of_date || row.published_at)}</p></div><Badge>{canonicalEvidenceStatus(row.verification_status)}</Badge><Citation row={row} label="Open" /></article>)}</div><div><h3>Company IR registry</h3>{data.ir_sources.map((row) => <article key={num(row, "id")}><div><strong>{text(row, "document_label", text(row, "source_kind"))}</strong><p>Collected {date(row.last_collected_at)}</p></div><StatusPill status={text(row, "status")} /><Citation row={row} label="Open IR" /></article>)}</div></div>
            {!data.fundamental_evidence.length ? <EmptyState title="No evidence on this page" detail="Use the pager to inspect another bounded evidence page; no source has been fabricated." /> : null}
            <Pager page={evidencePage} total={Math.max(evidenceTotal, num(data.pagination, "filings_total", 0))} onChange={setEvidencePage} />
          </ResearchSection>

          <ResearchSection id="agents" eyebrow="09 · independent lanes" title="Agent opinions and disagreement" state={data.specialist_opinions.some((row) => text(row, "opinion_status") === "dissent") ? "dissent preserved" : "review required"} source={opinions.get("bear_case") || data.specialist_opinions[0]}>
            <div className="ltw-agent-matrix">{data.specialist_opinions.map((row) => <Opinion key={num(row, "id")} row={row} />)}</div>
            {!data.specialist_opinions.length ? <EmptyState title="No agent opinions" detail="Dispatching specialists creates durable, independent lanes; it does not authorize a recommendation or trade." /> : null}
          </ResearchSection>

          <ResearchSection id="watchlist" eyebrow="10 · monitoring" title="Watchlist and alerts" state={data.watchlist.length ? "active" : "not watched"} source={data.watchlist[0]}>
            <div className="ltw-watchlist-head"><p>Monitoring state is internal only. No broker order, external alert, or account automation is created.</p><Button disabled={busy || data.watchlist.length > 0} icon={Send} onClick={() => mutate("Added to governed watchlist", watchlistAction, { symbol: text(selected, "symbol"), exchange: text(selected, "exchange"), company_name: text(selected, "legal_name", text(selected, "company_name")), item_type: "research", priority: "medium", thesis: text(selected, "thesis_summary"), invalidation: text(selected, "exit_criteria"), actor: "Devarsh" })}>{data.watchlist.length ? "Already monitored" : "Add to watchlist"}</Button></div>
            {data.watchlist.map((row) => <article className="ltw-watch-row" key={num(row, "id")}><div><strong>{text(row, "watchlist_name")}</strong><p>{text(row, "thesis")}</p><small>Invalidation: {text(row, "invalidation", "not recorded")}</small></div><StatusPill status={text(row, "status")} /><time>Review {date(row.review_on)}</time></article>)}
          </ResearchSection>

          <ResearchSection id="decision" eyebrow="11 · human gate" title="Decision, approval and outcome" state={text(committee, "decision_status", "committee not opened")} source={committee || thesisSource}>
            <div className="ltw-decision-grid"><div><span>Committee review</span><strong>{text(committee, "review_status", "Not opened")}</strong></div><div><span>Recommended decision</span><strong>{text(committee, "recommended_decision", "Research required")}</strong></div><div><span>Final outcome</span><strong>{text(committee, "final_decision", "No final decision")}</strong></div><div><span>Capital action</span><strong>{bool(committee, "capital_action_allowed", false) ? "Allowed" : "Blocked"}</strong></div></div>
            {data.thesis_reports.length ? <div className="ltw-report-ledger"><h3><FileText size={15} />Versioned thesis reports</h3>{data.thesis_reports.map((row) => <article key={num(row, "id")}><div><strong>Report v{num(row, "report_version")} · as of {text(row, "as_of_date")}</strong><p>{text(row, "report_status")} · SHA-256 {text(row, "artifact_hash").slice(0, 12)}… · citations, values, coverage and caveats included</p></div><a href={reportViewUrl(num(row, "id"))} target="_blank" rel="noreferrer">Open HTML <ExternalLink size={12} /></a></article>)}</div> : <EmptyState title="No dated thesis report" detail="Use Generate cited report. The output is versioned on Devarsh SSD and remains human-review gated." />}
            {committee ? <div className="ltw-committee-record"><Gavel size={18} /><div><strong>{text(committee, "decision_notes", "Committee record is open; a final rationale is not recorded.")}</strong><p>Approval {text(committee, "approval_status", "not issued")} · live execution {bool(committee, "live_execution_allowed", false) ? "allowed" : "blocked"} · updated {date(committee.updated_at)}</p></div></div> : <EmptyState title="No committee record" detail="Open a review only when the source packet is ready. This does not authorize capital or execution." />}
            <div className="ltw-decision-actions"><Button disabled={busy || Boolean(committee)} icon={Gavel} onClick={() => mutate("Committee review opened", committeeAction, { holding_thesis_id: selectedId, actor: "Devarsh" })}>Open committee review</Button><Button disabled={busy || !committee || text(committee, "decision_status") === "final"} icon={ClipboardCheck} onClick={() => setDecisionOpen((current) => !current)} variant="primary">Record human decision</Button></div>
            {decisionOpen && committee ? <form className="ltw-decision-form" onSubmit={(event) => { event.preventDefault(); if (!decision.confirmed || decision.rationale.trim().length < 12) return; mutate("Committee decision recorded", committeeDecision, { review_id: num(committee, "id"), decision: decision.choice, notes: decision.rationale.trim(), actor: "Devarsh" }); setDecisionOpen(false); }}><label><span>Decision</span><select value={decision.choice} onChange={(event) => setDecision({ ...decision, choice: event.target.value })}><option value="research_more">Research more</option><option value="monitor">Monitor</option><option value="reject">Reject</option><option value="approve_watchlist">Approve watchlist</option><option value="approve_hold">Approve hold</option></select></label><label><span>Decision rationale</span><textarea minLength={12} required rows={4} value={decision.rationale} onChange={(event) => setDecision({ ...decision, rationale: event.target.value })} /></label><label className="ltw-confirm"><input checked={decision.confirmed} onChange={(event) => setDecision({ ...decision, confirmed: event.target.checked })} type="checkbox" /><span>I explicitly confirm this committee record. It authorizes no broker, client, or external write.</span></label><Button disabled={!decision.confirmed || decision.rationale.trim().length < 12 || busy} icon={CheckCircle2} type="submit" variant="primary">Confirm durable decision</Button></form> : null}
          </ResearchSection>
        </div>

        <aside className="ltw-rail">
          <section><h2><ShieldCheck size={15} />Coverage state</h2><dl><div><dt>Company facts</dt><dd>{factsTotal}</dd></div><div><dt>Company evidence</dt><dd>{evidenceTotal}</dd></div><div><dt>Stored opinions</dt><dd>{num(coverage, "selected_company_opinions", 0)}</dd></div><div><dt>Company filings</dt><dd>{num(coverage, "selected_company_filings", 0)}</dd></div></dl></section>
          <section><h2><CalendarClock size={15} />Freshness</h2><dl><div><dt>Evidence</dt><dd>{date(freshness.evidence_at)}</dd></div><div><dt>Opinions</dt><dd>{date(freshness.opinions_at)}</dd></div><div><dt>Valuation</dt><dd>{date(freshness.valuation_at)}</dd></div><div><dt>News</dt><dd>{date(freshness.news_at)}</dd></div></dl></section>
          <section className="ltw-rail__lock"><h2><LockKeyhole size={15} />Control boundary</h2><p>{text(execution, "lock_reason", "Broker and external writes are locked.")}</p><Badge tone="warn">read-only → draft → paper → staged → human</Badge></section>
        </aside>
      </div>
      </details>
    </main>
  );
}
