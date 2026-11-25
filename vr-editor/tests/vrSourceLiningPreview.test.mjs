import test from "node:test";
import assert from "node:assert/strict";
import {sourceWallLiningPreview,sourceCeilingLiningPreview} from "../src/sourceLiningPreview.ts";
const row={objectId:"wall",objectType:"wall",renderState:"verified",unresolvedIssues:[],geometry:{kind:"wallFace",start:[1,2],end:[5,5],heightM:2.7},openingReview:{recordCount:1,positioned:[{openingId:"d",kind:"door",offsetM:1,widthM:1,sillM:0,heightM:2.04}]}};
test("source wall preview preserves input, both sides follow witnessed plane and no inferred cutout",()=>{
 const before=JSON.stringify(row),group=sourceWallLiningPreview(row);
 assert.ok(group);assert.equal(group.visible,false);assert.equal(group.children.length,2);
 for(const mesh of group.children){
  const p=mesh.geometry.attributes.position;
  for(let i=0;i<p.count;i++){
   const x=p.getX(i)-1,z=p.getZ(i)-2,offset=-.6*x+.8*z;
   assert.ok(Math.abs(offset)<=.008+1e-6);
   assert.ok(p.getY(i)>=0&&p.getY(i)<=2.7+1e-6);
  }
  assert.ok(mesh.userData.illustrativeLining);
 }
 assert.equal(JSON.stringify(row),before);
 assert.equal(sourceWallLiningPreview({...row,renderState:"review"}),null);
 assert.equal(sourceWallLiningPreview({...row,unresolvedIssues:["unresolved"]}),null);
 assert.equal(sourceWallLiningPreview({...row,geometry:{...row.geometry,kind:"wallLine"}}),null);
 assert.equal(sourceWallLiningPreview({...row,geometry:{...row.geometry,heightM:7}}),null);
});
test("source ceiling preview uses only witnessed ceiling triangles and not floors",()=>{
 const surface={kind:"ceiling",renderState:"verified",commercialAuthority:false,vertices:[[0,2.7,0],[4,2.7,0],[0,2.7,3]]};
 const group=sourceCeilingLiningPreview(surface);assert.ok(group);
 const p=group.children[0].geometry.attributes.position;
 for(let i=0;i<p.count;i++)assert.ok(p.getX(i)/4+p.getZ(i)/3<=1+1e-6);
 assert.equal(sourceCeilingLiningPreview({...surface,kind:"floor"}),null);
 assert.equal(sourceCeilingLiningPreview({...surface,commercialAuthority:true}),null);
});
