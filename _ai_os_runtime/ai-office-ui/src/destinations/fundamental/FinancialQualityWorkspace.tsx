import React from "react";
import { AlertTriangle, ExternalLink, LineChart } from "lucide-react";
import type { LiveRow } from "../../data/liveRow";
import { num, text } from "../../data/liveRow";
import { Badge, Button } from "../../system/primitives";

function object(raw: unknown): LiveRow {
  return raw && typeof raw === "object" && !Array.isArray(raw) ? raw as LiveRow : {};
}

function list(raw: unknown): LiveRow[] {
  return Array.isArray(raw) ? raw.filter((row): row is LiveRow => Boolean(row && typeof row === "object")) : [];
}

function displayValue(metric: LiveRow, scale: number, suffix = ""): string {
  if (metric.value === null || metric.value === undefined || Number.isNaN(Number(metric.value))) return "Not computable";
  return `${(Number(metric.value) / scale).toLocaleString("en-IN", { maximumFractionDigits: 1 })}${suffix}`;
}

function metricAt(row: LiveRow, group: "metrics" | "derived", key: string): LiveRow {
  return object(object(row[group])[key]);
}

function sourceHref(metric: LiveRow): string { return text(metric, "source_url"); }

function CalculationCard({ title, metric, scale = 1, suffix = "", note }: { title: string; metric: LiveRow; scale?: number; suffix?: string; note?: string }) {
  const inputs = list(metric.inputs);
  return <details className={`ltw-calc-card ${metric.value === null || metric.value === undefined ? "is-missing" : ""}`}>
    <summary><span>{title}</span><strong>{displayValue(metric, scale, suffix)}</strong><small>{text(metric, "status", text(metric, "kind", "Not computable")).replace(/_/g, " ")}</small></summary>
    <div><p><b>Formula:</b> {text(metric, "formula", "Formula not recorded")}</p>{note ? <p>{note}</p> : null}
      {list(metric.missing_inputs).length ? <p><b>Exact gap:</b> {list(metric.missing_inputs).map((row) => String(row)).join(", ")}</p> : null}
      {inputs.length ? <ul>{inputs.map((input, index) => <li key={`${text(input, "fact_key")}-${index}`}><span>{text(input, "label", text(input, "fact_key"))}: {displayValue(input, scale)}</span>{sourceHref(input) ? <a href={sourceHref(input)} target="_blank" rel="noreferrer">FY{num(input, "fiscal_year")} · p.{text(input, "page_number", "?")} <ExternalLink size={11} /></a> : <span>citation missing</span>}</li>)}</ul> : null}
    </div>
  </details>;
}

function MetricCell({ metric, scale = 1, suffix = "" }: { metric: LiveRow; scale?: number; suffix?: string }) {
  const unavailable = metric.value === null || metric.value === undefined;
  return <td className={unavailable ? "ltw-fq-missing" : ""} title={text(metric, "formula", "Historical fact; open the fact ledger for source lineage.")}>
    <strong>{displayValue(metric, scale, suffix)}</strong>
    <small>{text(metric, "kind", "missing").replace(/_/g, " ")}</small>
  </td>;
}

function TrendChart({ series, scale }: { series: LiveRow[]; scale: number }) {
  const chartRows = series.slice(-8);
  const values = chartRows.flatMap((row) => [
    num(metricAt(row, "metrics", "revenue_from_operations"), "value", NaN),
    num(metricAt(row, "metrics", "profit_after_tax"), "value", NaN),
  ]).filter(Number.isFinite);
  if (!values.length) return <div className="ltw-fq-empty"><LineChart size={18} />No comparable annual trend is available.</div>;
  const max = Math.max(...values, 1);
  const points = (key: string) => chartRows.map((row, index) => {
    const value = num(metricAt(row, "metrics", key), "value", NaN);
    const x = chartRows.length === 1 ? 50 : 8 + index * (84 / (chartRows.length - 1));
    if (!Number.isFinite(value)) return null;
    const y = 88 - (value / max) * 70;
    return x + "," + y;
  }).filter(Boolean).join(" ");
  return <figure className="ltw-fq-chart">
    <figcaption><strong>Annual revenue and PAT trajectory</strong><span>Historical, as reported · hover/table for exact values</span></figcaption>
    <svg aria-label="Annual revenue and PAT trend" role="img" viewBox="0 0 100 100" preserveAspectRatio="none">
      {[20, 40, 60, 80].map((y) => <line key={y} x1="7" x2="94" y1={y} y2={y} />)}
      <polyline className="revenue" points={points("revenue_from_operations")} />
      <polyline className="pat" points={points("profit_after_tax")} />
    </svg>
    <div className="ltw-fq-chart__axis">{chartRows.map((row) => <span key={num(row, "fiscal_year")}>FY{num(row, "fiscal_year")}</span>)}</div>
    <div className="ltw-fq-chart__legend"><span className="revenue">Revenue</span><span className="pat">PAT</span><span>Display scale ÷ {scale}</span></div>
  </figure>;
}

