import test from "node:test";
import assert from "node:assert/strict";
import { Ray, Vector3 } from "three";
import { EMPTY_BUILD, STARTING_SIZES, snapDraftWallPoint,
  translatedDraftWall, rotatedDraftWall, updateBuild, viewRelativeNudge } from "../src/buildPlacement.ts";
import { pickDraftWall, beginDraftGesture, draftGesturePreview } from "../src/buildScene.ts";
import { buildMenuLayout, EMPTY_ITEM_BROWSER } from "../src/catalogueMenu.ts";

const scope = "test-project-scope";
const wall = { proposalId:"local-1",scopeKey:scope,levelId:"ground",
  start:[0,0],end:[4,0],heightM:2.4,openings:[
    {openingId:"door-a",openingKind:"door",offsetM:1,widthM:0.9,heightM:2.1,sillHeightM:0}
  ] };
const state = {...EMPTY_BUILD,walls:[wall]};
const act = (s,a,level="ground",key=scope) => updateBuild(s,a,key,level,STARTING_SIZES);
const quest = {selectedWall:null,gridM:0.05,axis:"auto",nudgeM:0.05,
  pinned:false,help:false,deleteArmed:false};
const menu = (s=state,q=quest) => buildMenuLayout(s,"ground",EMPTY_ITEM_BROWSER,
  undefined,false,0,"","finished",false,
  {available:false,enabled:false,changed:false},
  {mode:"inspect",canUndo:true,canRedo:true,levels:["ground"],level:"ground"},q);

test("01 accurate Quest draft wall selection accepts wall face ray, excludes other floors",()=>{
  const ray = new Ray(new Vector3(2,1,2),new Vector3(0,0,-1));
  assert.equal(pickDraftWall(state,"ground",ray)?.proposalId,"local-1");
  assert.equal(pickDraftWall(state,"upper",ray),null);
  assert.equal(pickDraftWall(EMPTY_BUILD,"ground",ray),null);
});
test("02 configurable grid has 50, 100 and 250mm usable snapping",()=>{
  const empty={walls:[]};
  assert.deepEqual(snapDraftWallPoint(empty,"ground",[1.17,1.12],null,{gridM:0.05})?.point,[1.15,1.1]);
  assert.deepEqual(snapDraftWallPoint(empty,"ground",[1.17,1.12],null,{gridM:0.1})?.point,[1.2,1.1]);
  assert.deepEqual(snapDraftWallPoint(empty,"ground",[1.17,1.12],null,{gridM:0.25})?.point,[1.25,1]);
});
test("03 explicit horizontal/vertical axis lock and free drafting",()=>{
  const empty={walls:[]};
  assert.deepEqual(snapDraftWallPoint(empty,"ground",[5.32,1.47],[4,0],{axis:"horizontal"})?.point,[5.3,0]);
  assert.deepEqual(snapDraftWallPoint(empty,"ground",[5.32,1.47],[4,0],{axis:"vertical"})?.point,[4,1.45]);
  assert.equal(snapDraftWallPoint(empty,"ground",[5.32,0.08],[4,0],{axis:"free"})?.kind,"grid");
  assert.equal(snapDraftWallPoint(empty,"ground",[5.32,0.08],[4,0],{axis:"auto"})?.kind,"straight");
});
test("04 quick 50mm nudge preserves dimensions, openings and source scope",()=>{
  const changed=translatedDraftWall(wall,0.05,-0.1);
  assert.deepEqual(changed?.start,[0.05,-0.1]);
  assert.deepEqual(changed?.end,[4.05,-0.1]);
  assert.deepEqual(changed?.openings,wall.openings);
  const updated=act(state,{kind:"adjust",previous:wall,wall:changed});
  assert.deepEqual(updated.walls[0].start,[0.05,-0.1]);
  assert.deepEqual(act(updated,{kind:"undo"}).walls[0],wall);
  assert.deepEqual(state.walls[0],wall);
});
test("05 rotate selected draft wall 90 degrees about its midpoint; door offsets retained",()=>{
  const rotated=rotatedDraftWall(wall);
  assert.deepEqual(rotated?.start,[2,-2]);
  assert.deepEqual(rotated?.end,[2,2]);
  assert.deepEqual(rotated?.openings,wall.openings);
  assert.equal(act(state,{kind:"adjust",previous:wall,wall:rotated}).walls[0].end[1],2);
});
test("06 duplicate creates distinct local IDs, copies door geometry and supports Undo",()=>{
  const duplicated=act(state,{kind:"duplicate-local-wall",proposalId:"local-1",id:"local-2"});
  assert.equal(duplicated.walls.length,2);
  assert.deepEqual(duplicated.walls[1].start,[0.5,0]);
  assert.equal(duplicated.walls[1].openings[0].openingId,"local-2-opening-0");
  assert.deepEqual(act(duplicated,{kind:"undo"}).walls,state.walls);
  assert.strictEqual(act(state,{kind:"duplicate-local-wall",proposalId:"local-1",id:"local-1"}),state);
});
test("07 scope-guarded delete, Undo and Redo; never delete another tenant's draft",()=>{
  const deleted=act(state,{kind:"delete-local-wall",proposalId:"local-1"});
  assert.equal(deleted.walls.length,0);
  assert.equal(act(deleted,{kind:"undo"}).walls.length,1);
  assert.equal(act(act(deleted,{kind:"undo"}),{kind:"redo"}).walls.length,0);
  assert.strictEqual(act(state,{kind:"delete-local-wall",proposalId:"local-1"},"ground","other-scope"),state);
});
test("08 selected-wall context has spatial nudge, rotate, duplicate, guarded delete and back",()=>{
  const layout=menu(state,{...quest,selectedWall:wall,deleteArmed:true});
  assert.match(layout.title,/4000 mm/);
  const labels=layout.buttons.map(b=>b.label);
  for(const name of ["Nudge left","Nudge right","Nudge forward","Nudge back",
    "Rotate 90°","Duplicate","Confirm delete","Back to tools"]) assert.ok(labels.includes(name));
  for(const b of layout.buttons) assert.ok(b.x>=0&&b.y>=0&&
    b.x+b.w<=layout.width&&b.y+b.h<layout.height);
});
test("09 pinned control panel and recenter are discoverable from root tools",()=>{
  const labels=menu().buttons.map(b=>b.label);
  assert.ok(labels.includes("Pin panel"));
  assert.ok(labels.includes("Recenter"));
  assert.ok(menu(state,{...quest,pinned:true}).buttons.some(b=>b.label==="Unpin panel"));
});
test("10 quick help is in-headset, readable, and returns to tools",()=>{
  const help=menu(state,{...quest,help:true});
  assert.ok(help.helpLines.length>=5);
  assert.ok(help.helpLines.some(line=>line.includes("Trigger")));
  assert.equal(help.buttons[0].action.area,"quest");
  assert.equal(help.buttons[0].action.action,"help");
});
test("disabled editing and cross-level draft guards stay in effect",()=>{
  const empty=menu(EMPTY_BUILD);
  assert.equal(empty.buttons.find(b=>b.label==="Door")?.disabled,true);
  assert.strictEqual(act(state,{kind:"duplicate-local-wall",proposalId:"local-1",id:"local-2"},"upper"),state);
  assert.strictEqual(act(state,{kind:"delete-local-wall",proposalId:"local-1"},"upper"),state);
});

