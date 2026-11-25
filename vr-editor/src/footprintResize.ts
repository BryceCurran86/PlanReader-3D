import { planLength, validWallLength } from "./buildPlacement.ts";
import type { CeilingDraft, PlanPoint, WallVisual } from "./buildPlacement.ts";
import type { ItemHit, PlacedItem, Vector } from "./itemPlacement.ts";
import type { SceneManifest } from "./types.ts";

export type FootprintBounds = { minX: number; maxX: number; minZ: number; maxZ: number };
export type FootprintCorner = "top-left" | "top-right" | "bottom-left" | "bottom-right";
export type FootprintEdge = "top" | "right" | "bottom" | "left";
export type FootprintHandle = FootprintCorner | FootprintEdge;
export const FOOTPRINT_EDGES: readonly FootprintEdge[] = ["top","right","bottom","left"];
export type FootprintAnchor = FootprintCorner | "centre";
export type FootprintProjection = {
  original: FootprintBounds; draft: FootprintBounds; scaleX: number; scaleZ: number;
};

export const FOOTPRINT_CORNERS: readonly FootprintCorner[] = ["top-left", "top-right", "bottom-left", "bottom-right"];
export const footprintWidth = (box: FootprintBounds) => box.maxX - box.minX;
export const footprintDepth = (box: FootprintBounds) => box.maxZ - box.minZ;
export const sameFootprint = (a: FootprintBounds, b: FootprintBounds) =>
  a.minX === b.minX && a.minZ === b.minZ && a.maxX === b.maxX && a.maxZ === b.maxZ;

function validBounds(box: FootprintBounds) {
  return Object.values(box).every(value => Number.isFinite(value) && Math.abs(value) <= 10000) &&
    footprintWidth(box) >= 0.05 - 1e-6 && footprintDepth(box) >= 0.05 - 1e-6;
}

export function footprintBounds(scene: SceneManifest, demo: boolean) {
  const box = { minX: Infinity, maxX: -Infinity, minZ: Infinity, maxZ: -Infinity };
  const add = (x: number, z: number) => {
    box.minX = Math.min(box.minX, x); box.maxX = Math.max(box.maxX, x);
    box.minZ = Math.min(box.minZ, z); box.maxZ = Math.max(box.maxZ, z);
  };
  const verified = new Set(scene.objects.filter(row => row.renderState === "verified").map(row => row.objectId));
  for (const floor of scene.sourceSurfaces ?? []) {
    if (floor.kind === "floor" && verified.has(floor.objectId))
      for (const [x, , z] of floor.vertices) add(x, z);
  }
  // Include verified walls beyond any incomplete set of published floor patches.
  for (const row of scene.objects) {
    const wall = row.geometry;
    if (wall && (demo || verified.has(row.objectId))) {
      add(...wall.start); add(...wall.end);
    }
  }
  if (!validBounds(box)) {
    for (const row of scene.objects) if (row.geometry) {
      add(...row.geometry.start); add(...row.geometry.end);
    }
  }
  return validBounds(box) ? box : null;
}

export function footprintCorner(box: FootprintBounds, handle: FootprintCorner): PlanPoint {
  return [handle.endsWith("left") ? box.minX : box.maxX, handle.startsWith("top") ? box.minZ : box.maxZ];
}

export function resizeFromCorner(box: FootprintBounds, corner: FootprintCorner, point: PlanPoint) {
  const left = corner.endsWith("left"), top = corner.startsWith("top");
  const [oldX, oldZ] = footprintCorner(box, corner);
  const x = oldX + Math.round((point[0] - oldX) * 20) / 20;
  const z = oldZ + Math.round((point[1] - oldZ) * 20) / 20;
  const draft = {
    minX: left ? x : box.minX, maxX: left ? box.maxX : x,
    minZ: top ? z : box.minZ, maxZ: top ? box.maxZ : z,
  };
  return validBounds(draft) ? draft : null;
}

export function footprintHandlePoint(box:FootprintBounds,handle:FootprintHandle):PlanPoint{
  switch(handle){
    case "top":return [(box.minX+box.maxX)/2,box.minZ];
    case "bottom":return [(box.minX+box.maxX)/2,box.maxZ];
    case "left":return [box.minX,(box.minZ+box.maxZ)/2];
    case "right":return [box.maxX,(box.minZ+box.maxZ)/2];
    default:return footprintCorner(box,handle);
  }
}
export function resizeFromHandle(box:FootprintBounds,handle:FootprintHandle,point:PlanPoint){
  const [x,z]=footprintHandlePoint(box,handle);
  const dx=Math.round((point[0]-x)*20)/20,dz=Math.round((point[1]-z)*20)/20;
  const next={...box};
  switch(handle){
    case "top":next.minZ+=dz;break;
    case "bottom":next.maxZ+=dz;break;
    case "left":next.minX+=dx;break;
    case "right":next.maxX+=dx;break;
    default:return resizeFromCorner(box,handle,point);
  }
  return validBounds(next)?next:null;
}

export function resizeFromDimensions(box: FootprintBounds, width: number, depth: number, anchor: FootprintAnchor) {
  const x = anchor === "centre" ? (box.minX + box.maxX - width) / 2 :
    anchor.endsWith("left") ? box.minX : box.maxX - width;
  const z = anchor === "centre" ? (box.minZ + box.maxZ - depth) / 2 :
    anchor.startsWith("top") ? box.minZ : box.maxZ - depth;
  const draft = { minX: x, maxX: x + width, minZ: z, maxZ: z + depth };
  return validBounds(draft) ? draft : null;
}

