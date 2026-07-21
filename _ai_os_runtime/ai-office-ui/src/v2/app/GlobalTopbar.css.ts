export const GlobalTopbarCss = `
.aios-topbar {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  height: var(--topbar-height);
  padding: 0 var(--space-4);
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  box-shadow: var(--shadow-1);
  z-index: var(--z-topbar);
  position: relative;
  flex-shrink: 0;
}

/* Brand */
.aios-topbar__brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding-right: var(--space-3);
}
.aios-topbar__logo {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: var(--accent);
  color: var(--text-on-accent);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-1);
}
.aios-topbar__wordmark {
  display: flex;
  flex-direction: column;
  line-height: 1;
}
.aios-topbar__wordmark-line {
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: var(--weight-semibold);
  color: var(--text);
  letter-spacing: var(--tracking-tight);
}
.aios-topbar__wordmark-line2 {
  font-family: var(--font-display);
  font-size: 11px;
  color: var(--text-muted);
  letter-spacing: var(--tracking-wide);
  margin-top: 1px;
}

/* Nav */
.aios-topbar__nav {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex: 1;
  min-width: 0;
}
.aios-topbar__nav-item {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  height: 32px;
  padding: 0 var(--space-3);
  font-size: var(--text-md);
  font-weight: var(--weight-medium);
  color: var(--text-muted);
  border-radius: var(--radius-sm);
  transition: all var(--duration-fast) var(--ease-out);
  white-space: nowrap;
}
.aios-topbar__nav-item:hover {
  color: var(--text);
  background: var(--surface-soft);
}
.aios-topbar__nav-item--active {
  color: var(--accent);
  background: var(--accent-soft);
}

/* Actions */
.aios-topbar__actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.aios-topbar__search {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  height: 32px;
  padding: 0 var(--space-3);
  min-width: 240px;
  font-size: var(--text-sm);
  color: var(--text-muted);
  background: var(--bg-sunken);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  transition: all var(--duration-fast) var(--ease-out);
  cursor: pointer;
}
.aios-topbar__search:hover {
  border-color: var(--border);
  background: var(--surface-soft);
}
.aios-topbar__search-text {
  flex: 1;
  text-align: left;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.aios-topbar__kbd {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 2px 5px;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-muted);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-xs);
}

/* Attention badge */
.aios-topbar__attention {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}
.aios-topbar__attention--warn {
  color: var(--status-warn);
  background: var(--status-warn-soft);
}
.aios-topbar__attention--risk {
  color: var(--status-risk);
  background: var(--status-risk-soft);
  animation: aios-risk-pulse 1.8s ease-in-out infinite;
}
.aios-topbar__attention:hover {
  transform: scale(1.05);
}
.aios-topbar__attention-count {
  position: absolute;
  top: -4px;
  right: -4px;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  font-size: 10px;
  font-weight: var(--weight-bold);
  color: var(--text-on-status);
  background: var(--status-risk);
  border: 2px solid var(--surface);
  border-radius: var(--radius-pill);
}

/* Responsive: collapse nav labels on small screens */
@media (max-width: 1100px) {
  .aios-topbar__search { min-width: 160px; }
  .aios-topbar__search-text { display: none; }
}
@media (max-width: 900px) {
  .aios-topbar__nav-item span { display: none; }
  .aios-topbar__wordmark { display: none; }
  .aios-topbar__search { min-width: 40px; padding: 0 8px; justify-content: center; }
  .aios-topbar__kbd { display: none; }
}
`;
