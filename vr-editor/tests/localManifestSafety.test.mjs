import test from "node:test";
import assert from "node:assert/strict";
import { downgradeLocalManifest } from "../src/localManifestSafety.ts";
test("local JSON cannot claim authenticated floor, ceiling, roof, even with verified tokens",()=>{
  const source={
    schemaVersion:"1.0.0",
    objects:[{
      objectId:"room-1",renderState:"verified",unresolvedIssues:[],
      source:{originalGeometryRef:"path-3"},
    }],
    sourceSurfaces:[{
      surfaceId:"forged-roof",renderState:"verified",
      kind:"roof",vertices:[[0,0,0],[4,0,0],[0,2,4]],
    }],
  };
  const before=structuredClone(source);
  const review=downgradeLocalManifest(source);
  assert.equal("sourceSurfaces" in review,false);
  assert.equal(review.objects[0].renderState,"review");
  assert.ok(review.objects[0].unresolvedIssues.includes("local_manifest_not_authenticated"));
  assert.deepEqual(source,before);
});
test("existing unresolved evidence survives downgrade without duplication",()=>{
 const original={
  objects:[{objectId:"a",renderState:"review",
    unresolvedIssues:["missing_source","local_manifest_not_authenticated"]}],
 };
 const review=downgradeLocalManifest(original);
 assert.deepEqual(review.objects[0].unresolvedIssues,
   ["missing_source","local_manifest_not_authenticated"]);
});
