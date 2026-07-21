import React from "react";
import { AlertTriangle } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAction, useOfficeSnapshot, queryKeys } from "../../data/queries";
import { Panel } from "../../system/primitives";
import type { WorkspaceId } from "../../../types";

const LiveOffice = React.lazy(() => import("../../../office/LiveOffice"));

const workspaceRoute: Partial<Record<WorkspaceId, string>> = {
  command: "/today", approvals: "/today", agents: "/firm/agents",
  departments: "/firm/departments", committees: "/firm/committees",
  governance: "/firm/governance", portfolio: "/portfolio", clients: "/portfolio",
  tactical: "/risk-trading/scanners", research: "/research", ideas: "/research",
  arsenal: "/research", trading: "/risk-trading/trading", quant: "/risk-trading/quant",
  risk: "/risk-trading", models: "/firm/models", reports: "/research/reports",
  system: "/firm/system", capital: "/portfolio", treasury: "/research",
};

export function OfficeView() {
  const query = useOfficeSnapshot();
  const navigate = useNavigate();
  const send = useAction<{ body: string; subject: string; to_agent: string }>("/api/agents/messages", { invalidate: [queryKeys.office] });
  if (query.error) return <Panel variant="risk" icon={AlertTriangle} title="Cannot reach live office"><p className="aios-workspace-error">{query.error.message}</p></Panel>;
  return (
    <div className="aios-office-host">
      <React.Suspense fallback={<div className="aios-skeleton" style={{height:"100%"}}/>}>
        <LiveOffice
          liveStatus={query.isLoading ? "loading" : query.data ? "online" : "offline"}
          snapshot={query.data ?? null}
          onExit={() => navigate("/firm/agents")}
          onRefresh={() => void query.refetch()}
          onSelectWorkspace={(workspace) => navigate(workspaceRoute[workspace] ?? "/today")}
          onSendMessage={async ({body,subject,toAgent}) => { await send.mutateAsync({body,subject,to_agent:toAgent}); }}
        />
      </React.Suspense>
    </div>
  );
}
