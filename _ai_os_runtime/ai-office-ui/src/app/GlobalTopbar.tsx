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

import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { Search, Sparkles, Sun, Moon, Bell, Command, RefreshCw, Database, Radio, ShieldCheck } from "lucide-react";
import { useUIStore } from "../store";
import { useBeginZerodhaAuth, useExchangeZerodhaCallbackUrl, useMissionControl, useZerodhaAuthStatus, useZerodhaMarketStatus } from "../data/queries";
import { useSyncZerodhaAccount, useSyncZerodhaMarket } from "../data/actions";
import { Button, Drawer, IconButton, StatusPill, TextArea } from "../system/primitives";
import { bool, num, text, value } from "../data/liveRow";
import type { LiveRow } from "../data/liveRow";
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
  const [brokerOpen, setBrokerOpen] = React.useState(false);

  const { data: mission } = useMissionControl();
  const { data: zerodha } = useZerodhaAuthStatus();
  const { data: zerodhaMarket, refetch: refreshZerodhaMarket, isFetching: marketRefreshing } = useZerodhaMarketStatus();
  const beginZerodha = useBeginZerodhaAuth();
  const exchangeCallback = useExchangeZerodhaCallbackUrl();
  const syncAccount = useSyncZerodhaAccount();
  const syncMarket = useSyncZerodhaMarket();
  const approvalCount = mission?.approvals?.length ?? 0;
  const riskEvents = mission?.execution_control?.filter(
    (r) => text(r, "kind") === "risk_event" || text(r, "control_key") === "global_kill_switch"
  ) ?? [];
  const riskCount = riskEvents.length;

  const totalAttention = approvalCount + (riskCount > 0 ? 1 : 0);


  const reconnectZerodha = () => {
    const popup = window.open("about:blank", "_blank");
    beginZerodha.mutate(undefined, {
      onSuccess: (session) => {
        const loginUrl = text(session, "login_url");
        if (popup && loginUrl) {
          popup.opener = null;
          popup.location.href = loginUrl;
        } else {
          popup?.close();
        }
        setBrokerOpen(true);
      },
      onError: () => popup?.close(),
    });
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
            onClick={() => setBrokerOpen(true)}
            aria-label="Open Zerodha session control"
            title={
              beginZerodha.isPending
                ? "Creating a secure Zerodha login challenge"
                : beginZerodha.isError
                  ? `Zerodha reconnect failed: ${beginZerodha.error.message}`
                  : bool(zerodha, "daily_access_token_available")
                    ? "Zerodha connected. Reconnect today's session"
                    : "Reconnect Zerodha for today's live data"
            }
          >
            <span className={bool(zerodha, "daily_access_token_available") ? "aios-topbar__broker-dot aios-topbar__broker-dot--ok" : "aios-topbar__broker-dot aios-topbar__broker-dot--warn"} />
            <RefreshCw size={13} />
            <span className="aios-topbar__zerodha-label">
              {beginZerodha.isPending ? "Connecting…" : beginZerodha.isSuccess ? "Login opened" : "Zerodha"}
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
      <BrokerSessionDrawer
        open={brokerOpen}
        onClose={() => setBrokerOpen(false)}
        auth={zerodha}
        market={zerodhaMarket}
        reconnect={reconnectZerodha}
        reconnectPending={beginZerodha.isPending}
        exchangeCallback={(url) => exchangeCallback.mutate(url)}
        exchangePending={exchangeCallback.isPending}
        exchangeComplete={exchangeCallback.isSuccess}
        refresh={() => refreshZerodhaMarket()}
        refreshPending={marketRefreshing}
        syncAccount={() => syncAccount.mutate({ datasets: ["holdings", "positions", "orders", "trades", "funds"], actor: "Devarsh" })}
        syncAccountPending={syncAccount.isPending}
        syncMarket={() => syncMarket.mutate({ modes: ["quotes", "options"], underlyings: ["NIFTY", "BANKNIFTY"], strike_pairs: 24, actor: "Devarsh" })}
        syncMarketPending={syncMarket.isPending}
        error={beginZerodha.error ?? exchangeCallback.error ?? syncAccount.error ?? syncMarket.error}
      />
    </>
  );
}

