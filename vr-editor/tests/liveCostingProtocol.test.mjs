import test from "node:test";
import assert from "node:assert/strict";
import { verifyLiveCostingResponse } from "../src/liveCostingProtocol.ts";

const request = {
  commandId:"c1",targetObjectId:"wall-1",targetRevisionHash:"rev1",
  workspaceId:"w1",snapshotId:"snap1",
};
const before = {
  material:"115.20",waste:"5.76",labour:"76.80",
  subcontract:"0.00",plant:"9.60",direct:"207.36",
  overhead:"20.74",contingency:"0.00",costBeforeMargin:"228.10",
  margin:"57.03",sellExTax:"285.13",tax:"28.51",sellIncTax:"313.64",
};
const after = {
  material:"144.00",waste:"7.20",labour:"96.00",
  subcontract:"0.00",plant:"12.00",direct:"259.20",
  overhead:"25.92",contingency:"0.00",costBeforeMargin:"285.12",
  margin:"71.28",sellExTax:"356.40",tax:"35.64",sellIncTax:"392.04",
};
function toCents(s){const neg=s.startsWith("-");const [i,f]=(neg?s.slice(1):s).split(".");
const n=BigInt(i)*100n+BigInt(f);return neg?-n:n;}
function fromCents(n){return (n<0n?"-":"")+String((n<0n?-n:n)/100n)+"."+
String((n<0n?-n:n)%100n).padStart(2,"0");}
const delta=Object.fromEntries(Object.keys(before).map(k=>[
  k,fromCents(toCents(after[k])-toCents(before[k]))
]));
function make(){
 const quantityPreview={
  accepted:true,validationState:"valid_preview_only",
  commandId:"c1",targetObjectId:"wall-1",
  previousObjectRevision:"rev1",previewObjectRevision:"rev2",
  requiresApproval:true,persisted:false,
  commercialPublicationAllowed:false,blockingReasons:[],
  quantityImpacts:[
   {target:"wall_gross_area",status:"recalculated",
    oldValue:9.6,proposedValue:12,unit:"m²",reason:null},
   {target:"wall_net_area",status:"manual_review_required",
    oldValue:null,proposedValue:null,unit:"m²",reason:"source unresolved"},
  ],
 };
 return structuredClone({
  accepted:true,quantityPreview,
  costingPreview:{
   accepted:true,validationState:"cost_preview_only",
   commandId:"c1",targetObjectId:"wall-1",
   previousObjectRevision:"rev1",previewObjectRevision:"rev2",
   workspaceId:"w1",snapshotId:"snap1",
   rateBookRevision:"rates1",currency:"AUD",taxPct:"10",contingencyPct:"0",
   pricedComplete:false,partialTotalsOnly:true,quoteReady:false,
   requiresApproval:true,persisted:false,commercialPublicationAllowed:false,
   costPreviewReceiptSha256:"b".repeat(64),
   lines:[{target:"wall_gross_area",rateKey:"paint.wall.gross",
    rateRevision:"rates1",rateEvidenceIds:["rate-source"],
    bindingEvidenceIds:["binding-source"],previousQuantity:"9.6",
    proposedQuantity:"12.0",unit:"m²",before,after,deltaIncTax:"78.40"}],
   unpriced:[{target:"wall_net_area",reason:"manual_review_or_missing_quantity"}],
   totals:{before,after,delta},
  },
 });
}
test("accepts cent-exact incomplete preview without quote authority",()=>{
 const result=verifyLiveCostingResponse(make(),request);
 assert.equal(result.costingPreview.partialTotalsOnly,true);
 assert.equal(result.costingPreview.totals.delta.sellIncTax,"78.40");
 assert.equal(result.costingPreview.quoteReady,false);
});
test("stale revisions or workspace cannot be shown as live estimates",()=>{
 for(const field of ["commandId","targetObjectId","previousObjectRevision",
  "workspaceId","snapshotId"]){
  const m=make();m.costingPreview[field]="forged";
  assert.throws(()=>verifyLiveCostingResponse(m,request),/mismatch/);
 }
 const m=make();m.quantityPreview.previewObjectRevision="stale";
 assert.throws(()=>verifyLiveCostingResponse(m,request),/mismatch/);
});
test("browser rejects forged publication, quote and persistence flags",()=>{
 for(const [key,value] of [["quoteReady",true],["persisted",true],
  ["requiresApproval",false],["commercialPublicationAllowed",true],
  ["currency","USD$"]]){
   const m=make();m.costingPreview[key]=value;
   assert.throws(()=>verifyLiveCostingResponse(m,request),/authority|mismatch/);
 }
});
test("misfooted components, totals and tax cannot be presented",()=>{
 const m=make();m.costingPreview.lines[0].after.material="1.00";
 assert.throws(()=>verifyLiveCostingResponse(m,request),/foot/);
 const n=make();n.costingPreview.totals.after.sellIncTax="999.99";
 assert.throws(()=>verifyLiveCostingResponse(n,request),/foot/);
 const o=make();o.costingPreview.lines[0].deltaIncTax="3.12";
 assert.throws(()=>verifyLiveCostingResponse(o,request),/delta/);
});
test("no unpriced quantity may vanish from partial result",()=>{
 const a=make();a.costingPreview.unpriced=[];
 assert.throws(()=>verifyLiveCostingResponse(a,request),/impacts|accounted/);
 const b=make();b.costingPreview.pricedComplete=true;
 assert.throws(()=>verifyLiveCostingResponse(b,request),/completeness|accounted/);
 const c=make();c.costingPreview.lines[0].rateEvidenceIds=[];
 assert.throws(()=>verifyLiveCostingResponse(c,request),/source-quantity-bound/);
});
test("duplicates and invalid money strings are rejected",()=>{
 const m=make();m.costingPreview.lines.push({...m.costingPreview.lines[0]});
 assert.throws(()=>verifyLiveCostingResponse(m,request),/source-quantity-bound/);
 const x=make();x.costingPreview.lines[0].before.material="NaN";
 assert.throws(()=>verifyLiveCostingResponse(x,request),/exact-cent/);
});
