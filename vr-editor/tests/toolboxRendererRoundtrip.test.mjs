import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import {createBuildOverlay,displayWallDraft} from "../src/buildScene.ts";
import {buildMenuLayout,EMPTY_ITEM_BROWSER,updateItemBrowser} from "../src/catalogueMenu.ts";
import {starterManifest,starterBuild} from "../src/starterHouse.ts";
import {createCatalogueScene,draftCatalogueHosts} from "../src/catalogueScene.ts";
import {searchCatalogue} from "../src/itemCatalogue.ts";
import {emptyItemDraft,placeItem} from "../src/itemPlacement.ts";
test("toolbox renderer publishes labels, keeps texture allocation and ray mapping through repeated submenu transitions",()=>{
 const previous=globalThis.document,canvases=[];
 globalThis.document={createElement(){
  const labels=[];const ctx={setTransform(){},clearRect(){labels.length=0;},fillRect(){},strokeRect(){},beginPath(){},arc(){},closePath(){},fill(){},stroke(){},fillText(label){labels.push(label);}};
  const canvas={width:0,height:0,getContext(){return ctx;},labels};canvases.push(canvas);return canvas;
 }};
 const scene=new THREE.Scene();
 let overlay;
 try{
  overlay=createBuildOverlay(scene);
  const camera=new THREE.PerspectiveCamera();camera.position.set(0,1.65,2);camera.lookAt(0,1.65,0);camera.updateMatrixWorld(true);
  const state=starterBuild(starterManifest());
  const mk=(browser,quest)=>buildMenuLayout(state,"ground",browser,undefined,false,0,"","finished",false,undefined,undefined,quest);
  const home=mk(EMPTY_ITEM_BROWSER,{simpleHome:true}),groups=mk(updateItemBrowser(EMPTY_ITEM_BROWSER,{kind:"groups"}),{simpleHome:true}),products=mk(updateItemBrowser(EMPTY_ITEM_BROWSER,{kind:"choose-group",index:0}),{simpleHome:true});
  const finish=mk(EMPTY_ITEM_BROWSER,{finishContext:{hit:{target:"wall"}},finishGroup:"paint"});
  overlay.positionMenu(camera,true,true);
  const menu=scene.children.find(o=>o.renderOrder===23);
  const texture=menu.material.map,canvas=canvases[0],size=[canvas.width,canvas.height];
  for(const layout of [home,groups,products,finish,groups,home,finish]){
   overlay.hideMenu();overlay.sizeMenu(layout);
   assert.equal(overlay.drawMenu(layout,-1),true);
   assert.deepEqual([canvas.width,canvas.height],size);
   assert.equal(menu.material.map,texture);
   assert.ok(canvas.labels.includes(layout.title));
   for(const b of layout.buttons)assert.ok(canvas.labels.includes(b.label),b.label);
   overlay.showMenu();scene.updateMatrixWorld(true);
   const i=layout.buttons.findIndex(b=>!b.disabled),b=layout.buttons[i];
   const world=menu.localToWorld(new THREE.Vector3((b.x+b.w/2)/layout.width-.5,.5-(b.y+b.h/2)/layout.height,0));
   const ray=new THREE.Raycaster(camera.position,world.clone().sub(camera.position).normalize());
   assert.equal(overlay.menuHit(ray,layout)?.index,i);
   assert.deepEqual(overlay.menuHit(ray,layout)?.action,b.action);
   overlay.hideMenu();assert.equal(overlay.menuHit(ray,layout),null);
  }
 }finally{overlay?.dispose();if(previous===undefined)delete globalThis.document;else globalThis.document=previous;}
});
test("context selection on a physical draft wall applies a finish to the same host and permits replacement",()=>{
 const scene=new THREE.Scene(),catalogue=createCatalogueScene(scene);
 const wall={proposalId:"w",scopeKey:"project",levelId:"ground",start:[0,0],end:[4,0],heightM:2.4,openings:[]};
 const group=displayWallDraft(wall);scene.add(group);const hosts=draftCatalogueHosts(wall,group);
 scene.updateMatrixWorld(true);catalogue.sync([],hosts,[]);
 const ray=new THREE.Raycaster(new THREE.Vector3(2,1.1,2),new THREE.Vector3(0,0,-1));
 const context=catalogue.contextAt(ray);assert.ok(context);assert.equal(context.hit.hostId,"draft-wall:w");
 const paint=searchCatalogue("sage satin paint")[0],next=searchCatalogue("charcoal paint")[0];
 assert.ok(paint);assert.ok(next);
 let draft=placeItem(emptyItemDraft("project"),"project","first",paint.id,context.hit,0);
 assert.equal(draft.items.length,1);
 catalogue.sync([],hosts,draft.items);scene.updateMatrixWorld(true);
 const first=hosts[0].mesh.children.find(o=>o.material?.color?.getHex()===paint.visual.color);assert.ok(first);
 draft=placeItem(draft,"project","second",next.id,context.hit,0);
 assert.equal(draft.items.length,1);assert.equal(draft.items[0].hostId,context.hit.hostId);
 catalogue.sync([],hosts,draft.items);scene.updateMatrixWorld(true);
 assert.ok(hosts[0].mesh.children.some(o=>o.material?.color?.getHex()===next.visual.color));
 catalogue.clear();
});
