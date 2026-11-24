/** Read-only plan map in Quest. Uses existing source and draft coordinates only. */
import * as THREE from "three";
import type {SceneManifest} from "./types.ts";
import type {BuildState,PlanPoint} from "./buildPlacement.ts";

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
 let last="",lastHead=new THREE.Vector3(),placed=false;
 const head=new THREE.Vector3(),forward=new THREE.Vector3(),right=new THREE.Vector3();
 function update(build:Pick<BuildState,"walls">,level:string,
   visible:ReadonlySet<string>,camera:THREE.Camera,enabled:boolean){
  mesh.visible=enabled;
  if(!enabled){placed=false;return;}
  const segments=overviewSegments(manifest,build,level,visible);
  const key=JSON.stringify([level,segments]);
  if(key!==last&&ctx){
   last=key;
   ctx.clearRect(0,0,800,800);
   ctx.fillStyle="#102831";ctx.fillRect(0,0,800,800);
   ctx.font="bold 34px sans-serif";ctx.fillStyle="#e9fcfc";
   ctx.fillText("PLAN OVERVIEW · DRAFT",25,50,750);
   let minX=Infinity,maxX=-Infinity,minZ=Infinity,maxZ=-Infinity;
   for(const item of segments)for(const point of [item.start,item.end]){
     minX=Math.min(minX,point[0]);maxX=Math.max(maxX,point[0]);
     minZ=Math.min(minZ,point[1]);maxZ=Math.max(maxZ,point[1]);
   }
   if(!Number.isFinite(minX)){minX=0;maxX=1;minZ=0;maxZ=1;}
   const scale=Math.min(690/Math.max(maxX-minX,0.001),
     660/Math.max(maxZ-minZ,0.001));
   const dx=(800-(maxX-minX)*scale)/2,dz=95+(650-(maxZ-minZ)*scale)/2;
   ctx.lineWidth=5;
   for(const s of segments){
    ctx.beginPath();ctx.moveTo(dx+(s.start[0]-minX)*scale,dz+(s.start[1]-minZ)*scale);
    ctx.lineTo(dx+(s.end[0]-minX)*scale,dz+(s.end[1]-minZ)*scale);
    ctx.strokeStyle=s.source?(s.verified?"#c9e4dd":"#d5a56d"):"#70e9eb";
    ctx.stroke();
   }
   ctx.fillStyle="#d5a56d";ctx.fillRect(30,735,16,16);
   ctx.fillStyle="#e9fcfc";ctx.font="24px sans-serif";
   ctx.fillText("Source review",52,750);
   ctx.fillStyle="#70e9eb";ctx.fillRect(290,735,16,16);
   ctx.fillStyle="#e9fcfc";ctx.fillText("Local draft",312,750);
   ctx.fillText("Not a measured plan",25,786);
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
