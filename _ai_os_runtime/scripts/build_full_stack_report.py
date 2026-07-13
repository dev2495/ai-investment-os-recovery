#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


RUNTIME_ROOT = Path(os.environ.get("AI_OS_RUNTIME_ROOT") or Path(__file__).absolute().parents[1])
VAULT_ROOT = Path(os.environ.get("AI_OS_VAULT_ROOT") or RUNTIME_ROOT.parent)
REPORT_DIR = VAULT_ROOT / "ai memory" / "00 AI OS" / "Reports"
API_URL = "http://127.0.0.1:8765"
QDRANT_URL = "http://127.0.0.1:6333"


def fetch_json(url: str, timeout: float = 10.0) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    if isinstance(value, list):
        return ", ".join(text(item) for item in value)
    if isinstance(value, dict):
        return ", ".join(f"{key}: {text(item)}" for key, item in value.items())
    return str(value)


def esc(value: Any) -> str:
    return html.escape(text(value))


def rows(items: list[dict[str, Any]], columns: list[tuple[str, str]], limit: int | None = None) -> str:
    selected = items[:limit] if limit else items
    head = "".join(f"<th>{html.escape(label)}</th>" for label, _ in columns)
    body = []
    for item in selected:
        body.append("<tr>" + "".join(f"<td>{esc(item.get(key))}</td>" for _, key in columns) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def pill(value: Any) -> str:
    raw = text(value, "unknown")
    normalized = raw.lower().replace(" ", "-")
    return f'<span class="pill pill-{html.escape(normalized)}">{html.escape(raw)}</span>'


def qdrant_counts() -> list[dict[str, Any]]:
    try:
        collections_payload = fetch_json(f"{QDRANT_URL}/collections", timeout=5)
        collections = collections_payload.get("result", {}).get("collections", [])
        result = []
        for collection in collections:
            name = collection.get("name")
            if not name:
                continue
            try:
                detail = fetch_json(f"{QDRANT_URL}/collections/{name}", timeout=5)
                points = detail.get("result", {}).get("points_count")
            except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
                points = None
            result.append({"collection": name, "points": points})
        return sorted(result, key=lambda row: row["collection"])
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return []


def metric_card(label: str, value: Any, note: str = "") -> str:
    return f"""
    <article class="metric">
      <strong>{esc(value)}</strong>
      <span>{html.escape(label)}</span>
      <small>{html.escape(note)}</small>
    </article>
    """


def flow_diagram() -> str:
    steps = [
        ("Sources", "P2Cursor, broker files, trading journals, Fincept, OpenAlgo, Vibe, news, filings"),
        ("Data Spine", "Postgres warehouse, Redis queues, Qdrant retrieval, Obsidian graph"),
        ("Tool Layer", "MCP registry, browser/TradingView controller, importers, workers"),
        ("AI Office", "Charlie, Jarvis, departments, mailboxes, daemon, specialist agents"),
        ("Surfaces", "Dashboard, live office floor, chat, worker notes, PDF reports"),
    ]
    return '<div class="flow">' + "".join(
        f'<section><b>{html.escape(title)}</b><p>{html.escape(body)}</p></section>' for title, body in steps
    ) + "</div>"


def hierarchy_tree(org: list[dict[str, Any]]) -> str:
    children: dict[str, list[dict[str, Any]]] = {}
    roots = []
    for item in org:
        parent = item.get("reports_to_agent")
        if parent:
            children.setdefault(str(parent), []).append(item)
        else:
            roots.append(item)

    def render_node(item: dict[str, Any], depth: int = 0) -> str:
        child_html = "".join(render_node(child, depth + 1) for child in children.get(str(item.get("agent_name")), []))
        return (
            f'<li style="--depth:{depth}"><b>{esc(item.get("agent_name"))}</b>'
            f'<span>{esc(item.get("hierarchy_level"))} · {esc(item.get("department_name"))}</span>'
            f"{'<ul>' + child_html + '</ul>' if child_html else ''}</li>"
        )

    return '<ul class="tree">' + "".join(render_node(root) for root in roots) + "</ul>"


def skill_summary(external_skills: list[dict[str, Any]]) -> str:
    counts = Counter(text(row.get("source_family"), "unknown") for row in external_skills)
    return '<div class="bars">' + "".join(
        f'<div><span>{html.escape(name)}</span><b style="width:{min(100, count * 8)}%">{count}</b></div>'
        for name, count in sorted(counts.items())
    ) + "</div>"


def build_html() -> Path:
    snapshot = fetch_json(f"{API_URL}/api/snapshot", timeout=20)
    health = fetch_json(f"{API_URL}/api/health", timeout=10)
    qdrant = qdrant_counts()

    agents = snapshot.get("agents", [])
    org = snapshot.get("agent_org_chart", [])
    skills = snapshot.get("agent_skills", [])
    external_skills = snapshot.get("external_skills", [])
    models = snapshot.get("agent_models", [])
    messages = snapshot.get("agent_messages", [])
    workflows = snapshot.get("workflows", [])
    mcp = snapshot.get("mcp_candidates", [])
    widgets = snapshot.get("dashboard_widgets", [])
    readiness = snapshot.get("pipeline_readiness", [])
    data_sources = snapshot.get("data_sources", [])
    fincept = snapshot.get("fincept", [])
    office = (snapshot.get("agent_office_overview") or [{}])[0]
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    tradingview = health.get("tradingview_cdp", {})

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    output = REPORT_DIR / "2026-07-06-ai-hedge-fund-os-full-stack-report.html"

    qdrant_table = rows(qdrant, [("Collection", "collection"), ("Points", "points")]) if qdrant else "<p>Qdrant was not reachable during report generation.</p>"
    mcp_rows = rows(mcp, [("Integration", "integration_name"), ("Category", "category"), ("Status", "status"), ("Permission", "permission_level"), ("Use Case", "use_case")], limit=30)
    workflow_rows = rows(workflows, [("Workflow", "workflow_name"), ("Owner", "owner_agent"), ("Trigger", "trigger_type"), ("Status", "status"), ("Permission", "permission_level")], limit=30)
    data_source_rows = rows(data_sources, [("Source", "source_name"), ("Type", "source_type"), ("Provider", "provider"), ("Status", "status"), ("Owner", "owner_agent")], limit=30)

    html_doc = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>AI Hedge Fund OS Full Stack Report</title>
  <style>
    :root {{ color-scheme: light; --ink:#111827; --muted:#4b5563; --line:#d1d5db; --soft:#f3f4f6; --brand:#1d4ed8; --risk:#991b1b; --ok:#047857; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color:var(--ink); background:white; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 36px 42px 60px; }}
    h1 {{ margin:0; font-size: 34px; line-height: 1.05; letter-spacing:0; }}
    h2 {{ margin: 34px 0 12px; padding-top: 14px; border-top: 2px solid var(--line); font-size: 21px; }}
    h3 {{ margin: 20px 0 8px; font-size: 15px; }}
    p, li {{ color: var(--muted); font-size: 12.5px; line-height: 1.55; }}
    .subtitle {{ margin: 10px 0 0; max-width: 850px; color: var(--muted); font-size: 14px; }}
    .stamp {{ margin-top: 14px; color: var(--muted); font-size: 11px; }}
    .metrics {{ display:grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 22px 0; }}
    .metric {{ min-height: 78px; padding: 12px; border:1px solid var(--line); border-radius:8px; background:var(--soft); }}
    .metric strong {{ display:block; font-size: 25px; line-height:1; color:var(--brand); }}
    .metric span {{ display:block; margin-top: 7px; font-size: 12px; font-weight: 800; }}
    .metric small {{ display:block; margin-top: 4px; color:var(--muted); font-size: 10.5px; line-height: 1.35; }}
    .flow {{ display:grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin: 12px 0 18px; }}
    .flow section {{ position:relative; min-height: 116px; padding: 12px; border:1px solid var(--line); border-radius:8px; background:#fff; }}
    .flow section:not(:last-child)::after {{ content:""; position:absolute; top:50%; right:-8px; width:8px; border-top:2px solid var(--brand); }}
    .flow b {{ font-size: 13px; }}
    .flow p {{ margin:7px 0 0; font-size: 11px; }}
    table {{ width:100%; border-collapse: collapse; margin: 10px 0 18px; table-layout: fixed; }}
    th, td {{ border:1px solid var(--line); padding: 7px 8px; text-align:left; vertical-align:top; font-size: 10.5px; line-height: 1.35; overflow-wrap:anywhere; }}
    th {{ background:var(--soft); font-size:10px; text-transform:uppercase; color:#374151; }}
    .cols {{ display:grid; grid-template-columns: 1fr 1fr; gap: 18px; }}
    .callout {{ padding: 13px 15px; border-left: 4px solid var(--brand); background:#eff6ff; border-radius: 6px; }}
    .warning {{ border-left-color: var(--risk); background:#fef2f2; }}
    .ok {{ border-left-color: var(--ok); background:#ecfdf5; }}
    .pill {{ display:inline-block; padding:3px 7px; border-radius:999px; background:#e5e7eb; font-size:10px; font-weight:800; }}
    .pill-active, .pill-ok, .pill-completed, .pill-installed, .pill-build_success {{ background:#d1fae5; color:#065f46; }}
    .pill-planned, .pill-pending {{ background:#fef3c7; color:#92400e; }}
    .pill-false, .pill-error {{ background:#fee2e2; color:#991b1b; }}
    .tree, .tree ul {{ list-style:none; margin:0; padding-left: 16px; }}
    .tree li {{ margin: 7px 0; padding-left: calc(var(--depth) * 4px); }}
    .tree b {{ display:inline-block; min-width: 190px; color:var(--ink); font-size: 11px; }}
    .tree span {{ color:var(--muted); font-size: 10.5px; }}
    .bars {{ margin: 12px 0; }}
    .bars div {{ display:grid; grid-template-columns: 120px 1fr; align-items:center; gap: 8px; margin: 8px 0; }}
    .bars span {{ font-size: 11px; font-weight: 800; }}
    .bars b {{ display:block; min-width: 28px; padding: 5px 8px; border-radius: 6px; background:#dbeafe; color:#1e40af; font-size: 11px; }}
    .page-break {{ break-before: page; }}
    @page {{ margin: 14mm 12mm; }}
    @media print {{
      main {{ padding: 0; max-width: none; }}
      h2 {{ break-after: avoid; }}
      table, .metric, .flow section, .callout {{ break-inside: avoid; }}
      a {{ color: inherit; text-decoration: none; }}
    }}
  </style>
</head>
<body>
<main>
  <h1>AI Hedge Fund OS Full Stack Report</h1>
  <p class="subtitle">Current live foundation, operating flows, agent team, model routing, data spine, MCP/skill stack, GUI surfaces, and remaining production gaps for the personal AI investment office.</p>
  <p class="stamp">Generated {html.escape(generated_at)} from live local API, Postgres read models, Qdrant collection metadata, and service health checks.</p>

  <section class="metrics">
    {metric_card("Active agents", office.get("active_agents", len(agents)), "role-based hedge team")}
    {metric_card("Active skills", office.get("active_skills", len(skills)), "agent skill registry")}
    {metric_card("Mailboxes", office.get("active_mailboxes", 0), "internal agent email")}
    {metric_card("Worker runs", len(snapshot.get("agent_worker_runs", [])), "recent API-visible runs")}
    {metric_card("Client accounts", len(snapshot.get("clients", [])), "live portfolio clients")}
    {metric_card("Position rows", len(snapshot.get("latest_positions", [])), "latest holdings view")}
    {metric_card("External skills", len(external_skills), "Fincept/OpenAlgo/Vibe")}
    {metric_card("Snapshot issues", len(snapshot.get("issues", [])), "API query failures")}
  </section>

  <div class="callout ok">
    <p><b>Current state:</b> The operating foundation is live: dashboard, API, Postgres warehouse, Qdrant retrieval collections, agent team, mailboxes, message daemon, worker notes, Obsidian writeback, and a first live AI office floor view.</p>
  </div>
  <div class="callout warning">
    <p><b>Boundary:</b> This is not yet a fully autonomous hedge fund or live broker execution system. Trading execution remains intentionally blocked behind human approval, risk review, connector proof, and execution safety gates.</p>
  </div>

  <h2>Architecture Flow</h2>
  {flow_diagram()}
  <p>The stable direction is existing systems and external sources into a live warehouse, then MCP/tool adapters, then Jarvis and specialist agents, with durable output to dashboards and Obsidian.</p>

  <h2>Live Operating Surfaces</h2>
  <div class="cols">
    <div>
      <h3>Implemented</h3>
      <ul>
        <li>AI Office dashboard at local URL with live warehouse snapshot.</li>
        <li>Charlie chat operating layer with retrieval and widget intent creation.</li>
        <li>Dashboard widgets backed by warehouse queries.</li>
        <li>Agent team roster, departments, skill matrix, model routing, hierarchy, mailboxes, messages.</li>
        <li>Live AI office floor panel showing employees and work-state animation labels.</li>
        <li>Obsidian output reports and worker run notes.</li>
      </ul>
    </div>
    <div>
      <h3>Remaining UI Product Work</h3>
      <ul>
        <li>Richer animated office scene with rooms, desks, hover cards, and live task movement.</li>
        <li>Click-through employee pages with task history, inbox, skills, model route, and outputs.</li>
        <li>Bloomberg-style portfolio and market dashboards with drill-down research packs.</li>
        <li>Browser/TradingView visual artifact capture panel.</li>
      </ul>
    </div>
  </div>

  <h2>Agent Communication Flow</h2>
  <div class="flow">
    <section><b>Message</b><p>Agent or user sends internal message to an agent mailbox.</p></section>
    <section><b>Daemon</b><p>LaunchAgent reads pending messages and creates tasks plus inbox rows.</p></section>
    <section><b>Worker</b><p>Agent worker picks up queue item and writes a bounded output note.</p></section>
    <section><b>Review</b><p>Inbox/task moves to needs review with evidence attached.</p></section>
    <section><b>Dashboard</b><p>Snapshot exposes message, queue, run, and output state.</p></section>
  </div>
  <p>Latest smoke proof: API-created message was processed by the daemon into task 16, inbox 23, and worker run 21.</p>
  {rows(messages, [("ID","id"),("From","from_agent"),("To","to_agent"),("Subject","subject"),("Processing","processing_status"),("Task","generated_task_id")], limit=12)}

  <h2>Hedge Team Hierarchy</h2>
  {hierarchy_tree(org)}

  <h2>Agent Details</h2>
  {rows(org, [("Agent","agent_name"),("Reports To","reports_to_agent"),("Level","hierarchy_level"),("Department","department_name"),("Mailbox","mailbox_address"),("Work State","animation_state")])}

  <h2>Model Routing</h2>
  {rows(models, [("Agent","agent_name"),("Primary Route","primary_route"),("Model","assigned_model"),("Provider","assigned_provider"),("Cost Tier","max_autonomous_cost_tier"),("Escalation","escalation_route")])}

  <h2>External Skill Stack</h2>
  {skill_summary(external_skills)}
  {rows(external_skills, [("Skill","skill_name"),("Source","source_family"),("Type","skill_type"),("Status","status"),("Mode","execution_mode"),("Adapter","direct_runtime_adapter"),("Agents","assigned_agents")])}

  <h2>Fincept Status</h2>
  {rows(fincept, [("Component","component_name"),("Install","install_status"),("Build","build_status"),("Runtime","runtime_mode"),("Notes","known_runtime_notes")])}
  <p>Fincept is installed as a local reference/component checkout and skill source. Direct delegated runtime use remains planned.</p>

  <h2>MCP And Connectors</h2>
  {mcp_rows}

  <h2>Workflow Registry</h2>
  {workflow_rows}

  <h2>Data Spine</h2>
  <div class="cols">
    <div>
      <h3>Qdrant Collections</h3>
      {qdrant_table}
    </div>
    <div>
      <h3>Pipeline Readiness</h3>
      {rows(readiness, [("Class","record_class"),("Area","area"),("Rows","row_count"),("Interpretation","interpretation")], limit=24)}
    </div>
  </div>

  <h2>Data Sources</h2>
  {data_source_rows}

  <h2>Dashboard Widgets</h2>
  {rows(widgets, [("Widget","widget_title"),("Workspace","workspace"),("Owner","owner_agent"),("Status","status"),("Task","task_status"),("Inbox","inbox_status")])}

  <h2>Production Readiness And Remaining Gaps</h2>
  <div class="cols">
    <div class="callout ok">
      <h3>Ready Now</h3>
      <ul>
        <li>SSD-backed runtime layout and persistent Postgres/Qdrant/Redis Docker data.</li>
        <li>API and UI LaunchAgents.</li>
        <li>Agent message daemon LaunchAgent.</li>
        <li>Internal mailbox to task to worker to note flow.</li>
        <li>Agent hierarchy, characters, models, skills, external skill registry.</li>
        <li>Obsidian notes indexed and reports written back.</li>
      </ul>
    </div>
    <div class="callout warning">
      <h3>Not Yet Final Hedge Fund Production</h3>
      <ul>
        <li>TradingView CDP is currently {html.escape(text(tradingview.get("available", False)))}; TradingView must be relaunched with remote debugging for desktop control.</li>
        <li>Ollama local model server works manually but is not started by default as a reliable LaunchAgent.</li>
        <li>OpenAlgo, Vibe-Trading, and Fincept direct adapters are planned, not fully delegated live adapters.</li>
        <li>Live broker execution remains disabled by design.</li>
        <li>NSE/BSE/news/social collectors and filing parsers need scheduled production connectors.</li>
        <li>Full animated office scene and employee hover/task movement are next UI layer.</li>
      </ul>
    </div>
  </div>

  <h2>Recommended Next Build Order</h2>
  <ol>
    <li>TradingView relaunch/controller fix and screenshot artifact capture.</li>
    <li>Read-only OpenAlgo market-data adapter, then options analytics.</li>
    <li>Vibe-Trading MCP read-only adapter for research/tools, isolated from broker writes.</li>
    <li>Fincept report/tool catalog bridge as component reference, then selected direct calls only if stable.</li>
    <li>News, filings, and corporate-action collectors with source URLs and scheduler.</li>
    <li>Animated AI office scene: employee hover cards, live task lines, mailbox badges, work-room grouping.</li>
    <li>Risk/approval policy engine before any broker write path.</li>
  </ol>

  <h2>Source Notes</h2>
  <p>External repo references used in stack design: FinceptTerminal, OpenAlgo OKF/docs, and Vibe-Trading. Local private data remains in the local SSD-backed warehouse and vault.</p>
</main>
</body>
</html>
"""
    output.write_text(html_doc, encoding="utf-8")
    return output


def main() -> int:
    path = build_html()
    print(json.dumps({"html": str(path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
