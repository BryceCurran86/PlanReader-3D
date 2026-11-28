import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import {validSlab,slabArea,slabVolume,slabCorners,readSlabs,createIndependentSlabs} from "../src/independentSlabs.ts";
test("independent slab dimensions, volume and renderer follow the same geometry",()=>{
 const s={id:"slab1",kind:"garage",levelId:"ground",x:2,z:3,widthM:6,depthM:4,topM:.1,thicknessMm:150};
 assert.ok(validSlab(s));assert.equal(slabArea(s),24);assert.equal(slabVolume(s),3.6);
 assert.deepEqual(slabCorners(s),[[2,3],[8,3],[8,7],[2,7]]);
 assert.deepEqual(readSlabs([s],new Set(["ground"])),[s]);assert.throws(()=>readSlabs([s,s]));assert.throws(()=>readSlabs([{...s,widthM:-1}]));assert.throws(()=>readSlabs([s],new Set(["other"])));
 const scene=new THREE.Scene(),view=createIndependentSlabs(scene);
 view.update([s],"ground");assert.equal(scene.children[0].children.length,1);
 const mesh=scene.children[0].children[0];assert.equal(mesh.position.x,5);assert.equal(mesh.position.z,5);assert.equal(mesh.geometry.parameters.height,.15);
 view.update([s],"other");assert.equal(scene.children[0].children.length,0);view.dispose();assert.equal(scene.children.length,0);
});
