export const LivingAgentPanelCss = `
.living-agent-panel {
  --agent-panel-bg: var(--surface);
  --agent-panel-raised: var(--surface-soft);
  --agent-panel-text: var(--text);
  --agent-panel-muted: var(--text-muted);
  --agent-panel-faint: var(--text-faint);
  --agent-panel-border: var(--border-subtle);
  --agent-panel-accent: var(--accent);
  width: 100%;
  display: grid;
  gap: var(--space-4);
  padding: var(--space-4);
  color: var(--agent-panel-text);
  background: var(--agent-panel-bg);
  border: 1px solid var(--agent-panel-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  outline: none;
}
.living-agent-panel--overlay {
  --agent-panel-bg: rgba(25, 22, 19, 0.97);
  --agent-panel-raised: rgba(242, 237, 229, 0.055);
  --agent-panel-text: #f2ede5;
  --agent-panel-muted: rgba(242, 237, 229, 0.66);
  --agent-panel-faint: rgba(242, 237, 229, 0.48);
  --agent-panel-border: rgba(232, 220, 200, 0.18);
  --agent-panel-accent: #64d1ba;
  max-width: 760px;
  box-shadow: 0 14px 42px rgba(0, 0, 0, 0.5);
  pointer-events: auto;
}
.living-agent-panel:focus-visible {
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--agent-panel-accent) 38%, transparent);
}
.living-agent-panel__head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-3);
  align-items: start;
}
.living-agent-panel__identity { min-width: 0; }
.living-agent-panel__eyebrow {
  color: var(--agent-panel-faint);
  font: 600 var(--text-2xs) var(--font-mono);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.living-agent-panel__name {
  margin: 3px 0 0;
  overflow: hidden;
  color: var(--agent-panel-text);
  font-family: var(--font-display);
  font-size: var(--text-xl);
  font-weight: 650;
  letter-spacing: -0.02em;
  text-overflow: ellipsis;
  text-wrap: balance;
}
.living-agent-panel__role {
  margin-top: 3px;
  color: var(--agent-panel-muted);
  font-size: var(--text-xs);
  text-wrap: pretty;
}
.living-agent-panel__head-actions { display: flex; gap: var(--space-2); align-items: center; }
.living-agent-panel__lease {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: var(--space-2);
  align-items: center;
  min-height: 36px;
  padding: 7px 10px;
  color: var(--agent-panel-muted);
  background: var(--agent-panel-raised);
  border-left: 3px solid var(--status-warn);
  font-size: var(--text-xs);
}
.living-agent-panel__lease.is-live { border-left-color: var(--status-ok); }
.living-agent-panel__lease.is-blocked,
.living-agent-panel__lease.is-stale { border-left-color: var(--status-risk); }
.living-agent-panel__lease strong { color: var(--agent-panel-text); }
.living-agent-panel__lease time { color: var(--agent-panel-faint); font-family: var(--font-mono); font-size: var(--text-2xs); }
.living-agent-panel__work {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(190px, 0.8fr);
  gap: var(--space-3);
}
.living-agent-panel__assignment,
.living-agent-panel__progress-block {
  min-width: 0;
  padding: var(--space-3);
  background: var(--agent-panel-raised);
}
.living-agent-panel__label {
  display: block;
  color: var(--agent-panel-faint);
  font: 600 var(--text-2xs) var(--font-mono);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.living-agent-panel__assignment strong {
  display: block;
  margin-top: 5px;
  overflow: hidden;
  font-size: var(--text-sm);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.living-agent-panel__assignment p {
  margin: 4px 0 0;
  color: var(--agent-panel-muted);
  font-size: var(--text-xs);
  line-height: 1.45;
  text-wrap: pretty;
}
.living-agent-panel__progress-head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-2);
  color: var(--agent-panel-muted);
  font-size: var(--text-xs);
}
.living-agent-panel__progress-head strong { color: var(--agent-panel-text); font-variant-numeric: tabular-nums; }
.living-agent-panel__progress {
  height: 4px;
  margin-top: 9px;
  overflow: hidden;
  background: color-mix(in srgb, var(--agent-panel-muted) 18%, transparent);
  border-radius: 999px;
}
.living-agent-panel__progress span { display: block; height: 100%; background: var(--agent-panel-accent); }
.living-agent-panel__progress-meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2);
  margin-top: 9px;
  color: var(--agent-panel-faint);
  font-size: var(--text-2xs);
}
.living-agent-panel__progress-meta b { display: block; margin-top: 2px; color: var(--agent-panel-text); font-size: var(--text-xs); font-weight: 600; }
.living-agent-panel__facts {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  border-top: 1px solid var(--agent-panel-border);
  border-bottom: 1px solid var(--agent-panel-border);
}
.living-agent-panel__fact {
  min-width: 0;
  padding: var(--space-3);
  border-right: 1px solid var(--agent-panel-border);
}
.living-agent-panel__fact:nth-child(4n) { border-right: 0; }
.living-agent-panel__fact:nth-child(n + 5) { border-top: 1px solid var(--agent-panel-border); }
.living-agent-panel__fact b {
  display: block;
  margin-top: 4px;
  overflow: hidden;
  color: var(--agent-panel-text);
  font-size: var(--text-xs);
  font-weight: 600;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.living-agent-panel__fact b.is-missing { color: var(--agent-panel-faint); font-weight: 500; }
.living-agent-panel__sections { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-2) var(--space-3); }
.living-agent-panel__section { border-bottom: 1px solid var(--agent-panel-border); }
.living-agent-panel__section summary {
  min-height: 40px;
  display: flex;
  justify-content: space-between;
  gap: var(--space-2);
  align-items: center;
  color: var(--agent-panel-text);
  cursor: pointer;
  font-size: var(--text-xs);
  font-weight: 600;
  list-style: none;
}
.living-agent-panel__section summary::-webkit-details-marker { display: none; }
.living-agent-panel__section summary span { color: var(--agent-panel-faint); font: 500 var(--text-2xs) var(--font-mono); }
.living-agent-panel__records { display: grid; gap: 6px; padding: 0 0 var(--space-3); }
.living-agent-panel__record { min-width: 0; color: var(--agent-panel-muted); font-size: var(--text-xs); line-height: 1.4; }
.living-agent-panel__record strong { color: var(--agent-panel-text); }
.living-agent-panel__record time { margin-left: 5px; color: var(--agent-panel-faint); font: var(--text-2xs) var(--font-mono); }
.living-agent-panel__empty { color: var(--agent-panel-faint); font-size: var(--text-xs); }
.living-agent-panel__actions { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.living-agent-panel--overlay .aios-btn:not(.aios-btn--primary) { color: var(--agent-panel-text); background: var(--agent-panel-raised); border-color: var(--agent-panel-border); }
.living-agent-panel__delegate { display: grid; gap: var(--space-2); }
.living-agent-panel__delegate textarea {
  width: 100%;
  min-height: 84px;
  resize: vertical;
  padding: var(--space-3);
  color: var(--agent-panel-text);
  background: var(--agent-panel-raised);
  border: 1px solid var(--agent-panel-border);
  border-radius: var(--radius-sm);
  font: inherit;
}
.living-agent-panel__delegate textarea:focus-visible { outline: 2px solid var(--agent-panel-accent); outline-offset: 2px; }
.living-agent-panel[data-low-power="true"] .living-agent-panel__progress span { transition: none; }
@media (prefers-reduced-motion: reduce) {
  .living-agent-panel *, .living-agent-panel *::before, .living-agent-panel *::after { animation: none !important; scroll-behavior: auto !important; transition-duration: 0.01ms !important; }
}
@media (max-width: 720px) {
  .living-agent-panel { gap: var(--space-3); padding: var(--space-3); }
  .living-agent-panel__head { grid-template-columns: 1fr; }
  .living-agent-panel__head-actions { justify-content: space-between; }
  .living-agent-panel__work { grid-template-columns: 1fr; }
  .living-agent-panel__facts { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .living-agent-panel__fact:nth-child(4n) { border-right: 1px solid var(--agent-panel-border); }
  .living-agent-panel__fact:nth-child(2n) { border-right: 0; }
  .living-agent-panel__fact:nth-child(n + 3) { border-top: 1px solid var(--agent-panel-border); }
  .living-agent-panel__sections { grid-template-columns: 1fr; }
}
`;
