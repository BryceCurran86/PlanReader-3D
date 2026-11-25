/**
 * Reversible, unapproved VR draft edits. All dimensions here are explicitly
 * entered millimetres, never a substitute for a source-authenticated quantity.
 */
import { openingFits, planLength, validEditedWall } from "./buildPlacement.ts";
import type { PlacedWall, PlanPoint } from "./buildPlacement.ts";
import type { WallAdditionOpening } from "./wallAdditionProtocol.ts";

const metric = (mm: number, minMm: number, maxMm: number) =>
  Number.isInteger(mm) && mm >= minMm && mm <= maxMm ? mm / 1000 : null;
const mmPoint = (x: number, z: number): PlanPoint =>
  [Math.round(x * 1000) / 1000, Math.round(z * 1000) / 1000];

export type ExactWallField = "length" | "height" | "x" | "z";
export function exactDraftWall(wall: PlacedWall, field: ExactWallField, valueMm: number): PlacedWall | null {
  const value = metric(valueMm, field === "length" || field === "height" ? 50 : -10000000,
    field === "length" ? 200000 : field === "height" ? 20000 : 10000000);
  if (value === null) return null;
  let updated: PlacedWall;
  if (field === "height") updated = { ...wall, heightM: value };
  else if (field === "x" || field === "z") {
    const axis = field === "x" ? 0 : 1;
    const delta = value - wall.start[axis];
    const start = mmPoint(wall.start[0] + (axis === 0 ? delta : 0),
      wall.start[1] + (axis === 1 ? delta : 0));
    const end = mmPoint(wall.end[0] + (axis === 0 ? delta : 0),
      wall.end[1] + (axis === 1 ? delta : 0));
    updated = { ...wall, start, end };
  } else {
    const oldLength = planLength(wall.start, wall.end);
    if (!Number.isFinite(oldLength) || oldLength < 0.05) return null;
    const end = mmPoint(wall.start[0] + (wall.end[0] - wall.start[0]) * value / oldLength,
      wall.start[1] + (wall.end[1] - wall.start[1]) * value / oldLength);
    updated = { ...wall, end };
    if (Math.abs(planLength(updated.start, updated.end) - value) > 0.001) return null;
  }
  return validEditedWall(updated) &&
    [...updated.start, ...updated.end].every(x => Number.isFinite(x) && Math.abs(x) <= 10000)
    ? updated : null;
}

export type OpeningField = "offset" | "width" | "height" | "sill";
export function exactDraftOpening(
  wall: PlacedWall, openingId: string, field: OpeningField, valueMm: number,
): PlacedWall | null {
  const value = metric(valueMm, field === "width" || field === "height" ? 50 : 0, 200000);
  if (value === null) return null;
  const previous = wall.openings.find(opening => opening.openingId === openingId);
  if (!previous) return null;
  const map: Record<OpeningField, keyof WallAdditionOpening> = {
    offset: "offsetM", width: "widthM", height: "heightM", sill: "sillHeightM",
  };
  const changed = { ...previous, [map[field]]: value };
  if (!openingFits(wall, changed)) return null;
  if (wall.openings.some(other => other.openingId !== openingId &&
      Math.min(other.offsetM + other.widthM, changed.offsetM + changed.widthM) -
        Math.max(other.offsetM, changed.offsetM) > 0.000001)) return null;
  const openings = wall.openings.map(entry => entry.openingId === openingId ? changed : entry);
  const updated = { ...wall, openings };
  return validEditedWall(updated) ? updated : null;
}
