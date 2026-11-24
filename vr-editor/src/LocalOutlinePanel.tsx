import {useState} from "react";
import type {PlacedWall,PlanPoint} from "./buildPlacement.ts";
import {localOutline,editLocalOutline} from "./localOutline.ts";
import type {OutlineEdit} from "./localOutline.ts";
import {newPlacementId} from "./buildPlacement.ts";
type Props={walls:PlacedWall[];blocked:boolean;onEdit:(expected:string,edit:OutlineEdit)=>void};
export function LocalOutlinePanel({walls,blocked,onEdit}:Props){
 const [index,setIndex]=useState(0);
 const [message,setMessage]=useState("");
 const ring=localOutline(walls);
 if(!ring)return <details className="footprint-tools"><summary>Irregular local footprint</summary><p>Draw a single closed ring of connected local draft walls on this level to edit its individual vertices. Original source walls are not converted or replaced.</p></details>;
 const n=ring.points.length,i=Math.min(index,n-1),p=ring.points[i],q=ring.points[(i+1)%n];
 const xs=ring.points.map(p=>p[0]),zs=ring.points.map(p=>p[1]);
 const x0=Math.min(...xs),z0=Math.min(...zs),dx=Math.max(.05,Math.max(...xs)-x0),dz=Math.max(.05,Math.max(...zs)-z0);
 const scale=Math.min(270/dx,150/dz),xy=(p:PlanPoint)=>[15+(p[0]-x0)*scale,15+(p[1]-z0)*scale];
 const commit=(edit:OutlineEdit)=>{
  if(blocked){setMessage("Finish resizing and clear placed catalogue items before topology editing.");return;}
  if(!editLocalOutline(walls,edit)){setMessage("Invalid outline, crossing edges, or an opening cannot be retained. No change applied.");return;}
  onEdit(JSON.stringify(walls),edit);setMessage("Draft perimeter edit submitted; undo restores the previous ring.");
 };
 return <details className="footprint-tools"><summary>Irregular local footprint · {n} points</summary>
 <p>Local draft wall ring only · enclosed outline {ring.areaM2.toFixed(2)} m² (not a verified floor quantity). Select a vertex or enter exact dimensions. Source walls, ceiling/roof geometry and existing source quantities are unchanged.</p>
 <svg viewBox="0 0 300 180" width="300" style={{maxWidth:"100%"}} aria-label="Editable local outline preview">
  <polygon points={ring.points.map(p=>xy(p).join(",")).join(" ")} fill="#79b7a733" stroke="#218d79" strokeWidth="2"/>
  {ring.points.map((p,j)=>{const [x,y]=xy(p);return <g key={j}><circle cx={x} cy={y} r={j===i?6:4} fill={j===i?"#df9b26":"#218d79"}/><text x={x+8} y={y-3} fill="currentColor" fontSize="11">{j+1}</text></g>;})}
 </svg>
 <label>Vertex / outgoing edge <select value={i} onChange={e=>{setIndex(Number(e.target.value));setMessage("");}}>{ring.points.map((_,j)=><option key={j} value={j}>Point {j+1} / edge {j+1}–{(j+1)%n+1}</option>)}</select></label>
 <form key={JSON.stringify([i,p,q])} onSubmit={e=>{
  e.preventDefault();const data=new FormData(e.currentTarget);const operation=(e.nativeEvent as SubmitEvent).submitter?.getAttribute("value");
  const x=Number(data.get("x"))/1000,z=Number(data.get("z"))/1000;
  if(operation==="move")commit({kind:"move-point",index:i,point:[x,z]});
  if(operation==="insert")commit({kind:"insert-point",index:i,point:[x,z],newId:newPlacementId("outline-wall")});
 }}>
 <label>X (mm) <input name="x" type="number" step="1" defaultValue={Math.round(p[0]*1000)} required/></label>
 <label>Z (mm) <input name="z" type="number" step="1" defaultValue={Math.round(p[1]*1000)} required/></label>
 <button disabled={blocked} type="submit" value="move">Move point</button>
 <button disabled={blocked||n>=25} type="submit" value="insert">Insert point on outgoing edge</button>
 <button disabled={blocked||n>=25} type="button" onClick={()=>commit({kind:"insert-point",index:i,point:[(p[0]+q[0])/2,(p[1]+q[1])/2],newId:newPlacementId("outline-wall")})}>Split edge at midpoint</button>
 <button disabled={blocked||n<=3} type="button" onClick={()=>commit({kind:"remove-point",index:i})}>Remove point</button>
 </form>
 <form onSubmit={e=>{e.preventDefault();const data=new FormData(e.currentTarget);commit({kind:"move-edge",index:i,delta:[Number(data.get("dx"))/1000,Number(data.get("dz"))/1000]});}}>
  <label>Edge X shift (mm) <input name="dx" type="number" step="1" defaultValue="0" required/></label>
  <label>Edge Z shift (mm) <input name="dz" type="number" step="1" defaultValue="0" required/></label>
  <button type="submit" disabled={blocked}>Move entire edge</button>
 </form>
 <p role="status">{blocked?"Unavailable while resizing or catalogue placements exist.":message||"Opening widths stay fixed; invalid or intersecting changes are rejected."}</p>
 </details>;
}
