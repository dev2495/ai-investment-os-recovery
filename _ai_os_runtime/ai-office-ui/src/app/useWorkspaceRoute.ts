import { useCallback, useEffect, useState } from "react";
import type { WorkspaceId } from "../types";

export type InterfaceMode = "command" | "office";

interface WorkspaceRoute {
  mode: InterfaceMode;
  workspace: WorkspaceId;
}

const workspaceIds: WorkspaceId[] = ["command", "approvals", "agents", "departments", "committees", "governance", "portfolio", "clients", "research", "ideas", "arsenal", "trading", "quant", "risk", "capital", "treasury", "models", "reports", "system"];

function readRoute(): WorkspaceRoute {
  const params = new URLSearchParams(window.location.search);
  const requestedWorkspace = params.get("workspace");
  return {
    mode: params.get("mode") === "office" ? "office" : "command",
    workspace: workspaceIds.includes(requestedWorkspace as WorkspaceId) ? (requestedWorkspace as WorkspaceId) : "command"
  };
}

function writeRoute(route: WorkspaceRoute, replace = false): void {
  const url = new URL(window.location.href);
  url.searchParams.set("mode", route.mode);
  url.searchParams.set("workspace", route.workspace);
  window.history[replace ? "replaceState" : "pushState"]({}, "", url);
}

export function useWorkspaceRoute() {
  const [route, setRoute] = useState<WorkspaceRoute>(readRoute);

  useEffect(() => {
    const onPopState = () => setRoute(readRoute());
    window.addEventListener("popstate", onPopState);
    writeRoute(route, true);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const navigate = useCallback((next: Partial<WorkspaceRoute>) => {
    setRoute((current) => {
      const nextRoute = { ...current, ...next };
      writeRoute(nextRoute);
      return nextRoute;
    });
  }, []);

  const openCommandWorkspace = useCallback((workspace: WorkspaceId) => navigate({ mode: "command", workspace }), [navigate]);

  return {
    activeWorkspace: route.workspace,
    interfaceMode: route.mode,
    openCommandWorkspace,
    setActiveWorkspace: (workspace: WorkspaceId) => navigate({ workspace }),
    setInterfaceMode: (mode: InterfaceMode) => navigate({ mode })
  };
}
