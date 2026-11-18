/** Validate a private, review-only original PlanReader revision comparison. */
import type { SavedPlanRevision } from "./planRevisionProtocol.ts";

const SHA40=/^[0-9a-f]{40}$/;
function obj(input:unknown):Record<string,unknown>{
  if(!input||typeof input!=="object"||Array.isArray(input))
    throw Error("Malformed revision comparison");
  return input as Record<string,unknown>;
}
export interface PlanRevisionChangeSummary {
  revisionId:string;
  revisionNumber:number;
  pageIndices:number[];
}
export interface VerifiedPlanRevisionComparison {
  olderRevisionId:string;
  newerRevisionId:string;
  interveningRevisionCount:number;
  affectedPageIndices:number[];
  changes:PlanRevisionChangeSummary[];
}

export function verifyPlanRevisionComparison(
  raw:unknown,
  history:readonly SavedPlanRevision[],
  olderId:string,
  newerId:string,
):VerifiedPlanRevisionComparison{
  if(!SHA40.test(olderId)||!SHA40.test(newerId))
    throw Error("Invalid immutable revision selection");
  const source=obj(raw);
  const byId=new Map(history.map(r=>[r.revisionId,r]));
  if(byId.size!==history.length)
    throw Error("Duplicate revision history identities");
  const old=byId.get(olderId),newer=byId.get(newerId);
  if(!old||!newer||old.revisionNumber>=newer.revisionNumber)
    throw Error("Selection is not an older-to-newer revision range");
  const distance=newer.revisionNumber-old.revisionNumber;
  if(distance<1||distance>200 ||
     source.olderRevisionId!==olderId||source.newerRevisionId!==newerId ||
     source.interveningRevisionCount!==distance||
     source.reviewRevisionOnly!==true||source.requiresApproval!==true||
     source.geometryRedrawn!==false||source.commercialPublicationAllowed!==false ||
     !Array.isArray(source.changes)||source.changes.length!==distance||
     !Array.isArray(source.affectedPageIndices))
    throw Error("Unverified revision comparison range or review status");

  const changes:PlanRevisionChangeSummary[]=[];
  const affected=new Set<number>();
  for(let i=0;i<source.changes.length;i++){
    const rawChange=obj(source.changes[i]);
    const number=old.revisionNumber+i+1;
    const expected=history.find(r=>r.revisionNumber===number);
    if(!expected||rawChange.revisionId!==expected.revisionId ||
       rawChange.revisionNumber!==number||
       !Array.isArray(rawChange.pagesRevised)||rawChange.pagesRevised.length<1||
       !rawChange.event||typeof rawChange.event!=="object"||
       Array.isArray(rawChange.event))
      throw Error("Unverified intervening saved revision");
    const pageIndices:number[]=[];
    for(const rawPage of rawChange.pagesRevised){
      const page=obj(rawPage);
      if(!Number.isSafeInteger(page.pageIndex)||Number(page.pageIndex)<0)
        throw Error("Invalid affected page index");
      const index=Number(page.pageIndex);
      if(pageIndices.includes(index)||
         !expected.pagesRevised.some(p=>p.pageIndex===index))
        throw Error("Unverified affected page ownership");
      pageIndices.push(index);
      affected.add(index);
    }
    if(pageIndices.length!==expected.pagesRevised.length ||
       expected.pagesRevised.some(p=>!pageIndices.includes(p.pageIndex)))
      throw Error("Partial related-page evidence");
    changes.push({revisionId:expected.revisionId,revisionNumber:number,
                  pageIndices:pageIndices.sort((a,b)=>a-b)});
  }
  const expectedPages=[...affected].sort((a,b)=>a-b);
  const claimedPages=source.affectedPageIndices;
  if(claimedPages.length!==expectedPages.length ||
     claimedPages.some((v,i)=>v!==expectedPages[i]))
    throw Error("Comparison page union differs from history");
  return {
    olderRevisionId:olderId,newerRevisionId:newerId,
    interveningRevisionCount:distance,
    affectedPageIndices:expectedPages,changes,
  };
}
