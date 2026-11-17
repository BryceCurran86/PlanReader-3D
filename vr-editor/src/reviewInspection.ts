/** Source-safe 3D/VR inspection. All controls are *presentation* state. */
import type { EditorObject, SceneManifest } from "./types";

export type ReviewFilter = "all" | "verified" | "review" | "source-lines";
export type CameraView = "isometric" | "plan" | "north" | "east";
export type FocusTarget = "scene" | "selected";
export interface InspectionSettings {
  reviewFilter: ReviewFilter;
  search: string;
  isolateSelected: boolean;
  showGrid: boolean;
  showShadows: boolean;
  showLabels: boolean;
  showGhosts: boolean;
  showStatusColours: boolean;
}
export const DEFAULT_INSPECTION: Readonly<InspectionSettings> = {
  reviewFilter: "all", search: "", isolateSelected: false,
  showGrid: true, showShadows: true, showLabels: true,
  showGhosts: true, showStatusColours: true,
};
export function safeQuery(input: string): string {
  return input.trim().toLocaleLowerCase().slice(0, 128);
}
export function matchesSourceFilter(row: EditorObject, filter: ReviewFilter): boolean {
  if (filter === "all") return true;
  const verified = row.renderState === "verified" && row.unresolvedIssues.length === 0;
  if (filter === "verified") return verified;
  if (filter === "review") return !verified;
  return row.geometry?.kind === "wallLine";
}
export function filterEvidence(
  scene: SceneManifest, level: string, selectedId: string | null,
  settings: InspectionSettings,
): EditorObject[] {
  const q = safeQuery(settings.search);
  return scene.objects.filter(row => {
    if (level !== "all" && row.levelId !== level) return false;
    if (!matchesSourceFilter(row, settings.reviewFilter)) return false;
    if (settings.isolateSelected && row.objectId !== selectedId) return false;
    return !q || [row.objectId, row.canonicalObjectId ?? "",
      row.source.sheet ?? "", row.source.originalGeometryRef ?? ""]
      .some(value => value.toLocaleLowerCase().includes(q));
  });
}
export function nextReview(
  rows: readonly EditorObject[], current: string | null, direction: 1 | -1,
): string | null {
  const waiting = rows.filter(row =>
    row.renderState !== "verified" || row.unresolvedIssues.length > 0);
  if (!waiting.length) return null;
  const index = waiting.findIndex(row => row.objectId === current);
  if (index === -1) return direction === 1
    ? waiting[0].objectId : waiting[waiting.length - 1].objectId;
  return waiting[(index + direction + waiting.length) % waiting.length].objectId;
}
export function summarizeEvidence(rows: readonly EditorObject[]) {
  return rows.reduce((summary, row) => {
    summary.total++;
    if (row.geometry?.kind === "wallFace") summary.faces++;
    else if (row.geometry?.kind === "wallLine") summary.lines++;
    else summary.withoutDisplayGeometry++;
    if (row.renderState === "verified" && !row.unresolvedIssues.length) summary.verified++;
    else summary.review++;
    if (row.canonicalObjectId) summary.canonical++;
    return summary;
  }, { total: 0, faces: 0, lines: 0, withoutDisplayGeometry: 0,
    verified: 0, review: 0, canonical: 0 });
}
export function sourceSheets(rows: readonly EditorObject[]): string[] {
  return [...new Set(rows.map(row => row.source.sheet)
    .filter((sheet): sheet is string => typeof sheet === "string" && !!sheet))]
    .sort();
}
export function bySheet(rows: readonly EditorObject[], sheet: string): EditorObject[] {
  return sheet ? rows.filter(row => row.source.sheet === sheet) : [...rows];
}
