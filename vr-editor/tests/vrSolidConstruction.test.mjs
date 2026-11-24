import test from "node:test";
import assert from "node:assert/strict";
import {Mesh,MeshStandardMaterial,InstancedMesh,Matrix4,Box3,Vector3} from "three";
import {displayWallDraft,displayCeilingDraft,illustrativeTimberFrame} from "../src/buildScene.ts";
import {showConstructionItem} from "../src/constructionStages.ts";
import {ITEM_CATALOGUE} from "../src/itemCatalogue.ts";
const wall={proposalId:"w",scopeKey:"test",levelId:"ground",start:[0,0],end:[4,0],heightM:2.7,openings:[{openingId:"d",openingKind:"door",offsetM:1,widthM:.9,heightM:2.1,sillHeightM:0}]};
test("local finishes are opaque lit meshes, not review wireframes",()=>{
 const group=displayWallDraft(wall);
 for(const key of ["catalogueWallFace","catalogueDoorLeaf"]){
  const mesh=group.children.find(c=>c.userData[key]);
  assert.ok(mesh instanceof Mesh);
  assert.ok(mesh.material instanceof MeshStandardMaterial);
  assert.equal(mesh.material.opacity,1);assert.equal(mesh.material.transparent,false);assert.equal(mesh.material.depthWrite,true);
 }
 const ceiling=displayCeilingDraft({start:[0,0],end:[4,5],heightM:2.7});
 assert.ok(ceiling.material instanceof MeshStandardMaterial);assert.equal(ceiling.material.transparent,false);
});
test("nominal framing uses real solid members with door opening clear",()=>{
 const group=illustrativeTimberFrame(wall);
 assert.equal(group.userData.illustrativeFraming,true);
 assert.equal(group.visible,false);
 assert.equal(group.children.length,1);
 const m=group.children[0];assert.ok(m instanceof InstancedMesh);assert.ok(m.count>8);
 m.geometry.computeBoundingBox();
 for(let i=0;i<m.count;i++){
  const matrix=new Matrix4();m.getMatrixAt(i,matrix);
  const b=m.geometry.boundingBox.clone().applyMatrix4(matrix);
  assert.ok(!(b.min.x<1.9-1e-6&&b.max.x>1+1e-6&&b.min.y<2.1-1e-6&&b.max.y>1e-6),"framing obstructs door");
 }
 assert.equal(illustrativeTimberFrame({...wall,end:[0,0]}).children.length,0);
});
test("combined framing stage shows placed service catalogue items",()=>{
 const service=ITEM_CATALOGUE.find(x=>x.group==="electrical-rough-in");
 assert.ok(service);assert.equal(showConstructionItem("framing",service),true);
 assert.equal(showConstructionItem("rough-in",service),true);
 assert.equal(showConstructionItem("finished",service),false);
});
