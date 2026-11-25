import test from "node:test";
import assert from "node:assert/strict";
import {Mesh,Vector3} from "three";
import {displayWallDraft,displayCeilingDraft,illustrativeTimberFrame} from "../src/buildScene.ts";
import {makeLiningVisual,setLiningFinish,setLiningAppearance,makeShellCeilingLining} from "../src/constructionLiningVisual.ts";
const wall={proposalId:"test",scopeKey:"test",levelId:"ground",start:[1,2],end:[5,5],heightM:3,openings:[{openingId:"d",openingKind:"door",offsetM:1,widthM:.9,heightM:2.04,sillHeightM:0}]};
test("actual draft renderer has two interior lining faces, clipped to openings",()=>{
 const group=displayWallDraft(wall);
 const lining=group.children.filter(x=>x.userData.illustrativeLining);
 assert.equal(lining.length,2);
 for(const mesh of lining){
  assert.ok(mesh instanceof Mesh);assert.equal(mesh.visible,false);
  const p=mesh.geometry.attributes.position;
  for(let i=0;i<p.count;i++){
   const x=(p.getX(i)-1)*.8+(p.getZ(i)-2)*.6,y=p.getY(i);
   assert.ok(!(x>1+1e-5&&x<1.9-1e-5&&y>1e-5&&y<2.04-1e-5));
  }
  setLiningFinish(mesh,"sheeted");
  const raw=mesh.geometry.attributes.color,rawValues=Array.from(raw.array);
  setLiningFinish(mesh,"set");assert.equal(raw,mesh.geometry.attributes.color);assert.notDeepEqual(rawValues,Array.from(raw.array));
  setLiningFinish(mesh,"undercoat");
  const painted=mesh.geometry.attributes.color;
  for(let i=0;i<painted.count;i++)assert.equal(painted.getX(i),painted.getX(0));
 }
 const external=displayWallDraft({...wall,assembly:{profile:"external-timber",thicknessMm:140,exteriorSide:"left"}});
 assert.equal(external.children.filter(x=>x.userData.illustrativeLining).length,1);
 const masonry=displayWallDraft({...wall,assembly:{profile:"blockwork",thicknessMm:190,exteriorSide:"left"}});
 assert.equal(masonry.children.filter(x=>x.userData.illustrativeLining).length,0);
});
test("ceiling has underside sheet geometry and frame roles are rendered",()=>{
 const ceiling=displayCeilingDraft({start:[1,2],end:[4,6],heightM:2.7});
 const lining=ceiling.children.find(x=>x.userData.illustrativeLining);assert.ok(lining);
 const p=lining.geometry.attributes.position;
 for(let i=0;i<p.count;i++)assert.ok(p.getY(i)<2.7&&p.getY(i)>2.68);
 const frame=illustrativeTimberFrame(wall).children[0];
 assert.equal(frame.count,frame.userData.nominalFrameRoles.length);
 for(const role of ["king","trimmer","lintel","cripple","nogging","top-plate"])assert.ok(frame.userData.nominalFrameRoles.includes(role),role);
});
test("generated ceiling lining preserves a concave recess",()=>{
 const vertices=[[0,2.7,0],[6,2.7,0],[6,2.7,2],[0,2.7,0],[6,2.7,2],[0,2.7,2],[0,2.7,2],[3,2.7,2],[3,2.7,4],[0,2.7,2],[3,2.7,4],[0,2.7,4]];
 const mesh=makeShellCeilingLining(vertices);assert.ok(mesh);
 const p=mesh.geometry.attributes.position;
 for(let i=0;i<p.count;i++)assert.ok(!(p.getX(i)>3+1e-5&&p.getZ(i)>2+1e-5));
 assert.equal(makeShellCeilingLining([[0,2.7,0],[1,3,0],[0,2.7,1]]),null);
});
test("board type palette distinct; finish changes reuse the same geometry",()=>{
 const project=(x,y,offset)=>new Vector3(x,y,offset);
 const a=makeLiningVisual(3,2.7,[],project,"standard"),b=makeLiningVisual(3,2.7,[],project,"wet-area"),c=makeLiningVisual(3,2.7,[],project,"fire-rated");
 assert.ok(a&&b&&c);
 assert.notEqual(a.geometry.attributes.color.getY(0),b.geometry.attributes.color.getY(0));
 assert.notEqual(a.geometry.attributes.color.getX(0),c.geometry.attributes.color.getX(0));
 const g=a.geometry,colors=a.geometry.attributes.color;setLiningFinish(a,"sanded");assert.equal(a.geometry,g);
 setLiningAppearance(a,"set","wet-area");assert.equal(a.geometry.attributes.color,colors);assert.equal(a.userData.liningBoard,"wet-area");assert.equal(colors.getY(0),b.geometry.attributes.color.getY(0));
 assert.equal(makeLiningVisual(NaN,2.7,[],project),null);
});
