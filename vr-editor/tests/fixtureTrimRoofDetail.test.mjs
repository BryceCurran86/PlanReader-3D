import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import {createCatalogueFixture} from "../src/catalogueFixtures.ts";
import {trimRun} from "../src/catalogueGeometry.ts";
import {roofComponentMesh} from "../src/roofComponentGeometry.ts";
const fixture={kind:"fixture",shape:"cabinet",widthM:.9,heightM:.9,depthM:.6,count:2,color:0xeeeeee,metalness:0};
test("cabinet retains worktop and gains physical pull posts",()=>{
 const {group,worktop}=createCatalogueFixture(fixture,"floor");
 assert.ok(worktop);assert.equal(group.children.length,13);
 assert.ok(group.children.every(o=>o.geometry.attributes.position.count>0));
});
test("tap aerator and basin waste are visible mesh details",()=>{
 for(const shape of ["gooseneck","basin"]){
 const {group}=createCatalogueFixture({...fixture,shape,widthM:.1,heightM:.3,depthM:.2,count:1},"worktop");
 assert.ok(group.children.length>=4);
 if(shape==="basin"){
  for(const name of ["Ceramic bowl shell","Bowl drain","Waste flange","Waste plug"])assert.ok(group.children.some(o=>o.name===name),name);
  const flange=group.children.find(o=>o.name==="Waste flange");
  assert.equal(flange.geometry.type,"TorusGeometry");
  assert.ok(Math.abs(flange.rotation.x+Math.PI/2)<1e-9);
 }
 }
});
test("trim normalises skewed basis and rejects invalid dimensions",()=>{
 const a=new THREE.Vector3(),b=new THREE.Vector3(2,0,0),across=new THREE.Vector3(1,2,0),normal=new THREE.Vector3(1,1,3);
 const spec={kind:"trim",profile:"square",widthM:.09,depthM:.018,color:0xffffff};
 const mesh=trimRun(a,b,across,normal,spec);assert.ok(mesh);
 mesh.geometry.computeBoundingBox();
 const size=mesh.geometry.boundingBox.getSize(new THREE.Vector3());
 assert.ok(Math.abs(size.x-2)<1e-6&&Math.abs(size.y-.09)<1e-6&&Math.abs(size.z-.018)<1e-6);
 assert.equal(trimRun(a,b,across,normal,{...spec,widthM:0}),null);
});
test("fascia and gutter lips remain attached to original roof edge",()=>{
 const edge={from:[0,3,0],to:[4,3,0],interior:[2,3,2]};
 for(const [component,profile,count] of [["fascia","standard",2],["gutter","quad",4]]){
 const group=roofComponentMesh(edge,{component,profile,color:0x555555});
 assert.equal(group.children.length,count);
 assert.ok(group.children.every(o=>o.castShadow&&o.receiveShadow));
 assert.deepEqual(group.position.toArray(),[2,3,0]);
 }
});
