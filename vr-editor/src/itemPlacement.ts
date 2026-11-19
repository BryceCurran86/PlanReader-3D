import { catalogueGroupLabel, getCatalogueItem } from "./itemCatalogue.ts";
import type { CatalogueItem, ItemTarget } from "./itemCatalogue.ts";
import { openingFits, planLength, validWallLength } from "./buildPlacement.ts";
import type { WallVisual } from "./buildPlacement.ts";
import type { SceneManifest } from "./types.ts";

export type Vector = [number, number, number];
export type ItemHit = {
  hostId: string;
  target: ItemTarget;
  point: Vector;
  normal: Vector;
  side: 1 | -1;
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

export function itemGuide(item: CatalogueItem) {
  const target = item.targets;
  if (target.includes("wall") && target.includes("ceiling")) return "Aim at a wall or ceiling.";
  switch (target[0]) {
    case "wall": return "Aim at a wall face.";
    case "floor": return "Aim at a floor.";
    case "ceiling": return "Aim at the underside of a ceiling.";
    case "opening": return "Aim at a door or frame you drafted.";
    case "worktop": return "Aim at a worktop. You can place a vanity or base cabinet first.";
  }
}

function surfaceSlot(placement: PlacedItem, item: CatalogueItem) {
  const visual = item.visual;
  if (visual.kind === "fixture") return null;
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
  if (hit.target === "worktop" && !draft.items.some(entry => {
    const parent = getCatalogueItem(entry.itemId);
    return worktopId(entry.id) === hit.hostId && parent && makesWorktop(parent);
  })) return draft;
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
  const hosts = new Set<string>();
  for (const row of manifest.objects) {
    const shape = row.geometry;
    if (row.objectType === "wall" && shape?.kind === "wallFace" && shape.heightM > 0 &&
        planLength(shape.start, shape.end) > 0.000001) hosts.add(makeItemHostId("wall", row.objectId));
  }
  for (const surface of manifest.sourceSurfaces ?? []) {
    if (surface.kind === "floor" || surface.kind === "ceiling") hosts.add(makeItemHostId(surface.kind, surface.surfaceId));
  }
  if (demo) for (const room of ["west", "east"]) {
    hosts.add(makeItemHostId("floor", "demo-" + room));
    hosts.add(makeItemHostId("ceiling", "demo-" + room));
  }
  const distinct = new Map(walls.map(wall => [wall.proposalId, wall]));
  for (const wall of distinct.values()) {
    if (!validWallLength(planLength(wall.start, wall.end)) || wall.heightM <= 0) continue;
    hosts.add(makeItemHostId("draft-wall", wall.proposalId));
    const sorted = (wall.openings ?? []).filter(opening => openingFits(wall, opening))
      .sort((a, b) => a.offsetM - b.offsetM);
    let end = 0;
    for (const opening of sorted) {
      if (opening.offsetM < end - 0.000001) continue;
      end = opening.offsetM + opening.widthM;
      if (opening.openingKind !== "window") hosts.add(openingHostId(wall.proposalId, opening.openingId));
    }
  }
  return items.filter(entry => {
    if (!hosts.has(entry.hostId)) return false;
    const item = getCatalogueItem(entry.itemId);
    if (item && makesWorktop(item)) hosts.add(worktopId(entry.id));
    return !!item;
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
