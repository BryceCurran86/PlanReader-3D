import test from "node:test";
import assert from "node:assert/strict";
import {Ray,Vector3} from "three";
import {starterManifest,starterBuild,starterShell,starterBounds,STARTER_SHELL,STARTER_LEVEL} from "../src/starterHouse.ts";
import {isSceneManifest} from "../src/types.ts";
import {scopeKey} from "../src/reviewDraft.ts";
import {directDraftGesture,draftGesturePreview} from "../src/buildScene.ts";
import {updateBuild,STARTING_SIZES,openingFits} from "../src/buildPlacement.ts";
const scene=starterManifest(),state=starterBuild(scene);
const down=(x,z)=>new Ray(new Vector3(x,15,z),new Vector3(0,-1,0));
const opts={magnetic:true};
test("starter house is complete editable local design, not source evidence",()=>{
 assert.equal(isSceneManifest(scene),true);
 assert.equal(scene.commercialQuantityPublicationAllowed,false);
 assert.ok(scene.objects.every(o=>o.geometry===null&&o.quantityLinks.length===0&&!o.canEdit));
 assert.equal(state.walls.length,7);assert.equal(state.ceilings.length,4);
 assert.ok(state.walls.every(w=>w.scopeKey===scopeKey(scene)&&w.openings.every(o=>openingFits(w,o))));
 assert.deepEqual(starterBounds(state.walls),{minX:0,maxX:10,minZ:0,maxZ:8});
 const shell=starterShell(state.walls,STARTER_SHELL);
 assert.ok(shell);assert.equal(shell.floorM2,80);
 assert.deepEqual(shell.surfaces.map(s=>s.kind),["floor","roof"]);
});
test("top direct wall drag selects the wall before covering ceiling and uses validated undoable action",()=>{
 const gesture=directDraftGesture(state,STARTER_LEVEL,down(6,3),"auto",true,opts);
 assert.equal(gesture?.previous.proposalId,"room-divider");
 assert.equal(gesture.direct,true);assert.equal(gesture.mode,"move");
 const preview=draftGesturePreview(gesture,STARTING_SIZES,down(6.5,3),state,undefined,opts);
 assert.equal(preview.action.kind,"adjust");
 const next=updateBuild(state,preview.action,scopeKey(scene),STARTER_LEVEL,STARTING_SIZES);
 assert.notEqual(next,state);assert.equal(next.walls.find(w=>w.proposalId==="room-divider").start[0],6.5);
 assert.deepEqual(updateBuild(next,{kind:"undo"},scopeKey(scene),STARTER_LEVEL,STARTING_SIZES).walls,state.walls);
});
test("ceiling pick explicitly ignores walls and moves only ceiling geometry",()=>{
 const gesture=directDraftGesture(state,STARTER_LEVEL,down(3,2),"ceilings",true,opts);
 assert.equal(gesture?.previous.proposalId,"living-ceiling");
 const preview=draftGesturePreview(gesture,STARTING_SIZES,down(3.5,2),state,undefined,opts);
 assert.equal(preview.action.kind,"adjust-ceiling");
 const next=updateBuild(state,preview.action,scopeKey(scene),STARTER_LEVEL,STARTING_SIZES);
 assert.equal(next.walls,state.walls);
 assert.deepEqual(next.ceilings[0].start,[.5,0]);
 assert.equal(directDraftGesture(state,STARTER_LEVEL,down(30,30),"walls",true,opts),null);
});

import {editableSurfaceVisible,draftWallLayerVisible} from "../src/constructionLayers.ts";
test("top editing respects hidden ceilings and always keeps the roof out of the way",()=>{
 assert.equal(editableSurfaceVisible("framing","ceiling",{},true,true,true),true);
 assert.equal(editableSurfaceVisible("framing","ceiling",{ceiling:"hide"},true,true,true),false);
 assert.equal(editableSurfaceVisible("framing","ceiling",{ceiling:"show"},true,true,false),false);
 assert.equal(editableSurfaceVisible("framing","roof",{roof:"show"},true,true,true),false);
 assert.equal(editableSurfaceVisible("framing","ceiling",{ceiling:"show"},false,false,false),true);
});
test("direct wall and magnetic targets share visible construction-layer eligibility",()=>{
 assert.equal(draftWallLayerVisible("framing",{},false),true);
 assert.equal(draftWallLayerVisible("framing",{wall:"hide",framing:"hide"},false),false);
 assert.equal(draftWallLayerVisible("slab",{},false),false);
 assert.equal(draftWallLayerVisible("framing",{framing:"hide"},true),true);
 assert.equal(draftWallLayerVisible("slab",{wall:"show"},false),true);
 assert.equal(draftWallLayerVisible("slab",{wall:"hide",framing:"show"},false),true);
});
