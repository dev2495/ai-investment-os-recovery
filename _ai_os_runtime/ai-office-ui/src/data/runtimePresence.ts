import { useEffect, useState } from "react";
import type { LiveRow } from "./liveRow";

export function hasLiveLease(row: LiveRow, now = Date.now()): boolean {
  const expires = Date.parse(String(row.lease_expires_at ?? row.expires_at ?? ""));
  return row.has_live_lease === true && Number.isFinite(expires) && expires > now;
}

export function runtimePresence(row: LiveRow): string {
  if (row.has_live_lease === true && !hasLiveLease(row)) return "STALE";
  return String(row.presence_state ?? "UNVERIFIED");
}

/** Expire visible leases locally even while the network or snapshot is down. */
export function useLeaseClock(): void {
  const [, tick] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => tick((value) => value + 1), 2000);
    return () => window.clearInterval(timer);
  }, []);
}
