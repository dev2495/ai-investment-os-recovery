export const TodayCss = `
.aios-today__hero {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-3);
}

.aios-today__grid {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: var(--space-4);
  align-items: start;
}

@media (max-width: 1100px) {
  .aios-today__grid { grid-template-columns: 1fr; }
}

.aios-today__col {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

/* Brief */
.aios-today__brief-line {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--border-subtle);
}
.aios-today__brief-line:last-child { border-bottom: none; }
.aios-today__brief-bullet {
  color: var(--accent);
  font-weight: var(--weight-bold);
  flex-shrink: 0;
}
.aios-today__brief-title {
  font-size: var(--text-sm);
  color: var(--text);
  line-height: var(--leading-normal);
}
.aios-today__brief-meta {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-top: 2px;
}

/* Decision */
.aios-today__decision {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out);
  border-bottom: 1px solid var(--border-subtle);
}
.aios-today__decision:hover { background: var(--surface-soft); }
.aios-today__decision:last-child { border-bottom: none; }
.aios-today__decision-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: var(--status-warn-soft);
  color: var(--status-warn);
  border-radius: var(--radius-sm);
  flex-shrink: 0;
}
.aios-today__decision-main { flex: 1; min-width: 0; }
.aios-today__decision-title {
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  color: var(--text);
}
.aios-today__decision-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-1);
  font-size: var(--text-xs);
  color: var(--text-muted);
}

/* Delegation */
.aios-today__delegation {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out);
  border-bottom: 1px solid var(--border-subtle);
}
.aios-today__delegation:hover { background: var(--surface-soft); }
.aios-today__delegation:last-child { border-bottom: none; }
.aios-today__delegation-agent {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: var(--accent-soft);
  color: var(--accent);
  border-radius: var(--radius-circle);
  font-size: var(--text-2xs);
  font-weight: var(--weight-semibold);
  flex-shrink: 0;
}
.aios-today__delegation-main { flex: 1; min-width: 0; }
.aios-today__delegation-title {
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  color: var(--text);
}
.aios-today__delegation-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-1);
  font-size: var(--text-xs);
  color: var(--text-muted);
}

/* News */
.aios-today__news {
  padding: var(--space-3);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out);
  border-bottom: 1px solid var(--border-subtle);
}
.aios-today__news:hover { background: var(--surface-soft); }
.aios-today__news:last-child { border-bottom: none; }
.aios-today__news-main { flex: 1; }
.aios-today__news-headline {
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  color: var(--text);
  line-height: var(--leading-normal);
}
.aios-today__news-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-1);
  font-size: var(--text-xs);
  color: var(--text-muted);
}

/* Freshness */
.aios-today__freshness {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  border-bottom: 1px solid var(--border-subtle);
}
.aios-today__freshness:last-child { border-bottom: none; }
.aios-today__freshness--stale {
  background: var(--status-warn-soft);
}
.aios-today__freshness-name {
  flex: 1;
  font-size: var(--text-sm);
  color: var(--text);
}
.aios-today__freshness-time {
  font-size: var(--text-xs);
  color: var(--text-faint);
}

/* Charlie command bar */
.aios-today__charlie-bar {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
}
.aios-today__charlie-input {
  flex: 1;
  height: 38px;
  padding: 0 var(--space-3);
  font-size: var(--text-md);
  color: var(--text);
  background: var(--bg-sunken);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  outline: none;
  font-family: var(--font-sans);
}
.aios-today__charlie-input:focus { border-color: var(--accent); background: var(--surface); }
.aios-today__charlie-input::placeholder { color: var(--text-faint); }
.aios-today__charlie-send {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  height: 38px;
  padding: 0 var(--space-4);
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  color: var(--text-on-accent);
  background: var(--accent);
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
}
.aios-today__charlie-send:hover { background: var(--accent-hover); }
.aios-today__quick-cmds {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding: var(--space-3);
}
.aios-today__quick-cmd {
  padding: var(--space-1) var(--space-3);
  font-size: var(--text-xs);
  color: var(--text-secondary);
  background: var(--surface-soft);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-pill);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}
.aios-today__quick-cmd:hover {
  background: var(--accent-soft);
  border-color: var(--accent-soft-strong);
  color: var(--accent);
}

/* Watchlist items */
.aios-today__watch-item {
  padding: var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out);
}
.aios-today__watch-item:hover { background: var(--surface-soft); }
.aios-today__watch-item:last-child { border-bottom: none; }
.aios-today__watch-symbol {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-1);
}
.aios-today__watch-thesis {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  line-height: 1.4;
  margin-bottom: var(--space-1);
}
.aios-today__watch-meta {
  font-size: var(--text-xs);
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex-wrap: wrap;
}

/* Ideas */
.aios-today__idea {
  padding: var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out);
}
.aios-today__idea:hover { background: var(--surface-soft); }
.aios-today__idea:last-child { border-bottom: none; }
.aios-today__idea-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-1);
}
.aios-today__idea-thesis {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  line-height: 1.45;
}

/* Research ready */
.aios-today__research {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out);
}
.aios-today__research:hover { background: var(--surface-soft); }
.aios-today__research:last-child { border-bottom: none; }
`;
