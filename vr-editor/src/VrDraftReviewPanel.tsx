import {useRef} from "react";
import {vrDraftTakeoff,localIndicativeWallCost} from "./vrDraftTakeoff.ts";
import type {BuildState} from "./buildPlacement.ts";

type Props={build:BuildState;rate:string;onRate:(value:string)=>void;
  onSave:()=>void;onRestore:(file:File)=>void;status:string};
export function VrDraftReviewPanel({build,rate,onRate,onSave,onRestore,status}:Props){
  const file=useRef<HTMLInputElement>(null);
  const q=vrDraftTakeoff(build);
  const total=localIndicativeWallCost(q,rate);
  return <div className="section-block" aria-label="Local VR draft review and backup">
    <h2>VR draft quantities and backup</h2>
    <p className="muted">Unapproved local study only. Not a PlanReader customer estimate or
      source-authenticated measurement. No construction assemblies are assumed.</p>
    <div className="scope-info" aria-label="Indicative draft dimensions">
      <div><span>Draft walls</span><strong>{q.draftWalls}</strong></div>
      <div><span>Wall run</span><strong>{q.wallRunM.toFixed(3)} m</strong></div>
      <div><span>Net wall area, one face</span><strong>{q.wallNetFaceM2.toFixed(3)} m²</strong></div>
      <div><span>Indicative two-face lining</span><strong>{q.indicativeTwoFaceLiningM2.toFixed(3)} m²</strong></div>
      <div><span>Skirting candidate, both faces</span><strong>{q.skirtingCandidateM.toFixed(3)} m</strong></div>
      <div><span>Ceiling rectangle area</span><strong>{q.ceilingCandidateM2.toFixed(3)} m²</strong></div>
      <div><span>Doors / windows</span><strong>{q.draftDoors} / {q.draftWindows}</strong></div>
    </div>
    <label>Optional indicative lining-only rate (AUD/m², not verified)
      <input type="text" inputMode="decimal" placeholder="Leave blank to show unpriced"
        value={rate} maxLength={9} onChange={event=>onRate(event.currentTarget.value)}/>
    </label>
    <p role="status">{total===null
      ? "No approved rate loaded. Draft costs remain unpriced."
      : "Illustrative lining-only subtotal: A$"+total+
        " · owner-supplied rate; excludes all other trades, labour assumptions and tax verification."}</p>
    <details><summary>Components requiring a verified assembly profile</summary>
      <ul>{q.unpricedTrades.map(x=><li key={x}>{x}</li>)}</ul>
    </details>
    <div className="tool-group" role="group" aria-label="Local draft file actions">
      <button type="button" onClick={onSave}>Export local draft + undo history</button>
      <button type="button" onClick={()=>file.current?.click()}>Reopen saved draft file</button>
      <input type="file" ref={file} accept=".json,application/json" hidden
        onChange={event=>{const chosen=event.currentTarget.files?.[0];
          if(chosen)onRestore(chosen);
          event.currentTarget.value="";}}/>
    </div>
    {status&&<p role="status">{status}</p>}
    <p className="muted">Draft files only reopen against exactly the same workspace,
      original source SHA, revision, model revision and snapshot. They do not publish quantities.</p>
  </div>;
}
