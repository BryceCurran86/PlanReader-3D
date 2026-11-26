import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import {wallCornerJoins} from "../src/wallCornerJoin.ts";
import {displayWallDraft} from "../src/buildScene.ts";
import {draftCatalogueHosts} from "../src/catalogueScene.ts";
import {defaultWallAssembly} from "../src/wallProfiles.ts";
import {createPhysicalToolTray} from "../src/physicalToolTray.ts";
import {openingFrameVisual,nominalDoorSlab} from "../src/openingFinishVisual.ts";
import {starterBuild,starterManifest} from "../src/starterHouse.ts";

const assembly={...defaultWallAssembly("external-timber"),exteriorSide:"right"};
const wall=(id,start,end,more={})=>({proposalId:id,start,end,scopeKey:"s",levelId:"ground",heightM:2.4,openings:[],assembly,...more});
const front=wall("front",[0,0],[4,0]),right=wall("right",[4,0],[4,3]);
const near=(actual,expected)=>actual.forEach((n,i)=>assert.ok(Math.abs(n-expected[i])<1e-6,actual+" != "+expected));

test("external 90 degree corner has coincident inside and outside face endpoints",()=>{
 const joins=wallCornerJoins([front,right]);
 const a=joins.get("front").end,b=joins.get("right").start;
 near(a.right,[4.07,-.07]);near(a.left,[3.93,.07]);
 near(a.right,b.right);near(a.left,b.left);
 const groups=[displayWallDraft(front,undefined,joins.get("front")),displayWallDraft(right,undefined,joins.get("right"))];
 for(const [index,group] of groups.entries()){
  const host=draftCatalogueHosts([front,right][index],group).find(h=>h.target==="wall");
  const face=host.finishFaces.right.geometry.getAttribute("position");
  assert.ok(Array.from({length:face.count},(_,i)=>i).some(i=>Math.abs(face.getX(i)-4.07)<1e-6&&Math.abs(face.getZ(i)+.07)<1e-6));
 }
 assert.deepEqual(front.end,[4,0]);assert.deepEqual(right.start,[4,0]);
});
test("starter house four external corners stay joined after connected perimeter edits",()=>{
 const walls=starterBuild(starterManifest()).walls,joins=wallCornerJoins(walls);
 for(const name of ["front","right","back","left"]){
  assert.ok(joins.get(name).start);assert.ok(joins.get(name).end);
 }
});
test("unequal wall thickness has matching physical miters without moving the centreline",()=>{
 const other={...right,assembly:{...assembly,thicknessMm:253}};
 const j=wallCornerJoins([front,other]);
 near(j.get("front").end.right,j.get("right").start.right);
 near(j.get("front").end.right,[4.1265,-.07]);
});
test("no guessing across gaps, levels, incompatible heights, nearby openings or 3-way junctions",()=>{
 const variants=[{...right,start:[4.01,0]}, {...right,levelId:"upper"}, {...right,heightM:2.7}, {...right,openings:[{openingId:"d",openingKind:"door",offsetM:0,widthM:.8,heightM:2.04,sillHeightM:0}]}, {...right,end:[.1,.01]}];
 for(const other of variants)assert.equal(wallCornerJoins([front,other]).size,0);
 assert.equal(wallCornerJoins([front,right,wall("third",[4,0],[5,1])]).size,0);
});
test("tool keys and swatches are reused, hover changes only instance colours",()=>{
 const group=new THREE.Group(),tray=createPhysicalToolTray(group);
 const action={area:"done"},layout={title:"Tools",note:"",width:400,height:200,buttons:[
  {label:"Paint",x:10,y:20,w:180,h:70,action,swatch:0xabcdef},
  {label:"Close",x:210,y:20,w:180,h:70,action}
 ]};
 tray.update(layout);assert.equal(group.children.length,2);assert.equal(tray.keys.count,2);assert.equal(tray.samples.count,1);
 const version=tray.keys.instanceMatrix.version,col=new THREE.Color();tray.keys.getColorAt(0,col);const initial=col.getHex();
 tray.highlight(0);tray.keys.getColorAt(0,col);assert.notEqual(col.getHex(),initial);assert.equal(tray.keys.instanceMatrix.version,version);
 tray.highlight(-1);tray.keys.getColorAt(0,col);assert.equal(col.getHex(),initial);
 tray.update({...layout,radial:true});assert.equal(tray.keys.count,0);tray.dispose();
});
test("opening frames and solid door leaves have physical depth and do not change aperture metadata",()=>{
 const door={openingId:"d",openingKind:"door",offsetM:1,widthM:.9,heightM:2.04,sillHeightM:0};
 const w={...front,openings:[door]};const frame=openingFrameVisual(w,door);
 assert.equal(frame.count,3);
 const group=displayWallDraft(w),leaf=group.children.find(c=>c.userData.catalogueDoorLeaf==="d");
 leaf.geometry.computeBoundingBox();
 assert.ok(leaf.geometry.boundingBox.max.z-leaf.geometry.boundingBox.min.z>.03);
 assert.equal(leaf.children.length,4);
 assert.equal(leaf.userData.localDoorMotion.kind,"swing");
 assert.equal(openingFrameVisual(w,{...door,openingKind:"window"}).count,4);
 assert.ok(nominalDoorSlab(w,door));assert.equal(door.widthM,.9);
});
