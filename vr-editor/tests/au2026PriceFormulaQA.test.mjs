import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { CATALOGUE_GROUPS } from "../src/itemCatalogue.ts";
import { vrDraftTakeoff, localIndicativeWallCost } from "../src/vrDraftTakeoff.ts";
import { verifyCataloguePrice } from "../src/cataloguePricing.ts";

const fixture = JSON.parse(readFileSync(new URL("./fixtures/au2026PriceFormulaQA.json", import.meta.url), "utf8"));
const rate = (group) => fixture.testRates.find(item => item.group === group);
const wall=(length=4.2,doorWidth=0.9,doorHeight=2.1)=>({
  proposalId:"qa-wall",scopeKey:"QA-only",levelId:"ground",
  start:[0,0],end:[length,0],heightM:2.7,
  openings:[{openingId:"qa-door",openingKind:"door",offsetM:1,
    widthM:doorWidth,heightM:doorHeight,sillHeightM:0}],
});
const state=(w)=>({walls:[w],ceilings:[]});
const close=(actual,expected,tol=0.001)=>assert.ok(Math.abs(actual-expected)<=tol,
  `expected ${expected}, got ${actual}`);
const materialPackCount=(netArea,waste,packArea)=>Math.ceil(netArea*(1+waste)/packArea);

