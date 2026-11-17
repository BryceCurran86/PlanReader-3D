import test from "node:test";
import assert from "node:assert/strict";
import {
  freshWallBatch,wallBatchSourceKey,currentWallBatch,addOrReplaceWallStudy,
  removeWallStudy,undoWallBatch,redoWallBatch,findWallStudyConflicts,
  summarizeWallBatch,compareWallBatches,exportWallBatchReview,MAX_BATCH_WALLS,
} from "../src/wallBatchStudy.ts";

const scene={
  scope:{
    workspaceId:"work-1",projectId:"proj-1",documentId:"doc-1",
    revisionId:"rev-1",snapshotId:"snapshot-1",
    sourceSha256:"a".repeat(64),modelRevision:3,
  },
  objects:[],
};
const make=(id,start,end,level="ground",value=2,holds=["MEP_design_required"])=>{
  const command={
    workspaceId:scene.scope.workspaceId,projectId:scene.scope.projectId,
    documentId:scene.scope.documentId,revisionId:scene.scope.revisionId,
    snapshotId:scene.scope.snapshotId,sourceSha256:scene.scope.sourceSha256,
    baseModelRevision:scene.scope.modelRevision,
    proposalId:id,levelId:level,startPt:start,endPt:end,heightM:2.7,
    openings:[],assemblyProfileId:"assembly-a",
  };
  const preview={
    accepted:true,reviewOnly:true,persisted:false,
    commercialPublicationAllowed:false,sourceGeometryAltered:false,
    workspaceId:scene.scope.workspaceId,proposalId:id,
    baseModelRevision:scene.scope.modelRevision,assemblyProfileId:"assembly-a",
    package:{
      proposal_id:id,revision_scope_key:"b".repeat(64),
      wall_length_m:Math.round(Math.hypot(end[0]-start[0],end[1]-start[1])*1e6)/1e6,
      wall_height_m:2.7,can_publish_commercial:false,
      original_source_modified:false,
      quantities:[{
        line_id:"c".repeat(32),trade:"plastering",
        element:"Wall plasterboard lining",description:"13mm board · left",
        value,unit:"m²",formula:"source-hosted proposed geometry",
        status:"review_only",host_proposal_id:id,specification_id:"assembly-a",
      }],
      coordination_required:holds,
    },
  };
  return {command,preview};
};
const add=(batch,entry)=>addOrReplaceWallStudy(scene,batch,entry.command,entry.preview);
test("1 isolated original-source drawing and model revision",()=>{
  assert.equal(freshWallBatch(scene).entries.length,0);
  const previous=freshWallBatch(scene);
  const next={...scene,scope:{...scene.scope,sourceSha256:"d".repeat(64)}};
  assert.notEqual(wallBatchSourceKey(scene),wallBatchSourceKey(next));
  assert.equal(currentWallBatch(next,previous).entries.length,0);
  assert.throws(()=>addOrReplaceWallStudy(next,previous,...Object.values(make("a",[0,0],[1,0]))));
});
test("2 aggregate different walls without double-counting edited wall",()=>{
  let a=freshWallBatch(scene);
  a=add(a,make("one",[0,0],[2,0],"ground",4));
  a=add(a,make("two",[0,2],[2,2],"ground",3));
  assert.equal(summarizeWallBatch(scene,a).tradeTotals[0].value,7);
  a=add(a,make("one",[0,0],[4,0],"ground",8));
  assert.equal(a.entries.length,2);
  assert.equal(summarizeWallBatch(scene,a).tradeTotals[0].value,11);
  assert.equal(a.past.length,3);
});
test("3 removing one proposal subtracts its whole dependent package",()=>{
  let a=freshWallBatch(scene);
  a=add(a,make("one",[0,0],[2,0],"ground",4));
  a=add(a,make("two",[0,2],[2,2],"ground",3));
  const b=removeWallStudy(scene,a,"one");
  assert.equal(summarizeWallBatch(scene,b).tradeTotals[0].value,3);
  assert.equal(removeWallStudy(scene,b,"unknown"),b);
});
test("4 undo and 5 redo track proposal replacement and removal",()=>{
  let b=freshWallBatch(scene);
  b=add(b,make("one",[0,0],[2,0],"ground",4));
  b=add(b,make("two",[0,2],[2,2],"ground",3));
  const afterUndo=undoWallBatch(b);
  assert.equal(afterUndo.entries.length,1);
  assert.equal(redoWallBatch(afterUndo).entries.length,2);
  assert.equal(redoWallBatch(b),b);
});
test("6 group typed trade quantities, never mix units or source specs",()=>{
  let a=add(freshWallBatch(scene),make("one",[0,0],[2,0],"ground",4));
  const two=make("two",[0,2],[2,2],"ground",3);
  two.preview.package.quantities[0].unit="lm";
  a=add(a,two);
  assert.equal(summarizeWallBatch(scene,a).tradeTotals.length,2);
  assert.deepEqual(summarizeWallBatch(scene,a).tradeTotals.map(x=>x.unit),["lm","m²"]);
});
test("7 segregate floor levels and count per level",()=>{
  let b=add(freshWallBatch(scene),make("one",[0,0],[2,0],"ground",4));
  b=add(b,make("two",[0,0],[2,0],"upper",3));
  const report=summarizeWallBatch(scene,b);
  assert.deepEqual(report.levels.map(x=>x.levelId),["ground","upper"]);
  assert.deepEqual(report.perLevelTotals.map(x=>x.totals[0].value),[4,3]);
  assert.equal(report.geometryConflicts.length,0);
});
test("8 source-level crossing, overlap and same endpoint require coordination",()=>{
  let b=add(freshWallBatch(scene),make("one",[0,0],[3,0]));
  b=add(b,make("cross",[1,-1],[1,1]));
  b=add(b,make("overlap",[2,0],[4,0]));
  const found=findWallStudyConflicts(b.entries);
  assert.ok(found.some(x=>x.type==="collinear_overlap"));
  assert.ok(found.some(x=>x.type==="intersection_or_touch"));
  assert.equal(summarizeWallBatch(scene,b).requiresCoordination,true);
});
test("9 signed delta reports replacement and explicit removal not added quantities",()=>{
  const before=add(freshWallBatch(scene),make("one",[0,0],[2,0],"ground",4));
  const after=add(before,make("one",[0,0],[4,0],"ground",8));
  assert.equal(compareWallBatches(scene,before,after)[0].value,4);
  const removed=removeWallStudy(scene,after,"one");
  assert.equal(compareWallBatches(scene,after,removed)[0].value,-8);
});
test("10 merged coordination holds remain review-only and never priced",()=>{
  let b=add(freshWallBatch(scene),make("one",[0,0],[2,0],"ground",4,["bracing_design_required"]));
  b=add(b,make("two",[0,2],[2,2],"ground",3,["bracing_design_required","electrical_review"]));
  const report=summarizeWallBatch(scene,b);
  assert.deepEqual(report.coordinationHolds,["bracing_design_required","electrical_review"]);
  assert.equal(report.commerciallyApproved,false);
  assert.equal(report.quoteReady,false);
  assert.equal(report.persisted,false);
});
test("11 bounded queue and rejection of stale or forged server review states",()=>{
  let b=freshWallBatch(scene);
  for(let i=0;i<MAX_BATCH_WALLS;i++)
    b=add(b,make("w"+i,[0,i*2],[1,i*2]));
  assert.throws(()=>add(b,make("overflow",[0,100],[1,100])));
  const forged=make("forged",[0,0],[1,0]);
  forged.preview.commercialPublicationAllowed=true;
  assert.throws(()=>add(freshWallBatch(scene),forged));
});
test("12 export is limited summary without replayable command/rate/quantity authority",()=>{
  const b=add(freshWallBatch(scene),make("one",[0,0],[2,0]));
  const out=JSON.parse(exportWallBatchReview(scene,b));
  assert.equal(out.notAnApprovedQuantity,true);
  assert.equal(out.wallCount,1);
  assert.equal(out.tradeTotals[0].value,2);
  assert.equal("command" in out,false);
  assert.equal("preview" in out,false);
  assert.equal("approved" in out,false);
});
