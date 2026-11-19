import test from "node:test";
import assert from "node:assert/strict";
import { Ray, Vector3 } from "three";
import { EMPTY_BUILD, STARTING_SIZES, updateBuild } from "../src/buildPlacement.ts";
import { aimBuild } from "../src/buildScene.ts";
import { scopeKey } from "../src/reviewDraft.ts";
import { makeWallAdditionCommand } from "../src/wallAdditionProtocol.ts";

const scene = { scope: {
  workspaceId: "ws", projectId: "project", documentId: "doc", revisionId: "rev",
  snapshotId: "snap", sourceSha256: "a".repeat(64), modelRevision: 7,
} };
const key = scopeKey(scene);
const level = "ground";
const act = (state, action, levelId = level, scope = key) =>
  updateBuild(state, action, scope, levelId, STARTING_SIZES);
const tool = (state, name) => act(state, { kind: "tool", tool: name });
const point = (x, z, levelId = level) => ({
  kind: "place", hit: { kind: "wall", point: [x, z], levelId }, id: "wall-local",
});
const opening = (x, id = "opening-1") => ({
  kind: "place", hit: { kind: "opening", proposalId: "wall-local", point: [x, 0], levelId: level }, id,
});
const drawWall = () => act(act(tool(EMPTY_BUILD, "wall"), point(0, 0)), point(4, 0));

test("two plan points create one snapped, source-scoped wall and Undo cancels a pending point", () => {
  const start = act(tool(EMPTY_BUILD, "wall"), point(0.019, -0.031));
  assert.deepEqual(start.start.point, [0, -0.05]);
  assert.equal(start.walls.length, 0);
  assert.equal(act(start, { kind: "undo" }).start, null);
  const wallState = act(start, point(3.988, -0.031));
  assert.deepEqual(wallState.walls[0], {
    scopeKey: key, proposalId: "wall-local", start: [0, -0.05], end: [4, -0.05],
    openings: [], levelId: level, heightM: 2.4,
  });
  assert.equal(act(wallState, { kind: "undo" }).walls.length, 0);
  const other = act(start, point(4, 0, "upper"), "upper");
  assert.equal(other.walls.length, 0);
  assert.equal(other.start.levelId, "upper");
});

test("opening rays snap from above or in the headset and retain door/frame kinds for review", () => {
  const doorMode = tool(drawWall(), "door");
  const topRay = new Ray(new Vector3(1, 4, 0.04), new Vector3(0, -1, 0));
  const door = aimBuild(doorMode, level, STARTING_SIZES, topRay);
  assert.equal(door.hit.kind, "opening");
  const withDoor = act(doorMode, { kind: "place", hit: door.hit, id: "opening-door" });
  assert.equal(withDoor.walls[0].openings[0].offsetM, 0.55);
  const frameMode = tool(withDoor, "frame");
  const xrRay = new Ray(new Vector3(3, 1.3, 2), new Vector3(0, 0, -1));
  const frame = aimBuild(frameMode, level, STARTING_SIZES, xrRay);
  assert.equal(frame.hit.kind, "opening");
  const both = act(frameMode, { kind: "place", hit: frame.hit, id: "opening-frame" });
  const [wall] = both.walls;
  assert.deepEqual(makeWallAdditionCommand(scene, wall, "W01", wall.openings).openings.map(o => o.openingKind),
    ["door", "passage"]);
  assert.equal(act(both, { kind: "undo" }).walls[0].openings.length, 1);
  assert.equal(act(both, { kind: "done" }).walls[0].openings.length, 2);
});

test("opening placement respects ends, overlaps, wall height and source revision", () => {
  const doorMode = tool(drawWall(), "door");
  const installed = act(doorMode, opening(3.99));
  assert.equal(installed.walls[0].openings[0].offsetM, 3.1);
  assert.strictEqual(act(installed, opening(3.5, "overlap")), installed);
  assert.strictEqual(act(doorMode, opening(1), level, "new-scope"), doorMode);
  const ray = new Ray(new Vector3(1, 1.3, 2), new Vector3(0, 0, -1));
  const oversize = aimBuild(doorMode, level, { ...STARTING_SIZES, heightM: 3 }, ray);
  assert.equal(oversize.hit, null);
  assert.match(oversize.hint, /larger than/);
  const saved = act(installed, { kind: "saved", proposalId: "wall-local" });
  assert.equal(act(saved, { kind: "undo" }).walls.length, 0);
});
