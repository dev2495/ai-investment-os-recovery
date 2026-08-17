import React from "react";
import { AlertTriangle, CheckCircle2, ExternalLink, RefreshCw, Scale, ShieldCheck } from "lucide-react";
import type { LiveRow } from "../../data/liveRow";
import { num, text } from "../../data/liveRow";
import "./ValuationWorkbench.css";

const object = (raw: unknown): LiveRow => raw && typeof raw === "object" && !Array.isArray(raw) ? raw as LiveRow : {};
const list = (raw: unknown): LiveRow[] => Array.isArray(raw) ? raw.filter((row): row is LiveRow => Boolean(row && typeof row === "object")) : [];
const money = (raw: unknown) => raw === null || raw === undefined ? "Not available" : `₹${Number(raw).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
const percent = (raw: unknown) => raw === null || raw === undefined ? "Not available" : `${(Number(raw) * (Math.abs(Number(raw)) <= 1 ? 100 : 1)).toFixed(1)}%`;
const displayDate = (raw: unknown) => {
  if (!raw) return "timestamp unavailable";
  const parsed = new Date(String(raw));
  return Number.isNaN(parsed.getTime()) ? String(raw) : new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(parsed);
};
const compactJson = (raw: unknown) => {
  if (!raw || typeof raw !== "object") return "Not recorded";
  return Object.entries(raw as Record<string, unknown>)
    .filter(([, value]) => value !== null && value !== undefined && !Array.isArray(value) && typeof value !== "object")
    .map(([key, value]) => `${key.replace(/_/g, " ")}: ${String(value)}`)
    .join(" · ") || "See structured inputs";
};

function MethodRange({ row, price }: { row: LiveRow; price: number | null }) {
  const status = text(row, "status", "blocked");
  const output = status !== "blocked";
  const base = row.base === null || row.base === undefined ? null : num(row, "base");
  const expectedReturn = price && base ? ((base / price) - 1) * 100 : null;
  const assumptions = object(row.assumptions);
  const outputs = object(row.outputs);
  return <article className={`valuation-method is-${status.replace(/_/g, "-")}`}>
    <header><div><span>{text(row, "label")}</span><strong>{output ? money(base) : "Not computed"}</strong></div><em>{status.replace(/_/g, " ")}</em></header>
    <p>{text(row, "meaning")}</p>
    {output ? <div className="valuation-range">
      <span><small>Bear</small><b>{money(row.bear)}</b></span><span><small>Base</small><b>{money(row.base)}</b></span><span><small>Bull</small><b>{money(row.bull)}</b></span>
    </div> : null}
    <dl>
      <div><dt>Expected return to base</dt><dd>{expectedReturn === null ? "Not computable" : `${expectedReturn.toFixed(1)}%`}</dd></div>
      <div><dt>As of</dt><dd>{displayDate(row.as_of)}</dd></div>
      <div><dt>Decision use</dt><dd>{row.decision_usable === true ? "Reviewed input" : "Scenario only"}</dd></div>
    </dl>
    <details><summary>Formula, assumptions and lineage</summary><p><b>Inputs:</b> {compactJson(assumptions)}</p><p><b>Outputs:</b> {compactJson(outputs)}</p><p><b>Owner:</b> {text(row, "owner", "Valuation Agent")}</p></details>
  </article>;
}

export function ValuationWorkbench({ workbench }: { workbench: LiveRow }) {
  const price = object(workbench.current_price);
  const shareBasis = object(workbench.share_basis);
  const bridge = object(workbench.equity_bridge);
  const actuals = object(workbench.actuals);
  const review = object(workbench.review);
  const methods = list(workbench.methods);
  const blockers = list(workbench.blockers);
  const monte = object(workbench.monte_carlo);
  const dcf = methods.find((row) => text(row, "key") === "dcf");
  const reverse = methods.find((row) => text(row, "key") === "reverse_dcf");
  const dcfAssumptions = object(dcf?.assumptions);
  const scenarios = object(dcfAssumptions.scenarios);
  const currentPrice = price.value === null || price.value === undefined ? null : num(price, "value");
  const impliedGrowth = num(object(reverse?.outputs), "implied_annual_fcf_growth", Number.NaN);

  return <div className="valuation-workbench">
    <section className="valuation-verdict">
      <div><span>Valuation decision posture</span><h3>{text(review, "status", "review required").replace(/_/g, " ")}</h3><p>{text(review, "next_action", "Complete the source-backed valuation inputs and record human review.")}</p></div>
      <aside><ShieldCheck size={20}/><strong>No capital action</strong><small>Historical facts, management guidance, external estimates and model scenarios remain separate.</small></aside>
    </section>

    <div className="valuation-basis">
      <article><span>Market price</span><strong>{currentPrice === null ? "Missing" : money(currentPrice)}</strong><p>{text(price, "provider", "No provider")} · {displayDate(price.as_of)}</p><small className={`state-${text(price, "freshness_status", "missing")}`}>{text(price, "verification_status", "missing").replace(/_/g, " ")} · {text(price, "freshness_status", "missing")}</small></article>
      <article><span>Share basis</span><strong>{shareBasis.shares_crore === null || shareBasis.shares_crore === undefined ? "Missing" : `${num(shareBasis, "shares_crore").toFixed(2)}cr`}</strong><p>FY{num(shareBasis, "period", num(actuals, "fiscal_year_end"))} · {text(shareBasis, "method", "No method")}</p><small>{text(shareBasis, "status", "missing").replace(/_/g, " ")}</small></article>
      <article><span>Equity bridge</span><strong>{bridge.net_debt_crore === null || bridge.net_debt_crore === undefined ? "Missing" : `${num(bridge, "net_debt_crore") < 0 ? "Net cash" : "Net debt"} ${money(Math.abs(num(bridge, "net_debt_crore")))}cr`}</strong><p>Cash &amp; equivalents {money(bridge.cash_crore)}cr · debt {money(bridge.debt_crore)}cr</p><small>Other bank balances {bridge.other_bank_balances_crore === null || bridge.other_bank_balances_crore === undefined ? "not recorded" : `${money(bridge.other_bank_balances_crore)}cr (excluded pending liquidity review)`} · FY{num(bridge, "period")}</small></article>
      <article><span>Historical basis</span><strong>{num(actuals, "years")} years</strong><p>FY{num(actuals, "fiscal_year_start")}–FY{num(actuals, "fiscal_year_end")}</p><small>{num(actuals, "validation_checks_passed")}/{num(actuals, "validation_checks_total")} validation checks passed</small></article>
    </div>

    <section className="valuation-classification"><Scale size={17}/><div><strong>Read the labels before the values</strong><p><b>Actual:</b> issuer-reported and validated. <b>Guidance:</b> management claim. <b>Estimate:</b> unavailable unless lawfully sourced. <b>Scenario:</b> analyst calculation, never a historical fact.</p></div></section>

    <section className="valuation-methods"><header><div><span>Method comparison</span><h3>Each method answers a different investment question</h3></div><p>{num(workbench, "scenario_count")} calculated method{num(workbench, "scenario_count") === 1 ? "" : "s"}; none becomes decision-ready without fresh price and human review.</p></header><div>{methods.map((row) => <MethodRange key={text(row, "key")} row={row} price={currentPrice} />)}</div></section>

    {dcf && text(dcf, "status") !== "blocked" ? <section className="valuation-sensitivity"><header><span>DCF sensitivity</span><h3>Growth, discount rate and terminal value drive the range</h3><p>Outputs are persisted scenarios, not point-forecast certainty.</p></header><div className="valuation-scenario-grid">
      {Object.entries(scenarios).map(([key, raw]) => { const row = object(raw); const value = key === "low" ? dcf.bear : key === "high" ? dcf.bull : dcf.base; return <article key={key}><span>{key === "low" ? "Bear" : key === "high" ? "Bull" : "Base"}</span><strong>{money(value)}</strong><dl><div><dt>FCF growth</dt><dd>{percent(row.growth)}</dd></div><div><dt>Discount</dt><dd>{percent(row.discount)}</dd></div><div><dt>Terminal</dt><dd>{percent(row.terminal_growth)}</dd></div></dl></article>; })}
    </div><p className="valuation-normalization"><b>Cash-flow base:</b> {text(dcfAssumptions, "normalization", "Normalization method not recorded")} · horizon {num(dcfAssumptions, "years")} years. {Number.isFinite(impliedGrowth) ? <><b> Reverse DCF:</b> current price requires {percent(impliedGrowth)} annual FCF growth under the stored assumptions.</> : null}</p></section> : null}

    <section className="valuation-monte"><AlertTriangle size={19}/><div><strong>Monte Carlo distribution withheld</strong><p>{text(monte, "reason")}</p>{monte.legacy_run_id ? <small>Legacy run #{num(monte, "legacy_run_id")} · {num(monte, "simulation_count").toLocaleString("en-IN")} simulations retained for audit, not decision use.</small> : null}</div></section>

    <section className="valuation-repair"><header><div><span>Review and repair queue</span><h3>{blockers.length} exact valuation gate{blockers.length === 1 ? "" : "s"}</h3></div><a href="#research-case"><RefreshCw size={15}/> Open research workstream</a></header><div>{blockers.map((row) => <article key={text(row, "key")}><div><em>{text(row, "priority")}</em><strong>{text(row, "title")}</strong><p>{text(row, "reason")}</p><small><CheckCircle2 size={13}/> Repair: {text(row, "repair")}</small></div><a href={text(row, "key") === "market_price" ? "#catalysts" : text(row, "key") === "human_review" ? "#decision" : "#financials"}>Open input <ExternalLink size={12}/></a></article>)}</div></section>
  </div>;
}
