import test from "node:test";
import assert from "node:assert/strict";
import { validatedSourceSurfaces } from "../src/sourceSurfaces.ts";
import { isSceneManifest } from "../src/types.ts";

const scope={
  workspaceId:"w",projectId:"p",documentId:"d",revisionId:"r",
  snapshotId:"snap",sourceSha256:"a".repeat(64),modelRevision:1,
};
function row() {
  return {
    objectId:"room-1",objectType:"room",objectRevision:"hash-r1",
    canonicalObjectId:"canonical-room",levelId:"level1",authority:"firm",
    renderState:"review",geometry:null,dimensions:{},
    source:{sourceFileId:"file",page:2,sheet:"A100",sourceRegion:null,
      originalGeometryRef:"path-21",currentGeometryRef:"path-21"},
    quantityLinks:[],unresolvedIssues:["render_geometry_not_authenticated"],
    canEdit:false,
  };
}
function surface() {
  return {
    surfaceId:"floor-1",objectId:"room-1",objectRevision:"hash-r1",
    canonicalObjectId:"canonical-room",kind:"floor",
    vertices:[
      [0,0,0],[4,0,0],[4,0,3],
      [0,0,0],[4,0,3],[0,0,3],
    ],
    areaM2:12,geometryEvidenceId:"native-room-source",
    triangulationEvidenceId:"signed-triangulation",
    originalGeometryRef:"path-21",sourceSha256:"a".repeat(64),
    snapshotId:"snap",renderState:"verified",commercialAuthority:false,
  };
}
function manifest() {
  return {
    schemaVersion:"1.0.0",scope,
    coordinateSystem:{unit:"metres",sourceToModelTransform:null,renderOrigin:[0,0,0]},
    readOnly:true,objects:[row()],sourceSurfaces:[surface()],
    commercialQuantityPublicationAllowed:false,
  };
}
test("source floor triangle mesh passes exact browser schema without commercial authority",()=>{
  const scene=manifest();
  assert.equal(isSceneManifest(scene),true);
  const records=validatedSourceSurfaces(scene.objects,scene.scope,scene.sourceSurfaces);
  assert.equal(records.length,1);
  assert.equal(records[0].areaM2,12);
  assert.equal(records[0].vertices.length,6);
});
test("nonwall room record alone does not invent floor geometry",()=>{
  const scene=manifest();
  delete scene.sourceSurfaces;
  assert.equal(isSceneManifest(scene),true);
  assert.deepEqual(validatedSourceSurfaces(scene.objects,scene.scope,undefined),[]);
});
test("browser refuses stale or fabricated floor, unproven source or mismatched area",()=>{
  const sample=surface();
  const variants=[
    {...sample,sourceSha256:"b".repeat(64)},
    {...sample,snapshotId:"old-snapshot"},
    {...sample,canonicalObjectId:"other-room"},
    {...sample,objectRevision:"r0"},
    {...sample,originalGeometryRef:"fake"},
    {...sample,areaM2:20},
    {...sample,commercialAuthority:true},
    {...sample,producerAccepted:true,kind:"imaginary-partition"},
    {...sample,vertices:[[0,0,0],[4,0,0],[2,0,0]]},
    {...sample,vertices:[[0,0,0],[4,0,0],[4,0.5,3]]},
  ];
  for(const candidate of variants) {
    const scene=manifest();scene.sourceSurfaces=[candidate];
    assert.equal(isSceneManifest(scene),false);
  }
});
test("duplicate surface and unrelated source object are denied",()=>{
  const scene=manifest();scene.sourceSurfaces=[surface(),surface()];
  assert.equal(isSceneManifest(scene),false);
  const foreign=manifest();foreign.sourceSurfaces[0].objectId="unknown";
  assert.equal(isSceneManifest(foreign),false);
});
