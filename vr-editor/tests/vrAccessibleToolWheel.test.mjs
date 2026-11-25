import test from "node:test";
import assert from "node:assert/strict";
import {displayedMenuAction,menuButtonAt,radialSector,thumbstickSector} from "../src/toolWheelInput.ts";
import {buildMenuLayout,EMPTY_ITEM_BROWSER} from "../src/catalogueMenu.ts";
import {EMPTY_BUILD} from "../src/buildPlacement.ts";
const q={selectedWall:null,gridM:.05,axis:"auto",nudgeM:.05,pinned:false,help:false,deleteArmed:false,radial:true};
const layout=buildMenuLayout(EMPTY_BUILD,"ground",EMPTY_ITEM_BROWSER,undefined,false,0,"","finished",false,undefined,undefined,q);
test("every sector is selectable across its whole ring, and disabled tools are never activated",()=>{
 for(let i=0;i<8;i++)for(const radius of [.35,.6,.95])for(const shift of [-.3,0,.3]){
  const a=i*Math.PI/4-Math.PI/2+shift;
  const x=Math.cos(a)*radius,y=Math.sin(a)*radius;
  assert.equal(radialSector(x,y),i);
  assert.equal(menuButtonAt(layout,330+x*330,330+y*330),layout.buttons[i].disabled?-1:i);
 }
 assert.equal(menuButtonAt(layout,330,330),8);
 assert.equal(menuButtonAt(layout,0,0),-1);
});
test("right stick supports all eight directions without tiny targets and respects dead zone",()=>{
 for(let i=0;i<8;i++){
  const a=i*Math.PI/4-Math.PI/2;
  assert.equal(thumbstickSector([Math.cos(a)*.8,Math.sin(a)*.8]),i);
 }
 assert.equal(thumbstickSector([.1,.1]),-1);
 assert.equal(thumbstickSector([0,0]),-1);
});
test("detailed buttons tolerate modest edge misses but never activate a disabled control",()=>{
 const l={...layout,radial:false,buttons:[{...layout.buttons[0],x:10,y:10,w:100,h:50},{...layout.buttons[1],x:130,y:10,w:100,h:50,disabled:true}]};
 assert.equal(menuButtonAt(l,115,35),0);
 assert.equal(menuButtonAt(l,125,35),-1);
 assert.equal(menuButtonAt(l,140,35),-1);
 assert.equal(menuButtonAt(l,300,300),-1);
});

test("visible menu dispatch rejects stale, disabled, moved or hidden targets",()=>{
 const index=layout.buttons.findIndex(b=>!b.disabled);
 assert.ok(index>=0);
 const button=layout.buttons[index];
 const modify=change=>({...layout,buttons:layout.buttons.map((b,i)=>i===index?{...b,...change}:b)});
 assert.deepEqual(displayedMenuAction(layout,structuredClone(layout),index),button.action);
 assert.equal(displayedMenuAction(null,layout,index),null);
 assert.equal(displayedMenuAction(layout,layout,-1),null);
 assert.equal(displayedMenuAction(layout,layout,0.5),null);
 assert.equal(displayedMenuAction(layout,{...layout,width:layout.width+1},index),null);
 assert.equal(displayedMenuAction(layout,{...layout,radial:false},index),null);
 assert.equal(displayedMenuAction(layout,modify({disabled:true}),index),null);
 assert.equal(displayedMenuAction(modify({disabled:true}),layout,index),null);
 assert.equal(displayedMenuAction(layout,modify({x:button.x+1}),index),null);
 assert.equal(displayedMenuAction(layout,modify({action:{area:"quest",action:"hide-tools"}}),index),null);
 assert.deepEqual(displayedMenuAction(layout,{...layout,note:"New status"},index),button.action);
});
