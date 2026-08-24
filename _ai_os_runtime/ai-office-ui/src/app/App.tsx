/**
 * AI Investment OS — App Shell (v2)
 *
 * Bloomberg-style terminal layout:
 *   - Left rail: grouped function list (the "function keyboard")
 *   - Topbar: brand, command bar, attention badge, Charlie, theme
 *   - Center: the active function screen
 *   - Right rail: Charlie assistant (collapsible)
 *
 * Plus global surfaces: command palette (Cmd-K), evidence drawer,
 * toast viewport.
 */

import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { applyInitialDomState, useUIStore } from "../store";
import { GlobalTopbar } from "./GlobalTopbar";
import { FunctionSidebar } from "./FunctionSidebar";
import { CommandPalette } from "./CommandPalette";
import { AssistantRail } from "../assistant/AssistantRail";
import { EvidenceDrawer } from "../evidence/EvidenceDrawer";
import { ToastViewport } from "./ToastViewport";
import { AppShellCss } from "./AppShell.css";
import { TERMINAL_FUNCTIONS } from "./destinations";

applyInitialDomState();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: true,
      retry: 1,
      staleTime: 10_000,
    },
  },
});

/** Keyboard shortcuts: Cmd-K palette, Cmd-J assistant. */
function useGlobalShortcuts() {
  const togglePalette = useUIStore((s) => s.togglePalette);
  const closeEvidence = useUIStore((s) => s.closeEvidence);
  const toggleAssistant = useUIStore((s) => s.toggleAssistant);

  React.useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const mod = e.metaKey || e.ctrlKey;
      const target = e.target as HTMLElement;
      const inField = target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable;
      if (mod && e.key.toLowerCase() === "k") {
        e.preventDefault();
        togglePalette();
        return;
      }
      if (mod && e.key.toLowerCase() === "j" && !inField) {
        e.preventDefault();
        toggleAssistant();
        return;
      }
      if (e.key === "Escape" && !inField) {
        closeEvidence();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [togglePalette, closeEvidence, toggleAssistant]);
}

function AppShell() {
  useGlobalShortcuts();
  return (
    <div className="aios-app-shell">
      <style>{AppShellCss}</style>
      <GlobalTopbar />
      <div className="aios-app-body">
        <FunctionSidebar />
        <main className="aios-app-content">
          <React.Suspense fallback={<DestinationSkeleton />}>
            <Routes>
              <Route path="/" element={<Navigate to="/today" replace />} />
              {TERMINAL_FUNCTIONS.map((fn) => (
                <Route key={fn.path} path={`${fn.path}/*`} element={<FunctionRouter path={fn.path} />} />
              ))}
              {/* Legacy compat redirects */}
              <Route path="/portfolio" element={<Navigate to="/portfolio/overview" replace />} />
              <Route path="/research" element={<Navigate to="/research/desk" replace />} />
              <Route path="/risk-trading" element={<Navigate to="/risk/dashboard" replace />} />
              <Route path="/firm" element={<Navigate to="/firm/office" replace />} />
              <Route path="*" element={<Navigate to="/today" replace />} />
            </Routes>
          </React.Suspense>
        </main>
        <AssistantRail />
      </div>
      <CommandPalette />
      <EvidenceDrawer />
      <ToastViewport />
    </div>
  );
}

/**
 * Lazy components must live outside the suspending subtree. React discards
 * first-mount state when a component suspends, so useMemo here would recreate
 * the lazy wrapper on every retry and leave the destination skeleton forever.
 */
const lazyComponents = new Map<string, React.LazyExoticComponent<React.ComponentType>>();

/** Dynamically resolve a function's component from its path. */
function FunctionRouter({ path }: { path: string }) {
  const Component = lazyFunction(path);
  return <Component />;
}

