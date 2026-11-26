import test from "node:test";
import assert from "node:assert/strict";
import {nominalTrimLayout,nominalTrimMesh} from "../src/constructionTrimVisual.ts";
import {defaultWallAssembly} from "../src/wallProfiles.ts";
const door={openingId:"door",openingKind:"door",offsetM:1,widthM:.9,heightM:2.04,sillHeightM:0};
const window={openingId:"window",openingKind:"window",offsetM:2.4,widthM:1,heightM:1,sillHeightM:.9};
const wall={proposalId:"w",scopeKey:"scope",levelId:"ground",start:[0,0],end:[4,0],heightM:2.4,openings:[door,window]};
const overlap=(a,b)=>Math.min(a.x1,b.x1)-Math.max(a.x0,b.x0)>1e-7&&Math.min(a.y1,b.y1)-Math.max(a.y0,b.y0)>1e-7;
test("skirting stops at door and architraves surround openings on solid wall",()=>{
 const pieces=nominalTrimLayout(wall);
 assert.ok(pieces.some(p=>p.kind==="skirting"));
 assert.ok(pieces.some(p=>p.kind==="architrave"));
 const holes=wall.openings.map(o=>({x0:o.offsetM,x1:o.offsetM+o.widthM,y0:o.sillHeightM,y1:o.sillHeightM+o.heightM}));
 pieces.forEach((p,i)=>{
  assert.ok(p.x0>=0&&p.x1<=4&&p.y0>=0&&p.y1<=2.4);
  assert.ok(holes.every(h=>!overlap(p,h)));
  assert.ok(pieces.slice(0,i).every(h=>!overlap(p,h)));
 });
 assert.ok(pieces.some(p=>p.kind==="architrave"&&Math.abs(p.y1-.9)<1e-7));
});
test("trim geometry rebuilds on resize and uses only internal faces",()=>{
 const a=nominalTrimMesh(wall),b=nominalTrimMesh({...wall,end:[5,0]});
 assert.ok(b.boundingBox.max.x>a.boundingBox.max.x);
 const exterior=nominalTrimMesh({...wall,assembly:defaultWallAssembly("external-timber")});
 assert.equal(a.count,2*exterior.count);
 assert.equal(nominalTrimMesh({...wall,assembly:defaultWallAssembly("blockwork")}),null);
});
test("invalid overlapping openings do not generate trim",()=>{
 assert.deepEqual(nominalTrimLayout({...wall,openings:[door,{...window,offsetM:1.5}]}),[]);
});
