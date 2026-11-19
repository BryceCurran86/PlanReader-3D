import test from "node:test";
import assert from "node:assert/strict";
import { CATALOGUE_GROUPS, ITEM_CATALOGUE, searchCatalogue } from "../src/itemCatalogue.ts";
import { currentItemPlacements, emptyItemDraft, itemSchedule, itemScheduleCsv, placeItem, removeItem,
  undoItem, worktopId, openingHostId } from "../src/itemPlacement.ts";
import { buildMenuLayout, EMPTY_ITEM_BROWSER, updateItemBrowser } from "../src/catalogueMenu.ts";
import { EMPTY_BUILD } from "../src/buildPlacement.ts";

const exact = query => {
  const item = searchCatalogue(query)[0];
  assert.ok(item, query);
  return item;
};
const wall = { target: "wall", hostId: "wall:w1", side: 1, point: [2, 1, 0], normal: [0, 0, 1] };
const floor = { target: "floor", hostId: "floor:floor1", side: 1, point: [2, 0, 0], normal: [0, 1, 0] };
const item = (draft, label, hit, id) => placeItem(draft, "plan-revision", id, exact(label).id, hit, 0);
const start = () => emptyItemDraft("plan-revision");

test("catalogue covers each category with stable distinctive options and searchable profiles", () => {
  assert.ok(ITEM_CATALOGUE.length >= 1000);
  assert.equal(new Set(ITEM_CATALOGUE.map(entry => entry.id)).size, ITEM_CATALOGUE.length);
  for (const [group] of CATALOGUE_GROUPS) assert.ok(searchCatalogue("", group).length);
  assert.match(exact("moisture plasterboard 13").label, /13 mm/);
  assert.match(exact("ogee 138 skirting").label, /Ogee/);
  assert.match(exact("bullnose 66 architraves").label, /Bullnose/);
  assert.match(exact("brushed brass gooseneck").label, /Brushed brass/);
  assert.match(exact("double power point black").label, /Black/);
  assert.match(exact("porcelain tile graphite").label, /Porcelain/);
  assert.match(exact("sage satin paint").label, /Sage.*Satin/);
});

test("design choices replace a finish on one side, retain its board, and respect scope and target", () => {
  const board = item(start(), "moisture plasterboard 13", wall, "lining");
  const painted = item(board, "sage satin paint", wall, "finish");
  const replaced = item(painted, "chalk white satin", wall, "new-finish");
  assert.deepEqual(replaced.items.map(entry => entry.id), ["lining", "new-finish"]);
  assert.deepEqual(undoItem(replaced).items, painted.items);
  assert.strictEqual(item(replaced, "chalk white satin", wall, "same-finish"), replaced);
  assert.equal(item(replaced, "sage satin paint", { ...wall, side: -1 }, "reverse").items.length, 3);
  assert.strictEqual(item(replaced, "vinyl plank blond oak", wall, "wrong-surface"), replaced);
  assert.strictEqual(placeItem(replaced, "new-revision", "wrong-plan", exact("sage satin paint").id, wall, 0), replaced);
});

test("worktop tapware requires its cabinet and disappears from the schedule when the host is removed", () => {
  const worktop = { ...floor, target: "worktop", hostId: worktopId("vanity-1") };
  const blank = start();
  assert.strictEqual(item(blank, "basin mixer chrome", worktop, "tap-1"), blank);
  const cabinetry = item(start(), "vanity 600 polar", floor, "vanity-1");
  const installed = item(cabinetry, "basin mixer chrome", worktop, "tap-1");
  assert.equal(installed.items.length, 2);
  const snap = { objects: [], sourceSurfaces: [{ kind: "floor", surfaceId: "floor1" }] };
  assert.equal(currentItemPlacements(installed.items, snap, [], false).length, 2);
  assert.equal(currentItemPlacements(installed.items, { objects: [] }, [], false).length, 0);
  assert.match(itemScheduleCsv(itemSchedule(installed.items)), /"Tapware","Basin mixer · Chrome",1/);
  assert.equal(removeItem(installed, "vanity-1").items.length, 0);
});

test("every group is reachable through the headset catalogue and choosing a card arms that item", () => {
  let state = updateItemBrowser(EMPTY_ITEM_BROWSER, { kind: "toggle" });
  for (const [group, name] of CATALOGUE_GROUPS) {
    const panel = buildMenuLayout(EMPTY_BUILD, null, state, undefined, false, 0, "");
    assert.match(panel.subtitle, new RegExp(name));
    const selected = panel.buttons.find(button => button.action.area === "items" && button.action.action.kind === "choose");
    assert.ok(selected);
    assert.equal(selected.action.action.itemId, searchCatalogue("", group)[0].id);
    state = updateItemBrowser(state, { kind: "page", step: 1 });
    if (searchCatalogue("", group).length > 6) assert.equal(state.page, 1);
    state = updateItemBrowser(state, { kind: "category", step: 1 });
    assert.equal(state.page, 0);
  }
  assert.equal(state.category, 0);
});

test("the exterior selection retains its substrate and finish as separate choices on the same face", () => {
  const lined = item(start(), "fibre cement exterior sheet 9 grey", wall, "substrate");
  const clad = item(lined, "standing seam metal zinc", wall, "cladding");
  const painted = item(clad, "smooth exterior render limestone", wall, "render");
  assert.deepEqual(clad.items.map(placement => placement.id), ["substrate", "cladding"]);
  assert.deepEqual(painted.items.map(placement => placement.id), ["substrate", "render"]);
  assert.equal(exact("smooth timber decking 140 jarrah").targets[0], "floor");
  assert.equal(exact("fibre cement eaves lining charcoal").targets[0], "ceiling");
  assert.equal(exact("Square timber post 90 1800 Radiata Pine").visual.mount, "post");
  assert.equal(exact("Shiplap board Merbau").visual.profile, "shiplap");
});

test("front doors require a large enough door opening and retain one assembly through finish edits", () => {
  const id = openingHostId("w", "door");
  const hit = { ...wall, target: "opening", hostId: id, opening: { widthM: 1.5, heightM: 2.1, door: true } };
  assert.strictEqual(item(start(), "double-leaf entry Blackbutt", hit, "double").items.length, 1);
  assert.strictEqual(item(start(), "double-leaf entry", { ...hit, opening: { ...hit.opening, widthM: 0.9 } },
    "too-wide").items.length, 0);
  assert.strictEqual(item(start(), "double-leaf entry", { ...hit, opening: { ...hit.opening, door: false } },
    "wrong-kind").items.length, 0);
  const first = item(start(), "double-leaf entry Blackbutt", hit, "first");
  const second = item(first, "glazed sidelight spotted gum", { ...hit, side: -1 }, "second");
  const withFinish = item(second, "painted door leaf sage", hit, "finish");
  assert.deepEqual(withFinish.items.map(placement => placement.id), ["second", "finish"]);
  const sketch = { scopeKey: "plan-revision", proposalId: "w", levelId: "ground", start: [0, 0], end: [4, 0],
    heightM: 2.4, openings: [{ openingId: "door", openingKind: "door", sillHeightM: 0,
      offsetM: 1, widthM: 0.9, heightM: 2.1 }] };
  assert.deepEqual(currentItemPlacements(withFinish.items, { objects: [] }, [sketch], false).map(entry => entry.id),
    ["finish"]);
});
