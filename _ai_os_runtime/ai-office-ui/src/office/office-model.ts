import type { LiveRow, OfficeSnapshot } from "../api/live";

export type OfficeAgentState = "active" | "blocked" | "idle" | "review" | "waiting";

export interface OfficeAgent {
  avatarRole: string;
  characterName: string;
  colorToken: string;
  id: string;
  name: string;
  role: string;
  roomId: string;
  roomLabel: string;
  state: OfficeAgentState;
  task: string;
  visualTraits: string;
  voiceStyle: string;
  workload: number;
  model: string;
  updatedAt: string;
}

export interface OfficeRoom {
  id: string;
  label: string;
  lead: string;
  status: string;
  agentCount: number;
  activeCount: number;
}

export interface CommitteeItem {
  id: string;
  title: string;
  status: string;
  owner: string;
  nextAction: string;
}

export interface OfficeModel {
  agents: OfficeAgent[];
  committeeItems: CommitteeItem[];
  rooms: OfficeRoom[];
}

function text(row: LiveRow, ...keys: string[]): string {
  for (const key of keys) {
    const value = row[key];
    if (value !== null && value !== undefined && String(value).trim()) {
      return String(value).trim();
    }
  }
  return "";
}

function number(row: LiveRow, ...keys: string[]): number {
  for (const key of keys) {
    const value = Number(row[key]);
    if (Number.isFinite(value)) {
      return value;
    }
  }
  return 0;
}

function key(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "") || "unassigned";
}

function agentState(value: string): OfficeAgentState {
  const normalized = value.toLowerCase();
  if (normalized.includes("block") || normalized.includes("fail") || normalized.includes("critical_risk")) {
    return "blocked";
  }
  if (normalized.includes("review") || normalized.includes("approval") || normalized.includes("needs_attention")) {
    return "review";
  }
  if (normalized.includes("wait") || normalized.includes("queue")) {
    return "waiting";
  }
  if (normalized.includes("run") || normalized.includes("work") || normalized.includes("active") || normalized.includes("executing")) {
    return "active";
  }
  return "idle";
}

function toAgent(row: LiveRow): OfficeAgent | null {
  const name = text(row, "agent_name", "agent_display_name", "name", "owner_agent", "owner");
  if (!name) {
    return null;
  }

  const roomLabel = text(row, "room_name", "office_room", "department_name", "department", "department_key") || "Unassigned";
  return {
    avatarRole: text(row, "avatar_role"),
    characterName: text(row, "character_name"),
    colorToken: text(row, "color_token"),
    id: text(row, "agent_id", "id") || key(name),
    name,
    role: text(row, "display_title", "role", "agent_role", "title") || "AI specialist",
    roomId: text(row, "room_key", "office_room_key", "department_key") || key(roomLabel),
    roomLabel,
    state: agentState(text(row, "live_state", "activity_status", "status", "state", "task_status")),
    task: text(row, "current_work_title", "current_task", "task_title", "activity_summary", "work_description", "task") || "No live task detail recorded",
    visualTraits: text(row, "visual_traits"),
    voiceStyle: text(row, "voice_style"),
    workload: number(row, "workload_score", "workload", "priority_score"),
    model: text(row, "model_name", "model", "provider_model", "default_model"),
    updatedAt: text(row, "latest_activity_at", "updated_at", "last_activity_at", "started_at")
  };
}

function toRoom(row: LiveRow): OfficeRoom | null {
  const label = text(row, "room_name", "department_name", "name", "room_key", "department_key");
  if (!label) {
    return null;
  }
  return {
    id: text(row, "room_key", "department_key", "id") || key(label),
    label,
    lead: text(row, "room_lead", "department_head", "manager", "lead"),
    status: text(row, "room_state", "status", "room_status", "activity_status") || "idle",
    agentCount: number(row, "agent_count", "employee_count", "member_count"),
    activeCount: number(row, "active_agent_count", "active_count", "active_agents")
  };
}

function toCommitteeItem(row: LiveRow): CommitteeItem | null {
  const title = text(row, "title", "review_title", "symbol", "strategy_name", "name");
  if (!title) {
    return null;
  }
  return {
    id: text(row, "id", "review_key", "committee_key") || key(title),
    title,
    status: text(row, "status", "decision_status", "review_status") || "open",
    owner: text(row, "owner_agent", "chair", "requested_by", "owner") || "Committee",
    nextAction: text(row, "next_action", "recommended_decision", "decision", "summary") || "Awaiting review"
  };
}

export function buildOfficeModel(snapshot: OfficeSnapshot | null): OfficeModel {
  if (!snapshot) {
    return { agents: [], committeeItems: [], rooms: [] };
  }

  const byAgent = new Map<string, OfficeAgent>();
  for (const row of [...snapshot.live_office_agent_activity, ...snapshot.agents]) {
    const agent = toAgent(row);
    if (!agent) {
      continue;
    }
    const existing = byAgent.get(agent.id);
    byAgent.set(agent.id, existing ? {
      ...agent,
      avatarRole: existing.avatarRole || agent.avatarRole,
      characterName: existing.characterName || agent.characterName,
      colorToken: existing.colorToken || agent.colorToken,
      model: existing.model || agent.model,
      role: existing.role || agent.role,
      roomId: existing.roomId || agent.roomId,
      roomLabel: existing.roomLabel || agent.roomLabel,
      state: existing.state,
      task: existing.task || agent.task,
      updatedAt: existing.updatedAt || agent.updatedAt,
      visualTraits: existing.visualTraits || agent.visualTraits,
      voiceStyle: existing.voiceStyle || agent.voiceStyle,
      workload: Math.max(existing.workload, agent.workload)
    } : agent);
  }
  const agents = [...byAgent.values()].sort((left, right) => right.workload - left.workload || left.name.localeCompare(right.name));

  const byRoom = new Map<string, OfficeRoom>();
  for (const row of snapshot.live_office_rooms) {
    const room = toRoom(row);
    if (room) {
      byRoom.set(room.id, room);
    }
  }
  for (const agent of agents) {
    const room = byRoom.get(agent.roomId);
    if (room) {
      room.agentCount = Math.max(room.agentCount, agents.filter((candidate) => candidate.roomId === room.id).length);
      room.activeCount = Math.max(room.activeCount, agents.filter((candidate) => candidate.roomId === room.id && candidate.state === "active").length);
      continue;
    }
    const matchingRoom = [...byRoom.values()].find((candidate) => key(candidate.label) === key(agent.roomLabel));
    if (matchingRoom) {
      agent.roomId = matchingRoom.id;
      continue;
    }
    byRoom.set(agent.roomId, {
      id: agent.roomId,
      label: agent.roomLabel,
      lead: "",
      status: agent.state,
      agentCount: agents.filter((candidate) => candidate.roomId === agent.roomId).length,
      activeCount: agents.filter((candidate) => candidate.roomId === agent.roomId && candidate.state === "active").length
    });
  }

  const byCommitteeItem = new Map<string, CommitteeItem>();
  for (const row of [
    ...snapshot.committee_room_items,
    ...(snapshot.strategy_committee_queue ?? []),
    ...(snapshot.long_term_committee_queue ?? [])
  ]) {
    const item = toCommitteeItem(row);
    if (item) {
      byCommitteeItem.set(item.id, item);
    }
  }

  return {
    agents,
    committeeItems: [...byCommitteeItem.values()].slice(0, 8),
    rooms: [...byRoom.values()].sort((left, right) => right.activeCount - left.activeCount || left.label.localeCompare(right.label))
  };
}
