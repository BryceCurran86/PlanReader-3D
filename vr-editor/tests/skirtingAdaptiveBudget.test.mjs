import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import {skirtingEndCuts,applySkirtingCuts} from "../src/skirtingMitres.ts";
import {trimRun} from "../src/catalogueGeometry.ts";
import {adaptiveRenderQuality} from "../src/visualRealism.ts";
import {nearestPreviewLights} from "../src/lightingPreview.ts";
import {budgetMoney} from "../src/vrAssemblyStudy.ts";
test("skirting follows a local mitred wall face without modifying its centreline",()=>{
 const start=[0,0],end=[4,0],normal=new THREE.Vector3(0,0,1);
 const joins={end:{left:[3.93,.07],right:[4.07,-.07]}};
 const cuts=skirtingEndCuts(start,end,.07,normal,joins);
 assert.ok(Math.abs(cuts.end.offset+.07)<1e-6);
 assert.ok(Math.abs(cuts.end.slope+1)<1e-6);
 const a=new THREE.Vector3(),b=new THREE.Vector3(4,0,0);
 const mesh=trimRun(a,b,new THREE.Vector3(0,1,0),normal,{kind:"trim",profile:"square",widthM:.09,depthM:.018,color:0xffffff});
 applySkirtingCuts(mesh,a,b,normal,.018,cuts,true,true);
 const p=mesh.geometry.getAttribute("position");
 assert.ok(Array.from({length:p.count},(_,i)=>Math.abs(p.getX(i)-3.912)<1e-6&&Math.abs(p.getZ(i)-.018)<1e-6).some(Boolean));
 assert.deepEqual(end,[4,0]);
});
test("adaptive quality cannot exceed user preference",()=>{
 assert.equal(adaptiveRenderQuality("high",1),"balanced");
 assert.equal(adaptiveRenderQuality("balanced",0),"performance");
 assert.equal(adaptiveRenderQuality("performance",2),"performance");
 assert.equal(adaptiveRenderQuality("high",2),"high");
});
test("lighting selection retains distance, tie order and finite limits",()=>{
 const f=[{id:"b",position:[1,0,0]},{id:"a",position:[-1,0,0]},{id:"edge",position:[10,0,0]},{id:"outside",position:[10.01,0,0]},{id:"bad",position:[NaN,0,0]}];
 assert.deepEqual(nearestPreviewLights(f,[0,0,0]).map(x=>x.id),["a","b","edge"]);
});
test("cached currency formatter retains unknown and exact cents",()=>{
 assert.equal(budgetMoney(null),"Unpriced");
 assert.equal(budgetMoney(123456),"$1,234.56");
});
