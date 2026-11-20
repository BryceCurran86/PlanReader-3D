import { catalogueGroupLabel, getCatalogueItem } from "./itemCatalogue.ts";
import type { CatalogueItem, ItemTarget, TimberVisual } from "./itemCatalogue.ts";
import { openingFits, planLength, validWallLength } from "./buildPlacement.ts";
import type { WallVisual } from "./buildPlacement.ts";
import type { SceneManifest } from "./types.ts";

export type Vector = [number, number, number];
export type OpeningSize = { widthM: number; heightM: number; door: boolean };
export type WallSection = {
  start: [number, number]; end: [number, number]; heightM: number;
  apertures: { from: number; to: number; bottom: number; top: number }[];
};
export type ItemHit = {
  hostId: string;
  target: ItemTarget;
  point: Vector;
  normal: Vector;
  side: 1 | -1;
  opening?: OpeningSize;
};
export type PlacedItem = ItemHit & { id: string; itemId: string; turn: number };
export type ItemDraft = { sourceKey: string; items: PlacedItem[]; history: PlacedItem[][] };
export const emptyItemDraft = (sourceKey: string): ItemDraft => ({ sourceKey, items: [], history: [] });

export const makeItemHostId = (target: string, id: string) => target + ":" + id;
export const openingHostId = (proposalId: string, openingId: string) =>
  "opening:" + JSON.stringify([proposalId, openingId]);

export function worktopId(fixtureId: string) {
  return "worktop:" + fixtureId;
}

export function makesWorktop(item: CatalogueItem) {
  return item.visual.kind === "fixture" && ["vanity", "cabinet", "bench"].includes(item.visual.shape)
    && item.visual.heightM < 1.3;
}

export function openingFitMessage(item: CatalogueItem, opening: OpeningSize | undefined) {
  if (item.visual.kind !== "entry" && item.group !== "doors") return null;
  if (!opening?.door) return "Choose an opening placed with the Door tool.";
  if (item.visual.kind !== "entry") return null;
  const { minWidthM, minHeightM } = item.visual;
  if (!Number.isFinite(opening.widthM) || !Number.isFinite(opening.heightM) ||
      opening.widthM + 0.000001 < minWidthM || opening.heightM + 0.000001 < minHeightM) {
    return "This entry style needs at least " + Math.round(minWidthM * 1000) + " × " +
      Math.round(minHeightM * 1000) + " mm.";
  }
  return null;
}

export function timberFitsWall(spec: TimberVisual, point: Vector, turn: number, wall?: WallSection) {
  if (spec.mount === "post") return true;
  if (!wall) return false;
  const length = planLength(wall.start, wall.end);
  if (length < 0.000001) return false;
  const dx = (wall.end[0] - wall.start[0]) / length, dz = (wall.end[1] - wall.start[1]) / length;
  const x = point[0] - wall.start[0], z = point[2] - wall.start[1];
  const centre = x * dx + z * dz;
  const across = Math.abs(x * dz - z * dx);
  const vertical = turn % 2 === 0;
  const halfRun = (vertical ? spec.widthM : spec.lengthM) / 2;
  const halfHeight = (vertical ? spec.lengthM : spec.widthM) / 2;
  const left = centre - halfRun, right = centre + halfRun;
  const bottom = point[1] - halfHeight, top = point[1] + halfHeight;
  const margin = 0.000001;
  return across < 0.001 && left >= -margin && right <= length + margin &&
    bottom >= -margin && top <= wall.heightM + margin &&
    !wall.apertures.some(hole => left < hole.to - margin && right > hole.from + margin &&
      bottom < hole.top - margin && top > hole.bottom + margin);
}

