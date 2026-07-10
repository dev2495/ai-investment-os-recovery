import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { ArrowLeft, Building2, CircleAlert, RefreshCw, Send, ShieldCheck, UsersRound } from "lucide-react";
import type { FormEvent } from "react";
import { useMemo, useRef, useState } from "react";
import type { Group } from "three";
import type { LiveRow, LiveSnapshot } from "../api/live";
import type { WorkspaceId } from "../types";
import { buildOfficeModel, type OfficeAgent, type OfficeRoom } from "./office-model";
import "./live-office.css";

interface LiveOfficeProps {
  liveStatus: "loading" | "online" | "offline";
  onExit: () => void;
  onRefresh: () => void;
  onSelectWorkspace: (workspace: WorkspaceId) => void;
  onSendMessage: (input: { body: string; subject: string; toAgent: string }) => Promise<void>;
  snapshot: LiveSnapshot | null;
}

interface RoomPlacement {
  room: OfficeRoom;
  x: number;
  z: number;
}

const roomTone = ["#2b5a69", "#345843", "#514b73", "#6d4e37", "#33516e", "#4f633d"];

function activityTone(state: OfficeAgent["state"]): string {
  if (state === "blocked") return "#ee736c";
  if (state === "review") return "#e2a54a";
  if (state === "waiting") return "#7590a0";
  if (state === "active") return "#62c6b3";
  return "#71808c";
}

function relativeTime(value: string): string {
  if (!value) return "No timestamp";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const minutes = Math.max(0, Math.round((Date.now() - date.getTime()) / 60000));
  if (minutes < 2) return "Just updated";
  if (minutes < 60) return `${minutes}m ago`;
  return `${Math.round(minutes / 60)}h ago`;
}

function rowText(row: LiveRow, ...keys: string[]): string {
  for (const key of keys) {
    const value = row[key];
    if (value !== null && value !== undefined && String(value).trim()) return String(value).trim();
  }
  return "";
}

function OfficeScene({
  agents,
  onHover,
  onSelect,
  rooms,
  selectedAgentId
}: {
  agents: OfficeAgent[];
  onHover: (agent: OfficeAgent | null) => void;
  onSelect: (agent: OfficeAgent) => void;
  rooms: RoomPlacement[];
  selectedAgentId: string;
}) {
  const placements = new Map(rooms.map((placement) => [placement.room.id, placement]));
  const perRoom = new Map<string, number>();

  return (
    <>
      <color attach="background" args={["#0a1015"]} />
      <fog attach="fog" args={["#0a1015", 13, 34]} />
      <ambientLight intensity={0.65} />
      <directionalLight intensity={1.25} position={[4, 10, 4]} />
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[24, 18]} />
        <meshStandardMaterial color="#101b21" roughness={0.92} metalness={0.08} />
      </mesh>
      {rooms.map((placement, index) => (
        <OfficeRoomMesh key={placement.room.id} placement={placement} tone={roomTone[index % roomTone.length]} />
      ))}
      {agents.map((agent, index) => {
        const room = placements.get(agent.roomId);
        if (!room) return null;
        const stationIndex = perRoom.get(agent.roomId) ?? 0;
        perRoom.set(agent.roomId, stationIndex + 1);
        const column = stationIndex % 3;
        const row = Math.floor(stationIndex / 3);
        return (
          <AgentStation
            agent={agent}
            index={index}
            key={agent.id}
            onHover={onHover}
            onSelect={onSelect}
            position={[room.x - 1.1 + column * 1.1, 0.12, room.z - 0.55 + row * 0.88]}
            selected={selectedAgentId === agent.id}
          />
        );
      })}
      <OrbitControls enableDamping enablePan={false} maxDistance={25} maxPolarAngle={Math.PI / 2.2} minDistance={13} minPolarAngle={0.55} target={[0, 0, 0]} />
    </>
  );
}

