/**
 * 3D Live Office — React Three Fiber scene
 *
 * A warm, physical investment firm you can walk into. Two floors (ground +
 * mezzanine) plus a visible basement, glass-walled rooms, oak floors, warm
 * daylight, agents at desks with live status rings, data flowing between
 * rooms, and a camera that flies to any room you click.
 *
 * Hover a room → tooltip. Click a room → camera flies in + HUD shows the
 * room's live queue. Click an agent → opens a scoped chat in Charlie's rail.
 * Rooms with risk/breaches glow red and pulse.
 */

import React from "react";
import { Canvas, useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import {
  OrbitControls, Environment, ContactShadows, Html, Float, AdaptiveDpr, AdaptiveEvents,
  PerspectiveCamera, RoundedBox, Edges, Text, AccumulativeShadows, SoftShadows,
} from "@react-three/drei";
import { EffectComposer, Bloom, Vignette, SMAA, BrightnessContrast } from "@react-three/postprocessing";
import * as THREE from "three";
import { ROOMS, floorY, roomByKey, type RoomDef } from "./officeLayout";
import { useOfficeSnapshot } from "../data/queries";
import { useUIStore } from "../store";
import { text } from "../data/liveRow";
import type { LiveRow } from "../data/liveRow";
import { LiveOfficeCss } from "./LiveOffice.css";

/* ============================================================
 * MATERIALS (reused across the scene)
 * ============================================================ */
function useMaterials() {
  return React.useMemo(() => {
    const oakFloor = new THREE.MeshStandardMaterial({
      color: "#b08456",
      roughness: 0.55,
      metalness: 0.0,
    });
    const concrete = new THREE.MeshStandardMaterial({
      color: "#d4cfc4",
      roughness: 0.92,
      metalness: 0.0,
    });
    const glass = new THREE.MeshPhysicalMaterial({
      color: "#e8e4dc",
      roughness: 0.05,
      metalness: 0.0,
      transmission: 0.92,
      thickness: 0.4,
      transparent: true,
      opacity: 0.35,
      ior: 1.45,
    });
    const brass = new THREE.MeshStandardMaterial({
      color: "#b08d57",
      roughness: 0.3,
      metalness: 0.9,
    });
    const desk = new THREE.MeshStandardMaterial({
      color: "#6b4a2a",
      roughness: 0.6,
      metalness: 0.05,
    });
    return { oakFloor, concrete, glass, brass, desk };
  }, []);
}

/* ============================================================
 * FLOOR SLAB
 * ============================================================ */
function Floor({ materials, floor }: { materials: ReturnType<typeof useMaterials>; floor: number }) {
  const y = floorY(floor);
  const color = floor === 0 ? "#b08456" : floor === 1 ? "#c4a578" : "#3a322c";
  return (
    <mesh position={[0, y, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
      <planeGeometry args={[60, 40]} />
      <meshStandardMaterial color={color} roughness={floor === -1 ? 0.95 : 0.55} metalness={0.02} />
    </mesh>
  );
}

/* ============================================================
 * ROOM (glass-walled, with desks + agents)
 * ============================================================ */
interface RoomProps {
  room: RoomDef;
  materials: ReturnType<typeof useMaterials>;
  hasRisk: boolean;
  pendingCount: number;
  agentCount: number;
  isFocused: boolean;
  isHovered: boolean;
  onHover: (hovered: boolean) => void;
  onClick: () => void;
}

function Room({ room, materials, hasRisk, pendingCount, agentCount, isFocused, isHovered, onHover, onClick }: RoomProps) {
  const y = floorY(room.floor);
  const [w, d] = room.size;
  const [cx, cz] = room.center;
  const wallH = 2.6;
  const accentColor = room.color ?? "#0f766e";

  // Pulsing effect for risk rooms
  const roomRef = React.useRef<THREE.Group>(null);
  useFrame((state) => {
    if (!roomRef.current) return;
    if (hasRisk) {
      const pulse = 0.5 + 0.5 * Math.sin(state.clock.elapsedTime * 2);
      roomRef.current.traverse((child) => {
        if (child instanceof THREE.Mesh && child.material instanceof THREE.MeshStandardMaterial) {
          if (child.userData.isAccent) {
            child.material.emissive.setHex(new THREE.Color("#c0392b").getHex());
            child.material.emissiveIntensity = 0.3 + 0.4 * pulse;
          }
        }
      });
    }
  });

  return (
    <group
      ref={roomRef}
      position={[cx, y, cz]}
      onPointerOver={(e: ThreeEvent<PointerEvent>) => { e.stopPropagation(); onHover(true); document.body.style.cursor = "pointer"; }}
      onPointerOut={() => { onHover(false); document.body.style.cursor = "default"; }}
      onClick={(e: ThreeEvent<MouseEvent>) => { e.stopPropagation(); onClick(); }}
    >
      {/* Floor tile — accent color per room */}
      <mesh position={[0, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow userData={{ isAccent: false }}>
        <planeGeometry args={[w - 0.2, d - 0.2]} />
        <meshStandardMaterial color="#b08456" roughness={0.5} />
      </mesh>

      {/* Accent carpet/rug under desks */}
      <mesh position={[0, 0.03, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[w - 1.5, d - 1.5]} />
        <meshStandardMaterial color={accentColor} roughness={0.9} opacity={0.18} transparent />
      </mesh>

      {/* Glass walls — 4 sides, shorter toward the "front" (facing lobby) */}
      <mesh position={[0, wallH / 2, -d / 2]} castShadow>
        <boxGeometry args={[w, wallH, 0.08]} />
        <primitive object={materials.glass} attach="material" />
      </mesh>
      <mesh position={[0, wallH / 2, d / 2]}>
        <boxGeometry args={[w - 2, wallH, 0.08]} />
        <primitive object={materials.glass} attach="material" />
      </mesh>
      <mesh position={[-w / 2, wallH / 2, 0]}>
        <boxGeometry args={[0.08, wallH, d]} />
        <primitive object={materials.glass} attach="material" />
      </mesh>
      <mesh position={[w / 2, wallH / 2, 0]}>
        <boxGeometry args={[0.08, wallH, d]} />
        <primitive object={materials.glass} attach="material" />
      </mesh>

      {/* Brass frame on top */}
      <mesh position={[0, wallH, -d / 2]}>
        <boxGeometry args={[w + 0.1, 0.08, 0.1]} />
        <primitive object={materials.brass} attach="material" />
      </mesh>

      {/* Risk glow ring on the floor */}
      {hasRisk && (
        <mesh position={[0, 0.05, 0]} rotation={[-Math.PI / 2, 0, 0]} userData={{ isAccent: true }}>
          <ringGeometry args={[Math.max(w, d) / 2.2, Math.max(w, d) / 2, 32]} />
          <meshStandardMaterial color="#c0392b" emissive="#c0392b" emissiveIntensity={0.6} transparent opacity={0.7} side={THREE.DoubleSide} />
        </mesh>
      )}

      {/* Room label floating above */}
      <Html position={[0, wallH + 0.6, 0]} center distanceFactor={12} occlude={false}>
        <div className={`office-room-label ${hasRisk ? "office-room-label--risk" : ""} ${isFocused ? "office-room-label--active" : ""}`}>
          <span className="office-room-label__name">{room.label}</span>
          <div className="office-room-label__meta">
            <span className={`office-room-label__dot office-room-label__dot--${hasRisk ? "risk" : "ok"}`} />
            <span>{agentCount} {agentCount === 1 ? "agent" : "agents"}</span>
            {pendingCount > 0 && <span className="office-room-label__pending">· {pendingCount} pending</span>}
          </div>
        </div>
      </Html>

      {/* Desks + agents */}
      {room.desks.map((desk, i) => (
        <Desk key={i} desk={desk} materials={materials} />
      ))}

      {/* Hover/focus highlight */}
      {(isHovered || isFocused) && (
        <mesh position={[0, wallH / 2, 0]}>
          <boxGeometry args={[w + 0.4, wallH + 0.4, d + 0.4]} />
          <meshBasicMaterial color={accentColor} wireframe transparent opacity={isFocused ? 0.5 : 0.25} />
        </mesh>
      )}
    </group>
  );
}

/* ============================================================
 * DESK + AGENT FIGURE
 * ============================================================ */
function Desk({ desk, materials }: { desk: import("./officeLayout").DeskDef; materials: ReturnType<typeof useMaterials> }) {
  return (
    <group position={[desk.position[0], 0, desk.position[1]]} rotation={[0, desk.rotation ?? 0, 0]}>
      {/* Desk surface */}
      <mesh position={[0, 0.75, -0.3]} castShadow>
        <boxGeometry args={[1.6, 0.05, 0.7]} />
        <primitive object={materials.desk} attach="material" />
      </mesh>
      {/* Desk legs (simplified as a box pedestal) */}
      <mesh position={[-0.65, 0.37, -0.5]}>
        <boxGeometry args={[0.08, 0.75, 0.08]} />
        <primitive object={materials.brass} attach="material" />
      </mesh>
      <mesh position={[0.65, 0.37, -0.5]}>
        <boxGeometry args={[0.08, 0.75, 0.08]} />
        <primitive object={materials.brass} attach="material" />
      </mesh>
      {/* Monitor */}
      <mesh position={[0, 1.05, -0.5]} castShadow>
        <boxGeometry args={[0.9, 0.5, 0.04]} />
        <meshStandardMaterial color="#1a1714" emissive="#0f766e" emissiveIntensity={0.3} roughness={0.3} />
      </mesh>
      <mesh position={[0, 0.8, -0.5]}>
        <boxGeometry args={[0.1, 0.15, 0.1]} />
        <primitive object={materials.brass} attach="material" />
      </mesh>
      {/* Agent figure — seated */}
      <AgentFigure desk={desk} />
    </group>
  );
}

function AgentFigure({ desk }: { desk: import("./officeLayout").DeskDef }) {
  // Find this agent's status from the office snapshot
  const { data } = useOfficeSnapshot();
  const agentKey = desk.agentKey;
  const agentRow = React.useMemo(() => {
    if (!data || !agentKey) return null;
    return data.agents.find((a) => {
      const k = text(a, "agent_key", "").toLowerCase();
      const name = text(a, "agent_name", "").toLowerCase();
      return k.includes(agentKey.toLowerCase()) || name.includes(agentKey.toLowerCase().replace(/_/g, " "));
    }) ?? null;
  }, [data, agentKey]);

  const status = agentRow ? text(agentRow, "status", "active").toLowerCase() : "active";
  const isBusy = status.includes("active") || status.includes("running") || status.includes("working");
  const isBlocked = status.includes("block") || status.includes("error") || status.includes("fail");

  const ringColor = isBlocked ? "#c0392b" : isBusy ? "#2d7a4f" : "#7a6f62";

  const groupRef = React.useRef<THREE.Group>(null);
  // Subtle idle breathing motion for active agents
  useFrame((state) => {
    if (!groupRef.current || !isBusy) return;
    groupRef.current.position.y = 1.05 + Math.sin(state.clock.elapsedTime * 1.5 + (desk.position[0] ?? 0)) * 0.015;
  });

  return (
    <group ref={groupRef} position={[0, 1.05, 0.1]}>
      {/* Head */}
      <mesh castShadow>
        <sphereGeometry args={[0.18, 24, 24]} />
        <meshStandardMaterial color="#e8d4b8" roughness={0.7} />
      </mesh>
      {/* Body (capsule) */}
      <mesh position={[0, -0.45, 0]} castShadow>
        <capsuleGeometry args={[0.22, 0.5, 8, 16]} />
        <meshStandardMaterial color={isBlocked ? "#8f1d14" : "#2a4f7a"} roughness={0.6} />
      </mesh>
      {/* Status ring on the floor in front */}
      <mesh position={[0, -1.0, 0.4]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.28, 0.34, 24]} />
        <meshBasicMaterial color={ringColor} transparent opacity={0.85} side={THREE.DoubleSide} />
      </mesh>
    </group>
  );
}

/* ============================================================
 * DATA FLOW PARTICLES (between connected rooms)
 * ============================================================ */
function DataFlows() {
  const { data } = useOfficeSnapshot();
  const messages = data?.agent_messages ?? [];

  // Define static flow connections (which rooms talk to which)
  const connections: Array<[string, string]> = [
    ["research", "committee"],
    ["committee", "portfolio"],
    ["portfolio", "risk"],
    ["risk", "trading"],
    ["news", "research"],
    ["quant", "committee"],
    ["executive", "committee"],
  ];

  return (
    <>
      {connections.map(([from, to], i) => (
        <FlowLine key={i} fromKey={from} toKey={to} activity={messages.length} />
      ))}
    </>
  );
}

function FlowLine({ fromKey, toKey, activity }: { fromKey: string; toKey: string; activity: number }) {
  const from = roomByKey(fromKey);
  const to = roomByKey(toKey);
  const dashRef = React.useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (!dashRef.current) return;
    const t = (state.clock.elapsedTime * 0.3) % 1;
    dashRef.current.position.x = THREE.MathUtils.lerp(from!.center[0], to!.center[0], t);
    dashRef.current.position.z = THREE.MathUtils.lerp(from!.center[1], to!.center[1], t);
    dashRef.current.position.y = floorY(from!.floor) + 1.5;
  });

  if (!from || !to) return null;
  // Only show if there's activity
  if (activity === 0) return null;

  return (
    <mesh ref={dashRef}>
      <sphereGeometry args={[0.06, 8, 8]} />
      <meshBasicMaterial color="#ffd9a0" transparent opacity={0.9} />
    </mesh>
  );
}

/* ============================================================
 * CAMERA CONTROLLER — flies to focused room
 * ============================================================ */
function CameraController({ focusTarget }: { focusTarget: string | null }) {
  const { camera } = useThree();
  const targetPos = React.useRef(new THREE.Vector3(0, 12, 18));
  const targetLook = React.useRef(new THREE.Vector3(0, 0, 0));

  React.useEffect(() => {
    if (focusTarget) {
      const room = roomByKey(focusTarget);
      if (room) {
        const y = floorY(room.floor);
        // Position camera in front of and above the room
        targetPos.current.set(room.center[0] + room.size[0] * 0.6, y + 4, room.center[1] + room.size[1] + 4);
        targetLook.current.set(room.center[0], y + 0.5, room.center[1]);
      }
    } else {
      // Lobby overview
      targetPos.current.set(0, 10, 16);
      targetLook.current.set(0, 0, -2);
    }
  }, [focusTarget]);

  useFrame(() => {
    camera.position.lerp(targetPos.current, 0.05);
    camera.lookAt(targetLook.current);
  });

  return null;
}

/* ============================================================
 * SCENE
 * ============================================================ */
export interface LiveOfficeProps {
  /** Container height. */
  height?: number | string;
}

export function LiveOffice({ height = "100%" }: LiveOfficeProps) {
  const materials = useMaterials();
  const { data } = useOfficeSnapshot();
  const cameraTarget = useUIStore((s) => s.cameraTarget);
  const focusRoom = useUIStore((s) => s.focusRoom);
  const openEvidence = useUIStore((s) => s.openEvidence);
  const setAssistantScope = useUIStore((s) => s.setAssistantScope);
  const [hovered, setHovered] = React.useState<string | null>(null);

  // Detect WebGL support
  const [webglOk, setWebglOk] = React.useState<boolean | null>(null);
  React.useEffect(() => {
    try {
      const canvas = document.createElement("canvas");
      const gl = canvas.getContext("webgl2") || canvas.getContext("webgl");
      setWebglOk(Boolean(gl));
    } catch {
      setWebglOk(false);
    }
  }, []);

  const prefersReducedMotion = typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  if (webglOk === false || prefersReducedMotion) {
    return <OfficeFallback height={height} />;
  }

  // Compute risk state per room
  const riskRooms = React.useMemo(() => {
    const set = new Set<string>();
    if (data?.risk_events?.length) {
      // Map risk events to rooms by department heuristic
      set.add("risk");
      if (data.risk_events.some((r) => text(r, "department").includes("portfolio") || text(r, "book"))) set.add("portfolio");
    }
    return set;
  }, [data?.risk_events]);

  return (
    <>
      <style>{LiveOfficeCss}</style>
      <div className="office-canvas-wrap" style={{ height }}>
        <Canvas
          shadows
          dpr={[1, 2]}
          camera={{ position: [0, 10, 16], fov: 42 }}
          gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.1 }}
        >
          <AdaptiveDpr pixelated />
          <AdaptiveEvents />

          {/* Warm ambient + sun */}
          <ambientLight intensity={0.6} color="#fff4e0" />
          <hemisphereLight args={["#fff4e0", "#3a2f25", 0.5]} />
          <directionalLight
            position={[10, 18, 8]}
            intensity={1.4}
            color="#ffe8c4"
            castShadow
            shadow-mapSize={[2048, 2048]}
            shadow-camera-left={-25}
            shadow-camera-right={25}
            shadow-camera-top={25}
            shadow-camera-bottom={-25}
            shadow-camera-near={0.5}
            shadow-camera-far={50}
          />
          {/* Warm fill from the opposite side */}
          <pointLight position={[-8, 4, -6]} intensity={20} color="#ffd9a0" distance={20} />
          <pointLight position={[8, 4, 6]} intensity={15} color="#ffd9a0" distance={20} />

          {/* Sky + environment */}
          <Environment preset="apartment" background={false} />

          <SoftShadows size={28} samples={12} focus={0.6} />

          {/* Floors */}
          <Floor materials={materials} floor={0} />
          <Floor materials={materials} floor={1} />
          <Floor materials={materials} floor={-1} />

          {/* Floor dividers / stairs hint (simple ramps between floors) */}
          <mesh position={[14, 2, 0]}>
            <boxGeometry args={[0.3, 4, 4]} />
            <meshStandardMaterial color="#8a6440" roughness={0.7} />
          </mesh>

          {/* Rooms */}
          {ROOMS.map((room) => (
            <Room
              key={room.key}
              room={room}
              materials={materials}
              hasRisk={riskRooms.has(room.key)}
              pendingCount={0}
              agentCount={room.desks.length}
              isFocused={cameraTarget.roomKey === room.key}
              isHovered={hovered === room.key}
              onHover={(h) => setHovered(h ? room.key : null)}
              onClick={() => focusRoom(room.key)}
            />
          ))}

          {/* Data flows */}
          <DataFlows />

          {/* Soft contact shadows */}
          <ContactShadows position={[0, 0.01, 0]} opacity={0.4} scale={50} blur={2.5} far={8} color="#3a2f25" />

          {/* Camera controller */}
          <CameraController focusTarget={cameraTarget.roomKey} />

          {/* Orbit controls (limited) */}
          <OrbitControls
            enablePan={false}
            minDistance={8}
            maxDistance={28}
            minPolarAngle={0.2}
            maxPolarAngle={Math.PI / 2.1}
            target={[0, 1, -1]}
            makeDefault
          />

          {/* Post-processing — warm, cinematic */}
          <EffectComposer multisampling={0}>
            <Bloom luminanceThreshold={0.7} luminanceSmoothing={0.4} intensity={0.5} mipmapBlur />
            <BrightnessContrast brightness={0.02} contrast={0.06} />
            <Vignette eskil={false} offset={0.2} darkness={0.65} />
            <SMAA />
          </EffectComposer>
        </Canvas>

        {/* HUD overlay */}
        <OfficeHud focusedRoom={cameraTarget.roomKey} />
      </div>
    </>
  );
}

/* ============================================================
 * HUD — the HTML overlay on top of the canvas
 * ============================================================ */
function OfficeHud({ focusedRoom }: { focusedRoom: string | null }) {
  const focusRoom = useUIStore((s) => s.focusRoom);
  const room = focusedRoom ? roomByKey(focusedRoom) : null;
  return (
    <div className="office-hud">
      <div className="office-hud__top">
        <div className="office-hud__title">AI Investment Firm — Live</div>
        <div className="office-hud__hint">Click a room to fly in · Scroll to zoom · Drag to orbit</div>
      </div>
      <div className="office-hud__bottom">
        {room ? (
          <div className="office-hud__room-card">
            <div className="office-hud__room-name">{room.label}</div>
            <div className="office-hud__room-dept">{room.department}</div>
            <div className="office-hud__room-actions">
              {room.link && (
                <button className="office-hud__btn office-hud__btn--primary" onClick={() => { window.history.pushState({}, "", room.link!); window.dispatchEvent(new PopStateEvent("popstate")); }}>
                  Open in 2D →
                </button>
              )}
              <button className="office-hud__btn" onClick={() => focusRoom(null)}>Back to lobby</button>
            </div>
          </div>
        ) : (
          <div className="office-hud__lobby-hint">You're at the lobby overview. Pick a room to explore.</div>
        )}
      </div>
    </div>
  );
}

/* ============================================================
 * FALLBACK — static view when WebGL is unavailable
 * ============================================================ */
function OfficeFallback({ height }: { height: number | string }) {
  const focusRoom = useUIStore((s) => s.focusRoom);
  const cameraTarget = useUIStore((s) => s.cameraTarget);
  return (
    <div className="office-fallback" style={{ height }}>
      <div className="office-fallback__inner">
        <div className="office-fallback__title">Live Office (static view)</div>
        <div className="office-fallback__sub">3D rendering is unavailable on this device. Here's the floor plan:</div>
        <div className="office-fallback__grid">
          {ROOMS.map((room) => (
            <button
              key={room.key}
              className={`office-fallback__room ${cameraTarget.roomKey === room.key ? "office-fallback__room--active" : ""}`}
              onClick={() => focusRoom(room.key)}
            >
              <div className="office-fallback__room-name">{room.label}</div>
              <div className="office-fallback__room-dept">{room.department}</div>
              <div className="office-fallback__room-floor">{
                room.floor === 1 ? "Mezzanine" : room.floor === -1 ? "Basement" : "Ground"
              }</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
