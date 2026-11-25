import {ITEM_CATALOGUE,getCatalogueItem,catalogueGroupLabel} from "./itemCatalogue.ts";
import type {CatalogueGroup,CatalogueItem,ItemTarget} from "./itemCatalogue.ts";
import type {ItemHit,PlacedItem} from "./itemPlacement.ts";
export type FinishContext={hit:ItemHit;entry?:PlacedItem};
const priority:CatalogueGroup[]=["paint","substrates","facades","doors","entry","sliding-doors","windows","tapware","cabinets","lights","electrical","floors","walls","bathroom","skirting","architraves","boards","roofing","window-coverings"];
export function sameFixtureFamily(a:CatalogueItem,b:CatalogueItem){
 const x=a.visual,y=b.visual;
 return a.group===b.group&&x.kind==="fixture"&&y.kind==="fixture"&&x.shape===y.shape&&x.widthM===y.widthM&&x.heightM===y.heightM&&x.depthM===y.depthM&&x.count===y.count;
}
export function contextGroups(context:FinishContext):CatalogueGroup[]{
 const old=context.entry&&getCatalogueItem(context.entry.itemId);
 if(old?.visual.kind==="fixture")return [old.group];
 const t=context.hit.target;
 const groups=priority.filter(g=>ITEM_CATALOGUE.some(i=>i.group===g&&i.targets.includes(t)));
 if(t==="opening")return groups.filter(g=>context.hit.opening?.door?["doors","entry","sliding-doors"].includes(g):context.hit.opening?.window?["windows","window-coverings"].includes(g):false);
 return groups;
}
export function contextChoices(context:FinishContext,group:CatalogueGroup):CatalogueItem[]{
 if(!contextGroups(context).includes(group))return [];
 const old=context.entry&&getCatalogueItem(context.entry.itemId);
 return ITEM_CATALOGUE.filter(i=>i.group===group&&i.targets.includes(context.hit.target)&&(!old||old.visual.kind!=="fixture"||sameFixtureFamily(old,i)));
}
export function contextTitle(c:FinishContext){
 const entry=c.entry&&getCatalogueItem(c.entry.itemId);
 return entry?.label??(c.hit.target==="opening"?(c.hit.opening?.door?"Door":"Window"):c.hit.target==="wall"?"Wall finish":c.hit.target==="floor"?"Floor finishes":c.hit.target==="ceiling"?"Ceiling finishes":"Selected "+c.hit.target);
}
export function finishGroupLabel(group:CatalogueGroup){return group==="electrical"?"Power points / switches":group==="facades"?"External finishes":catalogueGroupLabel(group);}
export function preferredFinishGroup(target:ItemTarget){return target==="wall"?"paint":target==="floor"?"floors":target==="opening"?"doors":target==="ceiling"?"paint":null;}
