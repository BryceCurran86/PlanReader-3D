import { BUILD_TOOLS, planLength, STARTING_SIZES } from "./buildPlacement";
import type { BuildAction, BuildSizes, BuildState } from "./buildPlacement";
import { OPENING_DRAG_TYPE } from "./constructionStages";

type Props = {
  state: BuildState;
  sizes: BuildSizes;
  levelId: string | null;
  layoutEnabled: boolean;
  onAction: (action: BuildAction) => void;
  onSizes: (sizes: BuildSizes) => void;
  onReview: (proposalId: string) => void;
  hint: string;
  catalogueOpen: boolean;
  onCatalogueToggle: () => void;
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;
  onDone: () => void;
  busy: boolean;
  undoLabel: string;
};

export function BuildTools({ state, sizes, levelId, layoutEnabled, onAction, onSizes, onReview,
  hint, catalogueOpen, onCatalogueToggle, canUndo, canRedo, onUndo, onRedo, onDone, busy, undoLabel }: Props) {
  const walls = state.walls.filter(wall => !levelId || wall.levelId === levelId);
  function sizeInput(key: keyof BuildSizes, label: string) {
    const mm = Math.round((sizes[key] ?? STARTING_SIZES[key] ?? sizes.wallHeightM) * 1000);
    return <label>{label}
      <input type="number" min={key === "windowSillM" ? 0 : 50} max={key.endsWith("idthM") ? 200000 : 20000}
        key={mm} step={1} defaultValue={mm} onBlur={event => {
          const input = event.currentTarget;
          if (!input.value || !input.validity.valid) {
            input.value = String(mm);
            return;
          }
          onSizes({ ...sizes, [key]: input.valueAsNumber / 1000 });
        }}/>
    </label>;
  }
  return <section className="build-tools" aria-label="Editing tools">
    <div className="build-actions">
      <div className="tool-group" aria-label="Draw and edit draft geometry" role="group">
        {BUILD_TOOLS.map(({ id, label }) => {
          const isOpening = id === "door" || id === "frame" || id === "window";
          const available = !!levelId && layoutEnabled && (!isOpening || walls.length > 0) &&
            (id !== "opening-move" || walls.some(wall=>wall.openings.length>0)) &&
            ((id !== "move" && id !== "stretch") || walls.length > 0 ||
              state.ceilings.some(ceiling => ceiling.levelId === levelId));
          return <button key={id} type="button" className="build-tool" disabled={!available}
            title={isOpening && !walls.length ? "Draw a draft wall first" : undefined}
            aria-pressed={state.tool === id} draggable={available && isOpening}
            onDragStart={event => {
              if (!available || !isOpening) return;
              event.dataTransfer.setData(OPENING_DRAG_TYPE, id);
              event.dataTransfer.effectAllowed = "copy";
              if (state.tool !== id) onAction({ kind: "tool", tool: id });
            }}
            onClick={() => onAction({ kind: "tool", tool: id })}>{id === "frame" ? "Open frame" : label}</button>;
        })}
      </div>
      <div className="tool-group" role="group" aria-label="Items and editing history">
        <button type="button" aria-expanded={catalogueOpen} aria-controls="item-catalogue"
          onClick={onCatalogueToggle}>Items</button>
        <button type="button" disabled={!canUndo} title={"Undo " + undoLabel} onClick={onUndo}>Undo</button>
        <button type="button" disabled={!canRedo} title={"Redo " + undoLabel} onClick={onRedo}>Redo</button>
        <button type="button" disabled={!busy} title="Finish editing · Esc" onClick={onDone}>Done</button>
      </div>
    </div>
    <p className="build-hint" id="editor-instructions">{hint}</p>
    <div className="build-options">
      <details>
        <summary>Placement sizes</summary>
        <div className="build-sizes">
          {sizeInput("wallHeightM", "Wall height (mm)")}
          {sizeInput("ceilingHeightM", "Ceiling height (mm)")}
          {sizeInput("widthM", "Door or frame width (mm)")}
          {sizeInput("heightM", "Door or frame height (mm)")}
          {sizeInput("windowWidthM", "Window width (mm)")}
          {sizeInput("windowHeightM", "Window height (mm)")}
          {sizeInput("windowSillM", "Window sill (mm)")}
        </div>
      </details>
      {walls.length > 0 && <details>
        <summary>Draft walls ({walls.length})</summary>
        <ul>{walls.map((wall, index) => <li key={wall.proposalId}>
          <button type="button" onClick={() => onReview(wall.proposalId)}>
            Review wall {index + 1} · {planLength(wall.start, wall.end).toFixed(2)} m
            {wall.openings.length > 0 && " · " + wall.openings.length + " openings"}
          </button>
        </li>)}</ul>
      </details>}
    </div>
  </section>;
}
