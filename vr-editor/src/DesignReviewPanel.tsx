import {useState,useMemo} from "react";
import type {SceneManifest} from "./types";
import type {BuildState} from "./buildPlacement";
import {sceneCoverage,restoreAlternative} from "./vrDesignReview";
import type {DesignAlternative} from "./vrDesignReview";
import {evaluateAssemblyStudy,budgetMoney,hasPricedWork} from "./vrAssemblyStudy";
import type {AssemblyStudyConfig} from "./vrAssemblyStudy";
type Props={scene:SceneManifest;build:BuildState;items:number;alternatives:DesignAlternative[];blocked:boolean;onSave:(name:string)=>void;onRestore:(entry:DesignAlternative)=>void;onRemove:(id:string)=>void;study:AssemblyStudyConfig;status:string};
export function DesignReviewPanel({scene,build,items,alternatives,blocked,onSave,onRestore,onRemove,study,status}:Props){
 const [name,setName]=useState("");
 const coverage=useMemo(()=>sceneCoverage(scene),[scene]);
 const compared=useMemo(()=>alternatives.map(a=>{
  try{const draft=restoreAlternative(scene,a);const cost=evaluateAssemblyStudy(draft.build,{...study,baseline:null}).result;return {a,cost:cost&&hasPricedWork(cost)?cost.total:null,partial:cost?.partial??true};}catch{return {a,cost:null,partial:true};}
 }),[scene,alternatives,study]);
 const current=evaluateAssemblyStudy(build,{...study,baseline:null}).result;
 const total=current&&hasPricedWork(current)?current.total:null;
 return <details className="section-block">
 <summary>3D import coverage and design alternatives</summary>
 <p>Coverage of records supplied to this viewer, not an accuracy score or evidence of missing drawing quantities.</p>
 <div className="scope-info">
 <div><span>Wall faces / supplied wall records</span><strong>{coverage.wallFaces} / {coverage.wallRecords}</strong></div>
 <div><span>Verified wall faces</span><strong>{coverage.verifiedWalls}</strong></div>
 <div><span>Unknown-height guides / missing geometry</span><strong>{coverage.guideLines} / {coverage.missingWalls}</strong></div>
 <div><span>Floor / ceiling / roof surfaces</span><strong>{coverage.floors} / {coverage.ceilings} / {coverage.roofs}</strong></div>
 <div><span>Positioned opening candidates / recorded openings</span><strong>{coverage.positionedOpenings} / {coverage.openingRecords}</strong></div>
 <div><span>Imported wall assemblies</span><strong>Not supplied by scene contract</strong></div>
 <p>Cyan dashed openings are review guides, not verified apertures. Missing positions and conflicting records are withheld.</p>
 </div>
 <h3>Compare local alternatives</h3>
 <p>Capture up to eight designs in this open scene. Restoring replaces the local walls, ceilings and catalogue items, not the original plan. Save the current design before restoring another. These alternatives are session-only; use the existing draft export for durable copies. Costs use the same current assumptions and rates, exclude catalogue prices, and may be partial.</p>
 <label>Alternative name<input value={name} maxLength={64} onChange={e=>setName(e.currentTarget.value)}/></label>
 <button type="button" disabled={blocked||!name.trim()||alternatives.length>=8} onClick={()=>{onSave(name);}}>Capture current design</button>
 <p>Current: {build.walls.length} walls · {build.ceilings.length} ceilings · {items} items · {budgetMoney(total)}{current?.partial?" (partial)":""}</p>
 {compared.map(({a,cost,partial})=><div className="scope-info" key={a.id}>
 <strong>{a.name}</strong><span>{a.walls} walls · {a.ceilings} ceilings · {a.items} items</span>
 <span>{budgetMoney(cost)}{partial&&cost!==null?" (partial)":""}{cost!==null&&total!==null?" · change vs current "+budgetMoney(cost-total):""}</span>
 <button type="button" disabled={blocked} onClick={()=>{if(window.confirm("Replace current local design with "+a.name+"? Capture the current design first if needed."))onRestore(a);}}>Restore</button>
 <button type="button" onClick={()=>onRemove(a.id)}>Remove</button>
 </div>)}
 {status&&<p role="status">{status}</p>}
 </details>;
}
