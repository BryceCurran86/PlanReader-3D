/** Read-only plan map in Quest. Uses existing source and draft coordinates only. */
import * as THREE from "three";
import type {SceneManifest} from "./types.ts";
import {architecturalPlan,paintArchitecturalPlan} from "./architecturalPlan.ts";
import type {FootprintProjection} from "./footprintResize.ts";
import type {BuildState,PlanPoint,WallVisual} from "./buildPlacement.ts";

export type OverviewSegment={start:PlanPoint;end:PlanPoint;source:boolean;verified:boolean};
export function overviewSegments(
 scene:SceneManifest,build:Pick<BuildState,"walls">,level:string,
 visible?:ReadonlySet<string>,
):OverviewSegment[]{
 const segments:OverviewSegment[]=[];
 for(const row of scene.objects){
  const shape=row.geometry;
  if(row.objectType!=="wall"||!shape||
    (level!=="all"&&row.levelId!==level)||
    (visible&&!visible.has(row.objectId)))continue;
  if(![...shape.start,...shape.end].every(Number.isFinite))continue;
  segments.push({start:[...shape.start],end:[...shape.end],source:true,
    verified:row.renderState==="verified"&&row.unresolvedIssues.length===0});
 }
 for(const wall of build.walls){
  if(level!=="all"&&wall.levelId!==level)continue;
  segments.push({start:[...wall.start],end:[...wall.end],source:false,verified:false});
 }
 return segments.slice(0,25000);
}
const EMPTY_MOVES:readonly {objectId:string;dx:number;dz:number}[]=[];
const EMPTY_WALLS:readonly WallVisual[]=[];
export function createVrPlanOverview(scene:THREE.Scene,manifest:SceneManifest){
 const canvas=document.createElement("canvas");
 canvas.width=800;canvas.height=800;
 const ctx=canvas.getContext("2d");
 const texture=new THREE.CanvasTexture(canvas);
 texture.colorSpace=THREE.SRGBColorSpace;
 const material=new THREE.MeshBasicMaterial({
   map:texture,side:THREE.DoubleSide,toneMapped:false,
   depthTest:false,depthWrite:false,transparent:true});
 const mesh=new THREE.Mesh(new THREE.PlaneGeometry(0.78,0.78),material);
 mesh.visible=false;mesh.renderOrder=30;scene.add(mesh);
 let last:readonly unknown[]=[],lastHead=new THREE.Vector3(),placed=false;
 const head=new THREE.Vector3(),forward=new THREE.Vector3(),right=new THREE.Vector3();
 function update(build:Pick<BuildState,"walls">,level:string,
   visible:ReadonlySet<string>,camera:THREE.Camera,enabled:boolean,projection:FootprintProjection|null=null,moves:readonly {objectId:string;dx:number;dz:number}[]=EMPTY_MOVES,extra:readonly WallVisual[]=EMPTY_WALLS){
  mesh.visible=enabled;
  if(!enabled){placed=false;return;}
  const key=[build.walls,level,visible,projection,moves,extra] as const;
  if(!key.every((v,i)=>v===last[i])&&ctx){
   last=key;
   paintArchitecturalPlan(ctx,architecturalPlan(manifest,build,level,visible,projection,moves,extra),800,800);
   texture.needsUpdate=true;
  }
  camera.getWorldPosition(head);
  if(!placed||head.distanceTo(lastHead)>2){
   lastHead.copy(head);
   camera.getWorldDirection(forward);forward.y=0;
   if(forward.lengthSq()<0.01)forward.set(0,0,-1);
   forward.normalize();
   right.set(-forward.z,0,forward.x);
   mesh.position.copy(head).addScaledVector(forward,1.05)
      .addScaledVector(right,-0.52);
   mesh.position.y-=0.15;
   mesh.lookAt(head);
   placed=true;
  }
 }
 return {update,dispose(){scene.remove(mesh);mesh.geometry.dispose();material.dispose();texture.dispose();}};
}
