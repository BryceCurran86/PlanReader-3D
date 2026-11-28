import {useEffect,useMemo,useRef,useState} from "react";
import type {PointerEvent} from "react";
import {architecturalPlan,paintArchitecturalPlan} from "./architecturalPlan";
import {millimetrePoint,validEditedWall,validCeiling} from "./buildPlacement";
import type {BuildAction,BuildState,PlanPoint,PlacedWall,CeilingDraft} from "./buildPlacement";
type Inputs=Parameters<typeof architecturalPlan>;
type Props={scene:Inputs[0];build:BuildState;level:Inputs[2];visible:Inputs[3];projection:Inputs[4];moves:Inputs[5];extra:Inputs[6];shell?:Inputs[7];onEdit?:(action:BuildAction)=>void;onSelect?:(id:string|null)=>void;blocked?:boolean};
type Target={kind:"wall";object:PlacedWall}|{kind:"ceiling";object:CeilingDraft};
type Transform={scale:number;ox:number;oz:number;x0:number;z0:number};
function transform(bounds:InputsBounds):Transform{
 const [x0,z0,x1,z1]=bounds,scale=Math.min(1176/Math.max(x1-x0,.1),730/Math.max(z1-z0,.1));
 return {scale,ox:(1400-(x1-x0)*scale)/2,oz:120+(730-(z1-z0)*scale)/2,x0,z0};
}
type InputsBounds=ReturnType<typeof architecturalPlan>["bounds"];
function modelPoint(e:PointerEvent<HTMLCanvasElement>,t:Transform):PlanPoint{
 const r=e.currentTarget.getBoundingClientRect();
 return [t.x0+((e.clientX-r.left)*1400/r.width-t.ox)/t.scale,t.z0+((e.clientY-r.top)*1000/r.height-t.oz)/t.scale];
}
function distance(p:PlanPoint,a:PlanPoint,b:PlanPoint){
 const dx=b[0]-a[0],dz=b[1]-a[1],d=dx*dx+dz*dz;
 const f=d?Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dz)/d)):0;
 return Math.hypot(p[0]-a[0]-dx*f,p[1]-a[1]-dz*f);
}
export function ArchitecturalPlan({scene,build,level,visible,projection,moves,extra,shell,onEdit,onSelect,blocked}:Props){
 const canvas=useRef<HTMLCanvasElement>(null);
 const drawing=useMemo(()=>architecturalPlan(scene,build,level,visible,projection,moves,extra,shell),[scene,build.walls,level,visible,projection,moves,extra,shell]);
 const t=useMemo(()=>transform(drawing.bounds),[drawing]);
 const [kind,setKind]=useState<"wall"|"ceiling">("wall");
 const [edit,setEdit]=useState<"move"|"stretch">("move");
 const [connected,setConnected]=useState(true);
 const [selected,setSelected]=useState<string|null>(null);
 const [preview,setPreview]=useState<Target|null>(null);
 const [hint,setHint]=useState("");
 const drag=useRef<{id:number;target:Target;start:PlanPoint;t:Transform;first:boolean}|null>(null);
 const enabled=!!onEdit&&!projection&&!blocked;
 useEffect(()=>{
  const ctx=canvas.current?.getContext("2d");if(!ctx)return;
  paintArchitecturalPlan(ctx,drawing,1400,1000);
  const chosen=preview?.object??[...build.walls,...build.ceilings].find(o=>o.proposalId===selected);
  if(!chosen)return;
  const pos=(p:PlanPoint):PlanPoint=>[t.ox+(p[0]-t.x0)*t.scale,t.oz+(p[1]-t.z0)*t.scale];
  const a=pos(chosen.start),b=pos(chosen.end);
  ctx.strokeStyle="#087f8c";ctx.lineWidth=5;ctx.setLineDash([8,5]);ctx.beginPath();
  if(kind==="ceiling")ctx.rect(a[0],a[1],b[0]-a[0],b[1]-a[1]);else{ctx.moveTo(...a);ctx.lineTo(...b);}
  ctx.stroke();ctx.setLineDash([]);ctx.fillStyle="#087f8c";for(const p of [a,b]){ctx.beginPath();ctx.arc(p[0],p[1],7,0,Math.PI*2);ctx.fill();}
 },[drawing,t,build.walls,build.ceilings,selected,preview,kind]);
 function down(e:PointerEvent<HTMLCanvasElement>){
  if(!enabled||e.button!==0||!e.isPrimary)return;
  const p=modelPoint(e,t),r=e.currentTarget.getBoundingClientRect(),tol=Math.max(.08,18*1400/r.width/t.scale);
  const scoped=(o:PlacedWall|CeilingDraft)=>(level==="all"||o.levelId===level);
  let target:Target|undefined;
  if(kind==="wall"){
   const hit=build.walls.filter(scoped).map(o=>({o,d:distance(p,o.start,o.end)})).filter(x=>x.d<=tol).sort((a,b)=>a.d-b.d)[0];
   if(hit)target={kind:"wall",object:hit.o};
  }else{
   const hit=build.ceilings.filter(scoped).filter(o=>p[0]>=Math.min(o.start[0],o.end[0])-tol&&p[0]<=Math.max(o.start[0],o.end[0])+tol&&p[1]>=Math.min(o.start[1],o.end[1])-tol&&p[1]<=Math.max(o.start[1],o.end[1])+tol)[0];
   if(hit)target={kind:"ceiling",object:hit};
  }
  setSelected(target?.object.proposalId??null);onSelect?.(target?.object.proposalId??null);
  if(!target)return;
  const o=target.object,first=Math.hypot(p[0]-o.start[0],p[1]-o.start[1])<Math.hypot(p[0]-o.end[0],p[1]-o.end[1]);
  drag.current={id:e.pointerId,target,start:p,t,first};e.currentTarget.setPointerCapture(e.pointerId);setHint("Drag to move or stretch; release to apply.");
 }
 function candidate(e:PointerEvent<HTMLCanvasElement>):Target|null{
  const d=drag.current;if(!d||d.id!==e.pointerId)return null;
  const p=modelPoint(e,d.t),dx=p[0]-d.start[0],dz=p[1]-d.start[1],o=d.target.object;
  if(Math.hypot(dx,dz)<.001)return null;
  const shift=(v:PlanPoint)=>millimetrePoint([v[0]+dx,v[1]+dz]);
  const start=edit==="move"||d.first?shift(o.start):o.start,end=edit==="move"||!d.first?shift(o.end):o.end;
  if(!start||!end)return null;
  if(d.target.kind==="wall"){const object={...d.target.object,start,end};return validEditedWall(object)?{kind:"wall",object}:null;}
  const object={...d.target.object,start,end};return validCeiling(start,end)?{kind:"ceiling",object}:null;
 }
 function up(e:PointerEvent<HTMLCanvasElement>){
  const d=drag.current;if(!d||d.id!==e.pointerId)return;
  const next=candidate(e);drag.current=null;setPreview(null);
  if(e.currentTarget.hasPointerCapture(e.pointerId))e.currentTarget.releasePointerCapture(e.pointerId);
  if(!enabled||!next)return;
  if(next.kind==="wall"&&d.target.kind==="wall")onEdit?.({kind:"adjust",previous:d.target.object,wall:next.object,...(connected?{connected:true,allowTJunctions:true}:{})});
  if(next.kind==="ceiling"&&d.target.kind==="ceiling")onEdit?.({kind:"adjust-ceiling",previous:d.target.object,ceiling:next.object});
  setHint("Edit submitted to shared building model. Check the geometry and feedback.");
 }
 function cancel(){drag.current=null;setPreview(null);}
 function download(){const node=canvas.current;if(!node)return;node.toBlob(blob=>{if(!blob)return;const url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download="planreader-plan-preview.png";a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);});}
 return <section aria-label="Architectural plan preview"><p>Editable local draft plan · original source remains read-only. Changes use the same building model as 3D.</p>
 <label>Object <select value={kind} onChange={e=>{cancel();setSelected(null);setKind(e.currentTarget.value as typeof kind);}}><option value="wall">Walls</option><option value="ceiling">Ceilings</option></select></label>
 <label>Action <select value={edit} onChange={e=>{cancel();setEdit(e.currentTarget.value as typeof edit);}}><option value="move">Move</option><option value="stretch">Stretch nearest end</option></select></label>
 <label><input type="checkbox" checked={connected} onChange={e=>setConnected(e.currentTarget.checked)}/> Keep wall junctions connected</label>
 <button type="button" onClick={download}>Save plan preview PNG</button>
 <p role="status">{enabled?hint||"Choose a wall or ceiling, then drag it on the plan.": "Finish the active footprint or placement tool before editing the plan."}</p>
 <canvas ref={canvas} width={1400} height={1000} style={{width:"100%",height:"auto",display:"block",touchAction:"none",cursor:enabled?"crosshair":"default"}} aria-label="2D architectural plan drawing" onPointerDown={down} onPointerMove={e=>{if(drag.current)setPreview(candidate(e));}} onPointerUp={up} onPointerCancel={cancel} onLostPointerCapture={cancel}/></section>;
}
