import { Ban, Check, Clipboard, ExternalLink, FileSearch, RefreshCw, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchEntityEvidence, type EntityEvidence, type EvidenceSelection } from "../api/evidence";
import { resolveAccountChange, resolveApproval, resolveClientOnboarding, resolveHoldingUpdate, type LiveRow } from "../api/live";
import { resolveClientCashEntry, resolveClientReportDelivery } from "../api/portfolioOffice";

interface Props {
  onClose: () => void;
  onChanged?: () => void | Promise<void>;
  selection: EvidenceSelection | null;
}

function label(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function text(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not recorded";
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}

function rowTitle(row: LiveRow): string {
  for (const key of ["title", "subject", "task_title", "strategy_name", "artifact_key", "row_ref", "approval_type", "id"]) {
    if (row[key] !== null && row[key] !== undefined && row[key] !== "") return String(row[key]);
  }
  return "Linked evidence record";
}

function rowStatus(row: LiveRow): string {
  for (const key of ["status", "processing_status", "review_status", "decision_status", "reconciliation_status", "risk_level"]) {
    if (row[key] !== null && row[key] !== undefined && row[key] !== "") return String(row[key]);
  }
  return "recorded";
}

function usefulPath(record: LiveRow): string {
  for (const key of ["note_path", "memo_note_path", "output_note_path", "local_path", "artifact_location", "source_location"]) {
    if (record[key]) return String(record[key]);
  }
  return "";
}

function DetailFields({ record }: { record: LiveRow }) {
  const entries = Object.entries(record).filter(([, value]) => value !== null && value !== undefined && value !== "");
  if (!entries.length) return <p className="evidence-empty">No structured fields were returned.</p>;
  return (
    <dl className="evidence-field-grid">
      {entries.map(([key, value]) => (
        <div className={typeof value === "object" ? "evidence-field evidence-field-wide" : "evidence-field"} key={key}>
          <dt>{label(key)}</dt>
          <dd>{typeof value === "object" ? <pre>{text(value)}</pre> : text(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

export default function EvidenceDrawer({ onChanged, onClose, selection }: Props) {
  const [evidence, setEvidence] = useState<EntityEvidence | null>(null);
  const [busy, setBusy] = useState(false);
  const [decisionBusy, setDecisionBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLElement>(null);
  const onCloseRef = useRef(onClose);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  onCloseRef.current = onClose;

  const load = useCallback(async () => {
    if (!selection) return;
    setBusy(true);
    setError("");
    try {
      setEvidence(await fetchEntityEvidence(selection.kind, selection.key));
    } catch (reason) {
      setEvidence(null);
      setError(reason instanceof Error ? reason.message : "Evidence chain unavailable");
    } finally {
      setBusy(false);
    }
  }, [selection]);

  useEffect(() => {
    if (!selection) return;
    setEvidence(null);
    setNotice("");
    void load();
    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    window.requestAnimationFrame(() => closeButtonRef.current?.focus());
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab" || !drawerRef.current) return;
      const focusable = [...drawerRef.current.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), details > summary, input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')]
        .filter((element) => element.getClientRects().length > 0);
      if (!focusable.length) {
        event.preventDefault();
        closeButtonRef.current?.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
      previousFocusRef.current?.focus();
    };
  }, [load, selection]);

  const record = evidence?.record ?? selection?.record ?? {};
  const path = usefulPath(record);
  const sourceUrl = String(record.source_url ?? "");
  const canResolveApproval = evidence?.entity_kind === "approval" && String(record.status ?? "").toLowerCase() === "pending";
  const relationCount = useMemo(() => evidence?.groups.reduce((sum, group) => sum + group.records.length, 0) ?? 0, [evidence]);

  if (!selection) return null;

  const copyPath = async () => {
    if (!path) return;
    try {
      await navigator.clipboard.writeText(path);
      setNotice("Path copied to clipboard.");
    } catch {
      setError("Clipboard permission was denied. The path remains visible below.");
    }
  };

  const decide = async (status: "approved" | "rejected") => {
    if (!canResolveApproval || decisionBusy) return;
    const verb = status === "approved" ? "approve" : "reject";
    if (!window.confirm(`${verb[0].toUpperCase()}${verb.slice(1)} approval #${selection.key}? This records a human decision but does not place a broker order.`)) return;
    setDecisionBusy(true);
    setError("");
    setNotice("");
    try {
      const approvalType = String(record.approval_type ?? "");
      const common = { approval_id: selection.key, decision: status, decided_by: "Devarsh", actor: "Devarsh", decision_notes: `Decision recorded from the central Approval Board for ${approvalType || "approval"}.` };
      if (approvalType === "client_onboarding") await resolveClientOnboarding(common);
      else if (approvalType === "account_change") await resolveAccountChange(common);
      else if (approvalType === "holding_update") await resolveHoldingUpdate({ ...common, evidence: [{ table: "agent.approvals", id: selection.key, reviewed_in: "Approval Board" }] });
      else if (approvalType === "client_cash_entry") await resolveClientCashEntry(common);
      else if (approvalType === "client_report_send") await resolveClientReportDelivery(common);
      else await resolveApproval({ approval_id: selection.key, decided_by: "Devarsh", status });
      setNotice(`Approval #${selection.key} ${status}. Broker execution remains governed by separate risk gates.`);
      await load();
      await onChanged?.();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Approval decision failed");
    } finally {
      setDecisionBusy(false);
    }
  };

  return (
    <div className="evidence-drawer-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <aside aria-busy={busy} aria-describedby="evidence-drawer-description" aria-label={`${selection.title} evidence chain`} aria-modal="true" className="evidence-drawer" ref={drawerRef} role="dialog">
        <header className="evidence-drawer-header">
          <div><span><FileSearch size={14} aria-hidden="true" />Evidence chain</span><h2>{selection.title}</h2><p id="evidence-drawer-description">{selection.subtitle || `${label(selection.kind)} ${selection.key}`} · {relationCount} linked records</p></div>
          <button aria-label="Close evidence drawer" onClick={onClose} ref={closeButtonRef} title="Close evidence drawer" type="button"><X size={18} aria-hidden="true" /></button>
        </header>

        <div className="evidence-drawer-toolbar">
          <button disabled={busy} onClick={() => void load()} type="button"><RefreshCw size={14} aria-hidden="true" />{busy ? "Loading" : "Refresh"}</button>
          {path ? <button onClick={() => void copyPath()} type="button"><Clipboard size={14} aria-hidden="true" />Copy path</button> : null}
          {sourceUrl ? <a href={sourceUrl} rel="noreferrer" target="_blank"><ExternalLink size={14} aria-hidden="true" />Open source</a> : null}
          <span>{evidence?.generated_at ? new Date(evidence.generated_at).toLocaleString("en-IN") : "Loading live evidence"}</span>
        </div>

        {canResolveApproval ? (
          <section className="evidence-decision-bar" aria-label="Approval decision actions">
            <div><strong>Human decision required</strong><p>This updates the approval record only. Capital and broker execution gates remain independent.</p></div>
            <button className="evidence-reject" disabled={decisionBusy} onClick={() => void decide("rejected")} type="button"><Ban size={14} aria-hidden="true" />Reject</button>
            <button className="evidence-approve" disabled={decisionBusy} onClick={() => void decide("approved")} type="button"><Check size={14} aria-hidden="true" />Approve</button>
          </section>
        ) : null}

        {error ? <div className="error-strip">{error}</div> : null}
        {notice ? <div className="success-strip">{notice}</div> : null}

        <div className="evidence-drawer-body">
          <section className="evidence-primary-record"><div className="evidence-section-heading"><span>Primary record</span><strong>{rowStatus(record)}</strong></div><DetailFields record={record} /></section>
          {evidence?.groups.map((group) => group.records.length ? (
            <section className="evidence-group" key={group.key}>
              <div className="evidence-section-heading"><span>{group.label}</span><strong>{group.records.length}</strong></div>
              <div className="evidence-group-list">
                {group.records.map((row, index) => (
                  <details key={`${group.key}-${rowTitle(row)}-${index}`}>
                    <summary><span><strong>{rowTitle(row)}</strong><small>{rowStatus(row)}</small></span><span>Inspect</span></summary>
                    <DetailFields record={row} />
                  </details>
                ))}
              </div>
            </section>
          ) : null)}
          {!busy && evidence && !relationCount ? <p className="evidence-empty">No linked records were found for this entity.</p> : null}
        </div>
      </aside>
    </div>
  );
}
