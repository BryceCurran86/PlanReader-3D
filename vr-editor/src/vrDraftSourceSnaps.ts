/**
 * Source evidence is eligible only as read-only snap guidance. Never write
 * anchors to source DTOs or turn a snap into commercial quantity authority.
 */
import type { SceneManifest } from "./types.ts";
import type { PlanPoint } from "./buildPlacement.ts";

export type SourceSnapAnchor = {point:PlanPoint;objectId:string};
export function verifiedSourceWallAnchors(
  scene: SceneManifest, levelId: string | null, visible?: ReadonlySet<string>,
): SourceSnapAnchor[] {
  if (!levelId) return [];
  const found: SourceSnapAnchor[] = [];
  for (const row of scene.objects) {
    const g = row.geometry;
    if (row.objectType !== "wall" || row.levelId !== levelId ||
      row.renderState !== "verified" || !row.canonicalObjectId ||
      !row.source.sourceFileId || row.unresolvedIssues.length > 0 ||
      !g || (g.kind !== "wallFace" && g.kind !== "wallLine") ||
      (visible && !visible.has(row.objectId))) continue;
    for (const point of [g.start,g.end]) {
      if (point.length === 2 && point.every(v => Number.isFinite(v) && Math.abs(v) <= 10000)) {
        found.push({point:[...point],objectId:row.objectId});
      }
    }
  }
  return found;
}
