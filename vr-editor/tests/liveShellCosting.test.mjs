import test from "node:test";
import assert from "node:assert/strict";
import {newAssemblyStudy,evaluateAssemblyStudy} from "../src/vrAssemblyStudy.ts";
const geometry=(area,roof,volume)=>({walls:[],ceilings:[],shellMetrics:{floorM2:area,roofM2:roof,slabM3:volume,ceilingM2:area}});
const quantity=(r,id)=>r.rows.find(row=>row.id===id).quantity;
test("shell quantities update live and baseline retains its own dimensions",()=>{
 const base=geometry(80,86,8),next=geometry(100,108,10);
 const study={...newAssemblyStudy(),enabled:true,baseline:base,gst:"0",rates:{floor:{material:"0",labour:"10"}}};
 const e=evaluateAssemblyStudy(next,study);
 assert.equal(e.error,"");
 assert.equal(quantity(e.result,"floor"),100);
 assert.equal(quantity(e.result,"roof"),108);
 assert.equal(quantity(e.result,"slab"),10);
 assert.equal(quantity(e.prior,"floor"),80);
 assert.equal(e.result.total-e.prior.total,20000);
 assert.equal(quantity(e.result,"ceiling"),Math.round(100/2.88*1000)/1000);
});
test("manual override and missing shell do not fabricate floor or roof",()=>{
 const study={...newAssemblyStudy(),enabled:true,followShell:false};
 const e=evaluateAssemblyStudy(geometry(100,108,10),study);
 assert.equal(quantity(e.result,"floor"),null);
 assert.equal(quantity(e.result,"roof"),null);
 const missing=evaluateAssemblyStudy({walls:[],ceilings:[]},{...study,followShell:true});
 assert.equal(quantity(missing.result,"slab"),null);
});
test("explicit ceilings are not double counted with generated shell ceiling",()=>{
 const g={...geometry(100,108,10),ceilings:[{start:[0,0],end:[5,4]}]};
 const e=evaluateAssemblyStudy(g,{...newAssemblyStudy(),enabled:true});
 assert.equal(quantity(e.result,"ceiling"),Math.round(20/2.88*1000)/1000);
});
