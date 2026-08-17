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

.aios-today__thesis-feed {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  background: var(--border-subtle);
}
.aios-today__thesis-change {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-2) var(--space-3);
  padding: var(--space-4);
  background: var(--surface);
  border-left: 3px solid var(--status-warn);
}
.aios-today__thesis-change--source { border-left-color: var(--accent); }
.aios-today__thesis-change--agent_draft { border-left-color: var(--status-warn); background: var(--status-warn-soft); }
.aios-today__thesis-change--human_decision { border-left-color: var(--status-risk); }
.aios-today__thesis-origin {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.aios-today__thesis-main { min-width: 0; color: inherit; text-decoration: none; }
.aios-today__thesis-title { display: flex; align-items: center; gap: var(--space-2); color: var(--text); }
.aios-today__thesis-title strong {
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: .04em;
}
.aios-today__thesis-title span { flex: 1; font-size: var(--text-sm); font-weight: var(--weight-semibold); }
.aios-today__thesis-main p {
  margin: var(--space-2) 0;
  color: var(--text-muted);
  font-size: var(--text-sm);
  line-height: var(--leading-normal);
}
.aios-today__thesis-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1) var(--space-3);
  color: var(--text-faint);
  font-size: var(--text-xs);
}
.aios-today__thesis-source {
  align-self: end;
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  color: var(--accent);
  font-size: var(--text-xs);
  font-weight: var(--weight-semibold);
  text-decoration: none;
}
@media (max-width: 760px) {
  .aios-today__thesis-feed { grid-template-columns: 1fr; }
  .aios-today__thesis-change { grid-template-columns: minmax(0, 1fr); }
  .aios-today__thesis-source { justify-self: start; }
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

/* Governed delegation */
.aios-today__delegate-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.aios-today__delegate-fields {
  display: grid;
  grid-template-columns: minmax(220px, 1.4fr) minmax(190px, 1fr) minmax(120px, 0.55fr);
  gap: var(--space-3);
}
.aios-today__delegate-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}
.aios-today__safety-note {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-muted);
  font-size: var(--text-xs);
}

/* Accountable work queue */
.aios-today__work-record {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
}
.aios-today__work-record:last-child { border-bottom: none; }
.aios-today__work-main,
.aios-today__activity-record {
  appearance: none;
  width: 100%;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.aios-today__work-main {
  flex: 1;
  min-width: 0;
  padding: var(--space-1);
  border-radius: var(--radius-sm);
}
.aios-today__work-main:hover,
.aios-today__activity-record:hover { background: var(--surface-soft); }
.aios-today__work-main:focus-visible,
.aios-today__activity-record:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
.aios-today__work-main:disabled,
.aios-today__activity-record:disabled { cursor: default; }
.aios-today__work-title {
  color: var(--text);
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
}
.aios-today__work-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-top: var(--space-1);
  color: var(--text-muted);
  font-size: var(--text-xs);
}
.aios-today__work-actions {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex-shrink: 0;
}

/* Real worker and message activity */
.aios-today__activity-record {
  display: block;
  padding: var(--space-3);
  border-radius: var(--radius-sm);
  border-bottom: 1px solid var(--border-subtle);
}
.aios-today__activity-record:last-child { border-bottom: none; }
.aios-today__activity-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  color: var(--text);
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
}
.aios-today__activity-meta {
  margin-top: var(--space-1);
  color: var(--text-muted);
  font-size: var(--text-xs);
}
.aios-today__activity-error {
  margin-top: var(--space-1);
  color: var(--status-risk);
  font-size: var(--text-xs);
  line-height: var(--leading-normal);
}

@media (max-width: 760px) {
  .aios-today__delegate-fields { grid-template-columns: 1fr; }
  .aios-today__delegate-footer,
  .aios-today__work-record { align-items: stretch; flex-direction: column; }
  .aios-today__work-actions { justify-content: flex-end; }
}

.aios-today__research-actions{display:flex;align-items:center;gap:12px}.aios-today__research-actions>a{display:flex;align-items:center;gap:3px;color:var(--accent);font-size:var(--text-xs);font-weight:700;text-decoration:none}.aios-today__case-board{padding:2px}.aios-today__case-summary{display:flex;align-items:baseline;gap:6px;padding:8px 10px 13px;color:var(--text-muted);font-size:var(--text-xs)}.aios-today__case-summary strong{color:var(--text);font:700 19px Georgia,serif}.aios-today__case-summary i{width:1px;height:16px;background:var(--border);margin:0 7px}.aios-today__case-list{display:grid;border:1px solid var(--border);border-radius:var(--radius-md);overflow:hidden}.aios-today__case-row{display:grid;grid-template-columns:minmax(150px,1.1fr) minmax(150px,.8fr) minmax(210px,1.1fr) auto;gap:16px;align-items:center;padding:13px 15px;border-bottom:1px solid var(--border);color:inherit;text-decoration:none;background:var(--surface)}.aios-today__case-row:last-child{border-bottom:0}.aios-today__case-row:hover{background:var(--surface-hover)}.aios-today__case-company span{display:block;color:var(--accent);font-size:10px;font-weight:800;letter-spacing:.07em}.aios-today__case-company strong{display:block;margin-top:3px;font-size:var(--text-sm)}.aios-today__case-progress>div{height:4px;background:var(--surface-sunken);border-radius:5px;overflow:hidden}.aios-today__case-progress i{display:block;height:100%;background:var(--accent)}.aios-today__case-progress span,.aios-today__case-action>span{display:block;margin-top:5px;color:var(--text-muted);font-size:var(--text-xs)}.aios-today__case-action>span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.aios-today__case-row>svg{color:var(--text-faint)}
@media(max-width:760px){.aios-today__research-actions .aios-button{display:none}.aios-today__case-row{grid-template-columns:minmax(0,1fr) auto;gap:9px 12px}.aios-today__case-progress{grid-column:1}.aios-today__case-action{grid-column:1}.aios-today__case-row>svg{grid-column:2;grid-row:1/4}.aios-today__case-summary{flex-wrap:wrap}}
`;
