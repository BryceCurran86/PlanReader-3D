import { useEffect, useRef, useState } from "react";
import type { SceneManifest } from "./types";
import {
  makeWallAdditionCommand,validateAdditionSketch,verifyWallAssemblyPreview,
} from "./wallAdditionProtocol";
import type {
  WallAdditionOpening,WallAdditionSketch,WallAssemblyPreview,
} from "./wallAdditionProtocol";

type Props={
  scene:SceneManifest;
  authenticated:boolean;
  onSketch:(sketch:WallAdditionSketch|null)=>void;
};
export function WallAdditionPanel({scene,authenticated,onSketch}:Props){
  const [profile,setProfile]=useState("");
  const [level,setLevel]=useState("");
  const [coords,setCoords]=useState({x1:"",z1:"",x2:"",z2:"",height:""});
  const [door,setDoor]=useState({enabled:false,offset:"",width:"",height:""});
  const [result,setResult]=useState<WallAssemblyPreview|null>(null);
  const [error,setError]=useState<string|null>(null);
  const [working,setWorking]=useState(false);
  const controller=useRef<AbortController|null>(null);
  const proposal=useRef<string|null>(null);
  const levelOptions=[...new Set(scene.objects.map(o=>o.levelId).filter(
    (s):s is string=>typeof s==="string"&&!!s,
  ))].sort();
  const sceneIdentity=[
    scene.scope.workspaceId,scene.scope.sourceSha256,
    scene.scope.snapshotId,scene.scope.modelRevision,
  ].join(":");
  useEffect(()=>{
    controller.current?.abort();
    proposal.current=null;
    setProfile("");setLevel("");setCoords({x1:"",z1:"",x2:"",z2:"",height:""});
    setDoor({enabled:false,offset:"",width:"",height:""});
    setResult(null);setError(null);setWorking(false);
    onSketch(null);
    return ()=>controller.current?.abort();
  },[sceneIdentity,onSketch]);

  function stale(){
    controller.current?.abort();
    controller.current=null;
    setWorking(false);
    setResult(null);setError(null);onSketch(null);
  }
  async function addWallStudy(){
    stale();
    if(!authenticated){
      setError("Authenticate the original PlanReader workspace to request a trusted assembly scope.");
      return;
    }
    const csrf=document.querySelector<HTMLMetaElement>(
      'meta[name="planreader-csrf-token"]',
    )?.content;
    if(!csrf){
      setError("Authenticated wall study requires the application CSRF token.");
      return;
    }
    try{
      if(!proposal.current)proposal.current=`wall-${crypto.randomUUID()}`;
      const sketch=validateAdditionSketch(scene,{
        proposalId:proposal.current,levelId:level,
        start:[Number(coords.x1),Number(coords.z1)],
        end:[Number(coords.x2),Number(coords.z2)],
        heightM:Number(coords.height),
      });
      if(Object.values(coords).some(v=>!v.trim()))
        throw new Error("Enter all coordinates and a wall height in metres");
      const openings:WallAdditionOpening[]=door.enabled?[{
        openingId:`door-${sketch.proposalId}`,
        offsetM:Number(door.offset),widthM:Number(door.width),
        heightM:Number(door.height),sillHeightM:0,openingKind:"door",
      }]:[];
      if(door.enabled&&(!door.offset.trim()||!door.width.trim()||!door.height.trim()))
        throw new Error("Explicitly enter the door offset, width and height");
      const command=makeWallAdditionCommand(scene,sketch,profile,openings);
      onSketch(sketch);
      const abort=new AbortController();
      controller.current=abort;
      setWorking(true);
      const response=await fetch(
        `/api/editor/workspaces/${encodeURIComponent(scene.scope.workspaceId)}/walls/add/preview`,
        {
          method:"POST",credentials:"include",cache:"no-store",
          signal:abort.signal,
          headers:{"Content-Type":"application/json","X-CSRF-Token":csrf},
          body:JSON.stringify(command),
        },
      );
      const body:unknown=await response.json();
      if(!response.ok){
        const err=body&&typeof body==="object"&&"error" in body&&
          typeof body.error==="string"?body.error:"wall_scope_unavailable";
        throw new Error(`Wall trade scope blocked: ${err}`);
      }
      const verified=verifyWallAssemblyPreview(body,scene,command);
      if(!abort.signal.aborted){
        setResult(verified);
        setError(null);
      }
    }catch(e){
      if(!controller.current?.signal.aborted){
        setResult(null);
        setError(e instanceof Error?e.message:"Wall study unavailable");
      }
    }finally{
      if(!controller.current?.signal.aborted){
        controller.current=null;setWorking(false);
      }
    }
  }
  const label=(name:string,text:string,value:string,onChange:(s:string)=>void)=>
    <label className="added-wall-field">{name}
      <input inputMode="decimal" type="number" step="0.05" value={value}
        placeholder={text} onChange={e=>{onChange(e.target.value);stale();}} />
    </label>;
  return <div className="wall-addition-panel" aria-label="New wall and dependent trades">
    <span className="eyebrow">ADD WALL · ALL ASSOCIATED WORK</span>
    <p className="muted">Position a proposed wall and request a project-defined
      framing, bracing, plasterboard, skirting and electrical/plumbing scope.
      All quantities are REVIEW ONLY. A wall or service is not yet saved
      into the source plan.</p>
    <label htmlFor="new-wall-level">Wall level</label>
    <select id="new-wall-level" value={level}
      onChange={e=>{setLevel(e.target.value);stale();}}>
      <option value="">Choose a documented level</option>
      {levelOptions.map(v=><option key={v} value={v}>{v}</option>)}
    </select>
    <label htmlFor="new-wall-profile">Project wall assembly profile ID</label>
    <input id="new-wall-profile" type="text" value={profile}
      maxLength={128} placeholder="Registered profile, e.g. W01"
      onChange={e=>{setProfile(e.target.value);stale();}} />
    <div className="added-wall-grid">
      {label("Start X (m)","X1",coords.x1,v=>setCoords(c=>({...c,x1:v})))}
      {label("Start Z (m)","Z1",coords.z1,v=>setCoords(c=>({...c,z1:v})))}
      {label("End X (m)","X2",coords.x2,v=>setCoords(c=>({...c,x2:v})))}
      {label("End Z (m)","Z2",coords.z2,v=>setCoords(c=>({...c,z2:v})))}
      {label("Wall height (m)","Height",coords.height,
        v=>setCoords(c=>({...c,height:v})))}
    </div>
    <label className="added-wall-checkbox">
      <input type="checkbox" checked={door.enabled}
        onChange={e=>{setDoor(c=>({...c,enabled:e.target.checked}));stale();}} />
      Include a user-positioned doorway
    </label>
    {door.enabled&&<div className="added-wall-grid">
      {label("Door offset (m)","From wall start",door.offset,
        v=>setDoor(c=>({...c,offset:v})))}
      {label("Door width (m)","Documented width",door.width,
        v=>setDoor(c=>({...c,width:v})))}
      {label("Door height (m)","Documented height",door.height,
        v=>setDoor(c=>({...c,height:v})))}
    </div>}
    <button type="button" disabled={working||!authenticated}
      onClick={()=>void addWallStudy()}>
      {working?"Checking all dependent trades…":
       "Add wall to review and calculate associated work"}
    </button>
    {error&&<p role="alert" className="error">{error}</p>}
    {!authenticated&&<p className="muted">Source-authenticated workspace and
      project assembly schedule required. Local demo cannot create commercial work.</p>}
    {result&&<div className="wall-assembly-result" role="status">
      <strong>Linked construction scope for {result.proposalId}</strong>
      <p className="muted">Length {result.package.wall_length_m.toFixed(2)} m
        · Height {result.package.wall_height_m.toFixed(2)} m
        · {result.package.quantities.length} scoped trade lines
        · {result.package.coordination_required.length} coordination holds</p>
      <table>
        <thead><tr><th>Trade</th><th>Work item</th><th>Quantity</th></tr></thead>
        <tbody>{result.package.quantities.map(q=>
          <tr key={q.line_id}>
            <td>{q.trade}</td><td title={q.formula}>
              {q.element}<small>{q.description}</small>
            </td><td>{q.value.toFixed(2)} {q.unit}</td>
          </tr>)}</tbody>
      </table>
      <strong>Electrical / plumbing / structural coordination</strong>
      {result.package.coordination_required.length?
        <ul>{result.package.coordination_required.map(line=>
          <li key={line}>{line.replaceAll("_"," ")}</li>)}</ul>:
        <p>No unresolved coordination items were returned.</p>}
      <p className="muted">No quantities or prices approved. Services are
        included only when project schedules/verified routes establish
        their actual requirements. This proposal does not create a source
        drawing revision until a separately authorized wall-create
        transaction is available.</p>
    </div>}
  </div>;
}
