/**
 * AI Investment OS — Terminal entry point (canonical).
 *
 * Imports the design-system CSS (tokens → theme → primitives), the fonts,
 * and mounts the app shell. This is the sole production front door —
 * legacy code has been removed.
 */

import React from "react";
import ReactDOM from "react-dom/client";

// Fonts (Fraunces serif display, Inter sans, JetBrains Mono)
import "@fontsource/fraunces/400.css";
import "@fontsource/fraunces/500.css";
import "@fontsource/fraunces/600.css";
import "@fontsource/fraunces/700.css";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/500.css";

// Design system CSS (order matters: tokens → theme → primitives)
import "./system/tokens.css";
import "./system/theme.css";
import "./system/primitives.css";

import App from "./app/App";
import { GlobalErrorBoundary } from "./app/ErrorBoundary";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <GlobalErrorBoundary>
      <App />
    </GlobalErrorBoundary>
  </React.StrictMode>
);
