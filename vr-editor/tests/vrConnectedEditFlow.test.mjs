import test from "node:test";
import assert from "node:assert/strict";
import {EMPTY_BUILD,STARTING_SIZES,updateBuild} from "../src/buildPlacement.ts";
import {buildMenuLayout,EMPTY_ITEM_BROWSER} from "../src/catalogueMenu.ts";
import {connectedDraftShell} from "../src/connectedDraftShell.ts";
const wall=(id,start,end)=>({proposalId:id,scopeKey:"s",levelId:"ground",start,end,heightM:2.7,openings:[]});
const walls=[wall("a",[0,0],[4,0]),wall("b",[4,0],[4,3]),wall("c",[4,3],[0,3]),wall("d",[0,3],[0,0])];
const state={...EMPTY_BUILD,walls};
const q={selectedWall:walls[0],gridM:.05,axis:"auto",nudgeM:.05,pinned:false,help:false,deleteArmed:false,radial:true};
const menu=(s,quest)=>buildMenuLayout(s,"ground",EMPTY_ITEM_BROWSER,undefined,false,0,"","finished",false,{available:false,enabled:false,changed:false},{mode:"inspect",canUndo:!!s.history.length,canRedo:!!s.future?.length},quest);
test("selected wall quick wheel exposes direct angle, move, stretch and return to new tools",()=>{
 const layout=menu(state,q);assert.equal(layout.radial,true);
 assert.equal(layout.buttons.length,9);
 assert.deepEqual(layout.buttons.slice(0,8).map(b=>b.label),["Angle","Move","Stretch","Openings","Assembly","Undo","More edits","New tools"]);
 assert.equal(layout.buttons[3].disabled,true);
 assert.equal(menu(state,{...q,selectedWall:null}).buttons[0].label,"Wall");
});
test("angle tray offers big buttons, exact angle entry, back and explicit feedback",()=>{
 const angle=menu(state,{...q,angleTools:true,feedback:"Rotation blocked: opening clearance."});
 assert.equal(angle.radial,undefined);assert.match(angle.title,/WALL ANGLE/);
 assert.match(angle.note,/Rotation blocked/);
 assert.ok(angle.buttons.every(b=>b.w>=300&&b.x+b.w<=angle.width&&b.y+b.h<=angle.height));
 assert.ok(angle.buttons.some(b=>b.label==="Back to wall wheel"));
 const numeric=menu(state,{...q,angleTools:true,numeric:{field:"angle",digits:"25"}});
 assert.match(numeric.title,/25°/);
});
test("connected rotation updates roof and floor, then a single undo restores both",()=>{
 const settings={roof:"gable",pitchDeg:30,slabMm:100,ridgeDeg:0};
 const before=connectedDraftShell(state.walls,settings);
 const edited=updateBuild(state,{kind:"rotate-local-wall",previous:walls[0],angleDeg:15,pivot:"start",connected:true},"s","ground",STARTING_SIZES);
 assert.notEqual(edited,state);
 const shell=connectedDraftShell(edited.walls,settings);
 assert.ok(shell);assert.notEqual(shell.floorM2,before.floorM2);
 assert.ok(Math.abs(shell.roofM2-shell.floorM2/Math.cos(Math.PI/6))<1e-7);
 const restored=updateBuild(edited,{kind:"undo"},"s","ground",STARTING_SIZES);
 assert.deepEqual(connectedDraftShell(restored.walls,settings),before);
});