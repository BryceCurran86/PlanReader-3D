import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import {createSiteFence,validSiteBounds,validFence,DEFAULT_FENCE,FENCE_STYLES,fenceTexture} from "../src/siteFence.ts";
test("visual site fence is bounded, independent and reuses four lightweight surfaces",()=>{
 const scene=new THREE.Scene(),fence=createSiteFence(scene),bounds={minX:-5,maxX:15,minZ:0,maxZ:30};
 assert.ok(validSiteBounds(bounds));assert.ok(!validSiteBounds({...bounds,maxX:-6}));assert.ok(!validSiteBounds({...bounds,maxZ:Infinity}));
 assert.ok(!validFence({...DEFAULT_FENCE,heightM:20}));assert.ok(!validFence({...DEFAULT_FENCE,color:"invalid"}));
 fence.update(bounds,DEFAULT_FENCE,true);
 const group=scene.children[0];assert.equal(group.children.length,4);
 assert.deepEqual(group.children.map(m=>m.geometry.parameters.width),[20,30,20,30]);
 const first=group.children[0];fence.update(bounds,DEFAULT_FENCE,true);assert.equal(group.children[0],first);
 for(const style of FENCE_STYLES){
  fence.update(bounds,{style,heightM:1.5,color:"#aabbcc"},true);
  assert.equal(group.children.length,4);assert.ok(group.children.every(m=>m.geometry.parameters.height===1.5&&!m.castShadow));
  const t=fenceTexture(style);assert.equal(t.image.data.length,64*64*4);t.dispose();
 }
 fence.update(null,DEFAULT_FENCE,true);assert.equal(group.visible,false);
 fence.dispose();assert.equal(scene.children.length,0);
});
