import type {SceneManifest} from "./types.ts";
import type {BuildState} from "./buildPlacement.ts";
import {sourceWallDimensions} from "./sourceDimensions.ts";
import {wallAssembly} from "./wallProfiles.ts";
import {localOutline} from "./localOutline.ts";
import {saveVrReview,restoreVrReview} from "./vrDraftSave.ts";
import type {ItemDraft} from "./itemPlacement.ts";
export function sceneCoverage(scene:SceneManifest){
 const walls=scene.objects.filter(o=>o.objectType==="wall");
 const faces=walls.filter(o=>o.geometry?.kind==="wallFace");
 const verified=faces.filter(o=>sourceWallDimensions(o)!==null);
 const surfaces=(kind:string)=>(scene.sourceSurfaces??[]).filter(s=>s.kind===kind).length;
 return {wallRecords:walls.length,wallFaces:faces.length,verifiedWalls:verified.length,guideLines:walls.filter(o=>o.geometry?.kind==="wallLine").length,
  missingWalls:walls.filter(o=>!o.geometry).length,floors:surfaces("floor"),ceilings:surfaces("ceiling"),roofs:surfaces("roof"),
  openingGeometry:"not supplied",wallAssemblies:"not supplied"};
}
export type DimensionEntry={key:string;label:string;position:[number,number,number];kind:"wall"|"ceiling"|"floor";source:boolean};
export function reviewDimensions(scene:SceneManifest,build:Pick<BuildState,"walls"|"ceilings">,level:string,visible:ReadonlySet<string>):DimensionEntry[]{
 const entries:DimensionEntry[]=[];
 for(const row of scene.objects){
  if(!visible.has(row.objectId)||(level!=="all"&&row.levelId!==level))continue;
  const d=sourceWallDimensions(row),g=row.geometry;
  if(!d||g?.kind!=="wallFace")continue;
  entries.push({key:"source:"+row.objectId,label:d.label,position:[(g.start[0]+g.end[0])/2,g.heightM+.12,(g.start[1]+g.end[1])/2],kind:"wall",source:true});
 }
 for(const w of build.walls){
  if(level!=="all"&&w.levelId!==level)continue;
  const l=Math.hypot(w.end[0]-w.start[0],w.end[1]-w.start[1]);
  entries.push({key:"wall:"+w.proposalId,label:`${Math.round(l*1000)} × ${Math.round(w.heightM*1000)} × ${wallAssembly(w.assembly).thicknessMm} mm · DRAFT`,position:[(w.start[0]+w.end[0])/2,w.heightM+.12,(w.start[1]+w.end[1])/2],kind:"wall",source:false});
 }
 for(const c of build.ceilings){
  if(level!=="all"&&c.levelId!==level)continue;
  const w=Math.abs(c.end[0]-c.start[0]),d=Math.abs(c.end[1]-c.start[1]);
  entries.push({key:"ceiling:"+c.proposalId,label:`${(w*d).toFixed(2)} m² · H ${Math.round(c.heightM*1000)} mm · DRAFT`,position:[(c.start[0]+c.end[0])/2,c.heightM-.14,(c.start[1]+c.end[1])/2],kind:"ceiling",source:false});
 }
 // A single explicitly closed local ring is a review area, not an inferred room boundary.
 const walls=build.walls.filter(w=>level==="all"||w.levelId===level);
 const outline=localOutline(walls);
 if(outline){
  const xs=outline.points.map(p=>p[0]),zs=outline.points.map(p=>p[1]);
  entries.push({key:"local-ring",label:`${outline.areaM2.toFixed(2)} m² · DRAFT OUTLINE`,position:[(Math.min(...xs)+Math.max(...xs))/2,.18,(Math.min(...zs)+Math.max(...zs))/2],kind:"floor",source:false});
 }
 return entries;
}
export type DesignAlternative={id:string;name:string;payload:string;walls:number;ceilings:number;items:number};
export function captureAlternative(scene:SceneManifest,build:BuildState,items:ItemDraft|null,name:string,id:string):DesignAlternative{
 const clean=name.trim();
 if(!clean||clean.length>64||!id)throw Error("Enter an alternative name (1–64 characters).");
 // Use existing exact-source schema and validate before accepting.
 const payload=saveVrReview(scene,{...build,tool:null,start:null,history:[],future:[]},items?{...items,history:[],future:[]}:null);
 if(payload.length>3*1024*1024)throw Error("Alternative exceeds local draft limit.");
 const restored=restoreVrReview(scene,JSON.parse(payload));
 return {id,name:clean,payload,walls:restored.build.walls.length,ceilings:restored.build.ceilings.length,items:restored.itemDraft.items.length};
}
export function restoreAlternative(scene:SceneManifest,alternative:DesignAlternative){
 return restoreVrReview(scene,JSON.parse(alternative.payload));
}
