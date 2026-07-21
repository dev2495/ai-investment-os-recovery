/**
 * App shell layout CSS. The persistent grid:
 *   topbar (52px)
 *   +--- sidebar (232px) | content | assistant (380px) ---+
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

/* Destination container */
.aios-destination {
  max-width: var(--content-max);
  margin: 0 auto;
  padding: var(--space-6) var(--space-8);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

@media (max-width: 1200px) {
  .aios-destination { padding: var(--space-5) var(--space-5); }
}

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

/* Function sidebar (left rail) */
.aios-sidebar {
  width: 232px;
  flex-shrink: 0;
  height: 100%;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.aios-sidebar__scroll {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: var(--space-3) var(--space-2);
}
.aios-sidebar__group {
  margin-bottom: var(--space-3);
}
.aios-sidebar__group-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-2xs);
  font-weight: var(--weight-semibold);
  text-transform: uppercase;
  letter-spacing: var(--tracking-caps);
  color: var(--text-faint);
}
.aios-sidebar__group-head svg {
  color: var(--text-faint);
}
.aios-sidebar__item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-2);
  margin: 1px var(--space-1);
  font-size: var(--text-sm);
  color: var(--text-secondary);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  white-space: nowrap;
  position: relative;
}
.aios-sidebar__item:hover {
  background: var(--surface-soft);
  color: var(--text);
}
.aios-sidebar__item--active {
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: var(--weight-medium);
}
.aios-sidebar__item-icon {
  flex-shrink: 0;
  display: inline-flex;
}
.aios-sidebar__item-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
}
.aios-sidebar__item-code {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  color: var(--text-faint);
  padding: 1px 4px;
  background: var(--bg-sunken);
  border-radius: var(--radius-xs);
}
.aios-sidebar__item--active .aios-sidebar__item-code {
  background: var(--accent-soft-strong);
  color: var(--accent);
}
.aios-sidebar__item-status {
  width: 5px;
  height: 5px;
  border-radius: var(--radius-circle);
  flex-shrink: 0;
}
.aios-sidebar__item-status--preview { background: var(--status-warn); }
.aios-sidebar__item-status--beta { background: var(--status-info); }
.aios-sidebar__item-status--live { background: var(--status-ok); }

/* Sidebar collapse on small screens */
@media (max-width: 1000px) {
  .aios-sidebar { width: 52px; }
  .aios-sidebar__item-label,
  .aios-sidebar__item-code,
  .aios-sidebar__item-status,
  .aios-sidebar__group-head span { display: none; }
  .aios-sidebar__item { justify-content: center; }
  .aios-sidebar__group-head { justify-content: center; }
}
@media (max-width: 700px) {
  .aios-sidebar { display: none; }
}
`;
