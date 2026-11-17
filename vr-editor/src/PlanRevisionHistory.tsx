import { useEffect, useRef, useState } from "react";
import type { SceneManifest } from "./types";
import { verifyPlanRevisionHistory } from "./planRevisionProtocol";
import type { SavedPlanRevision } from "./planRevisionProtocol";

export function PlanRevisionHistory({workspace,authenticated}:{
  workspace:SceneManifest;authenticated:boolean;
}) {
  const [items,setItems]=useState<SavedPlanRevision[]|null>(null);
  const [working,setWorking]=useState(false);
  const [error,setError]=useState<string|null>(null);
  const current=useRef<AbortController|null>(null);

  useEffect(()=>{
    current.current?.abort();
    setItems(null);setError(null);setWorking(false);
    return ()=>current.current?.abort();
  },[workspace.scope.workspaceId,workspace.scope.documentId,
     workspace.scope.sourceSha256,workspace.scope.snapshotId]);

  async function loadHistory(){
    if(!authenticated)return;
    current.current?.abort();
    const request=new AbortController();
    current.current=request;
    setWorking(true);setError(null);
    try{
      const response=await fetch(
        `/api/editor/workspaces/${encodeURIComponent(workspace.scope.workspaceId)}/revisions`,
        {method:"GET",credentials:"include",cache:"no-store",signal:request.signal}
      );
      if(!response.ok)throw Error(`Revision history unavailable (${response.status})`);
      const result:unknown=await response.json();
      const verified=verifyPlanRevisionHistory(result,workspace);
      if(!request.signal.aborted)setItems(verified);
    }catch(e){
      if(!request.signal.aborted)
        setError(e instanceof Error?e.message:"Could not load plan revision history");
    }finally{
      if(!request.signal.aborted){
        setWorking(false);current.current=null;
      }
    }
  }
  return <div className="plan-revision-history" aria-label="Saved plan revisions">
    <span className="eyebrow">SAVED DRAWING REVISIONS</span>
    <p className="muted">Each saved version retains the original drawing source,
      an immutable revision chain and its source-verified affected pages.
      A revision marker does not mean geometry on each sheet has been redrawn.</p>
    {!authenticated&&<p className="muted">An authenticated workspace is required to view private revised PDF files.</p>}
    <button type="button" disabled={!authenticated||working}
      onClick={()=>void loadHistory()}>
      {working?"Reading private revision history…":
        items?"Refresh revision history":"View saved plan versions"}
    </button>
    {error&&<p role="alert" className="error">{error}</p>}
    {items?.length===0&&<p className="muted">No saved revisions for this source snapshot.</p>}
    {items?.map(item=><div className="plan-revision-history-row" key={item.revisionId}>
      <strong>{item.revisionLabel} · {item.pagesRevised.length} linked page(s)</strong>
      <p className="muted">Model {item.previousModelRevision} → {item.updatedModelRevision}.
        Unapproved review version; drawing coordination still required.</p>
      <p className="muted">Sheets: {item.pagesRevised.map(p=>p.sheet).join(", ")}</p>
      <a href={item.downloadPath} download>Download this revision PDF</a>
    </div>)}
  </div>;
}
