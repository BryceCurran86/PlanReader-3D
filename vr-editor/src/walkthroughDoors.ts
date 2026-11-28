import {localDoorMotion} from "./localDoorMotion.ts";
import type {WallVisual} from "./buildPlacement.ts";
import {openingFits,planLength} from "./buildPlacement.ts";
import {wallAssembly} from "./wallProfiles.ts";
import type {NavigationWall,Xz} from "./vrStationaryNavigation.ts";
export const doorKey=(wallId:string,openingId:string)=>JSON.stringify([wallId,openingId]);
export function doorSwingSegment(wall:WallVisual,offset:number,width:number,angle:number):NavigationWall{
 const l=planLength(wall.start,wall.end),ux=(wall.end[0]-wall.start[0])/l,uz=(wall.end[1]-wall.start[1])/l;
 const start:Xz=[wall.start[0]+ux*offset,wall.start[1]+uz*offset];
 const c=Math.cos(angle),s=Math.sin(angle);
 return {start,end:[start[0]+width*(ux*c+uz*s),start[1]+width*(-ux*s+uz*c)],halfThickness:.02};
}
export function localNavigationWalls(wall:WallVisual,openDoors:ReadonlySet<string>,showDoors=true):NavigationWall[]{
 const length=planLength(wall.start,wall.end);
 if(!Number.isFinite(length)||length<.05)return [];
 const halfThickness=wallAssembly(wall.assembly).thicknessMm/2000;
 const at=(d:number):Xz=>[wall.start[0]+(wall.end[0]-wall.start[0])*d/length,wall.start[1]+(wall.end[1]-wall.start[1])*d/length];
 const walls:NavigationWall[]=[];
 let end=0;
 for(const o of [...(wall.openings??[])].sort((a,b)=>a.offsetM-b.offsetM)){
  if(!openingFits(wall,o)||o.offsetM<end||o.sillHeightM>.01||o.heightM<1.9)continue;
  const door=o.openingKind==="door",motion=localDoorMotion(wall,o,halfThickness),open=door&&motion!==null&&openDoors.has(doorKey(wall.proposalId,o.openingId));
  if(o.openingKind!=="passage"&&!(door&&(open||!showDoors)))continue;
  if(o.offsetM>end)walls.push({start:at(end),end:at(o.offsetM),halfThickness});
  end=o.offsetM+o.widthM;
  if(open&&showDoors&&(motion?.kind==="stacker"||motion?.kind==="wide-stacker"))walls.push({start:at(end-o.widthM/(motion.kind==="stacker"?3:4)),end:at(end),halfThickness});
  if(open&&showDoors&&motion?.kind==="swing")walls.push(doorSwingSegment(wall,o.offsetM,o.widthM,motion.angle));
 }
 if(end<length)walls.push({start:at(end),end:wall.end,halfThickness});
 return walls;
}
