import * as THREE from "three";
import {planLength,openingFits} from "./buildPlacement.ts";
import type {WallVisual} from "./buildPlacement.ts";
import {wallAssembly,profileDetails} from "./wallProfiles.ts";
import {nominalFrameLayout} from "./constructionDetailLayout.ts";

type Backing={wallId:string;offset:number;side:number;bottom:number;top:number;depth:number;width:number;start:[number,number];end:[number,number];kind:"corner"|"tee"};
const T=.045,EPS=1e-6;
const timber=(w:WallVisual)=>profileDetails(w.assembly).core==="timber";
const length=(w:WallVisual)=>planLength(w.start,w.end);
/** Nominal junction backing only where actual local draft centreline adjacency exists.
 * No proximity snapping here, no source assumptions, no structural certification. */
export function junctionBacking(walls:readonly WallVisual[]):Backing[]{
 const result:Backing[]=[],seen=new Set<string>();
 const groups=new Map<string,WallVisual[]>();
 for(const w of walls){
  const l=length(w);
  if(!timber(w)||!Number.isFinite(l)||l<.15||l>200||!Number.isFinite(w.heightM)||w.heightM<.2||w.heightM>20)continue;
  const k=JSON.stringify([w.scopeKey,w.levelId]);const g=groups.get(k)??[];g.push(w);groups.set(k,g);
 }
 function add(host:WallVisual,x:number,side:number,h:number,kind:Backing["kind"]){
  const l=length(host),depth=Math.min(profileDetails(host.assembly).frameMm,wallAssembly(host.assembly).thicknessMm)/1000;
  const width=T;
  if(x-width/2< -EPS||x+width/2>l+EPS||depth<2*T-EPS||h<=3*T)return;
  // Do not put backing through an opening, even above/below a partial-height opening.
  if((host.openings??[]).some(o=>openingFits(host,o)&&o.offsetM<x+width/2+EPS&&o.offsetM+o.widthM>x-width/2-EPS))return;
  // Existing full-depth studs/plates already supply backing in this location.
  const holes=(host.openings??[]).filter(o=>openingFits(host,o)).map(o=>({x0:o.offsetM,x1:o.offsetM+o.widthM,y0:o.sillHeightM,y1:o.sillHeightM+o.heightM}));
  let existing:ReturnType<typeof nominalFrameLayout>;
  try{existing=nominalFrameLayout(l,host.heightM,holes);}catch{return;}
  if(existing.some(m=>["stud","king","trimmer","end-backing","cripple"].includes(m.role)&&m.x0<x+width/2-EPS&&m.x1>x-width/2+EPS))return;
  const k=[host.proposalId,Math.round(x*1e6),side].join(":");
  if(seen.has(k))return;seen.add(k);
  result.push({wallId:host.proposalId,offset:x,side,bottom:T,top:Math.min(h,host.heightM)-2*T,depth,width,start:host.start,end:host.end,kind});
 }
 for(const g of groups.values()){
  if(g.length>512)continue;
  for(const branch of g)for(const host of g){
   if(branch===host||branch.proposalId===host.proposalId)continue;
   const l=length(host),ux=(host.end[0]-host.start[0])/l,uz=(host.end[1]-host.start[1])/l;
   for(const [p,q] of [[branch.start,branch.end],[branch.end,branch.start]]){
    const x=(p[0]-host.start[0])*ux+(p[1]-host.start[1])*uz;
    const off=-(p[0]-host.start[0])*uz+(p[1]-host.start[1])*ux;
    if(Math.abs(off)>EPS||x< -EPS||x>l+EPS)continue;
    const transverse=-(q[0]-p[0])*uz+(q[1]-p[1])*ux;
    if(Math.abs(transverse)/length(branch)<.2)continue;
    const side=Math.sign(transverse),h=Math.min(branch.heightM,host.heightM);
    if(x>2*T&&x<l-2*T){
     // Two nominal backing strips flanking the actual intersecting branch.
     const half=Math.min(profileDetails(branch.assembly).frameMm,wallAssembly(branch.assembly).thicknessMm)/2000;
     add(host,x-half-T/2,side,h,"tee");add(host,x+half+T/2,side,h,"tee");
    }else{
     // End double studs are already present; add an adjacent nonoverlapping strip.
     add(host,x<=2*T?2.5*T:l-2.5*T,side,h,"corner");
    }
   }
  }
 }
 return result;
}
export function junctionBackingMesh(walls:readonly WallVisual[]){
 const entries=junctionBacking(walls);if(!entries.length)return null;
 const mesh=new THREE.InstancedMesh(new THREE.BoxGeometry(1,1,1),new THREE.MeshStandardMaterial({color:0xc99c65,roughness:.88}),entries.length);
 const obj=new THREE.Object3D();
 entries.forEach((e,i)=>{
  const l=planLength(e.start,e.end),ux=(e.end[0]-e.start[0])/l,uz=(e.end[1]-e.start[1])/l;
  // Place the backing on the requested side, inside nominal host depth.
  const shift=e.side*(e.depth/2-T/2);
  obj.position.set(e.start[0]+ux*e.offset-uz*shift,(e.top+e.bottom)/2,e.start[1]+uz*e.offset+ux*shift);
  obj.rotation.set(0,-Math.atan2(uz,ux),0);obj.scale.set(e.width,e.top-e.bottom,T);obj.updateMatrix();mesh.setMatrixAt(i,obj.matrix);
 });
 mesh.instanceMatrix.needsUpdate=true;mesh.computeBoundingBox();mesh.computeBoundingSphere();
 mesh.userData.nominalJunctionBacking=true;mesh.userData.junctionEntries=entries;mesh.visible=false;
 return mesh;
}
