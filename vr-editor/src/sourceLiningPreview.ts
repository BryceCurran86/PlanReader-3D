import * as THREE from "three";
import type {EditorObject} from "./types.ts";
import type {SourceSurface} from "./sourceSurfaces.ts";
import {makeLiningVisual,makeShellCeilingLining} from "./constructionLiningVisual.ts";
/** Cosmetic stage preview on a witnessed surface, never evidence of board
 * specification, construction assembly, opening subtraction or measured area.
 * Do not extrude source faces into guessed wall frames. */
export function sourceWallLiningPreview(row:EditorObject){
 const g=row.geometry;
 if(row.objectType!=="wall"||row.renderState!=="verified"||row.unresolvedIssues.length||g?.kind!=="wallFace")return null;
 const length=Math.hypot(g.end[0]-g.start[0],g.end[1]-g.start[1]);
 // Bound per-object work; large surfaces remain in the existing source view.
 if(!Number.isFinite(length)||length<.05||length>20||!Number.isFinite(g.heightM)||g.heightM<.05||g.heightM>6)return null;
 const ux=(g.end[0]-g.start[0])/length,uz=(g.end[1]-g.start[1])/length;
 const group=new THREE.Group();
 // Source openingReview is explicitly not cutout authority. Leave the entire
 // witnessed face intact and retain the separate original review markers.
 for(const side of [-1,1]){
  const mesh=makeLiningVisual(length,g.heightM,[],(x,y,offset)=>new THREE.Vector3(g.start[0]+ux*x-uz*side*offset,y,g.start[1]+uz*x+ux*side*offset));
  if(mesh){mesh.visible=true;group.add(mesh);}
 }
 if(!group.children.length)return null;
 group.userData.sourceNominalLining=true;group.visible=false;return group;
}
export function sourceCeilingLiningPreview(surface:SourceSurface){
 if(surface.kind!=="ceiling"||surface.renderState!=="verified"||surface.commercialAuthority!==false)return null;
 const mesh=makeShellCeilingLining(surface.vertices);if(!mesh)return null;
 const group=new THREE.Group();mesh.visible=true;group.add(mesh);group.userData.sourceNominalLining=true;group.visible=false;return group;
}
