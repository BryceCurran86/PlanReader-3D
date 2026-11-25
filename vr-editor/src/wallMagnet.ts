import type {Ray} from "three";
import type {PlanPoint} from "./buildPlacement.ts";
export type WallTarget={key:string;kind:"draft"|"source";id:string;start:PlanPoint;end:PlanPoint;heightM:number;halfThickness:number};
export type WallAim={target:WallTarget;distance:number;exact:boolean;point:PlanPoint};
export const MAGNET_ACQUIRE=.22;
export const MAGNET_RELEASE=.36;
// Ray/finite oriented wall box, including the actual thickness and upper edge.
// Expand only for magnetic acquisition/release, not exact selection.
function hit(ray:Ray,t:WallTarget,padding:number):WallAim|null{
 const dx=t.end[0]-t.start[0],dz=t.end[1]-t.start[1],length=Math.hypot(dx,dz);
 if(length<.05||t.heightM<=0||![length,t.heightM,t.halfThickness].every(Number.isFinite))return null;
 const ux=dx/length,uz=dz/length,nx=-uz,nz=ux;
 const x=ray.origin.x-t.start[0],z=ray.origin.z-t.start[1];
 const origin=[x*ux+z*uz,ray.origin.y,x*nx+z*nz];
 const dir=[ray.direction.x*ux+ray.direction.z*uz,ray.direction.y,ray.direction.x*nx+ray.direction.z*nz];
 const half=Math.max(.00001,t.halfThickness);
 const min=[-padding,-padding,-half-padding],max=[length+padding,t.heightM+padding,half+padding];
 let lo=0,hi=Infinity;
 for(let i=0;i<3;i++){
  if(Math.abs(dir[i])<1e-9){if(origin[i]<min[i]||origin[i]>max[i])return null;continue;}
  const a=(min[i]-origin[i])/dir[i],b=(max[i]-origin[i])/dir[i];
  lo=Math.max(lo,Math.min(a,b));hi=Math.min(hi,Math.max(a,b));if(hi<lo)return null;
 }
 if(!Number.isFinite(lo)||lo>30)return null;
 // Project the aimed point onto the actual wall centreline for editing.
 const center=Math.max(0,Math.min(length,origin[0]+dir[0]*lo));
 return {target:t,distance:lo,exact:padding===0,point:[t.start[0]+ux*center,t.start[1]+uz*center]};
}
export function wallAimWithin(ray:Ray,target:WallTarget,padding=MAGNET_RELEASE){
 return hit(ray,target,0)??hit(ray,target,padding);
}
export function chooseWallAim(ray:Ray,targets:readonly WallTarget[],previous:string|null,enabled=true):WallAim|null{
 const exact:WallAim[]=[],near:WallAim[]=[];
 let retained:WallAim|null=null;
 for(const t of targets){
  const direct=hit(ray,t,0);
  if(direct)exact.push(direct);
  if(enabled){
   const candidate=direct??hit(ray,t,t.key===previous?MAGNET_RELEASE:MAGNET_ACQUIRE);
   if(candidate&&t.key===previous)retained=candidate;
   if(candidate&&!direct)near.push(candidate);
  }
 }
 const sort=(a:WallAim,b:WallAim)=>a.distance-b.distance||a.target.key.localeCompare(b.target.key);
 exact.sort(sort);near.sort(sort);
 const nearest=exact[0];
 // Retain aim through small jitter, but never lock through a clearly nearer wall.
 if(retained&&(!nearest||retained.distance<=nearest.distance+.12))return retained;
 return nearest??near[0]??null;
}
