import test from "node:test";
import assert from "node:assert/strict";
import {navigationWallFace,collisionLimitedStep} from "../src/vrStationaryNavigation.ts";
import {readFileSync} from "node:fs";
test("the example yellow unknown-height guide never obstructs walking",()=>{
 const scene=JSON.parse(readFileSync(new URL("../public/synthetic-review-scene.json",import.meta.url),"utf8"));
 const guide=scene.objects.find(o=>o.objectId==="demo-unknown-height");
 assert.equal(guide.geometry.kind,"wallLine");
 assert.equal(navigationWallFace(guide.geometry,true),false);
 const walls=scene.objects.filter(o=>navigationWallFace(o.geometry,true)).map(o=>o.geometry);
 const step=collisionLimitedStep([2,3.2],[0,.6],walls);
 assert.ok(Math.abs(step[1]-.6)<1e-6);
 assert.ok(collisionLimitedStep([3.6,2],[.6,0],walls)[0]<.2);
});
test("hidden and invalid-height geometry is not a physical barrier",()=>{
 assert.equal(navigationWallFace({kind:"wallFace",heightM:2.4},true),true);
 assert.equal(navigationWallFace({kind:"wallFace",heightM:2.4},false),false);
 assert.equal(navigationWallFace({kind:"wallFace",heightM:0},true),false);
 assert.equal(navigationWallFace({kind:"wallFace",heightM:NaN},true),false);
 assert.equal(navigationWallFace(null,true),false);
});