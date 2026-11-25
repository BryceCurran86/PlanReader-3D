import test from "node:test";
import assert from "node:assert/strict";
import {localDoorMotion} from "../src/localDoorMotion.ts";
import {localNavigationWalls,doorKey} from "../src/walkthroughDoors.ts";
import {EMPTY_BUILD,STARTING_SIZES,updateBuild} from "../src/buildPlacement.ts";
const opening={openingId:"door",openingKind:"door",offsetM:1,widthM:1,heightM:2.04,sillHeightM:0};
const wall={proposalId:"wall",scopeKey:"scope",levelId:"ground",start:[0,0],end:[5,0],heightM:2.4,openings:[opening]};
const open=new Set([doorKey("wall","door")]);
const withMode=mode=>({...wall,openings:[{...opening,doorMechanism:mode}]});
test("sliding and overhead garage motion leave a clear walkthrough opening",()=>{
 for(const kind of ["sliding","garage"]){
  const w=withMode(kind),m=localDoorMotion(w,w.openings[0],.05);
  assert.equal(m.kind,kind);
  assert.equal(localNavigationWalls(w,new Set()).length,1);
  const segments=localNavigationWalls(w,open);
  assert.deepEqual(segments.map(s=>[s.start,s.end]),[[[0,0],[1,0]],[[2,0],[5,0]]]);
 }
 assert.equal(localNavigationWalls(wall,open).length,3);
 assert.equal(localDoorMotion(withMode("garage"),withMode("garage").openings[0],.05).pivot[1],2.04);
});
test("slider requires a clear adjacent host track and falls back to left",()=>{
 const o={...opening,doorMechanism:"sliding"};
 const right={...opening,openingId:"other",offsetM:2.1};
 assert.equal(localDoorMotion({...wall,openings:[o,right]},o,.05).translation[0],-1);
 const left={...opening,openingId:"left",offsetM:0};
 const blocked={...wall,openings:[o,right,left]};
 assert.equal(localDoorMotion(blocked,o,.05),null);
 assert.equal(localNavigationWalls(blocked,open).length,1);
});
test("mechanism is explicitly selected, scope checked and undoable",()=>{
 const s={...EMPTY_BUILD,walls:[wall]};
 const act={kind:"set-door-mechanism",proposalId:"wall",openingId:"door",mechanism:"garage"};
 const next=updateBuild(s,act,"scope","ground",STARTING_SIZES);
 assert.equal(next.walls[0].openings[0].doorMechanism,"garage");
 assert.equal(updateBuild(next,{kind:"undo"},"scope","ground",STARTING_SIZES).walls,s.walls);
 assert.equal(updateBuild(s,act,"other","ground",STARTING_SIZES),s);
});