test("Quest nudge direction follows view orientation without diagonal drift",()=>{
  assert.deepEqual(viewRelativeNudge("forward",[0,-1],0.05),[0,-0.05]);
  assert.deepEqual(viewRelativeNudge("right",[0,-1],0.05),[0.05,0]);
  assert.deepEqual(viewRelativeNudge("forward",[1,0.1],0.1),[0.1,0]);
  assert.deepEqual(viewRelativeNudge("left",[1,0.1],0.1),[0,-0.1]);
  assert.equal(viewRelativeNudge("forward",[0,0],0.05),null);
  assert.equal(viewRelativeNudge("forward",[1,1],Infinity),null);
});

test("selected draft wall exposes direct Grab, Stretch, Undo and Redo with guarded buttons",()=>{
  const layout=menu(state,{...quest,selectedWall:wall});
  const move=layout.buttons.find(b=>b.label==="Grab / Move");
  const stretch=layout.buttons.find(b=>b.label==="Stretch end");
  assert.deepEqual(move?.action,{area:"draft",action:"move",direction:undefined});
  assert.deepEqual(stretch?.action,{area:"draft",action:"stretch",direction:undefined});
  const undo=layout.buttons.find(b=>b.label==="Undo");
  const redo=layout.buttons.find(b=>b.label==="Redo");
  assert.deepEqual(undo?.action,{area:"history",action:"undo"});
  assert.equal(undo?.disabled,false);
  assert.equal(redo?.disabled,false);
  const noHistory=buildMenuLayout(state,"ground",EMPTY_ITEM_BROWSER,
    undefined,false,0,"","finished",false,
    {available:false,enabled:false,changed:false},
    {mode:"inspect",canUndo:false,canRedo:false}, {...quest,selectedWall:wall});
  assert.equal(noHistory.buttons.find(b=>b.label==="Undo")?.disabled,true);
  assert.equal(noHistory.buttons.find(b=>b.label==="Redo")?.disabled,true);
});
test("selected Grab tool activates the existing Quest wall-face trigger/hand-drag path",()=>{
  const moved=act(state,{kind:"tool",tool:"move"});
  const ray=new Ray(new Vector3(2,1.2,2),new Vector3(0,0,-1));
  const gesture=beginDraftGesture(moved,"ground",ray);
  assert.equal(gesture?.kind,"wall");
  assert.equal(gesture?.previous?.proposalId,"local-1");
  gesture.fromController=[2,2];
  const preview=draftGesturePreview(gesture,STARTING_SIZES,ray,moved,[2.15,2]);
  assert.equal(preview.action?.kind,"adjust");
  assert.deepEqual(preview.action.wall.start,[0.15,0]);
  assert.deepEqual(state.walls[0].start,[0,0]);
});

test("selected draft wall tools are hidden when footprint projection is active",()=>{
  for (const footprint of [
    {available:true,enabled:true,changed:false},
    {available:true,enabled:false,changed:true},
  ]) {
    const layout=buildMenuLayout(state,"ground",EMPTY_ITEM_BROWSER,
      undefined,false,0,"","finished",false,footprint,
      {mode:"resize",canUndo:false,canRedo:false},
      {...quest,selectedWall:wall});
    assert.ok(!layout.buttons.some(b=>b.label==="Grab / Move"));
    assert.ok(!layout.buttons.some(b=>b.label==="Stretch end"));
    if(footprint.enabled){
      assert.ok(layout.buttons.some(b=>b.label==="Apply / done"));
      assert.ok(!layout.buttons.some(b=>b.action.area==="build"&&!b.disabled));
      assert.equal(layout.buttons.filter(b=>b.action.area==="footprint-size").length,4);
    }else assert.ok(layout.buttons.some(b=>b.label==="Wall"&&b.disabled));
  }
});
