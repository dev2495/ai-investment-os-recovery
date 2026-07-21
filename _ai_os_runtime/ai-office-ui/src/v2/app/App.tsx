/**
 * AI Investment OS — App Shell (v2)
 *
 * The root of the new UI. Sets up:
 *   - TanStack Query provider (server state)
 *   - Theme + density application to <html>
 *   - Global keyboard shortcuts (Cmd-K palette, Esc)
 *   - The persistent layout: topbar + destination content + assistant rail
 *     + evidence drawer + command palette + toast viewport
 *
 * This replaces the 8,808-line legacy App.tsx with a focused ~150-line shell.
 */

import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { applyInitialDomState, useUIStore } from "../store";
import { GlobalTopbar } from "./GlobalTopbar";
import { CommandPalette } from "./CommandPalette";
import { AssistantRail } from "../assistant/AssistantRail";
import { EvidenceDrawer } from "../evidence/EvidenceDrawer";
import { ToastViewport } from "./ToastViewport";
import { AppShellCss } from "./AppShell.css";

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

/** Keyboard shortcut hook: Cmd-K / Ctrl-K opens palette. */
function useGlobalShortcuts() {
  const togglePalette = useUIStore((s) => s.togglePalette);
  const closeEvidence = useUIStore((s) => s.closeEvidence);
  const toggleAssistant = useUIStore((s) => s.toggleAssistant);

  React.useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const mod = e.metaKey || e.ctrlKey;
      // Cmd-K / Ctrl-K → command palette
      if (mod && e.key.toLowerCase() === "k") {
        e.preventDefault();
        togglePalette();
        return;
      }
      // Cmd-J / Ctrl-J → toggle assistant
      if (mod && e.key.toLowerCase() === "j") {
        e.preventDefault();
        toggleAssistant();
        return;
      }
      // Esc → close drawer / palette (don't hijack if typing in a field)
      if (e.key === "Escape") {
        const target = e.target as HTMLElement;
        const inField = target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable;
        if (!inField) {
          closeEvidence();
        }
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
        <main className="aios-app-content">
          <Routes>
            <Route path="/" element={<Navigate to="/today" replace />} />
            <Route path="/today/*" element={<React.Suspense fallback={<DestinationSkeleton />}><TodayRoute /></React.Suspense>} />
            <Route path="/portfolio/*" element={<React.Suspense fallback={<DestinationSkeleton />}><PortfolioRoute /></React.Suspense>} />
            <Route path="/research/*" element={<React.Suspense fallback={<DestinationSkeleton />}><ResearchRoute /></React.Suspense>} />
            <Route path="/risk-trading/*" element={<React.Suspense fallback={<DestinationSkeleton />}><RiskTradingRoute /></React.Suspense>} />
            <Route path="/firm/*" element={<React.Suspense fallback={<DestinationSkeleton />}><FirmRoute /></React.Suspense>} />
            <Route path="*" element={<Navigate to="/today" replace />} />
          </Routes>
        </main>
        <AssistantRail />
      </div>
      <CommandPalette />
      <EvidenceDrawer />
      <ToastViewport />
    </div>
  );
}

/** Lazy-loaded destinations (code-split per route). */
const TodayRoute = React.lazy(() => import("../destinations/today/TodayDestination"));
const PortfolioRoute = React.lazy(() => import("../destinations/portfolio/PortfolioDestination"));
const ResearchRoute = React.lazy(() => import("../destinations/research-strategy/ResearchStrategyDestination"));
const RiskTradingRoute = React.lazy(() => import("../destinations/risk-trading/RiskTradingDestination"));
const FirmRoute = React.lazy(() => import("../destinations/firm/FirmDestination"));

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
