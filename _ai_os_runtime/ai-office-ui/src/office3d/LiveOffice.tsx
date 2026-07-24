/**
 * 3D Live Office — React Three Fiber scene (robust rewrite)
 *
 * Design priorities for this rewrite, in order:
 *   1. NEVER crashes. No network fetches, no fragile transmission materials.
 *   2. Actually visible — bright warm lighting, clear camera framing.
 *   3. Interactive — click rooms to fly in, hover for labels, risk rooms glow.
 *   4. Beautiful — oak floors, warm daylight, glass-ish walls, live agents.
 *
 * The previous version crashed silently because Environment preset="apartment"
 * fetches an HDR from a CDN (fails offline) and MeshPhysicalMaterial
 * transmission needs special setup. Both removed. Lighting is hand-tuned.
 */

import React from "react";
import { Canvas, useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import { OrbitControls, Html, AdaptiveDpr } from "@react-three/drei";
import * as THREE from "three";
import { ROOMS, floorY, roomByKey, type RoomDef, type DeskDef } from "./officeLayout";
import { useOfficeSnapshot } from "../data/queries";
import { useUIStore } from "../store";
import { text } from "../data/liveRow";
import { LiveOfficeCss } from "./LiveOffice.css";

/* ============================================================
 * ROOM — a glass-ish box with a floor, desks, agents, and a label
 * ============================================================ */
interface RoomProps {
  room: RoomDef;
  hasRisk: boolean;
  isFocused: boolean;
  isHovered: boolean;
  onHover: (h: boolean) => void;
  onClick: () => void;
}

const ROOM_COLORS: Record<string, string> = {
  lobby: "#0f766e", research: "#2d7a4f", quant: "#6d4a8a", portfolio: "#0f766e",
  trading: "#d4a028", news: "#5b6b7a", executive: "#0f766e", committee: "#6d4a8a",
  risk: "#c0392b", runtime: "#5b6b7a", data: "#5b6b7a", library: "#2d7a4f",
};

function Room({ room, hasRisk, isFocused, isHovered, onHover, onClick }: RoomProps) {
  const y = floorY(room.floor);
  const [w, d] = room.size;
  const [cx, cz] = room.center;
  const wallH = 2.6;
  const accent = ROOM_COLORS[room.key] ?? "#0f766e";
  const groupRef = React.useRef<THREE.Group>(null);

  // Risk pulse
  useFrame((state) => {
    if (!groupRef.current || !hasRisk) return;
    const pulse = 0.4 + 0.3 * Math.sin(state.clock.elapsedTime * 2.5);
    groupRef.current.traverse((child) => {
      const mesh = child as THREE.Mesh;
      if (mesh.material && (mesh.userData as { riskGlow?: boolean }).riskGlow) {
        const mat = mesh.material as THREE.MeshStandardMaterial;
        mat.emissiveIntensity = pulse;
      }
    });
  });

  return (
    <group
      ref={groupRef}
      position={[cx, y, cz]}
      onPointerOver={(e: ThreeEvent<PointerEvent>) => { e.stopPropagation(); onHover(true); document.body.style.cursor = "pointer"; }}
      onPointerOut={() => { onHover(false); document.body.style.cursor = "default"; }}
      onClick={(e: ThreeEvent<MouseEvent>) => { e.stopPropagation(); onClick(); }}
    >
      {/* Floor tile — warm oak, accent-tinted rug */}
      <mesh position={[0, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[w - 0.1, d - 0.1]} />
        <meshStandardMaterial color="#b88a5a" roughness={0.6} />
      </mesh>
      <mesh position={[0, 0.03, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[w - 1.4, d - 1.4]} />
        <meshStandardMaterial color={accent} roughness={0.9} transparent opacity={0.16} />
      </mesh>

      {/* Glass-ish walls — semi-transparent standard material (no transmission) */}
      <mesh position={[0, wallH / 2, -d / 2]}>
        <boxGeometry args={[w, wallH, 0.06]} />
        <meshStandardMaterial color="#d8e4ec" transparent opacity={0.18} roughness={0.1} metalness={0.05} />
      </mesh>
      <mesh position={[0, wallH / 2, d / 2]}>
        <boxGeometry args={[w - 2.4, wallH, 0.06]} />
        <meshStandardMaterial color="#d8e4ec" transparent opacity={0.18} roughness={0.1} metalness={0.05} />
      </mesh>
      <mesh position={[-w / 2, wallH / 2, 0]}>
        <boxGeometry args={[0.06, wallH, d]} />
        <meshStandardMaterial color="#d8e4ec" transparent opacity={0.18} roughness={0.1} metalness={0.05} />
      </mesh>
      <mesh position={[w / 2, wallH / 2, 0]}>
        <boxGeometry args={[0.06, wallH, d]} />
        <meshStandardMaterial color="#d8e4ec" transparent opacity={0.18} roughness={0.1} metalness={0.05} />
      </mesh>

      {/* Brass top rail */}
      <mesh position={[0, wallH, -d / 2]}>
        <boxGeometry args={[w + 0.08, 0.08, 0.08]} />
        <meshStandardMaterial color="#b08d57" metalness={0.85} roughness={0.3} />
      </mesh>

      {/* Risk glow ring on floor */}
      {hasRisk && (
        <mesh position={[0, 0.05, 0]} rotation={[-Math.PI / 2, 0, 0]} userData={{ riskGlow: true }}>
          <ringGeometry args={[Math.max(w, d) / 2.3, Math.max(w, d) / 2, 48]} />
          <meshStandardMaterial color="#c0392b" emissive="#c0392b" emissiveIntensity={0.5} transparent opacity={0.7} side={THREE.DoubleSide} />
        </mesh>
      )}

      {/* Desks + agents */}
      {room.desks.map((desk, i) => (
        <DeskAndAgent key={i} desk={desk} accent={accent} />
      ))}

      {/* Floating label */}
      <Html position={[0, wallH + 0.5, 0]} center distanceFactor={11} occlude={false} zIndexRange={[20, 0]}>
        <div className={`office-room-label ${hasRisk ? "office-room-label--risk" : ""} ${isFocused ? "office-room-label--active" : ""}`}>
          <span className="office-room-label__name">{room.label}</span>
          <div className="office-room-label__meta">
            <span className={`office-room-label__dot office-room-label__dot--${hasRisk ? "risk" : "ok"}`} />
            <span>{room.desks.length} {room.desks.length === 1 ? "agent" : "agents"}</span>
          </div>
        </div>
      </Html>

      {/* Hover/focus wireframe highlight */}
      {(isHovered || isFocused) && (
        <mesh position={[0, wallH / 2, 0]}>
          <boxGeometry args={[w + 0.5, wallH + 0.5, d + 0.5]} />
          <meshBasicMaterial color={accent} wireframe transparent opacity={isFocused ? 0.45 : 0.22} />
        </mesh>
      )}
    </group>
  );
}

/* ============================================================
 * DESK + AGENT FIGURE
 * ============================================================ */
function DeskAndAgent({ desk, accent }: { desk: DeskDef; accent: string }) {
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
  const ringColor = isBlocked ? "#c0392b" : isBusy ? "#3d9a6f" : "#8a7f72";

  const figureRef = React.useRef<THREE.Group>(null);
  useFrame((state) => {
    if (!figureRef.current || !isBusy) return;
    figureRef.current.position.y = 1.0 + Math.sin(state.clock.elapsedTime * 1.4 + desk.position[0]) * 0.02;
  });

  return (
    <group position={[desk.position[0], 0, desk.position[1]]} rotation={[0, desk.rotation ?? 0, 0]}>
      {/* Desk surface + pedestal */}
      <mesh position={[0, 0.75, -0.35]} castShadow>
        <boxGeometry args={[1.6, 0.06, 0.7]} />
        <meshStandardMaterial color="#5a3a20" roughness={0.55} metalness={0.08} />
      </mesh>
      <mesh position={[-0.65, 0.37, -0.55]}>
        <boxGeometry args={[0.08, 0.74, 0.08]} />
        <meshStandardMaterial color="#b08d57" metalness={0.8} roughness={0.3} />
      </mesh>
      <mesh position={[0.65, 0.37, -0.55]}>
        <boxGeometry args={[0.08, 0.74, 0.08]} />
        <meshStandardMaterial color="#b08d57" metalness={0.8} roughness={0.3} />
      </mesh>
      {/* Monitor (glowing accent) */}
      <mesh position={[0, 1.05, -0.55]} castShadow>
        <boxGeometry args={[0.95, 0.52, 0.04]} />
        <meshStandardMaterial color="#0a0d10" emissive={accent} emissiveIntensity={0.5} roughness={0.3} />
      </mesh>
      <mesh position={[0, 0.82, -0.55]}>
        <boxGeometry args={[0.1, 0.16, 0.1]} />
        <meshStandardMaterial color="#b08d57" metalness={0.8} roughness={0.3} />
      </mesh>

      {/* Agent figure */}
      <group ref={figureRef} position={[0, 1.0, 0.15]}>
        {/* Head */}
        <mesh position={[0, 0.35, 0]} castShadow>
          <sphereGeometry args={[0.17, 20, 20]} />
          <meshStandardMaterial color="#e8d0b0" roughness={0.7} />
        </mesh>
        {/* Body */}
        <mesh position={[0, -0.1, 0]} castShadow>
          <capsuleGeometry args={[0.21, 0.45, 6, 14]} />
          <meshStandardMaterial color={isBlocked ? "#8f1d14" : "#2a4f7a"} roughness={0.6} />
        </mesh>
      </group>

      {/* Status ring on floor */}
      <mesh position={[0, 0.04, 0.45]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.26, 0.32, 24]} />
        <meshBasicMaterial color={ringColor} transparent opacity={0.85} side={THREE.DoubleSide} />
      </mesh>
    </group>
  );
}

/* ============================================================
 * DATA FLOW PARTICLES — warm light dots between connected rooms
 * ============================================================ */
function DataFlows({ activity }: { activity: number }) {
  const connections: Array<[string, string]> = React.useMemo(() => [
    ["research", "committee"], ["committee", "portfolio"], ["portfolio", "risk"],
    ["risk", "trading"], ["news", "research"], ["quant", "committee"], ["executive", "committee"],
  ], []);

  return (
    <>
      {connections.map(([from, to], i) => (
        <FlowDot key={i} fromKey={from} toKey={to} active={activity > 0} delay={i * 0.4} />
      ))}
    </>
  );
}

function FlowDot({ fromKey, toKey, active, delay }: { fromKey: string; toKey: string; active: boolean; delay: number }) {
  const from = roomByKey(fromKey);
  const to = roomByKey(toKey);
  const dotRef = React.useRef<THREE.Mesh>(null);
  useFrame((state) => {
    if (!dotRef.current || !from || !to || !active) return;
    const t = ((state.clock.elapsedTime + delay) * 0.25) % 1;
    dotRef.current.position.x = THREE.MathUtils.lerp(from.center[0], to.center[0], t);
    dotRef.current.position.z = THREE.MathUtils.lerp(from.center[1], to.center[1], t);
    dotRef.current.position.y = floorY(from.floor) + 1.6;
    (dotRef.current.material as THREE.MeshBasicMaterial).opacity = Math.sin(t * Math.PI);
  });
  if (!from || !to) return null;
  return (
    <mesh ref={dotRef} visible={active}>
      <sphereGeometry args={[0.07, 10, 10]} />
      <meshBasicMaterial color="#ffd9a0" transparent opacity={0.9} />
    </mesh>
  );
}

/* ============================================================
 * CAMERA CONTROLLER — smooth fly-to focused room
 * ============================================================ */
function CameraController({ focusTarget }: { focusTarget: string | null }) {
  const { camera } = useThree();
  const targetPos = React.useRef(new THREE.Vector3(0, 11, 17));
  const targetLook = React.useRef(new THREE.Vector3(0, 0, -1));

  React.useEffect(() => {
    if (focusTarget) {
      const room = roomByKey(focusTarget);
      if (room) {
        const ry = floorY(room.floor);
        targetPos.current.set(room.center[0] + room.size[0] * 0.55, ry + 4.5, room.center[1] + room.size[1] + 4.5);
        targetLook.current.set(room.center[0], ry + 0.8, room.center[1]);
      }
    } else {
      targetPos.current.set(0, 11, 17);
      targetLook.current.set(0, 0.5, -2);
    }
  }, [focusTarget]);

  useFrame(() => {
    camera.position.lerp(targetPos.current, 0.06);
    camera.lookAt(targetLook.current);
  });
  return null;
}

/* ============================================================
 * SCENE
 * ============================================================ */
export interface LiveOfficeProps {
  height?: number | string;
}

export function LiveOffice({ height = "100%" }: LiveOfficeProps) {
  const { data } = useOfficeSnapshot();
  const cameraTarget = useUIStore((s) => s.cameraTarget);
  const focusRoom = useUIStore((s) => s.focusRoom);
  const [hovered, setHovered] = React.useState<string | null>(null);
  const [errored, setErrored] = React.useState(false);

  // WebGL support check
  const [webglOk, setWebglOk] = React.useState<boolean | null>(null);
  React.useEffect(() => {
    try {
      const c = document.createElement("canvas");
      const gl = c.getContext("webgl2") || c.getContext("webgl");
      setWebglOk(Boolean(gl));
    } catch {
      setWebglOk(false);
    }
  }, []);

  const prefersReducedMotion = typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  // Compute risk rooms
  const riskRooms = React.useMemo(() => {
    const set = new Set<string>();
    if (data?.risk_events?.length) {
      set.add("risk");
      if (data.risk_events.some((r) => text(r, "department", "").includes("portfolio") || text(r, "book"))) set.add("portfolio");
    }
    return set;
  }, [data?.risk_events]);

  if (webglOk === false || prefersReducedMotion || errored) {
    return <OfficeFallback height={height} />;
  }

  return (
    <>
      <style>{LiveOfficeCss}</style>
      <div className="office-canvas-wrap" style={{ height }}>
        <Canvas
          shadows
          dpr={[1, 1.8]}
          camera={{ position: [0, 11, 17], fov: 42 }}
          gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.15 }}
          onError={() => setErrored(true)}
        >
          <React.Suspense fallback={null}>
            <AdaptiveDpr pixelated />

            {/* === LIGHTING — bright, warm, hand-tuned (no HDR fetch) === */}
            <ambientLight intensity={0.75} color="#fff2dc" />
            <hemisphereLight args={["#fff4e0", "#3a2f25", 0.7]} />
            <directionalLight
              position={[12, 20, 10]}
              intensity={1.6}
              color="#ffe8c4"
              castShadow
              shadow-mapSize={[2048, 2048]}
              shadow-camera-left={-30}
              shadow-camera-right={30}
              shadow-camera-top={30}
              shadow-camera-bottom={-30}
              shadow-camera-near={0.5}
              shadow-camera-far={60}
              shadow-bias={-0.0004}
            />
            {/* Warm fill lights */}
            <pointLight position={[-10, 5, -8]} intensity={28} color="#ffd9a0" distance={24} decay={2} />
            <pointLight position={[10, 5, 8]} intensity={20} color="#ffd9a0" distance={24} decay={2} />
            <pointLight position={[0, 8, 0]} intensity={15} color="#fff4e0" distance={30} decay={2} />

            {/* === FLOORS — three slabs === */}
            <Floor floor={0} />
            <Floor floor={1} />
            <Floor floor={-1} />

            {/* Stair tower connecting floors */}
            <mesh position={[14.5, 2, 0]}>
              <boxGeometry args={[0.4, 4, 5]} />
              <meshStandardMaterial color="#8a6440" roughness={0.7} />
            </mesh>

            {/* === ROOMS === */}
            {ROOMS.map((room) => (
              <Room
                key={room.key}
                room={room}
                hasRisk={riskRooms.has(room.key)}
                isFocused={cameraTarget.roomKey === room.key}
                isHovered={hovered === room.key}
                onHover={(h) => setHovered(h ? room.key : null)}
                onClick={() => focusRoom(room.key)}
              />
            ))}

            {/* === DATA FLOWS === */}
            <DataFlows activity={data?.agent_messages?.length ?? 0} />

            {/* === CAMERA + CONTROLS === */}
            <CameraController focusTarget={cameraTarget.roomKey} />
            <OrbitControls
              enablePan={false}
              minDistance={7}
              maxDistance={30}
              minPolarAngle={0.15}
              maxPolarAngle={Math.PI / 2.05}
              target={[0, 1, -1]}
              makeDefault
            />
          </React.Suspense>
        </Canvas>

        <OfficeHud focusedRoom={cameraTarget.roomKey} />
      </div>
    </>
  );
}

