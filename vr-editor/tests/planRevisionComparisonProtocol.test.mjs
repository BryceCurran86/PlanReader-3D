import test from "node:test";
import assert from "node:assert/strict";
import {verifyPlanRevisionComparison} from "../src/planRevisionComparisonProtocol.ts";

function history(){
 return [3,2,1].map(n=>({
   revisionId:String(n).repeat(40),revisionNumber:n,
   revisionLabel:`PR-R${String(n).padStart(4,"0")}`,
   pagesRevised:[{pageIndex:0},{pageIndex:1}],
 }));
}
const revisions=history();
const old=revisions[2].revisionId, latest=revisions[0].revisionId;
function payload(){
 return {
   olderRevisionId:old,newerRevisionId:latest,
   interveningRevisionCount:2,
   affectedPageIndices:[0,1],
   changes:[2,3].map(n=>({
     revisionId:String(n).repeat(40),revisionNumber:n,
     pagesRevised:[{pageIndex:0},{pageIndex:1}],
     event:{object_id:"wall-1",field:"height"},
   })),
   reviewRevisionOnly:true,requiresApproval:true,
   geometryRedrawn:false,commercialPublicationAllowed:false,
 };
}
test("authentic ordered history comparison returns source-linked page summaries",()=>{
 const result=verifyPlanRevisionComparison(payload(),revisions,old,latest);
 assert.equal(result.interveningRevisionCount,2);
 assert.deepEqual(result.affectedPageIndices,[0,1]);
 assert.deepEqual(result.changes.map(x=>x.revisionNumber),[2,3]);
 assert.ok(!("event" in result.changes[0]),"raw correction payload must not enter UI");
});
test("browser cannot inject publish approval or source-redraw authority",()=>{
 for(const [field,value] of [
  ["commercialPublicationAllowed",true],["geometryRedrawn",true],
  ["requiresApproval",false],["reviewRevisionOnly",false],
 ]) assert.throws(()=>verifyPlanRevisionComparison(
   {...payload(),[field]:value},revisions,old,latest));
});
test("wrong order, tampered revision ids or missing intermediate step fail",()=>{
 const p=payload();
 assert.throws(()=>verifyPlanRevisionComparison(p,revisions,latest,old));
 assert.throws(()=>verifyPlanRevisionComparison(
   {...p,olderRevisionId:latest},revisions,old,latest));
 assert.throws(()=>verifyPlanRevisionComparison(
   {...p,changes:p.changes.slice(1)},revisions,old,latest));
 assert.throws(()=>verifyPlanRevisionComparison(
   {...p,changes:[{...p.changes[0],revisionId:"a".repeat(40)},p.changes[1]]},
   revisions,old,latest));
});
test("altered or incomplete affected sheet receipts fail",()=>{
 const p=payload();
 const tooFew=[{...p.changes[0],pagesRevised:[{pageIndex:0}]},p.changes[1]];
 assert.throws(()=>verifyPlanRevisionComparison(
   {...p,changes:tooFew},revisions,old,latest));
 const foreign=[{...p.changes[0],pagesRevised:[{pageIndex:0},{pageIndex:3}]},p.changes[1]];
 assert.throws(()=>verifyPlanRevisionComparison(
   {...p,changes:foreign},revisions,old,latest));
 assert.throws(()=>verifyPlanRevisionComparison(
   {...p,affectedPageIndices:[1,0]},revisions,old,latest));
});
test("unverified event type and duplicated source receipts fail",()=>{
 const p=payload();
 assert.throws(()=>verifyPlanRevisionComparison(
   {...p,changes:[{...p.changes[0],event:null},p.changes[1]]},revisions,old,latest));
 assert.throws(()=>verifyPlanRevisionComparison(
   {...p,changes:[{...p.changes[0],pagesRevised:[{pageIndex:0},{pageIndex:0}]},p.changes[1]]},
   revisions,old,latest));
});
