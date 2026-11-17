import test from "node:test";
import assert from "node:assert/strict";
import { FINISH_SWATCHES, studyColor, visualStudyAllowed } from "../src/finishStudy.ts";

function wall(kind = "wallFace") {
  return {
    objectId: "wall-1", objectType: "wall",
    geometry: kind === "wallFace"
      ? { kind, start: [0, 0], end: [3, 0], heightM: 2.5 }
      : { kind, start: [0, 0], end: [3, 0] },
    renderState: "review", canEdit: false, quantityLinks: [],
  };
}

test("visual study colours only a selected wall face", () => {
  const original = wall();
  const before = structuredClone(original);
  const chosen = { objectId: "wall-1", swatch: "sage" };
  assert.equal(visualStudyAllowed(original), true);
  assert.equal(studyColor(original, chosen), FINISH_SWATCHES.find(s => s.id === "sage").color);
  assert.equal(studyColor(original, { objectId: "other", swatch: "sage" }), null);
  assert.equal(studyColor(original, { objectId: "wall-1", swatch: "unknown" }), null);
  assert.deepEqual(original, before, "cosmetic study must not mutate source DTO");
});

test("unresolved height, line-only and non-wall objects cannot gain study panels", () => {
  assert.equal(visualStudyAllowed(wall("wallLine")), false);
  const invalid = wall(); invalid.geometry.heightM = NaN;
  assert.equal(visualStudyAllowed(invalid), false);
  const room = wall(); room.objectType = "room";
  assert.equal(visualStudyAllowed(room), false);
  assert.equal(studyColor(room, { objectId: "wall-1", swatch: "clay" }), null);
  assert.equal(visualStudyAllowed(null), false);
});

test("swatches are an explicit closed palette with no rates, finish codes or authority", () => {
  assert.equal(FINISH_SWATCHES.length, 4);
  assert.equal(new Set(FINISH_SWATCHES.map(s => s.id)).size, 4);
  for (const swatch of FINISH_SWATCHES) {
    assert.match(swatch.label, /visual only/);
    assert.deepEqual(Object.keys(swatch).sort(), ["color", "id", "label"]);
  }
});
