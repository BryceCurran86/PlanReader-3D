import test from "node:test";
import assert from "node:assert/strict";
import { Box3, Raycaster, Scene, Vector3 } from "three";
import { displayWallDraft } from "../src/buildScene.ts";
import { createCatalogueScene, demoCatalogueHosts, draftCatalogueHosts } from "../src/catalogueScene.ts";
import { searchCatalogue } from "../src/itemCatalogue.ts";
import { emptyItemDraft, placeItem, undoItem, worktopId } from "../src/itemPlacement.ts";

const ray = (origin, direction) => new Raycaster(new Vector3(...origin), new Vector3(...direction));
const choice = query => searchCatalogue(query)[0];
const start = () => emptyItemDraft("project");
const assign = (draft, id, item, target) => placeItem(draft, "project", id, item.id, target, 0);

test("floor-standing fixtures generate a worktop that accepts a deck-mounted tap", () => {
  const scene = new Scene();
  const catalogue = createCatalogueScene(scene);
  const sample = demoCatalogueHosts(scene);
  scene.updateMatrixWorld(true);
  const vanity = choice("vanity 600 polar");
  const mixer = choice("basin mixer chrome");
  const fromAbove = ray([2, 5, 2], [0, -1, 0]);
  catalogue.sync(sample, [], []);
  const ground = catalogue.candidate(fromAbove, vanity).hit;
  assert.equal(ground.hostId, "floor:demo-west");
  assert.equal(catalogue.candidate(fromAbove, mixer).hit, null);
  const placed = assign(start(), "cabinet1", vanity, ground);
  catalogue.sync(sample, [], placed.items);
  const countertop = catalogue.candidate(fromAbove, mixer).hit;
  assert.equal(countertop.hostId, worktopId("cabinet1"));
  assert.ok(new Vector3(...countertop.normal).distanceTo(new Vector3(0, 1, 0)) < 1e-8);
  const withTap = assign(placed, "tap", mixer, countertop);
  catalogue.sync(sample, [], withTap.items);
  const cabinet = sample.find(entry => entry.id === "floor:demo-west").mesh.children[0];
  assert.ok(cabinet.children.some(part => part.children.length));
  catalogue.sync(sample, [], undoItem(placed).items);
  assert.equal(catalogue.candidate(fromAbove, mixer).hit, null);
});

test("a draft frame receives fitted architraves and retains the open passage for wall placement", () => {
  const scene = new Scene();
  const catalogue = createCatalogueScene(scene);
  const wall = { proposalId: "w", scopeKey: "project", levelId: "ground", start: [0, 0], end: [4, 0],
    heightM: 2.4, openings: [{ openingId: "f", openingKind: "passage", widthM: 1, heightM: 2.1,
      offsetM: 1, sillHeightM: 0 }] };
  const group = displayWallDraft(wall);
  scene.add(group);
  const targets = draftCatalogueHosts(wall, group);
  scene.updateMatrixWorld(true);
  catalogue.sync([], targets, []);
  const through = ray([1.5, 1, 2], [0, 0, -1]);
  const arch = choice("bullnose 66 architraves");
  const hit = catalogue.candidate(through, arch).hit;
  assert.equal(hit.target, "opening");
  assert.equal(catalogue.candidate(through, choice("painted door leaf charcoal")).hit, null);
  assert.equal(catalogue.candidate(through, choice("sage satin paint")).hit, null);
  const installed = assign(start(), "trim", arch, hit);
  catalogue.sync([], targets, installed.items);
  const opening = targets.find(host => host.target === "opening").mesh;
  assert.equal(opening.children[0].children.length, 3);
  catalogue.sync([], targets, []);
  assert.equal(opening.children.length, 0);
});

