import test from "node:test";
import assert from "node:assert/strict";
import {DesktopRenderGovernor,adaptiveRenderQuality} from "../src/visualRealism.ts";
import {createCatalogueFixture} from "../src/catalogueFixtures.ts";
test("desktop governor suspends loading and yields after slow frames",()=>{
 const g=new DesktopRenderGovernor();
 assert.equal(g.allow(0,"high",true),false);
 assert.equal(g.allow(0,"high",false),true);
 g.complete(0,80);
 assert.equal(g.allow(81,"high",false),false);
 assert.equal(g.allow(140,"high",false),true);
 g.complete(140,80);g.complete(280,80);
 assert.equal(g.cap,1);
 for(let i=1;i<=3;i++)g.complete(280+i*140,80);
 assert.equal(g.cap,0);assert.equal(adaptiveRenderQuality("high",g.cap),"performance");
 assert.equal(g.allow(710,"high",true),false);
 assert.equal(g.allow(711,"high",false),true);
 g.reset();assert.equal(g.cap,2);
});
test("cabinet joinery preserves worktop identity and draw count",()=>{
 const spec={kind:"fixture",shape:"cabinet",widthM:.9,heightM:.9,depthM:.6,count:2,color:0xeeeae1,metalness:0};
 const {group,worktop}=createCatalogueFixture(spec,"floor");
 assert.equal(group.children.length,13);assert.equal(worktop.name,"Bevelled benchtop");
 assert.ok(group.children.includes(worktop));assert.equal(group.children.filter(o=>o.name==="Radiused cabinet front").length,2);
 assert.equal(group.children.filter(o=>o.name==="Cabinet pull").length,2);
 assert.equal(worktop.position.y,spec.heightM*.9765);
});
test("toilet now has an actual hollow bowl and open seat",()=>{
 const {group}=createCatalogueFixture({kind:"fixture",shape:"toilet",widthM:.38,heightM:.82,depthM:.67,count:1,color:0xf0ece2,metalness:0},"floor");
 assert.ok(group.children.some(o=>o.name==="Recessed toilet bowl"));
 assert.equal(group.children.find(o=>o.name==="Open toilet seat").geometry.type,"TorusGeometry");
 assert.equal(group.children.length,5);
});
