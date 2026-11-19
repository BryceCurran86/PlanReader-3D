import { activeStart, BUILD_TOOLS } from "./buildPlacement.ts";
import type { BuildAction, BuildState } from "./buildPlacement.ts";
import { CATALOGUE_GROUPS, ITEM_CATALOGUE, itemCanRotate } from "./itemCatalogue.ts";
import type { CatalogueItem } from "./itemCatalogue.ts";

export type ItemAction =
  | { kind: "choose"; itemId: string }
  | { kind: "undo" | "done" | "rotate" };
type BrowseAction = { kind: "toggle" } | { kind: "category" | "page"; step: number };
export type MenuAction =
  | { area: "build"; action: BuildAction }
  | { area: "items"; action: ItemAction }
  | { area: "browse"; action: BrowseAction };

export type MenuButton = {
  label: string; x: number; y: number; w: number; h: number;
  action: MenuAction; active?: boolean; disabled?: boolean; swatch?: number;
};
export type MenuLayout = { title: string; width: number; height: number;
  note: string; subtitle?: string; buttons: MenuButton[] };
type BrowserState = { open: boolean; category: number; page: number };
export const EMPTY_ITEM_BROWSER: BrowserState = { open: false, category: 0, page: 0 };
const optionsByGroup = CATALOGUE_GROUPS.map(([key]) => ITEM_CATALOGUE.filter(entry => entry.group === key));
const PER_PAGE = 6;
const WIDTH = 980;
const maxPage = (category: number) => Math.max(0, Math.ceil(optionsByGroup[category].length / PER_PAGE) - 1);

export function updateItemBrowser(state: BrowserState, action: BrowseAction): BrowserState {
  if (action.kind === "toggle") return { ...state, open: !state.open };
  if (action.kind === "category") return { ...state, page: 0,
    category: (state.category + action.step + CATALOGUE_GROUPS.length) % CATALOGUE_GROUPS.length };
  return { ...state, page: Math.max(0, Math.min(maxPage(state.category), state.page + action.step)) };
}

export function buildMenuLayout(
  build: BuildState, levelId: string | null, browser: BrowserState,
  item: CatalogueItem | undefined, itemUndo: boolean, turn: number, hint: string,
): MenuLayout {
  const buttons: MenuButton[] = [];
  function add(label: string, x: number, y: number, w: number, h: number, action: MenuAction,
    settings: { active?: boolean; disabled?: boolean; swatch?: number } = {}) {
    buttons.push({ label, x, y, w, h, action, ...settings });
  }
  const browse = (action: BrowseAction): MenuAction => ({ area: "browse", action });
  const items = (action: ItemAction): MenuAction => ({ area: "items", action });
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
    add("Back", 819, 343, 141, 55, browse({ kind: "toggle" }));
    return { buttons, title: "Materials & fixtures", width: WIDTH, height: 457,
      subtitle: CATALOGUE_GROUPS[category][1] + " · " + list.length + " options",
      note: "Page " + (page + 1) + " of " + (maxPage(category) + 1) + " · Pick an item to place it." };
  }
  const actions: { label: string; target: MenuAction; active?: boolean; disabled?: boolean }[] =
    BUILD_TOOLS.map(({ id, label }) => ({ label, target: { area: "build" as const, action: { kind: "tool" as const, tool: id } },
      active: build.tool === id, disabled: !levelId }));
  actions.push(
    { label: "Items", target: browse({ kind: "toggle" }), active: !!item },
    { label: "Undo", target: item ? items({ kind: "undo" }) : { area: "build", action: { kind: "undo" } },
      disabled: item ? !itemUndo : !build.history.length && !activeStart(build, levelId) },
    { label: "Done", target: item ? items({ kind: "done" }) : { area: "build", action: { kind: "done" } },
      disabled: !item && !build.tool },
  );
  if (item && itemCanRotate(item)) actions.push({ label: "Rotate " + turn * 90 + "°", target: items({ kind: "rotate" }) });
  const stride = (WIDTH - 40) / actions.length;
  for (const [index, entry] of actions.entries()) {
    add(entry.label, 20 + stride * index, 67, stride - 9, 70, entry.target,
      { active: entry.active, disabled: entry.disabled });
  }
  return { buttons, title: item?.label ?? "Build tools", width: WIDTH, height: 228, note: hint };
}
