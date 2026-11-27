import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import {starterBuild,starterManifest} from "../src/starterHouse.ts";
import {doorJunctionDetails} from "../src/doorJunctionDetails.ts";
import {displayWallDraft} from "../src/buildScene.ts";
const b=starterBuild(starterManifest()),w=b.walls[0],d=w.openings.find(o=>o.openingKind==="door");
test("fine door detail stays on frame and follows current opening dimensions",()=>{
 const original=JSON.stringify(w),parts=doorJunctionDetails(w,d);
 assert.equal(parts.length,2);assert.equal(parts[0].name,"Door jamb stops");
 assert.ok(parts.every(p=>p.userData.nominalOpeningFrame&&p.geometry.attributes.position.count>0));
 const bounds=new THREE.Box3().setFromObject(parts[0]);
 assert.ok(bounds.min.x>=d.offsetM&&bounds.max.x<=d.offsetM+d.widthM);assert.ok(bounds.max.y<=d.heightM);
 const moved={...d,offsetM:d.offsetM+.2};const next=doorJunctionDetails(w,moved);
 const translated=new THREE.Box3().setFromObject(next[0]);assert.ok(Math.abs(translated.min.x-bounds.min.x-.2)<1e-5);
 assert.equal(JSON.stringify(w),original);
});
test("sliding/garage details do not invent swing hinges; integrated leaf retains its hardware",()=>{
 const sliding=doorJunctionDetails(w,{...d,doorMechanism:"sliding"});assert.equal(sliding.length,1);assert.ok(!sliding.some(p=>p.name==="Door jamb stops"));
 assert.deepEqual(doorJunctionDetails(w,{...d,doorMechanism:"garage"}),[]);
 const group=displayWallDraft(w),leaf=group.children.find(p=>p.userData.catalogueDoorLeaf===d.openingId);
 assert.ok(leaf);assert.equal(leaf.children.filter(p=>p.name==="Radiused door lever").length,2);
 assert.ok(group.children.some(p=>p.name==="Door jamb stops"));
});
