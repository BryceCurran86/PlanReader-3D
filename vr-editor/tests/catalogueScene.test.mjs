import test from "node:test";
import assert from "node:assert/strict";
import { Raycaster, Scene, Vector3 } from "three";
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
  const ground = catalogue.target(fromAbove, vanity);
  assert.equal(ground.hostId, "floor:demo-west");
  assert.equal(catalogue.target(fromAbove, mixer), null);
  const placed = assign(start(), "cabinet1", vanity, ground);
  catalogue.sync(sample, [], placed.items);
  const countertop = catalogue.target(fromAbove, mixer);
  assert.equal(countertop.hostId, worktopId("cabinet1"));
  assert.ok(new Vector3(...countertop.normal).distanceTo(new Vector3(0, 1, 0)) < 1e-8);
  const withTap = assign(placed, "tap", mixer, countertop);
  catalogue.sync(sample, [], withTap.items);
  const cabinet = sample.find(entry => entry.id === "floor:demo-west").mesh.children[0];
  assert.ok(cabinet.children.some(part => part.children.length));
  catalogue.sync(sample, [], undoItem(placed).items);
  assert.equal(catalogue.target(fromAbove, mixer), null);
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
  const hit = catalogue.target(through, arch);
  assert.equal(hit.target, "opening");
  assert.equal(catalogue.target(through, choice("painted door leaf charcoal")), null);
  assert.equal(catalogue.target(through, choice("sage satin paint")), null);
  const installed = assign(start(), "trim", arch, hit);
  catalogue.sync([], targets, installed.items);
  const opening = targets.find(host => host.target === "opening").mesh;
  assert.equal(opening.children[0].children.length, 3);
  catalogue.sync([], targets, []);
  assert.equal(opening.children.length, 0);
});
