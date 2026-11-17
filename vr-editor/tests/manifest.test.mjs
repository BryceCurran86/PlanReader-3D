import test from "node:test";
import assert from "node:assert/strict";
import { isSceneManifest } from "../src/types.ts";

function scene() {
  return {
    schemaVersion: "1.0.0",
    scope: {
      workspaceId: "w1", projectId: "p1", documentId: "d1",
      revisionId: "r1", snapshotId: "s1",
      sourceSha256: "a".repeat(64), modelRevision: 0,
    },
    coordinateSystem: {
      unit: "metres", sourceToModelTransform: null,
      renderOrigin: [0, 0, 0],
    },
    readOnly: true,
    commercialQuantityPublicationAllowed: false,
    objects: [
      {
        objectId: "W1", canonicalObjectId: "canonical-W1", objectType: "wall",
        levelId: "ground", objectRevision: "hash1", authority: "review_required",
        renderState: "review",
        geometry: {
          kind: "wallFace", start: [0, 0], end: [4, 0], heightM: 2.4,
        },
        dimensions: { lengthM: 4, heightM: 2.4 },
        source: {
          sourceFileId: "doc-1", page: 1, sheet: "A100",
          sourceRegion: "floor", originalGeometryRef: "path-101",
          currentGeometryRef: "wall-W1",
        },
        quantityLinks: [], unresolvedIssues: [], canEdit: false,
      },
    ],
  };
}

test("original-shaped read-only scene is accepted", () => {
  assert.equal(isSceneManifest(scene()), true);
});

test("bad or nonfinite third world-origin coordinate rejects scene", () => {
  for (const origin of [[0, 0, Infinity], [0, 0, NaN], [0, 0],
                        [0, 0, 0, 99], [0, 0, "0"]]) {
    const value = scene();
    value.coordinateSystem.renderOrigin = origin;
    assert.equal(isSceneManifest(value), false, JSON.stringify(origin));
  }
});

test("verified flag cannot contradict unresolved issues", () => {
  const good = scene();
  good.objects[0].renderState = "verified";
  assert.equal(isSceneManifest(good), true);
  good.objects[0].unresolvedIssues = ["missing_native_wall_authority"];
  assert.equal(isSceneManifest(good), false);
});

test("geometry for a room cannot be spoofed as a source wall", () => {
  const data = scene();
  data.objects[0].objectType = "room";
  assert.equal(isSceneManifest(data), false);
});

test("invalid and nonfinite source pages are rejected", () => {
  for (const page of [NaN, Infinity, -1, 0.2, true]) {
    const data = scene();
    data.objects[0].source.page = page;
    assert.equal(isSceneManifest(data), false);
  }
});

test("no writable or commercial payload may enter browser viewer", () => {
  const a = scene();
  a.objects[0].canEdit = true;
  assert.equal(isSceneManifest(a), false);
  const b = scene();
  b.commercialQuantityPublicationAllowed = true;
  assert.equal(isSceneManifest(b), false);
  const c = scene();
  c.readOnly = false;
  assert.equal(isSceneManifest(c), false);
});

test("duplicate canonical-view object ID cannot silently multiply quantity links", () => {
  const data = scene();
  data.objects.push({ ...data.objects[0] });
  assert.equal(isSceneManifest(data), false);
});

test("nonfinite wall geometry does not enter Three scene", () => {
  const bad = scene();
  bad.objects[0].geometry.end = [Infinity, 5];
  assert.equal(isSceneManifest(bad), false);
  const badHeight = scene();
  badHeight.objects[0].geometry.heightM = Number.NaN;
  assert.equal(isSceneManifest(badHeight), false);
});