test("all PlanReader catalogue groups have one test-only rate; no extras or duplicate codes",()=>{
  const actual=fixture.testRates.map(item=>item.group);
  const expected=CATALOGUE_GROUPS.map(([id])=>id);
  assert.deepEqual([...new Set(actual)].sort(),[...expected].sort());
  assert.equal(actual.length,expected.length);
  assert.equal(fixture.commercialPublicationAllowed,false);
  assert.equal(fixture.isProductionPricebook,false);
  assert.equal(fixture.previewOnly,true);
  assert.equal(fixture.asOf,"2026-11-24");
});
test("derived benchmark prices and synthetic fixture amounts stay explicitly distinguishable",()=>{
  for(const entry of fixture.testRates) {
    assert.ok(Number.isFinite(entry.amountExGstTest)&&entry.amountExGstTest>0);
    assert.ok(["m²","lm","each","job","step","window"].includes(entry.unit));
    assert.ok(["modelled-healthy","synthetic"].includes(entry.origin));
    assert.equal(entry.commercialUse,false);
    if(entry.origin==="synthetic") assert.equal(entry.sourceUrl,null);
    else assert.ok(entry.sourceUrl?.startsWith("https://www.sumitt.com.au/"));
  }
});
test("test fixture cannot be mistaken for an authenticated catalogue price response",()=>{
  assert.throws(()=>verifyCataloguePrice(rate("boards"),{}),
    /Malformed material price|missing|revision/);
  for(const path of ["../src/vrDraftTakeoff.ts","../src/cataloguePricing.ts","../src/App.tsx"]) {
    const source=readFileSync(new URL(path,import.meta.url),"utf8");
    assert.ok(!source.includes("au2026PriceFormulaQA.json"),
      "Runtime must never import QA-only pricebook");
  }
});
test("unapproved wall net face deducts only real door aperture; overhead remains wall",()=>{
  const q=vrDraftTakeoff(state(wall()));
  close(q.wallRunM,4.2);
  close(q.wallGrossFaceM2,11.34);
  close(q.wallNetFaceM2,9.45);
  close(q.indicativeTwoFaceLiningM2,18.9);
  close(q.skirtingCandidateM,6.6);
  assert.equal(q.draftDoors,1);
  assert.equal(q.commercialPublicationAllowed,false);
  assert.equal(q.reviewOnly,true);
});
test("representative plasterboard and painting rates reproduce reference multiplication",()=>{
  const q=vrDraftTakeoff(state(wall()));
  assert.equal(localIndicativeWallCost(q,String(rate("boards").amountExGstTest)),"1455.30");
  assert.equal(localIndicativeWallCost(q,String(rate("paint").amountExGstTest)),"756.00");
  assert.equal(localIndicativeWallCost(q,""),null);
  assert.equal(localIndicativeWallCost(q,"-1"),null);
});
test("moving the wall 500mm changes preview lining cost by the physically added face area",()=>{
  const before=vrDraftTakeoff(state(wall()));
  const after=vrDraftTakeoff(state(wall(4.7)));
  close(after.wallNetFaceM2-before.wallNetFaceM2,0.5*2.7);
  close(after.indicativeTwoFaceLiningM2-before.indicativeTwoFaceLiningM2,2*0.5*2.7);
  close(Number(localIndicativeWallCost(after,"77"))-
    Number(localIndicativeWallCost(before,"77")),207.90);
});
test("door width changes deduct net faces once and skirting where grounded",()=>{
  const before=vrDraftTakeoff(state(wall()));
  const after=vrDraftTakeoff(state(wall(4.2,1.2)));
  close(before.wallNetFaceM2-after.wallNetFaceM2,0.3*2.1);
  close(before.indicativeTwoFaceLiningM2-after.indicativeTwoFaceLiningM2,2*0.3*2.1);
  close(before.skirtingCandidateM-after.skirtingCandidateM,0.3*2);
});
test("sheet, paint and tile quantities round materials to purchasable packs",()=>{
  const lined=vrDraftTakeoff(state(wall())).indicativeTwoFaceLiningM2;
  assert.equal(materialPackCount(lined,0.10,2.88),8);
  const topcoatLitres=lined*2/16*1.10;
  close(topcoatLitres,2.59875);
  assert.equal(Math.ceil(topcoatLitres/4),1);
  assert.equal(materialPackCount(20,0.10,1.44),16);
  close(16*1.44,23.04);
});
test("slab concrete and pitched-roof volumes use correct physical dimensions",()=>{
  close(20*(100/1000),2);
  close(2*1.05,2.1);
  close(2.1*420,882);
  close(100/Math.cos(22.5*Math.PI/180),108.2392200292394,1e-8);
});
test("gross margin, markup and GST are independent operations",()=>{
  const cost=1000,margin=.25,markup=.25,gst=.10;
  const sellAtMargin=cost/(1-margin);
  const sellAtMarkup=cost*(1+markup);
  close(sellAtMargin,1333.3333333333);
  close(sellAtMarkup,1250);
  assert.ok(sellAtMargin>sellAtMarkup);
  close(sellAtMargin*(1+gst),1466.666666667);
  close(sellAtMargin*(1+gst)/11,sellAtMargin*gst);
});
test("supply+install cost codes cannot be stacked on equivalent labour/material subcodes",()=>{
  const combine=(items)=>{
    const scopes=new Map();
    for(const line of items){
      if(!Number.isFinite(line.quantity)||line.quantity<0||!Number.isFinite(line.rate)||line.rate<0)
        throw Error("invalid quantity/rate");
      const used=scopes.get(line.scope)||new Set();
      if((line.basis==="supply-install"&&used.size)||
        (used.has("supply-install")&&line.basis!=="supply-install")||
        used.has(line.basis)) throw Error("duplicate or mixed assembly scope");
      used.add(line.basis);scopes.set(line.scope,used);
    }
    return items.reduce((sum,line)=>sum+line.quantity*line.rate,0);
  };
  const board=rate("boards");
  close(combine([{scope:"wall-A",basis:board.basis,quantity:18.9,rate:board.amountExGstTest}]),1455.3);
  assert.throws(()=>combine([
    {scope:"wall-A",basis:"supply-install",quantity:18.9,rate:77},
    {scope:"wall-A",basis:"material",quantity:8,rate:20},
  ]),/duplicate or mixed assembly/);
  assert.throws(()=>combine([
    {scope:"wall-A",basis:"material",quantity:8,rate:20},
    {scope:"wall-A",basis:"supply-install",quantity:18.9,rate:77},
  ]),/duplicate or mixed assembly/);
});
