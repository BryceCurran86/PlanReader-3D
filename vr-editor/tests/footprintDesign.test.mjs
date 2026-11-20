import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import {
  footprintBounds, footprintProjection, originalPlacement, previewFootprint, projectCeiling,
  projectPlacement, projectVertex, projectWall, resizeFromCorner, resizeFromDimensions,
} from "../src/footprintResize.ts";
import { createFootprintGizmo, footprintGeometry, renderFootprintGeometry } from "../src/footprintScene.ts";
import { EMPTY_BUILD, STARTING_SIZES, updateBuild } from "../src/buildPlacement.ts";
import { displayWallDraft } from "../src/buildScene.ts";
import { createCatalogueScene, draftCatalogueHosts, draftSiteHost } from "../src/catalogueScene.ts";
import { EMPTY_ITEM_BROWSER, buildMenuLayout } from "../src/catalogueMenu.ts";
import { EXTENSION_CATALOGUE } from "../src/extensionCatalogue.ts";
import { currentItemPlacements, emptyItemDraft, openingHostId, placeItem, SITE_HOST_ID } from "../src/itemPlacement.ts";

const original = { minX: 0, maxX: 8, minZ: 0, maxZ: 5 };
const draft = { ...original, maxX: 10, maxZ: 7 };
const projection = footprintProjection(original, draft);
const door = { openingId: "door", openingKind: "door", widthM: 0.9, heightM: 2.1, sillHeightM: 0, offsetM: 3 };
const wall = { proposalId: "wall", levelId: "ground", scopeKey: "scope",
  start: [0, 0], end: [8, 0], heightM: 2.4, openings: [door] };

test("footprint resize anchors the opposite corner, preserves roof heights and keeps opening sizes", () => {
  assert.deepEqual(resizeFromCorner(original, "bottom-right", [9.999, 7.01]), draft);
  assert.deepEqual(resizeFromDimensions(original, 10, 7, "bottom-right"),
    { minX: -2, maxX: 8, minZ: -2, maxZ: 5 });
  assert.deepEqual(projectVertex([4, 3.7, 5], projection), [5, 3.7, 7]);
  const resized = projectWall(wall, projection);
  assert.deepEqual(resized.end, [10, 0]);
  assert.equal(resized.openings[0].widthM, 0.9);
  assert.equal(resized.openings[0].heightM, 2.1);
  assert.equal(resized.openings[0].offsetM, 3.8625);
  assert.equal(wall.end[0], 8);
  assert.equal(wall.openings[0].offsetM, 3);
  assert.deepEqual(projectCeiling({ ...wall, end: [8, 5] }, projection).end, [10, 7]);
  assert.equal(previewFootprint({objects: []}, original, {...original, maxX: 0.5}, [wall], []).projection, null);
});

test("floor extent or displayed wall fallback is separate from roof overhang", () => {
  const row = { objectId: "room", renderState: "verified", geometry: null };
  const scene = { objects: [row], sourceSurfaces: [
    { objectId: "room", kind: "floor", vertices: [[0,0,0],[8,0,0],[8,0,5],[0,0,5]] },
    { objectId: "room", kind: "roof", vertices: [[-1,2,-1],[9,2,-1],[9,2,6]] },
  ] };
  assert.deepEqual(footprintBounds(scene, false), original);
  const wallScene = { objects: [
    { geometry: { start: [0,0], end: [8,0] }, renderState: "review" },
    { geometry: { start: [8,0], end: [8,5] }, renderState: "review" },
  ] };
  assert.deepEqual(footprintBounds(wallScene, false), original);
});

test("stable render buffers update floors, walls and sloped roof triangles and restore exactly", () => {
  const points = new Float32Array([0, 0, 0, 8, 2.5, 0, 8, 3.5, 5]);
  const geometry = new THREE.BufferGeometry().setAttribute("position", new THREE.BufferAttribute(points.slice(), 3));
  const mesh = new THREE.Mesh(geometry);
  const source = footprintGeometry([mesh]);
  renderFootprintGeometry(source, projection);
  assert.deepEqual(Array.from(geometry.attributes.position.array), [0,0,0,10,2.5,0,10,3.5,7]);
  renderFootprintGeometry(source, null);
  assert.deepEqual(Array.from(geometry.attributes.position.array), Array.from(points));
  const ray = new THREE.Raycaster(new THREE.Vector3(10, 6, 7), new THREE.Vector3(0,-1,0));
  const handle = createFootprintGizmo(new THREE.Scene());
  handle.show(draft);
  assert.equal(handle.pick(ray), "bottom-right");
  handle.show(null);
  assert.equal(handle.pick(ray), null);
});

