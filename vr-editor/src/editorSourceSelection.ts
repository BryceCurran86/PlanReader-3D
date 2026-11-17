/** Identity for one pending correction against one selected canonical source object.
 * Scope changes MUST invalidate prior network responses, even when two objects
 * happen to share the same revision hash or have identical dimensions.
 */
import type { EditorObject, SceneManifest } from "./types.ts";

export function editorSourceSelectionKey(
  workspace: Pick<SceneManifest, "scope">,
  object: Pick<EditorObject, "objectId" | "objectRevision" | "canonicalObjectId">,
): string {
  const s = workspace.scope;
  return JSON.stringify([
    s.workspaceId, s.projectId, s.documentId, s.revisionId,
    s.snapshotId, s.sourceSha256, s.modelRevision,
    object.objectId, object.objectRevision, object.canonicalObjectId,
  ]);
}
