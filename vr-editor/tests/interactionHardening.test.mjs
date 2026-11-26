import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import {wallCornerJoins} from "../src/wallCornerJoin.ts";
import {defaultWallAssembly} from "../src/wallProfiles.ts";
import {createPresentationGarden} from "../src/presentationGarden.ts";
import {createPhysicalToolTray} from "../src/physicalToolTray.ts";
import {detailPixels} from "../src/materialDetail.ts";
test("large independent walls do not suppress an unambiguous corner",()=>{
 const assembly={...defaultWallAssembly("external-timber"),exteriorSide:"right"};
 const wall=(id,start,end)=>({proposalId:id,start,end,scopeKey:"s",levelId:"ground",heightM:2.4,openings:[],assembly});
 const walls=[wall("front",[0,0],[4,0]),wall("right",[4,0],[4,3])];
 for(let i=0;i<600;i++)walls.push(wall("extra"+i,[100+i*3,0],[101+i*3,0]));
 const joins=wallCornerJoins(walls);assert.equal(joins.size,2);
 assert.ok(joins.get("front").end);assert.ok(joins.get("right").start);
});
test("garden handles maximum bounds, invalid bounds and teardown",()=>{
 const scene=new THREE.Scene(),garden=createPresentationGarden(scene);
 garden.update({minX:0,maxX:35,minZ:0,maxZ:35},true);
 const group=scene.children[0];assert.ok(group.visible);
 for(const m of group.children)assert.ok(m.count<=m.instanceMatrix.count);
 garden.update({minX:2,maxX:1,minZ:0,maxZ:3},true);assert.equal(group.visible,false);
 garden.dispose();assert.equal(scene.children.length,0);
});
test("tool tray rejects invalid dimensions and removes instances on disposal",()=>{
 const group=new THREE.Group(),tray=createPhysicalToolTray(group);
 tray.update({width:0,height:0,buttons:[],title:"",note:""});
 assert.equal(tray.keys.count,0);assert.equal(tray.samples.count,0);
 tray.dispose();assert.equal(group.children.length,0);
});
test("procedural textures reject unbounded allocation",()=>{
 for(const n of [0,-1,Infinity,513,1.5])assert.throws(()=>detailPixels("tile",n),RangeError);
 assert.equal(detailPixels("tile",32).albedo.length,32*32*4);
});
