import {useState} from "react";
import type {BuildState} from "./buildPlacement.ts";
import {draftAssembly,draftAssemblyCost,STUDY_PROFILE} from "./vrDraftAssembly.ts";
import type {AssemblyProfile,AssemblyRates} from "./vrDraftAssembly.ts";

type Props={build:BuildState;scope:string};
const fields:readonly [keyof AssemblyProfile,string,number][]=[
 ["spacingMm","Stud spacing (mm)",1],["nogginRows","Noggin rows",1],
 ["wastePct","Material waste (%)",0.1],["sheetM2","Board sheet area (m²)",0.01],
 ["paintCoverage","Paint coverage (m²/L/coat)",0.1],["paintCoats","Paint coats",1],
 ["paintPackL","Paint container (L)",0.1],["floorM2","Floor area allowance (m²)",0.01],
 ["floorPackM2","Floor carton coverage (m²)",0.01],["slabMm","Slab thickness (mm)",1],
 ["roofPlanM2","Roof horizontal projected area (m²)",0.01],["roofPitchDeg","Roof pitch (degrees)",0.1],
 ["electricalPoints","Electrical points allowance",1],["plumbingPoints","Plumbing points allowance",1],
];
const nullable=new Set<keyof AssemblyProfile>(["floorM2","roofPlanM2","electricalPoints","plumbingPoints"]);
const money=(c:number|null)=>c===null?"Unpriced":new Intl.NumberFormat("en-AU",{style:"currency",currency:"AUD"}).format(c/100);
const qty=(n:number|null)=>n===null?"Not specified":n.toLocaleString("en-AU",{maximumFractionDigits:3});
export function AssemblyStudyPanel({build,scope}:Props){
 return <AssemblyStudy key={scope} build={build}/>;
}
function AssemblyStudy({build}:{build:BuildState}){
 const [enabled,setEnabled]=useState(false);
 const [inputs,setInputs]=useState(()=>Object.fromEntries(fields.map(([key])=>[key,STUDY_PROFILE[key]===null?"":String(STUDY_PROFILE[key])])));
 const [rates,setRates]=useState<AssemblyRates>({});
 const [mode,setMode]=useState<"margin"|"markup">("margin");
 const [margin,setMargin]=useState("0"),[gst,setGst]=useState("10");
 const [baseline,setBaseline]=useState<BuildState|null>(null);
 let result:ReturnType<typeof draftAssemblyCost>|null=null, prior:ReturnType<typeof draftAssemblyCost>|null=null,error="";
 if(enabled)try{
  const p={...STUDY_PROFILE};
  for(const [key] of fields){
   const value=inputs[key]?.trim()??"";
   if(!value&&!nullable.has(key))throw Error("Enter all required study assumptions.");
   if(value&&!/^(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)$/.test(value))throw Error("Enter positive numbers or zero.");
   Object.assign(p,{[key]:value?Number(value):null});
  }
  if(!margin.trim()||!gst.trim())throw Error("Enter margin/markup and GST, including zero if not applicable.");
  result=draftAssemblyCost(draftAssembly(build,p),rates,Number(margin),Number(gst),mode);
  if(baseline)prior=draftAssemblyCost(draftAssembly(baseline,p),rates,Number(margin),Number(gst),mode);
 }catch(e){error=e instanceof Error?e.message:"Invalid study inputs";}
 return <details className="section-block">
  <summary>Construction assembly budget · local study</summary>
  <p className="muted">Opt-in estimating allowances only. Not engineered framing, a certified takeoff, or a customer quote. Existing source geometry, catalogue prices and approved costs are excluded. Do not add the separate lining-only illustration to this subtotal.</p>
  <label><input type="checkbox" checked={enabled} onChange={e=>setEnabled(e.currentTarget.checked)}/> Enable indicative construction budget</label>
  {enabled&&<>
   <p>Review all starting assumptions. Gross studs and noggins are conservative allowances, not cut lists. Opening heads are spans, not specified lintels. Ceiling rectangles may overlap. Floor, roof and service allowances must be entered separately.</p>
   <details><summary>Assembly assumptions</summary>
    {fields.map(([key,label,step])=><label key={key}>{label}<input type="number" min="0" step={step} value={inputs[key]} placeholder={nullable.has(key)?"Unknown":undefined} onChange={e=>{const v=e.currentTarget.value;setInputs(old=>({...old,[key]:v}));}}/></label>)}
   </details>
   <label>Pricing method<select value={mode} onChange={e=>setMode(e.currentTarget.value==="markup"?"markup":"margin")}><option value="margin">Gross margin</option><option value="markup">Markup</option></select></label>
   <label>{mode==="margin"?"Gross margin (%)":"Markup (%)"}<input type="number" min="0" value={margin} onChange={e=>setMargin(e.currentTarget.value)}/></label>
   <label>GST (%)<input type="number" min="0" value={gst} onChange={e=>setGst(e.currentTarget.value)}/></label>
   {error&&<p role="alert">{error}</p>}
   {result&&<>
    <p role="status"><strong>{result.partial?"PARTIAL — unpriced or unspecified work excluded":"Indicative study only"}</strong> · updates from current draft geometry.</p>
    <div className="scope-info">
     <div><span>Material subtotal</span><strong>{money(result.material)}</strong></div>
     <div><span>Labour subtotal</span><strong>{money(result.labour)}</strong></div>
     <div><span>Subtotal</span><strong>{money(result.subtotal)}</strong></div>
     <div><span>After {mode}</span><strong>{money(result.sell)}</strong></div>
     <div><span>GST</span><strong>{money(result.gst)}</strong></div>
     <div><span>Indicative priced portion</span><strong>{money(result.total)}</strong></div>
    </div>
    <div className="tool-group">
     <button type="button" onClick={()=>setBaseline(structuredClone(build))}>Capture comparison baseline</button>
     {baseline&&<button type="button" onClick={()=>setBaseline(null)}>Clear baseline</button>}
    </div>
    {prior&&<p role="status">Geometry comparison at current assumptions and rates: {money(prior.total)} → {money(result.total)} · change {money(result.total-prior.total)}. Both totals may be partial; manual allowances remain fixed.</p>}
    <details><summary>Trade breakdown</summary><ul>{result.trades.map(t=><li key={t.trade}>{t.trade}: {money(t.cents)}{t.partial?" (partial)":""}</li>)}</ul></details>
    <details><summary>Quantities and separate rates</summary>
     <p>Enter local AUD ex-GST component rates, not bundled supply/install rates. Material rates apply to purchase quantities; labour rates apply to net quantities. Blank means unpriced; zero is an explicit zero allowance.</p>
     {result.rows.map(row=><fieldset key={row.id}>
      <legend>{row.label}</legend>
      <p>{qty(row.quantity)} {row.unit} net · {qty(row.purchase)} {row.unit} purchase allowance</p>
      {(["material","labour"] as const).map(kind=><label key={kind}>{kind==="material"?"Material":"Labour"} AUD/{row.unit}<input type="text" inputMode="decimal" maxLength={9} placeholder="Unpriced" value={rates[row.id]?.[kind]??""} disabled={row.quantity===null} onChange={e=>{const v=e.currentTarget.value;setRates(old=>({...old,[row.id]:{...old[row.id],[kind]:v}}));}}/></label>)}
      <p>Material {money(row.material)} · Labour {money(row.labour)}{row.partial?" · partial":""}</p>
     </fieldset>)}
    </details>
   </>}
  </>}
 </details>;
}
