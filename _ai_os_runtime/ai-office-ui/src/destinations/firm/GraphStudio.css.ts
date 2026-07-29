export const GraphStudioCss = `
.graph-studio { gap: var(--space-4); }
.graph-studio__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
}
.graph-studio__title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text);
  font-family: var(--font-display);
  font-size: var(--text-2xl);
  font-weight: 650;
  letter-spacing: 0;
}
.graph-studio__title > svg { color: var(--accent); }
.graph-studio__subtitle {
  margin-top: var(--space-1);
  color: var(--text-muted);
  font-size: var(--text-sm);
}
.graph-studio__toolbar,
.graph-run-actions,
.graph-run-bar__controls,
.graph-node-inspector__actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.graph-studio__metrics {
  display: grid;
  grid-template-columns: repeat(5, minmax(130px, 1fr));
  gap: var(--space-3);
}
.graph-studio__workspace {
  display: grid;
  grid-template-columns: minmax(230px, 0.7fr) minmax(540px, 2fr) minmax(300px, 0.9fr);
  gap: var(--space-3);
  align-items: start;
}
.graph-studio__catalog,
.graph-studio__attention { display: grid; gap: var(--space-3); }
.graph-catalog { max-height: 310px; overflow-y: auto; }
.graph-catalog__item {
  width: 100%;
  min-height: 64px;
  display: grid;
  grid-template-columns: 8px minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3);
  color: var(--text);
  background: transparent;
  border: 0;
  border-bottom: 1px solid var(--border-subtle);
  text-align: left;
  cursor: pointer;
}
.graph-catalog__item:hover { background: var(--surface-soft); }
.graph-catalog__item.is-active {
  background: var(--accent-soft);
  box-shadow: inset 3px 0 0 var(--accent);
}
.graph-catalog__status {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text-faint);
}
.graph-catalog__status.is-valid { background: var(--status-ok); }
.graph-catalog__status.is-invalid { background: var(--status-risk); }
.graph-catalog__copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
  gap: 3px;
}
.graph-catalog__copy strong,
.graph-catalog__copy span,
.graph-run-bar__subject strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.graph-catalog__copy strong { color: var(--text); font-size: var(--text-sm); }
.graph-catalog__copy span { color: var(--text-muted); font-size: var(--text-xs); }
.graph-catalog__runs {
  min-width: 24px;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  text-align: right;
}
.graph-launch,
.graph-form { display: grid; gap: var(--space-3); }
.graph-loading,
.graph-error,
.graph-muted {
  padding: var(--space-4);
  color: var(--text-muted);
  font-size: var(--text-sm);
}
.graph-studio__run-panel > .aios-panel__header {
  align-items: flex-start;
  flex-wrap: wrap;
}
.graph-studio__run-panel > .aios-panel__header > .aios-panel__title {
  flex: 1 1 220px;
  overflow-wrap: anywhere;
  letter-spacing: 0;
}
.graph-studio__run-panel > .aios-panel__header > .aios-panel__actions {
  flex: 1 1 auto;
  max-width: 100%;
}
.graph-run-actions {
  max-width: 100%;
  justify-content: flex-end;
}
.graph-run-actions .aios-select {
  flex: 1 1 210px;
  min-width: 0;
  max-width: 100%;
}
.graph-run-bar {
  min-height: 62px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3);
  background: var(--bg-sunken);
  border-bottom: 1px solid var(--border-subtle);
}
.graph-run-bar__subject {
  display: flex;
  flex-direction: column;
  min-width: 0;
  gap: 3px;
}
.graph-run-bar__subject strong { color: var(--text); font-size: var(--text-sm); }
.graph-run-bar__subject span { color: var(--text-muted); font-size: var(--text-xs); }
.graph-canvas {
  height: 690px;
  overflow: auto;
  background-color: var(--bg-sunken);
  background-image:
    linear-gradient(var(--border-subtle) 1px, transparent 1px),
    linear-gradient(90deg, var(--border-subtle) 1px, transparent 1px);
  background-size: 28px 28px;
  border-bottom: 1px solid var(--border-subtle);
}
.graph-canvas svg {
  display: block;
  width: 100%;
  min-width: 720px;
  height: auto;
  min-height: 100%;
}
.graph-edge {
  fill: none;
  stroke: var(--border-strong);
  stroke-width: 2;
  opacity: 0.72;
}
.graph-edge--live { stroke: var(--status-ok); stroke-width: 3; opacity: 1; }
.graph-edge--skipped { stroke-dasharray: 7 6; opacity: 0.35; }
.graph-edge-arrow { fill: var(--border-strong); }
.graph-edge-arrow--live { fill: var(--status-ok); }
.graph-node { cursor: pointer; outline: none; }
.graph-node rect {
  fill: var(--surface);
  stroke: var(--border-strong);
  stroke-width: 1.5;
}
.graph-node:hover rect,
.graph-node:focus rect { stroke: var(--accent); }
.graph-node--selected rect { stroke: var(--accent); stroke-width: 3; }
.graph-node--running rect,
.graph-node--ready rect,
.graph-node--queued rect { stroke: var(--status-info); }
.graph-node--waiting-approval rect,
.graph-node--waiting-input rect,
.graph-node--paused rect { stroke: var(--status-warn); }
.graph-node--failed rect,
.graph-node--cancelled rect { stroke: var(--status-risk); }
.graph-node--completed rect { stroke: var(--status-ok); }
.graph-node__state { fill: var(--text-faint); }
.graph-node--running .graph-node__state,
.graph-node--ready .graph-node__state,
.graph-node--queued .graph-node__state { fill: var(--status-info); }
.graph-node--waiting-approval .graph-node__state,
.graph-node--waiting-input .graph-node__state,
.graph-node--paused .graph-node__state { fill: var(--status-warn); }
.graph-node--failed .graph-node__state,
.graph-node--cancelled .graph-node__state { fill: var(--status-risk); }
.graph-node--completed .graph-node__state { fill: var(--status-ok); }
.graph-node__type {
  fill: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 9px;
  text-transform: uppercase;
}
.graph-node__name {
  fill: var(--text);
  font-family: var(--font-sans);
  font-size: 12px;
  font-weight: 650;
}
.graph-node__owner {
  fill: var(--text-muted);
  font-family: var(--font-sans);
  font-size: 10px;
}
.graph-node-inspector {
  display: grid;
  grid-template-columns: minmax(180px, 0.8fr) minmax(320px, 1.4fr) auto;
  gap: var(--space-3);
  align-items: center;
  padding: var(--space-3);
  background: var(--surface);
}
.graph-node-inspector__identity { display: flex; align-items: center; gap: var(--space-2); }
.graph-node-inspector__state,
.graph-ledger__mark {
  flex: 0 0 auto;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-faint);
}
.tone-ok { background: var(--status-ok); }
.tone-risk { background: var(--status-risk); }
.tone-warn { background: var(--status-warn); }
.tone-info { background: var(--status-info); }
.graph-node-inspector__identity > div { display: flex; flex-direction: column; gap: 2px; }
.graph-node-inspector__identity strong { font-size: var(--text-sm); }
.graph-node-inspector__identity span { color: var(--text-muted); font-size: var(--text-xs); }
.graph-node-inspector__facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(110px, 1fr));
  gap: var(--space-2);
}
.graph-node-inspector__facts span {
  display: flex;
  flex-direction: column;
  min-width: 0;
  color: var(--text);
  font-size: var(--text-xs);
}
.graph-node-inspector__facts b { margin-bottom: 2px; color: var(--text-muted); font-weight: 500; }
.graph-node-inspector__evidence { grid-column: 1 / -1; border-top: 1px solid var(--border-subtle); padding-top: var(--space-2); }
.graph-node-inspector__evidence summary,
.graph-json summary { color: var(--accent); font-size: var(--text-xs); cursor: pointer; }
.graph-node-inspector__evidence pre,
.graph-json pre {
  max-height: 260px;
  overflow: auto;
  margin: var(--space-2) 0 0;
  padding: var(--space-3);
  background: var(--bg-sunken);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  white-space: pre-wrap;
}
.graph-attention-list { display: grid; gap: var(--space-3); }
.graph-attention-item {
  display: grid;
  gap: var(--space-2);
  padding: var(--space-3);
  border: 1px solid var(--border-subtle);
  border-left: 3px solid var(--status-info);
  border-radius: var(--radius-sm);
  background: var(--surface-soft);
}
.graph-attention-item--approval { border-left-color: var(--status-warn); }
.graph-attention-item__head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text);
  font-size: var(--text-sm);
}
.graph-attention-item__head strong { flex: 1; }
.graph-attention-item__meta,
.graph-attention-item__detail { color: var(--text-muted); font-size: var(--text-xs); }
.graph-attention-item__recommendation {
  padding: var(--space-2);
  background: var(--status-warn-soft);
  color: var(--text);
  font-size: var(--text-xs);
}
.graph-attention-item__actions,
.graph-attention-item__options { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.graph-attention-item__options button {
  padding: 5px 8px;
  color: var(--text-muted);
  background: var(--surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  cursor: pointer;
}
.graph-attention-item__options button.is-selected {
  color: var(--accent);
  border-color: var(--accent);
  background: var(--accent-soft);
}
.graph-safety { display: grid; gap: var(--space-2); margin: 0; }
.graph-safety > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--border-subtle);
}
.graph-safety dt { color: var(--text-muted); font-size: var(--text-xs); }
.graph-safety dd { margin: 0; color: var(--text); font-size: var(--text-xs); }
.graph-json { margin-top: var(--space-3); }
.graph-studio__lower {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(360px, 0.65fr);
  gap: var(--space-3);
  align-items: start;
}
.graph-ledger { max-height: 420px; overflow-y: auto; }
.graph-ledger__row {
  display: grid;
  grid-template-columns: 8px minmax(170px, 0.7fr) minmax(230px, 1.3fr);
  gap: var(--space-2);
  align-items: center;
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--border-subtle);
}
.graph-ledger__row > div { display: flex; flex-direction: column; gap: 2px; }
.graph-ledger__row strong { color: var(--text); font-size: var(--text-xs); }
.graph-ledger__row span { color: var(--text-muted); font-size: var(--text-2xs); }
.graph-ledger__row code {
  overflow: hidden;
  color: var(--text-muted);
  font-size: var(--text-2xs);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.graph-checkpoints {
  display: grid;
  gap: var(--space-1);
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-subtle);
}
.graph-checkpoints > div {
  display: grid;
  grid-template-columns: 18px 1fr auto auto;
  gap: var(--space-2);
  align-items: center;
  color: var(--text-muted);
  font-size: var(--text-xs);
}
.graph-form__row { display: grid; grid-template-columns: 150px minmax(0, 1fr); gap: var(--space-2); }
.graph-correction-list {
  display: grid;
  gap: var(--space-2);
  margin-top: var(--space-4);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-subtle);
}
.graph-correction-list > div {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--space-2);
  align-items: start;
}
.graph-correction-list span:nth-child(2) { color: var(--text); font-size: var(--text-xs); }
.graph-correction-list small { grid-column: 2; color: var(--text-muted); }
.graph-change {
  display: grid;
  grid-template-columns: minmax(220px, 0.8fr) minmax(260px, 1.2fr) minmax(260px, 1fr) minmax(260px, 1fr) auto;
  gap: var(--space-3);
  align-items: end;
}
.mono { font-family: var(--font-mono) !important; }

@media (max-width: 1550px) {
  .graph-studio__workspace { grid-template-columns: minmax(220px, 0.65fr) minmax(520px, 1.7fr); }
  .graph-studio__run-panel > .aios-panel__header {
    align-items: stretch;
    flex-direction: column;
  }
  .graph-studio__run-panel > .aios-panel__header > .aios-panel__title {
    flex: 0 1 auto;
  }
  .graph-studio__run-panel > .aios-panel__header > .aios-panel__actions,
  .graph-run-actions { width: 100%; }
  .graph-run-actions {
    display: grid;
    grid-template-columns: auto auto minmax(0, 1fr);
  }
  .graph-studio__attention {
    grid-column: 1 / -1;
    grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.6fr);
  }
  .graph-change { grid-template-columns: repeat(2, minmax(260px, 1fr)); }
}
@media (max-width: 1080px) {
  .graph-studio__header,
  .graph-run-bar { align-items: stretch; flex-direction: column; }
  .graph-studio__metrics { grid-template-columns: repeat(2, minmax(130px, 1fr)); }
  .graph-studio__workspace,
  .graph-studio__lower,
  .graph-studio__attention { grid-template-columns: 1fr; }
  .graph-studio__attention { grid-column: auto; }
  .graph-canvas { height: 610px; }
  .graph-node-inspector { grid-template-columns: 1fr; }
  .graph-change { grid-template-columns: 1fr; }
}
@media (max-width: 680px) {
  .graph-run-actions { grid-template-columns: 1fr 1fr; }
  .graph-run-actions .aios-select {
    grid-column: 1 / -1;
    width: 100%;
  }
  .graph-studio__toolbar,
  .graph-run-bar__controls { width: 100%; }
  .graph-studio__toolbar .aios-btn,
  .graph-run-bar__controls .aios-btn { flex: 1 1 auto; }
  .graph-studio__metrics { grid-template-columns: 1fr 1fr; }
  .graph-canvas { height: 540px; }
  .graph-form__row { grid-template-columns: 1fr; }
  .graph-ledger__row { grid-template-columns: 8px minmax(0, 1fr); }
  .graph-ledger__row code { grid-column: 2; }
}
`;
