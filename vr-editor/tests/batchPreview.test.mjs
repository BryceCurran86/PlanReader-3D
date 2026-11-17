import test from "node:test";
import assert from "node:assert/strict";
import { makeHeightBatch, eligibleHeightTargets } from "../src/batchRequest.ts";
import { verifyBatchPreview } from "../src/batchProtocol.ts";
import { applyDraft, freshDrafts } from "../src/reviewDraft.ts";

function scene() {
  return {
    scope: {
      workspaceId:"w1", projectId:"project", documentId:"pdf",
      revisionId:"r1", snapshotId:"s1", sourceSha256:"a".repeat(64),
      modelRevision:1,
    },
    objects:[{
      objectId:"wall-1", objectType:"wall", levelId:"ground",
      objectRevision:"rev-1",canonicalObjectId:"canonical-1",
      geometry:{kind:"wallFace",start:[0,0],end:[4,0],heightM:2.4},
    },{
      objectId:"wall-2", objectType:"wall", levelId:"ground",
      objectRevision:"rev-2",canonicalObjectId:null,
      geometry:{kind:"wallFace",start:[0,0],end:[2,0],heightM:2.4},
    }],
  };
}
function prep() {
  const s=scene();
  let drafts=applyDraft(freshDrafts(s),s,"wall-1",{heightM:2.8});
  drafts=applyDraft(drafts,s,"wall-2",{heightM:3.2});
  return {s,drafts};
}
function response(cmd) {
  return {
    accepted:true,validationState:"valid_batch_preview_only",
    persisted:false,requiresApproval:true,commercialPublicationAllowed:false,
    rateEstimateAvailable:false,simulationMode:"independent_same_base_not_cumulative",
    blockingReasons:[],batchReceiptSha256:"b".repeat(64),
    commandPreviews:[{
      accepted:true,validationState:"valid_preview_only",
      commandId:cmd.commandId,idempotencyKey:cmd.idempotencyKey,
      targetObjectId:cmd.targetObjectId,
      previousObjectRevision:cmd.targetRevisionHash,
      previewObjectRevision:"new-r",requiresApproval:true,persisted:false,
      commercialPublicationAllowed:false,blockingReasons:[],
      quantityImpacts:[{target:"wall_gross_area",status:"recalculated",
        oldValue:9.6,proposedValue:11.2,unit:"m²",reason:null}],
    }],
  };
}

test("only canonical and revision-bound height proposals are sent",()=>{
  const {s,drafts}=prep();
  assert.deepEqual(eligibleHeightTargets(s,drafts),["wall-1"]);
  let n=0;const request=makeHeightBatch(s,drafts,"Checked source elevation",
    ()=>"token"+(++n));
  assert.equal(request.commands.length,1);
  const c=request.commands[0];
  assert.equal(c.payload.newValue,2.8);
  assert.equal(c.targetCanonicalId,"canonical-1");
  assert.equal(c.sourceSha256,"a".repeat(64));
  assert.equal(c.snapshotId,"s1");
  assert.equal(c.reason,"Checked source elevation");
});
test("stale scene, unsafe reason, duplicate ID and too many targets block",()=>{
  const {s,drafts}=prep();
  assert.throws(()=>makeHeightBatch(s,drafts,"bad",()=>crypto.randomUUID()),/reason/);
  assert.throws(()=>makeHeightBatch(s,drafts,"Source verified",()=>"same"),/unique/);
  const changed=structuredClone(s);changed.scope.snapshotId="new";
  assert.throws(()=>makeHeightBatch(changed,drafts,"Source verified",()=>crypto.randomUUID()),/Choose/);
  const many=structuredClone(s);for(let i=0;i<21;i++)
    many.objects.push({...many.objects[0],objectId:"X"+i,
      objectRevision:"r"+i,canonicalObjectId:"c"+i});
  let state=freshDrafts(many);for(let i=0;i<21;i++)
    state=applyDraft(state,many,"X"+i,{heightM:3});
  assert.throws(()=>makeHeightBatch(many,state,"Source verified",()=>crypto.randomUUID()),/1–20/);
});
test("batch result enforces no price, no persistence and exact command echo",()=>{
  const {s,drafts}=prep();let n=0;
  const request=makeHeightBatch(s,drafts,"Checked source elevation",()=>String(++n));
  const c=request.commands[0],r=response(c);
  assert.equal(verifyBatchPreview(r,request).status,"review_only");
  for(const [key,value] of [["persisted",true],["requiresApproval",false],
    ["commercialPublicationAllowed",true],["rateEstimateAvailable",true],
    ["simulationMode","cumulative"],["batchReceiptSha256","wrong"]]){
    const bad={...r,[key]:value};
    assert.throws(()=>verifyBatchPreview(bad,request),/Batch/);
  }
  const altered=structuredClone(r);
  altered.commandPreviews[0].idempotencyKey="wrong";
  assert.throws(()=>verifyBatchPreview(altered,request),/idempotency/);
});
