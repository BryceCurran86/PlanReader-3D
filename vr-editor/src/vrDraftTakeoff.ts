/**
 * Geometry-only local VR assembly schedule. It is not a quantity issuer and
 * cannot grant pricing or source authority. Components requiring an authenticated
 * assembly profile remain unpriced/unquantified here.
 */
import type {BuildState} from "./buildPlacement.ts";
import {planLength} from "./buildPlacement.ts";

export type VrDraftTakeoff = {
  draftWalls:number; draftOpenings:number; draftDoors:number; draftWindows:number;
  wallRunM:number; wallGrossFaceM2:number; wallNetFaceM2:number;
  indicativeTwoFaceLiningM2:number; skirtingCandidateM:number;
  ceilingCandidateM2:number; unpricedTrades:readonly string[];
  reviewOnly:true; commercialPublicationAllowed:false;
};
const round=(value:number) => Math.round(value*1000)/1000;
export function vrDraftTakeoff(state:Pick<BuildState,"walls"|"ceilings">):VrDraftTakeoff {
  let run=0,gross=0,net=0,skirting=0,doors=0,windows=0,openings=0;
  for(const wall of state.walls){
    const length=planLength(wall.start,wall.end);
    run+=length;gross+=length*wall.heightM;
    let removed=0,baseVoid=0;
    for(const opening of wall.openings){
      openings++;
      if(opening.openingKind==="door")doors++;
      if(opening.openingKind==="window")windows++;
      removed+=opening.widthM*opening.heightM;
      if(opening.sillHeightM<=0.001)baseVoid+=opening.widthM;
    }
    net+=Math.max(0,length*wall.heightM-removed);
    skirting+=Math.max(0,length-baseVoid);
  }
  const ceiling=state.ceilings.reduce((total,item)=>total+
    Math.abs((item.end[0]-item.start[0])*(item.end[1]-item.start[1])),0);
  return {draftWalls:state.walls.length,draftOpenings:openings,
    draftDoors:doors,draftWindows:windows,wallRunM:round(run),
    wallGrossFaceM2:round(gross),wallNetFaceM2:round(net),
    indicativeTwoFaceLiningM2:round(net*2),
    skirtingCandidateM:round(skirting*2),ceilingCandidateM2:round(ceiling),
    unpricedTrades:["framing and bracing (assembly profile required)",
      "insulation and plasterboard specification",
      "electrical and plumbing services",
      "door/window schedules and installation",
      "roof, ceiling and finishes"],reviewOnly:true,commercialPublicationAllowed:false};
}
export function localIndicativeWallCost(takeoff:VrDraftTakeoff,rateAudPerM2:string):string|null {
  if(!/^(?:0|[1-9][0-9]{0,5})(?:\.[0-9]{1,2})?$/.test(rateAudPerM2))return null;
  const cents=Math.round(Number(rateAudPerM2)*100);
  if(!Number.isSafeInteger(cents)||cents<=0)return null;
  const quantityMilli=Math.round(takeoff.indicativeTwoFaceLiningM2*1000);
  const totalCents=Math.round(quantityMilli*cents/1000);
  return Number.isSafeInteger(totalCents)?(totalCents/100).toFixed(2):null;
}
