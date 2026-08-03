/**
 * AI Investment OS — Terminal Function Registry
 *
 * Bloomberg-style: each function is a focused, deep terminal screen.
 * Functions are grouped by domain. Every function has a short mnemonic
 * code (like Bloomberg's <EQUITY>, <PORT>, <BLP>) for the command palette.
 *
 * The old UI collapsed everything into 5 ambiguous destinations. This
 * registry gives each specialized workflow its own home — long-term
 * fundamental research, quant strategy lab, options desk, macro, trades
 * journal, alpha tracker, idea generators, the 3D office, and more.
 */

import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard,
  Building2,
  Boxes,
  Users,
  Gavel,
  ShieldCheck,
  Cpu,
  Activity,
  Library,
  TrendingUp,
  TrendingDown,
  Newspaper,
  Globe2,
  BookOpen,
  Calculator,
  Lightbulb,
  BarChart3,
  Brain,
  LineChart,
  Target,
  Notebook,
  DollarSign,
  GitBranch,
  FileText,
  Microscope,
  Zap,
  Briefcase,
  Wallet,
  PieChart,
  Gauge,
  ClipboardCheck,
  Calendar,
  Download,
  ShieldAlert,
  Radar,
  Flame,
  Layers,
} from "lucide-react";

export type FunctionGroup =
  | "home"
  | "firm"
  | "fundamental"
  | "quant"
  | "trading"
  | "options"
  | "scanners"
  | "portfolio"
  | "macro"
  | "research"
  | "risk";

export interface TerminalFunction {
  code: string;
  path: string;
  label: string;
  icon: LucideIcon;
  description: string;
  group: FunctionGroup;
  order: number;
  status?: "live" | "beta" | "preview";
}

export const FUNCTION_GROUPS: Array<{ key: FunctionGroup; label: string; icon: LucideIcon }> = [
  { key: "home", label: "Home", icon: LayoutDashboard },
  { key: "firm", label: "The Firm", icon: Building2 },
  { key: "fundamental", label: "Fundamental Research", icon: BookOpen },
  { key: "quant", label: "Quant & Strategy", icon: BarChart3 },
  { key: "trading", label: "Trading Desk", icon: TrendingUp },
  { key: "options", label: "Options Desk", icon: TrendingDown },
  { key: "scanners", label: "Scanners", icon: Radar },
  { key: "portfolio", label: "Portfolio & Clients", icon: Wallet },
  { key: "macro", label: "Macro & Markets", icon: Globe2 },
  { key: "research", label: "Research & Filings", icon: FileText },
  { key: "risk", label: "Risk & Compliance", icon: ShieldCheck },
];