export function footprintProjection(original: FootprintBounds, draft: FootprintBounds): FootprintProjection {
  return { original, draft, scaleX: footprintWidth(draft) / footprintWidth(original),
    scaleZ: footprintDepth(draft) / footprintDepth(original) };
}

function mapXZ(x: number, z: number, view: FootprintProjection, reverse = false): PlanPoint {
  const { original, draft, scaleX, scaleZ } = view;
  return reverse ? [original.minX + (x - draft.minX) / scaleX, original.minZ + (z - draft.minZ) / scaleZ] :
    [draft.minX + (x - original.minX) * scaleX, draft.minZ + (z - original.minZ) * scaleZ];
}

export function projectVertex(point: Vector, projection: FootprintProjection): Vector {
  const [x, z] = mapXZ(point[0], point[2], projection);
  return [x, point[1], z];
}

function projectNormal(point: Vector, projection: FootprintProjection, reverse: boolean): Vector {
  const [x, y, z] = point;
  const projected: Vector = reverse ? [x * projection.scaleX, y, z * projection.scaleZ] :
    [x / projection.scaleX, y, z / projection.scaleZ];
  const length = Math.hypot(...projected);
  return length ? [projected[0] / length, projected[1] / length, projected[2] / length] : point;
}

export function projectPlan(point: PlanPoint, projection: FootprintProjection): PlanPoint {
  return mapXZ(...point, projection);
}

export function projectCeiling(ceiling: CeilingDraft, projection: FootprintProjection): CeilingDraft {
  return { ...ceiling, start: projectPlan(ceiling.start, projection), end: projectPlan(ceiling.end, projection) };
}

export function wallStretchRatio(wall: Pick<WallVisual, "start" | "end">, projection: FootprintProjection) {
  const length = planLength(wall.start, wall.end);
  return length ? planLength(projectPlan(wall.start, projection), projectPlan(wall.end, projection)) / length : 1;
}

export function projectWall<T extends WallVisual>(wall: T, projection: FootprintProjection): T {
  const start = projectPlan(wall.start, projection), end = projectPlan(wall.end, projection);
  const ratio = wallStretchRatio(wall, projection);
  const length = planLength(start, end);
  const openings = wall.openings?.map(opening => {
    const centre = (opening.offsetM + opening.widthM / 2) * ratio;
    const offsetM = Math.max(0, Math.min(length - opening.widthM, centre - opening.widthM / 2));
    return { ...opening, offsetM };
  });
  return { ...wall, start, end, ...(openings ? { openings } : {}) };
}

export function previewFootprint(
  scene: SceneManifest, original: FootprintBounds, requested: FootprintBounds,
  walls: readonly WallVisual[], ceilings: readonly CeilingDraft[],
): { projection: FootprintProjection | null; error?: string } {
  if (!validBounds(original) || !validBounds(requested)) return { projection: null, error: "Enter a positive width and depth within the model extents." };
  if (sameFootprint(original, requested)) return { projection: null };
  const projection = footprintProjection(original, requested);
  const validEnds = (points: readonly PlanPoint[]) =>
    points.every(point => projectPlan(point, projection).every(n => Number.isFinite(n) && Math.abs(n) <= 10000));
  for (const surface of scene.sourceSurfaces ?? []) {
    for (const [x, , z] of surface.vertices) {
      const [newX, newZ] = mapXZ(x, z, projection);
      if (!Number.isFinite(newX) || !Number.isFinite(newZ) || Math.abs(newX) > 10000 || Math.abs(newZ) > 10000)
        return { projection: null, error: "The resized model would extend beyond its working coordinates." };
    }
  }
  for (const row of scene.objects) {
    const wall = row.geometry;
    if (wall && !validEnds([wall.start, wall.end])) return { projection: null, error: "A model wall would be outside the working coordinates." };
  }
  for (const draft of [...walls, ...ceilings]) {
    if (!validEnds([draft.start, draft.end])) return { projection: null, error: "A draft would be outside the working coordinates." };
  }
  for (const draft of walls) {
    const wall = projectWall(draft, projection);
    const length = planLength(wall.start, wall.end);
    const openings = [...(wall.openings ?? [])].sort((a, b) => a.offsetM - b.offsetM);
    let right = 0;
    if (!validWallLength(length)) return { projection: null, error: "A draft wall would be outside the editor's length range." };
    for (const opening of openings) {
      if (opening.offsetM < right - 1e-6 || opening.offsetM + opening.widthM > length + 1e-6)
        return { projection: null, error: "This size would overlap draft openings or make a door or window too wide for its wall." };
      right = opening.offsetM + opening.widthM;
    }
  }
  return { projection };
}

function independentPlacement(hit: ItemHit) {
  return hit.target === "worktop" || hit.hostId.startsWith("site:");
}

export function projectPlacement<T extends PlacedItem>(entry: T, projection: FootprintProjection): T {
  if (independentPlacement(entry)) return entry;
  return { ...entry, point: projectVertex(entry.point, projection),
    normal: projectNormal(entry.normal, projection, false) };
}

export function originalPlacement(
  hit: ItemHit, projection: FootprintProjection, hostRun?: Pick<WallVisual, "start" | "end">,
): ItemHit {
  if (independentPlacement(hit)) return hit;
  const [x, z] = mapXZ(hit.point[0], hit.point[2], projection, true);
  const normal = projectNormal(hit.normal, projection, true);
  const anchor = hit.anchor?.kind === "wall" && hostRun
    ? { ...hit.anchor, offsetM: hit.anchor.offsetM / wallStretchRatio(hostRun, projection) } : hit.anchor;
  return { ...hit, point: [x, hit.point[1], z], normal, anchor };
}
