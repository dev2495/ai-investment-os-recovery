export interface DeskDef {
  position: [number, number];
  agentKey?: string;
  rotation?: number;
}

export interface RoomDef {
  key: string;
  floor: number;
  center: [number, number];
  size: [number, number];
  label: string;
  department: string;
  color: string;
  desks: DeskDef[];
  link?: string;
}

export const OFFICE_SCALE = 0.6;
export const FLOOR_HEIGHT = 4.8;
export const BASEMENT_Y = -4.2;

const room = (
  key: string,
  floor: number,
  center: [number, number],
  label: string,
  department: string,
  color: string,
  link: string,
  size: [number, number] = [7.2, 5.2],
): RoomDef => ({ key, floor, center, size, label, department, color, link, desks: [] });

export const ROOMS: RoomDef[] = [
  room("lobby", 0, [0, 0], "Operations Lobby", "Firm-wide live state", "#0f766e", "/today", [8.2, 5.2]),

  room("research", 0, [-12, -6], "Research Factory", "Research", "#2d7a4f", "/fundamental/theses"),
  room("news", 0, [0, -6], "News Intelligence", "News", "#4f6d7a", "/macro/news"),
  room("portfolio", 0, [12, -6], "Portfolio Office", "Portfolio", "#0f766e", "/portfolio/overview"),
  room("quant", 0, [-12, 5], "Quantitative Strategies", "Quant", "#70508d", "/quant/lab"),
  room("trading", 0, [0, 5], "Active Trading Desk", "Trading", "#c89222", "/trading/blotter"),
  room("tactical", 0, [12, 5], "Tactical Investing", "Tactical", "#9a5c36", "/scanners/ideas"),

  room("executive", 1, [-12, -6], "Executive Office", "Executive", "#0f766e", "/firm/agents"),
  room("committee", 1, [0, -6], "Committee Room", "Deliberation and human decisions", "#70508d", "/firm/committees", [8.2, 5.2]),
  room("risk", 1, [12, -6], "Independent Risk", "Risk", "#b53c32", "/risk/dashboard"),
  room("client", 1, [-12, 5], "Client Office", "Client", "#356b75", "/portfolio/clients"),
  room("treasury", 1, [0, 5], "Treasury, Hedges & Macro", "Treasury", "#6c6545", "/macro/dashboard"),
  room("automation", 1, [12, 5], "Automation Engineering", "Automation", "#4f6d7a", "/firm/system"),

  room("runtime", -1, [-12, -6], "Runtime Operations", "Runtime", "#4f6d7a", "/firm/system"),
  room("data", -1, [0, -6], "Data Engineering", "Data", "#42617a", "/firm/system"),
  room("knowledge", -1, [12, -6], "Knowledge & Memory", "Knowledge", "#2d7a4f", "/firm/library"),
  room("software", -1, [-6, 5], "Software Engineering", "Software", "#4a5d78", "/firm/system", [9.4, 5.2]),
];

export function floorY(floor: number): number {
  if (floor === 1) return FLOOR_HEIGHT;
  if (floor === -1) return BASEMENT_Y;
  return 0;
}

export function roomByKey(key: string): RoomDef | undefined {
  return ROOMS.find((candidate) => candidate.key === key);
}

export interface PlacedDesk extends DeskDef {
  room: RoomDef;
  worldPosition: [number, number, number];
}

export function allDesks(): PlacedDesk[] {
  return ROOMS.flatMap((officeRoom) => officeRoom.desks.map((desk) => ({
    ...desk,
    room: officeRoom,
    worldPosition: [
      officeRoom.center[0] + desk.position[0],
      floorY(officeRoom.floor),
      officeRoom.center[1] + desk.position[1],
    ],
  })));
}
