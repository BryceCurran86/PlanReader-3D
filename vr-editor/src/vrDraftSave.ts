/**
 * Explicit, opt-in, local browser export/reopen of VR review drafts.
 * This file does not contain original source documents or commercial prices.
 * It never submits a draft to an authenticated publication endpoint.
 */
import { openingFits, validEditedWall, validCeiling, MAX_DRAFT_WALLS, EMPTY_BUILD } from "./buildPlacement.ts";
import type { BuildState, PlacedWall, CeilingDraft } from "./buildPlacement.ts";
import type { ItemDraft, PlacedItem } from "./itemPlacement.ts";
import { emptyItemDraft } from "./itemPlacement.ts";
import { getCatalogueItem } from "./itemCatalogue.ts";
import { scopeKey } from "./reviewDraft.ts";
import type { SceneManifest } from "./types.ts";

const record=(v:unknown):v is Record<string,unknown> =>
  typeof v==="object" && v!==null && !Array.isArray(v);
const string=(v:unknown) => typeof v==="string" && v.length>0 && v.length<250;
const finite=(v:unknown) => typeof v==="number" && Number.isFinite(v) && Math.abs(v)<=10000;
const vector=(v:unknown,n:number) => Array.isArray(v) && v.length===n && v.every(finite);
const identity=(s:SceneManifest)=>({ ...s.scope });
const scopeKeys=["workspaceId","projectId","documentId","revisionId","snapshotId",
  "sourceSha256","modelRevision"] as const;

