import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import {starterBuild,starterManifest} from "../src/starterHouse.ts";
import {fineTrimMesh,corniceContactRuns,corniceMesh} from "../src/fineConstructionTrim.ts";
import {wallCornerJoins} from "../src/wallCornerJoin.ts";
import {windowDetailVisual} from "../src/openingFinishVisual.ts";
import {createCatalogueFixture} from "../src/catalogueFixtures.ts";
const b=starterBuild(starterManifest()),w=b.walls[0],joins=wallCornerJoins(b.walls);
test("profiled trim retains clipped layout and real mitered frame geometry",()=>{
 const before=JSON.stringify(w),m=fineTrimMesh(w,joins.get(w.proposalId));
 assert.ok(m instanceof THREE.Mesh&&m.userData.illustrativeTrim);assert.ok(m.geometry.attributes.position.count>100);assert.ok(m.userData.trimLayout.length>4);
 assert.equal(JSON.stringify(w),before);
});
test("cornices follow real ceiling contact, omit gaps and mismatched heights",()=>{
 const runs=corniceContactRuns(w,b.ceilings);assert.ok(runs.length>0);
 const m=corniceMesh(w,runs,joins.get(w.proposalId));assert.ok(m.userData.nominalCornice);m.geometry.computeBoundingBox();assert.ok(m.geometry.boundingBox.max.y<=w.heightM+.001);
 assert.deepEqual(corniceContactRuns(w,b.ceilings.map(c=>({...c,heightM:c.heightM+.2}))),[]);
 assert.deepEqual(corniceContactRuns(w,[]),[]);
});
test("external windows get tracks and flashings without altering aperture",()=>{
 const o=w.openings.find(o=>o.openingKind==="window"),before=JSON.stringify(o),parts=windowDetailVisual(w,o);
 assert.equal(parts.length,2);assert.equal(parts[0].count,4);assert.ok(parts[1].count>=8);
 assert.equal(JSON.stringify(o),before);
});
test("drawer unit has horizontal independent fronts and preserves its worktop",()=>{
 const spec={kind:"fixture",shape:"cabinet",widthM:.9,heightM:.9,depthM:.59,count:3,color:0xeeeeee,metalness:0};
 const {group,worktop}=createCatalogueFixture(spec,"floor"),fronts=group.children.filter(c=>c.name==="Radiused drawer front");
 assert.equal(fronts.length,3);assert.ok(fronts.every(c=>c.position.x===0));assert.equal(new Set(fronts.map(c=>c.position.y)).size,3);
 assert.ok(worktop&&group.children.includes(worktop));assert.equal(group.children.filter(c=>c.name==="Pull mounting post").length,6);
});
