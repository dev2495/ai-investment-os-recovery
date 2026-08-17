/**
 * AI Investment OS — UI Store (zustand)
 *
 * Holds ONLY client-side UI state. Server data lives in TanStack Query.
 * Kept deliberately small: theme, layout, assistant, evidence drawer,
 * 3D camera focus, and toasts.
 */

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

export type ThemeMode = "light" | "dark";
export type Density = "standard" | "compact";

/** What the 3D camera should focus on (room key or null = lobby overview). */
export interface CameraTarget {
  roomKey: string | null;
  /** timestamp to retrigger even if same room clicked twice */
  nonce: number;
}

/** A toast notification. */
export interface Toast {
  id: string;
  title: string;
  message?: string;
  tone: "ok" | "risk" | "warn" | "info";
  /** auto-dismiss after ms; 0 = sticky */
  duration: number;
}

/** The evidence drawer target. */
export interface EvidenceTarget {
  kind: string;
  key: string;
  title: string;
  subtitle?: string;
}

interface UIState {
  /* Theme + density */
  theme: ThemeMode;
  density: Density;
  setTheme: (theme: ThemeMode) => void;
  toggleTheme: () => void;
  setDensity: (density: Density) => void;

  /* Assistant (Charlie right rail) */
  assistantOpen: boolean;
  assistantScope: "charlie" | { agentKey: string; agentName: string };
  setAssistantOpen: (open: boolean) => void;
  toggleAssistant: () => void;
  setAssistantScope: (scope: UIState["assistantScope"]) => void;
  pendingAssistantMessage: { id: string; message: string } | null;
  queueAssistantMessage: (message: string) => void;
  consumeAssistantMessage: (id: string) => void;

  /* Command palette (Cmd-K) */
  paletteOpen: boolean;
  setPaletteOpen: (open: boolean) => void;
  togglePalette: () => void;

  /* 3D office camera */
  cameraTarget: CameraTarget;
  focusRoom: (roomKey: string | null) => void;

  /* Evidence drawer */
  evidenceTarget: EvidenceTarget | null;
  openEvidence: (target: EvidenceTarget) => void;
  closeEvidence: () => void;

  /* Toasts */
  toasts: Toast[];
  pushToast: (toast: Omit<Toast, "id">) => void;
  dismissToast: (id: string) => void;
}

const THEME_KEY = "aios-theme-v2";
const DENSITY_KEY = "aios-density";

/** Read the approved shell theme; the v1 black/teal preference is not carried forward. */
function initialTheme(): ThemeMode {
  if (typeof window === "undefined") return "light";
  try {
    const stored = window.localStorage.getItem(THEME_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch { /* ignore */ }
  return "light";
}

function initialDensity(): Density {
  if (typeof window === "undefined") return "standard";
  try {
    const stored = window.localStorage.getItem(DENSITY_KEY);
    if (stored === "compact" || stored === "standard") return stored;
  } catch { /* ignore */ }
  return "standard";
}

export const useUIStore = create<UIState>()(
  persist(
    (set, get) => ({
      /* ---- Theme + density ---- */
      theme: initialTheme(),
      density: initialDensity(),
      setTheme: (theme) => {
        applyThemeToDom(theme);
        try { window.localStorage.setItem(THEME_KEY, theme); } catch { /* ignore */ }
        set({ theme });
      },
      toggleTheme: () => {
        const next = get().theme === "light" ? "dark" : "light";
        get().setTheme(next);
      },
      setDensity: (density) => {
        applyDensityToDom(density);
        try { window.localStorage.setItem(DENSITY_KEY, density); } catch { /* ignore */ }
        set({ density });
      },

      /* ---- Assistant ---- */
      assistantOpen: true,
      assistantScope: "charlie",
      setAssistantOpen: (assistantOpen) => set({ assistantOpen }),
      toggleAssistant: () => set({ assistantOpen: !get().assistantOpen }),
      setAssistantScope: (assistantScope) =>
        set({ assistantScope, assistantOpen: true }),
      pendingAssistantMessage: null,
      queueAssistantMessage: (message) => {
        const trimmed = message.trim();
        if (!trimmed) return;
        set({
          assistantOpen: true,
          pendingAssistantMessage: { id: "assistant-" + Date.now() + "-" + Math.random().toString(36).slice(2, 8), message: trimmed },
        });
      },
      consumeAssistantMessage: (id) => {
        if (get().pendingAssistantMessage?.id === id) set({ pendingAssistantMessage: null });
      },

      /* ---- Command palette ---- */
      paletteOpen: false,
      setPaletteOpen: (paletteOpen) => set({ paletteOpen }),
      togglePalette: () => set({ paletteOpen: !get().paletteOpen }),

      /* ---- 3D camera ---- */
      cameraTarget: { roomKey: null, nonce: 0 },
      focusRoom: (roomKey) =>
        set({ cameraTarget: { roomKey, nonce: Date.now() } }),

      /* ---- Evidence drawer ---- */
      evidenceTarget: null,
      openEvidence: (evidenceTarget) => set({ evidenceTarget }),
      closeEvidence: () => set({ evidenceTarget: null }),

      /* ---- Toasts ---- */
      toasts: [],
      pushToast: (toast) => {
        const id = `t-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
        const fullToast: Toast = { id, ...toast };
        set({ toasts: [...get().toasts, fullToast] });
        if (toast.duration > 0) {
          setTimeout(() => get().dismissToast(id), toast.duration);
        }
      },
      dismissToast: (id) =>
        set({ toasts: get().toasts.filter((t) => t.id !== id) }),
    }),
    {
      name: "aios-ui",
      version: 2,
      migrate: (persisted, version) => {
        const state = (persisted ?? {}) as Partial<UIState>;
        return version < 2 ? { ...state, theme: "light" } as UIState : state as UIState;
      },
      storage: createJSONStorage(() => localStorage),
      // Only persist what makes sense across sessions; not transient state.
      partialize: (state) => ({
        theme: state.theme,
        density: state.density,
        assistantOpen: state.assistantOpen,
      }),
    }
  )
);

/** Apply theme + density to <html> data attributes. */
export function applyThemeToDom(theme: ThemeMode): void {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.theme = theme;
}

export function applyDensityToDom(density: Density): void {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.density = density;
}

/** Apply persisted theme/density to the DOM on app boot. */
export function applyInitialDomState(): void {
  const state = useUIStore.getState();
  applyThemeToDom(state.theme);
  applyDensityToDom(state.density);
  // On a phone the assistant is a full-screen surface; begin with the requested page visible.
  if (typeof window !== "undefined" && window.innerWidth <= 700 && state.assistantOpen) {
    state.setAssistantOpen(false);
  }
}