export const TERMINAL_FUNCTIONS: TerminalFunction[] = [
  /* ---- HOME ---- */
  { code: "TODAY", path: "/today", label: "Today", icon: LayoutDashboard, description: "Daily brief, decisions, delegations, what matters now", group: "home", order: 0, status: "live" },

  /* ---- THE FIRM ---- */
  { code: "OFFICE", path: "/firm/office", label: "3D Live Office", icon: Boxes, description: "Walk the firm — every employee, assignment, graph handoff, and risk state", group: "firm", order: 0, status: "live" },
  { code: "GRAPHS", path: "/firm/graphs", label: "Graph Studio", icon: GitBranch, description: "Launch, inspect, pause, decide, correct, and adapt governed agent workflows", group: "firm", order: 1, status: "live" },
  { code: "AGENTS", path: "/firm/agents", label: "Agents & Employees", icon: Users, description: "The full agent roster, departments, skills, model routes", group: "firm", order: 1, status: "beta" },
  { code: "DEPTS", path: "/firm/departments", label: "Departments", icon: Building2, description: "Live departments, mandates, leads, and work queues", group: "firm", order: 2, status: "beta" },
  { code: "COMM", path: "/firm/committees", label: "Committee Room", icon: Gavel, description: "Packets, positions, synthesis, human decisions", group: "firm", order: 3, status: "beta" },
  { code: "GOV", path: "/firm/governance", label: "Governance", icon: ShieldCheck, description: "Architecture changes, decisions, production safety", group: "firm", order: 4, status: "beta" },
  { code: "MODELS", path: "/firm/models", label: "Models & Routes", icon: Cpu, description: "Model endpoints, routes, catalog, cost ledger, escalations", group: "firm", order: 5, status: "beta" },
  { code: "SYSTEM", path: "/firm/system", label: "System Health", icon: Activity, description: "Daemons, data sources, freshness, connector health", group: "firm", order: 6, status: "beta" },
  { code: "LIBRARY", path: "/firm/library", label: "Knowledge Library", icon: Library, description: "Obsidian vault, Qdrant retrieval, note graph", group: "firm", order: 7, status: "beta" },

  /* ---- FUNDAMENTAL RESEARCH (Buffett school) ---- */
  { code: "LTF", path: "/fundamental/theses", label: "Long-Term Theses", icon: BookOpen, description: "Buffett-style investment theses per holding — moat, management, quality", group: "fundamental", order: 0, status: "beta" },
  { code: "SCOR", path: "/fundamental/scorecards", label: "Specialist Scorecards", icon: Microscope, description: "11 scorecards — business model, moat, governance, forensic, valuation", group: "fundamental", order: 1, status: "beta" },
  { code: "VAL", path: "/fundamental/valuation", label: "Valuation Suite", icon: Calculator, description: "DCF, multiples, reverse DCF, Monte Carlo per holding", group: "fundamental", order: 2, status: "beta" },
  { code: "COV", path: "/fundamental/coverage", label: "Coverage & Checklists", icon: ClipboardCheck, description: "Coverage queue, theses checklists, review schedule", group: "fundamental", order: 3, status: "beta" },
  { code: "LTID", path: "/fundamental/ideas", label: "Fundamental Idea Generator", icon: Lightbulb, description: "Generate long-term investment ideas from theses, filings, screens", group: "fundamental", order: 4, status: "beta" },

  /* ---- QUANT & STRATEGY ---- */
  { code: "QLAB", path: "/quant/lab", label: "Quant Lab", icon: BarChart3, description: "Strategy candidates, backtests, validation, promotion board", group: "quant", order: 0, status: "beta" },
  { code: "FACT", path: "/quant/factors", label: "Factor Analysis", icon: Target, description: "Portfolio and strategy factor exposure, contribution, beta and residual alpha", group: "quant", order: 1, status: "beta" },
  { code: "BACK", path: "/quant/backtests", label: "Backtests", icon: LineChart, description: "Backtest runs with explicit data lineage and reproducibility", group: "quant", order: 1, status: "beta" },
  { code: "OPT", path: "/quant/optimizer", label: "Strategy Optimizer", icon: Zap, description: "Walk-forward parameter search on OUR data, robustness heatmaps", group: "quant", order: 2, status: "beta" },
  { code: "MV", path: "/quant/model-validation", label: "Model Validation", icon: Brain, description: "Adversarial review — leakage, overfit, walk-forward, robustness", group: "quant", order: 3, status: "beta" },
  { code: "QID", path: "/quant/ideas", label: "Quant Idea Generator", icon: Lightbulb, description: "Mine trade journal + regime for new strategy candidates", group: "quant", order: 4, status: "beta" },
  { code: "MINE", path: "/quant/journal-mining", label: "Journal Mining", icon: GitBranch, description: "Mine your own trades for repeating edges and patterns", group: "quant", order: 5, status: "beta" },
  { code: "PROMO", path: "/quant/promotion", label: "Promotion Board", icon: TrendingUp, description: "Strategy promotion pipeline: paper → live-ready → retired", group: "quant", order: 6, status: "beta" },
  { code: "DSCV", path: "/quant/discovery", label: "Strategy Discovery", icon: Microscope, description: "Automated discovery runs + idea dossiers + triage queue", group: "quant", order: 7, status: "beta" },

  /* ---- TRADING DESK ---- */
  { code: "BLT", path: "/trading/blotter", label: "Trade Blotter", icon: TrendingUp, description: "Live blotter — manual, paper, broker-synced trades", group: "trading", order: 0, status: "beta" },
  { code: "JRN", path: "/trading/journal", label: "Trades Journal", icon: Notebook, description: "Annotate trades, track reasoning, emotions, lessons learned", group: "trading", order: 1, status: "beta" },
  { code: "TV", path: "/trading/tradingview", label: "TradingView Bridge", icon: LineChart, description: "Chart actions, Pine indicators, alert requests, templates", group: "trading", order: 2, status: "beta" },
  { code: "ALPHA", path: "/trading/alpha", label: "Alpha Tracker", icon: Target, description: "Track P&L attribution, edge decay, win rate, expectancy by strategy", group: "trading", order: 3, status: "beta" },
  { code: "SIG", path: "/trading/signals", label: "Signals & Alerts", icon: Zap, description: "Live signals, paper monitor heartbeats, drift checks", group: "trading", order: 4, status: "beta" },
  { code: "EXEC", path: "/trading/execution", label: "Execution Safety", icon: ShieldCheck, description: "Kill-switch, limited-live requests, order intents, gates", group: "trading", order: 5, status: "beta" },

  /* ---- OPTIONS DESK ---- */
  { code: "OPTS", path: "/options/desk", label: "Options Desk", icon: TrendingDown, description: "Options surface, chain, manual trade entry, the options agent", group: "options", order: 0, status: "beta" },
  { code: "OCHAIN", path: "/options/chain", label: "Option Chain", icon: BarChart3, description: "Live option prices, volume, open interest, and provider analytics when available", group: "options", order: 1, status: "beta" },
  { code: "OSURF", path: "/options/surface", label: "Vol Surface", icon: LineChart, description: "Implied vol smile, skew, and term structure when IV is available", group: "options", order: 2, status: "beta" },
  { code: "OIA", path: "/options/oi-analysis", label: "OI & Straddles", icon: Activity, description: "OI buildup, strike walls, PCR, and live straddle curves", group: "options", order: 3, status: "beta" },
  { code: "OSTRAT", path: "/options/strategies", label: "Strategy Builder", icon: Layers, description: "Construct live-chain option combinations and inspect expiry payoff", group: "options", order: 4, status: "beta" },
  { code: "OAGENT", path: "/options/agent", label: "Options Agent", icon: Brain, description: "Talk to the specialist options agent — strategies, risk, edge", group: "options", order: 5, status: "beta" },

  /* ---- SCANNERS ---- */
  { code: "SCAN", path: "/scanners/momentum", label: "Momentum Scanner", icon: TrendingUp, description: "Live momentum signals with direction + strength", group: "scanners", order: 0, status: "beta" },
  { code: "BRK", path: "/scanners/breakouts", label: "Breakouts", icon: Zap, description: "Watchlist + positions + strong signals near breakout", group: "scanners", order: 1, status: "beta" },
  { code: "VOL", path: "/scanners/volume", label: "Volume / OI Spurt", icon: Activity, description: "Contracts with the biggest OI change", group: "scanners", order: 2, status: "beta" },
  { code: "IDEA", path: "/scanners/ideas", label: "Idea Scanner", icon: Lightbulb, description: "Generated fundamental + quant ideas to review", group: "scanners", order: 3, status: "beta" },
  { code: "FLOW", path: "/scanners/options-flow", label: "Options Flow", icon: Flame, description: "Net OI buildup by underlying — call/put writing bias", group: "scanners", order: 4, status: "beta" },

  /* ---- PORTFOLIO & CLIENTS ---- */
  { code: "PORT", path: "/portfolio/overview", label: "Portfolio Overview", icon: Briefcase, description: "NAV, exposure, allocation, performance across clients", group: "portfolio", order: 0, status: "beta" },
  { code: "POS", path: "/portfolio/positions", label: "Positions", icon: PieChart, description: "Positions with book, purpose, thesis, horizon, exit criteria", group: "portfolio", order: 1, status: "beta" },
  { code: "BOOKS", path: "/portfolio/books", label: "Investment Books", icon: BookOpen, description: "Multi-book brain — mandates, allocations, cross-book conflicts", group: "portfolio", order: 2, status: "beta" },
  { code: "CLIENTS", path: "/portfolio/clients", label: "Clients", icon: Users, description: "Client registry, onboarding, suitability, NAV, performance", group: "portfolio", order: 3, status: "beta" },
  { code: "NAV", path: "/portfolio/nav", label: "NAV & Cash", icon: DollarSign, description: "NAV snapshots, cash ledger, fee ledger, FIFO tax lots", group: "portfolio", order: 4, status: "beta" },
  { code: "RECON", path: "/portfolio/reconciliation", label: "Reconciliation", icon: GitBranch, description: "Broker recon, p2cursor, legacy source readiness", group: "portfolio", order: 5, status: "beta" },
  { code: "FOLIO", path: "/portfolio/trackers", label: "Folio Trackers", icon: Activity, description: "Ongoing per-folio watch — thesis adherence, drift, review cadence", group: "portfolio", order: 6, status: "beta" },

  /* ---- MACRO & MARKETS ---- */
  { code: "MACRO", path: "/macro/dashboard", label: "Macro Dashboard", icon: Globe2, description: "Macro observations, regime, rates, FX, commodities, indices", group: "macro", order: 0, status: "beta" },
  { code: "MKT", path: "/macro/markets", label: "Markets", icon: TrendingUp, description: "Index quotes, breadth, sector rotation, market calendar", group: "macro", order: 1, status: "beta" },
  { code: "NEWS", path: "/macro/news", label: "News & Events", icon: Newspaper, description: "News feed, corporate actions, exchange announcements", group: "macro", order: 2, status: "beta" },
  { code: "CAL", path: "/macro/calendar", label: "Market Calendar", icon: Calendar, description: "Earnings, ex-dates, RBI, Fed, holidays", group: "macro", order: 3, status: "beta" },

  /* ---- RESEARCH & FILINGS ---- */
  { code: "FIL", path: "/research/filings", label: "Filings", icon: FileText, description: "NSE/BSE/SEC filings, collector runs, PDF extraction", group: "research", order: 0, status: "beta" },
  { code: "SPEC", path: "/research/special-situations", label: "Special Situations", icon: Target, description: "Arbitrage, demergers, buybacks, delistings — committee gates", group: "research", order: 1, status: "beta" },
  { code: "PAPER", path: "/research/papers", label: "Research Papers", icon: BookOpen, description: "Ingest academic papers → strategy hypotheses", group: "research", order: 2, status: "beta" },
  { code: "ING", path: "/research/ingest", label: "Research Ingest", icon: Download, description: "Ingest research pages, blogs, PDFs → strategy ideas", group: "research", order: 3, status: "beta" },

  /* ---- RISK & COMPLIANCE ---- */
  { code: "RISK", path: "/risk/dashboard", label: "Risk Dashboard", icon: ShieldAlert, description: "Live breaches, limit checks, concentration, drawdown", group: "risk", order: 0, status: "beta" },
  { code: "LIM", path: "/risk/limits", label: "Risk Limits", icon: Gauge, description: "Limit engine, per-book limits, institutional risk runs", group: "risk", order: 1, status: "beta" },
  { code: "INST", path: "/risk/institutional", label: "Institutional Risk", icon: ShieldCheck, description: "Stress tests, liquidity, factor concentration, VaR/ES", group: "risk", order: 2, status: "beta" },
  { code: "CAP", path: "/risk/capital", label: "Capital Allocation", icon: Wallet, description: "Capital policies, allocation analysis, capital committee", group: "risk", order: 3, status: "beta" },
];

/** Map of all functions by path. */
export const FUNCTIONS_BY_PATH = new Map(TERMINAL_FUNCTIONS.map((f) => [f.path, f]));

/** Get functions for a group, sorted. */
export function functionsForGroup(group: FunctionGroup): TerminalFunction[] {
  return TERMINAL_FUNCTIONS.filter((f) => f.group === group).sort((a, b) => a.order - b.order);
}

/** Get a function by its code mnemonic. */
export function functionByCode(code: string): TerminalFunction | undefined {
  return TERMINAL_FUNCTIONS.find((f) => f.code === code);
}

/** Find the function that owns a route path. */
export function functionForPath(path: string): TerminalFunction | undefined {
  // Try exact match first, then prefix match (longest first)
  const exact = TERMINAL_FUNCTIONS.find((f) => f.path === path);
  if (exact) return exact;
  const sorted = [...TERMINAL_FUNCTIONS].sort((a, b) => b.path.length - a.path.length);
  return sorted.find((f) => path.startsWith(f.path));
}

/** Legacy compat. */
export function getDestination(key: string): TerminalFunction | undefined {
  return functionForPath(`/${key}`);
}