function CashConversionChart({ series }: { series: LiveRow[] }) {
  const chartRows = series.slice(-8);
  const values = chartRows.flatMap((row) => [
    num(metricAt(row, "metrics", "operating_cash_flow"), "value", NaN),
    num(metricAt(row, "derived", "fcf"), "value", NaN),
  ]).filter(Number.isFinite);
  if (!values.length) return <div className="ltw-fq-empty"><LineChart size={18} />Cash conversion trend is not computable.</div>;
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 1);
  const span = Math.max(max - min, 1);
  const points = (group: "metrics" | "derived", key: string) => chartRows.map((row, index) => {
    const value = num(metricAt(row, group, key), "value", NaN);
    const x = chartRows.length === 1 ? 50 : 8 + index * (84 / (chartRows.length - 1));
    if (!Number.isFinite(value)) return null;
    const y = 88 - ((value - min) / span) * 70;
    return x + "," + y;
  }).filter(Boolean).join(" ");
  return <figure className="ltw-fq-chart">
    <figcaption><strong>Cash conversion and reinvestment</strong><span>Historical CFO and derived FCF · missing inputs stay unavailable</span></figcaption>
    <svg aria-label="Annual operating cash flow and free cash flow trend" role="img" viewBox="0 0 100 100" preserveAspectRatio="none">
      {[20, 40, 60, 80].map((y) => <line key={y} x1="7" x2="94" y1={y} y2={y} />)}
      <polyline className="cash" points={points("metrics", "operating_cash_flow")} />
      <polyline className="fcf" points={points("derived", "fcf")} />
    </svg>
    <div className="ltw-fq-chart__axis">{chartRows.map((row) => <span key={num(row, "fiscal_year")}>FY{num(row, "fiscal_year")}</span>)}</div>
    <div className="ltw-fq-chart__legend"><span className="cash">CFO</span><span className="fcf">FCF</span></div>
  </figure>;
}

