import * as THREE from "three";
import type {WallVisual} from "./buildPlacement.ts";
import {openingFits,planLength} from "./buildPlacement.ts";
import {profileDetails,wallAssembly} from "./wallProfiles.ts";
type Rect={x0:number;x1:number;y0:number;y1:number};
export type TrimPiece=Rect&{kind:"skirting"|"architrave"};
const EPS=1e-7;
const SKIRT=.09,ARCH=.067,DEPTH=.015;
const valid=(r:Rect)=>r.x1-r.x0>EPS&&r.y1-r.y0>EPS;
function subtract(r:Rect,h:Rect):Rect[]{
 const x0=Math.max(r.x0,h.x0),x1=Math.min(r.x1,h.x1),y0=Math.max(r.y0,h.y0),y1=Math.min(r.y1,h.y1);
 if(x1-x0<=EPS||y1-y0<=EPS)return [r];
 return [{...r,x1:x0},{...r,x0:x1},{x0,x1,y0:r.y0,y1:y0},{x0,x1,y0:y1,y1:r.y1}].filter(valid);
}
/** Nominal local finish preview. Trim pieces never enter a wall aperture,
 * exceed a wall face, or overlap another generated strip on that face. */
export function nominalTrimLayout(wall:WallVisual):TrimPiece[]{
 const length=planLength(wall.start,wall.end),height=wall.heightM;
 if(profileDetails(wall.assembly).core==="masonry"||!Number.isFinite(length)||length<.05||length>200||!Number.isFinite(height)||height<.1||height>20)return [];
 const openings=wall.openings??[];
 if(openings.length>100||openings.some(o=>!openingFits(wall,o)))return [];
 const holes=openings.map(o=>({x0:o.offsetM,x1:o.offsetM+o.widthM,y0:o.sillHeightM,y1:o.sillHeightM+o.heightM})).sort((a,b)=>a.x0-b.x0);
 if(holes.some((h,i)=>i>0&&h.x0<holes[i-1].x1-EPS))return [];
 const pieces:TrimPiece[]=[];
 function add(kind:TrimPiece["kind"],r:Rect){
  const clipped={x0:Math.max(0,r.x0),x1:Math.min(length,r.x1),y0:Math.max(0,r.y0),y1:Math.min(height,r.y1)};
  if(!valid(clipped))return;
  let fragments=[clipped];
  for(const h of [...holes,...pieces]){
   fragments=fragments.flatMap(f=>subtract(f,h));
   if(fragments.length>500)return;
  }
  if(pieces.length+fragments.length>2000)return;
  pieces.push(...fragments.map(f=>({...f,kind})));
 }
 // Architraves first, then skirting butted to them.
 for(const h of holes){
  add("architrave",{x0:h.x0-ARCH,x1:h.x0,y0:h.y0,y1:h.y1+ARCH});
  add("architrave",{x0:h.x1,x1:h.x1+ARCH,y0:h.y0,y1:h.y1+ARCH});
  add("architrave",{x0:h.x0,x1:h.x1,y0:h.y1,y1:h.y1+ARCH});
  if(h.y0>EPS)add("architrave",{x0:h.x0-ARCH,x1:h.x1+ARCH,y0:h.y0-ARCH,y1:h.y0});
 }
 add("skirting",{x0:0,x1:length,y0:0,y1:SKIRT});
 return pieces;
}
export function nominalTrimMesh(wall:WallVisual):THREE.InstancedMesh|null{
 const pieces=nominalTrimLayout(wall);if(!pieces.length)return null;
 const a=wallAssembly(wall.assembly),profile=profileDetails(a),length=planLength(wall.start,wall.end);
 const dx=(wall.end[0]-wall.start[0])/length,dz=(wall.end[1]-wall.start[1])/length;
 const sides=profile.role==="internal"?[1,-1]:[a.exteriorSide==="left"?-1:1];
 const mesh=new THREE.InstancedMesh(new THREE.BoxGeometry(1,1,1),new THREE.MeshStandardMaterial({color:0xf4f1e8,roughness:.8}),pieces.length*sides.length);
 const obj=new THREE.Object3D();obj.rotation.y=-Math.atan2(dz,dx);
 let i=0;
 for(const side of sides)for(const p of pieces){
  const x=(p.x0+p.x1)/2,z=side*(a.thicknessMm/2000+DEPTH/2+.002);
  obj.position.set(wall.start[0]+dx*x-dz*z,(p.y0+p.y1)/2,wall.start[1]+dz*x+dx*z);
  obj.scale.set(p.x1-p.x0,p.y1-p.y0,DEPTH);obj.updateMatrix();mesh.setMatrixAt(i++,obj.matrix);
 }
 mesh.instanceMatrix.needsUpdate=true;mesh.computeBoundingBox();mesh.computeBoundingSphere();
 mesh.userData.illustrativeTrim=true;mesh.userData.trimLayout=pieces;mesh.visible=false;return mesh;
}
