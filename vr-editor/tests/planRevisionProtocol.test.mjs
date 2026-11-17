import test from "node:test";
import assert from "node:assert/strict";
import {
  verifySavedPlanRevision,verifyPlanRevisionHistory,
} from "../src/planRevisionProtocol.ts";
function scene() {
 return {scope:{
  workspaceId:"w1",projectId:"p1",documentId:"d1",revisionId:"r1",
  snapshotId:"snap1",sourceSha256:"a".repeat(64),modelRevision:0,
 }};
}
function saved(number=1){
 const revisionId=String(number).repeat(40);
 return {
  saved:true,revisionId,revisionNumber:number,
  revisionLabel:`PR-R${String(number).padStart(4,"0")}`,
  parentRevisionId:number===1?null:String(number-1).repeat(40),
  previousModelRevision:number-1,updatedModelRevision:number,
  updatedPdfSha256:"b".repeat(64),
  pagesRevised:[
   {pageIndex:0,pageLabel:"1",sheet:"A101",relationship:"origin",
    originalGeometryRef:"path-1",evidenceIds:["original-source"],
    geometryRedrawn:false,requiresDrawingCoordination:true},
   {pageIndex:1,pageLabel:"2",sheet:"A201",relationship:"cross_sheet",
    originalGeometryRef:"target-4",evidenceIds:["cross-verified","callout","target"],
    geometryRedrawn:false,requiresDrawingCoordination:true},
  ],
  requiresApproval:true,commercialPublicationAllowed:false,
  geometryRedrawn:false,reviewRevisionOnly:true,
  downloadPath:`/api/editor/workspaces/w1/revisions/${revisionId}/pdf`,
 };
}
test("save response proves every affected page and current model revision",()=>{
 const r=verifySavedPlanRevision(saved(),scene());
 assert.equal(r.revisionLabel,"PR-R0001");
 assert.deepEqual(r.pagesRevised.map(p=>p.sheet),["A101","A201"]);
 assert.equal(r.commercialPublicationAllowed,false);
});
test("cross-tenant, stale, missing, duplicate and unproven page links fail",()=>{
 const tests=[
   {...saved(),downloadPath:"https://example.com/pdf"},
   {...saved(),previousModelRevision:5,updatedModelRevision:6},
   {...saved(),pagesRevised:[saved().pagesRevised[1]]},
   {...saved(),pagesRevised:[saved().pagesRevised[0],saved().pagesRevised[0]]},
   {...saved(),pagesRevised:[{...saved().pagesRevised[0],geometryRedrawn:true},
                             saved().pagesRevised[1]]},
   {...saved(),pagesRevised:[{...saved().pagesRevised[0],requiresDrawingCoordination:false},
                             saved().pagesRevised[1]]},
   {...saved(),requiresApproval:false},
   {...saved(),commercialPublicationAllowed:true},
   {...saved(),reviewRevisionOnly:false},
   {...saved(),revisionLabel:"PR-R9999"},
 ];
 for(const candidate of tests)
   assert.throws(()=>verifySavedPlanRevision(candidate,scene()));
});
test("history validates every old immutable revision, order and exact private paths",()=>{
 const p=verifyPlanRevisionHistory(
   {readOnly:true,revisions:[saved(2),saved(1)]},scene());
 assert.equal(p.length,2);
 assert.equal(p[0].revisionNumber,2);
 assert.throws(()=>verifyPlanRevisionHistory(
   {readOnly:true,revisions:[saved(1),saved(2)]},scene()),/non-descending/);
 assert.throws(()=>verifyPlanRevisionHistory(
   {readOnly:true,revisions:[saved(1),saved(1)]},scene()),/Duplicate/);
 assert.throws(()=>verifyPlanRevisionHistory(
   {readOnly:false,revisions:[]},scene()),/Malformed/);
});
test("review-only revision is never a publishable quote or redraw",()=>{
 const q=saved();
 for(const flag of ["commercialPublicationAllowed","geometryRedrawn"]){
  const bad={...q,[flag]:true};
  assert.throws(()=>verifySavedPlanRevision(bad,scene()));
 }
 const tampered={...q,pagesRevised:q.pagesRevised.map(p=>({...p}))};
 tampered.pagesRevised[1].relationship="other";
 assert.throws(()=>verifySavedPlanRevision(tampered,scene()),/lineage/);
});
