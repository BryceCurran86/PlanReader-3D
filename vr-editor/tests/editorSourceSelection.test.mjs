import test from "node:test";
import assert from "node:assert/strict";
import { editorSourceSelectionKey } from "../src/editorSourceSelection.ts";

const scope = {
  workspaceId: "workspace-a", projectId: "project-a", documentId: "drawing-a",
  revisionId: "rev-a", snapshotId: "snapshot-a",
  sourceSha256: "a".repeat(64), modelRevision: 8,
};
const object = {
  objectId: "wall-a", objectRevision: "same-hash",
  canonicalObjectId: "canonical-a",
};
const key = (s = scope, o = object) =>
  editorSourceSelectionKey({scope:s}, o);

test("exact same source and selected object keeps the same revision edit scope", () => {
  assert.equal(key(), key({...scope}, {...object}));
});

test("all source identity fields invalidate pending preview/save when changed", () => {
  for (const field of Object.keys(scope)) {
    const changed = {...scope, [field]: field === "modelRevision" ? 9 : scope[field]+"-other"};
    assert.notEqual(key(), key(changed, object), field);
  }
});

test("object selection and canonical identity invalidate even with equal revision hashes", () => {
  assert.notEqual(key(), key(scope, {...object, objectId:"wall-b"}));
  assert.notEqual(key(), key(scope, {...object, canonicalObjectId:"canonical-b"}));
  assert.notEqual(key(), key(scope, {...object, objectRevision:"changed-hash"}));
});
