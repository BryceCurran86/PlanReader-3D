/** Validate private PlanReader working revisions; never accept fake authority. */
import type { SceneManifest } from "./types.ts";
const SHA = /^[0-9a-f]{64}$/;
const REVISION_ID = /^[0-9a-f]{40}$/;
interface RevisedPage {
  pageIndex:number;
  pageLabel:string;
  sheet:string;
  relationship:"origin"|"cross_sheet";
  originalGeometryRef:string;
  evidenceIds:string[];
  geometryRedrawn:false;
  requiresDrawingCoordination:true;
  vectorGeometryOverlayDrawn?:boolean;
  vectorOverlayKind?:"source_verified_plan"|"source_verified_elevation"|null;
}
export interface SavedPlanRevision {
  saved:true;
  revisionId:string;
  revisionNumber:number;
  revisionLabel:string;
  parentRevisionId:string|null;
  previousModelRevision:number;
  updatedModelRevision:number;
  updatedPdfSha256:string;
  pagesRevised:RevisedPage[];
  requiresApproval:true;
  commercialPublicationAllowed:false;
  geometryRedrawn:false;
  reviewRevisionOnly:true;
  sourceVerifiedVectorOverlayComplete?:boolean;
  downloadPath:string;
}
function record(x:unknown):Record<string,unknown> {
  if(!x||typeof x!=="object"||Array.isArray(x))throw Error("Malformed saved plan revision");
  return x as Record<string,unknown>;
}
function sourcePage(input:unknown):RevisedPage {
  const x=record(input);
  if(!Number.isSafeInteger(x.pageIndex)||Number(x.pageIndex)<0 ||
     typeof x.pageLabel!=="string"||!x.pageLabel ||
     typeof x.sheet!=="string"||!x.sheet ||
     !["origin","cross_sheet"].includes(String(x.relationship)) ||
     typeof x.originalGeometryRef!=="string"||!x.originalGeometryRef ||
     !Array.isArray(x.evidenceIds)||x.evidenceIds.length<1||
     !x.evidenceIds.every(item=>typeof item==="string"&&!!item) ||
     x.geometryRedrawn!==false||x.requiresDrawingCoordination!==true ||
     !(x.vectorGeometryOverlayDrawn===undefined ||
       typeof x.vectorGeometryOverlayDrawn==="boolean") ||
     !(x.vectorOverlayKind===undefined || x.vectorOverlayKind===null ||
       x.vectorOverlayKind==="source_verified_plan" ||
       x.vectorOverlayKind==="source_verified_elevation") ||
     (x.vectorGeometryOverlayDrawn===true &&
       !["source_verified_plan","source_verified_elevation"].includes(String(x.vectorOverlayKind))))
    throw Error("Saved plan page lacks original-source review lineage");
  return x as unknown as RevisedPage;
}
export function verifySavedPlanRevision(
  raw:unknown, scene:SceneManifest, historical=false,
):SavedPlanRevision{
  const x=record(raw), scope=scene.scope;
  if(x.saved!==true||x.requiresApproval!==true||
     x.commercialPublicationAllowed!==false||
     x.geometryRedrawn!==false||x.reviewRevisionOnly!==true ||
     typeof x.revisionId!=="string"||!REVISION_ID.test(x.revisionId) ||
     !Number.isSafeInteger(x.revisionNumber)||Number(x.revisionNumber)<1 ||
     typeof x.revisionLabel!=="string"||
     x.revisionLabel!==`PR-R${String(x.revisionNumber).padStart(4,"0")}`||
     !(x.parentRevisionId===null ||
       typeof x.parentRevisionId==="string"&&REVISION_ID.test(x.parentRevisionId)) ||
     !Number.isSafeInteger(x.previousModelRevision) || Number(x.previousModelRevision)<0 ||
     x.updatedModelRevision!==Number(x.previousModelRevision)+1 ||
     (!historical && x.previousModelRevision!==scope.modelRevision) ||
     typeof x.updatedPdfSha256!=="string"||!SHA.test(x.updatedPdfSha256))
    throw Error("Saved revision does not match active model revision or review status");
  const pages = Array.isArray(x.pagesRevised)?x.pagesRevised.map(sourcePage):[];
  if(pages.length<1||pages.length>700||
      pages.filter(p=>p.relationship==="origin").length!==1 ||
      new Set(pages.map(p=>p.pageIndex)).size!==pages.length)
    throw Error("Saved revision lacks complete unique related-page entries");
  if (!(x.sourceVerifiedVectorOverlayComplete===undefined ||
        typeof x.sourceVerifiedVectorOverlayComplete==="boolean") ||
      (x.sourceVerifiedVectorOverlayComplete===true &&
        !pages.every(page=>page.vectorGeometryOverlayDrawn===true)) ||
      (x.sourceVerifiedVectorOverlayComplete===false &&
        pages.every(page=>page.vectorGeometryOverlayDrawn===true)))
    throw Error("Vector overlay coverage and page receipts disagree");
  const expected=`/api/editor/workspaces/${encodeURIComponent(scope.workspaceId)}/revisions/${x.revisionId}/pdf`;
  if(x.downloadPath!==expected)
    throw Error("Saved PDF download is not bound to this workspace");
  return {...x,pagesRevised:pages} as unknown as SavedPlanRevision;
}

export function verifyPlanRevisionHistory(raw:unknown, scene:SceneManifest):SavedPlanRevision[]{
  const payload=record(raw);
  if(payload.readOnly!==true||!Array.isArray(payload.revisions)||
     payload.revisions.length>200)
    throw Error("Malformed authenticated plan revision history");
  const result=payload.revisions.map(x=>verifySavedPlanRevision(x,scene,true));
  const seen=new Set<string>();
  let lastRevision=Number.MAX_SAFE_INTEGER;
  for(const revision of result) {
    if(seen.has(revision.revisionId)||revision.revisionNumber>=lastRevision)
      throw Error("Duplicate or non-descending plan revision history");
    seen.add(revision.revisionId);
    lastRevision=revision.revisionNumber;
  }
  return result;
}
