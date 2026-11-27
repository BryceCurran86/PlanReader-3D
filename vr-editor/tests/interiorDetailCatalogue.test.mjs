import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import {ITEM_CATALOGUE,itemCanRotate} from "../src/itemCatalogue.ts";
import {createCatalogueFixture} from "../src/catalogueFixtures.ts";
import {contextChoices} from "../src/contextFinishes.ts";
test("appliance catalogue options render bounded named parts and compatible finishes",()=>{
 for(const shape of ["oven","fridge","dishwasher","cooktop","shower-screen"]){
  const entries=ITEM_CATALOGUE.filter(i=>i.visual.kind==="fixture"&&i.visual.shape===shape);
  assert.ok(entries.length>=2,shape);
  const item=entries[0],target=item.targets[0],{group,worktop}=createCatalogueFixture(item.visual,target);
  assert.ok(group.children.length>=3&&group.children.length<=10,shape);
  assert.ok(group.children.every(c=>c instanceof THREE.Mesh&&c.geometry.attributes.position.count>0));
  assert.equal(worktop,undefined);assert.ok(itemCanRotate(item));
  const box=new THREE.Box3().setFromObject(group),size=box.getSize(new THREE.Vector3());
  assert.ok(size.x<=item.visual.widthM+.01&&size.y<=item.visual.heightM+.01&&size.z<=item.visual.depthM+.01,shape);
  const entry={id:"fixture",itemId:item.id,target,hostId:"local",point:[0,0,0],normal:[0,1,0],side:1,turn:0};
  assert.ok(contextChoices({hit:entry,entry},item.group).length>=2);
 }
});
test("shower screen is translucent with actual retaining channels, no opaque block",()=>{
 const item=ITEM_CATALOGUE.find(i=>i.visual.kind==="fixture"&&i.visual.shape==="shower-screen");
 const {group}=createCatalogueFixture(item.visual,"floor"),pane=group.children.find(o=>o.name==="Shower safety-glass preview");
 assert.ok(pane.material.transparent&&!pane.material.depthWrite&&!pane.castShadow);
 assert.ok(group.children.some(o=>o.name==="Screen wall channel"));
});
