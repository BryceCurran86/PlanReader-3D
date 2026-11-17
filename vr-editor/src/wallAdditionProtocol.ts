/** Typed, source-scoped wall creation STUDY protocol. Not a wall-create API.
 * Cross-trade quantities come only from a trusted authenticated server project
 * assembly profile and the source-verified service routing provider.
 */
import type { SceneManifest } from "./types.ts";
import { scopeKey } from "./reviewDraft.ts";

export interface WallAdditionSketch {
  scopeKey:string;
  proposalId:string;
  levelId:string;
  start:[number,number];
  end:[number,number];
  heightM:number;
}
export interface WallAdditionOpening {
  openingId:string;
  offsetM:number;
  widthM:number;
  heightM:number;
  sillHeightM:number;
  openingKind:"door"|"window"|"passage";
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
  if(distance<0.05||distance>200)throw new Error("New wall must measure 50mm–200m");
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
    openings:openings.map(o=>({...o})),assemblyProfileId,
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
