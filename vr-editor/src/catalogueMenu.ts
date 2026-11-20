import { activeStart, BUILD_TOOLS } from "./buildPlacement.ts";
import type { BuildAction, BuildState } from "./buildPlacement.ts";
import { CATALOGUE_GROUPS, ITEM_CATALOGUE, itemCanRotate } from "./itemCatalogue.ts";
import type { CatalogueItem } from "./itemCatalogue.ts";
import { CONSTRUCTION_STAGES, stageDetails } from "./constructionStages.ts";
import type { ConstructionStage } from "./constructionStages.ts";
import type { ControlMode, HistoryAction } from "./editorControls.ts";

export type ItemAction =
  | { kind: "choose"; itemId: string }
  | { kind: "undo" | "redo" | "done" | "rotate" };
type BrowseAction = { kind: "toggle" } | { kind: "groups" } | { kind: "category" | "page" | "group-page"; step: number }
  | { kind: "choose-group"; index: number };
export type MenuAction =
  | { area: "build"; action: BuildAction }
  | { area: "items"; action: ItemAction }
  | { area: "browse"; action: BrowseAction }
  | { area: "view"; stage?: ConstructionStage }
  | { area: "footprint"; reset?: boolean }
  | { area: "history"; action: HistoryAction }
  | { area: "level"; id: string }
  | { area: "done" };

export type MenuButton = {
  label: string; x: number; y: number; w: number; h: number;
  action: MenuAction; active?: boolean; disabled?: boolean; swatch?: number;
};
export type MenuLayout = { title: string; width: number; height: number;
  note: string; subtitle?: string; buttons: MenuButton[] };
type BrowserState = { open: boolean; category: number; page: number; groups?: boolean; groupPage?: number };
export const EMPTY_ITEM_BROWSER: BrowserState = { open: false, category: 0, page: 0 };
const optionsByGroup = CATALOGUE_GROUPS.map(([key]) => ITEM_CATALOGUE.filter(entry => entry.group === key));
const PER_PAGE = 6;
const WIDTH = 980;
const GROUPS_PER_PAGE = 12;
const lastGroupPage = Math.ceil(CATALOGUE_GROUPS.length / GROUPS_PER_PAGE) - 1;
const maxPage = (category: number) => Math.max(0, Math.ceil(optionsByGroup[category].length / PER_PAGE) - 1);

export function updateItemBrowser(state: BrowserState, action: BrowseAction): BrowserState {
  if (action.kind === "toggle") return { ...state, open: !state.open, groups: false };
  if (action.kind === "groups") return { ...state, open: true, groups: true,
    groupPage: Math.floor(state.category / GROUPS_PER_PAGE) };
  if (action.kind === "choose-group") return { ...state, open: true, groups: false,
    category: action.index, page: 0 };
  if (action.kind === "group-page") return { ...state,
    groupPage: Math.max(0, Math.min(lastGroupPage, (state.groupPage ?? 0) + action.step)) };
  if (action.kind === "category") return { ...state, page: 0,
    category: (state.category + action.step + CATALOGUE_GROUPS.length) % CATALOGUE_GROUPS.length };
  return { ...state, page: Math.max(0, Math.min(maxPage(state.category), state.page + action.step)) };
}

