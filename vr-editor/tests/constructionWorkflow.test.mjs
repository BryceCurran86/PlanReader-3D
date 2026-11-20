import test from "node:test";
import assert from "node:assert/strict";
import { Ray, Vector3 } from "three";
import { EMPTY_BUILD, STARTING_SIZES, updateBuild } from "../src/buildPlacement.ts";
import { beginDraftGesture, draftGesturePreview } from "../src/buildScene.ts";
import { buildMenuLayout, EMPTY_ITEM_BROWSER } from "../src/catalogueMenu.ts";
import { ITEM_CATALOGUE } from "../src/itemCatalogue.ts";
import { showConstructionItem, showConstructionSurface } from "../src/constructionStages.ts";
import { nearestRoofEdge, roofEdges } from "../src/roofComponents.ts";
import { catalogueQuantityOwner, verifyCataloguePrice } from "../src/cataloguePricing.ts";

const level = "ground";
const act = (state, action) => updateBuild(state, action, "snapshot", level, STARTING_SIZES);
const fromAbove = (x, z) => new Ray(new Vector3(x, 8, z), new Vector3(0, -1, 0));

test("one drag draws a snapped wall, and stretching an opening host preserves fit", () => {
  let state = act(EMPTY_BUILD, { kind: "tool", tool: "wall" });
  const drag = beginDraftGesture(state, level, fromAbove(0, 0));
  const preview = draftGesturePreview(drag, STARTING_SIZES, fromAbove(5.019, 0));
  state = act(state, { ...preview.action, id: "wall" });
  assert.deepEqual(state.walls[0].end, [5, 0]);
  assert.equal(state.history.length, 1);
  state = act(state, { kind: "tool", tool: "door" });
  state = act(state, { kind: "place", id: "door", hit: { kind: "opening", levelId: level,
    proposalId: "wall", point: [4, 0] } });
  assert.equal(state.walls[0].openings.length, 1);
  state = act(state, { kind: "tool", tool: "stretch" });
  const stretch = beginDraftGesture(state, level, fromAbove(5, 0));
  assert.equal(draftGesturePreview(stretch, STARTING_SIZES, fromAbove(3, 0)).action, null);
  const expanded = draftGesturePreview(stretch, STARTING_SIZES, fromAbove(6, 0));
  assert.equal(act(state, expanded.action).walls[0].openings[0].offsetM, state.walls[0].openings[0].offsetM);
});

test("ceiling drag and stretch edit only the draft and Undo restores the original footprint", () => {
  let state = act(EMPTY_BUILD, { kind: "tool", tool: "ceiling" });
  state = act(state, { kind: "drag", levelId: level, from: [0, 0], to: [3, 2], id: "ceiling" });
  state = act(state, { kind: "tool", tool: "stretch" });
  const drag = beginDraftGesture(state, level, fromAbove(3, 2));
  const resize = draftGesturePreview(drag, STARTING_SIZES, fromAbove(4, 5));
  assert.equal(resize.aim.line.length, 5);
  const changed = act(state, resize.action);
  assert.deepEqual(changed.ceilings[0].end, [4, 5]);
  assert.deepEqual(act(changed, { kind: "undo" }).ceilings, state.ceilings);
});

test("construction views hide concealed fittings and keep all five modes accessible in VR", () => {
  const air = ITEM_CATALOGUE.find(item => item.group === "air-conditioning");
  const roof = ITEM_CATALOGUE.find(item => item.group === "roof-components");
  assert.ok(air && roof);
  assert.equal(showConstructionItem("finished", air), false);
  assert.equal(showConstructionItem("rough-in", air), true);
  assert.equal(showConstructionItem("rough-in", roof), false);
  assert.equal(showConstructionItem("lock-up", roof), true);
  assert.equal(showConstructionSurface("slab", "floor"), true);
  assert.equal(showConstructionSurface("slab"), false);
  const menu = buildMenuLayout(EMPTY_BUILD, level, EMPTY_ITEM_BROWSER, undefined, false, 0, "", "slab", true);
  assert.deepEqual(menu.buttons.map(button => button.action.stage).filter(Boolean),
    ["finished", "slab", "framing", "rough-in", "lock-up"]);
});

test("roof accessory targets use shared geometry and ignore internal triangulation seams", () => {
  const a = [0, 0, 0], b = [4, 0, 0], c = [4, 1, 2], d = [0, 1, 2];
  const e = [0, 0, 4], f = [4, 0, 4];
  const surfaces = [
    { kind: "roof", surfaceId: "front", vertices: [a,b,c,a,c,d] },
    { kind: "roof", surfaceId: "back", vertices: [d,c,f,d,f,e] },
  ];
  const edges = roofEdges(surfaces);
  const gutter = ITEM_CATALOGUE.find(item => item.label.startsWith("Quad gutter")).visual;
  const cap = ITEM_CATALOGUE.find(item => item.label.startsWith("Ridge capping")).visual;
  assert.equal(edges.get("front").length, 4);
  assert.equal(nearestRoofEdge(edges.get("front"), gutter, [1, 0, 0.02]).kind, "eave");
  assert.equal(nearestRoofEdge(edges.get("front"), gutter, [1, 1, 2]), undefined);
  assert.equal(nearestRoofEdge(edges.get("front"), cap, [1, 1, 2]).key,
    nearestRoofEdge(edges.get("back"), cap, [1, 1, 2]).key);
});

test("live material pricing requires a source host and rejects mismatched item replies", () => {
  const row = { objectId: "wall", objectType: "wall", canonicalObjectId: "source-wall",
    objectRevision: "revision", renderState: "verified", quantityLinks: ["wall-net-area"] };
  assert.equal(catalogueQuantityOwner({ objects: [row] }, { target: "wall", hostId: "draft-wall:draft" }), undefined);
  assert.equal(catalogueQuantityOwner({ objects: [row] }, { target: "wall", hostId: "wall:wall" }), row);
  const request = { requestId: "request", quantityId: "wall-net-area", catalogueItemId: "sage" };
  const response = { ...request, accepted: true, previewOnly: true, commercialPublicationAllowed: false,
    currency: "AUD", quantity: "9.6", unit: "m2", priceIncTax: "12.00", rateKey: "rate",
    rateBookRevision: "r1", bindingEvidenceIds: ["bind"], rateEvidenceIds: ["rate-evidence"] };
  assert.equal(verifyCataloguePrice(response, request).priceIncTax, "12.00");
  assert.throws(() => verifyCataloguePrice({ ...response, catalogueItemId: "different" }, request));
});
