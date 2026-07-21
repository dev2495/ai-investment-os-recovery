/**
 * AI Investment OS — LiveRow typed accessors
 *
 * The backend warehouse serves rows as `Record<string, unknown>` — every
 * snapshot array contains these. Rather than pretend we know every column
 * ahead of time (which would break silently on backend renames), we provide
 * safe, defensive accessors that coerce common column shapes and never throw.
 *
 * Usage:
 *   const symbol = text(position, "symbol");
 *   const qty = num(position, "quantity", 0);
 *   const breached = bool(riskEvent, "breach", false);
 *
 * This is the pragmatic middle ground: type-safe at the call site, resilient
 * to payload drift, and zero-cost in production.
 */

export type LiveRow = Record<string, unknown>;

/** Read a value of unknown type from a row. Returns undefined if missing. */
export function raw(row: LiveRow | null | undefined, key: string): unknown {
  if (!row || typeof row !== "object") return undefined;
  return row[key];
}

/** Coerce to string with an optional fallback. */
export function text(row: LiveRow | null | undefined, key: string, fallback: string | number = ""): string {
  const v = raw(row, key);
  if (v === null || v === undefined) return String(fallback);
  if (typeof v === "string") return v;
  return String(v);
}

/** Coerce to a number with fallback. Handles string-encoded numbers. */
export function num(row: LiveRow | null | undefined, key: string, fallback = 0): number {
  const v = raw(row, key);
  if (v === null || v === undefined || v === "") return fallback;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : fallback;
}

/** Coerce to boolean. Treats "true"/"yes"/"1"/1 as truthy. */
export function bool(row: LiveRow | null | undefined, key: string, fallback = false): boolean {
  const v = raw(row, key);
  if (v === null || v === undefined || v === "") return fallback;
  if (typeof v === "boolean") return v;
  if (typeof v === "number") return v !== 0;
  const s = String(v).toLowerCase().trim();
  if (["true", "yes", "1", "t", "y", "on", "active", "ok"].includes(s)) return true;
  if (["false", "no", "0", "f", "n", "off", "inactive"].includes(s)) return false;
  return fallback;
}

/** Read an ISO timestamp string (or fallback). */
export function timestamp(row: LiveRow | null | undefined, key: string, fallback = ""): string {
  return text(row, key, fallback);
}

/** Read a nested object/array value, typed by the caller. */
export function value<T = unknown>(row: LiveRow | null | undefined, key: string, fallback: T): T {
  const v = raw(row, key);
  return (v === null || v === undefined ? fallback : (v as T));
}

/** Read an array of LiveRows (the common nested shape). */
export function rows(row: LiveRow | null | undefined, key: string): LiveRow[] {
  const v = raw(row, key);
  return Array.isArray(v) ? (v as LiveRow[]) : [];
}

/** Build a text summary of a row from a primary column (first found). */
export function primaryText(row: LiveRow | null | undefined, keys: string[]): string {
  for (const key of keys) {
    const v = text(row, key, "");
    if (v) return v;
  }
  return "";
}

/** Format a number as currency (INR default, given NSE focus). */
export function formatCurrency(amount: number, currency = "INR", opts?: Intl.NumberFormatOptions): string {
  if (!Number.isFinite(amount)) return "—";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
    ...opts,
  }).format(amount);
}

/** Format a number compactly (e.g. 1.2M, 3.4K). */
export function formatCompact(amount: number, currency?: string): string {
  if (!Number.isFinite(amount)) return "—";
  const opts: Intl.NumberFormatOptions = { notation: "compact", maximumFractionDigits: 1 };
  if (currency) {
    return new Intl.NumberFormat("en-IN", { ...opts, style: "currency", currency }).format(amount);
  }
  return new Intl.NumberFormat("en-IN", opts).format(amount);
}

/** Format a percentage (0.2825 → "28.25%"). Accepts ratio or already-percent. */
export function formatPercent(value: number, opts?: { alreadyPercent?: boolean; digits?: number }): string {
  if (!Number.isFinite(value)) return "—";
  const pct = opts?.alreadyPercent ? value : value * 100;
  const digits = opts?.digits ?? 2;
  return `${pct.toFixed(digits)}%`;
}

/** Relative time ("3m ago", "2h ago", "just now"). */
export function formatRelative(iso: string, now: number = Date.now()): string {
  if (!iso) return "—";
  const ts = Date.parse(iso);
  if (!Number.isFinite(ts)) return "—";
  const diff = Math.max(0, now - ts);
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return "just now";
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 30) return `${day}d ago`;
  const mo = Math.floor(day / 30);
  if (mo < 12) return `${mo}mo ago`;
  return `${Math.floor(mo / 12)}y ago`;
}

/** Truncate text with ellipsis. */
export function truncate(s: string, max: number): string {
  if (!s) return "";
  return s.length > max ? `${s.slice(0, max - 1)}…` : s;
}

/** Initials from a name (for avatars). */
export function initials(name: string): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
