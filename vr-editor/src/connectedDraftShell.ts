import {ShapeUtils,Vector2} from "three";
import {localOutline} from "./localOutline.ts";
import type {PlacedWall,PlanPoint} from "./buildPlacement.ts";
export type ShellSettings={roof:"off"|"flat"|"gable";pitchDeg:number;slabMm:number};
export const DEFAULT_SHELL:ShellSettings={roof:"off",pitchDeg:22.5,slabMm:100};
type Vertex=[number,number,number];
export type ShellSurface={kind:"floor"|"ceiling"|"roof";vertices:Vertex[]};
export type DraftShell={surfaces:ShellSurface[];floorM2:number;roofM2:number;slabM3:number;heightM:number;levelId:string};
const EPS=1e-6;
function rectangle(points:PlanPoint[]){
 if(points.length!==4)return false;
 const e=points.map((p,i)=>[points[(i+1)%4][0]-p[0],points[(i+1)%4][1]-p[1]]);
 return e.every((v,i)=>{const w=e[(i+1)%4];return Math.abs(v[0]*w[0]+v[1]*w[1])<=EPS*Math.hypot(...v)*Math.hypot(...w);});
}
export function connectedDraftShell(walls:readonly PlacedWall[],settings:ShellSettings):DraftShell|null{
 if(settings.roof==="off"||!["flat","gable"].includes(settings.roof)||!Number.isFinite(settings.pitchDeg)||settings.pitchDeg<5||settings.pitchDeg>60||!Number.isFinite(settings.slabMm)||settings.slabMm<50||settings.slabMm>600)return null;
 const ring=localOutline(walls);
 if(!ring)return null;
 const height=walls[0].heightM;
 if(!Number.isFinite(height)||height<.1||height>20||walls.some(w=>Math.abs(w.heightM-height)>EPS))return null;
 const pts=ring.points;
 if(settings.roof==="gable"&&!rectangle(pts))return null;
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
 let roof:Vertex[],roofM2=ring.areaM2;
 if(settings.roof==="flat"){roof=plane(height+.08);}
 else{
  const lengths=pts.map((p,i)=>Math.hypot(p[0]-pts[(i+1)%4][0],p[1]-pts[(i+1)%4][1]));
  const start=lengths[0]>=lengths[1]?0:1;
  const [a,b,c,d]=[0,1,2,3].map(i=>pts[(start+i)%4]);
  const span=lengths[(start+1)%4],rise=span/2*Math.tan(settings.pitchDeg*Math.PI/180);
  const mid=(p:PlanPoint,q:PlanPoint):PlanPoint=>[(p[0]+q[0])/2,(p[1]+q[1])/2];
  const r1=at(mid(a,d),height+rise),r2=at(mid(b,c),height+rise);
  roof=[...quad(at(a,height),at(b,height),r2,r1),...quad(r1,r2,at(c,height),at(d,height)),
   at(a,height),r1,at(d,height),at(b,height),at(c,height),r2];
  roofM2=ring.areaM2/Math.cos(settings.pitchDeg*Math.PI/180);
 }
 return {surfaces:[{kind:"floor",vertices:floor},{kind:"ceiling",vertices:ceiling},{kind:"roof",vertices:roof}],floorM2:ring.areaM2,roofM2,slabM3:ring.areaM2*settings.slabMm/1000,heightM:height,levelId:walls[0].levelId};
}
