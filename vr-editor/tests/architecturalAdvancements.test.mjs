import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import {ceramicBowlGeometry} from "../src/catalogueFixtures.ts";
import {previewBeam} from "../src/lightingPreview.ts";
import {createCatalogueScene,draftCatalogueHosts,demoCatalogueHosts} from "../src/catalogueScene.ts";
import {displayWallDraft} from "../src/buildScene.ts";
import {searchCatalogue} from "../src/itemCatalogue.ts";
import {emptyItemDraft,placeItem} from "../src/itemPlacement.ts";
test("ceramic shell preserves the nominal envelope and has a recessed centre",()=>{
 const g=ceramicBowlGeometry(.51,.14,.38);g.computeBoundingBox();
 const b=g.boundingBox;assert.ok(Math.abs(b.max.x-b.min.x-.51)<1e-6);assert.ok(Math.abs(b.max.y-.14)<1e-6);assert.ok(Math.abs(b.max.z-b.min.z-.38)<1e-6);
 const p=g.getAttribute("position"),n=g.getAttribute("normal");assert.ok(Array.from(n.array).every(Number.isFinite));
 assert.ok(Array.from({length:p.count},(_,i)=>i).some(i=>Math.abs(p.getX(i))<.001&&Math.abs(p.getZ(i))<.001&&Math.abs(p.getY(i)-.14*.19)<1e-6));
 assert.ok(g.index.count<2500);g.dispose();
});
test("illustrative downlights have narrower beams and bounded light output",()=>{
 const a=previewBeam("downlight"),b=previewBeam("pendant");assert.ok(a.angle<b.angle);for(const v of [a,b,previewBeam("sconce")]){assert.ok(v.candela>0&&v.candela<150);assert.ok(v.range<=6&&v.penumbra>=0&&v.penumbra<=1);}
});
test("changing an independent wall finish preserves unrelated mounted cabinet geometry",()=>{
 const scene=new THREE.Scene(),catalogue=createCatalogueScene(scene),source=demoCatalogueHosts(scene);
 const wall={proposalId:"w",scopeKey:"project",levelId:"ground",start:[0,0],end:[4,0],heightM:2.4,openings:[]};
 const group=displayWallDraft(wall);scene.add(group);const drafts=draftCatalogueHosts(wall,group);scene.updateMatrixWorld(true);
 const cabinet=searchCatalogue("vanity 600 polar")[0],paint=searchCatalogue("sage satin paint")[0],next=searchCatalogue("charcoal paint")[0];
 catalogue.sync(source,drafts,[]);
 const floorRay=new THREE.Raycaster(new THREE.Vector3(2,5,2),new THREE.Vector3(0,-1,0)),wallRay=new THREE.Raycaster(new THREE.Vector3(2,1.1,2),new THREE.Vector3(0,0,-1));
 let d=placeItem(emptyItemDraft("project"),"project","cab",cabinet.id,catalogue.candidate(floorRay,cabinet).hit,0);
 const host=catalogue.candidate(wallRay,paint).hit;assert.ok(host);
 d=placeItem(d,"project","first",paint.id,host,0);catalogue.sync(source,drafts,d.items);
 const floor=source.find(h=>h.id==="floor:demo-west").mesh,original=floor.children[0];assert.ok(original);
 d=placeItem(d,"project","second",next.id,host,0);catalogue.sync(source,drafts,d.items);
 assert.equal(floor.children[0],original);assert.ok(drafts[0].mesh.children.some(m=>m.material?.color?.getHex()===next.visual.color));
 catalogue.clear();
});
