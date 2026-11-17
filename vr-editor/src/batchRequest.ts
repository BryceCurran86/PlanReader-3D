/** Construct bounded source/revision-pinned VR height previews.
 * This is a suggestion-to-preview bridge, NOT a write/publish or pricing path.
 */
import type { SceneManifest } from "./types";
import type { DraftHistory } from "./reviewDraft";
import { safeDrafts } from "./reviewDraft.ts";

export interface BatchCommand {
  commandId: string;
  idempotencyKey: string;
  workspaceId: string;
  projectId: string;
  documentId: string;
  revisionId: string;
  snapshotId: string;
  sourceSha256: string;
  baseModelRevision: number;
  targetObjectId: string;
  targetRevisionHash: string;
  targetCanonicalId: string;
  commandType: "SET_WALL_HEIGHT";
  payload: { newValue: number };
  reason: string;
}
export interface BatchPreviewRequest { commands: BatchCommand[] }
const MAX = 20;

export function eligibleHeightTargets(scene: SceneManifest, drafts: DraftHistory): string[] {
  return safeDrafts(drafts, scene)
    .filter(d => d.heightM !== null)
    .filter(d => scene.objects.some(o =>
      o.objectId === d.objectId && !!o.canonicalObjectId &&
      o.objectRevision === d.objectRevision &&
      o.geometry?.kind === "wallFace"))
    .map(d => d.objectId).sort();
}
export function makeHeightBatch(
  scene: SceneManifest, drafts: DraftHistory, reason: string,
  makeId: () => string,
): BatchPreviewRequest {
  const targets = eligibleHeightTargets(scene, drafts);
  if (!targets.length || targets.length > MAX)
    throw new Error("Choose 1–20 canonical wall heights with current revisions.");
  if (reason.trim().length < 8 || reason.trim().length > 1024)
    throw new Error("Provide an evidence-based reason of 8–1024 characters.");
  if (typeof makeId !== "function") throw new Error("Missing unique command ID generator");
  const commands = targets.map(id => {
    const row = scene.objects.find(o => o.objectId === id)!;
    const change = safeDrafts(drafts, scene).find(d => d.objectId === id)!;
    const s = scene.scope;
    return {
      commandId: makeId(), idempotencyKey: makeId(),
      workspaceId: s.workspaceId, projectId: s.projectId,
      documentId: s.documentId, revisionId: s.revisionId,
      snapshotId: s.snapshotId, sourceSha256: s.sourceSha256,
      baseModelRevision: s.modelRevision, targetObjectId: id,
      targetRevisionHash: row.objectRevision,
      targetCanonicalId: row.canonicalObjectId!,
      commandType: "SET_WALL_HEIGHT" as const,
      payload: { newValue: change.heightM! },
      reason: reason.trim(),
    };
  });
  const ids = commands.flatMap(c => [c.commandId, c.idempotencyKey]);
  if (new Set(ids).size !== ids.length ||
      ids.some(id => !/^[A-Za-z0-9_.:-]{1,128}$/.test(id)))
    throw new Error("Command IDs must be unique bounded tokens.");
  return { commands };
}
