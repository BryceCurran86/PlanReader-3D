import * as THREE from "three";
import type {DraftGesture} from "./buildScene.ts";
import {snappedPoint} from "./buildPlacement.ts";
import type {PlacedWall,CeilingDraft,PlanPoint} from "./buildPlacement.ts";
export type HandleShape={kind:"wall";object:PlacedWall}|{kind:"ceiling";object:CeilingDraft};
export type DraftHandle={position:[number,number,number];mode:"move"|"stretch";anchor:PlanPoint;stretchStart?:boolean};
const RADIUS=.13;
export function draftHandlePoints(shape:HandleShape):DraftHandle[]{
 const {start:a,end:b,heightM}=shape.object,y=heightM+.16;
 const centre:PlanPoint=[(a[0]+b[0])/2,(a[1]+b[1])/2];
 const at=(p:PlanPoint):[number,number,number]=>[p[0],y,p[1]];
 const move:DraftHandle={position:at(centre),mode:"move",anchor:centre};
 if(shape.kind==="wall"){
  if(Math.hypot(a[0]-b[0],a[1]-b[1])<.6)return [move];
  return [move,{position:at(a),mode:"stretch",anchor:b,stretchStart:true},
   {position:at(b),mode:"stretch",anchor:a,stretchStart:false}];
 }
 const x0=Math.min(a[0],b[0]),x1=Math.max(a[0],b[0]),z0=Math.min(a[1],b[1]),z1=Math.max(a[1],b[1]);
 if(x1-x0<.6||z1-z0<.6)return [move];
 const corners:PlanPoint[]=[[x0,z0],[x1,z0],[x1,z1],[x0,z1]];
 return [move,...corners.map((p,i):DraftHandle=>({position:at(p),mode:"stretch",anchor:corners[(i+2)%4]}))];
}
export function pickDraftEditHandle(shape:HandleShape,ray:THREE.Ray):DraftGesture|null{
 const points=draftHandlePoints(shape);
 const hits=points.map(h=>({h,p:new THREE.Vector3(...h.position)}))
  .filter(({p})=>p.clone().sub(ray.origin).dot(ray.direction)>=0&&ray.distanceSqToPoint(p)<=RADIUS*RADIUS)
  .sort((a,b)=>ray.distanceSqToPoint(a.p)-ray.distanceSqToPoint(b.p));
 if(!hits.length)return null;
 const floor=ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0,1,0),0),new THREE.Vector3());
 const from=floor?snappedPoint([floor.x,floor.z]):snappedPoint([hits[0].p.x,hits[0].p.z]);
 if(!from)return null;
 const h=hits[0].h;
 const shared={mode:h.mode,from,anchor:h.anchor,levelId:shape.object.levelId,direct:true as const,stretchStart:h.stretchStart};
 return shape.kind==="wall"?{...shared,kind:"wall",previous:shape.object}:{...shared,kind:"ceiling",previous:shape.object};
}
export function createDraftEditHandles(){
 const group=new THREE.Group();group.name="DraftEditHandles";group.visible=false;
 const meshes=Array.from({length:5},(_,i)=>{
  const mesh=new THREE.Mesh(new THREE.SphereGeometry(RADIUS,12,8),new THREE.MeshBasicMaterial({color:i===0?0x16ad83:0xffc34c,depthTest:false}));
  mesh.renderOrder=20;mesh.visible=false;group.add(mesh);return mesh;
 });
 let previous:HandleShape|null=null;
 return {group,update(shape:HandleShape|null){
  group.visible=shape!==null;
  if(!shape){previous=null;return;}
  if(previous?.object===shape.object&&previous.kind===shape.kind)return;
  previous=shape;
  const points=draftHandlePoints(shape);
  meshes.forEach((m,i)=>{m.visible=!!points[i];if(points[i])m.position.set(...points[i].position);});
 }};
}
