import type { FootprintProjection } from "./footprintResize.ts";

export type ControlMode = "inspect" | "draw" | "place" | "resize" | "wall-move" | "teleport";
export type HistoryTarget = "draw" | "place" | "resize" | "wall-move" | "source";
export type HistoryAction = "undo" | "redo";

export function activeControl(enabled: {
  resize: boolean; place: boolean; draw: boolean; wallMove: boolean; teleport: boolean;
}): ControlMode {
  if (enabled.resize) return "resize";
  if (enabled.place) return "place";
  if (enabled.draw) return "draw";
  if (enabled.wallMove) return "wall-move";
  return enabled.teleport ? "teleport" : "inspect";
}

export function historyTarget(mode: ControlMode, lastEdit: HistoryTarget, resized: boolean): HistoryTarget {
  if (mode === "draw" || mode === "place" || mode === "resize" || mode === "wall-move") return mode;
  return resized && lastEdit === "draw" ? "resize" : lastEdit;
}

export function historyShortcut(event: Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey" | "shiftKey" | "altKey">): HistoryAction | null {
  if (!(event.ctrlKey || event.metaKey) || event.altKey) return null;
  const key = event.key.toLowerCase();
  if (key === "z") return event.shiftKey ? "redo" : "undo";
  return key === "y" && !event.shiftKey ? "redo" : null;
}

export type ResizeHistory = {
  projection: FootprintProjection | null;
  past: (FootprintProjection | null)[];
  future: (FootprintProjection | null)[];
  drag: symbol | null;
};

export const EMPTY_RESIZE_HISTORY: ResizeHistory = { projection: null, past: [], future: [], drag: null };

export function recordResize<T extends ResizeHistory>(state: T, projection: FootprintProjection | null, drag?: symbol): T {
  if (projection === state.projection) return state;
  const past = drag && drag === state.drag ? state.past : [...state.past, state.projection].slice(-32);
  return { ...state, projection, past, future: [], drag: drag ?? null };
}

export function stepResize<T extends ResizeHistory>(state: T, action: HistoryAction): T {
  const from = action === "undo" ? state.past : state.future;
  if (!from.length) return state;
  const projection = from[from.length - 1];
  return action === "undo" ? { ...state, projection, past: from.slice(0, -1),
    future: [...state.future, state.projection].slice(-32), drag: null } :
    { ...state, projection, past: [...state.past, state.projection].slice(-32),
      future: from.slice(0, -1), drag: null };
}
