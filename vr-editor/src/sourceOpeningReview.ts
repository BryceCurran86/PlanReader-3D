import type {DisplayGeometry} from "./types";
export type ReviewOpening={openingId:string;kind:"door"|"window"|"void";offsetM:number;sillM:number;widthM:number;heightM:number;sheet:string|null;page:number|null};
export type OpeningReview={recordCount:number;positioned:ReviewOpening[];status:"review_only"};
export function validOpeningReview(value:unknown,geometry:DisplayGeometry|null):value is OpeningReview{
 if(!value||typeof value!=="object")return false;
 const r=value as OpeningReview;
 if(r.status!=="review_only"||!Number.isSafeInteger(r.recordCount)||r.recordCount<1||!Array.isArray(r.positioned)||r.positioned.length>100||r.positioned.length>r.recordCount)return false;
 if(!r.positioned.length)return true;
 if(!geometry||geometry.kind!=="wallFace")return false;
 const length=Math.hypot(geometry.end[0]-geometry.start[0],geometry.end[1]-geometry.start[1]);
 const ids=new Set<string>();
 for(const o of r.positioned){
  if(!o||typeof o!=="object"||typeof o.openingId!=="string"||!o.openingId||o.openingId.length>200||ids.has(o.openingId)||!["door","window","void"].includes(o.kind))return false;
  if(![o.offsetM,o.sillM,o.widthM,o.heightM].every(v=>typeof v==="number"&&Number.isFinite(v))||o.offsetM<0||o.sillM<0||o.widthM<=0||o.heightM<=0||o.offsetM+o.widthM>length+1e-7||o.sillM+o.heightM>geometry.heightM+1e-7||o.kind==="door"&&o.sillM>.01)return false;
  if(!(o.sheet===null||typeof o.sheet==="string"&&o.sheet.length<=200)||!(o.page===null||Number.isSafeInteger(o.page)&&o.page>0))return false;
  ids.add(o.openingId);
 }
 for(let i=0;i<r.positioned.length;i++)for(let j=i+1;j<r.positioned.length;j++){
  const a=r.positioned[i],b=r.positioned[j];
  if(Math.min(a.offsetM+a.widthM,b.offsetM+b.widthM)-Math.max(a.offsetM,b.offsetM)>1e-7&&Math.min(a.sillM+a.heightM,b.sillM+b.heightM)-Math.max(a.sillM,b.sillM)>1e-7)return false;
 }
 return true;
}
export function reviewOpeningCorners(g:Extract<DisplayGeometry,{kind:"wallFace"}>,o:ReviewOpening):[number,number,number][]{
 const l=Math.hypot(g.end[0]-g.start[0],g.end[1]-g.start[1]),ux=(g.end[0]-g.start[0])/l,uz=(g.end[1]-g.start[1])/l;
 const p=(d:number,h:number):[number,number,number]=>[g.start[0]+ux*d,h,g.start[1]+uz*d];
 return [p(o.offsetM,o.sillM),p(o.offsetM,o.sillM+o.heightM),p(o.offsetM+o.widthM,o.sillM+o.heightM),p(o.offsetM+o.widthM,o.sillM),p(o.offsetM,o.sillM)];
}
