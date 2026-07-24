/**
 * Global Error Boundary
 *
 * Catches any uncaught render error in the app tree and shows a recovery
 * screen instead of a blank white page. Logs the error so Charlie/Jarvis
 * can pick it up. Never silently swallow — always surface.
 */

import React from "react";
import { AlertTriangle, RefreshCw, Home } from "lucide-react";

interface State {
  error: Error | null;
}

export class GlobalErrorBoundary extends React.Component<{ children: React.ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // Log to console for the dev tools + any observability pickup
    console.error("[aios] uncaught render error:", error, info.componentStack);
  }

  handleReload = () => {
    this.setState({ error: null });
    window.location.reload();
  };

  handleDismiss = () => {
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) {
      return (
        <div style={{
          display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
          minHeight: "100vh", padding: "var(--space-8)", background: "var(--bg)", color: "var(--text)",
          gap: "var(--space-4)", textAlign: "center",
        }}>
          <div style={{
            width: 64, height: 64, borderRadius: "50%",
            background: "var(--status-risk-soft)", color: "var(--status-risk)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <AlertTriangle size={32} />
          </div>
          <h1 style={{ fontFamily: "var(--font-display)", fontSize: "var(--text-2xl)", margin: 0 }}>
            Something broke
          </h1>
          <p style={{ color: "var(--text-muted)", maxWidth: 440, margin: 0, lineHeight: 1.6 }}>
            An unexpected error occurred while rendering this screen. The rest of the office is unaffected —
            reload to recover, or ask Charlie to report this to Jarvis.
          </p>
          <details style={{
            maxWidth: 600, width: "100%", textAlign: "left",
            background: "var(--surface-soft)", border: "1px solid var(--border)",
            borderRadius: "var(--radius-md)", padding: "var(--space-3)",
            fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: "var(--text-muted)",
          }}>
            <summary style={{ cursor: "pointer", color: "var(--text-secondary)" }}>Error details</summary>
            <pre style={{ marginTop: "var(--space-2)", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
              {this.state.error.message}
              {"\n\n"}
              {this.state.error.stack}
            </pre>
          </details>
          <div style={{ display: "flex", gap: "var(--space-2)" }}>
            <button
              onClick={this.handleDismiss}
              style={{
                display: "inline-flex", alignItems: "center", gap: "var(--space-2)",
                height: 38, padding: "0 var(--space-4)",
                background: "transparent", color: "var(--text-secondary)",
                border: "1px solid var(--border)", borderRadius: "var(--radius-md)",
                cursor: "pointer", fontSize: "var(--text-sm)",
              }}
            >
              <Home size={14} /> Try to continue
            </button>
            <button
              onClick={this.handleReload}
              style={{
                display: "inline-flex", alignItems: "center", gap: "var(--space-2)",
                height: 38, padding: "0 var(--space-4)",
                background: "var(--accent)", color: "var(--text-on-accent)",
                border: "none", borderRadius: "var(--radius-md)",
                cursor: "pointer", fontSize: "var(--text-sm)", fontWeight: 500,
              }}
            >
              <RefreshCw size={14} /> Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
