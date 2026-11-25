import type {SceneManifest} from "./types.ts";
import type {BuildState,PlanPoint,WallVisual} from "./buildPlacement.ts";
import {openingFits,planLength} from "./buildPlacement.ts";
import {wallAssembly} from "./wallProfiles.ts";
import {projectPlan,projectWall} from "./footprintResize.ts";
import type {FootprintProjection} from "./footprintResize.ts";

type PlanLine={a:PlanPoint;b:PlanPoint;kind:"wall"|"source"|"review"|"opening"|"window"|"door"|"dimension";weight:number};
type PlanText={at:PlanPoint;text:string};
export type PlanDrawing={lines:PlanLine[];labels:PlanText[];bounds:[number,number,number,number];level:string;unlocated:number};
type Move={objectId:string;dx:number;dz:number};
/** All geometry in model metres. Only editable draft walls have known physical thickness.
 * Source lines and positioned openings remain review evidence, never invented assemblies. */
export function architecturalPlan(scene:SceneManifest,build:Pick<BuildState,"walls">,level:string,visible?:ReadonlySet<string>,projection:FootprintProjection|null=null,moves:readonly Move[]=[],extra:readonly WallVisual[]=[]):PlanDrawing{
 const lines:PlanLine[]=[],labels:PlanText[]=[];let unlocated=0;
 const moveMap=new Map(moves.map(m=>[m.objectId,m]));
 function line(a:PlanPoint,b:PlanPoint,kind:PlanLine["kind"],weight=1){
  if([...a,...b].every(Number.isFinite)&&planLength(a,b)>1e-7)lines.push({a,b,kind,weight});
 }
 for(const row of scene.objects){
  const g=row.geometry;
  if(row.objectType!=="wall"||!g||(level!=="all"&&row.levelId!==level)||(visible&&!visible.has(row.objectId)))continue;
  const move=moveMap.get(row.objectId),transform=(p:PlanPoint):PlanPoint=>{
   const q=projection?projectPlan(p,projection):p;
   return [q[0]+(move?.dx??0)*(projection?.scaleX??1),q[1]+(move?.dz??0)*(projection?.scaleZ??1)];
  };
  const a=transform(g.start),b=transform(g.end),length=planLength(g.start,g.end);
  if(length<1e-7)continue;
  line(a,b,row.renderState==="verified"?"source":"review",1);
  const positioned=row.openingReview?.positioned??[];
  unlocated+=Math.max(0,(row.openingReview?.recordCount??0)-positioned.length);
  for(const o of positioned){
   const point=(d:number):PlanPoint=>transform([g.start[0]+(g.end[0]-g.start[0])*d/length,g.start[1]+(g.end[1]-g.start[1])*d/length]);
   const p=point(o.offsetM),q=point(o.offsetM+o.widthM);
   line(p,q,o.kind==="window"?"window":"opening",2);
  }
 }
 const unique=new Map<string,WallVisual>([...extra,...build.walls].map(w=>[w.proposalId,w]));
 for(const raw of unique.values()){
  if(level!=="all"&&raw.levelId!==level)continue;
  const w=projection?projectWall(raw,projection):raw;
  const length=planLength(w.start,w.end);
  if(!Number.isFinite(length)||length<.05)continue;
  const ux=(w.end[0]-w.start[0])/length,uz=(w.end[1]-w.start[1])/length,t=wallAssembly(w.assembly).thicknessMm/2000;
  const p=(x:number,z:number):PlanPoint=>[w.start[0]+ux*x-uz*z,w.start[1]+uz*x+ux*z];
  const openings=(w.openings??[]).filter(o=>openingFits(w,o)).sort((a,b)=>a.offsetM-b.offsetM);
  function solid(a:number,b:number){
   if(b-a<1e-7)return;
   line(p(a,-t),p(b,-t),"wall",2);line(p(a,t),p(b,t),"wall",2);
   line(p(a,-t),p(a,t),"wall");line(p(b,-t),p(b,t),"wall");
  }
  let cursor=0;
  for(const o of openings){
   if(o.offsetM<cursor-1e-7)continue;
   solid(cursor,o.offsetM);cursor=o.offsetM+o.widthM;
   if(o.openingKind==="window"){
    line(p(o.offsetM,-t*.35),p(cursor,-t*.35),"window");line(p(o.offsetM,t*.35),p(cursor,t*.35),"window");
   }else if(o.openingKind==="door"){
    // Draft hinged leaf is illustrated; swing side is not an approved design.
    line(p(o.offsetM,0),p(o.offsetM,o.widthM),"door");
    for(let i=0;i<12;i++){
     const a=i*Math.PI/24,b=(i+1)*Math.PI/24;
     line(p(o.offsetM+o.widthM*Math.cos(a),o.widthM*Math.sin(a)),p(o.offsetM+o.widthM*Math.cos(b),o.widthM*Math.sin(b)),"door");
    }
   }else line(p(o.offsetM,0),p(cursor,0),"opening");
  }
  solid(cursor,length);
  if(labels.length<120&&length>=.5){
   const offset=t+.24;
   line(p(0,offset),p(length,offset),"dimension");
   for(const x of [0,length])line(p(x,offset-.06),p(x,offset+.06),"dimension");
   labels.push({at:p(length/2,offset+.11),text:String(Math.round(length*1000))});
  }
 }
 let minX=Infinity,minZ=Infinity,maxX=-Infinity,maxZ=-Infinity;
 for(const l of lines)for(const p of [l.a,l.b]){minX=Math.min(minX,p[0]);minZ=Math.min(minZ,p[1]);maxX=Math.max(maxX,p[0]);maxZ=Math.max(maxZ,p[1]);}
 if(!Number.isFinite(minX)){minX=0;minZ=0;maxX=1;maxZ=1;}
 return {lines,labels,bounds:[minX,minZ,maxX,maxZ],level,unlocated};
}
/** Same paper-style drawing on desktop and headset, with metric scale bar. */
export function paintArchitecturalPlan(ctx:CanvasRenderingContext2D,plan:PlanDrawing,width:number,height:number){
 ctx.clearRect(0,0,width,height);ctx.fillStyle="#faf9f5";ctx.fillRect(0,0,width,height);
 const pad=width*.08,top=height*.12,bottom=height*.15;
 const [x0,z0,x1,z1]=plan.bounds;
 const scale=Math.min((width-2*pad)/Math.max(x1-x0,.1),(height-top-bottom)/Math.max(z1-z0,.1));
 const ox=(width-(x1-x0)*scale)/2,oz=top+(height-top-bottom-(z1-z0)*scale)/2;
 const pos=(p:PlanPoint):PlanPoint=>[ox+(p[0]-x0)*scale,oz+(p[1]-z0)*scale];
 const colors={wall:"#25313a",source:"#505a64",review:"#99703f",opening:"#99703f",window:"#397b99",door:"#496272",dimension:"#78818a"};
 ctx.lineCap="butt";
 for(const l of plan.lines){
  const a=pos(l.a),b=pos(l.b);
  ctx.strokeStyle=colors[l.kind];ctx.lineWidth=Math.max(1,width/1000*l.weight*1.6);
  ctx.setLineDash(l.kind==="review"||l.kind==="opening"?[5,4]:[]);
  ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.stroke();
 }
 ctx.setLineDash([]);ctx.textAlign="center";ctx.font=Math.max(11,width*.014)+"px sans-serif";ctx.fillStyle="#4c5560";
 for(const l of plan.labels){const p=pos(l.at);ctx.fillText(l.text,p[0],p[1]);}
 ctx.textAlign="left";ctx.fillStyle="#25313a";ctx.font="bold "+Math.round(width*.029)+"px sans-serif";
 ctx.fillText("ARCHITECTURAL PLAN · "+plan.level.toUpperCase(),pad,top*.5,width-2*pad);
 const available=(width*.28)/scale,bar=[.1,.2,.5,1,2,5,10,20,50,100].filter(x=>x<=available).pop()??available;
 const y=height-bottom*.8;ctx.fillRect(pad,y,bar*scale,4);
 ctx.font=Math.round(width*.016)+"px sans-serif";ctx.fillText(bar.toPrecision(2)+" m",pad,y-5);
 ctx.font=Math.round(width*.015)+"px sans-serif";ctx.fillText("Dark: draft walls  ·  Grey/ochre: source evidence  ·  Blue: openings",pad,height-bottom*.35,width-2*pad);
 ctx.fillText("Draft dimensions in mm · Not a certified drawing"+(plan.unlocated?" · "+plan.unlocated+" unlocated openings":""),pad,height-bottom*.12,width-2*pad);
}
