import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import {ITEM_CATALOGUE} from "../src/itemCatalogue.ts";
import {contextGroups,contextChoices,sameFixtureFamily,refreshFinishContext,activeContextFinish} from "../src/contextFinishes.ts";
import {emptyItemDraft,placeItem,replaceItemFinish,undoItem,currentItemPlacements,localFloorHostId} from "../src/itemPlacement.ts";
import {buildMenuLayout,EMPTY_ITEM_BROWSER} from "../src/catalogueMenu.ts";
import {EMPTY_BUILD,STARTING_SIZES,updateBuild} from "../src/buildPlacement.ts";
import {starterManifest,starterBuild} from "../src/starterHouse.ts";
import {scopeKey} from "../src/reviewDraft.ts";
import {createOutdoorEnvironment} from "../src/outdoorEnvironment.ts";
import {displayWallDraft} from "../src/buildScene.ts";
const hit={hostId:"wall:1",target:"wall",point:[1,1,0],normal:[0,0,1],side:1};
const options={selectedWall:null,gridM:.05,axis:"auto",nudgeM:.05,pinned:true,help:false,deleteArmed:false,simpleHome:true,outdoor:true};
test("direct surface choices exclude fixtures, opening groups match door type",()=>{
 const groups=contextGroups({hit});
 assert.ok(groups.includes("paint"));assert.ok(groups.includes("substrates"));assert.ok(!groups.includes("electrical"));
 assert.ok(contextChoices({hit},"paint").length>24);
 const door={...hit,hostId:'opening:["w","d"]',target:"opening",opening:{door:true,widthM:.9,heightM:2.04}};
 const c={hit:door};
 assert.ok(contextGroups(c).includes("doors"));assert.ok(!contextGroups(c).includes("windows"));
 const menu=buildMenuLayout(EMPTY_BUILD,"ground",EMPTY_ITEM_BROWSER,undefined,false,0,"","finished",false,undefined,undefined,{...options,finishContext:c});
 assert.equal(menu.buttons.filter(b=>b.action.area==="finish"&&b.action.action==="hardware").length,4);
});
test("fixture finish changes preserve identity and location and can be undone",()=>{
 for(const group of ["tapware","cabinets","lights","electrical"]){
  const old=ITEM_CATALOGUE.find(i=>i.group===group&&i.visual.kind==="fixture");
  const variant=ITEM_CATALOGUE.find(i=>i.id!==old.id&&sameFixtureFamily(old,i));
  const incompatible=ITEM_CATALOGUE.find(i=>i.group===group&&!sameFixtureFamily(old,i));
  const entry={...hit,target:old.targets[0],id:"selected",itemId:old.id,turn:2};
  const draft={...emptyItemDraft("key"),items:[entry]};
  const ctx={hit:entry,entry};
  assert.deepEqual(contextGroups(ctx),[group]);assert.ok(contextChoices(ctx,group).some(i=>i.id===variant.id));
  const next=replaceItemFinish(draft,"key",entry.id,variant.id);
  assert.deepEqual(next.items[0],{...entry,itemId:variant.id});
  assert.equal(undoItem(next).items,draft.items);
  assert.equal(replaceItemFinish(draft,"key",entry.id,incompatible.id),draft);
 }
});
test("starter slab floor host is valid only inside closed draft outline",()=>{
 const scene=starterManifest(),build=starterBuild(scene),key=scopeKey(scene);
 const floor=ITEM_CATALOGUE.find(i=>i.group==="floors");
 const floorHit={hostId:localFloorHostId("ground"),target:"floor",point:[2,.002,2],normal:[0,1,0],side:1};
 const draft=placeItem(emptyItemDraft(key),key,"floor",floor.id,floorHit,0);
 assert.equal(currentItemPlacements(draft.items,scene,build.walls,false,build.ceilings).length,1);
 assert.equal(currentItemPlacements([{...draft.items[0],point:[30,.002,30]}],scene,build.walls,false,build.ceilings).length,0);
 assert.equal(currentItemPlacements(draft.items,scene,build.walls.filter(w=>w.proposalId!=="front"),false,build.ceilings).length,0);
});
test("hardware is attached to moving local door and undo restores finish",()=>{
 const scene=starterManifest(),build=starterBuild(scene),key=scopeKey(scene);
 const wall=build.walls[0],opening=wall.openings.find(o=>o.openingKind==="door");
 const next=updateBuild(build,{kind:"set-door-hardware",proposalId:wall.proposalId,openingId:opening.openingId,finish:"matte-black"},key,"ground",STARTING_SIZES);
 const mesh=displayWallDraft(next.walls[0]);
 const leaf=mesh.children.find(c=>c.userData.catalogueDoorLeaf===opening.openingId);
 assert.equal(leaf.children.length,4);assert.equal(leaf.children[0].material.color.getHex(),0x292c2e);
 assert.equal(updateBuild(next,{kind:"undo"},key,"ground",STARTING_SIZES).walls,build.walls);
});
test("outdoor scene is lightweight, switchable and separate from design",()=>{
 const scene=new THREE.Scene(),outdoor=createOutdoorEnvironment(scene);
 outdoor.update(true,false,0,0);assert.equal(scene.children.length,2);assert.ok(scene.children.every(o=>o.visible));
 outdoor.update(false,false,0,0);assert.ok(scene.children.every(o=>!o.visible));outdoor.dispose();
});
test("new quick home uses large rectangular buttons and keeps controls discoverable",()=>{
 const menu=buildMenuLayout(EMPTY_BUILD,"ground",EMPTY_ITEM_BROWSER,undefined,false,0,"","finished",false,undefined,undefined,options);
 assert.ok(!menu.radial);assert.ok(menu.buttons.length<=12);
 assert.ok(menu.buttons.some(b=>b.label==="Resize footprint"));
 assert.ok(menu.buttons.some(b=>b.action.area==="slab"));
 assert.ok(menu.buttons.every(b=>b.h>=65));
 assert.ok(menu.buttons.some(b=>b.label.includes("Grass & sky")));
});

