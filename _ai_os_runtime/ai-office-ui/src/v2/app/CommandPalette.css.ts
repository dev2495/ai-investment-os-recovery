export const CommandPaletteCss = `
.aios-palette-overlay {
  position: fixed;
  inset: 0;
  background: rgba(20, 14, 8, 0.45);
  backdrop-filter: blur(4px);
  z-index: var(--z-palette);
  opacity: 0;
  animation: aios-fade-in var(--duration-base) var(--ease-out) forwards;
}

.aios-palette {
  position: fixed;
  top: 12vh;
  left: 50%;
  transform: translateX(-50%);
  width: 640px;
  max-width: calc(100vw - var(--space-8));
  max-height: 70vh;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-5);
  z-index: var(--z-palette);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transform-origin: top center;
  animation: aios-palette-in var(--duration-base) var(--ease-spring);
}

@keyframes aios-palette-in {
  from { opacity: 0; transform: translateX(-50%) translateY(-8px) scale(0.98); }
  to { opacity: 1; transform: translateX(-50%) translateY(0) scale(1); }
}

.aios-palette__input-wrap {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border);
}
.aios-palette__input-icon { color: var(--text-muted); flex-shrink: 0; }
.aios-palette__input {
  flex: 1;
  font-size: var(--text-lg);
  color: var(--text);
  background: transparent;
  border: none;
  outline: none;
}
.aios-palette__input::placeholder { color: var(--text-faint); }
.aios-palette__esc {
  font-family: var(--font-mono);
  font-size: 10px;
  padding: 2px 6px;
  color: var(--text-muted);
  background: var(--bg-sunken);
  border: 1px solid var(--border);
  border-radius: var(--radius-xs);
}

.aios-palette__list {
  flex: 1;
  overflow: auto;
  padding: var(--space-2);
}

.aios-palette__empty {
  padding: var(--space-8);
  text-align: center;
  color: var(--text-muted);
  font-size: var(--text-sm);
}

.aios-palette__group {
  padding: var(--space-1) 0;
}
.aios-palette__group [cmdk-group-heading] {
  padding: var(--space-2) var(--space-3) var(--space-1);
  font-size: var(--text-2xs);
  font-weight: var(--weight-semibold);
  text-transform: uppercase;
  letter-spacing: var(--tracking-caps);
  color: var(--text-faint);
}

.aios-palette__item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--text-secondary);
  transition: background var(--duration-fast) var(--ease-out);
}
.aios-palette__item:hover,
.aios-palette__item[aria-selected="true"],
.aios-palette__item[data-selected="true"] {
  background: var(--accent-soft);
  color: var(--accent);
}
.aios-palette__item-label {
  font-size: var(--text-md);
  font-weight: var(--weight-medium);
  color: inherit;
}
.aios-palette__item-desc {
  font-size: var(--text-xs);
  color: var(--text-muted);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.aios-palette__item-arrow {
  color: var(--text-faint);
  opacity: 0;
}
.aios-palette__item:hover .aios-palette__item-arrow,
.aios-palette__item[aria-selected="true"] .aios-palette__item-arrow {
  opacity: 1;
}
.aios-palette__item--charlie {
  border-top: 1px solid var(--border-subtle);
  margin-top: var(--space-2);
  padding-top: var(--space-3);
}
.aios-palette__charlie-q {
  color: var(--text);
  font-style: italic;
}
`;