function readWall(value:unknown,key:string,levels:ReadonlySet<string>):PlacedWall {
  if(!record(value) || value.scopeKey!==key || !string(value.proposalId) ||
    !string(value.levelId) || !levels.has(value.levelId as string) ||
    !vector(value.start,2) || !vector(value.end,2) || !finite(value.heightM) ||
    !Array.isArray(value.openings) || value.openings.length>100) throw Error("Invalid draft wall");
  const wall=value as unknown as PlacedWall;
  if(!validEditedWall(wall))throw Error("Invalid draft wall geometry");
  const ids=new Set<string>();
  for(const opening of wall.openings){
    if(!record(opening)||!string(opening.openingId)||ids.has(opening.openingId)||
      !["door","window","passage"].includes(String(opening.openingKind))||
      !openingFits(wall,opening))throw Error("Invalid draft opening");
    ids.add(opening.openingId);
  }
  for(let i=0;i<wall.openings.length;i++)for(let j=i+1;j<wall.openings.length;j++){
    const a=wall.openings[i],b=wall.openings[j];
    if(Math.min(a.offsetM+a.widthM,b.offsetM+b.widthM)-
      Math.max(a.offsetM,b.offsetM)>0.000001)throw Error("Overlapping draft openings");
  }
  return {scopeKey:key,proposalId:wall.proposalId,levelId:wall.levelId,
    start:[...wall.start],end:[...wall.end],heightM:wall.heightM,
    openings:wall.openings.map(x=>({openingId:x.openingId,openingKind:x.openingKind,
      offsetM:x.offsetM,widthM:x.widthM,heightM:x.heightM,sillHeightM:x.sillHeightM}))};
}
function readCeiling(value:unknown,key:string,levels:ReadonlySet<string>):CeilingDraft {
  if(!record(value)||value.scopeKey!==key||!string(value.proposalId)||
    !string(value.levelId)||!levels.has(value.levelId as string)||
    !vector(value.start,2)||!vector(value.end,2)||!finite(value.heightM))
    throw Error("Invalid draft ceiling");
  const ceiling=value as unknown as CeilingDraft;
  if(ceiling.heightM<=0||ceiling.heightM>20||!validCeiling(ceiling.start,ceiling.end))
    throw Error("Invalid ceiling dimensions");
  return {scopeKey:key,proposalId:ceiling.proposalId,levelId:ceiling.levelId,
    start:[...ceiling.start],end:[...ceiling.end],heightM:ceiling.heightM};
}
function readGeometry(raw:unknown,key:string,levels:ReadonlySet<string>){
  if(!record(raw)||!Array.isArray(raw.walls)||!Array.isArray(raw.ceilings)||
    raw.walls.length>MAX_DRAFT_WALLS||raw.ceilings.length>MAX_DRAFT_WALLS)
    throw Error("Draft exceeds safe geometry limits");
  const walls=raw.walls.map(value=>readWall(value,key,levels));
  const ceilings=raw.ceilings.map(value=>readCeiling(value,key,levels));
  const ids=[...walls.map(x=>x.proposalId),...ceilings.map(x=>x.proposalId)];
  if(new Set(ids).size!==ids.length)throw Error("Duplicate draft IDs");
  return {walls,ceilings};
}
function readItems(value:unknown,key:string):PlacedItem[] {
  if(!Array.isArray(value)||value.length>250)throw Error("Too many saved draft items");
  const ids=new Set<string>();
  return value.map(x=>{
    if(!record(x)||!string(x.id)||ids.has(x.id)||!string(x.itemId)||
      !string(x.hostId)||!getCatalogueItem(x.itemId as string)?.targets.includes(x.target as never)||
      !vector(x.point,3)||!vector(x.normal,3)||![1,-1].includes(x.side as number)||
      Math.abs(Math.hypot(...(x.normal as number[]))-1)>0.01||
      !Number.isInteger(x.turn)||Number(x.turn)<0||Number(x.turn)>3)
      throw Error("Invalid saved catalogue item");
    const anchor=x.anchor;
    if(anchor!==undefined && (!record(anchor) ||
      (anchor.kind==="wall" ? !finite(anchor.offsetM) :
       anchor.kind==="ceiling" ? ![anchor.xFraction,anchor.zFraction].every(
          value=>typeof value==="number" && Number.isFinite(value) && value>=0 && value<=1) : true)))
      throw Error("Invalid saved attachment coordinates");
    const opening=x.opening;
    if(opening!==undefined && (!record(opening)||
      !finite(opening.widthM)||!finite(opening.heightM)||
      opening.widthM<=0||opening.heightM<=0||typeof opening.door!=="boolean"||
      (opening.window!==undefined&&typeof opening.window!=="boolean")))
      throw Error("Invalid saved opening witness");
    if(x.roofEdgeKey!==undefined&&!string(x.roofEdgeKey))
      throw Error("Invalid saved roof edge");
    ids.add(x.id as string);
    return {id:x.id,itemId:x.itemId,hostId:x.hostId,target:x.target,
      point:[...(x.point as number[])],normal:[...(x.normal as number[])],side:x.side,
      turn:x.turn, ...(anchor?{anchor:{...anchor}}:{}),
      ...(opening?{opening:{...opening}}:{}),
      ...(x.roofEdgeKey?{roofEdgeKey:x.roofEdgeKey}:{})} as PlacedItem;
  });
}
export type RestoredVrDraft = {build:BuildState;itemDraft:ItemDraft};
export function saveVrReview(scene:SceneManifest,build:BuildState,items:ItemDraft|null):string {
  const key=scopeKey(scene);
  return JSON.stringify({format:"planreader-local-vr-review",schema:1,
    previewOnly:true,commercialPublicationAllowed:false,source:identity(scene),
    sourceKey:key,exportedAt:new Date().toISOString(),
    geometry:{walls:build.walls,ceilings:build.ceilings},
    history:build.history.slice(-50),future:(build.future??[]).slice(-50),
    catalogue:items?.sourceKey===key ? {
      items:items.items,history:items.history.slice(-50),future:(items.future??[]).slice(-50)
    } : {items:[],history:[],future:[]}},null,2);
}
export function restoreVrReview(scene:SceneManifest,data:unknown):RestoredVrDraft {
  if(!record(data)||data.format!=="planreader-local-vr-review"||data.schema!==1||
    data.previewOnly!==true||data.commercialPublicationAllowed!==false||
    data.sourceKey!==scopeKey(scene)||!record(data.source)||
    scopeKeys.some(field=>data.source[field]!==scene.scope[field]))
    throw Error("Draft file belongs to a different source revision or is not a review-only file");
  const levels=new Set(scene.objects.map(x=>x.levelId).filter((x):x is string=>!!x));
  const geometry=readGeometry(data.geometry,scopeKey(scene),levels);
  const history=(data.history??[]),future=(data.future??[]);
  if(!Array.isArray(history)||!Array.isArray(future)||history.length>50||future.length>50)
    throw Error("Invalid draft history");
  const past=history.map(x=>readGeometry(x,scopeKey(scene),levels));
  const ahead=future.map(x=>readGeometry(x,scopeKey(scene),levels));
  const catalogue=data.catalogue;
  if(!record(catalogue)||!Array.isArray(catalogue.history)||
    !Array.isArray(catalogue.future)||catalogue.history.length>50||catalogue.future.length>50)
    throw Error("Invalid item draft history");
  const items=readItems(catalogue.items,scopeKey(scene));
  const itemHistory=catalogue.history.map(x=>readItems(x,scopeKey(scene)));
  const itemFuture=catalogue.future.map(x=>readItems(x,scopeKey(scene)));
  return {build:{...EMPTY_BUILD,...geometry,history:past,future:ahead,tool:null,start:null},
    itemDraft:{...emptyItemDraft(scopeKey(scene)),items,history:itemHistory,future:itemFuture}};
}
