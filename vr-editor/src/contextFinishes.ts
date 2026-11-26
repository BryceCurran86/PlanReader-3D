import {ITEM_CATALOGUE,getCatalogueItem,catalogueGroupLabel} from "./itemCatalogue.ts";
import type {CatalogueGroup,CatalogueItem,ItemTarget} from "./itemCatalogue.ts";
import type {ItemHit,PlacedItem,Vector} from "./itemPlacement.ts";
export type FinishContext={hit:ItemHit;entry?:PlacedItem;worldPoint?:Vector};
const priority:CatalogueGroup[]=["paint","substrates","facades","doors","entry","sliding-doors","windows","tapware","cabinets","lights","electrical","floors","walls","bathroom","skirting","architraves","boards","roofing","window-coverings"];
export function sameFixtureFamily(a:CatalogueItem,b:CatalogueItem){
 const x=a.visual,y=b.visual;
 return a.group===b.group&&x.kind==="fixture"&&y.kind==="fixture"&&x.shape===y.shape&&x.widthM===y.widthM&&x.heightM===y.heightM&&x.depthM===y.depthM&&x.count===y.count;
}
const finishCandidates=ITEM_CATALOGUE.filter(i=>i.visual.kind!=="fixture"&&i.visual.kind!=="design-assembly");
export function contextGroups(context:FinishContext):CatalogueGroup[]{
 const old=context.entry&&getCatalogueItem(context.entry.itemId);
 if(old?.visual.kind==="fixture")return [old.group];
 const t=context.hit.target;
 const groups=priority.filter(g=>finishCandidates.some(i=>i.group===g&&i.targets.includes(t)));
 if(t==="opening")return groups.filter(g=>context.hit.opening?.door?["doors","entry","sliding-doors"].includes(g):context.hit.opening?.window?["windows","window-coverings"].includes(g):false);
 return groups;
}
export function contextChoices(context:FinishContext,group:CatalogueGroup):CatalogueItem[]{
 if(!contextGroups(context).includes(group))return [];
 const old=context.entry&&getCatalogueItem(context.entry.itemId);
 return ITEM_CATALOGUE.filter(i=>i.group===group&&i.targets.includes(context.hit.target)&&(old?.visual.kind==="fixture"?sameFixtureFamily(old,i):i.visual.kind!=="fixture"&&i.visual.kind!=="design-assembly"));
}
/** Enter the most likely finish immediately, while retaining Back for all groups. */
export function initialFinishGroup(context:FinishContext):CatalogueGroup|null {
 const groups=contextGroups(context);
 if(context.hit.target==="opening")return null; // retain hardware choices
 if(groups.length===1)return groups[0];
 const preferred=preferredFinishGroup(context.hit.target);
 return preferred&&groups.includes(preferred)?preferred:null;
}
export function contextTitle(c:FinishContext){
 const entry=c.entry&&getCatalogueItem(c.entry.itemId);
 return entry?.label??(c.hit.target==="opening"?(c.hit.opening?.door?"Door":"Window"):c.hit.target==="wall"?"Wall finish":c.hit.target==="floor"?"Floor finishes":c.hit.target==="ceiling"?"Ceiling finishes":"Selected "+c.hit.target);
}
export function finishGroupLabel(group:CatalogueGroup){return group==="electrical"?"Power points / switches":group==="facades"?"External finishes":catalogueGroupLabel(group);}
export function preferredFinishGroup(target:ItemTarget){return target==="wall"?"paint":target==="floor"?"floors":target==="opening"?"doors":target==="ceiling"?"paint":null;}

/** Do not keep editing a removed or rehosted fixture from an old grip selection. */
export function refreshFinishContext(context:FinishContext,items:readonly PlacedItem[]):FinishContext|null{
 const old=context.entry&&getCatalogueItem(context.entry.itemId);
 if(old?.visual.kind!=="fixture")return context;
 const live=items.find(p=>p.id===context.entry!.id);
 const next=live&&getCatalogueItem(live.itemId);
 if(!live||!next||!sameFixtureFamily(old,next)||live.hostId!==context.hit.hostId||live.target!==context.hit.target)return null;
 return live===context.entry?context:{...context,hit:live,entry:live};
}
/** Read the actual committed draft, not the palette's original selection snapshot. */
export function activeContextFinish(context:FinishContext,group:CatalogueGroup|null,items:readonly PlacedItem[]):string|undefined{
 if(!group)return;
 const refreshed=refreshFinishContext(context,items);
 if(!refreshed)return;
 const selected=refreshed.entry&&getCatalogueItem(refreshed.entry.itemId);
 if(selected?.visual.kind==="fixture")return selected.group===group?selected.id:undefined;
 const hit=refreshed.hit;
 const sideSensitive=hit.target==="wall"||hit.target==="opening";
 return [...items].reverse().find(p=>{
  const i=getCatalogueItem(p.itemId);
  if(p.hostId!==hit.hostId||p.target!==hit.target||i?.group!==group)return false;
  if(i.visual.kind==="fixture"||i.visual.kind==="design-assembly")return false;
  // Opening styles covering both sides share one slot; coverings retain side.
  const shared=hit.target==="opening"&&(i.visual.kind==="entry"||i.visual.kind==="opening-style"&&i.visual.type!=="covering");
  return !sideSensitive||shared||p.side===hit.side;
 })?.itemId;
}
