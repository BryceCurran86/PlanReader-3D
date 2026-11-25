import test from "node:test";
import assert from "node:assert/strict";
import {Raycaster,Vector3,MeshStandardMaterial} from "three";
import {createWallTextureLibrary,patternPixels,patternRepeat,exteriorPattern} from "../src/wallTextures.ts";
import {defaultWallAssembly} from "../src/wallProfiles.ts";
import {displayWallDraft} from "../src/buildScene.ts";
import {layerVisible,cycleLayer,itemLayerVisible,surfaceLayerVisible,CONSTRUCTION_LAYERS} from "../src/constructionLayers.ts";
import {ITEM_CATALOGUE} from "../src/itemCatalogue.ts";
import {EMPTY_BUILD} from "../src/buildPlacement.ts";
import {buildMenuLayout,EMPTY_ITEM_BROWSER} from "../src/catalogueMenu.ts";
const wall={proposalId:"w",scopeKey:"test",levelId:"ground",start:[0,0],end:[4,0],heightM:2.7,openings:[{openingId:"o",openingKind:"passage",offsetM:1,widthM:1,heightM:2.1,sillHeightM:0}]};
test("deterministic textures are shared, distinguish profiles and preserve real metre scale",()=>{
 const library=createWallTextureLibrary();
 assert.equal(library.get("internal-timber"),null);
 const brick=library.get("brick-veneer-timber");
 assert.strictEqual(brick.texture,library.get("brick-veneer-steel").texture);
 assert.notStrictEqual(brick.texture,library.get("blockwork").texture);
 assert.deepEqual(patternRepeat("brick"),[.46,.152]);
 assert.deepEqual(patternPixels("brick"),patternPixels("brick"));
 assert.notDeepEqual(patternPixels("brick"),patternPixels("cladding"));
 assert.equal(exteriorPattern("concrete"),"concrete");
 library.dispose();
});
test("exterior detail occupies one side only and does not fill apertures",()=>{
 const library=createWallTextureLibrary();
 for(const side of ["left","right"]){
  const group=displayWallDraft({...wall,assembly:{...defaultWallAssembly("brick-veneer-timber"),exteriorSide:side}},library);
  group.updateMatrixWorld(true);
  const detail=group.children.find(x=>x.userData.exteriorTexture);
  assert.ok(detail.material instanceof MeshStandardMaterial);
  assert.ok(detail.material.map);
  detail.geometry.computeBoundingBox();
  const box=detail.geometry.boundingBox;
  assert.ok(side==="left"?box.min.z>0:box.max.z<0);
  assert.ok(detail.geometry.getAttribute("uv").count>0);
  assert.equal(new Raycaster(new Vector3(1.5,1,1),new Vector3(0,0,-1)).intersectObject(detail).length,0);
  const insulation=group.children.find(x=>x.userData.illustrativeInsulation);
  assert.ok(insulation);assert.equal(insulation.visible,false);
 }
 assert.equal(displayWallDraft({...wall,assembly:defaultWallAssembly("blockwork")},library).children.some(x=>x.userData.illustrativeInsulation),false);
 library.dispose();
});
test("layer overrides are independent, resettable and never reveal roof in a cutaway",()=>{
 const electrical=ITEM_CATALOGUE.find(x=>x.group==="electrical-rough-in");
 const plumbing=ITEM_CATALOGUE.find(x=>x.group==="plumbing-rough-in");
 assert.equal(itemLayerVisible("finished",electrical,{}),false);
 const show=cycleLayer({},"electrical");
 assert.equal(itemLayerVisible("finished",electrical,show),true);
 assert.equal(itemLayerVisible("finished",plumbing,show),false);
 const hide=cycleLayer(show,"electrical");
 assert.equal(itemLayerVisible("framing",electrical,hide),false);
 assert.equal(cycleLayer(hide,"electrical").electrical,"auto");
 assert.equal(surfaceLayerVisible("finished","roof",{roof:"show"},true),false);
 assert.equal(surfaceLayerVisible("finished","ceiling",{ceiling:"hide"}),false);
 assert.equal(surfaceLayerVisible("framing","roof",{roof:"show"}),true);
 assert.equal(layerVisible({insulation:"show"},"insulation",false),true);
});
test("radial tools offer direct drawing, layers, more tools and guarded opening tools",()=>{
 const q={selectedWall:null,gridM:.05,axis:"auto",nudgeM:.05,pinned:false,help:false,deleteArmed:false,radial:true};
 const layout=buildMenuLayout(EMPTY_BUILD,"ground",EMPTY_ITEM_BROWSER,undefined,false,0,"","finished",false,undefined,undefined,q);
 assert.equal(layout.radial,true);assert.equal(layout.buttons.length,9);
 assert.equal(layout.buttons.find(b=>b.label==="Door").disabled,true);
 assert.ok(layout.buttons.some(b=>b.action.area==="quest"&&b.action.action==="more-tools"));
 assert.ok(layout.buttons.every(b=>b.x>=0&&b.y>=0&&b.x+b.w<=layout.width&&b.y+b.h<=layout.height));
 const layers=buildMenuLayout(EMPTY_BUILD,"ground",EMPTY_ITEM_BROWSER,undefined,false,0,"","finished",false,undefined,undefined,{...q,layersOpen:true,layers:{roof:"hide"}});
 assert.equal(layers.buttons.filter(b=>b.action.area==="layer").length,CONSTRUCTION_LAYERS.length);
 assert.ok(layers.buttons.some(b=>b.label==="Roof · HIDE"));
});
