import { BUILD_TOOLS, planLength, STARTING_SIZES, wallAngleDegrees } from "./buildPlacement";
import type { BuildAction, BuildSizes, BuildState, WallRotationPivot } from "./buildPlacement";
import { OPENING_DRAG_TYPE } from "./constructionStages";
import { WALL_PROFILES, defaultWallAssembly, wallAssembly, wallDimensionText } from "./wallProfiles";
import type { WallProfileId } from "./wallProfiles";

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
  function sizeInput(key: Exclude<keyof BuildSizes,"wallAssembly">, label: string) {
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
      <details open><summary>Wall construction · new walls</summary>
        <label>Assembly <select value={wallAssembly(sizes.wallAssembly).profile} onChange={e=>onSizes({...sizes,wallAssembly:defaultWallAssembly(e.currentTarget.value as WallProfileId)})}>{WALL_PROFILES.map(p=><option key={p.id} value={p.id}>{p.label} · {p.thicknessMm} mm</option>)}</select></label>
        <label>Overall thickness (mm) <input type="number" min={50} max={600} step={1} value={wallAssembly(sizes.wallAssembly).thicknessMm} onChange={e=>{const n=e.currentTarget.valueAsNumber;if(Number.isInteger(n)&&n>=50&&n<=600)onSizes({...sizes,wallAssembly:{...wallAssembly(sizes.wallAssembly),thicknessMm:n}});}}/></label>
        <label>Exterior side (looking along wall start → end) <select value={wallAssembly(sizes.wallAssembly).exteriorSide} onChange={e=>onSizes({...sizes,wallAssembly:{...wallAssembly(sizes.wallAssembly),exteriorSide:e.currentTarget.value==="right"?"right":"left"}})}><option value="left">Left</option><option value="right">Right</option></select></label>
        <p>Nominal design assembly. Imported wall specifications must be verified; no structural certification.</p>
      </details>
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
            Review wall {index + 1} · {wallDimensionText(planLength(wall.start, wall.end),wall.heightM,wall.assembly)}
            {wall.openings.length > 0 && " · " + wall.openings.length + " openings"}
          </button>
          <form key={JSON.stringify([wall.start,wall.end])} onSubmit={e=>{
            e.preventDefault();const data=new FormData(e.currentTarget);
            const angle=Number(data.get("angle")),pivot=data.get("pivot") as WallRotationPivot;
            if(Number.isFinite(angle))onAction({kind:"rotate-local-wall",previous:wall,angleDeg:angle,pivot,connected:data.get("connected")==="on"});
          }}>
            <label>Wall angle (degrees, +X toward +Z)<input name="angle" type="number" step="0.1" min="0" max="360" defaultValue={Math.round(wallAngleDegrees(wall)*10)/10} required disabled={!layoutEnabled||!levelId||busy}/></label>
            <label>Fixed pivot<select name="pivot" defaultValue="start" disabled={!layoutEnabled||!levelId||busy}><option value="start">Start end</option><option value="centre">Centre</option><option value="end">Far end</option></select></label>
            <label><input type="checkbox" name="connected" defaultChecked disabled={!layoutEnabled||!levelId||busy}/> Keep adjoining walls connected</label>
            <button type="submit" disabled={!layoutEnabled||!levelId||busy}>Apply wall angle</button>
          </form>
          <p>Connected rotation adjusts neighbouring endpoints and preserves opening sizes. Invalid or unsplit junctions are rejected. Uncheck to rotate independently.</p>
          <label>Assembly <select disabled={!layoutEnabled} value={wallAssembly(wall.assembly).profile} onChange={e=>onAction({kind:"set-wall-assembly",proposalId:wall.proposalId,assembly:defaultWallAssembly(e.currentTarget.value as WallProfileId)})}>{WALL_PROFILES.map(p=><option key={p.id} value={p.id}>{p.label}</option>)}</select></label>
        </li>)}</ul>
      </details>}
    </div>
  </section>;
}