test("an entry assembly fits its opening and hides only its own simple leaf until undo", () => {
  const scene = new Scene();
  const catalogue = createCatalogueScene(scene);
  const wall = { proposalId: "e", scopeKey: "project", levelId: "ground", start: [0, 0], end: [5, 0],
    heightM: 2.4, openings: [
      { openingId: "wide", openingKind: "door", widthM: 1.5, heightM: 2.1, offsetM: 1, sillHeightM: 0 },
      { openingId: "single", openingKind: "door", widthM: 0.9, heightM: 2.1, offsetM: 3.5, sillHeightM: 0 },
    ] };
  const group = displayWallDraft(wall);
  scene.add(group);
  const targets = draftCatalogueHosts(wall, group);
  scene.updateMatrixWorld(true);
  catalogue.sync([], targets, []);
  const double = choice("double-leaf entry blackbutt");
  const near = ray([1.7, 1.2, 2], [0, 0, -1]);
  const narrow = ray([3.8, 1.2, 2], [0, 0, -1]);
  assert.match(catalogue.candidate(narrow, double).reason, /1420 × 2050 mm/);
  const hit = catalogue.candidate(near, double).hit;
  assert.ok(hit);
  const applied = assign(start(), "front-door", double, hit);
  catalogue.sync([], targets, applied.items);
  const wide = targets.find(target => target.opening?.size.widthM === 1.5);
  const single = targets.find(target => target.opening?.size.widthM === 0.9);
  const assembly = wide.mesh.children[0];
  assert.equal(assembly.children.filter(child => child.name === "Entry door leaf").length, 2);
  const extents = new Box3().setFromObject(assembly);
  assert.ok(Math.abs(extents.min.x - 1) < 1e-6 && Math.abs(extents.max.x - 2.5) < 1e-6);
  assert.ok(Math.abs(extents.max.y - 2.1) < 1e-6);
  assert.equal(wide.opening.reviewLeaf.visible, false);
  assert.equal(single.opening.reviewLeaf.visible, true);
  catalogue.sync([], targets, undoItem(applied).items);
  assert.equal(wide.opening.reviewLeaf.visible, true);
  assert.equal(wide.mesh.children.length, 0);
});

test("rotated timber profiles retain their dimensions and stay clear of draft openings", () => {
  const scene = new Scene();
  const catalogue = createCatalogueScene(scene);
  const wall = { proposalId: "t", scopeKey: "project", levelId: "ground", start: [0, 0], end: [4, 0],
    heightM: 2.4, openings: [{ openingId: "door", openingKind: "door", widthM: 1.2, heightM: 2.1,
      offsetM: 1.3, sillHeightM: 0 }] };
  const group = displayWallDraft(wall);
  scene.add(group);
  const targets = draftCatalogueHosts(wall, group);
  scene.updateMatrixWorld(true);
  catalogue.sync([], targets, []);
  const board = choice("shiplap board 135 900 Western Red Cedar");
  const tooClose = ray([1.07, 1, 2], [0, 0, -1]);
  assert.equal(catalogue.candidate(tooClose, board, 0).hit.target, "wall");
  assert.match(catalogue.candidate(tooClose, board, 1).reason, /clear of the wall edge or opening/);
  const room = ray([0.7, 1, 2], [0, 0, -1]);
  const { hit } = catalogue.candidate(room, board, 1);
  const placed = placeItem(start(), "project", "timber", board.id, hit, 1);
  catalogue.sync([], targets, placed.items);
  const mesh = targets.find(target => target.target === "wall").mesh.children[0];
  const dimensions = new Box3().setFromObject(mesh).getSize(new Vector3());
  assert.ok(dimensions.distanceTo(new Vector3(0.9, 0.135, 0.019)) < 1e-6);
});

test("a glazed entry leaves the glass visible while the selected face finish colours its slab", () => {
  const scene = new Scene();
  const catalogue = createCatalogueScene(scene);
  const wall = { proposalId: "glass", scopeKey: "project", levelId: "ground", start: [0, 0], end: [4, 0],
    heightM: 2.4, openings: [{ openingId: "single", openingKind: "door",
      widthM: 0.9, heightM: 2.1, offsetM: 1, sillHeightM: 0 }] };
  const group = displayWallDraft(wall);
  scene.add(group);
  const targets = draftCatalogueHosts(wall, group);
  scene.updateMatrixWorld(true);
  catalogue.sync([], targets, []);
  const entry = choice("Heritage arched-lite entry Blackbutt");
  const finish = choice("painted door leaf charcoal");
  const click = ray([1.45, 1, 2], [0, 0, -1]);
  const first = assign(start(), "entry", entry, catalogue.candidate(click, entry).hit);
  const decorated = assign(first, "entry-finish", finish, catalogue.candidate(click, finish).hit);
  catalogue.sync([], targets, decorated.items);
  const [assembly] = targets.find(target => target.target === "opening").mesh.children;
  const glass = assembly.children.find(child => child.name === "Door glazing");
  const slab = assembly.children.find(child => child.name === "Entry door leaf");
  assert.ok(glass.material.transparent && glass.material.opacity < 1);
  assert.equal(slab.material[1].color.getHex(), finish.visual.color);
});
