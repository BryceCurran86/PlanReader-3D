import * as THREE from "three";
import type {WallVisual,CeilingDraft} from "./buildPlacement.ts";
import {planLength,openingFits} from "./buildPlacement.ts";
import {wallAssembly,profileDetails} from "./wallProfiles.ts";
import type {DraftShell} from "./connectedDraftShell.ts";

type Point=[number,number,number];
type Member={a:Point;b:Point;width:number;depth:number};
function memberMesh(members:Member[],color:number,kind:string){
 if(!members.length)return null;
 const mesh=new THREE.InstancedMesh(new THREE.BoxGeometry(1,1,1),new THREE.MeshStandardMaterial({color,roughness:.85}),members.length);
 const a=new THREE.Vector3(),b=new THREE.Vector3(),up=new THREE.Vector3(0,1,0),dir=new THREE.Vector3(),obj=new THREE.Object3D();
 members.forEach((m,i)=>{
  a.set(...m.a);b.set(...m.b);dir.subVectors(b,a);
  obj.position.copy(a).addScaledVector(dir,.5);
  obj.quaternion.setFromUnitVectors(up,dir.clone().normalize());
  obj.scale.set(m.width,dir.length(),m.depth);obj.updateMatrix();mesh.setMatrixAt(i,obj.matrix);
 });
 mesh.instanceMatrix.needsUpdate=true;mesh.computeBoundingBox();mesh.computeBoundingSphere();
 mesh.userData.constructionAccessory=kind;mesh.visible=false;return mesh;
}
/** Explicit illustrative connections, not a bracing capacity or tie-down schedule.
 * Straps are shown only in a full solid bay; no straps cross an aperture. */
export function nominalWallConnections(wall:WallVisual){
 const group=new THREE.Group();
 const length=planLength(wall.start,wall.end),h=wall.heightM,assembly=wallAssembly(wall.assembly),p=profileDetails(assembly);
 if(p.core!=="timber"||!Number.isFinite(length)||length<.3||length>200||!Number.isFinite(h)||h<.4||h>20)return group;
 const holes=(wall.openings??[]).filter(o=>openingFits(wall,o));
 const dx=(wall.end[0]-wall.start[0])/length,dz=(wall.end[1]-wall.start[1])/length,depth=Math.min(p.frameMm,assembly.thicknessMm)/2000;
 const point=(x:number,y:number,z:number):Point=>[wall.start[0]+dx*x-dz*z,y,wall.start[1]+dz*x+dx*z];
 const free=(a:number,b:number)=>holes.every(o=>o.offsetM>=b||o.offsetM+o.widthM<=a);
 const ties:Member[]=[],straps:Member[]=[];
 for(const x of [.0675,length-.0675]){
  if(free(x-.02,x+.02))ties.push({a:point(x,.015,depth+.012),b:point(x,.28,depth+.012),width:.035,depth:.008});
 }
 // At most one explicitly illustrative diagonal X per wall; do not imply compliance.
 for(let start=.045;start+1.35<=length-.045;start+=.45){
  if(!free(start,start+1.35))continue;
  straps.push({a:point(start,.09,depth+.025),b:point(start+1.35,h-.09,depth+.025),width:.035,depth:.008});
  straps.push({a:point(start+1.35,.09,depth+.035),b:point(start,h-.09,depth+.035),width:.035,depth:.008});break;
 }
 const brace=memberMesh(straps,0x89949b,"bracing"),tie=memberMesh(ties,0xa6a9aa,"tie-down");
 if(brace)group.add(brace);if(tie)group.add(tie);
 return group;
}
/** Visual-only joists/battens for an explicit rectangular ceiling draft. */
export function nominalCeilingFraming(ceiling:Pick<CeilingDraft,"start"|"end"|"heightM">){
 const x0=Math.min(ceiling.start[0],ceiling.end[0]),x1=Math.max(ceiling.start[0],ceiling.end[0]);
 const z0=Math.min(ceiling.start[1],ceiling.end[1]),z1=Math.max(ceiling.start[1],ceiling.end[1]),h=ceiling.heightM;
 if(![x0,x1,z0,z1,h].every(Number.isFinite)||x1-x0<.1||z1-z0<.1||x1-x0>20||z1-z0>20||h<.1||h>20)return null;
 const alongX=x1-x0<=z1-z0,span=alongX?z1-z0:x1-x0,rows=Math.ceil(span/.6);
 const members:Member[]=[];
 for(let i=0;i<=rows;i++){
  const offset=Math.min(span-.0225,Math.max(.0225,i*span/rows));
  members.push({a:alongX?[x0,h+.07,z0+offset]:[x0+offset,h+.07,z0],b:alongX?[x1,h+.07,z0+offset]:[x0+offset,h+.07,z1],width:.045,depth:.14});
 }
 return memberMesh(members,0xc99c65,"ceiling-frame");
}
/** Nominal parallel members clipped to explicit draft surface triangles.
 * Vertical roof closures are excluded. Never bridge a recess or imply a designed truss. */
