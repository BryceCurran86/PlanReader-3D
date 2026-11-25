/** Shared local budget study for desktop and immersive display. No commercial authority. */
import type {BuildState} from "./buildPlacement.ts";
import {draftAssembly,draftAssemblyCost,STUDY_PROFILE} from "./vrDraftAssembly.ts";
import type {AssemblyProfile,AssemblyRates,ShellStudyMetrics} from "./vrDraftAssembly.ts";

export type StudyGeometry=Pick<BuildState,"walls"|"ceilings">&{shellMetrics?:ShellStudyMetrics};
export const assemblyFields:readonly [keyof AssemblyProfile,string,number][]=[
 ["spacingMm","Stud spacing (mm)",1],["nogginRows","Noggin rows",1],
 ["wastePct","Material waste (%)",0.1],["sheetM2","Board sheet area (m²)",0.01],
 ["paintCoverage","Paint coverage (m²/L/coat)",0.1],["paintCoats","Paint coats",1],
 ["paintPackL","Paint container (L)",0.1],["floorM2","Floor area allowance (m²)",0.01],
 ["floorPackM2","Floor carton coverage (m²)",0.01],["slabMm","Slab thickness (mm)",1],
 ["roofPlanM2","Roof horizontal projected area (m²)",0.01],["roofPitchDeg","Roof pitch (degrees)",0.1],
 ["electricalPoints","Electrical points allowance",1],["plumbingPoints","Plumbing points allowance",1],
];
export const nullableAssemblyFields=new Set<keyof AssemblyProfile>(["floorM2","roofPlanM2","electricalPoints","plumbingPoints"]);
export type AssemblyStudyConfig={enabled:boolean;followShell?:boolean;inputs:Record<string,string>;rates:AssemblyRates;mode:"margin"|"markup";margin:string;gst:string;baseline:StudyGeometry|null};
export function newAssemblyStudy():AssemblyStudyConfig{
 return {enabled:false,followShell:true,inputs:Object.fromEntries(assemblyFields.map(([key])=>[key,STUDY_PROFILE[key]===null?"":String(STUDY_PROFILE[key])])),rates:{},mode:"margin",margin:"0",gst:"10",baseline:null};
}
type Cost=ReturnType<typeof draftAssemblyCost>;
export type StudyEvaluation={result:Cost|null;prior:Cost|null;error:string;baselineError:string};
export function evaluateAssemblyStudy(build:StudyGeometry,study:AssemblyStudyConfig):StudyEvaluation{
 const empty={result:null,prior:null,error:"",baselineError:""};
 if(!study.enabled)return empty;
 try{
  const p={...STUDY_PROFILE};
  for(const [key] of assemblyFields){
   const value=study.inputs[key]?.trim()??"";
   if(!value&&!nullableAssemblyFields.has(key))throw Error("Enter all required study assumptions.");
   if(value&&!/^(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)$/.test(value))throw Error("Enter positive numbers or zero.");
   Object.assign(p,{[key]:value?Number(value):null});
  }
  if(!study.margin.trim()||!study.gst.trim())throw Error("Enter margin/markup and GST, including zero if not applicable.");
  const calculate=(geometry:StudyGeometry)=>draftAssemblyCost(draftAssembly(geometry,p,study.followShell===false?undefined:geometry.shellMetrics),study.rates,Number(study.margin),Number(study.gst),study.mode);
  const result=calculate(build);
  let prior:Cost|null=null,baselineError="";
  if(study.baseline)try{prior=calculate(study.baseline);}catch{baselineError="Baseline no longer fits the current assumptions.";}
  return {result,prior,error:"",baselineError};
 }catch(e){return {...empty,error:e instanceof Error?e.message:"Invalid study inputs"};}
}
export function hasPricedWork(cost:Cost){
 return cost.rows.some(row=>row.quantity!==null&&row.quantity>0&&(row.material!==null||row.labour!==null));
}
export type ImmersiveBudget={status:"disabled"|"invalid"|"unpriced"|"partial"|"priced";total:number|null;material:number|null;labour:number|null;delta:number|null;walls:number;ceilings:number;hasBaseline:boolean;trades:{trade:string;cents:number|null;partial:boolean}[]};
export function immersiveBudget(build:StudyGeometry,study:AssemblyStudyConfig,evaluation:StudyEvaluation):ImmersiveBudget{
 const {result,prior}=evaluation;
 const summary:ImmersiveBudget={status:study.enabled?"invalid":"disabled",total:null,material:null,labour:null,delta:null,walls:build.walls.length,ceilings:build.ceilings.length,hasBaseline:!!study.baseline,trades:[]};
 if(!study.enabled||!result)return summary;
 const priced=hasPricedWork(result);
 summary.status=priced?(result.partial?"partial":"priced"):"unpriced";
 summary.total=priced?result.total:null;
 summary.material=result.rows.some(r=>r.quantity!==null&&r.quantity>0&&r.material!==null)?result.material:null;
 summary.labour=result.rows.some(r=>r.quantity!==null&&r.quantity>0&&r.labour!==null)?result.labour:null;
 summary.delta=priced&&prior&&hasPricedWork(prior)?result.total-prior.total:null;
 summary.trades=result.trades.map(t=>({trade:t.trade,cents:result.rows.some(r=>r.trade===t.trade&&r.quantity!==null&&r.quantity>0&&(r.material!==null||r.labour!==null))?t.cents:null,partial:t.partial}));
 return summary;
}
export const budgetMoney=(cents:number|null)=>cents===null?"Unpriced":new Intl.NumberFormat("en-AU",{style:"currency",currency:"AUD"}).format(cents/100);
export function budgetHeadline(b:ImmersiveBudget){
 if(b.status==="disabled")return "Budget off · enable in desktop review";
 if(b.status==="invalid")return "Budget unavailable · check desktop assumptions";
 if(b.status==="unpriced")return "Budget unpriced · enter rates in desktop review";
 return (b.status==="partial"?"PARTIAL ":"STUDY ")+budgetMoney(b.total);
}
