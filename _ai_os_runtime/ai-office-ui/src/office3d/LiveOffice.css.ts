export const LiveOfficeCss = `
.office-canvas-wrap {
  position: relative;
  width: 100%;
  background: linear-gradient(180deg, #2a2218 0%, #16110d 100%);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

/* Floating room labels (rendered in 3D via Drei <Html>) */
.office-room-label {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 6px 12px;
  background: rgba(34, 28, 22, 0.92);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(232, 220, 200, 0.15);
  border-radius: var(--radius-md);
  color: #f2ede5;
  font-family: var(--font-sans);
  white-space: nowrap;
  pointer-events: none;
  transform: translateY(-8px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
  transition: all var(--duration-fast) var(--ease-out);
}
.office-room-label--active {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px var(--accent-soft-strong), 0 8px 24px rgba(0, 0, 0, 0.5);
  transform: translateY(-8px) scale(1.05);
}
.office-room-label--risk {
  border-color: var(--status-risk);
  background: rgba(60, 20, 15, 0.92);
}
.office-room-label__name {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: -0.01em;
}
.office-room-label__meta {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  color: rgba(232, 220, 200, 0.7);
}
.office-room-label__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.office-room-label__dot--ok { background: #3d9a6f; }
.office-room-label__dot--risk {
  background: #e5564e;
  animation: aios-risk-pulse 1.4s ease-in-out infinite;
}
.office-room-label__pending { color: var(--status-warn); }

/* HUD overlay */
.office-hud {
  position: absolute;
  inset: 0;
  pointer-events: none;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: var(--space-4);
}
.office-hud__top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}
.office-hud__title {
  font-family: var(--font-display);
  font-size: var(--text-lg);
  font-weight: 600;
  color: rgba(242, 237, 229, 0.95);
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.6);
}
.office-hud__hint {
  font-size: var(--text-xs);
  color: rgba(242, 237, 229, 0.6);
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.6);
}
.office-hud__bottom {
  display: flex;
  justify-content: center;
}
.office-hud__room-card {
  pointer-events: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-4) var(--space-5);
  background: rgba(34, 28, 22, 0.95);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(232, 220, 200, 0.15);
  border-radius: var(--radius-lg);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5);
  min-width: 280px;
}
.office-hud__room-name {
  font-family: var(--font-display);
  font-size: var(--text-xl);
  font-weight: 600;
  color: #f2ede5;
}
.office-hud__room-dept {
  font-size: var(--text-sm);
  color: rgba(242, 237, 229, 0.7);
  text-align: center;
}
.office-hud__room-actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-2);
}
.office-hud__btn {
  padding: 6px 14px;
  font-size: var(--text-sm);
  font-weight: 500;
  color: rgba(242, 237, 229, 0.85);
  background: rgba(232, 220, 200, 0.08);
  border: 1px solid rgba(232, 220, 200, 0.15);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}
.office-hud__btn:hover {
  background: rgba(232, 220, 200, 0.15);
}
.office-hud__btn--primary {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
.office-hud__btn--primary:hover {
  background: var(--accent-hover);
}
.office-hud__lobby-hint {
  font-size: var(--text-sm);
  color: rgba(242, 237, 229, 0.6);
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.6);
}

/* Fallback (no WebGL) */
.office-fallback {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  overflow: auto;
}
.office-fallback__inner {
  max-width: 800px;
  margin: 0 auto;
}
.office-fallback__title {
  font-family: var(--font-display);
  font-size: var(--text-2xl);
  font-weight: 600;
  margin-bottom: var(--space-1);
}
.office-fallback__sub {
  color: var(--text-muted);
  margin-bottom: var(--space-5);
}
.office-fallback__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--space-3);
}
.office-fallback__room {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-3);
  text-align: left;
  background: var(--surface-soft);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}
.office-fallback__room:hover {
  border-color: var(--border-strong);
  background: var(--surface);
}
.office-fallback__room--active {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.office-fallback__room-name {
  font-weight: 600;
  font-size: var(--text-sm);
  color: var(--text);
}
.office-fallback__room-dept {
  font-size: var(--text-xs);
  color: var(--text-muted);
}
.office-fallback__room-floor {
  font-size: var(--text-2xs);
  text-transform: uppercase;
  letter-spacing: var(--tracking-caps);
  color: var(--text-faint);
  margin-top: var(--space-1);
}
`;
