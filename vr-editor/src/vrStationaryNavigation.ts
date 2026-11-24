/** Local WebXR viewer navigation. No edits to scene geometry or measurement evidence. */
export type Xz=[number,number];
export type StickSource={handedness?:string;targetRayMode?:string;gamepad?:{mapping?:string;axes?:readonly number[]}|null};
export type NavigationWall={start:Xz;end:Xz};
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
 if(steps>100)return [0,0];
 let p:Xz=[...from];
 const clear=(q:Xz)=>walls.every(w=>{
  const old=segmentDistance(p,w),next=segmentDistance(q,w);
  return next>=radius||next>old+1e-7;
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
