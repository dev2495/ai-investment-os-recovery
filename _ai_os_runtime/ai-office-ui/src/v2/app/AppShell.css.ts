/**
 * App shell layout CSS (exported as a string so it's colocated with the shell).
 * The persistent grid: topbar (52px) + [content | assistant rail].
 */
export const AppShellCss = `
.aios-app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  background: var(--bg);
}

.aios-app-body {
  display: flex;
  flex: 1;
  min-height: 0;
  position: relative;
}

.aios-app-content {
  flex: 1;
  min-width: 0;
  overflow: auto;
  position: relative;
}

/* Destination container — padded, max-width for readability */
.aios-destination {
  max-width: var(--content-max);
  margin: 0 auto;
  padding: var(--space-6) var(--space-8);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

@media (max-width: 900px) {
  .aios-destination {
    padding: var(--space-4);
  }
}

/* Destination header (title + tabs + actions) */
.aios-destination__head {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.aios-destination__title-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.aios-destination__title {
  font-family: var(--font-display);
  font-size: var(--text-3xl);
  font-weight: var(--weight-semibold);
  letter-spacing: var(--tracking-tight);
  color: var(--text);
}
.aios-destination__subtitle {
  font-size: var(--text-sm);
  color: var(--text-muted);
}
`;
