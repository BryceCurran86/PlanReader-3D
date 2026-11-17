/** Source-safe, local wall position proposals for desktop and WebXR.
 * Never writes the original coordinates, corrected ledger, PDF or prices.
 * Movement is relative to the EXISTING canonical source endpoints only.
 */
import type { EditorObject, SceneManifest } from "./types";
import { scopeKey } from "./reviewDraft.ts";

export type MoveMode = "inspect" | "move";
export interface WallMove {
  objectId: string;
  objectRevision: string;
  dx: number;
  dz: number;
}
export interface WallMoveHistory {
  scopeKey: string;
  moves: WallMove[];
  past: WallMove[][];
  future: WallMove[][];
}
export type MoveResult = {
  state: WallMoveHistory;
  accepted: boolean;
  reason: string | null;
};
const GRID=0.05, MAX_OFFSET=10, MAX_MOVES=500, MAX_HISTORY=30;
const EPS=1e-6;
type Pt = [number,number];
function point(p: unknown): p is Pt {
  return Array.isArray(p) && p.length===2 && p.every(
    v=>typeof v==="number"&&Number.isFinite(v)&&Math.abs(v)<=10000
  );
}
function endpoints(row: EditorObject): [Pt,Pt] | null {
  if(row.objectType!=="wall" || !row.objectRevision ||
     !row.geometry || !["wallFace","wallLine"].includes(row.geometry.kind) ||
     !point(row.geometry.start) || !point(row.geometry.end))
    return null;
  const a=row.geometry.start,b=row.geometry.end;
  if(Math.hypot(a[0]-b[0],a[1]-b[1])<0.05)return null;
  return [a,b];
}
function snap(v: number):number {
  const rounded=Math.round(v/GRID)*GRID;
  return Math.abs(rounded)<EPS ? 0 : Number(rounded.toFixed(3));
}
function orient(a:Pt,b:Pt,c:Pt):number {
  return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
}
function collideInterior(a:Pt,b:Pt,c:Pt,d:Pt):boolean {
  const ab1=orient(a,b,c),ab2=orient(a,b,d);
  const cd1=orient(c,d,a),cd2=orient(c,d,b);
  if(ab1*ab2<-EPS && cd1*cd2<-EPS)return true;
  if(Math.abs(ab1)>EPS||Math.abs(ab2)>EPS)return false;
  const x=Math.abs(a[0]-b[0])>Math.abs(a[1]-b[1])?0:1;
  const overlap=Math.min(Math.max(a[x],b[x]),Math.max(c[x],d[x]))-
    Math.max(Math.min(a[x],b[x]),Math.min(c[x],d[x]));
  return overlap>GRID/5;
}
export function freshWallMoves(scene:SceneManifest):WallMoveHistory {
  return {scopeKey:scopeKey(scene),moves:[],past:[],future:[]};
}
export function safeWallMoves(state:WallMoveHistory,scene:SceneManifest):WallMove[] {
  if(state.scopeKey!==scopeKey(scene))return [];
  return state.moves.filter(m=>{
    const row=scene.objects.find(o=>o.objectId===m.objectId);
    return !!row&&row.objectRevision===m.objectRevision&&
      !!endpoints(row)&&Number.isFinite(m.dx)&&Number.isFinite(m.dz)&&
      Math.abs(m.dx)<=MAX_OFFSET&&Math.abs(m.dz)<=MAX_OFFSET;
  });
}
export function planCollision(
  scene:SceneManifest,id:string,dx:number,dz:number,existing:readonly WallMove[],
):string|null {
  const target=scene.objects.find(x=>x.objectId===id);
  const points=target&&endpoints(target);
  if(!points)return "Selected wall has no authentic endpoints";
  const [a,b]=points;
  const movedA:Pt=[a[0]+dx,a[1]+dz],movedB:Pt=[b[0]+dx,b[1]+dz];
  if(Math.abs(movedA[0])>10000||Math.abs(movedB[0])>10000||
     Math.abs(movedA[1])>10000||Math.abs(movedB[1])>10000)
    return "Proposed wall is outside supported model bounds";
  for(const row of scene.objects) {
    if(row.objectId===id||row.levelId!==target.levelId)continue;
    const seg=endpoints(row);
    if(!seg)continue;
    const move=existing.find(m=>m.objectId===row.objectId);
    const otherA:Pt=[seg[0][0]+(move?.dx??0),seg[0][1]+(move?.dz??0)];
    const otherB:Pt=[seg[1][0]+(move?.dx??0),seg[1][1]+(move?.dz??0)];
    if(collideInterior(movedA,movedB,otherA,otherB))
      return `Proposed wall intersects ${row.objectId}; review junctions first`;
  }
  return null;
}
export function applyWallMove(
  state:WallMoveHistory,scene:SceneManifest,id:string,
  rawDx:number,rawDz:number,
):MoveResult {
  if(state.scopeKey!==scopeKey(scene))
    return {state:freshWallMoves(scene),accepted:false,reason:"Scene revision changed"};
  const row=scene.objects.find(r=>r.objectId===id);
  if(!row||!endpoints(row))return {state,accepted:false,reason:"Unsupported wall geometry"};
  if(!Number.isFinite(rawDx)||!Number.isFinite(rawDz)||
     Math.abs(rawDx)>MAX_OFFSET||Math.abs(rawDz)>MAX_OFFSET)
    return {state,accepted:false,reason:"Movement must be within 10 metres"};
  const dx=snap(rawDx),dz=snap(rawDz);
  const other=state.moves.filter(x=>x.objectId!==id);
  const reason=planCollision(scene,id,dx,dz,other);
  if(reason)return {state,accepted:false,reason};
  const moves=(dx===0&&dz===0?other:[...other,{
    objectId:id,objectRevision:row.objectRevision,dx,dz,
  }]).sort((a,b)=>a.objectId.localeCompare(b.objectId));
  if(moves.length>MAX_MOVES)
    return {state,accepted:false,reason:"Wall movement limit exceeded"};
  if(JSON.stringify(moves)===JSON.stringify(state.moves))
    return {state,accepted:true,reason:null};
  return {state:{scopeKey:state.scopeKey,moves,
    past:[...state.past.slice(-(MAX_HISTORY-1)),state.moves],
    future:[]},accepted:true,reason:null};
}
export function undoWallMove(state:WallMoveHistory):WallMoveHistory{
  if(!state.past.length)return state;
  return {...state,moves:state.past[state.past.length-1],
    past:state.past.slice(0,-1),
    future:[...state.future,state.moves].slice(-MAX_HISTORY)};
}
export function redoWallMove(state:WallMoveHistory):WallMoveHistory{
  if(!state.future.length)return state;
  return {...state,moves:state.future[state.future.length-1],
    future:state.future.slice(0,-1),
    past:[...state.past,state.moves].slice(-MAX_HISTORY)};
}
export function resetWallMoves(state:WallMoveHistory):WallMoveHistory{
  if(!state.moves.length)return state;
  return {...state,moves:[],past:[...state.past.slice(-(MAX_HISTORY-1)),state.moves],future:[]};
}
export function moveToWorld(row:EditorObject,m:WallMove|null):[Pt,Pt]|null{
  const coords=endpoints(row);
  if(!coords)return null;
  return [
    [coords[0][0]+(m?.dx??0),coords[0][1]+(m?.dz??0)],
    [coords[1][0]+(m?.dx??0),coords[1][1]+(m?.dz??0)],
  ];
}
