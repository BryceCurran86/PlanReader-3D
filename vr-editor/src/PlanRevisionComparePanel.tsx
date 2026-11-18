import { useEffect, useRef, useState } from "react";
import type { SceneManifest } from "./types";
import type { SavedPlanRevision } from "./planRevisionProtocol";
import {
  verifyPlanRevisionComparison,
  type VerifiedPlanRevisionComparison,
} from "./planRevisionComparisonProtocol";

/** Read-only review of two saved working-plan versions. Never changes geometry. */
export function PlanRevisionComparePanel({workspace,revisions}:{workspace:SceneManifest;revisions:SavedPlanRevision[]}){
  const [older,setOlder]=useState<string>("");
  const [newer,setNewer]=useState<string>("");
  const [result,setResult]=useState<VerifiedPlanRevisionComparison|null>(null);
  const [working,setWorking]=useState(false);
  const [error,setError]=useState<string|null>(null);
  const pending=useRef<AbortController|null>(null);

  useEffect(()=>{
    pending.current?.abort();
    setOlder("");setNewer("");setResult(null);setError(null);setWorking(false);
    return ()=>pending.current?.abort();
  },[workspace.scope.workspaceId,workspace.scope.documentId,
     workspace.scope.sourceSha256,workspace.scope.snapshotId,revisions]);

  if(revisions.length<2)return null;
  const olderSelected=revisions.find(r=>r.revisionId===older);
  const newerSelected=revisions.find(r=>r.revisionId===newer);
  const valid=Boolean(olderSelected&&newerSelected&&
    olderSelected.revisionNumber<newerSelected.revisionNumber);

  async function compare(){
    if(!valid||working)return;
    pending.current?.abort();
    const request=new AbortController();
    pending.current=request;
    setError(null);setResult(null);setWorking(true);
    try{
      const response=await fetch(
        `/api/editor/workspaces/${encodeURIComponent(workspace.scope.workspaceId)}/revisions/compare/${older}/${newer}`,
        {method:"GET",credentials:"include",cache:"no-store",signal:request.signal}
      );
      if(!response.ok)throw Error(`Private revision comparison unavailable (${response.status})`);
      const body:unknown=await response.json();
      const verified=verifyPlanRevisionComparison(body,revisions,older,newer);
      if(!request.signal.aborted)setResult(verified);
    }catch(e){
      if(!request.signal.aborted)setError(e instanceof Error?e.message:"Revision comparison unavailable");
    }finally{
      if(!request.signal.aborted){setWorking(false);pending.current=null;}
    }
  }
  return <section className="plan-revision-history" aria-label="Compare saved revisions">
    <h3>Compare saved drawing versions</h3>
    <p className="muted">Review the change sequence and affected sheets. This is not
      architectural redrafting, approval, live pricing or a restore operation.</p>
    <label>Older revision
      <select value={older} disabled={working} onChange={event=>{
        pending.current?.abort();setOlder(event.target.value);setResult(null);setError(null);
      }}>
        <option value="">Choose older version</option>
        {revisions.map(r=><option key={r.revisionId} value={r.revisionId}>{r.revisionLabel}</option>)}
      </select>
    </label>
    <label>Newer revision
      <select value={newer} disabled={working} onChange={event=>{
        pending.current?.abort();setNewer(event.target.value);setResult(null);setError(null);
      }}>
        <option value="">Choose newer version</option>
        {revisions.map(r=><option key={r.revisionId} value={r.revisionId}>{r.revisionLabel}</option>)}
      </select>
    </label>
    <button type="button" disabled={!valid||working} onClick={()=>void compare()}>
      {working?"Verifying revision chain…":"Compare revisions"}
    </button>
    {error&&<p className="error" role="alert">{error}</p>}
    {result&&<div role="status">
      <strong>{result.interveningRevisionCount} saved revision(s) between selected versions</strong>
      <p className="muted">Affected original PDF page indices: {
        result.affectedPageIndices.map(n=>n+1).join(", ")||"None"
      } (displayed as 1-based page numbers).</p>
      <ul>{result.changes.map(change=>
        <li key={change.revisionId}>
          {revisions.find(r=>r.revisionId===change.revisionId)?.revisionLabel} —
          {change.pageIndices.length} source-linked page(s)
        </li>
      )}</ul>
      <p className="muted">Review-only comparison. Source geometry and quantities remain unapproved.</p>
    </div>}
  </section>;
}
