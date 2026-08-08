import React from "react";
import { Canvas, useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import { AdaptiveDpr, Html, Line, OrbitControls } from "@react-three/drei";
import { useNavigate } from "react-router-dom";
import * as THREE from "three";
import { ROOMS, floorY, roomByKey, type RoomDef } from "./officeLayout";
import { useOfficeSnapshot } from "../data/queries";
import { useDelegateAgentTask } from "../data/actions";
import { useUIStore } from "../store";
import { formatRelative, num, text } from "../data/liveRow";
import type { LiveRow } from "../data/liveRow";
import { LiveOfficeCss } from "./LiveOffice.css";

const ACTIVE_STATES = ["active", "working", "running", "executing", "in_progress", "processing"];
const BLOCKED_STATES = ["blocked", "error", "failed", "critical"];

function normalizeDepartment(raw: string): string {
  const value = raw.toLowerCase().trim().replace(/[^a-z0-9]+/g, "_");
  const aliases: Record<string, string> = {
    knowledge_and_memory: "knowledge",
    knowledge_memory: "knowledge",
    risk_and_compliance: "risk",
    risk_compliance: "risk",
    quant_lab: "quant",
    quantitative_strategies_office: "quant",
    research_desk: "research",
    research_factory: "research",
    trading_desk: "trading",
    active_trading_desk: "trading",
    portfolio_office: "portfolio",
    client_office: "client",
    software_engineering: "software",
    automation_engineering: "automation",
    treasury_hedges_and_macro: "treasury",
    tactical_investing_office: "tactical",
    executive_office: "executive",
    runtime_operations: "runtime",
    data_engineering: "data",
    news_intelligence: "news",
  };
  return aliases[value] ?? value;
}

function agentDepartment(agent: LiveRow): string {
  return normalizeDepartment(text(agent, "department_key", text(agent, "department", text(agent, "department_name"))));
}

function agentRoomKey(agent: LiveRow): string {
  const department = agentDepartment(agent);
  return roomByKey(department) ? department : "lobby";
}

function liveState(agent: LiveRow): string {
  return text(
    agent,
    "presence_state",
    text(
      agent,
      "live_state",
      text(agent, "current_task_status", text(agent, "latest_worker_status", "idle")),
    ),
  ).toLowerCase();
}

function isBusy(agent: LiveRow): boolean {
  const state = liveState(agent);
  return ACTIVE_STATES.some((candidate) => state.includes(candidate));
}

function isBlocked(agent: LiveRow): boolean {
  const state = liveState(agent);
  return BLOCKED_STATES.some((candidate) => state.includes(candidate)) || num(agent, "blocked_task_count") > 0;
}

function mergeAgents(data: ReturnType<typeof useOfficeSnapshot>["data"]): LiveRow[] {
  if (!data) return [];
  const profiles = new Map((data.agents ?? []).map((row) => [text(row, "agent_name"), row]));
  const activity = data.live_office_agent_activity ?? [];
  const merged = activity.map((row) => ({
    ...(profiles.get(text(row, "agent_name")) ?? {}),
    ...row,
  }));
  const activeNames = new Set(merged.map((row) => text(row, "agent_name")));
  for (const profile of data.agents ?? []) {
    if (!activeNames.has(text(profile, "agent_name"))) merged.push(profile);
  }
  return merged;
}

function agentPlacements(room: RoomDef, agents: LiveRow[]) {
  if (agents.length === 0) return [];
  const [width, depth] = room.size;
  const ratio = Math.max(0.8, width / depth);
  const columns = Math.max(1, Math.ceil(Math.sqrt(agents.length * ratio)));
  const rows = Math.max(1, Math.ceil(agents.length / columns));
  const usableWidth = width - 1.0;
  const usableDepth = depth - 1.25;
  const spacingX = usableWidth / columns;
  const spacingZ = usableDepth / rows;
  const scale = Math.max(0.34, Math.min(0.58, Math.min(spacingX / 1.75, spacingZ / 1.35)));
  return agents.map((agent, index) => {
    const column = index % columns;
    const row = Math.floor(index / columns);
    return {
      agent,
      position: [
        -usableWidth / 2 + spacingX * (column + 0.5),
        -usableDepth / 2 + spacingZ * (row + 0.5),
      ] as [number, number],
      scale,
    };
  });
}

function hashName(name: string): number {
  let hash = 0;
  for (let index = 0; index < name.length; index += 1) hash = ((hash << 5) - hash + name.charCodeAt(index)) | 0;
  return Math.abs(hash);
}

interface RoomProps {
  room: RoomDef;
  agents: LiveRow[];
  stats?: LiveRow;
  hasRisk: boolean;
  isFocused: boolean;
  isHovered: boolean;
  committeeItems: number;
  activeGraphRuns: number;
  selectedAgentName: string;
  onHover: (hovered: boolean) => void;
  onClick: () => void;
  onSelectAgent: (agent: LiveRow) => void;
}

function Room({
  room,
  agents,
  stats,
  hasRisk,
  isFocused,
  isHovered,
  committeeItems,
  activeGraphRuns,
  selectedAgentName,
  onHover,
  onClick,
  onSelectAgent,
}: RoomProps) {
  const y = floorY(room.floor);
  const [width, depth] = room.size;
  const [centerX, centerZ] = room.center;
  const wallHeight = 2.8;
  const placements = React.useMemo(() => agentPlacements(room, agents), [agents, room]);
  const workingCount = stats ? num(stats, "executing_agent_count") : agents.filter(isBusy).length;
  const queuedCount = stats ? num(stats, "queued_agent_count") : agents.filter((agent) => liveState(agent) === "queued").length;
  const blockedCount = stats ? num(stats, "blocked_task_count") : agents.filter(isBlocked).length;
  const groupRef = React.useRef<THREE.Group>(null);

  useFrame((state) => {
    if (!groupRef.current || !hasRisk) return;
    const pulse = 0.35 + 0.25 * Math.sin(state.clock.elapsedTime * 2.4);
    groupRef.current.traverse((child) => {
      const mesh = child as THREE.Mesh;
      if (mesh.material && child.userData.riskGlow) {
        (mesh.material as THREE.MeshStandardMaterial).emissiveIntensity = pulse;
      }
    });
  });

  return (
    <group
      ref={groupRef}
      position={[centerX, y, centerZ]}
      onPointerOver={(event: ThreeEvent<PointerEvent>) => {
        event.stopPropagation();
        onHover(true);
        document.body.style.cursor = "pointer";
      }}
      onPointerOut={() => {
        onHover(false);
        document.body.style.cursor = "default";
      }}
      onClick={(event: ThreeEvent<MouseEvent>) => {
        event.stopPropagation();
        onClick();
      }}
    >
      <mesh position={[0, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[width - 0.1, depth - 0.1]} />
        <meshStandardMaterial color="#ae8259" roughness={0.66} />
      </mesh>
      <mesh position={[0, 0.035, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[Math.max(1, width - 1.1), Math.max(1, depth - 1.1)]} />
        <meshStandardMaterial color={room.color} roughness={0.9} transparent opacity={0.17} />
      </mesh>

      <mesh position={[0, wallHeight / 2, -depth / 2]}>
        <boxGeometry args={[width, wallHeight, 0.07]} />
        <meshStandardMaterial color="#d8e4ec" transparent opacity={0.2} roughness={0.18} />
      </mesh>
      <mesh position={[0, wallHeight / 2, depth / 2]}>
        <boxGeometry args={[Math.max(1, width - 2.2), wallHeight, 0.07]} />
        <meshStandardMaterial color="#d8e4ec" transparent opacity={0.16} roughness={0.18} />
      </mesh>
      <mesh position={[-width / 2, wallHeight / 2, 0]}>
        <boxGeometry args={[0.07, wallHeight, depth]} />
        <meshStandardMaterial color="#d8e4ec" transparent opacity={0.18} roughness={0.18} />
      </mesh>
      <mesh position={[width / 2, wallHeight / 2, 0]}>
        <boxGeometry args={[0.07, wallHeight, depth]} />
        <meshStandardMaterial color="#d8e4ec" transparent opacity={0.18} roughness={0.18} />
      </mesh>
      <mesh position={[0, wallHeight, -depth / 2]}>
        <boxGeometry args={[width + 0.08, 0.08, 0.08]} />
        <meshStandardMaterial color="#aa8758" metalness={0.78} roughness={0.34} />
      </mesh>

      {hasRisk && (
        <mesh position={[0, 0.055, 0]} rotation={[-Math.PI / 2, 0, 0]} userData={{ riskGlow: true }}>
          <ringGeometry args={[Math.max(width, depth) / 2.35, Math.max(width, depth) / 2.08, 48]} />
          <meshStandardMaterial color="#b53c32" emissive="#b53c32" emissiveIntensity={0.45} transparent opacity={0.74} side={THREE.DoubleSide} />
        </mesh>
      )}

      {room.key === "committee" && <CommitteeTable itemCount={committeeItems} />}
      {room.key === "lobby" && <LobbyConsole activeGraphRuns={activeGraphRuns} />}

      {placements.map((placement) => (
        <DeskAndAgent
          key={text(placement.agent, "agent_name")}
          agent={placement.agent}
          position={placement.position}
          scale={placement.scale}
          accent={room.color}
          selected={selectedAgentName === text(placement.agent, "agent_name")}
          onSelect={() => onSelectAgent(placement.agent)}
        />
      ))}

      <Html position={[0, wallHeight + 0.55, 0]} center distanceFactor={12} occlude={false} zIndexRange={[20, 0]}>
        <div className={`office-room-label ${hasRisk ? "office-room-label--risk" : ""} ${isFocused ? "office-room-label--active" : ""}`}>
          <span className="office-room-label__name">{room.label}</span>
          <div className="office-room-label__meta">
            <span className={`office-room-label__dot office-room-label__dot--${hasRisk ? "risk" : "ok"}`} />
            <span>{agents.length} employees · {workingCount} working{queuedCount ? ` · ${queuedCount} queued` : ""}</span>
            {blockedCount > 0 && <span className="office-room-label__pending">{blockedCount} blocked</span>}
          </div>
        </div>
      </Html>

      {(isHovered || isFocused) && (
        <mesh position={[0, wallHeight / 2, 0]}>
          <boxGeometry args={[width + 0.35, wallHeight + 0.35, depth + 0.35]} />
          <meshBasicMaterial color={room.color} wireframe transparent opacity={isFocused ? 0.42 : 0.2} />
        </mesh>
      )}
    </group>
  );
}

function DeskAndAgent({
  agent,
  position,
  scale,
  accent,
  selected,
  onSelect,
}: {
  agent: LiveRow;
  position: [number, number];
  scale: number;
  accent: string;
  selected: boolean;
  onSelect: () => void;
}) {
  const [hovered, setHovered] = React.useState(false);
  const state = liveState(agent);
  const busy = isBusy(agent);
  const blocked = isBlocked(agent);
  const name = text(agent, "agent_name", "Employee");
  const currentWork = text(agent, "current_work_title", text(agent, "current_task_title", "No active assignment"));
  const title = text(agent, "display_title", text(agent, "role_scope", agentDepartment(agent)));
  const seed = hashName(name);
  const skinColors = ["#e8d0b0", "#c8956c", "#8f6046", "#f0c9a5", "#ad7657"];
  const bodyColors = ["#294f70", "#3f6255", "#5b4d79", "#71503e", "#354a61", "#6b5b35"];
  const skin = skinColors[seed % skinColors.length];
  const body = blocked ? "#8f261d" : bodyColors[seed % bodyColors.length];
  const statusColor = blocked ? "#d9564c" : busy ? "#48a879" : state.includes("wait") ? "#d7a536" : "#8b8278";
  const figureRef = React.useRef<THREE.Group>(null);
  const leftArmRef = React.useRef<THREE.Group>(null);
  const rightArmRef = React.useRef<THREE.Group>(null);
  const leftLegRef = React.useRef<THREE.Group>(null);
  const rightLegRef = React.useRef<THREE.Group>(null);

  useFrame((frame) => {
    if (!figureRef.current) return;
    const elapsed = frame.clock.elapsedTime;
    const cycle = (elapsed + (seed % 13)) % 16;
    let progress = 0;
    let direction = 1;
    let moving = false;
    if (busy && !blocked) {
      if (cycle >= 2 && cycle < 4) {
        progress = THREE.MathUtils.smoothstep((cycle - 2) / 2, 0, 1);
        moving = true;
      } else if (cycle >= 4 && cycle < 10) {
        progress = 1;
      } else if (cycle >= 10 && cycle < 12) {
        progress = 1 - THREE.MathUtils.smoothstep((cycle - 10) / 2, 0, 1);
        direction = -1;
        moving = true;
      }
    }
    const laneX = ((seed % 5) - 2) * 0.2;
    const laneZ = (((seed >> 3) % 5) - 2) * 0.16;
    const targetX = (-position[0] * 0.55 + laneX) / scale;
    const targetZ = (-position[1] * 0.55 + laneZ) / scale;
    const gait = moving ? Math.sin(elapsed * 9 + seed) * 0.58 : 0;
    figureRef.current.position.set(
      targetX * progress,
      1.02 + Math.abs(Math.sin(elapsed * 9 + seed)) * (moving ? 0.035 : 0.01),
      0.12 + targetZ * progress,
    );
    figureRef.current.rotation.y = moving
      ? Math.atan2(targetX * direction, targetZ * direction)
      : Math.sin(elapsed * 0.35 + seed) * (busy ? 0.05 : 0.02);
    if (leftArmRef.current) leftArmRef.current.rotation.x = gait;
    if (rightArmRef.current) rightArmRef.current.rotation.x = -gait;
    if (leftLegRef.current) leftLegRef.current.rotation.x = -gait;
    if (rightLegRef.current) rightLegRef.current.rotation.x = gait;
  });

  return (
    <group
      position={[position[0], 0, position[1]]}
      scale={scale}
      onPointerOver={(event: ThreeEvent<PointerEvent>) => {
        event.stopPropagation();
        setHovered(true);
        document.body.style.cursor = "pointer";
      }}
      onPointerOut={(event: ThreeEvent<PointerEvent>) => {
        event.stopPropagation();
        setHovered(false);
        document.body.style.cursor = "default";
      }}
      onClick={(event: ThreeEvent<MouseEvent>) => {
        event.stopPropagation();
        onSelect();
      }}
    >
      <mesh position={[0, 0.72, -0.32]} castShadow>
        <boxGeometry args={[1.55, 0.08, 0.68]} />
        <meshStandardMaterial color="#553922" roughness={0.58} />
      </mesh>
      <mesh position={[-0.62, 0.34, -0.5]}>
        <boxGeometry args={[0.09, 0.7, 0.09]} />
        <meshStandardMaterial color="#a88355" metalness={0.7} roughness={0.34} />
      </mesh>
      <mesh position={[0.62, 0.34, -0.5]}>
        <boxGeometry args={[0.09, 0.7, 0.09]} />
        <meshStandardMaterial color="#a88355" metalness={0.7} roughness={0.34} />
      </mesh>
      <mesh position={[0, 1.0, -0.51]} castShadow>
        <boxGeometry args={[0.88, 0.48, 0.05]} />
        <meshStandardMaterial color="#090c0f" emissive={blocked ? "#b53c32" : accent} emissiveIntensity={busy ? 0.72 : 0.28} roughness={0.3} />
      </mesh>
      <mesh position={[0, 0.78, -0.5]}>
        <boxGeometry args={[0.1, 0.14, 0.1]} />
        <meshStandardMaterial color="#a88355" metalness={0.72} roughness={0.32} />
      </mesh>

      <group ref={figureRef} position={[0, 1.02, 0.12]}>
        <mesh position={[0, 0.34, 0]} castShadow>
          <sphereGeometry args={[0.18, 18, 18]} />
          <meshStandardMaterial color={skin} roughness={0.72} />
        </mesh>
        <mesh position={[0, -0.08, 0]} castShadow>
          <capsuleGeometry args={[0.22, 0.44, 6, 12]} />
          <meshStandardMaterial color={body} roughness={0.62} />
        </mesh>
        <group ref={leftArmRef} position={[-0.27, 0.05, 0]}>
          <mesh position={[0, -0.2, 0]} castShadow>
            <capsuleGeometry args={[0.065, 0.3, 5, 8]} />
            <meshStandardMaterial color={body} roughness={0.62} />
          </mesh>
        </group>
        <group ref={rightArmRef} position={[0.27, 0.05, 0]}>
          <mesh position={[0, -0.2, 0]} castShadow>
            <capsuleGeometry args={[0.065, 0.3, 5, 8]} />
            <meshStandardMaterial color={body} roughness={0.62} />
          </mesh>
        </group>
        <group ref={leftLegRef} position={[-0.11, -0.43, 0]}>
          <mesh position={[0, -0.2, 0]} castShadow>
            <capsuleGeometry args={[0.07, 0.3, 5, 8]} />
            <meshStandardMaterial color="#242b32" roughness={0.72} />
          </mesh>
        </group>
        <group ref={rightLegRef} position={[0.11, -0.43, 0]}>
          <mesh position={[0, -0.2, 0]} castShadow>
            <capsuleGeometry args={[0.07, 0.3, 5, 8]} />
            <meshStandardMaterial color="#242b32" roughness={0.72} />
          </mesh>
        </group>
      </group>

      <mesh position={[0, 0.045, 0.43]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[selected ? 0.3 : 0.25, selected ? 0.39 : 0.32, 24]} />
        <meshBasicMaterial color={selected ? "#f4d48d" : statusColor} transparent opacity={0.94} side={THREE.DoubleSide} />
      </mesh>

      {(hovered || selected) && (
        <Html position={[0, 2.1, 0]} center distanceFactor={8} occlude={false} zIndexRange={[30, 0]}>
          <div className={`office-agent-popover ${blocked ? "office-agent-popover--blocked" : ""}`}>
            <div className="office-agent-popover__head">
              <strong>{name}</strong>
              <span>{state.replace(/_/g, " ")}</span>
            </div>
            <div className="office-agent-popover__title">{title}</div>
            <div className="office-agent-popover__work">{currentWork}</div>
          </div>
        </Html>
      )}
    </group>
  );
}

function CommitteeTable({ itemCount }: { itemCount: number }) {
  const markers = Math.min(12, itemCount);
  return (
    <group position={[0, 0, 0]}>
      <mesh position={[0, 0.7, 0]} castShadow>
        <cylinderGeometry args={[1.45, 1.45, 0.12, 32]} />
        <meshStandardMaterial color="#503828" roughness={0.54} />
      </mesh>
      <mesh position={[0, 0.35, 0]}>
        <cylinderGeometry args={[0.16, 0.28, 0.65, 16]} />
        <meshStandardMaterial color="#a88355" metalness={0.7} roughness={0.32} />
      </mesh>
      {Array.from({ length: markers }).map((_, index) => {
        const angle = (index / Math.max(1, markers)) * Math.PI * 2;
        return (
          <mesh key={index} position={[Math.cos(angle) * 1.1, 0.86, Math.sin(angle) * 1.1]}>
            <sphereGeometry args={[0.07, 10, 10]} />
            <meshBasicMaterial color="#d9b85b" />
          </mesh>
        );
      })}
    </group>
  );
}

function LobbyConsole({ activeGraphRuns }: { activeGraphRuns: number }) {
  return (
    <group position={[0, 0, 0]}>
      <mesh position={[0, 0.85, 0]} castShadow>
        <cylinderGeometry args={[1.1, 1.28, 0.18, 8]} />
        <meshStandardMaterial color="#3e3024" metalness={0.28} roughness={0.48} />
      </mesh>
      <mesh position={[0, 1.18, 0]}>
        <sphereGeometry args={[0.55, 24, 24]} />
        <meshStandardMaterial color="#0f766e" emissive="#0f766e" emissiveIntensity={activeGraphRuns ? 0.85 : 0.28} transparent opacity={0.55} wireframe />
      </mesh>
    </group>
  );
}

type FlowConnection = {
  from: string;
  to: string;
  count: number;
  kind: "message" | "graph";
};

function buildConnections(data: ReturnType<typeof useOfficeSnapshot>["data"], agents: LiveRow[]): FlowConnection[] {
  if (!data) return [];
  const agentRooms = new Map(agents.map((agent) => [text(agent, "agent_name"), agentRoomKey(agent)]));
  const grouped = new Map<string, FlowConnection>();
  const add = (from: string, to: string, kind: FlowConnection["kind"]) => {
    if (!from || !to || from === to || !roomByKey(from) || !roomByKey(to)) return;
    const key = `${kind}:${from}:${to}`;
    const current = grouped.get(key);
    grouped.set(key, current ? { ...current, count: current.count + 1 } : { from, to, count: 1, kind });
  };

  for (const message of data.agent_messages ?? []) {
    add(agentRooms.get(text(message, "from_agent")) ?? "", agentRooms.get(text(message, "to_agent")) ?? "", "message");
  }
  for (const node of data.graph_node_runs ?? []) {
    const ownerRoom = agentRooms.get(text(node, "owner_agent")) ?? "";
    add("runtime", ownerRoom, "graph");
  }
  return [...grouped.values()].sort((left, right) => right.count - left.count).slice(0, 22);
}

function DataFlows({ connections }: { connections: FlowConnection[] }) {
  return (
    <>
      {connections.map((connection, index) => (
        <FlowPath key={`${connection.kind}-${connection.from}-${connection.to}`} connection={connection} delay={index * 0.31} />
      ))}
    </>
  );
}

function FlowPath({ connection, delay }: { connection: FlowConnection; delay: number }) {
  const from = roomByKey(connection.from);
  const to = roomByKey(connection.to);
  const dotRef = React.useRef<THREE.Mesh>(null);
  if (!from || !to) return null;
  const fromPoint = new THREE.Vector3(from.center[0], floorY(from.floor) + 2.1, from.center[1]);
  const toPoint = new THREE.Vector3(to.center[0], floorY(to.floor) + 2.1, to.center[1]);
  const middle = new THREE.Vector3(
    (fromPoint.x + toPoint.x) / 2,
    Math.max(fromPoint.y, toPoint.y) + 1.4,
    (fromPoint.z + toPoint.z) / 2,
  );
  const curve = new THREE.QuadraticBezierCurve3(fromPoint, middle, toPoint);
  const points = curve.getPoints(30);
  const color = connection.kind === "graph" ? "#a986c8" : "#f2cf86";

  useFrame((state) => {
    if (!dotRef.current) return;
    const speed = 0.12 + Math.min(0.1, connection.count * 0.012);
    const progress = ((state.clock.elapsedTime + delay) * speed) % 1;
    dotRef.current.position.copy(curve.getPoint(progress));
    const material = dotRef.current.material as THREE.MeshBasicMaterial;
    material.opacity = Math.max(0.22, Math.sin(progress * Math.PI));
  });

  return (
    <>
      <Line points={points} color={color} lineWidth={0.7} transparent opacity={0.2} />
      <mesh ref={dotRef}>
        <sphereGeometry args={[0.07 + Math.min(0.05, connection.count * 0.005), 10, 10]} />
        <meshBasicMaterial color={color} transparent opacity={0.9} />
      </mesh>
    </>
  );
}

function CameraController({ focusTarget }: { focusTarget: string | null }) {
  const { camera } = useThree();
  const targetPosition = React.useRef(new THREE.Vector3(0, 17, 29));
  const targetLook = React.useRef(new THREE.Vector3(0, 1, 0));

  React.useEffect(() => {
    const room = focusTarget ? roomByKey(focusTarget) : undefined;
    if (room) {
      const roomY = floorY(room.floor);
      targetPosition.current.set(
        room.center[0] + room.size[0] * 0.55,
        roomY + 4.8,
        room.center[1] + room.size[1] + 4.8,
      );
      targetLook.current.set(room.center[0], roomY + 0.9, room.center[1]);
    } else {
      targetPosition.current.set(0, 17, 29);
      targetLook.current.set(0, 1, 0);
    }
  }, [focusTarget]);

  useFrame(() => {
    camera.position.lerp(targetPosition.current, 0.055);
    camera.lookAt(targetLook.current);
  });
  return null;
}

export interface LiveOfficeProps {
  height?: number | string;
}

export function LiveOffice({ height = "100%" }: LiveOfficeProps) {
  const { data } = useOfficeSnapshot();
  const navigate = useNavigate();
  const cameraTarget = useUIStore((state) => state.cameraTarget);
  const focusRoom = useUIStore((state) => state.focusRoom);
  const setAssistantScope = useUIStore((state) => state.setAssistantScope);
  const openEvidence = useUIStore((state) => state.openEvidence);
  const [hoveredRoom, setHoveredRoom] = React.useState<string | null>(null);
  const [selectedAgent, setSelectedAgent] = React.useState<LiveRow | null>(null);
  const [errored, setErrored] = React.useState(false);
  const [webglOk, setWebglOk] = React.useState<boolean | null>(null);

  React.useEffect(() => {
    try {
      const canvas = document.createElement("canvas");
      setWebglOk(Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl")));
    } catch {
      setWebglOk(false);
    }
  }, []);

  const agents = React.useMemo(() => mergeAgents(data), [data]);
  const roomAgents = React.useMemo(() => {
    const map = new Map<string, LiveRow[]>();
    for (const room of ROOMS) map.set(room.key, []);
    for (const agent of agents) {
      const key = agentRoomKey(agent);
      const bucket = map.get(key);
      if (bucket) bucket.push(agent);
    }
    return map;
  }, [agents]);
  const roomStats = React.useMemo(() => new Map(
    (data?.live_office_rooms ?? []).map((row) => [normalizeDepartment(text(row, "room_key")), row]),
  ), [data?.live_office_rooms]);
  const connections = React.useMemo(() => buildConnections(data, agents), [data, agents]);
  const riskRooms = React.useMemo(() => {
    const rooms = new Set<string>();
    for (const [key, stats] of roomStats) {
      const state = text(stats, "room_state").toLowerCase();
      if (state.includes("risk") || state.includes("block") || num(stats, "blocked_task_count") > 0) rooms.add(key);
    }
    if ((data?.risk_events?.length ?? 0) > 0) rooms.add("risk");
    return rooms;
  }, [data?.risk_events, roomStats]);
  const activeGraphRuns = data?.graph_runs?.length ?? 0;
  const workingAgents = agents.filter(isBusy).length;
  const reducedMotion = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  function selectAgent(agent: LiveRow) {
    setSelectedAgent(agent);
    focusRoom(agentRoomKey(agent));
  }

  function talkToAgent(agent: LiveRow) {
    const name = text(agent, "agent_name");
    setAssistantScope({ agentKey: name, agentName: name });
  }

  function delegateToAgent(agent: LiveRow) {
    const name = text(agent, "agent_name");
    setAssistantScope("charlie");
    window.dispatchEvent(new CustomEvent("aios:assistant-prefill", {
      detail: `Delegate a task to ${name}: `,
    }));
  }

  function inspectAgentTask(agent: LiveRow) {
    const taskId = num(agent, "current_task_id");
    if (!taskId) return;
    openEvidence({
      kind: "task",
      key: String(taskId),
      title: text(agent, "current_task_title", `Task ${taskId}`),
      subtitle: `${text(agent, "agent_name")} · current assignment`,
    });
  }

  if (webglOk === false || reducedMotion || errored) {
    return (
      <OfficeFallback
        height={height}
        agents={agents}
        roomAgents={roomAgents}
        selectedRoom={cameraTarget.roomKey}
        selectedAgent={selectedAgent}
        onFocusRoom={focusRoom}
        onSelectAgent={selectAgent}
        onTalk={talkToAgent}
        onDelegate={delegateToAgent}
        onInspectTask={inspectAgentTask}
        onNavigate={(path) => navigate(path)}
      />
    );
  }

  return (
    <>
      <style>{LiveOfficeCss}</style>
      <div className="office-canvas-wrap" style={{ height }}>
        <Canvas
          shadows
          dpr={[1, 1.65]}
          camera={{ position: [0, 17, 29], fov: 43 }}
          gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.12 }}
          onError={() => setErrored(true)}
        >
          <React.Suspense fallback={null}>
            <AdaptiveDpr pixelated />
            <ambientLight intensity={0.7} color="#fff2dc" />
            <hemisphereLight args={["#fff4e0", "#332a23", 0.65]} />
            <directionalLight
              position={[14, 23, 12]}
              intensity={1.55}
              color="#ffe8c4"
              castShadow
              shadow-mapSize={[2048, 2048]}
              shadow-camera-left={-34}
              shadow-camera-right={34}
              shadow-camera-top={28}
              shadow-camera-bottom={-28}
              shadow-camera-near={0.5}
              shadow-camera-far={70}
              shadow-bias={-0.0004}
            />
            <pointLight position={[-13, 6, -8]} intensity={26} color="#ffd9a0" distance={28} decay={2} />
            <pointLight position={[13, 6, 8]} intensity={22} color="#ffd9a0" distance={28} decay={2} />
            <pointLight position={[0, 10, 0]} intensity={18} color="#fff4e0" distance={34} decay={2} />

            <Floor floor={0} />
            <Floor floor={1} />
            <Floor floor={-1} />

            <mesh position={[20.5, 2.2, 0]}>
              <boxGeometry args={[0.45, 4.6, 6]} />
              <meshStandardMaterial color="#82603f" roughness={0.72} />
            </mesh>

            {ROOMS.map((room) => (
              <Room
                key={room.key}
                room={room}
                agents={roomAgents.get(room.key) ?? []}
                stats={roomStats.get(room.key)}
                hasRisk={riskRooms.has(room.key)}
                isFocused={cameraTarget.roomKey === room.key}
                isHovered={hoveredRoom === room.key}
                committeeItems={data?.committee_room_items?.length ?? 0}
                activeGraphRuns={activeGraphRuns}
                selectedAgentName={text(selectedAgent, "agent_name")}
                onHover={(hovered) => setHoveredRoom(hovered ? room.key : null)}
                onClick={() => {
                  setSelectedAgent(null);
                  focusRoom(room.key);
                }}
                onSelectAgent={selectAgent}
              />
            ))}

            <DataFlows connections={connections} />
            <CameraController focusTarget={cameraTarget.roomKey} />
            <OrbitControls
              enablePan={false}
              minDistance={7}
              maxDistance={42}
              minPolarAngle={0.12}
              maxPolarAngle={Math.PI / 2.04}
              target={[0, 1, 0]}
              makeDefault
            />
          </React.Suspense>
        </Canvas>

        <OfficeHud
          focusedRoom={cameraTarget.roomKey}
          selectedAgent={selectedAgent}
          roomAgents={cameraTarget.roomKey ? roomAgents.get(cameraTarget.roomKey) ?? [] : []}
          workingAgents={workingAgents}
          totalAgents={agents.length}
          activeGraphRuns={activeGraphRuns}
          generatedAt={data?.generated_at ?? ""}
          activity={data?.agent_messages ?? []}
          onBack={() => {
            setSelectedAgent(null);
            focusRoom(null);
          }}
          onClearAgent={() => setSelectedAgent(null)}
          onTalk={talkToAgent}
          onDelegate={delegateToAgent}
          onInspectTask={inspectAgentTask}
          onNavigate={(path) => navigate(path)}
        />
      </div>
    </>
  );
}

function Floor({ floor }: { floor: number }) {
  const y = floorY(floor);
  const color = floor === 0 ? "#a77b52" : floor === 1 ? "#b28c66" : "#332d28";
  return (
    <mesh position={[0, y, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
      <planeGeometry args={[52, 34]} />
      <meshStandardMaterial color={color} roughness={floor === -1 ? 0.95 : 0.67} metalness={0.02} />
    </mesh>
  );
}

function OfficeHud({
  focusedRoom,
  selectedAgent,
  roomAgents,
  workingAgents,
  totalAgents,
  activeGraphRuns,
  generatedAt,
  activity,
  onBack,
  onClearAgent,
  onTalk,
  onDelegate,
  onInspectTask,
  onNavigate,
}: {
  focusedRoom: string | null;
  selectedAgent: LiveRow | null;
  roomAgents: LiveRow[];
  workingAgents: number;
  totalAgents: number;
  activeGraphRuns: number;
  generatedAt: string;
  activity: LiveRow[];
  onBack: () => void;
  onClearAgent: () => void;
  onTalk: (agent: LiveRow) => void;
  onDelegate: (agent: LiveRow) => void;
  onInspectTask: (agent: LiveRow) => void;
  onNavigate: (path: string) => void;
}) {
  const delegateTask = useDelegateAgentTask();
  const pushToast = useUIStore((state) => state.pushToast);
  const [showDelegate, setShowDelegate] = React.useState(false);
  const [delegateObjective, setDelegateObjective] = React.useState("");
  const room = focusedRoom ? roomByKey(focusedRoom) : null;
  React.useEffect(() => {
    setShowDelegate(false);
    setDelegateObjective("");
  }, [selectedAgent]);

  function submitDelegation() {
    if (!selectedAgent || !delegateObjective.trim()) return;
    const agentName = text(selectedAgent, "agent_name");
    delegateTask.mutate({
      to_agent: agentName,
      objective: delegateObjective.trim(),
      priority: "high",
      workspace: agentRoomKey(selectedAgent),
      actor: "Devarsh",
    }, {
      onSuccess: (result) => {
        pushToast({
          title: `Task queued to ${agentName}`,
          message: `Task #${num(result, "task_id")} is durable and visible in the office.`,
          tone: "ok",
          duration: 5000,
        });
        setShowDelegate(false);
        setDelegateObjective("");
      },
      onError: (error) => pushToast({ title: "Delegation failed", message: error.message, tone: "risk", duration: 6000 }),
    });
  }
  return (
    <div className="office-hud">
      <div className="office-hud__top">
        <div>
          <div className="office-hud__title">AI Investment Firm · Live</div>
          <div className="office-hud__hint">{totalAgents} employees · {workingAgents} working · {activeGraphRuns} graph runs · {formatRelative(generatedAt)}</div>
          {activity.length > 0 && (
            <div className="office-hud__activity" aria-label="Latest inter-agent handoffs">
              {activity.slice(0, 3).map((item, index) => (
                <div key={String(num(item, "id", index))}>
                  <span>{text(item, "from_agent", "Agent")} → {text(item, "to_agent", "Agent")}</span>
                  <b>{text(item, "subject", "Work handoff")}</b>
                  <time>{formatRelative(text(item, "created_at"))}</time>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="office-hud__legend">
          <span><i className="is-working" />Working</span>
          <span><i className="is-waiting" />Waiting</span>
          <span><i className="is-blocked" />Blocked</span>
        </div>
      </div>
      <div className="office-hud__bottom">
        {selectedAgent ? (
          <div className="office-hud__agent-card">
            <div className="office-hud__agent-head">
              <div>
                <strong>{text(selectedAgent, "agent_name")}</strong>
                <span>{text(selectedAgent, "display_title", text(selectedAgent, "role_scope"))}</span>
              </div>
              <span className={`office-hud__state ${isBlocked(selectedAgent) ? "is-blocked" : isBusy(selectedAgent) ? "is-working" : "is-idle"}`}>
                {liveState(selectedAgent).replace(/_/g, " ")}
              </span>
            </div>
            <div className="office-hud__work">
              <b>{text(selectedAgent, "presence_title", "Available for assignment")}</b>
              <span>{text(selectedAgent, "presence_detail", text(selectedAgent, "presence_reason", "No fresh assignment."))}</span>
            </div>
            <div className="office-hud__agent-facts">
              <span>Tasks <b>{num(selectedAgent, "open_task_count")}</b></span>
              <span>Inbox <b>{num(selectedAgent, "open_inbox_count")}</b></span>
              <span>Model <b>{text(selectedAgent, "latest_worker_skill_name", text(selectedAgent, "default_model_route", "route-managed"))}</b></span>
            </div>
            <div className="office-hud__room-actions">
              <button className="office-hud__btn office-hud__btn--primary" onClick={() => onTalk(selectedAgent)}>Talk</button>
              <button className="office-hud__btn" onClick={() => setShowDelegate((open) => !open)}>Delegate task</button>
              {num(selectedAgent, "current_task_id") > 0 && (
                <button className="office-hud__btn" onClick={() => onInspectTask(selectedAgent)}>Inspect task</button>
              )}
              {room?.link && <button className="office-hud__btn" onClick={() => onNavigate(room.link!)}>Open department</button>}
              <button className="office-hud__btn" onClick={onClearAgent}>Close employee</button>
            </div>
            {showDelegate && (
              <div style={{ display: "grid", gap: 8, marginTop: 10 }}>
                <textarea
                  aria-label={`Assignment for ${text(selectedAgent, "agent_name")}`}
                  value={delegateObjective}
                  onChange={(event) => setDelegateObjective(event.target.value)}
                  placeholder="State the exact deliverable, evidence required, deadline or review gate."
                  rows={3}
                  style={{ width: "100%", resize: "vertical", background: "rgba(5,10,12,.88)", color: "#f5f7f6", border: "1px solid rgba(255,255,255,.2)", padding: 10, font: "inherit" }}
                />
                <div className="office-hud__room-actions">
                  <button className="office-hud__btn office-hud__btn--primary" disabled={!delegateObjective.trim() || delegateTask.isPending} onClick={submitDelegation}>
                    {delegateTask.isPending ? "Queuing…" : "Queue assignment"}
                  </button>
                  <button className="office-hud__btn" onClick={() => setShowDelegate(false)}>Cancel</button>
                </div>
              </div>
            )}
          </div>
        ) : room ? (
          <div className="office-hud__room-card">
            <div className="office-hud__room-name">{room.label}</div>
            <div className="office-hud__room-dept">{room.department} · {roomAgents.length} employees · {roomAgents.filter(isBusy).length} working</div>
            <div className="office-hud__room-work">
              {roomAgents.filter(isBusy).slice(0, 3).map((agent) => (
                <span key={text(agent, "agent_name")}><b>{text(agent, "agent_name")}</b>{text(agent, "current_work_title", text(agent, "current_task_title", "Working"))}</span>
              ))}
            </div>
            <div className="office-hud__room-actions">
              {room.link && <button className="office-hud__btn office-hud__btn--primary" onClick={() => onNavigate(room.link!)}>Open department</button>}
              <button className="office-hud__btn" onClick={onBack}>Firm overview</button>
            </div>
          </div>
        ) : (
          <div className="office-hud__lobby-hint">All departments · live assignments · governed handoffs</div>
        )}
      </div>
    </div>
  );
}

function OfficeFallback({
  height,
  agents,
  roomAgents,
  selectedRoom,
  selectedAgent,
  onFocusRoom,
  onSelectAgent,
  onTalk,
  onDelegate,
  onInspectTask,
  onNavigate,
}: {
  height: number | string;
  agents: LiveRow[];
  roomAgents: Map<string, LiveRow[]>;
  selectedRoom: string | null;
  selectedAgent: LiveRow | null;
  onFocusRoom: (key: string | null) => void;
  onSelectAgent: (agent: LiveRow) => void;
  onTalk: (agent: LiveRow) => void;
  onDelegate: (agent: LiveRow) => void;
  onInspectTask: (agent: LiveRow) => void;
  onNavigate: (path: string) => void;
}) {
  const selectedRoomDefinition = selectedAgent ? roomByKey(agentRoomKey(selectedAgent)) : undefined;
  return (
    <div className="office-fallback" style={{ height }}>
      <style>{LiveOfficeCss}</style>
      <div className="office-fallback__inner">
        <div className="office-fallback__title">AI Investment Firm · Live Floor Plan</div>
        <div className="office-fallback__sub">{agents.length} employees across {ROOMS.filter((room) => room.key !== "lobby" && room.key !== "committee").length} departments</div>
        {selectedAgent && (
          <section className="office-fallback__selected">
            <div>
              <strong>{text(selectedAgent, "agent_name")}</strong>
              <span>{text(selectedAgent, "display_title", text(selectedAgent, "role_scope"))}</span>
              <b>{text(selectedAgent, "current_work_title", text(selectedAgent, "current_task_title", "No active assignment"))}</b>
              <small>{text(selectedAgent, "current_work_detail", text(selectedAgent, "latest_worker_summary", "No worker output recorded."))}</small>
            </div>
            <div className="office-hud__room-actions">
              <button className="office-hud__btn office-hud__btn--primary" onClick={() => onTalk(selectedAgent)}>Talk</button>
              <button className="office-hud__btn" onClick={() => onDelegate(selectedAgent)}>Delegate task</button>
              {num(selectedAgent, "current_task_id") > 0 && <button className="office-hud__btn" onClick={() => onInspectTask(selectedAgent)}>Inspect task</button>}
              {selectedRoomDefinition?.link && <button className="office-hud__btn" onClick={() => onNavigate(selectedRoomDefinition.link!)}>Open department</button>}
            </div>
          </section>
        )}
        <div className="office-fallback__grid">
          {ROOMS.map((room) => {
            const occupants = roomAgents.get(room.key) ?? [];
            return (
              <section key={room.key} className={`office-fallback__room ${selectedRoom === room.key ? "office-fallback__room--active" : ""}`}>
                <button className="office-fallback__room-button" onClick={() => onFocusRoom(room.key)}>
                  <span className="office-fallback__room-name">{room.label}</span>
                  <span className="office-fallback__room-dept">{occupants.length} employees · {occupants.filter(isBusy).length} working</span>
                  <span className="office-fallback__room-floor">{room.floor === 1 ? "Mezzanine" : room.floor === -1 ? "Infrastructure" : "Dealing floor"}</span>
                </button>
                {selectedRoom === room.key && occupants.slice(0, 12).map((agent) => (
                  <button key={text(agent, "agent_name")} className="office-fallback__agent" onClick={() => onSelectAgent(agent)}>
                    <span>{text(agent, "agent_name")}</span>
                    <small>{text(agent, "current_work_title", liveState(agent))}</small>
                  </button>
                ))}
              </section>
            );
          })}
        </div>
      </div>
    </div>
  );
}
