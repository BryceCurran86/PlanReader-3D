import type { WallAdditionOpening, WallAdditionSketch } from "./wallAdditionProtocol.ts";

export const BUILD_TOOLS = [
  { id: "wall", label: "Wall" },
  { id: "door", label: "Door" },
  { id: "frame", label: "Frame" },
  { id: "window", label: "Window" },
  { id: "ceiling", label: "Ceiling" },
  { id: "move", label: "Move" },
  { id: "stretch", label: "Stretch" },
] as const;
export type BuildTool = typeof BUILD_TOOLS[number]["id"];
export type PlanPoint = [number, number];
export type BuildSizes = { wallHeightM: number; widthM: number; heightM: number; ceilingHeightM?: number; windowWidthM?: number; windowHeightM?: number; windowSillM?: number };
export const STARTING_SIZES: BuildSizes = { wallHeightM: 2.4, widthM: 0.9, heightM: 2.1, ceilingHeightM: 2.4,
  windowWidthM: 1.2, windowHeightM: 1.05, windowSillM: 0.9 };
export const MAX_DRAFT_WALLS = 25;

export type PlacedWall = WallAdditionSketch & { openings: WallAdditionOpening[] };
export type WallVisual = WallAdditionSketch & { openings?: WallAdditionOpening[] };
export type CeilingDraft = {
  proposalId: string; scopeKey: string; levelId: string;
  start: PlanPoint; end: PlanPoint; heightM: number;
};
type DraftGeometry = { walls: PlacedWall[]; ceilings: CeilingDraft[] };
type StartPoint = { levelId: string; point: PlanPoint };
export type BuildState = DraftGeometry & {
  tool: BuildTool | null;
  start: StartPoint | null;
  history: DraftGeometry[];
  future?: DraftGeometry[];
};
export const EMPTY_BUILD: BuildState = { tool: null, start: null, walls: [], ceilings: [], history: [] };
export type BuildHit =
  | { kind: "wall" | "ceiling"; levelId: string; point: PlanPoint }
  | { kind: "opening"; levelId: string; proposalId: string; point: PlanPoint };
