import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import {starterManifest,starterBuild,starterBounds,STARTER_SHELL} from "../src/starterHouse.ts";
import {starterFurnishings} from "../src/starterFurnishings.ts";
import {commitLocalFootprint} from "../src/localFootprintEdit.ts";
import {previewFootprint,resizeFromDimensions} from "../src/footprintResize.ts";
import {localBuildingShell} from "../src/connectedDraftShell.ts";
import {architecturalPlan} from "../src/architecturalPlan.ts";
import {wallCornerJoins} from "../src/wallCornerJoin.ts";
import {displayWallDraft} from "../src/buildScene.ts";
import {createWallTextureLibrary} from "../src/wallTextures.ts";
import {detailPixels} from "../src/materialDetail.ts";
import {buildMenuLayout,EMPTY_ITEM_BROWSER} from "../src/catalogueMenu.ts";
import {currentItemPlacements} from "../src/itemPlacement.ts";
const scene=starterManifest(),build=starterBuild(scene),items=starterFurnishings(scene),box=starterBounds(build.walls);
test("enlarging starter commits new editable geometry, fixed opening sizes and retained fittings",()=>{
 const requested=resizeFromDimensions(box,12,9,"centre");
 const {projection}=previewFootprint(scene,box,requested,build.walls,build.ceilings);
 const next=commitLocalFootprint(scene,build,items,projection);
 assert.ok(next);assert.deepEqual(starterBounds(next.build.walls),requested);
 assert.equal(next.build.history.at(-1).walls,build.walls);
 assert.deepEqual(next.build.walls.flatMap(w=>w.openings.map(o=>o.widthM)),build.walls.flatMap(w=>w.openings.map(o=>o.widthM)));
 assert.deepEqual(next.items.items.map(p=>p.id),items.items.map(p=>p.id));
 assert.equal(currentItemPlacements(next.items.items,scene,next.build.walls,false,next.build.ceilings).length,currentItemPlacements(items.items,scene,build.walls,false,build.ceilings).length);
 const shell=localBuildingShell(next.build.walls,next.build.ceilings,STARTER_SHELL);
 assert.ok(shell);assert.ok(Math.abs(shell.floorM2-108)<1e-6);
 const drawing=architecturalPlan(scene,next.build,"ground",undefined,null,[],[],shell);
 assert.ok(drawing.labels.some(l=>l.text==="12000"));assert.ok(drawing.labels.some(l=>l.text==="9000"));
 assert.equal(drawing.lines.filter(l=>l.kind==="floor").length,4);
});
test("slab generation does not require a roof and thickness controls nominal volume",()=>{
 const shell=localBuildingShell(build.walls,build.ceilings,{roof:"off",pitchDeg:22.5,slabMm:150,slabEnabled:true});
 assert.ok(shell);assert.equal(shell.roofM2,0);assert.equal(shell.floorM2,80);assert.equal(shell.slabM3,12);
 assert.deepEqual(shell.surfaces.map(s=>s.kind),["floor"]);
 assert.ok(shell.surfaces[0].vertices.some(v=>v[1]===-.15));
 const roof=localBuildingShell(build.walls,build.ceilings,{...STARTER_SHELL,slabEnabled:false});
 assert.equal(roof.slabM3,0);assert.ok(!roof.surfaces.some(s=>s.kind==="floor"));
});
test("local exterior miter is identical in plan and cladding mesh, with no displaced corner edges",()=>{
 const joins=wallCornerJoins(build.walls),a=build.walls[0],b=build.walls[1];
 assert.ok(joins.get(a.proposalId)?.end);assert.ok(joins.get(b.proposalId)?.start);
 const right=joins.get(a.proposalId).end.right;
 assert.deepEqual(right,joins.get(b.proposalId).start.right);
 const textures=createWallTextureLibrary();
 for(const w of [a,b]){
  const mesh=displayWallDraft(w,textures,joins.get(w.proposalId)).children.find(m=>m.userData.exteriorTexture);
  assert.ok(mesh);const p=mesh.geometry.getAttribute("position");
  assert.ok(Array.from({length:p.count},(_,i)=>Math.hypot(p.getX(i)-right[0],p.getZ(i)-right[1])).some(n=>n<1e-5));
 }
 const drawing=architecturalPlan(scene,build,"ground");
 assert.ok(drawing.lines.filter(l=>l.kind==="wall").some(l=>[l.a,l.b].some(p=>Math.hypot(p[0]-right[0],p[1]-right[1])<1e-6)));
 textures.dispose();
});
test("footprint and slab toolbox buttons offer explicit edits and apply",()=>{
 const opts={simpleHome:true,slabMm:100};
 const mk=(footprint,quest)=>buildMenuLayout(build,"ground",EMPTY_ITEM_BROWSER,undefined,false,0,"","finished",false,footprint,undefined,quest);
 const resize=mk({available:true,enabled:true,changed:true},opts);
 assert.equal(resize.buttons.filter(b=>b.action.area==="footprint-size").length,4);
 assert.ok(resize.buttons.some(b=>b.label==="Apply / done"));
 const slab=mk({available:true,enabled:false,changed:false},{...opts,slabTools:true});
 assert.ok(slab.buttons.some(b=>b.action.area==="slab"&&b.action.mm===125));
 const p=detailPixels("concrete",64);assert.ok(new Set(p.albedo).size>12);assert.ok(new Set(p.relief).size>12);
});
