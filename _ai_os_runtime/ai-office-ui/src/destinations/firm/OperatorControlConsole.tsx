import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Beaker, CheckCircle2, Clock3, Cpu, Pause, Play, RotateCcw, ShieldCheck, TriangleAlert, Wrench } from "lucide-react";
import { get, post } from "../../data/client";
import type { LiveRow } from "../../data/liveRow";
import { formatCurrency, formatRelative, num, raw, text } from "../../data/liveRow";
import { Badge, Button, Drawer, Empty, Field, Metric, MetricTile, Panel, Select, StatusPill, TextArea, TextInput } from "../../system/primitives";
import { useUIStore } from "../../store";
import { OperatorControlConsoleCss } from "./OperatorControlConsole.css";

type ModelFabricSnapshot = {
  available?: boolean;
  reason?: string;
  bindings?: LiveRow[];
  history?: LiveRow[];
  qualifications?: LiveRow[];
  recent_calls?: LiveRow[];
  audit?: LiveRow[];
  provider_calls_made?: boolean;
  broker_write_allowed?: boolean;
};

type DoctorSnapshot = {
  available?: boolean;
  reason?: string;
  status?: string;
  latest_run?: LiveRow;
  checks?: LiveRow[];
  registry?: LiveRow[];
  history?: LiveRow[];
  broker_write_allowed?: boolean;
};

type RoutineSnapshot = {
  available?: boolean;
  reason?: string;
  routines?: LiveRow[];
  history?: LiveRow[];
  broker_write_allowed?: boolean;
};

type MutationRequest = { path: string; body: Record<string, unknown>; label: string };
type ModelReviewAction = "promote" | "rollback" | "disable";
type RoutineControlAction = "enable" | "pause";

const CONTROL_KEYS = {
  modelFabric: ["operator-model-fabric"] as const,
  doctor: ["operator-doctor"] as const,
  routines: ["operator-routines"] as const,
};

const ROUTINE_CATALOG = [
  { key: "daily_system_health", name: "Daily system health" },
  { key: "obsidian_incremental_index", name: "Obsidian incremental index" },
  { key: "research_company_change_monitor", name: "Company change monitor" },
  { key: "stale_task_and_lease_reaper", name: "Stale task and lease reaper" },
  { key: "zerodha_session_and_stream_watch", name: "Session and stream watch" },
] as const;

function rows(value: unknown): LiveRow[] {
  return Array.isArray(value) ? value.filter((item): item is LiveRow => Boolean(item) && typeof item === "object") : [];
}

function object(value: unknown): LiveRow {
  return value && typeof value === "object" && !Array.isArray(value) ? value as LiveRow : {};
}

function display(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not recorded";
  return String(value);
}

function relativeOrMissing(value: string): string {
  return value ? formatRelative(value) : "Not recorded";
}

function outcome(row: LiveRow | null): string {
  if (!row) return "";
  const state = text(row, "status", text(row, "state"));
  return state ? `Recorded outcome: ${state.replace(/_/g, " ")}.` : "Receipt received; outcome was not recorded by the API.";
}

function friendlyFailure(error: unknown, control: string): string {
  const status = num(error && typeof error === "object" ? error as LiveRow : {}, "status", 0);
  if (status === 401 || status === 403) return `Authenticated operator permission is required for ${control}.`;
  if (status === 404 || status === 501) return `${control} is not live on this runtime.`;
  if (status === 409) return `${control} was blocked by a governance or current-state check.`;
  return `${control} could not be verified. No successful outcome is being assumed.`;
}

function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return <div className="operator-console__fact"><span>{label}</span><b>{value || "Not recorded"}</b></div>;
}

function useOperatorMutation(invalidate: readonly (readonly string[])[]) {
  const queryClient = useQueryClient();
  return useMutation<LiveRow, Error, MutationRequest>({
    mutationFn: ({ path, body }) => post<LiveRow>(path, body),
    onSuccess: async () => {
      await Promise.all(invalidate.map((queryKey) => queryClient.invalidateQueries({ queryKey })));
    },
  });
}

