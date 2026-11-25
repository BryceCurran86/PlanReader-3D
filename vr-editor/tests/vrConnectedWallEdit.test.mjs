import test from "node:test";
import assert from "node:assert/strict";
import {EMPTY_BUILD,STARTING_SIZES,updateBuild,planLength,wallAngleDegrees} from "../src/buildPlacement.ts";
import {localOutline} from "../src/localOutline.ts";
import {buildMenuLayout,EMPTY_ITEM_BROWSER} from "../src/catalogueMenu.ts";
const w=(id,start,end,openings=[])=>({proposalId:id,scopeKey:"s",levelId:"ground",start,end,heightM:2.7,openings});
const ring=[w("a",[0,0],[4,0]),w("b",[4,0],[4,3]),w("c",[4,3],[0,3]),w("d",[0,3],[0,0])];
const state={...EMPTY_BUILD,walls:ring};
const act=(s,a)=>updateBuild(s,a,"s","ground",STARTING_SIZES);
const rotate=(previous,angleDeg=15,pivot="start",connected=true)=>({kind:"rotate-local-wall",previous,angleDeg,pivot,connected});
const close=(a,b)=>assert.ok(Math.abs(a-b)<1e-7);
test("rotating a perimeter wall propagates both endpoint joins with exact length, one undo and redo",()=>{
 const result=act(state,rotate(ring[0],15,"centre"));
 assert.notEqual(result,state);
 const [a,b,c,d]=result.walls;
 assert.deepEqual(a.end,b.start);assert.deepEqual(d.end,a.start);
 assert.equal(c,ring[2]);
 close(planLength(a.start,a.end),4);close(wallAngleDegrees(a),15);
 assert.ok(localOutline(result.walls));
 assert.notEqual(localOutline(result.walls).areaM2,localOutline(ring).areaM2);
 assert.deepEqual(act(result,{kind:"undo"}).walls,ring);
 assert.deepEqual(act(act(result,{kind:"undo"}),{kind:"redo"}).walls,result.walls);
});
test("connected edit retains opening size and distance from stationary adjacent endpoint",()=>{
 const door={openingId:"door",openingKind:"door",offsetM:1.5,widthM:.8,heightM:2.1,sillHeightM:0};
 const walls=ring.map((v,i)=>i===1?{...v,openings:[door]}:v);
 const s={...state,walls};
 const result=act(s,rotate(walls[0],5));
 assert.notEqual(result,s);
 const changed=result.walls[1],opening=changed.openings[0];
 assert.equal(opening.widthM,.8);assert.equal(opening.heightM,2.1);
 close(planLength(changed.start,changed.end)-opening.offsetM,3-door.offsetM);
 assert.deepEqual(changed.end,walls[1].end);
});
test("refuse shortening an adjoining wall past its opening or self intersecting ring",()=>{
 const door={openingId:"wide",openingKind:"door",offsetM:.1,widthM:2.8,heightM:2.1,sillHeightM:0};
 const walls=ring.map((v,i)=>i===1?{...v,openings:[door]}:v);
 const s={...state,walls};
 assert.equal(act(s,rotate(walls[0],15)),s);
 assert.equal(act(state,rotate(ring[0],90)),state);
});
test("connected open chain, reversed direction, unrelated levels and independent override",()=>{
 const first=w("first",[0,0],[4,0]),neighbor=w("reverse",[4,3],[4,0]),upper={...w("upper",[4,0],[5,0]),levelId:"upper"};
 const s={...state,walls:[first,neighbor,upper]};
 const result=act(s,rotate(first,30));
 assert.notEqual(result,s);assert.deepEqual(result.walls[0].end,result.walls[1].end);assert.equal(result.walls[2],upper);
 const independent=act(s,rotate(first,30,"start",false));assert.equal(independent.walls[1],neighbor);
});
test("unsplit T junctions are rejected rather than detached",()=>{
 const t=w("t",[2,0],[2,2]);
 const s={...state,walls:[ring[0],t]};
 assert.equal(act(s,rotate(ring[0],15)),s);
});
test("headset junction mode is discoverable and defaults on",()=>{
 const q={selectedWall:ring[0],gridM:.05,axis:"auto",nudgeM:.05,pinned:false,help:false,deleteArmed:false};
 const menu=q=>buildMenuLayout(state,"ground",EMPTY_ITEM_BROWSER,undefined,false,0,"","finished",false,{available:false,enabled:false,changed:false},undefined,q);
 assert.ok(menu(q).buttons.some(b=>b.label==="Junctions ON"));
 assert.ok(menu({...q,connectedRotation:false}).buttons.some(b=>b.label==="Junctions OFF"));
});