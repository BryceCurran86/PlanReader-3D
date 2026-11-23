import test from "node:test";
import assert from "node:assert/strict";
import { BUILD_TOOLS, EMPTY_BUILD } from "../src/buildPlacement.ts";
import { buildMenuLayout, EMPTY_ITEM_BROWSER } from "../src/catalogueMenu.ts";

function root(build = EMPTY_BUILD, canUndo = false) {
  return buildMenuLayout(build, "ground", EMPTY_ITEM_BROWSER, undefined, false, 0,
    "", "finished", false, { available: false, enabled: false, changed: false },
    { mode: "inspect", canUndo, canRedo: false, levels: ["ground"], level: "ground" });
}

test("Quest top-level tools are grouped without losing original actions", () => {
  const layout = root();
  assert.deepEqual(layout.sections?.map(section => section.label),
    ["BUILD & EDIT", "MATERIALS, VIEWS & CONTROLS"]);
  assert.equal(layout.buttons.length, BUILD_TOOLS.length + 5);
  for (const tool of BUILD_TOOLS) {
    assert.ok(layout.buttons.some(button =>
      button.action.area === "build" && button.action.action.kind === "tool" &&
      button.action.action.tool === tool.id));
  }
  for (const action of ["undo", "done"]) {
    assert.ok(layout.buttons.some(button =>
      button.action.area === "history" && button.action.action === action ||
      action === "done" && button.action.area === "done"));
  }
  const firstGroup = layout.buttons.slice(0, BUILD_TOOLS.length);
  const secondGroup = layout.buttons.slice(BUILD_TOOLS.length);
  assert.ok(firstGroup.every(button => button.y >= layout.sections[0].y));
  assert.ok(secondGroup.every(button => button.y >= layout.sections[1].y));
});

test("Quest tool ray targets fit the panel and cannot overlap", () => {
  const layout = root();
  for (const [index, button] of layout.buttons.entries()) {
    assert.ok(button.x >= 0 && button.y >= 0);
    assert.ok(button.x + button.w <= layout.width);
    assert.ok(button.y + button.h < layout.height);
    for (const other of layout.buttons.slice(index + 1)) {
      const separated = button.x + button.w <= other.x ||
        other.x + other.w <= button.x ||
        button.y + button.h <= other.y ||
        other.y + other.h <= button.y;
      assert.ok(separated, `${button.label} overlaps ${other.label}`);
    }
  }
});

test("Quest menu preserves disabled placement safeguards and undo availability", () => {
  const empty = root();
  assert.equal(empty.buttons.find(button => button.label === "Door")?.disabled, true);
  assert.equal(empty.buttons.find(button => button.label === "Undo")?.disabled, true);
  assert.equal(root(EMPTY_BUILD, true).buttons.find(button => button.label === "Undo")?.disabled, false);
  const withWall = { ...EMPTY_BUILD, walls: [{ levelId: "ground" }] };
  assert.equal(root(withWall).buttons.find(button => button.label === "Door")?.disabled, false);
});
