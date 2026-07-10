import { useCallback, useEffect, useState } from "react";
import { fetchLiveSnapshot, type LiveSnapshot } from "../api/live";

export type LiveConnectionStatus = "loading" | "online" | "offline";

interface UseLiveSnapshotOptions {
  onOffline: () => void;
  onSnapshot: (snapshot: LiveSnapshot) => void;
  pollIntervalMs?: number;
}

export function useLiveSnapshot({ onOffline, onSnapshot, pollIntervalMs = 30_000 }: UseLiveSnapshotOptions) {
  const [snapshot, setSnapshot] = useState<LiveSnapshot | null>(null);
  const [liveStatus, setLiveStatus] = useState<LiveConnectionStatus>("loading");

  const refresh = useCallback(async () => {
    const nextSnapshot = await fetchLiveSnapshot();
    setSnapshot(nextSnapshot);
    setLiveStatus("online");
    onSnapshot(nextSnapshot);
    return nextSnapshot;
  }, [onSnapshot]);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const nextSnapshot = await fetchLiveSnapshot();
        if (cancelled) return;
        setSnapshot(nextSnapshot);
        setLiveStatus("online");
        onSnapshot(nextSnapshot);
      } catch {
        if (cancelled) return;
        setSnapshot(null);
        setLiveStatus("offline");
        onOffline();
      }
    };

    void load();
    const timer = window.setInterval(load, pollIntervalMs);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [onOffline, onSnapshot, pollIntervalMs]);

  return { liveStatus, refresh, setLiveStatus, setSnapshot, snapshot };
}
