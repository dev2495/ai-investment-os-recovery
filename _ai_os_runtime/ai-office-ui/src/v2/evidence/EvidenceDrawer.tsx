/**
 * Evidence Drawer
 *
 * The single, elevated surface for inspecting any entity's full evidence
 * chain and resolving pending approvals. Kept + enhanced from the old
 * EvidenceDrawer (the most sophisticated component in the repo).
 *
 * Opens from anywhere via the UI store: openEvidence({ kind, key, title }).
 */

import React from "react";
import { X, FileText, Check, AlertTriangle, ExternalLink, ChevronRight } from "lucide-react";
import { useUIStore } from "../store";
import { useEntityEvidence, useResolveApproval } from "../data/queries";
import { text, timestamp, num, formatRelative } from "../data/liveRow";
import { Drawer, Button, StatusPill, Skeleton, Empty } from "../system/primitives";
import { EvidenceDrawerCss } from "./EvidenceDrawer.css";

export function EvidenceDrawer() {
  const target = useUIStore((s) => s.evidenceTarget);
  const close = useUIStore((s) => s.closeEvidence);
  const pushToast = useUIStore((s) => s.pushToast);

  const { data, isLoading, error } = useEntityEvidence(target?.kind ?? null, target?.key ?? null);
  const resolveApproval = useResolveApproval();

  const open = Boolean(target);

  function handleResolve(decision: "approved" | "rejected") {
    if (!target) return;
    const approvalId = num(data?.record, "approval_id", num(data?.record, "id", 0));
    resolveApproval.mutate(
      { approval_id: approvalId, decision, actor: "Devarsh", notes: `Resolved via Evidence Drawer` },
      {
        onSuccess: () => {
          pushToast({
            title: decision === "approved" ? "Approved" : "Rejected",
            message: target.title,
            tone: decision === "approved" ? "ok" : "warn",
            duration: 3000,
          });
          close();
        },
        onError: (err) => {
          pushToast({
            title: "Resolution failed",
            message: err.message,
            tone: "risk",
            duration: 5000,
          });
        },
      }
    );
  }

  return (
    <>
      <style>{EvidenceDrawerCss}</style>
      <Drawer
        open={open}
        onClose={close}
        title={target?.title}
        subtitle={target ? `${target.kind}${target.subtitle ? ` · ${target.subtitle}` : ""}` : ""}
        icon={FileText}
        width={560}
        actions={
          data && target?.kind === "approval" ? (
            <div className="aios-evidence__resolve">
              <Button variant="danger" size="sm" icon={X} onClick={() => handleResolve("rejected")} disabled={resolveApproval.isPending}>
                Reject
              </Button>
              <Button variant="primary" size="sm" icon={Check} onClick={() => handleResolve("approved")} disabled={resolveApproval.isPending}>
                Approve
              </Button>
            </div>
          ) : undefined
        }
      >
        {isLoading && <EvidenceSkeleton />}

        {error && (
          <Empty
            icon={AlertTriangle}
            title="Couldn't load evidence"
            description={error.message}
          />
        )}

        {data && !isLoading && (
          <div className="aios-evidence">
            {/* Primary record */}
            <section className="aios-evidence__section">
              <div className="aios-evidence__section-head">
                <h4>Record</h4>
                <span className="aios-evidence__generated">
                  {formatRelative(data.generated_at)}
                </span>
              </div>
              <RecordCard record={data.record} />
            </section>

            {/* Related evidence groups */}
            {data.groups.map((group) => (
              <section key={group.key} className="aios-evidence__section">
                <div className="aios-evidence__section-head">
                  <h4>{group.label}</h4>
                  <span className="aios-evidence__count">{group.records.length}</span>
                </div>
                {group.records.length === 0 ? (
                  <div className="aios-evidence__empty-group">No related records.</div>
                ) : (
                  <div className="aios-evidence__group-list">
                    {group.records.map((rec, i) => (
                      <RecordRow key={i} record={rec} />
                    ))}
                  </div>
                )}
              </section>
            ))}
          </div>
        )}
      </Drawer>
    </>
  );
}

function EvidenceSkeleton() {
  return (
    <div className="aios-evidence__skeleton">
      <Skeleton variant="title" />
      <Skeleton variant="text" />
      <Skeleton variant="text" width="80%" />
      <div style={{ height: 16 }} />
      <Skeleton variant="title" width="40%" />
      <Skeleton variant="text" />
      <Skeleton variant="text" />
      <Skeleton variant="text" width="70%" />
    </div>
  );
}

/** Render the primary record as key-value pairs (heuristic field selection). */
function RecordCard({ record }: { record: Record<string, unknown> }) {
  const keys = Object.keys(record).filter((k) => {
    const v = record[k];
    return v !== null && v !== undefined && v !== "" && typeof v !== "object";
  }).slice(0, 12);
  return (
    <div className="aios-evidence__record-card">
      {keys.map((key) => (
        <div key={key} className="aios-evidence__kv">
          <span className="aios-evidence__kv-label">{key.replace(/_/g, " ")}</span>
          <span className="aios-evidence__kv-value">{formatValue(record[key])}</span>
        </div>
      ))}
    </div>
  );
}

function RecordRow({ record }: { record: Record<string, unknown> }) {
  const title = text(record, "title") || text(record, "name") || text(record, "subject") || text(record, "symbol") || "Untitled";
  const sub = text(record, "status") || text(record, "kind") || text(record, "type") || "";
  const ts = timestamp(record, "created_at") || timestamp(record, "updated_at") || timestamp(record, "generated_at");
  return (
    <div className="aios-evidence__record-row">
      <ChevronRight size={14} />
      <div className="aios-evidence__record-row-main">
        <div className="aios-evidence__record-row-title">{title}</div>
        <div className="aios-evidence__record-row-meta">
          {sub && <span>{sub}</span>}
          {ts && <span>· {formatRelative(ts)}</span>}
        </div>
      </div>
      {sub && <StatusPill status={sub} />}
    </div>
  );
}

function formatValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v === "number") return String(v);
  if (typeof v === "string") {
    // ISO timestamp heuristic
    if (/^\d{4}-\d{2}-\d{2}T/.test(v)) return formatRelative(v);
    return v;
  }
  return String(v);
}