function OfficeRoomMesh({ placement, tone }: { placement: RoomPlacement; tone: string }) {
  const { room, x, z } = placement;
  return (
    <group position={[x, 0, z]}>
      <mesh position={[0, 0.04, 0]}>
        <boxGeometry args={[3.65, 0.12, 2.85]} />
        <meshStandardMaterial color="#17252c" roughness={0.84} metalness={0.1} />
      </mesh>
      <mesh position={[0, 0.1, -1.31]}>
        <boxGeometry args={[3.62, 0.15, 0.08]} />
        <meshStandardMaterial color={tone} emissive={tone} emissiveIntensity={0.22} roughness={0.7} />
      </mesh>
      <mesh position={[-1.76, 0.56, 0]}>
        <boxGeometry args={[0.09, 1.15, 2.72]} />
        <meshStandardMaterial color="#15242c" roughness={0.82} />
      </mesh>
      <mesh position={[1.76, 0.56, 0]}>
        <boxGeometry args={[0.09, 1.15, 2.72]} />
        <meshStandardMaterial color="#15242c" roughness={0.82} />
      </mesh>
      <mesh position={[0, 0.33, 0.94]}>
        <boxGeometry args={[2.8, 0.22, 0.34]} />
        <meshStandardMaterial color="#233940" roughness={0.6} metalness={0.25} />
      </mesh>
      <mesh position={[0, 0.61, 0.86]}>
        <boxGeometry args={[1.2, 0.42, 0.05]} />
        <meshStandardMaterial color="#071b25" emissive={tone} emissiveIntensity={0.18} roughness={0.4} metalness={0.35} />
      </mesh>
      <mesh position={[0, 0.16, -0.9]}>
        <boxGeometry args={[2.55, 0.02, 0.08]} />
        <meshStandardMaterial color={tone} emissive={tone} emissiveIntensity={0.5} />
      </mesh>
      <mesh position={[0, 0.24, -0.9]}>
        <boxGeometry args={[0.1, 0.26, 0.1]} />
        <meshStandardMaterial color={tone} emissive={tone} emissiveIntensity={0.42} />
      </mesh>
      <mesh position={[-1.42, 0.2, 1.02]}>
        <sphereGeometry args={[0.075, 16, 16]} />
        <meshStandardMaterial color={room.activeCount > 0 ? "#63c8b1" : "#6c7c86"} emissive={room.activeCount > 0 ? "#63c8b1" : "#6c7c86"} emissiveIntensity={0.6} />
      </mesh>
    </group>
  );
}

function AgentStation({
  agent,
  index,
  onHover,
  onSelect,
  position,
  selected
}: {
  agent: OfficeAgent;
  index: number;
  onHover: (agent: OfficeAgent | null) => void;
  onSelect: (agent: OfficeAgent) => void;
  position: [number, number, number];
  selected: boolean;
}) {
  const group = useRef<Group>(null);
  const tone = activityTone(agent.state);

  useFrame(({ clock }) => {
    if (!group.current || agent.state !== "active") return;
    group.current.position.y = position[1] + Math.sin(clock.elapsedTime * 1.6 + index) * 0.03;
  });

  return (
    <group
      onClick={(event) => {
        event.stopPropagation();
        onSelect(agent);
      }}
      onPointerOut={() => onHover(null)}
      onPointerOver={(event) => {
        event.stopPropagation();
        onHover(agent);
      }}
      position={position}
      ref={group}
    >
      <mesh position={[0, 0.1, 0]}>
        <cylinderGeometry args={[0.25, 0.32, 0.16, 24]} />
        <meshStandardMaterial color={selected ? "#d9f7ef" : "#31505a"} emissive={selected ? "#62c6b3" : "#142e36"} emissiveIntensity={selected ? 0.9 : 0.32} />
      </mesh>
      <mesh position={[0, 0.47, 0]}>
        <capsuleGeometry args={[0.16, 0.38, 6, 12]} />
        <meshStandardMaterial color="#b3c3c9" roughness={0.48} metalness={0.16} />
      </mesh>
      <mesh position={[0, 0.86, 0]}>
        <sphereGeometry args={[0.15, 18, 18]} />
        <meshStandardMaterial color="#e2c7ab" roughness={0.62} />
      </mesh>
      <mesh position={[0, 0.12, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.36, 0.022, 12, 32]} />
        <meshStandardMaterial color={tone} emissive={tone} emissiveIntensity={0.85} />
      </mesh>
    </group>
  );
}

