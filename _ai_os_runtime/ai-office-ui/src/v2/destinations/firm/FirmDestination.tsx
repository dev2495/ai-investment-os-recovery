import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Activity, Boxes, Building2, Cpu, Gavel, Mail, ShieldCheck, Users } from "lucide-react";
import { useIntegrationGateway, useOfficeSnapshot, useSystemHealth } from "../../data/queries";
import { formatRelative, initials, num, primaryText, text } from "../../data/liveRow";
import { Freshness, LiveTable, MetricCell, MetricStrip, RowTitle, StatusCell, WorkspaceError, WorkspaceGrid, countStatus } from "../../data/WorkspaceKit";
import { Avatar, Badge, Panel, StatusPill, Tabs } from "../../system/primitives";
import { useUIStore } from "../../store";
import { buildOfficeModel } from "../../../office/office-model";
import { OfficeView } from "./OfficeView";

const TABS = [
  { key: "office", label: "Live Office", icon: Boxes },
  { key: "agents", label: "Employees", icon: Users },
  { key: "departments", label: "Departments", icon: Building2 },
  { key: "committees", label: "Committees", icon: Gavel },
  { key: "governance", label: "Governance", icon: ShieldCheck },
  { key: "models", label: "Models", icon: Cpu },
  { key: "system", label: "System", icon: Activity },
];

export default function FirmDestination() {
  const location = useLocation();
  const navigate = useNavigate();
  const tab = location.pathname.split("/").filter(Boolean)[1] ?? "office";
  const active = TABS.some((item)=>item.key===tab) ? tab : "office";
  const office = useOfficeSnapshot();
  const model = React.useMemo(()=>buildOfficeModel((office.data ?? null) as never),[office.data]);
  const activeAgents = model.agents.filter((agent)=>agent.state!=="idle").length;
  const blocked = model.agents.filter((agent)=>agent.state==="blocked").length;
  return <div className="aios-destination"><div className="aios-destination__head"><div className="aios-destination__title-row"><div className="aios-destination__title">The Firm</div><Freshness generatedAt={office.data?.generated_at}/></div><div className="aios-destination__subtitle">The operating company behind the fund: people, inboxes, committees, authority, models and infrastructure.</div><Tabs tabs={TABS.map((item)=>item.key==="agents"?{...item,count:model.agents.length}:item.key==="committees"?{...item,count:model.committeeItems.length,countTone:"risk" as const}:item)} active={active} onChange={(key)=>navigate(`/firm/${key}`)}/></div><WorkspaceError error={office.error}/><MetricStrip><MetricCell label="Employees" value={model.agents.length} detail={`${activeAgents} working now`}/><MetricCell label="Departments" value={model.rooms.length}/><MetricCell label="Open committees" value={model.committeeItems.length} tone={model.committeeItems.length?"warn":"ok"}/><MetricCell label="Blocked employees" value={blocked} tone={blocked?"risk":"ok"}/><MetricCell label="Agent mail" value={office.data?.agent_messages.length??0}/><MetricCell label="Priority tasks" value={office.data?.priority_tasks.length??0}/></MetricStrip>{active==="office"?<OfficeView/>:active==="agents"?<Agents model={model}/>:active==="departments"?<Departments model={model}/>:active==="committees"?<Committees model={model}/>:active==="governance"?<Governance data={office.data}/>:active==="models"?<Models/>:<System/>}</div>;
}

type OfficeModel = ReturnType<typeof buildOfficeModel>;

function Agents({model}:{model:OfficeModel}) {
  const setScope=useUIStore((state)=>state.setAssistantScope);
  const openAgent=(agent:OfficeModel["agents"][number])=>{setScope({agentKey:agent.id,agentName:agent.name});window.dispatchEvent(new CustomEvent("aios:assistant-prefill",{detail:`Give me a concise status report from ${agent.name}: current work, evidence, blockers, next action, and any decision needed from me.`}));};
  return <div className="aios-agent-grid">{model.agents.map((agent)=><button className="aios-agent-card" key={agent.id} onClick={()=>openAgent(agent)} type="button"><Avatar initials={initials(agent.characterName||agent.name)} ring={agent.state==="active"?"ok":agent.state==="blocked"?"risk":agent.state==="review"?"warn":"idle"} name={agent.name}/><div className="aios-agent-card__body"><strong>{agent.characterName||agent.name}</strong><span>{agent.role} · {agent.roomLabel}</span><p>{agent.task}</p></div><StatusPill status={agent.state} dot pulse={agent.state==="active"}>{agent.state}</StatusPill></button>)}</div>;
}

