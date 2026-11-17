import { useRef, useState } from "react";
import type { EditorObject, SceneManifest } from "./types";
import {
  applyDraft, applyLevelSwatch, diffSummary, exportDrafts, freshDrafts,
  importDrafts, redoDraft, resetDraft, safeDrafts, undoDraft,
} from "./reviewDraft";
import type { DraftHistory } from "./reviewDraft";
import { FINISH_SWATCHES, visualStudyAllowed } from "./finishStudy";
import type { FinishSwatch } from "./finishStudy";

type Props = {
  scene: SceneManifest;
  selected: EditorObject | null;
  selectedLevel: string;
  state: DraftHistory;
  onChange: (next: DraftHistory) => void;
};
export function ReviewWorkbench({ scene, selected, selectedLevel, state, onChange }: Props) {
  const [heightText, setHeightText] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const importFile = useRef<HTMLInputElement>(null);
  const drafts = safeDrafts(state, scene);
  const current = drafts.find(d => d.objectId === selected?.objectId);
  const eligible = visualStudyAllowed(selected);
  const swatch = current?.swatch ?? "";
  const height = current?.heightM;
  const summaries = diffSummary(state, scene);

  function updateSwatch(value: string) {
    if (!selected || !eligible) return;
    if (value && !FINISH_SWATCHES.some(s => s.id === value)) return;
    onChange(applyDraft(state, scene, selected.objectId, { swatch: value ? value as FinishSwatch : null }));
    setMessage(null);
  }
  function proposeHeight() {
    if (!selected || !eligible || !heightText.trim()) return;
    const value = Number(heightText);
    if (!Number.isFinite(value) || value <= 0 || value > 20) {
      setMessage("Study height must be a finite positive number up to 20 m.");
      return;
    }
    onChange(applyDraft(state, scene, selected.objectId, { heightM: value }));
    setMessage("Local visual height only — no source measurement or price updated.");
  }
  async function readFile(file: File | undefined) {
    if (!file) return;
    try {
      if (file.size > 256 * 1024) throw new Error("Review file exceeds 256 KB.");
      const next = importDrafts(await file.text(), scene);
      onChange(next);
      setMessage("Local study imported for the exact current source snapshot only.");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not import this review file");
    }
  }
  function download() {
    try {
      const payload = exportDrafts(state, scene);
      const blob = new Blob([payload], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "planreader-local-vr-review.json";
      link.click();
      URL.revokeObjectURL(url);
      setMessage("Downloaded local REVIEW draft. Not an approved edit or quote.");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not export review");
    }
  }
  return (
    <div className="preview-section" aria-label="VR what-if review workbench">
      <span className="eyebrow">VR WHAT-IF WORKBENCH · LOCAL ONLY</span>
      <p className="muted">Visual experiments are pinned to this document, source SHA, model revision and snapshot. Never used to issue quantities or cost.</p>
      {eligible && selected ? (
        <>
          <label htmlFor="draft-finish">Wall visual finish study</label>
          <select id="draft-finish" value={swatch} onChange={e => updateSwatch(e.target.value)}>
            <option value="">Original review appearance</option>
            {FINISH_SWATCHES.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
          <label htmlFor="draft-height">Illustrative wall height (metres; unmeasured)</label>
          <input id="draft-height" type="number" min="0.01" max="20" step="0.01"
            placeholder={selected.geometry?.kind === "wallFace"
              ? `Original ${selected.geometry.heightM.toFixed(2)} m` : "Height"}
            value={heightText} onChange={e => setHeightText(e.target.value)} />
          <button type="button" onClick={proposeHeight}>Preview height as ghost wall</button>
          {height !== null && height !== undefined && (
            <button type="button" onClick={() => {
              onChange(applyDraft(state, scene, selected.objectId, { heightM: null }));
              setHeightText("");
            }}>Reset illustrative height</button>
          )}
        </>
      ) : <p className="muted">Select a wall face with documented height to create a visual proposal. Unknown-height lines remain lines.</p>}
      <label htmlFor="draft-level">Apply visual swatch to this explicit level</label>
      <div id="draft-level" className="muted">Current level: {selectedLevel === "all" ? "Choose one level first" : selectedLevel}</div>
      <div className="draft-swatches">
        {FINISH_SWATCHES.map(s => <button type="button" key={s.id} disabled={selectedLevel === "all"}
          onClick={() => onChange(applyLevelSwatch(state, scene, selectedLevel, s.id))}>
          {s.label}
        </button>)}
      </div>
      <p className="muted">Bulk operations are bounded to 500 existing wall faces; no new geometry is created.</p>
      <div className="draft-actions">
        <button type="button" disabled={!state.past.length}
          onClick={() => onChange(undoDraft(state))}>Undo</button>
        <button type="button" disabled={!state.future.length}
          onClick={() => onChange(redoDraft(state))}>Redo</button>
        <button type="button" disabled={!drafts.length}
          onClick={() => onChange(resetDraft(state))}>Clear all studies</button>
      </div>
      <strong className="muted">Local review changes: {drafts.length} / 500</strong>
      {summaries.length > 0 && (
        <div className="draft-diff" aria-label="Changes compared with source model">
          <strong>Before / proposed visual-only review</strong>
          <ul>{summaries.slice(0, 30).map((line, i) => <li key={i}>{line}</li>)}</ul>
          {summaries.length > 30 && <p>Showing first 30 of {summaries.length} draft changes.</p>}
        </div>
      )}
      <div className="draft-actions">
        <button type="button" onClick={download}>Export local review JSON</button>
        <button type="button" onClick={() => importFile.current?.click()}>Import review JSON</button>
        <input ref={importFile} aria-label="Import local review JSON" type="file"
          accept=".json,application/json" style={{ display: "none" }}
          onChange={e => { void readFile(e.target.files?.[0]); e.currentTarget.value = ""; }} />
      </div>
      {message && <p role="status" className="muted">{message}</p>}
      <p className="muted">For actual quantity impact, use the authenticated correction preview separately. No local VR draft generates a price, a correction receipt or an approval.</p>
    </div>
  );
}