/* ============================================================
 * FLOOR SLAB
 * ============================================================ */
function Floor({ floor }: { floor: number }) {
  const y = floorY(floor);
  const color = floor === 0 ? "#b88a5a" : floor === 1 ? "#c4a07a" : "#3a322c";
  return (
    <mesh position={[0, y, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
      <planeGeometry args={[64, 44]} />
      <meshStandardMaterial color={color} roughness={floor === -1 ? 0.95 : 0.6} metalness={0.02} />
    </mesh>
  );
}

/* ============================================================
 * HUD overlay
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
 * FALLBACK — static floor plan when WebGL unavailable
 * ============================================================ */
function OfficeFallback({ height }: { height: number | string }) {
  const focusRoom = useUIStore((s) => s.focusRoom);
  const cameraTarget = useUIStore((s) => s.cameraTarget);
  return (
    <div className="office-fallback" style={{ height }}>
      <div className="office-fallback__inner">
        <div className="office-fallback__title">Live Office (floor plan view)</div>
        <div className="office-fallback__sub">3D rendering is unavailable on this device. Here's the interactive floor plan:</div>
        <div className="office-fallback__grid">
          {ROOMS.map((room) => (
            <button
              key={room.key}
              className={`office-fallback__room ${cameraTarget.roomKey === room.key ? "office-fallback__room--active" : ""}`}
              onClick={() => focusRoom(room.key)}
            >
              <div className="office-fallback__room-name">{room.label}</div>
              <div className="office-fallback__room-dept">{room.department}</div>
              <div className="office-fallback__room-floor">
                {room.floor === 1 ? "Mezzanine" : room.floor === -1 ? "Basement" : "Ground"}
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
