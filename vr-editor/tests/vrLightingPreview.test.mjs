import test from "node:test";
import assert from "node:assert/strict";
import {MAX_PREVIEW_LIGHTS,previewLightingRole,nearestPreviewLights} from "../src/lightingPreview.ts";
import {ITEM_CATALOGUE} from "../src/itemCatalogue.ts";
import {VISUAL_PRESETS,isLightingMood} from "../src/visualRealism.ts";
test("light previews recognize light fittings and switches but not fans or power sockets",()=>{
 const shape=s=>ITEM_CATALOGUE.find(i=>i.visual.kind==="fixture"&&i.visual.shape===s);
 assert.equal(previewLightingRole(shape("switch")),"switch");
 assert.equal(previewLightingRole(shape("downlight")),"light");
 assert.equal(previewLightingRole(shape("socket")),null);
 assert.equal(previewLightingRole(shape("fan")),null);
 assert.equal(isLightingMood("night"),true);
 assert.ok(VISUAL_PRESETS.night.ambientIntensity<VISUAL_PRESETS.daylight.ambientIntensity);
});
test("nearby light pool is deterministic and capped for headset performance",()=>{
 const fixtures=Array.from({length:12},(_,i)=>({id:String(i),position:[i,0,0]}));
 const result=nearestPreviewLights(fixtures,[0,0,0]);
 assert.equal(result.length,MAX_PREVIEW_LIGHTS);
 assert.deepEqual(result.map(f=>f.id),["0","1","2","3"]);
 assert.deepEqual(nearestPreviewLights(fixtures,[100,0,0]),[]);
 assert.deepEqual(nearestPreviewLights(fixtures,[NaN,0,0]),[]);
});