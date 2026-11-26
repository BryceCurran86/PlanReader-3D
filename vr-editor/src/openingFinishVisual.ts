import * as THREE from "three";
import type {WallVisual} from "./buildPlacement.ts";
import {openingFits,planLength} from "./buildPlacement.ts";
import type {WallAdditionOpening} from "./wallAdditionProtocol.ts";
import {wallAssembly} from "./wallProfiles.ts";
/** Presentation-only frame within the existing aperture. No change to
 * clearances, source geometry, walkability or construction certification. */
export function openingFrameVisual(wall:WallVisual,o:WallAdditionOpening):THREE.InstancedMesh|null{
 if(!openingFits(wall,o)||o.openingKind==="passage")return null;
 const l=planLength(wall.start,wall.end),w=o.widthM,h=o.heightM;
 if(l<.05||w<.25||h<.25)return null;
 const t=Math.min(o.openingKind==="window"?.045:.035,w/8,h/8);
 // Span the nominal assembly, including thick external masonry, rather than leaving a floating jamb.
 const depth=wallAssembly(wall.assembly).thicknessMm/1000;
 const boxes=[[t/2,h/2,t,h],[w-t/2,h/2,t,h],[w/2,h-t/2,w-2*t,t]];
 if(o.openingKind==="window")boxes.push([w/2,t/2,w-2*t,t]);
 const dx=(wall.end[0]-wall.start[0])/l,dz=(wall.end[1]-wall.start[1])/l;
 const frame=new THREE.InstancedMesh(new THREE.BoxGeometry(1,1,1),new THREE.MeshStandardMaterial({color:o.openingKind==="window"?0x4b5558:0xe8e6df,roughness:.65}),boxes.length);
 const obj=new THREE.Object3D();obj.rotation.y=-Math.atan2(dz,dx);
 for(const [i,[x,y,sx,sy]] of boxes.entries()){
  obj.position.set(wall.start[0]+dx*(o.offsetM+x),o.sillHeightM+y,wall.start[1]+dz*(o.offsetM+x));
  obj.scale.set(sx,sy,depth);obj.updateMatrix();frame.setMatrixAt(i,obj.matrix);
 }
 frame.instanceMatrix.needsUpdate=true;frame.computeBoundingBox();frame.computeBoundingSphere();
 frame.userData.nominalOpeningFrame=true;return frame;
}
export function nominalDoorSlab(wall:WallVisual,o:WallAdditionOpening):THREE.Mesh|null{
 if(o.openingKind!=="door"||!openingFits(wall,o)||o.widthM<.25||o.heightM<.25)return null;
 const l=planLength(wall.start,wall.end),dx=(wall.end[0]-wall.start[0])/l,dz=(wall.end[1]-wall.start[1])/l;
 const mesh=new THREE.Mesh(new THREE.BoxGeometry(o.widthM-.014,o.heightM-.014,.038),new THREE.MeshStandardMaterial({color:0xb68b60,roughness:.72}));
 mesh.position.set(wall.start[0]+dx*(o.offsetM+o.widthM/2),o.sillHeightM+o.heightM/2,wall.start[1]+dz*(o.offsetM+o.widthM/2));
 mesh.rotation.y=-Math.atan2(dz,dx);mesh.userData.nominalDoorSlab=true;return mesh;
}
