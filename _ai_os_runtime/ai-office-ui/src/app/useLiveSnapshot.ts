import { useCallback, useEffect, useState } from "react";
import { fetchLiveSnapshot, type LiveSnapshot } from "../api/live";

export type LiveConnectionStatus = "loading" | "online" | "offline";

interface UseLiveSnapshotOptions<TSnapshot> {
  fetchSnapshot?: () => Promise<TSnapshot>;
  onOffline: () => void;
  onSnapshot: (snapshot: TSnapshot) => void;
  pollIntervalMs?: number;
}

export function useLiveSnapshot<TSnapshot = LiveSnapshot>({
  fetchSnapshot = fetchLiveSnapshot as () => Promise<TSnapshot>,
  onOffline,
  onSnapshot,
  pollIntervalMs = 30_000
}: UseLiveSnapshotOptions<TSnapshot>) {
  const [snapshot, setSnapshot] = useState<TSnapshot | null>(null);
  const [liveStatus, setLiveStatus] = useState<LiveConnectionStatus>("loading");

  const refresh = useCallback(async () => {
    const nextSnapshot = await fetchSnapshot();
    setSnapshot(nextSnapshot);
    setLiveStatus("online");
    onSnapshot(nextSnapshot);
    return nextSnapshot;
  }, [fetchSnapshot, onSnapshot]);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const nextSnapshot = await fetchSnapshot();
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
  }, [fetchSnapshot, onOffline, onSnapshot, pollIntervalMs]);

  return { liveStatus, refresh, setLiveStatus, setSnapshot, snapshot };
}
