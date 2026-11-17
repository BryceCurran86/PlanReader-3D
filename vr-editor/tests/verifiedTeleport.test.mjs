import test from "node:test";
import assert from "node:assert/strict";
import {
  evaluateSourceFloorTeleport,describeTeleportReason,
} from "../src/verifiedTeleport.ts";

function scene() {
  const scope={
    workspaceId:"workspace-1",projectId:"p",documentId:"d",revisionId:"r",
    snapshotId:"s1",sourceSha256:"a".repeat(64),modelRevision:3,
  };
  return {
    scope,
    objects:[{
      objectId:"room-1",objectRevision:"rev-1",
      canonicalObjectId:"canonical-room-1",objectType:"room",
      source:{originalGeometryRef:"original-source-native-floor"},
    }],
    sourceSurfaces:[{
      surfaceId:"original-floor-1",objectId:"room-1",
      objectRevision:"rev-1",canonicalObjectId:"canonical-room-1",
      kind:"floor",renderState:"verified",commercialAuthority:false,
      sourceSha256:scope.sourceSha256,snapshotId:scope.snapshotId,
      originalGeometryRef:"original-source-native-floor",
      vertices:[
        [0,0,0],[4,0,0],[4,0,4],
        [0,0,0],[4,0,4],[0,0,4],
      ],
      areaM2:16,
    }],
  };
}
const target=[2,0,2];
const head=[1,1.7,1];

test("allows short source-proven ground-floor teleport across internal triangle seam",()=>{
  const original=scene(), snapshot=structuredClone(original);
  const result=evaluateSourceFloorTeleport(original,"original-floor-1",target,head);
  assert.equal(result.accepted,true);
  assert.equal(result.reason,"ok");
  assert.deepEqual(result.destination,target);
  assert.ok(result.distanceM>1.4 && result.distanceM<1.5);
  assert.deepEqual(original,snapshot);
});
test("requires exact original-source floor and rejects synthetic or non-floor scenes",()=>{
  const s=scene();delete s.sourceSurfaces;
  assert.equal(evaluateSourceFloorTeleport(s,"original-floor-1",target,head).reason,
    "no_verified_source_floor");
  const roof=scene();roof.sourceSurfaces[0].kind="roof";
  assert.equal(evaluateSourceFloorTeleport(roof,"original-floor-1",target,head).reason,
    "no_verified_source_floor");
  const commerce=scene();commerce.sourceSurfaces[0].commercialAuthority=true;
  assert.equal(evaluateSourceFloorTeleport(commerce,"original-floor-1",target,head).reason,
    "no_verified_source_floor");
});
test("invalid, stale and cross-document candidate source cannot authorise locomotion",()=>{
  const tests=[
    s=>{s.sourceSurfaces[0].snapshotId="old";},
    s=>{s.sourceSurfaces[0].sourceSha256="b".repeat(64);},
    s=>{s.sourceSurfaces[0].canonicalObjectId="other-room";},
    s=>{s.sourceSurfaces[0].objectRevision="old";},
    s=>{s.sourceSurfaces[0].originalGeometryRef="wrong-pdf-stroke";},
    s=>{s.objects=[];},
  ];
  for(const tamper of tests){
    const s=scene();tamper(s);
    assert.equal(evaluateSourceFloorTeleport(s,"original-floor-1",target,head).reason,
      "stale_floor_source");
  }
  assert.equal(evaluateSourceFloorTeleport(scene(),"original-floor-1",
    [Infinity,0,2],head).reason,"invalid_target");
});
test("edge, outside, floor-height jumps, long and tiny moves are denied",()=>{
  const s=scene();
  for(const [hit,viewer,expected] of [
    [[.04,0,2],head,"unsafe_floor_edge"],
    [[4.5,0,2],head,"outside_floor_triangle"],
    [[2,1,2],head,"vertical_level_not_supported"],
    [[3,0,3],[-6,1.7,-6],"too_far"],
    [[2,0,2],[2.01,1.7,2.01],"too_close"],
  ]) {
    assert.equal(evaluateSourceFloorTeleport(s,"original-floor-1",hit,viewer).reason,
      expected);
  }
  const upstairs=scene();
  upstairs.sourceSurfaces[0].vertices=upstairs.sourceSurfaces[0].vertices.map(p=>[p[0],2.8,p[2]]);
  assert.equal(evaluateSourceFloorTeleport(upstairs,"original-floor-1",[2,2.8,2],head).reason,
    "vertical_level_not_supported");
});
test("explanations explicitly describe proof, safety and unsupported level jumps",()=>{
  assert.match(describeTeleportReason("too_far"),/7 metres/);
  assert.match(describeTeleportReason("no_verified_source_floor"),/source-verified/);
  assert.match(describeTeleportReason("vertical_level_not_supported"),/stair or lift/);
});
