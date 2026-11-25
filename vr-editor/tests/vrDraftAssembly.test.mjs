import test from "node:test";
import assert from "node:assert/strict";
import {draftAssembly,draftAssemblyCost,STUDY_PROFILE} from "../src/vrDraftAssembly.ts";
import {projectWall,projectCeiling,footprintProjection} from "../src/footprintResize.ts";
const wall={proposalId:"wall",scopeKey:"test",levelId:"ground",start:[0,0],end:[4.2,0],heightM:2.7,openings:[{openingId:"door",openingKind:"door",offsetM:1,widthM:.9,heightM:2.1,sillHeightM:0}]};
const ceiling={proposalId:"ceiling",scopeKey:"test",levelId:"ground",start:[0,0],end:[4,5],heightM:2.7};
const state={walls:[wall],ceilings:[ceiling]};
const profile={...STUDY_PROFILE,floorM2:20,roofPlanM2:100,electricalPoints:8,plumbingPoints:3};
const get=(rows,id)=>rows.find(x=>x.id===id);
const close=(a,b)=>assert.ok(Math.abs(a-b)<.002,`expected ${b}, got ${a}`);
test("framing allowances respect opening base and head",()=>{
 const rows=draftAssembly(state,profile);
 assert.equal(get(rows,"studs").quantity,11);
 close(get(rows,"plates").quantity,7.5);
 close(get(rows,"noggins").quantity,4.2);
 assert.equal(get(rows,"jambs").quantity,2);
 close(get(rows,"headers").quantity,.9);
 assert.equal(get(rows,"sills").quantity,0);
 assert.equal(get(rows,"bracing").quantity,null);
});
test("boards, insulation, skirting, trim and ceiling use local geometry",()=>{
 const rows=draftAssembly(state,profile);
 close(get(rows,"boards").quantity,18.9/2.88);
 assert.equal(get(rows,"boards").purchase,8);
 close(get(rows,"insulation").quantity,9.45);
 close(get(rows,"skirting").quantity,6.6);
 close(get(rows,"architraves").quantity,10.2);
 assert.equal(get(rows,"ceiling").purchase,8);
 close(get(rows,"paint").quantity,38.9*2/16);
 assert.equal(get(rows,"paint").purchase,8);
});
test("explicit manual surface and rough-in allowances, no invented areas",()=>{
 const rows=draftAssembly(state,profile);
 close(get(rows,"floor").purchase,23.04);
 close(get(rows,"slab").quantity,2);
 close(get(rows,"roof").quantity,108.239);
 assert.equal(get(rows,"electrical").quantity,8);
 assert.equal(get(rows,"plumbing").quantity,3);
 for(const id of ["floor","slab","roof","electrical","plumbing"])assert.equal(get(draftAssembly(state,STUDY_PROFILE),id).quantity,null);
});
test("split costs use purchase vs net and distinguish margin from markup",()=>{
 const lines=[{id:"boards",trade:"Lining",label:"Boards",unit:"sheet",quantity:5,purchase:6}];
 const rates={boards:{material:"20",labour:"10"}};
 const a=draftAssemblyCost(lines,rates,25,10);
 assert.equal(a.material,12000);assert.equal(a.labour,5000);
 assert.equal(a.subtotal,17000);assert.equal(a.sell,22667);assert.equal(a.gst,2267);
 assert.equal(a.total,24934);assert.equal(a.partial,false);
 assert.equal(draftAssemblyCost(lines,rates,25,10,"markup").total,23375);
 assert.equal(a.commercialPublicationAllowed,false);
 assert.equal(a.trades[0].cents,17000);
});
test("missing and invalid rates stay partial; explicit zero is distinct",()=>{
 const lines=[{id:"x",trade:"Trade",label:"X",unit:"each",quantity:1,purchase:1}];
 assert.equal(draftAssemblyCost(lines,{},0,10).partial,true);
 assert.equal(draftAssemblyCost(lines,{x:{material:"-1",labour:"0"}},0,10).rows[0].material,null);
 assert.equal(draftAssemblyCost(lines,{x:{material:"0",labour:"0"}},0,10).partial,false);
 assert.throws(()=>draftAssemblyCost(lines,{},100,10),/Invalid/);
});
test("wall stretching, opening resizing and footprint projection update amounts without mutation",()=>{
 const before=JSON.stringify(state);
 const projected=footprintProjection({minX:0,maxX:5,minZ:0,maxZ:5},{minX:0,maxX:10,minZ:0,maxZ:5});
 const after={walls:[projectWall(wall,projected)],ceilings:[projectCeiling(ceiling,projected)]};
 const rows=draftAssembly(after,profile);
 close(get(rows,"insulation").quantity,8.4*2.7-1.89);
 close(get(rows,"skirting").quantity,15);
 assert.ok(get(rows,"ceiling").quantity>get(draftAssembly(state,profile),"ceiling").quantity);
 assert.equal(JSON.stringify(state),before);
 const wide={...wall,openings:[{...wall.openings[0],widthM:1.2}]};
 close(get(draftAssembly({walls:[wide],ceilings:[]},profile),"insulation").quantity,4.2*2.7-1.2*2.1);
});
test("raised windows add sill and trim without cutting base skirting",()=>{
 const window={...wall.openings[0],openingKind:"window",heightM:1,sillHeightM:.9};
 const rows=draftAssembly({walls:[{...wall,openings:[window]}],ceilings:[]},profile);
 close(get(rows,"sills").quantity,.9);close(get(rows,"skirting").quantity,8.4);
 close(get(rows,"architraves").quantity,7.6);
 assert.equal(get(rows,"windows").quantity,1);
});
test("invalid geometry and assumptions fail closed",()=>{
 assert.throws(()=>draftAssembly(state,{...profile,spacingMm:0}),/Invalid/);
 assert.throws(()=>draftAssembly(state,{...profile,electricalPoints:1.5}),/Invalid/);
 assert.throws(()=>draftAssembly({walls:[{...wall,openings:[wall.openings[0],{...wall.openings[0],openingId:"other"}]}],ceilings:[]},profile),/overlapping/);
 assert.throws(()=>draftAssembly({walls:[{...wall,heightM:1}],ceilings:[]},profile),/Invalid/);
});
