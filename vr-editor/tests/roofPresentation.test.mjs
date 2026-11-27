import test from "node:test";
import assert from "node:assert/strict";
import {starterBuild,starterManifest,STARTER_SHELL} from "../src/starterHouse.ts";
import {localBuildingShell} from "../src/connectedDraftShell.ts";
import {roofPresentationParts,roofSkinAndGables} from "../src/roofPresentation.ts";
const build=starterBuild(starterManifest());
test("gable closures are separate from roof covering and rectangular roof gains bounded eaves",()=>{
 const shell=localBuildingShell(build.walls,build.ceilings,STARTER_SHELL),before=JSON.stringify(shell);
 const roof=shell.surfaces.find(s=>s.kind==="roof"),split=roofSkinAndGables(roof.vertices);
 assert.ok(split.skin.length>0);assert.ok(split.gables.length>0);assert.equal(split.skin.length+split.gables.length,roof.vertices.length);
 const parts=roofPresentationParts(shell);assert.deepEqual(parts.map(p=>p.kind),["skin","soffit","fascia","gutter"]);
 const skin=parts[0].vertices;
 assert.ok(Math.abs(Math.min(...skin.map(v=>v[0]))+.3)<1e-7);assert.ok(Math.abs(Math.max(...skin.map(v=>v[0]))-10.3)<1e-7);
 assert.ok(Math.abs(Math.min(...skin.map(v=>v[2]))+.3)<1e-7);assert.ok(Math.abs(Math.max(...skin.map(v=>v[2]))-8.3)<1e-7);
 assert.ok(parts.every(p=>p.vertices.length%3===0&&p.vertices.flat().every(Number.isFinite)));
 assert.equal(JSON.stringify(shell),before);
});
test("slab-only or nonrectangular roof does not get invented eaves",()=>{
 const slab=localBuildingShell(build.walls,build.ceilings,{roof:"off",slabEnabled:true,slabMm:100,pitchDeg:22.5});
 assert.deepEqual(roofPresentationParts(slab),[]);
 const triangle={...slab,surfaces:[{kind:"roof",vertices:[[0,2.4,0],[10,2.4,0],[3,2.4,8]]}]};
 assert.deepEqual(roofPresentationParts(triangle),[]);
});
