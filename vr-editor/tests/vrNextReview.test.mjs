import test from "node:test";
import assert from "node:assert/strict";
import {EMPTY_BUILD,STARTING_SIZES,updateBuild} from "../src/buildPlacement.ts";
import {saveVrReview,restoreVrReview} from "../src/vrDraftSave.ts";
import {vrDraftTakeoff,localIndicativeWallCost} from "../src/vrDraftTakeoff.ts";
import {buildMenuLayout,EMPTY_ITEM_BROWSER} from "../src/catalogueMenu.ts";
import {scopeKey} from "../src/reviewDraft.ts";
import {overviewSegments} from "../src/vrPlanOverview.ts";

const scene={scope:{
 workspaceId:"test-workspace",projectId:"test-project",documentId:"test-document",
 revisionId:"revision-1",snapshotId:"snapshot-1",sourceSha256:"f".repeat(64),modelRevision:1,
},objects:[{levelId:"ground"}]};
const key=scopeKey(scene);
const wall={proposalId:"draft-1",scopeKey:key,levelId:"ground",
 start:[0,0],end:[4,0],heightM:2.7,
 openings:[{openingId:"opening-1",openingKind:"door",offsetM:1,widthM:0.9,heightM:2.1,sillHeightM:0}]};
const build={...EMPTY_BUILD,walls:[wall],history:[{walls:[],ceilings:[]}]};
const quest={selectedWall:wall,gridM:0.05,axis:"auto",nudgeM:0.05,
 pinned:false,help:false,deleteArmed:false};
const layout=q=>buildMenuLayout(build,"ground",EMPTY_ITEM_BROWSER,undefined,false,0,
 "","finished",false,{available:false,enabled:false,changed:false},
 {mode:"inspect",canUndo:true,canRedo:true,levels:["ground"],level:"ground"},q);

test("opt-in local backup preserves source scope and reversible history, not original source",()=>{
 const text=saveVrReview(scene,build,null);
 const document=JSON.parse(text);
 assert.equal(document.commercialPublicationAllowed,false);
 assert.equal(document.previewOnly,true);
 assert.equal(document.geometry.walls.length,1);
 assert.ok(!("objects" in document));
 const restored=restoreVrReview(scene,document);
 assert.deepEqual(restored.build.walls,build.walls);
 assert.equal(restored.build.history.length,1);
 assert.equal(restored.itemDraft.items.length,0);
 const undone=updateBuild(restored.build,{kind:"undo"},key,"ground",STARTING_SIZES);
 assert.equal(undone.walls.length,0);
});
test("a stale or malicious backup cannot cross source revision, workspace or geometry guards",()=>{
 const record=JSON.parse(saveVrReview(scene,build,null));
 assert.throws(()=>restoreVrReview({...scene,scope:{...scene.scope,snapshotId:"snapshot-2"}},record));
 assert.throws(()=>restoreVrReview({...scene,scope:{...scene.scope,workspaceId:"another"}},record));
 assert.throws(()=>restoreVrReview({...scene,scope:{...scene.scope,sourceSha256:"a".repeat(64)}},record));
 const overlap=structuredClone(record);
 overlap.geometry.walls[0].openings.push({
  openingId:"second",openingKind:"window",offsetM:1,widthM:.4,heightM:1,sillHeightM:.4});
 assert.throws(()=>restoreVrReview(scene,overlap),/Overlapping/);
 const impossible=structuredClone(record);
 impossible.geometry.walls[0].heightM=1;
 assert.throws(()=>restoreVrReview(scene,impossible));
});
test("live draft quantities update from geometry and clearly separate unpriced trades",()=>{
 const q=vrDraftTakeoff(build);
 assert.equal(q.wallRunM,4);
 assert.equal(q.wallNetFaceM2,8.91);
 assert.equal(q.indicativeTwoFaceLiningM2,17.82);
 assert.equal(q.skirtingCandidateM,6.2);
 assert.equal(q.draftDoors,1);
 assert.equal(q.commercialPublicationAllowed,false);
 assert.ok(q.unpricedTrades.length>=4);
 assert.equal(localIndicativeWallCost(q,"20"),"356.40");
 assert.equal(localIndicativeWallCost(q,""),null);
 assert.equal(localIndicativeWallCost(q,"NaN"),null);
 const changed=updateBuild(build,{kind:"exact-local-wall",
  proposalId:"draft-1",field:"length",valueMm:5000},key,"ground",STARTING_SIZES);
 assert.equal(vrDraftTakeoff(changed).wallRunM,5);
});
test("headset compact panel, full tools, exact millimetre keypad, and opening editor are accessible",()=>{
 const compact=layout({...quest,compact:true,selectedWall:null,canTeleport:false});
 assert.ok(compact.buttons.some(b=>b.label==="Build tools"));
 assert.ok(compact.buttons.some(b=>b.label==="Save draft"));
 assert.equal(compact.buttons.find(b=>b.label==="Teleport")?.disabled,true);
 assert.ok(compact.buttons.every(b=>b.y+b.h<compact.height&&b.x+b.w<=compact.width));
 const selected=layout(quest);
 assert.ok(selected.buttons.some(b=>b.label==="Exact length"));
 assert.ok(selected.buttons.some(b=>b.label==="Edit openings"));
 assert.deepEqual(selected.buttons.find(b=>b.label==="Review + cost")?.action,
   {area:"quest",action:"review"});
 const numeric=layout({...quest,numeric:{field:"length",digits:"4200"}});
 assert.ok(numeric.buttons.some(b=>b.label==="Apply exact mm"));
 assert.ok(numeric.buttons.some(b=>b.label==="4"));
 assert.ok(numeric.buttons.every(b=>b.y+b.h<numeric.height));
 const openings=layout({...quest,openingTools:true,openingIndex:0});
 assert.ok(openings.buttons.some(b=>b.label==="Slide +50mm"));
 assert.ok(openings.buttons.some(b=>b.label==="Exact width"));
});
test("non-source placements retain 50mm rounding while explicit verified snap keeps native mm",()=>{
 const empty={...EMPTY_BUILD,tool:"wall"};
 const raw=updateBuild(empty,{kind:"place",hit:{kind:"wall",levelId:"ground",point:[1.127,0.018]},id:"point-1"},
   key,"ground",STARTING_SIZES);
 assert.deepEqual(raw.start.point,[1.15,0]);
 const precise=updateBuild(empty,{kind:"place",hit:{
   kind:"wall",levelId:"ground",point:[1.127,0.018],precisionSource:true},id:"point-1"},
   key,"ground",STARTING_SIZES);
 assert.deepEqual(precise.start.point,[1.127,0.018]);
});

test("read-only Quest overhead plan uses visible source segments and separate local draft segments",()=>{
  const source={...scene,objects:[
    {objectId:"verified",objectType:"wall",levelId:"ground",renderState:"verified",
      unresolvedIssues:[],geometry:{kind:"wallFace",start:[0,1],end:[2,1],heightM:2.4}},
    {objectId:"blocked",objectType:"wall",levelId:"upper",renderState:"review",
      unresolvedIssues:["unverified"],geometry:{kind:"wallLine",start:[3,3],end:[4,4]}},
  ]};
  const segments=overviewSegments(source,build,"ground",new Set(["verified"]));
  assert.equal(segments.length,2);
  assert.equal(segments[0].source,true);
  assert.equal(segments[0].verified,true);
  assert.equal(segments[1].source,false);
  assert.equal(overviewSegments(source,build,"upper",new Set(["verified"])).length,0);
  const visible=overviewSegments(source,build,"upper",new Set(["blocked"]));
  assert.equal(visible[0].verified,false);
});
