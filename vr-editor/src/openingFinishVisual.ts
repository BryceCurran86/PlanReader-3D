import * as THREE from "three";
import {RoundedBoxGeometry} from "three/addons/geometries/RoundedBoxGeometry.js";
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
 const mesh=new THREE.Mesh(new RoundedBoxGeometry(o.widthM-.014,o.heightM-.014,.038,2,.0025),new THREE.MeshStandardMaterial({color:0xb68b60,roughness:.72}));
 mesh.position.set(wall.start[0]+dx*(o.offsetM+o.widthM/2),o.sillHeightM+o.heightM/2,wall.start[1]+dz*(o.offsetM+o.widthM/2));
 mesh.rotation.y=-Math.atan2(dz,dx);mesh.userData.nominalDoorSlab=true;return mesh;
}

/** Recessed glazing perimeter, sash rails and sill, using just two instanced
 * draws per window. No extra clear opening or source dimensions are asserted. */
export function windowDetailVisual(wall:WallVisual,o:WallAdditionOpening):THREE.InstancedMesh[]{
 if(o.openingKind!=="window"||!openingFits(wall,o)||o.widthM<.3||o.heightM<.3)return [];
 const l=planLength(wall.start,wall.end),dx=(wall.end[0]-wall.start[0])/l,dz=(wall.end[1]-wall.start[1])/l;
 const w=o.widthM,h=o.heightM,depth=wallAssembly(wall.assembly).thicknessMm/1000;
 const t=Math.min(.045,w/8,h/8),g=.008;
 type Strip=[number,number,number,number,number,number];
 const seals:Strip[]=[[t+g/2,h/2,g,h-2*t,.014,0],[w-t-g/2,h/2,g,h-2*t,.014,0],[w/2,t+g/2,w-2*t-2*g,g,.014,0],[w/2,h-t-g/2,w-2*t-2*g,g,.014,0]];
 const aluminium:Strip[]=[[w/2,t*.45,w-2*t,t*.35,depth+.018,0],[w/2,h-t*.45,w-2*t,t*.25,depth*.66,0]];
 // Wide openings get a slim centre sash mullion. This is illustrative
 // joinery, not a verified window type or a change to the host aperture.
 if(w>=1.25){aluminium.push([w/2,h/2,.032,h-2*t,.045,0]);}
 const obj=new THREE.Object3D();obj.rotation.y=-Math.atan2(dz,dx);
 function batch(rows:Strip[],color:number,metalness:number,roughness:number,name:string){
  const mesh=new THREE.InstancedMesh(new THREE.BoxGeometry(1,1,1),new THREE.MeshStandardMaterial({color,metalness,roughness}),rows.length);
  rows.forEach(([x,y,sx,sy,sz,offset],i)=>{obj.position.set(wall.start[0]+dx*(o.offsetM+x)-dz*offset,o.sillHeightM+y,wall.start[1]+dz*(o.offsetM+x)+dx*offset);obj.scale.set(sx,sy,sz);obj.updateMatrix();mesh.setMatrixAt(i,obj.matrix);});
  mesh.instanceMatrix.needsUpdate=true;mesh.computeBoundingBox();mesh.computeBoundingSphere();mesh.name=name;mesh.userData.nominalOpeningFrame=true;mesh.receiveShadow=true;return mesh;
 }
 return [batch(seals,0x252a2b,0,.93,"Window glazing seals"),batch(aluminium,0x4a5357,.52,.38,"Window sash and sill")];
}
