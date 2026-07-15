import { ArrowDown, ArrowUp, Eye, EyeOff, LayoutDashboard, X } from "lucide-react";
import { useMemo, useState } from "react";
import type { LiveRow } from "../api/live";
import {
  fetchWorkspaceConfig,
  updateDashboardWidget,
  updateWorkspaceConfig,
  type CustomizableWorkspace,
  type WorkspaceConfig
} from "../api/terminal";

interface Props {
  config: WorkspaceConfig;
  onChanged: (config: WorkspaceConfig) => void;
  onClose: () => void;
  workspace: string;
}

const workspaceOptions = [
  ["command", "Command"], ["approvals", "Approvals"], ["agents", "Agents"],
  ["departments", "Departments"], ["committees", "Committees"], ["governance", "Governance"],
  ["portfolio", "Portfolio"], ["clients", "Clients"], ["tactical", "Tactical"], ["capital", "Capital"],
  ["treasury", "Treasury"], ["research", "Research"], ["ideas", "Ideas"],
  ["reports", "Reports"], ["arsenal", "Arsenal"], ["trading", "Trading"],
  ["quant", "Quant"], ["risk", "Risk"], ["models", "Data & models"], ["system", "System"]
] as const;

function text(row: LiveRow, key: string, fallback = "-"): string {
  const value = row[key];
  return value === null || value === undefined || value === "" ? fallback : String(value);
}

export default function WorkspaceManager({ config, onChanged, onClose, workspace }: Props) {
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const layout = config.layouts.find((item) => item.workspace_key === workspace);
  const widgets = useMemo(
    () => config.widgets.filter((item) => text(item, "workspace") === workspace),
    [config.widgets, workspace]
  );
  const visibleWorkspaces = useMemo(() => {
    const visible = config.profile.navigation?.visible;
    return Array.isArray(visible) && visible.length ? visible.map(String) : workspaceOptions.map(([key]) => key);
  }, [config.profile.navigation]);

  const saveProfile = async (patch: Record<string, unknown>) => {
    setBusy("profile");
    setError("");
    try {
      onChanged(await updateWorkspaceConfig({ actor: "Devarsh", profile_key: config.profile.profile_key, ...patch }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Workspace update failed");
    } finally {
      setBusy("");
    }
  };

  const saveWidget = async (widget: LiveRow, patch: Record<string, unknown>) => {
    const id = text(widget, "id");
    setBusy(`widget-${id}`);
    setError("");
    try {
      await updateDashboardWidget({ actor: "Devarsh", widget_id: Number(id), ...patch });
      onChanged(await fetchWorkspaceConfig(config.profile.profile_key));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Widget update failed");
    } finally {
      setBusy("");
    }
  };

  const setWorkspaceVisible = async (key: string, checked: boolean) => {
    const next = checked
      ? Array.from(new Set([...visibleWorkspaces, key]))
      : visibleWorkspaces.filter((item) => item !== key);
    await saveProfile({ navigation: { visible: next } });
  };

  return (
    <div className="workspace-manager-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <aside aria-label="Workspace manager" aria-modal="true" className="workspace-manager" role="dialog">
        <header>
          <div><span><LayoutDashboard size={14} aria-hidden="true" />Workspace manager</span><h2>{config.profile.profile_name}</h2><p>Reversible view controls. Data lineage and execution gates stay unchanged.</p></div>
          <button aria-label="Close workspace manager" onClick={onClose} title="Close" type="button"><X size={18} /></button>
        </header>
        {error ? <div className="error-strip">{error}</div> : null}
        <div className="workspace-manager-body">
          <section>
            <div className="terminal-section-heading"><span>Terminal appearance</span><strong>v{config.profile.version}</strong></div>
            <div className="workspace-segment-row">
              <span>Theme</span>
              <div className="segmented-control">
                {(["terminal_dark", "terminal_light"] as const).map((theme) => <button className={config.profile.theme === theme ? "active" : ""} disabled={busy === "profile"} key={theme} onClick={() => void saveProfile({ theme })} type="button">{theme === "terminal_dark" ? "Dark" : "Light"}</button>)}
              </div>
            </div>
            <div className="workspace-segment-row">
              <span>Density</span>
              <div className="segmented-control">
                {(["compact", "standard"] as const).map((density) => <button className={config.profile.density === density ? "active" : ""} disabled={busy === "profile"} key={density} onClick={() => void saveProfile({ density })} type="button">{density}</button>)}
              </div>
            </div>
            {layout ? <div className="workspace-segment-row"><span>Columns</span><div className="segmented-control">{[1, 2, 3].map((count) => <button className={layout.column_count === count ? "active" : ""} disabled={busy === "profile"} key={count} onClick={() => void saveProfile({ column_count: count, workspace_key: workspace as CustomizableWorkspace })} type="button">{count}</button>)}</div></div> : null}
            <div className="workspace-navigation-grid">
              {workspaceOptions.map(([key, label]) => <label key={key}><input checked={visibleWorkspaces.includes(key)} disabled={busy === "profile" || key === workspace} onChange={(event) => void setWorkspaceVisible(key, event.target.checked)} type="checkbox"/><span>{label}</span></label>)}
            </div>
          </section>

          <section>
            <div className="terminal-section-heading"><span>{workspace} widgets</span><strong>{widgets.length}</strong></div>
            <div className="workspace-widget-list">
              {widgets.map((widget) => {
                const id = text(widget, "id");
                const widgetLayout = (widget.layout && typeof widget.layout === "object" ? widget.layout : {}) as Record<string, unknown>;
                const order = Number(widgetLayout.order ?? 100);
                const size = String(widgetLayout.size ?? "standard");
                const hidden = text(widget, "status", "active") === "hidden";
                return (
                  <article key={id}>
                    <div><strong>{text(widget, "widget_title", "Widget")}</strong><span>{text(widget, "owner_agent")} · {text(widget, "query_ref")}</span></div>
                    <div className="workspace-widget-actions">
                      <button aria-label="Move widget up" disabled={busy === `widget-${id}`} onClick={() => void saveWidget(widget, { order: Math.max(0, order - 10) })} title="Move up" type="button"><ArrowUp size={14} /></button>
                      <button aria-label="Move widget down" disabled={busy === `widget-${id}`} onClick={() => void saveWidget(widget, { order: order + 10 })} title="Move down" type="button"><ArrowDown size={14} /></button>
                      <button aria-label={hidden ? "Show widget" : "Hide widget"} disabled={busy === `widget-${id}`} onClick={() => void saveWidget(widget, { status: hidden ? "active" : "hidden" })} title={hidden ? "Show" : "Hide"} type="button">{hidden ? <Eye size={14} /> : <EyeOff size={14} />}</button>
                    </div>
                    <div className="workspace-widget-size segmented-control" aria-label={`${text(widget, "widget_title")} size`}>
                      {["standard", "wide", "full"].map((option) => <button className={size === option ? "active" : ""} disabled={busy === `widget-${id}`} key={option} onClick={() => void saveWidget(widget, { size: option })} type="button">{option}</button>)}
                    </div>
                  </article>
                );
              })}
              {!widgets.length ? <p className="empty-state">Ask Charlie to add a widget to this workspace. It will appear here with durable layout controls.</p> : null}
            </div>
          </section>
        </div>
      </aside>
    </div>
  );
}
