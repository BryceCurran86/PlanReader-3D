import test from "node:test";
import assert from "node:assert/strict";
import {EMPTY_BUILD,STARTING_SIZES,planLength,wallAngleDegrees,rotateDraftWallTo,updateBuild} from "../src/buildPlacement.ts";
import {buildMenuLayout,EMPTY_ITEM_BROWSER} from "../src/catalogueMenu.ts";
const wall={proposalId:"w",scopeKey:"s",levelId:"ground",start:[1,2],end:[5,2],heightM:2.7,openings:[{openingId:"d",openingKind:"door",offsetM:1,widthM:.9,heightM:2.1,sillHeightM:0}]};
const state={...EMPTY_BUILD,walls:[wall]};
const act=(s,a)=>updateBuild(s,a,"s","ground",STARTING_SIZES);
const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-7,`${a} != ${b}`);
test("arbitrary rotation preserves length, height and apertures at all three pivots",()=>{
 for(const angle of [0,1,15,37.5,45,90,135,180,270,359.9])for(const pivot of ["start","centre","end"]){
  const next=rotateDraftWallTo(wall,angle,pivot);
  near(planLength(next.start,next.end),4);near(wallAngleDegrees(next),angle);
  assert.equal(next.heightM,2.7);assert.deepEqual(next.openings,wall.openings);
  if(pivot==="start")assert.deepEqual(next.start,wall.start);
  if(pivot==="end")assert.deepEqual(next.end,wall.end);
  if(pivot==="centre"){near((next.start[0]+next.end[0])/2,3);near((next.start[1]+next.end[1])/2,2);}
 }
});
test("incremental edits are atomic, preserve length and undo/redo",()=>{
 const action={kind:"rotate-local-wall",previous:wall,angleDeg:37.5,pivot:"start"};
 const next=act(state,action);
 near(wallAngleDegrees(next.walls[0]),37.5);
 const after=act(next,{...action,previous:next.walls[0],angleDeg:-5,relative:true});
 near(wallAngleDegrees(after.walls[0]),32.5);
 assert.deepEqual(act(after,{kind:"undo"}).walls,next.walls);
 assert.deepEqual(act(act(after,{kind:"undo"}),{kind:"redo"}).walls,after.walls);
 assert.equal(act(next,action),next);
 assert.equal(act(state,{...action,previous:{...wall}}),state);
 assert.equal(act(state,{...action,angleDeg:NaN}),state);
 assert.equal(act(state,{...action,pivot:"invalid"}),state);
 assert.equal(updateBuild(state,action,"s","upper",STARTING_SIZES),state);
});
test("full-width aperture does not shrink after many fine rotations",()=>{
 let w={...wall,openings:[{...wall.openings[0],offsetM:0,widthM:4}]};
 for(let i=0;i<360;i++){w=rotateDraftWallTo(w,wallAngleDegrees(w)+1,"start");assert.ok(w);}
 near(planLength(w.start,w.end),4);assert.deepEqual(w.start,wall.start);
});
test("headset exposes fine angle and fixed pivot controls plus degree keypad",()=>{
 const q={selectedWall:wall,gridM:.05,axis:"auto",nudgeM:.05,pinned:false,help:false,deleteArmed:false,rotationPivot:"start"};
 const menu=q=>buildMenuLayout(state,"ground",EMPTY_ITEM_BROWSER,undefined,false,0,"","finished",false,{available:false,enabled:false,changed:false},undefined,q);
 const labels=menu(q).buttons.map(b=>b.label);
 for(const name of ["Pivot start","-15°","-5°","-1°","+1°","+5°","+15°","Rotate 90°"])assert.ok(labels.includes(name));
 const keypad=menu({...q,numeric:{field:"angle",digits:"45"}});
 assert.match(keypad.title,/45°/);assert.ok(keypad.buttons.some(b=>b.label==="Apply angle °"));
});