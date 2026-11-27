import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import {createCatalogueFixture} from "../src/catalogueFixtures.ts";
import {fabricPixels,fabricUV} from "../src/fixtureFabric.ts";
import {applyMaterialDetailBudget,ownedDetailTextures} from "../src/materialQuality.ts";
import {createPresentationGarden} from "../src/presentationGarden.ts";
test("upholstery gets repeatable bounded tintable weave without new mesh draws",()=>{
 const p=fabricPixels();assert.equal(p.colour.length,64*64*4);assert.notDeepEqual(p.colour,p.relief);
 const spec={kind:"fixture",shape:"sofa",widthM:2.1,heightM:.82,depthM:.86,count:1,color:0xc5bba9,metalness:0};
 const {group}=createCatalogueFixture(spec,"floor");assert.equal(group.children.length,14);
 const material=group.children[0].material,bump=material.bumpMap;
 assert.ok(material.map&&bump);assert.ok(material.roughness>.9);
 const another=createCatalogueFixture({...spec,color:0x606365},"floor").group.children[0].material;
 assert.notEqual(another.map,material.map);assert.equal(another.map.image.data,material.map.image.data);
 applyMaterialDetailBudget(group,false);assert.equal(material.bumpMap,null);assert.ok(ownedDetailTextures(material).has(bump));
 applyMaterialDetailBudget(group,true);assert.equal(material.bumpMap,bump);
});
test("garden beds and paving are decorative, bounded and remain two instanced draws",()=>{
 const scene=new THREE.Scene(),garden=createPresentationGarden(scene);
 garden.update({minX:0,maxX:10,minZ:0,maxZ:8},true);
 const g=scene.children[0],a=g.children[0],b=g.children[1];assert.equal(g.children.length,2);
 assert.ok(a.count>35&&b.count>30);assert.ok(a.count<=a.instanceMatrix.count&&b.count<=b.instanceMatrix.count);
 const before=a.instanceMatrix.array.slice();garden.update({minX:0,maxX:10,minZ:0,maxZ:8},true);assert.deepEqual(a.instanceMatrix.array,before);
 garden.update({minX:-1,maxX:34,minZ:0,maxZ:35},true);assert.ok(a.count<=a.instanceMatrix.count&&b.count<=b.instanceMatrix.count);
 garden.update(null,true);assert.equal(g.visible,false);garden.dispose();assert.equal(scene.children.length,0);
});
