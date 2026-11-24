import test from "node:test";
import assert from "node:assert/strict";
import {parsePreciseCommand,previewPreciseCommand} from "../src/preciseCommands.ts";
import {EMPTY_BUILD,STARTING_SIZES,updateBuild} from "../src/buildPlacement.ts";
const wall={proposalId:"w",scopeKey:"s",levelId:"ground",start:[0,0],end:[4,0],heightM:2.4,openings:[{openingId:"d",openingKind:"door",offsetM:1,widthM:.9,heightM:2.1,sillHeightM:0}]};
test("parse explicit units, natural height commands and relative moves",()=>{
 assert.deepEqual(parsePreciseCommand("Make this wall 2,700 mm high."),{kind:"wall",field:"height",mm:2700,relative:false});
 assert.equal(parsePreciseCommand("set wall length to 4.2 metres").mm,4200);
 assert.equal(parsePreciseCommand("move wall x by -30 cm").mm,-300);
 assert.equal(parsePreciseCommand("make this ceiling 2700 mm high").kind,"ceiling");
 for(const bad of ["delete wall","move this wall 300","set wall height to 2.7","make ceiling 2 m long","set wall length to 0.0001 mm","set wall height to 3 m and delete"])assert.equal(parsePreciseCommand(bad),null);
});
test("preview uses exact current draft and preserves openings and undo",()=>{
 const state={...EMPTY_BUILD,walls:[wall]};
 const a=previewPreciseCommand(parsePreciseCommand("make wall 2700 mm high"),wall,null);
 assert.equal(a.kind,"adjust");assert.equal(a.wall.heightM,2.7);
 assert.deepEqual(a.wall.openings,wall.openings);
 const next=updateBuild(state,a,"s","ground",STARTING_SIZES);
 assert.equal(next.walls[0].heightM,2.7);
 assert.equal(updateBuild(next,{kind:"undo"},"s","ground",STARTING_SIZES).walls[0].heightM,2.4);
 assert.equal(updateBuild(next,a,"s","ground",STARTING_SIZES),next);
 assert.equal(previewPreciseCommand(parsePreciseCommand("make wall 1500 mm high"),wall,null),null);
 const move=previewPreciseCommand(parsePreciseCommand("move wall z by 300 mm"),wall,null);
 assert.deepEqual(move.wall.start,[0,.3]);assert.deepEqual(move.wall.end,[4,.3]);
});
test("ceiling height requires an explicitly selected ceiling",()=>{
 const ceiling={proposalId:"c",scopeKey:"s",levelId:"ground",start:[0,0],end:[3,4],heightM:2.4};
 const cmd=parsePreciseCommand("make ceiling 2700 mm high");
 assert.equal(previewPreciseCommand(cmd,wall,null),null);
 assert.equal(previewPreciseCommand(cmd,null,ceiling).ceiling.heightM,2.7);
});