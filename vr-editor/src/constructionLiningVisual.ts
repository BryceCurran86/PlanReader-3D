import * as THREE from "three";
import {nominalLiningLayout} from "./constructionDetailLayout.ts";
import type {Rect} from "./constructionDetailLayout.ts";
export type LiningFinish="sheeted"|"set"|"sanded"|"undercoat";
export type LiningBoard="standard"|"wet-area"|"fire-rated";
const paper:Record<LiningBoard,number>={standard:0xb1b3ad,"wet-area":0xa0b7a0,"fire-rated":0xc3a2a2};
export const LINING_BOARDS=["standard","wet-area","fire-rated"] as const;
const finishes:LiningFinish[]=["sheeted","set","sanded","undercoat"];
const parts=["paper","edge","compound","screw"] as const;
type Project=(x:number,y:number,offset:number)=>THREE.Vector3;
type Point2=[number,number];
type Triangle2=[Point2,Point2,Point2];
const MAX_LINING_VERTICES=150_000;
const CELL=1.2;
function spatialIndex<T>(items:readonly T[],bounds:(item:T)=>Rect){
 const cells=new Map<string,T[]>();
 const cell=(v:number)=>Math.floor(v/CELL);
 for(const item of items){
  const r=bounds(item);
  for(let x=cell(r.x0);x<=cell(r.x1);x++)for(let y=cell(r.y0);y<=cell(r.y1);y++){
   const key=x+":"+y,list=cells.get(key);
   if(list)list.push(item);else cells.set(key,[item]);
  }
 }
 return (r:Rect):T[]=>{
  const found=new Set<T>();
  for(let x=cell(r.x0);x<=cell(r.x1);x++)for(let y=cell(r.y0);y<=cell(r.y1);y++)for(const item of cells.get(x+":"+y)??[])found.add(item);
  return [...found];
 };
}
const triangleBounds=(t:Triangle2):Rect=>({x0:Math.min(t[0][0],t[1][0],t[2][0]),x1:Math.max(t[0][0],t[1][0],t[2][0]),y0:Math.min(t[0][1],t[1][1],t[2][1]),y1:Math.max(t[0][1],t[1][1],t[2][1])});
const cross=(a:Point2,b:Point2,p:Point2)=>(b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]);
function clipTriangle(poly:Point2[],tri:Triangle2){
 const sign=Math.sign(cross(tri[0],tri[1],tri[2]));if(!sign)return [];
 for(let i=0;i<3;i++){
  const a=tri[i],b=tri[(i+1)%3],next:Point2[]=[];
  for(let j=0;j<poly.length;j++){
   const p=poly[j],q=poly[(j+1)%poly.length],u=sign*cross(a,b,p),v=sign*cross(a,b,q);
   if(u>=-1e-9)next.push(p);
   if((u< -1e-9)!==(v< -1e-9)){const t=u/(u-v);next.push([p[0]+(q[0]-p[0])*t,p[1]+(q[1]-p[1])*t]);}
  }
  poly=next;if(poly.length<3)return [];
 }
 return poly;
}
const palette=(board:LiningBoard,part:"paper"|"edge"|"compound"|"screw",strength:number)=>{
 const base=new THREE.Color(paper[board]);
 const white=new THREE.Color(0xf2eee6);
 return finishes.map(stage=>{
  if(stage==="undercoat")return new THREE.Color(0xeeeae1);
  if(stage==="sheeted")return part==="screw"?new THREE.Color(0x575b56):part==="edge"?base.clone().multiplyScalar(.72):base.clone();
  if(part==="paper")return base.clone();
  return base.clone().lerp(white,Math.min(1,strength*(stage==="sanded"?.83:1)));
 });
};
/** Batched metric geometry, no canvas, no per-frame texture uploads. Only local review surfaces. */
export function makeLiningVisual(width:number,height:number,holes:readonly Rect[],project:Project,board:LiningBoard="standard",triangles?:readonly Triangle2[]){
 let layout:ReturnType<typeof nominalLiningLayout>;
 try{layout=nominalLiningLayout(width,height,holes);}catch{return null;}
 const positions:number[]=[],samples:number[]=[];
 const nearbyBoards=spatialIndex(layout.boards,b=>b),nearbyTriangles=triangles?spatialIndex(triangles,triangleBounds):null;
 let overBudget=false;
 function quad(r:Rect,offset:number,part:"paper"|"edge"|"compound"|"screw",strength:number){
  if(overBudget||r.x1-r.x0<1e-7||r.y1-r.y0<1e-7)return;
  const pts:Point2[]=[[r.x0,r.y0],[r.x1,r.y0],[r.x1,r.y1],[r.x0,r.y1]];
  const sample=parts.indexOf(part)*256+Math.round(strength*100);
  const polygons=nearbyTriangles?nearbyTriangles(r).map(t=>clipTriangle(pts,t)):[pts];
  for(const poly of polygons)for(let i=1;i+1<poly.length;i++){
   if(Math.abs(cross(poly[0],poly[i],poly[i+1]))<1e-10)continue;
   if(samples.length+3>MAX_LINING_VERTICES){overBudget=true;return;}
   for(const p of [poly[0],poly[i],poly[i+1]]){positions.push(...project(p[0],p[1],offset).toArray());samples.push(sample);}
  }
 }
 // Clip every detail band to the original solid board pieces, including apertures.
 function detail(r:Rect,offset:number,part:"edge"|"compound"|"screw",strength:number){
  if(overBudget)return;
  for(const b of nearbyBoards(r)){
   quad({x0:Math.max(b.x0,r.x0),x1:Math.min(b.x1,r.x1),y0:Math.max(b.y0,r.y0),y1:Math.min(b.y1,r.y1)},offset,part,strength);
  }
 }
 for(const b of layout.boards)quad(b,.001,"paper",0);
 for(const j of layout.joints){
  if(overBudget)return null;
  const band=(half:number,offset:number,strength:number,part:"edge"|"compound")=>detail(j.axis==="horizontal"?
    {x0:j.from,x1:j.to,y0:j.at-half,y1:j.at+half}:
    {x0:j.at-half,x1:j.at+half,y0:j.from,y1:j.to},offset,part,strength);
  const half=j.kind==="butt"?.15:j.kind==="perimeter"?.075:.105;
  band(half,.002,.18,"compound");
  band(half*.68,.003,.48,"compound");
  band(half*.38,.004,.88,"compound");
  band(.0015,.005,.96,"edge");
 }
 for(const f of layout.fixings){
  if(overBudget)return null;
  detail({x0:f.x-.021,x1:f.x+.021,y0:f.y-.016,y1:f.y+.016},.006,"compound",.55);
  detail({x0:f.x-.009,x1:f.x+.009,y0:f.y-.008,y1:f.y+.008},.007,"screw",.95);
 }
 if(overBudget||!positions.length)return null;
 const geometry=new THREE.BufferGeometry().setAttribute("position",new THREE.Float32BufferAttribute(positions,3));
 geometry.computeVertexNormals();
 geometry.setAttribute("color",new THREE.BufferAttribute(new Float32Array(positions.length),3));
 const mesh=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color:0xffffff,vertexColors:true,side:THREE.DoubleSide,roughness:.92}));
 mesh.userData.illustrativeLining=true;
 mesh.userData.liningSamples=new Uint16Array(samples);
 setLiningAppearance(mesh,"set",board);
 mesh.visible=false;
 return mesh;
}
export function setLiningAppearance(mesh:THREE.Mesh,finish:LiningFinish,board:LiningBoard="standard"){
 if(!mesh.userData.illustrativeLining||!LINING_BOARDS.includes(board)||!finishes.includes(finish)||
   (mesh.userData.liningFinish===finish&&mesh.userData.liningBoard===board))return;
 const samples=mesh.userData.liningSamples,attribute=mesh.geometry.getAttribute("color");
 if(!(samples instanceof Uint16Array)||!(attribute instanceof THREE.BufferAttribute)||samples.length!==attribute.count)return;
 const cache=new Map<number,THREE.Color>();
 for(let i=0;i<samples.length;i++){
  const sample=samples[i];let shade=cache.get(sample);
  if(!shade){shade=palette(board,parts[Math.floor(sample/256)],(sample%256)/100)[finishes.indexOf(finish)];cache.set(sample,shade);}
  attribute.setXYZ(i,shade.r,shade.g,shade.b);
 }
 attribute.needsUpdate=true;mesh.userData.liningFinish=finish;mesh.userData.liningBoard=board;
}
export function setLiningFinish(mesh:THREE.Mesh,finish:LiningFinish){
 setLiningAppearance(mesh,finish,mesh.userData.liningBoard??"standard");
}

// Generated flat ceiling only: clip every sheet, seam and screw patch to the actual footprint.
export function makeShellCeilingLining(vertices:readonly [number,number,number][]){
 if(vertices.length<3||vertices.length%3!==0||vertices.length>600||!vertices.every(p=>p.every(Number.isFinite)))return null;
 const y=vertices[0][1];if(vertices.some(p=>Math.abs(p[1]-y)>1e-5))return null;
 const x0=Math.min(...vertices.map(p=>p[0])),x1=Math.max(...vertices.map(p=>p[0]));
 const z0=Math.min(...vertices.map(p=>p[2])),z1=Math.max(...vertices.map(p=>p[2]));
 if(x1-x0>20||z1-z0>20)return null;
 const triangles:Triangle2[]=[];
 for(let i=0;i<vertices.length;i+=3)triangles.push(vertices.slice(i,i+3).map(p=>[p[0]-x0,p[2]-z0] as Point2) as Triangle2);
 return makeLiningVisual(x1-x0,z1-z0,[],(x,z,offset)=>new THREE.Vector3(x+x0,y-offset,z+z0),"standard",triangles);
}
