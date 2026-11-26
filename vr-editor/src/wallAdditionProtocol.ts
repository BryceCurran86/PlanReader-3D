/** Typed, source-scoped wall creation STUDY protocol. Not a wall-create API.
 * Cross-trade quantities come only from a trusted authenticated server project
 * assembly profile and the source-verified service routing provider.
 */
import type { SceneManifest } from "./types.ts";
import { scopeKey } from "./reviewDraft.ts";
import { validWallLength } from "./buildPlacement.ts";

export interface WallAdditionSketch {
  scopeKey:string;
  proposalId:string;
  levelId:string;
  start:[number,number];
  end:[number,number];
  heightM:number;
}
export type DoorHardwareFinish="chrome"|"matte-black"|"brushed-brass"|"brushed-nickel";
export type DoorMechanism="swing"|"sliding"|"garage";
export interface WallAdditionOpening {
  openingId:string;
  offsetM:number;
  widthM:number;
  heightM:number;
  sillHeightM:number;
  openingKind:"door"|"window"|"passage";
  /** Local walkthrough visual only; omitted from server quantity commands. */
  doorMechanism?:DoorMechanism;
  doorHardware?:DoorHardwareFinish;
}
export interface WallAdditionCommand {
  workspaceId:string;
  projectId:string;
  documentId:string;
  revisionId:string;
  snapshotId:string;
  sourceSha256:string;
  baseModelRevision:number;
  proposalId:string;
  levelId:string;
  startPt:[number,number];
  endPt:[number,number];
  heightM:number;
  openings:WallAdditionOpening[];
  assemblyProfileId:string;
}
export interface AssemblyQuantity{
  line_id:string;
  trade:string;
  element:string;
  description:string;
  value:number;
  unit:string;
  formula:string;
  status:"review_only";
  host_proposal_id:string;
  specification_id:string;
}
export interface WallAssemblyPreview {
  accepted:true;
  reviewOnly:true;
  persisted:false;
  commercialPublicationAllowed:false;
  sourceGeometryAltered:false;
  workspaceId:string;
  proposalId:string;
  baseModelRevision:number;
  assemblyProfileId:string;
  package:{
    proposal_id:string;
    revision_scope_key:string;
    wall_length_m:number;
    wall_height_m:number;
    quantities:AssemblyQuantity[];
    coordination_required:string[];
    can_publish_commercial:false;
    original_source_modified:false;
  };
}
const LINE=/^[0-9a-f]{32}$/i;
const HASH=/^[0-9a-f]{64}$/i;
const ID=/^[A-Za-z0-9_.:-]{1,128}$/;
const MAX=10000;
function point(value:unknown):value is [number,number]{
  return Array.isArray(value)&&value.length===2&&
    value.every(x=>typeof x==="number"&&Number.isFinite(x)&&Math.abs(x)<=MAX);
}
export function validateAdditionSketch(
  manifest:SceneManifest,
  input:Omit<WallAdditionSketch,"scopeKey">,
):WallAdditionSketch {
  if(!ID.test(input.proposalId)||
     typeof input.levelId!=="string"||!input.levelId.trim()||
     input.levelId.length>128||
     !point(input.start)||!point(input.end)||!Number.isFinite(input.heightM)||
     input.heightM<=0||input.heightM>20){
    throw new Error("A valid named wall, level, endpoints and height are required");
  }
  const distance=Math.hypot(
    input.end[0]-input.start[0],input.end[1]-input.start[1]);
  if(!validWallLength(distance))throw new Error("New wall must measure 50mm–200m");
  return {...input,scopeKey:scopeKey(manifest)};
}
export function makeWallAdditionCommand(
  manifest:SceneManifest,sketch:WallAdditionSketch,
  assemblyProfileId:string,openings:WallAdditionOpening[] = [],
):WallAdditionCommand{
  if(sketch.scopeKey!==scopeKey(manifest))
    throw new Error("Stale new-wall draft from another source revision");
  validateAdditionSketch(manifest,sketch);
  if(!ID.test(assemblyProfileId))
    throw new Error("A real project assembly profile ID is required");
  if(openings.length>100)throw new Error("Too many proposed wall openings");
  for(const o of openings){
    if(!ID.test(o.openingId)||
      !["door","window","passage"].includes(o.openingKind)||
      ![o.offsetM,o.widthM,o.heightM,o.sillHeightM].every(Number.isFinite)||
      o.offsetM<0||o.sillHeightM<0||o.widthM<=0||o.heightM<=0)
      throw new Error("Opening type or size not supported");
  }
  const s=manifest.scope;
  return {
    workspaceId:s.workspaceId,projectId:s.projectId,documentId:s.documentId,
    revisionId:s.revisionId,snapshotId:s.snapshotId,
    sourceSha256:s.sourceSha256,baseModelRevision:s.modelRevision,
    proposalId:sketch.proposalId,levelId:sketch.levelId,
    startPt:[...sketch.start],endPt:[...sketch.end],heightM:sketch.heightM,
    openings:openings.map(({doorMechanism: _local,doorHardware: _hardware,...o})=>o),assemblyProfileId,
  };
}
function obj(raw:unknown):Record<string,unknown>{
  if(!raw||typeof raw!=="object"||Array.isArray(raw))
    throw new Error("Malformed wall assembly response");
  return raw as Record<string,unknown>;
}
export function verifyWallAssemblyPreview(
  raw:unknown,scene:SceneManifest,
  command:WallAdditionCommand,
):WallAssemblyPreview{
  const r=obj(raw), p=obj(r.package);
  if(r.accepted!==true||r.reviewOnly!==true||r.persisted!==false||
     r.commercialPublicationAllowed!==false||r.sourceGeometryAltered!==false||
     r.workspaceId!==scene.scope.workspaceId||
     r.proposalId!==command.proposalId||
     r.baseModelRevision!==command.baseModelRevision||
     r.assemblyProfileId!==command.assemblyProfileId||
     p.proposal_id!==command.proposalId||
     p.can_publish_commercial!==false||
     p.original_source_modified!==false||
     typeof p.revision_scope_key!=="string"||!HASH.test(p.revision_scope_key)||
     typeof p.wall_length_m!=="number"||!Number.isFinite(p.wall_length_m)||
     typeof p.wall_height_m!=="number"||p.wall_height_m!==command.heightM||
     !Array.isArray(p.quantities)||p.quantities.length>1000||
     !Array.isArray(p.coordination_required)||p.coordination_required.length>1000||
     !p.coordination_required.every(x=>typeof x==="string"&&!!x))
    throw new Error("Source/study scope, review-only state or trade coverage mismatch");
  const expectedLength=Math.hypot(
    command.endPt[0]-command.startPt[0],
    command.endPt[1]-command.startPt[1]);
  if(Math.abs(p.wall_length_m-expectedLength)>0.00001)
    throw new Error("Wall assembly length differs from original proposal geometry");
  const ids=new Set<string>();
  for(const item of p.quantities){
    const q=obj(item);
    if(typeof q.line_id!=="string"||!LINE.test(q.line_id)||
       ids.has(q.line_id)||typeof q.trade!=="string"||
       !["carpentry","plastering","electrical","plumbing"].includes(q.trade)||
       typeof q.element!=="string"||!q.element||
       typeof q.description!=="string"||!q.description||
       typeof q.value!=="number"||!Number.isFinite(q.value)||q.value<0||
       !["lm","m²","No."].includes(String(q.unit))||
       typeof q.formula!=="string"||!q.formula||
       q.status!=="review_only"||q.host_proposal_id!==command.proposalId||
       typeof q.specification_id!=="string"||!q.specification_id)
      throw new Error("Unverified, duplicate or billable wall trade line");
    ids.add(q.line_id);
  }
  return raw as WallAssemblyPreview;
}


