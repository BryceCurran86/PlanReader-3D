import * as THREE from "three";
import {trimRun} from "./catalogueGeometry.ts";
import type {ItemVisual} from "./itemCatalogue.ts";
type TrimSpec=Extract<ItemVisual,{kind:"trim"}>;
/** Three nominal trim members with complementary 45-degree cuts.
 * Coordinates describe the existing opening only; no aperture changes. */
export function architraveMitres(left:THREE.Vector3,right:THREE.Vector3,bottom:number,normal:THREE.Vector3,spec:TrimSpec){
 const group=new THREE.Group();
 const up=new THREE.Vector3(0,1,0),along=right.clone().sub(left);
 const span=along.length(),height=left.y-bottom,w=spec.widthM;
 if(![span,height,w,spec.depthM].every(Number.isFinite)||span<=.001||height<=.001||w<=0||spec.depthM<=0||Math.abs(left.y-right.y)>1e-6||w>height/2)return group;
 along.normalize();
 const add=(start:THREE.Vector3,end:THREE.Vector3,across:THREE.Vector3)=>{
  const mesh=trimRun(start,end,across,normal,spec);if(!mesh)return;
  const axis=end.clone().sub(start).normalize(),len=start.distanceTo(end);
  const pos=mesh.geometry.getAttribute("position"),v=new THREE.Vector3();
  for(let i=0;i<pos.count;i++){
   v.fromBufferAttribute(pos,i);const delta=v.clone().sub(start),x=Math.max(0,Math.min(w,delta.dot(across))),z=delta.dot(axis);
   // Jambs extend toward the outer corner. Head begins/ends at the
   // corresponding diagonal; the profile cross-section is unchanged.
   const next=z*(len+x)/len;
   v.addScaledVector(axis,next-z);pos.setXYZ(i,v.x,v.y,v.z);
  }
  pos.needsUpdate=true;mesh.geometry.computeVertexNormals();mesh.geometry.computeBoundingBox();mesh.geometry.computeBoundingSphere();group.add(mesh);
 };
 const a=left.clone();a.y=bottom;const b=right.clone();b.y=bottom;
 add(a,left,along.clone().negate());add(b,right,along);
 // At inner edge of head (x=0) use opening span; at outer edge
 // (x=w) extend to the outside of both jambs.
 const start=left.clone().addScaledVector(along,-w),end=right.clone().addScaledVector(along,w);
 // Shear from outside-length baseline to inner-length using inverted cut.
 const head=trimRun(start,end,up,normal,spec);
 if(head){const pos=head.geometry.getAttribute("position"),len=start.distanceTo(end),v=new THREE.Vector3();
  for(let i=0;i<pos.count;i++){v.fromBufferAttribute(pos,i);const d=v.clone().sub(start),x=Math.max(0,Math.min(w,d.dot(up))),z=d.dot(along),inset=w-x;v.addScaledVector(along,inset+z*(len-2*inset)/len-z);pos.setXYZ(i,v.x,v.y,v.z);}
  pos.needsUpdate=true;head.geometry.computeVertexNormals();head.geometry.computeBoundingBox();head.geometry.computeBoundingSphere();group.add(head);
 }
 return group;
}
