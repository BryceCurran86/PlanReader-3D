import test from "node:test";
import assert from "node:assert/strict";
import {junctionBacking,junctionBackingMesh} from "../src/constructionJunctionVisual.ts";
const wall=(id,start,end,extra={})=>({proposalId:id,scopeKey:"s",levelId:"ground",start,end,heightM:2.7,openings:[],...extra});
test("T junctions add backing at real host adjacency and respect level/scope",()=>{
 const host=wall("h",[0,0],[5,0]),branch=wall("b",[2.1,0],[2.1,3]);
 const entries=junctionBacking([host,branch]);
 assert.ok(entries.some(e=>e.wallId==="h"&&e.kind==="tee"&&e.side===1));
 assert.ok(entries.every(e=>e.bottom>=0&&e.top<=2.7&&e.top>e.bottom));
 assert.equal(junctionBacking([host,{...branch,levelId:"upper"}]).length,0);
 assert.equal(junctionBacking([host,{...branch,scopeKey:"different"}]).length,0);
 assert.equal(junctionBacking([host,wall("gap",[2.1,.001],[2.1,3])]).length,0);
 assert.equal(junctionBacking([host,wall("straight",[5,0],[8,0])]).length,0);
 const mesh=junctionBackingMesh([host,branch]);assert.ok(mesh);assert.equal(mesh.count,entries.length);
});
test("corner backing uses actual endpoints and remains inside nominal timber host",()=>{
 const a=wall("a",[0,0],[5,0]),b=wall("b",[0,0],[0,3]);
 const entries=junctionBacking([a,b]);assert.ok(entries.some(e=>e.kind==="corner"));
 for(const e of entries){assert.ok(e.offset-e.width/2>=-1e-7);assert.ok(e.depth>=.09-1e-7);}
 assert.equal(junctionBacking([a,{...b,assembly:{profile:"blockwork",thicknessMm:190,exteriorSide:"left"}}]).length,0);
});
test("junction never adds a backing stud through a draft opening",()=>{
 const host=wall("h",[0,0],[5,0],{openings:[{openingId:"d",openingKind:"door",offsetM:1.5,widthM:1.2,heightM:2.04,sillHeightM:0}]});
 const b=wall("b",[2.1,0],[2.1,3]);
 assert.equal(junctionBacking([host,b]).filter(e=>e.wallId==="h").length,0);
});