test("host-relative items move, sites and worktops stay independent, and placed points round-trip", () => {
  const placement = { id: "item", itemId: "item", hostId: "draft-wall:wall", target: "wall",
    side: 1, point: [4,1,0], normal: [0,0,1], turn: 0, anchor: { kind: "wall", offsetM: 4 } };
  const moved = projectPlacement(placement, projection);
  assert.deepEqual(moved.point, [5,1,0]);
  const stored = originalPlacement({ ...moved, anchor: {kind: "wall", offsetM: 5} }, projection, wall);
  assert.deepEqual(stored, placement);
  for (const [target, hostId] of [["site", SITE_HOST_ID], ["worktop", "worktop:basin"]]) {
    const item = { ...placement, target, hostId };
    assert.equal(projectPlacement(item, projection), item);
  }
});

test("window tool, slider styles and drapery use the correct opening and separate slots", () => {
  const set = (state, action) => updateBuild(state, action, "scope", "ground", STARTING_SIZES);
  const start = set(EMPTY_BUILD, {kind: "tool", tool: "wall"});
  const built = set(start, {kind: "drag", from: [0,0], to: [8,0], id: "wall", levelId: "ground"});
  const windowTool = set(built, {kind: "tool", tool: "window"});
  const windowed = set(windowTool, {kind: "place", id: "win", hit: {
    kind: "opening", levelId: "ground", proposalId: "wall", point: [2,0],
  }});
  const opening = windowed.walls[0].openings[0];
  assert.equal(opening.openingKind, "window");
  assert.equal(opening.widthM, 1.2);
  assert.equal(opening.sillHeightM, 0.9);
  const group = displayWallDraft(windowed.walls[0]);
  const scene = new THREE.Scene();
  scene.add(group);
  const view = createCatalogueScene(scene);
  const hosts = draftCatalogueHosts(windowed.walls[0], group);
  view.sync([draftSiteHost(scene)], hosts, []);
  const ray = new THREE.Raycaster(new THREE.Vector3(2, 1.4, -2), new THREE.Vector3(0,0,1));
  const choice = groupName => EXTENSION_CATALOGUE.find(item => item.group === groupName);
  const windowStyle = choice("windows"), drape = choice("window-coverings");
  const result = view.candidate(ray, windowStyle);
  assert.ok(result.hit);
  assert.equal(result.hit.hostId, openingHostId("wall", "win"));
  assert.equal(view.candidate(ray, choice("sliding-doors")).hit, null);
  const selected = placeItem(placeItem(emptyItemDraft("scope"), "scope", "window", windowStyle.id, result.hit, 0),
    "scope", "drape", drape.id, result.hit, 0);
  const current = currentItemPlacements(selected.items, {objects: []}, windowed.walls, false);
  assert.equal(current.length, 2);
  view.sync([], hosts, current);
  assert.equal(hosts.find(host => host.target === "opening").mesh.children.length, 2);
});

test("site items find their own draft ground and the headset menu exposes footprint controls", () => {
  const scene = new THREE.Scene();
  const site = draftSiteHost(scene);
  const view = createCatalogueScene(scene);
  view.sync([site], [], []);
  const pool = EXTENSION_CATALOGUE.find(item => item.group === "pools");
  const hit = view.candidate(new THREE.Raycaster(new THREE.Vector3(12,6,4), new THREE.Vector3(0,-1,0)), pool).hit;
  assert.equal(hit.hostId, SITE_HOST_ID);
  const layout = buildMenuLayout(EMPTY_BUILD, "ground", EMPTY_ITEM_BROWSER, undefined, false, 0, "",
    "finished", false, {available: true, enabled: true, changed: true});
  assert.deepEqual(layout.buttons.filter(button => button.action.area === "footprint").map(button => button.label),
    ["Done resizing", "Reset size"]);
});
