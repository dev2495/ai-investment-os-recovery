/**
 * AI Investment OS — Design-System Primitives
 *
 * Lean React wrappers around the `.aios-*` CSS classes. Each component is
 * intentionally thin — the styling lives in primitives.css so it can be
 * tuned without touching component logic.
 *
 * Usage: `import { Button, Panel, StatusPill, ... } from "@/v2/system/primitives";`
 */

import React from "react";
import { X } from "lucide-react";
import type { LucideIcon } from "lucide-react";

/* ============================================================
 * BUTTON
 * ============================================================ */
type ButtonVariant = "default" | "primary" | "ghost" | "danger" | "subtle";
type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: LucideIcon;
  iconRight?: LucideIcon;
  block?: boolean;
}

export function Button({
  variant = "default",
  size = "md",
  icon: Icon,
  iconRight: IconRight,
  block,
  className,
  children,
  ...rest
}: ButtonProps) {
  const cls = [
    "aios-btn",
    variant !== "default" && `aios-btn--${variant}`,
    size !== "md" && `aios-btn--${size}`,
    block && "aios-btn--block",
    className,
  ].filter(Boolean).join(" ");
  return (
    <button className={cls} {...rest}>
      {Icon && <Icon size={size === "sm" ? 14 : 16} />}
      {children}
      {IconRight && <IconRight size={size === "sm" ? 14 : 16} />}
    </button>
  );
}

/* Icon Button */
export interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon: LucideIcon;
  size?: "sm" | "md" | "lg";
  active?: boolean;
  label: string; // accessible label
}
export function IconButton({ icon: Icon, size = "md", active, label, className, ...rest }: IconButtonProps) {
  const cls = [
    "aios-icon-btn",
    size !== "md" && `aios-icon-btn--${size}`,
    active && "aios-icon-btn--active",
    className,
  ].filter(Boolean).join(" ");
  return (
    <button className={cls} aria-label={label} title={label} {...rest}>
      <Icon size={size === "sm" ? 14 : size === "lg" ? 20 : 18} />
    </button>
  );
}

/* ============================================================
 * PANEL + CARD
 * ============================================================ */
type PanelVariant = "default" | "soft" | "sunken" | "borderless" | "risk" | "warn";

export interface PanelProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "title"> {
  variant?: PanelVariant;
  icon?: LucideIcon;
  title?: React.ReactNode;
  actions?: React.ReactNode;
  bodyClassName?: string;
  bodyTabIndex?: number;
  bodyFlush?: boolean;
  footer?: React.ReactNode;
}

export function Panel({
  variant = "default",
  icon: Icon,
  title,
  actions,
  bodyClassName,
  bodyTabIndex,
  bodyFlush,
  footer,
  className,
  children,
  ...rest
}: PanelProps) {
  const cls = ["aios-panel", variant !== "default" && `aios-panel--${variant}`, className]
    .filter(Boolean).join(" ");
  return (
    <div className={cls} {...rest}>
      {(title || actions || Icon) && (
        <div className="aios-panel__header">
          {Icon && <span className="aios-panel__icon"><Icon size={16} /></span>}
          {title && <div className="aios-panel__title">{title}</div>}
          {actions && <div className="aios-panel__actions">{actions}</div>}
        </div>
      )}
      <div tabIndex={bodyTabIndex} role={bodyTabIndex !== undefined ? "region" : undefined} aria-label={bodyTabIndex !== undefined && typeof title === "string" ? title : undefined} className={`aios-panel__body ${bodyFlush ? "aios-panel__body--flush" : ""} ${bodyClassName ?? ""}`.trim()}>
        {children}
      </div>
      {footer && <div className="aios-panel__footer">{footer}</div>}
    </div>
  );
}

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  hoverable?: boolean;
  clickable?: boolean;
}
export function Card({ hoverable, clickable, className, children, ...rest }: CardProps) {
  const cls = [
    "aios-card",
    hoverable && "aios-card--hoverable",
    clickable && "aios-card--clickable",
    className,
  ].filter(Boolean).join(" ");
  return <div className={cls} {...rest}>{children}</div>;
}

