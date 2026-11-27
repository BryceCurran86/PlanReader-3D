import {ShapeUtils,Vector2} from "three";
import {localOutline} from "./localOutline.ts";
import {profileDetails} from "./wallProfiles.ts";
import type {PlacedWall,PlanPoint,CeilingDraft} from "./buildPlacement.ts";
export type ShellSettings={roof:"off"|"flat"|"gable";pitchDeg:number;slabMm:number;ridgeDeg?:number;slabEnabled?:boolean};
export const DEFAULT_SHELL:ShellSettings={roof:"off",pitchDeg:22.5,slabMm:100};
type Vertex=[number,number,number];
export type ShellSurface={kind:"floor"|"ceiling"|"roof";vertices:Vertex[]};
export type DraftShell={surfaces:ShellSurface[];floorM2:number;roofM2:number;slabM3:number;heightM:number;levelId:string};
const EPS=1e-6;
/** Clip each source plan triangle independently at the ridge. This preserves
 * concave outlines without filling recesses or inventing hips/valleys. */
function clipAtRidge(poly:PlanPoint[],coordinate:(p:PlanPoint)=>number,ridge:number,lower:boolean):PlanPoint[]{
 const result:PlanPoint[]=[];
 const inside=(p:PlanPoint)=>lower?coordinate(p)<=ridge:coordinate(p)>=ridge;
 for(let i=0;i<poly.length;i++){
  const a=poly[i],b=poly[(i+1)%poly.length],inA=inside(a),inB=inside(b);
  if(inA)result.push(a);
  if(inA!==inB){const x=coordinate(a),y=coordinate(b),t=(ridge-x)/(y-x);result.push([a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t]);}
 }
 return result;
}
function projectedTriangleArea(a:PlanPoint,b:PlanPoint,c:PlanPoint){
 return Math.abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))/2;
}
export function connectedDraftShell(walls:readonly PlacedWall[],settings:ShellSettings):DraftShell|null{
 if(!["off","flat","gable"].includes(settings.roof)||(settings.roof==="off"&&!settings.slabEnabled)||!Number.isFinite(settings.pitchDeg)||settings.pitchDeg<5||settings.pitchDeg>60||!Number.isFinite(settings.slabMm)||settings.slabMm<50||settings.slabMm>600)return null;
 const ring=localOutline(walls);
 if(!ring)return null;
 const height=walls[0].heightM;
 if(!Number.isFinite(height)||height<.1||height>20||walls.some(w=>Math.abs(w.heightM-height)>EPS))return null;
 const pts=ring.points;
 if(settings.ridgeDeg!==undefined&&(!Number.isFinite(settings.ridgeDeg)||settings.ridgeDeg<0||settings.ridgeDeg>360))return null;
 const indices=ShapeUtils.triangulateShape(pts.map(p=>new Vector2(...p)),[]);
 if(indices.length!==pts.length-2)return null;
 const at=(p:PlanPoint,y:number):Vertex=>[p[0],y,p[1]];
 const plane=(y:number)=>indices.flatMap(t=>t.map(i=>at(pts[i],y)));
 const quad=(a:Vertex,b:Vertex,c:Vertex,d:Vertex):Vertex[]=>[a,b,c,a,c,d];
 const floor=plane(.002),bottom=-settings.slabMm/1000;
 floor.push(...plane(bottom));
 for(let i=0;i<pts.length;i++){
  const a=pts[i],b=pts[(i+1)%pts.length];
  floor.push(...quad(at(a,.002),at(b,.002),at(b,bottom),at(a,bottom)));
 }
 const ceiling=plane(height-.012);
 let roof:Vertex[],roofM2=settings.roof==="off"?0:ring.areaM2;
 if(settings.roof==="off"){roof=[];}
 else if(settings.roof==="flat"){roof=plane(height+.08);}
 else{
  // Auto ridge follows the longest perimeter edge. An explicit plan bearing
  // fixes the ridge direction across further connected footprint changes.
  let angle=settings.ridgeDeg===undefined?0:settings.ridgeDeg*Math.PI/180;
  if(settings.ridgeDeg===undefined){
   let longest=-1;
   for(let i=0;i<pts.length;i++){
    const a=pts[i],b=pts[(i+1)%pts.length],length=Math.hypot(b[0]-a[0],b[1]-a[1]);
    if(length>longest+EPS){longest=length;angle=Math.atan2(b[1]-a[1],b[0]-a[0]);}
   }
  }
  const nx=-Math.sin(angle),nz=Math.cos(angle),coordinate=(p:PlanPoint)=>p[0]*nx+p[1]*nz;
  const distances=pts.map(coordinate),min=Math.min(...distances),max=Math.max(...distances),ridge=(min+max)/2;
  const slope=Math.tan(settings.pitchDeg*Math.PI/180);
  const top=(p:PlanPoint):Vertex=>at(p,height+Math.max(0,Math.min(coordinate(p)-min,max-coordinate(p)))*slope);
  roof=[];let covered=0;
  for(const t of indices){
   const tri=t.map(i=>pts[i]);
   for(const lower of [true,false]){
    const poly=clipAtRidge(tri,coordinate,ridge,lower);
    for(let i=1;i+1<poly.length;i++){
     const area=projectedTriangleArea(poly[0],poly[i],poly[i+1]);
     if(area<=1e-10)continue;
     covered+=area;roof.push(top(poly[0]),top(poly[i]),top(poly[i+1]));
    }
   }
  }
  if(Math.abs(covered-ring.areaM2)>Math.max(1e-6,ring.areaM2*1e-8))return null;
  // Vertical infill above equal-height walls closes the roof shell.
  // These closures are not roof covering area or construction specifications.
  for(let i=0;i<pts.length;i++){
   const a=pts[i],b=pts[(i+1)%pts.length],x=coordinate(a),y=coordinate(b);
   const chain=[a];
   if((x<ridge&&y>ridge)||(x>ridge&&y<ridge)){
    const t=(ridge-x)/(y-x);chain.push([a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t]);
   }
   chain.push(b);
   for(let j=0;j+1<chain.length;j++){
    const p=chain[j],q=chain[j+1],tp=top(p),tq=top(q);
    if(tp[1]>height+EPS)roof.push(at(p,height),tp,tq);
    if(tq[1]>height+EPS)roof.push(at(p,height),tq,at(q,height));
   }
  }
  roofM2=ring.areaM2/Math.cos(settings.pitchDeg*Math.PI/180);
 }
 const slab=settings.slabEnabled??settings.roof!=="off";
 const surfaces:ShellSurface[]=[];
 if(slab)surfaces.push({kind:"floor",vertices:floor});
 if(settings.roof!=="off")surfaces.push({kind:"ceiling",vertices:ceiling},{kind:"roof",vertices:roof});
 return {surfaces,floorM2:slab?ring.areaM2:0,roofM2,slabM3:slab?ring.areaM2*settings.slabMm/1000:0,heightM:height,levelId:walls[0].levelId};
}

/** Local design only: an explicitly marked exterior ring takes precedence.
 * Internal partitions cannot be used to fill a missing exterior edge. Explicit
 * ceiling drafts replace the generated full-area ceiling, not the roof/slab. */
export function localBuildingShell(walls:readonly PlacedWall[],ceilings:readonly CeilingDraft[],settings:ShellSettings):DraftShell|null{
 if(!walls.length)return null;
 const {scopeKey,levelId}=walls[0];
 if([...walls,...ceilings].some(o=>o.scopeKey!==scopeKey||o.levelId!==levelId))return null;
 const exterior=walls.filter(w=>profileDetails(w.assembly).role==="external");
 const boundary=exterior.length?exterior:walls;
 const shell=connectedDraftShell(boundary,settings);
 if(!shell)return null;
 return ceilings.length?{...shell,surfaces:shell.surfaces.filter(s=>s.kind!=="ceiling")}:shell;
}
