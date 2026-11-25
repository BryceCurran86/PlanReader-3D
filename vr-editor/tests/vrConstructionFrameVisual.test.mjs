import test from "node:test";
import assert from "node:assert/strict";
import {Matrix4} from "three";
import {nominalWallConnections,nominalCeilingFraming,nominalShellFraming} from "../src/constructionFrameVisual.ts";
import {connectedDraftShell} from "../src/connectedDraftShell.ts";
import {CONSTRUCTION_LAYERS,layerVisible} from "../src/constructionLayers.ts";
import {buildMenuLayout,EMPTY_ITEM_BROWSER} from "../src/catalogueMenu.ts";
import {EMPTY_BUILD} from "../src/buildPlacement.ts";
const wall={proposalId:"w",scopeKey:"test",levelId:"ground",start:[0,0],end:[5,0],heightM:2.7,openings:[{openingId:"d",openingKind:"door",offsetM:1.5,widthM:1,heightM:2.1,sillHeightM:0}]};
test("nominal braces avoid apertures and unsupported masonry/steel assemblies",()=>{
 const group=nominalWallConnections(wall);
 const brace=group.children.find(x=>x.userData.constructionAccessory==="bracing");
 assert.ok(brace&&brace.count===2);
 const matrix=new Matrix4();brace.geometry.computeBoundingBox();
 for(let i=0;i<brace.count;i++){
  brace.getMatrixAt(i,matrix);const bounds=brace.geometry.boundingBox.clone().applyMatrix4(matrix);
  assert.ok(bounds.max.x<1.5||bounds.min.x>2.5);
 }
 assert.ok(group.children.some(x=>x.userData.constructionAccessory==="tie-down"));
 assert.equal(nominalWallConnections({...wall,assembly:{profile:"blockwork",thicknessMm:190,exteriorSide:"left"}}).children.length,0);
 assert.equal(nominalWallConnections({...wall,assembly:{profile:"internal-steel",thicknessMm:116,exteriorSide:"left"}}).children.length,0);
});
const ring=pts=>pts.map((p,i)=>({...wall,proposalId:"w"+i,start:p,end:pts[(i+1)%pts.length],openings:[]}));
test("explicit rectangular ceiling and shell display bounded nominal members; complex roof abstains",()=>{
 const ceiling=nominalCeilingFraming({start:[0,0],end:[6,4],heightM:2.7});
 assert.ok(ceiling&&ceiling.count>2);
 const settings={roof:"gable",pitchDeg:30,slabMm:100};
 const shell=connectedDraftShell(ring([[0,0],[6,0],[6,4],[0,4]]),settings);
 const group=nominalShellFraming(shell);
 for(const kind of ["roof-frame","ceiling-frame"])assert.ok(group.children.some(x=>x.userData.constructionAccessory===kind));
 const irregular=connectedDraftShell(ring([[0,0],[6,0],[6,2],[3,2],[3,4],[0,4]]),settings);
 assert.equal(nominalShellFraming(irregular).children.length,0);
 assert.equal(nominalCeilingFraming({start:[0,0],end:[0,4],heightM:2.7}),null);
});
test("new independent layers and accessible board controls fit menu bounds",()=>{
 const quest={selectedWall:wall,gridM:.05,axis:"auto",nudgeM:.05,pinned:true,help:false,deleteArmed:false,liningBoard:"wet-area"};
 const menu=buildMenuLayout(EMPTY_BUILD,"ground",EMPTY_ITEM_BROWSER,undefined,false,0,"","set",true,undefined,undefined,quest);
 assert.ok(menu.buttons.some(b=>b.action.area==="lining"&&b.action.action==="board"&&b.label.includes("wet-area")));
 assert.ok(menu.buttons.some(b=>b.action.area==="lining"&&b.action.action==="inspect"&&!b.disabled));
 const layers=buildMenuLayout(EMPTY_BUILD,"ground",EMPTY_ITEM_BROWSER,undefined,false,0,"","framing",false,undefined,undefined,{...quest,layersOpen:true});
 for(const layout of [menu,layers])for(const b of layout.buttons)assert.ok(b.x>=0&&b.y>=0&&b.x+b.w<=layout.width&&b.y+b.h<=layout.height);
 for(const name of ["bracing","tie-down","ceiling-frame","roof-frame"]){
  assert.ok(CONSTRUCTION_LAYERS.some(([id])=>id===name));assert.equal(layerVisible({[name]:"hide"},name,true),false);
 }
});
