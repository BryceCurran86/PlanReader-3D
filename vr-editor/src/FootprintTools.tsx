import { useState } from "react";
import { footprintDepth, footprintWidth, resizeFromDimensions } from "./footprintResize";
import type { FootprintAnchor, FootprintBounds } from "./footprintResize";

export function FootprintTools({ box, changed, hint, onApply, onReset, onDone }: {
  box: FootprintBounds; changed: boolean; hint: string;
  onApply: (bounds: FootprintBounds | null) => void; onReset: () => void; onDone: () => void;
}) {
  const [anchor, setAnchor] = useState<FootprintAnchor>("top-left");
  const width = (footprintWidth(box) * 1000).toFixed(0);
  const depth = (footprintDepth(box) * 1000).toFixed(0);
  return <section className="footprint-tools" aria-label="Draft footprint">
    <strong>Draft footprint</strong>
    <form onSubmit={event => {
      event.preventDefault();
      const data = new FormData(event.currentTarget);
      onApply(resizeFromDimensions(box, Number(data.get("width")) / 1000, Number(data.get("depth")) / 1000, anchor));
    }}>
      <label>Width (mm) <input key={width} name="width" type="number" min={50} step="1" defaultValue={width} required /></label>
      <label>Depth (mm) <input key={depth} name="depth" type="number" min={50} step="1" defaultValue={depth} required /></label>
      <label>Keep fixed
        <select value={anchor} onChange={event => setAnchor(event.currentTarget.value as FootprintAnchor)}>
          <option value="top-left">Top left</option><option value="top-right">Top right</option>
          <option value="bottom-left">Bottom left</option><option value="bottom-right">Bottom right</option>
          <option value="centre">Centre</option>
        </select>
      </label>
      <button type="submit">Resize</button>
      <button type="button" disabled={!changed} onClick={onReset}>Reset footprint</button>
      <button type="button" onClick={onDone}>Done</button>
    </form>
    <p role="status">{hint || "Drag one of four green corners or four gold edge handles, or enter dimensions. Edge handles move one side only."}</p>
  </section>;
}
