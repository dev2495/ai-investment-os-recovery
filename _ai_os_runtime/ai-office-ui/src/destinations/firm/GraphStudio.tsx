import React from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  CircleStop,
  Clock3,
  Database,
  FileWarning,
  Gavel,
  GitBranch,
  MessageSquare,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  Save,
  ShieldCheck,
  StepForward,
  Wrench,
} from "lucide-react";
import { useGraphControlSnapshot } from "../../data/queries";
import {
  useAdvanceActiveGraphRuns,
  useAdvanceGraphRun,
  useCancelGraphRun,
  usePauseGraphRun,
  useRecordGraphCorrection,
  useRequestGraphChange,
  useResolveGraphDecision,
  useResolveGraphWait,
  useResumeGraphRun,
  useStartGraphRun,
} from "../../data/actions";
import {
  Badge,
  Button,
  Empty,
  Field,
  Metric,
  MetricTile,
  Panel,
  Select,
  StatusPill,
  TextArea,
  TextInput,
} from "../../system/primitives";
import { formatRelative, num, text, truncate, value } from "../../data/liveRow";
import type { LiveRow } from "../../data/liveRow";
import { useUIStore } from "../../store";
import { GraphStudioCss } from "./GraphStudio.css";

type LaunchField = {
  key: string;
  label: string;
  required?: boolean;
  kind?: "text" | "number" | "date" | "csv" | "textarea";
};

const LAUNCH_FIELDS: Record<string, LaunchField[]> = {
  daily_office_intelligence: [
    { key: "as_of", label: "As of", kind: "date" },
    { key: "focus_symbols", label: "Focus symbols", kind: "csv" },
  ],
  research_to_investment_decision: [
    { key: "subject", label: "Research subject", required: true },
    { key: "symbol", label: "Symbol" },
    { key: "objective", label: "Decision objective", kind: "textarea" },
    { key: "source_ids", label: "Source IDs", kind: "csv" },
  ],
  strategy_research_lifecycle: [
    { key: "hypothesis", label: "Falsifiable hypothesis", required: true, kind: "textarea" },
    { key: "symbols", label: "Symbols", kind: "csv" },
    { key: "timeframe", label: "Timeframe" },
    { key: "cost_model", label: "Cost model" },
  ],
  kronos_forecast_research: [
    { key: "symbol", label: "Symbol", required: true },
    { key: "exchange", label: "Exchange", required: true },
    { key: "timeframe", label: "Timeframe", required: true },
    { key: "as_of", label: "Point-in-time cutoff", required: true, kind: "date" },
    { key: "lookback", label: "Lookback bars", required: true, kind: "number" },
    { key: "horizon", label: "Forecast bars", required: true, kind: "number" },
    { key: "path_count", label: "Stochastic paths", required: true, kind: "number" },
    { key: "model_revision", label: "Pinned model revision", required: true },
  ],
};

const today = new Date().toISOString().slice(0, 10);
const DEFAULT_INPUTS: Record<string, Record<string, string>> = {
  daily_office_intelligence: { as_of: today, focus_symbols: "" },
  research_to_investment_decision: { subject: "", symbol: "", objective: "", source_ids: "" },
  strategy_research_lifecycle: {
    hypothesis: "",
    symbols: "",
    timeframe: "1d",
    cost_model: "india_equities_full_costs",
  },
  kronos_forecast_research: {
    symbol: "",
    exchange: "NSE",
    timeframe: "1d",
    as_of: today,
    lookback: "512",
    model_revision: "67b630e67f6a18c9e9be918d9b4337c960db1e9a",
  },
};

const OPEN_RUN_STATES = new Set(["queued", "running", "waiting_approval", "waiting_input", "paused"]);

function rowId(row: LiveRow | undefined, key: string): number {
  return num(row, key, 0);
}

function asObject(row: LiveRow | undefined, key: string): Record<string, unknown> {
  return value<Record<string, unknown>>(row, key, {});
}

function asStrings(row: LiveRow | undefined, key: string): string[] {
  const raw = value<unknown>(row, key, []);
  return Array.isArray(raw) ? raw.map(String) : [];
}

function jsonPreview(raw: unknown): string {
  if (raw === null || raw === undefined) return "None";
  if (typeof raw === "string") return raw || "None";
  try {
    return JSON.stringify(raw, null, 2);
  } catch {
    return String(raw);
  }
}

function graphTone(status: string): "ok" | "risk" | "warn" | "info" | "neutral" {
  const normalized = status.toLowerCase();
  if (normalized.includes("fail") || normalized.includes("cancel") || normalized.includes("critical")) return "risk";
  if (normalized.includes("wait") || normalized.includes("pause") || normalized.includes("warn")) return "warn";
  if (normalized.includes("run") || normalized.includes("ready") || normalized.includes("queue") || normalized.includes("info")) return "info";
  if (normalized.includes("complete") || normalized.includes("active") || normalized.includes("approved")) return "ok";
  return "neutral";
}

