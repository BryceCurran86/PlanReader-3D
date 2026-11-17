import test from "node:test";
import assert from "node:assert/strict";
import {
  applyWallMove,freshWallMoves,planCollision,redoWallMove,
  resetWallMoves,safeWallMoves,undoWallMove,moveToWorld,
} from "../src/wallMoveStudy.ts";

function wall(id,a,b,level="L1") {
  return {objectId:id,objectType:"wall",objectRevision:"rev-"+id,
    levelId:level,canonicalObjectId:"canonical-"+id,
    geometry:{kind:"wallFace",start:a,end:b,heightM:2.7},
    renderState:"verified",unresolvedIssues:[],
  };
}
function scene() {
 return {
  scope:{workspaceId:"w",projectId:"p",documentId:"d",revisionId:"r",
    snapshotId:"s",sourceSha256:"a".repeat(64),modelRevision:4},
  objects:[
    wall("A",[0,0],[4,0]),
    wall("B",[2,1],[2,3]),
    wall("C",[0,8],[4,8],"upper"),
  ],
 };
}
test("moves source-revision-pinned wall ghost, snaps to 50mm and preserves scene",()=>{
 const s=scene(),unchanged=structuredClone(s),initial=freshWallMoves(s);
 const result=applyWallMove(initial,s,"A",0.126,0.074);
 assert.equal(result.accepted,true);
 assert.deepEqual(result.state.moves,[{
   objectId:"A",objectRevision:"rev-A",dx:0.15,dz:0.05,
 }]);
 assert.deepEqual(moveToWorld(s.objects[0],result.state.moves[0]),
   [[0.15,0.05],[4.15,0.05]]);
 assert.deepEqual(s,unchanged);
 assert.equal(initial.moves.length,0);
});
test("crossing another wall on the same level blocks local release",()=>{
 const s=scene(),initial=freshWallMoves(s);
 const result=applyWallMove(initial,s,"A",0,2);
 assert.equal(result.accepted,false);
 assert.match(result.reason,/intersects B/);
 assert.deepEqual(result.state,initial);
 assert.equal(planCollision(s,"A",0,8,[]),null);
});
test("undo, redo and reset cannot mutate source or publish corrections",()=>{
 const s=scene();const initial=freshWallMoves(s);
 const first=applyWallMove(initial,s,"A",0.1,0.25).state;
 const second=applyWallMove(first,s,"A",0.3,0.35).state;
 assert.deepEqual(undoWallMove(second).moves,first.moves);
 assert.deepEqual(redoWallMove(undoWallMove(second)).moves,second.moves);
 assert.deepEqual(resetWallMoves(second).moves,[]);
 assert.equal(second.scopeKey,initial.scopeKey);
});
test("stale source SHA, snapshot, model revision or object revision invalidates moves",()=>{
 const s=scene(),base=applyWallMove(freshWallMoves(s),s,"A",.1,.1).state;
 const stale=structuredClone(s);stale.scope.snapshotId="new";
 assert.deepEqual(safeWallMoves(base,stale),[]);
 assert.equal(applyWallMove(base,stale,"A",.3,.3).accepted,false);
 const altered=structuredClone(s);altered.objects[0].objectRevision="new-rev";
 assert.deepEqual(safeWallMoves(base,altered),[]);
});
test("invalid and unknown geometry, out of bounds, NaN and excessive offset refused",()=>{
 const s=scene(),state=freshWallMoves(s);
 for(const [id,dx,dz] of [
   ["missing",1,0],["A",Infinity,0],["A",NaN,0],["A",11,0],
 ]) {
   assert.equal(applyWallMove(state,s,id,dx,dz).accepted,false);
 }
 const noGeometry=structuredClone(s);noGeometry.objects[0].geometry=null;
 assert.equal(applyWallMove(freshWallMoves(noGeometry),noGeometry,"A",0.1,0).accepted,false);
});
