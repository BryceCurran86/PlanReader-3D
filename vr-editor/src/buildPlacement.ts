import type { WallAdditionOpening, WallAdditionSketch } from "./wallAdditionProtocol.ts";

export const BUILD_TOOLS = [
  { id: "wall", label: "Wall" },
  { id: "door", label: "Door" },
  { id: "frame", label: "Frame" },
] as const;
export type BuildTool = typeof BUILD_TOOLS[number]["id"];
export type PlanPoint = [number, number];
export type BuildSizes = { wallHeightM: number; widthM: number; heightM: number };
export const STARTING_SIZES: BuildSizes = { wallHeightM: 2.4, widthM: 0.9, heightM: 2.1 };
export const MAX_DRAFT_WALLS = 25;

export type PlacedWall = WallAdditionSketch & { openings: WallAdditionOpening[] };
export type WallVisual = WallAdditionSketch & { openings?: WallAdditionOpening[] };
type StartPoint = { levelId: string; point: PlanPoint };
export type BuildState = {
  tool: BuildTool | null;
  start: StartPoint | null;
  walls: PlacedWall[];
  history: PlacedWall[][];
};
export const EMPTY_BUILD: BuildState = { tool: null, start: null, walls: [], history: [] };
export type BuildHit =
  | { kind: "wall"; levelId: string; point: PlanPoint }
  | { kind: "opening"; levelId: string; proposalId: string; point: PlanPoint };
export type BuildAction =
  | { kind: "tool"; tool: BuildTool }
  | { kind: "done" | "undo" }
  | { kind: "place"; hit: BuildHit; id: string }
  | { kind: "saved"; proposalId: string }
  | { kind: "adjust"; previous: PlacedWall; wall: PlacedWall };

const EPSILON = 0.000001;
const HOST_TOLERANCE_M = 0.22;
const snap = (value: number) => Math.round(value * 20) / 20;

export function newPlacementId(kind: string) {
  const id = Array.from(crypto.getRandomValues(new Uint8Array(16)),
    byte => byte.toString(16).padStart(2, "0")).join("");
  return kind + "-" + id;
}

export function planLength(start: PlanPoint, end: PlanPoint) {
  return Math.hypot(end[0] - start[0], end[1] - start[1]);
}

export function validWallLength(length: number) {
  return length >= 0.05 - EPSILON && length <= 200;
}

export function projectOnWall(wall: WallAdditionSketch, point: PlanPoint) {
  const length = planLength(wall.start, wall.end);
  const dx = (wall.end[0] - wall.start[0]) / length;
  const dz = (wall.end[1] - wall.start[1]) / length;
  const x = point[0] - wall.start[0], z = point[1] - wall.start[1];
  return { offset: x * dx + z * dz, distance: Math.abs(x * dz - z * dx), length };
}

export function nearWall({ offset, distance, length }: ReturnType<typeof projectOnWall>) {
  return offset >= -HOST_TOLERANCE_M && offset <= length + HOST_TOLERANCE_M &&
    distance <= HOST_TOLERANCE_M;
}

export function openingFits(wall: WallAdditionSketch, opening: WallAdditionOpening): boolean {
  const { offsetM, widthM, heightM, sillHeightM } = opening;
  return [offsetM, widthM, heightM, sillHeightM].every(Number.isFinite) &&
    offsetM >= 0 && widthM > 0 && heightM > 0 && sillHeightM >= 0 &&
    offsetM + widthM <= planLength(wall.start, wall.end) + EPSILON &&
    sillHeightM + heightM <= wall.heightM + EPSILON;
}

export function aimOpening(
  wall: PlacedWall, point: PlanPoint, tool: "door" | "frame", sizes: BuildSizes,
  openingId = "placement-preview",
) {
  const projection = projectOnWall(wall, point);
  if (!nearWall(projection)) return null;
  const { offset, length } = projection;
  const { widthM, heightM } = sizes;
  const opening: WallAdditionOpening = {
    openingId,
    offsetM: Math.min(Math.max(snap(offset - widthM / 2), 0), length - widthM),
    widthM, heightM, sillHeightM: 0, openingKind: tool === "door" ? "door" : "passage",
  };
  if (!openingFits(wall, opening)) return { opening, error: "Opening is larger than this wall." };
  if (wall.openings.length >= 100) return { opening, error: "This draft has 100 openings." };
  if (wall.openings.some(other =>
    Math.min(other.offsetM + other.widthM, opening.offsetM + opening.widthM) -
      Math.max(other.offsetM, opening.offsetM) > EPSILON
  )) return { opening, error: "That position overlaps another opening." };
  return { opening, error: null };
}

