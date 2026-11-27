import test from "node:test";
import assert from "node:assert/strict";
import {MENU_ATLAS_SIZE,menuAtlasScale} from "../src/menuAtlas.ts";
import {buildMenuLayout,EMPTY_ITEM_BROWSER,updateItemBrowser} from "../src/catalogueMenu.ts";
import {starterManifest,starterBuild} from "../src/starterHouse.ts";
import {displayedMenuAction,menuButtonAt} from "../src/toolWheelInput.ts";
test("main, categories, products and finish palettes map to a constant GPU atlas",()=>{
 const build=starterBuild(starterManifest());
 const mk=(browser,quest)=>buildMenuLayout(build,"ground",browser,undefined,false,0,"","finished",false,undefined,undefined,quest);
 const home=mk(EMPTY_ITEM_BROWSER,{simpleHome:true});
 const groups=mk(updateItemBrowser(EMPTY_ITEM_BROWSER,{kind:"groups"}),{simpleHome:true});
 const items=mk(updateItemBrowser(EMPTY_ITEM_BROWSER,{kind:"choose-group",index:0}),{simpleHome:true});
 const finish=mk(EMPTY_ITEM_BROWSER,{finishContext:{hit:{target:"wall"}},finishGroup:"paint"});
 for(const l of [home,groups,items,finish]){
  const [sx,sy]=menuAtlasScale(l.width,l.height);
  assert.ok(Math.abs(sx*l.width-MENU_ATLAS_SIZE)<1e-8);
  assert.ok(Math.abs(sy*l.height-MENU_ATLAS_SIZE)<1e-8);
  for(const [i,b] of l.buttons.entries())if(!b.disabled){
   assert.ok(b.label.length);
   assert.equal(menuButtonAt(l,b.x+b.w/2,b.y+b.h/2),i);
  }
 }
 assert.notEqual(home.title,groups.title);
 assert.equal(displayedMenuAction(home,groups,0),null);
 assert.equal(displayedMenuAction(null,items,0),null);
 assert.equal(menuAtlasScale(0,400),null);
});
