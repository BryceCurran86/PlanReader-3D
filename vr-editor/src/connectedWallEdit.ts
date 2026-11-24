import type {PlacedWall,PlanPoint} from "./buildPlacement.ts";
import {localOutline} from "./localOutline.ts";

const EPS=1e-7;
const distance=(a:PlanPoint,b:PlanPoint)=>Math.hypot(a[0]-b[0],a[1]-b[1]);
const same=(a:PlanPoint,b:PlanPoint)=>distance(a,b)<=EPS;
const cross=(a:PlanPoint,b:PlanPoint,c:PlanPoint)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
const on=(a:PlanPoint,b:PlanPoint,p:PlanPoint)=>Math.abs(cross(a,b,p))<=EPS*Math.max(1,distance(a,b))&&
 p[0]>=Math.min(a[0],b[0])-EPS&&p[0]<=Math.max(a[0],b[0])+EPS&&p[1]>=Math.min(a[1],b[1])-EPS&&p[1]<=Math.max(a[1],b[1])+EPS;
const interior=(a:PlanPoint,b:PlanPoint,p:PlanPoint)=>on(a,b,p)&&!same(a,p)&&!same(b,p);
function conflict(a:PlacedWall,b:PlacedWall){
 // Exact shared endpoints are permitted; overlapping runs, mid-wall junctions and crossings
 // need a separate split/join operation before a connected edit.
 if(interior(a.start,a.end,b.start)||interior(a.start,a.end,b.end)||
    interior(b.start,b.end,a.start)||interior(b.start,b.end,a.end))return true;
 if(same(a.start,b.start)&&same(a.end,b.end)||same(a.start,b.end)&&same(a.end,b.start))return true;
 const s=cross(a.start,a.end,b.start),t=cross(a.start,a.end,b.end),
       u=cross(b.start,b.end,a.start),v=cross(b.start,b.end,a.end);
 return (s>EPS&&t< -EPS||s< -EPS&&t>EPS)&&(u>EPS&&v< -EPS||u< -EPS&&v>EPS);
}
function reshape(w:PlacedWall,start:PlanPoint,end:PlanPoint):PlacedWall|null{
 const old=distance(w.start,w.end),length=distance(start,end);
 if(!Number.isFinite(length)||length<.05-EPS||length>200||old<.05-EPS)return null;
 if([...start,...end].some(v=>!Number.isFinite(v)||Math.abs(v)>10000))return null;
 // Keep apertures measured from the stationary end where possible. Do not scale
 // door/window dimensions or clamp the opening into an invented location.
 const fromEnd=!same(w.start,start)&&same(w.end,end);
 const openings=w.openings.map(o=>({...o,offsetM:fromEnd?length-(old-o.offsetM):o.offsetM}));
 if(openings.some(o=>o.offsetM< -EPS||o.offsetM+o.widthM>length+EPS||
   ![o.offsetM,o.widthM,o.heightM,o.sillHeightM].every(Number.isFinite)))return null;
 for(const o of openings)if(o.offsetM<0)o.offsetM=0;
 const sorted=[...openings].sort((a,b)=>a.offsetM-b.offsetM);
 if(sorted.some((o,i)=>i>0&&o.offsetM<sorted[i-1].offsetM+sorted[i-1].widthM-EPS))return null;
 return {...w,start,end,openings};
}
/** Propagate exact endpoint changes to adjoining walls in the same local level/scope.
 * This is atomic. Unsplit T/intersecting wall topology is refused, not guessed. */
export function connectedWallEdit(walls:readonly PlacedWall[],previous:PlacedWall,edited:PlacedWall):PlacedWall[]|null{
 if(!walls.includes(previous)||edited.proposalId!==previous.proposalId||edited.scopeKey!==previous.scopeKey||edited.levelId!==previous.levelId)return null;
 const peers=walls.filter(w=>w.scopeKey===previous.scopeKey&&w.levelId===previous.levelId);
 const oldRing=localOutline(peers);
 const map=(p:PlanPoint):PlanPoint=>same(p,previous.start)?edited.start:same(p,previous.end)?edited.end:p;
 const changed=new Set<PlacedWall>();
 const next:PlacedWall[]=[];
 for(const w of walls){
  if(w===previous){changed.add(w);next.push(edited);continue;}
  if(!peers.includes(w)){next.push(w);continue;}
  const start=map(w.start),end=map(w.end);
  if(same(start,w.start)&&same(end,w.end)){next.push(w);continue;}
  const replacement=reshape(w,start,end);
  if(!replacement)return null;
  changed.add(w);next.push(replacement);
 }
 for(let i=0;i<walls.length;i++)for(let j=i+1;j<walls.length;j++){
  if(!peers.includes(walls[i])||!peers.includes(walls[j])||
     !changed.has(walls[i])&&!changed.has(walls[j]))continue;
  // Do not silently detach an existing unsplit T connection either.
  if(conflict(walls[i],walls[j])||conflict(next[i],next[j]))return null;
 }
 if(oldRing&&!localOutline(next.filter(w=>w.scopeKey===previous.scopeKey&&w.levelId===previous.levelId)))return null;
 return next;
}
