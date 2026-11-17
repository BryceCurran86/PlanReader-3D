import test from "node:test";
import assert from "node:assert/strict";
import { sourceWallUV, createPresentationRoughnessTile, isSurfaceDetail } from "../src/surfaceDetail.ts";

test("subtle wall microdetail uses bounded source geometry without creating geometry", () => {
  assert.equal(isSurfaceDetail("smooth"), true);
  assert.equal(isSurfaceDetail("subtle"), true);
  assert.equal(isSurfaceDetail("actual-plaster-certified"), false);
  const uv = sourceWallUV(4, 2.7);
  assert.ok(uv instanceof Float32Array);
  assert.equal(uv.length, 12);
  assert.deepEqual([...uv.slice(0,6)], [0,0,8,0,8,Math.fround(5.4)]);
  assert.equal(sourceWallUV(0,2.4),null);
  assert.equal(sourceWallUV(NaN,2.4),null);
  assert.equal(sourceWallUV(4,Infinity),null);
  assert.equal(sourceWallUV(4,0),null);
  assert.equal(sourceWallUV(10001,2),null);
});
test("microsurface tile is repeatable, small, neutral and not a texture asset download", () => {
  const a=createPresentationRoughnessTile(),b=createPresentationRoughnessTile();
  assert.equal(a.length,64*64*4);
  assert.deepEqual(a,b);
  for(let i=0;i<a.length;i+=4) {
    assert.ok(a[i]>=231 && a[i]<=247);
    assert.equal(a[i],a[i+1]);
    assert.equal(a[i],a[i+2]);
    assert.equal(a[i+3],255);
  }
});
