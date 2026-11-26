import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import {architraveMitres} from "../src/architraveMitres.ts";
const spec={kind:"trim",profile:"square",widthM:.09,depthM:.018,color:0xffffff};
test("architrave head and jambs share inner and outer corner coordinates",()=>{
 const group=architraveMitres(new THREE.Vector3(0,2,0),new THREE.Vector3(1,2,0),0,new THREE.Vector3(0,0,1),spec);
 assert.equal(group.children.length,3);
 const has=(mesh,x,y)=>{const p=mesh.geometry.getAttribute("position");return Array.from({length:p.count},(_,i)=>Math.abs(p.getX(i)-x)<1e-6&&Math.abs(p.getY(i)-y)<1e-6).some(Boolean);};
 for(const [jamb,inner,outer] of [[group.children[0],0,-.09],[group.children[1],1,1.09]]){
 assert.ok(has(jamb,inner,2)&&has(group.children[2],inner,2));
 assert.ok(has(jamb,outer,2.09)&&has(group.children[2],outer,2.09));
 }
});
test("invalid opening produces no nominal trim",()=>{
 assert.equal(architraveMitres(new THREE.Vector3(0,2,0),new THREE.Vector3(0,2,0),0,new THREE.Vector3(0,0,1),spec).children.length,0);
});
