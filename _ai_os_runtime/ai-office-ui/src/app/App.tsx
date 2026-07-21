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
              <Route path="/research" element={<Navigate to="/research/filings" replace />} />
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

/** Dynamically resolve a function's component from its path. */
function FunctionRouter({ path }: { path: string }) {
  const Component = React.useMemo(() => lazyFunction(path), [path]);
  return <Component />;
}

/** Map a function path to its lazy-loaded component. */
function lazyFunction(path: string): React.LazyExoticComponent<React.ComponentType> {
  const loader: Record<string, () => Promise<{ default: React.ComponentType }>> = {
    "/today": () => import("../destinations/today/TodayDestination"),
    "/firm/office": () => import("../destinations/firm/OfficeView").then((m) => ({ default: m.OfficeView })),
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
    "/fundamental/ideas": () => import("../destinations/fundamental/FundamentalResearch").then((m) => ({ default: m.default })),
    "/quant/lab": () => import("../destinations/quant/QuantStrategy").then((m) => ({ default: m.default })),
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
    "/options/agent": () => import("../destinations/options/OptionsDesk").then((m) => ({ default: m.default })),
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
    "/portfolio/nav": () => import("../destinations/portfolio/PortfolioTerminal").then((m) => ({ default: m.default })),
    "/portfolio/reconciliation": () => import("../destinations/portfolio/PortfolioTerminal").then((m) => ({ default: m.default })),
    "/portfolio/trackers": () => import("../destinations/portfolio/PortfolioTerminal").then((m) => ({ default: m.default })),
    // Research & filings
    "/research/filings": () => import("../destinations/research/ResearchFilings").then((m) => ({ default: m.default })),
    "/research/special-situations": () => import("../destinations/research/ResearchFilings").then((m) => ({ default: m.default })),
    "/research/papers": () => import("../destinations/research/ResearchFilings").then((m) => ({ default: m.default })),
    "/research/ingest": () => import("../destinations/research/ResearchFilings").then((m) => ({ default: m.default })),
  };
  const load = loader[path];
  if (load) return React.lazy(load);
  return React.lazy(() => import("./GenericTerminal").then((m) => ({ default: m.GenericTerminal })));
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
