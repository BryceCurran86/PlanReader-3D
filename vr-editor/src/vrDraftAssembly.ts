/** Local opt-in budgeting only; no source or structural authority. */
import type {BuildState} from "./buildPlacement.ts";
import {planLength,openingFits} from "./buildPlacement.ts";
import {profileDetails,wallAssembly} from "./wallProfiles.ts";
export type AssemblyProfile={spacingMm:number;nogginRows:number;wastePct:number;sheetM2:number;paintCoverage:number;paintCoats:number;paintPackL:number;floorM2:number|null;floorPackM2:number;slabMm:number;roofPlanM2:number|null;roofPitchDeg:number;electricalPoints:number|null;plumbingPoints:number|null};
export const STUDY_PROFILE:AssemblyProfile={spacingMm:450,nogginRows:1,wastePct:10,sheetM2:2.88,paintCoverage:16,paintCoats:2,paintPackL:4,floorM2:null,floorPackM2:1.44,slabMm:100,roofPlanM2:null,roofPitchDeg:22.5,electricalPoints:null,plumbingPoints:null};
export type AssemblyLine={id:string;trade:string;label:string;unit:string;quantity:number|null;purchase:number|null};
export type AssemblyRates=Record<string,{material?:string;labour?:string}>;
const round=(n:number)=>Math.round(n*1000)/1000;
const pack=(n:number,size:number)=>Math.ceil(n/size-1e-9);
const inRange=(n:number,min:number,max:number)=>Number.isFinite(n)&&n>=min&&n<=max;
export function draftAssembly(state:Pick<BuildState,"walls"|"ceilings">,p:AssemblyProfile):AssemblyLine[] {
 if(!inRange(p.spacingMm,100,1200)||!Number.isInteger(p.nogginRows)||!inRange(p.nogginRows,0,10)||!inRange(p.wastePct,0,100)||!inRange(p.sheetM2,.1,20)||!inRange(p.paintCoverage,.1,100)||!Number.isInteger(p.paintCoats)||!inRange(p.paintCoats,1,10)||!inRange(p.paintPackL,.1,100)||!inRange(p.floorPackM2,.01,100)||!inRange(p.slabMm,20,1000)||!inRange(p.roofPitchDeg,0,75))throw Error("Invalid study assumptions");
 for(const n of [p.floorM2,p.roofPlanM2])if(n!==null&&!inRange(n,0,100000))throw Error("Invalid surface area");
 for(const n of [p.electricalPoints,p.plumbingPoints])if(n!==null&&(!Number.isInteger(n)||!inRange(n,0,100000)))throw Error("Invalid point count");
 let studs=0,plates=0,noggins=0,jambs=0,headers=0,sills=0,net=0,skirting=0,trim=0,doors=0,windows=0,ceiling=0;
 let steelStuds=0,steelTracks=0,steelNoggins=0,steelJambs=0,steelHeads=0,steelSills=0,liningArea=0,brick=0,doubleBrick=0,block=0,concrete=0,cladding=0;
 for(const w of state.walls){
  const l=planLength(w.start,w.end);
  if(!inRange(l,.049,200)||!inRange(w.heightM,.01,100))throw Error("Invalid draft wall");
  const assembly=wallAssembly(w.assembly),spec=profileDetails(assembly),frame=spec.core;
  const openings=[...w.openings].sort((a,b)=>a.offsetM-b.offsetM);
  let removed=0,base=0,previousEnd=0;
  for(const o of openings){
   if(!openingFits(w,o)||o.offsetM<previousEnd-1e-6)throw Error("Invalid or overlapping opening");
   previousEnd=o.offsetM+o.widthM;
   removed+=o.widthM*o.heightM;
   const grounded=o.sillHeightM<=.001;
   if(grounded)base+=o.widthM;
   if(frame==="timber"){jambs+=2;headers+=o.widthM;if(!grounded)sills+=o.widthM;}
   if(frame==="steel"){steelJambs+=2;steelHeads+=o.widthM;if(!grounded)steelSills+=o.widthM;}
   if(frame!=="masonry")trim+=(spec.role==="internal"?2:1)*(2*o.heightM+o.widthM+(grounded?0:o.widthM));
   if(o.openingKind==="door")doors++;
   if(o.openingKind==="window")windows++;
  }
  // Gross regular stud allowance, deliberately conservative around openings.
  const area=Math.max(0,l*w.heightM-removed),sides=spec.role==="internal"?2:1;
  if(frame==="timber"){studs+=Math.ceil(l/(p.spacingMm/1000))+1;plates+=2*l-base;noggins+=l*p.nogginRows;}
  if(frame==="steel"){steelStuds+=Math.ceil(l/(p.spacingMm/1000))+1;steelTracks+=2*l-base;steelNoggins+=l*p.nogginRows;}
  if(frame!=="masonry"){net+=area;liningArea+=area*sides;skirting+=sides*Math.max(0,l-base);}
  if(assembly.profile.startsWith("brick-veneer"))brick+=area;
  if(assembly.profile==="double-brick")doubleBrick+=area*2;
  if(assembly.profile==="blockwork")block+=area;
  if(assembly.profile==="concrete")concrete+=area*assembly.thicknessMm/1000;
  if(assembly.profile==="external-timber"||assembly.profile==="external-steel")cladding+=area;
 }
 for(const c of state.ceilings){
  const a=Math.abs((c.end[0]-c.start[0])*(c.end[1]-c.start[1]));
  if(!inRange(a,0,100000))throw Error("Invalid draft ceiling");
  ceiling+=a;
 }
 const f=1+p.wastePct/100;
 const lines:AssemblyLine[]=[];
 function add(id:string,trade:string,label:string,unit:string,q:number|null,buy:number|null=q===null?null:q*f){
  lines.push({id,trade,label,unit,quantity:q===null?null:round(q),purchase:buy===null?null:round(buy)});
 }
 add("studs","Framing","Gross regular stud allowance","each",studs,pack(studs*f,1));
 add("plates","Framing","Single top + bottom plates","lm",plates);
 add("noggins","Framing","Gross noggin allowance","lm",noggins);
 add("jambs","Framing","Additional opening jamb allowance","each",jambs,pack(jambs*f,1));
 add("headers","Framing","Opening head span (not sized lintel)","lm",headers);
 add("sills","Framing","Raised opening sill span","lm",sills);
 add("bracing","Framing","Engineered bracing — not inferred","m²",null);
 if(steelStuds>0){
  add("steel-studs","Steel framing","Gross steel stud allowance","each",steelStuds,pack(steelStuds*f,1));
  add("steel-tracks","Steel framing","Top and bottom track","lm",steelTracks);
  add("steel-noggins","Steel framing","Noggin allowance","lm",steelNoggins);
  add("steel-jambs","Steel framing","Additional opening jamb allowance","each",steelJambs,pack(steelJambs*f,1));
  add("steel-heads","Steel framing","Opening head span (not engineered)","lm",steelHeads);
  add("steel-sills","Steel framing","Raised opening sill span","lm",steelSills);
 }
 if(brick>0)add("brick-veneer","Masonry","Net brick veneer area","m²",brick);
 if(doubleBrick>0)add("double-brick","Masonry","Two masonry leaf areas","m²",doubleBrick);
 if(block>0)add("blockwork","Masonry","Net blockwork area","m²",block);
 if(concrete>0)add("wall-concrete","Concrete","Net solid concrete wall volume","m³",concrete);
 if(cladding>0)add("cladding","Cladding","Net exterior cladding area","m²",cladding);
 add("boards","Lining","Internal wall boards","sheet",liningArea/p.sheetM2,pack(liningArea*f,p.sheetM2));
 add("insulation","Lining","Single cavity area","m²",net);
 add("skirting","Finishes","Both wall faces skirting","lm",skirting);
 add("architraves","Finishes","Both faces opening trim allowance","lm",trim);
 const paint=(liningArea+ceiling)*p.paintCoats/p.paintCoverage;
 add("paint","Painting","Wall and ceiling paint","L",paint,pack(paint*f,p.paintPackL)*p.paintPackL);
 add("ceiling","Lining","Ceiling boards (rectangle sum)","sheet",ceiling/p.sheetM2,pack(ceiling*f,p.sheetM2));
 add("floor","Flooring","Entered floor coverage","m²",p.floorM2,p.floorM2===null?null:pack(p.floorM2*f,p.floorPackM2)*p.floorPackM2);
 add("slab","Concrete","Entered floor area × slab thickness","m³",p.floorM2===null?null:p.floorM2*p.slabMm/1000);
 add("roof","Roofing","Entered projected area × pitch factor","m²",p.roofPlanM2===null?null:p.roofPlanM2/Math.cos(p.roofPitchDeg*Math.PI/180));
 add("doors","Openings","Draft door count","each",doors,doors);
 add("windows","Openings","Draft window count","each",windows,windows);
 add("electrical","Services","Entered electrical point allowance","each",p.electricalPoints,p.electricalPoints);
 add("plumbing","Services","Entered plumbing point allowance","each",p.plumbingPoints,p.plumbingPoints);
 return lines;
}
function cents(s:string|undefined):number|null {
 if(!s||!/^(?:0|[1-9][0-9]{0,5})(?:\.[0-9]{1,2})?$/.test(s))return null;
 return Math.round(Number(s)*100);
}
export function draftAssemblyCost(lines:AssemblyLine[],rates:AssemblyRates,marginPct:number,gstPct:number,pricingMode:"margin"|"markup"="margin"){
 if(!inRange(marginPct,0,pricingMode==="margin"?95:1000)||!inRange(gstPct,0,100))throw Error("Invalid budget percentages");
 const rows=lines.map(line=>{
  const r=rates[line.id],m=cents(r?.material),l=cents(r?.labour);
  const material=line.purchase===null||m===null?null:Math.round(line.purchase*m);
  const labour=line.quantity===null||l===null?null:Math.round(line.quantity*l);
  return {...line,material,labour,partial:line.quantity===null||(line.quantity>0&&(m===null||l===null))};
 });
 const material=rows.reduce((s,x)=>s+(x.material??0),0),labour=rows.reduce((s,x)=>s+(x.labour??0),0);
 const subtotal=material+labour;
 const sell=Math.round(pricingMode==="margin"?subtotal/(1-marginPct/100):subtotal*(1+marginPct/100));
 const gst=Math.round(sell*gstPct/100);
 if(![subtotal,sell,gst,sell+gst].every(Number.isSafeInteger))throw Error("Budget exceeds safe range");
 const trades=Array.from(new Set(rows.map(x=>x.trade))).map(trade=>({trade,cents:rows.filter(x=>x.trade===trade).reduce((s,x)=>s+(x.material??0)+(x.labour??0),0),partial:rows.some(x=>x.trade===trade&&x.partial)}));
 return {rows,trades,material,labour,subtotal,sell,gst,total:sell+gst,partial:rows.some(x=>x.partial),reviewOnly:true as const,commercialPublicationAllowed:false as const};
}
