import { useEffect, useRef, useState } from "react";
import type { SceneManifest } from "./types";
import {
  freshWallBatch,currentWallBatch,wallBatchSourceKey,addOrReplaceWallStudy,removeWallStudy,
  undoWallBatch,redoWallBatch,summarizeWallBatch,compareWallBatches,exportWallBatchReview,
} from "./wallBatchStudy";
import {
  makeWallAdditionCommand,validateAdditionSketch,verifyWallAssemblyPreview,verifyWallConstructionImpact,verifySavedNewWallRevision,
} from "./wallAdditionProtocol";
import type {
  WallAdditionOpening,WallAdditionSketch,WallAssemblyPreview,WallConstructionImpactPreview,WallAdditionCommand,SavedNewWallRevision,
} from "./wallAdditionProtocol";

type Props={
  scene:SceneManifest;
  authenticated:boolean;
  onSketch:(sketch:WallAdditionSketch|null)=>void;
  onBatchSketches:(sketches:WallAdditionSketch[])=>void;
};
export function WallAdditionPanel({scene,authenticated,onSketch,onBatchSketches}:Props){
  const [profile,setProfile]=useState("");
  const [level,setLevel]=useState("");
  const [coords,setCoords]=useState({x1:"",z1:"",x2:"",z2:"",height:""});
  const [door,setDoor]=useState({enabled:false,offset:"",width:"",height:""});
  const [result,setResult]=useState<WallAssemblyPreview|null>(null);
  const [impact,setImpact]=useState<WallConstructionImpactPreview|null>(null);
  const [autoReprice,setAutoReprice]=useState(false);
  const [lastCommand,setLastCommand]=useState<WallAdditionCommand|null>(null);
  const [savedWall,setSavedWall]=useState<SavedNewWallRevision|null>(null);
  const [savingWall,setSavingWall]=useState(false);
  const saveController=useRef<AbortController|null>(null);
  const saveToken=useRef<string|null>(null);
  const activeScope=useRef("");
  // Purely local unapproved construction scope. Recreated on source switch.
  const [batch,setBatch]=useState(()=>freshWallBatch(scene));
  const activeBatch=currentWallBatch(scene,batch);
  const batchReport=summarizeWallBatch(scene,activeBatch);
  const lastBatchDelta=activeBatch.past.length?compareWallBatches(
    scene,{...activeBatch,entries:activeBatch.past[activeBatch.past.length-1]},
    activeBatch,
  ):[];
  // Only original-source-scoped previewed proposals can be projected in 3D.
  const verifiedBatchSketches=activeBatch.entries.map(({command})=>({
    scopeKey:activeBatch.sourceKey,
    proposalId:command.proposalId,levelId:command.levelId,
    start:[...command.startPt] as [number,number],
    end:[...command.endPt] as [number,number],heightM:command.heightM,
  }));
  const [error,setError]=useState<string|null>(null);
  const [working,setWorking]=useState(false);
  const controller=useRef<AbortController|null>(null);
  const proposal=useRef<string|null>(null);
  const levelOptions=[...new Set(scene.objects.map(o=>o.levelId).filter(
    (s):s is string=>typeof s==="string"&&!!s,
  ))].sort();
  const sceneIdentity=wallBatchSourceKey(scene);
  activeScope.current=sceneIdentity;
  useEffect(()=>{
    controller.current?.abort();saveController.current?.abort();
    proposal.current=null;saveToken.current=null;
    setProfile("");setLevel("");setCoords({x1:"",z1:"",x2:"",z2:"",height:""});
    setDoor({enabled:false,offset:"",width:"",height:""});
    setResult(null);setImpact(null);setLastCommand(null);
    setSavedWall(null);setSavingWall(false);setError(null);setWorking(false);
    setAutoReprice(false);
    setBatch(freshWallBatch(scene));
    onSketch(null);
    onBatchSketches([]);
    return ()=>{controller.current?.abort();saveController.current?.abort();};
  },[sceneIdentity,authenticated,onSketch,onBatchSketches]);

  useEffect(()=>{
    onBatchSketches(verifiedBatchSketches);
  // Depend on immutable accepted batch entries, not a new mapped array each render.
  },[activeBatch.entries,onBatchSketches]);

  function stale(){
    controller.current?.abort();
    controller.current=null;
    setWorking(false);
    setResult(null);setImpact(null);setLastCommand(null);
    setSavedWall(null);saveToken.current=null;setError(null);onSketch(null);
  }
  // Automatic replanning never adds a wall to the persistent review batch.
  useEffect(()=>{
    if(!autoReprice||!authenticated||!level||
       !/^[A-Za-z0-9_.:-]{1,128}$/.test(profile)||
       Object.values(coords).some(v=>!v.trim())||
       (door.enabled&&[door.offset,door.width,door.height].some(v=>!v.trim())))
      return;
    const timer=window.setTimeout(()=>{void addWallStudy(false);},700);
    return ()=>window.clearTimeout(timer);
  },[autoReprice,authenticated,sceneIdentity,level,profile,coords,door]);

  async function addWallStudy(addToBatch=true){
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
      const verifiedImpact=verifyWallConstructionImpact(body,verified);
      if(!abort.signal.aborted){
        if(addToBatch)setBatch(previous=>addOrReplaceWallStudy(
          scene,currentWallBatch(scene,previous),command,verified,
        ));
        // Once the validated proposal joins the batch, remove the transient
        // single-wall ghost. Otherwise a removed wall would still appear.
        onSketch(null);
        setResult(verified);
        setLastCommand(command);
        setImpact(verifiedImpact);
        setError(null);
      }
    }catch(e){
      if(!controller.current?.signal.aborted){
        setResult(null);setImpact(null);setLastCommand(null);
        setError(e instanceof Error?e.message:"Wall study unavailable");
      }
    }finally{
      if(!controller.current?.signal.aborted){
        controller.current=null;setWorking(false);
      }
    }
  }
  async function commitWall(){
    if(!authenticated||!lastCommand||!result||savingWall||working||
       result.proposalId!==lastCommand.proposalId)return;
    const csrf=document.querySelector<HTMLMetaElement>(
      'meta[name="planreader-csrf-token"]',
    )?.content;
    if(!csrf){setError("Wall creation requires authenticated CSRF.");return;}
    saveController.current?.abort();
    const abort=new AbortController();
    saveController.current=abort;
    setSavingWall(true);setError(null);
    const exactScope=sceneIdentity;
    try{
      if(!saveToken.current)saveToken.current=`save-${crypto.randomUUID()}`;
      const body={...lastCommand,idempotencyKey:saveToken.current};
      const response=await fetch(
        `/api/editor/workspaces/${encodeURIComponent(scene.scope.workspaceId)}/walls/add/commit`,
        {method:"POST",credentials:"include",cache:"no-store",
         signal:abort.signal,headers:{"Content-Type":"application/json","X-CSRF-Token":csrf},
         body:JSON.stringify(body)},
      );
      const raw:unknown=await response.json();
      if(!response.ok){
        const reason=raw&&typeof raw==="object"&&"error" in raw&&
          typeof raw.error==="string"?raw.error:"wall_create_unavailable";
        throw new Error("Wall not saved: "+reason);
      }
      const saved=verifySavedNewWallRevision(raw,scene,lastCommand);
      if(!abort.signal.aborted&&activeScope.current===exactScope){
        setSavedWall(saved);setLastCommand(null);
        setResult(null);setImpact(null);
        setAutoReprice(false);
        setBatch(freshWallBatch(scene));
        onBatchSketches([]);
        onSketch(null);
      }
    }catch(e){
      if(!abort.signal.aborted&&activeScope.current===exactScope)
        setError(e instanceof Error?e.message:"Wall creation unavailable");
    }finally{
      if(!abort.signal.aborted){setSavingWall(false);saveController.current=null;}
    }
  }
  function downloadBatchReview(){
    try{
      const json=exportWallBatchReview(scene,activeBatch);
      const blob=new Blob([json],{type:"application/json"});
      const url=URL.createObjectURL(blob);
      const anchor=document.createElement("a");
      anchor.href=url;anchor.download="planreader-vr-multi-wall-review.json";
      document.body.appendChild(anchor);anchor.click();anchor.remove();
      URL.revokeObjectURL(url);
    }catch(e){setError(e instanceof Error?e.message:"Review export unavailable");}
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
    <label className="added-wall-checkbox">
      <input type="checkbox" checked={autoReprice} disabled={!authenticated}
        onChange={e=>{stale();setAutoReprice(e.target.checked);}} />
      Live preview construction costs and related pages after wall changes (700 ms pause)
    </label>
    <button type="button" disabled={working||!authenticated}
      onClick={()=>void addWallStudy(true)}>
      {working?"Checking all dependent trades…":
       "Add wall to review and calculate associated work"}
    </button>
    {error&&<p role="alert" className="error">{error}</p>}
    {!authenticated&&<p className="muted">Source-authenticated workspace and
      project assembly schedule required. Local demo cannot create commercial work.</p>}
    <section className="wall-assembly-result" aria-label="Multi-wall review batch">
      <strong>MULTI-WALL REVIEW · LOCAL WHAT-IF</strong>
      <p className="muted">{batchReport.wallCount} proposed wall(s) across
        {batchReport.levels.length} level(s). Totals are preliminary construction
        work scopes, not canonical takeoff rows or priced quotations.</p>
      <div className="live-cost-actions">
        <button type="button" disabled={working||!activeBatch.past.length}
          onClick={()=>setBatch(b=>undoWallBatch(currentWallBatch(scene,b)))}>
          Undo batch change
        </button>
        <button type="button" disabled={working||!activeBatch.future.length}
          onClick={()=>setBatch(b=>redoWallBatch(currentWallBatch(scene,b)))}>
          Redo batch change
        </button>
        <button type="button" disabled={!batchReport.wallCount||working}
          onClick={downloadBatchReview}>
          Export review summary
        </button>
      </div>
      {activeBatch.entries.map(entry=><div key={entry.command.proposalId}>
        <strong>{entry.command.proposalId}</strong>
        <span> · {entry.command.levelId}
          · {entry.preview.package.wall_length_m.toFixed(2)} m
          · {entry.preview.package.quantities.length} trade lines</span>
        <button type="button" disabled={working}
          onClick={()=>setBatch(b=>removeWallStudy(
            scene,currentWallBatch(scene,b),entry.command.proposalId,
          ))}>Remove from batch</button>
      </div>)}
      {batchReport.wallCount>0&&<>
        <strong>Combined trade takeoff study</strong>
        <table><thead><tr><th>Trade</th><th>Work item</th><th>Quantity</th></tr></thead>
          <tbody>{batchReport.tradeTotals.map(q=><tr
            key={JSON.stringify([q.trade,q.element,q.description,q.specificationId,q.unit])}>
            <td>{q.trade}</td><td>{q.element}<small>{q.description}</small></td>
            <td>{q.value.toFixed(2)} {q.unit}</td>
          </tr>)}</tbody>
        </table>
        <strong>Changes since prior review checkpoint</strong>
        {lastBatchDelta.length?
          <table><thead><tr><th>Trade</th><th>Work item</th><th>Difference</th></tr></thead>
            <tbody>{lastBatchDelta.map(q=><tr
              key={JSON.stringify([q.trade,q.element,q.description,q.specificationId,q.unit])}>
              <td>{q.trade}</td><td>{q.element}</td>
              <td>{q.value>0?"+":""}{q.value.toFixed(2)} {q.unit}</td>
            </tr>)}</tbody></table>:
          <p className="muted">No changed construction quantities from the previous checkpoint.</p>}
        <strong>Level totals</strong>
        {batchReport.perLevelTotals.map(group=>
          <div key={group.levelId}>
            <strong>{group.levelId} · {
              batchReport.levels.find(l=>l.levelId===group.levelId)?.wallCount
            } wall(s)</strong>
            <ul>{group.totals.map(q=><li
              key={JSON.stringify([q.trade,q.element,q.description,q.specificationId,q.unit])}>
              {q.trade}: {q.element} — {q.value.toFixed(2)} {q.unit}
            </li>)}</ul>
          </div>)}
        <strong>Wall intersection / overlap coordination</strong>
        {batchReport.geometryConflicts.length?
          <ul>{batchReport.geometryConflicts.map((c,i)=>
            <li key={i}>{c.levelId}: {c.first} ↔ {c.second}
              · {c.type.replaceAll("_"," ")} — inspect connection/detail</li>)}</ul>:
          <p className="muted">No proposed wall segment conflicts detected within this batch.</p>}
        <strong>Outstanding design and service coordination</strong>
        {batchReport.coordinationHolds.length?
          <ul>{batchReport.coordinationHolds.map(h=>
            <li key={h}>{h.replaceAll("_"," ")}</li>)}</ul>:
          <p className="muted">No further coordination holds returned for these proposals.</p>}
      </>}
      <p className="muted">This batch does not persist walls, change a PDF,
        authorize new services or publish commercial quantities. The explicit
        server-side wall assembly previews and original drawing source remain
        the only inputs. Saved-plan revisions are a separate controlled workflow.</p>
    </section>
    {lastCommand&&result&&!savedWall&&
      <section className="wall-assembly-result">
        <strong>Commit new wall + every registered drawing page</strong>
        <p className="muted">Requires a separate wall-create grant, current
          document head, and complete independently verified page projections.
          Creates an immutable review drawing set and a working-design wall;
          this does not approve construction or modify original source plans.</p>
        <button type="button" disabled={savingWall||working||!authenticated}
          onClick={()=>void commitWall()}>
          {savingWall?"Saving wall and coordinated pages…":
            "Create working wall and revise related PDF pages"}
        </button>
      </section>}
    {savedWall&&<section className="wall-assembly-result" role="status">
      <strong>Working wall created · revision {savedWall.revisionNumber}</strong>
      <p>{savedWall.pagesRevised.length} registered drawing page(s) received
        proposed-wall vectors. Commercial release remains blocked.</p>
      <ul>{savedWall.pagesRevised.map(p=>
        <li key={p.pageIndex}>Page {p.pageIndex+1} · {p.sheetId} · {p.pageKind}</li>)}</ul>
      <a href={savedWall.downloadPath} download>Download immutable working revision PDF</a>
      <p className="muted">Reload the project to hydrate the new model revision
        before further changes. The original architectural source is preserved.</p>
    </section>}
    {impact&&<section className="wall-assembly-result" role="status" aria-label="New wall preliminary costing and drawing impact">
      <strong>LIVE CONSTRUCTION COST STUDY · NOT A QUOTE</strong>
      <p>Priced construction subtotal: {impact.currency??"Currency unavailable"} {impact.pricedSubtotalOnly}
        {" · "}{impact.pricedComplete?"All returned work lines have a rate":"Incomplete rates — subtotal only"}</p>
      <p className="muted">Company rate revision: {impact.rateBookRevision??"not connected"}.
        Taxes, margins, unspecified work and coordination holds are not included
        in this provisional subtotal.</p>
      <strong>Related drawing pages — coordination review</strong>
      {impact.affectedPages.length?
        <ul>{impact.affectedPages.map(page=>
          <li key={page.pageIndex}>Page {page.pageIndex+1}: {page.sheetId}</li>)}</ul>:
        <p className="muted">No verified linked pages supplied by the drawing provider.</p>}
      <p>{impact.relatedPagesVerified?"Registered related pages identified for review.":"Related-page registration incomplete."}
        {" "}No drawing pages have been revised.</p>
      {impact.constructionHolds.length>0&&
        <p className="muted">Outstanding holds: {impact.constructionHolds.join("; ")}</p>}
    </section>}
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
