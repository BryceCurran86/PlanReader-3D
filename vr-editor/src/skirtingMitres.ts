import * as THREE from "three";
import type {WallCornerJoins} from "./wallCornerJoin.ts";
import type {PlanPoint} from "./buildPlacement.ts";
/** Local presentation only: extend/shorten the profile at a joined wall end
 * along the corner's existing cut plane. Never bridge an opening or gap. */
export function skirtingEndCuts(start:PlanPoint,end:PlanPoint,half:number,normal:THREE.Vector3,joins?:WallCornerJoins){
 const axis=new THREE.Vector3(end[0]-start[0],0,end[1]-start[1]);
 const len=axis.length();if(!Number.isFinite(len)||len<.05||!Number.isFinite(half)||half<=0)return null;
 axis.normalize();const left=new THREE.Vector3(-axis.z,0,axis.x),side=left.dot(normal);
 if(Math.abs(Math.abs(side)-1)>1e-5)return null;
 const cut=(p:PlanPoint,pair:WallCornerJoins["start"])=>{
  if(!pair)return null;
  const along=(q:PlanPoint)=>(q[0]-p[0])*axis.x+(q[1]-p[1])*axis.z;
  const l=along(pair.left),r=along(pair.right);
  const slope=(l-r)/(2*half)*side,offset=side>0?l:r;
  if(!Number.isFinite(slope)||!Number.isFinite(offset)||Math.abs(slope)>3)return null;
  return {slope,offset};
 };
 return {start:cut(start,joins?.start),end:cut(end,joins?.end)};
}
export function applySkirtingCuts(mesh:THREE.Mesh,start:THREE.Vector3,end:THREE.Vector3,normal:THREE.Vector3,depth:number,cuts:ReturnType<typeof skirtingEndCuts>,atStart:boolean,atEnd:boolean){
 if(!cuts)return;
 const a=atStart?cuts.start:null,b=atEnd?cuts.end:null;if(!a&&!b)return;
 const axis=end.clone().sub(start),len=axis.length();if(!Number.isFinite(len)||len<=.001)return;axis.normalize();
 const p=mesh.geometry.getAttribute("position"),v=new THREE.Vector3();
 const shift=(cut:NonNullable<typeof a>|null,d:number)=>cut?cut.offset+cut.slope*d:0;
 // Reject cuts that would invert short fragments.
 if([0,depth].some(d=>len+shift(b,d)-shift(a,d)<=.001))return;
 for(let i=0;i<p.count;i++){v.fromBufferAttribute(p,i);const d=v.clone().sub(start),z=Math.max(0,Math.min(len,d.dot(axis))),x=Math.max(0,Math.min(depth,d.dot(normal)));
  v.addScaledVector(axis,shift(a,x)*(1-z/len)+shift(b,x)*z/len);p.setXYZ(i,v.x,v.y,v.z);}
 p.needsUpdate=true;mesh.geometry.computeVertexNormals();mesh.geometry.computeBoundingBox();mesh.geometry.computeBoundingSphere();
}
