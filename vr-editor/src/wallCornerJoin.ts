import type {PlanPoint,WallVisual} from "./buildPlacement.ts";
import {wallAssembly,profileDetails} from "./wallProfiles.ts";
type End="start"|"end";
type Pair={left:PlanPoint;right:PlanPoint};
export type WallCornerJoins={start?:Pair;end?:Pair};
const EPS=1e-6;
const cross=(a:PlanPoint,b:PlanPoint)=>a[0]*b[1]-a[1]*b[0];
const sub=(a:PlanPoint,b:PlanPoint):PlanPoint=>[a[0]-b[0],a[1]-b[1]];
const add=(a:PlanPoint,b:PlanPoint,s:number):PlanPoint=>[a[0]+b[0]*s,a[1]+b[1]*s];
const dot=(a:PlanPoint,b:PlanPoint)=>a[0]*b[0]+a[1]*b[1];
const length=(a:PlanPoint)=>Math.hypot(...a);
type Incident={w:WallVisual;end:End;p:PlanPoint;u:PlanPoint;n:PlanPoint;len:number;half:number};
function incident(w:WallVisual,end:End):Incident|null{
 const p=w[end],d=sub(w[end==="start"?"end":"start"],p),len=length(d);
 if(!Number.isFinite(len)||len<.05||!Number.isFinite(w.heightM)||w.heightM<=0)return null;
 const u:PlanPoint=[d[0]/len,d[1]/len];
 return {w,end,p,u,n:[-u[1],u[0]],len,half:wallAssembly(w.assembly).thicknessMm/2000};
}
function intersection(a:Incident,b:Incident,side:number):PlanPoint|null{
 const x=add(a.p,a.n,a.half*side),y=add(b.p,b.n,-b.half*side),den=cross(a.u,b.u);
 if(Math.abs(den)<.1)return null;
 const t=cross(sub(y,x),b.u)/den,point=add(x,a.u,t);
 const bound=3*Math.max(a.half,b.half);
 if(length(sub(point,a.p))>bound||length(sub(point,b.p))>bound)return null;
 return point;
}
function clear(i:Incident,points:Pair){
 const reach=Math.max(0,dot(sub(points.left,i.p),i.u),dot(sub(points.right,i.p),i.u));
 if(reach>i.len*.45)return false;
 return !(i.w.openings??[]).some(o=>{
  const near=i.end==="start"?o.offsetM:i.len-o.offsetM-o.widthM;
  return !Number.isFinite(near)||near<reach+EPS;
 });
}
function ordered(i:Incident,left:PlanPoint,right:PlanPoint):Pair{
 return i.end==="start"?{left,right}:{left:right,right:left};
}
/** Strict two-member corner only. No gap snapping, T/cross guessing, source
 * authority, or change to design centreline/length/quantity. Unequal heights,
 * near openings and acute/ambiguous junctions retain independent geometry. */
export function wallCornerJoins(walls:readonly WallVisual[]):Map<string,WallCornerJoins>{
 const result=new Map<string,WallCornerJoins>(),groups=new Map<string,Incident[]>();
 for(const w of walls)for(const end of ["start","end"] as const){
  const i=incident(w,end);if(!i)continue;
  const k=JSON.stringify([w.scopeKey,w.levelId]),g=groups.get(k)??[];g.push(i);groups.set(k,g);
 }
 for(const group of groups.values()){
  // Spatial buckets retain exact distance checks and avoid quadratic scans.
  const buckets=new Map<string,number[]>();
  const cell=(p:PlanPoint)=>[Math.floor(p[0]/EPS),Math.floor(p[1]/EPS)] as const;
  for(let j=0;j<group.length;j++){
   const [x,y]=cell(group[j].p),key=x+":"+y;
   const ids=buckets.get(key)??[];ids.push(j);buckets.set(key,ids);
  }
  for(let index=0;index<group.length;index++){
   const a=group[index],[x,y]=cell(a.p);
   const peers:{b:Incident;j:number}[]=[];
   for(let dx=-1;dx<=1;dx++)for(let dy=-1;dy<=1;dy++){
    for(const j of buckets.get((x+dx)+":"+(y+dy))??[]){
     if(j!==index&&length(sub(a.p,group[j].p))<=EPS)peers.push({b:group[j],j});
     if(peers.length>1)break;
    }
   }
   if(peers.length!==1||peers[0].j<index)continue;
   const b=peers[0].b;
   if(a.w.proposalId===b.w.proposalId||Math.abs(a.w.heightM-b.w.heightM)>EPS||profileDetails(a.w.assembly).role!==profileDetails(b.w.assembly).role)continue;
   const l=intersection(a,b,1),rr=intersection(a,b,-1);
   if(!l||!rr)continue;
   const pa=ordered(a,l,rr),pb=ordered(b,rr,l);
   // Reject inverted exterior design faces (same handedness when looking away
   // from the junction). A valid perimeter has opposite outward-facing sides.
   if(profileDetails(a.w.assembly).role==="external"){
    const side=(i:Incident)=>(wallAssembly(i.w.assembly).exteriorSide==="left"?1:-1)*(i.end==="start"?1:-1);
    if(side(a)===side(b))continue;
   }
   if(!clear(a,pa)||!clear(b,pb))continue;
   for(const [i,p] of [[a,pa],[b,pb]] as const){
    const row=result.get(i.w.proposalId)??{};row[i.end]=p;result.set(i.w.proposalId,row);
   }
  }
 }
 return result;
}
