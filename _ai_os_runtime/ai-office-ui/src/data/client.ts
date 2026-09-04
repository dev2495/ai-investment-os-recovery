/**
 * AI Investment OS — Shared HTTP Client
 *
 * One source of truth for talking to the AI OS API server
 * (default http://127.0.0.1:8765). Replaces the 10+ per-file `API_URL` +
 * `request` helpers that were copy-pasted across the old `src/api/`.
 *
 * Responsibilities:
 *   - Single base URL + operator token config
 *   - Uniform error normalization (ApiError)
 *   - JSON request/response helpers with timeout + abort
 *   - Typed GET/POST wrappers
 *
 * Server state (caching, dedup, polling, optimistic updates) is handled by
 * TanStack Query in `data/queries/`. This module is intentionally low-level.
 */

function resolveApiBaseUrl(): string {
  const configured = String(import.meta.env.VITE_AI_OS_API_URL || "").trim();
  if (configured) return configured.replace(/\/$/, "");

  if (typeof window !== "undefined") {
    const { hostname, protocol } = window.location;
    if (hostname && hostname !== "localhost" && hostname !== "127.0.0.1") {
      return `${protocol}//${hostname}:8443`;
    }
  }

  return "http://127.0.0.1:8765";
}

const BASE_URL = resolveApiBaseUrl();
const OPERATOR_TOKEN = String(import.meta.env.VITE_AI_OS_OPERATOR_TOKEN || "").trim();

/** SSE shares the canonical URL/auth header; credentials never go in a URL. */
export function openRuntimeEventStream(cursor: number, signal: AbortSignal): Promise<Response> {
  return fetch(`${BASE_URL}/api/v1/office/events/stream?after_event_id=${cursor}`, {
    cache: "no-store", signal,
    headers: {
      Accept: "text/event-stream",
      ...(OPERATOR_TOKEN ? { Authorization: `Bearer ${OPERATOR_TOKEN}` } : {}),
    },
  });
}

/** Default request timeout (5 min — Charlie chat + model runs can be slow). */
const DEFAULT_TIMEOUT_MS = 300_000;

/** Snapshot polling cadence (30s) — shared by all snapshot queries. */
export const SNAPSHOT_REFETCH_MS = 30_000;

/**
 * Normalized API error. The backend returns `{ error, message }` payloads on
 * failure; we surface a clean message and keep the HTTP status for the UI.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly endpoint: string;
  readonly payload: unknown;

  constructor(message: string, status: number, endpoint: string, payload?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.endpoint = endpoint;
    this.payload = payload;
  }
}

interface RequestOptions {
  /** Query string params. */
  query?: Record<string, string | number | boolean | undefined>;
  /** Request body — will be JSON-encoded. */
  body?: unknown;
  /** Abort signal (TanStack Query passes these for cancellation). */
  signal?: AbortSignal;
  /** Per-request timeout override. */
  timeoutMs?: number;
  /** Extra headers. */
  headers?: Record<string, string>;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const base = path.startsWith("http") ? path : `${BASE_URL}${path}`;
  if (!query) return base;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null) {
      params.set(key, String(value));
    }
  }
  const qs = params.toString();
  return qs ? `${base}?${qs}` : base;
}

function withTimeout(signal: AbortSignal | undefined, timeoutMs: number): AbortSignal {
  if (!timeoutMs) return signal as AbortSignal;
  // If the caller provided a signal, race it against a timeout.
  const timeout = AbortSignal.timeout(timeoutMs);
  if (!signal) return timeout;
  // Combine: abort if EITHER fires.
  const combined = new AbortController();
  const onAbort = (reason: "signal" | "timeout") => {
    combined.abort(reason);
  };
  signal.addEventListener("abort", () => onAbort("signal"), { once: true });
  timeout.addEventListener("abort", () => onAbort("timeout"), { once: true });
  return combined.signal;
}

/** Core request function. Returns parsed JSON or throws ApiError. */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { query, body, signal, timeoutMs = DEFAULT_TIMEOUT_MS, headers } = options;
  const url = buildUrl(path, query);

  const init: RequestInit = {
    method: body !== undefined ? "POST" : "GET",
    cache: "no-store",
    signal: withTimeout(signal, timeoutMs),
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(OPERATOR_TOKEN ? { Authorization: `Bearer ${OPERATOR_TOKEN}` } : {}),
      ...(headers ?? {}),
    },
  };

  if (body !== undefined) {
    init.body = JSON.stringify(body);
  }

  let response: Response;
  try {
    response = await fetch(url, init);
  } catch (err) {
    if ((err as Error)?.name === "TimeoutError" || (err as Error)?.name === "AbortError") {
      throw new ApiError(
        "Request timed out or was cancelled.",
        0,
        path,
        { kind: "timeout", error: String(err) }
      );
    }
    // Network error — server likely down (Docker/Postgres off, etc.)
    throw new ApiError(
      `Cannot reach AI OS API at ${BASE_URL}. Is the server running?`,
      0,
      path,
      { kind: "network", error: String(err) }
    );
  }

  let payload: unknown = null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    payload = await response.json().catch(() => null);
  } else {
    payload = await response.text().catch(() => null);
  }

  if (!response.ok) {
    const errPayload = (payload && typeof payload === "object" ? payload : {}) as Record<string, unknown>;
    const message =
      String(errPayload.message || errPayload.error || `HTTP ${response.status} ${response.statusText}`);
    throw new ApiError(message, response.status, path, payload);
  }

  return payload as T;
}

/** Typed GET. */
export function get<T>(path: string, options?: Omit<RequestOptions, "body">): Promise<T> {
  return request<T>(path, options);
}

/** Typed POST. */
export function post<T>(path: string, body?: unknown, options?: Omit<RequestOptions, "body">): Promise<T> {
  return request<T>(path, { ...options, body });
}

/**
 * Upload a file (multipart). Used by the local-artifact upload endpoint,
 * which takes query params + a binary body rather than JSON.
 */
export async function uploadFile(
  path: string,
  file: File | Blob,
  query?: Record<string, string>,
  options?: { signal?: AbortSignal; headers?: Record<string, string> }
): Promise<unknown> {
  const url = buildUrl(path, query);
  const response = await fetch(url, {
    method: "POST",
    cache: "no-store",
    signal: options?.signal,
    headers: {
      "Content-Type": (file as File).type || "application/octet-stream",
      ...(OPERATOR_TOKEN ? { Authorization: `Bearer ${OPERATOR_TOKEN}` } : {}),
      ...(options?.headers ?? {}),
    },
    body: file,
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const errPayload = (payload && typeof payload === "object" ? payload : {}) as Record<string, unknown>;
    throw new ApiError(
      String(errPayload.message || errPayload.error || `Upload failed: HTTP ${response.status}`),
      response.status,
      path,
      payload
    );
  }
  return payload;
}

/** Expose base URL for display (e.g. freshness badges, health tooltips). */
export const API_BASE_URL = BASE_URL;

/** Is the client configured with an operator token? */
export const HAS_OPERATOR_TOKEN = OPERATOR_TOKEN.length > 0;