export function clippedSurfaceMembers(vertices:readonly Point[],direction:[number,number],spacing=.6,verticalOffset=0):Member[]{
 if(vertices.length<3||vertices.length%3!==0||vertices.length>6000||!Number.isFinite(spacing)||spacing<.2||spacing>1||!Number.isFinite(verticalOffset))return [];
 const d=Math.hypot(...direction);if(!Number.isFinite(d)||d<1e-7)return [];
 const ux=direction[0]/d,uz=direction[1]/d;
 const along=(p:Point)=>p[0]*ux+p[2]*uz,across=(p:Point)=>-p[0]*uz+p[2]*ux;
 const triangles:Point[][]=[];
 for(let i=0;i<vertices.length;i+=3){
  const [a,b,c]=vertices.slice(i,i+3);
  if(![...a,...b,...c].every(Number.isFinite))return [];
  if(Math.abs((b[0]-a[0])*(c[2]-a[2])-(b[2]-a[2])*(c[0]-a[0]))>1e-8)triangles.push([a,b,c]);
 }
 if(!triangles.length)return [];
 const points=triangles.flat(),min=Math.min(...points.map(across)),max=Math.max(...points.map(across));
 if(max-min<.05||max-min>100||Math.max(...points.map(along))-Math.min(...points.map(along))>100)return [];
 const count=Math.ceil((max-min)/spacing),result:Member[]=[];
 for(let i=0;i<=count;i++){
  const cross=min+Math.min(max-min-.015,Math.max(.015,i*(max-min)/count));
  const sections:{lo:number;hi:number;y0:number;y1:number}[]=[];
  for(const tri of triangles){
   const hits:Point[]=[];
   for(let j=0;j<3;j++){
    const a=tri[j],b=tri[(j+1)%3],da=across(a)-cross,db=across(b)-cross;
    if(Math.abs(da)<1e-8)hits.push(a);
    if(da*db< -1e-16){const t=da/(da-db);hits.push([a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,a[2]+(b[2]-a[2])*t]);}
   }
   hits.sort((a,b)=>along(a)-along(b));
   if(hits.length<2)continue;
   const a=hits[0],b=hits[hits.length-1],lo=along(a),hi=along(b);
   if(hi-lo>1e-6)sections.push({lo,hi,y0:a[1],y1:b[1]});
  }
  sections.sort((a,b)=>a.lo-b.lo);
  const joined:typeof sections=[];
  for(const s of sections){
   const prev=joined[joined.length-1];
   if(prev&&Math.abs(prev.hi-s.lo)<1e-6&&Math.abs(prev.y1-s.y0)<1e-6&&Math.abs((prev.y1-prev.y0)/(prev.hi-prev.lo)-(s.y1-s.y0)/(s.hi-s.lo))<1e-6){prev.hi=s.hi;prev.y1=s.y1;}
   else if(!prev||s.hi>prev.hi+1e-6)joined.push({...s});
  }
  const point=(a:number,y:number):Point=>[a*ux-cross*uz,y+verticalOffset,a*uz+cross*ux];
  for(const s of joined)if(s.hi-s.lo>.025)result.push({a:point(s.lo,s.y0),b:point(s.hi,s.y1),width:.045,depth:.14});
 }
 return result;
}
export function nominalShellFraming(shell:DraftShell){
 const group=new THREE.Group(),ceiling=shell.surfaces.find(s=>s.kind==="ceiling"),roof=shell.surfaces.find(s=>s.kind==="roof");
 if(!ceiling||!roof||!ceiling.vertices.length||!roof.vertices.length)return group;
 const xs=ceiling.vertices.map(p=>p[0]),zs=ceiling.vertices.map(p=>p[2]);
 const xSpan=Math.max(...xs)-Math.min(...xs),zSpan=Math.max(...zs)-Math.min(...zs);
 const direction:[number,number]=xSpan<=zSpan?[1,0]:[0,1];
 let roofDirection=direction;
 for(let i=0;i<roof.vertices.length;i+=3){
  const [a,b,c]=roof.vertices.slice(i,i+3);
  const ux=b[0]-a[0],uy=b[1]-a[1],uz=b[2]-a[2],vx=c[0]-a[0],vy=c[1]-a[1],vz=c[2]-a[2];
  const ny=uz*vx-ux*vz,nx=uy*vz-uz*vy,nz=ux*vy-uy*vx;
  if(Math.abs(ny)>1e-8&&Math.hypot(nx,nz)>1e-8){roofDirection=[nx,nz];break;}
 }
 const frame=memberMesh(clippedSurfaceMembers(ceiling.vertices,direction,.6,.07),0xc99c65,"ceiling-frame");
 const rafters=memberMesh(clippedSurfaceMembers(roof.vertices,roofDirection,.6,-.07),0xc99c65,"roof-frame");
 if(frame)group.add(frame);if(rafters)group.add(rafters);
 return group;
}