export function itemGuide(item: CatalogueItem) {
  if (item.visual.kind === "entry") return "Aim at an opening placed with the Door tool.";
  if (item.visual.kind === "timber" && item.visual.mount === "face") return "Aim at the centre of the timber on a wall face.";
  const target = item.targets;
  if (target.includes("wall") && target.includes("ceiling")) return "Aim at a wall or ceiling.";
  switch (target[0]) {
    case "wall": return "Aim at a wall face.";
    case "floor": return "Aim at a floor.";
    case "ceiling": return "Aim at the underside of a ceiling.";
    case "roof": return "Aim at the top of a source-backed roof face.";
    case "opening": return "Aim at a door or frame you drafted.";
    case "worktop": return "Aim at a worktop. You can place a vanity or base cabinet first.";
  }
}

function surfaceSlot(placement: PlacedItem, item: CatalogueItem) {
  const visual = item.visual;
  if (visual.kind === "fixture" || visual.kind === "timber") return null;
  if (visual.kind === "entry") return JSON.stringify([placement.hostId, "entry"]);
  const side = placement.target === "wall" || placement.target === "opening" ? placement.side : 1;
  return JSON.stringify([placement.hostId, side, visual.kind === "trim" ? "trim" : visual.slot]);
}

function checkpoint(draft: ItemDraft, items: PlacedItem[]) {
  return { ...draft, items, history: [...draft.history, draft.items].slice(-32) };
}

export function placeItem(
  draft: ItemDraft, sourceKey: string, id: string, itemId: string, hit: ItemHit, turn: number,
): ItemDraft {
  const item = getCatalogueItem(itemId);
  const vertices = [...hit.point, ...hit.normal];
  const magnitude = Math.hypot(...hit.normal);
  if (draft.sourceKey !== sourceKey || !item?.targets.includes(hit.target) ||
      !hit.hostId || !id || (hit.side !== 1 && hit.side !== -1) || !vertices.every(Number.isFinite) || magnitude < 0.99 || magnitude > 1.01 ||
      !Number.isInteger(turn) || turn < 0 || turn > 3 ||
      draft.items.some(entry => entry.id === id)) return draft;
  if (hit.target === "opening" && openingFitMessage(item, hit.opening)) return draft;
  if (hit.target === "worktop" && !draft.items.some(entry => {
    const parent = getCatalogueItem(entry.itemId);
    return worktopId(entry.id) === hit.hostId && parent && makesWorktop(parent);
  })) return draft;
  if (hit.target === "roof" && hit.normal[1] <= 0.001) return draft;
  const entry = { ...hit, id, itemId, turn };
  const slot = surfaceSlot(entry, item);
  let items = draft.items;
  if (slot) {
    items = items.filter(previous => {
      const old = getCatalogueItem(previous.itemId);
      return !old || surfaceSlot(previous, old) !== slot;
    });
    if (items.length < draft.items.length && draft.items.some(previous => !items.includes(previous) &&
      previous.itemId === itemId)) return draft;
  } else if (items.some(previous => previous.hostId === entry.hostId && previous.itemId === itemId &&
    previous.side === entry.side && previous.turn === entry.turn &&
    Math.hypot(...previous.point.map((p, index) => p - hit.point[index])) <= 0.01)) {
    return draft;
  }
  if (items.length >= 300) return draft;
  return checkpoint(draft, [...items, entry]);
}

export function removeItem(draft: ItemDraft, id: string) {
  if (!draft.items.some(item => item.id === id)) return draft;
  return checkpoint(draft, draft.items.filter(item => item.id !== id && item.hostId !== worktopId(id)));
}

export function undoItem(draft: ItemDraft) {
  const items = draft.history.at(-1);
  return items ? { ...draft, items, history: draft.history.slice(0, -1) } : draft;
}

