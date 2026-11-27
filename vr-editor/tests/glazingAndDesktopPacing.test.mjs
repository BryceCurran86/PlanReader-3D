import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import {starterBuild,starterManifest} from "../src/starterHouse.ts";
import {windowDetailVisual,nominalDoorSlab} from "../src/openingFinishVisual.ts";
import {displayWallDraft} from "../src/buildScene.ts";
import {shouldRenderDesktopFrame} from "../src/visualRealism.ts";
const wall=starterBuild(starterManifest()).walls[0];
const win=wall.openings.find(o=>o.openingKind==="window"),door=wall.openings.find(o=>o.openingKind==="door");
test("window detail has bounded batch count, seals and recessed reflective pane",()=>{
 const original=JSON.stringify(wall),parts=windowDetailVisual(wall,win);
 assert.equal(parts.length,2);assert.equal(parts[0].count,4);assert.equal(parts[1].count,3);
 assert.ok(parts.every(p=>p instanceof THREE.InstancedMesh&&p.userData.nominalOpeningFrame));
 const mesh=displayWallDraft(wall).children.find(p=>p.userData.catalogueWindow);assert.ok(mesh);mesh.geometry.computeBoundingBox();
 const b=mesh.geometry.boundingBox;assert.ok(b.max.x-b.min.x<win.widthM);assert.ok(b.max.y-b.min.y<win.heightM);
 assert.ok(mesh.material.roughness<.1&&!mesh.material.depthWrite);
 assert.equal(JSON.stringify(wall),original);
});
test("bevelled door retains original slab envelope",()=>{
 const mesh=nominalDoorSlab(wall,door);mesh.geometry.computeBoundingBox();
 const size=mesh.geometry.boundingBox.getSize(new THREE.Vector3());
 assert.ok(Math.abs(size.x-(door.widthM-.014))<1e-5);
 assert.ok(Math.abs(size.y-(door.heightM-.014))<1e-5);
 assert.ok(Math.abs(size.z-.038)<1e-5);
});
test("desktop rendering yields between frames and never caps XR",()=>{
 assert.equal(shouldRenderDesktopFrame(0,-Infinity,"high",false),true);
 assert.equal(shouldRenderDesktopFrame(16,0,"balanced",false),false);
 assert.equal(shouldRenderDesktopFrame(33,0,"balanced",false),true);
 assert.equal(shouldRenderDesktopFrame(20,0,"performance",false),false);
 assert.equal(shouldRenderDesktopFrame(1,0,"performance",true),true);
});
