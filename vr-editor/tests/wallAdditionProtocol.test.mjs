import test from "node:test";
import assert from "node:assert/strict";
import {
  validateAdditionSketch,makeWallAdditionCommand,verifyWallAssemblyPreview,
} from "../src/wallAdditionProtocol.ts";
function scene(){
  return {
    scope:{workspaceId:"ws",projectId:"pr",documentId:"doc",
      revisionId:"revision",snapshotId:"snap-1",sourceSha256:"a".repeat(64),
      modelRevision:7},
  };
}
function command(){
  const s=scene(),sketch=validateAdditionSketch(s,{
    proposalId:"new-wall-1",levelId:"ground",
    start:[-2,0],end:[2,0],heightM:2.7,
  });
  return makeWallAdditionCommand(s,sketch,"profile-W01",[]);
}
function preview(){
  const cmd=command();
  return {
    accepted:true,reviewOnly:true,persisted:false,
    commercialPublicationAllowed:false,sourceGeometryAltered:false,
    workspaceId:cmd.workspaceId,proposalId:cmd.proposalId,
    baseModelRevision:cmd.baseModelRevision,
    assemblyProfileId:cmd.assemblyProfileId,
    package:{
      proposal_id:cmd.proposalId,revision_scope_key:"f".repeat(64),
      wall_length_m:4,wall_height_m:2.7,
      quantities:[{
        line_id:"a".repeat(32),trade:"carpentry",
        element:"Preliminary wall stud count",description:"Profile W01",
        value:8,unit:"No.",formula:"ceil(4/0.6)+1",
        status:"review_only",host_proposal_id:cmd.proposalId,
        specification_id:"assembly-source-1",
      },{
        line_id:"b".repeat(32),trade:"plastering",element:"Wall plasterboard lining",
        description:"13mm PB left face",value:10.8,unit:"m²",
        formula:"4*2.7",status:"review_only",host_proposal_id:cmd.proposalId,
        specification_id:"assembly-source-1",
      }],
      coordination_required:["electrical_new_wall_services_to_be_reviewed",
        "plumbing_new_wall_services_to_be_reviewed"],
      can_publish_commercial:false,original_source_modified:false,
    },
  };
}
test("authenticated wall assembly preview binds original source and all dependent trades",()=>{
 const c=command();
 assert.equal(c.sourceSha256,"a".repeat(64));
 assert.deepEqual(c.startPt,[-2,0]);
 const p=verifyWallAssemblyPreview(preview(),scene(),c);
 assert.equal(p.reviewOnly,true);
 assert.equal(p.package.quantities.length,2);
 assert.equal(p.package.can_publish_commercial,false);
});
test("client refuses a requested speculative source edit across revisions",()=>{
 const sketch=validateAdditionSketch(scene(),{
   proposalId:"wall-X",levelId:"level-1",
   start:[1,1],end:[3,1],heightM:2.7,
 });
 const s=scene();s.scope.modelRevision++;
 assert.throws(()=>makeWallAdditionCommand(s,sketch,"profile-1"),/Stale/);
});
test("client rejects cross-tenant proposal, fake approval and mismatched framing quantity",()=>{
 const c=command();
 const valid=preview();
 const variants=[
   {...valid,workspaceId:"other-tenant"},
   {...valid,proposalId:"other-wall"},
   {...valid,baseModelRevision:6},
   {...valid,persisted:true},
   {...valid,commercialPublicationAllowed:true},
   {...valid,reviewOnly:false},
   {...valid,package:{...valid.package,wall_length_m:9}},
   {...valid,package:{...valid.package,wall_height_m:3}},
   {...valid,package:{...valid.package,can_publish_commercial:true}},
   {...valid,package:{...valid.package,original_source_modified:true}},
   {...valid,package:{...valid.package,quantities:[
     valid.package.quantities[0],valid.package.quantities[0],
   ]}},
   {...valid,package:{...valid.package,quantities:[{
     ...valid.package.quantities[0],status:"Measured",
   }]}},
   {...valid,package:{...valid.package,quantities:[{
     ...valid.package.quantities[0],trade:"unlicensed",
   }]}},
   {...valid,package:{...valid.package,quantities:[{
     ...valid.package.quantities[0],value:Infinity,
   }]}},
 ];
 for(const v of variants)assert.throws(()=>verifyWallAssemblyPreview(v,scene(),c));
});
test("new wall cannot use guessed or degenerate geometry or arbitrary profile identifier",()=>{
 const s=scene();
 for(const invalid of [
   {start:[0,0],end:[0,0],heightM:2.7},
   {start:[0,0],end:[4,0],heightM:0},
   {start:[0,0],end:[4,0],heightM:Infinity},
   {start:[0,0],end:[4,0],heightM:21},
   {start:[0,0],end:[201,0],heightM:2.7},
 ])assert.throws(()=>validateAdditionSketch(s,{
    proposalId:"W1",levelId:"level-1",...invalid,
 }));
 const sketch=validateAdditionSketch(s,{
   proposalId:"W1",levelId:"L1",start:[0,0],end:[4,0],heightM:2.7,
 });
 assert.throws(()=>makeWallAdditionCommand(s,sketch,"../../etc/passwd"));
});
test("proposed doorway remains a typed hosted opening, not a source approval",()=>{
 const s=scene(),sketch=validateAdditionSketch(s,{
   proposalId:"W1",levelId:"L1",start:[0,0],end:[4,0],heightM:2.7,
 });
 const command=makeWallAdditionCommand(s,sketch,"profile-1",[{
   openingId:"door-1",offsetM:1,widthM:.9,heightM:2.1,
   sillHeightM:0,openingKind:"door",
 }]);
 assert.equal(command.openings[0].widthM,.9);
 assert.equal(Object.hasOwn(command,"approved"),false);
 assert.equal(Object.hasOwn(command,"companyRates"),false);
});
