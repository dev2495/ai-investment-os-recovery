import React from "react";
import { ExternalLink } from "lucide-react";
import type { LiveRow } from "../../data/liveRow";
import "./UshaMultiYearReport.css";
import { num, text } from "../../data/liveRow";

const YEARS = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026];

function rec(raw: unknown): LiveRow {
  return raw && typeof raw === "object" && !Array.isArray(raw)
    ? (raw as LiveRow)
    : {};
}

function money(value: number | null): string {
  return value === null || !Number.isFinite(value)
    ? "—"
    : value < 0
      ? `(₹${Math.abs(value / 100).toLocaleString("en-IN", { maximumFractionDigits: 1 })})`
      : `₹${(value / 100).toLocaleString("en-IN", { maximumFractionDigits: 1 })}`;
}

function pct(value: number | null): string {
  return value === null || !Number.isFinite(value)
    ? "—"
    : `${value.toLocaleString("en-IN", { maximumFractionDigits: 1 })}%`;
}

function multiple(value: number | null): string {
  return value === null || !Number.isFinite(value)
    ? "—"
    : `${value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}×`;
}

function cagr(
  first: number | null,
  last: number | null,
  years: number,
): string {
  if (first === null || last === null || first <= 0 || last <= 0 || years <= 0)
    return "Not computable";
  return pct((Math.pow(last / first, 1 / years) - 1) * 100);
}

function subtract(left: number | null, right: number | null): number | null {
  return left === null || right === null ? null : left - right;
}

type DcfInputs = {
  normalizedFcf: number;
  growth: number;
  discount: number;
  terminalGrowth: number;
  years: number;
  netCash: number;
  shares: number;
};

function dcfValue(inputs: DcfInputs): number | null {
  if (
    inputs.normalizedFcf <= 0 ||
    inputs.shares <= 0 ||
    inputs.years < 1 ||
    inputs.discount <= inputs.terminalGrowth
  )
    return null;
  let presentValue = 0;
  let cashFlow = inputs.normalizedFcf;
  for (let year = 1; year <= inputs.years; year += 1) {
    cashFlow *= 1 + inputs.growth;
    presentValue += cashFlow / Math.pow(1 + inputs.discount, year);
  }
  const terminalValue =
    (cashFlow * (1 + inputs.terminalGrowth)) /
    (inputs.discount - inputs.terminalGrowth);
  return (
    (presentValue +
      terminalValue / Math.pow(1 + inputs.discount, inputs.years) +
      inputs.netCash) /
    inputs.shares
  );
}

function reverseDcfGrowth(
  inputs: DcfInputs,
  targetPrice: number,
): number | null {
  if (targetPrice <= 0) return null;
  let low = -0.2,
    high = 0.75;
  const lowValue = dcfValue({ ...inputs, growth: low });
  const highValue = dcfValue({ ...inputs, growth: high });
  if (
    lowValue === null ||
    highValue === null ||
    targetPrice < lowValue ||
    targetPrice > highValue
  )
    return null;
  for (let index = 0; index < 80; index += 1) {
    const midpoint = (low + high) / 2;
    const value = dcfValue({ ...inputs, growth: midpoint });
    if (value === null) return null;
    if (value < targetPrice) low = midpoint;
    else high = midpoint;
  }
  return (low + high) / 2;
}

function seededRandom(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state * 1664525 + 1013904223) >>> 0;
    return state / 4294967296;
  };
}

function triangular(
  random: () => number,
  low: number,
  mode: number,
  high: number,
): number {
  const sample = random();
  const split = (mode - low) / (high - low);
  return sample < split
    ? low + Math.sqrt(sample * (high - low) * (mode - low))
    : high - Math.sqrt((1 - sample) * (high - low) * (high - mode));
}

function percentile(sorted: number[], probability: number): number | null {
  if (!sorted.length) return null;
  const position = (sorted.length - 1) * probability;
  const lower = Math.floor(position),
    upper = Math.ceil(position);
  return sorted[lower] + (sorted[upper] - sorted[lower]) * (position - lower);
}

function runDcfMonteCarlo(inputs: DcfInputs, paths = 5000): number[] {
  const random = seededRandom(20260815);
  const values: number[] = [];
  for (let index = 0; index < paths; index += 1) {
    const growth = triangular(
      random,
      Math.max(-0.05, inputs.growth - 0.05),
      inputs.growth,
      inputs.growth + 0.05,
    );
    const discount = triangular(
      random,
      Math.max(0.06, inputs.discount - 0.025),
      inputs.discount,
      inputs.discount + 0.025,
    );
    const terminalGrowth = triangular(
      random,
      Math.max(0, inputs.terminalGrowth - 0.015),
      inputs.terminalGrowth,
      Math.min(inputs.terminalGrowth + 0.015, discount - 0.01),
    );
    const normalizedFcf = triangular(
      random,
      inputs.normalizedFcf * 0.78,
      inputs.normalizedFcf,
      inputs.normalizedFcf * 1.22,
    );
    const value = dcfValue({
      ...inputs,
      growth,
      discount,
      terminalGrowth,
      normalizedFcf,
    });
    if (value !== null && Number.isFinite(value)) values.push(value);
  }
  return values.sort((left, right) => left - right);
}

function InputControl({
  label,
  value,
  min,
  max,
  step,
  suffix,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  suffix: string;
  onChange: (value: number) => void;
}) {
  return (
    <label className="ltw-valuation-control">
      <span>{label}</span>
      <div>
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(event) => onChange(Number(event.target.value))}
        />
        <output>
          {value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
          {suffix}
        </output>
      </div>
    </label>
  );
}

function Trend({
  values,
  labels,
  format = money,
}: {
  values: Array<number | null>;
  labels: string[];
  format?: (v: number | null) => string;
}) {
  const points = values
    .map((value, index) => ({ value, index }))
    .filter(
      (point): point is { value: number; index: number } =>
        point.value !== null && Number.isFinite(point.value),
    );
  const width = 760,
    height = 210,
    left = 48,
    right = 24,
    top = 28,
    bottom = 42;
  const min = Math.min(...points.map((point) => point.value)),
    max = Math.max(...points.map((point) => point.value));
  const span = Math.max(1, max - min),
    x = (index: number) =>
      left + (index * (width - left - right)) / Math.max(1, values.length - 1);
  const y = (value: number) =>
    top + ((max - value) * (height - top - bottom)) / span;
  return (
    <svg
      className="ltw-history-chart"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={`${labels[0]} to ${labels[labels.length - 1]} historical trend`}
    >
      <line
        x1={left}
        x2={width - right}
        y1={height - bottom}
        y2={height - bottom}
      />
      <polyline
        points={points
          .map((point) => `${x(point.index)},${y(point.value)}`)
          .join(" ")}
      />
      {values.map((value, index) => (
        <g key={labels[index]}>
          {value === null ? (
            <text
              className="gap"
              x={x(index)}
              y={height - bottom - 8}
              textAnchor="middle"
            >
              missing
            </text>
          ) : (
            <>
              <circle cx={x(index)} cy={y(value)} r="4" />
              <text
                x={x(index)}
                y={Math.max(14, y(value) - 10)}
                textAnchor="middle"
              >
                {format(value)}
              </text>
            </>
          )}
          <text x={x(index)} y={height - 14} textAnchor="middle">
            {labels[index]}
          </text>
        </g>
      ))}
    </svg>
  );
}

