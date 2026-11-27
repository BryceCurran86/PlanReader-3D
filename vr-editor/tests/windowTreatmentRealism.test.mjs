import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import {createOpeningStyle} from "../src/extensionGeometry.ts";
import {drapedCurtainGeometry,createWindowTreatment} from "../src/windowTreatmentGeometry.ts";
test("curtains are continuous pleated fabric with bounded mesh count",()=>{
 for(const style of ["curtain","sheer"]){
  const g=createOpeningStyle({kind:"opening-style",type:"covering",style,color:0xded6c8},1.5,1.2);
  assert.equal(g.children.length,3);
  for(const p of g.children.slice(1)){
   assert.equal(p.name,"Pleated fabric panel");assert.ok(p.geometry.index.count>100);assert.ok(p.material.map&&p.material.bumpMap);
   assert.equal(p.material.transparent,style==="sheer");assert.equal(p.material.depthWrite,style!=="sheer");
   p.geometry.computeBoundingBox();assert.ok(p.geometry.boundingBox.max.z-p.geometry.boundingBox.min.z>.05);
  }
 }
 const g=drapedCurtainGeometry(20,10,.036,1000);assert.ok(g.attributes.position.count<=193*9);
});
test("blind slats use one bounded instance batch and remain within opening envelope",()=>{
 for(const style of ["vertical","venetian","roman","shutter"]){
  const g=createWindowTreatment({kind:"opening-style",type:"covering",style,color:0xbcb9b0},1.5,1.2);
  const slats=g.children.find(o=>o instanceof THREE.InstancedMesh);assert.ok(slats);assert.ok(slats.count<=80);assert.ok(g.children.length<=3);
  const bounds=new THREE.Box3().setFromObject(g);assert.ok(bounds.max.x-bounds.min.x<1.8);
 }
 const roller=createWindowTreatment({kind:"opening-style",type:"covering",style:"roller",color:0xffffff},1.5,1.2);
 assert.ok(roller.children.some(o=>o.name==="Roller tube"));assert.ok(roller.children.some(o=>o.name==="Bottom weight"));
 assert.equal(createWindowTreatment({kind:"opening-style",type:"covering",style:"roller",color:0xffffff},NaN,1).children.length,0);
});
