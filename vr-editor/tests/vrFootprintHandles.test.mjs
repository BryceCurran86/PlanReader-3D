import test from "node:test";
import assert from "node:assert/strict";
import { Scene, Raycaster, Vector3 } from "three";
import { FOOTPRINT_EDGES, footprintHandlePoint, resizeFromHandle, footprintProjection, projectWall } from "../src/footprintResize.ts";
import { createFootprintGizmo } from "../src/footprintScene.ts";
const box={minX:0,maxX:10,minZ:0,maxZ:8};
test("four additional edges constrain movement to a single dimension",()=>{
 assert.deepEqual(FOOTPRINT_EDGES,["top","right","bottom","left"]);
 assert.deepEqual(footprintHandlePoint(box,"right"),[10,4]);
 assert.deepEqual(resizeFromHandle(box,"right",[12.02,6]),{...box,maxX:12});
 assert.deepEqual(resizeFromHandle(box,"left",[-2,1]),{...box,minX:-2});
 assert.deepEqual(resizeFromHandle(box,"top",[8,-1]),{...box,minZ:-1});
 assert.deepEqual(resizeFromHandle(box,"bottom",[2,9]),{...box,maxZ:9});
 assert.deepEqual(resizeFromHandle(box,"bottom-right",[12,9]),{...box,maxX:12,maxZ:9});
 assert.equal(resizeFromHandle(box,"left",[11,4]),null);
});
test("midpoint handles are pickable in the real scene",()=>{
 const scene=new Scene(),gizmo=createFootprintGizmo(scene);
 gizmo.show(box);
 for(const edge of FOOTPRINT_EDGES){
  const [x,z]=footprintHandlePoint(box,edge);
  const ray=new Raycaster(new Vector3(x,5,z),new Vector3(0,-1,0));
  assert.equal(gizmo.pick(ray),edge);
 }
 gizmo.show(null);
 assert.equal(gizmo.pick(new Raycaster(new Vector3(10,5,4),new Vector3(0,-1,0))),null);
});
test("edge resize reuses existing projected-wall aperture preservation",()=>{
 const next=resizeFromHandle(box,"right",[12,4]);
 const wall={start:[0,0],end:[10,0],heightM:2.7,openings:[{openingId:"d",openingKind:"door",offsetM:4,widthM:1,heightM:2.1,sillHeightM:0}]};
 const projected=projectWall(wall,footprintProjection(box,next));
 assert.deepEqual(projected.end,[12,0]);
 assert.equal(projected.openings[0].widthM,1);
 assert.ok(Math.abs(projected.openings[0].offsetM-4.9)<1e-9);
});
