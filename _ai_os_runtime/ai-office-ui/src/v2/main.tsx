/**
 * AI Investment OS — v2 entry point.
 *
 * Imports the design-system CSS (tokens → theme → primitives), the fonts,
 * and mounts the new App shell.
 *
 * This is the production front door. The legacy application remains available only as imported components while migration verification completes.
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
import "./system/workspace.css";

import App from "./app/App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