function Departments({model}:{model:OfficeModel}) { return <WorkspaceGrid columns="3">{model.rooms.map((room)=><Panel key={room.id} icon={Building2} title={room.label} actions={<StatusPill status={room.status}>{room.status}</StatusPill>}><MetricStrip><MetricCell label="Employees" value={room.agentCount}/><MetricCell label="Active" value={room.activeCount} tone={room.activeCount?"ok":"default"}/><MetricCell label="Lead" value={room.lead||"Unassigned"}/></MetricStrip><LiveTable rows={model.agents.filter((agent)=>agent.roomId===room.id) as unknown as Record<string,unknown>[]} emptyTitle="No employees assigned" limit={12} columns={[
    {key:"name",label:"Employee",render:(row)=><RowTitle row={row} titleKeys={["characterName","name"]} detailKeys={["role","task"]}/>},{key:"state",label:"State",render:(row)=><StatusCell row={row} keys={["state"]}/>},
  ]}/></Panel>)}</WorkspaceGrid>; }

function Committees({model}:{model:OfficeModel}) { return <WorkspaceGrid><Panel className="aios-workspace-span" icon={Gavel} title="Committee decision room"><LiveTable rows={model.committeeItems as unknown as Record<string,unknown>[]} emptyTitle="No committee matters" columns={[
    {key:"title",label:"Matter",render:(row)=><RowTitle row={row} titleKeys={["title"]} detailKeys={["nextAction"]}/>},{key:"owner",label:"Chair / owner"},{key:"riskLevel",label:"Risk",render:(row)=><StatusCell row={row} keys={["riskLevel","status"]}/>},{key:"approvalStatus",label:"Approval",render:(row)=><StatusCell row={row} keys={["approvalStatus","decisionStatus"]}/>},{key:"requiredFollowups",label:"Follow-ups",align:"right"},{key:"finalDecision",label:"Decision"},
  ]}/></Panel></WorkspaceGrid>; }

function Governance({data}:{data:ReturnType<typeof useOfficeSnapshot>["data"]}) { const execution=data?.execution_control[0]; const stale=countStatus(data?.source_freshness??[],["stale","failed","error"]); return <WorkspaceGrid><Panel icon={ShieldCheck} title="Authority boundary"><MetricStrip><MetricCell label="Execution locked" value={String(execution?.global_execution_locked??true)} tone="ok"/><MetricCell label="Broker writes" value={String(execution?.live_broker_writes_allowed??false)} tone={execution?.live_broker_writes_allowed?"risk":"ok"}/><MetricCell label="Approval policy" value={text(execution,"broker_execution_policy","blocked")}/></MetricStrip></Panel><Panel icon={Activity} title="Evidence health"><MetricStrip><MetricCell label="Risk events" value={data?.risk_events.length??0} tone={data?.risk_events.length?"warn":"ok"}/><MetricCell label="Stale sources" value={stale} tone={stale?"risk":"ok"}/><MetricCell label="Issues" value={data?.issues.length??0}/></MetricStrip></Panel><Panel className="aios-workspace-span" icon={ShieldCheck} title="Risk events"><LiveTable rows={data?.risk_events??[]} emptyTitle="No open risk events" columns={[
    {key:"title",label:"Event",render:(row)=><RowTitle row={row} titleKeys={["title"]} detailKeys={["message","recommended_action"]}/>},{key:"scope_ref",label:"Scope"},{key:"owner_agent",label:"Owner"},{key:"severity",label:"Severity",render:(row)=><StatusCell row={row} keys={["severity","status"]}/>},{key:"updated_at",label:"Updated"},
  ]}/></Panel><Panel className="aios-workspace-span" icon={Mail} title="Agent inbox traffic"><LiveTable rows={data?.agent_messages??[]} emptyTitle="No agent messages" columns={[
    {key:"subject",label:"Message",render:(row)=><RowTitle row={row} titleKeys={["subject"]} detailKeys={["body"]}/>},{key:"from_agent",label:"From"},{key:"to_agent",label:"To"},{key:"priority",label:"Priority",render:(row)=><StatusCell row={row} keys={["priority","status"]}/>},{key:"created_at",label:"Time"},
  ]}/></Panel></WorkspaceGrid>; }