/** Map a function path to a stable lazy-loaded component. */
function lazyFunction(path: string): React.LazyExoticComponent<React.ComponentType> {
  const cached = lazyComponents.get(path);
  if (cached) return cached;
  const loader: Record<string, () => Promise<{ default: React.ComponentType }>> = {
    "/today": () => import("../destinations/today/TodayDestination"),
    "/firm/office": () => import("../destinations/firm/OfficeView").then((m) => ({ default: m.OfficeView })),
    "/firm/graphs": () => import("../destinations/firm/GraphStudio").then((m) => ({ default: m.GraphStudio })),
    "/firm/agents": () => import("../destinations/firm/FirmAgentViews").then((m) => ({ default: m.AgentsView })),
    "/firm/departments": () => import("../destinations/firm/FirmAgentViews").then((m) => ({ default: m.DepartmentsView })),
    "/firm/committees": () => import("../destinations/firm/FirmAgentViews").then((m) => ({ default: m.CommitteesView })),
    "/firm/governance": () => import("../destinations/firm/FirmAgentViews").then((m) => ({ default: m.GovernanceView })),
    "/firm/models": () => import("../destinations/firm/FirmAgentViews").then((m) => ({ default: m.ModelsView })),
    "/firm/system": () => import("../destinations/firm/FirmAgentViews").then((m) => ({ default: m.SystemView })),
    "/firm/library": () => import("../destinations/firm/FirmAgentViews").then((m) => ({ default: m.LibraryView })),
    "/fundamental/theses": () => import("../destinations/fundamental/FundamentalResearch").then((m) => ({ default: m.default })),
    "/fundamental/scorecards": () => import("../destinations/fundamental/FundamentalResearch").then((m) => ({ default: m.default })),
    "/fundamental/valuation": () => import("../destinations/fundamental/FundamentalResearch").then((m) => ({ default: m.default })),
    "/fundamental/coverage": () => import("../destinations/fundamental/FundamentalResearch").then((m) => ({ default: m.default })),
    "/fundamental/dossiers": () => import("../destinations/fundamental/FundamentalResearch").then((m) => ({ default: m.default })),
    "/fundamental/ideas": () => import("../destinations/fundamental/FundamentalResearch").then((m) => ({ default: m.default })),
    "/sector/overview": () => import("../destinations/sector/SectorIntelligence").then((m) => ({ default: m.default })),
    "/sector/fundamentals": () => import("../destinations/sector/SectorIntelligence").then((m) => ({ default: m.default })),
    "/sector/indices": () => import("../destinations/sector/SectorIntelligence").then((m) => ({ default: m.default })),
    "/sector/flows": () => import("../destinations/sector/SectorIntelligence").then((m) => ({ default: m.default })),
    "/sector/committee": () => import("../destinations/sector/SectorIntelligence").then((m) => ({ default: m.default })),
    "/quant/lab": () => import("../destinations/quant/QuantStrategy").then((m) => ({ default: m.default })),
    "/quant/factors": () => import("../destinations/quant/QuantStrategy").then((m) => ({ default: m.default })),
    "/quant/backtests": () => import("../destinations/quant/QuantStrategy").then((m) => ({ default: m.default })),
    "/quant/optimizer": () => import("../destinations/quant/QuantStrategy").then((m) => ({ default: m.default })),
    "/quant/model-validation": () => import("../destinations/quant/QuantStrategy").then((m) => ({ default: m.default })),
    "/quant/ideas": () => import("../destinations/quant/QuantStrategy").then((m) => ({ default: m.default })),
    "/quant/journal-mining": () => import("../destinations/quant/QuantStrategy").then((m) => ({ default: m.default })),
    "/quant/promotion": () => import("../destinations/quant/QuantStrategy").then((m) => ({ default: m.default })),
    "/quant/discovery": () => import("../destinations/quant/QuantStrategy").then((m) => ({ default: m.default })),
    // Options desk
    "/options/desk": () => import("../destinations/options/OptionsDesk").then((m) => ({ default: m.default })),
    "/options/chain": () => import("../destinations/options/OptionsDesk").then((m) => ({ default: m.default })),
    "/options/surface": () => import("../destinations/options/OptionsDesk").then((m) => ({ default: m.default })),
    "/options/oi-analysis": () => import("../destinations/options/OptionsDesk").then((m) => ({ default: m.default })),
    "/options/strategies": () => import("../destinations/options/OptionsDesk").then((m) => ({ default: m.default })),
    "/options/agent": () => import("../destinations/options/OptionsDesk").then((m) => ({ default: m.default })),
    // Scanners
    "/scanners/momentum": () => import("../destinations/scanners/Scanners").then((m) => ({ default: m.default })),
    "/scanners/breakouts": () => import("../destinations/scanners/Scanners").then((m) => ({ default: m.default })),
    "/scanners/volume": () => import("../destinations/scanners/Scanners").then((m) => ({ default: m.default })),
    "/scanners/ideas": () => import("../destinations/scanners/Scanners").then((m) => ({ default: m.default })),
    "/scanners/options-flow": () => import("../destinations/scanners/Scanners").then((m) => ({ default: m.default })),
    // Trading desk
    "/trading/blotter": () => import("../destinations/trading/TradingDesk").then((m) => ({ default: m.default })),
    "/trading/journal": () => import("../destinations/trading/TradingDesk").then((m) => ({ default: m.default })),
    "/trading/tradingview": () => import("../destinations/trading/TradingDesk").then((m) => ({ default: m.default })),
    "/trading/alpha": () => import("../destinations/trading/TradingDesk").then((m) => ({ default: m.default })),
    "/trading/signals": () => import("../destinations/trading/TradingDesk").then((m) => ({ default: m.default })),
    "/trading/execution": () => import("../destinations/trading/TradingDesk").then((m) => ({ default: m.default })),
    // Macro
    "/macro/dashboard": () => import("../destinations/macro/MacroMarkets").then((m) => ({ default: m.default })),
    "/macro/markets": () => import("../destinations/macro/MacroMarkets").then((m) => ({ default: m.default })),
    "/macro/news": () => import("../destinations/macro/MacroMarkets").then((m) => ({ default: m.default })),
    "/macro/calendar": () => import("../destinations/macro/MacroMarkets").then((m) => ({ default: m.default })),
    // Portfolio
    "/portfolio/overview": () => import("../destinations/portfolio/PortfolioTerminal").then((m) => ({ default: m.default })),
    "/portfolio/positions": () => import("../destinations/portfolio/PortfolioTerminal").then((m) => ({ default: m.default })),
    "/portfolio/books": () => import("../destinations/portfolio/PortfolioTerminal").then((m) => ({ default: m.default })),
    "/portfolio/clients": () => import("../destinations/portfolio/PortfolioTerminal").then((m) => ({ default: m.default })),
    "/portfolio/imports": () => import("../destinations/portfolio/PortfolioTerminal").then((m) => ({ default: m.default })),
    "/portfolio/nav": () => import("../destinations/portfolio/PortfolioTerminal").then((m) => ({ default: m.default })),
    "/portfolio/reconciliation": () => import("../destinations/portfolio/PortfolioTerminal").then((m) => ({ default: m.default })),
    "/portfolio/trackers": () => import("../destinations/portfolio/PortfolioTerminal").then((m) => ({ default: m.default })),
    // Risk and capital
    "/risk/dashboard": () => import("../destinations/risk/RiskCapital").then((m) => ({ default: m.default })),
    "/risk/limits": () => import("../destinations/risk/RiskCapital").then((m) => ({ default: m.default })),
    "/risk/institutional": () => import("../destinations/risk/RiskCapital").then((m) => ({ default: m.default })),
    "/risk/capital": () => import("../destinations/risk/RiskCapital").then((m) => ({ default: m.default })),
    // Company Research Desk
    "/research/desk": () => import("../destinations/research/ResearchDesk").then((m) => ({ default: m.ResearchDeskHome })),
    "/research/cases": () => import("../destinations/research/ResearchCases").then((m) => ({ default: m.default })),
    "/research/following": () => import("../destinations/research/ResearchDesk").then((m) => ({ default: m.ResearchFollowing })),
    "/research/scanners": () => import("../destinations/research/ResearchDesk").then((m) => ({ default: m.FundamentalScanners })),
    "/research/knowledge": () => import("../destinations/research/ResearchDesk").then((m) => ({ default: m.ResearchKnowledge })),
    "/research/filings": () => import("../destinations/research/ResearchFilings").then((m) => ({ default: m.default })),
    "/research/special-situations": () => import("../destinations/research/ResearchFilings").then((m) => ({ default: m.default })),
    "/research/papers": () => import("../destinations/research/ResearchFilings").then((m) => ({ default: m.default })),
    "/research/ingest": () => import("../destinations/research/ResearchFilings").then((m) => ({ default: m.default })),
  };
  const load = loader[path];
  const component = load
    ? React.lazy(load)
    : React.lazy(() => import("./GenericTerminal").then((m) => ({ default: m.GenericTerminal })));
  lazyComponents.set(path, component);
  return component;
}

function DestinationSkeleton() {
  return (
    <div style={{ padding: "var(--space-6)", display: "grid", gap: "var(--space-4)", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))" }}>
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="aios-skeleton" style={{ height: 160, borderRadius: "var(--radius-lg)" }} />
      ))}
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppShell />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
