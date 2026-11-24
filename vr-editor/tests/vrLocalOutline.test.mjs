import test from "node:test";
import assert from "node:assert/strict";
import {localOutline,outlineArea,editLocalOutline} from "../src/localOutline.ts";
import {EMPTY_BUILD,STARTING_SIZES,updateBuild} from "../src/buildPlacement.ts";
const w=(id,start,end,openings=[])=>({proposalId:id,scopeKey:"s",levelId:"g",start,end,heightM:2.7,openings});
const ring=[w("a",[0,0],[8,0]),w("b",[8,6],[8,0]),w("c",[8,6],[0,6]),w("d",[0,6],[0,0])];
test("closed outline follows actual connected walls independent of their direction",()=>{
 const o=localOutline(ring);
 assert.equal(o.areaM2,48);
 assert.equal(o.edges[1].reversed,true);
 assert.equal(localOutline(ring.slice(0,3)),null);
 assert.equal(localOutline([...ring,w("extra",[0,0],[2,2])]),null);
 assert.equal(outlineArea([[0,0],[4,4],[0,4],[4,0]]),null);
});
test("moving a corner or edge retains joined walls and rejects crossing",()=>{
 const moved=editLocalOutline(ring,{kind:"move-point",index:1,point:[10,0]});
 assert.deepEqual(moved[0].end,[10,0]);assert.deepEqual(moved[1].end,[10,0]);
 assert.equal(localOutline(moved).areaM2,54);
 const side=editLocalOutline(ring,{kind:"move-edge",index:1,delta:[2,0]});
 assert.equal(localOutline(side).areaM2,60);
 assert.equal(editLocalOutline(ring,{kind:"move-point",index:1,point:[-1,7]}),null);
});
test("insertion creates a genuine concave point; removal restores area",()=>{
 const extra=editLocalOutline(ring,{kind:"insert-point",index:0,point:[4,2],newId:"e"});
 assert.equal(extra.length,5);assert.equal(localOutline(extra).areaM2,40);
 const removed=editLocalOutline(extra,{kind:"remove-point",index:1});
 assert.equal(removed.length,4);assert.equal(localOutline(removed).areaM2,48);
});
test("opening dimensions preserved, destructive splits rejected and stale edits do not apply",()=>{
 const door={openingId:"d1",openingKind:"door",offsetM:2,widthM:1,heightM:2.1,sillHeightM:0};
 const original=[{...ring[0],openings:[door]},...ring.slice(1)];
 const changed=editLocalOutline(original,{kind:"move-point",index:1,point:[10,0]});
 assert.equal(changed[0].openings[0].widthM,1);
 assert.equal(editLocalOutline(original,{kind:"insert-point",index:0,point:[4,0],newId:"e"}),null);
 const state={...EMPTY_BUILD,walls:original};
 const action={kind:"edit-local-outline",expected:JSON.stringify(original),edit:{kind:"move-point",index:1,point:[10,0]}};
 const next=updateBuild(state,action,"s","g",STARTING_SIZES);
 assert.notEqual(next,state);assert.equal(next.history.length,1);
 assert.equal(updateBuild(next,action,"s","g",STARTING_SIZES),next);
 assert.deepEqual(updateBuild(next,{kind:"undo"},"s","g",STARTING_SIZES).walls,original);
});
