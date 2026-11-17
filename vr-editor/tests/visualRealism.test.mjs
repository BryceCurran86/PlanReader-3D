import test from "node:test";
import assert from "node:assert/strict";
import {
  isLightingMood, isRenderQuality, maxRenderPixelRatio, mayRenderWallFace,
  shadowMapSize, VISUAL_PRESETS,
} from "../src/visualRealism.ts";

test("three bounded illumination presets provide finite plausible values", () => {
  assert.deepEqual(Object.keys(VISUAL_PRESETS).sort(), ["daylight","dusk","studio"]);
  for (const [id, preset] of Object.entries(VISUAL_PRESETS)) {
    assert.equal(isLightingMood(id), true);
    assert.match(preset.label, /illustrative/);
    assert.ok(preset.exposure > 0 && preset.exposure <= 2);
    assert.ok(preset.ambientIntensity > 0 && preset.ambientIntensity <= 4);
    assert.ok(preset.sunIntensity > 0 && preset.sunIntensity <= 5);
    assert.equal(preset.sunPosition.length, 3);
    assert.ok(preset.sunPosition.every(Number.isFinite));
    assert.ok(preset.materialRoughness >= 0.5 && preset.materialRoughness <= 1);
    for (const field of ["background","ambientSky","ambientGround","sunColor"]) {
      assert.ok(Number.isInteger(preset[field]) && preset[field] >= 0 &&
        preset[field] <= 0xffffff);
    }
  }
  assert.equal(isLightingMood("photoreal_verified"), false);
  assert.equal(isLightingMood("__proto__"), false);
});

test("render quality caps are bounded and VR never gets a desktop pixel multiplier", () => {
  assert.equal(isRenderQuality("balanced"), true);
  assert.equal(isRenderQuality("high"), true);
  assert.equal(isRenderQuality("ultra"), false);
  assert.equal(maxRenderPixelRatio("balanced", false), 1.5);
  assert.equal(maxRenderPixelRatio("high", false), 2);
  assert.equal(maxRenderPixelRatio("high", true), 1);
  assert.equal(shadowMapSize("high"), 2048);
  assert.equal(shadowMapSize("balanced"), 1024);
});

test("no missing, unknown or nonfinite height may be photorealistically extruded", () => {
  assert.equal(mayRenderWallFace("wallFace", 2.7), true);
  for (const h of [undefined,null,0,-1,NaN,Infinity,1000]) {
    assert.equal(mayRenderWallFace("wallFace",h), false);
  }
  assert.equal(mayRenderWallFace("wallLine",2.7),false);
  assert.equal(mayRenderWallFace("room",2.7),false);
});