export function currentItemPlacements(
  items: readonly PlacedItem[], manifest: SceneManifest, walls: WallVisual[], demo: boolean,
) {
  const hosts = new Map<string, ItemTarget>();
  const openingSizes = new Map<string, OpeningSize>();
  const wallSections = new Map<string, WallSection>();
  for (const row of manifest.objects) {
    const shape = row.geometry;
    if (row.objectType === "wall" && shape?.kind === "wallFace" && shape.heightM > 0 &&
        planLength(shape.start, shape.end) > 0.000001) {
      const id = makeItemHostId("wall", row.objectId);
      hosts.set(id, "wall");
      wallSections.set(id, { start: shape.start, end: shape.end, heightM: shape.heightM, apertures: [] });
    }
  }
  for (const surface of manifest.sourceSurfaces ?? []) {
    hosts.set(makeItemHostId(surface.kind, surface.surfaceId), surface.kind);
  }
  if (demo) for (const room of ["west", "east"]) {
    hosts.set(makeItemHostId("floor", "demo-" + room), "floor");
    hosts.set(makeItemHostId("ceiling", "demo-" + room), "ceiling");
  }
  const distinct = new Map(walls.map(wall => [wall.proposalId, wall]));
  for (const wall of distinct.values()) {
    if (!validWallLength(planLength(wall.start, wall.end)) || wall.heightM <= 0) continue;
    const wallId = makeItemHostId("draft-wall", wall.proposalId);
    const apertures: WallSection["apertures"] = [];
    hosts.set(wallId, "wall");
    wallSections.set(wallId, { start: wall.start, end: wall.end, heightM: wall.heightM, apertures });
    const sorted = (wall.openings ?? []).filter(opening => openingFits(wall, opening))
      .sort((a, b) => a.offsetM - b.offsetM);
    let end = 0;
    for (const opening of sorted) {
      if (opening.offsetM < end - 0.000001) continue;
      end = opening.offsetM + opening.widthM;
      apertures.push({ from: opening.offsetM, to: end, bottom: opening.sillHeightM,
        top: opening.sillHeightM + opening.heightM });
      if (opening.openingKind !== "window") {
        const id = openingHostId(wall.proposalId, opening.openingId);
        hosts.set(id, "opening");
        openingSizes.set(id, { widthM: opening.widthM, heightM: opening.heightM,
          door: opening.openingKind === "door" });
      }
    }
  }
  return items.filter(entry => {
    // Saved drafts cannot bypass surface compatibility or source-host binding.
    if (hosts.get(entry.hostId) !== entry.target) return false;
    const item = getCatalogueItem(entry.itemId);
    if (!item || !item.targets.includes(entry.target) ||
        (entry.target === "opening" && openingFitMessage(item, openingSizes.get(entry.hostId)))) return false;
    if (entry.target === "roof" && (!Array.isArray(entry.normal) || entry.normal.length !== 3 ||
        !entry.normal.every(Number.isFinite) || entry.normal[1] <= 0.001)) return false;
    if (item.visual.kind === "timber" && !timberFitsWall(item.visual, entry.point, entry.turn, wallSections.get(entry.hostId)))
      return false;
    if (makesWorktop(item)) hosts.set(worktopId(entry.id), "worktop");
    return true;
  });
}

export type ItemScheduleRow = {
  itemId: string; name: string; category: string; placements: number;
};

export function itemSchedule(items: readonly PlacedItem[]): ItemScheduleRow[] {
  const rows = new Map<string, ItemScheduleRow>();
  for (const placement of items) {
    const choice = getCatalogueItem(placement.itemId);
    if (!choice) continue;
    const row = rows.get(choice.id);
    if (row) row.placements++;
    else rows.set(choice.id, { itemId: choice.id, name: choice.label,
      category: catalogueGroupLabel(choice.group), placements: 1 });
  }
  return [...rows.values()].sort((a, b) => a.category.localeCompare(b.category) || a.name.localeCompare(b.name));
}

export function itemScheduleCsv(rows: ItemScheduleRow[]) {
  const quote = (value: string) => '"' + value.replaceAll('"', '""') + '"';
  return ["Category,Item,Selections", ...rows.map(row => [
    quote(row.category), quote(row.name), String(row.placements),
  ].join(","))].join("\r\n") + "\r\n";
}
