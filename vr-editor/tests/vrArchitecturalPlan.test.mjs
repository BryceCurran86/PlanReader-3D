import test from "node:test";
import assert from "node:assert/strict";
import {architecturalPlan} from "../src/architecturalPlan.ts";
const wall={proposalId:"a",scopeKey:"scope",levelId:"ground",start:[0,0],end:[5,0],heightM:2.7,assembly:{profile:"internal-timber",thicknessMm:116,exteriorSide:"left"},openings:[{openingId:"d",openingKind:"door",offsetM:1,widthM:.9,heightM:2.1,sillHeightM:0},{openingId:"w",openingKind:"window",offsetM:3,widthM:1,heightM:1,sillHeightM:.9}]};
test("orthographic draft uses actual thickness, opening gaps, symbols and metric dimensions",()=>{
 const plan=architecturalPlan({objects:[]},{walls:[wall]},"ground");
 assert.ok(plan.labels.some(l=>l.text==="5000"));
 assert.ok(plan.lines.some(l=>l.kind==="wall"&&Math.abs(l.a[1]-.058)<1e-9));
 assert.ok(plan.lines.some(l=>l.kind==="door"));
 assert.equal(plan.lines.filter(l=>l.kind==="window").length,2);
 for(const l of plan.lines.filter(l=>l.kind==="wall")){
  assert.ok(!(Math.min(l.a[0],l.b[0])<1.9-1e-7&&Math.max(l.a[0],l.b[0])>1+1e-7));
 }
 assert.equal(architecturalPlan({objects:[]},{walls:[wall]},"upper").lines.length,0);
});
test("source evidence stays a line, unknown openings remain unlocated and source move updates position",()=>{
 const row={objectId:"s",objectType:"wall",levelId:"ground",renderState:"verified",geometry:{kind:"wallFace",start:[0,0],end:[3,0],heightM:2.7},openingReview:{recordCount:2,positioned:[{kind:"door",offsetM:1,widthM:.9}]}};
 const p=architecturalPlan({objects:[row]},{walls:[]},"ground",new Set(["s"]),null,[{objectId:"s",dx:1,dz:2}]);
 assert.equal(p.unlocated,1);assert.equal(p.lines.filter(l=>l.kind==="source").length,1);
 assert.deepEqual(p.lines[0].a,[1,2]);
 assert.equal(p.lines.some(l=>l.kind==="door"),false);
 assert.equal(architecturalPlan({objects:[row]},{walls:[]},"ground",new Set()).lines.length,0);
});