function Models() { const query=useIntegrationGateway(); const data=query.data; return <WorkspaceGrid><WorkspaceError error={query.error}/><Panel className="aios-workspace-span" icon={Cpu} title="Task-to-model routing"><LiveTable rows={data?.model_route_control??data?.model_routes??[]} emptyTitle="No model routes" columns={[
    {key:"route_name",label:"Route",render:(row)=><RowTitle row={row} titleKeys={["route_name"]} detailKeys={["notes","policy_reason"]}/>},{key:"default_provider",label:"Provider"},{key:"default_model",label:"Model"},{key:"max_cost_tier",label:"Cost tier"},{key:"status",label:"Status",render:(row)=><StatusCell row={row} keys={["assignment_status","status","enabled"]}/>},
  ]}/></Panel><Panel icon={Activity} title="Runtime endpoints"><LiveTable rows={data?.model_runtime_summary??[]} emptyTitle="No model endpoints" columns={[
    {key:"provider",label:"Provider"},{key:"model",label:"Model"},{key:"status",label:"Health",render:(row)=><StatusCell row={row} keys={["health_status","status"]}/>},{key:"latency_ms",label:"Latency",align:"right"},
  ]}/></Panel><Panel icon={ShieldCheck} title="Provider readiness"><LiveTable rows={data?.provider_readiness??[]} emptyTitle="No provider readiness checks" columns={[
    {key:"provider",label:"Provider",render:(row)=><RowTitle row={row} titleKeys={["provider","provider_key"]} detailKeys={["reason","notes"]}/>},{key:"status",label:"Gate",render:(row)=><StatusCell row={row} keys={["assignment_gate","status"]}/>},{key:"quality_score",label:"Quality",align:"right"},
  ]}/></Panel></WorkspaceGrid>; }

function System() { const query=useSystemHealth(); const data=query.data; return <WorkspaceGrid><WorkspaceError error={query.error}/><Panel icon={Activity} title="Runtime daemons"><LiveTable rows={data?.runtime_daemons??[]} emptyTitle="No daemon status" columns={[
    {key:"daemon_name",label:"Service",render:(row)=><RowTitle row={row} titleKeys={["daemon_name","service_name","label"]} detailKeys={["detail","command"]}/>},{key:"status",label:"Status",render:(row)=><StatusCell row={row} keys={["health_status","status","state"]}/>},{key:"checked_at",label:"Checked"},
  ]}/></Panel><Panel icon={Activity} title="Storage and recovery"><MetricStrip><MetricCell label="Vault mounted" value={String(data?.storage?.vault_mounted??false)} tone={data?.storage?.vault_mounted?"ok":"risk"}/><MetricCell label="Heavy state external" value={String(data?.storage?.heavy_state_external??false)} tone={data?.storage?.heavy_state_external?"ok":"warn"}/><MetricCell label="Latest backup" value={data?.recovery?.created_at?formatRelative(data.recovery.created_at):"Unknown"}/><MetricCell label="Vault files" value={data?.recovery?.vault_file_count??0}/></MetricStrip></Panel><Panel className="aios-workspace-span" icon={Activity} title="Data-source health"><LiveTable rows={data?.source_freshness??[]} emptyTitle="No source checks" columns={[
    {key:"source_name",label:"Source",render:(row)=><RowTitle row={row} titleKeys={["source_name","source_key"]} detailKeys={["message","next_action"]}/>},{key:"status",label:"Health",render:(row)=><StatusCell row={row} keys={["freshness_status","status","health_status"]}/>},{key:"row_count",label:"Rows",align:"right"},{key:"last_success_at",label:"Last success"},
  ]}/></Panel></WorkspaceGrid>; }
