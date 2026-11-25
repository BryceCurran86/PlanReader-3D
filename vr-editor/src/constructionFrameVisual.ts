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
/** Explicit closed axis-aligned rectangular shell only. Never infer a roof
 * truss from imported geometry. Use the actual generated roof's section. */
export function nominalShellFraming(shell:DraftShell){
 const group=new THREE.Group(),floor=shell.surfaces.find(s=>s.kind==="ceiling"),roof=shell.surfaces.find(s=>s.kind==="roof");
 if(!floor||!roof||!floor.vertices.length||!roof.vertices.length)return group;
 const x0=Math.min(...floor.vertices.map(p=>p[0])),x1=Math.max(...floor.vertices.map(p=>p[0]));
 const z0=Math.min(...floor.vertices.map(p=>p[2])),z1=Math.max(...floor.vertices.map(p=>p[2]));
 if(Math.abs((x1-x0)*(z1-z0)-shell.floorM2)>1e-6||x1-x0<.1||z1-z0<.1||x1-x0>20||z1-z0>20)return group;
 const ceiling=nominalCeilingFraming({start:[x0,z0],end:[x1,z1],heightM:shell.heightM-.012});
 if(ceiling)group.add(ceiling);
 const peak=Math.max(...roof.vertices.map(v=>v[1])),min=Math.min(...roof.vertices.map(v=>v[1]));
 if(peak-min<1e-5){
  const flat=nominalCeilingFraming({start:[x0,z0],end:[x1,z1],heightM:peak-.15});
  if(flat){flat.userData.constructionAccessory="roof-frame";group.add(flat);}return group;
 }
 const high=roof.vertices.filter(v=>Math.abs(v[1]-peak)<1e-6);
 const hx=Math.max(...high.map(v=>v[0]))-Math.min(...high.map(v=>v[0]));
 const hz=Math.max(...high.map(v=>v[2]))-Math.min(...high.map(v=>v[2]));
 const alongX=hz<1e-6&&Math.abs(hx-(x1-x0))<1e-6,alongZ=hx<1e-6&&Math.abs(hz-(z1-z0))<1e-6;
 if(!alongX&&!alongZ)return group;
 const length=alongX?x1-x0:z1-z0,rows=Math.ceil(length/.6),members:Member[]=[];
 for(let i=0;i<=rows;i++){
  const offset=Math.max(.025,Math.min(length-.025,i*length/rows));
  const a:Point=alongX?[x0+offset,min,z0]:[x0,min,z0+offset];
  const b:Point=alongX?[x0+offset,min,z1]:[x1,min,z0+offset];
  const top:Point=alongX?[x0+offset,peak,(z0+z1)/2]:[(x0+x1)/2,peak,z0+offset];
  for(const [start,end] of [[a,top],[top,b],[a,b]])members.push({a:start,b:end,width:.045,depth:.14});
 }
 const frame=memberMesh(members,0xc99c65,"roof-frame");if(frame)group.add(frame);
 return group;
}
