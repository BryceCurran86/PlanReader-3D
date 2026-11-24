import test from "node:test";
import assert from "node:assert/strict";
import {newAssemblyStudy,evaluateAssemblyStudy,immersiveBudget,budgetHeadline} from "../src/vrAssemblyStudy.ts";
import {buildMenuLayout,EMPTY_ITEM_BROWSER} from "../src/catalogueMenu.ts";
import {EMPTY_BUILD} from "../src/buildPlacement.ts";
const w={proposalId:"wall",scopeKey:"scope",levelId:"ground",start:[0,0],end:[4,0],heightM:2.7,openings:[]};
const geometry={walls:[w],ceilings:[]};
const summarize=(g,s)=>immersiveBudget(g,s,evaluateAssemblyStudy(g,s));
test("disabled and missing rates never display a false zero budget",()=>{
 const s=newAssemblyStudy();
 assert.equal(summarize(geometry,s).status,"disabled");
 s.enabled=true;
 const b=summarize(geometry,s);
 assert.equal(b.status,"unpriced");assert.equal(b.total,null);assert.equal(b.material,null);assert.match(budgetHeadline(b),/unpriced/);
 s.inputs.spacingMm="invalid";
 assert.equal(summarize(geometry,s).status,"invalid");
});
test("live geometry and baseline use exactly the same current rates",()=>{
 const s={...newAssemblyStudy(),enabled:true,baseline:geometry,rates:{paint:{material:"25",labour:"10"}}};
 const current={walls:[{...w,end:[8,0]}],ceilings:[]};
 const b=summarize(current,s);
 assert.equal(b.status,"partial");
 assert.ok(b.material>0);assert.ok(b.labour>0);assert.ok(b.delta>0);
 assert.equal(b.total,evaluateAssemblyStudy(current,s).result.total);
 assert.equal(b.delta,b.total-evaluateAssemblyStudy(geometry,s).result.total);
 assert.match(budgetHeadline(b),/^PARTIAL/);
 assert.equal(b.trades.find(t=>t.trade==="Framing").cents,null);
 assert.equal(b.hasBaseline,true);
});
test("explicit zero prices remain distinguishable from missing prices",()=>{
 const s={...newAssemblyStudy(),enabled:true,rates:{paint:{material:"0",labour:"0"}}};
 const b=summarize(geometry,s);
 assert.equal(b.status,"partial");assert.equal(b.total,0);
 assert.equal(b.material,0);assert.equal(b.labour,0);
});
test("headset budget panel exposes same estimate and baseline controls",()=>{
 const s={...newAssemblyStudy(),enabled:true,rates:{paint:{material:"25"}}};
 const b=summarize(geometry,s);
 const q={selectedWall:null,gridM:.05,axis:"auto",nudgeM:.05,pinned:false,help:false,deleteArmed:false,compact:true,budget:b,budgetOpen:true};
 const menu=buildMenuLayout(EMPTY_BUILD,"ground",EMPTY_ITEM_BROWSER,undefined,false,0,"","finished",false,undefined,undefined,q);
 assert.match(menu.title,/LIVE CONSTRUCTION BUDGET/);
 assert.equal(menu.helpLines[0],budgetHeadline(b));
 assert.ok(menu.buttons.some(b=>b.action.action==="budget-baseline"&&!b.disabled));
 assert.ok(menu.buttons.some(b=>b.action.action==="budget-clear"&&b.disabled));
 const closed=buildMenuLayout(EMPTY_BUILD,"ground",EMPTY_ITEM_BROWSER,undefined,false,0,"","finished",false,undefined,undefined,{...q,budgetOpen:false});
 assert.ok(closed.buttons.some(b=>b.action.action==="budget"));
});
