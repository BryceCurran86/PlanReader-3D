import test from "node:test";
import assert from "node:assert/strict";
import {Ray,Vector3} from "three";
import {exactDraftWall,exactDraftOpening} from "../src/vrDraftGeometry.ts";
import {EMPTY_BUILD, STARTING_SIZES, snapDraftWallPoint, updateBuild, planLength} from "../src/buildPlacement.ts";
import {pickDraftWalls,beginDraftGesture,draftGesturePreview} from "../src/buildScene.ts";
import {verifiedSourceWallAnchors} from "../src/vrDraftSourceSnaps.ts";

const scope="source-scoped-draft";
const wall={proposalId:"wall-1",scopeKey:scope,levelId:"ground",
  start:[0,0],end:[4,0],heightM:2.7,
  openings:[{openingId:"door-1",openingKind:"door",offsetM:1,widthM:0.9,heightM:2.1,sillHeightM:0}]};
const state={...EMPTY_BUILD,walls:[wall]};
const action=(s,a,key=scope,level="ground")=>updateBuild(s,a,key,level,STARTING_SIZES);
test("exact wall length, height and plan position use integer millimetres",()=>{
  const longer=exactDraftWall(wall,"length",4200);
  assert.equal(planLength(longer.start,longer.end),4.2);
  assert.deepEqual(exactDraftWall(wall,"x",1125).start,[1.125,0]);
  assert.deepEqual(exactDraftWall(wall,"z",-200).end,[4,-0.2]);
  assert.equal(exactDraftWall(wall,"height",2100).heightM,2.1);
  assert.equal(exactDraftWall(wall,"height",2000),null);
  assert.equal(exactDraftWall(wall,"length",NaN),null);
  assert.equal(exactDraftWall(wall,"length",200001),null);
});
test("precise edit is scope and level gated, undoable and does not mutate input",()=>{
  const payload={kind:"exact-local-wall",proposalId:"wall-1",field:"length",valueMm:4200};
  const changed=action(state,payload);
  assert.equal(changed.walls[0].end[0],4.2);
  assert.deepEqual(action(changed,{kind:"undo"}).walls,state.walls);
  assert.strictEqual(action(state,payload,"wrong"),state);
  assert.strictEqual(action(state,payload,scope,"roof"),state);
  assert.equal(state.walls[0].end[0],4);
});
test("door/window offsets and widths edit on host only, with collision rejection",()=>{
  const moved=exactDraftOpening(wall,"door-1","offset",1150);
  assert.equal(moved.openings[0].offsetM,1.15);
  assert.equal(exactDraftOpening(wall,"door-1","width",4000),null);
  assert.equal(exactDraftOpening(wall,"door-1","sill",1000),null);
  assert.equal(exactDraftOpening(wall,"unknown","width",900),null);
  const overlapping={...wall,openings:[...wall.openings,
    {openingId:"window-2",openingKind:"window",offsetM:2,widthM:0.8,heightM:1,sillHeightM:0.9}]};
  assert.equal(exactDraftOpening(overlapping,"door-1","width",1500),null);
  const changed=action(state,{kind:"exact-local-opening",proposalId:"wall-1",
    openingId:"door-1",field:"width",valueMm:1000});
  assert.equal(changed.walls[0].openings[0].widthM,1);
  assert.deepEqual(action(changed,{kind:"undo"}).walls,state.walls);
});
test("source snap candidates require verified level, source file, canonical ID and zero issues",()=>{
  const row={objectId:"verified-w1",objectType:"wall",levelId:"ground",
    canonicalObjectId:"canonical-w1",renderState:"verified",
    source:{sourceFileId:"architectural-source.pdf"},
    unresolvedIssues:[],geometry:{kind:"wallFace",start:[4.127,0.018],end:[8.127,0.018],heightM:2.7}};
  const scene={objects:[row,
    {...row,objectId:"other-level",levelId:"upper"},
    {...row,objectId:"review",renderState:"review"},
    {...row,objectId:"unresolved",unresolvedIssues:["unverified-height"]},
    {...row,objectId:"missing-file",source:{sourceFileId:null}},
  ]};
  const anchors=verifiedSourceWallAnchors(scene,"ground",new Set(["verified-w1","review","unresolved","missing-file"]));
  assert.equal(anchors.length,2);
  assert.deepEqual(anchors[0].point,[4.127,0.018]);
  const result=snapDraftWallPoint({walls:[]}, "ground",[4.12,0.03],null,
    {verifiedAnchors:anchors});
  assert.equal(result.kind,"verified");
  assert.equal(result.witness,"verified-w1");
  assert.deepEqual(result.point,[4.127,0.018]);
});
test("ambiguous equal-distance source guides never invent an authoritative snap",()=>{
  const points=[{objectId:"a",point:[1.9,0]},{objectId:"b",point:[2.1,0]}];
  const snap=snapDraftWallPoint({walls:[]},"ground",[2,0],null,{verifiedAnchors:points});
  assert.equal(snap.kind,"grid");
});
test("controller hit cycles overlapping drafts in deterministic order",()=>{
  const same={...wall,proposalId:"wall-2"};
  const ray=new Ray(new Vector3(2,1,2),new Vector3(0,0,-1));
  const hits=pickDraftWalls({...state,walls:[same,wall]},"ground",ray);
  assert.deepEqual(hits.map(x=>x.proposalId),["wall-1","wall-2"]);
  assert.equal(pickDraftWalls(state,"upper",ray).length,0);
});

test("Quest hand-drag slides a door opening on its wall, retaining its identity and source guard",()=>{
  const edit={...state,tool:"opening-move"};
  const ray=new Ray(new Vector3(1.45,1.5,2),new Vector3(0,0,-1));
  const gesture=beginDraftGesture(edit,"ground",ray);
  assert.equal(gesture?.kind,"opening");
  assert.equal(gesture?.openingId,"door-1");
  gesture.fromController=[1.45,2];
  const preview=draftGesturePreview(gesture,STARTING_SIZES,ray,edit,[1.7,2]);
  assert.deepEqual(preview?.action,{kind:"exact-local-opening",proposalId:"wall-1",
    openingId:"door-1",field:"offset",valueMm:1250});
  const updated=action(edit,preview.action);
  assert.equal(updated.walls[0].openings[0].offsetM,1.25);
  assert.equal(edit.walls[0].openings[0].offsetM,1);
  assert.equal(action(edit,preview.action,"other-tenant"),edit);
});
