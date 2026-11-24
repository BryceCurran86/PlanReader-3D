import test from "node:test";
import assert from "node:assert/strict";
import { Ray, Vector3 } from "three";
import { EMPTY_BUILD, STARTING_SIZES, updateBuild } from "../src/buildPlacement.ts";
import { magneticDraftWalls } from "../src/buildScene.ts";
import { buildMenuLayout, EMPTY_ITEM_BROWSER } from "../src/catalogueMenu.ts";
const wall=(id,z=0,scopeKey="scope",levelId="ground")=>({proposalId:id,scopeKey,levelId,start:[0,z],end:[4,z],heightM:2.4,openings:[]});
const state={...EMPTY_BUILD,walls:[wall("a"),wall("b",3)]};
const ray=(x,y,z=1)=>new Ray(new Vector3(x,y,z),new Vector3(0,0,-1));
const act=(s,a)=>updateBuild(s,a,"scope","ground",STARTING_SIZES);
test("magnetic wall targeting exact hits, near misses, release band and opt-out",()=>{
 assert.equal(magneticDraftWalls(state,"ground",ray(2,1))[0]?.proposalId,"a");
 assert.equal(magneticDraftWalls(state,"ground",ray(4.1,1))[0]?.proposalId,"a");
 assert.equal(magneticDraftWalls(state,"ground",ray(4.21,1),"a")[0]?.proposalId,"a");
 assert.deepEqual(magneticDraftWalls(state,"ground",ray(4.21,1)),[]);
 assert.deepEqual(magneticDraftWalls(state,"ground",ray(4.1,1),null,0),[]);
 assert.deepEqual(magneticDraftWalls(state,"upper",ray(2,1)),[]);
});
test("group transforms are local, atomic and undoable",()=>{
 const move={kind:"group-local-walls",proposalIds:["a","b"],operation:"translate",delta:[.2,.1]};
 const next=act(state,move);
 assert.deepEqual(next.walls.map(w=>w.start),[[.2,.1],[.2,3.1]]);
 assert.deepEqual(act(next,{kind:"undo"}).walls,state.walls);
 assert.strictEqual(act(state,{...move,proposalIds:["a","foreign"]}),state);
 assert.strictEqual(act({...state,walls:[wall("a"),wall("b",3,"other")]},move).walls[0].start[0],0);
 const duplicate=act(state,{kind:"group-local-walls",proposalIds:["a","b"],operation:"duplicate",copyIds:["c","d"]});
 assert.deepEqual(duplicate.walls.map(w=>w.proposalId),["a","b","c","d"]);
 assert.deepEqual(act(duplicate,{kind:"undo"}).walls,state.walls);
 assert.deepEqual(act(state,{kind:"group-local-walls",proposalIds:["a","b"],operation:"delete"}).walls,[]);
});
test("optional group tray marks selection count and disables edits when empty",()=>{
 const quest={selectedWall:null,gridM:.05,axis:"auto",nudgeM:.05,pinned:false,help:false,deleteArmed:false,multiSelect:true,selectedCount:0,magnetic:true};
 const menu=buildMenuLayout(state,"ground",EMPTY_ITEM_BROWSER,undefined,false,0,"","finished",false,{available:false,enabled:false,changed:false},undefined,quest);
 assert.match(menu.title,/0 WALLS/);
 assert.ok(menu.buttons.find(b=>b.label==="Rotate group 90°").disabled);
 assert.ok(menu.buttons.find(b=>b.label==="Single select"));
});
