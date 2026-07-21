export const AssistantRailCss = `
.aios-assistant {
  width: var(--assistant-width);
  flex-shrink: 0;
  height: 100%;
  background: var(--surface);
  border-left: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  z-index: var(--z-assistant);
}

/* Header */
.aios-assistant__head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-4) var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
}
.aios-assistant__identity {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex: 1;
}
.aios-assistant__avatar {
  position: relative;
  width: 40px;
  height: 40px;
  border-radius: var(--radius-circle);
  background: var(--accent);
  color: var(--text-on-accent);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: var(--weight-semibold);
  font-size: var(--text-md);
  letter-spacing: var(--tracking-tight);
}
.aios-assistant__avatar-status {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 11px;
  height: 11px;
  border-radius: var(--radius-circle);
  background: var(--status-ok);
  border: 2px solid var(--surface);
}
.aios-assistant__name {
  font-family: var(--font-display);
  font-size: var(--text-lg);
  font-weight: var(--weight-semibold);
  color: var(--text);
  line-height: 1.2;
}
.aios-assistant__role {
  font-size: var(--text-xs);
  color: var(--text-muted);
}
.aios-assistant__collapse {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  color: var(--text-muted);
  border-radius: var(--radius-sm);
  transition: all var(--duration-fast) var(--ease-out);
  cursor: pointer;
}
.aios-assistant__collapse:hover {
  background: var(--surface-soft);
  color: var(--text);
}

/* Context strip */
.aios-assistant__context {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  background: var(--surface-soft);
  border-bottom: 1px solid var(--border-subtle);
}
.aios-assistant__context-dest {
  font-size: var(--text-xs);
  font-weight: var(--weight-medium);
  color: var(--accent);
}

/* Messages */
.aios-assistant__messages {
  flex: 1;
  overflow: auto;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.aios-assistant__welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: var(--space-6) var(--space-4);
  gap: var(--space-2);
  color: var(--text-muted);
}
.aios-assistant__welcome > svg {
  color: var(--accent);
  margin-bottom: var(--space-2);
}
.aios-assistant__welcome-title {
  font-family: var(--font-display);
  font-size: var(--text-md);
  font-weight: var(--weight-semibold);
  color: var(--text);
}
.aios-assistant__welcome-sub {
  font-size: var(--text-xs);
  color: var(--text-muted);
  max-width: 260px;
  line-height: var(--leading-normal);
}
.aios-assistant__quick {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  width: 100%;
  margin-top: var(--space-4);
}
.aios-assistant__quick-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-xs);
  color: var(--text-secondary);
  background: var(--surface-soft);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  text-align: left;
  transition: all var(--duration-fast) var(--ease-out);
  cursor: pointer;
}
.aios-assistant__quick-btn:hover {
  background: var(--accent-soft);
  border-color: var(--accent-soft-strong);
  color: var(--accent);
}
.aios-assistant__quick-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Message bubbles */
.aios-assistant__msg {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  max-width: 90%;
}
.aios-assistant__msg--user {
  align-self: flex-end;
  align-items: flex-end;
}
.aios-assistant__msg--assistant {
  align-self: flex-start;
}
.aios-assistant__msg--system {
  align-self: center;
  font-size: var(--text-xs);
  color: var(--status-risk);
  background: var(--status-risk-soft);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
}
.aios-assistant__msg-content {
  padding: var(--space-3) var(--space-3);
  border-radius: var(--radius-lg);
  font-size: var(--text-sm);
  line-height: var(--leading-normal);
  white-space: pre-wrap;
  word-break: break-word;
}
.aios-assistant__msg--user .aios-assistant__msg-content {
  background: var(--accent);
  color: var(--text-on-accent);
  border-bottom-right-radius: var(--radius-xs);
}
.aios-assistant__msg--assistant .aios-assistant__msg-content {
  background: var(--surface-soft);
  color: var(--text);
  border: 1px solid var(--border-subtle);
  border-bottom-left-radius: var(--radius-xs);
}
.aios-assistant__msg-meta {
  font-size: var(--text-2xs);
  color: var(--text-faint);
  padding: 0 var(--space-1);
}
.aios-assistant__evidence {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
}
.aios-assistant__evidence-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}
.aios-assistant__evidence-chip {
  font-size: var(--text-xs);
  color: var(--accent);
  background: var(--accent-soft);
  padding: 2px var(--space-2);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out);
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.aios-assistant__evidence-chip:hover {
  background: var(--accent-soft-strong);
}

/* Typing indicator */
.aios-assistant__typing {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: var(--space-3);
  background: var(--surface-soft);
  border-radius: var(--radius-lg);
  align-self: flex-start;
}
.aios-assistant__typing span {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-circle);
  background: var(--text-muted);
  animation: aios-typing 1.4s infinite ease-in-out;
}
.aios-assistant__typing span:nth-child(2) { animation-delay: 0.2s; }
.aios-assistant__typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes aios-typing {
  0%, 60%, 100% { opacity: 0.3; transform: translateY(0); }
  30% { opacity: 1; transform: translateY(-3px); }
}

/* Routes */
.aios-assistant__routes {
  display: flex;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-4);
  border-top: 1px solid var(--border-subtle);
}
.aios-assistant__route {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  font-size: var(--text-xs);
  font-weight: var(--weight-medium);
  color: var(--text-muted);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}
.aios-assistant__route:hover { background: var(--surface-soft); color: var(--text); }
.aios-assistant__route--active {
  background: var(--accent-soft);
  color: var(--accent);
}

/* Input */
.aios-assistant__input-wrap {
  display: flex;
  align-items: flex-end;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--border);
  background: var(--surface);
}
.aios-assistant__input {
  flex: 1;
  resize: none;
  max-height: 120px;
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-sm);
  color: var(--text);
  background: var(--bg-sunken);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  outline: none;
  line-height: var(--leading-normal);
  font-family: var(--font-sans);
  transition: border-color var(--duration-fast) var(--ease-out);
}
.aios-assistant__input:focus {
  border-color: var(--accent);
  background: var(--surface);
}
.aios-assistant__input::placeholder { color: var(--text-faint); }
.aios-assistant__send {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  color: var(--text-on-accent);
  background: var(--accent);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}
.aios-assistant__send:hover:not(:disabled) { background: var(--accent-hover); }
.aios-assistant__send:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  background: var(--border-strong);
}

/* Responsive — collapse on small screens */
@media (max-width: 900px) {
  .aios-assistant {
    position: fixed;
    top: var(--topbar-height);
    right: 0;
    bottom: 0;
    width: 100%;
    max-width: var(--assistant-width);
    z-index: var(--z-assistant);
    box-shadow: var(--shadow-5);
  }
}
`;
