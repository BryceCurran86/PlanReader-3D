import test from "node:test";
import assert from "node:assert/strict";
import {nominalFrameLayout,nominalLiningLayout,NOMINAL_TIMBER,NOMINAL_LINING} from "../src/constructionDetailLayout.ts";

const door={x0:.9,x1:1.8,y0:0,y1:2.04};
const window={x0:2.7,x1:3.6,y0:.9,y1:2.1};
const overlaps=(a,b)=>Math.min(a.x1,b.x1)-Math.max(a.x0,b.x0)>1e-7&&Math.min(a.y1,b.y1)-Math.max(a.y0,b.y0)>1e-7;
const area=r=>(r.x1-r.x0)*(r.y1-r.y0);
test("nominal frame includes plates, jamb structure, lintels, sill and short studs without filling openings",()=>{
 const members=nominalFrameLayout(5,3,[door,window]);
 for(const role of ["bottom-plate","top-plate","stud","king","trimmer","lintel","sill","cripple","nogging"])assert.ok(members.some(m=>m.role===role),role);
 assert.equal(members.filter(m=>m.role==="top-plate").length,2);
 for(const member of members){
  assert.ok(member.x0>=0&&member.x1<=5&&member.y0>=0&&member.y1<=3);
  assert.ok(!overlaps(member,door)&&!overlaps(member,window));
 }
 assert.ok(members.some(m=>m.role==="cripple"&&m.x0>=window.x0&&m.x1<=window.x1&&m.y1<=window.y0));
 assert.ok(members.some(m=>m.role==="cripple"&&m.x0>=door.x0&&m.x1<=door.x1&&m.y0>=door.y1));
});
test("tall frames use repeated nogging rows; editable nominal parameters",()=>{
 const members=nominalFrameLayout(3,4.5,[],{...NOMINAL_TIMBER,topPlates:1,studSpacing:.6,noggingSpacing:1});
 assert.equal(members.filter(m=>m.role==="top-plate").length,1);
 assert.equal(new Set(members.filter(m=>m.role==="nogging").map(m=>m.y0)).size,4);
 assert.ok(members.some(m=>m.role==="stud"&&Math.abs((m.x0+m.x1)/2-.6)<1e-6));
});
test("sheet layout covers exactly the solid surface and staggers butt joints",()=>{
 const layout=nominalLiningLayout(5,3,[door,window]);
 assert.ok(Math.abs(layout.boards.reduce((sum,r)=>sum+area(r),0)-(15-area(door)-area(window)))<1e-7);
 for(const board of layout.boards)assert.ok(!overlaps(board,door)&&!overlaps(board,window));
 for(let i=0;i<layout.boards.length;i++)for(let j=0;j<i;j++)assert.ok(!overlaps(layout.boards[i],layout.boards[j]));
 for(const joint of layout.joints){
  assert.ok(joint.to>joint.from);
  for(const h of [door,window]){
   if(joint.axis==="horizontal"&&joint.at>=h.y0&&joint.at<=h.y1)assert.ok(joint.to<=h.x0+1e-7||joint.from>=h.x1-1e-7);
   if(joint.axis==="vertical"&&joint.at>=h.x0&&joint.at<=h.x1)assert.ok(joint.to<=h.y0+1e-7||joint.from>=h.y1-1e-7);
  }
 }
 assert.ok(layout.joints.some(j=>j.kind==="butt"&&j.at===2.4));
 assert.ok(layout.joints.some(j=>j.kind==="butt"&&j.at===1.2));
 assert.ok(layout.fixings.length>0);
 assert.ok(layout.fixings.every(({x,y})=>![door,window].some(h=>x>=h.x0&&x<=h.x1&&y>=h.y0&&y<=h.y1)));
});
test("small ceiling and custom sheet dimensions remain metric",()=>{
 const layout=nominalLiningLayout(1,1,[],NOMINAL_LINING);
 assert.equal(layout.boards.length,1);
 assert.equal(area(layout.boards[0]),1);
 assert.equal(layout.joints.length,4);
 assert.ok(nominalLiningLayout(4,3,[],{...NOMINAL_LINING,sheetWidth:1.35}).joints.some(j=>j.kind==="recessed"&&j.at===1.35));
});
test("reject nonfinite sizes, overlapping/out-of-bounds apertures and invalid presets",()=>{
 for(const fn of [nominalFrameLayout,nominalLiningLayout]){
  assert.throws(()=>fn(NaN,3,[]));
  assert.throws(()=>fn(5,3,[door,{...door,x0:1}]));
  assert.throws(()=>fn(5,3,[{...window,x1:6}]));
 }
 assert.throws(()=>nominalFrameLayout(5,3,[],{...NOMINAL_TIMBER,studSpacing:0}));
 assert.throws(()=>nominalLiningLayout(5,3,[],{...NOMINAL_LINING,sheetWidth:0}));
});
