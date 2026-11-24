import type { WallAdditionOpening, WallAdditionSketch } from "./wallAdditionProtocol.ts";
import { exactDraftOpening, exactDraftWall } from "./vrDraftGeometry.ts";
import type { ExactWallField, OpeningField } from "./vrDraftGeometry.ts";

export const BUILD_TOOLS = [
  { id: "wall", label: "Wall" },
  { id: "door", label: "Door" },
  { id: "frame", label: "Frame" },
  { id: "window", label: "Window" },
  { id: "ceiling", label: "Ceiling" },
  { id: "move", label: "Move" },
  { id: "stretch", label: "Stretch" },
  { id: "opening-move", label: "Slide opening" },
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
  | { kind: "wall" | "ceiling"; levelId: string; point: PlanPoint; precisionSource?:boolean }
  | { kind: "opening"; levelId: string; proposalId: string; point: PlanPoint };
export type BuildAction =
  | { kind: "tool"; tool: BuildTool }
  | { kind: "done" | "undo" | "redo" }
  | { kind: "place"; hit: BuildHit; id: string }
  | { kind: "saved"; proposalId: string }
  | { kind: "adjust"; previous: PlacedWall; wall: PlacedWall }
  | { kind: "adjust-ceiling"; previous: CeilingDraft; ceiling: CeilingDraft }
  | { kind: "drag"; from: PlanPoint; to: PlanPoint; id: string; levelId: string;
      precisionSource?:boolean }
  | { kind: "delete-local-wall"; proposalId: string }
  | { kind: "duplicate-local-wall"; proposalId: string; id: string }
  | { kind: "exact-local-wall"; proposalId: string; field: ExactWallField; valueMm: number }
  | { kind: "exact-local-opening"; proposalId: string; openingId: string;
      field: OpeningField; valueMm: number };

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

export function millimetrePoint(point: PlanPoint): PlanPoint | null {
  return point.every(v => Number.isFinite(v) && Math.abs(v) <= 10000)
    ? [Math.round(point[0]*1000)/1000,Math.round(point[1]*1000)/1000]
    : null;
}
export function snappedPoint(point: PlanPoint): PlanPoint | null {
  const bounded = millimetrePoint(point);
  return bounded ? [snap(bounded[0]),snap(bounded[1])] : null;
}

// Magnetic alignment is strictly for LOCAL draft wall placement. It does not
// alter source/verified geometry or override any source authority checks.
export type DraftWallSnap = { point: PlanPoint; kind: "corner" | "straight" | "grid" | "verified";
  witness?: string };
export type WallAxis = "auto" | "free" | "horizontal" | "vertical";
export type WallSnapOptions = { gridM?: 0.05 | 0.1 | 0.25; axis?: WallAxis;
  verifiedAnchors?: readonly {point: PlanPoint; objectId: string}[] };
export function snapDraftWallPoint(
  state: Pick<BuildState, "walls">,
  levelId: string,
  raw: PlanPoint,
  anchor: PlanPoint | null = null,
  options: WallSnapOptions = {},
): DraftWallSnap | null {
  if (!snappedPoint(raw)) return null;
  const step = options.gridM ?? 0.05;
  const gridRound = (value: number) => Math.round(Math.round(value / step) * step * 100) / 100;
  const grid: PlanPoint = [gridRound(raw[0]), gridRound(raw[1])];
  let nearest: { point: PlanPoint; distance: number } | null = null;
  // Prefer exact junctions over ambiguous coordinate alignment.
  for (const wall of state.walls) {
    if (wall.levelId !== levelId) continue;
    for (const endpoint of [wall.start, wall.end]) {
      const distance = planLength(raw, endpoint);
      const axis = options.axis ?? "auto";
      const axisAligned = !anchor || axis === "auto" || axis === "free" ||
        (axis === "horizontal" && Math.abs(endpoint[1] - anchor[1]) <= 0.001) ||
        (axis === "vertical" && Math.abs(endpoint[0] - anchor[0]) <= 0.001);
      if (axisAligned && distance <= 0.20 && (!nearest || distance < nearest.distance)) {
        nearest = { point: endpoint, distance };
      }
    }
  }
  if (nearest) return { point: [...nearest.point], kind: "corner" };
  // Read-only, already verified source endpoints may GUIDE local preview placement.
  // They are never promoted into source geometry or pricing authority.
  const candidates = (options.verifiedAnchors ?? []).filter(candidate =>
    candidate.objectId && candidate.point.length === 2 &&
    candidate.point.every(v => Number.isFinite(v) && Math.abs(v) <= 10000) &&
    planLength(raw, candidate.point) <= 0.20 &&
    (!anchor || options.axis !== "horizontal" ||
      Math.abs(candidate.point[1] - anchor[1]) <= 0.001) &&
    (!anchor || options.axis !== "vertical" ||
      Math.abs(candidate.point[0] - anchor[0]) <= 0.001))
    .sort((a,b) => planLength(raw,a.point)-planLength(raw,b.point) ||
      a.objectId.localeCompare(b.objectId));
  const best = candidates[0];
  // Do not choose arbitrarily between two distinct source endpoints
  // when both are equidistant from the user's hand.
  const second = candidates.find(candidate =>
    !best || planLength(candidate.point,best.point) > 0.001);
  if (best && (!second ||
      planLength(raw,second.point) - planLength(raw,best.point) > 0.005)) {
    return { point: [...best.point], kind: "verified", witness: best.objectId };
  }
  if (anchor && snappedPoint(anchor)) {
    const dx = raw[0] - anchor[0], dz = raw[1] - anchor[1];
    if (options.axis === "horizontal") return {
      point: [grid[0], anchor[1]], kind: "straight" };
    if (options.axis === "vertical") return {
      point: [anchor[0], grid[1]], kind: "straight" };
    if (options.axis === "free") return { point: grid, kind: "grid" };
    // Orthogonal guide holds when the pointer is close to horizontal/vertical,
    // but not at the origin where accidental zero-length walls are likely.
    if (Math.hypot(dx, dz) > 0.20) {
      if (Math.abs(dx) <= 0.15 && Math.abs(dx) <= Math.abs(dz)) {
        return { point: [anchor[0], grid[1]], kind: "straight" };
      }
      if (Math.abs(dz) <= 0.15) {
        return { point: [grid[0], anchor[1]], kind: "straight" };
      }
    }
  }
  return { point: grid, kind: "grid" };
}

export function buildGuide(state: BuildState, levelId: string | null) {
  if (!levelId) return "Choose a source level on the desktop to start building.";
  if (!state.tool) return "Choose Wall or Ceiling, then drag across the plan or pick two points.";
  if (state.tool === "opening-move") return "Point near a local door/window opening, hold trigger and slide it along its host wall.";
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

// Reversible draft-only edits: callers must dispatch an "adjust" action with
// the original object reference, which is checked against the current scope.
export function translatedDraftWall(wall: PlacedWall, dx: number, dz: number): PlacedWall | null {
  const start = snappedPoint([wall.start[0] + dx, wall.start[1] + dz]);
  const end = snappedPoint([wall.end[0] + dx, wall.end[1] + dz]);
  if (!start || !end) return null;
  const edited = { ...wall, start, end };
  return validEditedWall(edited) ? edited : null;
}

// Large spatial arrow actions are relative to the user's current Quest view,
// then constrained to the nearest plan axis for construction-friendly nudges.
export function viewRelativeNudge(
  direction: "left" | "right" | "forward" | "back",
  facing: PlanPoint, stepM: number,
): PlanPoint | null {
  if (!Number.isFinite(stepM) || stepM <= 0 ||
      !facing.every(Number.isFinite) || Math.hypot(...facing) < 0.001) return null;
  const forward: PlanPoint = Math.abs(facing[0]) > Math.abs(facing[1])
    ? [Math.sign(facing[0]), 0] : [0, Math.sign(facing[1])];
  const right: PlanPoint = [-forward[1], forward[0]];
  const delta = direction === "forward" ? forward :
    direction === "back" ? [-forward[0], -forward[1]] :
    direction === "right" ? right : [-right[0], -right[1]];
  return [delta[0] * stepM, delta[1] * stepM];
}

export function rotatedDraftWall(wall: PlacedWall): PlacedWall | null {
  const cx = (wall.start[0] + wall.end[0]) / 2;
  const cz = (wall.start[1] + wall.end[1]) / 2;
  const rotate = (point: PlanPoint): PlanPoint | null =>
    snappedPoint([cx - (point[1] - cz), cz + (point[0] - cx)]);
  const start = rotate(wall.start), end = rotate(wall.end);
  if (!start || !end) return null;
  const edited = { ...wall, start, end };
  return validEditedWall(edited) ? edited : null;
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
  if (action.kind === "exact-local-wall" || action.kind === "exact-local-opening") {
    const previous = state.walls.find(wall => wall.proposalId === action.proposalId &&
      wall.scopeKey === scopeKey && wall.levelId === levelId);
    if (!previous) return state;
    const next = action.kind === "exact-local-wall"
      ? exactDraftWall(previous, action.field, action.valueMm)
      : exactDraftOpening(previous, action.openingId, action.field, action.valueMm);
    if (!next || JSON.stringify(next) === JSON.stringify(previous)) return state;
    return checkpoint(state, { walls: state.walls.map(wall => wall === previous ? next : wall),
      ceilings: state.ceilings });
  }
  if (action.kind === "delete-local-wall") {
    const wall = state.walls.find(item => item.proposalId === action.proposalId &&
      item.scopeKey === scopeKey && item.levelId === levelId);
    if (!wall) return state;
    return checkpoint(state, { walls: state.walls.filter(item => item !== wall),
      ceilings: state.ceilings });
  }
  if (action.kind === "duplicate-local-wall") {
    const wall = state.walls.find(item => item.proposalId === action.proposalId &&
      item.scopeKey === scopeKey && item.levelId === levelId);
    if (!wall || state.walls.length >= MAX_DRAFT_WALLS || !action.id ||
      state.walls.some(item => item.proposalId === action.id)) return state;
    const shifted = translatedDraftWall(wall, 0.5, 0);
    if (!shifted) return state;
    const copy: PlacedWall = { ...shifted, proposalId: action.id,
      openings: shifted.openings.map((opening, index) => ({
        ...opening, openingId: action.id + "-opening-" + index,
      })) };
    return checkpoint(state, { walls: [...state.walls, copy], ceilings: state.ceilings });
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
    const precisionSource=action.kind==="drag" ? action.precisionSource===true :
      ("precisionSource" in action.hit && action.hit.precisionSource===true);
    const roundPoint=precisionSource ? millimetrePoint : snappedPoint;
    const point = roundPoint(action.kind === "drag" ? action.to : action.hit.point);
    const start = action.kind === "drag" ? roundPoint(action.from) : activeStart(state, levelId);
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
