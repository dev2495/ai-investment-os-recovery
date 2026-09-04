import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { openRuntimeEventStream } from "./client";
import { queryKeys } from "./queries";

export type RuntimeConnection = "connecting" | "live" | "snapshot fallback" | "unavailable";

/** Transport invalidates the existing snapshot; it is not a second state store. */
export function useRuntimeEvents(enabled: boolean, initialCursor: number): RuntimeConnection {
  const client = useQueryClient();
  const [connection, setConnection] = useState<RuntimeConnection>("connecting");
  useEffect(() => {
    if (!enabled) { setConnection("unavailable"); return; }
    const abort = new AbortController();
    let cursor = initialCursor;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let refreshTimer: ReturnType<typeof setTimeout> | undefined;
    const refresh = () => {
      if (refreshTimer) return;
      refreshTimer = setTimeout(() => {
        refreshTimer = undefined;
        void client.invalidateQueries({ queryKey: queryKeys.office });
        void client.invalidateQueries({ queryKey: ["runtime-task"] });
      }, 300);
    };
    async function connect() {
      let failed = false;
      try {
        const response = await openRuntimeEventStream(cursor, abort.signal);
        if (!response.ok || !response.body) throw new Error("Event stream unavailable");
        setConnection("live");
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let pending = "";
        try {
          while (!abort.signal.aborted) {
            const chunk = await reader.read();
            if (chunk.done) break;
            pending += decoder.decode(chunk.value, { stream: true }).replace(/\r\n/g, "\n");
            if (pending.length > 262144) throw new Error("Event buffer limit exceeded");
            let boundary: number;
            while ((boundary = pending.indexOf("\n\n")) >= 0) {
              const frame = pending.slice(0, boundary);
              pending = pending.slice(boundary + 2);
              const kind = frame.match(/^event: (.+)$/m)?.[1];
              const raw = frame.match(/^data: (.+)$/m)?.[1];
              if (kind === "reset" && raw) {
                const next = Number(JSON.parse(raw).cursor);
                if (Number.isSafeInteger(next) && next >= 0) cursor = next;
                refresh();
              } else if (kind === "runtime") {
                const next = Number(frame.match(/^id: (\d+)$/m)?.[1]);
                if (Number.isSafeInteger(next) && next > cursor) {
                  cursor = next;
                  refresh();
                }
              }
            }
          }
        } finally { await reader.cancel().catch(() => undefined); }
      } catch {
        failed = true;
        if (!abort.signal.aborted) { setConnection("snapshot fallback"); refresh(); }
      }
      if (!abort.signal.aborted) retryTimer = setTimeout(() => void connect(), failed ? 5000 : 500);
    }
    void connect();
    return () => { abort.abort(); clearTimeout(retryTimer); clearTimeout(refreshTimer); };
    // The first snapshot supplies the cursor. Later snapshots must not reset a
    // healthy connection or replay already-observed transitions.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client, enabled]);
  return connection;
}