export default function LiveOffice({ liveStatus, onExit, onRefresh, onSelectWorkspace, onSendMessage, snapshot }: LiveOfficeProps) {
  const model = useMemo(() => buildOfficeModel(snapshot), [snapshot]);
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [hoveredAgent, setHoveredAgent] = useState<OfficeAgent | null>(null);
  const [handoffDraft, setHandoffDraft] = useState({ body: "", subject: "" });
  const [handoffBusy, setHandoffBusy] = useState(false);
  const [handoffError, setHandoffError] = useState("");
  const rooms = useMemo<RoomPlacement[]>(() => model.rooms.map((room, index) => ({
    room,
    x: (index % 3 - 1) * 4.25,
    z: (Math.floor(index / 3) - 0.5) * 3.55
  })), [model.rooms]);
  const selectedAgent = model.agents.find((agent) => agent.id === selectedAgentId) ?? hoveredAgent ?? model.agents[0] ?? null;
  const activeAgents = model.agents.filter((agent) => agent.state !== "idle").length;
  const blockedAgents = model.agents.filter((agent) => agent.state === "blocked").length;
  const selectedMessages = useMemo(() => {
    if (!selectedAgent) return [];
    return (snapshot?.agent_messages ?? []).filter((message) => {
      const from = rowText(message, "from_agent", "sender_agent");
      const to = rowText(message, "to_agent", "recipient_agent");
      return from === selectedAgent.name || to === selectedAgent.name;
    }).slice(0, 4);
  }, [selectedAgent, snapshot]);

  const submitHandoff = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedAgent || handoffBusy || !handoffDraft.subject.trim() || !handoffDraft.body.trim()) return;
    setHandoffBusy(true);
    setHandoffError("");
    try {
      await onSendMessage({
        body: handoffDraft.body.trim(),
        subject: handoffDraft.subject.trim(),
        toAgent: selectedAgent.name
      });
      setHandoffDraft({ body: "", subject: "" });
    } catch (error) {
      setHandoffError(error instanceof Error ? error.message : "Unable to send the agent handoff");
    } finally {
      setHandoffBusy(false);
    }
  };

  return (
    <main className="live-office-shell">
      <header className="office-header">
        <div className="office-brand">
          <span className="office-brand-mark"><Building2 size={18} aria-hidden="true" /></span>
          <div>
            <p>AI Investment Office</p>
            <span>Charlie Munger / Jarvis operating floor</span>
          </div>
        </div>
        <div className="office-header-actions">
          <span className={`office-connection office-${liveStatus}`}>{liveStatus === "online" ? "Live warehouse" : liveStatus === "loading" ? "Connecting" : "Warehouse offline"}</span>
          <button className="office-icon-button" onClick={onRefresh} title="Refresh office activity" type="button"><RefreshCw size={17} aria-hidden="true" /></button>
          <button className="office-return-button" onClick={onExit} type="button"><ArrowLeft size={16} aria-hidden="true" /> Command Center</button>
        </div>
      </header>

      <section className="office-main-grid" aria-label="Live AI Office">
        <aside className="office-directory">
          <div className="office-section-title"><UsersRound size={16} aria-hidden="true" /><span>Departments</span></div>
          <div className="office-room-list">
            {model.rooms.length ? model.rooms.map((room) => (
              <button className="office-room-row" key={room.id} onClick={() => onSelectWorkspace(room.label.toLowerCase().includes("quant") ? "quant" : room.label.toLowerCase().includes("risk") ? "risk" : room.label.toLowerCase().includes("trad") ? "trading" : room.label.toLowerCase().includes("research") ? "research" : "command")} type="button">
                <span className={`office-status-dot status-${room.status.toLowerCase().replace(/[^a-z]+/g, "-")}`} />
                <span><strong>{room.label}</strong><small>{room.activeCount}/{room.agentCount || 0} active</small></span>
              </button>
            )) : <div className="office-empty">No live office room records have been published.</div>}
          </div>
          <div className="office-stat-stack">
            <div><span>Active specialists</span><strong>{activeAgents}</strong></div>
            <div><span>Review queue</span><strong>{model.committeeItems.length}</strong></div>
            <div className={blockedAgents ? "office-stat-risk" : ""}><span>Blocked work</span><strong>{blockedAgents}</strong></div>
          </div>
        </aside>

        <section className="office-stage" aria-label="Interactive AI office model">
          {rooms.length && model.agents.length ? (
            <Canvas camera={{ fov: 44, position: [11, 13, 15] }} dpr={[1, 2]} gl={{ antialias: true, preserveDrawingBuffer: true }}>
              <OfficeScene agents={model.agents} onHover={setHoveredAgent} onSelect={(agent) => setSelectedAgentId(agent.id)} rooms={rooms} selectedAgentId={selectedAgent?.id ?? ""} />
            </Canvas>
          ) : (
            <div className="office-stage-empty">
              <Building2 size={30} aria-hidden="true" />
              <strong>Office view is waiting for live room and activity records.</strong>
              <span>The Command Center remains available while the agent runtime publishes activity.</span>
            </div>
          )}
          <div className="office-stage-caption">
            <span>Live office</span>
            {hoveredAgent ? <strong>{hoveredAgent.name} / {hoveredAgent.task}</strong> : <strong>{model.agents.length} active records</strong>}
          </div>
        </section>

        <aside className="office-inspector">
          <div className="office-section-title"><ShieldCheck size={16} aria-hidden="true" /><span>Agent Inspector</span></div>
          {selectedAgent ? (
            <>
              <label className="office-agent-picker">
                <span>Focus employee</span>
                <select onChange={(event) => setSelectedAgentId(event.target.value)} value={selectedAgent.id}>
                  {model.agents.map((agent) => <option key={agent.id} value={agent.id}>{agent.name}</option>)}
                </select>
              </label>
              <article className="office-agent-profile">
                <div className={`office-agent-avatar state-${selectedAgent.state}`}>{selectedAgent.name.slice(0, 1)}</div>
                <div><h1>{selectedAgent.name}</h1><p>{selectedAgent.role}</p></div>
                <span className={`office-state state-${selectedAgent.state}`}>{selectedAgent.state}</span>
              </article>
              <article className="office-task-card">
                <span>Current work</span>
                <strong>{selectedAgent.task}</strong>
                <p>{selectedAgent.roomLabel} {selectedAgent.model ? ` / ${selectedAgent.model}` : ""}</p>
                <time>{relativeTime(selectedAgent.updatedAt)}</time>
              </article>
              <div className="office-message-list">
                <div className="office-section-title"><CircleAlert size={15} aria-hidden="true" /><span>Recent messages</span></div>
                {selectedMessages.length ? selectedMessages.map((message) => (
                  <article className="office-message-row" key={rowText(message, "id", "message_key")}>
                    <strong>{rowText(message, "subject", "title", "message_type") || "Agent message"}</strong>
                    <p>{rowText(message, "body", "summary", "message") || "No message body recorded."}</p>
                  </article>
                )) : <div className="office-empty">No mailbox traffic for this employee in the current snapshot.</div>}
              </div>
              <form className="office-handoff-form" onSubmit={submitHandoff}>
                <span>Internal handoff</span>
                <input aria-label="Handoff subject" onChange={(event) => setHandoffDraft((draft) => ({ ...draft, subject: event.target.value }))} placeholder="Subject" value={handoffDraft.subject} />
                <textarea aria-label="Handoff message" onChange={(event) => setHandoffDraft((draft) => ({ ...draft, body: event.target.value }))} placeholder="Assignment, question, or review request" rows={3} value={handoffDraft.body} />
                {handoffError ? <p className="office-handoff-error">{handoffError}</p> : null}
                <button disabled={handoffBusy || !handoffDraft.subject.trim() || !handoffDraft.body.trim()} type="submit"><Send size={14} aria-hidden="true" />{handoffBusy ? "Sending" : `Send to ${selectedAgent.name}`}</button>
              </form>
            </>
          ) : <div className="office-empty">Select an agent when the runtime publishes activity.</div>}
        </aside>
      </section>

      <section className="office-committee-strip" aria-label="Committee room">
        <div className="office-committee-heading"><span>Committee Room</span><strong>{model.committeeItems.length} open matters</strong></div>
        <div className="office-committee-list">
          {model.committeeItems.length ? model.committeeItems.map((item) => (
            <article className="office-committee-item" key={item.id}>
              <span className={`office-status-dot status-${item.status.toLowerCase().replace(/[^a-z]+/g, "-")}`} />
              <div><strong>{item.title}</strong><p>{item.owner} / {item.nextAction}</p></div>
              <small>{item.status}</small>
            </article>
          )) : <div className="office-empty">No live committee items are awaiting review.</div>}
        </div>
      </section>
    </main>
  );
}
