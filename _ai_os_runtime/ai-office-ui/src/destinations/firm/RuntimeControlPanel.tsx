import React from "react";
import { Activity, AlertTriangle, Pause, Play, RefreshCw, X } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { get, post } from "../../data/client";
import { queryKeys } from "../../data/queries";
import { formatRelative, num, text, value } from "../../data/liveRow";
import type { LiveRow } from "../../data/liveRow";
import { useRuntimeEvents } from "../../data/runtimeEvents";
import { Badge, Button, Empty, Panel, StatusPill } from "../../system/primitives";

export function RuntimeControlPanel({ runtime }: { runtime: LiveRow }) {
  const client = useQueryClient();
  const available = runtime.available === true;
  const connection = useRuntimeEvents(available, num(runtime, "event_cursor"));
  const tasks = value<LiveRow[]>(runtime, "tasks", []);
  const workers = value<LiveRow[]>(runtime, "workers", []);
  const events = value<LiveRow[]>(runtime, "events", []);
  const [selected, setSelected] = React.useState<number | null>(null);
  const [cancel, setCancel] = React.useState<number | null>(null);
  const [message, setMessage] = React.useState("");
  const detail = useQuery({
    queryKey: ["runtime-task", selected], enabled: selected !== null,
    queryFn: ({ signal }) => get<{ task: LiveRow; steps: LiveRow[] }>(`/api/v1/tasks/${selected}`, { signal }),
  });
  const control = useMutation({
    mutationFn: ({ id, action }: { id: number; action: "pause" | "resume" | "cancel" }) => post<LiveRow>(`/api/v1/tasks/${id}/${action}`, {}),
    onSuccess: () => {
      setCancel(null);
      setMessage("Control recorded. An active task applies it at the next safe boundary.");
      void client.invalidateQueries({ queryKey: queryKeys.office });
      void client.invalidateQueries({ queryKey: ["runtime-task"] });
    },
    onError: (error) => setMessage(error.message),
  });
  return <Panel icon={Activity} title="Worker & task control" actions={<Badge tone={connection === "live" ? "ok" : "warn"}>{connection === "live" ? "live events" : connection}</Badge>}>
    {runtime.synthetic_only === true && <Badge tone="warn">Synthetic local test</Badge>}
    <p style={{ color: "var(--text-muted)", marginTop: 0, fontSize: "var(--text-xs)" }}>
      Live work requires an unexpired lease. Historical research and graph runs keep their own evidence and review gates.
    </p>
    {!available ? <Empty icon={AlertTriangle} title="Live ownership is not verified" description="The lease runtime is unavailable or not installed. Existing activity remains historical; no worker is presented as live." /> : <>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)", marginBottom: "var(--space-3)" }}>
        <Badge>{workers.length} recent workers</Badge>
        <Badge>{workers.reduce((sum, worker) => sum + num(worker, "active_leases"), 0)} active leases</Badge>
        <Badge tone="warn">Broker writes locked</Badge>
        <Button size="sm" variant="ghost" icon={RefreshCw} onClick={() => void client.invalidateQueries({ queryKey: queryKeys.office })}>Refresh evidence</Button>
      </div>
      {tasks.length === 0 ? <Empty title="No lease-managed tasks yet" description="This is not a failure. Workers appear here when they claim a task through the durable runtime." /> : <div style={{ display: "grid", gap: "var(--space-3)" }}>
        {tasks.slice(0, 12).map((task) => {
          const id = num(task, "id");
          const state = text(task, "runtime_state", text(task, "status"));
          const expired = task.lease_status === "ACTIVE" && Date.parse(text(task, "expires_at")) <= Date.now();
          const blocked = ["blocked", "failed"].includes(text(task, "status"));
          const resumable = task.status === "paused" && task.has_side_effects !== true;
          return <article key={id} style={{ border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: "var(--space-3)" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "var(--space-2)" }}>
              <Button variant="ghost" size="sm" onClick={() => setSelected(selected === id ? null : id)}>Task #{id} · inspect steps</Button>
              <StatusPill status={expired ? "stale" : state.toLowerCase()}>{expired ? "STALE · recovery pending" : state.replace(/_/g, " ")}</StatusPill>
            </div>
            <p style={{ margin: "8px 0", color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>
              Attempt {num(task, "attempt")} · {text(task, "worker_id", "no worker").slice(0, 8)} · updated {formatRelative(text(task, "updated_at"))}
              {task.control_requested ? ` · ${text(task, "control_requested")} requested` : ""}
            </p>
            {(blocked || expired || (task.status === "paused" && !resumable)) && <p style={{ color: "var(--status-warn)", fontSize: "var(--text-xs)" }}>
              {task.has_side_effects ? "An output or tool step may have run. Inspect its receipt before any retry; this panel cannot approve replay." : "Inspect the task history. The reaper retries only explicitly idempotent reads within the recorded attempt limit."}
            </p>}
            <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)" }}>
              {["queued", "in_progress"].includes(text(task, "status")) && <Button size="sm" icon={Pause} disabled={control.isPending || Boolean(task.control_requested)} onClick={() => control.mutate({ id, action: "pause" })}>Pause task {id}</Button>}
              {resumable && <Button size="sm" icon={Play} disabled={control.isPending} onClick={() => control.mutate({ id, action: "resume" })}>Resume task {id}</Button>}
              {["queued", "in_progress", "paused"].includes(text(task, "status")) && <Button size="sm" variant="ghost" icon={X} disabled={control.isPending} onClick={() => setCancel(id)}>Cancel task {id}</Button>}
              {cancel === id && <><span style={{ fontSize: "var(--text-xs)", alignSelf: "center" }}>Cancel future work? Existing evidence stays.</span><Button size="sm" disabled={control.isPending} onClick={() => control.mutate({ id, action: "cancel" })}>Confirm cancellation</Button><Button size="sm" variant="ghost" onClick={() => setCancel(null)}>Keep task</Button></>}
            </div>
            {selected === id && <div style={{ marginTop: "var(--space-3)", fontSize: "var(--text-xs)" }}>
              {detail.isLoading ? "Loading recorded steps…" : detail.error ? detail.error.message : (detail.data?.steps ?? []).length === 0 ? "No step has started." : <ol style={{ paddingLeft: "var(--space-4)" }}>{detail.data?.steps.map((step) => <li key={num(step, "id")} style={{ marginBottom: 6 }}>{text(step, "step_key").replace(/_/g, " ")} · {text(step, "state")} · {step.has_receipt ? "receipt recorded" : text(step, "side_effect_status") === "none" ? "read-only step" : "receipt unresolved"}</li>)}</ol>}
            </div>}
          </article>;
        })}
      </div>}
      <div role="status" style={{ marginTop: "var(--space-2)", fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{message}</div>
      <details style={{ marginTop: "var(--space-3)", fontSize: "var(--text-xs)" }}><summary>Recent runtime events · {events.length}</summary>
        <ol style={{ paddingLeft: "var(--space-4)" }}>{events.slice(0, 15).map((event) => <li key={num(event, "id")} style={{ marginTop: 8 }}>Task #{num(event, "task_id")} · {text(event, "event_type").replace(/_/g, " ")} · {text(event, "state").replace(/_/g, " ")} · {formatRelative(text(event, "occurred_at"))}</li>)}</ol>
      </details>
    </>}
  </Panel>;
}
