export const LiveOfficeCss = `
.office-spatial-shell {
  width: 100%;
  min-height: 520px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #17130f;
  border-radius: var(--radius-md);
  outline: none;
}
.office-spatial-shell:focus-visible {
  box-shadow: 0 0 0 3px rgba(100, 209, 186, 0.42);
}
.office-spatial-toolbar {
  position: relative;
  z-index: 40;
  display: grid;
  grid-template-columns: minmax(170px, 0.8fr) minmax(280px, 1.4fr) auto;
  gap: var(--space-3);
  align-items: center;
  padding: 10px 12px;
  color: #f2ede5;
  background: #211c17;
  border-bottom: 1px solid rgba(232, 220, 200, 0.18);
}
.office-spatial-toolbar__identity {
  display: grid;
  gap: 2px;
  min-width: 0;
}
.office-spatial-toolbar__identity strong {
  font-family: var(--font-display);
  font-size: var(--text-md);
}
.office-spatial-toolbar__identity span {
  overflow: hidden;
  color: rgba(242, 237, 229, 0.58);
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.office-spatial-toolbar__status,
.office-spatial-toolbar__controls {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.office-spatial-toolbar__status span {
  padding: 4px 7px;
  color: rgba(242, 237, 229, 0.72);
  background: rgba(242, 237, 229, 0.06);
  border: 1px solid rgba(242, 237, 229, 0.1);
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 9px;
  text-transform: uppercase;
}
.office-spatial-toolbar__status .office-signal--fresh { color: #8ed9b6; border-color: rgba(72, 168, 121, 0.38); }
.office-spatial-toolbar__status .office-signal--partial,
.office-spatial-toolbar__status .office-signal--stale { color: #efc45c; border-color: rgba(215, 165, 54, 0.42); }
.office-spatial-toolbar__status .office-signal--error { color: #f08c84; border-color: rgba(217, 86, 76, 0.46); }
.office-spatial-toolbar__status .office-safety-lock { color: #f2cf86; border-color: rgba(242, 207, 134, 0.35); }
.office-spatial-toolbar__controls { justify-content: flex-end; }
.office-spatial-toolbar__controls button,
.office-projection-state button {
  padding: 5px 8px;
  color: rgba(242, 237, 229, 0.82);
  background: rgba(242, 237, 229, 0.07);
  border: 1px solid rgba(242, 237, 229, 0.16);
  border-radius: 4px;
  font: 550 10px var(--font-sans);
  cursor: pointer;
}
.office-spatial-toolbar__controls button:hover,
.office-projection-state button:hover { background: rgba(242, 237, 229, 0.14); }
.office-spatial-toolbar__controls button:focus-visible,
.office-projection-state button:focus-visible,
.office-hud__btn:focus-visible,
.office-fallback button:focus-visible {
  outline: 2px solid #64d1ba;
  outline-offset: 2px;
}
.office-spatial-toolbar__controls button:disabled { cursor: not-allowed; opacity: 0.48; }
.office-projection-state {
  flex: 1;
  min-height: 360px;
  display: grid;
  place-content: center;
  gap: 8px;
  padding: var(--space-6);
  color: rgba(242, 237, 229, 0.7);
  text-align: center;
}
.office-projection-state strong { color: #f2ede5; font-family: var(--font-display); font-size: var(--text-lg); }
.office-projection-state button { justify-self: center; margin-top: 6px; }
.office-projection-state--error strong { color: #f08c84; }
.office-spatial-help {
  position: relative;
  z-index: 40;
  margin: 0;
  padding: 6px 12px;
  color: rgba(242, 237, 229, 0.5);
  background: #211c17;
  border-top: 1px solid rgba(232, 220, 200, 0.12);
  font: 9px var(--font-mono);
  text-align: center;
}
.office-canvas-wrap {
  position: relative;
  width: 100%;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  background: #17130f;
  border-radius: var(--radius-md);
}
.office-room-label {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 6px 10px;
  color: #f2ede5;
  background: rgba(28, 24, 20, 0.94);
  border: 1px solid rgba(232, 220, 200, 0.2);
  border-radius: 6px;
  box-shadow: 0 5px 18px rgba(0, 0, 0, 0.42);
  font-family: var(--font-sans);
  letter-spacing: 0;
  pointer-events: none;
  white-space: nowrap;
  transform: translateY(-8px);
}
.office-room-label--active {
  border-color: #58c7b4;
  box-shadow: 0 0 0 2px rgba(88, 199, 180, 0.22), 0 7px 22px rgba(0, 0, 0, 0.48);
}
.office-room-label--risk {
  background: rgba(57, 20, 17, 0.96);
  border-color: #e05c52;
}
.office-room-label__name { font-size: 12px; font-weight: 650; }
.office-room-label__meta {
  display: flex;
  align-items: center;
  gap: 5px;
  color: rgba(242, 237, 229, 0.72);
  font-size: 9px;
}
.office-room-label__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.office-room-label__dot--ok { background: #48a879; }
.office-room-label__dot--risk { background: #e05c52; animation: aios-risk-pulse 1.4s ease-in-out infinite; }
.office-room-label__pending { color: #efc45c; }
.office-room-label__gated {
  color: #efc45c;
  font: 8px var(--font-mono);
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.office-agent-popover {
  width: 220px;
  padding: 9px 10px;
  color: #f2ede5;
  background: rgba(21, 19, 17, 0.97);
  border: 1px solid rgba(242, 237, 229, 0.2);
  border-left: 3px solid #48a879;
  border-radius: 6px;
  box-shadow: 0 9px 28px rgba(0, 0, 0, 0.54);
  font-family: var(--font-sans);
  letter-spacing: 0;
  pointer-events: none;
}
.office-agent-popover--blocked { border-left-color: #e05c52; }
.office-agent-popover__head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
}
.office-agent-popover__head strong {
  overflow: hidden;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.office-agent-popover__head span {
  color: #8ed9b6;
  font-family: var(--font-mono);
  font-size: 8px;
  text-transform: uppercase;
}
.office-agent-popover__title {
  margin-top: 3px;
  color: rgba(242, 237, 229, 0.66);
  font-size: 9px;
}
.office-agent-popover__work {
  margin-top: 6px;
  color: rgba(242, 237, 229, 0.92);
  font-size: 10px;
  line-height: 1.35;
}

.office-hud {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: var(--space-4);
  pointer-events: none;
}
.office-hud__top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-3);
}
.office-hud__title {
  color: rgba(246, 241, 232, 0.97);
  font-family: var(--font-display);
  font-size: var(--text-lg);
  font-weight: 650;
  letter-spacing: 0;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.62);
}
.office-hud__hint {
  margin-top: 3px;
  color: rgba(246, 241, 232, 0.64);
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.68);
}
.office-hud__activity {
  width: min(560px, 58vw);
  display: grid;
  gap: 3px;
  margin-top: 8px;
}
.office-hud__activity > button {
  display: grid;
  grid-template-columns: minmax(90px, 0.6fr) minmax(140px, 1fr) auto;
  gap: 8px;
  align-items: center;
  padding: 4px 7px;
  color: rgba(246, 241, 232, 0.7);
  background: rgba(22, 19, 16, 0.78);
  border-left: 2px solid rgba(100, 209, 186, 0.7);
  width: 100%;
  font-size: 9px;
  text-align: left;
  cursor: pointer;
}
.office-hud__activity > button:disabled { cursor: not-allowed; opacity: 0.68; }
.office-hud__activity span,
.office-hud__activity b {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.office-hud__activity b { color: rgba(246, 241, 232, 0.92); font-weight: 550; }
.office-hud__activity time { color: rgba(246, 241, 232, 0.5); font-family: var(--font-mono); white-space: nowrap; }
.office-hud__legend {
  display: flex;
  gap: var(--space-3);
  padding: 7px 10px;
  color: rgba(246, 241, 232, 0.75);
  background: rgba(22, 19, 16, 0.82);
  border: 1px solid rgba(246, 241, 232, 0.14);
  border-radius: 6px;
  font-size: 10px;
}
.office-hud__legend span { display: inline-flex; align-items: center; gap: 5px; }
.office-hud__legend i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #8b8278;
}
.office-hud__legend i.is-working { background: #48a879; }
.office-hud__legend i.is-waiting { background: #d7a536; }
.office-hud__legend i.is-blocked { background: #d9564c; }
.office-hud__bottom { display: flex; justify-content: center; }
.office-hud__room-card,
.office-hud__agent-card {
  min-width: 310px;
  max-width: 560px;
  padding: var(--space-3) var(--space-4);
  color: #f2ede5;
  background: rgba(25, 22, 19, 0.96);
  border: 1px solid rgba(232, 220, 200, 0.2);
  border-radius: 8px;
  box-shadow: 0 12px 38px rgba(0, 0, 0, 0.52);
  pointer-events: auto;
}
.office-hud__room-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
}
.office-hud__room-name {
  font-family: var(--font-display);
  font-size: var(--text-lg);
  font-weight: 650;
}
.office-hud__room-dept {
  color: rgba(242, 237, 229, 0.68);
  font-size: var(--text-xs);
  text-align: center;
}
.office-hud__room-work {
  width: 100%;
  display: grid;
  gap: 4px;
}
.office-hud__room-work span {
  display: grid;
  grid-template-columns: minmax(100px, 0.6fr) minmax(150px, 1.4fr);
  gap: 8px;
  color: rgba(242, 237, 229, 0.64);
  font-size: 10px;
}
.office-hud__room-work b {
  overflow: hidden;
  color: rgba(242, 237, 229, 0.9);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.office-hud__agent-card { display: grid; gap: var(--space-2); }
.office-hud__agent-head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
}
.office-hud__agent-head > div { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.office-hud__agent-head strong {
  overflow: hidden;
  font-family: var(--font-display);
  font-size: var(--text-lg);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.office-hud__agent-head > div span { color: rgba(242, 237, 229, 0.65); font-size: 10px; }
.office-hud__state {
  align-self: flex-start;
  padding: 3px 7px;
  color: rgba(242, 237, 229, 0.74);
  background: rgba(242, 237, 229, 0.08);
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 9px;
  text-transform: uppercase;
}
.office-hud__state.is-working { color: #8ed9b6; background: rgba(72, 168, 121, 0.14); }
.office-hud__state.is-blocked { color: #f08c84; background: rgba(217, 86, 76, 0.14); }
.office-hud__work {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 8px 0;
  border-top: 1px solid rgba(242, 237, 229, 0.11);
  border-bottom: 1px solid rgba(242, 237, 229, 0.11);
}
.office-hud__work b { font-size: var(--text-xs); }
.office-hud__work span {
  overflow: hidden;
  color: rgba(242, 237, 229, 0.62);
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.office-hud__agent-facts {
  display: grid;
  grid-template-columns: auto auto minmax(130px, 1fr);
  gap: var(--space-3);
  color: rgba(242, 237, 229, 0.58);
  font-size: 10px;
}
.office-hud__agent-facts span { display: flex; gap: 4px; min-width: 0; }
.office-hud__agent-facts b {
  overflow: hidden;
  color: rgba(242, 237, 229, 0.9);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.office-hud__workspace-gate {
  width: 100%;
  padding: 7px 9px;
  color: #efc45c;
  background: rgba(215, 165, 54, 0.08);
  border: 1px solid rgba(215, 165, 54, 0.22);
  border-radius: 4px;
  font-size: 10px;
  text-align: left;
}
.office-hud__room-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--space-2);
  margin-top: var(--space-1);
}
.office-hud__btn {
  padding: 6px 12px;
  color: rgba(242, 237, 229, 0.84);
  background: rgba(232, 220, 200, 0.08);
  border: 1px solid rgba(232, 220, 200, 0.17);
  border-radius: 5px;
  font-size: var(--text-xs);
  font-weight: 550;
  cursor: pointer;
}
.office-hud__btn:hover { background: rgba(232, 220, 200, 0.15); }
.office-hud__btn--primary { color: #081b17; background: #64d1ba; border-color: #64d1ba; }
.office-hud__btn--primary:hover { background: #7bdbc7; }
.office-hud__lobby-hint {
  padding: 7px 12px;
  color: rgba(242, 237, 229, 0.68);
  background: rgba(22, 19, 16, 0.78);
  border: 1px solid rgba(242, 237, 229, 0.12);
  border-radius: 5px;
  font-size: var(--text-xs);
}

.office-fallback {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: var(--space-5);
  background: var(--bg-sunken);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}
.office-fallback__inner { max-width: 1100px; margin: 0 auto; }
.office-fallback__title {
  color: var(--text);
  font-family: var(--font-display);
  font-size: var(--text-xl);
  font-weight: 650;
  letter-spacing: 0;
}
.office-fallback__sub { margin: 4px 0 var(--space-4); color: var(--text-muted); font-size: var(--text-sm); }
.office-fallback__selected {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-4);
  align-items: center;
  margin-bottom: var(--space-4);
  padding: var(--space-3) var(--space-4);
  color: #f2ede5;
  background: #211d19;
  border: 1px solid rgba(232, 220, 200, 0.2);
  border-radius: var(--radius-md);
}
.office-fallback__selected > div:first-child { display: grid; gap: 2px; min-width: 0; }
.office-fallback__selected strong { font-family: var(--font-display); font-size: var(--text-lg); }
.office-fallback__selected span,
.office-fallback__selected small { overflow: hidden; color: rgba(242, 237, 229, 0.65); text-overflow: ellipsis; white-space: nowrap; }
.office-fallback__selected b { margin-top: 5px; font-size: var(--text-xs); }
.office-fallback__selected .office-hud__room-actions { margin: 0; }
.office-fallback__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(225px, 1fr));
  gap: var(--space-3);
}
.office-fallback__room {
  overflow: hidden;
  background: var(--surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
}
.office-fallback__room--active { border-color: var(--accent); box-shadow: inset 3px 0 0 var(--accent); }
.office-fallback__room-button {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: var(--space-3);
  color: var(--text);
  background: transparent;
  border: 0;
  text-align: left;
  cursor: pointer;
}
.office-fallback__room-button:hover { background: var(--surface-soft); }
.office-fallback__room-name { font-size: var(--text-sm); font-weight: 650; }
.office-fallback__room-dept { color: var(--text-muted); font-size: var(--text-xs); }
.office-fallback__room-floor {
  margin-top: 3px;
  color: var(--text-faint);
  font-size: var(--text-2xs);
  text-transform: uppercase;
}
.office-fallback__agent {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 7px var(--space-3);
  color: var(--text);
  background: var(--bg-sunken);
  border: 0;
  border-top: 1px solid var(--border-subtle);
  text-align: left;
  cursor: pointer;
}
.office-fallback__agent:hover { color: var(--accent); }
.office-fallback__agent small {
  overflow: hidden;
  color: var(--text-muted);
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (prefers-reduced-motion: reduce) {
  .office-room-label__dot--risk { animation: none; }
}
@media (max-width: 850px) {
  .office-spatial-shell { min-height: 620px; }
  .office-spatial-toolbar { grid-template-columns: 1fr; align-items: start; }
  .office-spatial-toolbar__controls { justify-content: flex-start; }
  .office-spatial-toolbar__status { overflow-x: auto; flex-wrap: nowrap; padding-bottom: 2px; }
  .office-spatial-toolbar__status span { flex: 0 0 auto; }
  .office-spatial-help { text-align: left; }
  .office-hud { padding: var(--space-2); }
  .office-hud__activity { display: none; }
  .office-hud__legend { display: none; }
  .office-hud__room-card,
  .office-hud__agent-card { width: min(100%, 520px); min-width: 0; }
  .office-hud__agent-facts { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .office-hud__agent-facts span:last-child { grid-column: 1 / -1; }
  .office-fallback__selected { grid-template-columns: 1fr; }
  .office-fallback__selected .office-hud__room-actions { justify-content: flex-start; }
}
`;
