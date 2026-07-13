import { Clock3, CloudOff, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

type ConnectionStatus = "loading" | "online" | "offline";

interface Props {
  generatedAt?: string;
  staleAfterMs?: number;
  status: ConnectionStatus;
}

function ageLabel(ageMs: number): string {
  if (ageMs < 60_000) return `${Math.max(0, Math.round(ageMs / 1000))} seconds ago`;
  if (ageMs < 3_600_000) return `${Math.round(ageMs / 60_000)} minutes ago`;
  return `${Math.round(ageMs / 3_600_000)} hours ago`;
}

export default function WorkspaceFreshness({ generatedAt, staleAfterMs = 90_000, status }: Props) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 15_000);
    return () => window.clearInterval(timer);
  }, []);

  const generatedTime = useMemo(() => {
    const parsed = generatedAt ? new Date(generatedAt).getTime() : Number.NaN;
    return Number.isFinite(parsed) ? parsed : null;
  }, [generatedAt]);
  const ageMs = generatedTime === null ? null : Math.max(0, now - generatedTime);
  const stale = ageMs !== null && ageMs > staleAfterMs;
  const state = status === "offline" ? "offline" : status === "loading" && generatedTime === null ? "loading" : stale ? "stale" : "fresh";

  return (
    <div aria-live="polite" className={`workspace-freshness freshness-${state}`}>
      {state === "offline" ? <CloudOff size={14} aria-hidden="true" /> : state === "loading" ? <RefreshCw className="freshness-spin" size={14} aria-hidden="true" /> : <Clock3 size={14} aria-hidden="true" />}
      <span>{state === "offline" ? "Warehouse offline" : state === "loading" ? "Loading live snapshot" : state === "stale" ? "Snapshot stale" : "Live snapshot fresh"}</span>
      <strong>{ageMs === null ? "No successful read yet" : `Generated ${ageLabel(ageMs)}`}</strong>
    </div>
  );
}
