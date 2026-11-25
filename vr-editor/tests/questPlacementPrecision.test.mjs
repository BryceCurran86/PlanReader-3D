import test from "node:test";
import assert from "node:assert/strict";
import { Ray, Vector3 } from "three";
import { EMPTY_BUILD, STARTING_SIZES, snapDraftWallPoint } from "../src/buildPlacement.ts";
import { aimBuild, beginDraftGesture, draftGesturePreview } from "../src/buildScene.ts";

const wall = {
  proposalId: "local-wall", scopeKey: "test", levelId: "ground",
  start: [0, 0], end: [4, 0], heightM: 2.4, openings: [],
};
const drafts = { ...EMPTY_BUILD, walls: [wall] };
const down = (x, z) => new Ray(new Vector3(x, 4, z), new Vector3(0, -1, 0));
const towardsWall = () => new Ray(new Vector3(2, 1.2, 2), new Vector3(0, 0, -1));

test("magnetic wall snapping chooses local wall corners before 50mm grid", () => {
  const hit = snapDraftWallPoint(drafts, "ground", [4.13, 0.07]);
  assert.deepEqual(hit, { point: [4, 0], kind: "corner" });
  assert.deepEqual(snapDraftWallPoint(drafts, "upper", [4.13, 0.07]),
    { point: [4.15, 0.05], kind: "grid" });
  assert.equal(snapDraftWallPoint(drafts, "ground", [Infinity, 0]), null);
});

test("wall ends align orthogonally with start and retain free 50mm drafting", () => {
  assert.deepEqual(snapDraftWallPoint(drafts, "ground", [4.08, 2.27], [4, 0]),
    { point: [4, 2.25], kind: "straight" });
  assert.deepEqual(snapDraftWallPoint(drafts, "ground", [6.42, 0.09], [4, 0]),
    { point: [6.4, 0], kind: "straight" });
  assert.deepEqual(snapDraftWallPoint(drafts, "ground", [5.36, 2.17], [4, 0]),
    { point: [5.35, 2.15], kind: "grid" });
});

test("two-click Quest wall placement previews and places the same snapped coordinate", () => {
  const startAim = aimBuild({ ...drafts, tool: "wall" }, "ground", STARTING_SIZES, down(4.13, 0.07));
  assert.deepEqual(startAim.hit.point, [4, 0]);
  assert.match(startAim.hint, /corner snap/);
  const pending = { ...drafts, tool: "wall", start: { levelId: "ground", point: startAim.hit.point } };
  const endAim = aimBuild(pending, "ground", STARTING_SIZES, down(4.08, 2.27));
  assert.deepEqual(endAim.hit.point, [4, 2.25]);
  assert.match(endAim.hint, /2250 mm.*straight/);
  assert.equal(endAim.valid, true);
});

test("trigger-drag wall drawing uses the same snapped coordinates as click drawing", () => {
  const edit = { ...drafts, tool: "wall" };
  const gesture = beginDraftGesture(edit, "ground", down(4.13, 0.07));
  assert.deepEqual(gesture.from, [4, 0]);
  const preview = draftGesturePreview(gesture, STARTING_SIZES, down(4.08, 2.27), edit);
  assert.deepEqual(preview.action.from, [4, 0]);
  assert.deepEqual(preview.action.to, [4, 2.25]);
  assert.match(preview.aim.hint, /2250 mm.*straight/);
});

test("Quest can pick vertical draft walls and drag by hand motion without floor ray", () => {
  const edit = { ...drafts, tool: "move" };
  const ray = towardsWall();
  const gesture = beginDraftGesture(edit, "ground", ray);
  assert.equal(gesture?.kind, "wall");
  assert.equal(gesture?.previous, wall);
  assert.deepEqual(gesture?.from, [2, 0]);
  gesture.fromController = [2, 2];
  const preview = draftGesturePreview(gesture, STARTING_SIZES, ray, edit, [2.32, 2.08]);
  assert.equal(preview?.action?.kind, "adjust");
  assert.deepEqual(preview.action.wall.start, [0.3, 0.1]);
  assert.deepEqual(preview.action.wall.end, [4.3, 0.1]);
  assert.deepEqual(wall.start, [0, 0]); // never mutate original draft/source
});