/* ============================================================
 * BADGE + STATUS PILL + TAG
 * ============================================================ */
type BadgeTone = "default" | "ok" | "risk" | "warn" | "info" | "special" | "accent";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
  dot?: boolean;
  pulse?: boolean;
}
export function Badge({ tone = "default", dot, pulse, className, children, ...rest }: BadgeProps) {
  const cls = ["aios-badge", tone !== "default" && `aios-badge--${tone}`, className]
    .filter(Boolean).join(" ");
  return (
    <span className={cls} {...rest}>
      {dot && <span className={`aios-badge__dot ${pulse ? "aios-badge__dot--pulse" : ""}`} />}
      {children}
    </span>
  );
}

type StatusTone = "ok" | "risk" | "warn" | "info" | "neutral";

/** Map free-form status strings to a tone (resilient to backend vocabulary drift). */
export function statusTone(status: string | undefined): StatusTone {
  if (!status) return "neutral";
  const s = status.toLowerCase();
  if (["ok", "live", "active", "healthy", "ready", "running", "passed", "approved", "resolved", "fresh", "green"].some(w => s.includes(w))) return "ok";
  if (["breach", "critical", "error", "fail", "blocked", "killed", "stale", "armed", "red", "reject", "denied"].some(w => s.includes(w))) return "risk";
  if (["warn", "warning", "review", "pending", "await", "aging", "drift", "amber", "yellow"].some(w => s.includes(w))) return "warn";
  if (["info", "queued", "scheduled", "synced", "blue"].some(w => s.includes(w))) return "info";
  return "neutral";
}

export interface StatusPillProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: StatusTone;
  status?: string; // if provided, tone is inferred
  dot?: boolean;
  pulse?: boolean;
}
export function StatusPill({ tone, status, dot, pulse, className, children, ...rest }: StatusPillProps) {
  const resolved = tone ?? statusTone(status);
  const cls = ["aios-pill", resolved !== "neutral" && `aios-pill--${resolved}`, className]
    .filter(Boolean).join(" ");
  return (
    <span className={cls} {...rest}>
      {dot && <span className={`aios-pill__dot ${pulse ? "aios-pill__dot--pulse" : ""}`} />}
      {children ?? status}
    </span>
  );
}

export interface TagProps extends React.HTMLAttributes<HTMLSpanElement> {
  onRemove?: () => void;
}
export function Tag({ onRemove, className, children, ...rest }: TagProps) {
  const cls = ["aios-tag", className].filter(Boolean).join(" ");
  return (
    <span className={cls} {...rest}>
      {children}
      {onRemove && (
        <span className="aios-tag__remove" onClick={onRemove} role="button" aria-label="Remove tag">×</span>
      )}
    </span>
  );
}

/* ============================================================
 * METRIC + METRIC TILE
 * ============================================================ */
type MetricSize = "sm" | "md" | "lg";
type DeltaDirection = "up" | "down" | "flat";

export interface MetricProps {
  label: string;
  value: React.ReactNode;
  size?: MetricSize;
  delta?: { value: string; direction: DeltaDirection };
  sub?: React.ReactNode;
  className?: string;
}
export function Metric({ label, value, size = "md", delta, sub, className }: MetricProps) {
  return (
    <div className={`aios-metric ${className ?? ""}`.trim()}>
      <div className="aios-metric__label">{label}</div>
      <div className={`aios-metric__value aios-metric__value--${size} tnum`}>{value}</div>
      {delta && (
        <div className={`aios-metric__delta aios-metric__delta--${delta.direction} tnum`}>
          {delta.value}
        </div>
      )}
      {sub && <div className="aios-metric__sub">{sub}</div>}
    </div>
  );
}

