import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import {draftHandlePoints,pickDraftEditHandle,createDraftEditHandles} from "../src/draftEditHandles.ts";
const w={proposalId:"w",scopeKey:"scope",levelId:"ground",start:[0,0],end:[4,0],heightM:2.4,openings:[]};
const c={proposalId:"c",scopeKey:"scope",levelId:"ground",start:[0,0],end:[4,3],heightM:2.4};
const ray=(x,z)=>new THREE.Ray(new THREE.Vector3(x,8,z),new THREE.Vector3(0,-1,0));
test("wall centre moves, endpoints stretch around opposite anchor",()=>{
 const shape={kind:"wall",object:w};
 assert.equal(draftHandlePoints(shape).length,3);
 assert.equal(pickDraftEditHandle(shape,ray(2,0)).mode,"move");
 const start=pickDraftEditHandle(shape,ray(0,0));
 assert.equal(start.mode,"stretch");assert.equal(start.stretchStart,true);assert.deepEqual(start.anchor,[4,0]);
 const end=pickDraftEditHandle(shape,ray(4,0));
 assert.equal(end.stretchStart,false);assert.deepEqual(end.anchor,[0,0]);
 assert.equal(pickDraftEditHandle(shape,ray(1,1)),null);
});
test("ceiling corners stretch from opposite corners and centre moves",()=>{
 const shape={kind:"ceiling",object:c};
 assert.equal(draftHandlePoints(shape).length,5);
 assert.deepEqual(pickDraftEditHandle(shape,ray(4,3)).anchor,[0,0]);
 assert.equal(pickDraftEditHandle(shape,ray(2,1.5)).mode,"move");
 const view=createDraftEditHandles();view.update(shape);
 assert.equal(view.group.children.filter(x=>x.visible).length,5);
 view.update({kind:"wall",object:w});assert.equal(view.group.children.filter(x=>x.visible).length,3);
 view.update(null);assert.equal(view.group.visible,false);
});
test("handles do not select behind the controller or overlap on very short walls",()=>{
 const shape={kind:"wall",object:w};
 assert.equal(pickDraftEditHandle(shape,new THREE.Ray(new THREE.Vector3(0,8,0),new THREE.Vector3(0,1,0))),null);
 assert.equal(draftHandlePoints({kind:"wall",object:{...w,end:[.2,0]}}).length,1);
});