export interface WallConstructionImpactPreview {
  accepted:true;
  reviewOnly:true;
  persisted:false;
  wallCreated:false;
  relatedPagesRevised:false;
  commercialPublicationAllowed:false;
  quoteReady:false;
  proposalId:string;
  revisionScopeKey:string;
  currency:string|null;
  rateBookRevision:string|null;
  pricedSubtotalOnly:string;
  pricedComplete:boolean;
  relatedPagesVerified:boolean;
  affectedPages:{pageIndex:number;sheetId:string;registrationEvidenceId:string}[];
  unpricedLines:{lineId:string;reason:string}[];
  constructionHolds:string[];
  impactReceiptSha256:string;
}

/** Verify the linked provisional costing/related-sheet receipt before UI display. */
export function verifyWallConstructionImpact(
  raw:unknown, preview:WallAssemblyPreview,
):WallConstructionImpactPreview | null {
  const envelope=obj(raw);
  if(envelope.impactPreview===undefined)return null; // older preview-only hosts
  const impact=obj(envelope.impactPreview);
  if(impact.accepted!==true||impact.reviewOnly!==true||
     impact.persisted!==false||impact.wallCreated!==false||
     impact.relatedPagesRevised!==false||impact.commercialPublicationAllowed!==false||
     impact.quoteReady!==false||impact.proposalId!==preview.proposalId||
     impact.revisionScopeKey!==preview.package.revision_scope_key||
     typeof impact.pricedSubtotalOnly!=="string"||
     !/^(0|[1-9][0-9]*)\.[0-9]{2}$/.test(impact.pricedSubtotalOnly)||
     !["boolean"].includes(typeof impact.pricedComplete)||
     typeof impact.relatedPagesVerified!=="boolean"||
     typeof impact.impactReceiptSha256!=="string"||!HASH.test(impact.impactReceiptSha256)||
     !Array.isArray(impact.affectedPages)||impact.affectedPages.length>1000||
     !Array.isArray(impact.unpricedLines)||impact.unpricedLines.length>1000||
     !Array.isArray(impact.constructionHolds)||impact.constructionHolds.length>1000||
     !impact.constructionHolds.every(x=>typeof x==="string"&&x.length>0)||
     !(impact.currency===null||typeof impact.currency==="string"&&/^[A-Z]{3}$/.test(impact.currency))||
     !(impact.rateBookRevision===null||typeof impact.rateBookRevision==="string"&&impact.rateBookRevision.length<=128)){
    throw new Error("Unverified added-wall pricing or drawing coordination receipt");
  }
  const pages=new Set<number>();
  for(const item of impact.affectedPages){
    const p=obj(item);
    if(typeof p.pageIndex!=="number"||!Number.isSafeInteger(p.pageIndex)||p.pageIndex<0||
       typeof p.sheetId!=="string"||!ID.test(p.sheetId)||
       typeof p.registrationEvidenceId!=="string"||!ID.test(p.registrationEvidenceId)||
       pages.has(Number(p.pageIndex)))
      throw new Error("Duplicate or malformed registered drawing page");
    pages.add(Number(p.pageIndex));
  }
  const known=new Set(preview.package.quantities.map(q=>q.line_id));
  const unpriced=new Set<string>();
  for(const item of impact.unpricedLines){
    const m=obj(item);
    if(typeof m.lineId!=="string"||!known.has(m.lineId)||
       unpriced.has(m.lineId)||typeof m.reason!=="string"||!m.reason)
      throw new Error("Malformed unpriced construction scope line");
    unpriced.add(m.lineId);
  }
  if(impact.pricedComplete===true&&
     (unpriced.size>0||!impact.currency||!impact.rateBookRevision)||
     impact.relatedPagesVerified===true&&pages.size===0)
    throw new Error("Unsupported complete construction preview claim");
  return impact as unknown as WallConstructionImpactPreview;
}