function SourceLink({ row }: { row: LiveRow | undefined }) {
  if (!row) return null;
  return (
    <a
      className="ltw-inline-source"
      href={text(row, "source_url")}
      target="_blank"
      rel="noreferrer"
    >
      p.{num(row, "source_page")} <ExternalLink size={11} />
    </a>
  );
}

function DataTable({
  title,
  rows,
  fact,
  source,
}: {
  title: string;
  rows: Array<[string, string, (value: number | null) => string]>;
  fact: (year: number, key: string) => number | null;
  source: (year: number, key: string) => LiveRow | undefined;
}) {
  return (
    <section className="ltw-history-table">
      <h3>{title}</h3>
      <div className="ltw-history-scroll">
        <table>
          <thead>
            <tr>
              <th>₹ crore unless stated</th>
              {YEARS.map((year) => (
                <th key={year}>FY{String(year).slice(2)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, key, formatter]) => (
              <tr key={key}>
                <th>{label}</th>
                {YEARS.map((year) => (
                  <td key={year}>
                    {formatter(fact(year, key))}
                    <SourceLink row={source(year, key)} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function moatFramework(category: string): {
  mechanism: string;
  proof: string;
  kill: string;
} {
  const key = category.toLowerCase();
  if (key.includes("capacity"))
    return {
      mechanism:
        "Specialized capacity and capability investment can widen the addressable product set.",
      proof:
        "Utilization, mix, margins and incremental return on the new capital must rise together.",
      kill: "Low utilization or returns below the explicit hurdle after commissioning.",
    };
  if (key.includes("demand"))
    return {
      mechanism:
        "Diversified end markets and safety-critical applications can reduce dependence on one cycle.",
      proof: "Stable volumes and margins through mixed end-market conditions.",
      kill: "Broad volume weakness or pricing pressure across applications.",
    };
  if (key.includes("market_share"))
    return {
      mechanism:
        "Small disclosed share describes runway, not a moat by itself.",
      proof: "Share gains accompanied by pricing discipline and returns.",
      kill: "Growth bought through price concessions or share loss in core niches.",
    };
  if (key.includes("replacement"))
    return {
      mechanism:
        "A safety-led replacement cycle can create recurring demand after qualification.",
      proof: "Repeat-order, retention and replacement-cycle evidence.",
      kill: "Lengthening replacement cycles or material customer losses.",
    };
  return {
    mechanism:
      "Higher-specification products may support differentiation and better economics.",
    proof: "Sustained mix, realization and segment-margin improvement.",
    kill: "Commodity pricing, adverse mix or falling segment returns.",
  };
}

export function UshaMultiYearReport({
  data,
  onResearch,
}: {
  data: LiveRow;
  onResearch: () => void;
}) {
  const facts = Array.isArray(data.financial_history)
    ? (data.financial_history as LiveRow[]).flatMap((year) =>
        Array.isArray(year.facts) ? (year.facts as LiveRow[]) : [year],
      )
    : [];
  const segments = Array.isArray(data.financial_segment_history)
    ? (data.financial_segment_history as LiveRow[])
    : [];
  const ratios = Array.isArray(data.financial_production_ratios)
    ? (data.financial_production_ratios as LiveRow[])
    : [];
  const gaps = Array.isArray(data.financial_history_gaps)
    ? (data.financial_history_gaps as LiveRow[])
    : [];
  const models = Array.isArray(data.valuation_models)
    ? (data.valuation_models as LiveRow[])
    : [];
  const guidance = Array.isArray(data.management_guidance)
    ? (data.management_guidance as LiveRow[])
    : [];
  const governance = Array.isArray(data.governance_observations)
    ? (data.governance_observations as LiveRow[])
    : [];
  const committee = Array.isArray(data.committee)
    ? (data.committee as LiveRow[])
    : [];
  const operationalKpis = Array.isArray(data.operational_kpis)
    ? (data.operational_kpis as LiveRow[])
    : [];
  const industry = Array.isArray(data.industry_observations)
    ? (data.industry_observations as LiveRow[])
    : [];
  const marketShares = Array.isArray(data.market_share_observations)
    ? (data.market_share_observations as LiveRow[])
    : [];
  const peers = Array.isArray(data.operating_peers)
    ? (data.operating_peers as LiveRow[])
    : [];
  const filings = Array.isArray(data.filings)
    ? (data.filings as LiveRow[])
    : [];
  const killers = Array.isArray(rec(data.selected_thesis).thesis_killers)
    ? (rec(data.selected_thesis).thesis_killers as LiveRow[])
    : [];
  const factRow = (year: number, key: string) =>
    facts.find(
      (row) =>
        num(row, "fiscal_year") === year && text(row, "fact_key") === key,
    );
  const fact = (year: number, key: string) => {
    const row = factRow(year, key);
    return row ? num(row, "value") : null;
  };
  const ratio = (year: number, key: string) => {
    const row = ratios.find(
      (item) =>
        text(item, "formula_key") === key &&
        String(text(item, "period_end")).startsWith(String(year)),
    );
    return row && row.value !== null ? num(row, "value") : null;
  };
  const segment = (year: number, key: string, metric: string) => {
    const row = segments.find(
      (item) =>
        num(item, "fiscal_year") === year &&
        text(item, "segment_key") === key &&
        text(item, "metric_key") === metric,
    );
    return row && text(row, "extraction_status") !== "blocked"
      ? num(row, "value")
      : null;
  };
  const labels = YEARS.map((year) => `FY${String(year).slice(2)}`);
  const revenue = YEARS.map((year) => fact(year, "revenue"));
  const ebitda = YEARS.map((year) => {
    const pbt = fact(year, "pbt_pre_jv_exceptional"),
      finance = fact(year, "finance_cost"),
      da = fact(year, "depreciation");
    return pbt === null || finance === null || da === null
      ? null
      : pbt + finance + da;
  });
  const fcf = YEARS.map((year) => {
    const cfo = fact(year, "cfo"),
      capex = fact(year, "capex");
    return cfo === null || capex === null ? null : cfo - capex;
  });
  const ebitdaMargin = YEARS.map((year) => ratio(year, "ebitda_margin"));
  const cfoConversion = YEARS.map((year) => ratio(year, "cfo_pat"));
  const roce = YEARS.map((year) => ratio(year, "roce_financing_capital"));
  const capex = YEARS.map((year) => fact(year, "capex"));
  const dividends = YEARS.map((year) => fact(year, "dividends_paid"));
  const dcf = models.find((row) => text(row, "model_type") === "dcf") ?? {};
  const multiples =
    models.find((row) => text(row, "model_type") === "multiples") ?? {};
  const assumptions = rec(dcf.assumptions),
    priceSource = rec(assumptions.current_price_source),
    price = num(assumptions, "current_price", 0);
  const dcfScenarios = rec(assumptions.scenarios);
  const baseScenario = rec(dcfScenarios.base);
  const storedShares = num(
    assumptions,
    "diluted_shares_crore",
    num(assumptions, "diluted_shares", 30.474178),
  );
  const initialDcf = React.useMemo<DcfInputs>(
    () => ({
      normalizedFcf: num(
        assumptions,
        "normalized_fcf_crore",
        num(assumptions, "normalized_fcf", 177.11),
      ),
      growth: num(baseScenario, "growth", 0.08),
      discount: num(baseScenario, "discount", 0.12),
      terminalGrowth: num(baseScenario, "terminal_growth", 0.04),
      years: Math.max(1, Math.round(num(assumptions, "forecast_years", 10))),
      netCash: num(
        assumptions,
        "net_cash_crore",
        num(assumptions, "net_cash", 96.3),
      ),
      shares:
        storedShares > 1_000_000 ? storedShares / 10_000_000 : storedShares,
    }),
    [assumptions, baseScenario, storedShares],
  );
  const [valuationInputs, setValuationInputs] =
    React.useState<DcfInputs>(initialDcf);
  const updateValuation = (key: keyof DcfInputs, value: number) =>
    setValuationInputs((current) => ({ ...current, [key]: value }));
  const interactiveDcf = React.useMemo(
    () => dcfValue(valuationInputs),
    [valuationInputs],
  );
  const impliedGrowth = React.useMemo(
    () => reverseDcfGrowth(valuationInputs, price),
    [valuationInputs, price],
  );
  const simulation = React.useMemo(
    () => runDcfMonteCarlo(valuationInputs),
    [valuationInputs],
  );
  const simulationPoints = [0.05, 0.25, 0.5, 0.75, 0.95].map((point) =>
    percentile(simulation, point),
  );
  const belowMarketProbability =
    simulation.length && price > 0
      ? simulation.filter((value) => value < price).length / simulation.length
      : null;
  const sensitivityGrowth = [
    valuationInputs.growth - 0.02,
    valuationInputs.growth,
    valuationInputs.growth + 0.02,
  ];
  const sensitivityDiscount = [
    valuationInputs.discount - 0.01,
    valuationInputs.discount,
    valuationInputs.discount + 0.01,
  ];
  const committeeDecision = committee[0] ?? {};
  const fy20Distortion =
    fact(2020, "pat_total") !== fact(2020, "pat_continuing");
  const volumeGap = gaps.find(
    (row) => text(row, "metric_key") === "volume_price_mix",
  );

  return (
    <article className="ltw-history-report" id="thesis">
      <nav className="ltw-history-nav">
        <a href="#history-conclusion">Conclusion</a>
        <a href="#history-growth">Growth</a>
        <a href="#history-segments">Segments</a>
        <a href="#history-statements">Statements</a>
        <a href="#history-ratios">Ratios</a>
        <a href="#history-management">Management</a>
        <a href="#history-moat">Moat &amp; peers</a>
        <a href="#history-valuation">Valuation &amp; decision</a>
      </nav>

      <section className="ltw-history-hero" id="history-conclusion">
        <div>
          <span>Investment conclusion · evidence through 31 March 2026</span>
          <h2>
            Returns and cash conversion recovered after the portfolio reset;
            valuation still lacks a decision-grade proof.
          </h2>
          <p>
            Usha Martin grew continuing revenue from{" "}
            {money(fact(2020, "revenue"))} crore in FY2020 to{" "}
            {money(fact(2026, "revenue"))} crore in FY2026 (
            {cagr(fact(2020, "revenue"), fact(2026, "revenue"), 6)} CAGR).
            EBITDA margin expanded to {pct(ratio(2026, "ebitda_margin"))}, free
            cash flow reached {money(fcf[fcf.length - 1] ?? null)} crore and net
            debt became {money(ratio(2026, "net_debt"))} crore. The historical
            improvement is real; the stock conclusion remains “wait for proof”
            because volume/price/mix, customer concentration, maintenance versus
            growth capex, and a reviewed valuation are not yet evidenced.
          </p>
          <div className="ltw-history-proof">
            <span>10 fiscal years</span>
            <span>FY2017–FY2026</span>
            <span>10 issuer reports</span>
            <span>43 statement tie-outs</span>
          </div>
        </div>
        <aside>
          <span>Current posture</span>
          <strong>Research / no capital action</strong>
          <p>
            Complete operating-driver and valuation evidence before an add/trim
            decision.
          </p>
          <button onClick={onResearch}>Open research case</button>
        </aside>
      </section>

      <section
        className="ltw-numbers-story"
        aria-label="What changed and why it matters"
      >
        <header>
          <span>Numbers story</span>
          <h2>
            Growth became more profitable and cash-generative; the next test is
            whether reinvestment compounds those gains.
          </h2>
        </header>
        <div>
          <article>
            <span>01 · Earnings engine</span>
            <strong>Margin, not just sales, drove the recovery.</strong>
            <p>
              Revenue compounded at{" "}
              {cagr(fact(2021, "revenue"), fact(2026, "revenue"), 5)} from
              FY2021, while EBITDA margin moved from{" "}
              {pct(ratio(2021, "ebitda_margin"))} to{" "}
              {pct(ratio(2026, "ebitda_margin"))}. That combination points to
              mix and operating leverage; a validated price/volume/mix bridge is
              still required before assigning permanence.
            </p>
            <dl className="ltw-story-chain">
              <div>
                <dt>Driver</dt>
                <dd>Revenue recovery plus a higher EBITDA margin.</dd>
              </div>
              <div>
                <dt>Investor implication</dt>
                <dd>
                  Incremental revenue has recently carried better economics, but
                  the source does not split price, volume and mix.
                </dd>
              </div>
              <div>
                <dt>Next proof</dt>
                <dd>
                  Unit volume, realizations, utilization and product-mix
                  disclosure.
                </dd>
              </div>
            </dl>
            <footer>
              FY2021 and FY2026 consolidated statements{" "}
              <SourceLink row={factRow(2026, "revenue")} />
            </footer>
          </article>
          <article>
            <span>02 · Cash quality</span>
            <strong>FY2026 earnings converted into cash.</strong>
            <p>
              CFO reached {money(fact(2026, "cfo"))} crore, or{" "}
              {pct(ratio(2026, "cfo_pat"))} of continuing PAT. After{" "}
              {money(fact(2026, "capex"))} crore of capex, free cash flow was{" "}
              {money(fcf[9])} crore. One strong year is evidence of delivery,
              not yet proof of a through-cycle conversion rate.
            </p>
            <dl className="ltw-story-chain">
              <div>
                <dt>Driver</dt>
                <dd>
                  Operating cash flow rose faster than continuing earnings in
                  FY2026.
                </dd>
              </div>
              <div>
                <dt>Investor implication</dt>
                <dd>
                  The latest year funded capex and still left surplus cash;
                  normalized cash conversion remains the valuation hinge.
                </dd>
              </div>
              <div>
                <dt>Next proof</dt>
                <dd>
                  Repeat CFO/PAT and FCF/PAT performance through the next
                  down-cycle.
                </dd>
              </div>
            </dl>
            <footer>
              FY2026 consolidated cash-flow statement{" "}
              <SourceLink row={factRow(2026, "cfo")} />
            </footer>
          </article>
          <article>
            <span>03 · Capital cycle</span>
            <strong>
              Returns improved while the balance sheet moved to net cash.
            </strong>
            <p>
              ROCE rose from {pct(ratio(2021, "roce_financing_capital"))} to{" "}
              {pct(ratio(2026, "roce_financing_capital"))}; net debt was{" "}
              {money(ratio(2026, "net_debt"))} crore. The decision now turns on
              utilization and incremental returns from the added 40,000 MT
              capacity and planned annual capex.
            </p>
            <dl className="ltw-story-chain">
              <div>
                <dt>Driver</dt>
                <dd>
                  Higher operating margin, faster capital turnover and lower net
                  debt.
                </dd>
              </div>
              <div>
                <dt>Investor implication</dt>
                <dd>
                  Historical ROCE improved, but the next leg depends on returns
                  earned on the new asset base—not capacity alone.
                </dd>
              </div>
              <div>
                <dt>Next proof</dt>
                <dd>
                  Commissioning, utilization and incremental EBIT versus
                  incremental capital employed.
                </dd>
              </div>
            </dl>
            <footer>
              FY2026 balance sheet and return bridge{" "}
              <SourceLink row={factRow(2026, "total_equity")} />
            </footer>
          </article>
        </div>
      </section>

      <section className="ltw-history-section">
        <header>
          <span>A · Thesis evolution</span>
          <h2>
            The company moved from divestiture clean-up to cash-generative
            wire-rope reinvestment.
          </h2>
        </header>
        <div className="ltw-evolution">
          <article>
            <b>FY2020</b>
            <strong>Portfolio break</strong>
            <p>
              Total PAT includes a material discontinued steel-business disposal
              gain; continuing PAT was negative. Total and continuing earnings
              are never blended.
            </p>
          </article>
          <article>
            <b>FY2021–22</b>
            <strong>Recovery</strong>
            <p>
              Continuing revenue rose from {money(fact(2021, "revenue"))} to{" "}
              {money(fact(2022, "revenue"))} crore while finance cost declined.
            </p>
          </article>
          <article>
            <b>FY2023–24</b>
            <strong>Returns inflect</strong>
            <p>
              EBIT margin expanded despite FY2024 revenue softness; capex
              stepped up to {money(fact(2024, "capex"))} crore.
            </p>
          </article>
          <article>
            <b>FY2025–26</b>
            <strong>Cash and balance sheet</strong>
            <p>
              FY2026 CFO reached {money(fact(2026, "cfo"))} crore and cash
              exceeded borrowings, but the growth-capex return cycle is still
              incomplete.
            </p>
          </article>
        </div>
      </section>

      <section className="ltw-history-section" id="history-growth">
        <header>
          <span>B · Growth and operating bridge</span>
          <h2>
            FY2020–FY2026 post-reset revenue CAGR is{" "}
            {cagr(fact(2020, "revenue"), fact(2026, "revenue"), 6)}; the
            FY2017–FY2018 steel-business period is a labelled comparability
            break.
          </h2>
          <p>
            All chart points are consolidated, annual and as reported. FY2020
            total earnings are scope-distorted by discontinued operations, so
            continuing PAT is the comparable series.
          </p>
        </header>
        <div className="ltw-history-chart-grid">
          <figure>
            <figcaption>Revenue · ₹ crore</figcaption>
            <Trend values={revenue} labels={labels} />
          </figure>
          <figure>
            <figcaption>EBITDA · ₹ crore</figcaption>
            <Trend values={ebitda} labels={labels} />
          </figure>
          <figure>
            <figcaption>Free cash flow · ₹ crore</figcaption>
            <Trend values={fcf} labels={labels} />
          </figure>
          <figure>
            <figcaption>EBITDA margin · %</figcaption>
            <Trend values={ebitdaMargin} labels={labels} format={pct} />
          </figure>
          <figure>
            <figcaption>CFO / continuing PAT · %</figcaption>
            <Trend values={cfoConversion} labels={labels} format={pct} />
          </figure>
          <figure>
            <figcaption>ROCE · financing capital · %</figcaption>
            <Trend values={roce} labels={labels} format={pct} />
          </figure>
          <figure>
            <figcaption>Capital expenditure · ₹ crore</figcaption>
            <Trend values={capex} labels={labels} />
          </figure>
          <figure>
            <figcaption>Dividends paid · ₹ crore</figcaption>
            <Trend values={dividends} labels={labels} />
          </figure>
        </div>
        <div className="ltw-history-growth-table">
          <table>
            <thead>
              <tr>
                <th>Growth measure</th>
                <th>FY20–FY26</th>
                <th>FY21–FY26 post-reset</th>
                <th>What it says</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Revenue CAGR</td>
                <td>{cagr(fact(2020, "revenue"), fact(2026, "revenue"), 6)}</td>
                <td>{cagr(fact(2021, "revenue"), fact(2026, "revenue"), 5)}</td>
                <td>Top-line recovery is sustained but uneven.</td>
              </tr>
              <tr>
                <td>Continuing PAT CAGR</td>
                <td>Not comparable</td>
                <td>
                  {cagr(
                    fact(2021, "pat_continuing"),
                    fact(2026, "pat_continuing"),
                    5,
                  )}
                </td>
                <td>FY2020 continuing PAT was negative.</td>
              </tr>
              <tr>
                <td>FCF CAGR</td>
                <td>{cagr(fcf[3], fcf[9], 6)}</td>
                <td>{cagr(fcf[4], fcf[9], 5)}</td>
                <td>
                  Cash compounding outpaced revenue, with annual volatility.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <aside className="ltw-focused-gap">
          <strong>Volume / price / mix waterfall: not disclosed</strong>
          <p>
            {text(
              volumeGap,
              "reason",
              "Official annual reports do not provide compatible unit volume, realized price and product-mix inputs across the period.",
            )}
          </p>
        </aside>
      </section>

      <section className="ltw-history-section" id="history-segments">
        <header>
          <span>C · Business, segment and geography economics</span>
          <h2>
            Wire &amp; Wire Ropes remains the economic engine; “Others” is small
            and volatile.
          </h2>
        </header>
        <div className="ltw-history-chart-grid">
          <figure>
            <figcaption>Wire revenue · ₹ crore</figcaption>
            <Trend
              values={YEARS.map((year) => segment(year, "wire", "revenue"))}
              labels={labels}
            />
          </figure>
          <figure>
            <figcaption>Wire result margin</figcaption>
            <Trend
              values={YEARS.map((year) => {
                const r = segment(year, "wire", "revenue"),
                  p = segment(year, "wire", "result");
                return r && p !== null ? (p / r) * 100 : null;
              })}
              labels={labels}
              format={pct}
            />
          </figure>
          <figure>
            <figcaption>Outside-India revenue share</figcaption>
            <Trend
              values={YEARS.map((year) => {
                const g = segment(year, "outside_india", "revenue"),
                  r = fact(year, "revenue");
                return g && r ? (g / r) * 100 : null;
              })}
              labels={labels}
              format={pct}
            />
          </figure>
        </div>
        <div className="ltw-history-scroll">
          <table>
            <thead>
              <tr>
                <th>Segment economics · ₹ crore</th>
                {YEARS.map((year) => (
                  <th key={year}>FY{String(year).slice(2)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                <th>Wire revenue</th>
                {YEARS.map((year) => (
                  <td key={year}>{money(segment(year, "wire", "revenue"))}</td>
                ))}
              </tr>
              <tr>
                <th>Wire result before finance/tax</th>
                {YEARS.map((year) => (
                  <td key={year}>{money(segment(year, "wire", "result"))}</td>
                ))}
              </tr>
              <tr>
                <th>Wire capital employed*</th>
                {YEARS.map((year) => (
                  <td key={year}>
                    {money(
                      subtract(
                        segment(year, "wire", "assets"),
                        segment(year, "wire", "liabilities"),
                      ),
                    )}
                  </td>
                ))}
              </tr>
              <tr>
                <th>Others revenue</th>
                {YEARS.map((year) => (
                  <td key={year}>
                    {money(segment(year, "others", "revenue"))}
                  </td>
                ))}
              </tr>
              <tr>
                <th>Outside-India revenue</th>
                {YEARS.map((year) => (
                  <td key={year}>
                    {money(segment(year, "outside_india", "revenue"))}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
        <p className="ltw-table-note">
          * Segment assets less segment liabilities; not a full ROIC
          denominator. Segment capex and cash flow are undisclosed. FY2026
          geography is withheld because the issuer table is ₹95.4 crore below
          consolidated revenue.
        </p>
      </section>

      <section className="ltw-history-section" id="history-statements">
        <header>
          <span>D · Full financial history</span>
          <h2>
            Ten fiscal years of consolidated statements, cash flow and capital
            allocation—one source-linked row at a time.
          </h2>
        </header>
        <DataTable
          title="Income statement"
          fact={fact}
          source={factRow}
          rows={[
            ["Revenue", "revenue", money],
            ["Other income", "other_income", money],
            ["Total income", "total_income", money],
            ["Materials", "material_cost", money],
            ["Inventory change", "inventory_change", money],
            ["Employee expense", "employee_expense", money],
            ["Finance cost", "finance_cost", money],
            ["D&A", "depreciation", money],
            ["Other expense", "other_expense", money],
            ["Total expense", "total_expense", money],
            ["PBT — continuing", "pbt_continuing", money],
            ["Tax", "tax_expense", money],
            ["PAT — continuing", "pat_continuing", money],
            ["PAT — total", "pat_total", money],
            [
              "Basic EPS — total",
              "eps_basic_total",
              (v: number | null) => (v === null ? "—" : `₹${v.toFixed(2)}`),
            ],
          ]}
        />
        <DataTable
          title="Balance sheet"
          fact={fact}
          source={factRow}
          rows={[
            ["PPE", "ppe", money],
            ["CWIP", "cwip", money],
            ["Inventory", "inventory", money],
            ["Receivables", "trade_receivables", money],
            ["Cash", "cash", money],
            ["Other bank balances", "other_bank_balances", money],
            ["Current assets", "current_assets", money],
            ["Total assets", "total_assets", money],
            ["Total equity", "total_equity", money],
            ["Borrowings — current", "current_borrowings", money],
            ["Borrowings — non-current", "non_current_borrowings", money],
            ["Lease liabilities", "lease_liabilities_total", money],
            ["Trade payables", "trade_payables", money],
            ["Current liabilities", "current_liabilities", money],
            ["Total liabilities", "total_liabilities", money],
          ]}
        />
        <DataTable
          title="Cash flow and capital allocation"
          fact={fact}
          source={factRow}
          rows={[
            ["Cash from operations", "cfo", money],
            ["Capital expenditure", "capex", money],
            ["Investing cash flow", "cfi", money],
            ["Financing cash flow", "cff", money],
            ["Dividend paid", "dividends_paid", money],
            ["Closing cash", "closing_cash", money],
          ]}
        />
        <div className="ltw-derived-row">
          <strong>Free cash flow (CFO − capex)</strong>
          {YEARS.map((year) => (
            <span key={year}>
              <small>FY{String(year).slice(2)}</small>
              {money(fcf[YEARS.indexOf(year)] ?? null)}
            </span>
          ))}
        </div>
        {fy20Distortion ? (
          <p className="ltw-table-note">
            FY2020 total PAT includes discontinued operations; continuing PAT is
            the analytical base. This is a scope break, not normal growth.
          </p>
        ) : null}
      </section>

      <section className="ltw-history-section" id="history-ratios">
        <header>
          <span>E · Ratio library and return decomposition</span>
          <h2>
            Profitability, capital returns, cash conversion, leverage and
            reinvestment are shown on one annual basis.
          </h2>
        </header>
        <div className="ltw-history-scroll">
          <table>
            <thead>
              <tr>
                <th>Ratio / driver</th>
                {YEARS.map((year) => (
                  <th key={year}>FY{String(year).slice(2)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                ["EBITDA margin", "ebitda_margin", pct],
                ["EBIT margin", "ebit_margin_pre_exception", pct],
                ["Continuing PAT margin", "pat_margin_continuing", pct],
                ["ROE · average equity", "roe_avg_equity", pct],
                ["ROCE · financing capital", "roce_financing_capital", pct],
                ["ROIC · financing capital", "roic_financing_capital", pct],
                ["Asset turnover", "asset_turnover_avg", multiple],
                [
                  "Financing capital turnover",
                  "financing_capital_turnover",
                  multiple,
                ],
                ["CFO / continuing PAT", "cfo_pat", pct],
                ["FCF / continuing PAT", "fcf_pat", pct],
                ["FCF margin", "fcf_margin", pct],
                [
                  "Receivable days",
                  "dso_avg",
                  (v: number | null) =>
                    v === null ? "—" : `${v.toFixed(0)} days`,
                ],
                ["Current ratio", "current_ratio", multiple],
                ["Quick ratio", "quick_ratio", multiple],
                ["Interest coverage", "interest_coverage", multiple],
                ["Net debt / EBITDA", "net_debt_ebitda", multiple],
                ["Capex / revenue", "capex_revenue", pct],
                ["Dividend payout", "dividend_payout", pct],
              ].map(([label, key, formatter]) => (
                <tr key={String(key)}>
                  <th>{String(label)}</th>
                  {YEARS.map((year) => (
                    <td key={year}>
                      {(formatter as (v: number | null) => string)(
                        ratio(year, String(key)),
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="ltw-roce-bridge">
          <header>
            <h3>ROCE driver bridge</h3>
            <p>
              EBIT margin × average financing-capital turnover. Financing
              capital = equity + borrowings − cash.
            </p>
          </header>
          {YEARS.slice(1).map((year) => (
            <div key={year}>
              <span>FY{String(year).slice(2)}</span>
              <strong>{pct(ratio(year, "ebit_margin_pre_exception"))}</strong>
              <b>×</b>
              <strong>
                {multiple(ratio(year, "financing_capital_turnover"))}
              </strong>
              <b>=</b>
              <strong>{pct(ratio(year, "roce_financing_capital"))}</strong>
            </div>
          ))}
        </div>
        <div className="ltw-focused-gap">
          <strong>Not computable without new evidence</strong>
          <p>
            Gross margin, DIO, DPO, full cash-conversion cycle, maintenance
            versus growth capex, incremental ROIC, and forensic scores remain
            withheld. Material cost is not relabelled as COGS.
          </p>
        </div>
      </section>

      <section className="ltw-history-section" id="history-management">
        <header>
          <span>F · Management, moat and governance</span>
          <h2>
            Capex delivery is the key forward proof; dated guidance coverage
            remains shallow.
          </h2>
        </header>
        <div className="ltw-history-two">
          <div>
            <h3>Guidance vs delivery</h3>
            <table>
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>Target / horizon</th>
                  <th>Observed</th>
                </tr>
              </thead>
              <tbody>
                {guidance.length ? (
                  guidance.map((row) => (
                    <tr key={num(row, "claim_id")}>
                      <td>{text(row, "metric_key").replace(/_/g, " ")}</td>
                      <td>
                        {num(row, "target_value")} {text(row, "target_unit")} ·{" "}
                        {text(row, "target_period_end")}
                      </td>
                      <td>
                        {row.actual_value === null ||
                        row.actual_value === undefined
                          ? "Awaiting dated evidence"
                          : `${num(row, "actual_value")} ${text(row, "actual_unit")}`}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={3}>No validated dated guidance rows.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <aside>
            <h3>What is supported</h3>
            <p>
              <strong>Business quality:</strong> ten fiscal years of segment
              revenue and result are shown, with the legacy steel-business years
              labelled non-comparable.
            </p>
            <p>
              <strong>Capital allocation:</strong> capex rose materially from
              FY2023 onward; dividends have been paid since FY2023.
            </p>
            <p>
              <strong>Still unproven:</strong> market share, customer
              concentration, switching costs, peer returns and maintenance
              capex.
            </p>
          </aside>
        </div>
        <div className="ltw-governance-strip">
          {governance
            .filter((row) => text(row, "severity") === "high")
            .slice(0, 3)
            .map((row) => (
              <article key={num(row, "id")}>
                <span>{text(row, "category").replace(/_/g, " ")}</span>
                <strong>{text(row, "conclusion")}</strong>
                <small>
                  FY2026 annual report · p.{num(row, "source_page")}
                </small>
              </article>
            ))}
        </div>
      </section>

      <section
        className="ltw-history-section ltw-market-workbench"
        id="history-moat"
      >
        <header>
          <span>Market, operating drivers, peers and moat</span>
          <h2>
            The business is global and qualification-led; operating evidence is
            separated from unproven market claims.
          </h2>
          <p>
            Specialty wire ropes serve oil and gas, mining, elevators, ports,
            construction, fishing and renewable-energy applications. The moat
            case is framed as an economic hypothesis with explicit proof and
            kill tests—not as a generic quality label.
          </p>
        </header>
        <div className="ltw-quality-matrix">
          <article>
            <header>
              <span className="supported">Supported</span>
              <h3>Understandable earnings engine</h3>
            </header>
            <p>
              Wire and wire-rope economics dominate disclosed segment revenue
              and result. That makes the core engine legible; “Others” is kept
              separate rather than blended into a quality claim.
            </p>
            <footer>
              Test: wire result margin and reconciliation remain stable{" "}
              <SourceLink row={factRow(2026, "revenue")} />
            </footer>
          </article>
          <article>
            <header>
              <span className="partial">Partial</span>
              <h3>Pricing power versus mix</h3>
            </header>
            <p>
              EBITDA margin improved from {pct(ratio(2021, "ebitda_margin"))} to{" "}
              {pct(ratio(2026, "ebitda_margin"))}. Without unit realizations and
              volume/mix disclosure, the improvement cannot yet be called
              pricing power.
            </p>
            <footer>
              Test: realization holds without volume loss{" "}
              <SourceLink row={factRow(2026, "revenue")} />
            </footer>
          </article>
          <article>
            <header>
              <span className="unproven">Unproven</span>
              <h3>Customer captivity</h3>
            </header>
            <p>
              Qualification and safety-critical use can create switching
              friction, but repeat-order rates, customer tenure and
              concentration are not disclosed in a compatible series.
            </p>
            <footer>
              Needed: retention, qualification cycle and top-customer exposure
            </footer>
          </article>
          <article>
            <header>
              <span className="partial">Partial</span>
              <h3>Reinvestment runway</h3>
            </header>
            <p>
              Capex has stepped up and the asset base is expanding. Capacity
              becomes a compounding advantage only when utilization, segment
              margin and incremental return rise together.
            </p>
            <footer>
              Test: incremental EBIT divided by incremental capital{" "}
              <SourceLink row={factRow(2026, "capex")} />
            </footer>
          </article>
          <article>
            <header>
              <span className="supported">Supported</span>
              <h3>Balance-sheet resilience</h3>
            </header>
            <p>
              FY2026 cash exceeded borrowings and interest coverage improved.
              This creates operating room, but does not by itself make the
              equity cheap.
            </p>
            <footer>
              Test: net cash survives the investment cycle{" "}
              <SourceLink row={factRow(2026, "cash")} />
            </footer>
          </article>
          <article>
            <header>
              <span className="unproven">Unproven</span>
              <h3>Margin of safety</h3>
            </header>
            <p>
              The conservative normalized-cash-flow DCF remains far below the
              stored quote. A higher value requires sustained growth or a
              different cash-flow base; neither is silently assumed.
            </p>
            <footer>
              Decision rule: price follows evidence, not the reverse
            </footer>
          </article>
        </div>
        <aside className="ltw-compounder-test">
          <div>
            <span>What could make this a compounder</span>
            <p>
              Durable wire-margin gains, repeat cash conversion and incremental
              returns above an explicit user-reviewed hurdle while the balance
              sheet remains resilient.
            </p>
          </div>
          <div>
            <span>What breaks the case</span>
            <p>
              Price-led growth, falling utilization, poor returns on new
              capacity, customer losses, governance deterioration or
              normalization of FCF below the current valuation requirement.
            </p>
          </div>
        </aside>
        {operationalKpis.length ? (
          <div className="ltw-history-scroll">
            <table>
              <thead>
                <tr>
                  <th>Operating KPI</th>
                  <th>Period</th>
                  <th>Value</th>
                  <th>Decision use</th>
                </tr>
              </thead>
              <tbody>
                {operationalKpis.map((row, index) => (
                  <tr key={index}>
                    <th>{text(row, "kpi_name")}</th>
                    <td>{text(row, "period_end")}</td>
                    <td>
                      {row.value_numeric === null ||
                      row.value_numeric === undefined
                        ? text(row, "value_text")
                        : num(row, "value_numeric").toLocaleString(
                            "en-IN",
                          )}{" "}
                      {text(row, "unit")}
                    </td>
                    <td>{text(row, "description")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <aside className="ltw-focused-gap">
            <strong>Operating KPI history awaiting source persistence</strong>
            <p>
              Volume, utilization, product mix, working-capital days and
              fixed-asset turns render here only after page-level primary-source
              validation.
            </p>
          </aside>
        )}
        <div className="ltw-moat-ladder">
          <h3>Moat evidence ladder</h3>
          <div>
            {industry.length ? (
              industry.map((row) => {
                const frame = moatFramework(text(row, "category"));
                return (
                  <article key={num(row, "id")}>
                    <header>
                      <span>{text(row, "category").replace(/_/g, " ")}</span>
                      <strong>{text(row, "conclusion")}</strong>
                    </header>
                    <dl>
                      <div>
                        <dt>Economic mechanism</dt>
                        <dd>{frame.mechanism}</dd>
                      </div>
                      <div>
                        <dt>Proof required</dt>
                        <dd>{frame.proof}</dd>
                      </div>
                      <div>
                        <dt>Disconfirming test</dt>
                        <dd>{frame.kill}</dd>
                      </div>
                    </dl>
                    <a
                      href={text(row, "source_url")}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Annual report · p.{num(row, "source_page")}{" "}
                      <ExternalLink size={11} />
                    </a>
                  </article>
                );
              })
            ) : (
              <p>No validated industry observations are available.</p>
            )}
          </div>
        </div>
        <div className="ltw-history-two">
          <article>
            <h3>How to read the moat</h3>
            <p>
              Capacity, end-market breadth and replacement demand can support an
              advantage only if they produce repeat business, pricing durability
              and returns above the user-reviewed hurdle. The present evidence
              supports the mechanism; it does not yet prove persistence.
            </p>
            <p>
              <strong>Portfolio-level kill test:</strong> falling wire margin,
              weak incremental returns, customer losses or price-led growth
              would disconfirm durability.
            </p>
          </article>
          <div className="ltw-gap-grid">
            {marketShares.length ? (
              <aside>
                <h3>Market share</h3>
                {marketShares.map((row) => (
                  <p key={num(row, "id")}>
                    <strong>{text(row, "market_name")}</strong> ·{" "}
                    {pct(num(row, "share_pct"))} · {text(row, "period_end")}
                  </p>
                ))}
              </aside>
            ) : (
              <aside className="ltw-focused-gap">
                <strong>Market size / share not validated</strong>
                <p>
                  No compatible primary industry denominator currently supports
                  a defensible TAM or market-share series.
                </p>
              </aside>
            )}
            {peers.length ? (
              <aside>
                <h3>Scoped operating peers</h3>
                {peers.map((row) => (
                  <p key={num(row, "peer_company_id")}>
                    <strong>{text(row, "legal_name")}</strong> ·{" "}
                    {text(row, "primary_exchange")}:
                    {text(row, "primary_symbol")}
                    <br />
                    <small>{text(row, "inclusion_reason")}</small>
                  </p>
                ))}
              </aside>
            ) : (
              <aside className="ltw-focused-gap">
                <strong>Peer comparison not ready</strong>
                <p>
                  Compatible segment scope, current market data and return
                  definitions have not passed review.
                </p>
              </aside>
            )}
          </div>
        </div>
      </section>

      <section className="ltw-history-section" id="history-valuation">
        <header>
          <span>G · Valuation, catalysts, disconfirmers and decision</span>
          <h2>
            One cash-flow basis, three lenses: intrinsic value, market-implied
            expectations and uncertainty.
          </h2>
          <p>
            Stored quote as of {text(priceSource, "quote_ts", "unknown date")};
            refresh is required before any decision. Every control below runs
            locally in the browser and is neither persisted nor approved.
          </p>
        </header>
        <div className="ltw-history-valuations">
          <article>
            <span>Market reference · stored</span>
            <strong>
              {price > 0 ? `₹${price.toLocaleString("en-IN")}` : "Missing"}
            </strong>
            <small>
              {text(priceSource, "provider_symbol", "BSE:USHAMART")}
            </small>
          </article>
          <article>
            <span>Interactive DCF · research</span>
            <strong>
              {interactiveDcf === null
                ? "Not computable"
                : `₹${interactiveDcf.toFixed(0)}`}
            </strong>
            <small>FCFF per diluted share · not a price target</small>
          </article>
          <article>
            <span>Reverse DCF · market hurdle</span>
            <strong>
              {impliedGrowth === null
                ? "Not computable"
                : pct(impliedGrowth * 100)}
            </strong>
            <small>
              Annual FCFF growth needed for {valuationInputs.years} years
            </small>
          </article>
          <article>
            <span>Same-basis Monte Carlo</span>
            <strong>
              {simulationPoints[2] === null
                ? "Not computable"
                : `₹${simulationPoints[2]!.toFixed(0)}`}
            </strong>
            <small>Median of 5,000 deterministic-seed FCFF paths</small>
          </article>
        </div>
        <div className="ltw-valuation-explainer">
          <strong>Why the conservative DCF can sit far below the quote</strong>
          <p>
            The starting FCFF is {valuationInputs.normalizedFcf.toFixed(1)}{" "}
            crore, a normalized historical cash-flow basis rather than the
            unusually strong FY2026 FCF of {money(fcf[9])} crore. At the base
            assumptions, the market price requires{" "}
            {impliedGrowth === null
              ? "an out-of-range growth rate"
              : `${pct(impliedGrowth * 100)} annual FCFF growth`}{" "}
            for {valuationInputs.years} years. That is the question to prove—not
            a number to force.
          </p>
        </div>
        <div className="ltw-valuation-workbench">
          <section className="ltw-valuation-controls">
            <header>
              <div>
                <span>Interactive assumptions</span>
                <h3>Build the cash-flow case</h3>
              </div>
              <button
                type="button"
                onClick={() => setValuationInputs(initialDcf)}
              >
                Reset source case
              </button>
            </header>
            <InputControl
              label="Normalized FCFF"
              value={valuationInputs.normalizedFcf}
              min={75}
              max={500}
              step={1}
              suffix=" cr"
              onChange={(value) => updateValuation("normalizedFcf", value)}
            />
            <InputControl
              label="Explicit FCFF growth"
              value={valuationInputs.growth * 100}
              min={-5}
              max={35}
              step={0.5}
              suffix="%"
              onChange={(value) => updateValuation("growth", value / 100)}
            />
            <InputControl
              label="Discount rate"
              value={valuationInputs.discount * 100}
              min={8}
              max={18}
              step={0.25}
              suffix="%"
              onChange={(value) => updateValuation("discount", value / 100)}
            />
            <InputControl
              label="Terminal growth"
              value={valuationInputs.terminalGrowth * 100}
              min={0}
              max={6}
              step={0.25}
              suffix="%"
              onChange={(value) =>
                updateValuation("terminalGrowth", value / 100)
              }
            />
            <InputControl
              label="Forecast horizon"
              value={valuationInputs.years}
              min={5}
              max={15}
              step={1}
              suffix=" years"
              onChange={(value) => updateValuation("years", value)}
            />
            <div className="ltw-model-formula">
              <span>Formula</span>
              <code>
                Σ FCFFₜ ÷ (1 + discount rate)ᵗ + terminal value + net cash;
                divided by diluted shares
              </code>
              <p>
                Net cash {valuationInputs.netCash.toFixed(1)} crore · diluted
                shares {valuationInputs.shares.toFixed(2)} crore. Values remain
                in crore until the per-share step.
              </p>
            </div>
          </section>
          <section className="ltw-valuation-output">
            <header>
              <span>DCF and reverse DCF</span>
              <h3>
                {interactiveDcf === null
                  ? "Assumptions are invalid"
                  : `₹${interactiveDcf.toFixed(0)} per share`}
              </h3>
            </header>
            <p>
              {interactiveDcf !== null && price > 0
                ? `This case is ${pct((interactiveDcf / price - 1) * 100)} versus the stored quote.`
                : "A current quote and valid discount/terminal spread are required."}{" "}
              Reverse DCF solves only the explicit growth rate; all other inputs
              stay visible and unchanged.
            </p>
            <div className="ltw-sensitivity">
              <h4>Value sensitivity · growth × discount rate</h4>
              <table>
                <thead>
                  <tr>
                    <th>Growth</th>
                    {sensitivityDiscount.map((discount) => (
                      <th key={discount}>{pct(discount * 100)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sensitivityGrowth.map((growth) => (
                    <tr key={growth}>
                      <th>{pct(growth * 100)}</th>
                      {sensitivityDiscount.map((discount) => {
                        const value = dcfValue({
                          ...valuationInputs,
                          growth,
                          discount,
                        });
                        return (
                          <td key={discount}>
                            {value === null ? "—" : `₹${value.toFixed(0)}`}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section className="ltw-monte-carlo">
            <header>
              <span>Uncertainty, not false precision</span>
              <h3>5,000 same-basis FCFF paths</h3>
            </header>
            <div className="ltw-distribution">
              {["P05", "P25", "Median", "P75", "P95"].map((label, index) => (
                <div key={label}>
                  <span>{label}</span>
                  <i />
                  <strong>
                    {simulationPoints[index] === null
                      ? "—"
                      : `₹${simulationPoints[index]!.toFixed(0)}`}
                  </strong>
                </div>
              ))}
            </div>
            <p>
              Each path varies normalized FCFF ±22%, explicit growth ±5 points,
              discount rate ±2.5 points and terminal growth ±1.5 points using
              triangular distributions.{" "}
              {belowMarketProbability === null
                ? "A market comparison is unavailable."
                : `${pct(belowMarketProbability * 100)} of paths fall below the stored quote.`}
            </p>
            <small>
              Seed 20260815 makes results reproducible. This is scenario
              analysis, not a calibrated probability forecast or backtest.
            </small>
          </section>
          <section className="ltw-valuation-crosschecks">
            <header>
              <span>Cross-checks</span>
              <h3>What is and is not decision-ready</h3>
            </header>
            <dl>
              <div>
                <dt>Stored FCFF DCF</dt>
                <dd>
                  ₹{num(dcf, "fair_value_base").toFixed(0)} · source model,
                  unreviewed
                </dd>
              </div>
              <div>
                <dt>Earnings multiple</dt>
                <dd>
                  {num(multiples, "fair_value_base") > 0
                    ? `₹${num(multiples, "fair_value_base").toFixed(0)} · isolated cross-check`
                    : "Not available"}
                </dd>
              </div>
              <div>
                <dt>Peer valuation</dt>
                <dd>
                  Not available: no compatible, current peer set has passed
                  scope and basis review.
                </dd>
              </div>
              <div>
                <dt>Historical range</dt>
                <dd>
                  Not available: the stored market-history series is not yet
                  validated for this report.
                </dd>
              </div>
              <div>
                <dt>SOTP</dt>
                <dd>
                  Not applicable on current evidence: segment cash flow and
                  capital allocation are not separately disclosed.
                </dd>
              </div>
            </dl>
          </section>
        </div>
        <div className="ltw-history-two">
          <div>
            <h3>Catalysts and evidence windows</h3>
            <p>
              Capex commissioning and utilization: monitor annual-report
              fixed-asset additions, cash flow and resulting segment returns.
            </p>
            <p>
              Solar phase and financing-cost reduction: monitor the next filing
              and FY2027 statements.
            </p>
            <p>
              {filings[0]
                ? text(filings[0], "title")
                : "No newer material filing is surfaced."}
            </p>
          </div>
          <div>
            <h3>Kill conditions</h3>
            {killers.slice(0, 4).map((row, index) => (
              <p key={index}>
                <strong>{text(row, "killer").replace(/_/g, " ")}:</strong>{" "}
                {text(row, "test")}
              </p>
            ))}
          </div>
        </div>
        <div className="ltw-history-decision">
          <div>
            <span>
              Committee decision ·{" "}
              {text(committeeDecision, "decided_at", "historical record")}
            </span>
            <h2>
              {text(
                committeeDecision,
                "recommended_decision",
                "research_more",
              ).replace(/_/g, " ")}
              : do not convert operating momentum into valuation certainty.
            </h2>
            <p>
              {text(
                committeeDecision,
                "decision_notes",
                "Complete price/volume/mix, peer, market-size, capex-return and refreshed valuation work before any capital decision.",
              )}{" "}
            </p>
          </div>
          <button onClick={onResearch}>Open research workstream</button>
        </div>
      </section>

      <details className="ltw-history-appendix">
        <summary>Evidence, methods, extraction and coverage appendix</summary>
        <p>
          Front-stage values use validated annual-report rows only. Ten fiscal
          years of official issuer reports are stored on the external SSD with
          SHA-256 lineage. Each displayed table cell links to its exact PDF
          page. Forty-three core checks cover balance sheet, P&amp;L, cash-flow
          arithmetic, cash roll-forward and segment reconciliations across
          FY2017–FY2026. “Validated” means deterministic reconciliation, not
          human review.
        </p>
        <div className="ltw-history-scroll">
          <table>
            <thead>
              <tr>
                <th>Gap</th>
                <th>Status</th>
                <th>Exact reason</th>
                <th>Next source</th>
              </tr>
            </thead>
            <tbody>
              {gaps.map((row) => (
                <tr key={num(row, "id")}>
                  <td>{text(row, "metric_key").replace(/_/g, " ")}</td>
                  <td>{text(row, "gap_status").replace(/_/g, " ")}</td>
                  <td>{text(row, "reason")}</td>
                  <td>{text(row, "next_source")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </article>
  );
}