type TileTone = "default" | "risk" | "warn" | "ok";
export interface MetricTileProps extends React.HTMLAttributes<HTMLDivElement> {
  tone?: TileTone;
  clickable?: boolean;
}
export function MetricTile({ tone = "default", clickable, className, children, ...rest }: MetricTileProps) {
  const cls = [
    "aios-metric-tile",
    tone !== "default" && `aios-metric-tile--${tone}`,
    clickable && "aios-metric-tile--clickable",
    className,
  ].filter(Boolean).join(" ");
  return <div className={cls} {...rest}>{children}</div>;
}

/* ============================================================
 * TABLE
 * ============================================================ */
export interface DataTableProps<T> {
  columns: Array<{
    key: string;
    header: React.ReactNode;
    render?: (row: T) => React.ReactNode;
    width?: string | number;
    align?: "left" | "right" | "center";
    className?: string;
  }>;
  rows: T[];
  rowKey: (row: T, index: number) => string;
  onRowClick?: (row: T) => void;
  empty?: React.ReactNode;
  hoverable?: boolean;
  dense?: boolean;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  onRowClick,
  empty,
  hoverable = true,
  dense,
}: DataTableProps<T>) {
  if (rows.length === 0 && empty) {
    return <>{empty}</>;
  }
  return (
    <table className={`aios-table ${hoverable ? "aios-table--hoverable" : ""} ${onRowClick ? "aios-table--clickable" : ""}`}>
      <thead>
        <tr>
          {columns.map((col) => (
            <th
              key={col.key}
              style={{ width: col.width, textAlign: col.align ?? "left" }}
              className={col.className}
            >
              {col.header}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={rowKey(row, i)} onClick={onRowClick ? () => onRowClick(row) : undefined} style={dense ? { height: 32 } : undefined}>
            {columns.map((col) => (
              <td
                key={col.key}
                style={{ textAlign: col.align ?? "left" }}
                className={col.align === "right" ? "tnum" : col.className}
              >
                {col.render ? col.render(row) : String((row as Record<string, unknown>)[col.key] ?? "")}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/* ============================================================
 * TABS + SEGMENTED CONTROL
 * ============================================================ */
export interface TabItem {
  key: string;
  label: React.ReactNode;
  count?: number;
  countTone?: "default" | "risk";
  icon?: LucideIcon;
}
export interface TabsProps {
  tabs: TabItem[];
  active: string;
  onChange: (key: string) => void;
  className?: string;
}
export function Tabs({ tabs, active, onChange, className }: TabsProps) {
  return (
    <div className={`aios-tabs ${className ?? ""}`.trim()}>
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = tab.key === active;
        return (
          <button
            key={tab.key}
            className={`aios-tab ${isActive ? "aios-tab--active" : ""}`}
            onClick={() => onChange(tab.key)}
          >
            {Icon && <Icon size={14} />}
            {tab.label}
            {tab.count !== undefined && tab.count > 0 && (
              <span className={`aios-tab__count ${tab.countTone === "risk" ? "aios-tab__count--risk" : ""}`}>
                {tab.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

export interface SegmentedProps {
  options: Array<{ key: string; label: React.ReactNode; icon?: LucideIcon }>;
  active: string;
  onChange: (key: string) => void;
}
export function SegmentedControl({ options, active, onChange }: SegmentedProps) {
  return (
    <div className="aios-segmented">
      {options.map((opt) => {
        const Icon = opt.icon;
        const isActive = opt.key === active;
        return (
          <button
            key={opt.key}
            className={`aios-segmented__btn ${isActive ? "aios-segmented__btn--active" : ""}`}
            onClick={() => onChange(opt.key)}
          >
            {Icon && <Icon size={14} />}
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

/* ============================================================
 * DRAWER + MODAL
 * ============================================================ */
export interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  icon?: LucideIcon;
  actions?: React.ReactNode;
  footer?: React.ReactNode;
  width?: number | string;
  children: React.ReactNode;
}
export function Drawer({ open, onClose, title, subtitle, icon: Icon, actions, footer, width, children }: DrawerProps) {
  if (!open) return null;
  return (
    <>
      <div className="aios-drawer-overlay" onClick={onClose} />
      <aside
        className="aios-drawer"
        style={width ? ({ "--evidence-drawer-width": typeof width === "number" ? `${width}px` : width } as React.CSSProperties) : undefined}
        role="dialog"
        aria-modal="true"
      >
        <header className="aios-drawer__header">
          {Icon && <Icon size={20} />}
          <div style={{ flex: 1, minWidth: 0 }}>
            {title && <div style={{ fontSize: "var(--text-lg)", fontWeight: "var(--weight-semibold)" }}>{title}</div>}
            {subtitle && <div className="micro">{subtitle}</div>}
          </div>
          {actions}
          <IconButton icon={X} size="sm" label="Close" onClick={onClose} />
        </header>
        <div className="aios-drawer__body">{children}</div>
        {footer && <div className="aios-drawer__footer">{footer}</div>}
      </aside>
    </>
  );
}

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: React.ReactNode;
  size?: "md" | "lg";
  children: React.ReactNode;
  footer?: React.ReactNode;
}
export function Modal({ open, onClose, title, size = "md", children, footer }: ModalProps) {
  if (!open) return null;
  return (
    <>
      <div className="aios-modal-overlay" onClick={onClose} />
      <div className={`aios-modal aios-modal--${size}`} role="dialog" aria-modal="true">
        {title && (
          <div className="aios-modal__header">
            <h3>{title}</h3>
          </div>
        )}
        <div className="aios-modal__body">{children}</div>
        {footer && <div className="aios-modal__footer">{footer}</div>}
      </div>
    </>
  );
}

/* ============================================================
 * TOAST (rendered by a single ToastViewport in the app shell)
 * ============================================================ */
export interface ToastItem {
  id: string;
  title: string;
  message?: string;
  tone: "ok" | "risk" | "warn" | "info";
}
export function Toast({ toast, onDismiss }: { toast: ToastItem; onDismiss: () => void }) {
  return (
    <div className={`aios-toast aios-toast--${toast.tone}`} onClick={onDismiss} role="alert">
      <div className="aios-toast__icon">
        <span style={{ display: "inline-block", width: 16, height: 16, borderRadius: "50%", background: "currentColor" }} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="aios-toast__title">{toast.title}</div>
        {toast.message && <div className="aios-toast__msg">{toast.message}</div>}
      </div>
    </div>
  );
}

/* ============================================================
 * EMPTY + SKELETON
 * ============================================================ */
export interface EmptyProps {
  icon?: LucideIcon;
  title?: string;
  description?: string;
  action?: React.ReactNode;
}
export function Empty({ icon: Icon, title = "Nothing here yet", description, action }: EmptyProps) {
  return (
    <div className="aios-empty">
      {Icon && <span className="aios-empty__icon"><Icon size={32} strokeWidth={1.5} /></span>}
      <div className="aios-empty__title">{title}</div>
      {description && <div className="aios-empty__desc">{description}</div>}
      {action && <div style={{ marginTop: "var(--space-3)" }}>{action}</div>}
    </div>
  );
}

export function Skeleton({ variant = "text", width, height, className, style }: { variant?: "text" | "title" | "circle" | "block"; width?: string | number; height?: string | number; className?: string; style?: React.CSSProperties }) {
  const cls = ["aios-skeleton", variant !== "block" && `aios-skeleton--${variant}`, className].filter(Boolean).join(" ");
  return <div className={cls} style={{ width, height, ...style }} />;
}

/* ============================================================
 * TOOLTIP
 * ============================================================ */
export function Tooltip({ content, children, side = "top" }: { content: React.ReactNode; children: React.ReactNode; side?: "top" | "bottom" }) {
  return (
    <span className="aios-tooltip" style={{ display: "inline-flex", position: "relative" }}>
      {children}
      <span className="aios-tooltip__bubble" style={side === "bottom" ? { top: "calc(100% + 6px)", bottom: "auto" } : undefined}>
        {content}
      </span>
    </span>
  );
}

/* ============================================================
 * FORM CONTROLS
 * ============================================================ */
export interface FieldProps {
  label?: string;
  hint?: string;
  error?: string;
  required?: boolean;
  children: React.ReactNode;
}
export function Field({ label, hint, error, required, children }: FieldProps) {
  return (
    <div className="aios-field">
      {label && (
        <label className="aios-field__label">
          {label}
          {required && <span style={{ color: "var(--status-risk)" }}> *</span>}
        </label>
      )}
      {children}
      {hint && !error && <div className="aios-field__hint">{hint}</div>}
      {error && <div className="aios-field__error">{error}</div>}
    </div>
  );
}

export const TextInput = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  function TextInput({ className, ...rest }, ref) {
    return <input ref={ref} className={`aios-input ${className ?? ""}`.trim()} {...rest} />;
  }
);

export const TextArea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function TextArea({ className, ...rest }, ref) {
    return <textarea ref={ref} className={`aios-textarea ${className ?? ""}`.trim()} {...rest} />;
  }
);

export const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, children, ...rest }, ref) {
    return <select ref={ref} className={`aios-select ${className ?? ""}`.trim()} {...rest}>{children}</select>;
  }
);

export function Checkbox({ checked, onChange, label, disabled }: { checked: boolean; onChange: (v: boolean) => void; label?: React.ReactNode; disabled?: boolean }) {
  return (
    <label className={`aios-checkbox ${checked ? "aios-checkbox--checked" : ""}`} style={{ opacity: disabled ? 0.5 : 1, cursor: disabled ? "not-allowed" : "pointer" }}>
      <span className="aios-checkbox__box">{checked && <span style={{ fontSize: 11, lineHeight: 1 }}>✓</span>}</span>
      {label && <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} disabled={disabled} style={{ display: "none" }} />}
      {label && <span>{label}</span>}
    </label>
  );
}

export function Toggle({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label?: string }) {
  return (
    <label style={{ display: "inline-flex", alignItems: "center", gap: "var(--space-2)", cursor: "pointer" }}>
      <span className={`aios-toggle ${on ? "aios-toggle--on" : ""}`} onClick={() => onChange(!on)} role="switch" aria-checked={on}>
        <span className="aios-toggle__thumb" />
      </span>
      {label && <span style={{ fontSize: "var(--text-sm)" }}>{label}</span>}
    </label>
  );
}

/* ============================================================
 * AVATAR
 * ============================================================ */
type AvatarSize = "sm" | "md" | "lg" | "xl";
type AvatarRing = "none" | "ok" | "risk" | "warn" | "idle";
export function Avatar({ initials, size = "md", ring = "none", name }: { initials: string; size?: AvatarSize; ring?: AvatarRing; name?: string }) {
  const cls = [
    "aios-avatar",
    size !== "md" && `aios-avatar--${size}`,
    ring !== "none" && "aios-avatar__ring",
    ring !== "none" && ring !== "ok" && `aios-avatar__ring--${ring}`,
  ].filter(Boolean).join(" ");
  return (
    <div className={cls} title={name} role={name ? "img" : undefined} aria-label={name}>
      {initials}
    </div>
  );
}

/* ============================================================
 * SECTION HEADER + KEY-VALUE
 * ============================================================ */
export function SectionHeader({ title, action, icon: Icon }: { title: React.ReactNode; action?: React.ReactNode; icon?: LucideIcon }) {
  return (
    <div className="aios-section-header">
      {Icon && <Icon size={18} style={{ color: "var(--text-muted)" }} />}
      <div className="aios-section-header__title" style={{ flex: 1 }}>{title}</div>
      {action}
    </div>
  );
}

export function KeyValue({ label, value }: { label: React.ReactNode; value: React.ReactNode }) {
  return (
    <div className="aios-kv">
      <span className="aios-kv__label">{label}</span>
      <span className="aios-kv__value">{value}</span>
    </div>
  );
}

/* ============================================================
 * SCROLL LIST
 * ============================================================ */
export function ScrollList({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={`aios-scroll-list ${className ?? ""}`.trim()}>{children}</div>;
}
