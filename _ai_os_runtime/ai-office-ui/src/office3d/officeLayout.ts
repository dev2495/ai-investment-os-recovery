/**
 * Office Floor Plan Configuration
 *
 * Defines the physical layout of the firm as a two-floor space:
 *   - Ground floor (y=0): the dealing floor — research, quant, portfolio,
 *     trading, news desks around a central lobby
 *   - Mezzanine (y=4): oversight — executive, committee, risk, CIO
 *   - Basement (y=-3): runtime, data, library (visible via glass floor)
 *
 * Each room has a center position, size, and a list of desks (agents).
 * Agents are placed at desks within their room.
 *
 * Coordinates are in meters, scaled by OFFICE_SCALE in the scene.
 */

export interface DeskDef {
  /** Local position within the room (meters), relative to room center. */
  position: [number, number];
  /** Agent key (matched against agent.department / agent.agent_key). */
  agentKey?: string;
  /** Facing direction (radians). */
  rotation?: number;
}

export interface RoomDef {
  /** Stable key — matches the command palette + camera focus targets. */
  key: string;
  /** Floor: 0 = ground, 1 = mezzanine, -1 = basement. */
  floor: number;
  /** Center position on that floor's plane (meters). */
  center: [number, number];
  /** Width + depth (meters). */
  size: [number, number];
  /** Display name. */
  label: string;
  /** Department or function. */
  department: string;
  /** Accent color hint for the room (hex). */
  color?: string;
  /** Desks in this room. */
  desks: DeskDef[];
  /** Deep-link path for "Open in 2D". */
  link?: string;
}

/** Global scale factor for the whole scene. */
export const OFFICE_SCALE = 0.6;
export const FLOOR_HEIGHT = 4;
export const BASEMENT_Y = -3;

