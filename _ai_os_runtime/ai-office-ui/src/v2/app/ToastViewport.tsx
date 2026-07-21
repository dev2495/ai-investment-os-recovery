/**
 * Toast Viewport — renders the toast stack from the UI store.
 * Mounted once at the app shell level.
 */

import { useUIStore } from "../store";
import { Toast } from "../system/primitives";

export function ToastViewport() {
  const toasts = useUIStore((s) => s.toasts);
  const dismiss = useUIStore((s) => s.dismissToast);

  if (toasts.length === 0) return null;
  return (
    <div className="aios-toast-stack">
      {toasts.map((toast) => (
        <Toast key={toast.id} toast={toast} onDismiss={() => dismiss(toast.id)} />
      ))}
    </div>
  );
}
