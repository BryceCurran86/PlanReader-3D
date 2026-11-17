import test from "node:test";
import assert from "node:assert/strict";
import {
  DEFAULT_INSPECTION, filterEvidence, matchesSourceFilter, nextReview,
  safeQuery, sourceSheets, summarizeEvidence, bySheet,
} from "../src/reviewInspection.ts";

function makeScene() {
  const base = {
    objectType: "wall", canonicalObjectId: null,
    objectRevision: "r0", levelId: "lower",
    renderState: "review", geometry: null,
    source: {sheet:"A101",page:3,originalGeometryRef:"path-1"},
    unresolvedIssues: ["source_unresolved"],
  };
  return {
    scope: {workspaceId:"w1",snapshotId:"s1"},
    objects: [
      {...base,objectId:"wall-alpha",canonicalObjectId:"canonical-one",
        renderState:"verified",unresolvedIssues:[],geometry:{
          kind:"wallFace",start:[0,0],end:[4,0],heightM:2.7,
        }},
      {...base,objectId:"wall-beta",geometry:{
        kind:"wallLine",start:[0,0],end:[4,0],
      }},
      {...base,objectId:"wall-gamma",levelId:"upper",
        source:{...base.source,sheet:"A102",originalGeometryRef:"path-3"}},
      {...base,objectId:"wall-delta",source:{...base.source,originalGeometryRef:"path-4"}},
    ],
  };
}
const scene = makeScene();

test("20 control workflows do not modify original evidence objects", () => {
  const original = structuredClone(scene);
  const options = { ...DEFAULT_INSPECTION, reviewFilter:"review" };
  const rows = filterEvidence(scene,"lower",null,options);
  assert.deepEqual(rows.map(row=>row.objectId),["wall-beta","wall-delta"]);
  assert.deepEqual(scene,original);
});

test("trusted geometry status never inferred from canonical identity alone",()=>{
  const [a,b,c]=scene.objects;
  assert.equal(matchesSourceFilter(a,"verified"),true);
  assert.equal(matchesSourceFilter(b,"verified"),false);
  assert.equal(matchesSourceFilter(a,"review"),false);
  assert.equal(matchesSourceFilter(b,"review"),true);
  assert.equal(matchesSourceFilter(b,"source-lines"),true);
  assert.equal(matchesSourceFilter(c,"source-lines"),false);
});

test("search is bounded and covers object, canonical, sheet and primitive",()=>{
  const q={...DEFAULT_INSPECTION,search:" CANONICAL-ONE "};
  assert.deepEqual(filterEvidence(scene,"all",null,q).map(x=>x.objectId),["wall-alpha"]);
  assert.deepEqual(filterEvidence(scene,"all",null,{...q,search:"PATH-3"})
    .map(x=>x.objectId),["wall-gamma"]);
  assert.equal(safeQuery(" x ".repeat(200)).length,128);
});

test("isolation cannot summon a hidden object across explicit levels",()=>{
  const options={...DEFAULT_INSPECTION,isolateSelected:true};
  assert.deepEqual(filterEvidence(scene,"lower","wall-gamma",options),[]);
  assert.deepEqual(filterEvidence(scene,"all","wall-gamma",options)
    .map(x=>x.objectId),["wall-gamma"]);
  assert.deepEqual(filterEvidence(scene,"all",null,options),[]);
});

test("review traversal wraps, skips verified and handles no review",()=>{
  const rows=scene.objects;
  assert.equal(nextReview(rows,null,1),"wall-beta");
  assert.equal(nextReview(rows,null,-1),"wall-delta");
  assert.equal(nextReview(rows,"wall-beta",1),"wall-gamma");
  assert.equal(nextReview(rows,"wall-beta",-1),"wall-delta");
  assert.equal(nextReview(rows,"wall-delta",1),"wall-beta");
  assert.equal(nextReview([rows[0]],"wall-alpha",1),null);
});

test("source sheet navigation and counts keep source identity intact",()=>{
  assert.deepEqual(sourceSheets(scene.objects),["A101","A102"]);
  assert.deepEqual(bySheet(scene.objects,"A102").map(x=>x.objectId),["wall-gamma"]);
  assert.equal(bySheet(scene.objects,"").length,4);
  const summary=summarizeEvidence(scene.objects);
  assert.deepEqual(summary,{
    total:4,faces:1,lines:1,withoutDisplayGeometry:2,
    verified:1,review:3,canonical:1,
  });
});
