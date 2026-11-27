import test from "node:test";
import assert from "node:assert/strict";
import {realismBudget,architecturalShadowExtent} from "../src/visualRealism.ts";
import {detailPixels} from "../src/materialDetail.ts";
test("balanced VR retains bounded static shadows, performance mode may disable them",()=>{
 assert.equal(realismBudget("balanced",true).shadows,true);
 assert.equal(realismBudget("performance",true).shadows,false);
 assert.ok(realismBudget("balanced",true).shadowRefreshMs>=1000);
 assert.ok(architecturalShadowExtent(10,8)<12);
 assert.equal(architecturalShadowExtent(NaN,8),12);
});
test("neutral high resolution grain is deterministic with subdued seams",()=>{
 const a=detailPixels("plank",256),b=detailPixels("plank",256);
 assert.equal(a.albedo.length,256*256*4);
 assert.deepEqual(a.albedo,b.albedo);
 assert.ok(a.albedo[0]>=130);
 assert.notEqual(a.albedo[(80*256+80)*4],a.albedo[0]);
 assert.notDeepEqual(a.albedo,a.relief);
});