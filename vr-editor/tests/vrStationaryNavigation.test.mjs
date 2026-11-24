import test from "node:test";
import assert from "node:assert/strict";
import {standardThumbstick,walkDelta,collisionLimitedStep,snapTurn,navigationOffset} from "../src/vrStationaryNavigation.ts";
import {buildMenuLayout,EMPTY_ITEM_BROWSER} from "../src/catalogueMenu.ts";
import {EMPTY_BUILD} from "../src/buildPlacement.ts";
const source=(axes,mapping="xr-standard")=>({targetRayMode:"tracked-pointer",gamepad:{mapping,axes}});
const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-7,`${a} != ${b}`);
test("standard sticks use explicit mapping and deadzone",()=>{
 assert.deepEqual(standardThumbstick(source([1,1,0.1,-.1])),[0,0]);
 assert.deepEqual(standardThumbstick(source([0,0,0,-1])),[0,-1]);
 assert.deepEqual(standardThumbstick(source([0,0,1,0],"unknown")),[0,0]);
 assert.deepEqual(standardThumbstick(source([1,1])),[0,0]);
 assert.deepEqual(standardThumbstick(source([0,0,NaN,0])),[0,0]);
});
test("walk follows heading, strafes, clamps stale frames and diagonal speed",()=>{
 const f=walkDelta([0,-1],[0,-1],2,.05);near(f[0],0);near(f[1],-.1);
 const right=walkDelta([1,0],[0,-1],2,1);near(right[0],.1);near(right[1],0);
 const rotated=walkDelta([0,-1],[1,0],1,.05);near(rotated[0],.05);
});
test("wall collision is conservative, slides and permits moving away",()=>{
 const w=[{start:[0,-5],end:[0,5]}];
 const cross=collisionLimitedStep([-.4,0],[.8,0],w);
 assert.ok(-.4+cross[0]<=-.25+1e-7);
 const slide=collisionLimitedStep([-.3,0],[.2,.4],w);
 assert.ok(-.3+slide[0]<=-.25+1e-7);assert.ok(slide[1]>.3);
 assert.ok(collisionLimitedStep([-.1,0],[-.1,0],w)[0]<0);
});
test("snap turn triggers once until centered",()=>{
 const a=snapTurn(.9,true);near(a.angle,Math.PI/6);assert.equal(a.armed,false);
 assert.equal(snapTurn(.9,a.armed).angle,0);
 assert.equal(snapTurn(0,false).armed,true);
 assert.ok(snapTurn(-1,true).angle<0);
});
test("reference offsets preserve head pivot, allow elevation and translation",()=>{
 const h={x:3,y:1.6,z:2},d={x:1,y:5,z:-2},yaw=Math.PI/6;
 const t=navigationOffset(h,d,yaw),x=h.x+d.x,z=h.z+d.z;
 near(t.position.x+Math.cos(yaw)*x+Math.sin(yaw)*z,h.x);
 near(t.position.z-Math.sin(yaw)*x+Math.cos(yaw)*z,h.z);
 near(t.position.y+h.y+d.y,h.y);
});
test("headset quick and full menus offer walk speed and reversible elevated view",()=>{
 for(const compact of [true,false]){
  const q={selectedWall:null,gridM:.05,axis:"auto",nudgeM:.05,pinned:false,help:false,deleteArmed:false,compact,elevatedView:true,walkSpeed:2};
  const menu=buildMenuLayout(EMPTY_BUILD,"ground",EMPTY_ITEM_BROWSER,undefined,false,0,"","finished",false,{available:true,enabled:false,changed:false},undefined,q);
  assert.ok(menu.buttons.some(b=>b.action.action==="elevated-view"&&b.label==="Walkthrough"));
  assert.ok(menu.buttons.some(b=>b.action.action==="walk-speed"&&b.label.includes("2")));
 }
});
