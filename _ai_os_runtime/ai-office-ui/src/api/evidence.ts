import type { LiveRow } from "./live";

export type EvidenceEntityKind = "agent_message" | "task" | "approval" | "committee" | "strategy" | "integration" | "artifact" | "lineage";

export interface EvidenceSelection {
  kind: EvidenceEntityKind;
  key: string;
  title: string;
  subtitle?: string;
  record?: LiveRow;
}

export interface EvidenceGroup {
  key: string;
  label: string;
  records: LiveRow[];
}

export interface EntityEvidence {
  entity_kind: EvidenceEntityKind;
  entity_key: string;
  generated_at: string;
  record: LiveRow;
  groups: EvidenceGroup[];
}

const API_URL = (import.meta.env.VITE_AI_OS_API_URL || "http://127.0.0.1:8765").replace(/\/$/, "");

export async function fetchEntityEvidence(kind: EvidenceEntityKind, key: string): Promise<EntityEvidence> {
  const response = await fetch(`${API_URL}/api/evidence/entity/${encodeURIComponent(kind)}/${encodeURIComponent(key)}`, { cache: "no-store" });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload?.message || payload?.error || `Evidence API returned ${response.status}`);
  }
  return payload as EntityEvidence;
}
