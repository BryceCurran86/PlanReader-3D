import test from "node:test";
import assert from "node:assert/strict";
import { activeControl, historyShortcut, historyTarget, EMPTY_RESIZE_HISTORY, recordResize, stepResize } from "../src/editorControls.ts";
import { buildMenuLayout, EMPTY_ITEM_BROWSER, updateItemBrowser } from "../src/catalogueMenu.ts";
import { EMPTY_BUILD } from "../src/buildPlacement.ts";

test("escape and history target the current mode instead of an unrelated source study", () => {
  assert.equal(activeControl({ resize: false, place: true, draw: false, wallMove: false, teleport: false }), "place");
  assert.equal(historyTarget("place", "source", false), "place");
  assert.equal(historyTarget("inspect", "draw", true), "resize");
  assert.equal(historyShortcut({ key: "Z", ctrlKey: true, metaKey: false, shiftKey: true, altKey: false }), "redo");
  assert.equal(historyShortcut({ key: "z", ctrlKey: false, metaKey: true, shiftKey: false, altKey: false }), "undo");
});
test("a footprint drag is one history step, including its last valid frame", () => {
  const phase = Symbol();
  const first = { scaleX: 1.1 }, last = { scaleX: 1.2 };
  const changed = recordResize(recordResize(EMPTY_RESIZE_HISTORY, first, phase), last, phase);
  assert.deepEqual(changed.past, [null]);
  const restored = stepResize(changed, "undo");
  assert.equal(restored.projection, null);
  assert.deepEqual(stepResize(restored, "redo").projection, last);
  assert.deepEqual(recordResize(restored, first).future, []);
});
test("headset menus expose category browsing, level switching and the same history actions", () => {
  const layout = buildMenuLayout(EMPTY_BUILD, null, EMPTY_ITEM_BROWSER, undefined, false, 0, "",
    "finished", false, undefined, { mode: "resize", canUndo: true, canRedo: true, level: "all", levels: ["Ground", "First"] });
  assert.equal(layout.buttons.find(button => button.label === "Undo").action.area, "history");
  assert.equal(layout.buttons.find(button => button.label === "Redo").action.area, "history");
  assert.equal(layout.buttons.find(button => button.action.area === "level").action.id, "Ground");
  const open = layout.buttons.find(button => button.label === "Items").action.action;
  const groups = updateItemBrowser(EMPTY_ITEM_BROWSER, open);
  const picker = buildMenuLayout(EMPTY_BUILD, "Ground", groups, undefined, false, 0, "");
  assert.equal(picker.title, "Item categories");
  const group = picker.buttons.find(button => button.label === "Paint").action.action;
  assert.equal(buildMenuLayout(EMPTY_BUILD, "Ground", updateItemBrowser(groups, group),
    undefined, false, 0, "").subtitle.startsWith("Paint"), true);
});
