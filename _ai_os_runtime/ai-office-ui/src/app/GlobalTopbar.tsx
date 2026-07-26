/**
 * Global Topbar
 *
 * - App wordmark + 5-destination nav
 * - Live approval/risk badge (the evidence spine entry point)
 * - Command palette trigger (Cmd-K)
 * - Charlie (assistant) toggle
 * - Theme toggle
 *
 * This is the single navigation surface — no left sidebar, no duplicate
 * "command bars". Replaces the old top-of-page command parser.
 */

import React, { useEffect, useRef } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { Search, Sparkles, Sun, Moon, Bell, Command, RefreshCw } from "lucide-react";
import { useUIStore } from "../store";
import { useExchangeZerodhaToken, useMissionControl, useZerodhaAuthStatus } from "../data/queries";
import { IconButton } from "../system/primitives";
import { bool, text } from "../data/liveRow";
import { GlobalTopbarCss } from "./GlobalTopbar.css";

/**
 * Top-level nav shown in the topbar (the 5 primary domains).
 * The full Bloomberg-style function list lives in the left sidebar.
 */
const TOPBAR_NAV = [
  { path: "/today", label: "Today" },
  { path: "/firm/office", label: "Office" },
  { path: "/fundamental/theses", label: "Fundamental" },
  { path: "/quant/lab", label: "Quant" },
  { path: "/trading/blotter", label: "Trading" },
  { path: "/portfolio/overview", label: "Portfolio" },
  { path: "/macro/dashboard", label: "Macro" },
  { path: "/risk/dashboard", label: "Risk" },
];

export function GlobalTopbar() {
  const navigate = useNavigate();
  const togglePalette = useUIStore((s) => s.togglePalette);
  const toggleAssistant = useUIStore((s) => s.toggleAssistant);
  const theme = useUIStore((s) => s.theme);
  const toggleTheme = useUIStore((s) => s.toggleTheme);

  const { data: mission } = useMissionControl();
  const { data: zerodha } = useZerodhaAuthStatus();
  const exchangeZerodha = useExchangeZerodhaToken();
  const callbackHandled = useRef(false);
  const approvalCount = mission?.approvals?.length ?? 0;
  const riskEvents = mission?.execution_control?.filter(
    (r) => text(r, "kind") === "risk_event" || text(r, "control_key") === "global_kill_switch"
  ) ?? [];
  const riskCount = riskEvents.length;

  const totalAttention = approvalCount + (riskCount > 0 ? 1 : 0);

  useEffect(() => {
    if (callbackHandled.current) return;
    const callbackUrl = new URL(window.location.href);
    const requestToken = callbackUrl.searchParams.get("request_token");
    if (!requestToken) return;

    callbackHandled.current = true;
    exchangeZerodha.mutate(requestToken, {
      onSettled: () => {
        for (const key of ["request_token", "status", "action"]) {
          callbackUrl.searchParams.delete(key);
        }
        window.history.replaceState({}, "", `${callbackUrl.pathname}${callbackUrl.search}${callbackUrl.hash}`);
      },
    });
  }, [exchangeZerodha]);

  const reconnectZerodha = () => {
    const loginUrl = text(zerodha, "login_url");
    if (loginUrl) {
      window.open(loginUrl, "_blank", "noopener,noreferrer");
      return;
    }
    navigate("/firm/system");
  };

  return (
    <>
      <style>{GlobalTopbarCss}</style>
      <header className="aios-topbar">
        {/* Wordmark */}
        <div className="aios-topbar__brand">
          <div className="aios-topbar__logo">
            <Sparkles size={16} />
          </div>
          <div className="aios-topbar__wordmark">
            <span className="aios-topbar__wordmark-line">AI Investment</span>
            <span className="aios-topbar__wordmark-line2">Office</span>
          </div>
        </div>

        {/* Domain nav — the full function list is in the left sidebar */}
        <nav className="aios-topbar__nav">
          {TOPBAR_NAV.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `aios-topbar__nav-item ${isActive ? "aios-topbar__nav-item--active" : ""}`
              }
            >
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Right cluster */}
        <div className="aios-topbar__actions">
          {/* Command palette trigger */}
          <button
            className="aios-topbar__search"
            onClick={togglePalette}
            aria-label="Open command palette"
          >
            <Search size={14} />
            <span className="aios-topbar__search-text">Search or ask Charlie…</span>
            <kbd className="aios-topbar__kbd"><Command size={10} />K</kbd>
          </button>

          <button
            className="aios-topbar__zerodha"
            onClick={reconnectZerodha}
            aria-label="Reconnect Zerodha"
            title={
              exchangeZerodha.isPending
                ? "Connecting Zerodha and restarting the read-only stream"
                : exchangeZerodha.isError
                  ? `Zerodha reconnect failed: ${exchangeZerodha.error.message}`
                  : bool(zerodha, "daily_access_token_available")
                    ? "Zerodha connected. Reconnect today's session"
                    : "Reconnect Zerodha for today's live data"
            }
          >
            <span className={bool(zerodha, "daily_access_token_available") ? "aios-topbar__broker-dot aios-topbar__broker-dot--ok" : "aios-topbar__broker-dot aios-topbar__broker-dot--warn"} />
            <RefreshCw size={13} />
            <span className="aios-topbar__zerodha-label">
              {exchangeZerodha.isPending ? "Connecting…" : exchangeZerodha.isSuccess ? "Connected" : "Zerodha"}
            </span>
          </button>

          {/* Attention badge — approvals + risk */}
          {totalAttention > 0 && (
            <button
              className={`aios-topbar__attention ${riskCount > 0 ? "aios-topbar__attention--risk" : "aios-topbar__attention--warn"}`}
              onClick={() => navigate("/today")}
              title={`${approvalCount} approval${approvalCount === 1 ? "" : "s"}${riskCount > 0 ? `, ${riskCount} risk alert${riskCount === 1 ? "" : "s"}` : ""}`}
            >
              <Bell size={14} />
              <span className="aios-topbar__attention-count">{totalAttention}</span>
            </button>
          )}

          {/* Charlie toggle */}
          <IconButton
            icon={Sparkles}
            label="Toggle Charlie assistant (⌘J)"
            onClick={toggleAssistant}
            active={useUIStore.getState().assistantOpen}
          />

          {/* Theme toggle */}
          <IconButton
            icon={theme === "light" ? Moon : Sun}
            label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}
            onClick={toggleTheme}
          />
        </div>
      </header>
    </>
  );
}

/** Live indicator dot for the brand logo. */
export function LiveDot({ tone = "ok" }: { tone?: "ok" | "risk" | "warn" }) {
  return (
    <span
      className={`aios-topbar__live-dot aios-topbar__live-dot--${tone}`}
      style={{
        display: "inline-block",
        width: 6,
        height: 6,
        borderRadius: "50%",
        animation: "aios-risk-pulse 2s ease-in-out infinite",
      }}
    />
  );
}
