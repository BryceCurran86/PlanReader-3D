import * as THREE from "three";
import {mergeGeometries} from "three/addons/utils/BufferGeometryUtils.js";
import {openingFits,planLength} from "./buildPlacement.ts";
import type {WallVisual} from "./buildPlacement.ts";
import type {WallAdditionOpening} from "./wallAdditionProtocol.ts";
import {wallAssembly,profileDetails} from "./wallProfiles.ts";
/** Nominal local construction preview, not an installation specification.
 * Fixed jamb stops, sill and hinge knuckles are separate from the moving leaf.
 * Two batched meshes, at most, regardless of the number of small parts. */
export function doorJunctionDetails(wall:WallVisual,opening:WallAdditionOpening):THREE.Mesh[]{
 if(opening.openingKind!=="door"||!openingFits(wall,opening)||opening.widthM<.4||opening.heightM<1.2||opening.doorMechanism==="garage")return [];
 const length=planLength(wall.start,wall.end),dx=(wall.end[0]-wall.start[0])/length,dz=(wall.end[1]-wall.start[1])/length;
 const w=opening.widthM,h=opening.heightM,assembly=wallAssembly(wall.assembly),depth=assembly.thicknessMm/1000;
 const ext=profileDetails(assembly).role==="external",swing=(opening.doorMechanism??"swing")==="swing";
 const frame:THREE.BufferGeometry[]=[],metal:THREE.BufferGeometry[]=[];
 function add(parts:THREE.BufferGeometry[],geometry:THREE.BufferGeometry,x:number,y:number,z:number){
  const g=geometry.index?geometry.toNonIndexed():geometry;
  if(g!==geometry)geometry.dispose();
  g.rotateY(-Math.atan2(dz,dx));
  g.translate(wall.start[0]+dx*(opening.offsetM+x)-dz*z,opening.sillHeightM+y,wall.start[1]+dz*(opening.offsetM+x)+dx*z);
  parts.push(g);
 }
 const strip=(parts:THREE.BufferGeometry[],x:number,y:number,z:number,sx:number,sy:number,sz:number)=>add(parts,new THREE.BoxGeometry(sx,sy,sz),x,y,z);
 if(swing){
  const stopDepth=Math.min(.018,depth*.18),stopWidth=.011,offset=Math.min(.029,depth*.31);
  // Stops stand slightly proud of the nominal frame, behind the closed leaf.
  strip(frame,.035+stopWidth/2,(h-.035)/2,offset,stopWidth,h-.035,stopDepth);
  strip(frame,w-.035-stopWidth/2,(h-.035)/2,offset,stopWidth,h-.035,stopDepth);
  strip(frame,w/2,h-.035-stopWidth/2,offset,w-.07,stopWidth,stopDepth);
  for(const y of [.18,h*.5,h-.18]){
   // Knuckles and flat fixed hinge leaves remain on the jamb during door swing.
   add(metal,new THREE.CylinderGeometry(.007,.007,.075,12),.031,y,-.024);
   strip(metal,.018,y,-.018,.024,.075,.003);
  }
  // Strike plate recessed near the latch, not an additional opening.
  strip(metal,w-.036,Math.min(1.02,h*.6),.012,.004,.065,.025);
 }
 if(ext){
  // A low nominal weather threshold with two grooves. Does not change the
  // recorded clear opening, navigation, or commercial quantities.
  const span=w-.07,run=Math.min(depth,.12);
  strip(metal,w/2,.006,0,span,.012,run);
  for(const z of [-run*.28,run*.28])strip(metal,w/2,.014,z,span,.004,.008);
 }
 function batch(parts:THREE.BufferGeometry[],color:number,metalness:number,roughness:number,name:string){
  if(!parts.length)return null;
  const geometry=mergeGeometries(parts,false);parts.forEach(p=>p.dispose());if(!geometry)return null;
  const mesh=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color,metalness,roughness}));
  mesh.name=name;mesh.userData.nominalOpeningFrame=true;mesh.castShadow=true;mesh.receiveShadow=true;return mesh;
 }
 const hardware={chrome:0xc4ced4,"matte-black":0x292c2e,"brushed-brass":0xb99b63,"brushed-nickel":0xaaa9a4}[opening.doorHardware??"chrome"];
 return [batch(frame,0xe8e6df,0,.74,"Door jamb stops"),batch(metal,hardware,opening.doorHardware==="matte-black"?.12:.65,.38,"Door hinges, strike and threshold")].filter(p=>p!==null);
}
