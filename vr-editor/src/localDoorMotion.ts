import type {WallAdditionOpening,WallAdditionSketch,DoorMechanism} from "./wallAdditionProtocol.ts";
type Wall=WallAdditionSketch & {openings?:readonly WallAdditionOpening[]};
type Vec=[number,number,number];
const EPS=1e-6;
export const DOOR_MECHANISMS=["swing","sliding","garage","cavity","barn","stacker","wide-stacker"] as const;
export function nextDoorMechanism(value:DoorMechanism|undefined):DoorMechanism{
 return DOOR_MECHANISMS[(DOOR_MECHANISMS.indexOf(value??"swing")+1)%DOOR_MECHANISMS.length];
}
export type LocalDoorMotion={kind:DoorMechanism;axis:Vec;pivot:Vec;angle:number;translation:Vec};
/** Draft visual kinematics only. Sliding needs a clear full-width adjacent
 * track on its host. Garage is a nominal one-piece overhead panel, not a
 * structural or mechanical installation specification. */
export function localDoorMotion(wall:Wall,opening:WallAdditionOpening,halfThickness:number):LocalDoorMotion|null{
 if(opening.openingKind!=="door")return null;
 const kind=opening.doorMechanism??"swing";
 if(!DOOR_MECHANISMS.includes(kind)||![opening.offsetM,opening.widthM,opening.heightM,opening.sillHeightM,halfThickness].every(Number.isFinite)||halfThickness<0)return null;
 const dx=wall.end[0]-wall.start[0],dz=wall.end[1]-wall.start[1],length=Math.hypot(dx,dz);
 const a=opening.offsetM,w=opening.widthM,h=opening.heightM,y=opening.sillHeightM;
 if(!Number.isFinite(length)||length<.05||a<0||w<=0||h<=0||y<0||a+w>length+EPS||y+h>wall.heightM+EPS)return null;
 const ux=dx/length,uz=dz/length;
 const pivot:Vec=[wall.start[0]+ux*a,y,wall.start[1]+uz*a];
 if(kind==="swing")return {kind,axis:[0,1,0],pivot,angle:Math.PI/2,translation:[0,0,0]};
 if(kind==="garage"){
  if(y>.01||h<1.9)return null;
  return {kind,axis:[ux,0,uz],pivot:[pivot[0],y+h,pivot[2]],angle:Math.PI/2,translation:[0,0,0]};
 }
 if(kind==="stacker"||kind==="wide-stacker"){if(w<(kind==="stacker"?1.5:2.0))return null;return {kind,axis:[0,1,0],pivot,angle:0,translation:[0,0,0]};}
 const free=(lo:number,hi:number)=>lo>=-EPS&&hi<=length+EPS&&!(wall.openings??[]).some(o=>o.openingId!==opening.openingId&&
  o.offsetM<hi-EPS&&o.offsetM+o.widthM>lo+EPS&&o.sillHeightM<y+h-EPS&&o.sillHeightM+o.heightM>y+EPS);
 const travel=free(a+w,a+2*w)?w:free(a-w,a)?-w:0;
 if(!travel)return null;
 const side=kind==="cavity"?0:halfThickness+(kind==="barn"?.055:.025);
 return {kind,axis:[0,1,0],pivot,angle:0,translation:[ux*travel-uz*side,0,uz*travel+ux*side]};
}
export function stackerPanels(wall:Wall,opening:WallAdditionOpening){
 const motion=localDoorMotion(wall,opening,0);if(!motion||!(motion.kind==="stacker"||motion.kind==="wide-stacker"))return [];
 const count=motion.kind==="stacker"?3:4,w=opening.widthM/count,l=Math.hypot(wall.end[0]-wall.start[0],wall.end[1]-wall.start[1]),ux=(wall.end[0]-wall.start[0])/l,uz=(wall.end[1]-wall.start[1])/l;
 return Array.from({length:count},(_,i)=>{const travel=(count-1-i)*w;const track=(i-(count-1)/2)*.045;return {offsetM:opening.offsetM+i*w,widthM:w,track,translation:[ux*travel,0,uz*travel] as Vec};});
}
export function validLocalDoorMechanisms(wall:Wall):boolean{
 return (wall.openings??[]).every(o=>o.doorMechanism===undefined||
  (o.openingKind==="door"&&localDoorMotion(wall,o,0)!==null));
}