function BrokerSessionDrawer(props: {
  open: boolean;
  onClose: () => void;
  auth?: LiveRow;
  market?: LiveRow;
  reconnect: () => void;
  reconnectPending: boolean;
  exchangeCallback: (url: string) => void;
  exchangePending: boolean;
  exchangeComplete: boolean;
  refresh: () => void;
  refreshPending: boolean;
  syncAccount: () => void;
  syncAccountPending: boolean;
  syncMarket: () => void;
  syncMarketPending: boolean;
  error: Error | null;
}) {
  const [callbackUrl, setCallbackUrl] = React.useState("");
  const auth = value<LiveRow>(props.market, "auth", props.auth ?? {});
  const warehouse = value<LiveRow>(props.market, "warehouse", {});
  const stream = value<LiveRow>(props.market, "stream", {});
  const connected = bool(props.market, "daily_access_token_available", bool(props.auth, "daily_access_token_available"));
  const accountReady = bool(auth, "account_match") && bool(auth, "profile_validated");
  const instruments = num(warehouse, "active_instruments");
  const latestQuote = text(warehouse, "latest_quote_at", "");
  const latestOption = text(warehouse, "latest_option_at", "");
  const sessionExpiry = text(auth, "access_token_expires_at", text(props.auth, "access_token_expires_at", ""));
  const streamConnected = text(stream, "connection_state") === "connected";

  return (
    <Drawer open={props.open} onClose={props.onClose} title="Zerodha Market Session" subtitle="Read-only account and market data control" icon={ShieldCheck} width={520}>
      <div className="aios-broker-session">
        <div className="aios-broker-session__summary">
          <div><span>Daily login</span><StatusPill status={connected ? "connected" : "login required"} /></div>
          <div><span>Account binding</span><StatusPill status={accountReady ? "verified" : "needs verification"} /></div>
          <div><span>Live stream</span><StatusPill status={streamConnected ? "connected" : text(stream, "health_status", "not started")} /></div>
          <div><span>Broker execution</span><StatusPill status="locked" /></div>
        </div>

        <section className="aios-broker-session__stage">
          <div><ShieldCheck size={17} /><strong>1. Authenticate today</strong></div>
          <p>Zerodha requires one human login each trading day. If login ends on a kite.zerodha.com page, copy its full address and paste it below. The one-time request token is exchanged and stored only by the backend.</p>
          <Button variant="primary" icon={RefreshCw} onClick={props.reconnect} disabled={props.reconnectPending}>{props.reconnectPending ? "Opening login…" : connected ? "Renew today’s session" : "Connect Zerodha"}</Button>
          <TextArea
            rows={3}
            value={callbackUrl}
            onChange={(event) => setCallbackUrl(event.target.value)}
            placeholder="Paste the completed Zerodha login URL"
            aria-label="Completed Zerodha login URL"
          />
          <Button
            icon={ShieldCheck}
            onClick={() => props.exchangeCallback(callbackUrl.trim())}
            disabled={!callbackUrl.trim() || props.exchangePending}
          >
            {props.exchangePending ? "Connecting session…" : props.exchangeComplete ? "Session connected" : "Use pasted login URL"}
          </Button>
          {connected ? <p>Current session is verified{sessionExpiry ? ` until ${new Date(sessionExpiry).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })}` : ""}.</p> : null}
        </section>

        <section className="aios-broker-session__stage">
          <div><Database size={17} /><strong>2. Refresh read-only data</strong></div>
          <p>{instruments.toLocaleString("en-IN")} active instruments. Latest quote: {latestQuote || "none"}. Latest option snapshot: {latestOption || "none"}.</p>
          <div className="aios-broker-session__buttons">
            <Button icon={Database} onClick={props.syncAccount} disabled={!connected || props.syncAccountPending}>{props.syncAccountPending ? "Syncing account…" : "Sync account"}</Button>
            <Button icon={Radio} onClick={props.syncMarket} disabled={!connected || props.syncMarketPending}>{props.syncMarketPending ? "Syncing market…" : "Sync market + options"}</Button>
          </div>
        </section>

        <section className="aios-broker-session__stage">
          <div><Radio size={17} /><strong>3. Verify readiness</strong></div>
          <p>{streamConnected ? `${num(stream, "live_count")} instruments are streaming.` : "The stream remains paused until today’s login and data sync complete."}</p>
          <Button variant="ghost" icon={RefreshCw} onClick={props.refresh} disabled={props.refreshPending}>{props.refreshPending ? "Checking…" : "Check status"}</Button>
        </section>

        {props.error ? <div role="alert" className="aios-broker-session__error">{props.error.message}</div> : null}
        <div className="aios-broker-session__safety">This control cannot place, modify, or cancel orders. Broker writes remain locked.</div>
      </div>
    </Drawer>
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
