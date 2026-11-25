import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {sceneCoverage,reviewDimensions,captureAlternative,restoreAlternative} from "../src/vrDesignReview.ts";
import {EMPTY_BUILD} from "../src/buildPlacement.ts";
import {scopeKey} from "../src/reviewDraft.ts";
const scene=JSON.parse(readFileSync(new URL("../public/synthetic-review-scene.json",import.meta.url),"utf8"));
const level=scene.objects[0].levelId;
const wall={proposalId:"wall-one",scopeKey:scopeKey(scene),levelId:level,start:[0,0],end:[4,0],heightM:2.7,openings:[]};
const build={...EMPTY_BUILD,walls:[wall]};
test("import coverage reports real fixture faces and guides, not fabricated material evidence",()=>{
 const result=sceneCoverage(scene);
 assert.equal(result.wallRecords,6);assert.equal(result.wallFaces,5);
 assert.equal(result.guideLines,1);assert.equal(result.verifiedWalls,0);
 assert.equal(result.wallAssemblies,"not supplied");
});
test("review dimensions contain local measurements but no unverified source dimensions",()=>{
 const dims=reviewDimensions(scene,build,level,new Set(scene.objects.map(o=>o.objectId)));
 assert.equal(dims.length,1);
 assert.match(dims[0].label,/4000 × 2700 × 116 mm · DRAFT/);
});
test("named alternatives round-trip the exact source and are isolated from later edits",()=>{
 const alt=captureAlternative(scene,build,null,"Version A","a");
 const edited={...wall,heightM:3};
 assert.equal(restoreAlternative(scene,alt).build.walls[0].heightM,2.7);
 assert.equal(edited.heightM,3);
 assert.throws(()=>restoreAlternative({...scene,scope:{...scene.scope,snapshotId:"another"}},alt));
 assert.throws(()=>captureAlternative(scene,build,null,"","x"));
});