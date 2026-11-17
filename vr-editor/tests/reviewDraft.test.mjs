import test from "node:test";
import assert from "node:assert/strict";
import {
  applyDraft, applyLevelSwatch, diffSummary, draftHeightSuggestion, exportDrafts, freshDrafts,
  importDrafts, redoDraft, resetDraft, safeDrafts, scopeKey, undoDraft,
} from "../src/reviewDraft.ts";

function scene() {
  const wall = (objectId, levelId, kind="wallFace") => ({
    objectId, objectRevision: "rev-" + objectId, objectType: "wall",
    levelId, geometry: kind === "wallFace"
      ? {kind, start:[0,0], end:[3,0], heightM: 2.4}
      : {kind, start:[0,0], end:[3,0]},
  });
  return {
    scope: {
      workspaceId: "w", projectId: "p", documentId: "doc", revisionId: "r",
      snapshotId: "snapshot", sourceSha256: "a".repeat(64), modelRevision: 1,
    },
    objects: [wall("W1","ground"), wall("W2","ground"), wall("W3","first","wallLine")],
  };
}

test("source scoped immutable per-wall visual drafts never mutate model", () => {
  const model = scene(), frozen = structuredClone(model);
  const initial = freshDrafts(model);
  const first = applyDraft(initial,model,"W1",{swatch:"sage"});
  const second = applyDraft(first,model,"W2",{swatch:"clay",heightM:2.8});
  assert.equal(initial.drafts.length,0);
  assert.equal(second.drafts.length,2);
  assert.equal(second.drafts[1].heightM,2.8);
  assert.deepEqual(model,frozen);
});

test("scene snapshot and wall revision invalidates drafts", () => {
  const m=scene();const a=applyDraft(freshDrafts(m),m,"W1",{swatch:"slate"});
  const modified=structuredClone(m);modified.scope.snapshotId="changed";
  assert.deepEqual(safeDrafts(a,modified),[]);
  assert.equal(applyDraft(a,modified,"W1",{swatch:"clay"}).drafts.length,0);
  const newRevision=structuredClone(m);newRevision.objects[0].objectRevision="new";
  assert.deepEqual(safeDrafts(a,newRevision),[]);
  assert.notEqual(scopeKey(m),scopeKey(modified));
});

test("height must be finite and bounded; unknown-height wall cannot gain mass", () => {
  const m=scene(),s=freshDrafts(m);
  for(const bad of [0,-1,21,NaN,Infinity,"3",null]) {
    // null is a reset, not an invalid height
    const result=applyDraft(s,m,"W1",{heightM:bad});
    assert.equal(result.drafts.length,0);
  }
  assert.equal(applyDraft(s,m,"W3",{heightM:2.6}).drafts.length,0);
  assert.equal(applyDraft(s,m,"W1",{swatch:"unknown"}).drafts.length,0);
  assert.equal(applyDraft(s,m,"other",{swatch:"sage"}).drafts.length,0);
});

test("explicit level-wide swatch is one undo step and excludes source lines", () => {
  const m=scene(),a=freshDrafts(m);
  assert.equal(applyLevelSwatch(a,m,"all","sage"),a);
  const b=applyLevelSwatch(a,m,"ground","sage");
  assert.equal(b.drafts.length,2);
  assert.equal(b.past.length,1);
  assert.equal(undoDraft(b).drafts.length,0);
  assert.deepEqual(redoDraft(undoDraft(b)).drafts,b.drafts);
  assert.equal(resetDraft(b).drafts.length,0);
});

test("undo/redo is bounded and a fresh edit clears future", () => {
  const m=scene();let s=freshDrafts(m);
  for(let i=0;i<40;i++) s=applyDraft(s,m,"W1",{heightM:1+i/10});
  assert.equal(s.past.length,30);
  const u=undoDraft(s);
  assert.equal(u.future.length,1);
  assert.equal(applyDraft(u,m,"W1",{swatch:"chalk"}).future.length,0);
});

test("local export/import exact scope and strict no-extra-fields validation", () => {
  const m=scene(),a=applyDraft(freshDrafts(m),m,"W1",{swatch:"chalk",heightM:2.9});
  const raw=exportDrafts(a,m),b=importDrafts(raw,m);
  assert.deepEqual(b.drafts,a.drafts);
  assert.deepEqual(b.past,[]);
  assert.ok(diffSummary(b,m)[0].includes("2.40 → 2.90 m"));
  const wrong=structuredClone(m);wrong.scope.sourceSha256="b".repeat(64);
  assert.throws(()=>importDrafts(raw,wrong),/scope_or_schema/);
  assert.throws(()=>exportDrafts(a,wrong),/stale_scene/);
  const injected=JSON.parse(raw);injected.approved=true;
  assert.throws(()=>importDrafts(JSON.stringify(injected),m),/scope_or_schema/);
  const stale=JSON.parse(raw);stale.changes[0].objectRevision="stale";
  assert.throws(()=>importDrafts(JSON.stringify(stale),m),/object_revision/);
  const malicious=JSON.parse(raw);malicious.changes[0].quantity=123;
  assert.throws(()=>importDrafts(JSON.stringify(malicious),m),/invalid_local/);
  assert.throws(()=>importDrafts("x".repeat(256*1024+1),m),/too_large/);
});

test("duplicate imported wall IDs and unowned geometry never allowed", () => {
  const m=scene(),a=applyDraft(freshDrafts(m),m,"W1",{swatch:"clay"});
  const payload=JSON.parse(exportDrafts(a,m));
  payload.changes.push(structuredClone(payload.changes[0]));
  assert.throws(()=>importDrafts(JSON.stringify(payload),m),/invalid_local/);
  payload.changes[1].objectId="W3";payload.changes[1].objectRevision="rev-W3";
  assert.throws(()=>importDrafts(JSON.stringify(payload),m),/object_revision/);
});

test("capacity bound forbids ambiguous mass edits", () => {
  const m=scene();
  for(let i=0;i<501;i++) m.objects.push({
    ...m.objects[0], objectId:"B"+i,objectRevision:"b"+i,levelId:"big",
  });
  const s=freshDrafts(m);
  assert.equal(applyLevelSwatch(s,m,"big","chalk"),s);
});

test("ghost proposal only prefills source-checked preview; no anonymous or unowned identity", () => {
  const m=scene();
  m.objects[0].canonicalObjectId="canonical-wall";
  const draft=applyDraft(freshDrafts(m),m,"W1",{heightM:2.85});
  assert.deepEqual(draftHeightSuggestion(m.objects[0],draft,m),{
    command:"SET_WALL_HEIGHT",value:"2.85",objectRevision:"rev-W1",
  });
  assert.equal(draftHeightSuggestion(m.objects[1],draft,m),null);
  const unowned=structuredClone(m);unowned.objects[0].canonicalObjectId=null;
  assert.equal(draftHeightSuggestion(unowned.objects[0],draft,unowned),null);
  const changed=structuredClone(m);changed.scope.snapshotId="rev2";
  assert.equal(draftHeightSuggestion(changed.objects[0],draft,changed),null);
});
