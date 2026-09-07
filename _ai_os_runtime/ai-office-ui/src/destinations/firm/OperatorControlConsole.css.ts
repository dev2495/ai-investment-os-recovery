export const OperatorControlConsoleCss = `
.operator-console { display: grid; gap: var(--space-4); }
.operator-console__summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: var(--space-3);
}
.operator-console__notice {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: var(--space-3);
  align-items: center;
  padding: var(--space-3);
  color: var(--text-muted);
  background: var(--surface-soft);
  border: 1px solid var(--border-subtle);
  border-left: 3px solid var(--status-warn);
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
}
.operator-console__notice.is-ready { border-left-color: var(--status-ok); }
.operator-console__notice.is-risk { border-left-color: var(--status-risk); }
.operator-console__notice strong { display: block; margin-bottom: 2px; color: var(--text); }
.operator-console__notice code { color: var(--text-muted); font-family: var(--font-mono); font-size: var(--text-2xs); }
.operator-console__history-note { padding: var(--space-3); color: var(--text-muted); background: var(--surface-soft); border-bottom: 1px solid var(--border-subtle); font-size: var(--text-xs); line-height: 1.5; }
.operator-console__bindings { display: grid; gap: 1px; background: var(--border-subtle); }
.operator-console__binding {
  display: grid;
  grid-template-columns: minmax(170px, 1.1fr) minmax(190px, 1.25fr) minmax(140px, .8fr) auto;
  gap: var(--space-3);
  align-items: center;
  padding: var(--space-3);
  background: var(--surface);
}
.operator-console__binding strong { display: block; color: var(--text); font-size: var(--text-sm); }
.operator-console__binding small { display: block; margin-top: 3px; color: var(--text-muted); font-size: var(--text-xs); }
.operator-console__route { font-family: var(--font-mono); overflow-wrap: anywhere; }
.operator-console__actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: var(--space-2); }
.operator-console__checks { display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: var(--space-3); padding: var(--space-3); }
.operator-console__check {
  display: grid;
  gap: var(--space-2);
  min-width: 0;
  padding: var(--space-3);
  background: var(--surface-soft);
  border: 1px solid var(--border-subtle);
  border-top: 3px solid var(--status-warn);
  border-radius: var(--radius-md);
}
.operator-console__check.is-passed { border-top-color: var(--status-ok); }
.operator-console__check.is-failed { border-top-color: var(--status-risk); }
.operator-console__check-head { display: flex; justify-content: space-between; gap: var(--space-2); align-items: flex-start; }
.operator-console__check h4 { margin: 0; color: var(--text); font-size: var(--text-sm); }
.operator-console__check p { margin: 0; color: var(--text-muted); font-size: var(--text-xs); line-height: 1.5; }
.operator-console__facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-2); }
.operator-console__fact { min-width: 0; padding-top: var(--space-2); border-top: 1px solid var(--border-subtle); }
.operator-console__fact span { display: block; color: var(--text-faint); font: 600 var(--text-2xs) var(--font-mono); text-transform: uppercase; letter-spacing: .05em; }
.operator-console__fact b { display: block; margin-top: 3px; overflow: hidden; color: var(--text); font-size: var(--text-xs); text-overflow: ellipsis; white-space: nowrap; }
.operator-console__routines { display: grid; grid-template-columns: repeat(auto-fill, minmax(310px, 1fr)); gap: var(--space-3); padding: var(--space-3); }
.operator-console__routine {
  display: grid;
  gap: var(--space-3);
  min-width: 0;
  padding: var(--space-3);
  background: var(--surface-soft);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
}
.operator-console__routine-head { display: flex; justify-content: space-between; gap: var(--space-2); align-items: flex-start; }
.operator-console__routine h4 { margin: 0; color: var(--text); font-size: var(--text-sm); }
.operator-console__routine p { margin: 3px 0 0; color: var(--text-muted); font-size: var(--text-xs); line-height: 1.45; }
.operator-console__receipt { padding: var(--space-3); color: var(--text-muted); background: var(--surface-soft); border: 1px solid var(--border-subtle); font-size: var(--text-xs); line-height: 1.5; }
.operator-console__receipt strong { color: var(--text); }
.operator-console__form { display: grid; gap: var(--space-4); }
.operator-console__form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-3); }
.operator-console__warning { padding: var(--space-3); color: var(--status-warn); background: var(--surface-soft); border-left: 3px solid var(--status-warn); font-size: var(--text-xs); line-height: 1.5; }
.operator-console__empty { padding: var(--space-5); text-align: center; color: var(--text-muted); font-size: var(--text-sm); }
@media (prefers-reduced-motion: reduce) {
  .operator-console *, .operator-console *::before, .operator-console *::after { animation: none !important; scroll-behavior: auto !important; transition-duration: .01ms !important; }
  .operator-console .aios-drawer { transform: none; }
}
@media (max-width: 760px) {
  .operator-console__binding { grid-template-columns: 1fr; }
  .operator-console__actions { justify-content: flex-start; }
  .operator-console__notice { grid-template-columns: 1fr; }
  .operator-console__form-grid { grid-template-columns: 1fr; }
}
`;
