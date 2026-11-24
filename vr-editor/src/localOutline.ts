/** Editable closed local wall rings only; never infer an authoritative source footprint. */
import type { PlanPoint, PlacedWall } from "./buildPlacement.ts";
export type OutlineEdit =
 | {kind:"move-point";index:number;point:PlanPoint}
 | {kind:"move-edge";index:number;delta:PlanPoint}
 | {kind:"insert-point";index:number;point:PlanPoint;newId:string}
 | {kind:"remove-point";index:number};
type Edge={wall:PlacedWall;reversed:boolean};
export type LocalOutline={points:PlanPoint[];edges:Edge[];areaM2:number};
const EPS=1e-7;
const distance=(a:PlanPoint,b:PlanPoint)=>Math.hypot(a[0]-b[0],a[1]-b[1]);
const same=(a:PlanPoint,b:PlanPoint)=>distance(a,b)<=EPS;
const point=(p:PlanPoint):PlanPoint|null=>p.length===2&&p.every(v=>Number.isFinite(v)&&Math.abs(v)<=10000)?[Math.round(p[0]*1000)/1000,Math.round(p[1]*1000)/1000]:null;
const cross=(a:PlanPoint,b:PlanPoint,c:PlanPoint)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
function on(a:PlanPoint,b:PlanPoint,p:PlanPoint){return Math.abs(cross(a,b,p))<=EPS&&p[0]>=Math.min(a[0],b[0])-EPS&&p[0]<=Math.max(a[0],b[0])+EPS&&p[1]>=Math.min(a[1],b[1])-EPS&&p[1]<=Math.max(a[1],b[1])+EPS;}
function intersects(a:PlanPoint,b:PlanPoint,c:PlanPoint,d:PlanPoint){
 const s=cross(a,b,c),t=cross(a,b,d),u=cross(c,d,a),v=cross(c,d,b);
 return ((s>EPS&&t< -EPS||s< -EPS&&t>EPS)&&(u>EPS&&v< -EPS||u< -EPS&&v>EPS))||on(a,b,c)||on(a,b,d)||on(c,d,a)||on(c,d,b);
}
export function outlineArea(points:readonly PlanPoint[]):number|null{
 if(points.length<3||points.length>25||points.some(p=>!point(p)))return null;
 let twice=0;
 for(let i=0;i<points.length;i++){
  const a=points[i],b=points[(i+1)%points.length],c=points[(i+2)%points.length];
  const l=distance(a,b);if(l<.05-EPS||l>200)return null;
  // Adjacent collinear reversal overlaps; straight intermediate vertices are permitted.
  if(Math.abs(cross(a,b,c))<=EPS&&(a[0]-b[0])*(c[0]-b[0])+(a[1]-b[1])*(c[1]-b[1])>EPS)return null;
  twice+=a[0]*b[1]-a[1]*b[0];
  for(let j=i+2;j<points.length;j++){
   if(i===0&&j===points.length-1)continue;
   if(intersects(a,b,points[j],points[(j+1)%points.length]))return null;
  }
 }
 const area=Math.abs(twice)/2;
 return Number.isFinite(area)&&area>=.0025?area:null;
}
export function localOutline(walls:readonly PlacedWall[]):LocalOutline|null{
 if(walls.length<3||walls.length>25||new Set(walls.map(w=>w.proposalId)).size!==walls.length)return null;
 const first=walls[0];
 if(walls.some(w=>w.levelId!==first.levelId||w.scopeKey!==first.scopeKey||!point(w.start)||!point(w.end)))return null;
 const edges:Edge[]=[{wall:first,reversed:false}],points:PlanPoint[]=[first.start];
 let end=first.end;const remaining=walls.slice(1);
 while(remaining.length){
  const matches=remaining.filter(w=>same(w.start,end)||same(w.end,end));
  if(matches.length!==1||same(end,points[0]))return null;
  const wall=matches[0];remaining.splice(remaining.indexOf(wall),1);
  const reversed=same(wall.end,end);points.push(end);edges.push({wall,reversed});
  end=reversed?wall.start:wall.end;
 }
 if(!same(end,points[0]))return null;
 const areaM2=outlineArea(points);return areaM2===null?null:{points,edges,areaM2};
}
function reshape(edge:Edge,a:PlanPoint,b:PlanPoint):PlacedWall|null{
 const w=edge.wall,start=edge.reversed?b:a,end=edge.reversed?a:b;
 const oldLength=distance(w.start,w.end),length=distance(start,end);
 if(length<.05-EPS||oldLength<.05-EPS)return null;
 const openings=w.openings.map(o=>{
  if(o.widthM>length+EPS)return null;
  const center=(o.offsetM+o.widthM/2)*length/oldLength;
  return {...o,offsetM:Math.max(0,Math.min(length-o.widthM,center-o.widthM/2))};
 });
 if(openings.some(o=>o===null))return null;
 const valid=openings.filter((o):o is NonNullable<typeof o>=>o!==null);
 const sorted=[...valid].sort((a,b)=>a.offsetM-b.offsetM);
 if(sorted.some((o,i)=>i>0&&o.offsetM<sorted[i-1].offsetM+sorted[i-1].widthM-EPS))return null;
 return {...w,start,end,openings:valid};
}
export function editLocalOutline(walls:readonly PlacedWall[],edit:OutlineEdit):PlacedWall[]|null{
 const ring=localOutline(walls);
 if(!ring||!Number.isInteger(edit.index)||edit.index<0||edit.index>=ring.points.length)return null;
 const points=ring.points.map(p=>[...p] as PlanPoint),edges=[...ring.edges],i=edit.index,n=points.length,j=(i+1)%n;
 if(edit.kind==="move-point"){
  const p=point(edit.point);if(!p)return null;points[i]=p;
 }else if(edit.kind==="move-edge"){
  const a=point([points[i][0]+edit.delta[0],points[i][1]+edit.delta[1]]);
  const b=point([points[j][0]+edit.delta[0],points[j][1]+edit.delta[1]]);
  if(!a||!b)return null;points[i]=a;points[j]=b;
 }else if(edit.kind==="insert-point"){
  if(n>=25||edges[i].wall.openings.length||!edit.newId||walls.some(w=>w.proposalId===edit.newId))return null;
  const p=point(edit.point);if(!p)return null;
  points.splice(i+1,0,p);edges.splice(i+1,0,{wall:{...edges[i].wall,proposalId:edit.newId,openings:[]},reversed:edges[i].reversed});
 }else{
  if(n<=3)return null;
  const prev=(i+n-1)%n;
  if(edges[prev].wall.openings.length||edges[i].wall.openings.length||edges[prev].wall.heightM!==edges[i].wall.heightM)return null;
  points.splice(i,1);edges.splice(i,1);
 }
 if(outlineArea(points)===null)return null;
 const result=edges.map((edge,k)=>reshape(edge,points[k],points[(k+1)%points.length]));
 if(result.some(w=>!w))return null;
 return result as PlacedWall[];
}
