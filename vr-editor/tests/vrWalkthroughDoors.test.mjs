import test from "node:test";
import assert from "node:assert/strict";
import {localNavigationWalls,doorKey,doorSwingSegment} from "../src/walkthroughDoors.ts";
import {collisionLimitedStep} from "../src/vrStationaryNavigation.ts";
import {displayWallDraft} from "../src/buildScene.ts";
import {buildMenuLayout,EMPTY_ITEM_BROWSER} from "../src/catalogueMenu.ts";
import {EMPTY_BUILD} from "../src/buildPlacement.ts";
const wall={proposalId:"w",scopeKey:"test",levelId:"ground",start:[0,0],end:[4,0],heightM:2.7,openings:[{openingId:"d",openingKind:"door",offsetM:1,widthM:1,heightM:2.1,sillHeightM:0}]};
test("closed doors obstruct walking; opened door apertures can be crossed",()=>{
 const closed=localNavigationWalls(wall,new Set());
 const open=localNavigationWalls(wall,new Set([doorKey("w","d")]));
 assert.equal(closed.length,1);
 assert.equal(open.length,3);
 assert.ok(collisionLimitedStep([1.5,.5],[0,-1],closed)[1]>-.5);
 assert.ok(Math.abs(collisionLimitedStep([1.5,.5],[0,-1],open)[1]+1)<1e-6);
 assert.ok(collisionLimitedStep([.5,.5],[0,-1],open)[1]>-.5);
});
test("door swing uses hinge and correct orientation",()=>{
 const s=doorSwingSegment(wall,1,1,Math.PI/2);
 assert.deepEqual(s.start,[1,0]);assert.ok(Math.abs(s.end[0]-1)<1e-8);
 assert.ok(Math.abs(s.end[1]+1)<1e-8);
 const mesh=displayWallDraft(wall).children.find(c=>c.userData.catalogueDoorLeaf==="d");
 assert.deepEqual(mesh.userData.doorHinge.toArray(),[1,0,0]);
});
test("hidden doors do not block passages, windows still do",()=>{
 assert.ok(Math.abs(collisionLimitedStep([1.5,.5],[0,-1],localNavigationWalls(wall,new Set(),false))[1]+1)<1e-6);
 const w={...wall,openings:[{...wall.openings[0],openingKind:"window",sillHeightM:.6,heightM:1.5}]};
 assert.equal(localNavigationWalls(w,new Set([doorKey("w","d")])).length,1);
});
test("ghost toggle is discoverable and displays its current state",()=>{
 const quest={selectedWall:null,gridM:.05,axis:"auto",nudgeM:.05,pinned:false,help:false,deleteArmed:false,compact:true,ghost:true};
 const layout=buildMenuLayout(EMPTY_BUILD,"ground",EMPTY_ITEM_BROWSER,undefined,false,0,"","finished",false,undefined,undefined,quest);
 assert.ok(layout.buttons.some(b=>b.action.area==="quest"&&b.action.action==="ghost"&&b.label.includes("ON")));
});