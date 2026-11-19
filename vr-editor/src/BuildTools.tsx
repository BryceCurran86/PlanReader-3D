import { activeStart, BUILD_TOOLS, buildGuide, planLength } from "./buildPlacement";
import type { BuildAction, BuildSizes, BuildState } from "./buildPlacement";

type Props = {
  state: BuildState;
  sizes: BuildSizes;
  levels: string[];
  levelId: string | null;
  onLevel: (id: string) => void;
  onAction: (action: BuildAction) => void;
  onSizes: (sizes: BuildSizes) => void;
  onTopView: () => void;
  onReview: (proposalId: string) => void;
  hint: string;
  catalogueOpen: boolean;
  onCatalogueToggle: () => void;
};

export function BuildTools({
  state, sizes, levels, levelId, onLevel, onAction, onSizes, onTopView, onReview, hint, catalogueOpen, onCatalogueToggle,
}: Props) {
  const walls = state.walls.filter(wall => !levelId || wall.levelId === levelId);
  function sizeInput(key: keyof BuildSizes, label: string) {
    return <label>{label}
      <input type="number" min={50} max={key === "widthM" ? 200000 : 20000} step={1}
        defaultValue={Math.round(sizes[key] * 1000)} onBlur={event => {
          const input = event.currentTarget;
          if (!input.value || !input.validity.valid) {
            input.value = String(Math.round(sizes[key] * 1000));
            return;
          }
          onSizes({ ...sizes, [key]: input.valueAsNumber / 1000 });
        }}/>
    </label>;
  }
  return <section className="build-tools" aria-label="Build tools">
    <div className="build-actions">
      {BUILD_TOOLS.map(({ id, label }) => <button key={id} type="button" className="build-tool"
        disabled={!levelId} aria-pressed={state.tool === id}
        onClick={() => onAction({ kind: "tool", tool: id })}>{label}</button>)}
      <button type="button" className="build-tool" aria-expanded={catalogueOpen}
        aria-controls="item-catalogue" onClick={onCatalogueToggle}>Items</button>
      <button type="button" disabled={!state.history.length && !activeStart(state, levelId)}
        onClick={() => onAction({ kind: "undo" })}>Undo</button>
      <button type="button" disabled={!state.tool} onClick={() => onAction({ kind: "done" })}>Done</button>
      <button type="button" onClick={onTopView}>Top view</button>
    </div>
    {levels.length > 1 && <label className="build-level">Build on level
      <select value={levelId ?? ""} onChange={event => onLevel(event.currentTarget.value)}>
        <option value="">Choose level</option>
        {levels.map(id => <option key={id}>{id}</option>)}
      </select>
    </label>}
    <p className="build-hint">{hint || (!levelId ? "Choose a source level to build on." :
      !state.tool && walls.length ? "Choose a tool or review a wall draft." : buildGuide(state, levelId))}</p>
    <div className="build-options">
      <details>
        <summary>Placement sizes</summary>
        <div className="build-sizes">
          {sizeInput("wallHeightM", "Wall height (mm)")}
          {sizeInput("widthM", "Door / frame width (mm)")}
          {sizeInput("heightM", "Door / frame height (mm)")}
        </div>
        <p>Starting sizes for new drafts. Wall points snap to 50 mm.</p>
      </details>
      {walls.length > 0 && <details open={!state.tool || undefined}>
        <summary>Review drafts ({walls.length})</summary>
        <ul>
          {walls.map((wall, index) => <li key={wall.proposalId}>
            <button type="button" onClick={() => onReview(wall.proposalId)}>
              Review wall {index + 1} · {planLength(wall.start, wall.end).toFixed(2)} m
              {wall.openings.length > 0 && " · " + wall.openings.length + " opening" + (wall.openings.length === 1 ? "" : "s")}
            </button>
          </li>)}
        </ul>
      </details>}
    </div>
  </section>;
}
