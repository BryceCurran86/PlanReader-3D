/** Local WebXR viewer navigation. No edits to scene geometry or measurement evidence. */
export type Xz=[number,number];
export type StickSource={handedness?:string;targetRayMode?:string;gamepad?:{mapping?:string;axes?:readonly number[]}|null};
export type NavigationWall={start:Xz;end:Xz;halfThickness?:number};
/** A plan guide has no physical height and must never obstruct locomotion. */
export function navigationWallFace(geometry:{kind:string;heightM?:number}|null|undefined,visible:boolean):boolean{
 return visible&&geometry?.kind==="wallFace"&&typeof geometry.heightM==="number"&&Number.isFinite(geometry.heightM)&&geometry.heightM>0;
}
export function standardThumbstick(source:StickSource|null|undefined):Xz{
 const a=source?.gamepad?.axes;
 // XR standard thumbstick axes are 2/3, never guess unknown mappings.
 if(source?.targetRayMode!=="tracked-pointer"||source.gamepad?.mapping!=="xr-standard"||!a||a.length<4)return [0,0];
 const x=a[2],y=a[3];
 if(![x,y].every(n=>Number.isFinite(n)&&Math.abs(n)<=1))return [0,0];
 const magnitude=Math.hypot(x,y);
 if(magnitude<=.2)return [0,0];
 const scale=Math.min(1,(magnitude-.2)/.8)/magnitude;
 return [x*scale,y*scale];
}
export function walkDelta(stick:Xz,forward:Xz,speed:number,dt:number):Xz{
 const n=Math.hypot(...forward);
 if(n<.01||![...stick,...forward,speed,dt].every(Number.isFinite)||speed<0||dt<=0)return [0,0];
 const [fx,fz]=forward.map(v=>v/n);
 const d=Math.min(dt,.05)*Math.min(speed,3);
 return [(stick[0]*-fz-stick[1]*fx)*d,(stick[0]*fx-stick[1]*fz)*d];
}
function segmentDistance(p:Xz,w:NavigationWall){
 const dx=w.end[0]-w.start[0],dz=w.end[1]-w.start[1],l=dx*dx+dz*dz;
 const t=l>0?Math.min(1,Math.max(0,((p[0]-w.start[0])*dx+(p[1]-w.start[1])*dz)/l)):0;
 return Math.hypot(p[0]-w.start[0]-t*dx,p[1]-w.start[1]-t*dz);
}
export function collisionLimitedStep(from:Xz,delta:Xz,walls:readonly NavigationWall[],radius=.25):Xz{
 if(![...from,...delta,radius].every(Number.isFinite)||radius<=0)return [0,0];
 const steps=Math.max(1,Math.ceil(Math.hypot(...delta)/.05));
 // Broad-phase: skip distant walls before checking each movement substep.
 const minX=Math.min(from[0],from[0]+delta[0]),maxX=Math.max(from[0],from[0]+delta[0]);
 const minZ=Math.min(from[1],from[1]+delta[1]),maxZ=Math.max(from[1],from[1]+delta[1]);
 const nearby=walls.filter(w=>{const pad=radius+Math.max(0,w.halfThickness??0);return Math.max(w.start[0],w.end[0])+pad>=minX&&Math.min(w.start[0],w.end[0])-pad<=maxX&&Math.max(w.start[1],w.end[1])+pad>=minZ&&Math.min(w.start[1],w.end[1])-pad<=maxZ;});
 if(steps>100)return [0,0];
 let p:Xz=[...from];
 const clear=(q:Xz)=>nearby.every(w=>{
  const old=segmentDistance(p,w),next=segmentDistance(q,w);
  return next>=radius+Math.max(0,w.halfThickness??0)||next>old+1e-7;
 });
 for(let i=0;i<steps;i++){
  const x=delta[0]/steps,z=delta[1]/steps;
  const full:Xz=[p[0]+x,p[1]+z];
  if(clear(full)){p=full;continue;}
  const slideX:Xz=[p[0]+x,p[1]];
  if(clear(slideX))p=slideX;
  const slideZ:Xz=[p[0],p[1]+z];
  if(clear(slideZ))p=slideZ;
 }
 return [p[0]-from[0],p[1]-from[1]];
}
export function snapTurn(axis:number,armed:boolean){
 if(!Number.isFinite(axis)||Math.abs(axis)<.25)return {angle:0,armed:true};
 if(!armed||Math.abs(axis)<.7)return {angle:0,armed};
 return {angle:Math.sign(axis)*Math.PI/6,armed:false};
}
/** Offset reference-space origin, rotating around current head, not model origin. */
export function navigationOffset(head:{x:number;y:number;z:number},delta:{x:number;y:number;z:number},yaw:number){
 const c=Math.cos(yaw),s=Math.sin(yaw);
 const x=head.x+delta.x,z=head.z+delta.z;
 return {position:{x:head.x-(c*x+s*z),y:-delta.y,z:head.z-(-s*x+c*z)},orientation:{x:0,y:Math.sin(yaw/2),z:0,w:Math.cos(yaw/2)}};
}

/** Compose rigid yaw transforms in a single stable base reference space. */
export type NavOffset=ReturnType<typeof navigationOffset>;
export const identityNavOffset=():NavOffset=>({position:{x:0,y:0,z:0},orientation:{x:0,y:0,z:0,w:1}});
export function composeNavigationOffset(a:NavOffset,b:NavOffset):NavOffset{
 const {y,w}=a.orientation,c=w*w-y*y,s=2*y*w;
 const ay=y*b.orientation.w+w*b.orientation.y,aw=w*b.orientation.w-y*b.orientation.y;
 const n=Math.hypot(ay,aw)||1;
 return {position:{x:a.position.x+c*b.position.x+s*b.position.z,y:a.position.y+b.position.y,z:a.position.z-s*b.position.x+c*b.position.z},orientation:{x:0,y:ay/n,z:0,w:aw/n}};
}