export function ModelFabricConsole({ legacyRoutes }: { legacyRoutes: LiveRow[] }) {
  const pushToast = useUIStore((state) => state.pushToast);
  const fabric = useQuery<ModelFabricSnapshot>({
    queryKey: CONTROL_KEYS.modelFabric,
    queryFn: () => get<ModelFabricSnapshot>("/api/v1/model-fabric"),
    retry: false,
    refetchInterval: 30_000,
  });
  const action = useOperatorMutation([CONTROL_KEYS.modelFabric]);
  const [receipt, setReceipt] = React.useState<LiveRow | null>(null);
  const [proposeOpen, setProposeOpen] = React.useState(false);
  const [review, setReview] = React.useState<{ action: ModelReviewAction; binding: LiveRow; version: LiveRow } | null>(null);
  const [bindingKey, setBindingKey] = React.useState("");
  const [selectorKind, setSelectorKind] = React.useState("agent");
  const [selectorValue, setSelectorValue] = React.useState("");
  const [taskClass, setTaskClass] = React.useState("filing_analysis");
  const [primaryRoute, setPrimaryRoute] = React.useState("");
  const [reasoning, setReasoning] = React.useState("none");
  const [approvalId, setApprovalId] = React.useState("");
  const [confirmation, setConfirmation] = React.useState("");

  const snapshot = fabric.data;
  const available = snapshot?.available === true;
  const bindings = rows(snapshot?.bindings);
  const history = rows(snapshot?.history);
  const qualifications = rows(snapshot?.qualifications);
  const calls = rows(snapshot?.recent_calls);
  const routeOptions = Array.from(new Set([
    ...legacyRoutes.map((row) => text(row, "route_name", text(row, "name"))),
    ...bindings.map((row) => text(row, "primary_route")),
    ...qualifications.map((row) => text(row, "route_name")),
  ].filter(Boolean))).sort();
  const degradedCalls = calls.filter((row) => raw(row, "degraded") === true || ["failed", "blocked", "error"].includes(text(row, "status").toLowerCase())).length;
  const passedQualifications = qualifications.filter((row) => text(row, "state").toLowerCase() === "passed").length;

  React.useEffect(() => {
    if (!primaryRoute && routeOptions[0]) setPrimaryRoute(routeOptions[0]);
  }, [primaryRoute, routeOptions]);

  async function run(request: MutationRequest) {
    try {
      const result = await action.mutateAsync(request);
      setReceipt(result);
      pushToast({ title: `${request.label} receipt returned`, message: outcome(result), tone: ["passed", "enabled", "promoted", "rolled_back", "completed"].includes(text(result, "status", text(result, "state")).toLowerCase()) ? "ok" : "warn", duration: 5000 });
      return true;
    } catch (error) {
      pushToast({ title: `${request.label} not completed`, message: friendlyFailure(error, request.label), tone: "risk", duration: 5500 });
      return false;
    }
  }

  async function proposeBinding() {
    const complete = bindingKey.trim() && selectorValue.trim() && taskClass.trim() && primaryRoute;
    if (!complete) return;
    const ok = await run({
      path: "/api/v1/model-fabric/propose",
      label: "Binding proposal",
      body: {
        confirmed: true, binding_key: bindingKey.trim(), selector_kind: selectorKind, selector_value: selectorValue.trim(),
        task_class: taskClass.trim(), primary_route: primaryRoute, fallback_routes: [], fallback_policy: "fail_closed",
        reasoning_profile: reasoning, context_budget: 8192, max_output_tokens: 1800, temperature: 0.1,
        privacy_classes: ["public", "internal"], required_evaluations: ["numeric", "citation", "missing_data", "prompt_injection"],
      },
    });
    if (ok) setProposeOpen(false);
  }

  function currentQualification(binding: LiveRow): LiveRow {
    const id = num(binding, "qualification_id");
    return qualifications.find((row) => num(row, "id") === id)
      ?? qualifications.find((row) => text(row, "route_name") === text(binding, "primary_route") && text(row, "task_class") === text(binding, "task_class"))
      ?? {};
  }

  function historicalVersion(binding: LiveRow): LiveRow {
    return history.find((row) => text(row, "binding_key") === text(binding, "binding_key") && num(row, "version_id") !== num(binding, "version_id")) ?? {};
  }

  function openReview(nextAction: ModelReviewAction, binding: LiveRow, version: LiveRow = binding) {
    setReview({ action: nextAction, binding, version });
    setApprovalId("");
    setConfirmation("");
  }

  async function submitReview() {
    if (!review) return;
    const required = review.action.toUpperCase();
    if (confirmation.trim().toUpperCase() !== required) return;
    const binding = review.binding;
    const version = review.version;
    const body: Record<string, unknown> = review.action === "disable"
      ? { binding_key: text(binding, "binding_key"), confirmed: true }
      : review.action === "rollback"
        ? { binding_key: text(binding, "binding_key"), version_id: num(version, "version_id", num(version, "id")), approval_id: Number(approvalId), confirmed: true }
        : { version_id: num(version, "version_id", num(version, "id")), approval_id: Number(approvalId), confirmed: true };
    const ok = await run({ path: `/api/v1/model-fabric/${review.action}`, body, label: `${review.action} binding` });
    if (ok) setReview(null);
  }

  return (
    <div className="operator-console" role="region" aria-label="Governed model fabric">
      <style>{OperatorControlConsoleCss}</style>
      <div className={`operator-console__notice ${available ? "is-ready" : "is-risk"}`}>
        {available ? <CheckCircle2 size={18} aria-hidden="true" /> : <TriangleAlert size={18} aria-hidden="true" />}
        <div><strong>{available ? "Governed binding registry is available" : "Model Fabric unavailable"}</strong><span>{available ? "Every row below is an exact stored binding version and qualification state." : "No model route health, qualification, or promotion state can be inferred from the legacy route list."}</span></div>
        <code>GET /api/v1/model-fabric</code>
      </div>
      <div className="operator-console__summary">
        <MetricTile><Metric label="Bound versions" value={available ? bindings.length : "—"} /></MetricTile>
        <MetricTile tone={available && passedQualifications ? "ok" : "warn"}><Metric label="Qualified routes" value={available ? passedQualifications : "—"} /></MetricTile>
        <MetricTile tone={degradedCalls ? "risk" : undefined}><Metric label="Degraded / blocked calls" value={available ? degradedCalls : "—"} /></MetricTile>
        <MetricTile><Metric label="Provider calls by this view" value="0" /></MetricTile>
      </div>
      <Panel icon={Cpu} title="Exact model bindings" actions={<Button size="sm" icon={Cpu} onClick={() => setProposeOpen(true)} disabled={!available}>Propose binding</Button>}>
        {!available ? <Empty icon={Cpu} title="Binding registry not available" /> : bindings.length === 0 ? <Empty icon={Cpu} title="No governed bindings recorded" /> : (
          <div className="operator-console__bindings">
            {bindings.map((binding, index) => {
              const qualification = currentQualification(binding);
              const previous = historicalVersion(binding);
              const state = raw(binding, "enabled") === false ? "disabled" : text(qualification, "state", text(binding, "qualification_state", "not_qualified"));
              const route = text(binding, "primary_route");
              const legacy = legacyRoutes.find((row) => text(row, "route_name", text(row, "name")) === route) ?? {};
              const model = text(qualification, "model_name", text(legacy, "default_model", text(legacy, "model_name")));
              return (
                <div className="operator-console__binding" key={text(binding, "binding_key", `binding-${index}`)}>
                  <div><strong>{text(binding, "binding_key", "Unnamed binding")}</strong><small>Version {display(raw(binding, "version"))} · {text(binding, "selector_kind", "selector not recorded")} {text(binding, "selector_value")}</small></div>
                  <div><strong className="operator-console__route">{display(route)}</strong><small>{display(model)} · reasoning {display(raw(binding, "reasoning_profile"))}</small></div>
                  <div><StatusPill status={state} /><small>Qualification #{display(raw(binding, "qualification_id"))}</small></div>
                  <div className="operator-console__actions">
                    <Button size="sm" variant="ghost" icon={Beaker} disabled={action.isPending || !route} onClick={() => run({ path: "/api/v1/model-fabric/qualify", label: "Route qualification", body: { route_name: route, task_class: text(binding, "task_class"), confirmed: true } })}>Qualify</Button>
                    <Button size="sm" variant="ghost" icon={Play} disabled={action.isPending || !num(binding, "version_id")} onClick={() => run({ path: "/api/v1/model-fabric/test", label: "Binding test", body: { version_id: num(binding, "version_id"), confirmed: true } })}>Test</Button>
                    <Button size="sm" variant="ghost" icon={ShieldCheck} disabled={action.isPending || state !== "passed"} onClick={() => openReview("promote", binding)}>Review promote</Button>
                    {Object.keys(previous).length > 0 && <Button size="sm" variant="ghost" icon={RotateCcw} disabled={action.isPending} onClick={() => openReview("rollback", binding, previous)}>Review rollback</Button>}
                    <Button size="sm" variant="ghost" icon={Pause} disabled={action.isPending || raw(binding, "enabled") === false} onClick={() => openReview("disable", binding)}>Review disable</Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Panel>
      {receipt && <div className="operator-console__receipt" role="status"><strong>Latest control receipt.</strong> {outcome(receipt)} This view does not interpret HTTP success as model health.</div>}

      <Drawer open={proposeOpen} onClose={() => setProposeOpen(false)} title="Propose governed binding" subtitle="Creates a disabled version only; it does not call or promote a model." icon={Cpu} width={620} footer={<div className="operator-console__actions"><Button variant="ghost" onClick={() => setProposeOpen(false)}>Cancel</Button><Button variant="primary" disabled={action.isPending || !bindingKey.trim() || !selectorValue.trim() || !taskClass.trim() || !primaryRoute} onClick={proposeBinding}>Create disabled proposal</Button></div>}>
        <div className="operator-console__form">
          <div className="operator-console__form-grid">
            <Field label="Binding key" required><TextInput value={bindingKey} onChange={(event) => setBindingKey(event.target.value)} placeholder="research_company_analyst" /></Field>
            <Field label="Task class" required><TextInput value={taskClass} onChange={(event) => setTaskClass(event.target.value)} /></Field>
            <Field label="Selector type"><Select value={selectorKind} onChange={(event) => setSelectorKind(event.target.value)}><option value="agent">Named agent</option><option value="role">Role scope</option></Select></Field>
            <Field label="Exact selector" required><TextInput value={selectorValue} onChange={(event) => setSelectorValue(event.target.value)} placeholder="company_analyst" /></Field>
            <Field label="Primary route" required><Select value={primaryRoute} onChange={(event) => setPrimaryRoute(event.target.value)}><option value="">Select recorded route</option>{routeOptions.map((route) => <option key={route} value={route}>{route}</option>)}</Select></Field>
            <Field label="Reasoning profile"><Select value={reasoning} onChange={(event) => setReasoning(event.target.value)}><option value="none">None</option><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="xhigh">Extra high</option></Select></Field>
          </div>
          <div className="operator-console__warning">The proposal is fail-closed, restricted to public and internal data, and requires numeric, citation, missing-data, and prompt-injection qualification. Promotion remains a separate reviewed action.</div>
        </div>
      </Drawer>

      <Drawer open={review !== null} onClose={() => setReview(null)} title={`Review ${review?.action ?? "binding change"}`} subtitle={review ? `${text(review.binding, "binding_key")} · version ${num(review.version, "version_id", num(review.version, "id"))}` : ""} icon={ShieldCheck} width={600} footer={<div className="operator-console__actions"><Button variant="ghost" onClick={() => setReview(null)}>Cancel</Button><Button variant="primary" disabled={action.isPending || !review || confirmation.trim().toUpperCase() !== review.action.toUpperCase() || (review.action !== "disable" && !(Number(approvalId) > 0))} onClick={submitReview}>Submit reviewed action</Button></div>}>
        <div className="operator-console__form">
          <div className="operator-console__warning">This changes only the named binding pointer. It does not enable broker access, capital action, or prove the model healthy. The authenticated server principal and named approval receipt are the durable review evidence.</div>
          {review?.action !== "disable" && <Field label="Approved change receipt ID" required><TextInput aria-label="Approved change receipt ID" type="number" min={1} value={approvalId} onChange={(event) => setApprovalId(event.target.value)} /></Field>}
          <Field label={`Type ${review?.action.toUpperCase() ?? "ACTION"} to confirm`} required><TextInput aria-label={"Type " + (review?.action.toUpperCase() ?? "ACTION") + " to confirm"} value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></Field>
        </div>
      </Drawer>
    </div>
  );
}

export function SystemOperationsConsole() {
  const pushToast = useUIStore((state) => state.pushToast);
  const doctor = useQuery<DoctorSnapshot>({ queryKey: CONTROL_KEYS.doctor, queryFn: () => get<DoctorSnapshot>("/api/v1/doctor"), retry: false, refetchInterval: 30_000 });
  const routines = useQuery<RoutineSnapshot>({ queryKey: CONTROL_KEYS.routines, queryFn: () => get<RoutineSnapshot>("/api/v1/routines"), retry: false, refetchInterval: 30_000 });
  const doctorAction = useOperatorMutation([CONTROL_KEYS.doctor]);
  const routineAction = useOperatorMutation([CONTROL_KEYS.routines]);
  const [doctorReceipt, setDoctorReceipt] = React.useState<LiveRow | null>(null);
  const [routineReceipt, setRoutineReceipt] = React.useState<LiveRow | null>(null);
  const [fixCheck, setFixCheck] = React.useState<LiveRow | null>(null);
  const [fixConfirmation, setFixConfirmation] = React.useState("");
  const [routineControl, setRoutineControl] = React.useState<{ action: RoutineControlAction; routine: LiveRow } | null>(null);
  const [routineReason, setRoutineReason] = React.useState("");
  const [routineConfirmation, setRoutineConfirmation] = React.useState("");

  const doctorData = doctor.data;
  const doctorAvailable = doctorData?.available === true;
  const latestRun = object(doctorData?.latest_run);
  const doctorChecks = rows(doctorData?.checks).length ? rows(doctorData?.checks) : rows(raw(latestRun, "checks"));
  const registry = rows(doctorData?.registry);
  const doctorStatus = text(latestRun, "status", doctorData?.status ?? "not_recorded");
  const routineData = routines.data;
  const routinesAvailable = routineData?.available === true;
  const returnedRoutines = rows(routineData?.routines);
  const runHistory = rows(routineData?.history);
  const failedChecks = doctorChecks.filter((row) => text(row, "status").toLowerCase() === "failed").length;
  const unknownChecks = doctorChecks.filter((row) => ["unknown", "warning"].includes(text(row, "status").toLowerCase())).length;

  async function runDoctor() {
    try {
      const result = await doctorAction.mutateAsync({ path: "/api/v1/doctor/run", body: { mode: "scan", confirmed: true }, label: "Doctor scan" });
      setDoctorReceipt(result);
      const state = text(result, "status");
      pushToast({ title: "Doctor receipt returned", message: state ? `Recorded outcome: ${state}. Review failed and unknown checks below.` : "Outcome not recorded; no health state is assumed.", tone: state === "passed" ? "ok" : "warn", duration: 5000 });
    } catch (error) {
      pushToast({ title: "Doctor scan not completed", message: friendlyFailure(error, "Doctor scan"), tone: "risk", duration: 5500 });
    }
  }

  async function applySafeFix() {
    if (!fixCheck || fixConfirmation.trim().toUpperCase() !== "RELEASE EXPIRED LEASES") return;
    try {
      const result = await doctorAction.mutateAsync({ path: "/api/v1/doctor/fixes", body: { check_key: text(fixCheck, "check_key"), confirmed: true }, label: "Allowlisted lease repair" });
      setDoctorReceipt(result);
      setFixCheck(null);
      pushToast({ title: "Safe-fix receipt returned", message: outcome(result), tone: text(result, "status") === "applied" ? "ok" : "warn", duration: 5000 });
    } catch (error) {
      pushToast({ title: "Safe fix not completed", message: friendlyFailure(error, "allowlisted lease repair"), tone: "risk", duration: 5500 });
    }
  }

  async function testRoutine(routine: LiveRow) {
    const key = text(routine, "routine_key");
    try {
      const result = await routineAction.mutateAsync({ path: `/api/v1/routines/${encodeURIComponent(key)}/test`, body: { confirmed: true }, label: "Routine test" });
      setRoutineReceipt(result);
      pushToast({ title: "Routine test receipt returned", message: outcome(result), tone: ["completed", "passed", "fixture_checked"].includes(text(result, "status")) ? "ok" : "warn", duration: 5000 });
    } catch (error) {
      pushToast({ title: "Routine test not completed", message: friendlyFailure(error, "routine test"), tone: "risk", duration: 5500 });
    }
  }

  async function submitRoutineControl() {
    if (!routineControl || routineReason.trim().length < 8 || routineConfirmation.trim().toUpperCase() !== routineControl.action.toUpperCase()) return;
    const { action: nextAction, routine } = routineControl;
    const key = text(routine, "routine_key");
    try {
      const result = await routineAction.mutateAsync({ path: `/api/v1/routines/${encodeURIComponent(key)}/${nextAction}`, body: { confirmed: true, reason: routineReason.trim() }, label: `${nextAction} routine` });
      setRoutineReceipt(result);
      setRoutineControl(null);
      pushToast({ title: "Routine control receipt returned", message: outcome(result), tone: text(result, "status") === nextAction || text(result, "control_state") === nextAction + "d" ? "ok" : "warn", duration: 5000 });
    } catch (error) {
      pushToast({ title: "Routine control not completed", message: friendlyFailure(error, `${nextAction} routine`), tone: "risk", duration: 5500 });
    }
  }

  function registryFor(check: LiveRow): LiveRow {
    return registry.find((row) => text(row, "check_key") === text(check, "check_key")) ?? {};
  }

  return (
    <div className="operator-console" role="region" aria-label="System operations controls">
      <style>{OperatorControlConsoleCss}</style>
      <Panel icon={Activity} title="AI OS Doctor" actions={<Button size="sm" icon={Activity} disabled={!doctorAvailable || doctorAction.isPending} onClick={runDoctor}>{doctorAction.isPending ? "Checking" : "Run Doctor"}</Button>}>
        <div className={`operator-console__notice ${doctorAvailable ? doctorStatus === "passed" ? "is-ready" : "" : "is-risk"}`}>
          {doctorAvailable ? <Activity size={18} aria-hidden="true" /> : <TriangleAlert size={18} aria-hidden="true" />}
          <div><strong>{doctorAvailable ? `Last recorded state: ${doctorStatus.replace(/_/g, " ")}` : "Doctor unavailable"}</strong><span>{doctorAvailable ? "A completed request is not treated as healthy unless every recorded check passed." : "No system health, last-known-good state, or repair eligibility can be inferred."}</span></div>
          <code>GET /api/v1/doctor</code>
        </div>
        <div className="operator-console__summary" style={{ padding: "var(--space-3)" }}>
          <MetricTile tone={doctorStatus === "passed" ? "ok" : "warn"}><Metric label="Recorded Doctor state" value={doctorAvailable ? doctorStatus.replace(/_/g, " ") : "—"} /></MetricTile>
          <MetricTile tone={failedChecks ? "risk" : undefined}><Metric label="Failed checks" value={doctorAvailable ? failedChecks : "—"} /></MetricTile>
          <MetricTile tone={unknownChecks ? "warn" : undefined}><Metric label="Warning / unknown" value={doctorAvailable ? unknownChecks : "—"} /></MetricTile>
          <MetricTile><Metric label="Last run" value={doctorAvailable ? relativeOrMissing(text(latestRun, "finished_at", text(latestRun, "created_at"))) : "—"} /></MetricTile>
        </div>
        {!doctorAvailable ? <Empty icon={Activity} title="Doctor evidence is not available" /> : doctorChecks.length === 0 ? <Empty icon={Activity} title="No Doctor checks recorded" /> : (
          <div className="operator-console__checks">
            {doctorChecks.map((check, index) => {
              const definition = registryFor(check);
              const status = text(check, "status", "unknown").toLowerCase();
              const severity = text(check, "failure_severity", text(definition, "failure_severity"));
              const evidence = rows(raw(check, "evidence"));
              const sources = evidence.map((row) => text(row, "source", text(row, "check_key"))).filter(Boolean).slice(0, 3).join(", ");
              const safeFix = text(definition, "safe_fix_key") === "release_expired_leases" && text(check, "check_key") === "expired_task_leases";
              return (
                <article className={`operator-console__check is-${status}`} key={text(check, "check_key", `check-${index}`)}>
                  <div className="operator-console__check-head"><h4>{text(check, "check_name", text(definition, "check_name", text(check, "check_key", "Unnamed check")))}</h4><StatusPill status={status} /></div>
                  <p>{text(check, "headline", "No check summary was recorded.")}</p>
                  <div className="operator-console__facts"><Fact label="Severity" value={display(severity)} /><Fact label="Evidence" value={display(sources)} /><Fact label="Observed" value={relativeOrMissing(text(check, "observed_at"))} /><Fact label="Last known good" value={relativeOrMissing(text(check, "last_known_good_at"))} /></div>
                  {safeFix && <div className="operator-console__actions"><Button size="sm" icon={Wrench} disabled={doctorAction.isPending || status === "passed"} onClick={() => { setFixCheck(check); setFixConfirmation(""); }}>Review safe fix</Button></div>}
                </article>
              );
            })}
          </div>
        )}
        {doctorReceipt && <div className="operator-console__receipt" role="status"><strong>Latest Doctor receipt.</strong> {outcome(doctorReceipt)} Re-read the checks before deciding the system is healthy.</div>}
      </Panel>

      <Panel icon={Clock3} title="Reviewed operating routines" actions={<Badge tone={routinesAvailable ? "ok" : "warn"}>{routinesAvailable ? `${returnedRoutines.length}/5 recorded` : "Unavailable"}</Badge>}>
        <div className={`operator-console__notice ${routinesAvailable ? "is-ready" : "is-risk"}`}>
          {routinesAvailable ? <Clock3 size={18} aria-hidden="true" /> : <TriangleAlert size={18} aria-hidden="true" />}
          <div><strong>{routinesAvailable ? "Routine registry is available" : "Routine registry unavailable"}</strong><span>{routinesAvailable ? "Controls are limited to test, pause, and enable. A test receipt is not a production run." : "The five reviewed routine slots remain visible, but no schedule or run state is being inferred."}</span></div>
          <code>GET /api/v1/routines</code>
        </div>
        <div className="operator-console__routines">
          {ROUTINE_CATALOG.map((catalog) => {
            const routine = returnedRoutines.find((row) => text(row, "routine_key") === catalog.key) ?? {};
            const recorded = Boolean(text(routine, "routine_key"));
            const history = runHistory.filter((row) => text(row, "routine_key") === catalog.key);
            const state = recorded ? text(routine, "control_state", "not_recorded") : "unavailable";
            return (
              <article className="operator-console__routine" key={catalog.key} aria-label={`${catalog.name} routine`}>
                <div className="operator-console__routine-head"><div><h4>{text(routine, "routine_name", catalog.name)}</h4><p>{text(routine, "description", recorded ? "No description recorded." : "Definition not returned by the current runtime.")}</p></div><StatusPill status={state} /></div>
                <div className="operator-console__facts">
                  <Fact label="Owner" value={display(raw(routine, "owner_agent"))} />
                  <Fact label="Version" value={display(raw(routine, "current_version"))} />
                  <Fact label="Trigger" value={display(raw(routine, "trigger_kind"))} />
                  <Fact label="Cost ceiling" value={recorded && raw(routine, "cost_budget_usd") !== undefined ? formatCurrency(num(routine, "cost_budget_usd"), "USD") : "Not recorded"} />
                  <Fact label="Stale-data policy" value={display(raw(routine, "stale_data_policy"))} />
                  <Fact label="Last run" value={history.length ? `${text(history[0], "status", "not recorded")} · ${formatRelative(text(history[0], "finished_at", text(history[0], "started_at")))}` : "No run history"} />
                </div>
                <div className="operator-console__actions">
                  <Button size="sm" variant="ghost" icon={Beaker} disabled={!recorded || routineAction.isPending} onClick={() => testRoutine(routine)}>Test</Button>
                  {state === "enabled" ? <Button size="sm" variant="ghost" icon={Pause} disabled={routineAction.isPending} onClick={() => { setRoutineControl({ action: "pause", routine }); setRoutineReason(""); setRoutineConfirmation(""); }}>Review pause</Button> : <Button size="sm" variant="ghost" icon={Play} disabled={!recorded || routineAction.isPending} onClick={() => { setRoutineControl({ action: "enable", routine }); setRoutineReason(""); setRoutineConfirmation(""); }}>Review enable</Button>}
                </div>
              </article>
            );
          })}
        </div>
        {routineReceipt && <div className="operator-console__receipt" role="status"><strong>Latest routine receipt.</strong> {outcome(routineReceipt)} Verify run history before treating the routine as completed.</div>}
      </Panel>

      <Drawer open={fixCheck !== null} onClose={() => setFixCheck(null)} title="Review allowlisted safe fix" subtitle="Expired task leases only" icon={Wrench} width={560} footer={<div className="operator-console__actions"><Button variant="ghost" onClick={() => setFixCheck(null)}>Cancel</Button><Button variant="primary" disabled={doctorAction.isPending || fixConfirmation.trim().toUpperCase() !== "RELEASE EXPIRED LEASES"} onClick={applySafeFix}>Apply safe fix</Button></div>}>
        <div className="operator-console__form"><div className="operator-console__warning">This can release only expired task leases through the server allowlist. It cannot change credentials, client records, model routes, broker state, or capital.</div><Field label="Type RELEASE EXPIRED LEASES to confirm" required><TextInput aria-label="Type RELEASE EXPIRED LEASES to confirm" value={fixConfirmation} onChange={(event) => setFixConfirmation(event.target.value)} /></Field></div>
      </Drawer>

      <Drawer open={routineControl !== null} onClose={() => setRoutineControl(null)} title={`Review routine ${routineControl?.action ?? "control"}`} subtitle={routineControl ? text(routineControl.routine, "routine_name", text(routineControl.routine, "routine_key")) : ""} icon={ShieldCheck} width={560} footer={<div className="operator-console__actions"><Button variant="ghost" onClick={() => setRoutineControl(null)}>Cancel</Button><Button variant="primary" disabled={routineAction.isPending || !routineControl || routineReason.trim().length < 8 || routineConfirmation.trim().toUpperCase() !== routineControl.action.toUpperCase()} onClick={submitRoutineControl}>Submit reviewed control</Button></div>}>
        <div className="operator-console__form"><div className="operator-console__warning">The server remains authoritative for schedule state and will reject controls outside the reviewed five-routine allowlist.</div><Field label="Reason" required><TextArea aria-label="Reason" rows={4} value={routineReason} onChange={(event) => setRoutineReason(event.target.value)} /></Field><Field label={`Type ${routineControl?.action.toUpperCase() ?? "ACTION"} to confirm`} required><TextInput aria-label={"Type " + (routineControl?.action.toUpperCase() ?? "ACTION") + " to confirm"} value={routineConfirmation} onChange={(event) => setRoutineConfirmation(event.target.value)} /></Field></div>
      </Drawer>
    </div>
  );
}
