import test from "node:test";
import assert from "node:assert/strict";
import { verifyPreviewResponse } from "../src/previewProtocol.ts";

const request = {
  commandId: "c1", targetObjectId: "wall-1",
  targetRevisionHash: "before-1",
};
function response() {
  return {
    accepted: true, validationState: "valid_preview_only",
    commandId: "c1", targetObjectId: "wall-1",
    previousObjectRevision: "before-1",
    previewObjectRevision: "after-1",
    requiresApproval: true, persisted: false,
    commercialPublicationAllowed: false, blockingReasons: [],
    quantityImpacts: [{
      target: "wall_gross_area", status: "recalculated",
      oldValue: 9.6, proposedValue: 10.8,
      unit: "m²", reason: null,
    }],
  };
}
test("matching current preview can be displayed as proposal only", () => {
  const validated = verifyPreviewResponse(response(), request);
  assert.equal(validated.persisted, false);
  assert.equal(validated.requiresApproval, true);
  assert.equal(validated.quantityImpacts[0].proposedValue, 10.8);
});
test("stale or cross-object HTTP replies cannot masquerade as current preview", () => {
  for (const [key, value] of [
    ["commandId", "old-command"], ["targetObjectId", "other-wall"],
    ["previousObjectRevision", "superseded-hash"],
  ]) {
    const data = response();
    data[key] = value;
    assert.throws(() => verifyPreviewResponse(data, request), /does not match/);
  }
});
test("server cannot report persistence, approval or commercial publication", () => {
  for (const [key, value] of [
    ["accepted", false], ["validationState", "approved"],
    ["requiresApproval", false], ["persisted", true],
    ["commercialPublicationAllowed", true],
  ]) {
    const data = response();
    data[key] = value;
    assert.throws(() => verifyPreviewResponse(data, request), /invalid approval/);
  }
});
test("quantity impacts must be finite numeric or unresolved, never unsafe JSON", () => {
  for (const value of ["9.5", NaN, Infinity, -Infinity, undefined]) {
    const data = response();
    data.quantityImpacts[0].proposedValue = value;
    assert.throws(() => verifyPreviewResponse(data, request), /Malformed quantity impact/);
  }
  const unresolved = response();
  unresolved.quantityImpacts[0].proposedValue = null;
  assert.equal(verifyPreviewResponse(unresolved, request).quantityImpacts[0].proposedValue, null);
});
test("oversized, malformed and conflicting preview impact reports rejected", () => {
  const big = response();
  big.quantityImpacts = Array(501).fill(big.quantityImpacts[0]);
  assert.throws(() => verifyPreviewResponse(big, request), /Malformed quantity preview result/);
  const blocked = response();
  blocked.blockingReasons = ["source_conflict"];
  assert.throws(() => verifyPreviewResponse(blocked, request), /Malformed quantity preview result/);
  assert.throws(() => verifyPreviewResponse([], request), /Malformed quantity preview response/);
});
