/** Local, source-locked multi-wall construction-review workbench.
 *
 * Every line is an unapproved SERVER REVIEW PREVIEW from the existing wall
 * assembly endpoint. Grouping here is NOT an independent quantity issuer,
 * tariff calculator or an authority to edit source drawings.
 */
import type { SceneManifest } from "./types.ts";
import type { WallAdditionCommand, WallAssemblyPreview } from "./wallAdditionProtocol.ts";
import { verifyWallAssemblyPreview } from "./wallAdditionProtocol.ts";

export const MAX_BATCH_WALLS = 25;
export interface WallStudyEntry {
  command: WallAdditionCommand;
  preview: WallAssemblyPreview;
}
export interface WallStudyBatch {
  sourceKey: string;
  entries: WallStudyEntry[];
  past: WallStudyEntry[][];
  future: WallStudyEntry[][];
}
export interface StudyQuantity {
  trade: string;
  element: string;
  description: string;
  specificationId: string;
  unit: string;
  value: number;
  wallCount: number;
}
export interface StudyConflict {
  first: string;
  second: string;
  levelId: string;
  type: "collinear_overlap" | "intersection_or_touch";
}
export interface WallBatchReport {
  sourceKey: string;
  wallCount: number;
  levels: {levelId:string; wallCount:number}[];
  tradeTotals: StudyQuantity[];
  perLevelTotals: {levelId:string; totals:StudyQuantity[]}[];
  coordinationHolds: string[];
  geometryConflicts: StudyConflict[];
  requiresCoordination: boolean;
  reviewOnly: true;
  persisted: false;
  commerciallyApproved: false;
  quoteReady: false;
}