export function buildMenuLayout(
  build: BuildState, levelId: string | null, browser: BrowserState,
  item: CatalogueItem | undefined, itemUndo: boolean, turn: number, hint: string,
  stage: ConstructionStage = "finished", viewsOpen = false,
  footprint = { available: false, enabled: false, changed: false },
  interaction?: { mode: ControlMode; canUndo: boolean; canRedo: boolean; levels?: readonly string[]; level?: string },
): MenuLayout {
  const buttons: MenuButton[] = [];
  function add(label: string, x: number, y: number, w: number, h: number, action: MenuAction,
    settings: { active?: boolean; disabled?: boolean; swatch?: number } = {}) {
    buttons.push({ label, x, y, w, h, action, ...settings });
  }
  const browse = (action: BrowseAction): MenuAction => ({ area: "browse", action });
  const items = (action: ItemAction): MenuAction => ({ area: "items", action });
  if (viewsOpen) {
    for (const [index, option] of CONSTRUCTION_STAGES.entries()) {
      add(option.label, 20 + 158 * index, 69, 147, 65,
        { area: "view", stage: option.id }, { active: stage === option.id });
    }
    add("Back", 810, 69, 150, 65, { area: "view" });
    return { buttons, title: "Construction view", width: WIDTH, height: 228,
      note: stageDetails(stage).description };
  }
  if (browser.open && browser.groups) {
    const page = browser.groupPage ?? 0;
    const start = page * GROUPS_PER_PAGE;
    for (const [index, [, label]] of CATALOGUE_GROUPS.slice(start, start + GROUPS_PER_PAGE).entries()) {
      add(label, 20 + index % 3 * 318, 67 + Math.floor(index / 3) * 62, 304, 52,
        browse({ kind: "choose-group", index: start + index }));
    }
    add("Previous", 20, 322, 153, 54, browse({ kind: "group-page", step: -1 }), { disabled: !page });
    add("Next", 184, 322, 153, 54, browse({ kind: "group-page", step: 1 }), { disabled: page === lastGroupPage });
    add("Back to tools", 755, 322, 205, 54, browse({ kind: "toggle" }));
    return { buttons, title: "Item categories", width: WIDTH, height: 430,
      note: "Categories " + (page + 1) + " of " + (lastGroupPage + 1) };
  }
  if (browser.open) {
    const { category, page } = browser;
    const list = optionsByGroup[category];
    add("‹ Category", 20, 68, 165, 55, browse({ kind: "category", step: -1 }));
    add("Category ›", 795, 68, 165, 55, browse({ kind: "category", step: 1 }));
    for (const [index, entry] of list.slice(page * PER_PAGE, (page + 1) * PER_PAGE).entries()) {
      add(entry.label, index % 2 ? 500 : 20, 139 + Math.floor(index / 2) * 65, 460, 55,
        items({ kind: "choose", itemId: entry.id }), { swatch: entry.visual.color, active: item?.id === entry.id });
    }
    add("‹ Page", 20, 343, 138, 55, browse({ kind: "page", step: -1 }), { disabled: page === 0 });
    add("Page ›", 169, 343, 138, 55, browse({ kind: "page", step: 1 }), { disabled: page >= maxPage(category) });
    if (maxPage(category) > 9) {
      add("‹‹ 5 pages", 319, 343, 143, 55, browse({ kind: "page", step: -5 }), { disabled: page === 0 });
      add("5 pages ››", 474, 343, 143, 55, browse({ kind: "page", step: 5 }), { disabled: page >= maxPage(category) });
    }
    add("Undo item", 648, 343, 160, 55, items({ kind: "undo" }), { disabled: !itemUndo });
    add("Categories", 819, 343, 141, 55, browse({ kind: "groups" }));
    return { buttons, title: "Materials & fixtures", width: WIDTH, height: 457,
      subtitle: CATALOGUE_GROUPS[category][1] + " · " + list.length + " options",
      note: "Page " + (page + 1) + " of " + (maxPage(category) + 1) + " · Pick an item to place it." };
  }
  const hasWall = build.walls.some(wall => wall.levelId === levelId);
  const canMove = hasWall || build.ceilings.some(ceiling => ceiling.levelId === levelId);
  const actions: { label: string; target: MenuAction; active?: boolean; disabled?: boolean }[] =
    BUILD_TOOLS.map(({ id, label }) => ({ label: id === "frame" ? "Open frame" : label,
      target: { area: "build", action: { kind: "tool", tool: id } },
      active: build.tool === id, disabled: !levelId || footprint.enabled || footprint.changed ||
        ((id === "door" || id === "window" || id === "frame") && !hasWall) ||
        ((id === "stretch" || id === "move") && !canMove) }));
  actions.push(
    { label: "Items", target: browse({ kind: "groups" }), active: !!item },
    { label: "View", target: { area: "view" } },
    { label: "Undo", target: interaction ? { area: "history", action: "undo" } :
      item ? items({ kind: "undo" }) : { area: "build", action: { kind: "undo" } },
      disabled: interaction ? !interaction.canUndo : item ? !itemUndo : !build.history.length && !activeStart(build, levelId) },
    { label: "Done", target: interaction ? { area: "done" } :
      item ? items({ kind: "done" }) : { area: "build", action: { kind: "done" } },
      disabled: interaction ? interaction.mode === "inspect" : !item && !build.tool },
  );
  if (interaction?.canRedo) actions.push({ label: "Redo", target: { area: "history", action: "redo" } });
  if (interaction?.levels && interaction.levels.length > 1) {
    const levels = ["all", ...interaction.levels];
    const id = levels[(levels.indexOf(interaction.level ?? "all") + 1) % levels.length];
    actions.push({ label: interaction.level === "all" ? "All levels ↻" : (interaction.level ?? "Level") + " ↻",
      target: { area: "level", id } });
  }
  if (footprint.available) actions.push({ label: footprint.enabled ? "Done resizing" : "Footprint",
    target: { area: "footprint" }, active: footprint.enabled });
  if (footprint.changed) actions.push({ label: "Reset size", target: { area: "footprint", reset: true } });
  if (item && itemCanRotate(item)) actions.push({ label: "Rotate " + turn * 90 + "°", target: items({ kind: "rotate" }) });
  const stride = (WIDTH - 40) / 6;
  for (const [index, entry] of actions.entries()) {
    add(entry.label, 20 + stride * (index % 6), 67 + Math.floor(index / 6) * 68, stride - 9, 58, entry.target,
      { active: entry.active, disabled: entry.disabled });
  }
  return { buttons, title: item?.label ?? "Build tools", width: WIDTH, height: 149 + 68 * Math.ceil(actions.length / 6), note: hint };
}
