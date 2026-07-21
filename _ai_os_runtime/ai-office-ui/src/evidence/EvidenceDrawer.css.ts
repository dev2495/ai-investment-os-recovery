export const EvidenceDrawerCss = `
.aios-evidence {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.aios-evidence__resolve {
  display: flex;
  gap: var(--space-2);
}

.aios-evidence__section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.aios-evidence__section-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.aios-evidence__section-head h4 {
  font-family: var(--font-sans);
  font-size: var(--text-xs);
  font-weight: var(--weight-semibold);
  text-transform: uppercase;
  letter-spacing: var(--tracking-caps);
  color: var(--text-muted);
}
.aios-evidence__generated {
  margin-left: auto;
  font-size: var(--text-xs);
  color: var(--text-faint);
}
.aios-evidence__count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  font-size: var(--text-2xs);
  font-weight: var(--weight-semibold);
  background: var(--surface-soft);
  color: var(--text-muted);
  border-radius: var(--radius-pill);
}

.aios-evidence__record-card {
  display: flex;
  flex-direction: column;
  background: var(--surface-soft);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.aios-evidence__kv {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
}
.aios-evidence__kv:last-child { border-bottom: none; }
.aios-evidence__kv-label {
  font-size: var(--text-xs);
  text-transform: capitalize;
  color: var(--text-muted);
}
.aios-evidence__kv-value {
  font-size: var(--text-sm);
  color: var(--text);
  font-weight: var(--weight-medium);
  text-align: right;
  max-width: 60%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.aios-evidence__group-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.aios-evidence__record-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: var(--surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}
.aios-evidence__record-row:hover {
  background: var(--surface-soft);
  border-color: var(--border);
}
.aios-evidence__record-row-main {
  flex: 1;
  min-width: 0;
}
.aios-evidence__record-row-title {
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.aios-evidence__record-row-meta {
  font-size: var(--text-xs);
  color: var(--text-muted);
  display: flex;
  gap: var(--space-1);
}
.aios-evidence__empty-group {
  padding: var(--space-3);
  font-size: var(--text-xs);
  color: var(--text-faint);
  text-align: center;
}

.aios-evidence__skeleton {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
`;