export function wallBatchSourceKey(scene:SceneManifest):string {
  const s=scene.scope;
  return JSON.stringify([
    s.workspaceId,s.projectId,s.documentId,s.revisionId,
    s.snapshotId,s.sourceSha256,s.modelRevision,
  ]);
}
export function freshWallBatch(scene:SceneManifest):WallStudyBatch {
  return {sourceKey:wallBatchSourceKey(scene),entries:[],past:[],future:[]};
}
export function currentWallBatch(scene:SceneManifest,batch:WallStudyBatch):WallStudyBatch {
  return batch.sourceKey===wallBatchSourceKey(scene)?batch:freshWallBatch(scene);
}
function assertScope(scene:SceneManifest,batch:WallStudyBatch):void {
  if(batch.sourceKey!==wallBatchSourceKey(scene))
    throw Error("The wall batch belongs to a different drawing revision");
}
function boundedHistory(past:WallStudyEntry[][], entries:WallStudyEntry[]):WallStudyEntry[][] {
  return [...past,entries].slice(-20);
}
export function addOrReplaceWallStudy(
  scene:SceneManifest,batch:WallStudyBatch,
  command:WallAdditionCommand,preview:WallAssemblyPreview,
):WallStudyBatch {
  assertScope(scene,batch);
  const s=scene.scope;
  if(command.workspaceId!==s.workspaceId||command.projectId!==s.projectId||
     command.documentId!==s.documentId||command.revisionId!==s.revisionId||
     command.snapshotId!==s.snapshotId||command.sourceSha256!==s.sourceSha256||
     command.baseModelRevision!==s.modelRevision)
    throw Error("Wall command source revision has changed");
  verifyWallAssemblyPreview(preview,scene,command);
  // A proposal replaces its previous variant, never charges twice.
  const existing=batch.entries.findIndex(e=>e.command.proposalId===command.proposalId);
  if(existing<0&&batch.entries.length>=MAX_BATCH_WALLS)
    throw Error("Multi-wall review limit reached");
  const entry:WallStudyEntry={command,preview};
  const entries=existing>=0
    ?batch.entries.map((e,i)=>i===existing?entry:e)
    :[...batch.entries,entry];
  return {
    sourceKey:batch.sourceKey,entries,
    past:boundedHistory(batch.past,batch.entries),future:[],
  };
}
export function removeWallStudy(scene:SceneManifest,batch:WallStudyBatch,id:string):WallStudyBatch {
  assertScope(scene,batch);
  const entries=batch.entries.filter(e=>e.command.proposalId!==id);
  if(entries.length===batch.entries.length)return batch;
  return {sourceKey:batch.sourceKey,entries,
    past:boundedHistory(batch.past,batch.entries),future:[]};
}
export function undoWallBatch(batch:WallStudyBatch):WallStudyBatch {
  if(!batch.past.length)return batch;
  return {...batch,entries:batch.past[batch.past.length-1],
    past:batch.past.slice(0,-1),future:[batch.entries,...batch.future].slice(0,20)};
}
export function redoWallBatch(batch:WallStudyBatch):WallStudyBatch {
  if(!batch.future.length)return batch;
  return {...batch,entries:batch.future[0],
    past:boundedHistory(batch.past,batch.entries),
    future:batch.future.slice(1)};
}
function group(lines:ReadonlyArray<WallStudyEntry>):StudyQuantity[] {
  const totals=new Map<string,StudyQuantity>();
  for(const entry of lines) {
    const seen=new Set<string>();
    for(const q of entry.preview.package.quantities) {
      const key=JSON.stringify([
        q.trade,q.element,q.description,q.specification_id,q.unit,
      ]);
      if(seen.has(q.line_id))throw Error("Repeated wall trade line identity");
      seen.add(q.line_id);
      const previous=totals.get(key);
      const combined=(previous?.value??0)+q.value;
      if(!Number.isFinite(combined)||combined<0||combined>1e12)
        throw Error("Unbounded wall construction review total");
      totals.set(key,{
        trade:q.trade,element:q.element,description:q.description,
        specificationId:q.specification_id,unit:q.unit,
        value:Math.round(combined*1e6)/1e6,
        wallCount:(previous?.wallCount??0)+1,
      });
    }
  }
  return [...totals.values()].sort((a,b)=>JSON.stringify([
    a.trade,a.element,a.description,a.specificationId,a.unit,
  ]).localeCompare(JSON.stringify([
    b.trade,b.element,b.description,b.specificationId,b.unit,
  ])));
}
const EPS=1e-7;
type Pt=readonly [number,number];
function orient(a:Pt,b:Pt,c:Pt):number {
  return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
}
function on(a:Pt,b:Pt,c:Pt):boolean {
  return Math.abs(orient(a,b,c))<=EPS &&
    c[0]>=Math.min(a[0],b[0])-EPS&&c[0]<=Math.max(a[0],b[0])+EPS&&
    c[1]>=Math.min(a[1],b[1])-EPS&&c[1]<=Math.max(a[1],b[1])+EPS;
}
function conflictKind(a:Pt,b:Pt,c:Pt,d:Pt):StudyConflict["type"]|null {
  const ab=orient(a,b,c), ad=orient(a,b,d),
    ca=orient(c,d,a),cb=orient(c,d,b);
  if(Math.abs(ab)<=EPS&&Math.abs(ad)<=EPS&&
     Math.abs(ca)<=EPS&&Math.abs(cb)<=EPS) {
    const useX=Math.abs(b[0]-a[0])>=Math.abs(b[1]-a[1]);
    const axis=useX?0:1;
    const overlap=Math.min(Math.max(a[axis],b[axis]),Math.max(c[axis],d[axis]))-
      Math.max(Math.min(a[axis],b[axis]),Math.min(c[axis],d[axis]));
    if(overlap>EPS)return "collinear_overlap";
    return overlap>=-EPS?"intersection_or_touch":null;
  }
  if(((ab>EPS&&ad< -EPS)||(ab< -EPS&&ad>EPS))&&
     ((ca>EPS&&cb< -EPS)||(ca< -EPS&&cb>EPS)))return "intersection_or_touch";
  if(on(a,b,c)||on(a,b,d)||on(c,d,a)||on(c,d,b))
    return "intersection_or_touch";
  return null;
}
export function findWallStudyConflicts(entries:ReadonlyArray<WallStudyEntry>):StudyConflict[] {
  const issues:StudyConflict[]=[];
  for(let i=0;i<entries.length;i++)for(let j=i+1;j<entries.length;j++){
    const x=entries[i].command,y=entries[j].command;
    if(x.levelId!==y.levelId)continue;
    const type=conflictKind(x.startPt,x.endPt,y.startPt,y.endPt);
    if(type)issues.push({
      first:x.proposalId,second:y.proposalId,levelId:x.levelId,type,
    });
  }
  return issues;
}
export function summarizeWallBatch(scene:SceneManifest,batch:WallStudyBatch):WallBatchReport {
  assertScope(scene,batch);
  const levels=[...new Set(batch.entries.map(e=>e.command.levelId))].sort();
  const geometryConflicts=findWallStudyConflicts(batch.entries);
  const coordinationHolds=[...new Set(batch.entries.flatMap(
    e=>e.preview.package.coordination_required,
  ))].sort();
  return {
    sourceKey:batch.sourceKey,
    wallCount:batch.entries.length,
    levels:levels.map(levelId=>({
      levelId,wallCount:batch.entries.filter(e=>e.command.levelId===levelId).length,
    })),
    tradeTotals:group(batch.entries),
    perLevelTotals:levels.map(levelId=>({
      levelId,totals:group(batch.entries.filter(e=>e.command.levelId===levelId)),
    })),
    coordinationHolds,geometryConflicts,
    requiresCoordination:coordinationHolds.length>0||geometryConflicts.length>0,
    reviewOnly:true,persisted:false,commerciallyApproved:false,quoteReady:false,
  };
}
export function compareWallBatches(
  scene:SceneManifest,before:WallStudyBatch,after:WallStudyBatch,
):StudyQuantity[] {
  assertScope(scene,before);
  assertScope(scene,after);
  // Signed DELTA for changes. Removed proposals subtract, changed proposals
  // replace; never add both revisions into the current review subtotal.
  const prior=new Map(group(before.entries).map(q=>[
    JSON.stringify([q.trade,q.element,q.description,q.specificationId,q.unit]),q,
  ]));
  const now=new Map(group(after.entries).map(q=>[
    JSON.stringify([q.trade,q.element,q.description,q.specificationId,q.unit]),q,
  ]));
  const delta:StudyQuantity[]=[];
  for(const key of [...new Set([...prior.keys(),...now.keys()])].sort()){
    const a=prior.get(key),b=now.get(key);
    const change=Math.round(((b?.value??0)-(a?.value??0))*1e6)/1e6;
    if(change!==0)delta.push({...b??a!,value:change,
      wallCount:(b?.wallCount??0)-(a?.wallCount??0)});
  }
  return delta;
}
export function exportWallBatchReview(scene:SceneManifest,batch:WallStudyBatch):string {
  const report=summarizeWallBatch(scene,batch);
  // Explicitly export a summary, NOT replayable authority, source geometry
  // receipts, commercial rates or a transaction payload.
  const payload={schema:"planreader-vr-wall-review-v1",
    reviewOnly:true,notAnApprovedQuantity:true,
    sourceKey:report.sourceKey,
    wallCount:report.wallCount,
    levels:report.levels,tradeTotals:report.tradeTotals,
    perLevelTotals:report.perLevelTotals,
    coordinationHolds:report.coordinationHolds,
    geometryConflicts:report.geometryConflicts,
  };
  const json=JSON.stringify(payload,null,2);
  if(json.length>256*1024)throw Error("Review summary exceeds export limit");
  return json;
}
