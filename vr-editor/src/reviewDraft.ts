/** Noncommercial, immutable desktop/WebXR what-if workbench.
 * None of these values are authenticated corrections, priced finishes or quantities.
 * Never write the model/ledger from this module.
 */
import type { EditorObject, SceneManifest } from "./types";
import { FINISH_SWATCHES, visualStudyAllowed } from "./finishStudy.ts";
import type { FinishSwatch } from "./finishStudy";

export interface WallDraft {
  objectId: string;
  objectRevision: string;
  swatch: FinishSwatch | null;
  heightM: number | null; // cosmetic ghost height; NOT a measured wall quantity
}
export interface DraftHistory {
  scopeKey: string;
  drafts: WallDraft[];
  past: WallDraft[][];
  future: WallDraft[][];
}
export type DraftChange = { swatch?: FinishSwatch | null; heightM?: number | null };
const MAX_DRAFTS = 500;
const MAX_HISTORY = 30;
const MAX_IMPORT_BYTES = 256 * 1024;

export function scopeKey(manifest: SceneManifest): string {
  const s = manifest.scope;
  return JSON.stringify([
    s.workspaceId, s.projectId, s.documentId, s.revisionId, s.snapshotId,
    s.sourceSha256, s.modelRevision,
  ]);
}
export function freshDrafts(manifest: SceneManifest): DraftHistory {
  return { scopeKey: scopeKey(manifest), drafts: [], past: [], future: [] };
}
function objectFor(manifest: SceneManifest, id: string): EditorObject | null {
  return manifest.objects.find(o => o.objectId === id) ?? null;
}
function allowedHeight(row: EditorObject | null): boolean {
  return visualStudyAllowed(row) && !!row && row.geometry?.kind === "wallFace";
}
function validSwatch(value: unknown): value is FinishSwatch {
  return typeof value === "string" && FINISH_SWATCHES.some(s => s.id === value);
}
function ensureCurrent(state: DraftHistory, scene: SceneManifest): boolean {
  return state.scopeKey === scopeKey(scene);
}
export function applyDraft(
  state: DraftHistory, scene: SceneManifest, id: string, delta: DraftChange,
): DraftHistory {
  // Fail closed on stale scene or object revision; never carry drafts between plans.
  if (!ensureCurrent(state, scene)) return freshDrafts(scene);
  const row = objectFor(scene, id);
  if (!allowedHeight(row) || !row?.objectRevision) return state;
  if (delta.swatch !== undefined && delta.swatch !== null && !validSwatch(delta.swatch))
    return state;
  if (delta.heightM !== undefined && delta.heightM !== null &&
      (typeof delta.heightM !== "number" || !Number.isFinite(delta.heightM) ||
       delta.heightM <= 0 || delta.heightM > 20)) return state;
  const previous = state.drafts.find(d => d.objectId === id);
  const next: WallDraft = {
    objectId: id,
    objectRevision: row.objectRevision,
    swatch: delta.swatch !== undefined ? delta.swatch : previous?.swatch ?? null,
    heightM: delta.heightM !== undefined ? delta.heightM : previous?.heightM ?? null,
  };
  const filtered = state.drafts.filter(d => d.objectId !== id);
  const drafts = (next.swatch === null && next.heightM === null)
    ? filtered : [...filtered, next].sort((a, b) => a.objectId.localeCompare(b.objectId));
  if (drafts.length > MAX_DRAFTS || JSON.stringify(drafts) === JSON.stringify(state.drafts))
    return state;
  return {
    ...state, drafts,
    past: [...state.past.slice(-(MAX_HISTORY - 1)), state.drafts],
    future: [],
  };
}
export function applyLevelSwatch(
  state: DraftHistory, scene: SceneManifest, level: string, swatch: FinishSwatch | null,
): DraftHistory {
  if (!ensureCurrent(state, scene)) return freshDrafts(scene);
  if (swatch !== null && !validSwatch(swatch)) return state;
  // Restrict to explicit level; no ambiguous "all" mass application.
  if (!level || level === "all") return state;
  const eligible = scene.objects.filter(o => o.levelId === level && allowedHeight(o) && !!o.objectRevision);
  if (!eligible.length || eligible.length > MAX_DRAFTS) return state;
  const selected = new Map(state.drafts.map(d => [d.objectId, d]));
  for (const row of eligible) {
    const before = selected.get(row.objectId);
    const next: WallDraft = {
      objectId: row.objectId, objectRevision: row.objectRevision,
      swatch, heightM: before?.heightM ?? null,
    };
    if (next.swatch === null && next.heightM === null) selected.delete(row.objectId);
    else selected.set(row.objectId, next);
  }
  if (selected.size > MAX_DRAFTS) return state;
  const drafts = [...selected.values()].sort((a, b) => a.objectId.localeCompare(b.objectId));
  if (JSON.stringify(drafts) === JSON.stringify(state.drafts)) return state;
  return {
    ...state, drafts, past: [...state.past.slice(-(MAX_HISTORY - 1)), state.drafts], future: [],
  };
}
export function undoDraft(state: DraftHistory): DraftHistory {
  if (!state.past.length) return state;
  return {
    ...state, drafts: state.past[state.past.length - 1],
    past: state.past.slice(0, -1),
    future: [...state.future, state.drafts].slice(-MAX_HISTORY),
  };
}
export function redoDraft(state: DraftHistory): DraftHistory {
  if (!state.future.length) return state;
  return {
    ...state, drafts: state.future[state.future.length - 1],
    past: [...state.past, state.drafts].slice(-MAX_HISTORY),
    future: state.future.slice(0, -1),
  };
}
export function resetDraft(state: DraftHistory): DraftHistory {
  if (!state.drafts.length) return state;
  return { ...state, drafts: [], past: [...state.past.slice(-(MAX_HISTORY - 1)), state.drafts], future: [] };
}
export function safeDrafts(state: DraftHistory, scene: SceneManifest): WallDraft[] {
  if (!ensureCurrent(state, scene)) return [];
  return state.drafts.filter(d => {
    const row = objectFor(scene, d.objectId);
    return allowedHeight(row) && row?.objectRevision === d.objectRevision &&
      (d.swatch === null || validSwatch(d.swatch)) &&
      (d.heightM === null ||
        (Number.isFinite(d.heightM) && d.heightM > 0 && d.heightM <= 20));
  });
}
export function draftHeight(row: EditorObject, state: DraftHistory, scene: SceneManifest): number | null {
  return safeDrafts(state, scene).find(d => d.objectId === row.objectId)?.heightM ?? null;
}
export function exportDrafts(state: DraftHistory, scene: SceneManifest): string {
  if (!ensureCurrent(state, scene)) throw new Error("stale_scene_scope");
  const data = {
    schemaVersion: "planreader-local-vr-study-1",
    scopeKey: scopeKey(scene), reviewOnly: true,
    changes: safeDrafts(state, scene),
  };
  const text = JSON.stringify(data, null, 2);
  if (new TextEncoder().encode(text).byteLength > MAX_IMPORT_BYTES)
    throw new Error("local_study_export_too_large");
  return text;
}
export function importDrafts(raw: string, scene: SceneManifest): DraftHistory {
  if (new TextEncoder().encode(raw).byteLength > MAX_IMPORT_BYTES)
    throw new Error("local_study_import_too_large");
  const data: unknown = JSON.parse(raw);
  if (!data || typeof data !== "object" || Array.isArray(data))
    throw new Error("local_study_not_an_object");
  const o = data as Record<string, unknown>;
  if (Object.keys(o).sort().join(",") !== "changes,reviewOnly,schemaVersion,scopeKey" ||
      o.schemaVersion !== "planreader-local-vr-study-1" ||
      o.reviewOnly !== true || o.scopeKey !== scopeKey(scene) ||
      !Array.isArray(o.changes) || o.changes.length > MAX_DRAFTS)
    throw new Error("local_study_scope_or_schema_mismatch");
  const seen = new Set<string>();
  let next = freshDrafts(scene);
  for (const item of o.changes) {
    if (!item || typeof item !== "object" || Array.isArray(item))
      throw new Error("invalid_local_study_change");
    const d = item as Record<string, unknown>;
    if (Object.keys(d).sort().join(",") !== "heightM,objectId,objectRevision,swatch" ||
        typeof d.objectId !== "string" || typeof d.objectRevision !== "string" ||
        seen.has(d.objectId) || (d.swatch !== null && !validSwatch(d.swatch)) ||
        (d.heightM !== null && (typeof d.heightM !== "number" ||
          !Number.isFinite(d.heightM) || d.heightM <= 0 || d.heightM > 20)))
      throw new Error("invalid_local_study_change");
    const row = objectFor(scene, d.objectId);
    if (!allowedHeight(row) || row?.objectRevision !== d.objectRevision)
      throw new Error("local_study_object_revision_mismatch");
    seen.add(d.objectId);
    next = applyDraft(next, scene, d.objectId, {
      swatch: d.swatch as FinishSwatch | null,
      heightM: d.heightM as number | null,
    });
  }
  // Import is a fresh noncommercial session, not prior authenticated history.
  return { ...next, past: [], future: [] };
}
export function diffSummary(state: DraftHistory, scene: SceneManifest): string[] {
  return safeDrafts(state, scene).map(d => {
    const row = objectFor(scene, d.objectId);
    const sourceHeight = row?.geometry?.kind === "wallFace" ? row.geometry.heightM : null;
    const swatch = FINISH_SWATCHES.find(s => s.id === d.swatch)?.label ?? "unchanged";
    const height = d.heightM !== null && sourceHeight !== null
      ? `illustrative height ${sourceHeight.toFixed(2)} → ${d.heightM.toFixed(2)} m`
      : "height unchanged";
    return `${d.objectId}: ${swatch}; ${height}; source revision ${d.objectRevision}`;
  });
}
