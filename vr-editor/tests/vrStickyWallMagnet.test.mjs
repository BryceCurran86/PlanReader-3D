import test from "node:test";
import assert from "node:assert/strict";
import {Ray,Vector3} from "three";
import {chooseWallAim,wallAimWithin} from "../src/wallMagnet.ts";
import {snapDraftWallPoint,EMPTY_BUILD} from "../src/buildPlacement.ts";
const wall=(key,z,kind="draft",halfThickness=.058)=>({key,kind,id:key,start:[0,z],end:[4,z],heightM:2.7,halfThickness});
const ray=(x,y=1,z=4)=>new Ray(new Vector3(x,y,z),new Vector3(0,0,-1));
test("foreground imported walls beat more distant drafts",()=>{
 const s=wall("s",2,"source",0),d=wall("d",0);
 assert.equal(chooseWallAim(ray(2),[d,s],null).target.key,"s");
 assert.equal(chooseWallAim(ray(2),[d,s],"d").target.key,"s");
});
test("hold through jitter and release only beyond the wider tolerance",()=>{
 const t=wall("d",0);
 assert.equal(chooseWallAim(ray(4.18),[t],null).target.key,"d");
 assert.equal(chooseWallAim(ray(4.29),[t],null),null);
 assert.equal(chooseWallAim(ray(4.29),[t],"d").target.key,"d");
 assert.equal(wallAimWithin(ray(4.5),t),null);
 assert.equal(chooseWallAim(ray(4.18),[t],"d",false),null);
});
test("thick walls can be targeted from their top, side and end",()=>{
 const t=wall("d",0);
 const top=new Ray(new Vector3(2,5,.04),new Vector3(0,-1,0));
 assert.equal(chooseWallAim(top,[t],null,false).exact,true);
 const end=new Ray(new Vector3(5,1,0),new Vector3(-1,0,0));
 assert.equal(chooseWallAim(end,[t],null,false).target.key,"d");
});
test("snap new wall to a source wall run with millimetre positioning",()=>{
 const segments=[{objectId:"s",start:[0,1.137],end:[4,1.137]}];
 const snap=snapDraftWallPoint(EMPTY_BUILD,"ground",[2.123,1.28],null,{magnetic:true,wallSegments:segments});
 assert.deepEqual(snap.point,[2.123,1.137]);assert.equal(snap.kind,"wall-face");
 const free=snapDraftWallPoint(EMPTY_BUILD,"ground",[2.123,1.28],null,{magnetic:false,wallSegments:segments});
 assert.equal(free.kind,"grid");assert.notDeepEqual(free.point,snap.point);
});
