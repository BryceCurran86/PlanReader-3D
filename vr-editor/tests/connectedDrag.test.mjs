import test from "node:test";
import assert from "node:assert/strict";
import {EMPTY_BUILD,STARTING_SIZES,updateBuild} from "../src/buildPlacement.ts";
const wall=(id,start,end,levelId="L1")=>({proposalId:id,scopeKey:"draft",levelId,start,end,heightM:2.4,openings:[]});
const fixture=()=>{
 const a=wall("a",[0,0],[4,0]),b=wall("b",[4,0],[4,3]),c=wall("c",[4,3],[0,3]),d=wall("d",[0,3],[0,0]);
 return {...EMPTY_BUILD,walls:[a,b,c,d,wall("other",[0,0],[4,0],"L2")]};
};
const apply=(s,a)=>updateBuild(s,a,"draft","L1",STARTING_SIZES);
test("connected drag preserves perimeter endpoints and undoes atomically",()=>{
 const state=fixture(),previous=state.walls[0];
 const next=apply(state,{kind:"adjust",previous,wall:{...previous,start:[0,-1],end:[4,-1]},connected:true});
 assert.notEqual(next,state);
 assert.deepEqual(next.walls[1].start,[4,-1]);
 assert.deepEqual(next.walls[3].end,[0,-1]);
 assert.equal(next.walls[4],state.walls[4]);
 assert.equal(apply(next,{kind:"undo"}).walls,state.walls);
});
test("connected drag refuses unsplit junction and cross-level adjustment",()=>{
 const state=fixture(),previous=state.walls[0];
 const blocked={...state,walls:[...state.walls,wall("junction",[2,0],[2,1])]};
 assert.equal(apply(blocked,{kind:"adjust",previous,wall:{...previous,start:[0,-1],end:[4,-1]},connected:true}),blocked);
 const other=state.walls[4];
 assert.equal(apply(state,{kind:"adjust",previous:other,wall:{...other,end:[5,0]}}),state);
});
test("independent mode retains ordinary single-wall edits",()=>{
 const state=fixture(),previous=state.walls[0];
 const next=apply(state,{kind:"adjust",previous,wall:{...previous,start:[0,-1],end:[4,-1]},connected:false});
 assert.notEqual(next,state);
 assert.equal(next.walls[1],state.walls[1]);
 assert.equal(next.walls[3],state.walls[3]);
});