export const ROOMS: RoomDef[] = [
  /* ===================== GROUND FLOOR ===================== */
  {
    key: "lobby",
    floor: 0,
    center: [0, 0],
    size: [10, 7],
    label: "Lobby",
    department: "Today's Brief",
    color: "#0f766e",
    link: "/today",
    desks: [],
  },
  {
    key: "research",
    floor: 0,
    center: [-9, -4],
    size: [7, 5],
    label: "Research Desk",
    department: "Research, Filings, Special Situations",
    color: "#2d7a4f",
    link: "/fundamental/theses",
    desks: [
      { position: [-2, -1], agentKey: "research_analyst", rotation: 0 },
      { position: [0, -1], agentKey: "filings_analyst", rotation: 0 },
      { position: [2, -1], agentKey: "special_situations", rotation: 0 },
    ],
  },
  {
    key: "quant",
    floor: 0,
    center: [0, -5],
    size: [9, 5],
    label: "Quant Lab",
    department: "Strategy, Backtest, Validation, Optimizer",
    color: "#6d4a8a",
    link: "/quant/lab",
    desks: [
      { position: [-3, -1], agentKey: "strategy_generator", rotation: 0 },
      { position: [-1, -1], agentKey: "backtest_engineer", rotation: 0 },
      { position: [1, -1], agentKey: "model_validation", rotation: 0 },
      { position: [3, -1], agentKey: "optimizer", rotation: 0 },
    ],
  },
  {
    key: "portfolio",
    floor: 0,
    center: [9, -4],
    size: [7, 5],
    label: "Portfolio Management",
    department: "Portfolio Manager, Books",
    color: "#0f766e",
    link: "/portfolio/overview",
    desks: [
      { position: [-1.5, -1], agentKey: "portfolio_manager", rotation: 0 },
      { position: [1.5, -1], agentKey: "cio", rotation: 0 },
    ],
  },
  {
    key: "trading",
    floor: 0,
    center: [9, 4],
    size: [6, 4],
    label: "Trading Desk",
    department: "TradingView, Blotter, Signals",
    color: "#d4a028",
    link: "/trading/blotter",
    desks: [
      { position: [0, -0.8], agentKey: "trading_desk", rotation: 0 },
    ],
  },
  {
    key: "news",
    floor: 0,
    center: [-9, 4],
    size: [6, 4],
    label: "News Desk",
    department: "News, Social, Corporate Actions",
    color: "#5b6b7a",
    link: "/macro/news",
    desks: [
      { position: [0, -0.8], agentKey: "news_analyst", rotation: 0 },
    ],
  },

  /* ===================== MEZZANINE ===================== */
  {
    key: "executive",
    floor: 1,
    center: [-6, 3],
    size: [6, 4],
    label: "Executive Office",
    department: "Charlie Munger · Chief of Staff",
    color: "#0f766e",
    link: "/firm/agents",
    desks: [
      { position: [-1.5, -0.8], agentKey: "charlie_munger", rotation: 0 },
      { position: [1.5, -0.8], agentKey: "chief_of_staff", rotation: 0 },
    ],
  },
  {
    key: "committee",
    floor: 1,
    center: [0, 3],
    size: [7, 5],
    label: "Committee Room",
    department: "Packets, positions, synthesis, votes",
    color: "#6d4a8a",
    link: "/firm/committees",
    desks: [
      { position: [-2, 0], agentKey: "committee_lead", rotation: 0 },
      { position: [0, 0], agentKey: "charlie_munger", rotation: Math.PI },
      { position: [2, 0], agentKey: "cio", rotation: 0 },
    ],
  },
  {
    key: "risk",
    floor: 1,
    center: [6, 3],
    size: [6, 4],
    label: "Risk & Compliance",
    department: "Risk Agent — limits, breaches, gates",
    color: "#c0392b",
    link: "/risk/dashboard",
    desks: [
      { position: [0, -0.8], agentKey: "risk_agent", rotation: 0 },
    ],
  },

  /* ===================== BASEMENT ===================== */
  {
    key: "runtime",
    floor: -1,
    center: [-5, -2],
    size: [6, 4],
    label: "Runtime",
    department: "Jarvis — server racks, jobs",
    color: "#5b6b7a",
    link: "/firm/system",
    desks: [
      { position: [0, -0.8], agentKey: "jarvis", rotation: 0 },
    ],
  },
  {
    key: "data",
    floor: -1,
    center: [0, -2],
    size: [6, 4],
    label: "Data Engineering",
    department: "Data Steward — pipelines, lineage",
    color: "#5b6b7a",
    link: "/firm/system",
    desks: [
      { position: [0, -0.8], agentKey: "data_steward", rotation: 0 },
    ],
  },
  {
    key: "library",
    floor: -1,
    center: [5, -2],
    size: [6, 4],
    label: "Knowledge Library",
    department: "Librarian — Obsidian vault, Qdrant",
    color: "#2d7a4f",
    link: "/firm/library",
    desks: [
      { position: [0, -0.8], agentKey: "librarian", rotation: 0 },
    ],
  },
];

/** Get the Y offset for a floor. */
export function floorY(floor: number): number {
  if (floor === 1) return FLOOR_HEIGHT;
  if (floor === -1) return BASEMENT_Y;
  return 0;
}

/** Find a room by key. */
export function roomByKey(key: string): RoomDef | undefined {
  return ROOMS.find((r) => r.key === key);
}

/** All desks flattened, with world position + room reference. */
export interface PlacedDesk extends DeskDef {
  room: RoomDef;
  worldPosition: [number, number, number];
}

export function allDesks(): PlacedDesk[] {
  const placed: PlacedDesk[] = [];
  for (const room of ROOMS) {
    for (const desk of room.desks) {
      placed.push({
        ...desk,
        room,
        worldPosition: [
          room.center[0] + desk.position[0],
          floorY(room.floor),
          room.center[1] + desk.position[1],
        ],
      });
    }
  }
  return placed;
}
