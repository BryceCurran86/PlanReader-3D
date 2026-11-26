import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import {applyMaterialDetailBudget,ownedDetailTextures} from "../src/materialQuality.ts";
import {photoTexture} from "../src/architecturalAssets.ts";
test("performance mode suppresses optional texture samples but restores all maps and preserves disposal ownership",()=>{
 const colour=new THREE.Texture(),normal=new THREE.Texture(),roughness=new THREE.Texture(),bump=new THREE.Texture();
 const m=new THREE.MeshStandardMaterial({map:colour,normalMap:normal,roughnessMap:roughness,bumpMap:bump});
 const mesh=new THREE.Mesh(new THREE.BoxGeometry(),m);
 applyMaterialDetailBudget(mesh,false);
 assert.equal(m.map,colour);assert.equal(m.normalMap,null);assert.equal(m.roughnessMap,null);assert.equal(m.bumpMap,null);
 assert.deepEqual(ownedDetailTextures(m),new Set([colour,normal,roughness,bump]));
 applyMaterialDetailBudget(mesh,false);applyMaterialDetailBudget(mesh,true);
 assert.equal(m.normalMap,normal);assert.equal(m.roughnessMap,roughness);assert.equal(m.bumpMap,bump);
 mesh.geometry.dispose();m.dispose();for(const t of ownedDetailTextures(m))t.dispose();
});
test("photo wrappers share a decoded source but keep independent sampler/disposal ownership",async()=>{
 const oldDoc=globalThis.document,oldImage=globalThis.Image;
 let loads=0;
 globalThis.document={baseURI:"http://localhost/",documentElement:{setAttribute(){}},createElement(){return {width:1,height:1,getContext(){return {fillRect(){},drawImage(){}};}};}};
 globalThis.Image=class{naturalWidth=1024;naturalHeight=1024;set src(_){loads++;queueMicrotask(()=>this.onload());}};
 try{
  const a=photoTexture("plaster-normal.jpg"),b=photoTexture("plaster-normal.jpg");
  assert.notEqual(a,b);await new Promise(r=>setImmediate(r));
  assert.equal(loads,1);assert.equal(a.source,b.source);assert.equal(a.image.width,1024);
  a.repeat.set(2,3);assert.deepEqual(b.repeat.toArray(),[1,1]);
  a.dispose();assert.equal(b.image.width,1024);b.dispose();
 }finally{if(oldDoc===undefined)delete globalThis.document;else globalThis.document=oldDoc;if(oldImage===undefined)delete globalThis.Image;else globalThis.Image=oldImage;}
});