export type BuildAction =
  | { kind: "tool"; tool: BuildTool }
  | { kind: "done" | "undo" | "redo" }
  | { kind: "place"; hit: BuildHit; id: string }
  | { kind: "saved"; proposalId: string }
  | { kind: "adjust"; previous: PlacedWall; wall: PlacedWall }
  | { kind: "adjust-ceiling"; previous: CeilingDraft; ceiling: CeilingDraft }
  | { kind: "drag"; from: PlanPoint; to: PlanPoint; id: string; levelId: string };

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
  wall: PlacedWall, point: PlanPoint, tool: "door" | "frame" | "window", sizes: BuildSizes,
  openingId = "placement-preview",
) {
  const projection = projectOnWall(wall, point);
  if (!nearWall(projection)) return null;
  const { offset, length } = projection;
  const widthM = tool === "window" ? sizes.windowWidthM ?? STARTING_SIZES.windowWidthM! : sizes.widthM;
  const heightM = tool === "window" ? sizes.windowHeightM ?? STARTING_SIZES.windowHeightM! : sizes.heightM;
  const sillHeightM = tool === "window" ? sizes.windowSillM ?? STARTING_SIZES.windowSillM! : 0;
  const opening: WallAdditionOpening = {
    openingId,
    offsetM: Math.min(Math.max(snap(offset - widthM / 2), 0), length - widthM),
    widthM, heightM, sillHeightM, openingKind: tool === "frame" ? "passage" : tool,
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
  if (!state.tool) return "Choose Wall or Ceiling, then drag across the plan or pick two points.";
  if (state.tool === "move") return "Drag a draft wall or ceiling to move it.";
  if (state.tool === "stretch") return "Drag a wall end or ceiling corner to resize it.";
  if (state.tool === "ceiling") return activeStart(state, levelId)
    ? "Pick the opposite corner of the ceiling." : "Drag a ceiling rectangle or pick two opposite corners.";
  if (state.tool === "wall") {
    if (state.walls.length >= MAX_DRAFT_WALLS) return "Save a draft or undo a wall to add more.";
    return activeStart(state, levelId) ? "Pick the end of the wall." : "Drag from the wall start or pick two points.";
  }
  if (!state.walls.some(wall => wall.levelId === levelId)) return "Draw a wall first.";
  return state.tool === "door" ? "Point at a draft wall to place a door." :
    state.tool === "window" ? "Point at a draft wall to place a window opening." :
    "Point at a draft wall to place an open frame.";
}

const validHeight = (height: number) => Number.isFinite(height) && height > 0 && height <= 20;

export function validCeiling(start: PlanPoint, end: PlanPoint) {
  const spans = [Math.abs(end[0] - start[0]), Math.abs(end[1] - start[1])];
  return spans.every(span => span >= 0.05 - EPSILON && span <= 200);
}

export function draftShape<T extends CeilingDraft>(
  shape: T, mode: "move" | "stretch", from: PlanPoint, to: PlanPoint, anchor: PlanPoint,
): T | null {
  if (mode === "stretch") {
    const end = snappedPoint(to);
    return end ? { ...shape, end, start: anchor } : null;
  }
  const delta = snappedPoint([to[0] - from[0], to[1] - from[1]]);
  if (!delta) return null;
  const start = snappedPoint([shape.start[0] + delta[0], shape.start[1] + delta[1]]);
  const end = snappedPoint([shape.end[0] + delta[0], shape.end[1] + delta[1]]);
  return start && end ? { ...shape, start, end } : null;
}

export function validEditedWall(wall: PlacedWall) {
  return validWallLength(planLength(wall.start, wall.end)) && validHeight(wall.heightM) &&
    wall.openings.every(opening => openingFits(wall, opening));
}

function sameShape(a: CeilingDraft, b: CeilingDraft) {
  return a.start[0] === b.start[0] && a.start[1] === b.start[1] &&
    a.end[0] === b.end[0] && a.end[1] === b.end[1] && a.heightM === b.heightM;
}

function checkpoint(state: BuildState, geometry: DraftGeometry): BuildState {
  return { ...state, ...geometry, start: null,
    history: [...state.history, { walls: state.walls, ceilings: state.ceilings }].slice(-50), future: [] };
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
    const current = { walls: state.walls, ceilings: state.ceilings };
    return previous ? { ...state, ...previous, history: state.history.slice(0, -1),
      future: [...(state.future ?? []), current].slice(-50) } : state;
  }
  if (action.kind === "redo") {
    const next = state.future?.at(-1);
    if (!next) return state;
    return { ...checkpoint(state, next), future: state.future!.slice(0, -1) };
  }
  if (action.kind === "adjust") {
    const { previous, wall } = action;
    if (wall.scopeKey !== scopeKey || wall.proposalId !== previous.proposalId ||
        wall.levelId !== previous.levelId || !state.walls.includes(previous) ||
        !validEditedWall(wall)) return state;
    return checkpoint(state, { walls: state.walls.map(item => item === previous ? wall : item),
      ceilings: state.ceilings });
  }
  if (action.kind === "adjust-ceiling") {
    const { previous, ceiling } = action;
    if (levelId !== previous.levelId || ceiling.scopeKey !== scopeKey ||
        ceiling.proposalId !== previous.proposalId || ceiling.levelId !== previous.levelId ||
        !state.ceilings.includes(previous) || sameShape(previous, ceiling) ||
        !validCeiling(ceiling.start, ceiling.end) || !validHeight(ceiling.heightM)) return state;
    return checkpoint(state, { walls: state.walls,
      ceilings: state.ceilings.map(item => item === previous ? ceiling : item) });
  }
  if (action.kind === "saved") {
    const keep = (wall: PlacedWall) => wall.proposalId !== action.proposalId;
    return { ...state, walls: state.walls.filter(keep), start: null,
      history: state.history.map(snapshot => ({ ...snapshot, walls: snapshot.walls.filter(keep) })),
      future: state.future?.map(snapshot => ({ ...snapshot, walls: snapshot.walls.filter(keep) })) };
  }
  if (!levelId || !state.tool) return state;
  const tool = state.tool;
  if (action.kind === "drag" || (action.kind === "place" && action.hit.kind !== "opening")) {
    if (tool !== "wall" && tool !== "ceiling") return state;
    const hitLevel = action.kind === "drag" ? action.levelId : action.hit.levelId;
    if (hitLevel !== levelId || (action.kind === "place" && action.hit.kind !== tool)) return state;
    const point = snappedPoint(action.kind === "drag" ? action.to : action.hit.point);
    const start = action.kind === "drag" ? snappedPoint(action.from) : activeStart(state, levelId);
    if (!point || (action.kind === "drag" && !start)) return state;
    if (!start) return { ...state, start: { levelId, point } };
    const heightM = tool === "wall" ? sizes.wallHeightM : sizes.ceilingHeightM ?? STARTING_SIZES.wallHeightM;
    if (!validHeight(heightM)) return state;
    const shape = { scopeKey, proposalId: action.id, levelId, start, end: point, heightM };
    if (tool === "wall" && state.walls.length < MAX_DRAFT_WALLS && validWallLength(planLength(start, point))) {
      return checkpoint(state, { ceilings: state.ceilings, walls: [...state.walls, { ...shape, openings: [] }] });
    }
    if (tool === "ceiling" && state.ceilings.length < MAX_DRAFT_WALLS && validCeiling(start, point)) {
      return checkpoint(state, { walls: state.walls, ceilings: [...state.ceilings, shape] });
    }
    return state;
  }
  if (action.kind !== "place" || action.hit.kind !== "opening" ||
      action.hit.levelId !== levelId || (tool !== "door" && tool !== "frame" && tool !== "window")) return state;
  const { hit, id } = action;
  const wall = state.walls.find(item =>
    item.proposalId === hit.proposalId && item.levelId === levelId && item.scopeKey === scopeKey);
  const result = wall && aimOpening(wall, hit.point, tool, sizes, id);
  if (!wall || !result || result.error) return state;
  const updated = { ...wall, openings: [...wall.openings, result.opening] };
  return checkpoint(state, { walls: state.walls.map(item => item === wall ? updated : item),
    ceilings: state.ceilings });
}