interface Point {
  x: number;
  y: number;
}

function graphLayout(nodes: LiveRow[]): { points: Map<string, Point>; height: number } {
  const coordinates = nodes.map((node) => {
    const position = asObject(node, "ui_position");
    return {
      key: text(node, "node_key"),
      x: Number(position.x ?? 0),
      y: Number(position.y ?? 0),
    };
  });
  const xs = coordinates.map((point) => point.x);
  const ys = coordinates.map((point) => point.y);
  const minX = Math.min(...xs, 0);
  const maxX = Math.max(...xs, 0);
  const minY = Math.min(...ys, 0);
  const maxY = Math.max(...ys, 0);
  const height = Math.max(680, Math.min(980, 170 + nodes.length * 58));
  const points = new Map<string, Point>();
  for (const point of coordinates) {
    const x = maxX === minX ? 520 : 105 + ((point.x - minX) / (maxX - minX)) * 830;
    const y = maxY === minY ? height / 2 : 70 + ((point.y - minY) / (maxY - minY)) * (height - 140);
    points.set(point.key, { x, y });
  }
  return { points, height };
}

function NodeCanvas({
  nodes,
  edges,
  nodeRuns,
  edgeRuns,
  selectedNodeKey,
  onSelectNode,
}: {
  nodes: LiveRow[];
  edges: LiveRow[];
  nodeRuns: LiveRow[];
  edgeRuns: LiveRow[];
  selectedNodeKey: string;
  onSelectNode: (key: string) => void;
}) {
  if (nodes.length === 0) {
    return <Empty icon={GitBranch} title="No validated nodes" description="The selected graph version has no node definition." />;
  }

  const { points, height } = graphLayout(nodes);
  const runByNode = new Map(nodeRuns.map((row) => [text(row, "node_key"), row]));
  const edgeRunByPath = new Map(edgeRuns.map((row) => [
    `${text(row, "from_node_key")}::${text(row, "to_node_key")}`,
    row,
  ]));

  return (
    <div className="graph-canvas" role="region" aria-label="Workflow node graph">
      <svg viewBox={`0 0 1040 ${height}`} preserveAspectRatio="xMidYMin meet">
        <defs>
          <marker id="graph-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
            <path d="M0,0 L8,4 L0,8 Z" className="graph-edge-arrow" />
          </marker>
          <marker id="graph-arrow-live" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
            <path d="M0,0 L8,4 L0,8 Z" className="graph-edge-arrow graph-edge-arrow--live" />
          </marker>
        </defs>

        {edges.map((edge) => {
          const fromKey = text(edge, "from_node_key");
          const toKey = text(edge, "to_node_key");
          const from = points.get(fromKey);
          const to = points.get(toKey);
          if (!from || !to) return null;
          const edgeRun = edgeRunByPath.get(`${fromKey}::${toKey}`);
          const traversal = String(edgeRun?.traversal ?? "").toLowerCase();
          const live = traversal === "true" || traversal === "t" || traversal === "1";
          const skipped = text(edgeRun, "status").includes("skip");
          const middleY = from.y + (to.y - from.y) / 2;
          return (
            <path
              key={`${fromKey}-${toKey}-${text(edge, "edge_kind")}`}
              d={`M ${from.x} ${from.y + 36} C ${from.x} ${middleY}, ${to.x} ${middleY}, ${to.x} ${to.y - 36}`}
              className={`graph-edge ${live ? "graph-edge--live" : ""} ${skipped ? "graph-edge--skipped" : ""}`}
              markerEnd={`url(#${live ? "graph-arrow-live" : "graph-arrow"})`}
            />
          );
        })}

        {nodes.map((node) => {
          const key = text(node, "node_key");
          const point = points.get(key) ?? { x: 520, y: height / 2 };
          const run = runByNode.get(key);
          const status = run ? text(run, "status", "defined") : "defined";
          const selected = selectedNodeKey === key;
          return (
            <g
              key={key}
              transform={`translate(${point.x - 91},${point.y - 35})`}
              className={`graph-node graph-node--${status.replace(/_/g, "-")} ${selected ? "graph-node--selected" : ""}`}
              role="button"
              tabIndex={0}
              aria-label={`${text(node, "node_name")} ${status}`}
              onClick={() => onSelectNode(key)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelectNode(key);
                }
              }}
            >
              <rect width="182" height="70" rx="6" />
              <circle cx="14" cy="14" r="4" className="graph-node__state" />
              <text x="25" y="18" className="graph-node__type">{text(node, "node_type").replace(/_/g, " ")}</text>
              <text x="14" y="39" className="graph-node__name">{truncate(text(node, "node_name"), 25)}</text>
              <text x="14" y="57" className="graph-node__owner">{truncate(text(node, "owner_agent"), 27)}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function DecisionItem({
  row,
  pending,
  onDecide,
}: {
  row: LiveRow;
  pending: boolean;
  onDecide: (approvalId: number, decision: string, rationale: string) => void;
}) {
  const [rationale, setRationale] = React.useState("");
  const options = asStrings(row, "committee_decision_options");
  const choices = options.length ? options : ["approve", "reject"];
  const approvalId = rowId(row, "approval_id");

  return (
    <section className="graph-attention-item graph-attention-item--approval">
      <div className="graph-attention-item__head">
        <Gavel size={15} />
        <strong>{text(row, "node_name", "Human decision")}</strong>
        <StatusPill status={text(row, "approval_status", "pending")} />
      </div>
      <div className="graph-attention-item__meta">
        Run {rowId(row, "graph_run_id")} · {text(row, "graph_key")} · {text(row, "owner_agent")}
      </div>
      {text(row, "committee_recommendation") && (
        <div className="graph-attention-item__recommendation">
          Committee: {text(row, "committee_recommendation")}
        </div>
      )}
      <TextArea
        rows={3}
        value={rationale}
        onChange={(event) => setRationale(event.target.value)}
        placeholder="Decision rationale and evidence considered"
        aria-label="Decision rationale"
      />
      <div className="graph-attention-item__actions">
        {choices.map((choice) => (
          <Button
            key={choice}
            size="sm"
            variant={choice.includes("reject") || choice.includes("retire") ? "danger" : "primary"}
            disabled={pending || !rationale.trim()}
            onClick={() => onDecide(approvalId, choice, rationale.trim())}
          >
            {choice.replace(/_/g, " ")}
          </Button>
        ))}
      </div>
    </section>
  );
}

function WaitItem({
  row,
  pending,
  onResolve,
}: {
  row: LiveRow;
  pending: boolean;
  onResolve: (waitId: number, response: string) => void;
}) {
  const options = asStrings(row, "options");
  const [response, setResponse] = React.useState("");
  return (
    <section className="graph-attention-item">
      <div className="graph-attention-item__head">
        <MessageSquare size={15} />
        <strong>{text(row, "title", "Input requested")}</strong>
        <StatusPill status={text(row, "status", "open")} />
      </div>
      <div className="graph-attention-item__detail">{text(row, "question", text(row, "detail"))}</div>
      {options.length > 0 && (
        <div className="graph-attention-item__options">
          {options.map((option) => (
            <button
              key={option}
              className={response === option ? "is-selected" : ""}
              onClick={() => setResponse(option)}
            >
              {option}
            </button>
          ))}
        </div>
      )}
      <TextArea
        rows={2}
        value={response}
        onChange={(event) => setResponse(event.target.value)}
        placeholder="Your response"
        aria-label="Principal response"
      />
      <Button
        size="sm"
        variant="primary"
        disabled={pending || !response.trim()}
        onClick={() => onResolve(rowId(row, "id"), response.trim())}
      >
        Submit response
      </Button>
    </section>
  );
}

export function GraphStudio() {
  const { data, isLoading, error, refetch, isFetching } = useGraphControlSnapshot();
  const startRun = useStartGraphRun();
  const advanceRun = useAdvanceGraphRun();
  const advanceActive = useAdvanceActiveGraphRuns();
  const pauseRun = usePauseGraphRun();
  const resumeRun = useResumeGraphRun();
  const cancelRun = useCancelGraphRun();
  const resolveWait = useResolveGraphWait();
  const resolveDecision = useResolveGraphDecision();
  const recordCorrection = useRecordGraphCorrection();
  const requestChange = useRequestGraphChange();
  const pushToast = useUIStore((state) => state.pushToast);
  const setAssistantScope = useUIStore((state) => state.setAssistantScope);

  const graphs = data?.graphs ?? [];
  const [selectedGraphKey, setSelectedGraphKey] = React.useState("");
  const [selectedRunId, setSelectedRunId] = React.useState<number | null>(null);
  const [selectedNodeKey, setSelectedNodeKey] = React.useState("");
  const [inputs, setInputs] = React.useState<Record<string, Record<string, string>>>(DEFAULT_INPUTS);
  const [correctionSeverity, setCorrectionSeverity] = React.useState<"low" | "medium" | "high" | "critical">("medium");
  const [correctiveAction, setCorrectiveAction] = React.useState("");
  const [rootCause, setRootCause] = React.useState("");
  const [changeTitle, setChangeTitle] = React.useState("");
  const [changeRationale, setChangeRationale] = React.useState("");
  const [changePatch, setChangePatch] = React.useState("{}");
  const [changeSafety, setChangeSafety] = React.useState('{"broker_writes":false}');

  React.useEffect(() => {
    if (!selectedGraphKey && graphs.length > 0) {
      setSelectedGraphKey(text(graphs[0], "graph_key"));
    }
  }, [graphs, selectedGraphKey]);

  const selectedGraph = graphs.find((row) => text(row, "graph_key") === selectedGraphKey) ?? graphs[0];
  const graphKey = text(selectedGraph, "graph_key");
  const graphNodes = (data?.nodes ?? []).filter((row) => text(row, "graph_key") === graphKey);
  const graphEdges = (data?.edges ?? []).filter((row) => text(row, "graph_key") === graphKey);
  const graphRuns = (data?.runs ?? []).filter((row) => text(row, "graph_key") === graphKey);

  React.useEffect(() => {
    if (!graphKey) return;
    const stillVisible = selectedRunId && graphRuns.some((run) => rowId(run, "graph_run_id") === selectedRunId);
    if (!stillVisible) {
      const preferred = graphRuns.find((run) => OPEN_RUN_STATES.has(text(run, "run_status"))) ?? graphRuns[0];
      setSelectedRunId(preferred ? rowId(preferred, "graph_run_id") : null);
    }
    if (!graphNodes.some((node) => text(node, "node_key") === selectedNodeKey)) {
      setSelectedNodeKey(text(graphNodes[0], "node_key"));
    }
  }, [graphKey, graphNodes, graphRuns, selectedNodeKey, selectedRunId]);

  const selectedRun = graphRuns.find((row) => rowId(row, "graph_run_id") === selectedRunId);
  const nodeRuns = (data?.node_runs ?? []).filter((row) => rowId(row, "graph_run_id") === selectedRunId);
  const edgeRuns = (data?.edge_runs ?? []).filter((row) => rowId(row, "graph_run_id") === selectedRunId);
  const selectedNode = graphNodes.find((row) => text(row, "node_key") === selectedNodeKey);
  const selectedNodeRun = nodeRuns.find((row) => text(row, "node_key") === selectedNodeKey);
  const selectedEvents = (data?.events ?? []).filter((row) => !selectedRunId || rowId(row, "graph_run_id") === selectedRunId);
  const selectedCheckpoints = (data?.checkpoints ?? []).filter((row) => !selectedRunId || rowId(row, "graph_run_id") === selectedRunId);
  const approvalNodes = (data?.node_runs ?? []).filter((row) =>
    text(row, "approval_status") === "pending" &&
    (!selectedRunId || rowId(row, "graph_run_id") === selectedRunId)
  );
  const openWaits = (data?.waiting ?? []).filter((row) =>
    text(row, "status") === "open" &&
    text(row, "request_type") !== "approval" &&
    (!selectedRunId || rowId(row, "graph_run_id") === selectedRunId)
  );
  const openCorrections = (data?.corrections ?? []).filter((row) =>
    ["open", "in_progress", "verification"].includes(text(row, "status"))
  );

  const currentInputs = inputs[graphKey] ?? {};
  const launchFields = LAUNCH_FIELDS[graphKey] ?? [];
  const selectedRunStatus = text(selectedRun, "run_status");
  const mutationPending = startRun.isPending || advanceRun.isPending || advanceActive.isPending ||
    pauseRun.isPending || resumeRun.isPending || cancelRun.isPending;

  function notify(title: string, tone: "ok" | "risk" | "warn" | "info", message?: string) {
    pushToast({ title, message, tone, duration: tone === "risk" ? 6000 : 3200 });
  }

  function updateInput(key: string, next: string) {
    setInputs((previous) => ({
      ...previous,
      [graphKey]: { ...(previous[graphKey] ?? {}), [key]: next },
    }));
  }

  function buildInputPayload(): Record<string, unknown> {
    const payload: Record<string, unknown> = {};
    for (const field of launchFields) {
      const raw = (currentInputs[field.key] ?? "").trim();
      if (!raw) continue;
      if (field.kind === "csv") {
        payload[field.key] = raw.split(",").map((item) => item.trim()).filter(Boolean);
      } else if (field.kind === "number") {
        payload[field.key] = Number(raw);
      } else {
        payload[field.key] = raw;
      }
    }
    return payload;
  }

  function launchGraph() {
    const missing = launchFields.filter((field) => field.required && !(currentInputs[field.key] ?? "").trim());
    if (missing.length) {
      notify("Required graph inputs missing", "warn", missing.map((field) => field.label).join(", "));
      return;
    }
    const inputPayload = buildInputPayload();
    const subjectRef = String(inputPayload.symbol ?? inputPayload.subject ?? inputPayload.hypothesis ?? "");
    startRun.mutate({
      graph_key: graphKey,
      input_payload: inputPayload,
      actor: "Devarsh",
      trigger_type: "manual",
      subject_type: graphKey.includes("strategy") ? "strategy_hypothesis" : graphKey.includes("research") ? "research_subject" : "office_cycle",
      subject_ref: subjectRef.slice(0, 240),
      correlation_key: `ui-${Date.now()}`,
      max_steps: 30,
    }, {
      onSuccess: (result) => {
        const runId = rowId(result, "graph_run_id");
        if (runId) setSelectedRunId(runId);
        notify("Workflow started", "ok", runId ? `Run ${runId}` : graphKey);
      },
      onError: (mutationError) => notify("Workflow start failed", "risk", mutationError.message),
    });
  }

  function operateRun(action: "advance" | "pause" | "resume" | "cancel") {
    if (!selectedRunId) return;
    const callbacks = {
      onSuccess: () => notify(`Run ${action} recorded`, "ok", `Run ${selectedRunId}`),
      onError: (mutationError: Error) => notify(`Run ${action} failed`, "risk", mutationError.message),
    };
    if (action === "advance") {
      advanceRun.mutate({ graph_run_id: selectedRunId, actor: "Devarsh", max_steps: 40 }, callbacks);
    } else if (action === "pause") {
      pauseRun.mutate({ graph_run_id: selectedRunId, actor: "Devarsh", reason: "Paused from Graph Studio" }, callbacks);
    } else if (action === "resume") {
      resumeRun.mutate({ graph_run_id: selectedRunId, actor: "Devarsh" }, callbacks);
    } else if (window.confirm(`Cancel graph run ${selectedRunId}? Completed evidence remains preserved.`)) {
      cancelRun.mutate({ graph_run_id: selectedRunId, actor: "Devarsh", reason: "Cancelled from Graph Studio" }, callbacks);
    }
  }

  function submitDecision(approvalId: number, decision: string, rationale: string) {
    resolveDecision.mutate({ approval_id: approvalId, decision, rationale, actor: "Devarsh" }, {
      onSuccess: () => notify("Decision recorded", "ok", decision.replace(/_/g, " ")),
      onError: (mutationError) => notify("Decision failed", "risk", mutationError.message),
    });
  }

  function submitWait(waitId: number, response: string) {
    resolveWait.mutate({ wait_id: waitId, resolution: { response }, actor: "Devarsh" }, {
      onSuccess: () => notify("Response recorded", "ok", `Wait ${waitId}`),
      onError: (mutationError) => notify("Response failed", "risk", mutationError.message),
    });
  }

  function submitCorrection() {
    if (!correctiveAction.trim()) {
      notify("Corrective action required", "warn");
      return;
    }
    recordCorrection.mutate({
      source_kind: "graph_studio_observation",
      source_ref: selectedRunId ? `graph_run:${selectedRunId}` : graphKey,
      graph_run_id: selectedRunId ?? undefined,
      graph_node_run_id: selectedNodeRun ? rowId(selectedNodeRun, "graph_node_run_id") : undefined,
      correction_type: "operator_correction",
      severity: correctionSeverity,
      root_cause: rootCause.trim(),
      corrective_action: correctiveAction.trim(),
      expected_state: { note: "Operator expected a correct, evidence-backed outcome." },
      observed_state: { node_status: text(selectedNodeRun, "status"), node_error: value(selectedNodeRun, "error", {}) },
      prevention_change: { requires_review: true },
      actor: "Devarsh",
    }, {
      onSuccess: () => {
        setCorrectiveAction("");
        setRootCause("");
        notify("Correction entered", "ok", "Model Risk Agent review queued");
      },
      onError: (mutationError) => notify("Correction failed", "risk", mutationError.message),
    });
  }

  function submitChangeRequest() {
    if (!changeTitle.trim() || !changeRationale.trim()) {
      notify("Change title and rationale required", "warn");
      return;
    }
    try {
      const proposedPatch = JSON.parse(changePatch) as Record<string, unknown>;
      const safetyImpact = JSON.parse(changeSafety) as Record<string, unknown>;
      requestChange.mutate({
        graph_key: graphKey,
        title: changeTitle.trim(),
        rationale: changeRationale.trim(),
        proposed_patch: proposedPatch,
        safety_impact: safetyImpact,
        actor: "Devarsh",
      }, {
        onSuccess: () => {
          setChangeTitle("");
          setChangeRationale("");
          notify("Versioned change requested", "ok", "CTO review and approval created");
        },
        onError: (mutationError) => notify("Change request failed", "risk", mutationError.message),
      });
    } catch (parseError) {
      notify("Patch JSON is invalid", "warn", String(parseError));
    }
  }

  if (error) {
    return (
      <div className="aios-destination">
        <Panel variant="risk" icon={AlertTriangle} title="Graph control plane unavailable">
          <div className="graph-error">{error.message}</div>
        </Panel>
      </div>
    );
  }

  const validation = asObject(selectedGraph, "validation_result");
  const validationOk = validation.valid === true;
  const runProgress = selectedRun
    ? `${num(selectedRun, "completed_node_count")} / ${num(selectedRun, "node_run_count")}`
    : "No run";

  return (
    <div className="aios-destination graph-studio">
      <style>{GraphStudioCss}</style>
      <header className="graph-studio__header">
        <div>
          <div className="graph-studio__title">
            <GitBranch size={26} />
            Graph Studio
            <Badge tone="accent">CONTROL</Badge>
          </div>
          <div className="graph-studio__subtitle">Governed agent workflows, decisions, evidence, corrections, and live handoffs.</div>
        </div>
        <div className="graph-studio__toolbar">
          {data && <StatusPill tone="ok" dot>{formatRelative(data.generated_at)}</StatusPill>}
          <Button
            icon={StepForward}
            onClick={() => advanceActive.mutate(
              { actor: "Devarsh", limit: 20, max_steps: 40 },
              {
                onSuccess: () => notify("Active workflows advanced", "ok"),
                onError: (mutationError) => notify("Advance failed", "risk", mutationError.message),
              }
            )}
            disabled={advanceActive.isPending}
          >
            Advance all
          </Button>
          <Button icon={RefreshCw} onClick={() => refetch()} disabled={isFetching}>Refresh</Button>
        </div>
      </header>

      <div className="graph-studio__metrics">
        <MetricTile><Metric label="Validated Graphs" value={graphs.filter((graph) => asObject(graph, "validation_result").valid === true).length} /></MetricTile>
        <MetricTile tone={(data?.runs ?? []).some((run) => OPEN_RUN_STATES.has(text(run, "run_status"))) ? "ok" : "default"}>
          <Metric label="Open Runs" value={(data?.runs ?? []).filter((run) => OPEN_RUN_STATES.has(text(run, "run_status"))).length} />
        </MetricTile>
        <MetricTile tone={approvalNodes.length || openWaits.length ? "warn" : "ok"}>
          <Metric label="Principal Waits" value={approvalNodes.length + openWaits.length} />
        </MetricTile>
        <MetricTile tone={openCorrections.some((row) => ["high", "critical"].includes(text(row, "severity"))) ? "risk" : openCorrections.length ? "warn" : "ok"}>
          <Metric label="Open Corrections" value={openCorrections.length} />
        </MetricTile>
        <MetricTile><Metric label="Autonomy Policies" value={data?.autonomy?.length ?? 0} /></MetricTile>
      </div>

      <div className="graph-studio__workspace">
        <aside className="graph-studio__catalog">
          <Panel icon={GitBranch} title="Workflow Catalog" bodyFlush>
            <div className="graph-catalog">
              {isLoading && graphs.length === 0 ? <div className="graph-loading">Loading validated graphs…</div> : graphs.map((graph) => {
                const key = text(graph, "graph_key");
                const valid = asObject(graph, "validation_result").valid === true;
                return (
                  <button
                    key={key}
                    className={`graph-catalog__item ${key === graphKey ? "is-active" : ""}`}
                    onClick={() => {
                      setSelectedGraphKey(key);
                      setSelectedRunId(null);
                    }}
                  >
                    <span className={`graph-catalog__status ${valid ? "is-valid" : "is-invalid"}`} />
                    <span className="graph-catalog__copy">
                      <strong>{text(graph, "graph_name")}</strong>
                      <span>{text(graph, "owner_agent")} · v{text(graph, "active_version")}</span>
                    </span>
                    <span className="graph-catalog__runs">{num(graph, "open_run_count")}</span>
                  </button>
                );
              })}
            </div>
          </Panel>

          <Panel
            icon={Play}
            title="Launch"
            actions={<StatusPill tone={validationOk ? "ok" : "risk"}>{validationOk ? "validated" : "blocked"}</StatusPill>}
          >
            <div className="graph-launch">
              {launchFields.map((field) => (
                <Field key={field.key} label={field.label} required={field.required}>
                  {field.kind === "textarea" ? (
                    <TextArea rows={3} value={currentInputs[field.key] ?? ""} onChange={(event) => updateInput(field.key, event.target.value)} />
                  ) : (
                    <TextInput
                      type={field.kind === "number" ? "number" : field.kind === "date" ? "date" : "text"}
                      value={currentInputs[field.key] ?? ""}
                      onChange={(event) => updateInput(field.key, event.target.value)}
                    />
                  )}
                </Field>
              ))}
              {launchFields.length === 0 && <div className="graph-muted">This graph has no declared launch fields.</div>}
              <Button variant="primary" icon={Play} block onClick={launchGraph} disabled={!graphKey || !validationOk || startRun.isPending}>
                Start governed run
              </Button>
            </div>
          </Panel>
        </aside>

        <main className="graph-studio__main">
          <Panel
            icon={Activity}
            title={selectedRun ? `${text(selectedGraph, "graph_name")} · Run ${selectedRunId}` : text(selectedGraph, "graph_name", "Select a graph")}
            actions={
              <div className="graph-run-actions">
                {selectedRun && <StatusPill tone={graphTone(selectedRunStatus)} dot pulse={selectedRunStatus === "running"}>{selectedRunStatus.replace(/_/g, " ")}</StatusPill>}
                <Badge>{runProgress}</Badge>
                {selectedRun && (
                  <Select aria-label="Select workflow run" value={selectedRunId ?? ""} onChange={(event) => setSelectedRunId(Number(event.target.value))}>
                    {graphRuns.map((run) => (
                      <option key={rowId(run, "graph_run_id")} value={rowId(run, "graph_run_id")}>
                        #{rowId(run, "graph_run_id")} · {text(run, "run_status")} · {text(run, "subject_ref", "general")}
                      </option>
                    ))}
                  </Select>
                )}
              </div>
            }
            bodyFlush
          >
            <div className="graph-run-bar">
              <div className="graph-run-bar__subject">
                <strong>{text(selectedRun, "subject_ref", "Definition view")}</strong>
                <span>{selectedRun ? `Started by ${text(selectedRun, "triggered_by")} · ${formatRelative(text(selectedRun, "started_at"))}` : text(selectedGraph, "description")}</span>
              </div>
              <div className="graph-run-bar__controls">
                <Button size="sm" icon={StepForward} disabled={!selectedRunId || mutationPending || !["queued", "running", "waiting_input"].includes(selectedRunStatus)} onClick={() => operateRun("advance")}>Advance</Button>
                <Button size="sm" icon={Pause} disabled={!selectedRunId || mutationPending || !["queued", "running", "waiting_input", "waiting_approval"].includes(selectedRunStatus)} onClick={() => operateRun("pause")}>Pause</Button>
                <Button size="sm" icon={RotateCcw} disabled={!selectedRunId || mutationPending || selectedRunStatus !== "paused"} onClick={() => operateRun("resume")}>Resume</Button>
                <Button size="sm" variant="danger" icon={CircleStop} disabled={!selectedRunId || mutationPending || !OPEN_RUN_STATES.has(selectedRunStatus)} onClick={() => operateRun("cancel")}>Cancel</Button>
              </div>
            </div>
            <NodeCanvas
              nodes={graphNodes}
              edges={graphEdges}
              nodeRuns={nodeRuns}
              edgeRuns={edgeRuns}
              selectedNodeKey={selectedNodeKey}
              onSelectNode={setSelectedNodeKey}
            />
            <div className="graph-node-inspector">
              <div className="graph-node-inspector__identity">
                <span className={`graph-node-inspector__state tone-${graphTone(text(selectedNodeRun, "status", "defined"))}`} />
                <div>
                  <strong>{text(selectedNode, "node_name", "Select a node")}</strong>
                  <span>{text(selectedNode, "node_type").replace(/_/g, " ")} · {text(selectedNode, "skill_key", "runtime primitive")}</span>
                </div>
              </div>
              <div className="graph-node-inspector__facts">
                <span><b>Owner</b>{text(selectedNode, "owner_agent", "—")}</span>
                <span><b>Status</b>{text(selectedNodeRun, "status", "defined")}</span>
                <span><b>Task</b>{text(selectedNodeRun, "task_title", selectedNodeRun ? "Runtime primitive" : "Not started")}</span>
                <span><b>Worker</b>{text(selectedNodeRun, "worker_status", "—")}</span>
              </div>
              <div className="graph-node-inspector__actions">
                {text(selectedNode, "owner_agent") && (
                  <Button
                    size="sm"
                    icon={MessageSquare}
                    onClick={() => setAssistantScope({ agentKey: text(selectedNode, "owner_agent"), agentName: text(selectedNode, "owner_agent") })}
                  >
                    Talk to owner
                  </Button>
                )}
              </div>
              {selectedNodeRun && (
                <details className="graph-node-inspector__evidence">
                  <summary>Evidence and output</summary>
                  <pre>{jsonPreview({
                    evidence: value(selectedNodeRun, "evidence", {}),
                    output: value(selectedNodeRun, "output_payload", {}),
                    error: value(selectedNodeRun, "error", {}),
                  })}</pre>
                </details>
              )}
            </div>
          </Panel>
        </main>

        <aside className="graph-studio__attention">
          <Panel
            icon={Gavel}
            title="Principal Desk"
            variant={approvalNodes.length || openWaits.length ? "warn" : "default"}
            actions={<Badge tone={approvalNodes.length || openWaits.length ? "warn" : "ok"}>{approvalNodes.length + openWaits.length}</Badge>}
          >
            <div className="graph-attention-list">
              {approvalNodes.length === 0 && openWaits.length === 0 ? (
                <Empty icon={CheckCircle2} title="No decision waiting" description="No active workflow is blocked on your input." />
              ) : (
                <>
                  {approvalNodes.map((row) => (
                    <DecisionItem key={rowId(row, "approval_id")} row={row} pending={resolveDecision.isPending} onDecide={submitDecision} />
                  ))}
                  {openWaits.map((row) => (
                    <WaitItem key={rowId(row, "id")} row={row} pending={resolveWait.isPending} onResolve={submitWait} />
                  ))}
                </>
              )}
            </div>
          </Panel>

          <Panel icon={ShieldCheck} title="Safety Contract">
            <dl className="graph-safety">
              <div><dt>Autonomy</dt><dd>{text(selectedGraph, "default_autonomy_level", "—")}</dd></div>
              <div><dt>Broker writes</dt><dd><StatusPill tone="ok">disabled</StatusPill></dd></div>
              <div><dt>Version</dt><dd>v{text(selectedGraph, "active_version", "—")}</dd></div>
              <div><dt>Definition</dt><dd className="mono">{truncate(text(selectedGraph, "definition_hash"), 15)}</dd></div>
            </dl>
            <details className="graph-json">
              <summary>Policy JSON</summary>
              <pre>{jsonPreview(value(selectedGraph, "safety_policy", {}))}</pre>
            </details>
          </Panel>
        </aside>
      </div>

      <div className="graph-studio__lower">
        <Panel icon={Clock3} title="Run Ledger" actions={<Badge>{selectedEvents.length}</Badge>}>
          <div className="graph-ledger">
            {selectedEvents.length === 0 ? (
              <Empty icon={Clock3} title="No events for this run" />
            ) : selectedEvents.slice(0, 40).map((event) => (
              <div key={rowId(event, "id")} className="graph-ledger__row">
                <span className={`graph-ledger__mark tone-${graphTone(text(event, "severity"))}`} />
                <div>
                  <strong>{text(event, "event_type").replace(/_/g, " ")}</strong>
                  <span>{text(event, "actor")} · {formatRelative(text(event, "occurred_at"))}</span>
                </div>
                <code>{truncate(jsonPreview(value(event, "event_payload", {})).replace(/\s+/g, " "), 120)}</code>
              </div>
            ))}
          </div>
          {selectedCheckpoints.length > 0 && (
            <div className="graph-checkpoints">
              {selectedCheckpoints.slice(0, 8).map((checkpoint) => (
                <div key={rowId(checkpoint, "id")}>
                  <Database size={14} />
                  <span>{text(checkpoint, "checkpoint_kind")}</span>
                  <code>{truncate(text(checkpoint, "resume_token"), 18)}</code>
                  <time>{formatRelative(text(checkpoint, "created_at"))}</time>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel icon={Wrench} title="Correction Ledger" actions={<Badge tone={openCorrections.length ? "warn" : "ok"}>{openCorrections.length}</Badge>}>
          <div className="graph-form">
            <div className="graph-form__row">
              <Field label="Severity">
                <Select value={correctionSeverity} onChange={(event) => setCorrectionSeverity(event.target.value as typeof correctionSeverity)}>
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </Select>
              </Field>
              <Field label="Root cause"><TextInput value={rootCause} onChange={(event) => setRootCause(event.target.value)} /></Field>
            </div>
            <Field label="Corrective action" required>
              <TextArea rows={3} value={correctiveAction} onChange={(event) => setCorrectiveAction(event.target.value)} />
            </Field>
            <Button icon={Save} variant="primary" onClick={submitCorrection} disabled={recordCorrection.isPending}>Record and assign review</Button>
          </div>
          <div className="graph-correction-list">
            {openCorrections.slice(0, 8).map((row) => (
              <div key={rowId(row, "id")}>
                <StatusPill status={text(row, "severity")} />
                <span>{truncate(text(row, "corrective_action"), 85)}</span>
                <small>{text(row, "owner_agent")} · {text(row, "status")}</small>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <Panel icon={FileWarning} title="Versioned Graph Change" actions={<Badge tone="warn">approval required</Badge>}>
        <div className="graph-change">
          <Field label="Change title" required><TextInput value={changeTitle} onChange={(event) => setChangeTitle(event.target.value)} /></Field>
          <Field label="Rationale" required><TextArea rows={3} value={changeRationale} onChange={(event) => setChangeRationale(event.target.value)} /></Field>
          <Field label="Declarative patch JSON"><TextArea className="mono" rows={5} value={changePatch} onChange={(event) => setChangePatch(event.target.value)} /></Field>
          <Field label="Safety impact JSON"><TextArea className="mono" rows={5} value={changeSafety} onChange={(event) => setChangeSafety(event.target.value)} /></Field>
          <Button icon={ArrowRight} onClick={submitChangeRequest} disabled={requestChange.isPending}>Send to CTO review</Button>
        </div>
      </Panel>
    </div>
  );
}

export default GraphStudio;
