import * as THREE from "three";
import {nominalLiningLayout} from "./constructionDetailLayout.ts";
import type {Rect} from "./constructionDetailLayout.ts";
export type LiningFinish="sheeted"|"set"|"sanded"|"undercoat";
export type LiningBoard="standard"|"wet-area"|"fire-rated";
const paper:Record<LiningBoard,number>={standard:0xb1b3ad,"wet-area":0xa0b7a0,"fire-rated":0xc3a2a2};
const finishes:LiningFinish[]=["sheeted","set","sanded","undercoat"];
type Project=(x:number,y:number,offset:number)=>THREE.Vector3;
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
export function makeLiningVisual(width:number,height:number,holes:readonly Rect[],project:Project,board:LiningBoard="standard"){
 let layout:ReturnType<typeof nominalLiningLayout>;
 try{layout=nominalLiningLayout(width,height,holes);}catch{return null;}
 const positions:number[]=[],colors=finishes.map(()=>[] as number[]);
 function quad(r:Rect,offset:number,part:"paper"|"edge"|"compound"|"screw",strength:number){
  if(r.x1-r.x0<1e-7||r.y1-r.y0<1e-7)return;
  const pts=[[r.x0,r.y0],[r.x1,r.y0],[r.x1,r.y1],[r.x0,r.y1]];
  const shades=palette(board,part,strength);
  for(const i of [0,1,2,0,2,3]){
   positions.push(...project(pts[i][0],pts[i][1],offset).toArray());
   shades.forEach((c,j)=>colors[j].push(c.r,c.g,c.b));
  }
 }
 // Clip every detail band to the original solid board pieces, including apertures.
 function detail(r:Rect,offset:number,part:"edge"|"compound"|"screw",strength:number){
  for(const b of layout.boards){
   quad({x0:Math.max(b.x0,r.x0),x1:Math.min(b.x1,r.x1),y0:Math.max(b.y0,r.y0),y1:Math.min(b.y1,r.y1)},offset,part,strength);
  }
 }
 for(const b of layout.boards)quad(b,.001,"paper",0);
 for(const j of layout.joints){
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
  detail({x0:f.x-.021,x1:f.x+.021,y0:f.y-.016,y1:f.y+.016},.006,"compound",.55);
  detail({x0:f.x-.009,x1:f.x+.009,y0:f.y-.008,y1:f.y+.008},.007,"screw",.95);
 }
 if(!positions.length)return null;
 const geometry=new THREE.BufferGeometry().setAttribute("position",new THREE.Float32BufferAttribute(positions,3));
 geometry.computeVertexNormals();
 const attributes=colors.map(c=>new THREE.Float32BufferAttribute(c,3));
 geometry.setAttribute("color",attributes[1]);
 const mesh=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color:0xffffff,vertexColors:true,side:THREE.DoubleSide,roughness:.92}));
 mesh.userData.illustrativeLining=true;
 mesh.userData.liningColors=attributes;
 mesh.userData.liningFinish="set";
 mesh.userData.liningBoard=board;
 mesh.visible=false;
 return mesh;
}
export function setLiningFinish(mesh:THREE.Mesh,finish:LiningFinish){
 if(!mesh.userData.illustrativeLining||mesh.userData.liningFinish===finish)return;
 const attribute=mesh.userData.liningColors?.[finishes.indexOf(finish)];
 if(attribute instanceof THREE.BufferAttribute){mesh.geometry.setAttribute("color",attribute);mesh.userData.liningFinish=finish;}
}
