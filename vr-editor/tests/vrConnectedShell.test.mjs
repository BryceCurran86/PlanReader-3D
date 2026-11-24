import test from "node:test";
import assert from "node:assert/strict";
import {connectedDraftShell,DEFAULT_SHELL} from "../src/connectedDraftShell.ts";
const ring=(pts)=>pts.map((p,i)=>({proposalId:"w"+i,scopeKey:"x",levelId:"ground",start:p,end:pts[(i+1)%pts.length],heightM:2.7,openings:[]}));
test("closed rectangular ring derives floor, ceiling and pitched roof without guessing source geometry",()=>{
 const w=ring([[0,0],[8,0],[8,6],[0,6]]);
 const result=connectedDraftShell(w,{roof:"gable",pitchDeg:30,slabMm:100});
 assert.equal(result.floorM2,48);assert.ok(Math.abs(result.slabM3-4.8)<1e-9);
 assert.ok(Math.abs(result.roofM2-48/Math.cos(Math.PI/6))<1e-9);
 assert.equal(result.surfaces.length,3);
 const peak=Math.max(...result.surfaces[2].vertices.map(v=>v[1]));
 assert.ok(Math.abs(peak-(2.7+3*Math.tan(Math.PI/6)))<1e-9);
 assert.equal(connectedDraftShell(w,DEFAULT_SHELL),null);
});
test("irregular and changed local footprints recompute the shell; invalid outlines fail closed",()=>{
 const w=ring([[0,0],[6,0],[6,3],[3,3],[3,6],[0,6]]);
 assert.equal(connectedDraftShell(w,{roof:"gable",pitchDeg:30,slabMm:100}),null);
 const flat={roof:"flat",pitchDeg:30,slabMm:100};
 assert.equal(connectedDraftShell(w,flat).floorM2,27);
 const expanded=ring([[0,0],[8,0],[8,3],[3,3],[3,6],[0,6]]);
 assert.equal(connectedDraftShell(expanded,flat).floorM2,33);
 assert.equal(connectedDraftShell(w.slice(0,-1),flat),null);
 assert.equal(connectedDraftShell(w.map((x,i)=>({...x,heightM:i===0?3:2.7})),flat),null);
});