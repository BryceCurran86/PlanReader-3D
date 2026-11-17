import test from "node:test";
import assert from "node:assert/strict";
import {
  activeReviewNotes, addReviewNote, deleteReviewNote, exportReviewNotes,
  freshReviewNotes, importReviewNotes, reviewNotesSummary, setNoteStatus,
} from "../src/reviewNotes.ts";
function scene(){
  return {
    scope:{workspaceId:"w",projectId:"p",documentId:"d",revisionId:"r",
      snapshotId:"s",sourceSha256:"a".repeat(64),modelRevision:1},
    objects:[{objectId:"W1",objectRevision:"rev1",objectType:"wall",
      source:{sheet:"A101",page:2,originalGeometryRef:"path-5"}},
      {objectId:"W2",objectRevision:"rev2",objectType:"wall"}],
  };
}
test("review annotations stay local and immutable, without changing source",()=>{
  const s=scene(),copy=structuredClone(s),initial=freshReviewNotes(s);
  const next=addReviewNote(initial,s,"W1","Check the elevation on A101","high",()=>"issue-1");
  assert.equal(initial.notes.length,0);
  assert.equal(next.notes.length,1);
  assert.deepEqual(s,copy);
  assert.equal(next.notes[0].status,"open");
  assert.deepEqual(reviewNotesSummary(next,s),{total:1,open:1,reviewed:0,high:1});
  const reviewed=setNoteStatus(next,s,"issue-1","reviewed");
  assert.deepEqual(reviewNotesSummary(reviewed,s),{total:1,open:0,reviewed:1,high:0});
  assert.equal(deleteReviewNote(reviewed,s,"issue-1").notes.length,0);
});
test("unowned objects and unsafe notes are refused",()=>{
  const s=scene(),base=freshReviewNotes(s);
  assert.equal(addReviewNote(base,s,"forged","Source concern","high",()=>"ok"),base);
  assert.equal(addReviewNote(base,s,"W1","short","high",()=>"ok"),base);
  assert.equal(addReviewNote(base,s,"W1","Check source sheet","high",()=>"bad token"),base);
  const once=addReviewNote(base,s,"W1","Check source sheet","normal",()=>"same");
  assert.equal(addReviewNote(once,s,"W1","Check another sheet","normal",()=>"same"),once);
});
test("export/import rejects stale scope, malformed review and authority forgery",()=>{
  const s=scene();
  const notes=addReviewNote(freshReviewNotes(s),s,"W2","Review unresolved enclosure","low",()=>"note-1");
  const json=exportReviewNotes(notes,s);
  assert.deepEqual(importReviewNotes(json,s),notes);
  const stale=structuredClone(s);stale.scope.snapshotId="another";
  assert.deepEqual(activeReviewNotes(notes,stale),[]);
  assert.throws(()=>exportReviewNotes(notes,stale),/stale_review/);
  assert.throws(()=>importReviewNotes(json,stale),/scope_or_schema/);
  const injected=JSON.parse(json);injected.commercialAuthority=true;
  assert.throws(()=>importReviewNotes(JSON.stringify(injected),s),/scope_or_schema/);
  const wrong=JSON.parse(json);wrong.notes[0].quantity=500;
  assert.throws(()=>importReviewNotes(JSON.stringify(wrong),s),/invalid_review/);
  const old=JSON.parse(json);old.notes[0].objectRevision="superseded";
  assert.throws(()=>importReviewNotes(JSON.stringify(old),s),/invalid_review/);
  assert.throws(()=>importReviewNotes("x".repeat(256*1024+1),s),/too_large/);
});
test("duplicate review-note identity and size caps deny import",()=>{
  const s=scene(),a=addReviewNote(freshReviewNotes(s),s,"W1","Source dimension needed","normal",()=>"n1");
  const dup=JSON.parse(exportReviewNotes(a,s));
  dup.notes.push({...dup.notes[0]});
  assert.throws(()=>importReviewNotes(JSON.stringify(dup),s),/invalid_review/);
});