test("context palette follows committed replacement and refuses a removed fixture",()=>{
 const old=ITEM_CATALOGUE.find(i=>i.group==="tapware"&&i.visual.kind==="fixture");
 const variant=ITEM_CATALOGUE.find(i=>i.id!==old.id&&sameFixtureFamily(old,i));
 const entry={...hit,target:old.targets[0],id:"selected",itemId:old.id,turn:0};
 const ctx={hit:entry,entry},live={...entry,itemId:variant.id};
 assert.equal(activeContextFinish(ctx,"tapware",[live]),variant.id);
 assert.equal(refreshFinishContext(ctx,[live]).entry,live);
 assert.equal(refreshFinishContext(ctx,[]),null);
 assert.equal(refreshFinishContext(ctx,[{...live,hostId:"other"}]),null);
 const menu=buildMenuLayout(EMPTY_BUILD,"ground",EMPTY_ITEM_BROWSER,undefined,false,0,"","finished",false,undefined,undefined,{...options,finishContext:ctx,finishGroup:"tapware",activeFinishId:variant.id});
 assert.equal(menu.buttons.find(b=>b.action.itemId===variant.id)?.active,true);
 assert.equal(menu.buttons.find(b=>b.action.itemId===old.id)?.active,false);
});
test("surface palette highlights the current same-side finish and ignores opposite face",()=>{
 const [a,b]=ITEM_CATALOGUE.filter(i=>i.group==="paint"&&i.targets.includes("wall"));
 const first={...hit,id:"a",itemId:a.id,turn:0};
 const other={...hit,id:"b",itemId:b.id,turn:0,side:-1};
 assert.equal(activeContextFinish({hit},"paint",[first,other]),a.id);
 assert.equal(activeContextFinish({hit},"paint",[other]),undefined);
});

test("quick and selected toolboxes remain bounded and advanced controls remain reachable",()=>{
 const scene=starterManifest(),build=starterBuild(scene);
 const layout=(q)=>buildMenuLayout(build,"ground",EMPTY_ITEM_BROWSER,undefined,false,0,"","finished",false,undefined,undefined,q);
 const home=layout(options),wall=layout({...options,selectedWall:build.walls[0],dragGain:3});
 const advanced=layout({...options,simpleHome:false,compact:true,dragGain:3});
 for(const menu of [home,wall,advanced]){
  for(const b of menu.buttons){assert.ok(b.x>=0&&b.y>=0&&b.x+b.w<=menu.width&&b.y+b.h<=menu.height,b.label);}
  for(let i=0;i<menu.buttons.length;i++)for(let j=i+1;j<menu.buttons.length;j++){
   const a=menu.buttons[i],b=menu.buttons[j];
   assert.ok(a.x+a.w<=b.x||b.x+b.w<=a.x||a.y+a.h<=b.y||b.y+b.h<=a.y,a.label+" overlaps "+b.label);
  }
 }
 assert.ok(home.buttons.length<=12&&wall.buttons.length<=12);
 for(const menu of [wall,advanced])assert.ok(menu.buttons.some(b=>b.label==="Drag speed: 3×"&&b.action.action==="drag-gain"));
 assert.ok(advanced.buttons.some(b=>b.action.action==="home"));
 assert.ok(advanced.buttons.some(b=>b.action.action==="recenter"));
});
