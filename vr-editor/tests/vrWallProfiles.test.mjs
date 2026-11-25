import test from "node:test";
import assert from "node:assert/strict";
import {Mesh,Raycaster,Vector3,Box3} from "three";
import {WALL_PROFILES,defaultWallAssembly,isWallAssembly,wallDimensionText} from "../src/wallProfiles.ts";
import {displayWallDraft,illustrativeTimberFrame} from "../src/buildScene.ts";
import {draftCatalogueHosts} from "../src/catalogueScene.ts";
import {EMPTY_BUILD,STARTING_SIZES,updateBuild} from "../src/buildPlacement.ts";
import {draftAssembly,STUDY_PROFILE} from "../src/vrDraftAssembly.ts";
import {collisionLimitedStep,composeNavigationOffset,identityNavOffset,navigationOffset} from "../src/vrStationaryNavigation.ts";
import {buildMenuLayout,EMPTY_ITEM_BROWSER} from "../src/catalogueMenu.ts";
const w={proposalId:"w",scopeKey:"s",levelId:"ground",start:[0,0],end:[4,0],heightM:2.7,openings:[{openingId:"pass",openingKind:"passage",offsetM:1,widthM:1,heightM:2.1,sillHeightM:0}]};
const near=(a,b)=>assert.ok(Math.abs(a-b)<.00001,`${a} != ${b}`);
const row=(rows,id)=>rows.find(x=>x.id===id);
test("all construction profiles produce actual thickness, clear openings and matching host offset",()=>{
 for(const p of WALL_PROFILES){
  const wall={...w,assembly:defaultWallAssembly(p.id)},group=displayWallDraft(wall);
  const face=group.children.find(c=>c.userData.catalogueWallFace);
  assert.ok(face instanceof Mesh);
  face.geometry.computeBoundingBox();
  near(face.geometry.boundingBox.max.z-face.geometry.boundingBox.min.z,p.thicknessMm/1000);
  group.updateMatrixWorld(true);
  assert.equal(new Raycaster(new Vector3(1.5,1,1),new Vector3(0,0,-1)).intersectObject(face).length,0);
  assert.ok(new Raycaster(new Vector3(.5,1,1),new Vector3(0,0,-1)).intersectObject(face).length>0);
  const host=draftCatalogueHosts(wall,group).find(h=>h.target==="wall");
  near(host.halfThickness,p.thicknessMm/2000);
  assert.equal(host.mesh.userData.catalogueMountFace,true);
  assert.equal(host.mesh.material.visible,false);
  assert.equal(wallDimensionText(4,2.7,wall.assembly),`4000 × 2700 × ${p.thicknessMm} mm`);
  if(p.core==="masonry")assert.equal(illustrativeTimberFrame(wall).children.length,0);
 }
});
test("wall profile metadata is validated and undoable, legacy drafts remain accepted",()=>{
 const original={...EMPTY_BUILD,walls:[w]};
 const a=defaultWallAssembly("brick-veneer-timber");
 const edited=updateBuild(original,{kind:"set-wall-assembly",proposalId:"w",assembly:a},"s","ground",STARTING_SIZES);
 assert.deepEqual(edited.walls[0].assembly,a);
 assert.deepEqual(updateBuild(edited,{kind:"undo"},"s","ground",STARTING_SIZES).walls,original.walls);
 assert.equal(updateBuild(original,{kind:"set-wall-assembly",proposalId:"w",assembly:{...a,thicknessMm:9000}},"s","ground",STARTING_SIZES),original);
 assert.equal(isWallAssembly({...a,profile:"unknown"}),false);
});
test("construction budget does not charge timber or plasterboard allowances to masonry",()=>{
 const area=4*2.7-2.1;
 const concrete=draftAssembly({walls:[{...w,assembly:defaultWallAssembly("concrete")}],ceilings:[]},STUDY_PROFILE);
 assert.equal(row(concrete,"studs").quantity,0);
 assert.equal(row(concrete,"boards").quantity,0);
 near(row(concrete,"wall-concrete").quantity,Math.round(area*.15*1000)/1000);
 const steel=draftAssembly({walls:[{...w,assembly:defaultWallAssembly("brick-veneer-steel")}],ceilings:[]},STUDY_PROFILE);
 assert.equal(row(steel,"studs").quantity,0);
 assert.ok(row(steel,"steel-studs").quantity>0);
 near(row(steel,"brick-veneer").quantity,area);
 near(row(steel,"boards").quantity,Math.round(area/STUDY_PROFILE.sheetM2*1000)/1000);
});
test("thick collision stays on physical side of wall and ignores far obstacles",()=>{
 const delta=collisionLimitedStep([-.6,0],[.5,0],[{start:[0,-3],end:[0,3],halfThickness:.15},{start:[99,99],end:[99,100]}]);
 assert.ok(-.6+delta[0]<=-.4+1e-7);
});
test("reference transforms compose without nesting and remain normalized",()=>{
 let offset=identityNavOffset();
 const move={position:{x:1,y:0,z:0},orientation:{x:0,y:0,z:0,w:1}};
 for(let i=0;i<1000;i++)offset=composeNavigationOffset(offset,move);
 near(offset.position.x,1000);
 const turn=navigationOffset({x:0,y:0,z:0},{x:0,y:0,z:0},Math.PI/2);
 const combined=composeNavigationOffset(turn,move);
 near(combined.position.x,0);near(combined.position.z,-1);
 near(Math.hypot(combined.orientation.y,combined.orientation.w),1);
});
test("headset offers each construction type with dimensions and a return action",()=>{
 const quest={selectedWall:w,gridM:.05,axis:"auto",nudgeM:.05,pinned:false,help:false,deleteArmed:false,wallProfilesOpen:true,dimensions:true};
 const layout=buildMenuLayout({...EMPTY_BUILD,walls:[w]},"ground",EMPTY_ITEM_BROWSER,undefined,false,0,"","finished",false,undefined,undefined,quest);
 assert.equal(layout.buttons.filter(x=>x.action.area==="wall-profile").length,WALL_PROFILES.length);
 assert.ok(layout.buttons.some(x=>x.action.area==="quest"&&x.action.action==="wall-profiles"));
});