export function activeStart(state: BuildState, levelId: string | null) {
  return state.start && state.start.levelId === levelId ? state.start.point : null;
}

export function snappedPoint(point: PlanPoint): PlanPoint | null {
  return point.every(v => Number.isFinite(v) && Math.abs(v) <= 10000)
    ? [snap(point[0]), snap(point[1])]
    : null;
}

export function buildGuide(state: BuildState, levelId: string | null) {
  if (!levelId) return "Choose a source level on the desktop to start building.";
  if (!state.tool) return state.walls.length
    ? "Pull the trigger on a tool to keep building. Review drafts on the desktop."
    : "Choose Wall and pick two points to start.";
  if (state.tool === "wall") {
    if (state.walls.length >= MAX_DRAFT_WALLS) return "Save a draft or undo a wall to add more.";
    return activeStart(state, levelId) ? "Pick the end of the wall." : "Pick the start of the wall.";
  }
  if (!state.walls.some(wall => wall.levelId === levelId)) return "Draw a wall first.";
  return state.tool === "door" ? "Point at a draft wall to place a door." :
    "Point at a draft wall to place an open frame.";
}

export function updateBuild(
  state: BuildState, action: BuildAction, scopeKey: string,
  levelId: string | null, sizes: BuildSizes,
): BuildState {
  if (action.kind === "tool") return { ...state, tool: action.tool, start: null };
  if (action.kind === "done") return { ...state, tool: null, start: null };
  if (action.kind === "undo") {
    if (activeStart(state, levelId)) return { ...state, start: null };
    const previous = state.history.at(-1);
    return previous ? { ...state, walls: previous, history: state.history.slice(0, -1) } : state;
  }
  if (action.kind === "adjust") {
    const { previous, wall } = action;
    if (wall.scopeKey !== scopeKey || !state.walls.includes(previous)) return state;
    return { ...state, walls: state.walls.map(item => item === previous ? wall : item),
      history: [...state.history, state.walls].slice(-50) };
  }
  if (action.kind === "saved") {
    const keep = (wall: PlacedWall) => wall.proposalId !== action.proposalId;
    return { ...state, walls: state.walls.filter(keep), start: null,
      history: state.history.map(walls => walls.filter(keep)) };
  }
  if (action.kind !== "place" || !levelId || action.hit.levelId !== levelId || !state.tool) return state;
  const { hit, id } = action;
  if (hit.kind === "wall" && state.tool === "wall") {
    const point = snappedPoint(hit.point);
    if (!point || state.walls.length >= MAX_DRAFT_WALLS) return state;
    const start = activeStart(state, levelId);
    if (!start) return { ...state, start: { levelId, point } };
    const { wallHeightM } = sizes;
    if (!validWallLength(planLength(start, point)) || !Number.isFinite(wallHeightM) ||
      wallHeightM <= 0 || wallHeightM > 20) return state;
    const wall = { scopeKey, proposalId: id, levelId, start, end: point, heightM: wallHeightM, openings: [] };
    return { ...state, start: null, walls: [...state.walls, wall],
      history: [...state.history, state.walls].slice(-50) };
  }
  if (hit.kind !== "opening" || state.tool === "wall") return state;
  const wall = state.walls.find(item =>
    item.proposalId === hit.proposalId && item.levelId === levelId && item.scopeKey === scopeKey);
  const result = wall && aimOpening(wall, hit.point, state.tool, sizes, id);
  if (!wall || !result || result.error) return state;
  const updated = { ...wall, openings: [...wall.openings, result.opening] };
  return { ...state, walls: state.walls.map(item => item === wall ? updated : item),
    history: [...state.history, state.walls].slice(-50) };
}