export interface SavedNewWallRevision {
  revisionId:string;
  revisionNumber:number;
  canonicalWallId:string;
  modelRevision:number;
  pdfSha256:string;
  pagesRevised:{pageIndex:number;sheetId:string;pageKind:string;registrationEvidenceId:string;newWallVectorDrawn:true;approved:false}[];
  persisted:true;
  workingDesignOnly:true;
  commercialPublicationAllowed:false;
  idempotentReplay:boolean;
  downloadPath:string;
}
export function verifySavedNewWallRevision(
  raw:unknown, scene:SceneManifest, command:WallAdditionCommand,
):SavedNewWallRevision{
  const p=obj(raw);
  if(typeof p.revisionId!=="string"||!/^[0-9a-f]{40}$/.test(p.revisionId)||
     typeof p.revisionNumber!=="number"||!Number.isSafeInteger(p.revisionNumber)||
     p.revisionNumber<1||
     typeof p.canonicalWallId!=="string"||!/^vr-wall:[0-9a-f]{32}$/.test(p.canonicalWallId)||
     p.modelRevision!==scene.scope.modelRevision+1||
     typeof p.pdfSha256!=="string"||!HASH.test(p.pdfSha256)||
     p.persisted!==true||p.workingDesignOnly!==true||
     p.commercialPublicationAllowed!==false||
     typeof p.idempotentReplay!=="boolean"||
     !Array.isArray(p.pagesRevised)||p.pagesRevised.length<1||
     p.pagesRevised.length>700||
     p.downloadPath!==(
       "/api/editor/workspaces/"+scene.scope.workspaceId+
       "/walls/revisions/"+p.revisionId+"/pdf"
     ))throw new Error("Wall creation save receipt invalid or source-stale");
  const pages=new Set<number>();
  for(const item of p.pagesRevised){
    const page=obj(item);
    if(typeof page.pageIndex!=="number"||!Number.isSafeInteger(page.pageIndex)||
       page.pageIndex<0||pages.has(page.pageIndex)||
       typeof page.sheetId!=="string"||!ID.test(page.sheetId)||
       typeof page.pageKind!=="string"||!ID.test(page.pageKind)||
       typeof page.registrationEvidenceId!=="string"||
       !ID.test(page.registrationEvidenceId)||
       page.newWallVectorDrawn!==true||page.approved!==false)
      throw new Error("Saved wall revised-sheet manifest malformed");
    pages.add(page.pageIndex);
  }
  if(!ID.test(command.proposalId))throw new Error("Unsaved proposal identity");
  return raw as SavedNewWallRevision;
}
