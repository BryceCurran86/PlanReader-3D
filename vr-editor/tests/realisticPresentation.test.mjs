import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import {detailPixels,createMaterialDetailLibrary,physicalUV} from "../src/materialDetail.ts";
import {realismBudget,isRenderQuality,maxRenderPixelRatio} from "../src/visualRealism.ts";
import {starterManifest,starterBuild} from "../src/starterHouse.ts";
import {starterFurnishings} from "../src/starterFurnishings.ts";
import {currentItemPlacements,replaceItemFinish} from "../src/itemPlacement.ts";
import {getCatalogueItem,ITEM_CATALOGUE} from "../src/itemCatalogue.ts";
import {sameFixtureFamily} from "../src/contextFinishes.ts";
import {createPresentationGarden} from "../src/presentationGarden.ts";
test("physical textures are deterministic distinct bounded albedo and relief maps",()=>{
 for(const pattern of ["plaster","plank","tile","woven","fleck","stone","roof"]){
  const pixels=detailPixels(pattern);assert.equal(pixels.albedo.length,256*256*4);
  assert.deepEqual(pixels,detailPixels(pattern));assert.notDeepEqual(pixels.albedo,pixels.relief);
  assert.ok(pixels.albedo.every((v,i)=>i%4!==3||v===255));
 }
 const lib=createMaterialDetailLibrary();assert.equal(lib.get("plank"),lib.get("plank"));assert.notEqual(lib.get("tile"),lib.get("plank"));lib.dispose();
 const g=new THREE.BufferGeometry().setAttribute("position",new THREE.Float32BufferAttribute([0,0,0,2,0,0,2,3,0],3));
 physicalUV(g,.2,.5,[1,0]);assert.deepEqual(Array.from(g.getAttribute("uv").array),[0,0,10,0,10,6]);
});
test("starter has editable real catalogue placements on current valid hosts",()=>{
 const scene=starterManifest(),build=starterBuild(scene),draft=starterFurnishings(scene);
 const current=currentItemPlacements(draft.items,scene,build.walls,false,build.ceilings);
 assert.equal(current.length,draft.items.length);assert.equal(draft.history.length,0);
 for(const id of ["oak-floor","kitchen-base-0","kitchen-island","kitchen-mixer","bath-vanity","bath-mixer","living-sofa","living-table","bed-one","bed-two","living-switch","living-socket"])assert.ok(current.some(i=>i.id===id),id);
 const entry=current.find(i=>i.id==="kitchen-mixer"),old=getCatalogueItem(entry.itemId);
 const variant=ITEM_CATALOGUE.find(i=>i.id!==old.id&&sameFixtureFamily(old,i));
 const updated=replaceItemFinish(draft,draft.sourceKey,entry.id,variant.id);
 assert.equal(updated.items.find(i=>i.id===entry.id).itemId,variant.id);
 assert.equal(scene.commercialQuantityPublicationAllowed,false);
});
test("three quality modes retain headset caps and offer distinct realism budgets",()=>{
 for(const mode of ["performance","balanced","high"]){assert.ok(isRenderQuality(mode));assert.equal(maxRenderPixelRatio(mode,true),1);}
 assert.equal(realismBudget("performance",true).detail,false);
 assert.equal(realismBudget("balanced",true).detail,true);
 assert.equal(realismBudget("high",true).shadows,true);
 assert.equal(realismBudget("balanced",true).shadows,true);
 assert.ok(realismBudget("high",true).shadowRefreshMs>=1000);
});
test("garden remains isolated and uses fixed draw-call budget",()=>{
 const scene=new THREE.Scene(),g=createPresentationGarden(scene);
 g.update({minX:0,maxX:10,minZ:0,maxZ:8},true);
 const group=scene.children[0];assert.ok(group.visible);assert.equal(group.children.length,2);
 assert.ok(group.children.every(m=>m.count>0&&m.count<=m.instanceMatrix.count));
 g.update(null,true);assert.equal(group.visible,false);
 g.dispose();assert.equal(scene.children.length,0);
});