export function FinancialQualityWorkspace({ quality, facts, page, total, onPage }: {
  quality: LiveRow;
  facts: LiveRow[];
  page: number;
  total: number;
  onPage: (page: number) => void;
}) {
  const groups = list(quality.basis_groups);
  const [basisKey, setBasisKey] = React.useState("");
  const [unitMode, setUnitMode] = React.useState<"crore" | "lakh">("crore");
  const [year, setYear] = React.useState("all");
  const [windowSize, setWindowSize] = React.useState("5");
  const [ledgerOpen, setLedgerOpen] = React.useState(false);
  const group = groups.find((row) => text(row, "basis_key") === basisKey) || groups[0] || {};
  React.useEffect(() => { if (!basisKey && groups[0]) setBasisKey(text(groups[0], "basis_key")); }, [basisKey, groups]);
  const fullSeries = list(group.series);
  const windowedSeries = windowSize === "all" ? fullSeries : fullSeries.slice(-Number(windowSize));
  const series = year === "all" ? windowedSeries : fullSeries.filter((row) => String(num(row, "fiscal_year")) === year);
  const latest = fullSeries[fullSeries.length - 1] || {};
  const scale = text(group, "unit") === "lakh" && unitMode === "crore" ? 100 : 1;
  const unitLabel = text(group, "currency") === "INR" ? `₹ ${unitMode}` : `${text(group, "currency")} ${text(group, "unit")}`;
  const latestDerived = object(latest.derived);
  const cagr = object(group.cagr);

  if (!groups.length) return <div className="ltw-fq-empty"><AlertTriangle size={18} /><div><strong>Financial Quality unavailable</strong><p>No consistent annual fact basis exists. Ratios and trends are not inferred.</p></div></div>;
  return <div className="ltw-financial-quality">
    <div className="ltw-basis-ribbon" aria-label="Financial statement basis controls">
      <label><span>Basis</span><select value={basisKey} onChange={(event) => setBasisKey(event.target.value)}>{groups.map((row) => <option key={text(row, "basis_key")} value={text(row, "basis_key")}>{text(row, "basis_label")}</option>)}</select></label>
      <label><span>Fiscal year</span><select value={year} onChange={(event) => setYear(event.target.value)}><option value="all">Trend view</option>{fullSeries.slice().reverse().map((row) => <option key={num(row, "fiscal_year")} value={String(num(row, "fiscal_year"))}>FY{num(row, "fiscal_year")}</option>)}</select></label>
      <label><span>History</span><select value={windowSize} onChange={(event) => setWindowSize(event.target.value)}><option value="5">5 years</option><option value="10">10 years</option><option value="all">All {fullSeries.length} years</option></select></label>
      <label><span>Units</span><select value={unitMode} onChange={(event) => setUnitMode(event.target.value as "crore" | "lakh")} disabled={text(group, "currency") !== "INR" || text(group, "unit") !== "lakh"}><option value="crore">₹ crore</option><option value="lakh">₹ lakh</option></select></label>
      <div><span>Scope</span><strong>{text(group, "statement_scope", "Not recorded")}</strong></div>
      <div><span>Period end</span><strong>{text(latest, "period_end", `FY${num(latest, "fiscal_year")}`)}</strong></div>
      <div><span>Source date</span><strong>{text(group, "latest_source_as_of_date", "Not recorded")}</strong></div>
      <div><span>Verification</span><Badge tone={text(group, "verification_status") === "Human-reviewed" ? "ok" : "warn"}>{text(group, "verification_status", "Missing")}</Badge></div>
    </div>

    <div className="ltw-fq-readiness"><div><span>Evidence coverage</span><strong>{fullSeries.length} comparable annual periods · quarterly series unavailable</strong></div><div><span>Evidence quality</span><strong>{text(group, "verification_status")}</strong></div><div><span>Decision readiness</span><strong>Human review required</strong></div></div>
    <div className="ltw-fq-story"><span>What changed—and why it matters</span>{text(group, "verification_status") === "Human-reviewed" || text(group, "verification_status") === "Validated" ? <p>FY{num(latest, "fiscal_year")} revenue is {displayValue(metricAt(latest, "metrics", "revenue_from_operations"), scale)} {unitLabel}; PAT is {displayValue(metricAt(latest, "metrics", "profit_after_tax"), scale)} and CFO/PAT is {displayValue(object(latestDerived.cfo_pat_conversion_pct), 1, "%")}. Open each calculation below for source components.</p> : <p>A financial interpretation is withheld because the latest series is {text(group, "verification_status").toLowerCase()}. The exact FY{num(latest, "fiscal_year")} reported lines remain visible below for verification; no unreviewed driver narrative is presented as fact.</p>}</div>
    <div className="ltw-fq-chart-grid"><TrendChart series={windowedSeries} scale={scale} /><CashConversionChart series={windowedSeries} /></div>

    <div className="ltw-fq-driver-grid">
      <article><span>Revenue CAGR</span><strong>{displayValue(object(cagr.revenue_from_operations), 1, "%")}</strong><small>{text(object(cagr.revenue_from_operations), "formula")}</small></article>
      <article><span>PAT CAGR</span><strong>{displayValue(object(cagr.profit_after_tax), 1, "%")}</strong><small>{text(object(cagr.profit_after_tax), "formula")}</small></article>
      <article><span>CFO / PAT</span><strong>{displayValue(object(latestDerived.cfo_pat_conversion_pct), 1, "%")}</strong><small>{text(object(latestDerived.cfo_pat_conversion_pct), "formula")}</small></article>
      <article><span>Net debt / (cash)</span><strong>{displayValue(object(latestDerived.net_debt), scale)}</strong><small>{unitLabel} · {text(object(latestDerived.net_debt), "formula")}</small></article>
    </div>

    <section className="ltw-capital-efficiency" aria-labelledby="capital-efficiency-heading">
      <header><div><span>Transparent return architecture</span><h3 id="capital-efficiency-heading">Capital efficiency</h3><p>ROCE and ROIC are decomposed into operating return and capital intensity. Every value opens to its formula, components and source pages; missing inputs stay missing.</p></div><Badge tone="warn">Average-capital basis</Badge></header>
      <div className="ltw-return-bridge"><div><strong>ROCE bridge</strong><p>EBIT margin × capital turnover = ROCE</p></div><CalculationCard title="EBIT margin" metric={object(latestDerived.ebit_margin_pct)} suffix="%" /><span>×</span><CalculationCard title="Capital turnover" metric={object(latestDerived.capital_turnover)} suffix="×" /><span>=</span><CalculationCard title="ROCE" metric={object(latestDerived.roce_pct)} suffix="%" /></div>
      <div className="ltw-return-bridge"><div><strong>ROIC bridge</strong><p>NOPAT ÷ average invested capital = ROIC</p></div><CalculationCard title="NOPAT" metric={object(latestDerived.nopat)} scale={scale} /><span>÷</span><CalculationCard title="Average invested capital" metric={object(latestDerived.average_invested_capital)} scale={scale} /><span>=</span><CalculationCard title="ROIC" metric={object(latestDerived.roic_pct)} suffix="%" /></div>
      <div className="ltw-return-bridge"><div><strong>ROE bridge</strong><p>PAT margin × asset turns × financial leverage = ROE</p></div><CalculationCard title="PAT margin" metric={object(latestDerived.pat_margin_pct)} suffix="%" /><span>×</span><CalculationCard title="Asset turns" metric={object(latestDerived.asset_turnover)} suffix="×" /><span>×</span><CalculationCard title="Financial leverage" metric={object(latestDerived.financial_leverage)} suffix="×" /><span>=</span><CalculationCard title="ROE" metric={object(latestDerived.roe_pct)} suffix="%" /></div>
      <div className="ltw-capital-grid">
        <CalculationCard title="Closing invested capital" metric={object(latestDerived.closing_invested_capital)} scale={scale} note="Financing approach: equity + interest-bearing debt − cash. Operating-component reconciliation remains unavailable until payables, PP&E, intangibles and other operating balances are captured." />
        <CalculationCard title="Net operating working capital" metric={object(latestDerived.net_operating_working_capital)} scale={scale} />
        <CalculationCard title="Capex / revenue" metric={object(latestDerived.capex_reinvestment_pct)} suffix="%" note="Maintenance versus growth capex is not classified: the captured disclosure does not separate it." />
        <CalculationCard title="Capex / depreciation" metric={object(latestDerived.capex_depreciation)} suffix="×" />
        <CalculationCard title="Reinvestment rate" metric={object(latestDerived.reinvestment_rate)} suffix="%" />
        <CalculationCard title="DSO" metric={object(latestDerived.dso_days)} suffix=" days" />
        <CalculationCard title="DIO" metric={object(latestDerived.dio_days)} suffix=" days" />
        <CalculationCard title="DPO" metric={object(latestDerived.dpo_days)} suffix=" days" />
      </div>
      <div className="ltw-incremental-returns"><strong>Incremental return windows</strong>{list(group.incremental_returns).map((metric) => <CalculationCard key={num(metric, "window_years")} title={`${num(metric, "window_years")}y incremental ROCE`} metric={metric} suffix="%" />)}</div>
      <div className="ltw-wacc-gate"><AlertTriangle size={16} /><p><strong>Value-creation spread withheld.</strong> No user-reviewed WACC or hurdle is attached to this company. The workspace will not imply ROIC − WACC until both sides are reproducible on compatible bases.</p></div>
    </section>

    <div className="ltw-table-wrap ltw-fq-table"><table><thead><tr><th>Period</th><th>Revenue</th><th>EBITDA</th><th>EBIT</th><th>PAT</th><th>PAT margin</th><th>CFO</th><th>FCF</th><th>ROCE</th><th>ROE</th><th>Net debt</th></tr></thead><tbody>{series.map((row) => <tr key={num(row, "fiscal_year")}><th>FY{num(row, "fiscal_year")}<small>{unitLabel}</small></th><MetricCell metric={metricAt(row, "metrics", "revenue_from_operations")} scale={scale} /><MetricCell metric={metricAt(row, "metrics", "ebitda")} scale={scale} /><MetricCell metric={metricAt(row, "metrics", "earnings_before_interest_and_tax")} scale={scale} /><MetricCell metric={metricAt(row, "metrics", "profit_after_tax")} scale={scale} /><MetricCell metric={metricAt(row, "derived", "pat_margin_pct")} suffix="%" /><MetricCell metric={metricAt(row, "metrics", "operating_cash_flow")} scale={scale} /><MetricCell metric={metricAt(row, "derived", "fcf")} scale={scale} /><MetricCell metric={metricAt(row, "derived", "roce_pct")} suffix="%" /><MetricCell metric={metricAt(row, "derived", "roe_pct")} suffix="%" /><MetricCell metric={metricAt(row, "derived", "net_debt")} scale={scale} /></tr>)}</tbody></table></div>

    <div className="ltw-fq-quality-flags"><article><strong>Working-capital days</strong><p>{text(object(latestDerived.working_capital_days), "status", "Not computable")} · {text(object(latestDerived.working_capital_days), "formula")}</p></article><article><strong>Capex reinvestment</strong><p>{displayValue(object(latestDerived.capex_reinvestment_pct), 1, "%")} · {text(object(latestDerived.capex_reinvestment_pct), "formula")}</p></article><article><strong>Dividend payout</strong><p>{displayValue(object(latestDerived.dividend_payout_pct), 1, "%")} · {text(object(latestDerived.dividend_payout_pct), "formula")}</p></article><article><strong>Buyback</strong><p>{text(object(latestDerived.buyback), "status", "Not available")}</p></article></div>

    <div className="ltw-ledger-toggle"><div><strong>Normalized fact ledger</strong><p>Audit drill-through only: reported line, page, source date, extraction and restatement state.</p></div><Button onClick={() => setLedgerOpen((value) => !value)} size="sm" variant="ghost">{ledgerOpen ? "Hide ledger" : `Open ${total}-fact ledger`}</Button></div>
    {ledgerOpen ? <><div className="ltw-table-wrap"><table><thead><tr><th>FY</th><th>Reported fact</th><th>Value</th><th>Basis</th><th>Status</th><th>Exact citation</th></tr></thead><tbody>{facts.map((row, index) => { const locator = object(row.source_locator); return <tr key={`${text(row, "fact_key")}-${num(row, "fiscal_year")}-${index}`}><td>FY{num(row, "fiscal_year")}</td><td><strong>{text(row, "canonical_name")}</strong><small>{text(row, "fact_key")}</small></td><td>{row.value_numeric === null || row.value_numeric === undefined ? text(row, "value_text") : Number(row.value_numeric).toLocaleString("en-IN")} {text(row, "unit")}</td><td>{text(row, "statement_scope")} · {text(row, "fiscal_period")}</td><td>{text(row, "verification_status").toLowerCase().includes("human") ? "Human-reviewed" : text(row, "verification_status").toLowerCase().includes("valid") ? "Validated" : text(row, "verification_status").toLowerCase().includes("machine") ? "Machine-extracted" : "Source captured"}</td><td>{text(row, "source_url") ? <a href={text(row, "source_url")} target="_blank" rel="noreferrer">Page {text(locator, "page_number", "not recorded")} <ExternalLink size={12} /></a> : "Locator missing"}</td></tr>; })}</tbody></table></div><div className="ltw-pager"><Button disabled={page <= 1} onClick={() => onPage(page - 1)} size="sm" variant="ghost">Previous</Button><span>Page {page} of {Math.max(1, Math.ceil(total / 12))}</span><Button disabled={page >= Math.ceil(total / 12)} onClick={() => onPage(page + 1)} size="sm" variant="ghost">Next</Button></div></> : null}
  </div>;
}
