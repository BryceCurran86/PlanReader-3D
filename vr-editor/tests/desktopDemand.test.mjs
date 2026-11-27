import test from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import {DesktopFrameDemand,DesktopRenderGovernor} from "../src/visualRealism.ts";
import {neutralStudioTexture} from "../src/neutralStudioTexture.ts";
test("desktop demand renders changed inputs, active drags and async heartbeat, skips idle frames",()=>{
 const d=new DesktopFrameDemand(),state={};
 assert.equal(d.shouldDraw(0,[state,0]),true);
 assert.equal(d.shouldDraw(16,[state,0]),false);
 assert.equal(d.shouldDraw(499,[state,0]),false);
 assert.equal(d.shouldDraw(500,[state,0]),true);
 assert.equal(d.shouldDraw(516,[state,1]),true);
 assert.equal(d.shouldDraw(532,[state,1],true),true);
 assert.equal(d.shouldDraw(548,[state,1]),false);
 d.reset();assert.equal(d.shouldDraw(549,[state,1]),true);
});
test("idle time does not falsely downgrade desktop quality",()=>{
 const g=new DesktopRenderGovernor();g.allow(0,"high",false);g.complete(0,5);
 for(let i=1;i<=5;i++){g.idle();g.complete(i*1000,5);}
 assert.equal(g.cap,2);
});
test("studio fallback is finite bounded HDR and needs no offscreen room render",()=>{
 const t=neutralStudioTexture();assert.equal(t.image.width,256);assert.equal(t.image.height,128);
 assert.equal(t.mapping,THREE.EquirectangularReflectionMapping);assert.equal(t.type,THREE.FloatType);
 let peak=0;for(const n of t.image.data){assert.ok(Number.isFinite(n)&&n>=0);peak=Math.max(peak,n);}
 assert.ok(peak>2&&peak<8);t.dispose();
});
