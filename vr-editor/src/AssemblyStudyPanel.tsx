import {useState,useMemo} from "react";
import {assemblyFields as fields,nullableAssemblyFields as nullable,budgetMoney as money,newAssemblyStudy,evaluateAssemblyStudy,immersiveBudget,hasPricedWork} from "./vrAssemblyStudy.ts";
import type {AssemblyStudyConfig,StudyGeometry} from "./vrAssemblyStudy.ts";

export function useAssemblyStudy(build:StudyGeometry,scope:string|null){
 const [stored,setStored]=useState(()=>({scope,study:newAssemblyStudy()}));
 const study=stored.scope===scope?stored.study:newAssemblyStudy();
 if(stored.scope!==scope)setStored({scope,study});
 const change=(update:(previous:AssemblyStudyConfig)=>AssemblyStudyConfig)=>setStored(previous=>previous.scope===scope?{scope,study:update(previous.study)}:previous);
 const evaluation=useMemo(()=>evaluateAssemblyStudy(build,study),[build,study]);
 const summary=useMemo(()=>immersiveBudget(build,study,evaluation),[build,study,evaluation]);
 const capture=()=>change(s=>s.enabled&&evaluation.result?{...s,baseline:structuredClone({walls:build.walls,ceilings:build.ceilings})}:s);
 const clear=()=>change(s=>({...s,baseline:null}));
 return {study,change,evaluation,summary,capture,clear};
}
type Props={controller:ReturnType<typeof useAssemblyStudy>};
const qty=(n:number|null)=>n===null?"Not specified":n.toLocaleString("en-AU",{maximumFractionDigits:3});
export function AssemblyStudyPanel({controller}:Props){
 const {study,change,evaluation,summary,capture,clear}=controller;
 const {enabled,inputs,rates,mode,margin,gst,baseline}=study;
 const {result,prior,error,baselineError}=evaluation;
 const setEnabled=(enabled:boolean)=>change(s=>({...s,enabled}));
 const setInputs=(update:(old:typeof inputs)=>typeof inputs)=>change(s=>({...s,inputs:update(s.inputs)}));
 const setRates=(update:(old:typeof rates)=>typeof rates)=>change(s=>({...s,rates:update(s.rates)}));
 const setMode=(mode:typeof study.mode)=>change(s=>({...s,mode}));
 const setMargin=(margin:string)=>change(s=>({...s,margin}));
 const setGst=(gst:string)=>change(s=>({...s,gst}));
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
     <div><span>Material subtotal</span><strong>{money(summary.material)}</strong></div>
     <div><span>Labour subtotal</span><strong>{money(summary.labour)}</strong></div>
     <div><span>Subtotal</span><strong>{money(summary.total===null?null:result.subtotal)}</strong></div>
     <div><span>After {mode}</span><strong>{money(summary.total===null?null:result.sell)}</strong></div>
     <div><span>GST</span><strong>{money(summary.total===null?null:result.gst)}</strong></div>
     <div><span>Indicative priced portion</span><strong>{money(summary.total)}</strong></div>
    </div>
    <div className="tool-group">
     <button type="button" onClick={capture}>Capture comparison baseline</button>
     {baseline&&<button type="button" onClick={clear}>Clear baseline</button>}
    </div>
    {baselineError&&<p role="alert">{baselineError}</p>}
    {prior&&<p role="status">Geometry comparison at current assumptions and rates: {money(hasPricedWork(prior)?prior.total:null)} → {money(summary.total)} · change {money(summary.delta)}. Both totals may be partial; manual allowances remain fixed.</p>}
    <details><summary>Trade breakdown</summary><ul>{summary.trades.map(t=><li key={t.trade}>{t.trade}: {money(t.cents)}{t.partial?" (partial)":""}</li>)}</ul></details>
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
