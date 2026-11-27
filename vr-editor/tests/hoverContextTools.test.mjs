import test from "node:test";
import assert from "node:assert/strict";
import {HoverToolDwell} from "../src/hoverToolDwell.ts";
import {contextTargetKey,localContextTarget} from "../src/contextFinishes.ts";
import {buildMenuLayout,EMPTY_ITEM_BROWSER} from "../src/catalogueMenu.ts";
import {starterBuild,starterManifest} from "../src/starterHouse.ts";
import {ITEM_CATALOGUE} from "../src/itemCatalogue.ts";
const b=starterBuild(starterManifest());
const hit=(hostId,target)=>({hostId,target,point:[1,1,1],normal:[0,0,1],side:1});
const menu=(c,g=null)=>buildMenuLayout(b,"ground",EMPTY_ITEM_BROWSER,undefined,false,0,"","finished",false,undefined,undefined,{finishContext:c,finishGroup:g,hoverContext:true});
test("stable hover opens once; pointer jitter and same target dismissal do not reopen",()=>{
 const d=new HoverToolDwell();assert.equal(d.observe("wall",0),false);assert.equal(d.observe("ceiling",200),false);assert.equal(d.observe("wall",300),false);assert.equal(d.observe("wall",749),false);assert.equal(d.observe("wall",750),true);assert.equal(d.observe("wall",900),false);
 d.dismiss("wall");assert.equal(d.observe("wall",2000),false);d.observe(null,2100);d.observe("wall",2200);assert.equal(d.observe("wall",2650),true);
});
test("object context keys retain target identity instead of tracking every ray coordinate",()=>{
 const a={hit:hit("draft-wall:front","wall")};assert.equal(contextTargetKey(a),contextTargetKey({hit:{...a.hit,point:[9,1,2]}}));assert.notEqual(contextTargetKey(a),contextTargetKey({hit:{...a.hit,side:-1}}));
 assert.deepEqual(localContextTarget(a),{kind:"wall",id:"front"});assert.deepEqual(localContextTarget({hit:hit("draft-ceiling:living-ceiling","ceiling")}),{kind:"ceiling",id:"living-ceiling"});
 assert.equal(localContextTarget({hit:hit("wall:source","wall")}),null);
});
test("hover toolbox offers matching geometry controls, finishes and guarded placement actions",()=>{
 const wall=menu({hit:hit("draft-wall:front","wall")},"paint");assert.ok(wall.buttons.some(b=>b.action.area==="context-edit"&&b.action.action==="wall"));assert.ok(wall.buttons.some(b=>b.action.area==="finish"&&b.action.action==="apply"));
 const ceiling=menu({hit:hit("draft-ceiling:living-ceiling","ceiling")},"paint");assert.ok(ceiling.buttons.some(b=>b.action.area==="context-edit"&&b.action.action==="stretch"));
 const opening=menu({hit:{...hit('opening:["front","entry"]',"opening"),opening:{door:true,widthM:.92,heightM:2.04}}});assert.ok(opening.buttons.some(b=>b.action.area==="context-edit"&&b.action.action==="opening"));
 const floor=menu({hit:hit("draft-floor:ground","floor")},"floors");assert.ok(floor.buttons.some(b=>b.action.area==="context-edit"&&b.action.action==="slab"));
 const source=menu({hit:hit("wall:source","wall")},"paint");assert.ok(!source.buttons.some(b=>b.action.area==="context-edit"));
 const tap=ITEM_CATALOGUE.find(i=>i.group==="tapware"&&i.visual.kind==="fixture");const entry={...hit("worktop:cabinet","worktop"),id:"tap",itemId:tap.id,turn:0};const palette=menu({hit:entry,entry},"tapware");assert.ok(palette.buttons.some(b=>b.action.area==="context-edit"&&b.action.action==="remove"));assert.ok(palette.buttons.every(b=>b.y+b.h<=palette.height));
});
